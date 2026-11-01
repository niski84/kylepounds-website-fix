#!/usr/bin/env python3
"""Publish archive news and the shared announcement assets from reviewed posts.

Add entries to scripts/news/posts.json, newest first. Optional announcement_until
(ISO date, inclusive) retires a notice without removing its permanent article.
Both mirror deployment paths call this builder, so news survives daily syncs.
"""
import argparse
import datetime as dt
import html
import hashlib
import json
from pathlib import Path
import re
import shutil

BASE = 'https://kylepounds.org'
RSS = BASE + '/patrol/api/podcasts/feed.xml'
HOST = 'https://www.spreaker.com/podcast/kyle-pounds-archive--7513543'
ASSETS = Path(__file__).with_name('news')
ASSET_VERSION = hashlib.sha256((ASSETS / 'news.css').read_bytes() + (ASSETS / 'news.js').read_bytes()).hexdigest()[:12]
THEME = """<script>(function(){var t;try{t=localStorage.getItem('kp-theme')}catch(e){}t=t||(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');document.documentElement.dataset.kpTheme=t;document.documentElement.classList.toggle('dark',t==='dark')})();</script>"""


def posts(today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    entries = json.loads((ASSETS / 'posts.json').read_text())
    seen = set()
    for p in entries:
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', p['slug']) or p['slug'] in seen:
            raise ValueError('Invalid or duplicate news slug')
        seen.add(p['slug'])
        dt.date.fromisoformat(p['date'])
        if p.get('announcement_until'):
            dt.date.fromisoformat(p['announcement_until'])
    return sorted((p for p in entries if dt.date.fromisoformat(p['date']) <= today), key=lambda p: p['date'], reverse=True)


def header(entries, active='', today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    e = html.escape
    notices = [p for p in entries if p.get('announcement') and (not p.get('announcement_until') or dt.date.fromisoformat(p['announcement_until']) >= today)][:3]
    links = ''.join(f'<a href="{url}"' + (' aria-current="page"' if name == active else '') + f'>{name}</a>' for name, url in [('Library','/patrol/#library'),('Podcasts','/patrol/#podcasts'),('News','/news/'),('Bike school','/bike-school.html')])
    ticker = ''
    if notices:
        items = ''.join(f'<a href="/news/{e(p["slug"])}/">{e(p["announcement"])}</a>' for p in notices)
        # Identical halves make the scrolling loop continuous. Duplicate is not
        # announced to assistive technology or included in keyboard navigation.
        duplicate = ''.join(f'<a href="/news/{e(p["slug"])}/" aria-hidden="true" tabindex="-1">{e(p["announcement"])}</a>' for p in notices)
        ticker = f'<div class="kp-announcement" aria-label="Latest archive news"><a href="/news/">Latest news</a><div class="kp-ticker-window"><div class="kp-ticker-track">{items}{duplicate}</div></div><button type="button" data-kp-pause aria-pressed="false" aria-label="Pause scrolling news">Pause</button></div>'
    return f'<!-- kp-archive-header:start -->\n<header class="kp-header"><nav class="kp-nav" aria-label="Archive"><a class="kp-brand" href="/">Kyle Pounds<small>The independent archive</small></a>{links}<button type="button" data-kp-theme-toggle>Theme</button></nav>{ticker}</header>\n<!-- kp-archive-header:end -->'


def shell(title, description, path, content, entries):
    e = html.escape
    url = BASE + path
    return f'''<!doctype html>
<html lang="en" class="kp-news dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="dark light">{THEME}
<title>{e(title)} · Kyle Pounds Archive</title><meta name="description" content="{e(description, quote=True)}"><link rel="canonical" href="{e(url)}">
<meta property="og:title" content="{e(title, quote=True)}"><meta property="og:description" content="{e(description, quote=True)}"><meta property="og:url" content="{e(url)}"><meta property="og:type" content="article"><meta property="og:image" content="{BASE}/patrol/podcast-cover.png"><meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/news/news.css?v={ASSET_VERSION}"><script defer src="/news/news.js?v={ASSET_VERSION}"></script></head>
<body>{header(entries, 'News')}<main>{content}</main><footer>An independent mirror of <a href="https://kylepounds.com">Kyle Pounds’ website</a>. Podcast conversations are AI generated.<br><a href="/patrol/podcasts">Listen to the archive</a> · <a href="mailto:podcast@kylepounds.org">Contact the podcast</a></footer></body></html>'''


def build(root):
    root = Path(root)
    destination = root / 'news'
    destination.mkdir(parents=True, exist_ok=True)
    entries = posts()
    e = html.escape
    for asset in ['news.css', 'news.js']:
        shutil.copyfile(ASSETS / asset, destination / asset)
    cards = ''
    for p in entries:
        date = dt.date.fromisoformat(p['date']).strftime('%B %d, %Y').replace(' 0', ' ')
        cards += f'<article class="kp-story"><time datetime="{p["date"]}">{date}</time><div><h2><a href="/news/{p["slug"]}/">{e(p["title"])}</a></h2><p>{e(p["summary"])}</p><a href="/news/{p["slug"]}/">Read the announcement</a></div></article>'
        body = ''.join(f'<p>{e(text)}</p>' for text in p['body'])
        content = f'''<article class="kp-article"><a href="/news/">All archive news</a><p class="kp-muted"><time datetime="{p['date']}">{date}</time></p><h1>{e(p['title'])}</h1><p class="kp-lede">{e(p['summary'])}</p>{body}
<div class="kp-listen"><h2>Choose your way in.</h2><p>Free to listen. No Google subscription required.</p><div class="kp-links"><a href="/patrol/podcasts">Listen on this website</a><a href="{HOST}">Listen on Spreaker</a><a href="{RSS}">Subscribe with RSS</a></div></div>
<div class="kp-share"><span>Pass the story along</span><button type="button" data-copy-link>Copy link</button><button type="button" data-share hidden>Share</button></div><p role="status" data-share-result></p></article>'''
        folder = destination / p['slug']
        folder.mkdir(exist_ok=True)
        (folder / 'index.html').write_text(shell(p['title'], p['summary'], f'/news/{p["slug"]}/', content, entries))
    intro = '''<section class="kp-intro"><div><h1>More ways into the archive.</h1><p>New listening journeys, fresh discoveries, and updates from the Kyle Pounds archive.</p><a href="/patrol/podcasts">Explore the podcast</a></div><img class="kp-cover" src="/patrol/podcast-cover.png" width="340" height="340" alt="Kyle Pounds Archive podcast: history, ideas, myth"></section>'''
    (destination / 'index.html').write_text(shell('News from the archive', 'Podcast releases and updates from the Kyle Pounds archive.', '/news/', intro + cards, entries))
    print(f'News published: {len(entries)} articles at {destination}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root')
    build(parser.parse_args().root)
