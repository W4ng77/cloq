# W99p — m24 (Mistral-Small-3.2-24B-Instruct-2506) second-family gate

**Verdict: see the table; the fork checks (3, 4) are filled in by `analyze_gate.py` when the 4-GPU fork gates have run.**

Model: `mistralai/Mistral-Small-3.2-24B-Instruct-2506@95a6d26c` (models.json `m24`), served **text-only** from
`/data/ziyangs/cloq_work/ckpt_cache/m24_textonly_v1` (the `language_model.*` tensors of the pinned HF shards, byte-identical,
renamed to `MistralForCausalLM`; provenance and per-file sha256 in `textonly.json`; builder `scripts/a6000/m24_textonly.py`).
Official tokenizer `tekken.json` with vLLM 0.29 `--tokenizer-mode mistral` and `--tool-call-parser mistral`; TP=2 on one NVLink pair.
B = BF16, Q = RTN-W4 (g128, `cloq.compress`, the main study's RTN grid). Fork tasks: 4 GPUs, B and Q each TP=2 on its own pair.

Acceptance sample (frozen hash rules, ids only, written before any m24 run):
- τ²: `manifests/a6k2/m24/gate_tau2_v1.json`. Per domain, the tasks outside the 85-task panel, sorted by sha256('cloq-m24-gate-v1:'+domain+':'+id); first 10 retail + 10 airline. One nonce, `sha256('cloq-m24-gate-v1|nonce')[:8]`.
- BFCL: `manifests/bfcl/bfcl_mt_m24_v1.json` `gate_m24`. Per category, bfcl_mt_v1 minus its dev ids minus the 200 nmp_v1 panel ids, sorted by sha256('cloq-ext-m24-v1:'+id); first 5 (20 items). Disjoint from the formal BFCL panel.

## Why the earlier smoke failed

`queue/failed/a6k2_smoke_m24.json`: vLLM resolved the multimodal checkpoint to `PixtralForConditionalGeneration`, whose module
imports `transformers.models.pixtral.modeling_pixtral.PixtralRotaryEmbedding`. transformers 5.17 no longer has that class, so the
architecture inspection subprocess raised ImportError and the server exited before loading. `Mistral3ForConditionalGeneration`
imports the same module. Fix: serve the language model alone (`MistralForCausalLM`), which needs no vision code.

## Checks

| # | Check | Result | Evidence |
|---|---|---|---|
| 1a | Serving (text-only path, TP=2) | **PASS** | `Resolved architecture: MistralForCausalLM`; weights 82 s from /data; KV cache 248,944 tokens (7.4× the 33,792-token context). The BF16 canary reference was written: `analysis/determinism/canary_agent_m24.json` (`2c2cdf5659344c4c`). |
| 1b | Tool protocol, τ² (mistral parser + tokenizer) | **PASS** | BF16: 207 decisions, 168 parsed tool calls (35 decisions with several calls), 0 parser errors, 0 infra errors, 20/20 normal stops. **Local prompt ids == server prompt ids on 207/207 decisions** (`cloq/mistral_render.py`). RTN-W4: 223/223, 0 parser errors. |
| 1c | Tool protocol, BFCL | **PASS** | BF16: 172 decisions, 123 tool calls, 0 parser errors, 0 calls to tools not offered, 0 decode errors on tool calls; 20/20 items completed. RTN-W4 r0: one item ended with HTTP 400 (the agent's own call with an empty function name, which mistral_common refuses to render next turn). It is now scored `agent_parse_error` (W27 rule) and the item rerun (see 1d). |
| 1d | Deterministic tool-call ids | **PASS (by construction, checked)** | The Mistral template renders `[CALL_ID]`; vLLM draws ids at random, so identical decisions would give different later prompts and no-op replays could never be bit-exact. τ²/BFCL now set id = `d<decision:05d>c<k:02d>` (m24 only). All recorded ids follow the rule. |
| 2 | BF16 capability vs Qwen | **PASS (not at floor)** | τ²: 4/20 = 20% (Wilson 8–42%). On the 16 gate tasks in the calibration split, m24 25% vs Qwen BF16 q4 19%, q8 25%, q14 38%, q32 44% (same tasks, `a6k2_<q>_bf16_cal`). BFCL: 2/20 = 10% (3–30%) vs Qwen q4 10%, q8 15%, q14 15% on the same 20 items. l8 (W99f) was 0/20 and 4.2%. RTN-W4: τ² 3/20, BFCL see summary. |
| 3 | BB and QQ no-op replay bit-exact (τ², BFCL) | PENDING | `fork_gate_m24_rtn_w4`, `fork_ext_gate_m24_rtn_w4_bfcl` (4 GPUs). |
| 4 | Same-checkpoint negative control (τ², BFCL) | PENDING | `fork_gate_same_m24_rtn_w4`, `fork_ext_gate_same_m24_rtn_w4_bfcl`. |
| 5 | BFCL leak regression (`tests/test_bfcl_instance_leak.py`) | **PASS** 9/9 | Default env and `CLOQ_TOKENIZER_MODE=mistral`: `test_bfcl_instance_leak{,_mistralmode}.out`. |
| 6 | Throughput | measured | τ² eval: 20 tasks in 662 s (BF16) / 718 s (RTN-W4, including a ~30 s RTN build and ~3 min server start) on 2 GPUs; median episode 201 s retail, 129 s airline. BFCL: 20 items in 291 s on 2 GPUs (median item 91–144 s). |
| 7 | Qwen paths unchanged | **PASS** | No m24 env → `template_view` path and random-id path untouched. `tests/test_template_view.py`: q4 257/257 server match. The q8 case gives the same counts (0/400 server match) with the pre-W99p code, so that failure predates this change (`test_template_view_qwen_unchanged.out`). Runner dry run: identical claims on a legacy queue. |

## Runner change (engineering condition 1)

`scripts/a6000/noderunner.py`: a task needing 2k > 2 GPUs (`gpus 4`, `gpus_per_role 2`) takes k whole free NVLink pairs. While one is runnable on the node, the top k agent pairs take nothing smaller, so they empty as their tasks finish. `scripts/a6000/worker.py::run_fork`: with `gpus_per_role 2`, B is served on the first pair and Q on the second. Every pre-W99p task behaves identically: the old and new runner give the same claim sequence on a dry-run legacy queue (fake clock, fake workers). Running runners pick this up only when restarted; node008 is being drained for that (coordinator).

## Files

`scripts/a6000/{noderunner.py,worker.py,serve.sh,models.json,m24_textonly.py,make_tasks_m24.py}`, `cloq/{mistral_render.py,context_policy.py,agent.py}`, `scripts/ext/{common.py,bfcl_run.py}`, `analysis/fork/m24_gate/{analyze_gate.py,gate_summary.json}`, runs `runs/a6k2_m24_{bf16,rtn_w4}_g1`, `runs/ext_m24_{bf16,rtn_w4}_bfcl_gate_m24` (cluster), logs `/data/ziyangs/cloq_work/logs/tasks/<id>.{log,vllm.log}`.
