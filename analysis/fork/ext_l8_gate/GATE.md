# W99f — l8 (Llama-3.1-8B-Instruct) BFCL four-arm fork gate

**Verdict: FAIL. Stop this line; do not queue the formal panel.**

The machinery runs on Llama: a GPTQ-W4 d1 checkpoint was built and served, Q replay is bit-exact, and QQ no-op passes 18/18. BFCL multi-turn is still not a usable testbed for l8:

1. **BF16 is at the capability floor.** It solves 0/20 smoke items and 5/100 items of a disjoint probe; together that is 5/120 = 4.2% (Wilson 95% CI 1.8–9.4%). Qwen q4/q8/q14 BF16 solve 19.9% / 14.3% / 20.1% of the same 788-item pool.
2. **The cells carry almost no outcome variance.** All four arms fail on 17 of the 18 divergent smoke states.
3. **The protocol had to change for l8.** The official Llama-3.1 template cannot render a turn with more than one tool call. The l8 BFCL requests therefore use `parallel_tool_calls=false`, so the comparison with Qwen changes in two ways at once: model family and tool-call protocol.
4. **The strict engineering gate fails.** BB no-op and isolation each fail on 1 of 4 states. Both failures come from the same item, through a harness leak of the per-branch instance name into one observation; the model's numerics are not the cause.

Model: meta-llama/Llama-3.1-8B-Instruct @0e9e39f2 (`scripts/a6000/models.json` l8), parser llama3_json, `tools_in_user_message=false`.
Quantizer: GPTQ-W4 d1, the same method as the Qwen main experiments. B = BF16, Q = GPTQ-W4 d1.
Protocol: fork-ext-v1 (W39-extfork), gate mode, unchanged code (`scripts/ext/fork_ext.py`).
Time used: 20:16 → 21:35 PDT (about 1 h 20 min of the 4 h box). GPU use: about 1.6 GPU-h, all through the queue, all on node008, priority −14.

## Checks

| # | Check | Result | Evidence |
|---|---|---|---|
| 0 | W4 checkpoint built through the queue | **PASS** | `a6k2_l8_bf16_cal` (τ² calibration split, 469 s) → `a6k2_l8_calib_c1` → `manifests/a6k2/l8/calib_fp_traj_c1.json` (57 sequences, 64,000 rows). GPTQ W4 g128 act-order takes 532 s per build. Per-layer error is identical in the eval and fork builds. Q ckpt sha256 `90aa2de7…7345` (fork). |
| 1a | Chat template, as frozen (parallel calls allowed; r0) | **FAIL** | `ext_l8_bf16_bfcl_smoke_l8g`. 4/20 items end with `agent_parse_error`: vLLM returns HTTP 400 "This model only supports single tool-calls at once!" because the template refuses the agent's own multi-call turn. Before this gate the ext adapter scored that as an outage and would have aborted the task; it now scores it as an agent failure (W27 rule, `scripts/ext/common.py`). |
| 1b | Tool parsing with `parallel_tool_calls=false` (r1, `_sc`) | **PASS (mechanics)**, protocol deviation | `ext_l8_*_smoke_l8g_sc` and `ext_l8_bf16_bfcl_probe_l8_sc`. No item ends in a parse error (0/140). The causes per tool-call decision (BF16 smoke / W4 smoke / BF16 probe) are listed below. |
| 1c | BFCL usability (BF16 capability) | **FAIL** | BF16 solves 0/20 smoke and 5/100 probe items (base 1/25, miss_param 0/25, miss_func 3/25, long_context 1/25). Force-quit (more than 20 steps in a turn) hits 33/120 items. Failures are genuine: instance-state or execution-response mismatches, checked against the official evaluator errors. No item overflows the context. |
| 2a | QQ no-op (same configuration, live Q replaces the recorded Q) | **PASS** 18/18 | `gate_bfcl_l8_gptq_w4_d1_sc/gate.json` (`a_QQ`). Q regenerates a_Q bit-exactly at all 18 states (`q_replay_at_state`), across two independent GPTQ builds. Save/load and re-prefill pass. |
| 2b | BB no-op on BF16 mid-episode states | **FAIL** 3/4 | The failure is `313f89b3eda5cff2` (base_126, t = 9). Prompt and completion ids match through decision 10. At decision 10 the observation differs. The agent passed a call expression as an argument (`order_id='get_order_history()[0]'`). BFCL's call rewriter then prefixes it with the instance name, which contains the per-branch `model_name`, and that name appears in the error text. Branches therefore see different observations by construction. Of the 120 l8 items, only base_126 leaks this way; 0 decisions leak in the q4/q8 Qwen BFCL eval runs (22,867 decisions). |
| 2c | Branch isolation (reverse order, concurrent) | **FAIL** 3/4 | The failing state is `33153df14222950d`, the same item (base_126), with the same cause. |
| 3 | Quantized serving | **PASS** | The W4 server comes up, has its own canary (`26d04987cff36263`), and the BF16 canary matches the l8 reference (`cbabe9a77c80c825`). The W4 smoke eval finishes 20/20 items with 0 errors and solves 1/20. |
| 4 | Throughput | measured | Eval: 100 items in 439 s on 1 GPU (≈ 4.4 s/item amortised; median item 55 s). Search: 24 s/item; divergence 18/20 = 90%, t* median 2.5. Branches: 4.0 s wall per branch at concurrency 8 (median branch 19 s, p90 58 s). The gate task took 1422 s on 2 GPUs, including a 537 s GPTQ build. |
| 5 | Stop rule | **triggered** | The l8 line needed a request-protocol change, and its outcome floor leaves the four-arm cells nearly uninformative (see below). The formal panel cannot test large interaction effects at a 4% base rate, so this is reported as FAIL rather than fixed further. |

### Parse-failure causes by type, per tool-call decision

| Cause | BF16 smoke | W4 smoke | BF16 probe |
|---|---|---|---|
| Response generated more than one call; vLLM kept the first | 7/256 | 7/262 | 76/1363 (5.6%) |
| Call to a tool not offered at that step | 2/256 | 36/262 | 58/1363 |
| Tool call written as text | 2 | 0 | 0 |
| Empty response | 0 | 0 | 0 |

In r0, with parallel calls allowed, 4 of the 218 tool-call decisions were multi-call responses, and each one ended its item. Most offered-tool misses are miss_func items, where calling a held-out function is the expected failure mode.

## Smoke four-arm numbers

These come from the gate states, which are all divergent states of the frozen 20-item smoke subset. The effects are computed with the unchanged `ext_r2.r2_effects`.

- **Coverage.** 20 items searched; 18 divergent states, 2 without divergence, 0 excluded. The divergence types are tool_args, tool_name, act→talk and talk→act.
- **Arm success on the 18 states.** BB 0, BQ 1, QB 1, QQ 1. The original episodes agree: BF16 0/20 and W4 1/20.
- **Patterns (BB, BQ, QB, QQ).** `0000` × 17 and `0111` × 1 (miss_param_192: only BB fails).
- **Sums.** ΣG = 0, ΣH = 0, ΣF = −1, ΣI = +1. One state is off-diagonal and none is a strict reversal.
- **Comparison.** On Qwen BFCL GPTQ-W4 d1 divergent states, at least one arm succeeds in 23.9% (q4) and 14.1% (q8) of states. For l8 the figure is 1/18.

The development-mode smoke forks (one per category, `noop_frac` 1.0) were dropped once BF16 was seen at the floor. They would have repeated the gate's QQ checks on all-zero cells. `analyze_ext.py`/`ext_r2.py` were therefore not run on l8 dev directories; the effect functions were applied to the gate states instead (`analyze_gate.py`).

## Projected formal panel (if the main session overrides this verdict)

- **Frozen manifest.** `manifests/bfcl/bfcl_mt_l8gate_v1.json`, subset `formal_l8`: 50 per category, 200 items. The order is a sha256 hash with salt `cloq-ext-l8-v1`. It excludes the bfcl_mt_v1 dev ids, is disjoint from `smoke_l8g` (5 per category), and uses no outcome or divergence information. The probe subset (`bfcl_mt_l8probe_v1.json`, positions 55–79 in the same order) is disjoint from both.
- **Staged tasks (not queued).** `/data/ziyangs/cloq_work/staged/w99f_l8_formal/` holds 2 evals (BF16 and W4 on `formal_l8`) and 4 dev forks, one per category, each on 2 GPUs with QQ no-op at 10%. Outputs go to `analysis/fork/ext_l8/dev/`, outside the Qwen pools of analyze_ext/ext_r2. Priority −14, no node pin. To queue: `cp /data/ziyangs/cloq_work/staged/w99f_l8_formal/*.json /data/ziyangs/cloq_work/queue/todo/`. The `a6k2_l8_calib_c1` dependency is already done.
- **Cost.** About 4 GPU-h: BF16 eval ≈ 0.3 GPU-h; W4 eval ≈ 0.4 GPU-h, including a 9-minute build; 4 forks × about 25 min × 2 GPUs ≈ 3.3 GPU-h. Wall time is about 1 h with 8 free GPUs.
- **Expected yield.** About 180 divergent states, of which only about 10–20 would have any arm succeed (base rate ≈ 4–5%). Any |G|, |I| is bounded by about that share. With a 4% base rate, the panel cannot separate "no Qwen-specific effect" from "no room for an effect". The formal report would have to count tasks and divergent states separately, and the denominator would be dominated by `0000` cells.
- **Before any rerun, fix the harness leak (≈ 1 h).** Map the per-branch instance name back to the canonical `cloq_agent_<id>` name in BFCL observations, or exclude items whose observations contain an instance name. In either case, re-run the gate first.

## Backup: q14 (Qwen3-14B, same family)

Everything else needed for a BFCL four-arm cell is already in place.

- **Evals.** `ext_q14_bf16_bfcl_eval` and `ext_q14_gptq_w4_d1_bfcl_eval`: done, 788 items each. Success is 20.1% (BF16) and 15.1% (W4).
- **Calibration.** `manifests/a6k2/q14/calib_fp_traj_c1.json` is committed.
- **What is still needed.** Only the 4 fork tasks. They are staged, not queued, in `/data/ziyangs/cloq_work/staged/w99f_q14_backup/`. Each task is a dev fork on 2 GPUs; outputs go to `analysis/fork/ext/dev/bfcl_q14_gptq_w4_d1_<cat>`, so they would enter the Qwen W4 pool.
- **Cost.** Scaled from q8 (40–72 min per category on 2 GPUs) by about 1.5×: about 8–14 GPU-h, and about 2 h wall on 8 GPUs.
- **Scope.** This answers a scale question within the Qwen family. It does not answer whether the effect is Qwen-specific.

## Code and protocol changes made by this gate

- `scripts/ext/common.py`
  - An HTTP error containing "only supports single tool-calls" now raises `ChatError("agent_parse_error")`, an agent failure, instead of an outage.
  - New `_ext_request_opts()` adds a model's `ext_request` fields to every ext chat request. Qwen requests are unchanged; this was checked against `gen_params()`.
- `scripts/a6000/models.json`: l8 gets `ext_request: {"parallel_tool_calls": false}`. The ext adapters read it and τ² does not.
- `cloq/quantize.py`: `source_dir()` now passes `ignore_patterns=["original/*"]`. Meta repos ship `original/*.pth`, which was not downloaded, and recent huggingface_hub rejects such a snapshot as incomplete after the 9-minute GPTQ pass. Qwen snapshots have no `original/`.
- `scripts/ext/make_manifest_l8gate.py`, `scripts/ext/make_tasks_l8gate.py`, `analysis/fork/ext_l8_gate/analyze_gate.py`: new files.
- Queue record: `queue/failed/ext_l8_gptq_w4_d1_bfcl_smoke_l8g_sc.json` is the first W4 attempt, which failed on the snapshot check. It was resubmitted and is now in `done/`.

## Evidence

- Summary: `analysis/fork/ext_l8_gate/gate_summary.json`, produced by `analyze_gate.py` with the bfcl venv python.
- Gate: `analysis/fork/ext_l8_gate/gate_bfcl_l8_gptq_w4_d1_sc/{gate.json,search.json,states/,branches/}`.
- Runs (cluster only): `runs/ext_l8_bf16_bfcl_smoke_l8g` (r0), `runs/ext_l8_{bf16,gptq_w4_d1}_bfcl_smoke_l8g_sc`, `runs/ext_l8_bf16_bfcl_probe_l8_sc`, `runs/a6k2_l8_bf16_cal`.
- Queue: `done/{a6k2_l8_bf16_cal,a6k2_l8_calib_c1,ext_l8_bf16_bfcl_smoke_l8g,ext_l8_bf16_bfcl_smoke_l8g_sc,ext_l8_gptq_w4_d1_bfcl_smoke_l8g_sc,ext_l8_bf16_bfcl_probe_l8_sc,fork_ext_gate_l8_gptq_w4_d1_bfcl_sc}.json`.
- Logs: `/data/ziyangs/cloq_work/logs/tasks/<task id>.log`.
