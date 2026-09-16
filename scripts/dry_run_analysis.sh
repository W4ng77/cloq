#!/bin/bash
# Dry run of the post-simulation analysis chain on the small sanity runs (bi_d as "bf16", qtest as an arm).
# CPU only (representation extractor swapped for Qwen3-0.6B via CLOQ_REP_MODEL). Catches code-path bugs early.
set -uo pipefail
cd /home/xinyu/cloq
source ~/miniconda3/etc/profile.d/conda.sh && conda activate cloq
SCR=/tmp/claude-1003/-home-xinyu/822446b5-66f6-44be-b2ea-c6f351322b3f/scratchpad/dry
rm -rf $SCR; mkdir -p $SCR/man $SCR/analysis
log() { echo "[$(date '+%T')] $*"; }
log "split"; python -m cloq.tasks --bf16-run bi_d --out $SCR/man/task_split_v0.json 2>&1 | tail -3
python3 - <<EOF
import json; s=json.load(open("$SCR/man/task_split_v0.json"))
for d,v in s["domains"].items(): print(d, "cal", v["calibration"], "eval", v["evaluation"], "edges", v["horizon_quartile_edges"])
EOF
log "calib static"; python -m cloq.calib --arm static --split $SCR/man/task_split_v0.json --fp-run bi_d --out $SCR/man/calib_static.json 2>&1 | grep -E "total_tokens|n_contexts|within_tolerance|notes|Error|error" | head -6
log "calib fp_traj"; python -m cloq.calib --arm fp_traj --split $SCR/man/task_split_v0.json --fp-run bi_d --out $SCR/man/calib_fp_traj.json 2>&1 | grep -E "total_tokens|n_contexts|within_tolerance|tokens_by_depth|Error|error" | head -6
log "calib cloq"; python -m cloq.calib --arm cloq --split $SCR/man/task_split_v0.json --fp-run bi_d --q-run bi_d --out $SCR/man/calib_cloq.json 2>&1 | grep -E "total_tokens|n_contexts|within_tolerance|tokens_by_source|Error|error" | head -6
log "occupancy extract (cpu, 0.6B stand-in)"
for r in bi_d qtest; do rm -f runs/$r/airline/reps.npz runs/$r/retail/reps.npz; done
CLOQ_REP_MODEL=Qwen/Qwen3-0.6B python -m cloq.occupancy extract --runs bi_d qtest --domains airline --device cpu 2>&1 | grep -vE "^INFO|WARNING" | tail -4
log "occupancy analyze"; python -m cloq.occupancy analyze --bf16-run bi_d --arm-runs qtest=qtest --calib static=$SCR/man/calib_static.json fp_traj=$SCR/man/calib_fp_traj.json cloq=$SCR/man/calib_cloq.json --domains airline --eval-file $SCR/man/eval_tasks_v0.json --out $SCR/analysis/occupancy_last.json 2>&1 | tail -30
log "report"; python -m cloq.report --bf16-run bi_d --arm-runs qtest=qtest --split $SCR/man/task_split_v0.json --domains airline --out $SCR/analysis 2>&1 | tail -5
log "integrity"; python -m cloq.integrity --bf16-run bi_d --arm-runs qtest=qtest --calib static=$SCR/man/calib_static.json --split $SCR/man/task_split_v0.json --out $SCR/analysis/integrity.json 2>&1 | tail -15
log "DRY RUN DONE"; ls $SCR/analysis; head -60 $SCR/analysis/REPORT.md
