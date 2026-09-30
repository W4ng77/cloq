# Replay acceptance: same-state forks on ALFWorld and BFCL multi-turn (protocol fork-ext-v1)

**TL;DR** The fork-v1 engineering gate (FORK_PROTOCOL.md §7) was ported to the two simulator-free environments and passes on both. The checks are on q4 GPTQ-W4 d1 (c1) vs BF16, on the W36-ext smoke blocks, which are development runs and never the reported eval runs.

Every no-op is bit-exact: prompt token ids, completion token ids, observations, outcome and the BFCL result record. Every replayed step reproduces the recorded observations and the agent's prompt, and backend-state hashes are identical across branches. With no LLM user in either environment, the user-simulator confound of the τ² forks is absent by construction.

BFCL passed on its second run. The first run failed a representation check: the fork replay wrote text replies differently from how BFCL records them. That was fixed before any development fork ran.

Code: `scripts/ext/fork_ext.py`; replay hooks in `scripts/ext/{alfworld_run,bfcl_run}.py`; worker kind `fork` + `"env"` (`scripts/a6000/worker.py::run_fork`); task maker `scripts/ext/make_tasks_extfork.py`.

## How state is restored

ALFWorld and BFCL are deterministic, and neither has a user simulator. A fork state is rebuilt by re-executing Q's recorded action prefix through the adapters' own episode code:
- **ALFWorld:** reset the same game and replay the commands.
- **BFCL:** fresh backend class instances from the entry's initial config; the calls are replayed through BFCL's `inference_multi_turn_FC` loop, with `miss_func` holdout injection included.

A policy hook replaces the server call:
- before the state: the recorded response;
- at the state: the forced action a_X;
- after the state: the controller's live server.

Budgets need no restoration because they are re-accumulated by the replay: ALFWorld has 50 actions / 50 decisions, BFCL 20 steps per turn.

**Backend-state hash before every decision**
- ALFWorld: the PDDL facts.
- BFCL: the canonical public instance state plus the seeded-RNG position (memory addresses and back-references removed).

**Divergence**
- **Category:** a change of action class (act / talk / parse_fail / empty), tool count, tool name, or normalised arguments. For ALFWorld the argument is the `act` command, lower-cased with whitespace collapsed.
- **Where the search looks:** along Q's replay. At each step B receives the identical chat request, and B's server-side prompt ids must equal Q's recorded ids.
- **Q-replay check:** at the state, the Q server regenerates a_Q, and its completion ids must equal the recorded ones.

## Gate results

| Check (fork-v1 §7) | ALFWorld (q4 GPTQ-W4 d1, 12 smoke games) | BFCL r2 (q4 GPTQ-W4 d1, 40 smoke items) |
|---|---|---|
| Search: states / items (excluded) | 12/12 (0) | 26/40 (0); gate runs the first 12 |
| Categories covered | command | class act→talk, talk→act, tool_args, tool_count, tool_name |
| Q replay at state (completion + prompt ids, action) | 12/12 | 12/12 |
| (a) Q→Q no-op | 12/12 | 12/12 |
| (a) B→B no-op (BF16 smoke blocks, mid-episode t) | 4/4 (t = 3–25) | 4/4 (t = 4–6) |
| Replay fidelity: prompt + observations at every replayed step; state hash equal across the 4 branches and equal to the search replay | 12/12 states (every replayed step; the B→B no-ops add 25-step replays) | 12/12 states (47 replayed steps) |
| (b) same checkpoint (two servers of the Q ckpt) | search: 0 divergences in 6 items; 4/4 states with four identical branches, equal to the original | search: 0 divergences in 12 items; 4/4 states with four identical branches, equal to the original |
| (c) isolation: reversed order and all-four-concurrent give identical signatures | 4/4 | 4/4 |
| (c) save/load (history, tools, a_B hashes) | 12/12 | 12/12 |
| (d) budget | implied by exact prefix replay; the no-op final counters equal the original | same |
| (e) re-prefill: QB first request = Q's recorded prompt at t+1 | 12/12 | 12/12 |
| (e) re-prefill: BQ first request = BB's first continuation request | 12/12 | 12/12 |
| Verdict | **PASS** | **PASS** (r2) |

Evidence:
- ALFWorld: `analysis/fork/ext/gate/alfworld_q4_gptq_w4_d1/gate.json`, `analysis/fork/ext/gate/alfworld_q4_same_ckpt/gate_same.json`.
- BFCL: `analysis/fork/ext/gate/bfcl_q4_gptq_w4_d1_r2/gate.json`, `analysis/fork/ext/gate/bfcl_q4_same_ckpt_r2/gate_same.json`.
- For every gate output: `states/`, `branches/`, `search.json`.

**BFCL r1** (`analysis/fork/ext/gate/bfcl_q4_{gptq_w4_d1,same_ckpt}/`, kept as history) failed on the `outcome` field only:
- Q→Q no-op 5/12, B→B 1/4, same checkpoint 0/4 equal to the original. All prompt ids, completion ids, observations, rewards and terminations matched.
- **Cause:** for a replayed text reply, the fork rebuilt `tool_calls: []`, but vLLM returns `null`. BFCL's parser therefore recorded `[]` instead of the content string in `bfcl_result`. This does not change the prompt or the evaluator verdict, but it breaks the bit-exact result comparison.
- **Fix:** `raw_from_rec` keeps `null`. r2 then passes every check.

**Coverage gaps**
- The gate states are on base and miss_param only, because the gate takes the first 12 states in block order. miss_func and long_context are covered by the QQ no-op sample (10%) of every development task, and a mismatch quarantines that task (protocol A).
- The gate runs q4 only, with B+Q on one GPU. The q8 development tasks use the 2-GPU layout of the τ² q8 gate; their QQ no-op sample is the ongoing check.

## Throughput (gate runs, q4, one GPU B+Q, concurrency 8)

| | ALFWorld | BFCL |
|---|---|---|
| Divergence rate (smoke) | 12/12 = 100% (t* 0 in 10/12) | 26/40 = 65% (t* 0–9, median 1.5) |
| Shadow B cost per searched decision (median) | 2.2 s | 3.6 s |
| Search wall per item (serial per item; 8 in parallel) | 7.1 s | 36.8 s |
| Branch duration, median / p90 | 186 / 315 s | 31 / 112 s |
| Effective wall per branch at concurrency 8 | 26 s | 6.0 s |

**Development estimate:** 3.1 branches per state (BB/BQ/QB plus a 10% QQ sample).
- **ALFWorld q8:** 134 games, about 1.1–1.4 h wall per cell on 2 GPUs.
- **BFCL q4:** 197 items per category, about 1 GPU-h per category and cell.
- **BFCL q8:** about 2–3 GPU-h per category and cell.
- **Total:** the 36 queued tasks come to about 90 GPU-h. These are estimates from the q4 gate; the q8 wall is not yet measured.
