# Fresh W4 scoring experiment on Narval

The runner regenerates the policy trajectories for Qwen3-8B GPTQ-W4 on the original 58 retail and 27 airline development tasks. It builds a checkpoint from the original committed 57-context calibration draw. Within each newly generated W4 episode (QQ), it finds the first semantic action disagreement, substitutes the BF16 action once, and continues with W4 (BQ). With no eligible disagreement, the intervention leaves the episode as recorded. This experiment tests the action-only policy in one quantized configuration.

## Run

From the repository checkout on the Narval login node, set `SLURM_ACCOUNT` to your allocation and set `WORK` to a writable absolute path on scratch.

```bash
export SLURM_ACCOUNT=YOUR_NARVAL_ALLOCATION
WORK="$SCRATCH/experiments/cloq-fresh-w4"
RUNNER=scripts/narval_precision/submit_fresh_w4.sh
bash "$RUNNER" prepare "$WORK" && bash "$RUNNER" smoke "$WORK"
```

Prepare requires Python 3.12 and login-node network access to the package index, GitHub and Hugging Face. Load the Python 3.12 module first. Use `module spider python/3.12` to find the exact version and its prerequisites. The launcher accepts Python 3.12 exposed as `python3.12`, `python`, or `python3`. Set `CLOQ_BOOTSTRAP_PYTHON` to override detection. The default environment is `$WORK/venv`. To reuse a dedicated existing environment, set `CLOQ_PYTHON` to its absolute Python executable. Prepare installs the pinned dependencies into that environment. On Narval x86-64 it uses the upstream vLLM 0.29.0 CUDA 12.9 wheel and matching PyTorch CUDA 12.9 wheels. The vLLM wheel is checksum-pinned, and these packages cannot fall back to a source build. To reuse staged model snapshots, set `CLOQ_HF_HOME` to the absolute cache root that contains `hub/` and keep it exported on submission. The two original model revisions occupy roughly 80 GB combined, plus the reconstructed W4 checkpoint. Compute jobs use cached weights and run local servers.

Smoke submits a one-GPU GPTQ build when needed, then a dependent four-GPU job. The jobs default to Narval A100s. Set `CLOQ_GPU_TYPE=h100` to select H100s if the account has access. The evaluation needs four GPUs on one node, with one each for BF16 and W4 and two for the user simulator and NL judge. Use the same GPU type throughout the production panel. Both agent servers use the same dense BF16 execution path, separate caches and batch invariance. Slurm output is under `$WORK/logs/`. The Python process uses four concurrent tasks per job.

Only proceed after `$WORK/blocks/00.json` exists. The six-task smoke replays every observed QQ fork from its restored state and checks the suffix, prompt IDs, scores, termination, environment and budget. On production blocks a deterministic 10% sample (rounded up) receives full QQ replay, while state restoration and the Q action are checked at every divergence. Inspect the failed job's logs and attempt directory if a gate does not pass.

```bash
bash "$RUNNER" pilot "$WORK"         # Blocks 1–3
bash "$RUNNER" pilot-report "$WORK"  # After blocks 1–3 finish
bash "$RUNNER" full "$WORK"          # Blocks 4–20
bash "$RUNNER" full-report "$WORK"   # After all 20 production blocks finish
```

The tasks and prompt nonces of the 20 production blocks are fixed in advance. Smoke is excluded from all reports. Keep all 20 production blocks on the same code, model, GPU and runtime configuration. The final report includes blocks 1–3, so use the pilot as an operational check without changing the design based on the observed scores.

## Apptainer on Narval

If pip rejects the host wheel tag, run prepare and all follow-up commands with `CLOQ_RUNTIME=apptainer` exported. Load the site Apptainer or Singularity module if the executable is unavailable. Prepare pulls the official vLLM 0.29.0 CUDA 12.9 image into the work directory and creates a separate container virtual environment. The host virtual environment and τ²-bench checkout remain available. The build and evaluation jobs run the same image with GPU passthrough.

```bash
export CLOQ_RUNTIME=apptainer
bash "$RUNNER" prepare "$WORK" && bash "$RUNNER" smoke "$WORK"
```

## Endpoints and outputs

Each branch is generated once. The same transcripts are scored under the DB endpoint and the official task reward basis. Airline includes the deterministic COMMUNICATE checks. Retail includes NL_ASSERTION when listed by the task. The runner uses the pinned local Qwen3-30B-A3B simulator as the NL judge with the repository's τ² judge prompt. This is the official reward basis with a local judge. It may differ from scores obtained with a different judge model. Judging happens on the saved trajectories. A malformed judgment fails the block visibly. For an episode that already fails another criterion, the overall score is zero regardless of its NL judgment.

The JSON reports give rescue, damage, net and paired changes between endpoints in percentage points, pooled and by domain. These full-pool statistics include no-divergence units as zero-effect units. The analysis reuses CLOQ's fixed-pool and crossed task-by-block interval code. Saved attempt directories retain state files, branch transcripts, reward components, NL judgments, replay audits and serving provenance. Treat the output as an independent regeneration for one W4 configuration on the original task panel.
