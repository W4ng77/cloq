#!/bin/bash
# Launch one vLLM OpenAI server on the given GPUs (tensor parallel over all of them).
# usage: serve.sh <gpus e.g. 0 or 2,3> <port> <model dir or hf id> <served name> <max_model_len> [extra vllm args...]
# env: CLOQ_TOOL_PARSER (hermes), GPU_UTIL (0.90)
set -euo pipefail
source /data/ziyangs/cloq/scripts/a6000/env.sh
GPUS=$1; PORT=$2; MODEL=$3; NAME=$4; MAXLEN=$5; shift 5
export CUDA_VISIBLE_DEVICES=$GPUS
TP=$(awk -F, '{print NF}' <<<"$GPUS")
exec vllm serve "$MODEL" --served-model-name "$NAME" --port "$PORT" --host 127.0.0.1 \
  --dtype bfloat16 --max-model-len "$MAXLEN" --gpu-memory-utilization "${GPU_UTIL:-0.90}" \
  --tensor-parallel-size "$TP" --generation-config vllm --seed 0 \
  --enable-auto-tool-choice --tool-call-parser "${CLOQ_TOOL_PARSER:-hermes}" --max-logprobs 20 "$@"
