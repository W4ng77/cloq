**TL;DR** Marginal-preserving pairing agreement control for the W93 (Δ_Q, Δ_B) 3×3 tables. Equal-weight W4 pool (the paper's target, 4 cells, 20 common blocks): observed off-diagonal 26.9 [25.7, 28.1]% vs 38.0 [36.7, 39.0]% expected under marginal-preserving within-cell re-pairing; κ = 0.291 [0.265, 0.318] (block bootstrap; crossed [0.223, 0.359]). KV8 pool: 15.3 [13.2, 17.3]% vs 33.6 [31.8, 35.3]%, κ = 0.546 [0.487, 0.604]. Every main cell shows less disagreement than the pairing control (κ 0.17–0.57). Count-summed W4 (labelled separately, not the paper's target): 27.10% observed, 37.85% expected, κ 0.284. Lower-than-expected disagreement means the action effects under the two controllers agree more than random cross-state pairing would; the same-state I = Δ_Q − Δ_B ≠ 0 in the deterministic, replay-verified setting is non-additive interaction on the success scale; this identification does not depend on exceeding the pairing control.

# Marginal-preserving pairing agreement control for the (Δ_Q, Δ_B) table (20261002T024240Z)

Script `analysis/fork/agreement_control.py` (sha 7aae7273c75a; imports analyze_ghf sha 4190c9d588d0, analyze_dev sha 5851a57b1a7b), git a1c9150eba. Input `analysis/fork/out/ghf_20261001T211519Z.json` (snapshot `20261001T0600Z`). Full numbers: `analysis/fork/out/agreement_control_20261002T024240Z.json`.

Inputs re-derived through analyze_ghf's loaders: per-cell 3×3 counts equal the ghf JSON for 11/11 cells; units digests equal the reference for 11/11. Reproduction: equal-weight W4 pool off-diagonal = 26.931% (target 26.9%: reproduced); count-summed W4 = 27.10% / 37.85% / κ 0.284 (targets 27.10 / 37.85 / 0.284).

**Definitions.** Rows Δ_Q = Y_BQ − Y_QQ, columns Δ_B = Y_BB − Y_QB, values in {−1, 0, +1}. Observed agreement p_o = Σ_k P(Δ_Q = k, Δ_B = k) (diagonal share; off-diagonal = 1 − p_o = P(I ≠ 0)). Expected agreement under independent pairing that preserves both marginals p_e = Σ_k p_Q(k)·p_B(k) (each cell's own marginals: states are re-paired only within a cell). Cohen's κ = (p_o − p_e)/(1 − p_e). Excess agreement = p_o − p_e (pp).

**Interpretation (terminology fixed).** This is a marginal-preserving pairing agreement control, not a no-interaction null and not a chance baseline for controller dependence. Lower-than-expected disagreement means the action effects under the two controllers agree more than random cross-state pairing would; the same-state I = Δ_Q − Δ_B ≠ 0 in the deterministic, replay-verified setting is non-additive interaction on the success scale; this identification does not depend on exceeding the pairing control.

**Aggregation.** Equal-weight pools = the paper's target weights (analyze_ghf.pool: equal weight per cell over the complete blocks common to every pooled cell): pool p_o, p_e = means of per-cell values; pool κ from those means (mean of per-cell κ also given). Count-summed pools add the cells' counts and use the summed table's marginals; they are a different weighting (cells with more divergent states weigh more) and are reported in their own table, never mixed with the equal-weight figures.

**Intervals.** Same draws as analyze_ghf (analyze_dev.Boot, B = 2000, seed 20261001). Primary = block bootstrap over the fixed task pool (ratio of block sums; the 9 shares of one draw form one table, so p_o, p_e and κ are computed per draw); secondary = crossed task × block bootstrap (new tasks). Stress cells (3 blocks): t over per-block values is primary; they are flagged and never pooled.

## 1. Per cell (each cell's divergent states; %, κ unitless; primary 95% interval)

| cell | n | marg. Δ_Q (−1/0/+1 %) | marg. Δ_B (−1/0/+1 %) | observed agreement | observed off-diag | expected agreement | expected off-diag | excess agreement (pp) | κ | κ crossed |
|---|---|---|---|---|---|---|---|---|---|---|
| q4:awq_w4 | 1439 | 12.0/76.4/11.6 | 12.4/76.9/10.7 | 70.7 [68.8, 72.8] | 29.3 [27.2, 31.2] | 61.5 [59.6, 63.9] | 38.5 [36.1, 40.4] | 9.1 [8.2, 10.1] | 0.238 [0.215, 0.261] | [0.138, 0.343] |
| q4:gptq_w3 (STRESS, flagged: 3 blocks, t primary, not poolable) | 232 | 11.2/78.9/9.9 | 12.5/78.0/9.5 | 68.5 [47.4, 89.5] | 31.5 [10.5, 52.6] | 63.9 [55.1, 72.6] | 36.1 [27.4, 44.9] | 4.7 [-7.7, 17.0] | 0.129 [-0.258, 0.534] | [-0.049, 0.347] |
| q4:gptq_w4_d1 | 1102 | 13.4/76.0/10.5 | 14.5/74.1/11.3 | 75.0 [72.7, 77.2] | 25.0 [22.8, 27.3] | 59.5 [57.5, 61.9] | 40.5 [38.1, 42.5] | 15.4 [12.8, 18.1] | 0.381 [0.325, 0.437] | [0.245, 0.520] |
| q4:kvq_int4_rot (STRESS, flagged: 3 blocks, t primary, not poolable) | 233 | 7.7/79.4/12.9 | 11.2/74.7/14.2 | 67.0 [51.7, 82.4] | 33.0 [17.6, 48.3] | 62.0 [48.2, 76.1] | 38.0 [23.9, 51.8] | 5.0 [-0.1, 9.9] | 0.131 [-0.016, 0.280] | [-0.034, 0.298] |
| q4:kvq_int8 | 593 | 10.8/79.4/9.8 | 10.6/77.4/12.0 | 84.3 [81.4, 87.3] | 15.7 [12.7, 18.6] | 63.8 [61.3, 66.8] | 36.2 [33.2, 38.7] | 20.5 [17.1, 23.7] | 0.567 [0.487, 0.643] | [0.412, 0.705] |
| q8:awq_w4 | 1562 | 10.3/77.3/12.4 | 9.7/78.7/11.6 | 69.5 [67.4, 71.7] | 30.5 [28.3, 32.6] | 63.2 [61.8, 64.9] | 36.8 [35.1, 38.2] | 6.3 [4.8, 7.8] | 0.171 [0.128, 0.213] | [0.075, 0.274] |
| q8:gptq_w3 (STRESS, flagged: 3 blocks, t primary, not poolable) | 242 | 8.7/80.6/10.7 | 11.2/76.0/12.8 | 76.9 [59.8, 94.0] | 23.1 [6.0, 40.2] | 63.6 [47.5, 80.3] | 36.4 [19.7, 52.5] | 13.2 [10.2, 15.9] | 0.364 [0.190, 0.548] | [0.199, 0.532] |
| q8:gptq_w4_d1 | 1473 | 8.7/79.3/12.0 | 8.8/77.3/13.8 | 77.1 [75.5, 78.9] | 22.9 [21.1, 24.5] | 63.7 [61.9, 65.7] | 36.3 [34.3, 38.1] | 13.4 [11.5, 15.1] | 0.369 [0.324, 0.409] | [0.235, 0.492] |
| q8:kvq_int4_rot (STRESS, flagged: 3 blocks, t primary, not poolable) | 239 | 9.2/78.2/12.6 | 9.2/76.2/14.6 | 69.0 [57.0, 81.0] | 31.0 [19.0, 43.0] | 62.3 [48.3, 76.6] | 37.7 [23.4, 51.7] | 6.8 [2.6, 10.5] | 0.179 [0.098, 0.251] | [0.032, 0.327] |
| q8:kvq_int8 | 855 | 8.2/82.3/9.5 | 7.7/81.8/10.5 | 85.1 [83.0, 87.1] | 14.9 [12.9, 17.0] | 68.9 [66.9, 71.1] | 31.1 [28.9, 33.1] | 16.2 [13.9, 18.4] | 0.522 [0.462, 0.584] | [0.386, 0.656] |
| q8:rtn_w3 (STRESS, flagged: 3 blocks, t primary, not poolable) | 255 | 3.5/93.3/3.1 | 10.6/75.7/13.7 | 71.0 [66.5, 75.4] | 29.0 [24.6, 33.5] | 71.4 [69.3, 73.5] | 28.6 [26.5, 30.7] | -0.5 [-6.7, 5.9] | -0.016 [-0.233, 0.200] | [-0.101, 0.142] |

## 2. Equal-weight pools (paper's target weights; block bootstrap, then crossed)

| pool | cells | blocks | states/cell | observed off-diag | expected off-diag | excess agreement (pp) | κ (from pooled p_o, p_e) | mean of per-cell κ |
|---|---|---|---|---|---|---|---|---|
| W4:q4 | q4:awq_w4, q4:gptq_w4_d1 | 20 | 1439, 1102 | 27.2 [25.6, 28.7]<br>[21.4, 33.1] | 39.5 [37.5, 41.0]<br>[32.6, 45.7] | 12.3 [10.8, 13.8]<br>[8.4, 16.4] | 0.311 [0.279, 0.343]<br>[0.220, 0.405] | 0.310 [0.279, 0.341] |
| W4:q8 | q8:awq_w4, q8:gptq_w4_d1 | 20 | 1562, 1473 | 26.7 [25.1, 28.2]<br>[20.9, 32.6] | 36.5 [35.4, 37.5]<br>[29.6, 42.9] | 9.8 [8.7, 10.9]<br>[6.2, 13.6] | 0.269 [0.237, 0.302]<br>[0.179, 0.363] | 0.270 [0.239, 0.303] |
| W4:all | q4:awq_w4, q4:gptq_w4_d1, q8:awq_w4, q8:gptq_w4_d1 | 20 | 1439, 1102, 1562, 1473 | 26.9 [25.7, 28.1]<br>[22.1, 32.0] | 38.0 [36.7, 39.0]<br>[32.2, 43.2] | 11.1 [10.0, 12.2]<br>[8.2, 13.8] | 0.291 [0.265, 0.318]<br>[0.223, 0.359] | 0.290 [0.264, 0.315] |
| KV8:q4 | q4:kvq_int8 | 22 | 593 | 15.7 [12.7, 18.6]<br>[9.7, 22.1] | 36.2 [33.2, 38.7]<br>[26.1, 45.6] | 20.5 [17.1, 23.7]<br>[12.4, 29.1] | 0.567 [0.487, 0.643]<br>[0.412, 0.705] | 0.567 [0.487, 0.643] |
| KV8:q8 | q8:kvq_int8 | 22 | 855 | 14.9 [12.9, 17.0]<br>[9.9, 20.1] | 31.1 [28.9, 33.1]<br>[23.2, 39.4] | 16.2 [13.9, 18.4]<br>[10.0, 23.6] | 0.522 [0.462, 0.584]<br>[0.386, 0.656] | 0.522 [0.462, 0.584] |
| KV8:all | q4:kvq_int8, q8:kvq_int8 | 22 | 593, 855 | 15.3 [13.2, 17.3]<br>[10.9, 19.7] | 33.6 [31.8, 35.3]<br>[26.9, 40.3] | 18.4 [16.2, 20.5]<br>[13.1, 24.2] | 0.546 [0.487, 0.604]<br>[0.436, 0.652] | 0.544 [0.486, 0.601] |

Stress cells are not pooled (one common complete block), as in analyze_ghf.

## 3. Count-summed pools (SEPARATE weighting, labelled; not the paper's equal-weight target)

| pool | states | observed off-diag % | expected off-diag % | excess agreement (pp) | κ |
|---|---|---|---|---|---|
| W4:q4 (count-summed) | 2541 | 27.47 | 39.35 | +11.88 | 0.302 |
| W4:q8 (count-summed) | 3035 | 26.79 | 36.51 | +9.72 | 0.266 |
| W4:all (count-summed) | 5576 | 27.10 | 37.85 | +10.75 | 0.284 |
| KV8:q4 (count-summed) | 593 | 15.68 | 36.20 | +20.52 | 0.567 |
| KV8:q8 (count-summed) | 855 | 14.85 | 31.05 | +16.20 | 0.522 |
| KV8:all (count-summed) | 1448 | 15.19 | 33.21 | +18.02 | 0.543 |

Point estimates only for the count-summed rows (no interval: the paper's intervals belong to the equal-weight target).

