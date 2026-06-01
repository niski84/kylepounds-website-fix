#!/usr/bin/env python3
"""Inject Kyle Pounce banner into all HTML files after <body> (top of page).

Usage: inject_banner.py <root_dir> [mirror_date]
  mirror_date: YYYY-MM-DD, defaults to today
"""
import os, re, sys
from datetime import date

MIRROR_DATE = sys.argv[2] if len(sys.argv) > 2 else date.today().strftime('%Y-%m-%d')

BANNER = (
    '<!-- Kyle Pounce Banner -->\n'
    '<div style="'
    'background:linear-gradient(90deg,#b827fc 0%,#2c90fc 25%,#b8fd33 50%,#fec837 75%,#fd1892 100%);'
    'color:#fff;'
    'font-family:Arial,sans-serif;'
    'font-size:12px;'
    'font-weight:bold;'
    'padding:6px 20px;'
    'display:flex;'
    'flex-wrap:wrap;'
    'align-items:center;'
    'justify-content:space-between;'
    'gap:8px;'
    'letter-spacing:.3px;'
    'text-shadow:0 1px 3px rgba(0,0,0,.4);'
    '">'
    '<span>'
    '&#x26A1; <a href="/kp.html" style="color:#fff;text-decoration:none;">Kyle Pounce</a>'
    ' &nbsp;&middot;&nbsp; Mirrored from '
    '<a href="https://kylepounds.com" style="color:#fff;opacity:.85;text-decoration:none;" rel="nofollow">kylepounds.com</a>'
    ' &nbsp;&middot;&nbsp; Last synced: ' + MIRROR_DATE +
    ' &nbsp;&middot;&nbsp; Adobe fonts working &nbsp;&middot;&nbsp; Links fixed'
    '</span>'
    '<a href="/patrol/" style="'
    'background:rgba(0,0,0,.25);'
    'color:#fff;'
    'font-size:11px;'
    'padding:3px 10px;'
    'border-radius:4px;'
    'text-decoration:none;'
    '">Dashboard &rarr;</a>'
    '</div>'
)

# Strip any previous banner variant
OLD_BANNER_RE = re.compile(
    r'<!-- Kyle Pounce Banner -->\n<div[^>]*>.*?</div>\n?',
    re.DOTALL
)

BODY_RE = re.compile(r'(<body[^>]*>)', re.IGNORECASE)

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
            skipped += 1
            continue

        # Strip any existing banner (so we can re-inject updated version)
        content = OLD_BANNER_RE.sub('', content)

        # Inject after <body>
        new_content, n = BODY_RE.subn(r'\1\n' + BANNER, content, count=1)
        if n == 0:
            skipped += 1
            continue

        with open(fpath, 'w', encoding='utf-8', errors='replace') as f:
            f.write(new_content)
        patched += 1

print(f'Banner injected: {patched} files, skipped: {skipped}')
