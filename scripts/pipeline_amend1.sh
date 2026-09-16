#!/bin/bash
# Amendment 1 / 1a arms: CLOQ-MatchedRandom and CLOQ-MatchedAlt.
# Waits for the running pipeline_v1.sh to finish, then quantizes and evaluates the six
# control checkpoints exactly as stages 5-7 treat the twelve pre-registered ones.
#   a1 quantize 6 checkpoints            both GPUs, no simulator
#   a2 dev evaluation + divergence+judge simulator GPU0 + agent GPU1
#   a3 open-loop replay                  simulator GPU0 + agent GPU1
#   a4 occupancy extraction + v1 report  both GPUs, no simulator
# usage: pipeline_amend1.sh [a1 a2 a3 a4]   (default: wait, then all four)
set -uo pipefail
cd /home/xinyu/cloq
source ~/miniconda3/etc/profile.d/conda.sh && conda activate cloq
export PYTHONUNBUFFERED=1
MODEL=Qwen/Qwen3-4B-Instruct-2507; REV=cdbee75f17c01a7cc42f958dc650907174af0554
DOMAINS="retail airline"; DRAWS="c1 c2 c3"; ARMS="cloq_matched_random cloq_matched_alt"
log() { echo "[$(date '+%F %T')] $*"; }
stop_all() { scripts/stop_vllm.sh 8000 >/dev/null 2>&1; scripts/stop_vllm.sh 8001 >/dev/null 2>&1; sleep 3; }
serve_user() {
  if scripts/wait_server.sh 8000 5 >/dev/null 2>&1; then return; fi
  (GPU_UTIL=0.9 nohup scripts/serve_vllm.sh 0 8000 $MODEL user 32768 --revision $REV > logs/v1/vllm_user_a1.log 2>&1 &)
  scripts/wait_server.sh 8000 900
}
serve_agent() {
  scripts/stop_vllm.sh 8001 >/dev/null 2>&1; sleep 2
  m=$1; n=$2; shift 2
  (nohup scripts/serve_vllm.sh 1 8001 "$m" agent 9216 "$@" > logs/v1/vllm_agent_$n.log 2>&1 &)
  scripts/wait_server.sh 8001 900
}
eval_ckpt() {
  # `local` matters: without it the domain loop clobbers the caller's draw variable $d,
  # which is how stage 5 of pipeline_v1.sh ended up addressing runs/static_airline_dev.
  local rid=$1 arm=$2 tf=$3 ck=$4 d
  for d in $DOMAINS; do
    if [ -f runs/$rid/$d/status.json ] && grep -q '"completed"' runs/$rid/$d/status.json; then log "$rid/$d done"; continue; fi
    log "running $rid/$d"
    python -m cloq.run_arm --run-id $rid --arm $arm --domain $d --task-file $tf --checkpoint $ck 2>&1 \
      | grep -vE "^INFO|Using data|DEBUG|isn.t mapped" | tail -8
  done
}
wait_for_v1() {
  # do not compete with the main pipeline for the GPUs
  while pgrep -f "bash scripts/pipeline_v1[.]sh" > /dev/null; do sleep 60; done
  log "pipeline_v1.sh is no longer running; proceeding"
  if grep -q "PIPELINE V1 DONE" logs/v1/pipeline_s567.log 2>/dev/null; then
    log "stage 5-7 completed normally"
  else
    log "WARN stage 5-7 did not print PIPELINE V1 DONE; continuing anyway (GPUs are free)"
  fi
  stop_all
}
a1() {
  stop_all
  for a in $ARMS; do for d in $DRAWS; do
    [ -f manifests/v1/calib_${a}_${d}.json ] || { log "MISSING manifests/v1/calib_${a}_${d}.json"; exit 1; }
  done; done
  bash scripts/quantize_queue.sh 0 cloq_matched_random_c1 cloq_matched_alt_c2 cloq_matched_random_c3 > logs/v1/quant_a1_gpu0.log 2>&1 &
  bash scripts/quantize_queue.sh 1 cloq_matched_alt_c1 cloq_matched_random_c2 cloq_matched_alt_c3 > logs/v1/quant_a1_gpu1.log 2>&1 &
  wait
}
a2() {
  serve_user
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
a3() {
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
a4() {
  stop_all
  H=""; T=""
  for d in $DRAWS; do H="$H cloq_matched_random_${d}_dev"; T="$T cloq_matched_alt_${d}_dev"; done
  CUDA_VISIBLE_DEVICES=0 python -m cloq.occupancy extract --runs $H > logs/v1/reps_a1_gpu0.log 2>&1 &
  CUDA_VISIBLE_DEVICES=1 python -m cloq.occupancy extract --runs $T > logs/v1/reps_a1_gpu1.log 2>&1 &
  wait
  python -m cloq.report_v1 2>&1 | tail -30 || log "WARN report_v1 failed"
}
mkdir -p logs/v1
STAGES="${*:-a1 a2 a3 a4}"
if [ "${1:-}" != "--no-wait" ]; then wait_for_v1; else shift; STAGES="${*:-a1 a2 a3 a4}"; fi
for s in $STAGES; do log "=== $s starting"; $s; log "=== $s finished"; done
log "AMENDMENT 1 PIPELINE DONE: $STAGES"
