# W100n — g12 (google/gemma-4-12B-it) second-family gate

**Status (2026-10-02 22:42 PDT): protocol frozen, gate queued at −21; no g12 outcome exists yet.**

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

## Results

(none yet)
