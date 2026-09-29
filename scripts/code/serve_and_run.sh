#!/bin/bash
# Serve one BF16 model on this task's GPU(s) and run the code loop against it (inside a queue "cmd" task, which
# sets CUDA_VISIBLE_DEVICES and CLOQ_TASK_PORT). serve.sh/env.sh are the campaign's (merged from master ebb8533:
# combo-kernel pin + TORCHINDUCTOR_DETERMINISTIC); the numerics canary of the tau2 campaign is checked first.
# usage: serve_and_run.sh <model code, e.g. q4> <run_id> [cloq_code.run_code args, e.g. --limit 20]
set -euo pipefail
WT=$(cd "$(dirname "$0")/../.." && pwd)
source "$WT/scripts/a6000/env.sh"
export CLOQ_ROOT=$WT PYTHONPATH=$WT
MODEL=$1; RUN=$2; shift 2
PORT=${CLOQ_TASK_PORT:-8001}
eval "$(python - "$MODEL" <<'PY'
import json, sys, shlex
m = json.load(open("/data/ziyangs/cloq/scripts/a6000/models.json"))[sys.argv[1]]
snap = f"/data/ziyangs/cloq_work/hf/hub/models--{m['hf_id'].replace('/', '--')}/snapshots/{m['revision']}"
for k, v in {"CLOQ_MODEL_ID": m["hf_id"], "CLOQ_MODEL_REVISION": m["revision"], "SNAP": snap,
             "CLOQ_CHAT_TEMPLATE_KWARGS": json.dumps(m.get("chat_template_kwargs") or {}),
             "CLOQ_TOOL_PARSER": m["parser"]}.items():
    print(f"export {k}={shlex.quote(v)}")
PY
)"
export CLOQ_TOP_LOGPROBS=5 CLOQ_MAX_PROMPT_TOKENS=32768 CLOQ_AGENT_PORT=$PORT
export CLOQ_CODE_TMP=${CLOQ_CODE_TMP:-$TMPDIR}
LOG=/data/ziyangs/cloq_work/logs/tasks/code_${RUN}.vllm.log
setsid "$WT/scripts/a6000/serve.sh" "$CUDA_VISIBLE_DEVICES" "$PORT" "$SNAP" agent 33792 >"$LOG" 2>&1 &
SPID=$!
cleanup() { kill -TERM -$SPID 2>/dev/null || true; sleep 10; kill -KILL -$SPID 2>/dev/null || true; }
trap cleanup EXIT
for i in $(seq 360); do
  curl -sf "http://127.0.0.1:$PORT/v1/models" >/dev/null && break
  kill -0 $SPID 2>/dev/null || { echo "server died"; tail -40 "$LOG"; exit 3; }
  sleep 5
done
curl -sf "http://127.0.0.1:$PORT/v1/models" >/dev/null || { echo "server did not come up"; exit 3; }
# numerics canary: the same BF16 flavour as every tau2 run of this model (reads analysis/determinism/canary_agent_<m>.json)
python - "$PORT" "$MODEL" <<'PY'
import sys
sys.path.insert(0, "/data/ziyangs/cloq/scripts/a6000")
from worker import check_canary
print("canary", check_canary(int(sys.argv[1]), sys.argv[2], "agent"))
PY
python -m cloq_code.run_code --run-id "$RUN" --arm bf16 --agent-base "http://127.0.0.1:$PORT/v1" "$@"
