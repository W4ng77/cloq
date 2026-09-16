#!/bin/bash
# CLOQ v1 pipeline (plan section 8). Idempotent: completed work is skipped.
#   stage1 quantize static x3 + fp_traj x3        both GPUs, no simulator
#   stage2 Q0 rollouts on calibration tasks       simulator GPU0 + agent GPU1
#   stage3 Q0 representations, then novelty       both GPUs, no simulator
#   stage4 quantize cloq_all x3 + cloq_novel x3   both GPUs, no simulator
#   stage5 dev evaluation of the 12 checkpoints   simulator GPU0 + agent GPU1
#   stage6 open-loop replay of the 12            simulator GPU0 + agent GPU1
#   stage7 occupancy extraction + v1 report       both GPUs, no simulator
# usage: pipeline_v1.sh stage2 stage3 ...
set -uo pipefail
cd /home/xinyu/cloq
source ~/miniconda3/etc/profile.d/conda.sh && conda activate cloq
export PYTHONUNBUFFERED=1
MODEL=Qwen/Qwen3-4B-Instruct-2507; REV=cdbee75f17c01a7cc42f958dc650907174af0554
DOMAINS="retail airline"; DRAWS="c1 c2 c3"; ARMS="static fp_traj cloq_all cloq_novel"
log() { echo "[$(date '+%F %T')] $*"; }
stop_all() { scripts/stop_vllm.sh 8000 >/dev/null 2>&1; scripts/stop_vllm.sh 8001 >/dev/null 2>&1; sleep 3; }
serve_user() {
  if scripts/wait_server.sh 8000 5 >/dev/null 2>&1; then return; fi
  (GPU_UTIL=0.9 nohup scripts/serve_vllm.sh 0 8000 $MODEL user 32768 --revision $REV > logs/v1/vllm_user.log 2>&1 &)
  scripts/wait_server.sh 8000 900
}
serve_agent() {
  scripts/stop_vllm.sh 8001 >/dev/null 2>&1; sleep 2
  m=$1; n=$2; shift 2
  (nohup scripts/serve_vllm.sh 1 8001 "$m" agent 9216 "$@" > logs/v1/vllm_agent_$n.log 2>&1 &)
  scripts/wait_server.sh 8001 900
}
eval_ckpt() {
  rid=$1; arm=$2; tf=$3; ck=$4
  for d in $DOMAINS; do
    if [ -f runs/$rid/$d/status.json ] && grep -q '"completed"' runs/$rid/$d/status.json; then log "$rid/$d done"; continue; fi
    log "running $rid/$d"
    if [ "$ck" = "-" ]; then
      python -m cloq.run_arm --run-id $rid --arm $arm --domain $d --task-file $tf 2>&1 | grep -vE "^INFO|Using data|DEBUG|isn.t mapped" | tail -8
    else
      python -m cloq.run_arm --run-id $rid --arm $arm --domain $d --task-file $tf --checkpoint $ck 2>&1 | grep -vE "^INFO|Using data|DEBUG|isn.t mapped" | tail -8
    fi
  done
}
stage1() {
  stop_all
  for d in $DRAWS; do for a in static fp_traj; do
    [ -f manifests/v1/calib_${a}_${d}.json ] || python -m cloq.calib_v1 --arm $a --draw $d --out manifests/v1/calib_${a}_${d}.json > /dev/null
  done; done
  bash scripts/quantize_queue.sh 0 fp_traj_c1 fp_traj_c3 static_c2 > logs/v1/quant_gpu0.log 2>&1 &
  bash scripts/quantize_queue.sh 1 fp_traj_c2 static_c1 static_c3 > logs/v1/quant_gpu1.log 2>&1 &
  wait
}
stage2() {
  serve_user
  for d in $DRAWS; do
    ck=ckpts/v1/fp_traj_${d}_w4
    if [ ! -f $ck/quantization.json ]; then log "MISSING $ck"; continue; fi
    serve_agent $ck fp_traj_$d
    eval_ckpt q0_v1_$d q0 manifests/cal_tasks_v0.json $ck
  done
}
stage3() {
  stop_all
  CUDA_VISIBLE_DEVICES=0 python -m cloq.occupancy extract --runs q0_v1_c1 q0_v1_c3 > logs/v1/reps_gpu0.log 2>&1 &
  CUDA_VISIBLE_DEVICES=1 python -m cloq.occupancy extract --runs q0_v1_c2 > logs/v1/reps_gpu1.log 2>&1 &
  wait
  for d in $DRAWS; do
    [ -f manifests/v1/novelty_$d.json ] || python -m cloq.novelty --draw $d --q-run q0_v1_$d --fp-calib manifests/v1/calib_fp_traj_$d.json 2>&1 | tail -16
  done
}
stage4() {
  stop_all
  for d in $DRAWS; do
    [ -f manifests/v1/calib_cloq_all_$d.json ] || python -m cloq.calib_v1 --arm cloq_all --draw $d --q-run q0_v1_$d --out manifests/v1/calib_cloq_all_$d.json | tail -16
    [ -f manifests/v1/calib_cloq_novel_$d.json ] || python -m cloq.calib_v1 --arm cloq_novel --draw $d --q-run q0_v1_$d --novelty manifests/v1/novelty_$d.json --out manifests/v1/calib_cloq_novel_$d.json | tail -16
  done
  bash scripts/quantize_queue.sh 0 cloq_all_c1 cloq_novel_c2 cloq_all_c3 > logs/v1/quant2_gpu0.log 2>&1 &
  bash scripts/quantize_queue.sh 1 cloq_novel_c1 cloq_all_c2 cloq_novel_c3 > logs/v1/quant2_gpu1.log 2>&1 &
  wait
}
stage5() {
  serve_user
  serve_agent $MODEL bf16 --revision $REV
  eval_ckpt bf16_v1 bf16 manifests/eval_tasks_v0.json -
  for a in $ARMS; do for d in $DRAWS; do
    ck=ckpts/v1/${a}_${d}_w4
    if [ ! -f $ck/quantization.json ]; then log "MISSING $ck"; continue; fi
    serve_agent $ck ${a}_${d}
    eval_ckpt ${a}_${d}_dev $a manifests/eval_tasks_v0.json $ck
    for dom in $DOMAINS; do
      [ -f runs/${a}_${d}_dev/$dom/divergence.json ] || python -m cloq.divergence --bf16-run bf16_v1 --arm-run ${a}_${d}_dev --domain $dom > /dev/null 2>&1 || log "WARN divergence ${a}_${d}/$dom"
      [ -f runs/${a}_${d}_dev/$dom/task_success.json ] || python -m cloq.nl_judge --run-dir runs/${a}_${d}_dev/$dom 2>&1 | tail -1 || log "WARN judge ${a}_${d}/$dom"
    done
  done; done
}
stage6() {
  serve_user
  for a in $ARMS; do for d in $DRAWS; do
    ck=ckpts/v1/${a}_${d}_w4
    [ -f $ck/quantization.json ] || continue
    need=0
    for dom in $DOMAINS; do [ -f runs/${a}_${d}_dev/$dom/openloop.summary.json ] || need=1; done
    if [ $need -eq 0 ]; then log "openloop ${a}_${d} done"; continue; fi
    serve_agent $ck ${a}_${d}
    for dom in $DOMAINS; do
      [ -f runs/${a}_${d}_dev/$dom/openloop.summary.json ] || python -m cloq.openloop --bf16-run bf16_v1 --arm $a --arm-run ${a}_${d}_dev --domain $dom 2>&1 | tail -2 || log "WARN openloop ${a}_${d}/$dom"
    done
  done; done
}
stage7() {
  stop_all
  RUNS=""
  for a in $ARMS; do for d in $DRAWS; do RUNS="$RUNS ${a}_${d}_dev"; done; done
  H=$(echo $RUNS | tr ' ' '\n' | grep . | head -6 | tr '\n' ' ')
  T=$(echo $RUNS | tr ' ' '\n' | grep . | tail -6 | tr '\n' ' ')
  CUDA_VISIBLE_DEVICES=0 python -m cloq.occupancy extract --runs bf16_v1 $H > logs/v1/reps2_gpu0.log 2>&1 &
  CUDA_VISIBLE_DEVICES=1 python -m cloq.occupancy extract --runs $T > logs/v1/reps2_gpu1.log 2>&1 &
  wait
  python -m cloq.report_v1 2>&1 | tail -25 || log "WARN report_v1 failed"
}
mkdir -p logs/v1 manifests/v1 ckpts/v1
for s in "$@"; do log "=== $s starting"; $s; log "=== $s finished"; done
log "PIPELINE V1 DONE: $*"
