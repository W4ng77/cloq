# CLOQ research log — every version, insight and work item, with TL;DR and evidence

**TL;DR** — The calibration method (CLOQ) was falsified at v1. The paper is now about *perturbation equivalence*:
judge a compressed agent against the model's own perturbation null. The A6000 multi-model matrix has been running
since 2026-09-28 18:10. The live dashboard is https://claude.ai/artifact/PqFrT9bVufKqdkD43u5c1B.

Paths are relative to the repo root unless they start with `/data/` (cluster only; not in git). Stable ids:
versions `V*`, insights `I*` (iteration-scoped in `docs/insights/`), experiment proposals `E*`, work items `W*`.
Newest first.

---

## V6 · Insight loop, iteration 1 (2026-09-29, in discussion)
**TL;DR** Four candidates (I1–I4), repositioned against the literature. The per-step margin model is inherited
from Du et al. 2026. Our claims are the closed-loop composition, saturation along δ, a later damage threshold, and
cross-model transfer.
- Candidates: `docs/insights/iter_1_candidates.md`. Scripts: `analysis/insights/iter_1/s0*.py`.
  Outputs: `analysis/insights/iter_1/out/*.json` (snapshot `s00_snapshot.json`, 2026-09-29T01:26Z).
- Literature: `docs/insights/SURVEY.md`, `docs/insights/survey_sweeps/{margins_flips_divergence,compressed_agents_eval_noise,equivalence_null_criteria}.md`,
  `analysis/insights/references_new.bib`.
- Discussion (survey + experiment round 1): `docs/insights/iter_1_discussion.md`. Plan: `docs/insights/EXPERIMENTS.md`.
- Agent roles: `~/.claude/agents/cloq-{insight,survey,experiment,verify}.md` (on the cluster login node).
- **Verifier (iter 1, 2026-09-29 02:36Z):** I1 REVISE (v2: per-decision hazard floor), I2 HYPOTHESIS, I3 HYPOTHESIS (at risk: q8 RTN-W4), I4 HYPOTHESIS with I4a HELD (serving numerics move the canonical score ±8 pp). Also: legacy→a6k2 changed the user simulator (11/20 det tasks), so E5 needs the eager null. `docs/insights/iter_1_verdicts.md`, `docs/insights/LEDGER.md`, scripts `analysis/insights/iter_1/verify/v0{1..4}_*.py`.

## W9 · Llama-3.1-8B (l8) in the τ²-bench harness (2026-09-28 23:59 PDT)
**TL;DR** The l8 smoke run's 5 `infrastructure_error` episodes ("object of type 'NoneType' has no len()") were our
local prompt rendering, not the server. tau2's `to_litellm_messages` gives every assistant text turn `tool_calls: None`.
The Llama-3.1 template tests `'tool_calls' in message` and then takes `tool_calls|length`, so it crashed. The Qwen
template only tests truthiness. vLLM drops a None `tool_calls` and parses string `arguments` into dicts before it
renders, so it never crashed. Fix: `cloq/context_policy.template_view` applies the same normalisation before every
local render. Local prompt ids now equal the server's (smoke v1 17.5% → v2 100%). Qwen is byte-identical: 960 replayed
q4/q8/q30a3 decisions give the same text and match the server ids. l8 now uses the official meta repo, pinned. It also
sets `tools_in_user_message=false`, because by default the template relabels tau2's assistant greeting as a user turn
that carries the tool list. vLLM's `examples/tool_chat_template_llama3.1_json.jinja` is not in the wheel. We did not
adopt it: it has the same `tool_calls` test, and it stamps `strftime_now` (today's date) into the prompt. Smoke v2
(20 det tasks): no infra errors. airline db 0.2 / reward 0.2 / tool_err 0.22; retail db 0.2 / reward 0.0 /
tool_err 0.67 (q4: 0.04 / 0.16). The retail tool errors come from the model: it invents identifiers (21/38 "User not
found") and passes JSON arrays as strings (11/38). The template ablation gives the same retail rate (0.67).
- Code: `cloq/context_policy.py` (`template_view`, used by `render_prompt`/`render_prompt_ids`). Test:
  `tests/test_template_view.py` replays logged decisions (Qwen: identical text and 100% server-id match; l8: the raw path
  crashes on 165/165, `template_view` matches the server on 165/165). A synthetic case reproduces the crash.
- Model: `scripts/a6000/models.json` l8 = `meta-llama/Llama-3.1-8B-Instruct@0e9e39f249a16976918f6564b8830bc894c89659`.
  The 4 safetensors sha256 equal the unsloth mirror's (2b1879f3…, 09d433f6…, fc1cdddd…, 92ecfe1a…), and
  `hf cache verify` checked 14 files. The tokenizer encodes identically (57/57 prompts). The unsloth config/generation_config
  differ only in eos/pad metadata. The agent canary hash equals the unsloth one (`cbabe9a77c80c825`; old ref kept as
  `analysis/determinism/canary_agent_l8.unsloth.json`). The unsloth mirror was removed with `hf cache rm`. It freed only
  17 MB, because the shared blob store already deduplicated the weights with the meta repo.
- Runs: `/data/ziyangs/cloq/runs/a6k2_smoke_l8_v2/` (fix + `tools_in_user_message=false`) and
  `/data/ziyangs/cloq/runs/a6k2_smoke_l8tum/` (fix + default template, ablation: airline db 0.3 / tool_err 0.16 /
  16 tool calls per task with one max_steps; retail db 0.1 / tool_err 0.67). The ablation code `l8tum` was removed from
  models.json. Failed v1: `/data/ziyangs/cloq_work/queue/failed/a6k2_smoke_l8.json`, `/data/ziyangs/cloq_work/logs/tasks/a6k2_smoke_l8.log`.
- Consequence: l8's high retail tool-error rate belongs to the model, not to the harness. Treat l8 as a
  low-capability family (floor effects on db_match) when reading its perturbation nulls.

## W8 · Duplicate decision records from resumed runs; more infra-error runs (2026-09-28 23:45 PDT)
**TL;DR** tau2's `auto_resume` and retries re-run a simulation, but `cloq.agent` appends to decisions.jsonl. So an
interrupted or retried task kept the records of its abandoned attempt (6,724 records in 52 run-domains). Outcomes were
unaffected (trajectory.jsonl is rebuilt from the final results), but per-decision analyses were polluted. Fix:
`scripts/a6000/dedup_decisions.py` keeps the last attempt per task (applied to all a6k2 runs; the remaining count
mismatches are only infrastructure-error episodes), and `cloq/run_arm.py` now does the same at the end of every run.
The rescan found 6 more runs with simulator-outage episodes from before the W6 guard; they were deleted and re-queued
(`*_redo`). Also: the runners on node004/005/007 crashed on an unknown model code (l8) after my W5 change. Their tasks
were re-queued, the runners resubmitted (49671–49673), and the runner now re-reads models.json (unknown model = not
claimable).
- Evidence: dry-run log in session; `scripts/a6000/dedup_decisions.py`; `/data/ziyangs/cloq_work/logs/node_node004_49664.out` (KeyError 'l8').
- Consequence: iter_2 analyses (p0x, c01, c02) must be re-run after the redos finish.

## W7 · X1 real deployed formats in the live pipeline (2026-09-28 23:50 PDT)
**TL;DR** Official Qwen3 AWQ-INT4 (q8/q14/q32) and FP8 (q4/q8/q14/q30a3/q32) checkpoints are served with vLLM
0.29 kernels in the a6k2 pipeline. Each cell gets canonical + 2 nonces, a node005/node004 det pair and E3 open-loop:
32 tasks, `make_tasks.py --only x1`. **KV-FP8 and bitsandbytes cannot run here** and are not queued.
Under our frozen numerics (`VLLM_BATCH_INVARIANT=1`), vLLM swaps the "deployed" kernels for batch-invariant ones:
- FP8 uses the Humming FP8 kernel (not FP8 Marlin, which vLLM rejects in batch-invariant mode).
- AWQ uses `awq_dequantize` + matmul (not awq_marlin), and it must run with FP16 activations.
The weights are the real deployed ones; the GEMM kernels are not. Smokes passed for both formats; q30a3 FP8 det pair
275/275 decisions identical so far.
- Checkpoints (HF cache `/data/ziyangs/cloq_work/hf`, pinned in `scripts/a6000/make_tasks.py::X1_HF`):
  Qwen3-8B-AWQ `4da05a8e`, 14B-AWQ `31c69efc`, 32B-AWQ `0499c3ac`, 4B-Instruct-2507-FP8 `85918040`, 8B-FP8 `220b46e3`,
  14B-FP8 `9a283b4a`, 30B-A3B-Instruct-2507-FP8 `5a5a7763`, 32B-FP8 `aa55da1e`. There is no official AWQ for the 2507
  models (q4/q30a3), so they have no AWQ cell.
- Same model variant: `analysis/x1/verify_checkpoints.py` → `analysis/x1/checkpoint_verification.json`. For all 8, the
  model card's `base_model` is exactly our BF16 repo. tokenizer.json, vocab, added/special tokens, chat_template and
  generation_config are hash-identical to our BF16 snapshot; config.json differs only in `torch_dtype` (AWQ: float16).
  The same `chat_template_kwargs` are passed: worker `model_env` is keyed by task model, so enable_thinking=false
  applies for q8/q14/q32. Smoke check: server-side prompt ids equal local BF16-tokenizer ids, 312/312 decisions; no
  thinking content.
- Code: `worker.py` ckpt kind `hf` (serve `hf_id@revision`; `runs/<id>/quantization.json` records the repo, revision
  and quantization_config) plus per-task `serve_env`; `make_tasks.py::x1` (priority 30+model; det −6; E3 ref `a6k2_<m>_bf16`,
  out `analysis/openloop/a6k2/<m>/<fmt>`); arms `x1_awq` / `x1_fp8`.
- Fix 1, FP8: Humming reads NVML device index 0 regardless of CUDA_VISIBLE_DEVICES. On node003 index 0 is the faulty card,
  so the server died with `NVMLError_Unknown`. `scripts/a6000/pyhooks/sitecustomize.py`, enabled only by
  `CLOQ_PYHOOKS=1` (FP8 tasks' `serve_env`; `env.sh` adds the dir to PYTHONPATH), remaps index i → CUDA_VISIBLE_DEVICES[i]
  inside humming only. Log: `/data/ziyangs/cloq_work/logs/x1/smoke1_failed_nvml.json`.
- Fix 2, AWQ: with BF16 activations the batch-invariant path crashes (`awq_dequantize` expects Half,
  `/data/ziyangs/cloq_work/logs/tasks/a6k2_det_q14_x1_awq_b.vllm.log`). AWQ cells therefore add `--dtype float16`, which is the
  checkpoints' config dtype and vLLM's default. This is a second difference from BF16 besides the weights. FP8 stays BF16.
- Dropped formats:
  - kv_fp8: on SM86, Triton attention refuses an FP8 KV cache ("native FP8 requires SM89+",
    `/data/ziyangs/cloq_work/logs/x1/withdrawn_kv_fp8/`). FA2 has FP8 KV only on SM90+, FlexAttention has none, and
    FlashInfer is not batch-invariant, so it is excluded under our protocol (vllm `v1/attention/backend.py:321`).
  - bnb: `--quantization bitsandbytes` was removed in vLLM 0.29 (not in `QUANTIZATION_METHODS`), and bitsandbytes is
    not installed.
- Smokes: `runs/a6k2_smoke_x1_q8_fp8` (det tasks, node005; retail 0.30, airline 0.10) and `runs/a6k2_smoke_x1_q8_awq`
  (node003; retail 0.20, airline 0.10; 1226 s vs 251 s for FP8, because the dequant path is slow). Downloads: `/data/ziyangs/cloq_work/logs/x1/download.{py,log}`.
- Open: an X1 variant with `CLOQ_BATCH_INVARIANT=0` would run the actual Marlin kernels, at the cost of batch-dependent
  numerics. `serve_env` supports it. A BF16 + TRITON_ATTN control would matter only if KV-FP8 ever becomes possible.

## W6 · Simulator outages scored as agent failures (2026-09-28 23:10 PDT)
**TL;DR** node003 uses node004's user simulator. When I restarted node004 (19:43 and ~21:50), node003 episodes ended in
`infrastructure_error`, yet the tasks exited rc=0. 11 run-families had ≥2 such episodes (q4 nulls n3–n5 were 100%).
Scored as failures, they would have fabricated +8–16 pp "gains" and a −23 pp q8 W3 "loss". Fix: those runs were
deleted and re-queued as `*_redo`, pinned to nodes with their own simulator. The worker now fails any run with an
infrastructure_error. Analyses treat such episodes as missing (`analysis/insights/iter_2/common.py` INFRA).
- Evidence: `docs/insights/iter_2_prep.md` §0 F1; `/data/ziyangs/cloq_work/logs/tasks/a6k2_q4_bf16.log` ("Connection
  refused"); fix `scripts/a6000/worker.py` (termination_reasons check).
- Also queued: E8 FP32-head control (`a6k2_*fp32h*`, spec in `docs/insights/iter_2_prep.md` §E8).

## W5 · TP=2 starvation fix (2026-09-28 22:00 PDT)
**TL;DR** A freed card was always taken by a 1-GPU task, so no NVLink pair ever became free. At 21:49, q30a3 and q32
main cells stood at 5 and 3 done with 0 running. Fix: while a runnable 2-GPU task waits, the upper agent pairs
(4,5)(6,7) take only 2-GPU tasks. Runners on node004/005/007 were restarted (jobs 49664/49665/49666).
- Evidence: queue counts at 21:49 in this entry. Fix: `scripts/a6000/noderunner.py` (`tp2_wait`, `reserved`).

## W4 · TP=2 on NVLink pairs only (2026-09-28 20:45 PDT)
**TL;DR** `a6k2_q32_bf16_cal` hung in NCCL init on node005 GPUs 5,6, a cross-switch pair with no NVLink. The runner now
gives 2-GPU tasks only NVLink pairs (0,1)(2,3)(4,5)(6,7), and single-GPU tasks prefer broken pairs. This likely also
explains the earlier node007 TP=2 hangs. Runners on node004–007 were restarted (jobs 49638/49639/49641/49642; node006
is down to 4 GPUs because mg546924 took 4).
- Evidence: `/data/ziyangs/cloq_work/logs/tasks/a6k2_q32_bf16_cal.vllm.log` (stops after `pynccl.py:113`), topology
  from `nvidia-smi topo -m` (NV4 within pairs, NODE/SYS across). Fix: `scripts/a6000/noderunner.py` (allocation).

## W3 · Cross-node determinism incident (2026-09-29, root cause found, fix deployed)
**TL;DR** torch Inductor picked the reduction config for the fused residual+RMSNorm kernel by timing it at compile
time: R0_BLOCK 2048 on node005 vs 4096 elsewhere. The summation order changed, so every token shifted, and vLLM batch
invariance does not cover this. Fix: `TORCHINDUCTOR_DETERMINISTIC=1` plus a numerics canary at every server start.
The whole matrix is re-run as `a6k2_*`; old `a6000_*` runs are kept as a legacy "numerics flavour" null (E5).
- Symptom: `runs/a6000_det_q4_a` (node005) vs `runs/a6000_det_q4_b` (node004): 20/20 tasks and 113/113
  identical-prompt decisions shift; `analysis/insights/iter_1/out/s04_node_floor.json`,
  `analysis/insights/iter_1/exp/e_detshift.py`.
- Kernels are identical across nodes: `/data/ziyangs/cloq_work/numtest.py` (hash `932e7dab8e342639` on node004–007).
- Runtime is not the cause: `analysis/determinism/probe_q4.json`. On node006, cold / warm / concurrent / no-prefix-cache
  all match node004 30/30; eager is a third flavour (A 14/30, B 16/30). Script `scripts/a6000/det_probe.py`.
- Root cause (experiment agent): `analysis/insights/iter_1/exp/e_bestconfig.sh`, `e_server_flavour.py`;
  discussion `docs/insights/iter_1_discussion.md` (Experiment round 1), plan E1–E6 `docs/insights/EXPERIMENTS.md`.
- Fix: `scripts/a6000/env.sh` (flag), `scripts/a6000/worker.py::check_canary`; references in
  `analysis/determinism/canary_{agent,sim}_<model>.json`; per-start log `/data/ziyangs/cloq_work/logs/canary.log`.
- **Fix verified (2026-09-28 20:00 PDT):** `runs/a6k2_det_q4_a` (node005) vs `runs/a6k2_det_q4_b` (node004): 257/257 decisions
  byte-identical (prompt + completion), identical metrics. q30a3 pair 303/303 identical. Canary log
  `/data/ziyangs/cloq_work/logs/canary.log`: sim + q4/q8/q30a3 agents match on every node so far.
- Rerun: `scripts/a6000/make_tasks.py --prefix a6k2`. Old unfinished tasks archived in
  `/data/ziyangs/cloq_work/queue/legacy_v1/`.

## W2 · A6000 matrix running (2026-09-28 18:10 →)
**TL;DR** 5 models × 30 configs + determinism pairs; 110 tasks on node003–007 (38 GPUs). Checkpoints live only in
node RAM disk.
- Plan: `docs/A6000_PLAN.md` §3. Generator: `scripts/a6000/make_tasks.py`. Runner/worker: `scripts/a6000/{noderunner,worker}.py`.
- Live queue: `docs/a6000/QUEUE.md` (snapshot pushed every 30 min); `/data/ziyangs/cloq_work/queue/{todo,running,done,failed}/`.
- Logs: `/data/ziyangs/cloq_work/logs/node_<node>_<job>.out` (runner), `.../logs/tasks/<task>.log` (worker + run_arm),
  `.../logs/tasks/<task>.vllm.log`, `.../logs/sim_<node>_<job>.log` (user simulator).
- Per-run artifacts: `runs/a6000_<model>_<config>/<domain>/{metrics,status,config,environment,model}.json`
  (in git), `decisions.jsonl` / `trajectory.jsonl` (cluster only).

## W1 · Phase 0 + environment (2026-09-28)
**TL;DR** Driver 550 cannot run the pinned cu130 stack, so we built the cu129 builds of the same versions. Code is
model-generic with per-token margins. RTN is bit-identical to v1. Smoke test passed.
- Commits `3313d01`, `724b3dc` (and later). Env notes: `env/README_A6000.md`.
- Smoke test: `/data/ziyangs/cloq_work/logs/smoke/49592.out` (3 retail tasks, 83 s, 35/35 decisions with margins,
  server/local prompt ids identical).
- RTN equivalence check (vectorized vs `cloq/gptq.rtn_quantize_linear`, W8/W4/W3 on q4 layer 0): identical — command
  in session log; code `cloq/compress.py`.
- Node GPU faults: node003 PCI 01:00.0 and E1:00.0 (probe in `scripts/a6000/node.sbatch`; log
  `/data/ziyangs/cloq_work/logs/node_node003_49601.out`).

## V5 · Perturbation null on 4B (4080, 2026-09-28 → 09-29)
**TL;DR** BF16 × 5 nonces; Static / FP-Traj / RTN × 3 nonces; 8k harness. Results arrive with release `data-4080`.
- Script: `scripts/null_rerolls.sh`. Handoff: `docs/HANDOFF_4080_FINAL.md` (when pushed).

## V4 · E4 8k vs 32k context control (4080, 2026-09-28)
**TL;DR** Removing truncation lifts every model by 0.01–0.04 and leaves the ranking almost unchanged, so the main
harness moved to 32k. A W4 checkpoint beats BF16 under both harnesses, which is a live example of re-roll noise.
- Evidence: `docs/PROGRESS_2026-09-28.md` §2 (table); script `scripts/ctx_control.sh`; runs `runs/ctx32k_*`
  (4080; in `data-4080`).

## V3 · Strategy pivot to evaluation science (2026-09-28)
**TL;DR** A 48-agent strategy workflow plus an independent recompute. Flips are decided by the state (AUC 0.93).
Open-loop NLL does not track closed-loop success (|r| ≤ 0.13). Failures are write-dominated. Loops are mostly
agent-side.
- Strategy: `docs/STRATEGY_v2.md`. Recompute: `analysis/coling/RESULTS.md` + `analysis/coling/0[1-5]_*.py`.
- Workflow analyses: `analysis/strategy_v2_workflow/{mechanism,truncation,variance}/` (e.g. `mechanism/res_churn.json`).
- Loop attribution: `analysis/coling/04_loop_attribution.py`. Retired claims / reporting conventions: `docs/PROGRESS_2026-09-28.md` §3.

## V2 · v1: 3 draws × 6 arms (4080, 2026-09-16 → 09-27)
**TL;DR** The six calibration arms cannot be told apart in closed loop (arm permutation p = 0.683 pooled / 0.368
long). The CLOQ method claim is falsified. Draw variance is amplified by the closed loop.
- Evidence: `analysis/v1/FINDINGS_V1.md`, `analysis/v1/REPORT_V1.md`, `analysis/v1/results_v1.json`,
  `analysis/V1_STATUS_2026-09-16.md`, amendments `analysis/amendments/`. Protocol: `docs/PLAN_v1.md`, `configs/frozen_v1.json`.

## V1 · v0: single draw, 4 arms (4080, ≤ 2026-09-16)
**TL;DR** Horizon amplification (short 0.000 vs long 0.189, p = 0.039). Open-loop fidelity does not predict
closed-loop success. Support shifts after the first divergence. FP-Traj +0.121 later proved a false positive
(McNemar p = 0.0195; replication −0.035).
- Evidence: `analysis/FINDINGS.md`, `analysis/REPORT.md`, `analysis/results.json`, `analysis/occupancy_obs.json`,
  figures `analysis/fig2_horizon.png`, `analysis/fig6_openloop_vs_closedloop.png`; false-positive recompute
  `analysis/coling/02_v0_gap.py` → `analysis/coling/RESULTS.md`. Protocol: `docs/PLAN_v0.md`, `configs/frozen_v0.json`.
