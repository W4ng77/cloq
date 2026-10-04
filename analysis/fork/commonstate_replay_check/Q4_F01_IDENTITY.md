**TL;DR**
- **One state quarantined q4 block f01:** 7411758182009c20 (airline task 30, t = 6, source `a6k2_q4_bfpair_f01`). It failed the implicit identity in both tasks:
  - task A (`implicit_vs_orig`) failed on `suffix_messages` and `prompt_token_ids`, first mismatch at prompt 1;
  - task B (`implicit_vs_refQQ`) failed on `branch_signature`: suffix_sha, prompts[1] and completions[0].
- **The cause is a 4-key reordering, invisible to canonical comparison.** a_d2 contains the same 96 tokens as a_BF16 and a_d1, except for the order of the keys of `arguments.flights[0]`:
  - d2: flight_number, origin, destination, date;
  - BF16 and d1: flight_number, date, origin, destination.
- **Why the check applied.** `canon_msg` compares parsed arguments as Python dicts, which ignores key order. So a_d2 counted as canonically equal to both actions, and both implicit checks applied.
- **Why it failed.** The chat template renders arguments in insertion order, so the t = 7 prompt differs: 24 of 7,016 token positions are permuted, `600f0c14…` vs `211d510b…`. Re-tokenizing on CPU with the swapped order gives both recorded hashes exactly (the t = 7 prompt and the a_d2 completion). The continuations therefore condition on a different prompt and are not replays.
- **Not numerical non-determinism.** Every serving-side check at this state passed, and the run is inside the q4 BF16 TP=1 envelope (257/257).
- **It is a comparison artifact.** The check's precondition is canonical equality, which is weaker than token identity.
- **The quarantine was correctly triggered** under the frozen rule (§2 "Implicit identity", §4 "Block quarantine").
- **Acceptance over all q4 + q8 common-state tasks (gate + panel):**
  - implicit identity 869/871;
  - reference re-runs 369/369;
  - together **1,238/1,240 (99.84 %, Wilson 95 % [99.41, 99.96])**;
  - d2 replay 1,578/1,578;
  - cross-task a_d2 789/789.
  
  Both failures are this one state, one per task.

# q4 f01 identity failure: state 7411758182009c20

Written 2026-10-03, after the once-only q4 reading (`analysis/fork/out/commonstate_q4_20261004T001159Z.{md,json}`).
The investigation was read-only and CPU-only. The only computation was a local re-tokenization with the Qwen3-4B-Instruct-2507 tokenizer @ cdbee75f.
Machine-readable companion: `q4_f01_identity.json` (same directory).

## 1. Which checks failed

The driver computes the checks in `scripts/a6000/fork_driver.py` `commonstate()`, L1281-1453:
- `n_identity_fail` counts rows whose `identity_ok` is false. `identity_ok` is the AND of every `implicit_*` and `ref_*` check in the row.
- Implicit A is `noop_check`, at L272.
- Implicit B is `F.branch_signature(arm) == F.branch_signature(refQQ)`.

| task | row | check | failed fields | equal fields |
|---|---|---|---|---|
| `cs_q4_d2_bf16_f01` (arm QB: a_d2 then BF16) | 7411758182009c20, airline 30, t = 6 | `implicit_vs_orig` (a_d2 = a_BF16 canonical) | `suffix_messages` (5255114b… vs orig 04645bb9…), `prompt_token_ids` (`first_prompt_mismatch` = 1 of 2) | termination, reward, db_match, official_reward, budget_final, env_hash_final vs orig replay, env_hash replay vs live, env_hash_init, history_prefix |
| `cs_q4_d2_d1_f01` (arm BQ: a_d2 then d1) | same | `implicit_vs_refQQ` (a_d2 = a_d1 canonical) | suffix_sha (04886801… vs refQQ ba9a92d6…), prompts[1], completions[0] | prompts[0], termination, reward, db_match, official_reward, env_hash_final, steps, errors |

The other checks at this state all passed:
- same-state checks (`ref_same`: all six fields true);
- d2 replay in both tasks (prompt_ok, replay_prompt_ok, replay_completion_ok, replay_action_ok);
- cross-task a_d2 identity: completion sha `6d8416af…` in both tasks, canonical equal.

The state is not a reference re-run sample in either task, and it is not in the 12-row gate.

Agreement flags at this state:
- `vs_bf16.exact = true` but `completion_ids_equal = false`. This is the only such row among the 1,578 common-state rows.
- `vs_d1.exact = true`.
- `bf16_vs_d1.exact = true`. Bank U reused QB = BB and BQ = QQ here, which is correct, because a_B and a_Q render identically.

## 2. Decision by decision: first divergence

The four trajectories compared are:
- orig BB: `runs/a6k2_q4_bfpair_f01/airline`, decisions 6-7;
- refQQ: `analysis/fork/bank_u/q4_gptq_w4_d1/f01/branches/7411758182009c20.json`;
- arm A and arm B: `analysis/fork/commonstate/q4/panel/{d2_bf16,d2_d1}/f01/branches/7411758182009c20.json`.

| step | orig BB (BF16) | refQQ (d1) | arm A (a_d2, BF16) | arm B (a_d2, d1) |
|---|---|---|---|---|
| decision 6 prompt (h_t) | 6da19502…, 6,629 tok | same | same | same |
| decision 6 action | a_BF16, completion d6e6dd39…, 96 tok; flights[0] order f#, **date**, origin, dest | a_d1 forced, same render as a_BF16 | a_d2 forced: 6d8416af…, 96 tok; order f#, origin, dest, **date** | same a_d2 |
| tool output (update_reservation_flights) | canonical 5c4f01f8… | equal | equal | equal |
| **decision 7 prompt** | **211d510b…**, 7,016 tok | **211d510b…** | **600f0c14…**, 7,016 tok | **600f0c14…** |
| decision 7 completion | cdf11590…, 172 tok, stop, "refund $207" | a5909e94…, 173 tok, "refund $198" | 62019699…, 170 tok, "refund $207" | 9e0007aa…, 174 tok, "refund $198" |
| user simulator | `###STOP###` | `###STOP###` | `###STOP###` | "Thank you for the update. I appreciate the help. ###STOP###" |
| final env hash, Y | 11f99847…, Y = 0 | same | same | same |

**First divergence: the decision-7 prompt.** It is the first prompt that contains the forced action rendered in history, and its hash differs between the arms and both references:
- arm A and arm B agree with each other (`600f0c14…`), because they render the same a_d2;
- the original and refQQ agree with each other (`211d510b…`), because a_BF16 and a_d1 render the same;
- the history before it, the h_t prompt, the tool output and the environment are identical in all four.

So the side is neither the agent server's numerics, nor the user simulator (first called after the divergence), nor the environment. It is the forced action's token sequence, which the comparison declared equal.

**Mechanism reproduced exactly (CPU, tokenizer only):**
- Decoding the recorded BF16 decision-7 prompt ids and re-encoding them gives the same ids (roundtrip equal).
- Swapping the key order of flights[0] inside the last `<tool_call>` and re-encoding gives sha `600f0c14030fd1ac…`. This equals the arm prompt. The difference covers token positions 6679-6704: 24 positions, with the same token count.
- The same swap on the recorded a_BF16 completion ids gives sha `6d8416af6ac0808f…`. This equals the recorded a_d2 completion: 96 tokens.

**Why the comparison says "equal".** `cloq/fork.py` `canon_msg` (L68) keeps `arguments` as the parsed dict (`_args`). Python dict equality ignores insertion order. The renderer, by contrast, preserves it:
- `cloq/context_policy.py` `template_view` passes the parsed dict to the HF template;
- `tojson` there does not sort keys.

Two actions can therefore be canonically equal and still produce different next prompts.

**Why d2 differs.** The order is not noise:
- d2 reproduces the same order on replay on the same server, and on another GPU (GPU 7) in task B.
- In the BF16 source decision, the token `date` at completion index 50 had a logit margin of 0.25 over the runner-up, with logprob −0.576. That is the smallest margin in the decision (`min_margin` 0.25). The runner-up token id is not recorded.

This is a near-tie that the d2 weights flip. The two orders mean the same thing, but their tokens and rendering differ.

## 3. Serving context

| run | node / job | GPU, port | effective_config_sha | ckpt sha256 / canary | load near the row |
|---|---|---|---|---|---|
| arm A, `cs_q4_d2_bf16_f01` (row 15:22:09-15:22:39 PDT, 2026-10-03) | node007 / 49864 | GPU 2 (B and Q share it, gpu_util 0.44): B BF16 :8103 (pid 536577), Q d2 :8203 (pid 536980) | B efce043e33600dcc, Q 861413c546616bf9 | B c7343b60da095480 (canary_ref_ok); Q 21c0934e…, a0fb6c52f4eb27fd | B running 4-7, waiting 0; Q running 0-2, waiting 0. Task max: running 8 / 4, waiting 0 |
| arm B, `cs_q4_d2_d1_f01` (row 16:00:22-16:00:43 PDT) | node007 / 49864 | GPU 7: B d2 :8108 (pid 543831), Q d1 :8208 (pid 544148) | B 861413c546616bf9, Q 29ba0176bfc6a4e0 | B 21c0934e…, a0fb6c52f4eb27fd; Q e6c24bc2…, a72b3da03409576e | Q running 4-7, waiting 0; B running 0-3, waiting 0. Task max: 6 / 8, waiting 0 |
| orig BF16 source `a6k2_q4_bfpair_f01` | node003 / 49694, 2026-09-30 03:20Z | agent :8006 | (BF16) | c7343b60 (same weights) | not checked: the BB no-ops reproduce it |
| ref QQ `bank_u_q4_gptq_w4_d1_f01` (a_Q at 2026-10-01 01:22) | node001 / 49727 | GPU 7, d1 :8208 | 29ba0176bfc6a4e0 (same as arm B Q) | e6c24bc2…, a72b3da03409576e | d1 running 0-2, waiting 0 |

All agent servers ran vLLM 0.29.0 at TP = 1 with `VLLM_BATCH_INVARIANT=1`, `TORCHINDUCTOR_DETERMINISTIC=1` and `VLLM_USE_FLASHINFER_SAMPLER=0`. The source run recorded vllm 0.29.0+cu129, torch 2.13.0+cu129 and transformers 5.17.0. The GPTQ checkpoints are stored as fake-quant bf16 (W4 g128, act_order), so they run the same dense BF16 kernels.

Load data comes from the `loggers.py` lines of `/data/ziyangs/cloq_work/logs/tasks/cs_q4_d2_*_f01.{B,Q}.vllm.log`. `gpumon/node007.jsonl` does not list the fork ports 81xx/82xx. It shows the node-local user simulator (port 8000, Qwen3-30B-A3B, TP = 2) at run ≤ 3, wait ≤ 7 in the arm A window. The simulator is first called after the divergence, so this does not matter here.

**Determinism envelope.** `analysis/status/gpu_fill_20261003/rerun_premise_det.json` entry `a6k2_det_q4` covers the dense Qwen3 BF16 path at TP = 1:
- 257/257 decisions bit-exact (prompt, completion, logprobs);
- running max 16/15, waiting max 0/1.

These runs (BF16 and fake-quant-bf16 checkpoints, TP = 1, running ≤ 8, waiting 0) are **inside** the envelope. The same tasks also confirm it:
- BB no-ops 15/15 in task A;
- QQ re-runs 18/18 in task B;
- d2 replay 85/85 in each task;
- a_d2 identical across GPU 2 and GPU 7 at 85/85 states.

## 4. Same state elsewhere, and acceptance counts

- **This state** belongs to block f01 only (state keys are per block) and is not in the q4 gate.
- **The same task (airline 30) in other blocks passes:**
  - f02, `df711b812ccd1f91`, t = 4: a_d2 is text and differs from a_BF16 and a_d1, so no implicit check applies. ref_rerun_QQ passes and cross-task a_d2 passes.
  - f03, `b28e295c4a9ce066`, t = 1: a_d2 = `get_reservation_details`, token-identical to a_BF16. Both implicit checks pass.
- **Canonical equal but rendered differently:**
  - Among 1,578 common-state rows, only this state matches. It appears 4 times: vs BF16 and vs d1, in each of the 2 tasks.
  - Implicit checks with a render-identical action pass 869/869. Those with a render-different action pass 0/2.
  - The Bank U reference rows use the same canonical rule for reuse. On those rows the audit found 0 render-different exact pairs:
    - q4 f01-f03: 0 of 290;
    - q8 f01-f03: 0 of 349;
    - q8 ref_d1 f04-f06: 0 of 137.

    No reference reuse is affected.

**Identity checks, all common-state tasks (pass / total):**

| design / phase | implicit A (vs orig) | implicit B (vs refQQ) | ref BB no-op | ref QQ re-run | d2 replay | cross-task a_d2 |
|---|---|---|---|---|---|---|
| q4 gate | 9/9 | 9/9 | 12/12 | 12/12 | 24/24 | 12/12 |
| q4 panel f01-f03 | **139/140** | **136/137** | 49/49 | 58/58 | 510/510 | 255/255 |
| q8 gate | 4/4 | 5/5 | 12/12 | 12/12 | 24/24 | 12/12 |
| q8 panel f01-f06 | 292/292 | 275/275 | 102/102 | 112/112 | 1,020/1,020 | 510/510 |
| **total** | 444/445 | 425/426 | 175/175 | 194/194 | 1,578/1,578 | 789/789 |

Summary of the acceptance rates:
- **Implicit + reference re-run checks:** 1,238/1,240 = 99.84 % (Wilson 95 % [99.41, 99.96]).
  - q4: 424/426;
  - q8: 814/814.
- **By row:** 1,043 of the 1,045 rows that carry any identity check pass.
- **Extra checks, all passing:**
  - gate vs panel a_d2 at the same state: 48/48, with Y equal 48/48;
  - q8 `ref_d1` (bank_u) BB no-ops at f04-f06: 33/33.

Per-task counts are in the JSON (`per_task_counts`).

## 5. Verdict

**This is a comparison artifact, not numerical non-determinism and not a recording gap.**

Everything on the serving side reproduced at this state:
- the h_t prompt;
- a_d2 on replay, and across GPU 2 and GPU 7;
- the tool output, the final DB hash, the budget and every outcome field (Y = 0 in all four trajectories);
- in the same tasks, the BF16 no-ops (15/15) and the d1 QQ re-runs (18/18), byte-exact;
- the q4 BF16 TP = 1 path stayed inside its 257/257 envelope.

What differs is the action itself, at token level:
- d2 deterministically writes the four keys of `flights[0]` in another order. BF16 had a 0.25 logit margin at that token, so this is a near-tie flipped by the quantized weights.
- `canon_msg` compares arguments as order-insensitive dicts, so the check counted a_d2 as "a_d2 = a_BF16" and "a_d2 = a_d1".
- The chat template renders insertion order. Both continuations therefore conditioned on a prompt with 24 permuted tokens and produced different text. The suffix and prompt-id identity required by `noop_check` and `branch_signature` cannot hold.

**The quarantine was correctly triggered.** The frozen protocol states the implicit identity's precondition as canonical equality (§2), and §4 removes a block on any failed implicit identity. Both checks applied, both failed, and f01 left the analysis set as the frozen rule requires.

## Evidence paths
- `analysis/fork/commonstate/q4/panel/{d2_bf16,d2_d1}/f01/{cs_rows.jsonl, cs_summary.json, branches/7411758182009c20.json, rows/7411758182009c20.json}`
- `analysis/fork/bank_u/q4_gptq_w4_d1/f01/{bank_rows.jsonl, bank_summary.json, branches/7411758182009c20.json}`
- `runs/a6k2_q4_bfpair_f01/airline/{decisions.jsonl, trajectory.jsonl, environment.json, config.json}` (task 30, decisions 6-7)
- `analysis/fork/out/commonstate_q4_20261004T001159Z.{md,json}` (f01 `quarantined_by: [d2_bf16, d2_d1]`)
- `/data/ziyangs/cloq_work/queue/done/{cs_q4_d2_bf16_f01, cs_q4_d2_d1_f01, bank_u_q4_gptq_w4_d1_f01}.json`
- `/data/ziyangs/cloq_work/logs/tasks/cs_q4_d2_{bf16,d1}_f01.{B,Q}.vllm.log`, `/data/ziyangs/cloq_work/gpumon/node007.jsonl`
- `analysis/status/gpu_fill_20261003/rerun_premise_det.json` (`a6k2_det_q4`)
- Code:
  - `scripts/a6000/fork_driver.py`: commonstate L1281-1453, noop_check L272, bank_u `exact` L729;
  - `cloq/fork.py`: canon_msg L68, run_branch L539, branch_signature L657;
  - `cloq/context_policy.py`: template_view, render_prompt_ids.
- Protocol: `docs/insights/COMMONSTATE_SOURCES_PROTOCOL.md`, §2 "Implicit identity" (L68), §4 "Block quarantine" (L99), A1.4.
