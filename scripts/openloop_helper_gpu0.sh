#!/bin/bash
# GPU0 helper for stage 6: replay open-loop checkpoints from the END of pipeline_v1.sh's order
# while that pipeline works forward from the start on GPU1. Open-loop replay never calls the
# user simulator (verified: cloq/openloop.py only uses --agent-base), so GPU0 is otherwise idle.
#
# Collision safety: a checkpoint is taken only if BOTH its summaries are missing AND stage 6 is
# still at least MARGIN positions behind it. Stage 6's position is read from the newest
# logs/v1/vllm_agent_<arm>_<draw>.log, which it writes when it swaps the agent server.
# This helper deliberately does NOT use that filename prefix for its own logs.
set -uo pipefail
cd /home/xinyu/cloq
source ~/miniconda3/etc/profile.d/conda.sh && conda activate cloq
export PYTHONUNBUFFERED=1
MARGIN=${MARGIN:-2}
ORDER=(static_c1 static_c2 static_c3 fp_traj_c1 fp_traj_c2 fp_traj_c3 \
       cloq_all_c1 cloq_all_c2 cloq_all_c3 cloq_novel_c1 cloq_novel_c2 cloq_novel_c3)
log() { echo "[$(date '+%F %T')] $*"; }

idx_of() { local n=$1 i; for i in "${!ORDER[@]}"; do [ "${ORDER[$i]}" = "$n" ] && { echo $i; return; }; done; echo -1; }
stage6_idx() {
  local f b
  f=$(ls -t logs/v1/vllm_agent_*.log 2>/dev/null | head -1) || { echo -1; return; }
  [ -z "$f" ] && { echo -1; return; }
  b=$(basename "$f" .log); b=${b#vllm_agent_}
  idx_of "$b"
}

for pid in "$@"; do while kill -0 "$pid" 2>/dev/null; do sleep 30; done; log "waited out pid $pid"; done
log "GPU0 helper starting; stage6 currently at index $(stage6_idx)"

for (( k=${#ORDER[@]}-1; k>=0; k-- )); do
  name=${ORDER[$k]}
  ck=ckpts/v1/${name}_w4
  [ -f "$ck/quantization.json" ] || { log "skip $name (no checkpoint)"; continue; }
  need=0
  for dom in retail airline; do [ -f runs/${name}_dev/$dom/openloop.summary.json ] || need=1; done
  [ $need -eq 0 ] && { log "skip $name (already done)"; continue; }
  s=$(stage6_idx)
  if [ "$s" -ge $((k-MARGIN)) ]; then
    log "STOP: stage6 at index $s is within $MARGIN of target $name (index $k); leaving the rest to it"
    break
  fi
  log "taking $name (index $k, stage6 at $s)"
  scripts/stop_vllm.sh 8002 >/dev/null 2>&1; sleep 2
  (GPU_UTIL=0.90 nohup scripts/serve_vllm.sh 0 8002 "$ck" agent 9216 > logs/v1/ol_gpu0_${name}.log 2>&1 &)
  if ! scripts/wait_server.sh 8002 900; then log "ALERT server for $name did not come up"; continue; fi
  for dom in retail airline; do
    [ -f runs/${name}_dev/$dom/openloop.summary.json ] && continue
    log "openloop $name/$dom"
    python -m cloq.openloop --bf16-run bf16_v1 --arm "${name%_c[0-9]}" --arm-run ${name}_dev \
      --domain $dom --agent-base http://127.0.0.1:8002/v1 2>&1 | tail -1 \
      || log "WARN openloop $name/$dom"
  done
done
scripts/stop_vllm.sh 8002 >/dev/null 2>&1
log "GPU0 HELPER DONE"
