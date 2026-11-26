#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 {prepare|smoke|pilot|full|pilot-report|full-report} ABSOLUTE_WORK_DIR" >&2
  exit 2
fi
phase=$1
mkdir -p "$2"
work=$(realpath -e "$2")
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
runner="$here/fresh_w4.py"
tau2="$work/tau2-bench"
tau2_rev=2174a603f6d014ef94473ffa95957f6ce27100db
python_path=${CLOQ_PYTHON:-"$work/venv/bin/python"}

if [[ "$phase" == prepare ]]; then
  if [[ ! -d "$tau2/.git" ]]; then
    git clone --filter=blob:none --no-checkout https://github.com/sierra-research/tau2-bench.git "$tau2"
    git -C "$tau2" checkout --detach "$tau2_rev"
  fi
  [[ "$(git -C "$tau2" rev-parse HEAD)" == "$tau2_rev" ]]
  if [[ -z "${CLOQ_PYTHON:-}" && ! -x "$python_path" ]]; then
    bootstrap=${CLOQ_BOOTSTRAP_PYTHON:-}
    if [[ -z "$bootstrap" ]]; then
      for candidate in python3.12 python python3; do
        if command -v "$candidate" >/dev/null 2>&1 &&
           "$candidate" -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))'; then
          bootstrap=$(command -v "$candidate")
          break
        fi
      done
    fi
    if [[ -z "$bootstrap" ]] || ! command -v "$bootstrap" >/dev/null 2>&1 ||
       ! "$bootstrap" -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))'; then
      echo "Python 3.12 is required. Run: module spider python/3.12, then load the listed module." >&2
      echo "You can also set CLOQ_BOOTSTRAP_PYTHON to a Python 3.12 executable." >&2
      exit 1
    fi
    "$bootstrap" -m venv "$work/venv"
  fi
  # Use the upstream CUDA 12.9 binary and matching PyTorch wheels on Narval.
  vllm_wheel="https://github.com/vllm-project/vllm/releases/download/v0.29.0/vllm-0.29.0%2Bcu129-cp38-abi3-manylinux_2_28_x86_64.whl"
  vllm_wheel+="#sha256=22e8d8fec755986b3ad964004a1f8c65a55626ec948354bdbe95993e6b0289fe"
  "$python_path" -m pip install --only-binary=vllm,torch,torchvision,torchaudio \
    --extra-index-url https://download.pytorch.org/whl/cu129 \
    --extra-index-url https://flashinfer.ai/whl/ \
    "$vllm_wheel" 'torch==2.13.0+cu129' 'torchvision==0.28.0+cu129' 'torchaudio==2.11.0+cu129' \
    'transformers==5.17.0' 'litellm==1.82.6' -e "$tau2" scipy safetensors accelerate
  HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 "$python_path" -u "$runner" prepare --work "$work"
  exit
fi

[[ -x "$python_path" && -d "$tau2/data" ]] || {
  echo "Run prepare first. Missing runtime or tau2 data under $work" >&2
  exit 1
}
if [[ "$phase" == pilot-report || "$phase" == full-report ]]; then
  exec "$python_path" "$runner" "$phase" --work "$work"
fi

account=${SLURM_ACCOUNT:?Set SLURM_ACCOUNT to your Narval allocation}
gpu=${CLOQ_GPU_TYPE:-a100}
mkdir -p "$work/logs"
common=(--parsable --account="$account" --nodes=1 --ntasks=1)
eval_args=(--gpus="$gpu:4" --cpus-per-task=12 --mem=120G
           --output="$work/logs/%x-%A_%a.out" --error="$work/logs/%x-%A_%a.err")
dependency=()
case "$phase" in
  smoke)
    array=0
    limit=04:00:00
    if [[ ! -s "$work/gptq_w4/quantization.json" ]]; then
      build=$(sbatch "${common[@]}" --job-name=cloq-w4-build --gpus="$gpu:1" \
        --cpus-per-task=8 --mem=100G --time=08:00:00 \
        --output="$work/logs/%x-%j.out" --error="$work/logs/%x-%j.err" \
        "$here/run_fresh_w4.sbatch" build "$work" "$python_path" "$runner")
      echo "GPTQ-W4 build job: ${build%%;*}"
      dependency=(--dependency="afterok:${build%%;*}" --kill-on-invalid-dep=yes)
    fi
    ;;
  pilot|full)
    [[ -s "$work/blocks/00.json" ]] || {
      echo "A completed six-task smoke block is required. Run smoke first." >&2
      exit 1
    }
    if [[ "$phase" == pilot ]]; then array='1-3%1'; else array='4-20%2'; fi
    limit=12:00:00
    ;;
  *) echo "Unexpected phase: $phase" >&2; exit 2 ;;
esac

job=$(sbatch "${common[@]}" "${eval_args[@]}" "${dependency[@]}" \
  --job-name="cloq-w4-$phase" --array="$array" --time="$limit" \
  "$here/run_fresh_w4.sbatch" eval "$work" "$python_path" "$runner")
echo "W4 $phase job: ${job%%;*}"
echo "Logs: $work/logs"
