"""
Rewrite relative `src` attributes to absolute https://kylepounds.com/ URLs.

Run after inject_basehref.py. At that point <base href="https://kylepounds.org/">
is present, so every relative path resolves from the site root. We compute the
absolute kylepounds.com equivalent and hard-code it so browsers don't need the
base tag to find images.

Absolute URLs (Flickr, etc.) are left unchanged.
"""
import os, re, sys
from urllib.parse import urljoin

BASE_HREF = "https://kylepounds.org/"
ORIGIN = "https://kylepounds.com"

# Matches src= and data-src= attribute values (single or double quoted)
SRC_RE = re.compile(r'(\bdata-src\s*=\s*|(?<!\w)src\s*=\s*)(["\'])([^"\']+)\2', re.IGNORECASE)


def _is_relative(url):
    return url and not url.startswith(
        ("http://", "https://", "//", "data:", "mailto:", "javascript:", "#")
    )


def _to_abs(url):
    resolved = urljoin(BASE_HREF, url)
    if resolved.startswith(BASE_HREF):
        return ORIGIN + "/" + resolved[len(BASE_HREF):]
    return resolved  # absolute to a third-party host — leave alone


def fix_src_attr(m):
    attr_prefix = m.group(1)
    quote = m.group(2)
    url = m.group(3)
    if _is_relative(url):
        return attr_prefix + quote + _to_abs(url) + quote
    return m.group(0)


root = sys.argv[1]
patched = unchanged = errors = 0

for dirpath, dirs, files in os.walk(root):
    for fname in files:
        if not fname.lower().endswith((".html", ".htm")):
            continue
        fpath = os.path.join(dirpath, fname)
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            errors += 1
            continue

        new_content = SRC_RE.sub(fix_src_attr, content)

        if new_content != content:
            with open(fpath, "w", encoding="utf-8", errors="replace") as f:
                f.write(new_content)
            patched += 1
        else:
            unchanged += 1

print(f"fix_image_src: patched={patched} unchanged={unchanged} errors={errors}")
