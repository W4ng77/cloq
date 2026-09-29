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
(none)
