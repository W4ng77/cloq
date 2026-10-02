#!/bin/bash
# Launch one vLLM OpenAI server on the given GPUs (tensor parallel over all of them).
# usage: serve.sh <gpus e.g. 0 or 2,3> <port> <model dir or hf id> <served name> <max_model_len> [extra vllm args...]
# env: CLOQ_TOOL_PARSER (hermes), GPU_UTIL (0.90), CLOQ_TOKENIZER_MODE (unset = vLLM default; W99p m24: mistral)
# Combo-kernel fusion is fixed on (vLLM's default decides it by benchmarking, i.e. by timing): with
# TORCHINDUCTOR_DETERMINISTIC=1 Inductor refuses that benchmark, and it would be another node-dependent choice (W3).
set -euo pipefail
source /data/ziyangs/cloq/scripts/a6000/env.sh
GPUS=$1; PORT=$2; MODEL=$3; NAME=$4; MAXLEN=$5; shift 5
export CUDA_VISIBLE_DEVICES=$GPUS
TP=$(awk -F, '{print NF}' <<<"$GPUS")
exec vllm serve "$MODEL" --served-model-name "$NAME" --port "$PORT" --host "${CLOQ_SERVE_HOST:-127.0.0.1}" \
  --dtype bfloat16 --max-model-len "$MAXLEN" --gpu-memory-utilization "${GPU_UTIL:-0.90}" \
  --tensor-parallel-size "$TP" --generation-config vllm --seed 0 \
  --enable-auto-tool-choice --tool-call-parser "${CLOQ_TOOL_PARSER:-hermes}" --max-logprobs 20 \
  ${CLOQ_TOKENIZER_MODE:+--tokenizer-mode "$CLOQ_TOKENIZER_MODE"} \
  --compilation-config '{"inductor_compile_config": {"combo_kernels": true, "benchmark_combo_kernel": false}}' "$@"
