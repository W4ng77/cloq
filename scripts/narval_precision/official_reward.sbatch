#!/usr/bin/env bash
set -euo pipefail
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
export OMP_NUM_THREADS="$OPENBLAS_NUM_THREADS"
python_path=$1
script=$2
repo=$3
raw=$4
snapshot=$5
out=$6
"$python_path" "$script" --repo "$repo" --data "$raw" --snapshot "$snapshot" \
    --out "$out/official_reward_${SLURM_JOB_ID:?}.json"
