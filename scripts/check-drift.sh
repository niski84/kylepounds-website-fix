#!/usr/bin/env bash
# check-drift.sh — compare file sizes between site/ mirror and docs/ build.
# Pages where docs/ is < THRESHOLD of the mirror size are flagged as drifted
# (content likely stripped by the extractor).
#
# Usage: ./scripts/check-drift.sh [threshold%]   default: 10

set -euo pipefail

SITE="$(dirname "$0")/../site/kylepounds.com"
DOCS="$(dirname "$0")/../docs"
THRESHOLD="${1:-10}"   # percent

python3 - "$SITE" "$DOCS" "$THRESHOLD" <<'PYEOF'
import sys
from pathlib import Path

site_dir = Path(sys.argv[1])
docs_dir = Path(sys.argv[2])
threshold = float(sys.argv[3]) / 100.0

issues = []
for src in sorted(site_dir.rglob("*.htm*")):
    rel = src.relative_to(site_dir)
    dst = docs_dir / rel
    if not dst.exists():
        continue
    src_sz = src.stat().st_size
    dst_sz = dst.stat().st_size
    if src_sz < 5000:
        continue  # skip tiny pages — ratio is noisy
    # Cap the mirror size used for ratio at 5 MB. Files larger than that are
    # almost always Dreamweaver artefacts bloated with whitespace indentation;
    # the real content (and therefore the docs/ output) is far smaller.
    effective_src = min(src_sz, 5 * 1024 * 1024)
    ratio = dst_sz / effective_src
    if ratio < threshold:
        issues.append((ratio, src_sz, dst_sz, str(rel)))

issues.sort()
if not issues:
    print(f"✓ No drift detected (all pages ≥ {sys.argv[3]}% of mirror size)")
    sys.exit(0)

print(f"⚠  {len(issues)} pages with docs/ < {sys.argv[3]}% of mirror size:\n")
print(f"  {'ratio':>6}  {'mirror':>8}  {'docs':>8}  path")
print(f"  {'-'*6}  {'-'*8}  {'-'*8}  {'-'*50}")
for ratio, sz_src, sz_dst, rel in issues:
    print(f"  {ratio:>5.1%}  {sz_src//1024:>7}KB  {sz_dst//1024:>7}KB  {rel}")

sys.exit(1)
PYEOF
