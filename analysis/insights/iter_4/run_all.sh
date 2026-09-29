#!/bin/bash
# Iteration-4 disposition analysis (docs/insights/iter_4_disposition.md). 0 GPU-h, ~5 min on 24 cores.
# usage: bash analysis/insights/iter_4/run_all.sh [snapshot manifest]
set -euo pipefail
source /data/ziyangs/cloq/scripts/a6000/env.sh >/dev/null 2>&1
export CLOQ_SNAPSHOT=${1:-/data/ziyangs/cloq/analysis/insights/iter_3/out/snapshot_live_20260929T1937Z.json}
export CLOQ_TAG=${CLOQ_TAG:-live_$(python -c "import json,sys;print(json.load(open('$CLOQ_SNAPSHOT'))['snapshot_id'])")}
cd /data/ziyangs/cloq/analysis/insights/iter_4
for s in p1_overdispersion p2_dispositions p4_openloop_forks f1_fragile_forks p5_dose_scaling h00_holm; do
  python $s.py 2>&1 | grep -v -e RuntimeWarning -e "nanmean(" -e "X0 = " | tee out/${s}_${CLOQ_TAG}.log
done
