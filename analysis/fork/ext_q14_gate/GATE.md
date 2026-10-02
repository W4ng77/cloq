# W99g — q14 (Qwen3-14B) BFCL four-arm fork gate

**TL;DR** The gate PASSES on every check, so the 4 prepared q14 fork tasks are queued (W99h).
- **(a)** BB and QQ no-op acceptance pass on q14: 8 divergent states, 4 BB mid-states, 4 isolation states.
- **(b)** The same-checkpoint negative control passes: 4 forced states, four arms identical.
- **(c)** The call-rewriter leak is fixed and covered by a regression test that reproduces it. Replaying all 45,035 recorded Qwen q4/q8/q14 BFCL decisions gives byte-identical observations.
- **New finding.** While verifying (c), the gate found a second restoration bug in BFCL: process-shared long-context backend state. It is now fixed for q14. Historical q4 long-context forks carry it (see "Open issue").

Scope: this is a within-Qwen-family scale sensitivity check with a single configuration (GPTQ-W4 d1). It is not second-family evidence, and it is exploratory.

Model: Qwen3-14B (`q14`). B = BF16, Q = GPTQ-W4 d1 (`manifests/a6k2/q14/calib_fp_traj_c1.json`). Q checkpoint sha256 `120c6929…0a48dc9` was identical in both gate tasks (two independent builds), and the Q canary was `dfc2dd0a3a14a324`. The BF16 canary `80a6244fbc48e071` matches the q14 reference.
Protocol: fork-ext-v1 (`scripts/ext/fork_ext.py`, unchanged), with the W99g fixes in `scripts/ext/bfcl_run.py` (sha256 `b35d9303…c3937e`; last edit 22:32:39 PDT; both gate fork processes started after it).
Blocks: `ext_q14_gptq_w4_d1_bfcl_eval` and `ext_q14_bf16_bfcl_eval` (788 items each). Gate states come from the first 3 hash-ordered items per category: 12 items in total.
Time: 22:20 → 23:05 PDT 2026-10-01, about 45 min. GPU: about 1.1 GPU-h, all through the queue, node006, priority −14.

## Verdict per check

| # | Check | Result | Evidence |
|---|---|---|---|
| a1 | QQ no-op (Q→Q). The live Q server replaces the recorded Q from t on. Prompt ids, completion ids, observations, number of decisions, termination, official outcome and `bfcl_result` must all equal the original. | **PASS 8/8** | `gate_bfcl_q14_gptq_w4_d1/gate.json` (`a_noop_QQ`), `branches/<sid>.json` |
| a2 | BB no-op (B→B) on BF16 mid-episode states (t = n/2), with the same checks | **PASS 4/4** | `gate.json` (`a_noop_BB`: base_105 t2, base_162 t6, base_38 t2, base_116 t6), `branches/*_bbnoop.json` |
| a3 | State restoration. The replayed prefix messages and observations must equal the recorded ones at every step. The backend-state hash before every decision must be identical across branches and equal to the search replay at t. | **PASS 8/8** | `gate.json` states[].replay |
| a4 | Action injection. At t, Q regenerates a_Q bit-exactly (completion ids, prompt ids, action). | **PASS 8/8** | states[].q_replay |
| a5 | Re-prefill. QB's first live prompt at t+1 must equal the original Q prompt; BQ and BB first prompts must be equal. | **PASS 8/8** | states[].e_reprefill |
| a6 | Save/load of state files (history, tools, a_B) | **PASS 8/8** | states[].io_check |
| a7 | Isolation. Branch signatures must be equal across forward, reverse-sequential and fully concurrent runs. The signature covers reward, termination, n_decisions, final backend state, suffix messages and suffix decision ids. | **PASS 4/4** | `gate.json` c_isolation, `branches/*_{rev,conc}.json` |
| a8 | Budget counters. The state budget (decisions used, turn, step in turn, 20 steps per turn) must be reproduced, and the no-op n_decisions and termination must match. | **PASS** | states[].budget, a1/a2 |
| a9 | Branch errors / search exclusions | **0 / 0** | `gate.json` verdict |
| b | Same-checkpoint negative control. B and Q are two servers of the same GPTQ-W4 d1 checkpoint (identical effective config and canary). (1) The search over 12 items must find no divergence: shadow = recorded at every step. (2) At 4 forced mid-episode states the same complete action is injected in all four arms, and BB/BQ/QB/QQ must be identical (signature as a7) and equal to the original. | **PASS**: 0/12 divergent; 4/4 states four-identical and equal to the original; replay ok | `gate_same_bfcl_q14_gptq_w4_d1/gate_same.json`, `branches/*_same.json` |
| c1 | Fix the instance-name leak. Branch identifiers must never change the observation. | **PASS** (fix below) | `scripts/ext/bfcl_run.py` (W99g blocks) |
| c2 | Regression test that reproduces the W99f failure and checks identical observations across branches | **PASS 9/9** (each leak test fails with the fix switched off) | `tests/test_bfcl_instance_leak.py`, output `test_bfcl_instance_leak.out` |
| c3 | Existing Qwen q4/q8 decisions unchanged. Replay with old code vs new code. | **PASS**: 45,035/45,035 decisions with byte-identical observations and prompts (4,728 episodes) | `replay_obs_check.{py,json}` |

Gate throughput (q14, 2 GPUs):
- Search: 49 s per item; divergence 8/12; t* = 0, 0, 1, 2, 2, 4, 7, 8.
- Branches: median 30 s, p90 56 s, 5.7 s wall per branch at concurrency 8.
- GPTQ build: 986 s.
- Gate (a) task: 956 s of fork time.

Divergence categories: talk→act, tool_args, tool_count, tool_name.
Four-arm outcomes at the 8 gate states:
- 5 × `0000`
- miss_param_164: BQ only
- miss_param_151: BB and BQ
- long_context_51: BB and BQ

## c1 — the leak fix

**Cause (W99f, l8 base_126).** Fork branches run BFCL under the model name `cf_<12 hex>` (`fork_ext.run_env`), so concurrent branches get separate backend instances. BFCL's `_process_method_calls` prefixes every `name(` with the instance name, including inside string arguments. As a result:
- `order_id='get_order_history()[0]'` became `'<model>_multi_turn_base_126_TradingBot_instance.get_order_history()[0]'`.
- That string reached the error observation.
- It can also be stored in backend state, for example as a file's content.

**Fix** (`scripts/ext/bfcl_run.py`, minimal; identity for live runs):
- `run_item` registers a fork-branch model name. It must match `cf_[0-9a-f]{12}`; any other non-canonical name raises an error.
- (i) **Inside the string literals of the rewritten call** (found by `tokenize`), a registered branch prefix of an instance name is mapped back to the canonical `cloq_agent_`. The call target keeps the branch's own instance. The wrapper is installed on `multi_turn_utils._process_method_calls`, so the agent loop and the official evaluator both use it.
- (ii) **The execution results the agent sees** pass through the same canonicalisation, as a second layer.
- **Live eval runs** (`cloq_agent`) never register a name, so both steps are the identity there. A fork branch therefore sees exactly the text the canonical run would show.

## c2 — regression test (`/data/ziyangs/cloq_work/envs/bfcl/bin/python tests/test_bfcl_instance_leak.py`)

**Scripted cases** (CPU only, no server) run through `bfcl_run.run_item`, the code path every branch uses:
- **TradingBot base_126** with `get_order_details(order_id="get_order_history()[0]")` and `cancel_order(order_id="get_order_history()[1]")`, the W99f case.
- **GorillaFileSystem base_1** with `touch`, then `echo(content="see ls() and pwd()")`, then `cat`, where the leaked name is stored in state.

**Checks:**
- With the fix switched off (`CANON_BRANCH_NAMES = False`), the two branches' observations differ and contain the branch name. The FS case also differs in its backend-state hash.
- With the fix on, the canonical run and two branches have byte-identical observations, prompts, per-decision state hashes, final state, success and `bfcl_result`, and no observation contains `cf_`.
- **Recorded exposed case** (`test_recorded_l8_base_126`). The W99f l8 base_126 episode is replayed with every decision forced to the recorded response. Without the fix the two branches differ; with the fix both reproduce the recorded canonical observations byte for byte, including `cloq_agent_multi_turn_base_126_TradingBot_instance.get_order_history()[0]`.
- **Supporting checks:**
  - canonical identity
  - branch-name format enforcement
  - the two restoration tests below

## c3 — Qwen q4/q8 decisions unchanged (`replay_obs_check.json`)

**Method.**
- Episodes: every recorded episode of `ext_{q4,q8,q14}_{gptq_w4_d1,bf16}_bfcl_eval`. That is 6 runs × 788 items, 4,728 episodes and 45,035 decisions.
- Replay: each episode is replayed through `fork_ext.run_env` under a fork-branch name, with every decision forced to the recorded response.
- Passes: four, each in a fresh 12-process pool. They are old code (both W99g fixes off) and new code (both on), each in forward and reverse item order.
- Process history: each worker process replays many episodes, so process-shared state is exercised as in a fork task.

**Results.**
- New code: 45,035/45,035 observations are byte-equal to the recorded ones in both orders, and 45,035/45,035 prompt message lists are equal.
- Old vs new: observations are identical on 4,728/4,728 episodes.
- Episode results: the decision count, success and termination equal the recorded ones on 4,728/4,728 episodes.
- Leaks: 0 observations contain an instance name.
- New-code backend-state hashes are identical across process histories on 4,728/4,728 episodes.

Recorded leak count in the eval runs (canonical name `cloq_agent`): 0 of 181,723 decisions in all 24 Qwen BFCL eval runs (q4/q8/q14/q30a3/q32, every arm). The leak needs an argument that contains a call expression, which Qwen never produced.

## Second restoration bug found by c3: process-shared long-context backend state (fixed for q14)

**Cause.**
- `TravelAPI._load_scenario(long_context=True)` inserts the module-level `CREDIT_CARD_EXTENSION` / `BOOKING_RECORD_EXTENSION` dicts into the instance by reference (`_add_credit_cards`).
- `book_flight` then decrements `balance` inside the shared constant.
- Every later TravelAPI instance in the same Python process starts from the mutated card list. That covers another item, another fork branch, and the evaluator's instances.

**Exposed by** the first c3 run. `ext_q4_bf16_bfcl_eval` long_context_180 replays correctly in a fresh process. When an earlier replay of the same episode has run in the same process, the card balance shows 2600 instead of 5000, so `book_flight` fails and the observations diverge.

**Fix** (`bfcl_run._install_unalias_patch`). Right after `_load_scenario`, each multi-turn backend instance (the 8 classes of the four multi_turn categories) takes a private deep copy of its own attributes. This is done in one deepcopy call, so internal sharing such as GorillaFileSystem's root/_current_dir is kept. The loaded values are unchanged, and only the aliasing is cut. The memory/web backends are never imported.

**Tests.**
- `test_long_context_shared_state_unaliased` reproduces the contamination with the fix off.
- `test_recorded_q4_long_context_180_twice` replays the recorded episode twice in one process; both replays must reproduce the recorded observations.
- c3 above shows new-code state hashes are history-independent on every episode. The old code's backend-state hash depends on process history on 50 episodes (`old_code_state_hash_differences`); its observations differ from the recorded run on 1 episode in reverse order.

### Open issue for the main session (historical q4, not touched here)

The dev forks run every branch of a category in one process, and old code was in use. The per-state replay-consistency flag (`effects.jsonl` "replay", `dev_summary.replay_ok`) is therefore false for q4 long-context states in four cells:

| cell | replay-inconsistent states |
|---|---|
| `bfcl_q4_gptq_w4_d1_long_context` | 38/133 |
| `bfcl_q4_awq_w4_d1_long_context` | 21/151 |
| `bfcl_q4_gptq_w3_long_context` | 43/165 |
| `bfcl_q4_kvq_int4_long_context` | 50/197 |

All q8 cells and all other q4 categories are 100% consistent. In the inspected q4 GPTQ-W4 cases:
- prefix observations and prompts match;
- the BB branch state equals the search replay;
- BQ/QB start from a backend state whose hash differs, because the BB phase ran first and mutated the shared cards.

`analyze_ext.load_dir` and `ext_r2` do not use this flag, so these states are admitted in the published ext/ext-R2 numbers. Whether any of their outcomes changed is unknown; settling it needs GPU reruns of those four q4 long-context cells with the fixed code. This affects the q4 BFCL long-context part of the ext supplementary results only. q14 runs with the fix.

## Notes

- **Pooling.** The q14 dev outputs go to `analysis/fork/ext/dev/bfcl_q14_gptq_w4_d1_*`, the path in the staged tasks, unchanged. A rerun of `analyze_ext.py`/`ext_r2.py` without `--dirs` would therefore pool q14 into the W4 BFCL pool. The W99h analysis uses `analysis/fork/ext_q14.py`, which reads only the q4/q8/q14 GPTQ-W4 d1 BFCL directories and pools nothing.
- **Queue records.**
  - `done/fork_ext_gate_q14_gptq_w4_d1_bfcl.json`
  - `done/fork_ext_gate_same_q14_gptq_w4_d1_bfcl.json`
  - staged copies: `/data/ziyangs/cloq_work/staged/w99g_q14_gate/`
- **Logs.** `/data/ziyangs/cloq_work/logs/tasks/fork_ext_gate{,_same}_q14_gptq_w4_d1_bfcl.log`.
