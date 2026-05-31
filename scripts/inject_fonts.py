#!/usr/bin/env python3
"""Inject Kyle Pounce hosted font stylesheet into all HTML files."""
import os, re, sys

LINK = '<link rel="stylesheet" href="/fonts/fonts.css">'
HEAD_RE = re.compile(r'(<head[^>]*>)', re.IGNORECASE)

root = sys.argv[1] if len(sys.argv) > 1 else '.'
patched = skipped = 0

for dirpath, dirs, files in os.walk(root):
    for fname in files:
        if not fname.lower().endswith(('.html', '.htm')):
            continue
        fpath = os.path.join(dirpath, fname)
        try:
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception as e:
            print(f'SKIP {fpath}: {e}')
            skipped += 1
            continue
        if '/fonts/fonts.css' in content:
            skipped += 1
            continue
        new_content, n = HEAD_RE.subn(r'\1\n' + LINK, content, count=1)
        if n == 0:
            skipped += 1
            continue
        with open(fpath, 'w', encoding='utf-8', errors='replace') as f:
            f.write(new_content)
        patched += 1

print(f'Font link injected: {patched} files, skipped: {skipped}')
