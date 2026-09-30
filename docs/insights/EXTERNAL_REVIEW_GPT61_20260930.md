**TL;DR** External review by GPT-6.1 (2026-09-30), based on commit ed45187, and the agreed decisions after one round of
reply. New main line: how quantization changes the agent's *current decision* vs its *subsequent execution*,
identified by a same-state 2×2 fork (current action from B or Q × continuation controller B or Q); when those changes
cause real task loss. Conformal leaves the core. The targeted-repair method is out of scope for this submission.
Development uses all 85 tasks with many independent blocks; confirmation uses the untouched telecom holdout (34
tasks) after a frozen protocol. Thresholds: g_min = 3 pp, non-inferiority and equivalence margin 3 pp (5 pp
sensitivity only). P0 statistics and measurement fixes and the BF16 q1–q5 pairing start immediately. The replay
engineering gate is the evening of 10-01.

# External review (GPT-6.1) and agreed plan, 2026-09-30

The full execution plan and replies were exchanged in chat via the author. This file records the substance the
executing agents must follow. Section numbers "§x" refer to the reviewer's plan.

## A. Agreed decisions

1. **Main line.**
   - Measure how quantization changes the current decision and the subsequent execution, and when these changes cause loss.
   - Core design: the same-state 2×2 fork.
   - A mechanism and measurement paper; no method contribution this round.
   - No claims of "success-equivalent", "lossless", "quantization destroys recovery" or "losses concentrate in few steps" before the evidence exists.
2. **Conformal.** Removed from the core, title and abstract. Existing code and records are kept and described accurately.
   The statistics collaborator's role moves to crossed-design inference (see D).
3. **Checkpoint lottery.** Correct wording: "exploratory results did not replicate in the pre-registered confirmation".
   - This is not evidence that checkpoint effects are absent.
   - It is not evidence of BF16 = W4 success equivalence.
4. **q4 range.** "+1.5 to +3.9 pp" applies only to q4. q8 AWQ-W4 d3 is +5.29 pp (+8.24 pp on q2). Always report stratified results; pooled averages support only their weighted estimand.
5. **Three populations kept distinct:**
   - repeated runs on the fixed task set;
   - a new task distribution;
   - new checkpoints of the same method.

   Task, nonce and checkpoint are crossed (shared indices), not nested.

## B. P0 statistics fixes (§4)

- **H3** (`prereg_h1_h4.py::split_cos`): scaling uses the true-pair A−B differences, and the permutation reuses the fixed cosine matrix.
  - Main fix: a pairing-invariant scale, either frozen from independent development data or an unpaired pooled scale.
  - Sensitivity: recompute the full preprocessing inside each permutation.
  - Fix feature lists, zero-variance and missing-value handling, and split seeds, using the same seeds for the observed statistic and the permutations.
  - Simulate the false-rejection rate under exchangeability and power under a known signal, with Monte Carlo error.
  - The old H3 p-value stays as history; the "confirmed" label is removed until the corrected test passes.
- **Report separately:** pooled, RECAL-only, RAND-only, per-model, and within-model-and-method.
  - The original same−different cosines are q4 RECAL 0.095, q8 RECAL 0.140, q4 RAND 0.323, q8 RAND 0.578. RAND contributes about 74% of the pooled F.
- **p1 variance decomposition:** the subtracted term includes the shared nonce main effect.
  - The H1 permutation p-value is unaffected: the term is invariant under checkpoint relabelling (agreed in the narrow sense).
  - Any new variance formula, df or standardisation must be re-validated.
  - Use a crossed model with explicit nonce main effect, design matrix and df.
  - A negative moment estimate is not "negative variance"; truncating it at zero is not evidence of absence.
  - This does not reopen the lottery line.
- **Success.**
  - Non-inferiority: H0 is Δ = success_Q − success_B ≤ −ε, with ε = 3 pp justified in writing before unblinding.
  - Equivalence: TOST, with the 90% CI inside (−3, +3) pp.
  - Report ordinary difference tests separately.
  - Paired design: common nonce (and simulator configuration). Compute run-level success first, then paired run differences; do not treat task×run rows as independent.
  - Generalisation to new tasks: a separate analysis with task_id-clustered crossed resampling.
- **Task-level difference effect sizes (§4.5), next to λ–c (kept as an auxiliary model):**
  - Δ = E_i[q_i − p_i] and D = E_i[(q_i − p_i)²] = Δ² + Var_i(q_i − p_i).
  - D is a U-statistic over independent replicate blocks r: D̂ = Σ_i w_i{(Σ_r Z_ri)² − Σ_r Z_ri²}/{R(R−1)}, with Z_ri = Y_Qri − Y_Bri.
  - V̂ is the task heterogeneity beyond the mean change.
  - Cross-check against the Hamming form, excluding same-nonce coupled cross terms.
  - Keep negative unbiased estimates; do not claim exact tests for D near zero.
- **Reference controls, recorded separately:**
  - identical-setting repeats;
  - nonce input perturbation;
  - numerics / rotated-BF16;
  - fixed random weight perturbation (a control intervention, not a "no change" null).

  Floors are reported stratified; single canonical-run floors are flagged.

## C. P0 measurement fixes (§5)

| Location | Fix |
|---|---|
| `scripts/a6000/openloop_topk.py::p_act` | Force-score the key token, or give truncation bounds (missing ≤ p_20) and a missing flag; cross-check against the fully generated action class |
| `topk_kl` | No longer called exact KL; use common known categories plus a residual, or complete the candidate probabilities |
| `name_mass` | Main metric = fully generated and parsed tool name and arguments; the prefix approximation only as a proxy after its error is measured |
| `analysis/insights/iter_4/common4.py::_feat_traj` | Rename `confirm_bw` to a confirmation-request proxy; judge real authorisation and violations from user replies, tool rules and state changes |
| write classification | Explicit tool-type table: read / write / handoff / invalid |
| `cloq/divergence.py::analyze_task` | Causal forks query both precisions only on the same saved history |
| `cloq/nl_judge.py` | If used: explicit dependency injection or serial calls, plus a concurrency-isolation check |
| `cloq/metrics.py::task_success` | Name it accurately (DB success for retail/airline); report other scores separately; telecom uses its official deterministic task-basis success |

- The act/talk shift conditional on BF16's choice has a selection effect. Add full-action comparisons, unconditional analysis and random-perturbation controls.

## D. Statistics collaborator deliverables (replacing conformal theory)

- Estimands and intervals for fixed tasks and fixed checkpoints.
- The assumptions, and matching intervals, for generalising to new tasks and new checkpoints.
- Paired-block inference for G and for A/C/I.
- Simulation calibration for sparse flips and statistics that degenerate near zero.
- Power and sample size for confirmation, from development data.
- Multiplicity rules across models, methods and secondary endpoints.

## E. Core experiment (§6–§7)

- **Primary state distribution.**
  - Along Q's actual history, at each candidate position, B and Q read the *identical* history. The primary state is the first semantic action divergence: act/talk class, tool name, or normalised arguments.
  - At most one state per task × model × checkpoint × block, frozen before any fork outcome is seen.
  - Free-text-only differences are recorded separately. The paper states that text differences such as commitments or authorisation requests can matter and are out of the primary scope.
  - Late divergences are kept, with their remaining budget.
  - Tasks with no divergence stay in the denominator with zero effect.
- **Branches.** From the saved state h, generate full actions a_B and a_Q, execute the current action, then continue with B or Q to the end: L_BB, L_BQ, L_QB, L_QQ.
  - G = E[Y_BQ − Y_QQ] = h − b, where h = P(Y_BQ = 1, Y_QQ = 0) (rescue) and b = P(Y_BQ = 0, Y_QQ = 1) (new damage).
  - A = L_QB − L_BB, C = L_BQ − L_BB, I = L_QQ − L_QB − L_BQ + L_BB, with L_QQ − L_BB = A + C + I.
  - Report the paired four-way composition.
- **Primary confirmatory endpoint.** One-replacement gain over the full task pool with fixed cell weights, G_all.
  - The conditional-on-divergence G is secondary and uses the ratio form with block resampling.
  - Divergence prevalence, number of valid states and exclusion reasons are always reported.
  - Infrastructure failures are never coded as "no divergence".
- **Recovery claims need process evidence.**
  - Is the current Q action verifiably wrong?
  - Is there a later correction aimed at that error?
  - Which task requirements are satisfied after it?
  - Is non-recovery tied to remaining budget, error type or controller?

  How to read G close to zero:

  | Pattern | Reading |
  |---|---|
  | Wide interval | Inconclusive |
  | Many rescues and many breaks | Cancellation |
  | Both branches usually succeed | Small consequence |
  | Explicit Q error, then a correction, then success | Observed recovery |

- **Replay acceptance (the engineering gate, evening of 10-01).**
  - Correct restoration of the DB, devices, user-simulator state and step budget.
  - No-op B→B and Q→Q reproduce the trajectories and outcomes.
  - With B and Q pointed at the same checkpoint, all four branches agree.
  - Branches are isolated; execution order does not matter.
  - After a checkpoint switch, the context is re-prefilled from history (no KV or prefix-cache reuse across weights).
  - Forced actions consume the same step and error budget.
  - Canonical state hashes match after save/load.

  If the gate is not met, forks are not used as mechanism evidence.
- **Scope.** q4 and q8 × GPTQ-W4 and AWQ-W4.
  - Primary checkpoints are fixed by completeness before analysis, never by favourable old results.
  - Development: all 85 tasks, about 20 independent blocks. Each block changes a stated source of randomness (a new nonce).
  - Confirmation: telecom holdout, 34 tasks, about 40 blocks. The final count comes from development block variance and is frozen before the holdout opens.
  - Measure throughput on a small real batch first: BF16 shadow proposals, prefix prefill, the simulator and retries.
- **Scoring.**
  - Retail/airline: DB success, named as such.
  - Telecom: the official deterministic task-basis success.
  - Graders are listed per domain.
  - Secondary outcomes are pre-specified. Policy violations only after their grader is validated.

## F. Thresholds

| Parameter | Value | Decision rule |
|---|---|---|
| g_min | 3 pp | Plan power for true G = 3 pp |
| Positive gain | — | Lower one-sided 95% bound of G > 0 |
| Gain above 3 pp | — | Lower one-sided 95% bound > 3 pp |
| Success non-inferiority ε | 3 pp | Lower one-sided 95% bound of Q − B > −3 pp |
| Small average effect | ±3 pp | Valid 90% CI inside (−3, +3) pp |

- 5 pp is pre-registered as a looser sensitivity analysis only; it never replaces the 3 pp primary.
- A pooled pass does not imply a per-model or per-method pass.

## G. Priorities and deprioritised items

- **Order:** complete task coverage → enough independent blocks → validation on unused tasks or independent checkpoints → more model cells.
- **Deprioritised:**
  - new quantization formats;
  - more high-dose Gaussian cells;
  - collapsed W3/KV settings;
  - large low-capability-model matrices;
  - more checkpoints for fingerprint significance;
  - sampling baseline (only with per-request seeds derived from run/task/turn);
  - simulator swap (after the main pipeline is stable, on a full preset queue).

## H. Schedule

| Date | Work |
|---|---|
| 09-30 | Audit record, P0 fixes, BF16 pairing, queue priorities, replay engineering start |
| 10-01 | Replay no-op acceptance; go/no-go in the evening |
| 10-02 | Development forks: 85 tasks × 2 × 2 × blocks |
| 10-03 | Freeze `PREREG_FORK_CONFIRM.md` (thresholds, sample size, analysis family); start telecom holdout confirmation |
| 10-04 – 10-05 | Confirmation completes, simulator robustness if time allows, evidence freeze |

- **Deliverables:** `docs/insights/METHODOLOGY_REVISION.md`, `FORK_PROTOCOL.md`, `PREREG_FORK_CONFIRM.md`, and a new analysis directory, each with a machine-readable manifest, script entry points, input hashes and run commands.
- **After each stage:** report what changed, what was observed, which claims were supported / refuted / unresolved, gate status, GPU and simulator cost, commits and paths.

## Literature to position against (§13)

- Accuracy is Not All You Need (2407.09141)
- Flat Score Amplified Failures (2607.27275)
- AgentProv (2609.00052)
- Model Equality Testing (2410.20247)
- The Replay Gap (2608.08239)
- Dynamic Mixed Precision Routing (2602.02711)

Update `docs/insights/SURVEY.md`.

## Round 2 (after W29 corrections), agreed

- **Old main line ended.**
  - "Success-equivalent, behaviourally distinct" leaves the title, abstract and contribution list. Success equivalence is not established, and no W4 fingerprint was detected.
  - Random-perturbation result, wording: "The corrected exploratory analysis detected cross-run behavioural consistency in random-perturbation checkpoints; no corresponding evidence was detected for W4 quantized checkpoints." Its RAND-only p = 0.028 is post-hoc and must be read with multiplicity. The pooled result no longer supports any quantization claim.
  - "Turnover above the noise floor" stays as motivation, restricted to the verified task set, run conditions and comparison.
- **Main line.** On identical interaction histories: which task consequences do quantized action substitutions cause, and which part comes from the current action, the subsequent execution, and their interaction?
  - A different full action is not by itself a mechanism finding. Forks must show the consequence, locate it, and give process evidence.
  - The BF16 action is only a reference. Defects are judged from tool preconditions, task requirements, authorisation and state changes, never from "differs from BF16".
- **Gates.**
  - The 10-01 engineering gate stays.
  - No research go/no-go on the sign of G.
  - The development evidence gate asks whether divergence consequences are measured clearly enough to yield a specific explanation testable on the holdout.

  | Development deliverable | Question |
  |---|---|
  | Divergence coverage | How many tasks in the full pool reach a qualifying first divergence, and at what position |
  | Consequence composition | Counts and shares of rescue, new damage, both succeed, both fail |
  | Four-branch decomposition | G and A/C/I with intervals, per model and method |
  | Process mechanism | Verifiable action defects, evidence of later correction, remaining budget |
  | Precision | Which effect sizes can be excluded, and which conclusions remain indistinguishable |

  Paths after development:
  - Stable consequences with mechanism evidence: freeze the mechanism hypothesis and confirm.
  - Small effect with a narrow interval: report a limited consequence, and check rescue/damage cancellation.
  - A few critical divergence types: freeze the type definitions and opportunity denominators, then confirm their damage rates.
  - Wide intervals and few events: report insufficient evidence; no new story.
- **Per-fork annotation, three independent fields:**
  1. Does the current action have a verifiable defect?
  2. Is there a later correction aimed at that defect?
  3. Which task requirements are satisfied at the end?

  Only "defect, then correction, then satisfied" supports recovery. Otherwise: "not recovered under the tested continuation controllers and the fixed remaining budget". Freeze the tool-type table (source, version, manual check) before confirmation.
- **Inference.**
  - Report conclusions for the fixed benchmark task pool and for a new task distribution separately. Nonce repeats reduce run-level uncertainty, not task-sampling uncertainty.
  - Non-inferiority is not equivalence. A 3 pp margin that the data cannot resolve is reported as inconclusive.
  - New independent tasks help generalisation more than further repeats.
- **Submission.** Still possible, but the fork design itself is not the contribution. The contribution has to be one of:
  - a stable, consequential divergence;
  - a small average effect with a clear rescue/damage cancellation;
  - recovery shown with process evidence;
  - a few predefined divergence types that carry high damage risk.

**Our addition:** include the telecom development split (80 tasks, disjoint from the 34-task holdout) in development forks, to add independent tasks in the confirmation domain. The 22 excluded retail/airline tasks stay out: they were selected on BF16 behaviour.
