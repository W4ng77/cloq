#!/usr/bin/env bash
# Re-run the full COLING independent re-audit pipeline. CPU-only, read-only against runs/.
set -euo pipefail
cd "$(dirname "$0")"

export CUDA_VISIBLE_DEVICES=""
PY="${CLOQ_PYTHON:-$HOME/miniconda3/envs/cloq/bin/python}"

mkdir -p out figs

echo "== 01: per-checkpoint success + arm/draw-seed permutation tests =="
"$PY" 01_checkpoint_success.py

echo "== 02: v0 FP-Traj vs Static retail gap under exchangeable null =="
"$PY" 02_v0_gap.py

echo "== 03: open-loop NLL vs closed-loop success =="
"$PY" 03_openloop_vs_closedloop.py

echo "== 04: loop attribution (agent-side / simulator-side / mixed) =="
"$PY" 04_loop_attribution.py

echo "== 05: figures =="
"$PY" 05_figures.py

echo "Done. See out/*.json and figs/*.pdf, and RESULTS.md for the write-up."
