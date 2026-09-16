#!/bin/bash
# BF16 restart-replicate control (run AFTER scripts/pipeline.sh, user server still up).
# Same weights/config as the `bf16` arm but a fresh vLLM launch: quantifies the launch-to-launch
# numeric noise floor for closed-loop success, first divergence and open-loop agreement.
set -euo pipefail
cd /home/xinyu/cloq
source ~/miniconda3/etc/profile.d/conda.sh && conda activate cloq
MODEL=Qwen/Qwen3-4B-Instruct-2507; REV=cdbee75f17c01a7cc42f958dc650907174af0554
log() { echo "[$(date '+%F %T')] $*"; }
scripts/wait_server.sh 8000 60 || { log "user server not up; start it with the SAME config as the pipeline first"; exit 1; }
scripts/stop_vllm.sh 8001 >/dev/null; sleep 2
(nohup scripts/serve_vllm.sh 1 8001 $MODEL agent 9216 --revision $REV > logs/vllm_agent_bf16_rep.log 2>&1 &)
scripts/wait_server.sh 8001 900
for d in retail airline; do
  if [ -f runs/bf16_rep_eval/$d/status.json ] && grep -q '"completed"' runs/bf16_rep_eval/$d/status.json; then log "bf16_rep_eval/$d done"; continue; fi
  python -m cloq.run_arm --run-id bf16_rep_eval --arm bf16_rep --domain $d --task-file manifests/eval_tasks_v0.json --note "BF16 restart replicate (noise-floor control)" 2>&1 | grep -vE "^INFO|Using data directory|DEBUG|isn't mapped" | tail -20
  [ -f runs/bf16_rep_eval/$d/openloop.summary.json ] || python -m cloq.openloop --arm bf16_rep --arm-run bf16_rep_eval --domain $d 2>&1 | tail -2 || log "WARN openloop failed"
  [ -f runs/bf16_rep_eval/$d/divergence.json ] || python -m cloq.divergence --arm-run bf16_rep_eval --domain $d 2>&1 | tail -3 || log "WARN divergence failed"
  [ -f runs/bf16_rep_eval/$d/task_success.json ] || python -m cloq.nl_judge --run-dir runs/bf16_rep_eval/$d 2>&1 | tail -1 || log "WARN judge failed"
done
# self-replay of the bf16 arm's own states through THIS instance is not exact (different launch); the
# exact self-check is bf16_rep states through this same instance:
for d in retail airline; do
  [ -f runs/bf16_rep_eval/$d/openloop_self.summary.json ] || python - <<EOF
from pathlib import Path
import json
from cloq import config as C
from cloq.openloop import run
ids = json.load(open("manifests/eval_tasks_v0.json"))["$d"]
run("bf16_rep_eval", "bf16_rep_self", "bf16_rep_eval", "$d", ids, C.AGENT_API_BASE, Path("runs/bf16_rep_eval/$d/openloop_self.jsonl"))
EOF
done
scripts/stop_vllm.sh 8001 >/dev/null
CUDA_VISIBLE_DEVICES=1 python -m cloq.occupancy extract --runs bf16_rep_eval 2>&1 | tail -3 || log "WARN occupancy extract failed"
python -m cloq.occupancy analyze --arm-runs static=static_eval fp_traj=fp_traj_eval cloq=cloq_eval bf16_rep=bf16_rep_eval --calib static=manifests/calib_static.json fp_traj=manifests/calib_fp_traj.json cloq=manifests/calib_cloq.json --rep last 2>&1 | tail -2 || log "WARN occupancy analyze failed"
python -m cloq.occupancy analyze --arm-runs static=static_eval fp_traj=fp_traj_eval cloq=cloq_eval bf16_rep=bf16_rep_eval --calib static=manifests/calib_static.json fp_traj=manifests/calib_fp_traj.json cloq=manifests/calib_cloq.json --rep obs 2>&1 | tail -2 || log "WARN occupancy analyze failed"
python -m cloq.report --arm-runs static=static_eval fp_traj=fp_traj_eval cloq=cloq_eval bf16_rep=bf16_rep_eval || log "WARN report failed"
log "BF16 REPLICATE DONE"
