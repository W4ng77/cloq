#!/bin/bash
# Rewrite the origin machine's absolute paths to this clone's location.
# Run once after cloning, from anywhere inside the repo. Idempotent; a no-op on the origin box.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
OLD="/home/xinyu/cloq"
[ "$ROOT" = "$OLD" ] && { echo "already at $OLD; nothing to do"; exit 0; }
n=0
while IFS= read -r -d '' f; do
  grep -qI "$OLD" "$f" 2>/dev/null || continue
  sed -i "s#$OLD#$ROOT#g" "$f"
  echo "  rewrote $f"; n=$((n+1))
done < <(git -C "$ROOT" ls-files -z)
echo "rewrote $n files: $OLD -> $ROOT"
echo
echo "Still machine-specific, check by hand:"
echo "  * conda bootstrap path in scripts and env/setup_env.sh (assumes ~/miniconda3)"
echo "  * configs/frozen_v*.json 'plan_file' provenance strings (now docs/PLAN_v*.md)"
echo "  * GPU indices in scripts/pipeline_v1.sh (serve_user uses GPU 0, serve_agent GPU 1)"
