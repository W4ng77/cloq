#!/bin/bash
# Run a queue of v1 quantization jobs on one GPU, sequentially. Idempotent: a checkpoint that
# already carries quantization.json is skipped.
#
# usage: quantize_queue.sh <gpu> <arm_draw> [arm_draw ...]
#   e.g. quantize_queue.sh 0 fp_traj_c1 fp_traj_c3 static_c2
set -uo pipefail
cd /home/xinyu/cloq
source ~/miniconda3/etc/profile.d/conda.sh && conda activate cloq
GPU=$1; shift
log() { echo "[$(date '+%F %T')] gpu$GPU $*"; }
for job in "$@"; do
  out=ckpts/v1/${job}_w4
  calib=manifests/v1/calib_${job}.json
  if [ -f "$out/quantization.json" ]; then log "$job already built"; continue; fi
  if [ ! -f "$calib" ]; then log "MISSING $calib"; continue; fi
  log "building $out"
  CUDA_VISIBLE_DEVICES=$GPU python -m cloq.quantize --calib "$calib" --out "$out" 2>&1 \
    | grep -E "layer 35|saved|Error|error|Traceback" | tail -3
  if [ -f "$out/quantization.json" ]; then log "$job done"; else log "$job FAILED"; fi
done
log "queue finished"
