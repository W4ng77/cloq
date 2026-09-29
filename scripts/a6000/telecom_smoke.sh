#!/bin/bash
# X3 GPU smoke: q4 BF16 agent served from the telecom worktree on this worker's card, 5 telecom tasks
# (manifests/telecom/smoke_v1.json) against the node's user simulator. Run as a queue task of kind "cmd"
# (the worker sets CUDA_VISIBLE_DEVICES and CLOQ_TASK_PORT).
# usage: telecom_smoke.sh <run_id> [task_file]
set -uo pipefail
WT=/data/ziyangs/cloq_wt/telecom
RUN_ID=${1:-telecom_smoke_q4_bf16}; TASKS=${2:-$WT/manifests/telecom/smoke_v1.json}
source /data/ziyangs/cloq/scripts/a6000/env.sh
export CLOQ_ROOT=$WT PYTHONPATH=$WT
cd $WT
M=$(python -c "import json;m=json.load(open('scripts/a6000/models.json'))['q4'];print(m['hf_id'],m['revision'])")
export CLOQ_MODEL_ID=${M% *} CLOQ_MODEL_REVISION=${M#* } CLOQ_CHAT_TEMPLATE_KWARGS='{}' CLOQ_TOOL_PARSER=hermes
export CLOQ_MAX_PROMPT_TOKENS=32768 CLOQ_TOP_LOGPROBS=5 CLOQ_AGENT_PORT=$CLOQ_TASK_PORT CLOQ_USER_PORT=8000
PORT=$CLOQ_TASK_PORT; UBASE=${CLOQ_USER_BASE:-http://127.0.0.1:8000/v1}
# the combo-kernel flag mirrors the (not yet committed) live serve.sh, required with TORCHINDUCTOR_DETERMINISTIC=1 (W3)
SNAP=$(snapshot $CLOQ_MODEL_ID $CLOQ_MODEL_REVISION)
LOG=/data/ziyangs/cloq_work/logs/tasks/${RUN_ID}.vllm.log
echo "$(date) host=$(hostname) gpus=$CUDA_VISIBLE_DEVICES port=$PORT user=$UBASE snap=$SNAP"
setsid $WT/scripts/a6000/serve.sh "$CUDA_VISIBLE_DEVICES" "$PORT" "$SNAP" agent 33792 \
  --compilation-config '{"inductor_compile_config": {"combo_kernels": true, "benchmark_combo_kernel": false}}' > "$LOG" 2>&1 &
SPID=$!
cleanup() {
  kill -TERM -- -$SPID 2>/dev/null; sleep 20; kill -KILL -- -$SPID 2>/dev/null
  for i in $(seq 30); do  # orphaned EngineCore processes hold the card
    P=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader -i "$CUDA_VISIBLE_DEVICES" 2>/dev/null)
    [ -z "$P" ] && break; kill -9 $P 2>/dev/null; sleep 2
  done
}
trap cleanup EXIT
for i in $(seq 360); do
  curl -sf -m 5 http://127.0.0.1:$PORT/v1/models >/dev/null && break
  kill -0 $SPID 2>/dev/null || { echo "vLLM died"; tail -30 "$LOG"; exit 3; }
  sleep 5
done
curl -sf -m 5 http://127.0.0.1:$PORT/v1/models >/dev/null || { echo "vLLM not up"; exit 4; }
echo "$(date) agent server up"
python -m cloq.run_arm --run-id "$RUN_ID" --arm bf16 --domain telecom --task-file "$TASKS" \
  --agent-base http://127.0.0.1:$PORT/v1 --user-base "$UBASE" --checkpoint '{"kind": "bf16"}' --note "X3 telecom smoke"
RC=$?
python - "$WT/runs/$RUN_ID/telecom" <<'PY'
import json, sys
m = json.load(open(sys.argv[1] + "/metrics.json"))
print(json.dumps({k: m.get(k) for k in ("n_tasks", "success_rate", "official_reward_mean", "reward_mean", "db_match_rate", "env_assert_rate",
      "mean_tool_calls", "mean_user_tool_calls", "tool_error_rate", "user_tool_error_rate", "mean_decisions", "premature_rate",
      "termination_reasons", "truncated_context_rate", "parser_error_rate")}, indent=1))
for r in m["per_task"]:
    print(r["task_id"][:70], r["success"], r["termination_reason"], "agent_tc", r["n_tool_calls"], "user_tc", r["n_user_tool_calls"], "dec", r["n_decisions"], "maxP", r["max_prompt_tokens"])
PY
exit $RC
