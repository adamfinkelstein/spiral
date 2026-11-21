#!/bin/bash
# Sanity check of cardlab (Python) against the JS card pipeline (card_js.html):
# each stage gets identical inputs in both. Needs node and the Python deps.
# Usage: checks/compare_with_js.sh [preset] [seed]
set -e
here="$(cd "$(dirname "$0")" && pwd)"; root="$here/.."
dump="$(mktemp -d)"
python3 "$here/js_dump.py" "${1:-typical}" "${2:-1}" "$dump"
# the JS samples 5% of the annulus for the coherence; use all pixels, as js_dump.py does
{ echo "const N=1024;"
  cat "$root"/chunkfit.js "$root"/render.js "$root"/fftspacing.js "$root"/gradcenter.js "$root"/cardmodel.js "$root"/cardpipe.js "$here/js_compare_tail.js"
} | sed 's/^const N = typeof.*$//; s/if (hp\[i\] !== 0 \&\& rnd() < 0.05)/if (hp[i] !== 0)/' > "$dump/compare.js"
DUMP="$dump" node --max-old-space-size=4000 "$dump/compare.js"
rm -rf "$dump"
