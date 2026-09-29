**TL;DR**
- Four insights, all extending the published per-step margin→flip model (Du, 2609.26621):
  - **I1** divergence is set by tie density, and it saturates even under a kernel-autotune numerics change;
  - **I2** there are two thresholds, with a free zone between them;
  - **I3** the logit-shift distribution D is sufficient and transfers across models;
  - **I4** the reference run is one draw, and equivalence means exchangeability with a weight-only null.
- On the legacy numerics flavour, divergence is flat and D transfers: GPTQ and AWQ W4 sit where I3 predicted on q8. I2's outcome threshold and its task-level cost claim (P2c) have **no support yet**.
- Everything decisive now runs on the clean `a6k2_*` cells. Next steps, ranked: E4 → a6k2 canary (E2) → E5 → E3 → E7 (§Experiments).

# Insight candidates: iteration 1, round 2 (revised after discussion)

Owner: cloq-insight. Framing: `docs/COLING_PLAN.md` §2.

Discussion: `docs/insights/iter_1_discussion.md`, sections "Survey (round 1)", "Experiment (round 1)" and "Insight (round 2)".
Literature: `docs/insights/SURVEY.md`. Experiment plan: `docs/insights/EXPERIMENTS.md`.

No ledger exists yet, so every insight is **new**, with stable ids I1–I4.

## Data status (read first)

- **Legacy A6000 runs (`runs/a6000_*`)** were served with an unpinned Inductor reduction autotune, so every server drew a
  numerics "flavour" when it compiled.
  - evidence: `iter_1_discussion.md#experiment-round-1` D1–D5; `analysis/determinism/probe_q4.json`; `analysis/insights/iter_1/exp/out/bestconfig_*.tsv`.
  - Only q4 bf16 and its nonce nulls are verified to share one flavour.
    evidence: `analysis/insights/iter_1/exp/out/server_flavour.json` ← `exp/e_server_flavour.py`.
  - Every other legacy cell is "config + an unknown flavour". All legacy numbers below are labelled **[legacy]**.
  - The clean rerun, `runs/a6k2_*` under `TORCHINDUCTOR_DETERMINISTIC=1`, started 2026-09-28 19:05. It had **no runs on disk** at snapshot `analysis/insights/iter_1/out/s00_snapshot.json`
    (2026-09-29T02:06Z, 57 legacy run dirs) ← `s00_snapshot.py`.
- The live-snapshot outputs are in `analysis/insights/iter_1/out/` and are written by `run_all.sh`.
  - `s02` was fixed per E4a: a raw-token difference on an identical context is now a divergence event of type `format`, not a censoring. The counts of "context mismatch without agent flip" are now 0 everywhere, which confirms D6 (agent-side, not the simulator).
  - evidence: `out/s02_trajectory_divergence_{q4,q8}.json` ← `s02_trajectory_divergence.py`.
- **4080 numbers** are recomputed from analysis files. The raw-run check is pending (release `data-4080`).

## What we inherit, and the closest competitor

- **Inherited.** The per-step margin→flip model P(flip at t) ≲ P(Δ_t < σ).
  - Du et al. 2026, TMLR, Eq. 14: https://arxiv.org/abs/2609.26621.
  - Validated by Integer Alibi (AUC 0.942, Brier 0.035; https://arxiv.org/abs/2608.13756) and MarginGate (https://arxiv.org/abs/2605.30218).
  - Our `s01` decision-level AUCs are a closed-loop, multi-family *replication* of it, not a contribution.
    Values: 0.79–0.97 across all cells. evidence: `out/s01_token_flip_margin_{q4,q8}.json` ← `s01_token_flip_margin.py`.
- **Closest competitor.** Flat Score, https://arxiv.org/abs/2607.27275.
  - Same τ²-bench; AWQ-INT4/FP8; a verbal margin account; no logprobs; no divergence measurement; a TOST margin taken from one rerun.
  - evidence: `SURVEY.md#t1-compressed-llms-as-agents-tool-use-multi-turn`.

---

## I1. Closed-loop divergence is set by the agent's tie density, not by the perturbation (extends Du Eq. 14; P1)

**Status:** new (sharpened in round 2).

**Principle.** In a greedy closed-loop LLM agent, any perturbation large enough to break near-ties re-rolls almost every
trajectory within about ten decisions. This includes a change of floating-point reduction order in a single fused kernel.
Free-text turns carry several near-tied tokens each, and action turns carry almost none. Trajectory divergence therefore
measures the model's tie density, not the size or type of the perturbation, and cannot rank perturbations.

**Mechanism.**
- Per step, this is inherited (Du Eq. 14): a token flips when the perturbation's logit shift exceeds its top-1/top-2 margin.
- Our additions:
  - (i) The composition over closed-loop decisions, P(diverged by t) = 1 − ∏_{s≤t}(1 − p_s), with p_s = 1 − ∏_tokens P(D ≥ −m).
  - (ii) The two-tier margin structure. Text turns have median min-margin ≈ 0 and ≈ 3–6 tokens below 0.5 nats. Tool turns
    have median min-margin ≈ 4–7.5 nats. Once D exceeds the bf16 logprob resolution (0.125), text turns flip at ≈ 0.4 per
    decision, and the product drives P(diverged by t) to 1.

**Evidence** (all A6000 numbers are [legacy]).
- *A real-world numerics perturbation saturates divergence.* The same weights and prompt are served under two Inductor
  reduction configs (R0_BLOCK 2048 vs 4096):
  - identical-context shift median |d| = 0.125, non-zero on 59% of tokens;
  - KM P(first divergence ≤ 4 / ≤ 12) = 0.50 / 0.95 over 20 tasks;
  - 4/20 task outcomes differ (db_match 0.45 vs 0.55, McNemar p = 0.63).
  - The same comparison for q30a3, whose autotune drew the same R0_BLOCK on both nodes, is fully identical.
  - evidence: `out/s04_node_floor.json` ← `s04_node_floor.py`; `out/s07_flavour_outcome.json` ← `s07_flavour_outcome.py`;
    mechanism `iter_1_discussion.md#experiment-round-1` D5.
- *Divergence is flat across 1.5 decades of weight-error norm (q4).* KM P(first div ≤ 4 / ≤ 12), after the E4a fix.
  evidence: `out/s02_trajectory_divergence_q4.json` ← `s02_trajectory_divergence.py`.

  | configuration | ≤ 4 | ≤ 12 |
  |---|---|---|
  | kernel flavour | 0.50 | 0.95 |
  | nonce n1 / n2 / n3 | 0.73 / 0.80 / 0.75 | 0.98–0.99 |
  | gauss 0.03 ×2 | 0.61 / 0.65 | 1.0 |
  | gauss 0.1 ×2 | 0.75 / 0.71 | 0.98 / 1.0 |
  | RTN W8 ×2 | 0.62 / 0.60 | 0.97 |
  | gauss 0.3 ×2 | 0.92 / 0.88 | 1.0 |
  | gauss 1 ×2 | 1.0 / 0.99 | 1.0 |
  | RTN W4 ×2 | 0.99 / 0.98 | 1.0 |

  - First divergences at k ≤ 0.1, nonce and W8 are mostly wording or format: 72–82 of 77–85 per config.
  - The reference margin at the flipped token has median 0.25.
- *Same pattern on q8, with somewhat lower saturation (fewer text ties).* KM ≤ 4 / ≤ 12.
  evidence: `out/s02_trajectory_divergence_q8.json`.

  | configuration | ≤ 4 | ≤ 12 |
  |---|---|---|
  | gauss 0.03 | 0.44–0.47 | 0.84–0.93 |
  | gauss 0.1 | 0.62–0.67 | 0.94–0.98 |
  | RTN W8 | 0.51–0.52 | 0.88–0.92 |
  | nonce | 0.67–0.68 | 0.97 |
  | gauss 0.3 | 0.80–0.87 | 1.0 |
  | GPTQ W4 | 0.93–0.98 | 1.0 |
  | AWQ W4 | 1.0 | 1.0 |
  | RTN W4 | 0.98–0.99 | 1.0 |

- *Two-tier margins in 4 models.* evidence: `out/s03_margin_predictions.json` ← `s03_margin_predictions.py`, `models.*.margins`.
  - Text-turn median min-margin: 0.0 (q4, q30a3), 0.125–0.25 (q8, q14). Text-turn tokens < 0.5 per decision: 2.7–6.0.
  - Tool-turn median min-margin: 4.25–7.75. Tool-turn tokens < 0.5 per decision: 0.06–0.65.
- *Identical-context flip rates (q4).* Text turns 0.38–0.53 vs tool turns 0.02–0.05 at k ≤ 0.1, nonce and W8.
  evidence: `out/s01_token_flip_margin_q4.json` `by_bf16_kind`.
- *4080 W4 analogue* (recomputed from analysis files; raw-run check pending):
  - 95.8% of (checkpoint, task) pairs diverge;
  - text states flip in full-action 0.908 but behaviourally 0.051;
  - the divergence step is the least-confident step so far in 0.844 of pairs (null 0.292).
  - evidence: `analysis/strategy_v2_workflow/mechanism/a23.out` (Q2, Q3), `a4.out` (a).

**Predictions** (score only on `a6k2_*` cells unless stated).
- **P1a (flatness).** For each of q4, q8, q14, q30a3, q32, KM P(≤ 12) ≥ 0.85 for nonce ×5, gauss 0.03 ×2, gauss 0.1 ×2 and rtn_w8 ×2.
  - A task-bootstrap CI (n = 85) is added in E4.
  - KM P(≤ 4) rises by less than 0.3 from k = 0.03 to k = 0.1.
  - **Falsified** if any model has P(≤ 12) < 0.7 at nonce or k = 0.03, or a rise > 0.3.
  - Legacy q8 is borderline: k = 0.03 gives ≤ 12 of 0.84, and the ≤ 4 rise is 0.18–0.2. It is the model to watch.
- **P1b.** On identical contexts, text-turn flip rate / tool-turn flip rate ≥ 5 at every k ≤ 0.3 in every model.
- **P1c (null width is bimodal in D).** Under the a6k2 fix, cross-node BF16 det pairs must have D ≡ 0 and no divergence.
  - Legacy-vs-a6k2 BF16 pairs (the E5 flavour null) must saturate: KM ≤ 12 ≥ 0.85 whenever D ≠ 0 on ≥ 10% of tokens.
  - This extends to real-kernel paths: E7 runs det pairs for q8 awq_w4/gptq_w4 on Marlin kernels.
  - **Falsified** by any path with D ≠ 0 on ≥ 10% of tokens but KM ≤ 12 < 0.5.
- **P1d.** At k ≤ 0.3, the first free-running divergence lands on the lowest-margin decision so far in ≥ 60% of tasks.
  - Chance on the 4080 data is 0.29 (`a4.out`).
  - Caveat (Integer Alibi): the first teacher-forced flip is not the first free-running divergence. We score the free-running one.

**Scope.** Greedy decoding, and agents that emit free text into a closed loop. The claim predicts that tool-only or constrained-output agents do *not*
saturate. Under sampling, sampling noise dominates.

**What is new.**
- The composition law against KM curves.
- One δ axis running from a kernel reduction-order change through nonce, Gaussian noise and RTN W8/W4/W3 to GPTQ/AWQ, with divergence flat across it.
- The text-vs-action tie structure. The survey calls this (b); the two-tier split is (a).
  evidence: `SURVEY.md#i1-divergence-set-by-tie-density`.
- Nearest prior work: Patodiya (saturation stated in words; https://arxiv.org/abs/2609.04748) and Replay Gap (FP8 vs AWQ control forks; https://arxiv.org/abs/2608.08239).
  Our reading of Replay Gap is that its FP8 vs AWQ contrast is the D > 0 vs D ≡ 0 case of P1c, not a property of quantization.

**Questions for survey.**
- Has anyone measured divergence from a compiler/autotune-level numerics change (not batch or kernel swap) in multi-turn agents?
- AgentDiff (https://arxiv.org/abs/2605.25981) full text: first-divergence step statistics, for P1d.

---

## I2. Damage has a later threshold, set by action-decision margins (P2)

**Status:** new (weakened in round 2: P2c demoted, P2a restated).

**Principle.** A perturbation lowers closed-loop task success only once its logit shift reaches the margins of action
decisions. Those margins are about an order of magnitude above the tie scale that drives divergence. Between the two
thresholds lies a free zone: trajectories are fully re-rolled, but expected success and process-error rates stay at null
level. The flip rate at action turns, not divergence and not mean NLL, is what tracks damage.

**Mechanism.** A near-tie is the model saying the alternatives are equivalent (a paraphrase, or a harmless ordering), so
flipping it re-samples among continuations of similar value. Action turns (tool name, arguments, writes) have margins of
4–8 nats. Their hazard P(D < −m) stays ≈ 0 until the spread of D approaches those margins. When they flip, the result is
irreversible state change, which is where db_match failures come from (4080: `a567.out` Q5).

**Evidence.**
- *Action-turn flips switch on between k = 0.3 and k = 1* [legacy]. Identical-context tool-turn flip rates:

  | model | configuration | tool-turn flip rate |
  |---|---|---|
  | q4 | k ≤ 0.1, nonce, W8 | 0.02–0.05 |
  | q4 | k = 0.3 | 0.08–0.13 |
  | q4 | RTN W4 | 0.19–0.20 |
  | q4 | k = 1 | 0.26–0.85 (n = 27 / 13) |
  | q4 | RTN W3 | 1.0 |
  | q8 | k ≤ 0.1, nonce, W8 | 0.01–0.07 |
  | q8 | k = 0.3 | 0.06–0.18 |
  | q8 | GPTQ W4 | 0.23–0.30 |
  | q8 | k = 1 | 0.35–0.41 |
  | q8 | AWQ W4 | 0.38–0.41 |
  | q8 | RTN W4 | 0.39–0.44 |
  | q8 | RTN W3 | 0.76–0.82 |

  evidence: `out/s01_token_flip_margin_{q4,q8}.json` `by_bf16_kind.tool.observed_div`.
- *Outcome pilot, q4, revised P2a test* [legacy; nulls = canonical bf16 + completed nonce nulls].
  - The statistic is a task-cluster bootstrap Δ against the null mean.
  - Retail (58 tasks, 3 nulls):
    - every cell's 95% CI contains 0;
    - k ≤ 0.1 ranges −0.017 to +0.069;
    - k = 1 gives −0.069 / −0.034;
    - RTN W4 gives 0.000 / 0.000.
  - Airline (27 tasks, 2 nulls):
    - k = 0.3 s1 gives −0.167 [−0.315, −0.019] while s2 gives −0.019;
    - k = 1 gives −0.093 / −0.130 (the upper bound of s2 is 0.000);
    - RTN W4 gives −0.093 / −0.056.
  - **No damage threshold is established yet.** The pilot has 1–3 nulls and one model.
  - evidence: `out/s06_pilot_delta_q4_{retail,airline}.json` ← `s06_pilot_delta.py`.
- *Process channels move first, at k = 1* [legacy, q4]. The survey's P2e and T2 point in this direction.

  | q4 retail | k = 1 | nulls |
  |---|---|---|
  | mean decisions per episode | 15.1 / 16.9 | 12.0–12.3 |
  | premature rate | 0.034 / 0.069 | 0 |
  | repeated tool calls | up to 0.236 | 0.04–0.07 |

  - RTN W4 and every k ≤ 0.3 cell stay at null level: decisions 11.1–12.9, premature 0.
  - A strict error budget (≤ 2 tool errors) changes Δ by at most 0.017.
  - evidence: `out/s06_pilot_delta_q4_{retail,airline}.json`.
- *The task-level cost of a flip (old P2c) is not supported.*
  - Airline, mean change vs the free-zone task mean: flip margin ≥ 1 gives −0.059 (n = 113), < 1 gives −0.027 (n = 179).
  - Retail: −0.017 vs −0.004. Action-type first divergences give +0.021 (retail) and −0.029 (airline).
  - These are small and inconsistent, and there is no CI.
  - evidence: `out/s05_pilot_success_q4_{airline,retail}.json` ← `s05_pilot_success.py`.
- *4080 analogue* (recomputed; raw-run check pending):
  - W4 net loss 0.044 [−0.038, 0.126] against gross churn 0.261;
  - checkpoint variance share 0.008;
  - recovery is lower when a flip writes (0.214–0.346) than when it only changes text (0.677–1.0).
  - evidence: `mechanism/churn.out`, `mechanism/a567.out` Q7.

**Predictions** (a6k2 cells).
- **P2a (two thresholds; replaces "inside the range of 5 nulls").**
  - Per model, Δdb_match(cell − mean of the 5 nonce nulls) with a task-cluster bootstrap, pooled over domains.
  - Free-zone cells (k ≤ 0.1, rtn_w8) have 95% CIs that include 0, and their pooled 5-model Δ is within ±3.4 pp (the MDE).
    evidence for the MDE: `iter_1_discussion.md#experiment-round-1` §Decisive tests.
  - gauss 3, rtn_w3 and gptq_w3 have CIs below 0.
  - The first k whose Δ CI excludes 0 is ≥ 1 in every model.
  - Exchangeability is also checked with the P4b permutation test.
  - Reported on db_match and on the strict-budget endpoint.
  - **Falsified** if the pooled free-zone Δ < −3.4 pp with a CI excluding 0.
- **P2b (the right predictor).** Across all cells of a model, Δ correlates with the identical-context tool-turn flip rate
  at |Spearman| ≥ 0.7, and better than with KM ≤ 4 or with median |d|.
  - The flip rate is taken from E3 (open-loop, on the cell's own server).
- **P2e (process channels).** Mean decisions per episode, premature rate and repeated-call rate stay inside the null band
  for every free-zone cell. They rise only where the tool-turn flip rate is ≥ 0.15.
  - Flat Score's "amplified failures" then follow from D, at the same |d| for AWQ as for Gaussian noise.
- **P2c (demoted to exploratory).** The flip margin at first divergence predicts the cost of the divergence. Kept only as a pooled 5-model test.
- **P2d (dropped from main).** Cross-model ordering of damage onset at k = 1 is underpowered with 2 seeds (SE ≈ 0.037).
  It would need E6. evidence: `EXPERIMENTS.md` E6.

**Scope.** Environments where success hinges on a few state-changing actions (db end-state). NL-judged endpoints should
move the damage threshold toward the divergence threshold; this is testable on `tau2_reward`.

**What is new.**
- Survey call (a): a two-threshold dose-response along one δ axis, and the action-turn flip rate as the fidelity metric.
  evidence: `SURVEY.md#i2-later-damage-threshold-set-by-action-decision-margins`.
- Flat Score is a single point (INT4/FP8); we turn its verbal account into a measured threshold.

**Questions for survey.**
- Lead https://arxiv.org/abs/2606.02965, which is unopened: does it link decision confidence to downstream cost in agents?
- Any agent-quantization work reporting turns or decisions per episode against a noise null?

---

## I3. The logit-shift distribution D is a sufficient statistic, and it transfers across models (P3)

**Status:** new (strengthened in round 2 by q8 GPTQ/AWQ placement; small-k evidence reclassified as not yet clean).

**Principle.** Two weight perturbations with the same output-logit shift distribution produce the same flip hazards,
divergence and damage in a closed-loop agent, whatever their structure (random, round-to-nearest, or error-minimising
quantizer). Under per-layer norm matching, D is roughly model-independent. A model's closed-loop sensitivity curve is
therefore predictable from its reference margins alone.

**Mechanism.** Within the inherited margin model, the perturbation enters only through D. Dense quantization error enters
the logits as a sum of many small terms, so it behaves like norm-matched noise (CLT). Error-minimising quantizers
(GPTQ, YAQA; https://arxiv.org/abs/2505.22988) shrink D and therefore move left on the same curve. Model size enters only
through the margins.

**Evidence** [legacy].
- *Quantizers land on the Gaussian ladder by measured D (q8).*

  | q8 configuration | median |d| | p90 | tool-turn flip | KM ≤ 0 |
  |---|---|---|---|---|
  | gauss 0.3 | 0.5 | 1.6–1.75 | 0.06–0.18 | 0.09–0.25 |
  | GPTQ W4 (2 draws × 2 nonces) | 0.75 | 2.0–2.25 | 0.23–0.30 | 0.17–0.20 |
  | AWQ W4 | 1.5 | 3.5 | 0.38–0.41 | 0.17–0.27 |
  | RTN W4 | 1.5 | 4.1–4.25 | 0.39–0.44 | 0.44–0.48 |
  | gauss 1 | 1.625–1.75 | 4.6–4.75 | 0.35–0.41 | 0.44–0.46 |

  - GPTQ falls between k = 0.3 and k = 1, as the round-1 P3b placement predicted. AWQ ≈ RTN W4 ≈ k = 1 in D and in tool flips.
  - Divergence at d = 0 does not fully line up (AWQ 0.17–0.27 vs k = 1 at 0.44). That is a hint that p90 and shape matter, not only the median.
  - evidence: `out/s01_token_flip_margin_q8.json`, `out/s02_trajectory_divergence_q8.json`.
- *q4, RTN W4 vs k = 1.* |d| 1.875 (p90 5.1–5.25) vs 2.0–2.25 (p90 6.0–6.25). Text-turn flips 0.91 vs 0.95–1.0.
  evidence: `out/s01_token_flip_margin_q4.json`.
- *D(k) is the same on q4 and q8 at k ≥ 0.3.* Median |d| is 0.5 vs 0.5 at k = 0.3, and 2.125 vs 1.75 at k = 1.
  - At k ≤ 0.1 the values also match (0.125, 0.25), but the kernel flavour alone has D = 0.125, so **the small-k match is not evidence until a6k2**.
  - evidence: `out/s03_margin_predictions.json` `shift_by_k`; `iter_1_discussion.md#experiment-round-1` impact-by-claim.
- *The margin-only prediction on q4 under-predicts by 0.1–0.15.* The cause is survivorship: D is estimated only on unflipped
  prefix tokens. E3 removes that by measuring D open-loop on the reference contexts.
  - evidence: `out/s03_margin_predictions.json` vs `out/s02_trajectory_divergence_q4.json`.

**Predictions** (a6k2 cells, D from E3).
- **P3a.** At k = 0.1 / 0.3 / 1, median |d| for q14, q30a3 and q32 is within 1.5× of q4's.
- **P3b.** Place gptq_w4 (d1, d2), awq_w4, gptq_w3 and rtn_w8/w4/w3 by measured D (median and p90).
  - Their Δdb_match, tool-turn flip rate and process channels fall inside the Gaussian-ladder *band* at matched D.
  - The band is non-monotone-tolerant, per Qamar (https://arxiv.org/abs/2609.07664).
  - The Gaussian ladder is applied only to BF16 weights (Fang, https://arxiv.org/abs/2506.22776).
  - **Falsified** if a quantizer is more than 2 SE below the band at matched D. That would be quantization-specific damage, the fallback in COLING_PLAN §6.
- **P3c.** Pre-registered margin-only first-divergence curves for q8, q14 and q30a3 (numbers in `out/s03_margin_predictions.json` `models.*.pred`).
  - Score them after a +0.10 bias correction, or after E3 removes the bias, within ±0.15 at d = 0 / 4 / 8.
  - Examples at k = 0.3, P(≤ 0 / ≤ 4 / ≤ 8): q14 0.25 / 0.77 / 0.99; q30a3 0.35 / 0.61 / 1.00.
- **Token-level calibration (the survey's idea 3).** Fit the Integer Alibi-style margin→flip calibration (Brier) on the kernel-flavour pair.
  Apply it unchanged to every family after δ-rescaling. One curve fitting all families is token-level evidence for sufficiency (E4e).

**Scope.** Dense, small per-weight perturbations of BF16 weights. Outlier-concentrated or activation quantization may break the CLT argument; P3b tests that.

**What is new.**
- Survey calls (a): D-sufficiency across families, size-independent D(k), and pre-registered cross-model curves.
- Survey call (b): margin-predicted robustness in principle (Fu, https://arxiv.org/abs/2601.06118).
- evidence: `SURVEY.md#i3-d-as-a-sufficient-statistic-transferable-across-models`.

**Questions for survey.**
- Does any work compare quantizers at matched output KL or matched logit shift in agentic or multi-turn settings? (Round 1 found none. Re-check before submission.)

---

## I4. The reference run is one draw; equivalence means exchangeability with a weight-only null

**Status:** new (revised in round 2: the null is now weight-side first, for the canonical-prompt risk).

**Principle.** Under greedy, deterministic serving, a closed-loop agent's canonical score is reproducible on a fixed
server. It is still one draw from the distribution induced by sub-threshold perturbations, and even a compiler autotune
choice moves it. A compressed model should be judged by task-level exchangeability with a null built from such
perturbations. That null should be built on the *canonical prompt* (weight-side and numerics-side perturbations), with
prompt nonces reported alongside, because prompt variants can carry a systematic canonical-prompt offset.

**Mechanism.** By I1, every sub-threshold perturbation re-rolls the trajectory, so each task outcome is ~Bernoulli(p_t).
The run-level SD is √(mean p_t(1−p_t)/n). Rerun nulls are either 0 or saturated depending on D (P1c), so they are not a
valid unit. Prompt nonces may shift p_t systematically; see Lunardi (https://arxiv.org/abs/2509.04013) and Mizrahi (https://arxiv.org/abs/2401.00595).

**Evidence** [legacy].
- *The canonical score moves with the kernel flavour.* q4 BF16, same weights and prompt, 20 tasks: db_match 0.45 vs 0.55;
  4/20 tasks flip. evidence: `out/s07_flavour_outcome.json` ← `s07_flavour_outcome.py`.
- *Null spread against the Bernoulli prediction (q4).*
  - Tasks disagree between null draws in 0.185 (airline) and 0.195 (retail) of cases.
  - Retail: 3 nulls all score 0.345 (SD 0; Bernoulli SD 0.034).
  - Airline: canonical 0.556 vs nonce 0.370 (SD 0.131; Bernoulli 0.041).
  - Pooled over 85 tasks, the Bernoulli SD is ≈ 2.6 pt. The tau2 issue #540 estimate, 7–11 pt, was measured under sampling
    (https://github.com/sierra-research/tau2-bench/issues/540). Greedy decoding explains the narrower width, which still is not zero.
  - evidence: `out/s06_pilot_delta_q4_{retail,airline}.json`.
- *Canonical-prompt advantage: undecided.* Canonical BF16 is the top of the airline set (Δ +0.093 [+0.019, +0.167] vs the
  null mean) but tied on retail (0.345 = 0.345 = 0.345). evidence: same files.
- *4080* (recomputed; raw-run check pending):
  - checkpoint variance share 0.008 vs residual 0.490 (`mechanism/churn.out`);
  - v0's +0.121 at p = 0.0195 reversed on re-draw (`analysis/coling/RESULTS.md` §2);
  - the gain rate 166/954 = 0.174 means W4 pass sets are *not* nested in BF16's (`churn.out`).

**Predictions** (a6k2 cells, plus E5 families).
- **P4a.** The pooled null SD across 5 models × 5 nonce nulls (20 df) lies within [0.5, 2] × the Bernoulli prediction from p_t.
  It is reported next to tau2 #540.
- **P4b (exchangeability).** In each model's task × run matrix, a permutation test on mean pairwise φ (null–null vs null–cell) gives p > 0.05 for free-zone cells.
  - Damage cells (k = 3, W3) form a separate cluster.
- **P4c (canonical-prompt test; now decided by E5).** Compare three families on the canonical-vs-null comparison: the weight-only null (gauss k = 0.03 s1–s5, canonical prompt), the numerics-flavour null (legacy-vs-a6k2 BF16) and the nonce null.
  - If the canonical run is systematically above the nonce null but not above the weight-only or flavour nulls, then the nonce carries a prompt offset.
  - In that case the paper's null becomes the weight-only / flavour family, and nonce is reported as a separate prompt-sensitivity axis.
  - If the canonical run tops all three families, the free zone in I2 is refuted as stated.
- **P4d.** Naive per-task McNemar of each free-zone cell against canonical bf16 yields at least one nominal p < 0.05 across the 5 models. Tests against the null yield none.
- **P4e (nestedness).** For free-zone cells, the gain rate (fail → pass vs the null) sits inside the null's own gain-rate band.
  - Damage cells show nested pass sets: the gain rate falls below the null's 5th percentile.

**Scope.** Greedy evaluation with ≈ 85 tasks. With many sampled trials per task, the "one draw" issue shrinks, but the exchangeability test still applies.

**What is new.** Survey call (b), plus (a) for φ-exchangeability in closed-loop compressed agents.
- evidence: `SURVEY.md#i4-the-reference-run-is-one-draw-equivalence-means-exchangeability`.
- Cite Compared to What? (https://arxiv.org/abs/2605.01048), Singh (https://arxiv.org/abs/2608.15046), Acharyya (https://arxiv.org/abs/2509.10963) and Koobs & Koning (https://arxiv.org/abs/2603.16213).

**Questions for survey.**
- Has anyone shown that a compiler/autotune choice changes an agent-benchmark score (not only token output)?
- Acharyya or Koobs & Koning full text: which one gives the formal basis for a null-derived equivalence margin?

---

## Experiments: agreed and ranked

Ids follow `docs/insights/EXPERIMENTS.md`. The ranking is by value per GPU-hour.

| rank | id | what | serves | GPU-h | status | evidence |
|---|---|---|---|---|---|---|
| 1 | **E4** | Analyses of existing and a6k2 runs (sub-items below) | I1, I2, I3, I4 | 0 | E4a done; rest proposed | `analysis/insights/iter_1/s02_trajectory_divergence.py`, `s06_pilot_delta.py` |
| 2 | **E2** | a6k2 rerun under `TORCHINDUCTOR_DETERMINISTIC=1` (running since 19:05), plus a **canary gate and one cross-node det pair per model**, which is what P1c needs | all paired statistics; P1a, P3a/c | ≈115 (whole matrix, already scheduled) | running | `iter_1_discussion.md#experiment-round-1` (b); `EXPERIMENTS.md` E2 |
| 3 | **E5** | Flavour + weight-only null families (details below) | P1c, P4c, the survey's weight-only null | ≈6 | proposed | `out/s07_flavour_outcome.json`; `SURVEY.md#ideas-from-recent-work` 4 |
| 4 | **E3** | Open-loop D per cell on its own server, on the BF16 reference contexts | P2b, P3a–c; removes the survivorship bias in D | ≈26 (est.) | proposed | `EXPERIMENTS.md` E3 |
| 5 | **E7** (new) | Real-kernel (Marlin) det pairs for q8 awq_w4 and gptq_w4 (Phase 4) | P1c per format (Replay Gap) | ≈0.5 | proposed | https://arxiv.org/abs/2608.08239; `docs/A6000_PLAN.md` §4 Phase 4 |
| — | E6 | seeds s3/s4 at k = 0.3 and k = 1 | P2d only | ≈15 | deferred | `EXPERIMENTS.md` E6 |
| — | E1 | determinism probes | — | ≈0.75 | superseded (root cause confirmed; fix adopted) | `analysis/determinism/probe_q4.json` |
| — | X1 | drop `q32_gptq_w4_d2` if it OOMs | — | −4 to −8 | agreed (conditional) | `EXPERIMENTS.md` X1 |

E4 sub-items:
- (a) s02 `format` events. Done in this round.
- (b) Tag every run with its server flavour. Paired statistics use clean pairs only.
- (c) Strict-budget endpoint, process channels, and an empty-episode audit. Implemented in `s06`; still to be run on the damage cells.
- (d) P4a SD next to tau2 #540.
- (e) Margin→flip Brier calibration across families.
- (f) P4b φ permutation and P4e nestedness.

E5 contents:
- The legacy q4/q8 BF16 runs against their a6k2 twins. These are free.
- Gauss k = 0.03 s3–s5 on the canonical prompt for q4 and q8.
- One `--enforce-eager` BF16 run per model, as a third numerics flavour.

## Changes after discussion (round 2)

- **Kernel flavour (experiment D1–D5; fact 1).** The "node005 floor" is relabelled a *compiled-kernel numerics flavour* (Inductor reduction autotune).
  - It becomes I1's cleanest datum: a reduction-order change re-rolls 95% of trajectories and 20% of task outcomes.
    evidence: `out/s04_node_floor.json`, `out/s07_flavour_outcome.json`.
  - It is a measured null family (E5) for P1c and P4c.
  - All legacy numbers are labelled [legacy]; decisive tests move to a6k2.
- **Simulator attribution retracted.** The round-1 "context mismatch = simulator noise" claim is withdrawn: the mismatches are agent-side raw-token differences.
  After the fix they are 0. evidence: `exp/out/ctxmis.json`; `out/s02_*`.
- **s02 censoring bug fixed (E4a; fact 2).** Divergence is now defined on raw tokens, with a `format` type.
  - KM curves rose slightly: q4 k = 0.03 ≤ 4 went from 0.57–0.60 to 0.61–0.65, and q8 k = 1 ≤ 0 is now 0.44–0.46.
  - evidence: `out/s02_trajectory_divergence_{q4,q8}.json`.
- **P2a restated (fact 3).** "Inside the range of 5 nulls" is replaced by a task-bootstrap Δ against the null mean, pooled MDE ≈ 3.4 pp, plus the P4b permutation test.
  - The round-1 rule had a ≈ 1/3 false-flag rate per run.
- **Flat Score's error budget (fact 4).** P2 is reported on db_match, on a strict-budget endpoint (≤ 2 tool errors) and on process channels (P2e).
  - The first pilot shows the process channels move at k = 1 while db_match does not yet. evidence: `out/s06_*`.
- **Canonical-prompt risk (fact 4).** P4c is recast as a three-family comparison, and the weight-only null is adopted (E5).
  - Pilot: canonical is the top on airline but tied on retail, so the question is undecided.
- **P2c demoted, P2d dropped from main.** The pilot shows no task-level cost-by-margin effect, and P2d is underpowered.
- **Per-step model** positioned as inherited (Du Eq. 14, Integer Alibi, MarginGate). Calibration by Brier is added (E4e).
- **P3b placement partly confirmed on legacy q8.** GPTQ D = 0.75 falls between k = 0.3 and k = 1; AWQ ≈ RTN W4 ≈ k = 1.
  - Small-k D matching is reclassified as not yet evidence (it is flavour-confounded).
- **Replay Gap and the per-format null.** Handled by P1c plus E7.
  - Nonce is presentation-only (a "Session ID" line; `cloq/agent.py` L93–96), per AgentDiff.

## Rejected or merged (carried from round 1)

- Horizon amplification: an obvious-sounding corollary of 1 − ∏(1 − p_s). evidence: `docs/STRATEGY_v2.md` §2.2.
- "Open-loop fidelity ≠ closed-loop": occupied. Merged into I2/P2b.
- "Calibration data doesn't matter at W4": subsumed by I3.
- CLOQ occupancy repair: a killed method claim. Loop attribution: an engineering fact.
- Token inflation (T2) and false success (T4) are not insights. T2 is used as the P2e process channel.

## Most important next experiment

Take the first two a6k2 models (q4, q8) with all 5 nonce nulls, the E5 weight-only nulls, and gauss k = 1 and k = 3, and run P2a/P2e together with P4c.
- The free zone survives if the pooled k ≤ 0.1 / W8 Δ is within ±3.4 pp *and* the canonical run is not above the weight-only null.
- It dies if either condition fails.
