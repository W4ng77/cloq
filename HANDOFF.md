# CLOQ — handoff

You have 4×A100 80GB. This repo was built on 2×RTX 4080 16GB, and that constraint shaped almost
every design choice in it. This document tells you what the project is asking, what state it is
in, how to run it, and specifically what is worth running on your hardware that cannot be run
on mine.

Read `docs/PLAN_v1.md` for the full protocol. This is the orientation, not the specification.

---

## 1. The question

Quantize an LLM agent to W4 and it degrades. The interesting part is *where* the degradation
comes from. The claim under test, in one line:

> A quantized agent's first behavioral divergence pushes it into states its calibration set
> never covered, and refreshing calibration with exactly those states repairs it.

The chain has four links, and v0 (finished, `analysis/FINDINGS.md`) established the first three
on τ²-bench retail+airline with Qwen3-4B:

1. **Horizon amplification.** The quantization gap lives in long tasks. Static calibration loses
   0.000 on short tasks and 0.189 on long ones, one-sided p = 0.039.
2. **Open-loop fidelity lies.** Tool-call agreement sits at 0.81–0.85 across arms while
   closed-loop success spreads 0.24–0.36. Nominal-state fidelity does not predict closed-loop
   reliability.
3. **Support shift after divergence.** Distance to the calibration buffer jumps from ~0.06
   before the first divergence to 0.12–0.30 after it.
4. **The method works.** *Not established.* Pooled `cloq − fp_traj` was −0.012, CI
   [−0.106, 0.082].

v0's diagnosis for link 4 was that calibration support was too thin to test it: a 64k **token**
budget buys only ~10 agent contexts, because one agent context is 5–8k tokens, and the on-policy
half held just 5. Every arm rested on a single draw, so draw variance and method effect were
inseparable.

**v1 fixes that and is running now.** Budget is 64000 GPTQ **activation rows**, one state per
calibration task (57 states), three independent calibration draws per arm.

---

## 2. Where things stand

Running on the origin machine as of 2026-09-16 evening, expected to finish late 2026-09-17:

| stage | what | state |
|---|---|---|
| 1–4 | 12 calibration manifests + 12 W4 checkpoints | done |
| 5 | closed-loop dev evaluation, 12 checkpoints × 3 draws | running, ~5/12 |
| 6 | open-loop replay | queued |
| 7 | occupancy extraction + `analysis/v1/REPORT_V1.md` | queued |
| A1 | 6 control checkpoints (Amendment 1/1a) | queued behind stage 7 |

**Nothing in v1 has been read yet.** The amendments below were frozen in git before any arm
produced a number, which is the whole point of them.

### The arms

| arm | calibration Q states | isolates |
|---|---|---|
| Static | none, turn-0 contexts only | the naive baseline |
| FP-Traj | none, depth-stratified BF16 states | nominal trajectory support |
| CLOQ-All | 29 random on-policy | whether on-policy states help at all |
| CLOQ-MatchedRandom | 29, depth+truncation matched to Novel | whether *late/off-nominal* states help |
| CLOQ-MatchedAlt | same, excluding Novel's own pick | same, with more power |
| CLOQ-Novel | 29 highest-novelty post-divergence | **whether the novelty score adds anything** |

The last three exist because of a confound worth understanding before you touch anything.
CLOQ-Novel changes novelty **and** trajectory depth at once: its states pile into the deepest
quartile, and deep contexts are also the truncated ones. So "CLOQ-Novel wins" would have been
indistinguishable from "we calibrated on later contexts". The matched controls hold depth,
truncation and post-divergence status fixed and randomise only *which* state in that stratum is
taken. `Novel − MatchedRandom` is therefore the contrast that actually tests the selector.

Read `analysis/amendments/` before interpreting any result. In particular: the matched stratum
is small, 63–77% of the MatchedRandom buffer coincides with Novel's, so **a null on that
contrast is inconclusive, not evidence against novelty.** That was committed in writing before
the numbers existed and should not be quietly forgotten when the numbers arrive.

---

## 3. Setup

```bash
git clone <this repo> cloq && cd cloq
bash scripts/make_portable.sh          # rewrites the origin machine's absolute paths
git clone https://github.com/sierra-research/tau2-bench third_party/tau2-bench
git -C third_party/tau2-bench checkout 2174a603f6d014ef94473ffa95957f6ce27100db
bash env/setup_env.sh                  # conda env "cloq": python 3.12, vllm 0.29.0, torch 2.13
```

`ckpts/`, `runs/`, `logs/` and `third_party/` are gitignored. You are cloning code, protocol and
calibration manifests, not 128GB of weights. The manifests under `manifests/v1/` are the
reproducibility artifacts: they pin the exact contexts and the exact activation-row indices, so
your rebuilt checkpoints should be bit-comparable to mine given the same model revision.

Model is pinned to `Qwen/Qwen3-4B-Instruct-2507` at revision `cdbee75f17c0`. Do not float it.

### Running it

```bash
bash scripts/pipeline_v1.sh stage1 stage2 stage3 stage4   # calibration + quantization
bash scripts/pipeline_v1.sh stage5 stage6 stage7          # evaluation + analysis
```

Every stage is idempotent: a completed run or an existing checkpoint is skipped, so you can kill
and resume freely. Serving assumes GPU 0 = user simulator (port 8000, never quantized) and
GPU 1 = agent (port 8001, swapped per checkpoint).

---

## 4. What your hardware makes possible

Ranked by scientific value, not by ease.

### 4.1 The context-length control — the most valuable thing you can run

This is the one control the study currently cannot answer and the one a reviewer will reach for
first.

The agent runs under an 8192-token context policy. The system prompt and tool schema alone are
~4.8k tokens, so history starts getting dropped almost immediately: **42–72% of decisions run on
a truncated context.** Every arm shares that policy, so the *method comparison is unaffected*.
But the headline phenomenon is not obviously safe:

> Is long-horizon failure caused by quantization-induced occupancy shift, or by history being
> dropped?

On 16GB I cannot separate these. On 80GB you can. Re-run a task subset at 16k and 32k context
and check whether horizon amplification survives. If it does, link 1 of the chain is solid. If
it weakens a lot, the paper's framing has to change, and it is far better to learn that now.

Change `context_policy.max_prompt_tokens` and `vllm_max_model_len_agent` in a **copy** of
`configs/frozen_v0.json`; do not mutate the frozen file.

### 4.2 More calibration draws

Draw variance is one of v1's likely findings in its own right. Same W4 recipe, same row budget,
same agent — only the calibration trajectory draw differs — and behavior swings hard: retail
mean decisions 21.8 to 35.6, airline repeated-tool-call rate 0.080 to 0.469. In ordinary LM
quantization, calibration sample choice moves perplexity in the third decimal. In a long-horizon
agent it is amplified by the closed loop into visibly different trajectories.

Three draws is the minimum that separates draw variance from method effect. Six or ten would
tighten every interval in the study, and draws are embarrassingly parallel across your four
GPUs. Add draws to `configs/frozen_v1.json` under `calibration.draws` with fresh seeds.

### 4.3 Throughput, with one important caveat

Both models are 4B. At 80GB you can co-locate the user simulator and the agent on a single GPU
and run four independent evaluation workers, instead of my one worker spread across two cards.
That turns a ~12-hour stage 5 into roughly 3 hours.

**Do not pool results across machines without re-verifying determinism.** This study leans on an
exact noise floor: v0 verified that a fresh BF16 launch reproduced all 58 retail outcomes and
replayed 742 stored contexts with 1.000 agreement, which is why any observed difference is
attributable to the arm. That guarantee depends on `VLLM_BATCH_INVARIANT=1` and on an unchanged
serving configuration. Different GPU, different kernels, possibly different outputs.

Run `scripts/bf16_replicate.sh` on your box first. Treat A100 numbers as their own replication
of the study, not as extra samples to merge into the 4080 numbers.

### 4.4 Model scale — only after v1 reads out

The natural next step is a 7B/8B agent, and your hardware makes it easy. The plan deliberately
gates it (`docs/PLAN_v1.md` §19): *do not jump to 7B solely to search for a positive result.*
If the mechanism does not hold at 4B, a bigger model is a more expensive way to be confused.
Wait for `analysis/v1/REPORT_V1.md`.

### 4.5 Evaluation set size

Dev is 58 retail + 27 airline. On airline a two-task swing moves the rate by 0.074, which is why
several v0 intervals were uninformative. τ²-bench has more tasks than the split uses. Enlarging
evaluation is explicitly the prescribed response to a moderate result, ahead of changing the
method.

---

## 5. Rules that must not be quietly broken

These are frozen and several are load-bearing for the study's validity.

- **Do not edit `configs/frozen_v*.json` or anything in `manifests/`.** Copy and branch instead.
- **Do not re-pick the method after seeing results.** The selection rule is written down in
  `docs/PLAN_v1.md` §16 and implemented in `cloq/report_v1.py`. No third selector may be
  invented once the numbers land.
- **The evaluation split is held out from calibration**, and the builder asserts it. The task
  split hash `7d167115…` appears in every manifest; if it changes, something leaked.
- **The primary endpoint is the deterministic database end-state match**, not the language
  judge. The judge is the same 4B model as the agent, because the origin machine had no external
  API. Treat judge numbers as secondary and say so in any writeup.
- **Report the match audit whether or not the control wins** (`analysis/amendments/`).

---

## 6. Known rough edges

- **A scoping bug in `scripts/pipeline_v1.sh` stage 5, already diagnosed.** `eval_ckpt` loops
  `for d in $DOMAINS` without `local`, and bash functions share the caller's scope, so the draw
  variable gets clobbered to "airline" after every call. The divergence and judge calls then
  address run ids like `static_airline_dev` and fail. **Closed-loop results are unaffected** —
  the run id is expanded at the call site, before the clobber — and only two post-hoc artifacts
  are lost. `scripts/repair_divergence_judge.sh` regenerates them idempotently.
  `scripts/pipeline_amend1.sh` has the `local` fix; `pipeline_v1.sh` will get it once the
  current run exits, since editing a bash script while it executes can corrupt it.
- `env/setup_env.sh` and most scripts assume `~/miniconda3`.
- `VLLM_USE_FLASHINFER_SAMPLER=0` is set because the origin box only had nvcc 12.4. You may not
  need it, but changing it changes numerics, so re-run the replication check if you do.
- The judge occasionally errors on a handful of tasks; counts are reported as `judge_errors`.
- The user simulator sometimes fails to end a conversation, which is what produces step-cap
  terminations. This is a known property of the zero-API setup, not a bug in an arm.

---

## 7. Where to look first

| file | what |
|---|---|
| `analysis/V1_STATUS_2026-09-16.md` | current interim report, most useful single document |
| `analysis/FINDINGS.md` | v0 results in full |
| `analysis/amendments/` | the two frozen protocol amendments and why they exist |
| `docs/PLAN_v1.md` | the protocol, including §16 selection and §19 go/rethink rules |
| `analysis/v1/REPORT_V1.md` | v1 results, once stage 7 writes it |
| `cloq/calib_v1.py` | how each arm picks its calibration states |
| `cloq/novelty.py` | the novelty score |
