# Insight candidates, iteration 1 (2026-09-28/29)

Owner: cloq-insight. Framing: `docs/COLING_PLAN.md` §2 (perturbation equivalence, first-order margin model, P1–P3).
No ledger exists yet, so every insight below is **new**. The draft was revised after reading `SURVEY.md` and the two
sweeps (`survey_sweeps/margins_flips_divergence.md`, `survey_sweeps/compressed_agents_eval_noise.md`).

**What we inherit and do not claim.** The per-step margin flip model, P(flip at t) ≲ P(margin_t < σ), is published:
- Du et al. 2026, TMLR, 2609.26621, Eq. 14 (single-turn, BF16 vs FP16);
- validated empirically by Integer Alibi (2608.13756; margin → flip AUC 0.94) and MarginGate (2605.30218).

Our `s01` result (decision-level AUC 0.86–0.97) is a replication of it in a closed-loop agent across perturbation
families, not a contribution. Every novelty claim below sits on top of that model:
- (i) its composition over closed-loop decisions;
- (ii) saturation along δ across perturbation families;
- (iii) a later damage threshold;
- (iv) cross-model prediction and D-sufficiency;
- (v) the null/equivalence definition.

**The closest competitor** is Flat Score (Jang et al. 2607.27275): same τ²-bench, AWQ-INT4/FP8, a verbal margin
account, no logprobs, no divergence measurement, no perturbation null.

## Data snapshot

- **4080 (Qwen3-4B, τ² retail+airline, 85 dev tasks, 8k harness, greedy):** raw runs are not on this machine
  (release `data-4080` expected around 2026-09-29 04:00). Every 4080 number is **recomputed from analysis files;
  raw-run check pending**, and the source file and section are given each time.
- **A6000 (32k harness, greedy, top-5 logprobs):** snapshot `analysis/insights/iter_1/out/s00_snapshot.json`,
  taken 2026-09-29T01:26Z, 36 run dirs. Re-running `run_all.sh` overwrites `out/` with a newer live snapshot, so numbers will drift upward as runs finish. No matrix cell is complete in both domains. Completed at snapshot:
  q4 airline for bf16, null_n1, gauss0.03 s1/s2, gauss0.3 s1/s2, rtn_w4 n1/n2, rtn_w8 n1/n2; det_q4_a/b and det_q30a3_a/b;
  q4/q8/q14 `_bf16_cal` airline. Every other run is **partial** (in progress). All A6000 numbers below are a
  **pilot on a live snapshot**. Scripts right-censor tasks that are still running, and the numbers will move.
- Scripts (read-only over `runs/`): `analysis/insights/iter_1/` `s00`–`s05`, `run_all.sh`; outputs go to `out/`.
  - `s01`: token-level flips on identical-context decisions.
  - `s02`: closed-loop first divergence (Kaplan–Meier).
  - `s03`: cross-model margin tables and pre-registered predictions.
  - `s04`: the node numerical floor.
  - `s05`: pilot outcomes.

### A design issue found while computing (not an insight, but it affects every cell)

`s04_node_floor.py` shows that **q4 BF16 served on node005 (`det_q4_a`) is not bitwise identical to q4 BF16 on
node003/node004**:
- node005 vs node003: 20/20 tasks diverge, and the identical-context token shift is non-zero on 59% of tokens (median |d| = 0.125 nats).
- node004 vs node003 (`det_q4_b` vs `q4_bf16`): 0/20 tasks diverge over 245 identical decisions and 22,667 tokens, all with shift 0.
- q30a3 det a (node005) vs b (node004): identical.

So at least one single-GPU agent server on node005 computes different logits. That node hosts all q4 RTN runs and
q8 gauss0.1/0.3. The user simulator is also served from different endpoints. In `s02` there are 1–8 "context
mismatch without agent flip" events per config, meaning simulator-side numerical differences.
**Consequence:** the matrix's "serving is deterministic" premise holds per server but not across nodes. The
per-node determinism check should compare against a fixed reference node, not only a/b on the same node.
Scientifically this is also the cleanest possible P1 datum, and I1 uses it.

---

## I1. Closed-loop divergence is set by the agent's own tie density, not by the perturbation (P1, sharpened)

**Status:** new.

**Principle.** In a greedy closed-loop LLM agent, the probability that a perturbed run's trajectory leaves the
reference trajectory saturates at the smallest perturbation that can break exact near-ties. This includes pure
floating-point differences between machines. It saturates because free-text turns contain several near-tied tokens
each. Trajectory divergence therefore measures the model's tie density, not the size or kind of the perturbation,
and cannot rank perturbations.

**Mechanism.** First-order margin model: token i flips iff the perturbation lowers its top-1/top-2 gap m_i by more
than m_i, so P(decision flips) = 1 − ∏_i P(D ≥ −m_i). A natural-language turn has about 3–6 tokens with m < 0.5 nats,
and many with m = 0 (bf16 exact ties). Any D whose spread exceeds the bf16 logprob resolution (≈0.125) therefore
flips about 40% of text turns. The closed loop turns one flip into a new context for every later decision, so
P(trajectory diverged by step t) = 1 − ∏_{s≤t}(1 − p_s) → 1 within about 10 decisions. Tool-call decisions have
median min-margin ≈ 6–7.5 nats and do not take part at small D. That is why divergence saturates while tool
behaviour is still intact.

**Evidence.**
- *Divergence at the numerical floor equals divergence under nonce, Gaussian k = 0.03–0.1 and RTN-W8 (A6000 q4, pilot).*
  - Kaplan–Meier P(first divergence ≤ decision 4 / ≤ 12), `out/s02_trajectory_divergence_q4.json`:

    | configuration | ≤ 4 | ≤ 12 |
    |---|---|---|
    | node floor (BF16 vs BF16, node005 vs node003) | 0.50 | 0.95 |
    | nonce n1 | 0.75 | 1.00 |
    | gauss 0.03 s1 / s2 | 0.60 / 0.57 | 1.00 / 1.00 |
    | gauss 0.1 s1 / s2 | 0.75 / 0.66 | 1.00 / 1.00 |
    | RTN W8 n1 / n2 | 0.62 / 0.78 | 1.00 / 1.00 |
    | gauss 0.3 | 0.84–0.87 | 1.00 |
    | gauss 1 / RTN W4 | 0.94–0.97 | 0.95–1.00 |

    From k = 0.03 to k = 1 the Frobenius norm of the weight error grows 33×. The ≤ 12 value is 1.0 at every level.
  - Almost all first divergences are wording (text vs text):
    - k ≤ 0.1, nonce and W8: 47–53 of 51–55 per config;
    - k = 0.3: 46–47 of 52–54;
    - k = 1 and RTN W4: 38–48 of 55–57.
  - The reference margin at the flipped token has median 0.25 nats for the floor, nonce, k ≤ 0.1 and W8
    (`s02`, `ref_margin_at_flip_median`).
- *Two-tier margin structure, the same in 4 models* (`out/s03_margin_predictions.json`):

  | model | text: median decision min-margin | text: tokens < 0.5 per decision | tool: median min-margin | tool: tokens < 0.5 per decision |
  |---|---|---|---|---|
  | q4 | 0.0 | 4.25 | 7.56 | 0.06–0.65 |
  | q8 | 0.25 | 2.67 | 4.25 (6.25 on cal tasks) | 0.10 |
  | q14 (cal tasks) | 0.125 | 3.27 | 6.5 | 0.13 |
  | q30a3 | 0.0 | 5.98 | 6.5 | 0.06 |

- *The margin model predicts which identical-context decisions flip* (`out/s01_token_flip_margin_{q4,q8}.json`).
  The shift distribution is cross-fitted across domains.
  - Decision-level AUC: 0.94–0.97 for q4 gauss ≤ 0.1, nonce and floor; 0.90–0.94 at k = 0.3; 0.86–0.95 at k = 1 and RTN W4; 0.93–0.96 for q8.
  - Per-token hazard is monotone in the BF16 margin. For q4 gauss0.03 s1 (11,438 tokens): 0.32 for [0, 0.25), 0.17 for [0.25, 0.5), 0.043 for [0.5, 1), 0.003 for [1, 2), and 0 for ≥ 2.
  - Identical-context text turns vs tool turns flip at 0.39–0.49 vs 0.014–0.07 (q4, k ≤ 0.1). For q8 at k = 0.03 the figures are 0.28–0.34 vs 0.02.
- *4080, the same phenomenon at W4* (recomputed from analysis files; raw-run check pending).
  - `analysis/strategy_v2_workflow/mechanism/a23.out` Q2/Q3:
    - 1466/1530 (95.8%) (checkpoint, task) pairs diverge in tool behaviour, and 1031 of them first diverge in context at decision 1 (the first agent utterance);
    - text states flip in full-action 0.908 of the time but behaviourally only 0.051; tool states flip 0.165;
    - median t_tool/H is 0.30–0.31 for all 6 calibration arms.
  - `a4.out` (a): the divergence decision is the least-confident decision so far in 0.844 of pairs (null 0.292); mean rank u = 0.924 [0.881, 0.958].
- Checked on: q4 (all of the above), q8 (nonce and k ≤ 0.3, partial), q14 and q30a3 (margins only). Not yet: q32,
  closed-loop divergence for q14/q30a3/q32, GPTQ/AWQ.

**Prediction (A6000 cells).**
- **P1a.** For every model (q4, q8, q14, q30a3, q32), each of the 5 nonce nulls, gauss k = 0.03 (s1, s2), k = 0.1 and
  rtn_w8 (n1, n2) will have KM P(first divergence ≤ decision 12) ≥ 0.85. Their KM curves will lie within ±0.15 of
  each other at d = 4, and ≥ 75% of their first divergences will be text-vs-text with reference flip margin < 0.5.
  **Falsified** if any model has P(≤ 12) < 0.7 at nonce or k = 0.03, or if divergence at d = 4 increases by more than
  0.3 from k = 0.03 to k = 0.1. That would mean divergence is dose-sensitive at small δ.
- **P1b.** On identical contexts, text-turn flip rate / tool-turn flip rate ≥ 5 at every k ≤ 0.3 in every model.
- **P1c (null width is bimodal in D, T1).** For every model, the rerun ("control") divergence of a fixed config
  (a vs b on a reference node, det runs, and the Phase-4 real-kernel reruns) is either ≈ 0 (D ≡ 0,
  bit-deterministic) or saturated (KM ≤ 12 ≥ 0.85, D > 0), and nothing in between. The saturated case happens exactly
  when the identical-context shift is non-zero on ≥ 10% of tokens. Data so far: node004 vs node003 gives 0/20 with
  D ≡ 0; node005 vs node003 gives 20/20 with 59% of tokens shifted (`s04`). **Falsified** by a path with non-zero D
  but KM ≤ 12 < 0.5.
- **P1d (first divergence lands on the lowest-margin decision, T3).** Whatever the family, for configs with
  k ≤ 0.3, the first divergent decision is the lowest-margin decision so far (by BF16 min-margin) in ≥ 60% of tasks.
  The chance level is the 1/(index + 1) average: 0.29 in the 4080 data. The 4080 W4 analogue is 0.844 (`a4.out` (a)).
- Pre-registered cross-model numbers for the first-divergence curve are under I3.

**Scope limit.** Greedy decoding; agents that emit free-text turns into a closed loop. The claim predicts that an
agent restricted to tool-only or constrained outputs would *not* saturate. Under temperature sampling the tie floor
is swamped by sampling noise anyway.

**What is new versus prior work.**

*Known and cited:*
- a single numerical perturbation re-rolls whole generations: Du 2609.26621 (49–100% of prompts, BF16 vs FP16);
  Illusion of Equivalence 2604.15409; Integer Alibi 2608.13756;
- in multi-turn tool use, Patodiya 2609.04748 ("amplification saturates at the coarsest settings", prefix caching
  36% → 75% at 4-bit) says the same in words, and chaining is also described in words;
- Du notes that CoT concentrates margin mass at small values.

*New:*
- (a) The composition law 1 − ∏(1 − p_s) over closed-loop decisions, measured against Kaplan–Meier first-divergence
  curves. No explicit statement of it was found (sweep §Novelty 2).
- (b) One δ axis that puts float noise, nonce, Gaussian k = 0.03–1 and RTN W8/W4/W3 on it, with divergence flat
  across 1.5 decades of weight-error norm.
- (c) The text-turn vs action-turn split of tie density *within* agent turns (≈ 4 near-ties per text turn vs ≈ 0.1
  per tool turn, in 4 models). This is what makes divergence uninformative about damage (→ I2).

*The competing observation and how I1 handles it.* Replay Gap (2608.08239, COLM 2026) finds that the width of the
same-model "control fork" null depends on the serving format: FP8 controls diverge > 90%, AWQ controls are nearly
identical. I1 does not say that re-runs always diverge. It says divergence is set by whether the path's D exceeds the
tie scale. A bit-deterministic path has D = 0 and zero divergence; any path with D above bf16 resolution saturates.
Replay Gap's FP8 vs AWQ contrast and our node005 vs node004 contrast are the two regimes of the same law. They are
not a property of quantization. **Prediction P1c** (survey test T1) states this.

**Questions for survey.**
1. Has anyone shown, for LLM agents or multi-turn dialogue, that trajectory divergence saturates in perturbation
   size (prompt, weight noise or quantization) or is matched by hardware nondeterminism?
2. Is there prior work splitting token margins or logit gaps by *free-text vs tool-call/structured* output and
   relating tie density to run-to-run divergence?
3. Do quantization "flip" papers (Dutta et al. 2407.09141; Singh 2608.15046; Flat Score 2607.27275) measure how flips
   scale with bit-width, and do they report flat flip rates at high bit-widths?
4. Does any work fit a margin-threshold model, P(flip) = P(logit shift > margin), to predict *which* tokens or
   decisions flip under quantization?

---

## I2. Outcome damage has a later threshold set by action-decision margins (P2, sharpened)

**Status:** new.

**Principle.** A perturbation lowers closed-loop task success only once its logit shift reaches the margins of
*action* decisions (which tool, which arguments). Those margins are an order of magnitude larger than the margins
that drive divergence. So there is a "free zone" of perturbation sizes where trajectories are fully re-rolled but
expected success is unchanged. The size of the free zone is predicted by the reference model's action-margin
distribution. Damage is predicted by the flip rate at action decisions, not by divergence or by the mean logit shift.

**Mechanism.** A small margin means the model rates the alternatives as nearly equivalent: paraphrases, or the order
of harmless questions. Flipping such a token re-samples among continuations of similar value, so it adds variance
but no expected loss. A flip at a decision with margin of about 6–7 nats overrides a confident choice. Such a flip
(a different write, wrong arguments, a premature transfer) changes the environment state irreversibly, and that is
where db_match failures come from. The hazard at those margins is P(D < −6), which is ≈ 0 until the spread of D
approaches the action margins.

**Evidence.**
- *Action-decision flips switch on between k = 0.3 and k = 1 (A6000 q4, pilot).* Sources: `s01`, `s02`.
  - Identical-context tool-turn flip rate:

    | configuration | tool-turn flip rate | tool decisions (n) |
    |---|---|---|
    | node floor | 0.015 | |
    | nonce | 0.029 | |
    | k = 0.03 | 0.014–0.045 | |
    | k = 0.1 | 0.018–0.07 | |
    | RTN W8 | 0.03–0.04 | |
    | k = 0.3 | 0.05–0.20 | |
    | k = 1 | 0.21–0.83 | 24 / 12 |
    | RTN W4 | 0.08–0.23 | |
    | RTN W3 | 1.0 | |

  - Per-token hazard in the [4, 8) margin bin is ≤ 0.003 for all k ≤ 0.1 (q4 and q8), 0.09–0.21 for k = 1, and 0.12–0.13 for RTN W4.
  - The median reference margin at the first flipped token rises from 0.25 (k ≤ 0.1) to 0.75–1.0 (k = 0.3), 2.25–2.5 (k = 1 and RTN W4), and 2.75–3.25 (RTN W3).
  - The share of first divergences that are action-type (args or behaviour) grows from 4–11% (k ≤ 0.1, nonce, W8) to 13–31% (k = 1, RTN W4).
- *Outcome pilot (A6000 q4 airline, 27 tasks, completed domains only; `out/s05_pilot_success_q4_airline.json`).*
  - The free-zone runs are bf16, nonce, gauss 0.03 × 2, gauss 0.3 × 2 and RTN W8 × 2. Their db_match ranges 0.296–0.556 (mean 0.440, SD 0.078).
  - RTN W4 (0.370, 0.407) is inside that range. No damage is visible at W4 yet, which is consistent with W4 sitting at the onset of action flips.
  - The task-level test (outcome change split by first-divergence type) shows **no signal yet**: wording −0.025 (n = 192), action +0.003 (n = 36). It is underpowered, and it is referenced to a free-zone mean that includes the same runs. This part is untested.
- *4080, recomputed from analysis files; raw-run check pending.*
  - Sources: `mechanism/churn.out`, RESULTS.md §1.
  - At W4, 18 GPTQ checkpoints diverge in 95.8% of pairs, yet the net success loss is only 0.044 pooled
    (task-bootstrap CI [−0.038, 0.126]), against a gross churn of 0.261: 234/576 BF16 successes lost and 166/954
    failures gained.
  - Variance decomposition of the 85 × 18 success matrix: task 0.502, checkpoint 0.008, residual 0.490.
  - Cost depends on what flips (`a567.out` Q7, recovery of BF16-solved tasks after a divergence):
    - BF16 text → Q read: 0.677;
    - BF16 text → Q ended: 1.0;
    - BF16 read → Q write: 0.214;
    - BF16 write → Q different write: 0.346.
  - Failures are write-dominated (`a567.out` Q5: missing write 60, wrong-args write 64 incl. +extra, extra write only 42, of 234).
  - Open-loop mean fidelity does not track closed-loop success: Spearman |ρ| ≤ 0.13 over 18 checkpoints, with the sign depending on pooling (RESULTS.md §3). CLOQ-Novel has the best NLL and the worst long-task success (FINDINGS_V1 §4, §7).
- Checked on: q4 (token level, and a 27-task outcome pilot), 4080 q4 at W4. Not yet: any outcome data for q8/q14/q30a3/q32;
  GPTQ/AWQ; k = 1 and k = 3 outcomes.

**Prediction (A6000 cells).**
- **P2a (two thresholds).** For every model, pooled db_match of gauss k ∈ {0.03, 0.1, 0.3} (both seeds) and
  rtn_w8 (both nonces) will lie inside the range of that model's 5 nonce nulls, widened by one Bernoulli SE.
  gauss k = 3 and gptq_w3/rtn_w3 will lie below the null minimum. The first k at which the mean falls below the null
  range will be 1 or 3, never ≤ 0.3. In every model, divergence saturates (P1a) at least a factor of 10 in k before
  damage starts. **Falsified** if any model shows k = 0.1 or rtn_w8 below its null range in both domains.
- **P2b (the right predictor).** Across all configs of a model (≥ 20 cells), Δsuccess versus the null mean will
  correlate with the identical-context *tool-turn* flip rate (`s01`, `by_bf16_kind.tool.observed_div`) at
  |Spearman| ≥ 0.7. It will correlate more weakly with trajectory divergence at d = 4 and with the median |d|.
  **Falsified** if either divergence or median |d| predicts Δsuccess better.
- **P2c (cost of a flip).** Pool (config, task) pairs across models. Tasks whose first divergence is an action flip
  with reference margin ≥ 2 will have a lower success rate relative to the task's null rate than tasks whose first
  divergence is a text flip with margin < 0.5. Predicted difference ≤ −0.10 with a task-cluster CI excluding 0.
- **P2e (Flat Score's amplified failures, test T3/T6).** The per-run rate of tool errors, invalid tool names and
  repeated tool calls (`metrics.json`: `tool_error_rate`, `repeated_tool_call_rate`) is inside the 5-nonce null range
  for every k ≤ 0.3 and rtn_w8 cell. It rises above the null only in cells whose identical-context tool-turn flip rate
  is ≥ 0.15. awq_w4 and gptq_w4 fall on the Gaussian ladder at matched |d|.
- **P2d (cross-model).** A model's damage onset in k is ordered by its median tool-decision min-margin. Predicted
  order of the k = 1 tool-turn flip rate: q8 (margin 4.25) > q14 ≈ q30a3 (6.5) > q4 (7.6). The same order holds for
  the k = 1 success drop relative to the null.

**Scope limit.** Environments where success depends on a small number of state-changing actions (db end-state).
Endpoints that grade wording (NL-assertion judges) would put the damage threshold much closer to the divergence
threshold. The claim predicts that, and it is testable on the `communicate` / `tau2_reward` endpoint.

**What is new.**

*Taken:*
- "Aggregate hides churn": Dutta 2407.09141; Singh 2608.15046, churn ≈ 5.4× net delta;
- "flat score, amplified failures": Flat Score 2607.27275;
- "open-loop fidelity doesn't predict closed-loop": VLA and driving; Replay Gap for agents.

*New:*
- a measured dose-response along one δ axis with *two* thresholds, since all prior work observes divergence ≫
  damage at a single perturbation size;
- the mechanism that says which flips cost success (the margin of the flipped decision, from the action-turn
  margins);
- the prediction that the action-turn flip rate, not mean NLL/KL or divergence, is the fidelity metric that carries
  over.

*Against Flat Score specifically.* Flat Score reports a flat aggregate but 2.5× tool-name hallucination at INT4, and
explains it verbally as "noise flips thin-margin argmax decisions". I2 turns that into a test (P2e): amplified tool
failures should appear exactly where the measured action-turn flip rate rises, at the same |d| for Gaussian noise as
for AWQ. If AWQ-W4's tool-failure rate is inside the null at its |d|, part of Flat Score's amplification is re-roll.
If it sits above the Gaussian ladder, it is quantization-specific (→ I3 falsified).

**Questions for survey.**
1. Has anyone shown a "free zone" for LLM agents, where perturbations fully change trajectories but not expected task
   success, or a separation between behavioural-divergence and damage thresholds?
2. Is there work linking the *confidence or margin of a flipped decision* to its downstream cost in multi-step or
   agent tasks (for example "high-confidence errors are costly" in sequential decision-making, or DAgger-style
   compounding analyses with confidence)?
3. Do Flat Score (2607.27275) or ACBench (2505.19433) break failures down by tool/write vs text decisions, or report
   the tool-call flip rate as a predictor of agent success under quantization?
4. Does any quantization paper propose a decision-level (action-token) fidelity metric in place of perplexity/KL for
   agents?

---

## I3. Perturbation equivalence: the logit-shift distribution is a sufficient statistic, and it transfers across models (P3, sharpened)

**Status:** new.

**Principle.** Two weight perturbations with the same per-token logit-shift distribution produce the same flip
hazards, divergence and damage in a closed-loop agent, whatever their structure (random Gaussian or
quantization). When perturbations are scaled to a fixed fraction of each layer's quantization-error norm, that shift
distribution is roughly model-independent. A model's closed-loop sensitivity curve can therefore be predicted from
its reference margins alone.

**Mechanism.** The first-order margin model depends on the perturbation only through D, the distribution of margin
shifts. Quantization error that is spread across many weights enters the logits as a sum of many small terms, which
behaves like isotropic noise of the same norm (a CLT argument). In that case RTN at bits b ≈ Gaussian at
k = ‖err_b‖ / ‖err_W4‖. Model size enters only through margins and not through D, as long as noise is scaled
per layer relative to the quantization error of that layer.

**Evidence (A6000, pilot).**
- *Structured vs random at equal norm* (`s01`):
  - RTN W4 (paired with nonce-matched BF16, same prompt): |d| median 2.0 / 2.0, p90 5.16 / 5.25. Gauss k = 1: median 1.875 / 2.06, p90 6.25 / 5.75.
  - Identical-context text-turn flip rate: 0.92–0.96 (RTN W4) vs 0.94–1.0 (k = 1).
  - KM ≤ 0: 0.72–0.79 (RTN W4) vs 0.76–0.93 (k = 1). Median flip margin: 2.4–2.5 vs 2.25–2.5.
  - RTN W8: |d| 0.125–0.25, sitting between k = 0.03 and k = 0.1. The expected position is k ≈ 1/16 ≈ 0.06.
- *D(k) is model-independent (q4 vs q8)* (`s03`, `shift_by_k`):
  - median |d| is 0.125 vs 0.125, 0.25 vs 0.25, 0.5 vs 0.5 and 2.0 vs 1.63 at k = 0.03 / 0.1 / 0.3 / 1;
  - p90 is 0.375 vs 0.375, 0.625 vs 0.75, 1.5 vs 1.625 and 6.0 vs 5.0.
  - D grows roughly linearly in k from 0.1 to 1: 0.25 → 0.5 → 2.0.
- *Margin-only prediction is roughly calibrated on q4*: `s03`, using q4 BF16 margins and q4 D(k), compared with the observed `s02` KM.

  | k | predicted P(div ≤ 0 / ≤ 4 / ≤ 8) | observed |
  |---|---|---|
  | 0.03 | 0.08 / 0.46 / 0.76 | 0.10–0.12 / 0.57–0.60 / 0.90 |
  | 0.3 | 0.37 / 0.83 / 0.98 | 0.52–0.53 / 0.84–0.87 / 1.0 |

  The model under-predicts by 0.1–0.15 at small k. This is a known bias: D is estimated only on tokens that did not
  flip, which truncates its tail.
- Not yet: GPTQ, AWQ, q14/q30a3/q32 shifts, and any outcome comparison at matched |d|.
- 4080 relevance (recomputed from analysis files; raw-run check pending):
  - 6 calibration arms × 3 draws of GPTQ W4 are exchangeable in closed loop (arm permutation p = 0.683 pooled / 0.368 long; draw p = 0.881 / 0.744; RESULTS.md §1).
  - Open-loop flips are shared across arms: φ within-arm 0.548 vs cross-arm 0.538 (STRATEGY_v2 A7).
  - This is what a D-only account predicts when the arms have near-equal D. Note that the 5 trajectory arms are also indistinguishable in open-loop NLL (F = 0.59, p = 0.68), so this is consistency, not a test.

**Prediction (A6000 cells).**
- **P3a (D transfers).** For q14, q30a3 and q32, median |d| at k = 0.03 / 0.1 / 0.3 / 1 will be within a factor 1.5 of
  q4's 0.125 / 0.25 / 0.5 / 2.0. **Falsified** if any model is off by > 2× at k ≥ 0.1 (below that, bf16 resolution
  limits the test).
- **P3b (sufficiency).** Place gptq_w4 (d1, d2), awq_w4, gptq_w3 and rtn_w8/w4/w3 on the Gaussian ladder by their
  measured median |d| and tool-turn flip rate. Their db_match will fall within the Bernoulli-SE band of the Gaussian
  ladder interpolated at the same |d|, in every model. Expected placement: GPTQ/AWQ W4 between k = 0.3 and k = 1
  (smaller |d| than RTN W4), GPTQ W3 near k = 1–3. **Falsified** if any quantizer is more than 2 SE below the
  Gaussian curve at matched |d|. That would be quantization-specific (structured or outlier) damage, which is itself
  publishable, and the fallback in COLING_PLAN §6.
- **P3c (margin-only prediction, pre-registered numbers).** Computed from each model's own BF16 margins and q4's
  D(k), `out/s03_margin_predictions.json`. Tolerance ±0.15 at d = 0 / 4 / 8, after adding the +0.10 bias correction
  measured on q4. Predicted P(first divergence ≤ 0 / ≤ 4 / ≤ 8):

  | model (margin source) | k = 0.03 | k = 0.3 | k = 1 |
  |---|---|---|---|
  | q8 (bf16, eval) | 0.03 / 0.38 / 0.58 | 0.11 / 0.82 / 0.92 | 0.46 / 0.94 / 0.96 |
  | q14 (bf16_cal) | 0.04 / 0.30 / 0.67 | 0.25 / 0.77 / 0.99 | 0.49 / 0.94 / 1.00 |
  | q30a3 (det) | 0.13 / 0.29 / 0.83 | 0.35 / 0.61 / 1.00 | 0.66 / 0.93 / 1.00 |

  Predicted identical-context tool-turn flip rate at k = 1: q8 0.27–0.33, q14 0.26, q30a3 0.23, q4 0.18–0.21.
  q32 is to be filled in when `q32_bf16_cal` exists.

**Scope limit.** Weight perturbations that are dense and small per weight. Sparse, outlier-concentrated
perturbations (e.g. breaking a massive-activation channel), or activation quantization, may violate the CLT argument.
P3b is the test. Prompt perturbations (nonce) are handled by measuring their D directly: q4 nonce has |d| median
0.25, the same as k = 0.1.

**What is new.**

*Known:*
- QuantNoise and "quantization as noise" (training-time);
- Du 2609.26621: flip risk "depends primarily on the margin distribution", stated in words for one perturbation;
- Fu 2601.06118: impact estimable from one run's token probabilities (abstract only);
- Fang 2506.22776: quantized models withstand Gaussian weight noise differently. That affects the Gaussian ladder, so
  we must check that the ladder is applied to BF16 weights only, which is how it is used here.

*New:*
- (a) D as a *sufficient statistic* across perturbation families for closed-loop flip hazard, divergence *and*
  outcome;
- (b) D(k) being model-independent under per-layer norm matching;
- (c) margin-only, cross-model predictions of whole first-divergence curves, pre-registered below.

No direct precedent for (c) was found (sweep §Novelty 4).

**Questions for survey.**
1. Has anyone shown that RTN/GPTQ weight error and norm-matched Gaussian weight noise produce the same output-logit
   perturbation distribution, or the same downstream behaviour, in LLMs?
2. Is there a known scaling of logit shift with a relative weight-noise level that is independent of model size?
3. Does any work predict a model's robustness to quantization or noise from its unperturbed confidence-margin
   distribution, across models?
4. Are there "iso-KL" or "iso-logit-shift" comparisons of quantizers in agent or multi-turn settings?

---

## I4. The reference run is one draw from its own perturbation distribution; equivalence means exchangeability with that distribution

**Status:** new. It merges the old C1/C4/C5/C6 variance claims into one principle.

**Principle.** Under greedy, deterministic serving, re-running a closed-loop agent returns the same score, but that
score is a single draw from the distribution induced by perturbations at or below the tie-breaking floor (prompt
nonces, cross-hardware float differences). The unit of comparison for a compressed model is therefore the reference
model's perturbation-null distribution, not its canonical run. A compressed model is "equivalent" exactly when its
per-task outcomes are exchangeable with null draws.

**Mechanism.** This follows from I1. Every run in the free zone re-rolls the trajectory, so each task's outcome
under the reference is Bernoulli(p_t), with p_t spread widely over tasks. The between-run SD of pooled success is
√(mean_t p_t(1−p_t) / n). That is non-zero even though a fixed server reproduces the canonical run bit for bit.
Comparing against the canonical run confounds that draw's luck with damage.

**Evidence.**
- *The canonical score depends on the machine (A6000 q4, `s04`).* BF16 on node005 vs node003: 20/20 tasks diverge.
  The divergence curve (KM ≤ 4: 0.50, ≤ 12: 0.95) matches nonce and k = 0.03. Only float differences separate the two
  runs (flip margins median 0.125).
- *The free-zone spread matches the Bernoulli model (pilot, q4 airline, 27 tasks, `s05`).* 8 free-zone runs (bf16,
  nonce, gauss 0.03 × 2, gauss 0.3 × 2, RTN W8 × 2) give db_match 0.296–0.556, SD 0.078. The Bernoulli prediction
  from per-task p_t is 0.058. The canonical BF16 (0.556) is the *maximum* of the 8.
- *4080, recomputed from analysis files; raw-run check pending.*
  - Checkpoint share of the task × run variance is 0.008, against a residual of 0.490 (`mechanism/churn.out`).
  - Overdispersion: var(#checkpoints solving a task) is 28.9 against a binomial 4.3 (`a567.out` Q6). Outcomes are task-determined plus Bernoulli churn.
  - The v0 "significant" FP-Traj − Static = +0.121 (exact one-sided McNemar p = 0.0195) reverses on re-draw (RESULTS.md §2; v1 −0.035, FINDINGS_V1 §5).
  - The canonical BF16 long-task success (0.297) sits above all but a few of the 18 W4 checkpoints (0.054–0.270; RESULTS.md §1). On long tasks, BF16's outcome vector correlates with the ensemble mean less than any quantized member (0.286 vs 0.316–0.689; `churn.out`). Without a BF16 null this was uninterpretable, and it is the direct test of this insight.

**Prediction (A6000 cells).**
- **P4a.** For each model, the pooled-success SD across the 5 nonce nulls will be within [0.5, 2] × the Bernoulli
  prediction from p_t. p_t is estimated from the nulls plus the other free-zone cells (k ≤ 0.1, rtn_w8).
- **P4b (exchangeability).** In each model's task × run success matrix, free-zone cells (nonce ×5, gauss k ≤ 0.1,
  rtn_w8) will be exchangeable with the nulls: a permutation test of the mean pairwise task-level φ, null–null vs
  null–config, gives p > 0.05. Damage cells (gauss 3, W3) form a separate common-mode cluster (higher mutual φ than
  with the nulls). **Falsified** if the free-zone cells are systematically separated from the nulls.
- **P4c (canonical run is not special).** Across 5 models × 2 domains, the rank of canonical bf16 among {bf16 + 5
  nonce nulls} will be uniform. Expected mean rank 3.5; a sign test on "bf16 above the null median" gives p > 0.1.
  **If instead canonical bf16 tops the nulls in most of the 10 cells**, there is a systematic
  canonical-prompt advantage. Any perturbation, even a nonce, would then be net-negative. That would *refute* the
  "free zone" of I2 as stated, and it would need to be reframed as "damage starts at the tie floor".
- **P4d (the practical consequence).** The naive test (each free-zone config vs canonical bf16, paired McNemar per
  task) will give at least one nominal p < 0.05 somewhere in the 5-model free zone. A task-level test against the
  null distribution will give none.

- **P4e (re-roll vs damage by nestedness, T5/T6).** For free-zone cells, the pass set is *not* nested in the null
  union. Gains (fail → pass relative to the canonical run) happen at the null's own gain rate. 4080 W4 analogue:
  166/954 = 0.174 of BF16 failures gained (`churn.out`), so there is no nesting. For damage cells (gauss 3, W3), the
  pass set is nested: the gain rate falls below the null's 5th percentile while the loss rate rises. This gives a
  two-number diagnostic (gain rate, loss rate), which a mean difference cannot separate.

**Scope limit.** Deterministic greedy evaluation with a small task count (≈ 85). With many sampled trials per task,
the canonical-run issue disappears, but the exchangeability test still applies.

**What is new.**

*Known:*
- evaluation variance and pass^k (τ-bench; On Randomness in Agentic Evals 2602.07150: pass@1 moves 2.2–6.0 pp at T = 0);
- noise floors (Noise Floor Audit 2608.22331, single-turn BFCL);
- TOST at a declared margin for compressed LMs (Singh 2608.15046, static);
- a neutral-perturbation (paraphrase) null for judging counterfactual flips (Compared to What? 2605.01048, the
  closest methodological precedent, single-turn QA);
- same-model control-fork nulls in agents (Replay Gap 2608.08239, model swaps, not compression).

*New:*
- (a) The null is built from *deliberate* sub-threshold perturbations (nonce) rather than reruns. By I1/P1c, rerun
  nulls are 0 or saturated depending on serving numerics (Replay Gap's FP8 vs AWQ; our node005), so they are not a
  valid unit.
- (b) Equivalence is defined as task-level exchangeability with that null, on a closed-loop, state-mutating
  benchmark.
- (c) Nestedness of pass sets as a discriminator between re-roll and damage (P4e).

**Questions for survey.**
1. Has any agent-evaluation paper shown that a deterministic (greedy, batch-invariant) reference score changes across
   hardware, or that prompt nonces re-roll agent outcomes at the same rate as hardware noise?
2. Does Noise Floor Audit (2608.22331) or Singh (2608.15046) define equivalence as exchangeability with a
   perturbation null (not a margin on the mean difference)?
3. Has anyone reported that the canonical/unperturbed prompt systematically outperforms semantically-null prompt
   variants (a "canonical advantage") on agent benchmarks? This bears on P4c.
4. Is there prior use of task × run φ / clustering to separate systematic damage from re-roll in compressed-model
   evaluation?

---

## Rejected or merged this iteration

- *"Horizon amplification" (quantization gap concentrated in long tasks):* dropped as a stand-alone insight. It is
  obvious-sounding ("longer tasks are harder") and marginal (STRATEGY_v2 §2.2: CI [−0.039, 0.315]). In I1/I2 the
  horizon effect follows from 1 − ∏(1 − p_s). It is kept only as a corollary to test: damage should scale with the
  *number of action decisions*, not the number of turns (`churn3.out`: ≥ 2 required writes gap 0.121 vs ≤ 1 write
  0.005).
- *Per-step margin → flip (s01 AUC):* inherited (Du 2609.26621 Eq. 14; Integer Alibi; MarginGate). Reported only
  as a replication that supports I1–I3.
- *Token inflation (T2) and false success (T4):* not adopted as insights this round. They are plausible secondary
  damage endpoints. If needed, the verifier can check whether they move before db_match does (a P2 corollary).
- *"Open-loop fidelity doesn't predict closed-loop success":* occupied in general (VLA and driving). Merged into I2 as
  the sharper claim that the tool-turn flip rate predicts damage and mean NLL does not.
- *"Calibration data doesn't matter at W4":* a single-model observation, and occupied (Damage Predicts Recovery).
  Subsumed by I3: arms with equal D are equivalent.
- *Coverage/occupancy repair (CLOQ):* a killed method claim; not an insight.
- *Loop attribution (simulator vs agent):* an engineering or measurement fact.

## Most important next experiment

For I1–I3, the leading chain: **finish q4 and q8 in both domains for the 5 nonce nulls plus gauss k = 1 and k = 3,
then run P2a/P2b.**
- If success at k ≤ 0.3 stays inside the null range while the tool-turn flip rate stays below 0.1, and success drops
  only where the tool-turn flip rate exceeds about 0.2, the two-threshold account holds on two models.
- If k = 0.1 or rtn_w8 already falls below the null range, or if canonical bf16 tops the nulls (P4c), the free zone
  is dead.
- A prerequisite for all cells: re-check node005 against a reference node (see the design issue above) before
  pooling runs across nodes.
