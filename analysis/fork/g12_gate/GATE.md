# W100n — g12 (google/gemma-4-12B-it) second-family gate

**Verdict (2026-10-03 07:00 PDT, W100p): FAIL — check 3 (replay).** g12 is measurable (checks 1, 2, 5 and 6 pass; BF16 τ² 8/20
and BFCL 8/20 against the 10% floor) but not replayable under the frozen serving stack. The τ² fork gate fails five of its eight
sub-checks with 0 state or branch errors: idcheck Q 9/16 and B 12/16, Q replay at state 6/8, QQ no-op 1/8, BB no-op 0/4, isolation
2/4. Tool-call decisions regenerate exactly (17/17 in the fork's identity probe, 6/6 in the determinism probe). Long text replies mostly do not
(4/15 and 7/16). A fix would need new serving work after the 6 h engineering cap expired (04:27 PDT), so the gate closes as FAIL.
No formal g12 task is queued. Details are under "Results" below. The 22:42 status line is kept: "protocol frozen, gate queued at −21; no g12 outcome exists yet".

Question for the paper: what does the structure of action replacement vs continuation takeover look like in another
tool-capable model family? Either answer is useful. A similar structure adds external validity; a different one shows
that the protocol finds the boundary. The gate admits g12 only if the model is **measurable and replayable**. Rescues,
positive gains and expected interactions are never pass criteria.

Precedent: the m24 line (`analysis/fork/m24_gate/GATE.md`, W99p/W99q/W100e). The pipeline is reused unchanged except
for the model-gated items listed under "Code changes".

## Frozen model and protocol (written before any g12 run)

| Item | Value |
|---|---|
| Model | `google/gemma-4-12B-it` @ **707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7** (models.json `g12`; code unused before: `g12` not in models.json, W100n not in the log) |
| Source file | `model.safetensors`, sha256 **5a84cb313260ac447237b890387116dfa8682e49a6b44bc585ae8353abbff18d** (= the HF LFS sha256 of that revision) |
| Serving | text-only view `/data/ziyangs/cloq_work/ckpt_cache/g12_textonly_v1` (`scripts/a6000/g12_textonly.py`): the 666 `model.language_model.*` tensors, byte-identical (`--check`: 666/666 bit-equal), renamed `model.X`; dropped `model.vision_embedder.*`, `model.embed_vision.*`, `model.embed_audio.*` (11 tensors). Config = source `text_config` (`gemma4_unified_text`), architectures `Gemma4ForCausalLM`: the class and config vLLM's own `Gemma4UnifiedForConditionalGeneration` builds for its language model. Provenance and per-file sha256 in `textonly.json`. 1 GPU (TP=1); forks: B and Q one GPU each. |
| Chat template | the official `chat_template.jinja` (sha256 ae53464b…), copied byte-identical; local rendering via the HF tokenizer of the pinned revision |
| Content format | vLLM 0.29 detects the `openai` content format for this template, so the server renders content as text parts (the system turn then ends with one space). The local renderer emulates exactly that step (`cloq/context_policy.py::_openai_parts`, Gemma-4 ids only); checked against `vllm.entrypoints.chat_utils.parse_chat_messages` on a tool-call conversation (identical message lists). Per-decision check in every run: `prompt_ids_match_local`. |
| Tool parser | vLLM `--tool-call-parser gemma4` (`vllm/parser/gemma4.py`, the official parser in this vLLM) |
| Thinking | **disabled**: `chat_template_kwargs {"enable_thinking": false}` (the template default; set explicitly). The template then opens each generated model turn with an empty thought channel. |
| Stop ids | `generation_config.json` copied byte-identical: eos 1, 106 (`<turn|>`), 50; vLLM `--generation-config vllm` reads only the special tokens from it, never sampling defaults (as for every model) |
| Generation budget | identical to the existing protocol: serve.sh flags, max_model_len 33,792, `CLOQ_MAX_PROMPT_TOKENS` 32,768, greedy, the tau2 / BFCL runner budgets unchanged |
| Tool-call ids | not rendered by this template (tool results are matched to calls by id, then rendered by function name), so vLLM's random ids do not enter any prompt; no deterministic-id hook is needed (m24 needed one) |
| B / Q | B = BF16. Q = RTN-W4, g128 asymmetric, `cloq.compress rtn` (the main study's RTN grid). |
| Quantized modules | every `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj` in the 48 decoder layers: **328 linears** (`v_proj` exists only in the 40 sliding-attention layers; the 8 full-attention layers use K = V, `attention_k_eq_v`, so their quantized `k_proj` also supplies V). BF16: `embed_tokens` (tied with the LM head), all norms, `layer_scalar`. |

## Acceptance sample (frozen hash rules, ids only, written before any g12 run)

- τ²: `manifests/a6k2/g12/gate_tau2_v1.json` (sha256 fb237eb9…). Per domain, the tasks outside the 85-task panel, sorted by sha256('cloq-g12-gate-v1:'+domain+':'+id); first 10 retail + 10 airline. Nonce `sha256('cloq-g12-gate-v1|nonce')[:8]`.
- BFCL: `manifests/bfcl/bfcl_mt_g12_v1.json` (sha256 196dd734…) `gate_g12`. Per category, bfcl_mt_v1 minus its dev ids minus the 200 nmp_v1 panel ids, sorted by sha256('cloq-ext-g12-v1:'+id); first 5 (20 items). Disjoint from the formal BFCL panel.

## Serving change r1 (2026-10-02 23:20 PDT, before any g12 episode ran)

The first three g12 servers (`a6k2_g12_bf16_cal`, `a6k2_g12_bf16_gate`, `a6k2_g12_rtn_w4_gate`, node006, 23:12–23:14) died at EngineCore startup: `InductorError: No valid triton configs. OutOfMemoryError: out of resource: triton_red_fused_3 Required: 262144 Hardware limit: 101376`.
- **Cause (from the generated kernel on node006).** `triton_red_fused_3` is an Inductor *combo* kernel (three sub-kernels, `xnumel_0/1/2`, each a reduction over r0 = 512): the per-head q/k/v norms of the 512-dim full-attention layers fused by `combo_kernels: true` (serve.sh's fixed setting). Under `TORCHINDUCTOR_DETERMINISTIC=1` Inductor keeps one config per reduction, and the combo of three needs 256 KiB of shared memory; the A6000 has 99 KiB. Attention itself is not involved: vLLM selects TRITON_ATTN for Gemma 4's mixed head dims (256/512) and that loaded fine.
- **Fix (g12 only, task-level, no shared file).** Every g12 server (eval tasks and both fork roles) gets `serve_extra = ["--compilation-config", {"inductor_compile_config": {"combo_kernels": false, "benchmark_combo_kernel": false}}]`. Everything else in serve.sh is unchanged (`VLLM_BATCH_INVARIANT=1`, `TORCHINDUCTOR_DETERMINISTIC=1`, TRITON_ATTN, CUDA graphs, seed 0). With combo kernels off there is still no on-device benchmarking, so the deterministic, node-independent compile is preserved. All g12 numerics share this one flavour (B and Q alike).
- **Determinism evidence.** A task with `serve_extra` skips the worker's cross-node BF16 canary, by the worker's own rule. Cross-node and cross-server determinism is therefore established by the fork gates instead: the B and Q identity probes (idcheck: each server regenerates the recorded decisions of eval runs that may have run on other nodes and must match exactly), the QQ/BB no-ops and the same-checkpoint control. These are admission checks 3–4. The superseded task definitions are kept in `/data/ziyangs/cloq_work/staged/w100n_superseded/`. All 11 tasks were requeued (`make_tasks_g12.py gate --requeue …`) at −24, the priority set by the main session.

## Admission checks (all must pass; fixed before any g12 run)

1. **Serving.** BF16 and RTN-W4 servers start on the text-only path; the BF16 canary reference is written.
2. **Tool-call protocol exactness.** τ²: local prompt ids == server prompt ids on every decision of the BF16 and RTN-W4 gate runs; 0 parser errors (unparsed `<|tool_call>` text in content); 0 infrastructure errors. BFCL: 0 parser errors, 0 calls to tools not offered.
3. **State and budget restore; QQ and BB no-ops.** τ² and BFCL fork gates (`mode gate`): Q replay at state, QQ no-op, BB no-op, isolation, save/load, budget, re-prefill all pass; idcheck Q and B all match; 0 state / branch errors.
4. **Same-checkpoint control.** τ² and BFCL `gate_same` with B = Q = RTN-W4: shadow = a_Q, the four arms equal, no-op vs the original.
5. **BF16 capability floor**, the criterion that failed l8 (W99f; NEWMETHOD_PANEL_PROTOCOL §10): **BF16 success ≥ 10%** on the gate sample, separately for τ² (20 tasks) and BFCL (20 items). l8: 4.2% (FAIL); m24: τ² 20%, BFCL 10% (PASS). The Qwen BF16 rates on the same items are reported alongside (descriptive, as in the m24 gate).
6. Gate items disjoint from the formal panels (by construction, asserted in `make_tasks_g12.py manifests`).

A check that cannot be made to pass within the time box (6 h engineering from 22:27 PDT; 24 GPU-h of gate compute) is a
FAIL with its reason. Not criteria: RTN-W4 success, any divergence count, any arm difference.

GPTQ-W4 d1 readiness (needed only for the formal cell, not an admission check): `a6k2_g12_bf16_cal` → `a6k2_g12_calib_c1`
→ `a6k2_g12_gptq_w4_d1_gate` (build + serve on the τ² gate sample).

## Code changes (model-gated; no-op for every other model)

- `scripts/a6000/models.json`: new `g12` entry only.
- `cloq/context_policy.py`: `_OPENAI_PARTS = MODEL_ID.startswith("google/gemma-4-")`; when false, `template_view` returns exactly what it returned before.
- `cloq/quantize.py` (GPTQ path): `groups_for` drops a module that is `None` only for Gemma-4 layers (full-attention `v_proj`); `capture_layer0_inputs` additionally captures the kwargs of the first layer of every other attention type and `_layer_kwargs` swaps `position_embeddings` / `attention_mask` per layer type, only when the model type starts with `gemma4` and its layer types differ. For every other model `per_type` is None and `_layer_kwargs` returns the captured kwargs unchanged. CPU test `test_gptq_gemma4_kwargs.py` (`.out`): on a tiny random Gemma-4 stack (sliding window 8, types S S F S F) the propagated hidden state equals the model's own forward exactly (max |diff| 0.0); the pre-change path fails on the first full layer; Qwen3 groups unchanged.
- New: `scripts/a6000/g12_textonly.py`, `scripts/a6000/make_tasks_g12.py`, the two manifests, this directory.
- Not changed: worker.py, noderunner.py, serve.sh, fork_driver.py, the ext adapters, configs/frozen_v*.json, existing manifests.

## Queue (2026-10-02, −21)

`make_tasks_g12.py gate --write`: `a6k2_g12_{bf16,rtn_w4}_gate`, `ext_g12_{bf16,rtn_w4}_bfcl_gate_g12` (1 GPU),
`fork_gate_g12_rtn_w4`, `fork_gate_same_g12_rtn_w4`, `fork_ext_gate_g12_rtn_w4_bfcl`, `fork_ext_gate_same_g12_rtn_w4_bfcl`
(2 GPUs), `a6k2_g12_bf16_cal`, `a6k2_g12_calib_c1`, `a6k2_g12_gptq_w4_d1_gate`.

## Results (W100p, 2026-10-03 07:00 PDT): FAIL on check 3

All numbers come from `gate_summary.json`, regenerated by `analyze_gate.py` from the run directories, the fork outputs and the queue records.
Compute: 8.0 GPU-h of the 24 GPU-h cap, counting done tasks only (the r0 server failures were seconds).

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Serving | **PASS (start)**; canary reference not written | Every g12 server came up on the text-only path after r1: 6 eval tasks, the τ² fork's B and Q, and the determinism probe's 4 configurations. The worker skips the cross-node BF16 canary for tasks that carry `serve_extra` (r1 rule above). No `analysis/determinism/canary_agent_g12.json` exists, so cross-server determinism had to be shown by checks 3–4, and it was not. Fork servers: B canary `693414548b8799a2` and Q canary `0456198d7238c97e` (they differ, as expected). |
| 2 | Tool-call protocol exactness | **PASS** (as the frozen wording defines it) | τ²: local prompt ids == server prompt ids on **230/230** BF16 and **237/237** RTN-W4 decisions (and 218/218 GPTQ-W4 d1). 0 parser errors, 0 content with `<\|tool_call>`/`<tool_call\|>`/`<\|tool_response>`/`<\|tool>`, 0 infrastructure causes, 40/40 `user_stop`. BFCL: 0 parser errors, 0 calls to tools not offered, 0 decode errors on tool calls (273 BF16 and 303 RTN-W4 decisions). Note: 63/230 BF16 τ² decisions (and 70/237 RTN-W4) start their content with the template's empty thought channel `<\|channel>thought\n<channel\|>`. The model emits it, the `gemma4` parser leaves it in `content` because no reasoning parser is set, and it is part of user-facing text replies. This is not a tool-call parser error under the check's wording ("unparsed `<\|tool_call>` text"). The analysis script committed at 23:57 had counted the channel markers as markup. The split into `MARKUP` and `CHANNEL` was made after outcomes existed, so both counts are reported. The verdict does not depend on this. |
| 3 | State/budget restore; QQ and BB no-ops; idcheck | **FAIL** (τ²); BFCL not run | `tau2_rtn_w4/gate.json` (`fork_gate_g12_rtn_w4`, node001, 2 GPUs, 2.9 h): **idcheck Q 9/16, B 12/16; Q replay at state 6/8; QQ no-op 1/8; BB no-op 0/4; isolation 2/4** (reversed/concurrent order differs on the same server). Save/load, budget and re-prefill pass; 8 states, 0 state errors, 0 BB errors. By decision type, idcheck regenerates **17/17 tool-call decisions** and **4/15 text replies** (all mismatches are text replies of 46–482 tokens). The BFCL fork gate was never run (see "Remaining gate tasks"). |
| 4 | Same-checkpoint control | **NOT RUN** (moot) | Both gate_same tasks are in `queue/deferred/`. The verdict is already FAIL on check 3. |
| 5 | BF16 capability floor (≥ 10%) | **PASS** | τ² **8/20 = 40%** (Wilson 22–61%; retail 3/10, airline 5/10; normal stop + DB match, = official reward on all 20). BFCL **8/20 = 40%** (22–61%; base 4/5, miss_param 0/5, miss_func 2/5, long_context 2/5). On the same items (descriptive): Qwen BF16 BFCL q4 3/20, q8 1/20, q14 1/20; on the 10 gate tasks in the calibration split, g12 5/10 vs q4 4/10, q8 3/10, q14 1/10, q32 4/10. RTN-W4 (not a criterion): τ² 6/20, BFCL 5/20. |
| 6 | Gate items disjoint from the formal panels | **PASS** | Re-checked: 0/20 τ² gate ids in `eval_tasks_v0`; 0/20 BFCL gate ids in any `nmp_v1` list. 5 BFCL gate ids appear only in nmp_v1's `bfcl_selection.excluded_ids`, i.e. outside the panel. |

GPTQ-W4 d1 readiness (not a criterion): `a6k2_g12_gptq_w4_d1_gate` built and served (`a6k2_g12_gptq_w4_d1_g1`: 8/20, 20/20 `user_stop`, 218/218 prompt ids match).

**Determinism probe** (`det_probe.json`, `scripts/a6000/g12_det_probe.py`, task `g12_det_probe`, node006, 0.7 GPU-h, run by the previous gate agent after the idcheck failure at 01:04). A fresh BF16 server re-generated 22 recorded decisions (16 text replies and 6 tool calls) from `a6k2_g12_bf16_{g1,cal}`, by prompt ids, under four flag sets:

| Configuration (gate flags + one change) | = record | = own sequential cold run (cold / warm / concurrent) |
|---|---|---|
| base (the gate's flags) | 13/22 (text 7/16, tool 6/6) | 22 / 22 / 22 |
| `--no-enable-prefix-caching` | 13/22 | 22 / 22 / **13** |
| `--enforce-eager` | 14/22 | 22 / 22 / 22 |
| no prefix caching + `--no-enable-chunked-prefill` | 16/22 | 22 / 22 / 22 |

What the data show:
- One server answering one request at a time is deterministic.
- With prefix caching off, concurrent requests change 9/22 outputs. Prefill numerics then depend on which requests share a forward step, so `VLLM_BATCH_INVARIANT=1` does not make this model's prefill batch-invariant.
- No tested configuration reproduces the records (best 16/22).
- The fork's isolation failure (2/4) shows the same effect inside one server on the real fork workload.

Mechanism: **not identified.** By code reading (vLLM 0.29 `triton_unified_attention.py`), TRITON_ATTN is forced onto the 2D kernel with a fixed tile when batch invariance is on. So the split-KV attention path is excluded, and the batch-variant op is elsewhere in the Gemma 4 path. This was not tested.

Unlike m24 r1, this is not a probe artifact. m24's idcheck mismatch came from grammar-constrained chat requests replayed through an unconstrained probe. Here:
- the `gemma4` parser has no structural-tag grammar;
- the QQ, BB and isolation failures all go through the chat path itself.

**Why this cannot be fixed inside the time box.** A fix needs three things:
1. find the batch-variant op;
2. choose a new serving flavour and show that it is deterministic across servers;
3. rerun the four gate evals and all four fork gates.

Steps 1–2 are new serving debugging. The cap of 6 h from 22:27 PDT expired at 04:27 PDT. The closest tested flavour (no prefix caching + no chunked prefill) is not shown to be deterministic across servers (16/22 against the record). It would also drop prefix caching, which served 93% (B) and 96% (Q) of the fork's prompt tokens (`metrics_end`). The gate therefore closes as FAIL. As with l8 (check 5), this is a valid paper result: under the frozen deterministic serving stack, this second family is measurable but its same-state replays are not reproducible, so the protocol cannot measure its divergences.

**Remaining gate tasks.** `fork_gate_same_g12_rtn_w4`, `fork_ext_gate_g12_rtn_w4_bfcl` and `fork_ext_gate_same_g12_rtn_w4_bfcl` were moved to `queue/deferred/` at 01:44 PDT, 40 min after the τ² idcheck failure (01:03–01:04, `logs/tasks/fork_gate_g12_rtn_w4.log`). That is consistent with the previous gate agent parking them pending diagnosis; no note records who moved them. They are left there, because no outcome can change the verdict. `make_tasks_g12.py` now sets `fail_loud` on every gate_same spec (9ddb588 rule), so `gate --requeue <ids> --write` would requeue them compliantly if a characterization run is ever wanted (open question in W100p).
