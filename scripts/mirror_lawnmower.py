#!/usr/bin/env python3
"""
mirror_lawnmower.py — robomower-style incremental mirror of kylepounds.com.

THE PROBLEM
-----------
kylepounds.com (GlowHost) rate-blocks an IP after it downloads too many full
pages in one go — wget pulling all ~2,700 multi-MB pages tripped it around page
~84. But it ALSO ignores If-Modified-Since, so wget --timestamping re-downloads
everything every night and keeps tripping the block.

THE INSIGHT (measured)
----------------------
The block is triggered by BODY DOWNLOADS (bandwidth), not by requests. Cheap
HEAD requests sail through (400 HEADs = 0 blocks). The server sends a reliable
Last-Modified + Content-Length on HEAD. So:

  * HEAD the whole inventory (light, no block) to find what CHANGED.
  * GET only the changed/new pages, BOUNDED per run to stay under the body
    ceiling.
  * Like a robot mower: mow a safe batch, and if we ever DO get blocked, retreat
    and resume next run from where we left off — over a few days we complete a
    full cycle, then start over.

BLOCK vs ANOMALY (so we never act on a false reading)
-----------------------------------------------------
  * Lots of OK responses, then a run of connection-errors/403/429  -> BLOCKED:
    real GlowHost throttling. Stop, save progress, resume next run.
  * Failures from the very start with ~no OK responses              -> ANOMALY:
    NOT normal throttling (DNS/cert/total ban/our bug). Flag loudly; don't
    pretend it's a normal block.
  * Worked through the batch fine                                   -> HEALTHY.

STATE (JSON, persisted between runs — lives on the VPS, pulled by the runner):
  { "cycle_started": "<iso>",
    "pending_fetch": ["<url>", ...],          # changed pages awaiting GET
    "pages": { "<url>": {"lm","cl","lc","ft"} } }   # lc=last_checked ft=last_fetched

Usage:
  mirror_lawnmower.py --state state.json --out ./mirror-output --host kylepounds.com \
      [--seed URL ...] [--max-checks 4000] [--max-fetches 50] [--wait 0.15] \
      [--record-only]            # bootstrap: HEAD+record signatures, never GET
"""
import argparse, json, os, sys, time, urllib.parse, urllib.request, urllib.error
from html.parser import HTMLParser

UA = "Mozilla/5.0 (compatible; kylepounds-mirror/3.0; +https://kylepounds.org)"
FAIL_STREAK = 6     # consecutive block-signals -> stop (we're blocked)
MIN_OK = 15         # fewer OKs than this before a stall => anomaly, not a block


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.hrefs = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.hrefs.append(v)


def enc(url):
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(urllib.parse.unquote(p.path)), "", ""))


# Response classes
OK, NOTFOUND, BLOCKSIG = "ok", "404", "block"


def head(url, timeout=15):
    try:
        req = urllib.request.Request(enc(url), method="HEAD", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return OK, r.headers.get("Last-Modified", ""), r.headers.get("Content-Length", ""), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return (NOTFOUND if e.code == 404 else BLOCKSIG), "", "", ""
    except Exception:
        return BLOCKSIG, "", "", ""


def fetch(url, timeout=40):
    req = urllib.request.Request(enc(url), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return OK, r.read(), r.headers.get("Last-Modified", ""), r.headers.get("Content-Length", "")


def url_to_path(out_dir, host, url):
    p = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(p.path)
    if path.endswith("/") or path == "":
        path += "index.html"
    return os.path.join(out_dir, host, path.lstrip("/"))


def is_html(url, ctype):
    return ("html" in (ctype or "").lower()) or url.lower().endswith((".html", ".htm", "/"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--host", default="kylepounds.com")
    ap.add_argument("--seed", nargs="*", default=[])
    ap.add_argument("--seed-file")
    ap.add_argument("--max-checks", type=int, default=4000, help="HEAD budget per run")
    ap.add_argument("--max-fetches", type=int, default=50, help="GET budget per run (stay under the body ceiling)")
    ap.add_argument("--wait", type=float, default=0.15, help="seconds between requests")
    ap.add_argument("--record-only", action="store_true", help="bootstrap: HEAD+record, never GET")
    args = ap.parse_args()

    st = {"cycle_started": now(), "pending_fetch": [], "pages": {}}
    if os.path.exists(args.state):
        with open(args.state) as f:
            st.update(json.load(f))
    pages = st["pages"]
    cycle_started = st["cycle_started"]

    seeds = list(args.seed)
    if args.seed_file and os.path.exists(args.seed_file):
        seeds += [l.strip() for l in open(args.seed_file) if l.strip() and not l.startswith("#")]

    # Build the HEAD work list: not-yet-checked-this-cycle pages (oldest first) + seeds.
    due = [u for u, m in pages.items() if m.get("lc", "") < cycle_started]
    due.sort(key=lambda u: pages[u].get("lc", ""))
    queue = list(dict.fromkeys(seeds + due))   # de-dup, seeds first
    in_queue = set(queue)
    # Register every queued URL in the inventory NOW (lc='' => still due this
    # cycle) so a per-run budget that leaves some unprocessed doesn't lose them —
    # they carry to the next run (oldest-checked-first) and the cycle only
    # completes once the whole inventory is genuinely swept.
    for u in queue:
        pages.setdefault(u, {})

    ok = blocked = streak = checks = 0
    blocked_flag = False
    pending = list(st.get("pending_fetch", []))

    # ---- Phase 1: HEAD (cheap) to detect changes ----
    while queue and checks < args.max_checks and not blocked_flag:
        url = queue.pop(0)
        cls, lm, cl, ctype = head(url)
        checks += 1
        time.sleep(args.wait)
        if cls == BLOCKSIG:
            blocked += 1; streak += 1
            if streak >= FAIL_STREAK:
                blocked_flag = True
            continue
        streak = 0; ok += 1
        if cls == NOTFOUND:
            pages.setdefault(url, {})["lc"] = now()   # definitive; keep our copy
            continue
        if not is_html(url, ctype):
            pages.setdefault(url, {})["lc"] = now()
            continue
        prev = pages.get(url, {})
        changed = prev.get("lm") != lm or prev.get("cl") != cl or not prev.get("ft")
        pages.setdefault(url, {})
        pages[url]["lc"] = now()
        if args.record_only:
            pages[url].update({"lm": lm, "cl": cl, "ft": now()})  # trust on-disk copy
        elif changed and url not in pending:
            pages[url].update({"lm": lm, "cl": cl})
            pending.append(url)

    # ---- Phase 2: GET changed/new pages, bounded ----
    fetched = 0
    if not args.record_only and not blocked_flag:
        still = []
        for url in pending:
            if fetched >= args.max_fetches or blocked_flag:
                still.append(url); continue
            try:
                _, body, lm2, cl2 = fetch(url)
                time.sleep(args.wait)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue  # gone; keep our copy
                blocked += 1; streak += 1
                still.append(url)
                if streak >= FAIL_STREAK:
                    blocked_flag = True
                continue
            except Exception:
                blocked += 1; streak += 1; still.append(url)
                if streak >= FAIL_STREAK:
                    blocked_flag = True
                continue
            streak = 0; ok += 1; fetched += 1
            dest = url_to_path(args.out, args.host, url)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(body)
            pages.setdefault(url, {}).update({"lm": lm2 or pages.get(url, {}).get("lm", ""),
                                              "cl": cl2 or pages.get(url, {}).get("cl", ""),
                                              "ft": now(), "lc": now()})
            # discover new pages from this changed page
            try:
                lp = LinkParser(); lp.feed(body.decode("utf-8", "replace"))
                for href in lp.hrefs:
                    if href.startswith(("#", "mailto:", "javascript:", "tel:")):
                        continue
                    absu = urllib.parse.urljoin(url, href).split("#")[0]
                    if urllib.parse.urlparse(absu).hostname == args.host and absu not in pages and absu not in in_queue:
                        pages[absu] = {}  # registered; will be HEAD-checked next run
            except Exception:
                pass
        pending = still

    # ---- Classify outcome ----
    remaining_due = sum(1 for u, m in pages.items() if m.get("lc", "") < cycle_started)
    if blocked_flag:
        status = "BLOCKED_PARTIAL" if ok >= MIN_OK else "ANOMALY"
    elif remaining_due == 0 and not pending:
        status = "CYCLE_COMPLETE"
        st["cycle_started"] = now()   # start a fresh sweep next run
    else:
        status = "HEALTHY_PARTIAL"

    st["pending_fetch"] = pending
    st["pages"] = pages
    tmp = args.state + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, separators=(",", ":"))
    os.replace(tmp, args.state)

    summary = {"status": status, "checked": checks, "ok": ok, "block_signals": blocked,
               "fetched": fetched, "pending": len(pending), "remaining_due": remaining_due,
               "inventory": len(pages)}
    print("LAWNMOWER " + json.dumps(summary))
    if status == "ANOMALY":
        print("::warning::ANOMALY — failed almost immediately (ok=%d). NOT normal GlowHost "
              "throttling; check connectivity/cert/total-ban before assuming a block." % ok, file=sys.stderr)
    # Exit 0 always (blocked is an expected, handled state — never red-fail the job).


if __name__ == "__main__":
    main()
