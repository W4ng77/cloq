**TL;DR** EXPLORATORY. Under the Sonnet 5.5 simulator (SIMCTRL-P, 80 states, 20 per cell, R = 5 per arm), pooled (equal weight over 4 cells): mean Î = -0.015, mean Î² = 0.110 (uncorrected), mean noise correction = 0.060, mean U = 0.050 [+0.004, +0.107] (states) / [+0.001, +0.111] (task cluster) — the estimate of the mean squared interaction E[I_s²] on the probability scale. Advisor's first computation 0.110 / 0.060 / 0.050: reproduced to 3 dp. EXPLORATORY: no significance claim; estimates the mean squared interaction E[I_s²], NOT the share of states with interaction and NOT a variance; must NOT be converted to or compared with the deterministic 26.9%.

# SIMCTRL-P interaction diagnostic (EXPLORATORY) (20261002T024357Z)

Script `analysis/fork/simctrl_p_interaction.py` (sha d37944d2f30d; imports analyze_simctrl_p sha 35eb9d91b1d7), git a1c9150eba. Manifest `manifests/fork/simctrl_p_v1.json` (sha fa3dbf366b85, frozen). Rows `analysis/fork/simctrl_p/<cell>/b{1,2}/simctrl_p_rows.jsonl` via analyze_simctrl_p's loaders (gate and row re-verification pass); per-arm replicate outcomes equal those stored in `analysis/fork/out/simctrl_p_20261002T015200Z.json` for all 80 states. Full numbers: `analysis/fork/out/simctrl_p_interaction_20261002T024357Z.json`.

**Label.** EXPLORATORY: no significance claim; estimates the mean squared interaction E[I_s²], NOT the share of states with interaction and NOT a variance; must NOT be converted to or compared with the deterministic 26.9%.

**Sign convention** (consistent with W93): Δ_Q = Y_BQ − Y_QQ, Δ_B = Y_BB − Y_QB, I = Δ_Q − Δ_B = Y_BQ + Y_QB − Y_BB − Y_QQ. Per state s, with arm means Ȳ_a,s over n_a = 5 valid replicates: Î_s = Ȳ_BQ + Ȳ_QB − Ȳ_BB − Ȳ_QQ (= Δ̂_Q − Δ̂_B exactly); U_s = Î_s² − Σ_a Ȳ_a,s(1 − Ȳ_a,s)/(n_a − 1). Since E[Î²] = I² + Σ_a p_a(1 − p_a)/n_a and E[Ȳ(1 − Ȳ)/(n − 1)] = p(1 − p)/n, U_s is unbiased for I_s². Negative U_s and negative cell means are kept (no truncation).

**Independence assumptions.**

- Given the state, the n_a replicates of each arm are i.i.d. Bernoulli(p_a,s) (the simulator and controllers are re-sampled independently per replicate; no shared cache or seed across replicates).
- The four arms of a state are mutually independent given the state (no shared randomness across arms).
- n_a ≥ 2 valid replicates per arm (here n_a = 5 for every arm: no missing replicate).
- Unbiasedness is per state and conditional on the state; the pooled mean of U estimates the equal-weight-over-cells average of I_s² over these 80 frozen states (20 per cell), not over any wider state population.
- Unexposed branches (10 BB, 10 QB arm-replicates with 0 user calls) keep their Y, as in the final SIMCTRL-P analysis.

**What it is not.** Mean U estimates E[I_s²], the mean squared probability-scale interaction over these states. It is not the share of states with I ≠ 0 (a state with |I_s| = 0.2 contributes 0.04), not a variance of anything, and carries no significance claim; it is not converted to or compared with the deterministic W93 off-diagonal 26.9%.

## Per cell and pooled (raw probability scale; 95% intervals: stratified state bootstrap, then task-cluster bootstrap)

| cell | states (tasks) | mean Î | mean Î² (uncorrected) | mean noise correction Σ_a Ȳ(1−Ȳ)/(n_a−1) | mean U (estimate of E[I_s²]) | states with U < 0 |
|---|---|---|---|---|---|---|
| q4:gptq_w4_d1 | 20 (18) | -0.090<br>[-0.220, +0.030]<br>[-0.218, +0.033] | +0.090<br>[+0.032, +0.164]<br>[+0.031, +0.169] | +0.064<br>[+0.033, +0.097]<br>[+0.029, +0.101] | +0.026<br>[-0.029, +0.094]<br>[-0.027, +0.099] | 6 |
| q4:awq_w4 | 20 (18) | -0.060<br>[-0.160, +0.030]<br>[-0.160, +0.033] | +0.048<br>[+0.016, +0.092]<br>[+0.015, +0.089] | +0.073<br>[+0.042, +0.103]<br>[+0.042, +0.107] | -0.025<br>[-0.066, +0.022]<br>[-0.071, +0.013] | 9 |
| q8:gptq_w4_d1 | 20 (17) | +0.030<br>[-0.100, +0.170]<br>[-0.096, +0.174] | +0.090<br>[+0.006, +0.218]<br>[+0.006, +0.219] | +0.042<br>[+0.018, +0.068]<br>[+0.017, +0.074] | +0.048<br>[-0.037, +0.172]<br>[-0.041, +0.180] | 6 |
| q8:awq_w4 | 20 (20) | +0.060<br>[-0.140, +0.270]<br>[-0.120, +0.280] | +0.212<br>[+0.060, +0.400]<br>[+0.058, +0.416] | +0.061<br>[+0.030, +0.093]<br>[+0.030, +0.095] | +0.151<br>[+0.006, +0.336]<br>[+0.002, +0.343] | 6 |
| **pool (equal weight, 4 cells)** | 80 (49) | -0.015<br>[-0.085, +0.055]<br>[-0.083, +0.064] | +0.110<br>[+0.061, +0.169]<br>[+0.060, +0.169] | +0.060<br>[+0.045, +0.075]<br>[+0.043, +0.079] | +0.050<br>[+0.004, +0.107]<br>[+0.001, +0.111] | 27 |

Advisor check (pooled): mean_I2 0.1100 vs 0.110; mean_corr 0.0600 vs 0.060; mean_U 0.0500 vs 0.050.
Mean U = mean Î² − mean correction holds exactly per cell and pooled. Intervals are descriptive (EXPLORATORY).

