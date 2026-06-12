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
    '<span id="kp-pod" style="'
    'flex:1;'
    'text-align:center;'
    'padding:0 20px;'
    'font-size:12px;'
    'opacity:0;'
    'transition:opacity .5s;'
    'white-space:nowrap;'
    'overflow:hidden;'
    'text-overflow:ellipsis;'
    '"></span>'
    '<span style="display:flex;gap:6px;flex-shrink:0">'
    '<a href="/patrol/#audit" style="'
    'background:rgba(0,0,0,.25);'
    'color:#fff;'
    'font-size:11px;'
    'padding:3px 10px;'
    'border-radius:4px;'
    'text-decoration:none;'
    '">Audit Doc</a>'
    '<a href="/patrol/" style="'
    'background:rgba(0,0,0,.25);'
    'color:#fff;'
    'font-size:11px;'
    'padding:3px 10px;'
    'border-radius:4px;'
    'text-decoration:none;'
    '">Dashboard &rarr;</a>'
    '</span>'
    '</div>\n'
    '<script>(function(){'
    'var el=document.getElementById("kp-pod");'
    'if(!el)return;'
    'var parts=[];'
    'var done=0;'
    'function render(){'
    '  if(parts.length){'
    '    el.innerHTML=parts.join("<span style=\'color:rgba(255,255,255,.4);margin:0 10px\'>|</span>");'
    '    el.style.opacity="1";'
    '  }'
    '}'
    'try{'
    '  fetch("/api/podcasts").then(function(r){return r.json()}).then(function(eps){'
    '    var ep=(eps||[]).find(function(e){return e.status==="published"});'
    '    if(ep){'
    '      var d=new Date(ep.release_at).toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"});'
    '      var t=ep.title.replace(/&/g,"&amp;").replace(/</g,"&lt;");'
    '      parts.push("&#x1F3A7; <strong>Kyle Pounce Podcast</strong> &mdash; "'
    '        +"<a href=\\"/patrol/podcasts/"+ep.id+"\\" style=\\"color:#fff;text-decoration:underline;font-weight:bold\\">"+t+"</a>"'
    '        +" &middot; "+d'
    '        +"&nbsp;<a href=\\"/patrol/podcasts/"+ep.id+"\\" style=\\"background:rgba(255,255,255,.2);color:#fff;padding:2px 9px;border-radius:3px;font-size:11px;text-decoration:none;margin-left:4px\\">Listen &rarr;</a>");'
    '    }'
    '    if(++done===2)render();'
    '  }).catch(function(){if(++done===2)render();});'
    '  fetch("/api/videos/latest").then(function(r){return r.json()}).then(function(v){'
    '    if(v&&v.youtube_id){'
    '      var ago=v.days_ago===0?"today":v.days_ago===1?"yesterday":v.days_ago+"d ago";'
    '      var t=(v.title||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").substring(0,60);'
    '      if(t.length===60)t+="…";'
    '      parts.push("&#x1F4FA; <strong>Latest Video</strong> &mdash; "'
    '        +"<a href=\\"https://youtu.be/"+v.youtube_id+"\\" target=\\"_blank\\" style=\\"color:#fff;text-decoration:underline;font-weight:bold\\">"+t+"</a>"'
    '        +" &middot; "+ago);'
    '    }'
    '    if(++done===2)render();'
    '  }).catch(function(){if(++done===2)render();});'
    '}catch(e){}'
    '})();</script>'
)

# Strip any previous banner variant (including the inline podcast script)
OLD_BANNER_RE = re.compile(
    r'<!-- Kyle Pounce Banner -->\n<div[^>]*>.*?</div>\n?(?:<script>.*?</script>\n?)?',
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
