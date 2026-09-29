**TL;DR**
- The draw-level conformal test is exact but coarse. A family with 2 draws cannot be rejected at 5% on q4 (p ≥ 1/15) or q14 (p ≥ 1/10), and ±5 pp equivalence is out of reach on every single model. Pooled over q4+q8+q14, 8 families pass ±5 pp. RTN-W4, RTN-W8 and k=1 do not, and k=1 is below the null (Holm p = 0.026).
- The new finding is task-profile churn. Quantized families that are rate-equivalent still change *which* tasks succeed (pooled churn test, Holm p ≤ 0.007 for AWQ, GPTQ-W3/W4 and RTN-W4). The churn statistic is the one to headline.
- Open-loop decision-flip rate predicts closed-loop hazard (ρ = 0.989; jackknife+ coverage 81/90% at nominal 80/90) but carries no information on success Δ (residual SD = target SD). So the C4 "open-loop gate" can gate divergence, not damage.

# Conformal layer for perturbation equivalence (iteration 2)

Snapshot: `analysis/insights/iter_2/out/c01_conformal_equivalence.json` `snapshot.utc` = 2026-09-29T05:45Z; c02 at 05:46Z.
Scripts: `analysis/insights/iter_2/c01_conformal_equivalence.py`, `analysis/insights/iter_2/c02_openloop_conformal.py`. Both are registered in `analysis/insights/iter_2/run_all.sh` and are read-only over `runs/` and `analysis/openloop/`.
Logs: `analysis/insights/iter_2/out/c01.log` and `c02.log`.

Ids: **A2-10** (conformal equivalence, c01), **A2-11** (open→closed conformal prediction, c02), **E12/E13** (proposals, §5), **S-C1…S-C9** (survey entries, `docs/insights/SURVEY.md#t8-conformal-methods-in-llm-and-agent-evaluation-iter-2`). They serve C2 and C4 of `docs/insights/PLAN_iter3.md#1-storyline-v3`.

## 0. Data state and rules

- **Outcome.** `common.outcomes` = db_match AND normal termination. `infrastructure_error` episodes are **missing** (`analysis/insights/iter_2/common.py` `INFRA`).
- **Run eligibility.** A run is used only if it has ≥ 90% of the 85 tasks. Each test runs on the complete-case task set of its bag.
  - Runs used and their task counts: `c01…json` `runs_used_n_tasks`.
  - Excluded partial runs are those with `snapshot.runs.*.n_scored` < 77. Examples: q14 `null_n3` (32), `null_n4` (8), q4 `rtn_w3_n*` (73/60), q4 `gauss1_s4` (39).
- **Re-runs in flight.** At the snapshot, the redo tasks listed in `snapshot.redo_tasks` were queued or running: `a6k2_q4_bf16_redo`, which re-creates q4 `null_n3..n5`, plus 7 cell redos. Re-running `bash run_all.sh` picks them up. Every number below is tied to this snapshot.
- **Null draws per model (null set A = bf16, bf16_eager, nonce nulls):**

  | model | n | SD | evidence |
  |---|---|---|---|
  | q4 | 4 | 2.03 pp | `nullsets.A.models.q4.null_draws`, `null_sd` |
  | q8 | 7 | 2.70 pp | same keys, q8 |
  | q14 | 3 | 3.87 pp | same keys, q14 |

- **Why A is not the whole story: prompt strata.** The null family mixes two prompt strata. Canonical-prompt runs are bf16, eager and all gauss cells. Nonce-prompt runs are the null_n* and the quantized cells.
  - The quantized cells reuse the nonces of null_n1/n2 (`scripts/a6000/make_tasks.py` `NONCES`, L44/L53).
  - Null set **S** is prompt-stratum matched. Gauss families are compared with the canonical-prompt nulls (bf16, eager; n = 2). Nonce families are compared with nonce nulls whose nonce the family does not use (q8: n3–n5; none on q4 or q14 yet).
  - **B** = A + gauss0.03 is a sensitivity set.
  - Definitions: `c01…json` `note_S`.

## 1. Conformal equivalence test (A2-10)

### 1.1 Definition

The unit is one closed-loop run r, a draw of the perturbation. Its outcome vector is y_r ∈ {0,1}^T over the tasks.
The hypothesis H0(C): the runs of cell or family C are **exchangeable** with the null-family runs N = {N_1..N_n}.
Three statistics, all symmetric in the bag:
- **net** = |mean_t (ȳ_C(t) − ȳ_N(t))|;
- **harm** = mean_t (ȳ_N(t) − ȳ_C(t)), one-sided;
- **churn** = mean_t |ȳ_C(t) − ȳ_N(t)|, a task-profile distance. It detects a change in *which* tasks succeed even when the rate does not move.

Four procedures (docstring of `c01_conformal_equivalence.py`):
1. **Per-draw conformal p-value.** Full conformal on the bag N ∪ {C_j}: p = (#{s_i > s_C} + U·#{s_i = s_C})/(n+1), U ~ Unif(0,1). The conservative version has U = 1. Per-draw values are under `families.*.per_draw`.
2. **Family test.** An exact permutation test over draw labels: all C(n+m, m) relabelings of m family draws and n nulls, with randomized and conservative p (`families.*.perm`).
3. **E-values.** Soft-rank conformal e-value e = (n+1)·s_C/Σ_bag s. Within a family, e-values are **averaged** over draws (valid under any dependence). Per-task e-values are averaged over tasks (`e_task_avg`). Across models, e-values are **multiplied**; this assumes independent model-level experiments.
   - The e-product can be extended as q30a3/q32 finish, with no re-planning (optional continuation; https://arxiv.org/abs/2503.13050).
4. **Pooled test.** A stratified permutation test (labels permuted within model; Monte Carlo B = 20,000, or 4,000 for churn and shift), with Holm correction across families (`nullsets.*.pooled`).

**Equivalence.** Non-rejection is not equivalence. We invert the permutation test under a location-shift model on run-level rates (C rates − δ are exchangeable with the null rates). This gives a 90% confidence set for δ.
- The family is **ε-equivalent** if both one-sided tests reject at 5%, i.e. the 90% set lies inside (−ε, ε).
- `eps_min` is the smallest ε on a 0.25 pp grid for which this holds. The pooled version assumes one common shift across models (`families.*.equiv`, `pooled.*.equiv_common_shift`).

A **conditional task-wise permutation** (labels permuted independently per task) is reported only to show the power gap. It is valid only if tasks are independent within a run given the draw.
- The null SD is consistent with Bernoulli noise but the CIs are wide. SD_obs/SD_pred = 0.63 [0.36, 2.34] on q4, 0.81 [0.52, 1.78] on q8, 1.28 [0.67, 8.0] on q14.
- evidence: `analysis/insights/iter_2/out/p01_equivalence.json` `models.*.clean.null_width_A.ratio_ci95`.

### 1.2 Granularity and power (state these in the paper)

| model | n null | min per-run conformal p = 1/(n+1) | min family p, m = 2: 1/C(n+2,2) | power of exact harm test at Δ = −5 / −10 pp (m = 2) | evidence |
|---|---|---|---|---|---|
| q4 | 4 | 0.20 | 0.067 | 0.59 / 0.74 | `nullsets.A.models.q4.families.awq_w4.perm.p_min`, `power_exact_harm_test` |
| q8 | 7 | 0.125 | 0.028 | 0.61 / 0.98 | same keys, q8 |
| q14 | 3 | 0.25 | 0.10 | 0.23 / 0.43 | same keys, q14 |

- The power model is Gaussian run rates with σ = the observed null SD and 4,000 simulations (`power()` in c01).
- On q4 and q14, a 2-draw family can reject at 5% only through the randomization coin. Power is therefore capped at 0.05·C(n+2,2): 0.75 on q4.
- **The randomized p-value is exact-size but coin-dependent.** Example: q8 gauss1 under S has randomized p_net = 0.005 but conservative p_net = 0.333 (`nullsets.S.models.q8.families.gauss1.perm`).
- Decisions below therefore use the **conservative** p. Randomized p is reported for calibration only.
- A single-draw conformal test at α = 0.05 needs n ≥ 19 null draws. A 2-draw family test needs n ≥ 5 **per prompt stratum**.

### 1.3 Results, per model (null set A, conservative p; Δ in pp)

| family | q4 Δ / p_harm / p_churn | q8 Δ / p_harm / p_churn | q14 Δ / p_harm / p_churn | p01 TOST ±5 pp (q4 / q8 / q14) |
|---|---|---|---|---|
| awq_w4 | +0.9 / 0.73 / 0.067 | −2.9 / 0.19 / **0.028** | −3.8 / 0.20 / 0.20 | incon. / incon. / incon. |
| gptq_w3 | +1.5 / 0.87 / 0.067 | +0.7 / 0.64 / **0.028** | −4.5 / 0.20 / 0.10 | incon. ×3 |
| gptq_w4 (4 draws) | +2.1 / 0.79 / **0.029** | −2.9 / 0.051 / **0.003** | −4.7 / 0.14 / **0.029** | incon. ×3 |
| rtn_w4 | −2.1 / 0.19 / **0.029** (4 draws) | −0.5 / 0.56 / **0.028** | −7.4 / 0.10 / 0.10 | incon. ×3 |
| rtn_w8 | −0.3 / 0.53 / 0.20 | −1.7 / 0.28 / 0.33 | −5.9 / 0.20 / 0.20 | incon. ×3 |
| gauss0.03 (5/5/2 draws) | **+4.2 (p_net 0.024)** / 1.0 / 0.23 | −0.3 / 0.49 / **0.048** | −5.0 / 0.20 / 0.20 | above / **equiv.** / incon. |
| gauss0.3 | +3.3 / 0.80 / 0.067 | +1.8 / 0.86 / **0.028** | −1.4 / 0.40 / 0.60 | incon. ×3 |
| gauss1 (4/2/2 draws) | −0.9 / 0.37 / **0.029** | **−6.6 / 0.028** / **0.028** | −7.4 / 0.10 / 0.10 | incon. ×3 |

evidence (all cells): `analysis/insights/iter_2/out/c01_conformal_equivalence.json` `nullsets.A.models.<m>.families.<f>.{delta,perm}`. The p01 column is `families.<f>.p01_tost.verdict_5pp`, copied from `out/p01_equivalence.json`, whose snapshot is 05:06Z and still included q4 `null_n3` with 58 tasks.

**Rate.** Only two conservative rejections occur on single models:
- q4 gauss0.03 lies **above** the null. It stays above in the canonical-prompt stratum S (Δ +5.2 pp, p_net = 0.048 = 1/21).
- q8 gauss1 lies below (p_harm = 1/36).

This agrees with p01 ("above-null" for q4 gauss0.03) and with the canonical-prompt concern of SURVEY idea 4 (`docs/insights/SURVEY.md#ideas-from-recent-work`).

**Churn.**
- On q8, every quantized W≤4 family has conservative p_churn ≤ 0.028, the 2-draw floor.
- On q4, GPTQ-W4 and RTN-W4 (4 draws) reach 0.029. AWQ-W4 and GPTQ-W3 sit at their 2-draw floor of 0.067.
- The observed churn is 0.18–0.26 against permutation medians of 0.13–0.17 (`perm.churn_obs`, `perm.churn_null_median`).

**ε-equivalence on one model.** It is attainable only when C(n+m,m) ≥ 20, and passes ±5 pp for just:
- q4 gauss1 (ε_min 4.25 pp);
- q8 gauss0.03 (3.0 pp);
- q8 free zone (2.75 pp).

All other attainable cells have ε_min 5.5–13.5 pp (`families.*.equiv.eps_min`). The draw-level interval is wider than the task-bootstrap TOST (p01) because it counts the draw as the unit. That is the honest unit for "is this checkpoint a re-roll".

### 1.4 Results, pooled over q4 + q8 + q14 (stratified permutation, common shift)

| family | Δ̄ (pp) | 90% set for δ (pp) | ±5 pp / ±7.5 pp | p_harm (Holm) | churn p (Holm) | e_harm product | evidence |
|---|---|---|---|---|---|---|---|
| awq_w4 | −1.9 | [−4.5, +0.75] | yes / yes | 0.11 (0.79) | 0.001 (**0.007**) | 3.4 | `nullsets.A.pooled.awq_w4` |
| gptq_w3 | −0.8 | [−3.25, +2.25] | yes / yes | 0.32 (1.0) | 0.0005 (**0.0045**) | 0.46 | `…pooled.gptq_w3` |
| gptq_w4 | −1.8 | [−4.75, +1.0] | yes / yes | 0.15 (0.81) | 0.00025 (**0.003**) | 5.7 | `…pooled.gptq_w4` |
| rtn_w4 | −3.3 | [−5.75, −0.5] | **no** / yes | 0.025 (0.25) | 0.00025 (**0.003**) | 7.3 | `…pooled.rtn_w4` |
| rtn_w8 | −2.6 | [−5.5, +0.25] | **no** / yes | 0.080 (0.72) | 0.056 (0.22) | 2.6 | `…pooled.rtn_w8` |
| gauss0.03 | −0.4 | [−2.75, +2.5] | yes / yes | 0.40 (1.0) | 0.024 (0.12) | 0 | `…pooled.gauss0.03` |
| gauss0.1 | −1.9 | [−4.75, +1.25] | yes / yes | 0.13 (0.81) | 0.94 (0.94) | 0.92 | `…pooled.gauss0.1` |
| gauss0.3 | +1.2 | [−1.5, +4.25] | yes / yes | 0.77 (1.0) | 0.0055 (**0.033**) | 0 | `…pooled.gauss0.3` |
| gauss1 | −5.0 | [−7.5, −2.25] | **no / no** | 0.0024 (**0.026**) | 0.0005 (**0.0045**) | **21.7** | `…pooled.gauss1` |
| free zone (gauss0.03 + gauss0.1 + rtn_w8) | −1.0 | [−3.0, +1.0] | yes / yes | 0.21 | 0.11 | 1.3 | `…pooled.free_zone` |

- **k = 1 is the only family that is harmful after correction.** Its e-value product (21.7 ≥ 1/0.05) rejects on its own. With Bonferroni over 11 families, the e-threshold is 220, which it does not reach.
- **Sensitivity B** (gauss0.03 admitted to the null) sharpens this. gauss1 has p_harm Holm 0.0005, and rtn_w4 has Holm 0.042 (`nullsets.B.pooled`).
- **Sensitivity S** (the exact version within a prompt stratum) can be pooled only for gauss families on q4 + q8. There, **no** family is ±5 pp-equivalent (ε_min 5.5–10.75 pp) and nothing survives Holm (`nullsets.S.pooled`).
- The pooled ±5 pp equivalences in the table therefore rest on null set A. Why A is a fair comparison:
  - Mixing the strata makes the churn and net tests **conservative**. The true labeling pairs Q_n1 with its nonce-mate null_n1, and relabelings that group the canonical pair {bf16, eager} are more extreme.
  - This is an argument, not a theorem. E12 below removes the need for it.

## 2. Open-loop → closed-loop conformal prediction (A2-11)

- **Unit.** One E3 cell. Models with E3 at the snapshot are q4 (19 cells with a closed-loop target) and q8 (12) (`c02_openloop_conformal.json` `models`, `cells`).
- **Coverage for other models.** The script re-runs unchanged when `analysis/openloop/a6k2/{q14,q30a3,q32}` appear (the queued `*_ol_*` tasks).
- **Targets.**
  - The per-decision first-divergence hazard, continuity-corrected (ev + 0.5)/(risk + 1). It is pooled over the cell's runs, paired as in p02 (`c02…py` `closed_loop`).
  - Success Δ against the task-level null mean (null set A).

| target | predictor | pooled jackknife+ LOO coverage, 80% / 90% | median width 80% / 90% | leave-one-model-out coverage, 80% / 90% | evidence |
|---|---|---|---|---|---|
| hazard | identity: ĥ = open-loop decision-any-flip (0 parameters) | — | — | q4 held out 0.63 / 0.63; q8 held out 1.0 / 1.0 | `identity.hazard` |
| hazard | logit-linear (slope 1.59) | 0.81 / 0.90 | 0.14 / 0.17 (probability) | q4 held out (trained on q8) 0.58 / 0.63; q8 held out 0.92 / 1.0 | `jackknife_plus.hazard`, `lomo.hazard` |
| success Δ | linear in log10 flip rate | 0.80 / 0.90 | 9.1 / 15.8 pp | q4 held out 0.61 / 0.83; q8 held out 0.92 / 1.0 | `jackknife_plus.delta`, `lomo.delta` |

- **Divergence is predictable.** Spearman(open-loop flip, closed-loop hazard) = 0.989 over 31 cells. The median |logit residual| of the zero-parameter identity is 0.26, and closed-loop hazards are higher on average (+0.14 logit) (`identity.hazard`).
- **Coverage does not transfer across models.** Calibrating on q8 under-covers q4 (0.58–0.63). The q8-trained slope is 1.28 and the q4-trained slope is 1.67 (`lomo.hazard.*.fit`). Cells are design points and models are a distribution shift, so coverage is empirical, not guaranteed. With 2 models, LOMO is two data points.
- **Damage is not predictable from open-loop features at this n.** The residual SD of Δ is 0.0391 and the SD of Δ itself is 0.0389 (`jackknife_plus.delta.resid_sd`, `y_sd`). Valid 90% intervals are about ±8 pp wide.
- **Consequence for C4** (`docs/insights/PLAN_iter3.md`): the open-loop probe can certify *divergence* risk. It cannot decide a ±5 pp *damage* tolerance. A C4 gate must fall back to closed-loop runs for damage.

## 3. Novelty

Conformal methods in LLM evaluation (2024–2026) cover four settings:
- **Judge scores:** interval-valued LLM-as-a-judge ratings (https://aclanthology.org/2025.emnlp-main.569/, https://arxiv.org/abs/2609.06367).
- **Elo across held-out models:** split conformal with models as the exchangeable unit (https://arxiv.org/abs/2606.13221). This is the closest precedent for our LOMO.
- **Agent trajectories:** error attribution (https://arxiv.org/abs/2605.06788), argument-role risk control for tool calls (https://arxiv.org/abs/2607.24343), and e-process verifiers (https://arxiv.org/abs/2512.03109).
- **Compressed models:** the model's own uncertainty sets (https://arxiv.org/abs/2606.01850).

In a 7-query sweep we found no work that tests a compressed checkpoint's *closed-loop run* for exchangeability with a perturbation-null family, and none that conformalizes an open-loop → closed-loop prediction. Details: `docs/insights/SURVEY.md#t8-conformal-methods-in-llm-and-agent-evaluation-iter-2`. Re-sweep before submission.

## 4. Paste-ready text

**Framework (definition + test).**
> *Perturbation equivalence as exchangeability.* A closed-loop run is one draw from the distribution induced by the evaluation's nuisance randomness (prompt nonce, serving numerics). We call an intervention C *perturbation-equivalent* for model M if the task-outcome vectors of C's runs are exchangeable with those of M's null family N (runs differing from the reference only by such nuisance). Given n null runs and m runs of C on T tasks, we test this hypothesis with an exact permutation test over run labels, using three statistics: the net success difference, its one-sided (harm) version, and the task-profile distance mean_t |ȳ_C(t) − ȳ_N(t)|, which detects re-allocation of successes across tasks at an unchanged rate. For a single run this is a full-conformal p-value with granularity 1/(n+1), and with m draws it is 1/C(n+m, m). Across models we combine by stratified permutation, and as an anytime-valid alternative by multiplying soft-rank conformal e-values. Failing to reject is not evidence of equivalence. For that we invert the permutation test under a location shift of the run-level success rate. C is ε-equivalent if the resulting 90% set lies inside (−ε, ε), i.e. two one-sided tests at 5%. Because the run, not the task, is the exchangeable unit, the test is exact under H0 without assuming independence across tasks. The price is that its resolution is set by the number of null draws per prompt stratum: n ≥ 19 for a single-run test at 5%, and n ≥ 5 for a two-draw family.

**Results.**
> On q4, q8 and q14 (4, 7 and 3 eligible null draws), no single-model two-draw family can be declared ±5 pp-equivalent at the draw level. Only three cells attain it at all: q4 k=1 (4 draws) and q8 k=0.03 and the q8 free zone (5–9 draws), with ε_min = 2.75–4.25 pp. Pooling the three models by stratified permutation, AWQ-W4, GPTQ-W3/W4 and Gaussian k ≤ 0.3 are ±5 pp-equivalent (90% sets within [−4.75, +4.25] pp). RTN-W4 and RTN-W8 are equivalent only at ±7.5 pp. These pooled statements use a null family that mixes canonical and nonce prompts. Within a single prompt stratum, the current null draws are too few to certify ±5 pp for any family. Gaussian k = 1 is worse than the null (Δ = −5.0 pp, 90% set [−7.5, −2.25] pp; Holm-adjusted p = 0.026; e-value 21.7). Rate equivalence does not imply behavioural equivalence. The same quantized families re-allocate successes across tasks beyond what null draws do (pooled task-profile distance 0.19–0.25, against per-model permutation medians of 0.13–0.17; pooled Holm-adjusted p ≤ 0.007 for AWQ-W4, GPTQ-W3, GPTQ-W4 and RTN-W4). Open-loop decision-flip rates predict the closed-loop per-decision divergence hazard (Spearman 0.99; jackknife+ coverage 0.81/0.90 at nominal 0.80/0.90, interval width 0.14–0.17). They carry no information about the success change (residual SD equal to the outcome SD). The open-loop probe can therefore screen for divergence but not certify damage.

(Every number in these two paragraphs is in the tables of §1.2–§2, with the evidence keys given there.)

## 5. Design flaws and proposals

1. **F-C1: prompt strata and shared nonces.** This threatens the pooled equivalence claim.
   - The flaw: quantized cells reuse null nonces n1/n2, and gauss cells use the canonical prompt, of which only 2 null runs exist per model. The exact within-stratum test (S) therefore has n = 2–3.
   - **E12**: add nonce nulls n6–n8 for q4, q8 and q14. This gives S-stratum n = 6 for nonce families once q4/q14 n3–n5 finish, so p_min = 1/28 for 2 draws.
   - Cost ≈ 2.4 GPU-h. Basis (`/data/ziyangs/cloq_work/queue/done/*.json` `seconds`):
     - `a6k2_q8_bf16` (6 runs) 2,680 s;
     - `a6k2_q4_bf16` 2,243 s;
     - `a6k2_q14_gauss0.1_s1` (1 run) 1,968 s.
   - Ready-to-queue spec, one per model (replace q4 with q8 or q14, and keep the node rule of the redo tasks):
   ```json
   {"id": "a6k2_q4_null_extra", "kind": "eval", "model": "q4", "arm": "bf16", "ckpt": {"kind": "bf16"},
    "runs": [{"run_id": "a6k2_q4_null_n6", "task_file": "manifests/eval_tasks_v0.json", "nonce": "c3e18a52"},
             {"run_id": "a6k2_q4_null_n7", "task_file": "manifests/eval_tasks_v0.json", "nonce": "71b5d0e9"},
             {"run_id": "a6k2_q4_null_n8", "task_file": "manifests/eval_tasks_v0.json", "nonce": "2a9f64cd"}],
    "priority": -3, "deps": []}
   ```
2. **E13: nonce rule for new cells.** This costs 0 GPU-h (a rule for `make_tasks.py`).
   - New nonce'd cells (PLAN_iter3 X1 real formats, X2 second family) should use nonces **disjoint** from the null nonces, e.g. two fresh nonces per model, so that S needs no dropping.
   - For canonical-prompt families, the canonical stratum stays at bf16 + eager. Either state A as primary with the conservativeness argument (§1.4), or give gauss cells nonces in future families.
3. **F-C2: the C4 gate cannot certify damage at 85 tasks** (§2). This is not a compute fix. Reword C4 to "divergence gate + closed-loop damage test", or wait for X3 (more tasks).
4. **Holm vs e-values.** Report Holm-adjusted permutation p as primary and the e-product as the anytime-valid companion that q30a3/q32 can extend. Cost: 0.
