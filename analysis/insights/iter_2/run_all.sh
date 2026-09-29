#!/bin/bash
# Iteration-2 prep analyses (review items 1-9), read-only over runs/ and analysis/openloop/. Outputs in ./out/.
set -e
cd "$(dirname "$0")"
source /data/ziyangs/cloq/scripts/a6000/env.sh >/dev/null 2>&1
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
