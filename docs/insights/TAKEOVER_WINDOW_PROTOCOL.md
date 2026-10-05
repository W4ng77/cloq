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
