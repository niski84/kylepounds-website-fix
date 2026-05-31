"""
Content extractor: converts kylepounds.com table-soup HTML into
clean semantic HTML ready to be wrapped in the v2 base template.
"""
import re
import sys
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Comment, Tag

ASSET_BASE = "https://kylepounds.com/"

def make_absolute(url: str, base: str = ASSET_BASE) -> str:
    if not url or url.startswith(("http://", "https://", "//", "data:", "#", "mailto:")):
        return url
    return urljoin(base, url)

NAV_HREFS = {
    "index.html", "about me/about me.html", "education/education.html",
    "education/philosophy/philosophy.html", "education/politics/politics.htm",
    "news/news.html", "travel/travel.html", "sports/sports.html", "funding.html",
}

def is_nav_block(tag):
    """Return True if this tag is the main site nav.

    His nav is always a Dreamweaver <table>. Restricting to tables avoids
    false positives on wrapper <div>s that incidentally contain the nav table
    along with substantial page content.
    """
    if not isinstance(tag, Tag) or tag.name != "table":
        return False
    links = tag.find_all("a", href=True)
    if len(links) < 4:
        return False
    matched = sum(
        1 for a in links
        if a["href"].lower().lstrip("./") in NAV_HREFS
    )
    # Either the block is small (≤25 links) or nav links dominate (≥20% ratio)
    return matched >= 4 and (len(links) <= 25 or matched / len(links) >= 0.20)

# Dreamweaver document-level rules we strip so they don't override our template.
# We capture body{background-color} separately before stripping.
_DOC_RULES = re.compile(
    r'(?:body\s*,\s*td\s*,\s*th|body|html|a(?:\s*:\s*(?:link|visited|hover|active))?)'
    r'\s*\{[^}]*\}',
    re.IGNORECASE | re.DOTALL,
)
_BODY_BG = re.compile(
    r'body\s*\{[^}]*background-color\s*:\s*([^;}\s]+)',
    re.IGNORECASE | re.DOTALL,
)

def extract_page_styles(soup):
    """Return (filtered_css, body_bg_color)."""
    blocks = []
    body_bg = ""
    for style in soup.find_all("style"):
        raw = style.string or ""
        # Strip old-browser HTML comment wrappers (<!-- ... -->) but
        # capture body background-color first — browsers DO apply CSS
        # inside these wrappers (CDO/CDC tokens are ignored, not the rules).
        raw_unwrapped = raw.replace("<!--", "").replace("-->", "")
        if not body_bg:
            m = _BODY_BG.search(raw_unwrapped)
            if m:
                body_bg = m.group(1).strip()
        filtered = _DOC_RULES.sub("", raw_unwrapped).strip()
        if filtered:
            blocks.append(filtered)
        style.decompose()
    return "\n".join(blocks), body_bg

def extract(html: str, page_url: str = ASSET_BASE) -> dict:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup.find_all("base"):
        tag.decompose()

    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    page_styles, body_bg = extract_page_styles(soup)

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else "Kyle Pounds"

    head = soup.find("head")
    if head:
        head.decompose()

    body = soup.find("body") or soup

    # Find the nav block; collect any siblings that precede it as the
    # page-specific header (shown above our nav in the template).
    pre_nav = ""
    for tag in body.find_all(True):
        if is_nav_block(tag):
            pre_parts = []
            to_remove = []
            for sib in tag.previous_siblings:
                if isinstance(sib, Tag):
                    pre_parts.append(str(sib))
                    to_remove.append(sib)
            pre_nav = "".join(reversed(pre_parts))
            for sib in to_remove:
                sib.decompose()  # remove from body so it doesn't appear in content too
            tag.decompose()
            break

    # Strip bgcolor only from purely structural layout TDs — those that contain
    # a nested table but have no meaningful content of their own (no text visible
    # outside the nested table, even inside child divs/spans).
    def _text_outside_tables(tag):
        """Collect visible text from tag, skipping anything inside <table>."""
        parts = []
        for child in tag.children:
            if isinstance(child, str):
                parts.append(child)
            elif isinstance(child, Tag) and child.name != "table":
                parts.append(_text_outside_tables(child))
        return "".join(parts)

    for td in body.find_all("td", bgcolor=True):
        if not td.find("table"):
            continue
        outside_text = _text_outside_tables(td).strip()
        if len(outside_text) <= 5:
            del td["bgcolor"]

    # Make relative asset src/background attrs absolute (resolved against this page's URL)
    for img in body.find_all("img", src=True):
        img["src"] = make_absolute(img["src"], page_url)
    for tag in body.find_all(True):
        if tag.get("background"):
            tag["background"] = make_absolute(tag["background"], page_url)

    # Absolutize <a href> links that point to non-HTML assets (KMZ, PDF, GPX, etc.)
    # We mirror HTML pages so we keep those relative; everything else lives on his server.
    _HTML_EXTS = {".html", ".htm"}
    for a in body.find_all("a", href=True):
        href = a["href"]
        if href.startswith(("http://", "https://", "//", "#", "mailto:", "javascript:")):
            continue
        path = href.split("?")[0].split("#")[0].lower()
        ext = path.rsplit(".", 1)[-1] if "." in path else ""
        if f".{ext}" not in _HTML_EXTS:
            a["href"] = make_absolute(href, page_url)

    content = body.decode_contents().strip()
    return {
        "title":    title,
        "styles":   page_styles,
        "body_bg":  body_bg,
        "pre_nav":  pre_nav,
        "content":  content,
    }
