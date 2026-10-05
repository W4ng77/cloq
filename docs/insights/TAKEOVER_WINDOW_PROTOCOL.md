# Takeover window: how long must BF16 control last, and is its value kept after handback? (protocol tw-v1)

**TL;DR** An exploratory follow-up diagnostic, chosen after seeing results and registered separately. It asks how the value of a BF16 takeover depends on its duration, and whether that value stays after control returns to the quantized agent Q.
- **Configurations and states.** Two q8 configurations, GPTQ-W4 d1 and SpinQuant-W4A4, run on the **same** ordinary BF16-sourced states: the q8 U2B rows of NEWMETHOD Panel A.
- **Design.** At each state the current action comes from B or from Q. Then BF16 executes the next L complete decisions and hands control back to Q, with L ∈ {0, 1, 4, ∞}.
  - L = 0 and L = ∞ are the existing endpoint arms (xQ and xB). They are reused after a consistency acceptance.
  - Only L = 1 and L = 4 are new: 4 suffixes per state.
- **Scale.** 3 blocks (f01–f03) is about 2,040 new suffixes. 6 blocks (f01–f06) is about 5,100, including SpinQuant's missing f04–f06 endpoints.
  - The scale is decided **once**, from the gate-measured throughput, before any window outcome is read. It is never changed by results.
- **Deadline.** 2026-10-05 21:00 PDT (Toronto 2026-10-06 00:00).
- **Frozen readings unchanged.** SAMEPREC, COMMONSTATE, NEWMETHOD and the holdout readings stay as they are. Nothing here amends them, and nothing here reads `analysis/fork/holdout/`.
- **Positioning.** This is a temporal-response diagnostic of precision value. It is not a new routing method: DMR (arXiv 2602.02711) already studies stepwise mixed-precision routing.

PROTOCOL sha256: frozen at gate submission (2026-10-04); the sha256 of this file, with this line exactly as written, is recorded in docs/RESEARCH_LOG.md (tw-v1 entry) and in the guard constant of `analysis/fork/analyze_takeover.py`. Later changes are appended amendments (§10).

| Frozen artifact | sha256 |
|---|---|
| `manifests/fork/takeover_window_v1.json` (510 q8 U2B rows f01–f06 copied verbatim from the panel manifest; endpoint sources; template tasks) | `396e3b35f4eaea15359e6c5e13b85e66218711bdeee2fe5da4cb8c05c428501d` |
| Row list f01–f03 (255 rows) | `119d01d4c6f854ad45df5240fb4283712c11b24037239034b75de4b70a3bc602` |
| Row list f01–f06 (510 rows) | `b8c607fe2b05422e6d2f0e1c56f4dd10856bb2129c77c78b51afe4a1ce9e3c6c` |
| Source panel manifest `manifests/fork/newmethod_panel_v1.json` | `7534c6907fa68bc8dab48061d7a2944a719e6e2fa123b639e7a0674c5a6ca201` |
| Bank U manifest (GPTQ f01–f03 endpoints ran under it; its U2B rows f01–f03 equal the panel rows) | `e236ee6483e723ffe8acd743ff2f5af8c1f92b49a39a7e721359c960ee12a907` |

**Row-list sha rule.** sha256 over the compact JSON (`separators=(",", ":")`) of the list `[state_key, block, domain, task_id, t, source_run]` for each row, sorted. The rule is `make_tasks_takeover.rows_sha`.

**Code.**
- `cloq/fork.py`: `ForkAgent` handback and `run_branch(handback=...)`.
- `scripts/a6000/takeover_window.py`: fork_driver mode `takeover_window`.
- `scripts/a6000/make_tasks_takeover.py`: manifest, gate, decide and panel.
- `tests/test_takeover_window.py`: CPU selftest with mock servers.

The commit that freezes this protocol records the sha256 of each file.

---

## 1. Status and label

- **Exploratory.** The two configurations were chosen **after** the NEWMETHOD and Bank U results were known:
  - GPTQ-W4 d1 had no resolved sustained-takeover benefit on ordinary states.
  - SpinQuant-W4A4 had H = Y_QB − Y_QQ = +11.8 pp.

  Every result is labelled "exploratory follow-up diagnostic (configurations chosen after seeing results)". No result is confirmatory, and none feeds back into a frozen reading.
- **No new holdout.** No holdout or other confirmatory set is used or created.

## 2. Configurations and servers

| Cell | Q role (copied verbatim from the endpoint task) | Expected Q server identity (canary / ckpt sha / effective config sha) |
|---|---|---|
| `gptq_w4_d1` | GPTQ-W4, calibration c1 (`bank_u_q8_gptq_w4_d1_f0k`, `cs_ref_q8_gptq_w4_d1_f0k`) | `a9f812fb17241b72` / `6ee628e6…` / `cd7c70f5e9fe40d4` |
| `spinquant_w4a4` | SpinQuant W4A4, learned rotations seed 0, pyhooks A4 (`nmp_tau2_q8_spinquant_w4a4_f0k`) | `66028ece4c06573c` / `b7223e20…` / `f32980982246866d` |

B is BF16 in every task: canary `e340c7991fa5bc08`, effective config `0d4bf272db1da1c5`.
- Every window task carries `fork.expect` with these values, taken from the endpoint task's `logs/tasks/<id>.servers.json`. The driver records `server_expect_ok`.
- A mismatch fails the gate. In the panel, it invalidates that task's output.

## 3. States and endpoints

**States.** The 510 q8 U2B rows of `newmethod_panel_v1.json` (f01–f06, 85 per block: retail 58 + airline 27). They are BF16-sourced (`a6k2_q8_bfpair_<blk>`), sampled outcome-blind (NEWMETHOD §2.2), with none missing. Both configurations use the identical row list.

Limitation, stated with every result: these are states that a BF16 agent reaches. They are not the states Q visits.

**Endpoint sources** (only read, never written):

| Cell | Blocks | Endpoint block (bank_rows.jsonl + branches/) | Ran under manifest |
|---|---|---|---|
| gptq_w4_d1 | f01–f03 | `analysis/fork/bank_u/q8_gptq_w4_d1/<blk>` (U2B rows) | Bank U `e236…` |
| gptq_w4_d1 | f04–f06 | `analysis/fork/commonstate/q8/ref_d1/<blk>` | panel `7534…` |
| spinquant_w4a4 | f01–f03 | `analysis/fork/newmethod/tau2/q8_spinquant_w4a4/<blk>`; f01 also uses `tau2_recovery/.../f01/rr1` (A7: 9/9 arms recovered) | panel `7534…` |
| spinquant_w4a4 | f04–f06 (6-block scale only) | new: `analysis/fork/takeover/endpoints/q8_spinquant_w4a4/<blk>`, tasks `tw_ep_q8_spinquant_w4a4_<blk>` | panel `7534…` |

- **New SpinQuant f04–f06 endpoints.** These run fork mode `bank_u`, unchanged: U2B, noop_frac 0.1, with the SpinQuant role copied verbatim. They stay outside `analysis/fork/newmethod/`, so they never enter a NEWMETHOD analysis. The NEWMETHOD phase-2 decision (`expansion_q8.json`, expand = false) is unchanged.
- **Current actions.** a_B is the recorded BF16 source action. a_Q is the action recorded in the endpoint row, from the cell's Q shadow at the stored prompt. Neither is regenerated.
- **Q shadow check.** The Q shadow is regenerated once per state as a check only (`shadow_identical`).
- **State rebuild.** Each state is rebuilt from the manifest row. It must equal the endpoint row on state_id, history_sha, prompt_ids_sha and steps_left (`state_identical`).

## 4. Policies and the decision count

At state h_t, the current action is a_x with x ∈ {B, Q}. Policy π_L:
1. Force a_x.
2. B (BF16) generates the next **L complete assistant decisions**.
3. Q generates every later decision, to the end of the episode.

| L | Suffix | Source |
|---|---|---|
| 0 | a_x, then Q to the end = arm **xQ** (BQ, QQ) | endpoint (reused) |
| 1 | a_x, B decides once, then Q | new |
| 4 | a_x, B decides four times, then Q | new |
| ∞ | a_x, then B to the end = arm **xB** (BB, QB) | endpoint (reused) |

**Counting rule** (`cloq/fork.py` ForkAgent):
- **What counts.** A decision is one assistant message produced by one generation request, **including all of its parallel tool calls**. The forced current action does not count.
- **When the switch happens.** Before each generated decision, the agent checks its own counter `n_cont`, the number of decisions generated so far. When n_cont ≥ L, it switches `llm_args["api_base"]` to Q's server once and records `switch_decision_idx`.
- **Isolation.** The counter and `llm_args` belong to the one agent object of a branch (llm_args is a per-agent deep copy). Concurrent branches share nothing.
- **Loop guard.** A loop-guard stop is not a generation and does not count. The guard is opt-in and off in this panel.
- **Errors.** A generation that raises does not count: n_cont is incremented only after the decision is logged.
  - A context overflow raised by Q's first request leaves switch_decision_idx set with n_cont = L (`attempted_handback` true, `handed_back` false). One raised by the simulator before that request leaves it unset. Both are valid outcomes (Y = 0) and pass `counter_ok`.
- **Labels.** Window and L = 0 records keep fork-v1's branch label (`xB`, controller B) although Q answers some or all of their decisions. The authoritative fields are `window.L` and the record's key (`W_<x><L>`, `R_<x><L>`); no loader may key on `branch` or `controller` for this panel.
- **Episodes that end inside the window.** If the episode ends before decision L+1 is requested (user stop, step or error budget), it is **not handed back** (`handed_back` = false). Its suffix then equals π_∞'s suffix.
  - These suffixes are kept in every estimate.
  - The share handed back and the number of BF16 decisions used (`n_B` = min(n_cont, L)) are reported per cell, source and L.
  - A task that ends inside the window is never read as evidence that "L suffices".
  - Structurally, in the BF16 source episodes, 85% of states have more than 1 decision after t and 62% have more than 4. These counts are for orientation only; the measured handback shares are reported.
- **Mechanics.** Switching to Q works like a controller switch in fork-v1. Q's server prefills the full history from scratch, and prefix caches are per process.

Per suffix, the driver records:
- Y, termination, official_reward and db_match;
- n_cont, n_B, n_Q, handed_back and switch_decision_idx;
- the per-request `api_base` (which server answered each decision);
- the prefix check, budget and env-hash checks, and suffix_sha.

## 5. Gate (at most 2 h from gate start)

**Task design.** One task per cell, `tw_gate_q8_<cell>`, on the same 8 f01 states for both cells, ordered by sha256("tw-v1-gate|state_key"). Only states whose BF16 source episode has more than 5 decisions after t are eligible, so that an L = 4 window can hand back.
- The first 4 retail and 2 airline eligible states, plus the first 2 other eligible states whose current actions a_B and a_Q render differently for **both** cells. The extra 2 exercise the non-reused BQ/QB endpoints and B vs Q windows that actually differ (5 of the first 6 are exact-agreement for GPTQ). Selection uses structure and recorded actions only, never outcomes.
- State keys: `006ba8f68c05b627 4bba2d240ce1711a 7c68e507e803e37d 9985ee888911c032 b858e455a36fcd30 c4209bd6e73eaf27 e34be950d767b00b fe1eb4b31bb5ddda`.
- Each state runs the 4 windows and re-runs all 4 endpoints through the same code (repro "all"). The switch-point check is on, and concurrency equals the panel's (6).
- **Simulator load.** Both gate tasks name the same simulator replica (`user_base` http://node005:8000/v1) and wait up to 30 min for each other to start (`co_gate`), so the rate is measured with two fork tasks on one replica. Each records its replica, job start and end times, and the replica's queue (requests waiting and running, sampled every 20 s) during its suffix jobs.

**Outcome blinding before the decision.**
- Gate tasks do not write window outcomes: their `window_rows.jsonl` carries no Y, termination, official_reward or db_match for window suffixes.
- Until `scale_decision.json` is written, only the pass/fail and throughput fields of `window_summary.json` are read. `branches/` of a gate is opened only by `make_tasks_takeover.py handback`, which prints per suffix the server that answered each generated decision (B/Q) and the counters, nothing else.
- Gate window outcomes never enter any analysis. The f01 panel task re-runs all 85 f01 states, the gate states included, into its own directory.

**Pass requires all of the following** (`window_summary.json` `gate_pass`; the task raises otherwise):
1. **Same checkpoint.** Server identity equals the endpoint tasks' (§2).
2. **L = 0 and L = ∞ reproduce the endpoints.**
   - L = 0 is run as handback(0, Q), so it exercises the switch path. L = ∞ is the controller-B path.
   - Each re-run must equal the stored endpoint's branch signature: suffix sha, every prompt and completion id sha, termination, reward, db_match, official reward, final DB hash and final step/error budget.
   - BB is compared with the original BF16 episode by `noop_check`.
   - A reused endpoint arm (`reuse=XX`, token-identical actions) is compared with XX.
3. **Prefix consistency across windows.** Each window run, through decision L, equals the L = ∞ endpoint of the same current action:
   - prompt ids of decisions 0..L+1, where L+1 is Q's first, re-prefilled request;
   - completion ids of generated decisions 1..L.

   A run that ends inside the window must equal the endpoint suffix as a whole.
4. **State, environment and budget at the switch.** For every handed-back window:
   - the history up to Q's first request is identical to the reference's (canonical sha);
   - the DB hashes from a strict replay are identical;
   - the step and error budget used are identical.

   Also required: state_identical, env_hash_init_ok, history_prefix_ok and budget_ok on every suffix.
5. **Independent per-agent counters under concurrency.** Every suffix's servers follow exactly B^L then Q (`pattern_ok`, from the logged api_base of each request). The agent's own counter agrees (`counter_ok`: n_cont = generated decisions, switch_decision_idx = forced index + 1 + L, exactly one forced decision; the L = 0 endpoint re-runs too). All windows and endpoints of a state run interleaved with the other states' at concurrency 6.
6. **At least one real B→Q handback** at L = 4 for each current-action source with `pattern_ok` true (not merely unrecorded): decisions after the window carry Q's api_base. The lead confirms it with `make_tasks_takeover.py handback` (outcome-blind, above).
7. **Shadow and exact pairs.** shadow_identical holds for every state. Where a_B and a_Q render identically, the B-first and Q-first windows of the same L are identical (`exact_pair`).
8. **No unchecked comparison.** Every window has a prefix reference (`prefix_unchecked` = 0) and every endpoint re-run is comparable (`n_not_comparable` = 0).
9. **Endpoint block valid.** The endpoint block's own `bank_summary.json` has gate_pass true and its B/Q server identity equals §2 (`src_ok`). This also covers the new SpinQuant f04–f06 endpoint tasks before their windows are analysed.

**Throughput measurement.** The gate also measures throughput (`throughput`: suffixes/hour at the panel concurrency, suffix wall p50/p90, the mean window and endpoint suffix seconds, the pool efficiency, and the simulator load above). Gate states are selected for long remaining episodes, so this rate is conservative.

**If the gate fails or runs past 2 h** (task seconds > 7200; `decide` refuses), no panel task is queued. The failure is reported to the lead and GPT with the summary path.

**Selftest** (CPU, mock servers, no GPU): `tests/test_takeover_window.py`.
- It uses a real frozen state rebuilt from `a6k2_q8_bfpair_f01`.
- It runs L ∈ {0, 1, 4, 6, 8, ∞} × {B, Q} concurrently with random delays.
- It checks:
  - the server sequence seen by the mock;
  - a two-tool-call decision counting once;
  - no handback when the episode ends inside the window;
  - prefix consistency;
  - the counter on a context overflow at, or just before, Q's first request;
  - negative controls: a different action breaks the prefix check, and a wrong L breaks the counter and pattern checks.
- Passed 2026-10-04.

## 6. Scale decision (once, throughput only)

`make_tasks_takeover.py decide --slots S --write`, run after both gates pass, writes `analysis/fork/takeover/scale_decision.json` and refuses to run again.

**Inputs.** Only:
- each gate's `gate_pass` and `throughput` fields (mean window and endpoint suffix seconds, pool efficiency, replica, job times, simulator load);
- the gate task's wall-clock overhead (task seconds − suffix seconds);
- S, the number of parallel 2-GPU fork slots the queue gives this panel, stated by the lead at decision time;
- the live simulator replicas in the instance registry (`simreg`) at decision time.

No Y and no window field other than these is read.

**Simulator capacity.** Every fork task shares the user simulator, and that is the known bottleneck (NEWMETHOD A7.E1: SpinQuant overloaded it at concurrency 8). Throughput therefore does not grow linearly with S. The projection uses S_eff = min(S, k × live replicas):
- k = 2 when both gates ran on the same replica with job intervals overlapping ≥ 50% of the shorter one and the replica's waiting-queue p90 ≤ 4 in both gates (a gate with no load samples does not show this);
- k = 1 otherwise (the per-task rate was not shown to hold with two tasks per replica).

The panel tasks are chained (`deps`) so that at most S_eff of them run at once, in block-major order (f01 of both configurations first).

**Projection.**
- Per block, a window task runs 85 × (4 + 4 × 0.1) suffixes: windows plus the 10% endpoint re-run sample. Its hours are 85 × (4 × mean window seconds + 0.4 × mean endpoint seconds) / (6 × pool efficiency × 3600), from the gate of that configuration, so the panel's job mix (mostly windows) is used rather than the gate's. A SpinQuant f04–f06 endpoint task is counted as 85 × 3 endpoint suffixes.
- Projected wall = SAFETY × max(total task-hours / S_eff, longest dependent chain), with SAFETY = 1.5.

**Rule.** Choose **6 blocks** iff now + projected wall ≤ 2026-10-05 21:00 PDT; otherwise choose **3 blocks** (f01–f03). Free GPU count alone is never converted into a completion time.

**After the decision.** The decision is never revised by results. If, at the deadline, some panel blocks are unfinished, the analysis uses the blocks complete at the deadline (strict-block rule, §8) and labels the design incomplete. Nothing is extended and nothing is re-selected.

**Second priority (α = 2 error-dose gap).** It is not started under this protocol. The decision file reports `alpha2_capacity_h`, the hours left after the projected finish. Whether to start it is the lead's and GPT's call.

## 7. Estimands

Per state s and cell c, Y_{x,L} ∈ {0, 1} is retail/airline DB success with a normal stop (`fork_driver._y`), for x ∈ {B, Q} and L ∈ {0, 1, 4, ∞}. The endpoints are Y_{B,0} = Y_BQ, Y_{B,∞} = Y_BB, Y_{Q,0} = Y_QQ and Y_{Q,∞} = Y_QB.

| Symbol | Definition | Reading |
|---|---|---|
| Δ_L | Y_{B,L} − Y_{Q,L} | effect of the current action under window L (Δ_0 = G, Δ_∞ = Y_BB − Y_QB = −D_cc) |
| V_{x,L} | Y_{x,L} − Y_{x,0} | value of the window itself, given current action x (V_{Q,∞} = H) |
| R_{x,L} | Y_{x,L} − Y_{x,∞} | shortfall of window L against sustained takeover |
| ΔΔ_L | Δ_L − Δ_0 and Δ_L − Δ_∞ | how the action effect changes with the window |
| rescue_{x,L} / damage_{x,L} | 1[Y_{x,0} = 0, Y_{x,L} = 1] / 1[Y_{x,0} = 1, Y_{x,L} = 0] | net = rescue − damage = V_{x,L} |

**Pre-specified contrasts per cell.** These are reported with intervals, as exploration with no confirmatory test:
- **C1:** R_{Q,4} = Y_{Q,4} − Y_{Q,∞}, the four-step window against sustained takeover.
- **C2:** V_{Q,4}, the value kept after a four-step takeover and handback.
- **C3:** R_{Q,1} and V_{Q,1}.
- The same quantities with x = B, and the Δ_L curve over L ∈ {0, 1, 4, ∞}.

**Transition tables** (per cell and x, between L levels), each listed with task and block:
- rescues at ∞ (Y_{x,∞} − Y_{x,0} = 1) that are kept at L = 4 and at L = 1, or undone;
- damages at ∞ that are kept or undone;
- changes that appear only at a short window (Y_{x,L} ≠ Y_{x,0} while Y_{x,∞} = Y_{x,0});
- the full state vector (Y_{x,0}, Y_{x,1}, Y_{x,4}, Y_{x,∞}) counts.

**Eligibility.** E_{x,L} = 1[the L = ∞ endpoint of source x (BB for x = B, QB for x = Q) generated more than L decisions after the forced action] (`ref_n_gen`, `E` in each window record).
- E is read from the existing endpoint only, so it is fixed before any window is run and is not post-treatment for the π_L vs π_0 and π_L vs π_∞ contrasts.
- On E = 0 the window never hands back: under deterministic replay π_L's suffix equals π_∞'s, so Y_{x,L} = Y_{x,∞}, R_{x,L} = 0 and V_{x,L} = V_{x,∞} **by construction**. Such states carry no information about value kept after handback, while they still add V_{x,∞} to an all-state V_{x,L}.
- Hence every V and R is reported all-state **and** within E = 1 with its interval and the E = 1 share, plus the E = 0 contribution (share × V_{x,∞} on E = 0) separately. C1 and C2 are also reported within E = 1.
- `handed_back` should equal E; disagreements (`n_E_handback_mismatch`) are reported and indicate nondeterminism.

**Handback.** Per cell, x and L: the share handed back and the distribution of n_B. A split by the realized `handed_back` (rather than E) is descriptive only.

## 8. Analysis plan

**Unit and admission.**
- **Unit.** A state with all 8 cells defined (2 sources × 4 L).
- **Endpoint values.** Exactly as the frozen loaders use them: `analyze_newmethod.load_tau2` primary rule (A6 agent-output errors = 0, A7 re-runs) for the SpinQuant panel blocks and the Bank U reference rows. The same A6 rule applies to the commonstate ref_d1 rows, the new SpinQuant f04–f06 endpoints and the window suffixes.
- **Errors.** A6 is read from the branch error record. An arm error that is not A6 stays missing and is never imputed.
- **Strict blocks.** A (cell, block) enters the primary analysis only when all 85 states have all 8 values. A single non-A6 missing arm removes that whole (cell, block) from the primary and only that state from the complete-case analysis, which is reported alongside.

**Means and intervals.**
- **Means.** All-state task-equal means (`analyze_dev.Boot.task_mean`).
- **Primary interval.** t over block means (K = 3 or 6).
- **Alongside.** The block bootstrap, and crossed task × block as secondary, as in analyze_newmethod. 95% intervals. The cross-cell comparison (SpinQuant vs GPTQ) uses the same states and blocks and is paired by state.

**Endpoint reuse acceptance** (in the panel, beyond the gate):
- On a hash sample, int(sha256("tw-v1-repro|state_key|cell")[:8], 16) / 16⁸ < 0.1, all four endpoints are re-run through the window code and compared as in the gate (§5.2).
- Any mismatch in a (cell, block) quarantines that block's endpoint-dependent contrasts (Δ_0, Δ_∞, V, R). L = 1 vs L = 4 contrasts remain, labelled as such.

**Window prefix acceptance** (every suffix):
- `pattern_ok` or `counter_ok` false on any suffix invalidates the task output, as a code or isolation failure. Repairing it is a deviation (§10).
- Prefix mismatches against the same-source endpoint are counted and reported. The primary keeps those suffixes (each one is a valid draw of π_L). A sensitivity analysis excludes states with any mismatch.

**Exact-agreement states** (a_B renders identically to a_Q): Δ_L = 0 by construction. Both sources are still run, which gives an in-panel determinism check (`exact_pair`). The conditional-on-difference readings use the non-exact states (Boot.ratio, as in NEWMETHOD).

**Script.** The analysis script, `analysis/fork/analyze_takeover.py`, is written **before** any panel output is read. Its guard checks this file's sha256 and the manifest sha256. It never opens `analysis/fork/holdout/`.

## 9. Reporting rules

- **The three meaningful answers**, read per cell from C1, C2 and the transition tables:
  1. **Value kept after a short takeover.** V_{Q,4} > 0 **within E_{Q,4} = 1**, with an interval excluding 0, reported with the E = 1 share. Part of the upgrade's value is obtained in a local phase and survives the return to Q. An all-state V_{Q,4} > 0 alone does not support this answer, because E = 0 states contribute V_{Q,∞} mechanically (§7).
  2. **Only sustained takeover helps.** Within E_{Q,4} = 1, V_{Q,4}'s interval includes 0, while R_{Q,4} < 0 with an interval excluding 0.
  3. **Longer is not monotone.** Damage or cancellation appears as the window grows: net V_{x,L} below V_{x,L'} for L > L', or short-window-only changes that reverse at ∞, with an interval excluding 0. This is read together with the earlier complementarity and cancellation finding.

  Anything else is "not resolved at this n". It is reported with the intervals and is never read as "no difference". At the 3-block scale the block-t interval has 2 df and is wide, so "not resolved at this n" is the expected wording for many contrasts.
- **No "four steps suffice".** An interval for R_{Q,4} that crosses zero must not be written as "four steps suffice" or "four steps are enough". It is written as "not distinguishable from sustained takeover at this n, interval [a, b]". No equivalence margin is registered, so no equivalence claim is made.
- **Handback.** Report the handed-back share and the BF16 decisions used, next to every window estimate.
- **Labels and positioning.** Label every result exploratory, with the configurations chosen after seeing results. State the U2B limitation (§3). State that the panel is a temporal-response diagnostic, not a routing method (DMR, arXiv 2602.02711).
- **Scale.** Report the scale decision record verbatim, and any block missing at the deadline.

## 10. Deviations

- **Amendments.** Any change is appended to this file as a dated amendment, with the reason and whether any window outcome had been read. Earlier text is never edited.
- **Labelling.** A change made after reading outcomes is labelled post hoc, and its results are reported as sensitivity only.
- **Infrastructure failures.** Simulator outage, timeouts or a lost node may be re-run once, by a recorded rule that names the arms. This follows the A7 precedent: the same servers, recorded actions and concurrency 1, decided without reading outcomes.

---

## 11. Amendment 1 (2026-10-04, about 22:00 PDT): null gate, subset naming, reading rules, execution guards

**TL;DR** Four revisions from GPT's review of commit `1c2a263`, appended before any formal panel task is released and before any window outcome is read. They add a true same-checkpoint null gate, rename the handback-eligible set as a reference-policy-defined subset, tighten the reading of a short-window null, and add two execution guards (NO PANEL; prefix-mismatch quarantine). Sections 1 to 10 are not edited; where this amendment conflicts with them, this amendment governs.

**Outcome status at the time of writing.** No window outcome had been read. `tw_gate_q8_gptq_w4_d1` had finished with `gate_pass` true (only pass/fail read); `tw_gate_q8_spinquant_w4a4` was running. Gate tasks do not write window outcomes (§5). No panel task existed. This amendment is therefore not post hoc (§10).

**Code.** `scripts/a6000/takeover_window.py` (`null_identity`, `quarantine`, overflow category, `null` spec), `scripts/a6000/make_tasks_takeover.py` (`gate --null`, `null_keys`, `plan_scale`, NO PANEL), `tests/test_takeover_window.py` (selftest extended, passed 2026-10-04). The sha256 of each file is recorded by the commit that adds this amendment. The changes leave the running SpinQuant gate unaffected (its process loaded the earlier code) and change no behaviour of a non-null gate spec except the overflow handling below. The two files over the 200-line cap (takeover_window.py, make_tasks_takeover.py) are split only after the panel ends.

### 11.1 Same-checkpoint null gate (new gate criterion 10)

§5.1 "Same checkpoint" checks that the window tasks use the same servers as the endpoint tasks; B and Q there are still different checkpoints, so it is not a null intervention. The null gate is:
- **Task** `tw_gate_null_bf16` (`make_tasks_takeover.py gate --null`), fork mode `takeover_window` with `null: true`. Both roles are BF16 (Q role = B role, one build); the driver points **both** controllers at B's server (`bases["Q"] = bases["B"]`), so one service answers every decision. The Q-role server is started by the worker but not used.
- **States.** Two f01 states with the most BF16 decisions after t, one retail and one airline, ranked by `n_decisions - t - 1` of the manifest row (structure only, ties by sha256("tw-v1-null|state_key")): `cf71d574b6a973bc` (airline, 58 decisions after t) and `dea7c55ac4885a0c` (retail, 35).
- **Arms.** The current action is fixed to a_B (`sources: ["B"]`). L = 0 (handback (0, B's server)), 1, 4 and inf run concurrently through the window code.
- **Pass** (`window_summary.json` `null` and `gate_pass`): for every state, the L = 0, 1, 4 runs have a branch signature identical to L = inf (suffix sha, every prompt and completion id sha, termination, reward, db_match, official reward, final DB hash, final step and error budget; only differing key names are stored); L = 0 and L = inf also pass `noop_check` against the BF16 source episode; every window is handed back with `counter_ok` (switch_decision_idx = forced index + 1 + L, so the switch still happens and is counted); `at_switch`, `budget_ok`, `env_hash_init_ok`, `history_prefix_ok`, server identity (both roles BF16, §2 B values) and the endpoint block's B identity hold.
- **Switch evidence and records.** In the null gate `pattern_ok` is trivially true (B and Q bases are one URL); the switch evidence is `switch_decision_idx` and `counter_ok`. The L = 0 and L = inf endpoint records are kept separately (`repro` keys `BB0`, `BBinf`), and `null.switch_counted` requires every L = 1, 4 window and every L = 0 handback to be handed back with `counter_ok` true. All 8 suffixes (2 states x L = 0, 1, 4, inf) run at once (`concurrency` 8), which is also the stronger nondeterminism test. The two longest states are the likeliest to overflow; an overflow there fails the gate for a reason other than identity and is diagnosed before any rerun.
- **Independence and order.** It runs independently of the two configuration gates, pinned to node006 (idle GPUs, not node002 where the SpinQuant gate runs) with `user_base` set to node006's own simulator replica (same Qwen3-30B-A3B-Instruct-2507 snapshot 0d7cf239 and max_model_len 65536 as node005; not node005, so the gates' throughput measurement is untouched). `decide` refuses to run until `tw_gate_null_bf16` is done with `gate_pass` true: the scale decision waits for it.

### 11.2 All-state primary; the eligible set is a reference-policy-defined subset

- **Primary.** All-state estimates are primary for every V, R and Δ.
- **Naming.** E_{x,L} (§7) is read from the L = inf endpoint, i.e. from the continuous BF16 trajectory after a_x. It is fixed before the window runs, but it is a property of that reference continuation, not a pre-intervention task property. §7's phrase "not post-treatment" is withdrawn; results on E = 1 are reported as "the subset defined by the reference policy (continuous BF16) generating more than L decisions".
- **Fixed composition for the duration curve.** The Q-action curve Y_{Q,L}, V_{Q,L}, R_{Q,L} over L ∈ {0, 1, 4, ∞} uses E_{Q,4} = 1 for **all four** L (one state set), alongside the all-state curve. Action-source comparisons (Δ_L) use the intersection E_{B,L} = 1 and E_{Q,L} = 1; the Δ curve across L uses E_{B,4} = E_{Q,4} = 1 at every L.
- **§9 answer 1 and §7.** Answer 1 (a short-takeover gain that survives handback) is still decided on E_{Q,4} = 1, now read as a conditional result on the reference-policy-defined subset and always shown next to the all-state V_{Q,4}; §7's rule that all-state V_{Q,4} > 0 alone does not support answer 1 is kept.
- **Overflow at handback.** A state whose first Q request after the window raises a context overflow is a valid failure (Y = 0, §4) and stays in every estimate, all-state and E = 1. It is reported per cell, x and L as its own category, **"attempted handback, generation failed"** (`overflow` = `attempted_handback_generation_failed`; summary `overflow`), next to the handed-back share and the ended-inside-window share. It is never filtered out. The handback-share buckets are made disjoint by taking `overflow` first: a suffix with `overflow` = `attempted_handback_generation_failed` is counted only there, never also as ended inside the window or in `n_E_handback_mismatch`.
- **Code fix.** For a context-overflow record, `budget_ok` is not checkable (no recount) and is recorded as None rather than False, and `prefix_check` does not flag the missing suffix sha as a mismatch; `counter_ok` already accepts switch recorded with n_cont = L. An overflow at a B request inside the window that the reference does not show is still a prefix mismatch (`overflow_in_window_not_in_reference`).

### 11.3 Reading rules (supersede §9 answer 2 where they conflict)

- If the L = 4 net gain V_{Q,4} has an interval crossing 0 and V_{Q,∞} − V_{Q,4} (equivalently −R_{Q,4}) has an interval excluding 0, the only permitted wording is: **"continuous takeover beats four-step takeover; the four-step net gain is unresolved."** It is never written as "short takeover is ineffective" or "only sustained takeover helps".
- If R_{Q,4} has an interval crossing 0, it is never written as "four steps suffice" (§9 rule kept).
- These rules apply to both the all-state and the E_{Q,4} = 1 readings, and to L = 1 in the same way.

### 11.4 Execution guards

- **NO PANEL.** `decide` chooses 6 blocks if they fit (§6), else 3 if they fit, else **NO PANEL**: `blocks` is empty, `no_panel` is true, and `panel` queues nothing. Free GPUs are never converted into a completion time (§6).
- **Prefix-mismatch quarantine** (supersedes §8 "the primary keeps those suffixes"). In the panel, a window suffix whose prefix check fails before the switch carries `quarantine` with the first mismatching item and a diagnosis (`state_rebuild`, `bf16_generation_nondeterminism`, `observation_or_simulator`, `reprefill_at_switch`, or the raw item). Its Y_{x,L} is excluded from the main analysis for Δ_L, V_{x,L} and R_{x,L}, and the state leaves the source-x duration curve at every L (fixed composition). Quarantined suffixes are counted per cell, x and L, diagnosed, and shown in a sensitivity table only; they never enter as a clean duration result. In a gate a prefix mismatch fails the gate (§5.3, unchanged).

### 11.5 Paper target and labels

- **Figure.** One takeover-duration vs net-gain curve per cell (L = 0, 1, 4, ∞; V_{Q,L} with block-t intervals, all-state and E_{Q,4} = 1), annotated at each L with the realized handback share (handed back / attempted handback, generation failed / ended inside window) and the rescue and damage counts whose difference is the net gain.
- **Readings it can support** (each subject to 11.3): a short-takeover gain that survives handback to Q; sustained takeover gaining more than short takeover; longer takeover both rescuing and damaging tasks, with cancellation.
- **Labels.** Exploratory follow-up, both configurations chosen after seeing results (§1). Deadline unchanged: 2026-10-05 21:00 PDT (Toronto 2026-10-06 00:00). Frozen readings (SAMEPREC, COMMONSTATE, NEWMETHOD, holdout) unchanged.

---

## 12. Amendment 2 (2026-10-05, about 07:20 PDT): analysis script recorded

**TL;DR** Records the analysis code required by §8 ("written before any panel output is read"). It implements §7, §9 and Amendment 1 (§11) as written; no estimand, subset, rule or interval is changed. Sections 1 to 11 are not edited.

**Outcome status at the time of writing.** Panel outputs for some blocks exist on disk, but no window outcome (`analysis/fork/takeover/q8_*/f0*/branches/`, the outcome fields of `window_rows.jsonl`) and nothing under `analysis/fork/keyorder/**/branches/` or `analysis/fork/holdout/` was opened while writing or testing the code. The code was tested only on synthetic data (fake panel directories with random Y). This amendment is therefore not post hoc (§10).

**Files.** The §8 script is split in three to keep each file under the 200-line cap:

| File | Role | sha256 |
|---|---|---|
| `analysis/fork/analyze_takeover.py` | guard, panel loader (A6 on window errors, §8 task invalidation), endpoint loading via `analyze_newmethod.load_tau2` (A6 + A7), main | `8d36b6a5a1c3cc219b65a52f6433f75493ee50ea9d8f536202fa19e1c6bf8932` |
| `analysis/fork/takeover_report.py` | estimands, subsets, transitions, handback, reading rules, cross-cell contrast | `ad20a3af06706c7404e4ffcad4bc8a8f24aedc9dd503ad048f1722414e95dcd6` |
| `analysis/fork/analyze_takeover_selftest.py` | `--selftest`, synthetic only | `3c99c8ba5648432ecc9bc34121c7ce3c360e52ff0075440445cc88b9c2655b32` |

**Guard.** The script refuses to run unless sections 1 to 11 of this file (the text before the `---` separator that precedes `## 12.`) hash to `75bf7c3557c63d7b8e1cf9026447ffce2a24a6d398501495c82c86daeb009750` (commit 560d717), this file contains the sha256 of all three files above, the manifest hashes to `396e3b35…` and the row list of the blocks in `scale_decision.json` hashes to the frozen row-list value (§ header). Any later code change needs a further dated amendment with the new sha256 values.

**Implementation choices that the text leaves open** (fixed here, before any outcome is read):
- **Strict blocks.** A quarantined suffix (§11.4) counts as recorded for the strict-block rule (§8); only a missing value (non-A6 error) removes the (cell, block). An A6 window error is Y = 0.
- **Quarantine masking.** A quarantined Y_{x,L} masks Δ_L at that L and every source-x quantity (Y_{x,·}, V_{x,·}, R_{x,·}, rescue/damage, short-window-only) at every L.
- **Reuse acceptance.** One repro mismatch in a (cell, block) masks Y_{x,0}, Y_{x,∞} and every quantity that uses them for that block; Y_{x,1}, Y_{x,4}, Δ_1, Δ_4 and Y_{x,4} − Y_{x,1} remain.
- **Answer 3.** "Longer is not monotone" fires when V_{x,L} − V_{x,L'} (L > L') has a primary interval below 0, or the signed short-window-only change (Y_{x,L} − Y_{x,0}) · 1[Y_{x,∞} = Y_{x,0}] has an interval excluding 0. A t interval of zero width (zero between-block variance) is flagged as degenerate in the reading text.
- **Fixed-composition B curve.** The x = B curve on E_{B,4} = 1 is reported alongside the registered Q curve, descriptive.
- **BF16 usage.** Per cell, x and L: n_B distribution and mean BF16 / Q prefill and generated tokens per window suffix (the first n_B generated decisions, guaranteed by `pattern_ok`); for L = ∞ the BF16 decision count is `ref_n_gen`; tokens of reused endpoints are not in the window rows and are not reported.
- **Outputs.** `analysis/fork/out/takeover_<UTC>.{json,md}`.

---

## 13. Amendment 3 (2026-10-05, about 07:45 PDT): reading needs two blocks, repro classes, strict-block and deadline checks

**TL;DR** Fixes from the review of the Amendment 2 code, written before any window outcome is read. A §9 / §11.3 reading now needs a t interval over at least 2 block means with nonzero width; otherwise the line says "not estimable". A repro record is classed as mismatch, error or not comparable, and only a mismatch masks a block's endpoint contrasts. Strict blocks need all 85 states, and only blocks complete at the deadline enter. No estimand or subset changes. Sections 1 to 12 are not edited.

**Outcome status at the time of writing.** As for Amendment 2: no window outcome (`analysis/fork/takeover/q8_*/f0*/branches/`, the outcome fields of `window_rows.jsonl`), nothing under `analysis/fork/keyorder/**/branches/` and nothing under `analysis/fork/holdout/` was opened. The code was tested only on synthetic data. No `takeover_*` output exists in `analysis/fork/out`. This amendment is therefore not post hoc (§10).

**Files** (supersede the Amendment 2 values; the guard requires these):

| File | sha256 |
|---|---|
| `analysis/fork/analyze_takeover.py` | `de416d4d710989b04f8c5fa140f0f49cee79b79eba5c3cdb03d147fcb853b415` |
| `analysis/fork/takeover_report.py` | `1d56aacf99df4470ef06e9a65f699db76d8adb651f4f6c263af3ef62b7409750` |
| `analysis/fork/analyze_takeover_selftest.py` | `b1a25529387238e3f6ec071d3c89153c715c9402e94785653444a6c84b763573` |

**Rules** (fixed here, before any outcome is read):
- **A reading needs two blocks and a nonzero-width interval.** Every reading line (V_{Q,L}, R_{Q,L}, V_{Q,∞} − V_{Q,L}, the answer 3 contrasts, the short-window-only change) uses its interval only when `t_ci95` exists (`n_blocks` ≥ 2) and the primary interval has nonzero width. Otherwise the line reads "<statistic> not estimable (<reason>)" and supports no §9 answer. The reasons are "no data", "data in fewer than 2 blocks, no t interval" and "zero-width interval (zero between-block variance)". The one-block block bootstrap fallback of `analyze_dev.summarise` (zero width at the estimate) is never read. This closes the case where masking or a dropped block leaves a statistic in one block.
- **Degenerate intervals.** A zero-width t interval (identical block means, possible at K = 2 or 3) does not support any answer. This supersedes Amendment 2's "flagged as degenerate in the reading text". V and R are judged separately: a non-estimable R_{Q,L} does not suppress the V_{Q,L} line, and the reverse.
- **Repro classes** (§8 "mismatch"; `analyze_takeover.repro_kind`).
  - *mismatch*: a comparable re-run whose branch signature differs (`differs`), or a failed `noop_check`.
  - *error*: the re-run raised (timeout, simulator outage, not run), i.e. `ok` False with `why` and no `differs`. This is an infrastructure failure (§10), re-runnable once by a recorded rule.
  - *not_comparable*: `ok` None (the stored endpoint has no comparable record).
  - Only a mismatch masks Y_{x,0}, Y_{x,∞} and their contrasts for the (cell, block). An error or a not-comparable record does not mask. Both are counted per block in the JSON and the .md. The block's endpoint contrasts are accepted only with zero mismatches **and** at least one re-run that compared equal (`endpoint_accepted`). So a block whose sample yielded no comparable re-run is masked as untested. §5.8 (no not-comparable re-run) stays a gate criterion. In the panel a not-comparable record is reported, not counted as an acceptance.
- **Task invalidation (§8, §5.5).** An L = 0 endpoint re-run with `window_counter_ok` False invalidates the task output like a window suffix. `server_expect_ok` and `src_ok` must be present and non-empty in `window_summary.json`. An absent field fails; it no longer passes vacuously.
- **Strict blocks (§8).** A (cell, block) enters the primary only when all 85 states are present (distinct state keys) and each has all 8 values. A bank row refused by `load_tau2` therefore drops the block instead of shrinking it.
- **Deadline (§6, §11.5).** A block enters only if `window_summary.json` `throughput.jobs_end_unix` ≤ 1791259200 (2026-10-05 21:00 PDT). A missing end time counts as not complete. Such a block is listed in `design_incomplete` with status "not complete at the deadline (§6)".
- **Handback mismatch.** `n_E_handback_mismatch` excludes only `attempted_handback_generation_failed`, as in the driver and §11.2. Other overflow categories are counted.
- **Report (.md).** The .md now carries the scale decision record verbatim, per-block status and repro counts (ok, mismatch, error, not comparable), and the handback buckets, E share, n_B and BF16 decisions for every window (§9). The answer 1 line prints the E_{Q,4} = 1 share.
- **Selftest.** It now reproduces the review case: f01 alone (K = 1) gives "not estimable" and no answer. It also checks that a zero-width 2-block interval gives no answer. It checks that a repro error and a not-comparable record do not mask, and that a mismatch-only block or a block with no ok re-run is not accepted. Further checks: the 85-state rule, a block finished after the deadline, and an absent `src_ok`. The planted answer 1 and "beats" modes now carry noise so that their block-t intervals are non-degenerate. Passed 2026-10-05 (`--selftest --B 300`).
- **Not changed.** Δ_∞ − Δ_0 is still not computed (it was not registered in §7), and the minor review items not listed here remain open.

---

## 14. Amendment 4 (2026-10-05, about 07:47 PDT): analysis script frozen

**TL;DR** The Amendment 3 code is frozen as the §8 analysis, frozen before any outcome of this experiment was read. No code, estimand, subset or rule changes. Sections 1 to 13 are not edited.

| File | sha256 |
|---|---|
| `analysis/fork/analyze_takeover.py` | `de416d4d710989b04f8c5fa140f0f49cee79b79eba5c3cdb03d147fcb853b415` |
| `analysis/fork/takeover_report.py` | `1d56aacf99df4470ef06e9a65f699db76d8adb651f4f6c263af3ef62b7409750` |
| `analysis/fork/analyze_takeover_selftest.py` | `b1a25529387238e3f6ec071d3c89153c715c9402e94785653444a6c84b763573` |

**Outcome status.** No window outcome (`analysis/fork/takeover/q8_*/f0*/branches/`, the outcome fields of `window_rows.jsonl`), nothing under `analysis/fork/keyorder/**/branches/` and nothing under `analysis/fork/holdout/` was opened. No `takeover_*` output exists in `analysis/fork/out`. `analyze_takeover.py --selftest --B 300` (synthetic data with random Y only) passed at 07:46 PDT. Any later change to these files needs a further dated amendment with the new sha256 values.
