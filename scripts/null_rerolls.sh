#!/bin/bash
# Perturbation null for the COLING analysis paper: same weights, neutral system-prompt nonce -> trajectory re-roll.
# BF16 x5 nonces, then Static c1 / FP-Traj c1 / RTN x3 nonces (the same first three). Frozen 8192 context. Idempotent.
# Waits for the 32k control run (scripts/ctx_control.sh) to release the GPUs first.
set -uo pipefail
cd /home/xinyu/cloq
source ~/miniconda3/etc/profile.d/conda.sh && conda activate cloq
export PYTHONUNBUFFERED=1 PATH=$CONDA_PREFIX/bin:$PATH
MODEL=Qwen/Qwen3-4B-Instruct-2507; REV=cdbee75f17c01a7cc42f958dc650907174af0554
DOMAINS="retail airline"; TF=manifests/eval_tasks_v0.json
NONCES="3f9a1c07 b84e2d91 5c0d7e3a e21f6b48 9a7c4f15"
mkdir -p logs/null
log() { echo "[$(date '+%F %T')] $*"; }
while pgrep -f "scripts/ctx_control.sh" >/dev/null; do sleep 60; done
serve_user() {
  if scripts/wait_server.sh 8000 5 >/dev/null 2>&1; then return; fi
  (GPU_UTIL=0.9 nohup scripts/serve_vllm.sh 0 8000 $MODEL user 32768 --revision $REV > logs/null/vllm_user.log 2>&1 &)
  scripts/wait_server.sh 8000 900
}
serve_agent() {
  scripts/stop_vllm.sh 8001 >/dev/null 2>&1; sleep 2
  local m=$1 n=$2; shift 2
  (nohup scripts/serve_vllm.sh 1 8001 "$m" agent 9216 "$@" > logs/null/vllm_agent_$n.log 2>&1 &)
  scripts/wait_server.sh 8001 900
}
eval_run() {
  local rid=$1 arm=$2 ck=$3 d
  for d in $DOMAINS; do
    if [ -f runs/$rid/$d/status.json ] && grep -q '"completed"' runs/$rid/$d/status.json; then log "$rid/$d done"; continue; fi
    log "running $rid/$d"
    if [ "$ck" = "-" ]; then
      python -m cloq.run_arm --run-id $rid --arm $arm --domain $d --task-file $TF 2>&1 | grep -vE "^INFO|Using data|DEBUG|isn.t mapped" | tail -8
    else
      python -m cloq.run_arm --run-id $rid --arm $arm --domain $d --task-file $TF --checkpoint $ck 2>&1 | grep -vE "^INFO|Using data|DEBUG|isn.t mapped" | tail -8
    fi
  done
}
serve_user
serve_agent $MODEL bf16 --revision $REV
i=0; for n in $NONCES; do i=$((i+1)); CLOQ_PROMPT_NONCE=$n eval_run null_bf16_n$i bf16 -; done
for spec in "static ckpts/v1/static_c1_w4" "fp_traj ckpts/v1/fp_traj_c1_w4" "rtn ckpts/rtn_w4"; do
  set -- $spec; a=$1; ck=$2
  serve_agent $ck $a
  i=0; for n in $NONCES; do i=$((i+1)); [ $i -le 3 ] || break; CLOQ_PROMPT_NONCE=$n eval_run null_${a}_n$i $a $ck; done
done
scripts/stop_vllm.sh 8001; scripts/stop_vllm.sh 8000
log "null rerolls done"
