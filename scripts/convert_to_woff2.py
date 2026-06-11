"""
Convert all .otf / .ttf files in a directory to .woff2.
Skips files that already have an up-to-date .woff2 counterpart.

Usage: python3 convert_to_woff2.py /path/to/fonts/
Requires: fonttools + brotli  (pip install fonttools brotli)
"""
import os, sys
from pathlib import Path

try:
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.sfnt import calcChecksum  # noqa – just checks import
except ImportError:
    print("ERROR: fonttools not installed. Run: pip3 install fonttools brotli")
    sys.exit(1)

fonts_dir = Path(sys.argv[1])
converted = skipped = errors = 0

for src in sorted(fonts_dir.glob("*")):
    if src.suffix.lower() not in (".otf", ".ttf"):
        continue
    dest = src.with_suffix(".woff2")
    if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        skipped += 1
        continue
    try:
        font = TTFont(src)
        font.flavor = "woff2"
        font.save(dest)
        src_kb  = src.stat().st_size  // 1024
        dest_kb = dest.stat().st_size // 1024
        pct = int(100 * dest_kb / src_kb) if src_kb else 0
        print(f"  {src.name} → {dest.name}  ({src_kb}KB → {dest_kb}KB, {pct}%)")
        converted += 1
    except Exception as e:
        print(f"  ERROR {src.name}: {e}")
        errors += 1

print(f"\nconvert_to_woff2: converted={converted} skipped={skipped} errors={errors}")
