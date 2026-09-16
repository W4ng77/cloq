# CLOQ v0 — Closed-Loop Calibration for Quantized LLM Agents (2×RTX 4080 diagnostic)

Implements `/home/xinyu/llm_agent_closed_loop_quantization_plan_v0.md` on τ²-bench (retail, airline, text mode)
with Qwen3-4B-Instruct-2507. Frozen protocol: `configs/frozen_v0.json`.

## Layout

```
configs/frozen_v0.json      frozen constants (model revision, generation, context policy, quantizer, budgets, split rule)
cloq/config.py              paths + llm_args builders
cloq/context_policy.py      frozen 8192-token context function (identical for all arms)
cloq/agent.py               tau2 llm_agent + context policy + decision-state logging (registered as "cloq_agent")
cloq/run_arm.py             run one arm on one domain -> runs/<run_id>/<domain>/{config,environment,model,task_manifest,
                            decisions.jsonl,trajectory.jsonl,metrics,status}.json
cloq/nl_judge.py            offline NL-assertion judge (frozen local BF16 model) -> task_success.json
cloq/tasks.py               BF16-only characterisation + stratified calibration/evaluation split (manifests/)
cloq/calib.py               token-budget-matched calibration buffers: static / fp_traj / cloq / q_only
cloq/gptq.py, quantize.py   GPTQ core (ported from tim-gptq) + streaming layer-wise driver -> fake-quant BF16 checkpoints
cloq/openloop.py            open-loop agreement / argument F1 / teacher-forced NLL on BF16 held-out states
cloq/divergence.py          first-divergence statistics
cloq/occupancy.py           hidden-state extraction + support distance / MMD
cloq/metrics.py             tool-call normalisation, per-run summaries, paired bootstrap
cloq/integrity.py           plan §23 checks
cloq/report.py              tables, contrasts, horizon buckets, figures -> analysis/
scripts/pipeline.sh         phases 0-8 end to end (idempotent)
scripts/serve_vllm.sh       vLLM server launcher (batch-invariant, FlashInfer sampler disabled)
third_party/tau2-bench      pinned checkout (commit in frozen_v0.json)
```

## Serving

* GPU 0: user simulator (`user`, port 8000, BF16, never quantized, no truncation, temperature 0). Also the NL judge.
* GPU 1: agent (`agent`, port 8001), swapped per arm. Quantized arms are fake-quant BF16 checkpoints
  (dequantised W4 g128 weights) served through the identical BF16 path, so kernels/numerics are the same for all arms.
* `VLLM_BATCH_INVARIANT=1` for every server so greedy outputs do not depend on batch composition.
  vLLM returns `prompt_token_ids`; every decision record asserts they equal the local chat-template rendering.

## Environment

conda env `cloq` (`env/setup_env.sh`): python 3.12, vllm 0.29.0, torch 2.13.0+cu130, transformers 5.17.0,
litellm 1.82.6, tau2 1.0.1 (editable). `VLLM_USE_FLASHINFER_SAMPLER=0` because this box only has nvcc 12.4.

## Deviations / decisions recorded before any quantized run

* No external API on this machine: zero-API mode (plan §20). The user simulator and the NL-assertion judge are the
  frozen local BF16 model. Primary endpoint is therefore the deterministic DB end-state match; the official-style
  tau2 reward (DB ∧ COMMUNICATE / DB ∧ NL-judge) is secondary and can be re-judged later from stored trajectories.
* retail uses all 114 tasks at the plan's 40/60 ratio (46/68) rather than 20/30, for held-out power; airline 20/30.
* Context budget 8192 tokens as in the plan. System prompt + tool schema alone are ≈4.8k tokens, so roughly a third
  of decisions in longer tasks are truncated (recorded per decision).
