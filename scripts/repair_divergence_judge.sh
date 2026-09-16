#!/bin/bash
# Repair pass for the eval_ckpt scoping bug in pipeline_v1.sh stage 5.
#
# eval_ckpt looped `for d in $DOMAINS` without `local`, so it overwrote the caller's draw
# variable. Every divergence / nl_judge call in stage 5 therefore addressed a run id like
# `static_airline_dev` instead of `static_c1_dev` and failed with FileNotFoundError.
# The closed-loop evaluations themselves are unaffected: their run id is expanded before the
# call. Only divergence.json and task_success.json were lost, and both are post-hoc over
# stored artifacts, so they can be recomputed at any time.
#
# Waits for the running pipelines to release the GPUs, then fills in every missing artifact.
# Idempotent: anything already present is skipped.
set -uo pipefail
cd /home/xinyu/cloq
source ~/miniconda3/etc/profile.d/conda.sh && conda activate cloq
export PYTHONUNBUFFERED=1
MODEL=Qwen/Qwen3-4B-Instruct-2507; REV=cdbee75f17c01a7cc42f958dc650907174af0554
log() { echo "[$(date '+%F %T')] $*"; }

for pid in "$@"; do
  while kill -0 "$pid" 2>/dev/null; do sleep 60; done
  log "pid $pid finished"
done
log "all watched pipelines done; starting repair"

# divergence needs no server at all
n_div=0
for rd in runs/*_dev; do
  [ -d "$rd" ] || continue
  rid=$(basename "$rd")
  for dom in retail airline; do
    [ -f "$rd/$dom/metrics.json" ] || continue
    [ -f "$rd/$dom/divergence.json" ] && continue
    log "divergence $rid/$dom"
    python -m cloq.divergence --bf16-run bf16_v1 --arm-run "$rid" --domain "$dom" > /dev/null 2>&1 \
      && n_div=$((n_div+1)) || log "WARN divergence failed $rid/$dom"
  done
done
log "divergence written: $n_div"

# the NL judge calls the user simulator endpoint
need_judge=0
for rd in runs/*_dev runs/bf16_v1; do
  [ -d "$rd" ] || continue
  for dom in retail airline; do
    [ -f "$rd/$dom/metrics.json" ] || continue
    [ -f "$rd/$dom/task_success.json" ] || need_judge=1
  done
done
if [ $need_judge -eq 1 ]; then
  if ! scripts/wait_server.sh 8000 5 > /dev/null 2>&1; then
    log "starting user server on GPU0"
    (GPU_UTIL=0.9 nohup scripts/serve_vllm.sh 0 8000 $MODEL user 32768 --revision $REV > logs/v1/vllm_user_repair.log 2>&1 &)
    scripts/wait_server.sh 8000 900 || { log "ALERT user server did not come up; judge skipped"; exit 1; }
  fi
  n_j=0
  for rd in runs/*_dev runs/bf16_v1; do
    [ -d "$rd" ] || continue
    rid=$(basename "$rd")
    for dom in retail airline; do
      [ -f "$rd/$dom/metrics.json" ] || continue
      [ -f "$rd/$dom/task_success.json" ] && continue
      log "judge $rid/$dom"
      python -m cloq.nl_judge --run-dir "$rd/$dom" 2>&1 | tail -1 && n_j=$((n_j+1)) || log "WARN judge failed $rid/$dom"
    done
  done
  log "task_success written: $n_j"
else
  log "no judge work needed"
fi
log "REPAIR DONE"
