#!/bin/bash
# Optional extras, to be run AFTER scripts/pipeline.sh finishes (plan sections 12 and 11.D).
#   1. RTN W4 (no calibration at all) -- the cheap reference that shows what calibration buys.
#   2. Q-only calibration -- built ONLY if CLOQ beat FP-Traj on the primary endpoint.
# The user-simulator server must still be the one the pipeline used (never restart it mid-experiment).
set -uo pipefail
cd /home/xinyu/cloq
source ~/miniconda3/etc/profile.d/conda.sh && conda activate cloq
DOMAINS="retail airline"
log() { echo "[$(date '+%F %T')] $*"; }

scripts/wait_server.sh 8000 60 || { log "user server not up; aborting (it must be the pipeline's instance)"; exit 1; }

serve_agent() { scripts/stop_vllm.sh 8001 >/dev/null; sleep 2; (nohup scripts/serve_vllm.sh 1 8001 "$1" agent 9216 > logs/vllm_agent_$2.log 2>&1 &); scripts/wait_server.sh 8001 900; }
eval_arm() {  # eval_arm <run_id> <arm> <ckpt>
  for d in $DOMAINS; do
    if [ -f runs/$1/$d/status.json ] && grep -q '"completed"' runs/$1/$d/status.json; then log "$1/$d done"; continue; fi
    python -m cloq.run_arm --run-id $1 --arm $2 --domain $d --task-file manifests/eval_tasks_v0.json --checkpoint $3 2>&1 | grep -vE "^INFO|Using data|DEBUG|isn't mapped" | tail -12
    python -m cloq.openloop --arm $2 --arm-run $1 --domain $d 2>&1 | tail -1 || log "WARN openloop $1/$d"
    python -m cloq.divergence --arm-run $1 --domain $d 2>&1 | tail -2 || log "WARN divergence $1/$d"
    python -m cloq.nl_judge --run-dir runs/$1/$d 2>&1 | tail -1 || log "WARN judge $1/$d"
  done
}

# ---- 1. RTN W4 (no calibration) --------------------------------------------
if [ ! -f ckpts/rtn_w4/quantization.json ]; then
  scripts/stop_vllm.sh 8001 >/dev/null; sleep 2
  log "building ckpts/rtn_w4 (round-to-nearest, no calibration)"
  CUDA_VISIBLE_DEVICES=1 python -m cloq.quantize --rtn --out ckpts/rtn_w4 2>&1 | tail -3
fi
serve_agent ckpts/rtn_w4 rtn
eval_arm rtn_eval rtn ckpts/rtn_w4

# ---- 2. Q-only, only if CLOQ improved over FP-Traj on db_match --------------
GO=$(python - <<'PY'
import json
from pathlib import Path
try:
    r = json.load(open("analysis/results.json"))
    d = r["pooled"]["db_match"]["means"]
    print("yes" if d.get("cloq", 0) > d.get("fp_traj", 1) else "no")
except Exception as e:
    print("no")
PY
)
if [ "$GO" = "yes" ]; then
  log "CLOQ beat FP-Traj -> building the Q-only diagnostic"
  [ -f manifests/calib_q_only.json ] || python -m cloq.calib --arm q_only --q-run q0_fp_traj --out manifests/calib_q_only.json | tail -6
  if [ ! -f ckpts/q_only_w4/quantization.json ]; then
    scripts/stop_vllm.sh 8001 >/dev/null; sleep 2
    CUDA_VISIBLE_DEVICES=1 python -m cloq.quantize --calib manifests/calib_q_only.json --out ckpts/q_only_w4 2>&1 | tail -3
  fi
  serve_agent ckpts/q_only_w4 q_only
  eval_arm q_only_eval q_only ckpts/q_only_w4
  EXTRA="q_only=q_only_eval"
else
  log "CLOQ did not beat FP-Traj on pooled db_match -> skipping Q-only (plan section 11.D)"
  EXTRA=""
fi

# ---- report with every arm --------------------------------------------------
scripts/stop_vllm.sh 8001 >/dev/null; sleep 2
CUDA_VISIBLE_DEVICES=1 python -m cloq.occupancy extract --runs rtn_eval ${EXTRA:+q_only_eval} 2>&1 | tail -4 || log "WARN occupancy extract"
ARMS="static=static_eval fp_traj=fp_traj_eval cloq=cloq_eval rtn=rtn_eval $EXTRA"
[ -d runs/bf16_rep_eval ] && ARMS="$ARMS bf16_rep=bf16_rep_eval"
python -m cloq.occupancy analyze --arm-runs $ARMS --calib static=manifests/calib_static.json fp_traj=manifests/calib_fp_traj.json cloq=manifests/calib_cloq.json --rep last 2>&1 | tail -2 || log "WARN occupancy analyze"
python -m cloq.report --arm-runs $ARMS || log "WARN report"
log "EXTRAS DONE"
