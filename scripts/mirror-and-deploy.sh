#!/bin/bash
# Runs on the VPS — parallel incremental mirror of kylepounds.com HTML/CSS,
# processes files in-place, then triggers a site-patrol scan.
set -e

SITE=/var/www/kylepounds.org
SCRIPTS=/opt/kp-mirror/scripts
DATE=$(date +%Y-%m-%d)
START=$(date +%s)

WGET_ARGS=(
  --recursive
  --level=3
  --no-parent
  --accept="html,htm,css"
  --timestamping
  --timeout=15
  --tries=1
  --user-agent="Mozilla/5.0 (compatible; site-archiver)"
  --directory-prefix="$SITE"
  -q
)

echo "=== Kyle Pounce mirror: $DATE ==="
echo "[1/3] Mirroring HTML/CSS in parallel (no wait, incremental)..."

# Crawl root + each top-level section simultaneously
wget "${WGET_ARGS[@]}" "https://kylepounds.com/" &
wget "${WGET_ARGS[@]}" "https://kylepounds.com/About%20Me/" &
wget "${WGET_ARGS[@]}" "https://kylepounds.com/Education/" &
wget "${WGET_ARGS[@]}" "https://kylepounds.com/News/" &
wget "${WGET_ARGS[@]}" "https://kylepounds.com/Sports/" &
wget "${WGET_ARGS[@]}" "https://kylepounds.com/Travel/" &
wait

FILES=$(find "$SITE/kylepounds.com" -name '*.html' -o -name '*.htm' -o -name '*.css' 2>/dev/null | wc -l)
ELAPSED=$(( $(date +%s) - START ))
echo "Mirror done: $FILES files on disk in ${ELAPSED}s"

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

TOTAL=$(( $(date +%s) - START ))
echo "=== Done in ${TOTAL}s ==="
