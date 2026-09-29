**TL;DR** On the gated snapshot 20260929T1937Z (q4/q8/q14/q30a3/q32; l8 has no runs), with a hierarchical paired bootstrap (tasks + null draws + checkpoints + draws), three results survive Holm. W4 turnover is above a numerics floor, pooled over 5 models: RTN +0.19 [0.10, 0.30], GPTQ +0.15 [0.07, 0.24], AWQ +0.16 [0.07, 0.25]. RTN also re-rolls no more than random-sign error of RTN magnitude (NI, margin 0.10). Four things fail or are unidentified. (1) λ-equivalence of W4 methods at ±0.10 is **not** shown: the point differences are small but no TOST passes. (2) c is **unidentified** for RTN on every model, so "c follows method" cannot be tested at all. (3) The same-method checkpoint gap in Δ (q4 GPTQ d1−d2 +9.6 pp [1.8, 17.4]) is larger than any method gap. (4) The open-loop probe adds little beyond dose for λ: partial ρ 0.39 [−0.03, 0.73]. The 0.86 figure was the flip-vs-hazard statistic, not a λ correlation.

# R3/R4 statistics for the λ–c turnover analysis (review_storyline_v4 R3, R4)

Date 2026-09-29. Answers `paper/review_storyline_v4.md` W1–W8, R3, R4 and Q2/Q5. 0 GPU-h.
Script `analysis/insights/iter_3/r10_turnover_stats.py` → `analysis/insights/iter_3/out/r10_turnover_stats_live_20260929T1937Z.json` (log `out/r10_live_20260929T1937Z.log`).
Snapshot: a fresh integrity gate, `analysis/insights/iter_3/out/snapshot_live_20260929T1937Z.json` (`iter_2/integrity.py`; 417 runs scanned, 325 frozen; log `out/integrity_live_20260929T1937Z.log`). `r01_realloc.py` was re-run on the same snapshot for **all** models → `out/r01_realloc_live_20260929T1937Z.json`.

New in `r_common.py`: the `CLOQ_TAG` env var overrides the output tag. Outputs of this snapshot are tagged `live_20260929T1937Z` and do not overwrite `*_live.json` (snapshot 1159Z).

`out/r01_realloc_unfrozen.json` is **unchanged** and still ungated (`_snapshot.id = null`). It was last produced at 12:09 PDT (commit 11ca12d) with `CLOQ_MODELS=q4,q8` only. That is why it has no q14 numbers (review W6). Do not cite it.

## Method (declared in the script docstring and in `declared` of the output JSON, before the first run on this snapshot; not a pre-registration)

- **Estimator.** The r01 estimator is unchanged: the shrink-to-attractor λ, c against the stratum-matched nonce null U, with n_ref = |U|−1 and nonce-mates removed. One change: every **draw has weight 1**. In r01, a fresh-nonce draw weighs |U|× a nonce-mate draw. Point estimates therefore differ slightly from r01 for families that mix `_n` and `_q` draws (q4 GPTQ λ 0.251 → 0.288; q8 AWQ 0.310 → 0.352).
- **Hierarchical paired bootstrap, B = 2000.** Each replicate resamples:
  - tasks, shared by every family and the null;
  - the U null draws, shared;
  - per family, checkpoints with replacement, then draws within each checkpoint.

  All contrasts are within-replicate differences (paired). Single-checkpoint families carry no checkpoint variance. That is a data limit, and `n_ckpt` is shown per row.
- **Floor (R3).** Floor families: `rot_bf16` (function-preserving rotation, fresh nonces), `null_K` (canonical prompt ± eager), and `gauss0.001` / `gauss0.003` (canonical cells, composed with λ_K).
  - floor = the equal-weight mean of the available floor families, computed in the same replicate;
  - band = [min, max] of their point estimates;
  - excess = λ − floor, tested one-sided.

  q14/q30a3/q32 have **only null_K** (one or two canonical runs), so their floor is weak.
- **Tests.** The margin is 0.10 on λ throughout.
  - TOST on Δλ vs RTN: p = max(P*(Δ ≥ .1), P*(Δ ≤ −.1)).
  - NI "λ_RTN − λ_rand < +0.10" against the matched random controls `gauss1` (Frobenius-matched, canonical, composed), `gauss1_fixed`, `gshape_w4` (RTN per-group RMS) and `rtnsign_w4` (RTN magnitudes, random signs). The strict one-sided P*(Δ ≥ 0) is also reported.
  - One-sided excess over the floor for RTN/GPTQ/AWQ-W4.
  - TOST of W8 vs the floor.
  - Two-sided Δc, only where both c are identified.
- **Pooling.** The pooled estimate is the equal-weight mean of per-model estimates over the models that have both families. The per-model bootstraps are independent and are combined replicate by replicate (a stratified bootstrap with model as the stratum). Inverse-variance weights are reported as a sensitivity (`ci90_iv`, `p_iv`). The conclusions are the same, except that W8-at-floor has IV p = 0.003 vs equal-weight p = 0.04.
- **Identification rule.** c is reported only if λ's 2.5% bound is > 0.10. Otherwise it is "unidentified".
- **Coin check.** The rule was declared up front: a cell PASSES iff the 95% CI of dCoin_obs − dCoin_pred contains 0, where dCoin_pred = f − (1−λ)f0 − λ·μ0_coin. This is finite even when c is not identified.
- **Holm.** Holm at α = 0.05 over the declared family: the 14 pooled tests in the table below, plus per-model Δc vs RTN wherever identified (none was).

## Results per model

All rows are families (or `ckpt:` sub-units) of the gated snapshot. λ uses the hierarchical 95% CI, and Δ is observed net success vs the U null.
- "(composed)" = a canonical-prompt cell, corrected for λ_K.
- "ckpt/draws" = the number of checkpoints and draws resampled.

### q4 (|U| = 8, n_ref = 7, 84 tasks)

Floor λ = 0.07 [0.00, 0.15], band [0.02, 0.12] from rot_bf16 0.12, null_K 0.09, gauss0.001 0.07, gauss0.003 0.02.

| family | ckpt/draws | λ [95% CI] | λ − floor [95% CI] | c | Δ (pp) [95% CI] | coin check |
|---|---|---|---|---|---|---|
| rtn_w4 | 1/8 | 0.24 [0.10, 0.40] | 0.17 [0.02, 0.34] | unidentified | -3.9 [-11.2, +3.7] | pass |
| gptq_w4 | 2/7 | 0.29 [0.10, 0.48] | 0.22 [0.05, 0.38] | unidentified | +2.4 [-9.5, +10.9] | pass |
| ckpt:gptq_w4_d1 | 1/5 | 0.29 [0.10, 0.50] | 0.22 [0.05, 0.41] | 0.46 [0.22, 0.87] | +5.2 [-3.3, +13.2] | pass |
| ckpt:gptq_w4_d2 | 1/2 | 0.28 [0.07, 0.51] | 0.20 [0.01, 0.42] | unidentified | -4.5 [-13.0, +3.9] | pass |
| awq_w4 | 2/8 | 0.27 [0.12, 0.42] | 0.20 [0.05, 0.35] | 0.35 [0.07, 0.63] | +0.0 [-9.6, +8.6] | pass |
| ckpt:awq_w4 | 1/5 | 0.29 [0.12, 0.48] | 0.21 [0.05, 0.40] | 0.37 [0.12, 0.69] | +2.8 [-6.1, +11.2] | pass |
| ckpt:awq_w4_d2 | 1/3 | 0.24 [0.08, 0.41] | 0.17 [0.00, 0.35] | unidentified | -4.7 [-12.5, +3.4] | pass |
| rot_rtn_w4 | 1/3 | 0.23 [0.05, 0.43] | 0.15 [-0.02, 0.36] | unidentified | -2.7 [-11.9, +6.6] | pass |
| rot_gptq_w4 | 1/3 | 0.23 [0.06, 0.43] | 0.16 [0.00, 0.35] | unidentified | +4.5 [-3.7, +12.8] | pass |
| mxfp4 | 1/3 | 0.22 [0.05, 0.42] | 0.15 [-0.01, 0.33] | unidentified | -1.5 [-9.6, +6.0] | pass |
| nf4 | 1/3 | 0.37 [0.18, 0.59] | 0.30 [0.12, 0.49] | 0.45 [0.21, 0.78] | -0.3 [-9.3, +8.6] | pass |
| gauss1 (composed) | 4/4 | 0.27 [0.07, 0.47] | 0.20 [0.00, 0.40] | unidentified | -0.9 [-10.4, +8.3] | pass |
| gauss1_fixed | 1/2 | 0.34 [0.12, 0.57] | 0.27 [0.06, 0.49] | 0.20 [-0.07, 0.59] | -5.7 [-14.9, +3.4] | pass |
| gshape_w4 | 1/3 | 0.42 [0.19, 0.65] | 0.34 [0.12, 0.58] | 0.17 [0.00, 0.38] | -4.3 [-12.5, +4.7] | pass |
| rtnsign_w4 | 1/3 | 0.24 [0.08, 0.41] | 0.16 [0.02, 0.34] | unidentified | -3.1 [-11.5, +5.4] | pass |
| rtnsr_w4 | 1/3 | 0.35 [0.15, 0.57] | 0.28 [0.07, 0.50] | 0.12 [-0.07, 0.35] | -11.0 [-20.3, -1.9] | pass |
| rtn_w8 | 1/2 | 0.17 [0.01, 0.36] | 0.09 [-0.06, 0.28] | unidentified | -1.5 [-8.8, +6.4] | pass |
| rtn_w3 | 1/1 | 0.74 [0.51, 0.94] | 0.66 [0.43, 0.89] | 0.03 [-0.02, 0.11] | -22.9 [-32.9, -12.8] | pass |
| gptq_w3 | 1/5 | 0.24 [0.08, 0.45] | 0.17 [0.00, 0.40] | unidentified | +0.2 [-7.8, +8.1] | pass |
| rot_bf16 | 1/3 | 0.12 [-0.02, 0.28] | (floor cell) | unidentified | +0.1 [-6.2, +6.5] | pass |
| null_K | 1/2 | 0.09 [-0.03, 0.23] | (floor cell) | unidentified | -2.1 [-10.0, +5.7] | pass |
| gauss0.001 (composed) | 2/2 | 0.07 [-0.04, 0.21] | (floor cell) | unidentified | +6.6 [-1.2, +14.3] | pass |
| gauss0.003 (composed) | 2/2 | 0.02 [-0.16, 0.18] | (floor cell) | unidentified | +1.2 [-7.1, +9.5] | pass |

### q8 (|U| = 8, n_ref = 7, 85 tasks)

Floor λ = 0.04 [-0.08, 0.17], band [-0.03, 0.12] from null_K 0.12, gauss0.001 -0.03, gauss0.003 0.04.

| family | ckpt/draws | λ [95% CI] | λ − floor [95% CI] | c | Δ (pp) [95% CI] | coin check |
|---|---|---|---|---|---|---|
| rtn_w4 | 1/2 | 0.21 [-0.00, 0.50] | 0.17 [-0.09, 0.48] | unidentified | +1.2 [-7.3, +9.8] | pass |
| gptq_w4 | 2/7 | 0.33 [0.08, 0.63] | 0.28 [0.06, 0.58] | unidentified | +0.0 [-8.3, +7.8] | pass |
| ckpt:gptq_w4_d1 | 1/5 | 0.30 [0.04, 0.59] | 0.25 [0.00, 0.53] | unidentified | +0.7 [-7.2, +8.7] | pass |
| ckpt:gptq_w4_d2 | 1/2 | 0.40 [0.10, 0.75] | 0.35 [0.10, 0.68] | 0.17 [-0.03, 0.56] | -1.8 [-10.4, +7.3] | pass |
| awq_w4 | 2/7 | 0.35 [0.05, 0.62] | 0.31 [-0.01, 0.59] | unidentified | +1.5 [-5.7, +10.6] | pass |
| ckpt:awq_w4 | 1/5 | 0.42 [0.17, 0.69] | 0.38 [0.10, 0.67] | 0.20 [0.05, 0.45] | +0.2 [-8.1, +8.7] | pass |
| ckpt:awq_w4_d2 | 1/2 | 0.18 [-0.01, 0.44] | 0.13 [-0.08, 0.41] | unidentified | +4.7 [-3.7, +13.2] | pass |
| gauss1 (composed) | 3/3 | 0.56 [0.19, 0.90] | 0.51 [0.22, 0.84] | 0.03 [-0.19, 0.17] | -9.0 [-20.4, +2.4] | fail |
| gauss1_fixed | 1/2 | 0.27 [0.06, 0.57] | 0.23 [0.02, 0.51] | unidentified | +1.8 [-6.8, +11.3] | pass |
| gshape_w4 | 1/3 | 0.17 [-0.01, 0.41] | 0.12 [-0.06, 0.36] | unidentified | -0.4 [-8.3, +7.9] | pass |
| rtnsign_w4 | 1/3 | 0.42 [0.14, 0.74] | 0.37 [0.08, 0.70] | 0.16 [-0.00, 0.45] | +0.0 [-9.0, +8.8] | pass |
| rtn_w8 | 1/2 | 0.14 [-0.09, 0.47] | 0.10 [-0.14, 0.41] | unidentified | +0.0 [-7.3, +6.6] | pass |
| rtn_w3 | 1/4 | 0.58 [0.27, 0.87] | 0.53 [0.21, 0.85] | 0.05 [-0.04, 0.15] | -16.2 [-24.9, -7.5] | pass |
| gptq_w3 | 1/5 | 0.46 [0.17, 0.76] | 0.41 [0.17, 0.71] | 0.13 [0.01, 0.36] | -0.7 [-9.6, +8.2] | fail |
| null_K | 1/2 | 0.12 [-0.07, 0.32] | (floor cell) | unidentified | +3.5 [-5.1, +12.8] | pass |
| gauss0.001 (composed) | 2/2 | -0.03 [-0.34, 0.23] | (floor cell) | unidentified | -4.1 [-12.9, +4.1] | pass |
| gauss0.003 (composed) | 2/2 | 0.04 [-0.20, 0.33] | (floor cell) | unidentified | -1.2 [-10.0, +8.2] | pass |

### q14 (|U| = 5, n_ref = 4, 85 tasks)

Floor λ = 0.09 [-0.09, 0.25], band [0.09, 0.09] from null_K 0.09 — **null_K only (weak floor)**.

| family | ckpt/draws | λ [95% CI] | λ − floor [95% CI] | c | Δ (pp) [95% CI] | coin check |
|---|---|---|---|---|---|---|
| rtn_w4 | 1/5 | 0.26 [0.04, 0.48] | 0.18 [-0.03, 0.39] | unidentified | -6.6 [-14.6, +1.4] | pass |
| gptq_w4 | 2/7 | 0.16 [-0.06, 0.37] | 0.08 [-0.12, 0.28] | unidentified | -3.8 [-11.8, +6.8] | pass |
| ckpt:gptq_w4_d1 | 1/5 | 0.17 [-0.06, 0.38] | 0.08 [-0.12, 0.30] | unidentified | -6.1 [-13.2, +1.2] | pass |
| ckpt:gptq_w4_d2 | 1/2 | 0.16 [-0.08, 0.39] | 0.07 [-0.14, 0.30] | unidentified | +2.0 [-6.2, +10.1] | pass |
| awq_w4 | 1/5 | 0.07 [-0.12, 0.25] | -0.02 [-0.20, 0.17] | unidentified | -1.4 [-8.5, +4.9] | pass |
| gauss1 (composed) | 2/2 | 0.27 [-0.03, 0.56] | 0.18 [-0.18, 0.54] | unidentified | -10.0 [-20.0, +1.2] | pass |
| gauss1_fixed | 1/2 | 0.30 [0.06, 0.54] | 0.21 [0.00, 0.45] | unidentified | -5.7 [-14.8, +3.1] | pass |
| gshape_w4 | 1/3 | 0.20 [-0.02, 0.42] | 0.11 [-0.13, 0.37] | unidentified | +0.6 [-7.2, +8.7] | pass |
| rtnsign_w4 | 1/3 | 0.35 [0.09, 0.60] | 0.26 [-0.02, 0.54] | unidentified | -3.3 [-12.4, +5.8] | pass |
| rtn_w8 | 1/2 | -0.02 [-0.19, 0.12] | -0.11 [-0.27, 0.02] | unidentified | -0.4 [-7.5, +6.3] | pass |
| rtn_w3 | 1/3 | 0.37 [0.13, 0.63] | 0.29 [0.04, 0.57] | 0.05 [-0.20, 0.22] | -14.3 [-23.1, -5.6] | pass |
| gptq_w3 | 1/3 | 0.18 [-0.01, 0.37] | 0.10 [-0.11, 0.33] | unidentified | -4.1 [-13.2, +4.5] | pass |
| null_K | 1/1 | 0.09 [-0.09, 0.25] | (floor cell) | unidentified | +4.9 [-2.6, +13.2] | pass |

### q30a3 (|U| = 8, n_ref = 7, 85 tasks)

Floor λ = -0.02 [-0.17, 0.14], band [-0.02, -0.02] from null_K -0.02 — **null_K only (weak floor)**.

| family | ckpt/draws | λ [95% CI] | λ − floor [95% CI] | c | Δ (pp) [95% CI] | coin check |
|---|---|---|---|---|---|---|
| rtn_w4 | 1/2 | 0.14 [-0.05, 0.35] | 0.17 [-0.01, 0.37] | unidentified | +2.9 [-5.1, +11.3] | pass |
| gptq_w4 | 2/4 | 0.01 [-0.13, 0.16] | 0.04 [-0.15, 0.21] | unidentified | +2.1 [-5.0, +9.7] | pass |
| ckpt:gptq_w4_d1 | 1/2 | 0.00 [-0.15, 0.15] | 0.03 [-0.16, 0.20] | unidentified | +1.2 [-6.0, +8.8] | pass |
| ckpt:gptq_w4_d2 | 1/2 | 0.02 [-0.14, 0.22] | 0.04 [-0.16, 0.26] | unidentified | +2.9 [-5.1, +11.2] | pass |
| awq_w4 | 1/2 | 0.11 [-0.11, 0.34] | 0.13 [-0.07, 0.35] | unidentified | +1.8 [-6.3, +9.7] | pass |
| gauss1 (composed) | 2/2 | 0.23 [0.03, 0.49] | 0.25 [-0.03, 0.58] | unidentified | -1.2 [-9.4, +7.6] | pass |
| rtn_w8 | 1/2 | -0.03 [-0.18, 0.12] | -0.01 [-0.19, 0.18] | unidentified | +4.1 [-2.6, +11.8] | pass |
| rtn_w3 | 1/2 | 0.71 [0.36, 1.02] | 0.73 [0.32, 1.07] | 0.05 [-0.08, 0.15] | -21.8 [-31.3, -12.1] | pass |
| gptq_w3 | 1/2 | 0.18 [-0.08, 0.46] | 0.20 [-0.07, 0.47] | unidentified | +0.6 [-8.1, +9.8] | pass |
| null_K | 1/1 | -0.02 [-0.17, 0.14] | (floor cell) | unidentified | -1.8 [-8.5, +4.7] | pass |

### q32 (|U| = 8, n_ref = 7, 85 tasks)

Floor λ = -0.03 [-0.13, 0.06], band [-0.03, -0.03] from null_K -0.03 — **null_K only (weak floor)**.

| family | ckpt/draws | λ [95% CI] | λ − floor [95% CI] | c | Δ (pp) [95% CI] | coin check |
|---|---|---|---|---|---|---|
| rtn_w4 | 1/1 | 0.26 [0.04, 0.50] | 0.29 [0.06, 0.54] | unidentified | -6.5 [-15.3, +2.5] | pass |
| gptq_w4 | 2/4 | 0.11 [-0.04, 0.26] | 0.13 [0.01, 0.28] | unidentified | +3.5 [-5.0, +11.9] | pass |
| ckpt:gptq_w4_d1 | 1/2 | 0.10 [-0.07, 0.28] | 0.12 [-0.00, 0.30] | unidentified | +7.1 [-0.7, +14.8] | fail |
| ckpt:gptq_w4_d2 | 1/2 | 0.12 [-0.03, 0.29] | 0.14 [0.00, 0.32] | unidentified | +0.0 [-8.2, +8.2] | pass |
| awq_w4 | 1/2 | 0.18 [-0.02, 0.39] | 0.20 [0.03, 0.41] | unidentified | +0.6 [-7.2, +8.7] | pass |
| gauss1 (composed) | 2/2 | 0.19 [0.01, 0.43] | 0.21 [0.02, 0.47] | unidentified | -2.4 [-11.8, +5.9] | pass |
| rtn_w8 | 1/2 | 0.01 [-0.10, 0.09] | 0.03 [-0.07, 0.12] | unidentified | -0.6 [-7.2, +5.9] | pass |
| gptq_w3 | 1/2 | 0.27 [0.09, 0.47] | 0.29 [0.14, 0.50] | unidentified | +1.8 [-8.1, +12.2] | pass |
| null_K | 1/1 | -0.03 [-0.13, 0.06] | (floor cell) | unidentified | +0.6 [-6.5, +7.8] | pass |

## Declared family, Holm-adjusted

| test | per model | pooled est | 90% CI | 95% CI | p | p (Holm) | verdict |
|---|---|---|---|---|---|---|---|
| TOST dlam gptq_w4-rtn_w4 pooled | q4 +0.05, q8 +0.11, q14 -0.10, q30a3 -0.13, q32 -0.16 | -0.045 | [-0.13, 0.04] | [-0.15, 0.06] | 0.1449 | 0.750 | not supported after Holm |
| TOST dlam awq_w4-rtn_w4 pooled | q4 +0.03, q8 +0.14, q14 -0.19, q30a3 -0.04, q32 -0.09 | -0.030 | [-0.15, 0.07] | [-0.17, 0.09] | 0.1694 | 0.750 | not supported after Holm |
| TOST dlam rot_rtn_w4-rtn_w4 pooled | q4 -0.02 | -0.016 | [-0.17, 0.16] | [-0.20, 0.18] | 0.1839 | 0.750 | not supported after Holm |
| TOST dlam rot_gptq_w4-rtn_w4 pooled | q4 -0.01 | -0.009 | [-0.14, 0.12] | [-0.17, 0.15] | 0.1249 | 0.750 | not supported after Holm |
| TOST dlam mxfp4-rtn_w4 pooled | q4 -0.02 | -0.023 | [-0.18, 0.14] | [-0.23, 0.17] | 0.2284 | 0.750 | not supported after Holm |
| TOST dlam nf4-rtn_w4 pooled | q4 +0.13 | +0.126 | [-0.02, 0.27] | [-0.05, 0.29] | 0.6302 | 0.750 | not supported after Holm |
| NI lam rtn_w4-gauss1 < +0.10 pooled | q4 -0.03, q8 -0.34, q14 -0.01, q30a3 -0.08, q32 +0.08 | -0.077 | [-0.20, 0.04] | [-0.22, 0.07] | 0.0090 | 0.090 | not supported after Holm |
| NI lam rtn_w4-gauss1_fixed < +0.10 pooled | q4 -0.10, q8 -0.06, q14 -0.04 | -0.065 | [-0.18, 0.05] | [-0.21, 0.07] | 0.0125 | 0.112 | not supported after Holm |
| NI lam rtn_w4-gshape_w4 < +0.10 pooled | q4 -0.17, q8 +0.05, q14 +0.07 | -0.021 | [-0.13, 0.09] | [-0.15, 0.11] | 0.0355 | 0.284 | not supported after Holm |
| NI lam rtn_w4-rtnsign_w4 < +0.10 pooled | q4 +0.00, q8 -0.20, q14 -0.09 | -0.095 | [-0.22, 0.02] | [-0.24, 0.05] | 0.0035 | 0.038 | reject H0 (claim supported) |
| excess lam rtn_w4 - floor > 0 pooled | q4 +0.17, q8 +0.17, q14 +0.18, q30a3 +0.17, q32 +0.29 | +0.194 | [0.11, 0.28] | [0.10, 0.30] | 0.0005 | 0.007 | reject H0 (claim supported) |
| excess lam gptq_w4 - floor > 0 pooled | q4 +0.22, q8 +0.28, q14 +0.08, q30a3 +0.04, q32 +0.13 | +0.149 | [0.08, 0.23] | [0.07, 0.24] | 0.0005 | 0.007 | reject H0 (claim supported) |
| excess lam awq_w4 - floor > 0 pooled | q4 +0.20, q8 +0.31, q14 -0.02, q30a3 +0.13, q32 +0.20 | +0.164 | [0.08, 0.24] | [0.07, 0.25] | 0.0030 | 0.036 | reject H0 (claim supported) |
| TOST lam rtn_w8 - floor pooled | q4 +0.09, q8 +0.10, q14 -0.11, q30a3 -0.01, q32 +0.03 | +0.021 | [-0.05, 0.10] | [-0.06, 0.11] | 0.0405 | 0.284 | not supported after Holm |

The 14 Δc tests (every W4 method vs RTN, on every model) are listed in `holm_family_not_testable`. They could not be run because RTN's c is unidentified everywhere (q4 RTN λ 2.5% bound = 0.098).

## Checkpoint vs method (W1, R1 pre-analysis)

Paired contrasts, same replicate: model | contrast | Δλ [95% CI] | ΔΔ pp [95% CI] | two-sided p | Δc status.

| model | contrast | Δλ | ΔΔ (pp) | p(ΔΔ) | Δc |
|---|---|---|---|---|---|

| q4 | gptq_w4-rtn_w4 | +0.046 [-0.15, 0.23] | +6.3 [-5.4, +14.9] | 0.3438 | unidentified |
| q4 | awq_w4-rtn_w4 | +0.028 [-0.13, 0.18] | +3.9 [-5.8, +11.9] | 0.4458 | unidentified |
| q4 | ckpt:gptq_w4_d1-ckpt:gptq_w4_d2 | +0.015 [-0.18, 0.22] | +9.6 [+1.8, +17.4] | 0.019 | unidentified |
| q4 | ckpt:awq_w4-ckpt:awq_w4_d2 | +0.044 [-0.16, 0.24] | +7.5 [-0.6, +15.7] | 0.074 | unidentified |
| q8 | gptq_w4-rtn_w4 | +0.113 [-0.17, 0.42] | -1.2 [-11.2, +7.5] | 0.7756 | unidentified |
| q8 | awq_w4-rtn_w4 | +0.140 [-0.27, 0.48] | +0.3 [-8.2, +10.6] | 0.8876 | unidentified |
| q8 | ckpt:gptq_w4_d1-ckpt:gptq_w4_d2 | -0.099 [-0.47, 0.23] | +2.5 [-7.3, +12.3] | 0.6337 | unidentified |
| q8 | ckpt:awq_w4-ckpt:awq_w4_d2 | +0.243 [0.05, 0.45] | -4.5 [-13.7, +4.2] | 0.3188 | unidentified |
| q14 | gptq_w4-rtn_w4 | -0.099 [-0.31, 0.07] | +2.8 [-5.3, +14.1] | 0.4638 | unidentified |
| q14 | awq_w4-rtn_w4 | -0.194 [-0.44, 0.02] | +5.2 [-4.2, +14.8] | 0.2859 | unidentified |
| q14 | ckpt:gptq_w4_d1-ckpt:gptq_w4_d2 | +0.006 [-0.23, 0.24] | -8.1 [-15.8, +0.0] | 0.055 | unidentified |
| q30a3 | gptq_w4-rtn_w4 | -0.131 [-0.33, 0.06] | -0.9 [-9.7, +7.6] | 0.8496 | unidentified |
| q30a3 | awq_w4-rtn_w4 | -0.037 [-0.28, 0.22] | -1.2 [-11.2, +9.4] | 0.8216 | unidentified |
| q30a3 | ckpt:gptq_w4_d1-ckpt:gptq_w4_d2 | -0.017 [-0.19, 0.12] | -1.8 [-10.6, +7.1] | 0.7446 | unidentified |
| q32 | gptq_w4-rtn_w4 | -0.156 [-0.43, 0.10] | +10.0 [-0.9, +20.6] | 0.081 | unidentified |
| q32 | awq_w4-rtn_w4 | -0.089 [-0.42, 0.21] | +7.1 [-4.7, +18.2] | 0.2579 | unidentified |
| q32 | ckpt:gptq_w4_d1-ckpt:gptq_w4_d2 | -0.018 [-0.22, 0.17] | +7.1 [-2.9, +17.1] | 0.1699 | unidentified |

**Variance decomposition** (`models.<m>.variance_decomposition`).
- Method of moments, conditional on the 85 tasks: a draw-only bootstrap with tasks and null fixed gives each checkpoint's nonce variance.
- Components: nonce = single-draw variance within a checkpoint; checkpoint = within-method between-checkpoint variance minus nonce noise; method = between-method variance of the method means minus checkpoint and nonce noise.
- Negative values are left untruncated.

| model | stat | nonce var (df) | checkpoint var (df) | method var (#methods) |
|---|---|---|---|---|
| q4 | λ | 0.0060 (26) | −0.0013 (2) | 0.0012 (7) |
| q4 | Δ | 0.0007 (26) | **0.0035** (2), SD 5.9 pp | −0.0025 (7) |
| q8 | λ | 0.0062 (11) | **0.0150** (2); AWQ d1 0.42 vs d2 0.18 | −0.0071 (3) |
| q8 | Δ | 0.0010 (11) | 0.0003 (2) | −0.0003 (3) |
| q14 | Δ | 0.0005 (13) | 0.0031 (1) | −0.0019 (3) |
| q32 | Δ | 0.0003 (3) | 0.0023 (1) | 0.0005 (3) |
| all | c | — | **not estimable**: at most one c-identified checkpoint per method | — |

Gaussian seeds are separate checkpoints of a matched random perturbation. The spread across seeds, minus the nonce variance of the fixed-checkpoint control, gives:
- q4 k=1 (4 seeds): λ 0.31/0.38/0.25/0.15, checkpoint var ≈ 0.008 (SD 0.09).
- q8 k=0.03 (5 seeds): λ −0.17…+0.17, checkpoint var ≈ 0.017.
- q14 k=1 (2 seeds): λ 0.15 vs 0.39.

Status:
- **Estimable now:**
  - nonce variance: many checkpoints have ≥ 2 draws;
  - checkpoint variance of λ and Δ, with 1–2 df per model, from GPTQ d1/d2 and AWQ d1/d2 (AWQ d2 only on q4/q8);
  - a point estimate of the method variance.
- **Estimable only after R1** (GPTQ d3/d4, AWQ d3, rot_rtn seeds, rot_bf16 seeds):
  - any test of "method variance > checkpoint variance";
  - every c component.

  The point estimates available now point the other way: the checkpoint variance of Δ exceeds the method variance on q4, q14 and q32.

## Which storyline claims survive

| claim (STORYLINE_v4) | verdict | numbers |
|---|---|---|
| C2 "quantization re-rolls tasks" (turnover above the numerics floor) | **survives (rescoped)** | Pooled excess λ − floor: RTN +0.19 [0.10, 0.30], GPTQ +0.15 [0.07, 0.24], AWQ +0.16 [0.07, 0.25]; Holm p 0.007 / 0.007 / 0.036. Per model, RTN's excess CI excludes 0 only on q4 (+0.17 [0.02, 0.34]) and q32 (+0.29 [0.06, 0.54]). |
| "re-rolls 20–40% of tasks" | **fails as worded** | W4 λ is 0.21–0.37 on q4/q8, but 0.01–0.26 on q14/q30a3/q32 (GPTQ q30a3 0.01, AWQ q14 0.07). Against the floor, the excess is 0.15–0.30. |
| "break/fix 5–10× the null" | **fails** | Against the floor, q4 RTN break is 2.19× [0.86, 8.9] and fix 1.20× [0.39, 3.7]. Neither ratio CI excludes 1. |
| S4 "λ is method-invariant at W4" | **not established (inconclusive)** | Pooled Δλ vs RTN: GPTQ −0.045 (90% [−0.13, 0.04]), AWQ −0.030 [−0.15, 0.07], rot_rtn −0.02 [−0.17, 0.16], rot_gptq −0.01 [−0.14, 0.12], MXFP4 −0.02 [−0.18, 0.14], NF4 +0.13 [−0.02, 0.27]. No TOST at ±0.10 passes (p 0.12–0.63). There is no detectable difference, but equivalence needs more draws or R2. |
| C3a "λ follows error size, not structure" | **replaced** by the one-sided claim | NI "RTN ≤ matched random + 0.10": rtnsign p_holm 0.038 (**survives**); gauss1 0.09, gauss1_fixed 0.11, gshape 0.28 (fail after Holm). Every pooled point estimate is ≤ 0 (−0.02 to −0.09). The strict "RTN < random" is not significant (p 0.09–0.37). |
| W8 ≈ floor | **not established** | Pooled excess +0.02 (90% [−0.05, 0.10]), TOST p 0.04 (Holm 0.28). q4/q8 excess is +0.09/+0.10. |
| C3b "c follows method" | **unidentified** | RTN's c is unidentified on all 5 models. c is identified only for q4 AWQ 0.35 [0.07, 0.63], q4 NF4 0.45, q4 GPTQ-d1 0.46, q4 AWQ-d1 0.37, q8 GPTQ-d2 0.17 and q8 AWQ-d1 0.20. None of the 14 Δc tests can be run. ΔΔ vs RTN excludes 0 on no model. |
| "net effect is a checkpoint lottery" (review reframing) | **supported descriptively (not in Holm)** | Same method, different calibration draw: q4 GPTQ d1−d2 ΔΔ +9.6 pp [1.8, 17.4] (p 0.019); q4 AWQ d1−d2 +7.5 [−0.6, 15.7]; q14 GPTQ −8.1 [−15.8, 0.0]; q8 AWQ d1−d2 Δλ +0.24 [0.05, 0.45]. Every method-vs-RTN ΔΔ CI covers 0. |
| λ–c model check (coin stratum) | **passes, but weak** | 81/83 family cells pass (97.6%; binomial p for excess fails 0.92). Fails: q8 gauss1 (resid +0.23 [0.04, 0.43]) and q8 GPTQ-W3 (+0.20 [0.00, 0.39]); also the sub-unit q32 GPTQ-d1. The median residual CI width is 0.39, so the check has little power. |
| C4 "open-loop probe predicts λ (partial ρ 0.86)" | **fails as worded** | 0.86 is A2-15, partial ρ(flip rate, per-decision **hazard** \| dose) (`iter_2/out/d01_matched_dose.json`). For λ over 34 E3 cells (q4 19, q8 11, q30a3 4): raw ρ(flip, λ) 0.84 [0.70, 0.92], ρ(dose, λ) 0.81, partial ρ(flip, λ \| log dose) **0.39 [−0.03, 0.73]**, and within model 0.15 (q4) and 0.15 (q8). So the probe is mostly a dose proxy for λ. |
| "higher p̄ → more damage" | not tested here | Unchanged (review W5). |

## Provenance fixes (W6, W7)

- **Task set.** The 85 tasks are the `evaluation` split of `manifests/task_split_v0.json` (sha256 `7d1671154c37…`, seed 2024, from the legacy `bf16` run): 58 retail + 27 airline.
  - Every model's run `task_manifest.json` equals that split: checked for q4/q8/q14/q30a3/q32, stored under `provenance.task_split.run_task_manifest_equals_evaluation_split`.
  - Of the 164 characterised tasks, 22 were excluded as unstable (17 retail + 5 airline). Their legacy BF16 termination was not in {agent_stop, user_stop}.
  - The 57 `calibration` tasks (39 + 18) are unused.
  - q4 analyses use 84 tasks. airline task 45 is missing (infrastructure_error, counted as missing) in `a6k2_q4_null_n2`, and tasks are complete-case over U.
- **"partial ρ 0.86".** See the C4 row above. It must not be quoted for λ. The λ-level number is 0.39 [−0.03, 0.73].
- **E3 open-loop outputs** (`analysis/openloop/a6k2/`) are not covered by the integrity gate, and another session was still writing them during this run (the cell count went from 33 to 34 between two runs). Each input is pinned by sha256 in `openloop_lambda.cells[].ol_sha256`.
- **Ungated evidence.** STORYLINE_v4 cites `r01_realloc_unfrozen.json`. Replace it with `r01_realloc_live_20260929T1937Z.json` and this file.

## Caveats

- The declared family was written after the team and the reviewer had seen ungated numbers. It is a declaration, not a pre-registration. R2 on the 57 unused tasks is the confirmatory test.
- The floor on q14/q30a3/q32 is null_K alone. Its λ is negative on q30a3/q32, which inflates the excess there.
- The two-stage bootstrap with 2 checkpoints is crude. It is conservative for family-level CIs and says nothing about the checkpoint distribution.
- Bootstrap p-values are floored at 1/2001.

Evidence: `analysis/insights/iter_3/r10_turnover_stats.py`; `analysis/insights/iter_3/out/r10_turnover_stats_live_20260929T1937Z.json` (`declared`, `models.<m>.{floor,families,contrasts,variance_decomposition}`, `holm_family`, `holm_family_not_testable`, `coin_check`, `openloop_lambda`, `provenance`); `analysis/insights/iter_3/out/r01_realloc_live_20260929T1937Z.json`; `analysis/insights/iter_3/out/snapshot_live_20260929T1937Z.json`; `analysis/insights/iter_2/out/d01_matched_dose.json`; `manifests/task_split_v0.json`; `paper/review_storyline_v4.md`.
