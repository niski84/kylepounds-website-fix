#!/bin/bash
# Mirror kylepounds.com — HTML and CSS only, max 5 levels deep
set -e

SITE_DIR="$(dirname "$0")/../site"

wget \
  --recursive \
  --level=5 \
  --no-parent \
  --accept="html,htm,css" \
  --timeout=20 \
  --tries=2 \
  --wait=0.5 \
  --random-wait \
  --user-agent="Mozilla/5.0 (compatible; site-archiver)" \
  --directory-prefix="$SITE_DIR" \
  "https://kylepounds.com/"

echo "Mirror complete: $(find "$SITE_DIR" -type f | wc -l) files"
