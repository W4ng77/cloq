**TL;DR** Pre-registration (2026-09-29, before any closed-loop outcome of the confirmatory units below was analysed) of the
iteration-4 confirmatory tests: (H1) same-method recalibration produces checkpoint-level net effects beyond nonce noise
("checkpoint lottery"); (H2) a checkpoint's net effect replicates across nonce draws; (H3) a checkpoint's behavioural
fingerprint persists on disjoint task halves; (H4, secondary) quantizer vs size-matched random checkpoints differ in
coherence. Confirmatory units are only the NEW checkpoints listed in §1. Registration record = the git commit that
adds this file (its sha256 is logged in RESEARCH_LOG W22). Amendments go in §7 with date and reason, never by editing §1–6.

# Pre-registration, iteration 4

Motivation and review context: `docs/insights/STORYLINE_v5.md`, `paper/review_storyline_v5.md` (action 1),
`docs/insights/iter_4_disposition.md` (exploratory W18 results that generated these hypotheses).

## 1. Confirmatory units (fixed now)
| Set | Checkpoints | Draws (fresh nonces) | Models |
|---|---|---|---|
| RECAL | GPTQ-W4 d3, d4; AWQ-W4 d3, d4 (calibration draws c3, c4; `configs/draws_extra.json` c4) | q1 = 6d1f0b3e, q2 = f07a5c21 | q4, q8 |
| RAND | Gaussian k=1 fixed checkpoints, seeds s2, s4, s5 | q1, q2 | q4, q8 |
Task ids: `a6k2_{q4,q8}_{gptq,awq}_w4_d{3,4}`, `a6k2_{q4,q8}_churnctl_k1_s{2,4,5}`. 20 checkpoints × 2 draws = 40 runs.
Reference null: BF16 nonce draws n1–n8 of the same model (nonce stratum, NULL_RULE). Tasks: the 85 development tasks
(q4: 84, airline 45 excluded as in W17). Existing checkpoints (d1, d2, earlier Gaussian seeds, other methods) are
used only for secondary/descriptive analyses, never inside a confirmatory test.

## 2. Outcomes and statistics
- Task outcome y ∈ {0,1} = τ² official success (db_match), per (run, task).
- Net effect of a draw: Δ = mean_tasks(y) − mean over null draws of mean_tasks(y).
- Checkpoint net effect: mean of its two draws' Δ.
- φ (overdispersion): between-checkpoint variance of checkpoint net effect within a set (per model), minus the
  within-checkpoint (draw) variance component, divided by the variance expected under independent task landing given
  each checkpoint's observed turnover (the P1 estimator in `analysis/insights/iter_4/p1_overdispersion.py`, applied
  unchanged). Test: permutation of draw labels across checkpoints within (model, set), B = 5000, one-sided φ > 1.
- Draw-replication r: Pearson correlation of Δ(q1) vs Δ(q2) across checkpoints of a set, pooled over models after
  centring per model. Test: permutation of q2 labels within model, one-sided r > 0.
- Split-task fingerprint F_split: behaviour-shift vectors (the 12 P2 features, `p2_dispositions.py`) computed for
  draw q1 on a random half of tasks and for draw q2 on the complementary half (100 random splits, averaged);
  F_split = mean same-checkpoint cosine − mean different-checkpoint cosine within (model, set). Test: permutation of
  checkpoint labels, one-sided F_split > 0.

## 3. Hypotheses
| id | Hypothesis | Test | Set | Role |
|---|---|---|---|---|
| H1 | Recalibration lottery: φ_RECAL > 1 | §2 φ, pooled over q4, q8 (sum of per-model numerators / sum of denominators) | RECAL | primary |
| H2 | Net effect replicates across nonces: r > 0 | §2 r | RECAL | primary |
| H3 | Fingerprint persists on disjoint task halves: F_split > 0 | §2 F_split, pooled | RECAL ∪ RAND | primary |
| H4 | Coherence differs between quantizer recalibrations and size-matched random checkpoints: φ_RECAL − φ_RAND ≠ 0 | permutation of set labels within model, two-sided | RECAL vs RAND | secondary; with 2 models × 3–4 checkpoints it is underpowered, so a null result will be reported as "not detected", not as "no difference" |
Multiplicity: Holm over H1–H3 at α = 0.05. H4 reported with its own p and CI, outside the Holm family.
Directional prediction for H4 (stated, not tested as primary): φ_RECAL > φ_RAND.

## 4. Secondary (descriptive, pre-specified)
- Per model and per domain (retail, airline) versions of H1–H3.
- Sensitivity: exclude episodes ending in max_steps; exclude context-overflow failures.
- Variance components of checkpoint net effect: method vs checkpoint vs nonce, using d1–d4 where available.
- Open-loop (E3, E4-2) predictors of checkpoint net effect and act-share shift, on the new checkpoints (open-loop
  outputs for d3/d4 already exist; they are predictors, not outcomes, and were produced before any closed-loop outcome).

## 5. Data rules
- A run enters only through the integrity gate (`analysis/insights/iter_2/integrity.py`); episodes with an outage
  infrastructure error are rerun, context overflow counts as failure (W10).
- If a confirmatory run cannot complete by 2026-10-05, the test uses the available checkpoints and says so; no
  replacement checkpoints are drawn after outcomes are seen.
- Analysis runs once, on the first snapshot in which all 40 runs are admitted (or on 10-05), via a script committed
  before that snapshot exists.

## 6. What would change the storyline
- H1 and H2 hold: lead with the checkpoint lottery ("same method, different agent").
- H1 fails or H2 fails: net effects are not checkpoint-specific beyond nonce noise; the lottery is dropped and the
  paper leads with turnover above the numerics floor plus generic fingerprints.
- H3 fails on split halves: fingerprint claims are dropped.

## 7. Amendments
**Amendment 1 (2026-09-29/30, before any confirmatory outcome was computed or inspected).** Clarifications made while
implementing `analysis/insights/iter_4/prereg_h1_h4.py` (commit a4b5c8a) using stand-in checkpoints only; full list and
rationale in `docs/insights/PREREG_iter4_analysis.md` (A1–A18). Substantive ones:
- A1: §1 miscounted. The listed units are 8 RECAL + 6 RAND = 14 checkpoints × 2 draws = **28 runs** (not 20 × 2 = 40);
  the queued tasks and the script use these 28.
- A2: run ids are `a6k2_<m>_{gptq,awq}_w4_d{3,4}_q{1,2}` and `a6k2_<m>_gauss1_s{2,4,5}_q{1,2}` (the `churnctl_*` names are task ids).
- A3/A7/A9: permutation nulls are P1's within-task relabelling (H1), exact enumeration when ≤ 5000 relabellings
  (H2: 576; H4: 1225), otherwise 5000 random; H4 two-sided p = min(1, 2·min one-sided), CI by task bootstrap (B = 2000).
- A5/A6: complete-case tasks over the eligible nonce null (n1–n8 with ≥ 77 tasks) and confirmatory draws; q4 airline
  task 45 removed; success = db_match and not premature; outage infra errors missing, context overflow = failure.
- A8/A17/A18: H3 split scaling, block structure (4 blocks: model × set) and H2 centring as specified in the analysis doc.
- A10: when φ is undefined (E_indep ≤ 0) H4 conditions on relabellings where it is defined and reports their count.
- A12: sensitivity drops a task for the whole model if any confirmatory draw of that model ended in max_steps (or overflow).
- A13: variance components by nested method of moments over GPTQ/AWQ-W4 d1–d4 (secondary).
- A14: the §4 open-loop predictor analysis is a separate, later script (secondary).
No hypothesis, test statistic, unit, α or Holm family changed.
