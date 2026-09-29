#!/bin/bash
# Re-run every iteration-1 insight script (read-only over runs/). Outputs land in ./out/.
set -e
cd "$(dirname "$0")"
source /data/ziyangs/cloq/scripts/a6000/env.sh >/dev/null 2>&1
python s00_snapshot.py
for m in q4 q8; do python s01_token_flip_margin.py $m; python s02_trajectory_divergence.py $m; done
python s03_margin_predictions.py
python s04_node_floor.py
for d in airline retail; do python s05_pilot_success.py q4 $d; done
for a in "q4 airline" "q4 retail"; do python s06_pilot_delta.py $a; done
python s07_flavour_outcome.py
