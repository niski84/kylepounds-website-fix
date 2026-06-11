#!/usr/bin/env python3
"""Inject Kyle Pounce hosted font stylesheets into all HTML files.

Two <link> tags:
  1. /fonts/fonts.css       — local WOFF2/OTF @font-face rules (never blocked by ad-blockers)
  2. /fonts/google-fonts.css — Google Fonts CJK/Latin import (separate so
     ad-blockers that kill *.googleapis.com don't nuke the local fonts too)

Idempotent: skips pages that already have both links. Patches pages that
have only fonts.css (legacy) by appending the google-fonts link.
"""
import os, re, sys

LOCAL_HREF  = "/fonts/fonts.css"
GOOGLE_HREF = "/fonts/google-fonts.css"
GOOGLE_LINK = f'<link rel="stylesheet" href="{GOOGLE_HREF}">'
BOTH_LINKS  = f'<link rel="stylesheet" href="{LOCAL_HREF}">\n{GOOGLE_LINK}'
HEAD_RE = re.compile(r'(<head[^>]*>)', re.IGNORECASE)
LOCAL_TAG_RE = re.compile(r'(<link[^>]*href=["\']' + re.escape(LOCAL_HREF) + r'["\'][^>]*>)', re.IGNORECASE)

root = sys.argv[1] if len(sys.argv) > 1 else '.'
inserted = patched_google = skipped = 0

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

        has_local  = LOCAL_HREF  in content
        has_google = GOOGLE_HREF in content

        if has_local and has_google:
            skipped += 1
            continue

        if has_local and not has_google:
            # Legacy page — already has fonts.css, just append google-fonts link after it
            new_content = LOCAL_TAG_RE.sub(r'\1\n' + GOOGLE_LINK, content, count=1)
            if new_content == content:
                skipped += 1
                continue
            with open(fpath, 'w', encoding='utf-8', errors='replace') as f:
                f.write(new_content)
            patched_google += 1
            continue

        # Fresh page — inject both links
        new_content, n = HEAD_RE.subn(r'\1\n' + BOTH_LINKS, content, count=1)
        if n == 0:
            skipped += 1
            continue
        with open(fpath, 'w', encoding='utf-8', errors='replace') as f:
            f.write(new_content)
        inserted += 1

print(f'inject_fonts: inserted={inserted} google-only-patch={patched_google} skipped={skipped}')
