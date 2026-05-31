#!/usr/bin/env python3
"""Rewrite http:// Flickr URLs to https:// to prevent mixed content warnings."""
import os, re, sys

PATTERN = re.compile(r'http://(farm\d+\.staticflickr\.com|www\.flickr\.com|farm\d+\.static\.flickr\.com)')
root = sys.argv[1] if len(sys.argv) > 1 else '.'
patched = 0

for dirpath, dirs, files in os.walk(root):
    for fname in files:
        if not fname.lower().endswith(('.html', '.htm')): continue
        fpath = os.path.join(dirpath, fname)
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        new_content = PATTERN.sub(r'https://\1', content)
        if new_content != content:
            with open(fpath, 'w', encoding='utf-8', errors='replace') as f:
                f.write(new_content)
            patched += 1

print(f'Fixed mixed content: {patched} files')
