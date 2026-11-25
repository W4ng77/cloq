#!/usr/bin/env bash
set -euo pipefail

mode=$1
work=$2
python_path=$3
runner=$4
index=${SLURM_ARRAY_TASK_ID:-0}
case "$mode" in
  build) lock=build ;;
  eval) lock="block-$index" ;;
  *) echo "Unexpected mode: $mode" >&2; exit 2 ;;
esac

mkdir -p "$work/locks" "$work/attempts"
exec 8>"$work/locks/$lock.lock"
flock -x 8
attempt="$work/attempts/$mode-${SLURM_JOB_ID}-${index}-$(date +%s%N)"
mkdir -p "$attempt"

export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONUNBUFFERED=1
export TMPDIR="${SLURM_TMPDIR:-/tmp}/cloq-$SLURM_JOB_ID-$index"
mkdir -p "$TMPDIR"
cd "$attempt"
if [[ "$mode" == eval && -s "$work/blocks/$(printf '%02d' "$index").json" ]]; then
  echo "Block $index already completed in $work"
  exit 0
fi

"$python_path" -u "$runner" "$mode" --work "$work" --attempt "$attempt" --block "$index"
