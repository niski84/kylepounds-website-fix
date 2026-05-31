#!/usr/bin/env python3
"""Strip third-party tracker scripts and pixels from all HTML files."""
import os, re, sys

# Domains whose <script src> and <img src> tags we remove
TRACKER_DOMAINS = [
    'hitwebcounter.com',
    'cloudflareinsights.com',
    'doubleclick.net',
    'google-analytics.com',
    'googletagmanager.com',
]

# Regex: remove <script ...src="...tracker...">...</script> (including inline content)
SCRIPT_RE = re.compile(
    r'<script[^>]+src=["\'][^"\']*(?:' +
    '|'.join(re.escape(d) for d in TRACKER_DOMAINS) +
    r')[^"\']*["\'][^>]*>.*?</script>',
    re.IGNORECASE | re.DOTALL
)

# Regex: remove <img ...src="...tracker..."...>
IMG_RE = re.compile(
    r'<img[^>]+src=["\'][^"\']*(?:' +
    '|'.join(re.escape(d) for d in TRACKER_DOMAINS) +
    r')[^"\']*["\'][^>]*>',
    re.IGNORECASE
)

# Also remove self-closing script tags with no closing tag
SCRIPT_SC_RE = re.compile(
    r'<script[^>]+src=["\'][^"\']*(?:' +
    '|'.join(re.escape(d) for d in TRACKER_DOMAINS) +
    r')[^"\']*["\'][^>]*/?>',
    re.IGNORECASE
)

root = sys.argv[1] if len(sys.argv) > 1 else '.'
patched = skipped = removed_total = 0

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

        new_content = SCRIPT_RE.sub('', content)
        new_content = SCRIPT_SC_RE.sub('', new_content)
        new_content = IMG_RE.sub('', new_content)

        if new_content == content:
            skipped += 1
            continue

        removed = content.count('\n') - new_content.count('\n')
        removed_total += abs(len(content) - len(new_content))
        with open(fpath, 'w', encoding='utf-8', errors='replace') as f:
            f.write(new_content)
        patched += 1

print(f'Trackers stripped: {patched} files, {removed_total} bytes removed, {skipped} unchanged')
