#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 4 ]]; then
    echo "Usage: $0 CLOQ_CHECKOUT RAW_DATA_ROOT FROZEN_SNAPSHOT OUTPUT_DIR" >&2
    exit 2
fi
repo=$(realpath -e "$1")
raw=$(realpath -e "$2")
snapshot=$(realpath -e "$3")
mkdir -p "$4"
out=$(realpath -e "$4")
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
python_path=$(command -v "${CLOQ_PYTHON:-python3}")
[[ -f "$repo/analysis/fork/analyze_dev.py" && -f "$repo/manifests/fork/splits_v1.json" ]]
[[ -d "$raw/runs" && -d "$raw/analysis/fork/dev" && -s "$snapshot" ]]
sbatch --parsable --account="${SLURM_ACCOUNT:?Set SLURM_ACCOUNT to your Narval allocation}" \
    --job-name=cloq-official --time=00:45:00 --cpus-per-task=4 --mem=8G \
    --output="$out/%x-%j.out" --error="$out/%x-%j.err" \
    "$script_dir/official_reward.sbatch" "$python_path" "$script_dir/official_reward.py" "$repo" "$raw" "$snapshot" "$out"
