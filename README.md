> **Current research entry:** [review packet](docs/REVIEW_PACKET.md), [execution plan](docs/EXECUTION_PLAN_20260930.md), and [storyline](docs/insights/STORYLINE_v6.md) — *Tracing the Consequences of Quantization in Closed-Loop Agents* (2026-09-30 Toronto). The implementation notes below describe the original v0 diagnostic; the linked plans cover the current multi-model A6000 program. Project log: [docs/RESEARCH_LOG.md](docs/RESEARCH_LOG.md).

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
* Task usability (frozen before any quantized run): a task enters the pool only if its BF16 episode terminated
  normally (`user_stop` / `agent_stop`). Episodes that hit the 200-step cap (the 4B user simulator sometimes never
  emits `###STOP###` and keeps exchanging pleasantries) or the tool-error cap have no well-defined horizon.

## Scoring runs that do not finish

tau2 short-circuits `evaluate_simulation` when a run did not end through normal conversation
termination (`user_stop` / `agent_stop`): it returns reward 0.0 and leaves `db_check` empty.
Treating that empty check as a missing value would silently drop exactly the held-out tasks where a
quantized agent loops to the step cap, inflating its score, so `cloq.metrics.resolved_db_match`
records those runs as `db_match = False` (which is what tau2's own reward of 0.0 means). The BF16
reference is unaffected: the task-usability rule above keeps only tasks whose BF16 episode ended
normally, so every held-out task has a real BF16 database check.

One further recorded quirk: in about 1 decision in 6000, a tool-call argument contains a non-ASCII
character (an arrow, say). litellm ships `arguments` as a JSON string with `\uXXXX` escapes while vLLM
re-renders it decoded, so the server prompt and the local rendering differ by a few tokens. The decision
record always stores the *server's* token ids, so every replay uses the true context; only the local
sha256 (used identically by all arms) differs. `cloq.integrity` reports the rate per run.

Two failure modes show up on the quantized arms and are reported, not hidden:

* **step cap** -- the agent and the simulated user exchange pleasantries until the 200-step cap.
* **infrastructure error** -- the same loop occasionally grows the (never-truncated) user-simulator
  context past its 32768-token window, the server returns 400, and tau2 exhausts its retries. Counted
  as a failure because the agent's own looping causes it; the per-arm count is in `metrics.json`
  under `termination_reasons` and must be checked before reading any result.

## Determinism and the noise floor

Measured with a proper control, not assumed. `scripts/bf16_replicate.sh` re-runs the BF16 arm on the
same held-out tasks from a **fresh vLLM launch**, with the user-simulator server left untouched:

| check | retail | airline |
|---|---|---|
| held-out success, original vs replicate | 0.362 vs 0.362 | 0.407 vs 0.407 |
| task outcomes identical | 58 of 58 | 27 of 27 |
| premature terminations | 0 | 0 |
| open-loop replay of stored BF16 contexts | 1.000 over 742 states | 1.000 over 304 states |

Agreement is 1.000 on tool names, complete tool calls **and** full free text.

So with `VLLM_BATCH_INVARIANT=1` and an identical serving configuration, this pipeline is deterministic
across launches, and the noise floor on every reported metric is zero. Every difference between arms is
a quantization effect.

Two things still have to hold, and the scripts enforce them:

1. The user-simulator server is started once and never restarted during an experiment. Changing its
   `--max-model-len` changes its outputs, which changes the observations every arm sees.
2. `VLLM_BATCH_INVARIANT=1` is required. Without it, outputs depend on batch composition: two runs of the
   same five tasks at different concurrency diverged (`runs/bi_a` vs `runs/bi_b`), while with it enabled
   two such runs agreed on 74 of 74 decisions (`runs/bi_c` vs `runs/bi_d`).

An earlier note here claimed that greedy output drifts between launches of the same weights. That was
wrong: the measurement behind it had accidentally been replayed through a small quantized test checkpoint
that was serving on the agent port at the time. The control above replaces it.

The teacher-forced NLL of BF16 on its own actions is 0.038 per token on retail and 0.040 on airline. That is
the reference floor for the NLL column: it is the model's own uncertainty about its greedy output, not a
noise term. The quantized arms sit at 0.074 to 0.094.
