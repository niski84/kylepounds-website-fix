#!/usr/bin/env python3
"""Refresh archive navigation and current news on every mirrored HTML page."""
import argparse
from pathlib import Path
import re
import sys
from build_news import build, header, posts, THEME, ASSET_VERSION

OLD = re.compile(r'<!-- Kyle Pounce Banner -->\s*<div[^>]*>.*?</div>\s*(?:<script>.*?</script>\s*)?', re.DOTALL)
CURRENT = re.compile(r'<!-- kp-archive-header:start -->.*?<!-- kp-archive-header:end -->', re.DOTALL)
HEAD_ASSETS = re.compile(r'<!-- kp-news-assets:start -->.*?<!-- kp-news-assets:end -->', re.DOTALL)
BODY = re.compile(r'(<body\b[^>]*>)', re.IGNORECASE)
HEAD = re.compile(r'(<head\b[^>]*>)', re.IGNORECASE)
ASSETS = '<!-- kp-news-assets:start --><meta name="color-scheme" content="dark light">' + THEME + f'<link rel="stylesheet" href="/news/news.css?v={ASSET_VERSION}"><script defer src="/news/news.js?v={ASSET_VERSION}"></script><!-- kp-news-assets:end -->'


def transform(content, banner):
    if '<html lang="en" class="kp-news' in content:
        return content  # Builder owns complete news pages.
    content = OLD.sub('', content)
    content = CURRENT.sub('', content)
    content = HEAD_ASSETS.sub('', content)
    # A previous pass pinned the original body to light. Keep its legacy body
    # styling, while letting the new header respect the visitor's preference.
    content = re.sub(r'<meta name="color-scheme" content="light">', '', content)
    content = HEAD.sub(lambda m: m[1] + ASSETS, content, count=1)
    return BODY.sub(lambda m: m[1] + banner, content, count=1)


def inject(root):
    root = Path(root)
    build(root)
    banner = header(posts())
    patched = errors = 0
    for path in root.rglob('*'):
        if path.suffix.lower() not in ('.html', '.htm') or root / 'news' in path.parents:
            continue
        try:
            content = path.read_text(encoding='utf-8', errors='replace')
            if not BODY.search(content):
                continue
            updated = transform(content, banner)
            if content != updated:
                path.write_text(updated, encoding='utf-8')
                patched += 1
        except OSError as error:
            errors += 1
            print(f'Cannot update {path}: {error}', file=sys.stderr)
    print(f'Archive header updated: {patched} files; errors: {errors}')
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', default='.')
    parser.add_argument('mirror_date', nargs='?')  # Compatibility with both deploy scripts.
    inject(parser.parse_args().root)
