#!/bin/bash
# Launch one vLLM OpenAI-compatible server.
# usage: serve_vllm.sh <gpu> <port> <model_path_or_hf_id> <served_name> <max_model_len> [extra args...]
set -euo pipefail
GPU=$1; PORT=$2; MODEL=$3; NAME=$4; MAXLEN=$5; shift 5
source ~/miniconda3/etc/profile.d/conda.sh && conda activate cloq
export CUDA_VISIBLE_DEVICES=$GPU
export VLLM_LOGGING_LEVEL=${VLLM_LOGGING_LEVEL:-INFO}
# FlashInfer JIT needs a CUDA-13 nvcc which this box lacks; greedy decoding does not need its sampler.
export VLLM_USE_FLASHINFER_SAMPLER=0
# Batch-invariant kernels so greedy outputs do not depend on batch composition (CLOQ_BATCH_INVARIANT=0 disables).
export VLLM_BATCH_INVARIANT=${CLOQ_BATCH_INVARIANT:-1}
mkdir -p /home/xinyu/cloq/logs; echo $$ > /home/xinyu/cloq/logs/vllm_port${PORT}.pid
exec vllm serve "$MODEL" \
  --served-model-name "$NAME" \
  --port "$PORT" --host 127.0.0.1 \
  --dtype bfloat16 \
  --max-model-len "$MAXLEN" \
  --gpu-memory-utilization "${GPU_UTIL:-0.92}" \
  --generation-config vllm \
  --seed 0 \
  --enable-auto-tool-choice --tool-call-parser hermes \
  "$@"
