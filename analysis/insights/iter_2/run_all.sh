#!/bin/bash
# Iteration-2 analyses on ONE frozen snapshot (review v2 W-A). Read-only over runs/, analysis/openloop/ and the queue.
#   bash run_all.sh                       # new snapshot: integrity gate -> out/snapshot_<utc>.json, then everything
#   SNAPSHOT=out/snapshot_<id>.json bash run_all.sh   # re-run every script on an existing frozen snapshot
# Every script reads CLOQ_SNAPSHOT (common.py): it sees only runs admitted by integrity.py and refuses any
# decisions/trajectory/metrics file changed after the freeze. Previous outputs are copied to out/prev_<utc>/ and every
# headline number is diffed against them (out/diff_<utc>.md + .json).
set -e
cd "$(dirname "$0")"
source /data/ziyangs/cloq/scripts/a6000/env.sh >/dev/null 2>&1
UTC=$(date -u +%Y%m%dT%H%MZ)
PREV=out/prev_$UTC
mkdir -p "$PREV"
cp out/*.json out/*.log "$PREV"/ 2>/dev/null || true
rm -f "$PREV"/snapshot_*.json "$PREV"/diff_*.json
if [ -z "$SNAPSHOT" ]; then
  SNAPSHOT=out/snapshot_$UTC.json
  python integrity.py --out "$SNAPSHOT" > out/integrity.log 2>&1
fi
export CLOQ_SNAPSHOT=$(readlink -f "$SNAPSHOT")
echo "frozen snapshot: $CLOQ_SNAPSHOT (previous outputs: $PREV)"
python p00_snapshot.py > out/p00.log 2>&1
python p01_equivalence.py > out/p01.log 2>&1
python p02_ties.py > out/p02.log 2>&1
python p03_replay_gap.py > out/p03.log 2>&1
python p04_write_flips.py > out/p04.log 2>&1
python p05_e3_axis.py > out/p05.log 2>&1
PYTHONPATH=/data/ziyangs/cloq python p06_weight_ulp.py > out/p06.log 2>&1
python p07_protocol_tally.py > out/p07.log 2>&1
tail -n 1 out/p0*.log
# conformal layer (docs/insights/iter_2_conformal.md); c02 needs p02_ties.py importable
python c01_conformal_equivalence.py > out/c01.log 2>&1
python c02_openloop_conformal.py > out/c02.log 2>&1
# review v2 must-do items (docs/insights/iter_2_integrity.md)
python n01_null_rule.py > out/n01.log 2>&1        # pre-declared null-admission rule (docs/insights/NULL_RULE.md)
python k01_churn.py > out/k01.log 2>&1            # churn: stratum-matched, excess, negative + fixed-checkpoint controls
python d01_matched_dose.py > out/d01.log 2>&1     # C3 matched-dose / partial correlation
python f01_floor_strata.py > out/f01.log 2>&1     # C1 floor by pairing stratum + stratum-matched cross-model prediction
python diff_outputs.py "$PREV" out --md out/diff_$UTC.md --json out/diff_$UTC.json
