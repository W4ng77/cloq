# Task fragility and difficulty strata, tau2 core W4 (EXPLORATORY, POST HOC; 20261005T134836Z)

Script `analysis/fork/task_fragility.py` (sha256 cbb15f23b5d5f8a4), git a431b7ff6e, B = 2000, seed 20261001. Full numbers: `analysis/fork/out/task_fragility_20261005T134836Z.json`. Split file: `analysis/fork/out/task_fragility_split_20261005T134815Z.json`. All values in % (pp for G and differences).

## Full pool (primary; 4 cells equal weight, 20 blocks x 85 tasks per cell)

- pool r: 9.62 [block 8.93, 10.25; t 8.88, 10.36; crossed 7.35, 12.19]
- pool d: 8.96 [block 8.22, 9.66; t 8.18, 9.74; crossed 6.93, 11.22]
- pool M: 18.57 [block 17.50, 19.51; t 17.49, 19.66; crossed 15.01, 22.34]
- pool G: 0.66 [block -0.37, 1.57; t -0.40, 1.73; crossed -2.06, 3.49]
- q4:awq_w4 M: 19.94 [block 17.88, 21.76; t 17.86, 22.02; crossed 14.94, 25.47]; G: -0.29 [block -2.18, 1.59; t -2.39, 1.80; crossed -5.82, 5.24]
- q4:gptq_w4_d1 M: 15.53 [block 13.71, 17.30; t 13.54, 17.52; crossed 10.71, 20.82]; G: -1.88 [block -3.82, -0.12; t -3.94, 0.17; crossed -6.71, 3.06]
- q8:awq_w4 M: 20.88 [block 19.35, 22.24; t 19.29, 22.48; crossed 15.29, 27.00]; G: 1.94 [block -0.41, 4.35; t -0.74, 4.62; crossed -3.82, 7.82]
- q8:gptq_w4_d1 M: 17.94 [block 16.47, 19.47; t 16.23, 19.65; crossed 12.47, 24.24]; G: 2.88 [block 1.47, 4.35; t 1.23, 4.53; crossed -2.76, 9.12]

## Conditional rates (all 20 blocks)

- rescue|QQ fail pool: 14.62 [block 13.66, 15.47; t 13.48, 15.50; crossed 10.75, 19.13]
- rescue|QQ fail q4:awq_w4: 15.53 [block 13.02, 17.78; t 12.73, 18.11; crossed 9.96, 22.34]
- rescue|QQ fail q4:gptq_w4_d1: 11.37 [block 9.32, 13.31; t 9.04, 13.40; crossed 6.96, 17.09]
- rescue|QQ fail q8:awq_w4: 16.67 [block 14.63, 18.51; t 14.40, 18.66; crossed 10.21, 24.18]
- rescue|QQ fail q8:gptq_w4_d1: 14.90 [block 13.28, 16.48; t 13.01, 16.60; crossed 8.79, 22.53]
- damage|QQ success pool: 26.08 [block 24.08, 27.97; t 23.93, 28.16; crossed 19.93, 32.94]
- damage|QQ success q4:awq_w4: 27.52 [block 24.92, 29.95; t 24.76, 30.40; crossed 18.11, 38.46]
- damage|QQ success q4:gptq_w4_d1: 21.76 [block 18.70, 25.00; t 18.42, 25.18; crossed 13.09, 31.78]
- damage|QQ success q8:awq_w4: 30.04 [block 26.33, 33.45; t 25.87, 33.48; crossed 20.28, 41.48]
- damage|QQ success q8:gptq_w4_d1: 25.00 [block 21.99, 27.89; t 21.81, 28.45; crossed 16.19, 35.93]
- P(QQ success) pool: 34.60 [block 33.65, 35.52; t 33.57, 35.63; crossed 27.82, 41.52]
- P(QQ success) q4:awq_w4: 36.76 [block 35.00, 38.47; t 34.85, 38.68; crossed 28.82, 44.82]
- P(QQ success) q4:gptq_w4_d1: 40.00 [block 38.47, 41.53; t 38.31, 41.69; crossed 31.41, 48.65]
- P(QQ success) q8:awq_w4: 31.53 [block 30.12, 32.94; t 29.96, 33.10; crossed 23.47, 39.41]
- P(QQ success) q8:gptq_w4_d1: 30.12 [block 28.88, 31.47; t 28.68, 31.55; crossed 22.12, 38.47]

## Split-half fragility: fragility define A -> estimate B

- defining half: {"top20 mean fragility M %": 43.58, "rest mean fragility M %": 12.17, "threshold M %": 36.36, "tied at threshold (outside top)": 1}
| group | r | d | M | G |
|---|---|---|---|---|
| top20 | +21.08 [t +18.61, +23.54; crossed +14.81, +28.13] | +17.65 [t +14.30, +20.99; crossed +12.39, +23.34] | +38.73 [t +34.85, +42.60; crossed +32.31, +45.71] | +3.43 [t -0.98, +7.85; crossed -7.08, +13.70] |
| rest | +6.50 [t +5.24, +7.75; crossed +4.43, +9.00] | +7.23 [t +6.19, +8.27; crossed +4.82, +9.92] | +13.73 [t +12.54, +14.91; crossed +10.20, +17.47] | -0.74 [t -2.71, +1.24; crossed -4.06, +2.44] |
| top20 - rest | +14.58 [t +12.24, +16.93; crossed +7.93, +22.00] | +10.42 [t +7.06, +13.78; crossed +4.78, +16.86] | +25.00 [t +21.87, +28.13; crossed +17.93, +32.33] | +4.17 [t -0.71, +9.05; crossed -6.66, +15.25] |

- top-20% share of held-out turnover (20.0 if fragility does not persist): +40.96 [t +39.00, +43.09; crossed +26.56, +55.90]

## Split-half fragility: fragility define B -> estimate A

- defining half: {"top20 mean fragility M %": 42.97, "rest mean fragility M %": 12.66, "threshold M %": 36.11, "tied at threshold (outside top)": 1}
| group | r | d | M | G |
|---|---|---|---|---|
| top20 | +21.39 [t +18.69, +24.09; crossed +15.15, +27.90] | +17.65 [t +14.55, +20.74; crossed +13.45, +22.35] | +39.04 [t +34.15, +43.92; crossed +32.39, +45.86] | +3.74 [t +0.61, +6.88; crossed -5.05, +12.43] |
| rest | +6.89 [t +5.94, +7.83; crossed +4.64, +9.51] | +6.42 [t +5.29, +7.55; crossed +4.29, +8.80] | +13.30 [t +12.13, +14.47; crossed +10.00, +16.83] | +0.47 [t -1.25, +2.19; crossed -2.70, +3.84] |
| top20 - rest | +14.51 [t +11.98, +17.03; crossed +7.87, +21.19] | +11.23 [t +8.23, +14.23; crossed +6.71, +16.49] | +25.74 [t +21.54, +29.93; crossed +18.63, +32.72] | +3.28 [t -0.35, +6.90; crossed -6.07, +12.45] |

- top-20% share of held-out turnover (20.0 if fragility does not persist): +42.32 [t +39.25, +44.74; crossed +27.02, +57.50]

## BF16 difficulty tertiles: BF16 difficulty define A -> estimate B (cuts {'q4': [0.0, 0.45454545454545453], 'q8': [0.0, 0.2727272727272727]}; T1 = hardest)

| stratum | tasks per cell | r | d | M | G |
|---|---|---|---|---|---|
| T1 | [34, 34, 43, 43] | +5.77 [t +4.46, +7.08; crossed +2.83, +9.53] | +4.27 [t +2.91, +5.63; crossed +1.89, +7.27] | +10.04 [t +8.08, +11.99; crossed +5.66, +15.08] | +1.50 [t -0.33, +3.32; crossed -2.32, +5.71] |
| T2 | [24, 24, 14, 14] | +11.72 [t +9.20, +14.25; crossed +7.36, +16.59] | +14.29 [t +11.66, +16.91; crossed +9.63, +19.17] | +26.01 [t +24.35, +27.67; crossed +19.72, +32.05] | -2.56 [t -7.44, +2.31; crossed -9.37, +4.46] |
| T3 | [27, 27, 28, 28] | +12.66 [t +10.54, +14.78; crossed +8.11, +18.14] | +12.92 [t +10.61, +15.24; crossed +8.80, +17.86] | +25.58 [t +22.97, +28.20; crossed +18.92, +32.92] | -0.26 [t -3.84, +3.32; crossed -6.67, +6.20] |
| T1 - T3 | – | -6.90 [t -9.34, -4.45; crossed -13.18, -0.89] | -8.65 [t -11.05, -6.26; crossed -14.09, -3.86] | -15.55 [t -18.14, -12.96; crossed -24.05, -7.29] | +1.76 [t -2.33, +5.85; crossed -5.62, +9.26] |
- T1: rescue|QQ fail +6.36 [t +4.87, +7.69; crossed +3.07, +10.74]; damage|QQ success +45.35 [t +30.69, +54.49; crossed +24.47, +67.45]
- T2: rescue|QQ fail +20.07 [t +16.29, +22.12; crossed +12.12, +29.25]; damage|QQ success +36.66 [t +33.03, +39.21; crossed +25.12, +48.49]
- T3: rescue|QQ fail +39.57 [t +34.19, +43.22; crossed +26.87, +53.69]; damage|QQ success +19.01 [t +15.67, +22.18; crossed +12.20, +27.53]

## BF16 difficulty tertiles: BF16 difficulty define B -> estimate A (cuts {'q4': [0.0, 0.4444444444444444], 'q8': [0.0, 0.4444444444444444]}; T1 = hardest)

| stratum | tasks per cell | r | d | M | G |
|---|---|---|---|---|---|
| T1 | [34, 34, 34, 34] | +3.28 [t +2.04, +4.51; crossed +1.34, +5.84] | +3.41 [t +2.67, +4.15; crossed +1.54, +5.87] | +6.68 [t +5.28, +8.09; crossed +3.71, +10.25] | -0.13 [t -1.61, +1.35; crossed -3.16, +2.78] |
| T2 | [24, 24, 26, 26] | +13.39 [t +11.52, +15.26; crossed +9.04, +17.80] | +13.88 [t +11.10, +16.65; crossed +9.79, +18.48] | +27.27 [t +24.45, +30.08; crossed +21.11, +33.50] | -0.49 [t -4.30, +3.32; crossed -7.42, +5.87] |
| T3 | [27, 27, 25, 25] | +14.95 [t +13.31, +16.58; crossed +9.36, +21.18] | +10.41 [t +7.95, +12.87; crossed +6.66, +14.73] | +25.36 [t +21.89, +28.83; crossed +18.21, +33.54] | +4.54 [t +2.20, +6.87; crossed -2.25, +11.29] |
| T1 - T3 | – | -11.67 [t -12.84, -10.50; crossed -18.45, -5.62] | -7.00 [t -9.65, -4.36; crossed -11.80, -2.50] | -18.67 [t -21.83, -15.52; crossed -27.53, -10.93] | -4.67 [t -7.27, -2.07; crossed -12.27, +2.79] |
- T1: rescue|QQ fail +3.54 [t +2.18, +4.87; crossed +1.46, +6.31]; damage|QQ success +49.82 [t +37.67, +57.54; crossed +31.09, +68.35]
- T2: rescue|QQ fail +20.58 [t +17.81, +23.16; crossed +13.74, +28.18]; damage|QQ success +40.15 [t +34.40, +46.45; crossed +30.17, +52.14]
- T3: rescue|QQ fail +44.74 [t +39.21, +48.21; crossed +29.97, +60.30]; damage|QQ success +15.10 [t +11.42, +18.54; crossed +9.43, +22.40]

## Method

```
EXPLORATORY, POST HOC (review 2026-10-05, W3): do fragile tasks dominate the tau2 core W4 consequences? Low base success?
Cells: tau2 retail/airline core W4 (q4/q8 x awq_w4/gptq_w4_d1), Bank P, 20 complete blocks x 85 tasks = 1,700 units per cell, loaded exactly
as offdiag_null.load_tau2 (analyze_ghf roots: analysis/fork/holdout/ is never opened). Per unit (analyze_dev.effects): r = 1[Y_BQ=1, Y_QQ=0],
d = 1[Y_BQ=0, Y_QQ=1], M = r + d, G = r - d; non-divergent units = 0 (full-pool denominator). Pool = equal-weight mean of the four cells.
Split (fixed before any outcome is read; `--write-split` writes it alone): half(b) = int(sha256('frag-v1|' + b), 16) mod 2 (A = 0, B = 1).
(1) Fragility of a task in the defining half = its mean M over the four cells and that half's blocks; top 20% = the 17 of 85 tasks with the
largest fragility (ties broken by sha256('frag-v1|' + task)). In the OTHER half: r, d, M, G for top-20% vs rest, their difference, and the
top-20% share of the held-out turnover (sum of M over top tasks / sum over all; 20% if fragility does not persist). Both directions (A->B, B->A).
(2) Conditional rates, all 20 blocks: rescue rate among QQ failures P(Y_BQ=1 | Y_QQ=0) = sum r / sum (1 - Y_QQ), damage rate among QQ
successes P(Y_BQ=0 | Y_QQ=1) = sum d / sum Y_QQ (ratios of sums per cell; non-divergent units are in the denominators).
(3) BF16 difficulty: task BF16 success rate from the nonce-matched BF16 closed-loop runs (a6k2_<model>_bfpair_<block>, retail/airline only,
infra-missing tasks dropped as analyze_difficulty.bf16_task_stats) in the defining half, per model; tertiles (analyze_difficulty.tertile_labels,
ties go low, so strata sizes are reported); r, d, M, G in the other half, both directions.
Intervals 95%: held-out halves (9-11 blocks): t over per-block pool values (primary: only 9 or 11 blocks)
and crossed task x block bootstrap (tasks resampled over all 85, blocks over the held-out half; group membership fixed by the defining half);
full pool: block bootstrap (primary, K = 20), t, crossed. B = 2000, seed 20261001 (analyze_dev.SEED). Strata are defined on one half and
estimated on the other, so selection on the outcome (regression to the mean) does not enter the held-out estimates.
usage: python analysis/fork/task_fragility.py [--write-split] [--B 2000] -> analysis/fork/out/task_fragility_<UTC>.{md,json}
```

## Data sources (sha256)

- `analysis/insights/iter_3/out/snapshot_auto_20261001T0600Z.json` b3ab767fad5a679a2da6ccfeac301d67225a0f579124c0c8e8140b21101d7604
- `manifests/fork/splits_v1.json` f7e805b88a5a4bc06b18840f444354ca7f83b24af08e088556e8ea867a127043
- `analysis/fork/out/task_fragility_split_20261005T134815Z.json` a82040553b3c66c62f19684034ae3d279c696dedc29be55afc06264e3489157f
- `analysis/fork/analyze_dev.py` 5851a57b1a7b6199a2e9ddb113b85df33faeefe49980ff03a158857e80fda372
- `analysis/fork/analyze_ghf.py` 4190c9d588d046413d4e17eaf72755074ab68553cec92c935a99c5c9ff346000
- `analysis/fork/analyze_difficulty.py` a77f7d52ca5d43942106e7c9ba0006effbc8cfff17dabe5ca0486d0451cda8a6
- `analysis/fork/offdiag_null.py` 897d3b61c4e918c5c16bc633265b3e0ce82958d0817e9e88017d85e0159b3112
- `analysis/fork/task_fragility.py` cbb15f23b5d5f8a4c37b23892da8729665ae87b94dcd315ae88b653980174111
- units digest per cell: {'q4:awq_w4': 'ed25a43c6af22805', 'q4:gptq_w4_d1': 'd4b8404cc48c5025', 'q8:awq_w4': '4682d291cedfd736', 'q8:gptq_w4_d1': '55103355340116c3'}
- BF16 inputs: {'bf16_task_blocks_counted': 340, 'bf16_episodes': 3400}
