**TL;DR**
- PROVISIONAL (frozen snapshot `20260929T0732Z`; redos, null_extra and churnctl still in flight). One command re-runs everything on a new frozen snapshot: `bash analysis/insights/iter_2/run_all.sh`. The integrity gate admitted 161 of 242 runs. Four *completed* runs still carry abandoned-attempt decisions (W8 dedup missing) and are excluded until main dedups them (E14, 0 GPU-h).
- Churn is not yet a finding. Stratum-matched and pooled over 4 models, W4/W3 quantizers show an excess churn of +0.037 to +0.065 (CIs above 0; Holm-all p ≤ 0.034). The negative controls RTN-W8 and k=0.03 show none. But dose-matched Gaussian k=1 churns more (+0.091), and the fixed-checkpoint control is not in yet, so the verdict is "provisional", not "survives".
- By the pre-declared rule NR1, canonical-prompt and nonce nulls are **not** exchangeable (pooled churn p = 0.0099), so S is primary. Under S, AWQ/GPTQ-W3/GPTQ-W4 stay ±5 pp-equivalent pooled; the k=1 harm result and all Gaussian equivalences become untestable (canonical stratum n = 2). C3's ρ survives dose control (partial ρ = 0.86 [0.67, 0.96]). The cross-model floor prediction degrades from "within 7%" to 5–29%.

# Iteration 2: integrity gate, frozen re-run and the review-v2 statistics items

Input: `paper/review_v2.md`, must-do items 2–5 (W-A, W-B, W-C, W-D). Context: `docs/insights/iter_2_prep.md`, `docs/insights/iter_2_conformal.md`, `docs/RESEARCH_LOG.md` W6–W9.

Scripts live in `analysis/insights/iter_2/` and are read-only over `runs/`, `analysis/openloop/` and the queue. Outputs go to `analysis/insights/iter_2/out/`.

Stable ids, new in this file:
- **A2-12**: integrity gate and frozen snapshot.
- **A2-13**: churn checks.
- **A2-14**: statistics cleanup and null rule NR1.
- **A2-15**: matched-dose check for C3.
- **A2-16**: floor by pairing stratum.
- **E14–E16**: proposals, see §7.

**Status: provisional.** Every number here comes from snapshot `20260929T0732Z`, taken while these were still queued or running:
- 7 `*_redo` tasks;
- `null_extra` for q4/q8/q14;
- the churn controls;
- the q14 W3/W8 cells.

evidence: `analysis/insights/iter_2/out/snapshot_20260929T0732Z.json` (`queue_pending_run_ids`, `excluded`).

## 0. How to re-run

```
bash /data/ziyangs/cloq/analysis/insights/iter_2/run_all.sh                                  # new frozen snapshot + everything + diff
SNAPSHOT=out/snapshot_<id>.json bash /data/ziyangs/cloq/analysis/insights/iter_2/run_all.sh  # same frozen set again
```

What `run_all.sh` does, in order:
1. Copies the current outputs to `out/prev_<utc>/`.
2. Runs `integrity.py`, which writes `out/snapshot_<utc>.json`.
3. Exports `CLOQ_SNAPSHOT`.
4. Runs p00–p07, c01, c02, n01, k01, d01 and f01.
5. Writes `out/diff_<utc>.md` and `out/diff_<utc>.json`, which compare every headline number against the previous outputs.

How the frozen set is enforced (`analysis/insights/iter_2/common.py`: `SNAP`, `in_snapshot`, `check_frozen`, `runs_for`):
- `runs_for`, `outcomes`, `load_many`, and the direct run references in p02, p03 and c02 see only the runs in the manifest.
- Reading a decisions, metrics or trajectory file whose size or mtime changed after the freeze raises an error.
- Every output JSON carries `_frozen_snapshot`.
- Fixed-checkpoint controls (`*_q<k>`) are hidden from p0x and c0x. `k01_churn.py` picks them up automatically once both runs pass the gate (`runs_for(..., ctl=True)`).

Runtime: 2 min 28 s on the login node (this session).

## 1. Integrity gate (A2-12; review W-A)

Script: `analysis/insights/iter_2/integrity.py`. Manifest: `out/snapshot_20260929T0732Z.json`. Log: `out/integrity.log`.

Checks per run-domain (docstring of `integrity.py`):

| check | rule | on failure |
|---|---|---|
| G1 | `status.json` is `completed` and `metrics.json` is present | run excluded |
| G2 | `infrastructure_error` episodes | listed as missing (not a failure) |
| G3 | exactly one `trajectory_id` per task in `decisions.jsonl` | run excluded |
| G4 | decision records = assistant turns (or −1 for the greeting); `decision_idx` without gaps; one trajectory record per task; metrics, trajectory and manifest task sets equal; record `run_id` = directory | run excluded |
| G5 | `environment.json` `prompt_nonce` = the nonce in the queue task (`runs[].nonce`); one system-prompt hash per run-domain, consistent across runs with the same (model, domain, nonce) | run excluded |
| G6 | the run id is not in a pending `*_redo` task | run excluded |
| G7 | numerics canary for canonical BF16 runs | informational |

Results:

| item | value | evidence |
|---|---|---|
| runs scanned / admitted / excluded | 242 / 161 / 81 (a6k2 admitted 143; legacy a6000 admitted 18, excluded 39) | `snapshot_…json` `n_runs_scanned`, `n_frozen`, `n_excluded`, `frozen`, `excluded` |
| a6k2 excluded: not completed (running or partial) | 30 run ids (incl. q14 `null_n2..n4`, q14 W3 cells, churnctl `*_q1/_q2`, q4/q8 `gauss1_s3`, q8 `null_n6..n8`) | `excluded` |
| a6k2 excluded: pending `*_redo` | 8 (q4 `null_n3..n5`, q4 `gauss2_s1/s2`, `gauss3_s1`, q8 `rtn_w3_n1/n2`) | `excluded`, `queue_pending_run_ids` |
| **a6k2 excluded: completed but not deduplicated (G3)** | **4: `a6k2_q4_gauss1_s4` (airline, 1 task), `a6k2_q4_rtn_w4_n3` (airline, 1), `a6k2_q8_gauss0.001_s1` (airline, 7), `a6k2_q8_gauss1_s4` (retail 8, airline 2)** | `detail.<run>.<dom>.tasks_multi_trajectory` |
| infra episodes treated as missing (admitted runs) | 6: q4 `null_n2`, `gauss0.001_s2`, `gptq_w4_d1_n1/n2` (airline task 45 each), q4/q8 `bf16_cal` | `frozen.<run>.<dom>.infra_missing` |
| nonce and system-prompt consistency | 0 G5 failures among admitted runs; 0 inconsistent (model, domain, nonce) groups; 0 hashes shared across nonces | `system_prompt_inconsistent_groups`, `system_prompt_shared_across_nonces` |
| canary | all 60 admitted canonical a6k2 BF16 run-domains have `ok`; legacy a6000 runs have no record (pre-W3) | `detail.*.*.canary` |
| NULL_RULE precedence | the snapshot records NULL_RULE.md sha256 `65711ed7…`, mtime 07:13:54Z, before the snapshot at 07:32Z | `snapshot_…json` `null_rule` |

Findings for main:
- **G3 finding.** The one-off W8 dedup (06:45Z) did not reach runs that finished afterwards under workers that still ran the old `run_arm`. The in-line dedup in `cloq/run_arm.py` (L266) is committed but was not yet loaded by those workers.
  - `common._parse` keys records by (task, decision_idx), so for these 4 runs it would silently mix attempts.
  - They are therefore excluded. Fix: E14.
- **q14 canonical/null runs are admitted with a warning.** `todo/a6k2_q14_bf16.json` (requeued after a runner crash) will rewrite `a6k2_q14_bf16` and `null_n1..n5`.
  - `a6k2_q14_null_n2/retail` is a stale partial (status `running` since 20:53) and is excluded.
  - Consequence: q14's null is {bf16, n1, n6, n7, n8}, not {bf16, n1, n2}.
  - evidence: `snapshot_…json` `detail.a6k2_q14_bf16.*.warn`, `excluded.a6k2_q14_null_n2`.
- **Orphan runs.** `a6k2_q14_{gptq_w3,rtn_w3,rtn_w8}_n*` are not written by any queue task (G5 warning "intended nonce unknown") and are partial. Main should check whether they belong to a task that was lost from the queue.
  - evidence: `detail.a6k2_q14_rtn_w8_n1.retail.warn`.

### 1.1 What the recompute changed (review Q4)

Full list: `analysis/insights/iter_2/out/diff_20260929T0732Z.md`, section "Key numbers". It records 1,771 changed headline leaves. Most of the change comes from composition (the null sets changed) and from new keys; dedup itself changed little.

| number (doc where quoted) | before (05:45Z) | now (07:32Z) | why | evidence (`out/…`) |
|---|---|---|---|---|
| q4 / q8 eager hazard (C1 floor) | 0.1703 / 0.104 | 0.1703 / 0.104 | unchanged: dedup did not touch these runs | `p02_ties.json` `closed_loop.<m>.a6k2_<m>_bf16_eager.hazard` |
| q4 floor median (pooled cells) | 0.1887 | 0.2051 | nonce nulls n6–n8 in, n3 out | `p02_ties.json` `cross_model.q4.observed_floor_hazard_median` |
| q8/q14 cross-model floor prediction (iter_2_prep A2-3 item 5, "within 7%") | 0.120 vs 0.113; 0.151 vs 0.152 | pooled 0.133 vs 0.114 (+17%), 0.166 vs 0.169 (−2%) | pooled median depends on the nonce share (§6) | `f01_floor_strata.json` `models.<m>.calibrated_prediction.pooled` |
| ρ(open-loop flip, hazard) (C3) | 0.989 | 0.988 | — | `c02_openloop_conformal.json` `identity.hazard.spearman` |
| jackknife+ coverage, hazard 80/90 | 0.806 / 0.903 | 0.80 / 0.90 | — | `jackknife_plus.hazard.{80,90}.coverage_loo` |
| resid SD / SD of Δ (C4 refuted) | 0.0391 / 0.0389 | 0.0369 / 0.0372 | still resid ≈ SD: C4 stays refuted | `jackknife_plus.delta.{resid_sd,y_sd}` |
| q4 null draws (A) / SD | 4 / 2.03 pp | 7 / 2.97 pp | n6–n8 added; n3–n5 pending redo | `c01_conformal_equivalence.json` `nullsets.A.models.q4.{null_draws,null_sd}` |
| q14 null draws (A) / SD | 3 / 3.87 pp | 5 / 2.76 pp | n6–n8 added, n2 partial | same keys, q14 |
| pooled Δ RTN-W4, 90% set (A) | −3.3 [−5.75, −0.5], ±5 no | −2.6 [−4.75, −0.75], ±5 yes | more nulls | `nullsets.A.pooled.rtn_w4` |
| pooled Δ RTN-W8, 90% set (A) | [−5.5, +0.25], ±5 no | [−4.25, +0.75], ±5 yes | — | `nullsets.A.pooled.rtn_w8` |
| k=1 pooled harm, Holm (A) | 0.026 | 0.0066 (per statistic), 0.0168 (Holm across all family × statistic) | — | `nullsets.A.pooled.gauss1.p_harm_stratified_mc_holm{,_all}` |
| protocol tally (A2-4): families / null-ref equiv ±7.5 / Flat-Score equiv | 40 / 11 / 2 | 30 / 14 / 2 | 10 families lost to exclusions (W3 cells, q14 W8) | `p07_protocol_tally.json` `total` |

## 2. Churn checks (A2-13; review W-B, Q1, Q2, Q5)

Script: `analysis/insights/iter_2/k01_churn.py`. Output: `out/k01_churn.json`. Log: `out/k01.log`.

**Method.**
- Everything is stratum-matched:
  - canonical-prompt families are tested against K = {bf16, eager};
  - nonce families are tested against the nonce nulls minus the family's nonce-mates.
- Excess churn = observed churn − the median of the exact relabelling distribution. Its 95% CI comes from a joint task bootstrap across models.
- Pooling across models is a stratified permutation.
- Holm is applied across all (family × {net, churn}) pooled tests (m = 24, `k01_churn.json` `holm_all_m`).
- The survival rule was pre-declared in the script docstring before this snapshot was read. Churn "survives" only if all three hold:
  - (a) Holm-adjusted p ≤ 0.05;
  - (b) the excess CI is above 0;
  - (c) the CI lower bound exceeds the fixed-checkpoint control's excess.

**Results (pooled, stratum-matched):**

| family (ref) | models | excess churn [95% CI] | p churn → Holm-all | verdict | evidence (`out/k01_churn.json`) |
|---|---|---|---|---|---|
| AWQ-W4 (S_nonce) | q4 q8 q14 q30a3 | +0.044 [0.024, 0.067] | 0.0016 → 0.034 | provisional (c pending) | `pooled["awq_w4\|S_nonce"]`, `verdict` |
| GPTQ-W3 | q4 q8 q30a3 | +0.065 [0.039, 0.092] | 0.0006 → 0.013 | provisional | `pooled["gptq_w3\|S_nonce"]` |
| GPTQ-W4 | q4 q8 q14 q30a3 | +0.037 [0.021, 0.053] | 5e-5 → 0.0012 | provisional | `pooled["gptq_w4\|S_nonce"]` |
| RTN-W4 | q4 q8 q14 q30a3 | +0.049 [0.026, 0.069] | 5e-5 → 0.0012 | provisional | `pooled["rtn_w4\|S_nonce"]` |
| **RTN-W8 (negative control)** | q4 q8 q30a3 | +0.007 [−0.010, +0.029] | 0.18 → 1.0 | no churn | `pooled["rtn_w8\|S_nonce"]` |
| **Gaussian k=0.03 (negative control, canonical)** | q4 q8 | +0.004 [−0.014, +0.025] | 0.36 → 1.0 | no churn | `pooled["gauss0.03\|S_canonical"]` |
| **Gaussian k=1 (dose-matched to RTN-W4)** | q4 q8 | **+0.091 [0.047, 0.133]** | 0.034 → 0.67 | no (under-powered: canonical K has n = 2) | `pooled["gauss1\|S_canonical"]` |
| Gaussian k=0.3 | q4 q8 | +0.012 [−0.018, +0.059] | 0.22 → 1.0 | no | `pooled["gauss0.3\|S_canonical"]` |
| null vs null (every pair of nonce nulls vs the rest) | per model | mean −0.001 to +0.012; no pair has p ≤ 0.05 | — | calibration OK | `models.<m>.null_vs_null` |

**Answers to the review's questions:**
- **Q2 (q8 under null S).** AWQ, GPTQ-W3 and RTN-W4 all reach p_churn = 0.100, which is the floor p_min = 1/C(5,2) with 3 nonce nulls. GPTQ-W4 gets 0.114. q8 alone therefore cannot reject at 5%; pooling decides.
  - evidence: `models.q8.families.<f>.S_nonce.{p_churn_cons,p_min}`.
- **Q1 (fixed-checkpoint control).** `a6k2_{q4,q8,q14}_churnctl` (k=0.03 s1 × nonces `6d1f0b3e`/`f07a5c21`) is not in the snapshot: q4/q8 are in todo, q14 is running. `controls_present` is empty for every model.
  - Criterion (c) is therefore "pending", and no family can reach "survives".
  - The control will be tested against all nonce nulls (`S_nonce`) and against the quantizers' own reference (`S_nonce_as_quant`).
  - evidence: `k01_churn.json` `controls_present`; `snapshot_…json` `excluded.a6k2_q14_gauss0.03_s1_q1`.
- **Q5 (Flat-Score-style failure-set agreement).** Pearson r between per-task success rates of family and null:
  - quantizers at W4/W3: r = 0.48–0.80;
  - RTN-W8: r = 0.71–0.87;
  - null halves against each other: r = 0.78–0.88.
  - So quantized failure sets agree with the null *less* than null halves agree with each other, but r ≈ 0.5–0.8 is far from "different tasks". Flat Score's ρ ≥ 0.94 comes from 4 reference trials, so the two are not directly comparable.
  - evidence: `models.<m>.families.<f>.S_nonce.flatscore_r_task_rates`, `models.<m>.flatscore_r_null_halves`.

**Reading.** Most of what was called churn is null churn. The excess is small: +0.04 to +0.065, against raw churn of 0.14–0.25.

The excess is real relative to both negative controls, but **it is not specific to quantization**:
- A Gaussian perturbation of the same Frobenius size (k=1) shows at least as much excess (+0.091).
- NR1 (§3) finds that the canonical and nonce null strata *themselves* differ in task profile (pooled p_churn = 0.0099). That is, any shared fixed nuisance factor (here, the prompt) creates its own task profile.

This supports the review's alternative: "any fixed checkpoint above the floor has its own task profile". The churnctl result (fixed k=0.03 checkpoint) and E15 (fixed k=1 checkpoint under fresh nonces) decide it.

The PLAN_iter4 headline ("quantization reallocates capability", `docs/insights/PLAN_iter4.md`) should be worded as "perturbations of W4 size reallocate capability, quantizers included" until E15 is in.

## 3. Statistics cleanup and the null rule (A2-14; review W-C, W-G)

Changes in `analysis/insights/iter_2/c01_conformal_equivalence.py`:

1. **Holm across all statistics.**
   - Pooled: Holm over every (family × {net, harm, churn}) test (`nullsets.<ns>.pooled.<f>.p_*_stratified_mc_holm_all`; m = 33 under A).
   - Per model: Holm over every (family × statistic) conservative exact p (`nullsets.<ns>.models.<m>.families.<f>.perm.p_*_cons_holm_all`, `holm_all_m`).
   - The old per-statistic Holm keys are kept only for the diff.
2. **The e-value product is dropped.** Per-model family e-values are reported (`pooled.<f>.e_per_model`), together with their arithmetic mean (`e_mean_over_models`).
   - An average of e-values is an e-value under any dependence (Vovk & Wang 2021, https://arxiv.org/abs/1912.06116). Tasks, nonces, simulator and harness are shared across models, so a product is not valid.
   - k=1: mean e_harm = 3.86 (per model 2.04 / 5.54 / 4.0). The former product was 21.7. It no longer rejects on its own (it would need ≥ 20).
   - evidence: `c01_conformal_equivalence.json` `nullsets.A.pooled.gauss1.{e_per_model,e_mean_over_models}`.
3. **Pre-declared null rule.** `docs/insights/NULL_RULE.md` (NR1 v1) was written at 07:13:54Z, before this snapshot at 07:32Z; its sha256 is in the manifest. It is implemented in `analysis/insights/iter_2/n01_null_rule.py` → `out/n01_null_rule.json`.

   | model | K / U draws | Δ(K−U) | churn obs vs perm median | p_net / p_churn (cons.) | p_min | NR1 verdict |
   |---|---|---|---|---|---|---|
   | q4 | 2 / 5 | −3.0 pp | 0.170 vs 0.137 | 0.29 / **0.048** | 0.048 | S primary (churn rejects) |
   | q8 | 2 / 5 | +2.6 pp | 0.169 vs 0.144 | 0.33 / **0.095** | 0.048 | S primary (churn rejects at 0.10) |
   | q14 | 1 / 4 | +5.9 pp | 0.194 vs 0.153 | 0.20 / 0.20 | 0.20 | S primary (uninformative) |
   | q30a3 | 1 / 8 | −1.8 pp | 0.153 vs 0.159 | 0.44 / 0.67 | 0.11 | S primary (uninformative) |
   | pooled (4 models) | — | +0.9 pp | 0.172 | 0.48 / **0.0099** | — | rejects |

   evidence: `n01_null_rule.json` `models.<m>`, `pooled`.

   **Verdict V-NR1:** S is primary for every model.

   Canonical and nonce null draws differ in *which* tasks succeed, not in rate. So the exactness claim for null A ("exact under H0") does not hold. The paper must say "exact given an exchangeable null family; our null family has two non-exchangeable strata, and we test within stratum".
4. **Results under S (primary), pooled over q4+q8+q14** (`nullsets.S.pooled`):

   | family | 90% set for δ (pp) | ±5 pp / ±7.5 pp |
   |---|---|---|
   | AWQ-W4 | [−4.25, +1.5] | yes / yes |
   | GPTQ-W3 (q4+q8) | [−4.0, +4.5] | yes / yes |
   | GPTQ-W4 | [−4.25, +1.25] | yes / yes |
   | RTN-W4 | [−5.0, −0.75] | no / yes |
   | RTN-W8 | [−5.25, +1.0] | no / yes |

   - **Every Gaussian family, including k=1, is inconclusive under S**: canonical K has n = 2 per model.
   - The k=1 harm (Holm-all 0.017 under A) therefore rests on the null set that NR1 rejects. Under S its 90% set is [−12.75, +2.25].
   - This is a structural limit: canonical BF16 serving is deterministic, so K can never grow beyond {bf16, eager}. The fix is nonce'd Gaussian cells (E15).
   - The free zone (W-G) is reported per member only. `free_zone` is excluded from Holm, and under S the members stand alone (see above).

## 4. Matched-dose check for C3 (A2-15; review W-D)

Script: `analysis/insights/iter_2/d01_matched_dose.py`. Output: `out/d01_matched_dose.json`. Input: `out/c02_openloop_conformal.json` (27 E3 cells with a closed-loop hazard, q4 + q8).

**Dose** = Frobenius error in RTN-W4 units (k_eq):
- Gaussian k: exact by construction.
- RTN: sqrt(ratio of `mean_rel_weight_err`), which is a squared-norm ratio. Check: Gaussian k = 0.1 gives sqrt ratio 0.1012; RTN-W8 → k_eq 0.062.
- GPTQ/AWQ: bit-matched nominal, since no weight error is recorded (`runs/<run>/quantization.json`).

evidence: `d01_matched_dose.json` `dose`.

| cell set | ρ(flip, hazard) | ρ(dose, hazard) | partial ρ(flip, hazard \| dose) [95% CI] | same, ranks within model | ΔR² from flip over dose + model FE [95% CI] | evidence |
|---|---|---|---|---|---|---|
| all dosed (27) | 0.973 | 0.905 | **0.86 [0.67, 0.96]** | 0.77 [0.19, 0.97] | 0.135 [0.024, 0.26] | `all_dosed` |
| measured dose only (23) | 0.962 | 0.865 | 0.88 [0.69, 0.98] | 0.77 [0.06, 1.0] | 0.077 [0.011, 0.16] | `measured_dose_only` |
| Gaussian only (21) | 0.956 | 0.849 | 0.87 [0.67, 0.98] | 0.79 [0.04, 1.0] | 0.089 [0.005, 0.19] | `gauss_only` |

**Within matched-dose strata**, the rank correlation pooled over q4 k=0.03 (5 seeds), q8 k=0.03 (5 seeds) and q4 k=1 (6 cells) is 0.81, with a one-sided within-stratum permutation p = 0.001.
- The only cross-family stratum (q4, k_eq = 1): GPTQ-W4 has flip 0.034 and hazard 0.45–0.49; AWQ 0.054 / 0.80; RTN-W4 0.064 / 0.74; Gaussian k=1 0.068–0.076 / 0.76–0.98.
- Within that stratum ρ = 0.77, p = 0.051 (n = 6).
- evidence: `within_dose_bands.pooled`, `within_dose_bands.bands`.

**Verdict V-C3:** C3's divergence claim survives the dose control. Open-loop flip rate carries information on hazard beyond dose (partial ρ ≈ 0.86; ΔR² > 0 in every subset). At equal nominal W4 dose, GPTQ both flips and diverges least, which is the "structure vs size" signal.

The paper should report the partial ρ, not the raw 0.99.

Caveats:
- Only 2 models.
- GPTQ/AWQ dose is nominal.
- There is 1 cross-family stratum.
- The q8 GPTQ/RTN E3 cells are missing (c02 `cells.q8`).

## 5. Floor by pairing stratum (A2-16; review Q4, C1)

Script: `analysis/insights/iter_2/f01_floor_strata.py`. Output: `out/f01_floor_strata.json`.

p02's "floor cells" include the nonce nulls, which by A2-3 item 3 sit *above* the floor. So the pooled floor median shifts whenever nonce nulls are added.

| model | same-prompt floor median (n) | nonce-pair median (n) | q4-calibrated prediction error: same-prompt / nonce / pooled | evidence |
|---|---|---|---|---|
| q4 | 0.186 (13) | 0.260 (5) | calibration | `models.q4` |
| q8 | 0.108 (12) | 0.177 (5) | +11% / −5% / +17% | `models.q8.calibrated_prediction` |
| q14 | 0.117 (2; no eager, W8 still running) | 0.172 (4) | +29% / +22% / −2% | `models.q14.calibrated_prediction` |

**Verdict V-C1pred:** the "within 7%" cross-model prediction (`iter_2_prep.md` A2-3 item 5) depended on the null composition. Stratum-matched, it is within 5–11% on q8 and 22–29% on q14. The q14 same-prompt set is only 2 cells: no eager run, and W8 is still running.

Report stratum-matched predictions, and pre-register q30a3/q32 per stratum.

## 6. Design flaws that threaten a headline claim

1. **F-I1: the canonical stratum is capped at n = 2.** Deterministic BF16 serving means any canonical-prompt family (every Gaussian cell) is untestable under the stratum-matched null that NR1 makes primary.
   - This affects the "k=1 harmful", "damage only at k ≥ 2" and the Gaussian free-zone equivalences.
   - Fix: E15, nonce'd Gaussian cells.
2. **F-I2: churn is dose, not quantization, until shown otherwise.** Gaussian k=1 excess churn ≥ quantizer excess (§2).
   - Also, a shared fixed prompt produces churn between null strata (NR1).
   - Fix: the churnctl result (queued) plus E15.
3. **F-I3: the W8 dedup is incomplete.** Four completed runs were excluded (§1). Fix: E14.
4. **F-I4: pooled model sets differ between scripts.** c01 pools q4+q8+q14 (`CLOQ_POOL`); k01 and n01 pool every model with data (adding q30a3).
   - Report k01 as the churn number and c01 as the rate number, or set `CLOQ_POOL` to match.

## 7. Proposals (for main; costs from `queue/done/*.json` `seconds`)

| id | what | cost | needed for | evidence |
|---|---|---|---|---|
| E14 | Run `python scripts/a6000/dedup_decisions.py runs/a6k2_q4_gauss1_s4/*/ runs/a6k2_q4_rtn_w4_n3/*/ runs/a6k2_q8_gauss0.001_s1/*/ runs/a6k2_q8_gauss1_s4/*/`, and confirm that every worker runs the post-W8 `run_arm` | 0 GPU-h | F-I3 | `snapshot_20260929T0732Z.json` `excluded` |
| E15 | Fixed Gaussian k=1 s1 checkpoint under the churnctl nonces, on q4/q8/q14 (spec below). It is dose-matched to RTN-W4, nonce'd, and at a fixed checkpoint. It gives the stratum-S Gaussian damage test (F-I1) and the "structure vs size" churn test (F-I2). k01 picks it up automatically as `ctl:gauss1_s1`. | 3 tasks × 2 runs; about 0.5–1.0 GPU-h per run (`a6k2_q4_gauss1_s4_redo` 1,724 s, `a6k2_q14_gauss1_s1` 1,848 s, `a6k2_q8_gauss1_s2` 3,498 s) → **about 3.5–6 GPU-h** | F-I1, F-I2 | `queue/done/a6k2_q4_gauss1_s4_redo.json`, `a6k2_q8_gauss1_s2.json`, `a6k2_q14_gauss1_s1.json` |
| E16 | Re-run `bash analysis/insights/iter_2/run_all.sh` once the redos, null_extra and churnctl are in done/, and replace every provisional number here | about 3 min CPU | all | this file |

E15 spec (one per model; replace q4 with q8 and q14). The nonces are the churnctl pair, disjoint from null n1–n8:

```json
{"id": "a6k2_q4_churnctl_k1", "kind": "eval", "model": "q4", "arm": "gauss", "ckpt": {"kind": "gauss", "k": 1.0, "seed": 1},
 "runs": [{"run_id": "a6k2_q4_gauss1_s1_q1", "task_file": "manifests/eval_tasks_v0.json", "nonce": "6d1f0b3e"},
          {"run_id": "a6k2_q4_gauss1_s1_q2", "task_file": "manifests/eval_tasks_v0.json", "nonce": "f07a5c21"}],
 "priority": -3, "deps": []}
```

## 8. Files

| path | role |
|---|---|
| `analysis/insights/iter_2/integrity.py` | gate + manifest (A2-12) |
| `analysis/insights/iter_2/common.py` | frozen-snapshot enforcement (`SNAP`, `in_snapshot`, `check_frozen`, `runs_for(ctl=)`) |
| `analysis/insights/iter_2/run_all.sh` | one command |
| `analysis/insights/iter_2/diff_outputs.py` | headline diff |
| `analysis/insights/iter_2/n01_null_rule.py` | NR1 (A2-14) |
| `analysis/insights/iter_2/c01_conformal_equivalence.py` | Holm-all, e-mean (A2-14) |
| `analysis/insights/iter_2/k01_churn.py` | churn (A2-13) |
| `analysis/insights/iter_2/d01_matched_dose.py` | matched dose (A2-15) |
| `analysis/insights/iter_2/f01_floor_strata.py` | floor strata (A2-16) |
| `docs/insights/NULL_RULE.md` | pre-declared rule NR1 |
| `analysis/insights/iter_2/out/snapshot_20260929T0732Z.json` | the frozen snapshot |
| `analysis/insights/iter_2/out/diff_20260929T0732Z.{md,json}` | the diff |
| `analysis/insights/iter_2/out/prev_20260929T0732Z/` | the pre-dedup outputs (05:45Z) |
