"""Remove any <base href> tag from every page.

WHY THIS REPLACED inject_basehref.py
------------------------------------
We mirror kylepounds.com WITHOUT --convert-links, so Kyle's original links are
preserved verbatim. Those links are *page-relative*: bare fragments (href="#1"),
same-directory links (href="Audio Science.html"), and parent-relative links
(href="../../CE/0-500/World.html#5"). On kylepounds.com they have NO <base> tag,
so the browser resolves them against each page's real URL — and they work.

inject_basehref.py used to add <base href="https://kylepounds.org/"> to every
page. That overrode the browser's default base (the page URL) and forced EVERY
relative link to resolve from the domain root instead:
  - href="#Timeline1"  on /Education/Education.html  ->  /#Timeline1        (broken)
  - href="Audio Science.html"                        ->  /Audio Science.html (broken)
That's the bug: same-page anchors and page-relative links all pointed at root.
(fix_image_src.py was a second band-aid that hard-coded image src to absolute
kylepounds.com URLs to dodge the same base-href breakage — images therefore
already work without the base tag. Fonts/banner links use root-absolute "/..."
paths, which are unaffected by removing the base tag.)

Removing the <base> tag makes kylepounds.org resolve links identically to
kylepounds.com — i.e. correctly. Idempotent; safe to run every mirror pass.
"""
import os
import re
import sys

# Match any <base ...> tag (with or without href, self-closing or not).
BASE_RE = re.compile(r'[ \t]*<base\b[^>]*>\s*\n?', re.IGNORECASE)


def main(root: str) -> None:
    removed = clean = skipped = 0
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
            if '<base' not in content.lower():
                clean += 1
                continue
            new_content = BASE_RE.sub('', content)
            if new_content != content:
                with open(fpath, 'w', encoding='utf-8', errors='replace') as f:
                    f.write(new_content)
                removed += 1
            else:
                clean += 1
    print(f'Base href removed from {removed} pages, {clean} already clean, {skipped} skipped')


if __name__ == '__main__':
    main(sys.argv[1])
