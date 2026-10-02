# W99p — m24 (Mistral-Small-3.2-24B-Instruct-2506) second-family gate

**Verdict at the end of the 6-h window (2026-10-02 06:05 PDT): NOT YET DECIDED.** Checks 1, 2 and 5–7 pass, and the BFCL halves
of checks 3 and 4 pass. The τ² fork gate (`fork_gate_m24_rtn_w4`) is still running on the restarted node008 runner. It has one known
failing sub-check, `idcheck Q 13/16`, explained below as a probe mismatch rather than a numerics fault. The τ² negative control
(`fork_gate_same_m24_rtn_w4`) is queued behind it. No new backend is needed. The formal panel is **not queued**.

**τ² idcheck finding.** fork_driver's checkpoint-identity probe regenerates recorded decisions through `/v1/completions` (raw
prompt ids, unconstrained). With `--tokenizer-mode mistral`, vLLM 0.29's mistral tool parser constrains every *chat* request that
carries tools with mistral-common's tool-call grammar (llguidance; `vllm/parser/mistral.py::adjust_request`, the official tool
path). The recorded Q decisions were therefore grammar-constrained, and the probe is not. The 3 mismatches are all single
tool calls (airline 7/t9, 15/t2, 21/t7, 18–20 tokens) where the grammar changed the greedy token. B gave 16/16 because no
constrained position changed its argmax in that sample.
- The BFCL gate replays through chat, and there the Q replay at state is bit-exact (`q_replay_at_state` true).
- For m24 the identity probe must go through chat with the same tools, or the grammar must be disabled for *all* m24 serving
  (`--structured-outputs-config` / tool_choice handling). The latter would change the official tool protocol and needs a decision.
- Until then, a τ² gate "FAIL" on `idcheck` alone is a probe artefact. The other τ² sub-checks decide.

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
| 2 | BF16 capability vs Qwen | **PASS (not at floor)** | τ²: 4/20 = 20% (Wilson 8–42%). On the 16 gate tasks in the calibration split, m24 25% vs Qwen BF16 q4 19%, q8 25%, q14 38%, q32 44% (same tasks, `a6k2_<q>_bf16_cal`). BFCL: 2/20 = 10% (3–30%) vs Qwen q4 10%, q8 15%, q14 15% on the same 20 items. l8 (W99f) was 0/20 and 4.2%. RTN-W4: τ² 3/20 = 15%, BFCL 1/20 = 5%. |
| 3 | BB and QQ no-op replay bit-exact (τ², BFCL) | **BFCL PASS**; τ² running | BFCL (`bfcl_rtn_w4/gate.json`, 1197 s on 4 GPUs): 10 divergent states from 12 items, 0 excluded. Q replay at state, QQ no-op, BB no-op 4/4, replay fidelity, isolation 4/4, save/load and re-prefill all pass; 0 branch errors. Divergence types: act→talk, talk→act, tool_args, tool_count, tool_name. τ²: search 20 states from 20 tasks; idcheck B 16/16, Q 13/16 (see above); branches running. |
| 4 | Same-checkpoint negative control (τ², BFCL) | **BFCL PASS**; τ² queued | BFCL (`bfcl_same_rtn_w4/gate_same.json`, 507 s): no divergence on any item, shadow = a_Q, four arms identical, equal to the original, replay ok (4 states). τ² `fork_gate_same_m24_rtn_w4` runs after the τ² gate. |
| 5 | BFCL leak regression (`tests/test_bfcl_instance_leak.py`) | **PASS** 9/9 | Default env and `CLOQ_TOKENIZER_MODE=mistral`: `test_bfcl_instance_leak{,_mistralmode}.out`. |
| 6 | Throughput | measured | τ² eval: 20 tasks in 662 s (BF16) / 718 s (RTN-W4, including a ~30 s RTN build and ~3 min server start) on 2 GPUs; median episode 201 s retail, 129 s airline. BFCL: 20 items in 291 s on 2 GPUs (median item 91–144 s). |
| 7 | Qwen paths unchanged | **PASS** | No m24 env → `template_view` path and random-id path untouched. `tests/test_template_view.py`: q4 257/257 server match. The q8 case gives the same counts (0/400 server match) with the pre-W99p code, so that failure predates this change (`test_template_view_qwen_unchanged.out`). Runner dry run: identical claims on a legacy queue. |

## Invalid tool names (protocol signal, Mistral only)

Mistral sometimes emits a tool call whose function name is invalid: empty, or the text "YOU ARE BEING TRANSFERRED TO A HUMAN AGENT. PLEASE HOLD ON.". vLLM's parser returns it, but mistral_common refuses to render that turn at the next request (HTTP 400). This is the agent's own output, so it is scored `agent_parse_error` (W27 rule, already in AGENT_SIDE) in the worker and the ext adapters. Two tasks that failed on it as "outages" (RTN BFCL gate, BF16 cal) were requeued. Rate: **3 of 1,348 decisions (0.22%), 3 of 137 episodes (2.2%)**. By run: BF16 τ² gate 0/20, RTN τ² gate 0/20, BF16 cal 2/57, BF16 BFCL 0/20, RTN BFCL 1/20 (`gate_summary.json` `invalid_tool_names`).

## Runner change (engineering condition 1)

`scripts/a6000/noderunner.py`: a task needing 2k > 2 GPUs (`gpus 4`, `gpus_per_role 2`) takes k whole free NVLink pairs. While one is runnable on the node, the top k agent pairs take nothing smaller, so they empty as their tasks finish. `scripts/a6000/worker.py::run_fork`: with `gpus_per_role 2`, B is served on the first pair and Q on the second. Every pre-W99p task behaves identically: the old and new runner give the same claim sequence on a dry-run legacy queue (fake clock, fake workers). Running runners pick this up only when restarted. node008 was drained and restarted at 04:34 (job 49869). It then claimed `fork_ext_gate_m24_rtn_w4_bfcl` on GPUs 4,5,6,7 (B TP=2 on 4,5 and Q on 6,7, both servers up) alongside a 2-GPU q8 task on 2,3. That is the live verification of the multi-pair path.

## Files

`scripts/a6000/{noderunner.py,worker.py,serve.sh,models.json,m24_textonly.py,make_tasks_m24.py}`, `cloq/{mistral_render.py,context_policy.py,agent.py}`, `scripts/ext/{common.py,bfcl_run.py}`, `analysis/fork/m24_gate/{analyze_gate.py,gate_summary.json}`, runs `runs/a6k2_m24_{bf16,rtn_w4}_g1`, `runs/ext_m24_{bf16,rtn_w4}_bfcl_gate_m24` (cluster), logs `/data/ziyangs/cloq_work/logs/tasks/<id>.{log,vllm.log}`.
