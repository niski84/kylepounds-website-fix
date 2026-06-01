"""Inject responsive viewport meta into every mirrored HTML page.

Idempotent: skips pages that already have <meta name="viewport"> in any form.
Drops the tag right after <head>, mirroring inject_basehref.py's pattern.
Run as part of the daily mirror pipeline — see mirror-and-deploy.sh.
"""
import os
import re
import sys

VIEWPORT_TAG = '<meta name="viewport" content="width=device-width, initial-scale=1">'
HEAD_RE = re.compile(r'(<head[^>]*>)', re.IGNORECASE)
# Match any existing viewport meta to detect already-fixed pages. Tolerant of
# attribute order / single vs double quotes.
VIEWPORT_PRESENT_RE = re.compile(
    r'<meta\s+[^>]*name\s*=\s*["\']?viewport["\']?', re.IGNORECASE
)

root = sys.argv[1]
patched = already = skipped = 0

for dirpath, dirs, files in os.walk(root):
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

        if VIEWPORT_PRESENT_RE.search(content):
            already += 1
            continue

        new_content, n = HEAD_RE.subn(r'\1\n' + VIEWPORT_TAG, content, count=1)
        if n == 0:
            # No <head> tag — pre-HTML5 stub, skip.
            skipped += 1
            continue

        try:
            with open(fpath, 'w', encoding='utf-8', errors='replace') as f:
                f.write(new_content)
            patched += 1
        except Exception:
            skipped += 1

print(f'Viewport injected: {patched}, already had: {already}, skipped: {skipped}')
