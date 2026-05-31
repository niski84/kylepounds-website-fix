#!/usr/bin/env python3
"""Inject anti-FOUC <meta> + <style> early in <head> to prevent flash of white/dark.

Inserts immediately after <head> (before any external CSS):
  <meta name="color-scheme" content="light">
  <style>html,body{background:#fff;}</style>

This ensures:
- Kyle's light-themed site renders with white background from first paint
- Browsers in dark mode don't invert colors before stylesheet loads
"""
import os, re, sys

NOFLASH = (
    '<meta name="color-scheme" content="light">\n'
    '<style>html,body{background:#fff;}body{padding-bottom:44px;}</style>'
)
MARKER = 'kp-noflash'

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
            skipped += 1
            continue
        if MARKER in content:
            skipped += 1
            continue
        new_content, n = HEAD_RE.subn(
            r'\1\n<!-- ' + MARKER + r' -->\n' + NOFLASH,
            content, count=1
        )
        if n == 0:
            skipped += 1
            continue
        with open(fpath, 'w', encoding='utf-8', errors='replace') as f:
            f.write(new_content)
        patched += 1

print(f'No-flash injected: {patched} files, skipped: {skipped}')
