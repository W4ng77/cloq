# Replay check: the 9 q8 f01-f03 overlap states (SAMEPREC q8 g1 vs common-state d2_d1 panel)

2026-10-03. Read-only CPU check. No GPU work was run and no existing file was changed. Machine-readable version: `replay_8of9.json` in this directory.

## TL;DR

- **The "8/9" premise does not reproduce.** All 9 (d2 action, d1 continuation) arms are byte-identical replays across the two studies. There is no first point of divergence on any side (agent, user simulator or environment).
  - a_d2 completion-id sha: 9/9 equal.
  - Every d1 decision has equal prompt-token sha, completion-token sha, token counts, finish_reason and tool calls: 148 decisions, 6,370 completion tokens.
  - Every user-simulator message (59) and tool output (98) is equal.
  - suffix_sha, the final DB hash, termination, reward, db_match, official_reward and the whole `reward_info` are equal.
  - `branch_signature` (`cloq/fork.py:657-663`) is equal 9/9.
  - The only fields that differ are timestamps, generation/wall seconds, duration, ports, tags, the study-specific state_id, and the random tool-call ids. Those ids are not rendered into the prompt, because the prompt shas stay equal.
- **Where "8/9" came from.** It comes out exactly when the common-state Y (DB success: db_match and user_stop/agent_stop, `scripts/a6000/fork_driver.py:664-670`) is compared with SAMEPREC's τ² `official_reward` from `branches.json`. The single "mismatch" is **79aa9e6a7ca99243** (f03, airline 3, t = 0). In both runs that arm ends in a transfer to a human with db_match = True and user_stop, so Y = 1, while official_reward = 0 (ACTION 0, COMMUNICATE 0: "Information '4' not communicated"). SAMEPREC's own outcome (`analysis/fork/analyze_dev.py:203-206`, used for BQ at `:333`) is DB success = 1. With the same definition on both sides, outcomes are equal **9/9**.
  - Other comparisons give: Y vs SAMEPREC DB success 9/9, Y vs official_reward 8/9, Y vs `reward` 6/9.
- **Serving context.** The serving stack was identical in every setting that affects numerics: vLLM 0.29.0, the batch-invariant env, prefix caching and chunked prefill, CUDA graphs, TP = 1, equal effective_config_sha and checkpoint sha256. What differed:
  - node: node004 vs node005 for f01/f02;
  - GPU ids and port (f01);
  - KV-cache size;
  - user-simulator instance;
  - load on the d1 server: SAMEPREC ran a median of 1 request (max 6), common-state a median of 2-5 (max 8, waiting up to 4).
  
  The tokens were identical under different batch compositions and on different nodes.
- **Determinism coverage.** No det pair serves a GPTQ checkpoint. The q8 GPTQ-W4 d1 ckpt is fake-quant BF16 (vLLM `quantization=None`), so it falls in the dense BF16 TP=1 kernel class covered by `a6k2_det_q4` (257/257) and `a6k2_tel_det_q8` (Qwen3-8B, 1520/1520). It is covered by kernel class, not by a direct pair.
  - This run's load (8 running, waiting up to 4) is above every det pair's waiting_max ≤ 1. No preemption was logged.
  - Direct fork-level evidence for this config now exists:
    - this check, 9/9;
    - the common-state QQ reference re-runs against Bank U, 68/68;
    - the implicit identities, 147/147.
- **Verdict.** The mismatch is neither non-batch-invariant numerics nor a user-simulator difference. It is an outcome-definition mismatch in the overlap comparison. "The replays are close but not exact" (protocol D2.1, `docs/insights/COMMONSTATE_SOURCES_PROTOCOL.md:338-339`, `:447`; `docs/RESEARCH_LOG.md:68`) should read "exact, 9/9". The earlier review's 9/9 was right.

## 1. Which state, and where the arms live

**State mapping.** The two studies key the same state differently. SAMEPREC uses `state_id` built from the d1 source run (`a6k2_q8_gptq_w4_d1_f0x`). Common-state uses the Bank U `state_key` (source run `a6k2_q8_bfpair_f0x`). Matching was done on history_sha, the recorded prompt_ids_sha (`q_decision.prompt_ids_sha` vs row `prompt_ids_sha`), env_hash, steps_left, domain and task_id. Exactly one SAMEPREC state matched each key. sim_seed (626729) and nonce agree.

| state_key | blk | domain/task | t | CS state_id | SAMEPREC state_id | CS Y | SP db_success | SP official_reward |
|---|---|---|---|---|---|---|---|---|
| c4209bd6e73eaf27 | f01 | retail 10 | 0 | 0f07da117962b15a | f5828251e92b6268 | 0 | 0 | 0 |
| 2857c7a7b30fe4e5 | f01 | retail 44 | 1 | 72b3b6c3f4e7e902 | d1e6a397a45c75cd | 1 | 1 | 1 |
| ae8398d726bf9a2c | f01 | retail 81 | 0 | 904fe1497b6e1a64 | d427cc3635956e1b | 0 | 0 | 0 |
| cc4156b2230c6fbf | f02 | retail 68 | 0 | 72ab2bad8aa575bc | 7338dc39feab2b95 | 0 | 0 | 0 |
| **79aa9e6a7ca99243** | f03 | airline 3 | 0 | 868193df553e24a9 | 5859e02aecc11d39 | **1** | **1** | **0** |
| 1d40f5f213d18ec6 | f03 | airline 5 | 1 | e323d1dddf68b721 | 9c56d53ae0493f7a | 1 | 1 | 1 |
| 3f0beb57c67b8233 | f03 | retail 68 | 0 | a1fd24bdc2121757 | 9dd5b1df4615fdc3 | 0 | 0 | 0 |
| 763a22f520eda960 | f03 | retail 82 | 1 | 0fc1238d41af6cb4 | 02f6b4051e32b744 | 0 | 0 | 0 |
| 762a8bf4acfc1d88 | f03 | retail 95 | 1 | 8e401580c289ae51 | ee81224144b8b751 | 0 | 0 | 0 |

**Record locations.**
- Common-state:
  - the loader `analysis/fork/analyze_commonstate.py:131-219` reads `<panel_dir>/d2_d1/<blk>/cs_rows.jsonl`, with `panel_dir` = `analysis/fork/commonstate/q8/panel` from `manifests/fork/commonstate_v1.json`;
  - per-state rows are in `.../d2_d1/<blk>/rows/<state_key>.json`;
  - per-state branches are in `.../d2_d1/<blk>/branches/<state_key>.json` (key `BQ`; `fork_driver.py:1416` dumps them).
- SAMEPREC:
  - branch records: `analysis/fork/sameprec/q8_gptq_w4_d1_vs_d2/g1/branches/<state_id>.json` (key `BQ`; B = d2, Q = d1, so BQ = d2 action then d1 continuation);
  - states: `.../g1/states/<state_id>.json`;
  - the outcome summary `.../g1/branches.json` `rows[].outcomes.BQ` holds only `reward, db_match, official_reward, termination_reason, duration, error` (`fork_driver.py:1552`). It does not hold Y.

## 2. Decision-by-decision comparison

Fields compared:
- per agent decision: prompt_ids_sha, completion_ids_sha, n_prompt_tokens, n_completion_tokens, finish_reason, tool_calls (ids stripped), content, forced, parser_error, system_sha256, usage;
- per message (user, tool, assistant): every field except `id`.

The records do not store separate user-LLM call records, so the user side is compared through the user messages in `suffix`.

**79aa9e6a7ca99243 (the "differing" state).**

| dec | forced | prompt_ids_sha (both) | completion_ids_sha (both) | n_prompt | n_compl | finish |
|---|---|---|---|---|---|---|
| 0 | yes (a_d2) | 9f4db4494d2c… | (a_d2: cc19111a10ff… both) | 4951 | - | - |
| 1 | | 9fe706e95539… | bfc215019367… | 5007 | 27 | stop |
| 2 | | 61fd26483d2b… | 390d47cd0b97… | 5107 | 30 | tool_calls |
| 3 | | 216325cea1bd… | 644b98185929… | 5461 | 96 | stop |
| 4 | | 78bdb4d088b0… | 3d15f72b6b94… | 5635 | 47 | tool_calls |
| 5 | | 5126ee0bccb3… | cacc8c3e2541… | 5697 | 19 | stop |

All rows are equal on both sides. The suffix has 12 messages and all are equal. Content, identical in both runs:
- a_d2 `get_user_details(user_id=anya_garcia_123)` returns "Error: User anya_garcia_123 not found";
- the agent asks for the ID again, and the user gives "anya_garcia_5901";
- `get_user_details` succeeds, and the agent says "You are a Silver member…";
- the user says "I'm certain I'm a Gold member … supervisor";
- the agent calls `transfer_to_human_agents`, and the user ends with `###TRANSFER###`.

Both runs end the same way:
- `suffix_sha` = 5d4d49aa…;
- env_hash_final = 124e39a6…, unchanged from the initial hash;
- termination user_stop, db_match True, reward 0.0, official_reward 0.0;
- reward_breakdown {DB 1, ACTION 0, COMMUNICATE 0}, with action check `get_reservation_details` unmatched.

**First divergence: none.**

**Controls:**
- **c4209bd6e73eaf27** (f01, retail 10). This is the cross-node control: common-state ran on node005 GPU 7, port 8207, and SAMEPREC on node004 GPU 5, port 8205. 21 decisions and 8 user turns; prompts 4,928 to 7,855 tokens; 1,030 completion tokens. Every decision and message is equal, and suffix_sha 178c370a… is equal.
- **3f0beb57c67b8233** (f03, retail 68). Same node and GPU, ending in too_many_errors. 30 decisions and 13 user turns; prompts to 9,778 tokens. Every decision and message is equal, and suffix_sha 0a1a2fd2… is equal.

The other 6 states are also fully equal (`replay_8of9.json` → `states[]`).

**Load at each d1 decision.** This is approximate: the max of the two bracketing 10 s vLLM engine-log intervals on the Q server.

| state | common-state | SAMEPREC |
|---|---|---|
| 79aa | [6, 6, 6, 5, 5] | [2, 2, 2, 1, 1] |
| c4209 | mostly 7-8 | 1-4 |
| 3f0b | 3-7 | 0-6 |

The batch compositions differed, and the tokens did not.

## 3. Serving context

Sources:
- `/data/ziyangs/cloq_work/queue/done/{fork_sameprec_q8_g1,cs_q8_d2_d1_f01,cs_q8_d2_d1_f02,cs_q8_d2_d1_f03}.json` → `result.servers`;
- `/data/ziyangs/cloq_work/logs/tasks/<task>.servers.json`, `<task>.{B,Q}.vllm.log` and `<task>.log`;
- `/data/ziyangs/cloq_work/logs/sim_node00{4,5}_4986{2,3}.log`.

| | SAMEPREC q8 g1 | CS d2_d1 f01 | CS d2_d1 f02 | CS d2_d1 f03 |
|---|---|---|---|---|
| node / job | node004 / 49862 | node005 / 49863 | node005 / 49863 | node004 / 49862 |
| wall (PDT, 10-02) | 02:11-05:55 | 11:00-11:41 | 11:30-12:29 | 11:34-12:46 |
| GPU B(d2) / Q(d1) | 4 / 5 | 6 / 7 | 4 / 5 | 4 / 5 |
| Q port | 8205 | 8207 | 8205 | 8205 |
| arms run | BB, BQ, QB (+10 % no-op) | BQ (+20 % QQ ref re-run) | same | same |
| driver concurrency | 8 | 8 | 8 | 8 |
| Q running median / max, waiting max | 1 / 6, 1 | 5 / 8, 3 | 2 / 8, 0 | 3 / 8, 4 |
| Q KV-cache usage max; KV size | 30.1 %; 174,128 tok | 32.7 %; 193,680 | 37.7 %; 174,128 | 62.4 %; 174,128 |
| preemption lines in Q log | 0 | 0 | 0 | 0 |
| user simulator instance | sim_node004_49862 | sim_node005_49863 | sim_node005_49863 | sim_node004_49862 |

Identical in all four:
- **Stack and launch.**
  - vLLM 0.29.0 (one conda env, `/data/ziyangs/cloq_work/envs/cloq`).
  - `scripts/a6000/serve.sh`: TP = #GPUs = 1, `--seed 0`, bf16, max_model_len 33792, gpu_util 0.90, hermes parser, combo_kernels on with benchmark off.
  - `serve_env` {} and `serve_extra` [], `hook_coverage` null.
  - `scripts/a6000/env.sh`: VLLM_BATCH_INVARIANT=1, VLLM_USE_FLASHINFER_SAMPLER=0, TORCHINDUCTOR_DETERMINISTIC=1. This is also recorded in `effective_config.numerics_env`.
- **Engine config.**
  - `quantization=None`: the ckpt is GPTQ-W4 "fake-quant bf16" storage (cs_summary `q_quantization.storage`).
  - enable_prefix_caching=True, enable_chunked_prefill=True.
  - compilation mode VLLM_COMPILE(3), cudagraph_mode FULL_AND_PIECEWISE, max capture size 512.
  - FLASH_ATTN, kv_cache_dtype auto.
  - max_num_seqs not set, so the vLLM 0.29.0 default for a GPU under 70 GiB applies: 256 seqs with max_num_batched_tokens 2048 (`vllm/engine/arg_utils.py:2718-2727`).
- **Configs and checkpoints.**
  - effective_config_sha B = 6efd8895e51ea91e, Q = cd7c70f5e9fe40d4.
  - d1 ckpt sha256 6ee628e6… (canary a9f812fb17241b72), d2 320409ad… (canary 15e5098c08c412da). Each task rebuilt its checkpoint by GPTQ, and the sha matches.
- **Sampling.**
  - Agent: temperature 0, top_k -1, seed 0, thinking off.
  - User simulator: Qwen3-30B-A3B-Instruct-2507, TP=2, prefix caching on, batch-invariant env, temperature 0, seed 0.
  - The state files label the simulator `Qwen/Qwen3-4B-Instruct-2507`. That is the known stale label recorded in `docs/RESEARCH_LOG.md:1527`.

## 4. What determinism acceptance covers

`analysis/status/gpu_fill_20261003/rerun_premise_det.json` (generated by `.py`; summarized in `docs/RESEARCH_LOG.md:146,161-173`) contains the closed-loop det pairs. Each pair is the same config run on two nodes at different times, compared per common decision on prompt ids, completion ids and token logprobs:

| pair | covers | result | running max (a, b) | waiting max |
|---|---|---|---|---|
| a6k2_det_q4 | dense Qwen3 BF16 TP=1 (derived ckpts) | 257/257 bit-exact, prompts to 13.8k | 16, 15 | 0, 1 |
| a6k2_det_q4_fp32h | dense TP=1, fp32 head | 281/281 | 13, 14 | 0, 0 |
| a6k2_det_q30a3 | user simulator (MoE TP=2) | 303/303, to 25.5k | 16, 16 | 0, 0 |
| a6k2_tel_det_q8 | Qwen3-8B BF16 telecom, long contexts | 1520/1520, to 32.3k | 6, 7 | 0, 0 |
| *_x1_fp8 (q4, q8, q14, q30a3, q32) | FP8 GEMM, TP=1 and TP=2 | all bit-exact | ≤ 16 | ≤ 1 |
| *_x1_awq (q8, q14, q32) | AWQ fp16 dequant | **NOT bit-exact**, 20/20 tasks diverge | ≤ 16 | ≤ 1 |
| a6k2_det_q4_kvq_int4_rot | KV-quant pyhook | pair incomplete | - | - |

`docs/RESEARCH_LOG.md:3582-3584` records the W3 fix (q4 257/257, q30a3 303/303 across node005/node004). The caveat at `RESEARCH_LOG.md:173` is that no det pair ran with a waiting queue, so preemption is not covered.

**Is the q8 GPTQ-W4 d1 continuation under concurrent load inside the verified range?**
- **No direct det pair.** No pair serves a GPTQ (or any W4) checkpoint.
- **Covered by kernel class.** The W4 ckpt is stored and served as dense BF16 (`quantization=None`), so the kernels are those of the dense Qwen3 BF16 TP=1 path. That path is verified for Qwen3-4B (257/257, 16 running) and Qwen3-8B telecom (1520/1520, 7 running). The user simulator is covered directly by the q30a3 pair.
- **Outside the det-pair envelope on queueing.** The common-state d1 servers reached 8 running with waiting up to 3 (f01) and 4 (f03). Every det pair had waiting ≤ 1. No preemption was logged, and KV usage stayed ≤ 62.4 %.
- **Direct fork evidence for this exact config, under concurrency-8 load and across nodes.**
  - This check: 9/9 byte-identical arms between node004 at low load and node004/node005 at higher load.
  - Common-state d1 QQ reference re-runs, branch_signature-equal against Bank U (node004, job 49671): 12/12 in the gate (node007) and 19 + 18 + 19 = 56/56 in panels f01-f03. Total 68/68.
  - Implicit identities: 5 + 142 = 147/147 (`commonstate/q8/{gate,panel}/d2_d1/**/cs_summary.json`, `n_ref_rerun_pass`, `n_implicit`, `n_identity_fail` = 0).

## 5. Conclusion

The mismatch is not consistent with non-batch-invariant numerics. That would show up as a decision whose prompt is identical and whose completion differs, and there is none: 148/148 d1 decisions have equal prompt and completion token shas despite clearly different batch loads and two different nodes. It is not a user-simulator difference either, since all 59 user turns are equal, and it is not an environment difference, since all 98 tool outputs and the final DB hashes are equal.

It is a comparison artifact. The overlap check set this design's Y (DB success) against the only outcome fields SAMEPREC's `branches.json` exposes, and took `official_reward` for Y. At airline 3, a transfer-to-human episode passes the DB check and fails the τ² ACTION/COMMUNICATE checks, so the two metrics disagree there by definition, identically in both runs. Under one definition the outcomes agree 9/9. The trajectories are exact replays.

D2.1's sensitivity reading is unaffected: it excludes the 26 states regardless. Only the descriptive sentence is wrong, at `COMMONSTATE_SOURCES_PROTOCOL.md:338-339` and `:447` and at `RESEARCH_LOG.md:68`. The text "close but not exact; 8/9; the review said 9/9" should become "exact; 9/9; the review was right".

## 6. Proposed scoped wording

**Protocol D2.1 bullet (replacement for "The replays are close but not exact"):**

> On the 9 f01-f03 overlaps, the (d2 action, d1 continuation) arms of SAMEPREC q8 g1 and of this design are byte-identical replays. This covers the a_d2 completion ids (9/9), every d1 decision's prompt and completion token ids (148 decisions), every user-simulator and tool message, the final DB hash and all reward fields. Outcomes are therefore equal 9/9. An earlier count of 8/9 compared this design's DB-success Y with SAMEPREC's τ² official_reward. At 79aa9e6a7ca99243 these two metrics differ by definition; the runs do not differ.

**Paper / methods claim (scoped to what was verified):**

> Replays are exact within the verified serving envelope. We decode greedily on a batch-invariant vLLM 0.29.0 stack (VLLM_BATCH_INVARIANT=1, TORCHINDUCTOR_DETERMINISTIC=1, prefix caching and chunked prefill on). Under that stack, a fork arm re-run at the same state with the same checkpoint (sha256) and the same user simulator (Qwen3-30B-A3B-Instruct-2507, TP=2) reproduced the original trajectory token for token.
>
> We verified this directly for Qwen3-8B GPTQ-W4 checkpoints stored as fake-quant BF16 and served at TP=1 on A6000 nodes 004, 005 and 007, with 1-8 concurrent requests per server and no preemption: 9/9 overlapping arms across two studies, and 68/68 d1 reference re-runs. Closed-loop det pairs extend it to dense BF16 and FP8-GEMM Qwen3 paths at TP=1 and TP=2, with up to 16 concurrent requests and a waiting queue of at most 1.
>
> Replays are not exact on the AWQ fp16-dequant path (20/20 det-pair tasks diverge). We did not test them under KV-cache preemption, with the KV-quant hook, or on other models, GPUs or vLLM versions.

## Reproduction (CPU, read-only)

1. **Map the states.** For each state key, load `analysis/fork/commonstate/q8/panel/d2_d1/*/rows/<key>.json` and find the unique `analysis/fork/sameprec/q8_gptq_w4_d1_vs_d2/g1/states/*.json` with equal `history_sha`, `q_decision.prompt_ids_sha`, `env_hash`, `budget.steps_left`, `task_id` and `domain`.
2. **Compare the branches.** Compare `branches/<key>.json["BQ"]` with `g1/branches/<sid>.json["BQ"]`: `branch_signature`, the per-decision fields, and the per-message fields minus `id`, timestamps and timings.
3. **Reproduce 8/9.** Compare row `Y` with `g1/branches.json` `rows[sid].outcomes.BQ.official_reward`.
4. **Reproduce 9/9.** Compare row `Y` with `analyze_dev.success(domain, outcomes.BQ)`.
