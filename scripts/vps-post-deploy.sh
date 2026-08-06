#!/bin/bash
# Runs on the VPS after the GitHub Actions runner has already mirrored + processed
# the HTML and rsynced it here. Only steps that require VPS-local resources:
#   - rebuild fonts.css from actual .otf files on disk
#   - re-ingest the library into SQLite FTS5
#   - trigger a fresh site-patrol scan
set -e

SITE=/var/www/kylepounds.org
SCRIPTS=/opt/kp-mirror/scripts
STATE_LOG=/var/log/kp-mirror-state.log
DATE=$(date +%Y-%m-%dT%H:%M:%SZ)

FONTS_DIR=/var/www/kylepounds.org/fonts

# Publish the freshly-processed mirror to the SERVED docroot.
# nginx serves Kyle's pages from $SITE/<section>/... (the docroot root), but the
# GitHub Actions runner rsyncs the processed mirror into $SITE/kylepounds.com/
# (a staging subdir). Without this overlay the live site stays frozen while the
# subdir updates daily — exactly the "stale site" bug. We overlay subdir -> root
# WITHOUT --delete so our custom files (kp.html, bike-school.html, fonts/,
# favicons, transparent.png, kyle-pounds.mp3, podcasts/) are preserved, and we
# exclude the staging subdir itself so it isn't nested into the root.
echo "Publishing mirror to served docroot (overlay, no --delete)..."
rsync -a "$SITE/kylepounds.com/" "$SITE/" --exclude="/kylepounds.com"
echo "Served HTML pages now: $(find "$SITE" -name '*.html' -not -path '*/kylepounds.com/*' | wc -l)"

# Convert any new/updated OTF files to WOFF2 (idempotent — skips up-to-date)
python3 "$SCRIPTS/convert_to_woff2.py" "$FONTS_DIR"

# Rebuild fonts.css + google-fonts.css from whatever's on disk
python3 "$SCRIPTS/build_fonts_css.py" "$FONTS_DIR"

if [ -x /opt/site-patrol/kp-ingest ]; then
  /opt/site-patrol/kp-ingest \
    -root "$SITE/kylepounds.com" \
    -db /opt/site-patrol/data/archive.db \
    -host kylepounds.org || echo "WARN: ingest failed (continuing)"
else
  echo "WARN: /opt/site-patrol/kp-ingest not found — skipping"
fi

curl -s -c /tmp/sp.txt -X POST http://localhost:8211/api/login \
  -H 'Content-Type: application/json' -d '{"password":"excellent"}' > /dev/null
curl -s -b /tmp/sp.txt -X POST http://localhost:8211/api/scan > /dev/null

# Update site-patrol LLM models to latest DeepSeek V4 Flash if still on the old slug.
# (The old deepseek/deepseek-v4-flash was deprecated by OpenRouter and returns
# "User not found" — this keeps the VPS in sync with the local config.)
ENV_FILE=/opt/site-patrol/.env
sed -i 's/^KYLE_ANSWER_MODEL=deepseek\/deepseek-v4-flash$/KYLE_ANSWER_MODEL=deepseek\/deepseek-v4-flash-0731/' "$ENV_FILE"
sed -i 's/^KYLE_CLAIMS_MODEL=deepseek\/deepseek-chat$/KYLE_CLAIMS_MODEL=deepseek\/deepseek-v4-flash-0731/' "$ENV_FILE"
systemctl restart site-patrol

echo "$DATE OK vps-post-deploy complete" >> "$STATE_LOG"
echo "VPS post-deploy done"
