#!/bin/bash
# Iteration-3 insight analyses (docs/insights/iter_3_candidates.md). Read-only over runs/, analysis/openloop/, the queue.
#   bash run_all.sh                                   # frozen iter-2 snapshot AND a new live snapshot (integrity gate)
#   LIVE=out/snapshot_live_<utc>.json bash run_all.sh # reuse an existing live manifest
# Outputs: out/r0*_<tag>.json with tag = frozen | live; logs out/r0*_<tag>.log.
set -e
cd "$(dirname "$0")"
source /data/ziyangs/cloq/scripts/a6000/env.sh >/dev/null 2>&1
export PYTHONPATH=/data/ziyangs/cloq/analysis/insights/iter_2
FROZEN=/data/ziyangs/cloq/analysis/insights/iter_2/out/snapshot_20260929T0732Z.json
if [ -z "$LIVE" ]; then
  UTC=$(date -u +%Y%m%dT%H%MZ)
  LIVE=$(readlink -f out)/snapshot_live_$UTC.json
  python ../iter_2/integrity.py --out "$LIVE" > out/integrity_live_$UTC.log 2>&1
fi
for S in "$FROZEN" "$(readlink -f "$LIVE")"; do
  export CLOQ_SNAPSHOT=$S
  TAG=$(case "$S" in *live*) echo live;; *) echo frozen;; esac)
  for s in r01_realloc r02_stability r03_fragility r04_margin_predict r05_openloop_task r06_crossmodel r07_damage r08_size_generic r09_headline r10_turnover_stats; do
    python $s.py > out/${s%%_*}_$TAG.log 2>&1
  done
  echo "done $TAG ($S)"
done
