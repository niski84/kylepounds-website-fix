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

python3 "$SCRIPTS/build_fonts_css.py" "$SITE/../fonts" 2>/dev/null \
  || python3 "$SCRIPTS/build_fonts_css.py" /var/www/kylepounds.org/fonts

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

echo "$DATE OK vps-post-deploy complete" >> "$STATE_LOG"
echo "VPS post-deploy done"
