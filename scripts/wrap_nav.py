"""Wrap Kyle's top-level section nav table in a semantic <nav> element.

Kyle's site renders its 8-section nav (About Me / Education / News / Sports /
Travel / Philosophy / Politics / Funding) as a small <table> at the top of
each <body>. Site-patrol's missing-nav-element check flags every page that
lacks a <nav>; wrapping the existing table satisfies the check without
changing any visual.

Detection mirrors the Go cleaner's looksLikeNavTable heuristic:
  - Element is a <table>
  - Its visible text is short (< 800 chars — Kyle's data tables are huge)
  - Contains 5+ of the section markers

Idempotent: skips pages whose <body> already contains a <nav> tag.
Run as part of the daily mirror pipeline — see mirror-and-deploy.sh.
"""
import os
import sys
from bs4 import BeautifulSoup

SECTION_MARKERS = [
    "About Me", "Education", "News", "Sports",
    "Travel", "Philosophy", "Politics", "Funding",
]
MIN_HITS = 5
MAX_NAV_TEXT_LEN = 800  # nav is small; data tables are huge


def looks_like_nav(table) -> bool:
    text = table.get_text(separator=" ", strip=True)
    if len(text) > MAX_NAV_TEXT_LEN:
        return False
    lowered = text.lower()
    hits = sum(1 for m in SECTION_MARKERS if m.lower() in lowered)
    return hits >= MIN_HITS


def wrap_first_nav_table(soup: BeautifulSoup) -> bool:
    """Wrap the first nav-looking table in <nav>. Returns True if changed."""
    body = soup.body
    if body is None:
        return False
    # Already has a nav? Idempotent skip.
    if body.find("nav") is not None:
        return False
    for table in body.find_all("table"):
        if looks_like_nav(table):
            nav = soup.new_tag("nav", role="navigation", attrs={"aria-label": "Site sections"})
            table.wrap(nav)
            return True
    return False


def main(root: str) -> None:
    wrapped = already = no_nav_found = skipped = 0
    for dirpath, _dirs, files in os.walk(root):
        for fname in files:
            if not fname.lower().endswith(('.html', '.htm')):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except Exception:
                skipped += 1
                continue

            # Cheap pre-filter — if body already has <nav>, skip without
            # parsing the whole document.
            if '<nav ' in content.lower() or '<nav>' in content.lower():
                already += 1
                continue

            try:
                soup = BeautifulSoup(content, 'html.parser')
            except Exception:
                skipped += 1
                continue

            if wrap_first_nav_table(soup):
                try:
                    with open(fpath, 'w', encoding='utf-8', errors='replace') as f:
                        f.write(str(soup))
                    wrapped += 1
                except Exception:
                    skipped += 1
            else:
                no_nav_found += 1

    print(f'Nav wrapped: {wrapped}, already had: {already}, '
          f'no nav table found: {no_nav_found}, skipped: {skipped}')


if __name__ == '__main__':
    main(sys.argv[1])
