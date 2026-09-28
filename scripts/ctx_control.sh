#!/bin/bash
# Context-length control: rerun dev evaluation with a 32k prompt limit instead of the frozen 8192.
# BF16 first, then the c1 checkpoint of every v1 arm. Runs go to runs/ctx32k_*. Idempotent.
set -uo pipefail
cd /home/xinyu/cloq
source ~/miniconda3/etc/profile.d/conda.sh && conda activate cloq
export PYTHONUNBUFFERED=1 CLOQ_MAX_PROMPT_TOKENS=32768
export PATH=$CONDA_PREFIX/bin:$PATH
MODEL=Qwen/Qwen3-4B-Instruct-2507; REV=cdbee75f17c01a7cc42f958dc650907174af0554
DOMAINS="retail airline"; TF=manifests/eval_tasks_v0.json
log() { echo "[$(date '+%F %T')] $*"; }
serve_user() {
  if scripts/wait_server.sh 8000 5 >/dev/null 2>&1; then return; fi
  (GPU_UTIL=0.9 nohup scripts/serve_vllm.sh 0 8000 $MODEL user 32768 --revision $REV > logs/ctx32k/vllm_user.log 2>&1 &)
  scripts/wait_server.sh 8000 900
}
serve_agent() {
  scripts/stop_vllm.sh 8001 >/dev/null 2>&1; sleep 2
  local m=$1 n=$2; shift 2
  (nohup scripts/serve_vllm.sh 1 8001 "$m" agent 33792 "$@" > logs/ctx32k/vllm_agent_$n.log 2>&1 &)
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
eval_run ctx32k_bf16 bf16 -
for a in static fp_traj cloq_all cloq_novel cloq_matched_random cloq_matched_alt; do
  ck=ckpts/v1/${a}_c1_w4
  serve_agent $ck ${a}_c1
  eval_run ctx32k_${a}_c1 $a $ck
done
scripts/stop_vllm.sh 8001; scripts/stop_vllm.sh 8000
log "ctx32k done"
