#!/usr/bin/env bash
set -euo pipefail

image=$1
mode=$2
here=$3
work=$4
shift 4
engine=$(command -v apptainer || command -v singularity) || {
  echo "Load Apptainer or Singularity before running CLOQ." >&2
  exit 1
}
repo=$(realpath "$here/../..")
tmp=${TMPDIR:-/tmp}
args=(--cleanenv --bind "$repo:$repo" --bind "$work:$work"
      --bind "$tmp:$tmp" --env "TMPDIR=$tmp"
      --env "CLOQ_CHECKOUT_REV=$(git -C "$repo" rev-parse HEAD)"
      --env "CLOQ_TAU2_REV=$(git -C "$work/tau2-bench" rev-parse HEAD)")
if [[ -n "${CLOQ_HF_HOME:-}" ]]; then
  cache=$(realpath -e "$CLOQ_HF_HOME")
  args+=(--bind "$cache:$cache" --env "CLOQ_HF_HOME=$cache")
fi
if [[ "$mode" == gpu ]]; then
  devices=${CUDA_VISIBLE_DEVICES:?Slurm must assign CUDA devices}
  if [[ "${engine##*/}" == apptainer ]]; then
    export APPTAINERENV_CUDA_VISIBLE_DEVICES="$devices"
  else
    export SINGULARITYENV_CUDA_VISIBLE_DEVICES="$devices"
  fi
  args+=(--nv --env "SLURM_JOB_ID=${SLURM_JOB_ID:?Expected a Slurm allocation}"
         --env OMP_NUM_THREADS=2 --env OPENBLAS_NUM_THREADS=2)
fi
exec "$engine" exec "${args[@]}" "$image" "$@"
