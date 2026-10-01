# Holdout K planning-precision simulation (telecom DEV only) — 20261001T134838Z

Script `analysis/fork/holdout_k_planning.py`; snapshot `analysis/insights/iter_3/out/snapshot_auto_20261001T1344Z.json`; seed 20261001; 1000 reps per K, 2000 permutations per rep (the prereg uses 10,000). JSON: `analysis/fork/out/holdout_k_planning_20261001T134838Z.json`.

Purpose: confirm K = 12 is adequate (GPT-6.1 review 4); not a K-selection exercise. No holdout task was read.

## Dev fit (q8, telecom dev, 80 tasks × blocks f01–f06, all 12 cell-blocks complete)

| cell | M rate | G_all | tasks with any M | s_u (95% profile) | s_v | ρ_u (GPTQ–AWQ) | rescue share (beta mean) | dev split-half ρ (descr.) |
|---|---|---|---|---|---|---|---|---|
| q8 gptq_w4_d1 | 0.148 | +0.0271 | 30/80 | 2.22 [1.73, 2.85] | 0.57 | 0.80 | 0.59 | +0.63 |
| q8 awq_w4 | 0.123 | -0.0063 | 31/80 | 1.62 [1.26, 2.09] | 0.35 | 0.80 | 0.47 | +0.51 |

Assumptions: holdout_tasks: 34; holdout_persona_mix: 11 Easy / 11 Hard / 12 None (dev mix 27/25/28 scaled; holdout ids not read); cells: ['q4 gptq_w4_d1', 'q8 gptq_w4_d1', 'q8 awq_w4']; cell_weights: equal (1/3); q4_gptq_w4_d1: no telecom dev forks exist for q4; parameters borrowed from q8 GPTQ-W4 d1 (flag); cross_cell_task_corr_rho_u: 0.804; cross_cell_block_corr_rho_v: 0.119; rho_v_raw: 0.119; halves: first K/2 vs last K/2 blocks (exchangeable, equivalent to the sha order); repeatability_test: Spearman per cell, equal-weight mean over estimable cells, one-sided, persona-stratified permutation of m_B task labels identical across cells; constant vector -> cell not estimable; G_intervals: t over K block means of the cell-averaged task mean (df K-1); crossed = two-way ANOVA moments, normal

## Fitted dev heterogeneity

| K | 90% CI width G_all, t over blocks (pp) | 95% width t (pp) | 90% width crossed (pp) | P(one-sided 95% t-LB > 0) | P(90% t-CI inside ±3 pp) | P(90% crossed CI inside ±3 pp) | repeatability power / size (α 0.05) | P(endpoint not estimable) | rate levels per half |
|---|---|---|---|---|---|---|---|---|---|
| 6 | 5.72 | 7.29 | 5.35 | 0.197 | 0.15 | 0.148 | 0.989 | 0.0 | 3.55 |
| 8 | 4.65 | 5.81 | 4.6 | 0.277 | 0.247 | 0.238 | 0.997 | 0.0 | 4.18 |
| 12 | 3.56 | 4.36 | 3.74 | 0.397 | 0.412 | 0.385 | 1.0 | 0.0 | 5.27 |
| 16 | 3.09 | 3.75 | 3.28 | 0.469 | 0.49 | 0.454 | 1.0 | 0.0 | 6.17 |

True G_all under the model (equal weight): +0.0156.

## Sensitivity: task heterogeneity s_u halved

| K | 90% CI width G_all, t over blocks (pp) | 95% width t (pp) | 90% width crossed (pp) | P(one-sided 95% t-LB > 0) | P(90% t-CI inside ±3 pp) | P(90% crossed CI inside ±3 pp) | repeatability power / size (α 0.05) | P(endpoint not estimable) | rate levels per half |
|---|---|---|---|---|---|---|---|---|---|
| 6 | 4.16 | 5.31 | 4.0 | 0.152 | 0.431 | 0.471 | 0.455 | 0.0 | 2.68 |
| 8 | 3.5 | 4.37 | 3.46 | 0.176 | 0.626 | 0.628 | 0.569 | 0.0 | 3.03 |
| 12 | 2.78 | 3.41 | 2.82 | 0.241 | 0.783 | 0.789 | 0.757 | 0.0 | 3.66 |
| 16 | 2.37 | 2.88 | 2.43 | 0.306 | 0.886 | 0.88 | 0.863 | 0.0 | 4.21 |

True G_all under the model (equal weight): +0.0082.

## Null: no task heterogeneity (size check)

| K | 90% CI width G_all, t over blocks (pp) | 95% width t (pp) | 90% width crossed (pp) | P(one-sided 95% t-LB > 0) | P(90% t-CI inside ±3 pp) | P(90% crossed CI inside ±3 pp) | repeatability power / size (α 0.05) | P(endpoint not estimable) | rate levels per half |
|---|---|---|---|---|---|---|---|---|---|
| 6 | 3.47 | 4.42 | 3.33 | 0.132 | 0.676 | 0.73 | 0.056 | 0.0 | 2.27 |
| 8 | 2.93 | 3.66 | 2.86 | 0.16 | 0.818 | 0.832 | 0.056 | 0.0 | 2.47 |
| 12 | 2.31 | 2.83 | 2.32 | 0.164 | 0.962 | 0.966 | 0.03 | 0.0 | 2.84 |
| 16 | 2.0 | 2.44 | 2.03 | 0.188 | 0.988 | 0.988 | 0.046 | 0.0 | 3.16 |

Under this null the repeatability column is the test's size; the G columns use the dev G direction.

## Planning alternative of EXTERNAL_REVIEW §F: true G_all = +3 pp (rescue share shifted)

| K | 90% CI width G_all, t over blocks (pp) | 95% width t (pp) | 90% width crossed (pp) | P(one-sided 95% t-LB > 0) | P(90% t-CI inside ±3 pp) | P(90% crossed CI inside ±3 pp) | repeatability power / size (α 0.05) | P(endpoint not estimable) | rate levels per half |
|---|---|---|---|---|---|---|---|---|---|
| 6 | 5.61 | 7.15 | 5.52 | 0.54 | 0.043 | 0.046 | 0.989 | 0.0 | 3.56 |
| 8 | 4.71 | 5.88 | 4.8 | 0.643 | 0.088 | 0.077 | 0.994 | 0.0 | 4.19 |
| 12 | 3.65 | 4.47 | 4.01 | 0.833 | 0.09 | 0.075 | 1.0 | 0.0 | 5.29 |
| 16 | 3.11 | 3.78 | 3.57 | 0.914 | 0.109 | 0.088 | 1.0 | 0.0 | 6.21 |

True G_all under the model (equal weight): +0.0300.

## GPU cost from measured telecom dev logs

| component (per 80-task block) | GPU-h (mean over dev groups) |
|---|---|
| closed_q8_bfpair | 0.72 |
| closed_q8_gptq | 0.86 |
| closed_q8_awq | 0.91 |
| closed_q4_bfpair | 0.66 |
| closed_q4_gptq | 1.65 |
| fork_q8_gptq | 6.58 |
| fork_q8_awq | 5.11 |
| fork_q4_gptq_scaled | 2.4 |

Holdout, K = 12, 3 cells, 34 tasks: **≈ 96.3 GPU-h** (range ×0.7–×1.5: [67.0, 144.0]); ≈ 8.0 GPU-h per block; conservative 194.5 GPU-h (fork costs include failed/killed attempts and q4 fork uses the larger of the two q4/q8 ratios). q4/q8 fork ratio (retail/airline dev) 0.364, closed-loop telecom 1.919. means over measured dev groups; linear in tasks (holdout tasks are a stratified draw of the same base split, so per-task cost is assumed equal); q4 telecom forks were never run, so their cost is scaled; failed attempts excluded from the central figure.

Measured groups (GPU-h, successful attempts / all attempts):

- `closed|q4|awq_w4|fdev1`: 0.78 / 1.75 (2 attempts, 1 failed)
- `closed|q4|bfpair|fdev1`: 1.8 / 1.8 (1 attempts, 0 failed)
- `closed|q4|bfpair|fdev2`: 2.13 / 2.13 (1 attempts, 0 failed)
- `closed|q4|gptq_w4_d1|fdev1`: 5.14 / 5.14 (1 attempts, 0 failed)
- `closed|q4|gptq_w4_d1|fdev2`: 4.75 / 4.75 (1 attempts, 0 failed)
- `closed|q8|awq_w4|fdev1`: 3.68 / 3.68 (1 attempts, 0 failed)
- `closed|q8|awq_w4|fdev2`: 1.79 / 1.79 (1 attempts, 0 failed)
- `closed|q8|bfpair|fdev1`: 2.08 / 2.08 (1 attempts, 0 failed)
- `closed|q8|bfpair|fdev2`: 2.23 / 2.23 (1 attempts, 0 failed)
- `closed|q8|gptq_w4_d1|fdev1`: 2.33 / 2.33 (1 attempts, 0 failed)
- `closed|q8|gptq_w4_d1|fdev2`: 2.85 / 2.85 (1 attempts, 0 failed)
- `forkRA|q4|awq_w4|g1`: 5.6 / 5.6 (1 attempts, 0 failed)
- `forkRA|q4|awq_w4|g2`: 5.79 / 5.79 (1 attempts, 0 failed)
- `forkRA|q4|awq_w4|g3`: 6.12 / 6.12 (1 attempts, 0 failed)
- `forkRA|q4|awq_w4|g4`: 6.66 / 6.66 (1 attempts, 0 failed)
- `forkRA|q4|gptq_w4_d1|g1`: 4.37 / 4.37 (1 attempts, 0 failed)
- `forkRA|q4|gptq_w4_d1|g2`: 4.27 / 4.27 (1 attempts, 0 failed)
- `forkRA|q4|gptq_w4_d1|g3`: 4.79 / 4.79 (1 attempts, 0 failed)
- `forkRA|q4|gptq_w4_d1|g4`: 4.08 / 4.08 (1 attempts, 0 failed)
- `forkRA|q8|awq_w4|g1`: 11.67 / 11.67 (1 attempts, 0 failed)
- `forkRA|q8|awq_w4|g2`: 11.47 / 11.47 (1 attempts, 0 failed)
- `forkRA|q8|awq_w4|g3`: 11.91 / 11.91 (1 attempts, 0 failed)
- `forkRA|q8|awq_w4|g4`: 10.55 / 10.55 (1 attempts, 0 failed)
- `forkRA|q8|gptq_w4_d1|g1`: 13.79 / 13.79 (1 attempts, 0 failed)
- `forkRA|q8|gptq_w4_d1|g2`: 12.34 / 12.34 (1 attempts, 0 failed)
- `forkRA|q8|gptq_w4_d1|g3`: 10.39 / 10.39 (1 attempts, 0 failed)
- `forkRA|q8|gptq_w4_d1|g4`: 11.57 / 11.57 (1 attempts, 0 failed)
- `fork|q8|awq_w4|g1`: 12.68 / 12.68 (1 attempts, 0 failed)
- `fork|q8|awq_w4|g2`: 10.96 / 10.96 (1 attempts, 0 failed)
- `fork|q8|awq_w4|g3`: 7.04 / 20.31 (6 attempts, 4 failed)
- `fork|q8|gptq_w4_d1|g1`: 9.07 / 11.49 (6 attempts, 3 failed)
- `fork|q8|gptq_w4_d1|g2`: 8.56 / 8.56 (1 attempts, 0 failed)
- `fork|q8|gptq_w4_d1|g3`: 21.82 / 33.4 (5 attempts, 2 failed)
