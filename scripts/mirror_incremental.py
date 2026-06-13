#!/usr/bin/env python3
"""
mirror_incremental.py — lightweight change detection for the kylepounds.com mirror.

WHY: kylepounds.com ignores If-Modified-Since (conditional GET returns the full
body, not 304), so `wget --timestamping` re-downloads the entire site every
night — thousands of multi-MB pages, which blew past CI time limits. But the
server DOES send a reliable `Last-Modified` (Apache file mtime) and
`Content-Length` on a cheap `HEAD`. So instead of downloading everything we:

  1. HEAD every page we already know about (tiny — headers only).
  2. Compare Last-Modified + Content-Length to a stored manifest.
  3. GET ONLY the pages that actually changed (or are new).
  4. Discover new pages from the links of changed pages.

Most nights almost nothing changed, so this is minutes of HEADs + a few GETs
instead of a full multi-hour crawl. We never delete (custodial archive).

Usage:
    mirror_incremental.py --manifest m.json --out ./mirror-output [--host kylepounds.com]
                          [--wait 0.4] [--max-new 500] [--seed URL ...]

Manifest format: { "<url>": {"lm": "<Last-Modified>", "cl": "<Content-Length>"} }
On first run (empty/missing manifest) pass --seed URLs (the section roots) to
bootstrap discovery, or point it at a manifest built from the existing mirror.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

UA = "Mozilla/5.0 (compatible; kylepounds-mirror/3.0; +https://kylepounds.org)"


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.hrefs.append(v)


def head(url, timeout=20):
    """Return (status, last_modified, content_length, content_type) or (None,...) on error."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            h = r.headers
            return r.status, h.get("Last-Modified", ""), h.get("Content-Length", ""), h.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, "", "", ""
    except Exception:
        return None, "", "", ""


def fetch(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get("Last-Modified", ""), r.headers.get("Content-Length", "")


def url_to_path(out_dir, host, url):
    """Map an absolute URL to the wget-style on-disk path: <out>/<host>/<path>."""
    p = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(p.path)
    if path.endswith("/") or path == "":
        path += "index.html"
    return os.path.join(out_dir, host, path.lstrip("/"))


def is_html(url, ctype):
    if ctype and "html" in ctype.lower():
        return True
    return url.lower().endswith((".html", ".htm", "/"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--host", default="kylepounds.com")
    ap.add_argument("--wait", type=float, default=0.4, help="seconds between requests (polite)")
    ap.add_argument("--max-new", type=int, default=500)
    ap.add_argument("--seed", nargs="*", default=[])
    ap.add_argument("--seed-file", help="file with one URL per line to add to the check queue")
    ap.add_argument("--dry-run", action="store_true", help="HEAD only; report what WOULD download")
    ap.add_argument("--record-only", action="store_true",
                    help="HEAD each URL and record its Last-Modified/Content-Length to the manifest "
                         "WITHOUT downloading. Use once to bootstrap the manifest from the URLs of the "
                         "mirror we already have on disk.")
    args = ap.parse_args()

    manifest = {}
    if os.path.exists(args.manifest):
        with open(args.manifest) as f:
            manifest = json.load(f)

    seeds = list(args.seed)
    if args.seed_file and os.path.exists(args.seed_file):
        with open(args.seed_file) as f:
            seeds += [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]

    # Work queue starts with every known URL plus any seeds.
    known = set(manifest.keys())
    queue = list(known) + [s for s in seeds if s not in known]
    seen = set()
    stats = {"checked": 0, "unchanged": 0, "changed": 0, "new": 0, "removed": 0, "errors": 0}
    new_count = 0

    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)

        status, lm, cl, ctype = head(url)
        stats["checked"] += 1
        time.sleep(args.wait)

        if status is None:
            stats["errors"] += 1
            continue
        if status == 404:
            # Page removed upstream. We KEEP our copy (archive), just note it.
            if url in manifest:
                stats["removed"] += 1
            continue
        if status >= 400:
            stats["errors"] += 1
            continue
        if not is_html(url, ctype):
            continue

        if args.record_only:
            # Bootstrap: trust the copy we already have; just record its current
            # signature so future runs can detect changes from this baseline.
            manifest[url] = {"lm": lm, "cl": cl}
            continue

        prev = manifest.get(url)
        changed = (prev is None) or (lm != prev.get("lm")) or (cl != prev.get("cl"))
        if not changed:
            stats["unchanged"] += 1
            continue

        is_new = prev is None
        if is_new:
            new_count += 1
            stats["new"] += 1
            if new_count > args.max_new:
                print(f"  [cap] hit --max-new={args.max_new}; deferring further new pages", file=sys.stderr)
                continue
        else:
            stats["changed"] += 1

        label = "NEW " if is_new else "CHG "
        if args.dry_run:
            print(f"  {label}{url}  (lm={lm})")
            manifest.setdefault(url, {})
            continue

        # Download the changed/new page.
        try:
            body, lm2, cl2 = fetch(url)
            time.sleep(args.wait)
        except Exception as e:
            stats["errors"] += 1
            print(f"  ! fetch failed {url}: {e}", file=sys.stderr)
            continue
        dest = url_to_path(args.out, args.host, url)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(body)
        manifest[url] = {"lm": lm2 or lm, "cl": cl2 or cl}
        print(f"  {label}{url}  -> {dest}")

        # Discover new pages linked from this changed page.
        try:
            parser = LinkParser()
            parser.feed(body.decode("utf-8", "replace"))
            for href in parser.hrefs:
                if href.startswith(("#", "mailto:", "javascript:", "tel:")):
                    continue
                absu = urllib.parse.urljoin(url, href)
                pu = urllib.parse.urlparse(absu)
                if pu.hostname != args.host:
                    continue
                absu = absu.split("#")[0]
                if absu not in seen and absu not in queue:
                    queue.append(absu)
        except Exception:
            pass

    with open(args.manifest, "w") as f:
        json.dump(manifest, f, indent=0, sort_keys=True)

    print(f"\nDone. checked={stats['checked']} unchanged={stats['unchanged']} "
          f"changed={stats['changed']} new={stats['new']} removed(kept)={stats['removed']} "
          f"errors={stats['errors']}  manifest={len(manifest)} urls")


if __name__ == "__main__":
    main()
