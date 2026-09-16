#!/bin/bash
# CLOQ v0 end-to-end pipeline (plan section 21). Idempotent: completed steps are skipped.
# GPU0: user simulator server (port 8000, stays up). GPU1: agent server (port 8001, swapped per arm) / GPTQ builds.
set -euo pipefail
cd /home/xinyu/cloq
source ~/miniconda3/etc/profile.d/conda.sh && conda activate cloq
export PYTHONUNBUFFERED=1
MODEL=Qwen/Qwen3-4B-Instruct-2507; REV=cdbee75f17c01a7cc42f958dc650907174af0554
DOMAINS="retail airline"
log() { echo "[$(date '+%F %T')] $*"; }

serve_user() {
  if scripts/wait_server.sh 8000 5 >/dev/null 2>&1; then log "user server already up"; return; fi
  (GPU_UTIL=0.78 nohup scripts/serve_vllm.sh 0 8000 $MODEL user 16384 --revision $REV > logs/vllm_user.log 2>&1 &)
  scripts/wait_server.sh 8000 900
}
serve_agent() {  # serve_agent <model_path_or_id> <logname> [extra]
  scripts/stop_vllm.sh 8001 >/dev/null; sleep 2
  local m=$1; local n=$2; shift 2
  (nohup scripts/serve_vllm.sh 1 8001 "$m" agent 9216 "$@" > logs/vllm_agent_$n.log 2>&1 &)
  scripts/wait_server.sh 8001 900
}
run_arm() {  # run_arm <run_id> <arm> <task_file|ALL> <checkpoint|->
  local rid=$1 arm=$2 tf=$3 ck=$4
  for d in $DOMAINS; do
    if [ -f runs/$rid/$d/status.json ] && grep -q '"completed"' runs/$rid/$d/status.json; then log "$rid/$d done"; continue; fi
    log "running $rid/$d"
    if [ "$tf" = "ALL" ]; then python -m cloq.run_arm --run-id $rid --arm $arm --domain $d ${ck:+--checkpoint $ck} 2>&1 | grep -vE "^INFO|Using data directory|DEBUG|isn't mapped" | tail -25
    else python -m cloq.run_arm --run-id $rid --arm $arm --domain $d --task-file $tf ${ck:+--checkpoint $ck} 2>&1 | grep -vE "^INFO|Using data directory|DEBUG|isn't mapped" | tail -25; fi
  done
}
judge() { for d in $DOMAINS; do [ -f runs/$1/$d/task_success.json ] || python -m cloq.nl_judge --run-dir runs/$1/$d 2>&1 | tail -2; done; }
build_ckpt() {  # build_ckpt <calib_manifest> <out>
  [ -f $2/quantization.json ] && { log "$2 exists"; return; }
  scripts/stop_vllm.sh 8001 >/dev/null; sleep 2
  log "building $2 from $1"
  CUDA_VISIBLE_DEVICES=1 python -m cloq.quantize --calib $1 --out $2 2>&1 | grep -vE "^INFO" | tail -8
}
openloop_div() {  # <arm> <run_id>
  for d in $DOMAINS; do
    [ -f runs/$2/$d/openloop.summary.json ] || python -m cloq.openloop --arm $1 --arm-run $2 --domain $d 2>&1 | tail -2
    [ -f runs/$2/$d/divergence.json ] || python -m cloq.divergence --arm-run $2 --domain $d 2>&1 | tail -3
  done
}

serve_user
# ---------------- Phase 1+2: BF16 on all tasks (pilot == trajectory collection under the frozen config)
serve_agent $MODEL bf16 --revision $REV
run_arm bf16 bf16 ALL -
judge bf16
# ---------------- freeze split
[ -f manifests/task_split_v0.json ] || python -m cloq.tasks --bf16-run bf16
# ---------------- Phase 3: calibration buffers + Static / FP-Traj checkpoints
[ -f manifests/calib_static.json ]  || python -m cloq.calib --arm static  --out manifests/calib_static.json  | tail -20
[ -f manifests/calib_fp_traj.json ] || python -m cloq.calib --arm fp_traj --out manifests/calib_fp_traj.json | tail -20
build_ckpt manifests/calib_static.json  ckpts/static_w4
build_ckpt manifests/calib_fp_traj.json ckpts/fp_traj_w4
# ---------------- Phase 4: held-out evaluation of Static and FP-Traj (+ open-loop, divergence)
serve_agent ckpts/static_w4 static
run_arm static_eval static manifests/eval_tasks_v0.json ckpts/static_w4
openloop_div static static_eval
judge static_eval
serve_agent ckpts/fp_traj_w4 fp_traj
run_arm fp_traj_eval fp_traj manifests/eval_tasks_v0.json ckpts/fp_traj_w4
openloop_div fp_traj fp_traj_eval
judge fp_traj_eval
# ---------------- Phase 5: Q0 (= FP-Traj W4) closed-loop on calibration tasks
run_arm q0_fp_traj q0 manifests/cal_tasks_v0.json ckpts/fp_traj_w4
# ---------------- Phase 6: CLOQ buffer + checkpoint
[ -f manifests/calib_cloq.json ] || python -m cloq.calib --arm cloq --q-run q0_fp_traj --out manifests/calib_cloq.json | tail -20
build_ckpt manifests/calib_cloq.json ckpts/cloq_w4
# ---------------- Phase 7: CLOQ held-out evaluation
serve_agent ckpts/cloq_w4 cloq
run_arm cloq_eval cloq manifests/eval_tasks_v0.json ckpts/cloq_w4
openloop_div cloq cloq_eval
judge cloq_eval
# ---------------- Phase 8: occupancy analysis (HF BF16 extractor on GPU1; agent server stopped)
scripts/stop_vllm.sh 8001 >/dev/null; sleep 2
CUDA_VISIBLE_DEVICES=1 python -m cloq.occupancy extract --runs bf16 static_eval fp_traj_eval cloq_eval q0_fp_traj 2>&1 | tail -12
python -m cloq.occupancy analyze --arm-runs static=static_eval fp_traj=fp_traj_eval cloq=cloq_eval --calib static=manifests/calib_static.json fp_traj=manifests/calib_fp_traj.json cloq=manifests/calib_cloq.json --rep last 2>&1 | tail -3
python -m cloq.occupancy analyze --arm-runs static=static_eval fp_traj=fp_traj_eval cloq=cloq_eval --calib static=manifests/calib_static.json fp_traj=manifests/calib_fp_traj.json cloq=manifests/calib_cloq.json --rep obs 2>&1 | tail -3
# ---------------- integrity + report
python -m cloq.integrity --arm-runs static=static_eval fp_traj=fp_traj_eval cloq=cloq_eval --calib static=manifests/calib_static.json fp_traj=manifests/calib_fp_traj.json cloq=manifests/calib_cloq.json 2>&1 | tail -20 || true
python -m cloq.report --arm-runs static=static_eval fp_traj=fp_traj_eval cloq=cloq_eval
log "PIPELINE DONE"
