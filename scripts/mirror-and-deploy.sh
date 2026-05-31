#!/bin/bash
# Runs on the VPS — mirrors HTML/CSS from kylepounds.com (timestamped, incremental),
# processes files in-place, then triggers a site-patrol scan.
set -e

SITE=/var/www/kylepounds.org
SCRIPTS=/opt/kp-mirror/scripts
DATE=$(date +%Y-%m-%d)

echo "=== Kyle Pounce mirror: $DATE ==="

echo "[1/3] Mirroring HTML/CSS (incremental — only changed files)..."
timeout 10m wget \
  --recursive \
  --level=3 \
  --no-parent \
  --accept="html,htm,css" \
  --timestamping \
  --timeout=15 \
  --tries=1 \
  --wait=0.2 \
  --user-agent="Mozilla/5.0 (compatible; site-archiver)" \
  --directory-prefix="$SITE" \
  "https://kylepounds.com/" || true
echo "Mirror done: $(find "$SITE/kylepounds.com" -name '*.html' -o -name '*.htm' -o -name '*.css' 2>/dev/null | wc -l) files on disk"

echo "[2/3] Processing HTML..."
python3 "$SCRIPTS/inject_noflash.py"      "$SITE/kylepounds.com/"
python3 "$SCRIPTS/fix_mixed_content.py"   "$SITE/kylepounds.com/"
python3 "$SCRIPTS/inject_basehref.py"     "$SITE/kylepounds.com/"
python3 "$SCRIPTS/strip_trackers.py"      "$SITE/kylepounds.com/"
python3 "$SCRIPTS/inject_banner.py"       "$SITE/kylepounds.com/" "$DATE"
python3 "$SCRIPTS/inject_fonts.py"        "$SITE/kylepounds.com/"

echo "[3/3] Triggering site-patrol scan..."
curl -s -c /tmp/sp.txt -X POST http://localhost:8211/api/login \
  -H 'Content-Type: application/json' -d '{"password":"excellent"}' > /dev/null
curl -s -b /tmp/sp.txt -X POST http://localhost:8211/api/scan > /dev/null

echo "=== Done ==="
