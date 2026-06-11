#!/bin/bash
# Runs on the VPS — incremental polite mirror of kylepounds.com, processes
# files in place, then triggers a site-patrol scan + library re-ingest.
#
# Restraint principles after the GlowHost auto-block incident:
#  * Pre-flight reachability check — if Kyle's host is blocking our IP, exit
#    gracefully (status 0) so CI doesn't fail. We'll wait it out and try
#    again tomorrow. Hammering a blocked target makes the block longer.
#  * One section at a time, never parallel.
#  * --wait=3 --random-wait + --limit-rate=150k — slow on purpose.
#  * 30-second sleep between sections so the host sees gaps, not a burst.
#  * Abort after 2 consecutive section failures (likely block in progress).
#  * Every run writes to /var/log/kp-mirror-state.log so we can see block
#    history at a glance and the dashboard can surface health.
set -e

SITE=/var/www/kylepounds.org
SCRIPTS=/opt/kp-mirror/scripts
STATE_LOG=/var/log/kp-mirror-state.log
DATE=$(date +%Y-%m-%d)
START=$(date +%s)

log_state() {
  # status, message → appended to state log as "ISO8601 status message"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $1 $2" >> "$STATE_LOG"
}

echo "=== Kyle Pounce mirror: $DATE ==="

# Stage 0 — reachability check. If we can't even establish TCP, bail before
# wasting cycles and before triggering further escalation on the host side.
echo "[0/4] Checking kylepounds.com reachability from this VPS..."
if ! curl -sI -m 10 https://kylepounds.com -o /dev/null -w "" 2>/dev/null; then
  echo "  ✗ kylepounds.com unreachable (likely blocked). Skipping mirror."
  log_state "BLOCKED" "kylepounds.com unreachable from VPS — skipping daily mirror"
  echo "[3/4] Re-running existing-mirror downstream steps anyway..."
  # Still rebuild the Library index + trigger a scan against our mirror
  # so the dashboard data stays fresh even when upstream is blocked.
  if [ -x /opt/site-patrol/kp-ingest ]; then
    /opt/site-patrol/kp-ingest -root "$SITE/kylepounds.com" \
      -db /opt/site-patrol/data/archive.db -host kylepounds.org \
      2>&1 | tail -2 || true
  fi
  curl -s -c /tmp/sp.txt -X POST http://localhost:8211/api/login \
    -H 'Content-Type: application/json' -d '{"password":"excellent"}' > /dev/null
  curl -s -b /tmp/sp.txt -X POST http://localhost:8211/api/scan > /dev/null
  echo "=== Done (blocked path) in $(( $(date +%s) - START ))s ==="
  exit 0
fi
echo "  ✓ kylepounds.com reachable"

WGET_ARGS=(
  --recursive
  --level=3
  --no-parent
  --accept="html,htm,css"
  --timestamping
  --timeout=20
  --tries=2
  # Politeness — keep GlowHost's auto-firewall happy.
  --wait=3                # 3s between requests (was 1s — still triggered blocks)
  --random-wait           # ±50% jitter on --wait
  --limit-rate=150k       # cap bandwidth to look like a slow real client
  --user-agent="Mozilla/5.0 (compatible; kylepounds-mirror/2.1; +https://kylepounds.org)"
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

echo "[1/4] Mirroring HTML/CSS sequentially (polite — 3s wait, 150k cap)..."

CONSECUTIVE_FAILS=0
SECTIONS_OK=0
SECTIONS_FAIL=0
SECTION_SLEEP=30  # seconds between sections

for i in "${!SECTIONS[@]}"; do
  url="${SECTIONS[$i]}"
  echo "  → $url"
  if wget "${WGET_ARGS[@]}" "$url"; then
    SECTIONS_OK=$((SECTIONS_OK + 1))
    CONSECUTIVE_FAILS=0
  else
    SECTIONS_FAIL=$((SECTIONS_FAIL + 1))
    CONSECUTIVE_FAILS=$((CONSECUTIVE_FAILS + 1))
    echo "  ✗ section failed (wget exit $?). Consecutive fails: $CONSECUTIVE_FAILS"
    if [ $CONSECUTIVE_FAILS -ge 2 ]; then
      echo "  STOP — 2 consecutive section failures. Likely block in progress, aborting to avoid making it worse."
      log_state "ABORTED" "consecutive section failures — stopped at section $((i+1))/${#SECTIONS[@]}"
      break
    fi
  fi
  # Sleep between sections so the host sees us as a series of distinct
  # visits, not one continuous burst. Skip after the last section.
  if [ $i -lt $((${#SECTIONS[@]} - 1)) ]; then
    echo "  ⏱  sleeping ${SECTION_SLEEP}s before next section..."
    sleep $SECTION_SLEEP
  fi
done

FILES=$(find "$SITE/kylepounds.com" -name '*.html' -o -name '*.htm' -o -name '*.css' 2>/dev/null | wc -l)
ELAPSED=$(( $(date +%s) - START ))
echo "Mirror done: $FILES files on disk in ${ELAPSED}s · sections OK=$SECTIONS_OK fail=$SECTIONS_FAIL"
log_state "OK" "$SECTIONS_OK/${#SECTIONS[@]} sections fetched in ${ELAPSED}s, $FILES files on disk"

echo "[2/4] Processing HTML..."
python3 "$SCRIPTS/inject_noflash.py"      "$SITE/kylepounds.com/"
python3 "$SCRIPTS/fix_mixed_content.py"   "$SITE/kylepounds.com/"
python3 "$SCRIPTS/inject_basehref.py"     "$SITE/kylepounds.com/"
python3 "$SCRIPTS/inject_viewport.py"     "$SITE/kylepounds.com/"
python3 "$SCRIPTS/wrap_nav.py"            "$SITE/kylepounds.com/"
python3 "$SCRIPTS/strip_trackers.py"      "$SITE/kylepounds.com/"
python3 "$SCRIPTS/inject_banner.py"       "$SITE/kylepounds.com/" "$DATE"
python3 "$SCRIPTS/inject_fonts.py"        "$SITE/kylepounds.com/"
python3 "$SCRIPTS/fix_image_src.py"       "$SITE/kylepounds.com/"
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
