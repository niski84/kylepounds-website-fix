#!/bin/bash
# Runs on the VPS — serial polite incremental mirror of kylepounds.com.
# The original 6-parallel-wget-with-no-wait setup tripped GlowHost's auto-
# firewall (cPHulk/CSF), which blocked the VPS IP entirely for hours after
# each daily run. We now do one section at a time with --wait + --limit-rate.
# Trades ~10 extra minutes of runtime for not being rate-banned.
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
  --timeout=20
  --tries=2
  # Politeness flags — keep GlowHost's auto-block happy:
  --wait=1                # 1s between consecutive requests
  --random-wait           # adds 0.5-1.5x jitter to --wait
  --limit-rate=300k       # cap bandwidth
  --user-agent="Mozilla/5.0 (compatible; kylepounds-mirror/2.0; +https://kylepounds.org)"
  --directory-prefix="$SITE"
  -q
)

SECTIONS=(
  "https://kylepounds.com/"
  "https://kylepounds.com/About%20Me/"
  "https://kylepounds.com/Education/"
  "https://kylepounds.com/News/"
  "https://kylepounds.com/Sports/"
  "https://kylepounds.com/Travel/"
)

echo "=== Kyle Pounce mirror: $DATE ==="
echo "[1/4] Mirroring HTML/CSS sequentially with politeness gates..."

for url in "${SECTIONS[@]}"; do
  echo "  → $url"
  wget "${WGET_ARGS[@]}" "$url" || echo "  WARN: section failed (likely blocked); continuing"
done

FILES=$(find "$SITE/kylepounds.com" -name '*.html' -o -name '*.htm' -o -name '*.css' 2>/dev/null | wc -l)
ELAPSED=$(( $(date +%s) - START ))
echo "Mirror done: $FILES files on disk in ${ELAPSED}s"

echo "[2/4] Processing HTML..."
python3 "$SCRIPTS/inject_noflash.py"      "$SITE/kylepounds.com/"
python3 "$SCRIPTS/fix_mixed_content.py"   "$SITE/kylepounds.com/"
python3 "$SCRIPTS/inject_basehref.py"     "$SITE/kylepounds.com/"
python3 "$SCRIPTS/inject_viewport.py"     "$SITE/kylepounds.com/"
python3 "$SCRIPTS/wrap_nav.py"            "$SITE/kylepounds.com/"
python3 "$SCRIPTS/strip_trackers.py"      "$SITE/kylepounds.com/"
python3 "$SCRIPTS/inject_banner.py"       "$SITE/kylepounds.com/" "$DATE"
python3 "$SCRIPTS/inject_fonts.py"        "$SITE/kylepounds.com/"
python3 "$SCRIPTS/build_fonts_css.py"     "$SITE/../fonts" 2>/dev/null || python3 "$SCRIPTS/build_fonts_css.py" /var/www/kylepounds.org/fonts

echo "[3/4] Rebuilding archive search index..."
if [ -x /opt/site-patrol/kp-ingest ]; then
  /opt/site-patrol/kp-ingest \
    -root "$SITE/kylepounds.com" \
    -db /opt/site-patrol/data/archive.db \
    -host kylepounds.org || echo "WARN: ingest failed (continuing)"
else
  echo "WARN: /opt/site-patrol/kp-ingest not found — skipping archive index"
fi

echo "[4/4] Triggering site-patrol scan..."
curl -s -c /tmp/sp.txt -X POST http://localhost:8211/api/login \
  -H 'Content-Type: application/json' -d '{"password":"excellent"}' > /dev/null
curl -s -b /tmp/sp.txt -X POST http://localhost:8211/api/scan > /dev/null

TOTAL=$(( $(date +%s) - START ))
echo "=== Done in ${TOTAL}s ==="
