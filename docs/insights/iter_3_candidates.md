**TL;DR**
- At W4, quantization re-deals 10–48% of the tasks the model controls, and the aggregate score barely moves. This is **not quantization-specific**: at the same weight-space size, Gaussian noise re-deals *more* (pooled +0.11 to +0.13 λ over RTN, GPTQ and AWQ; 4/4 models), while a null-scale fixed checkpoint re-deals nothing. evidence: `analysis/insights/iter_3/out/r08_size_generic_{live,frozen}.json`.
- Which tasks break is a model-specific, perturbation-agnostic latent property. Noise-derived fragility predicts quantizer breaks (AUC 0.75–0.83), but it does not transfer across models (AUC ≈ 0.5). Neither BF16 margins nor open-loop flips reveal it. Open-loop flips predict *how many* tasks are re-dealt (ρ ≈ 0.75), not *which*. evidence: `r03_fragility_live.json`, `r04_margin_predict_live.json`, `r05_openloop_task_live.json`, `r06_crossmodel_live.json`.
- Decisive next experiment: **E17**, RTN-shaped Gaussian noise (per-group σ matched to RTN-W4). It decides whether the noise > quantizer gap comes from the error's energy distribution or from its rounding structure. Also finish the queued W5/W6 cells and E3 on q8/q14/q30a3 (predictions P5.1–P7.1).

# Insight candidates: iteration 3 (quantization-centred; round 1)

Owner: cloq-insight. Framing: `docs/insights/PLAN_iter4.md` (RQ2–RQ4; the BF16 null is the yardstick only).
Ids continue from the ledger (`docs/insights/LEDGER.md`): **I5–I8** are new. Rejected claims are **R3-a…R3-f**, and experiment proposals are **E17–E21** (continuing `docs/insights/EXPERIMENTS.md` and `iter_2_integrity.md` §7).

## Data and method (read first)

Two manifests are built with the same integrity gate (`analysis/insights/iter_2/integrity.py`):
- **frozen** `analysis/insights/iter_2/out/snapshot_20260929T0732Z.json` (the iteration-2 frozen set, 161 runs);
- **live** `analysis/insights/iter_3/out/snapshot_live_20260929T1159Z.json` (213 runs; log `out/integrity_live_20260929T1159Z.log`). It is PROVISIONAL. It adds:
  - the fixed-checkpoint controls: q4 and q14 `gauss1_s1_q1/q2`, q14 `gauss0.03_s1_q1/q2`, and one draw each of q4/q8 `gauss0.03_s1_q*`;
  - the fresh-nonce quantizer draws `*_q3..q5` (q4 AWQ/GPTQ-W3; q14 AWQ, GPTQ-W4-d1, GPTQ-W3);
  - the q4 null redos n3–n5 (q4 U = 8 nonce nulls);
  - q8 null n6/n7;
  - q8 RTN-W3.

Every number below says which manifest it comes from. Unless marked *frozen*, it is **live**. Wherever both exist, the frozen/live difference is small and is shown.

- **Scripts.** `analysis/insights/iter_3/r0[1-9]_*.py` plus the shared `r_common.py`, which imports `iter_2/common.py`. That gives the same outcome definition, infra handling, W10 context-overflow-as-failure and frozen-file checks.
- **Re-run.** `bash analysis/insights/iter_3/run_all.sh`. Outputs: `analysis/insights/iter_3/out/r0*_{frozen,live}.json`.
- **Null (NR1-conform, `docs/insights/NULL_RULE.md`).**
  - The primary reference is the nonce-null stratum U, with each draw's nonce-mates removed (NR1-3).
  - Canonical-prompt Gaussian cells are cross-stratum. They are reported raw and composed-corrected (λ_P = 1 − (1−λ_tot)/(1−λ_K), where λ_K is the canonical prompt's own λ), and are used as sensitivity only.
  - The fixed-checkpoint Gaussian controls under fresh nonces are the primary Gaussian evidence.
- **Estimator (r01).** Tasks are classified on n_ref = |U|−1 null draws as always-ok, always-fail or coin. For a perturbed draw:
  - break b = P(fail | always-ok), fix f = P(success | always-fail);
  - held-out null draws give b0, f0 (misclassification);
  - the shrink-to-attractor model p′ = (1−λ)p + λc gives **λ = (b+f−b0−f0)/(1−b0−f0)** and **c = (f − (1−λ)f0)/λ**;
  - Δ = λ(c − p̄) follows.
  - 95% CIs come from a task bootstrap (tasks are clusters; draws are not resampled). Per-draw λ is listed as well.
  - Null calibration: the SD of a single held-out null draw's λ is 0.038 / 0.077 / 0.048 / 0.062 on q4 / q8 / q14 / q30a3; for pairs of null draws it is 0.024–0.050. evidence: `r08_size_generic_live.json` `models.<m>.null_single_draw_lam_sd`, `null_pair_lam_sd`.
- **Not available:** l8, q32 (|U| = 3 in live) and X1. W5/W6, q4/q14 RTN-W3 and q8 churnctl are still running or queued. Open-loop E3 exists only for q4 (all cells) and q8 (Gaussian + AWQ).

## 0. Direct answer to the lead's question

**Is reallocation quantization-specific or size-generic?** It is size-generic, and quantizers are *gentler* than noise of equal weight norm.
- At k = 1, a per-linear Gaussian with ‖N‖_F = ‖RTN-W4 error‖_F re-deals at least as many tasks as each W4 quantizer on every model (λ, live):

  | model | Gaussian k = 1 | RTN-W4 | GPTQ-W4 | AWQ-W4 |
  |---|---|---|---|---|
  | q4 | 0.27 | 0.24 | 0.32 | 0.25 |
  | q8 | 0.61 | 0.29 | 0.35 | 0.48 |
  | q14 | 0.28 | 0.27 | 0.16 | 0.07 |
  | q30a3 | 0.23 | 0.14 | 0.01 | 0.11 |

- Pooled contrast "Gaussian k = 1 − quantizer":

  | quantizer | live | frozen |
  |---|---|---|
  | RTN | +0.11 [−0.01, +0.24] | +0.14 [+0.01, +0.28] |
  | GPTQ | +0.13 [+0.03, +0.23] | +0.15 [+0.05, +0.26] |
  | AWQ | +0.12 [−0.01, +0.25] | +0.13 [+0.00, +0.27] |

  evidence: `r08_size_generic_{live,frozen}.json` `pooled`.
- Among W4 methods there is no pooled difference: RTN − GPTQ +0.02 [−0.07, +0.12]; RTN − AWQ +0.01 [−0.11, +0.14] (same file).
- The review's alternative, "any fixed checkpoint has its own task profile" (`paper/review_v2.md` W-B.1), is rejected where it has been tested. Fixed k = 0.03 checkpoint under 2 fresh nonces on q14: λ = −0.03 [−0.16, +0.09]. Fixed k = 1 minus fixed k = 0.03 (pooled q4 + q14): +0.27 [+0.12, +0.44] (`r08…live.json` `pooled["gauss1_fixed-gauss0.03_fixed"]`; `r01_realloc_live.json` `models.q14.families.gauss0.03_fixed`).

**Which formulation is useful for practitioners?** "Predict the agentic effect from error size and base-rate profile" is right for the *amount* only. We therefore propose three numbers instead of one:
1. **λ, the number of re-dealt tasks.** Predictable from an open-loop output-space size (ρ = 0.75–0.83 across cells; I7).
2. **Δ = λ(c − p̄), the net change.** Error size does not predict it. It is bounded by λ·|c − p̄|, and at W4 c sits just below p̄ (median c − p̄ = −0.09; I5). So |Δ| ≲ 0.1·λ at deployable sizes.
3. **The fragile set F, which tasks.** It is model-specific but perturbation-agnostic. Map it once with any perturbation of size ≥ k = 0.3, and reuse it for every quantizer (I6).

Report λ and F against a re-roll null. Do not report Δ alone.

---

## I5 (new; supersedes the PLAN_iter4 RQ2 wording "quantization reallocates capability") — size-generic reallocation toward an attractor

**Principle.** A fixed weight perturbation above a size threshold moves every task's success probability toward a common attractor, p′ = (1−λ)p + λc.
- Aggregate success therefore changes by only λ(c − p̄), while a fraction λ of the robustly solved and robustly failed tasks change fate.
- λ grows with the perturbation's size. It does not depend on whether the perturbation is quantization, and structured quantization error re-deals no more than isotropic noise of the same weight norm.

**Mechanism.**
- This builds on the first-order margin model (Du et al. 2026, https://arxiv.org/abs/2609.26621, Eq. 14). A decision flips when the perturbation's logit shift at that decision exceeds its margin.
- A *fixed* perturbation shifts the same critical decision the same way under every prompt re-roll, so the flip is repeatable. Nonce re-rolls, which leave the weights intact, cannot produce this (see I6).
- In closed loop, one flip at a critical decision sends the episode onto a new trajectory. Its outcome is close to a fresh draw from the model's competence on such trajectories, which gives the attractor c.
- λ is the probability that at least one critical decision on the task's path flips. It rises with the output-space size of the perturbation and saturates once most fragile decisions flip.
- Error-compensating quantizers (GPTQ/AWQ) reduce output error per unit weight error. RTN's error is bounded and scale-proportional per group, not isotropic. Both therefore sit at a lower effective size than Gaussian noise of equal ‖·‖_F.

**Evidence.**

| item | numbers | evidence |
|---|---|---|
| λ at W4, with 95% task-bootstrap CI | q4: RTN 0.24 [0.11, 0.39] (5 draws), GPTQ 0.32 [0.16, 0.53] (4), AWQ 0.25 [0.13, 0.38] (4). q8: 0.29 [0.05, 0.57], 0.35 [0.13, 0.58], 0.48 [0.20, 0.75]. q14: 0.27 [0.03, 0.48], 0.16 [−0.02, 0.34] (7), 0.07 [−0.10, 0.23] (5). q30a3: 0.14, 0.01, 0.11. The null single-draw SD is 0.04–0.08. | `r01_realloc_live.json` `models.<m>.families.<f>.{lam,lam_ci,n_draws}`; `r08…live.json` `null_single_draw_lam_sd` |
| matched-size Gaussian ≥ quantizers | §0 table; pooled +0.11 to +0.15 | `r08_size_generic_{live,frozen}.json` |
| fixed-checkpoint controls (fresh nonces) reproduce the canonical Gaussian λ | k = 1: q4 0.34 (fixed) vs 0.27 (canonical, composed); q14 0.32 vs 0.28. k = 0.03: q14 −0.03 (2 draws); q4 0.14 [0.03, 0.27] and q8 0.10 [−0.06, 0.30] (1 draw each, partial) | `r01_realloc_live.json` `families.{gauss1_fixed,gauss1,gauss0.03_fixed}` |
| small-size negative controls | RTN-W8 (k_eq = 0.062): q4 0.17 [0.03, 0.31], q8 0.13 [−0.06, 0.33], q30a3 −0.03. Gaussian k = 0.03 canonical: 0.06 / 0.06 / 0.14 / 0.04 | `r01…live.json` `families.rtn_w8`, `gauss0.03`; k_eq `r08…live.json` `k_eq_rtn` |
| attractor sits near p̄ at W4 | c − p̄ over 10 W4 families with λ > 0.1: mean −0.06, median −0.09, 8/10 negative. Per-family c CIs are wide (e.g. q4 RTN c 0.25 [0.06, 0.53]) | `r09_headline_live.json` `I5_attractor_W4` |
| Δ is consistent with the identity | ρ(Δ_obs, λ(c − p̄)) = 0.57 (p = 0.006, 22 families with λ > 0.15) | `r07_damage_live.json` `pooled_lam_gt_0.15` |
| draw spread within a checkpoint is larger than null draws | q4 GPTQ-W3 per-draw λ 0.34, 0.38 (n1/n2) vs 0.17, 0.06 (fresh q3/q4) | `r01…live.json` `families.gptq_w3.per_draw_lam` |

**Consequences of the draw spread.**
- At least 3 draws per checkpoint are needed.
- q4 GPTQ-W3 moved from λ = 0.38 (frozen) to 0.14 (live), and the claim is scoped accordingly.
- Checked on: q4, q8, q14, q30a3 (Qwen3; τ² retail + airline; greedy).
- Not yet checked on: l8, q32, X1, W5/W6, and more than 2 fixed-control draws on q8.

**Predictions (A6000 matrix).**
- **P5.1 (bit-width dose; RTN W5/W6, GPTQ W5 on q4/q8/q14, queued).**
  - λ is monotone in bits: λ(W8) ≤ λ(W6) ≤ λ(W5) ≤ λ(W4), within the null pair SD (0.02–0.05).
  - Each RTN width sits at or below the Gaussian λ at its own weight-space k_eq = sqrt(err ratio) (W8 = 0.062 measured; W3 = 2.14 on q8).
  - False if RTN-W5/W6 exceed the Gaussian λ interpolated at their k_eq by more than 2 null pair SDs, or if the order breaks on 2 of 3 models.
- **P5.2 (q8 churnctl, running).** Fixed k = 1 under fresh nonces gives λ ∈ [0.45, 0.75], matching canonical k = 1 (0.61). Fixed k = 0.03 gives λ ≤ 0.10.
  - The "any fixed checkpoint" alternative predicts fixed k = 0.03 ≈ fixed k = 1.
- **P5.3 (X1 official FP8 / AWQ).**
  - FP8 is a W8-size perturbation: λ ≤ 0.15 on every model.
  - Official AWQ-INT4 has λ within ±0.15 of our AWQ-W4 on the same model.
  - Caveat: the X1 AWQ dtype confound (`paper/review_v2.md` W-F).
- **P5.4 (l8).** λ(Gaussian k = 1) ≥ λ(best W4 quantizer), and c − p̄ ≤ 0 at W4.

**Scope limit.**
- Greedy decoding; one simulator family; 85 tasks.
- λ and c are identified only through always-ok / always-fail tasks. With 4–8 null draws the classification is coarse: 12–22 always-ok tasks per model.
- c is poorly identified per family. Only the pooled sign is claimed.

**Positioning.**
- *Dutta et al. 2024* (https://arxiv.org/abs/2407.09141): compressed LLMs show balanced flips at equal accuracy on static tasks.
- *Hooker et al. 2019*, "What do compressed deep neural networks forget?" (https://arxiv.org/abs/1911.05248): compression hits a subset of examples.
- *Flat Score* (https://arxiv.org/abs/2607.27275): τ²-bench, aggregate flat across precisions, failure set preserved (ρ ≥ 0.94).
- *Rath 2026* (https://arxiv.org/abs/2605.15208): new failures counted against seed flips.
- *Widrow-style additive-noise models of quantization*, and *Jacobian-guided noise injection* (https://arxiv.org/abs/2608.20988): Gaussian noise as a quantization proxy.
- What is new here:
  1. reallocation measured **against the closed-loop re-roll null**, with a misclassification-corrected (λ, c) estimator;
  2. a **matched-weight-norm isotropic control**, which shows reallocation is not quantization-specific and quantizers sit at or below noise;
  3. a **null-scale fixed-checkpoint control** (λ ≈ 0), which rules out the trivial "every checkpoint has a profile" reading.

**Questions for survey.**
- S5-a. Has anyone compared a quantizer's per-example flip set with that of **isotropic noise of matched weight norm**, in LLMs or any agent setting? Is "quantization error is less harmful than equal-norm noise" reported for LLM PTQ (RTN included, not only GPTQ/AWQ)?
- S5-b. Does Flat Score's "failure set preserved, ρ ≥ 0.94" refer to per-task outcomes or to failure categories? If per task, how does it square with λ = 0.1–0.5? (We need their unit to position.)
- S5-c. Is there a published mixture / "shrink toward base rate" model of per-item success under model perturbation, e.g. in the prediction-churn literature (Bhojanapalli 2021, https://arxiv.org/abs/2102.03349)?

---

## I6 (new) — task fragility is a latent (model, task) property: repeatable, shared across perturbation types, not shared across models, invisible to the unperturbed model

**Principle.** The tasks that a weight perturbation breaks or fixes have four properties:
- (a) they are largely **decided by the checkpoint**, and repeat across prompt re-rolls;
- (b) they are **shared across perturbation types**: quantizers of any method and isotropic noise break the same tasks;
- (c) they are **not shared across models**;
- (d) they **cannot be read off the unperturbed model**: neither from its decision margins, nor from its trajectory length, nor from teacher-forced flips on its own trajectory.

**Mechanism.**
- A task's fate hinges on a few critical decisions that the closed loop actually reaches.
- A generic perturbation (random, or quantization error that is nearly orthogonal to any task-specific direction) shifts a critical decision's logit gap by an amount of order ‖∂gap/∂W‖·‖δW‖. Its flip probability is therefore ranked by the *normalised* margin, gap / ‖∂gap/∂W‖, which is a property of the model.
- (a) and (b) follow directly.
- (c) follows because normalised margins are model-specific.
- (d) follows for two reasons:
  - the raw margin omits the sensitivity term;
  - the decisions that matter are often reached only after the loop has diverged, so they never appear on the reference trajectory that open-loop probes teacher-force.

**Evidence** (live; the frozen values agree within 0.03 AUC).

| item | numbers | evidence |
|---|---|---|
| (a) repeatable within a checkpoint | P(break in draw b \| break in draw a) = 0.56 / 0.75 / 0.81 / 0.29 on q4 / q8 / q14 / q30a3, against marginal 0.20 / 0.34 / 0.16 / 0.07 (lift 2.8 / 2.2 / 5.1 / 3.9). Fix lift 4.5 / 6.8 / 6.3 / 4.0. Example: q14 GPTQ-W4-d1 over 5 nonces, of 20 null-always-ok tasks 16 are ok in all 5 and 3 fail in all 5. | `r03_fragility_live.json` `models.<m>.groups.same_ckpt`; `r02_stability_live.json` `models.q14.checkpoints.gptq_w4_d1.fate_counts` |
| (b) shared across perturbation types | quantizer-vs-Gaussian break lift 2.2 / 1.5 / 2.2 / 1.9, fix lift 2.8 / 2.8 / 3.2 / 1.8. quantizer-vs-other-quantizer break lift 2.0 / 1.5 / 2.9 / 1.3. Fragility score from Gaussian draws (k ≥ 0.3) predicts each quantizer draw's breaks: mean AUC 0.83 / 0.83 / 0.82 / 0.75, AUC > 0.5 in 94–100% of draws; fixes 0.78 / 0.81 / 0.73 / 0.62. Frozen breaks: 0.84 / 0.82 / 0.83 / 0.75. | `r03_fragility_{live,frozen}.json` `groups.quant_vs_gauss`, `auc_summary_excl_w8` |
| (b) robust to null misclassification | on "super-robust" tasks (ok in every U, K and k ≤ 0.03 draw), Gaussian → quantizer break AUC 0.80 / 0.81 / 0.79 / 0.68, fix AUC 0.77 / 0.79 / 0.52 / 0.55 | `r04_margin_predict_live.json` `models.<m>.super_robust` |
| (c) not shared across models | model A's fragility predicting model B's quantizer breaks: mean AUC 0.51 over 12 ordered pairs (range 0.21–0.64). Task-fragility Pearson across models: −0.21 … +0.03. | `r06_crossmodel_live.json` `pairs`, `fragility_pearson_across_models` |
| (d) invisible to the unperturbed model | BF16 nonce-null margins, min over tool-call decisions: break AUC 0.43 / 0.56 / 0.60 / 0.45; near-tie count 0.42 / 0.49 / 0.59 / 0.30; length (tool calls) 0.67 / 0.58 / 0.63 / 0.67. Open-loop per-task flips on the E3 sample (quantizer's own cell / Gaussian cells): 0.48 / 0.42 on q4, 0.40 / 0.47 on q8. | `r04_margin_predict_live.json` `auc_summary`; `r05_openloop_task_live.json` `auc_summary` |

- The E3 per-task reconstruction is verified token-for-token against the stored margins (assert in `r05_openloop_task.py`).
- Checked on: q4, q8, q14, q30a3; 4–17 quantizer draws per model.
- Not yet checked on: l8, q32, X1, W5/W6.
- q30a3 (MoE) is the weakest case, with few breaks (7 draws with breaks).

**Predictions.**
- **P6.1 (every new quantizer cell: W5/W6, X1 AWQ/FP8, *_qx).** Gaussian-derived fragility predicts its breaks with AUC ≥ 0.70 wherever the draw has ≥ 5 breaks among null-always-ok tasks. False if the mean AUC over new cells is < 0.6 on 2 of 3 dense models.
- **P6.2 (l8).**
  - Within-model Gaussian → quantizer AUC ≥ 0.70.
  - Qwen fragility → l8 AUC in [0.4, 0.6].
  - A cross-family AUC ≥ 0.7 would make fragility a task property and falsify (c).
- **P6.3 (E19, 0 GPU-h + E3 extension).** A normalised-margin score, margin / ‖∇ logit-gap‖ at tool-call decisions (the gradient norm is estimable by finite differences from two Gaussian seeds' open-loop d = Δlogprob at the *same* decision: |d| ∝ ‖∇‖), predicts breaks better than the raw margin (AUC gain ≥ 0.1). If it does not, the mechanism is wrong.
- **P6.4 (benchmark design).** The top-20 fragile tasks per model detect a W4 quantizer's λ with half the draws that all 85 tasks need. Test: subsample existing draws.

**Scope limit.**
- AUCs are computed over 8–22 always-ok tasks per model.
- "Invisible" refers to the margin statistics we tried and to a 400-decision open-loop sample (≈ 4.7 decisions per task). A denser open-loop probe could still work.

**Positioning.**
- *Hooker et al. 2019* (https://arxiv.org/abs/1911.05248): pruning-identified exemplars are consistent across compressed models and tend to be atypical.
- *Toneva et al. 2019*, forgetting events (https://arxiv.org/abs/1812.05159).
- *Baldock et al. 2021*, example difficulty (https://arxiv.org/abs/2106.09647).
- New here:
  - closed-loop agent tasks;
  - an explicit **noise ↔ quantizer transfer** of the fragile set;
  - **checkpoint repeatability across prompt re-rolls**;
  - **no cross-model transfer**;
  - a negative result: fragility is *not* visible in the reference model's confidence or open-loop flips, which contrasts with confidence-based accounts of PIEs.

**Questions for survey.**
- S6-a. Do PIE-style analyses (Hooker 2019/2020) test whether **random weight noise** selects the same examples as pruning/quantization?
- S6-b. Do they test whether the set transfers across architectures?
- S6-c. Has any LLM or agent paper predicted *which* items a quantized model gets wrong from the full-precision model's confidence, and with what AUC?
- S6-d. Is there prior use of "normalised margin" (margin / gradient norm) as a per-example robustness score for weight perturbations (cf. PAC-Bayes sharpness)?

---

## I7 (new; reframes the refuted C4 "open-loop gate") — open loop predicts how much, closed loop decides which

**Principle.**
- The open-loop decision-flip rate of a perturbed model, measured on reference contexts, predicts how many tasks it will re-deal in closed loop.
- It predicts neither which tasks nor the net score change: the identity is set in closed loop (I6), and the net change is λ(c − p̄), with c ≈ p̄ at deployable sizes (I5).

**Mechanism.**
- λ is a monotone function of the per-decision flip probability (margin model).
- Δ is a product in which the size term λ multiplies the attractor gap c − p̄. At W4 the gap is small and of either sign, so any dose measure is nearly uninformative about Δ. This explains the iteration-2 result "residual SD of Δ = SD of Δ".

**Evidence.**
- ρ(open-loop decision-any-flip, λ) = 0.75 (p = 0.0009, 16 cells, q4; frozen 0.83) and 0.76 (p = 0.006, 11 cells, q8).
  - evidence: `r05_openloop_task_{live,frozen}.json` `models.<m>.cell_identity`.
- ρ(open-loop, Δ_obs) = −0.45 (p = 0.08; frozen −0.56, p = 0.02) on q4 and −0.21 (p = 0.53) on q8.
  - The iteration-2 C4 result is the same: Δ residual SD 0.0369 vs SD 0.0372 (`analysis/insights/iter_2/out/c02_openloop_conformal.json` `jackknife_plus.delta`).
- Task-level open-loop AUC ≈ 0.4–0.6 (I6 d).
- Visible saturation on q4:
  - λ reaches 0.18–0.38 once open-loop any-flip is ≥ 0.43 (Gaussian k ≥ 0.3), and stays there through flip 0.67;
  - GPTQ-W4 flips half as often as RTN-W4 (0.034 vs 0.064 token flip) but has λ 0.32 vs 0.24.
  - evidence: `r05_openloop_task_live.json` `cell_identity.points`.
- Checked on: q4 (all cells) and q8 (Gaussian + AWQ only).

**Predictions.**
- **P7.1 (E3 on q8 quantizers, q14, q30a3, all queued; E18 for W5/W6).**
  - Per model, ρ(open-loop any-flip, λ) ≥ 0.6, and |ρ(open-loop, Δ)| is lower than that on the same cells.
  - The q4 saturation implies that above any-flip ≈ 0.45 the ranking by λ is no better than chance.
  - Falsified if ρ(open-loop, λ) < 0.4 on 2 of 3 new models.
- **P7.2.** A per-model saturating fit λ = λ_max(1 − exp(−a·x)) on Gaussian cells alone predicts each quantizer's λ within ±0.15 (leave-quantizers-out).
  - q4 GPTQ-W3 (open-loop 0.66, λ 0.14) is the known outlier to report.

**Positioning.**
- Du et al. (https://arxiv.org/abs/2609.26621) give the per-token flip model.
- Qamar et al. (https://arxiv.org/abs/2609.07664) argue for divergence metrics over accuracy.
- Our own V3 found open-loop NLL ≠ closed-loop success (`docs/RESEARCH_LOG.md` V3).
- New: the **amount/identity/net split**, with a quantitative identity (Δ = λ(c − p̄)) that says *why* open-loop metrics fail for Δ while they succeed for λ.

**Questions for survey.**
- S7-a. Any work that predicts closed-loop *outcome churn* (not accuracy) from open-loop/teacher-forced divergence, in agents or in RL policy compression?
- S7-b. Evidence that per-token KL or flip rate saturates as a predictor of downstream flips at 4 bits?

---

## I8 (new, HYPOTHESIS) — net damage is attractor collapse, and it arrives with loud control failures; below it, breaks are silent

**Principle.**
- A perturbation costs net success only when it lowers the attractor c well below p̄. This coincides with failures of the agent's control loop: step exhaustion, repeated calls and context overflow.
- At deployable sizes, almost all re-dealt tasks fail *silently*: the dialogue terminates normally with a wrong database state.

**Mechanism.**
- Loop and runaway states are absorbing: the episode cannot succeed once the agent repeats calls until max_steps or context overflow (W10).
- Their entry needs the stop/progress decisions to flip consistently, which needs a larger perturbation than flipping one argument does. Hence a later threshold, as in I2 (v2), which this insight replaces.
- Silent breaks are single critical-decision flips (a wrong argument, a wrong or missing write) after which the dialogue still closes normally.

**Evidence.**
- Share of breaks of null-always-ok tasks that end abnormally:
  - W4, all models: 5/137 (3.6%). Per family: q4 RTN/GPTQ/AWQ 0/18, 0/16, 0/14; q8 0/10 AWQ, 1/16 GPTQ, 1/6 RTN; q14 1/12 RTN, 0/26 GPTQ, 2/11 AWQ; q30a3 0/8.
  - q8 RTN-W3: 4/14 (29%).
  - evidence: `r07_damage_live.json` `models.<m>.families.<f>.{brk_abn,n_breaks}`.
- q8 RTN-W3 against the q8 null:

  | | abnormal-termination rate | decisions per episode | repeated calls | c (p̄) | Δ |
  |---|---|---|---|---|---|
  | q8 RTN-W3 | 0.37 | 32.8 | 5.8 | 0.06 (p̄ 0.29) | −0.157 |
  | q8 null | 0.06 | 17.7 | 2.4 | — | — |

  - q8 Gaussian k = 1: abnormal-termination rate 0.14, c 0.10.
  - Pooled over 22 families with λ > 0.15: ρ(p̄ − c, excess abnormal rate) = 0.48 (p = 0.023).
  - evidence: `r07_damage_live.json` `models.q8.families.rtn_w3`, `pooled_lam_gt_0.15`.
- W10 context-overflow runaways appear at k ≥ 1–2 (`docs/RESEARCH_LOG.md` W10).
- Weak points:
  - p̄ − c is noisy;
  - per-model ρ is not significant (n = 5–8);
  - there is only one clear damage cell (q8 RTN-W3) in the live snapshot;
  - q4/q14 W3 and k = 2/3 are still running.

**Predictions.**
- **P8.1 (q4/q14 RTN-W3, q4 k = 2/3, q14/q30a3 k = 3; running).** Every cell with Δ < −5 pp has an abnormal-termination excess of ≥ 5 pp, and p̄ − c ≥ 0.15. No W4–W6 cell has an abnormal excess > 3 pp. Falsified by a cell with Δ < −5 pp and abnormal excess < 2 pp: loss without control failure.
- **P8.2 (base-rate profile).** Once c collapses (c ≈ 0), Δ ≈ −λp̄, so the *relative* loss Δ/p̄ ≈ −λ is equal across models at matched λ. Stronger models lose more absolute points. Test on k = 3 / W3 across q4/q8/q14/q30a3.

**Positioning.**
- Flat Score (https://arxiv.org/abs/2607.27275): tool-name hallucination up 2.5×; a tighter error budget re-exposes 17 pt.
- Lian 2026 (https://arxiv.org/abs/2606.25519): quantization lengthens reasoning.
- "Anatomy of a closed-loop collapse" (https://arxiv.org/abs/2609.23048).
- New: loud failures are tied to the *attractor* parameter of a reallocation model, and the silent-break share at W4 is measured against a re-roll null.

**Questions for survey.**
- S8-a. Do agent-quantization papers report termination-reason distributions (max_steps, loops) against a same-model re-roll baseline?
- S8-b. Is "silent wrong-state completion vs loud failure" a documented split in agent reliability work?

---

## Rejected or killed in this iteration

| id | claim | verdict | evidence |
|---|---|---|---|
| R3-a | The reference model's decision margins at tool calls predict which tasks a quantizer breaks | **killed** (AUC 0.43–0.60, below length 0.58–0.67) | `r04_margin_predict_live.json` `auc_summary` |
| R3-b | Per-task open-loop flips (own cell or Gaussian) predict closed-loop breaks | **killed** (AUC 0.40–0.60) | `r05_openloop_task_live.json` `auc_summary` |
| R3-c | Fragility is a property of the task or benchmark | **killed** (cross-model AUC 0.51 mean; r ≈ 0) | `r06_crossmodel_live.json` |
| R3-d | "Any fixed checkpoint has its own task profile" (review W-B.1) | **rejected at k = 0.03 on q14** (λ −0.03, 2 draws); q4/q8 1 draw each, pending the running `a6k2_{q4,q8}_churnctl` | `r01_realloc_live.json` `models.<m>.families.gauss0.03_fixed` |
| R3-e | Structured quantization error is *more* harmful to agents than noise at equal size (the iteration-1 I3 threat from legacy q8 RTN-W4) | **rejected**: clean q8 RTN-W4 λ 0.29 vs Gaussian k = 1 0.61; the pooled sign is the opposite | `r08_size_generic_{live,frozen}.json` |
| R3-f | Out-of-sample check of the shrink model on the coin stratum, per family | **not claimed**: single-draw coin-stratum noise (≈ 0.09) swamps it (e.g. Gaussian k = 0.03 cells show coin Δ −0.09 to +0.15) | `r01_realloc_live.json` `families.*.{dcoin_obs,dcoin_pred}` |

**Relation to ledger I1–I4.**
- I1 (floor) and I4 (re-roll null) are BF16 behaviour. By PLAN_iter4 they move to Methods and are not re-proposed.
- I3 ("matched D ⇒ matched outcomes") is superseded at the λ level by I5 and I7: at matched weight size, outcomes are *not* matched (noise ≥ quantizers), while at output-space size the ordering is monotone but saturating.
- I2 (free zone / later damage threshold) is recast as I8 with a process mechanism.

## Experiments (ranked; costs from `queue/done/*.json` `seconds` where cited)

| id | what | decides | cost | status |
|---|---|---|---|---|
| E17 | **RTN-shaped Gaussian**: per 128-group Gaussian with σ equal to that group's RTN-W4 error RMS (same per-group energy as RTN, no rounding structure), fixed seed, 2 fresh nonces, on q4/q8/q14. Needs a `gauss_shaped` ckpt kind in `cloq/compress.py` (main implements it; we do not modify `cloq/`). | I5 mechanism. λ(shaped) ≈ λ(RTN-W4) means energy distribution explains the noise > quantizer gap; λ(shaped) ≈ λ(isotropic k = 1) means rounding structure matters. | 3 models × 2 runs, about 0.5–1 GPU-h each → **3–6 GPU-h** (same as E15, `iter_2_integrity.md` §7) | proposed |
| E18 | E3 open-loop for RTN-W5/W6 and GPTQ-W5 on q4/q8/q14. Not currently queued: no `*_ol_rtn_w5` in the queue. | P5.1, P7.1/P7.2 dose axis | about 6 min each × 9 → **about 1 GPU-h** | proposed |
| E19 | Normalised-margin fragility score (P6.3) from existing E3 npz (two Gaussian seeds at the same decisions) + closed-loop fates | I6 mechanism | 0 GPU-h | proposed (insight loop, iteration 4) |
| E20 | One more fresh-nonce draw of the q8 and q30a3 W4 quantizer checkpoints (only n1/n2 exist; within-checkpoint λ spread is large, e.g. q4 GPTQ-W3 0.06–0.38) | I5 per-model λ; I6 (a) on q8/q30a3 | 6 runs, about 0.5–1 GPU-h each → **3–6 GPU-h** | proposed |
| E21 | Re-run `analysis/insights/iter_3/run_all.sh` once the q8 churnctl, q4/q14 RTN-W3, k = 2/3, W5/W6, X1 and l8 cells pass the gate | P5.1–P8.2 | about 5 min CPU | when data lands |

Already queued and needed: `a6k2_{q4,q8}_churnctl`, `a6k2_q8_churnctl_k1` (running); W5/W6 (todo); X1 (todo); E3 on q8 quantizers, q14 and q30a3 (todo); l8 (todo). evidence: `/data/ziyangs/cloq_work/queue/{running,todo}/`.

## Changes from the previous iteration

- The subject moved from BF16 behaviour (I1–I4) to what quantization does (I5–I8), following PLAN_iter4.
- The PLAN_iter4 pilot (break 19–41%, fix 4–20%) is replaced by the misclassification-corrected (λ, c) estimator on stratum-matched nulls. The pilot pooled nonce-mates, so its numbers are not comparable.
- The iteration-2 churn verdict "provisional, fixed-checkpoint control pending" (`iter_2_integrity.md` §2) is now partly answered:
  - fixed k = 0.03 gives no reallocation (q14);
  - fixed k = 1 reproduces canonical k = 1.
  - The churn claim is therefore upgraded from "may be a fixed-checkpoint artefact" to "size-generic, not quantization-specific".

Data snapshot: frozen `snapshot_20260929T0732Z` (161 runs) plus live `snapshot_live_20260929T1159Z` (213 runs; a6k2 runs admitted by the same gate).
