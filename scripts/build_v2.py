"""
Build v2: walks site/kylepounds.com/, extracts content from each HTML file,
wraps it in the base template, and writes to docs/.
"""
import os
import sys
import shutil
from pathlib import Path

sys.setrecursionlimit(5000)  # Cyclocross.html is deeply nested (12 MB)

ROOT = Path(__file__).parent.parent
SITE_DIR = ROOT / "site" / "kylepounds.com"
DOCS_DIR = ROOT / "docs"
BASE_TEMPLATE = ROOT / "docs" / "_base.html"

sys.path.insert(0, str(ROOT / "scripts"))
from extract import extract, ASSET_BASE

def build():
    if not SITE_DIR.exists():
        print(f"ERROR: site dir not found at {SITE_DIR}", file=sys.stderr)
        sys.exit(1)

    template = BASE_TEMPLATE.read_text(encoding="utf-8")
    built = 0
    errors = 0

    html_files = list(SITE_DIR.rglob("*.html")) + list(SITE_DIR.rglob("*.htm"))
    print(f"Building {len(html_files)} pages...")

    for src in html_files:
        # Skip the base template itself
        if src.name.startswith("_"):
            continue

        rel = src.relative_to(SITE_DIR)
        dest = DOCS_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            raw = src.read_text(encoding="utf-8", errors="ignore")
            page_url = ASSET_BASE + str(rel).replace("\\", "/")
            result = extract(raw, page_url=page_url)

            depth = len(rel.parts) - 1  # e.g. "About Me/About Me.html" → 1
            nav_prefix = "../" * depth if depth > 0 else ""

            page_html = (
                template
                .replace("{{TITLE}}", result["title"])
                .replace("{{PAGE_STYLES}}", result["styles"])
                .replace("{{BODY_BG}}", result.get("body_bg", ""))
                .replace("{{PRE_NAV}}", result.get("pre_nav", ""))
                .replace("{{CONTENT}}", result["content"])
                .replace("{{NAV_PREFIX}}", nav_prefix)
            )
            dest.write_text(page_html, encoding="utf-8")
            built += 1
        except Exception as e:
            print(f"  WARN: {rel} — {e}", file=sys.stderr)
            # Fall back: copy original
            shutil.copy2(src, dest)
            errors += 1

    # Copy styles.css into docs root (already there, but ensure freshness)
    print(f"\nDone: {built} built, {errors} fallback copies")
    print(f"Output: {DOCS_DIR}")

if __name__ == "__main__":
    build()
