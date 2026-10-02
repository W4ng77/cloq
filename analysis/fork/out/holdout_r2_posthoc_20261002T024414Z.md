**TL;DR** POST-HOC, descriptive, not part of the pre-registered confirmation. Telecom holdout, W93 R2 on divergent states (success scale; pp; crossed task × block 95%): q4:gptq_w4_d1 (385 st): G -3.1, H +0.5, F +1.8, G−H -3.6 [-9.1, +1.8], off-diag 19.7% (expected under independent pairing 27.0%, κ 0.27), reversals 13; q8:gptq_w4_d1 (399 st): G -5.8, H -4.0, F -5.3, G−H -1.8 [-6.4, +2.9], off-diag 19.5% (expected under independent pairing 23.1%, κ 0.16), reversals 12; q8:awq_w4 (396 st): G -6.6, H -8.3, F -8.3, G−H +1.8 [-3.3, +6.8], off-diag 23.7% (expected under independent pairing 26.0%, κ 0.09), reversals 4. Prereg-weighted pool: G -4.6 [-7.8, -1.5], H -2.8 [-6.3, +0.6], F -2.5 [-6.2, +1.3], G−H -1.8 [-4.8, +1.1], off-diag 20.7% (expected 25.7%, κ 0.19), strict reversals 2.7%. The frozen primary endpoint (G_all) is untouched.

> **POST-HOC, descriptive, not part of the pre-registered confirmation.** Supplementary descriptive output under docs/insights/PREREG_FORK_CONFIRM.md §10 (supplementary descriptive; advisor-approved). Decides nothing.

Source: `analysis/fork/out/holdout_r2_posthoc_20261002T024414Z.json`; script sha `009306b59e4a`, analyze_holdout_confirm sha `2af1b6890def` (unmodified), git `8148721be3`. Snapshot `analysis/insights/iter_3/out/snapshot_holdout_20261002T0123Z.json` (sha `f5023c633f02`). Loaded through analyze_dev.split_guard(--split holdout) and analyze_holdout_confirm.load; admission = the confirmatory script's (§4.2–4.5). Analysed units digest = confirmatory output's (`0fbcc42ac775b00c…`, `analysis/fork/out/holdout_confirm_20261002T012353Z.json`).

Blocks used (K = 12): ['h01', 'h02', 'h03', 'h04', 'h05', 'h06', 'h07', 'h08', 'h09', 'h10', 'h11', 'h12']. Tasks: 34. Missing by reason: {"q4:gptq_w4_d1": {"structural: search: decision/trajectory count mismatch 61 vs 0": 1}, "q8:awq_w4": {"structural: search: decision/trajectory count mismatch 94 vs 0": 1}}.

Notation: G = Y_BQ−Y_QQ, H = Y_QB−Y_QQ, F = Y_BB−Y_QQ; Δ_Q = G, Δ_B = Y_BB−Y_QB, I = Δ_Q−Δ_B. Per cell: ratio over its divergent states; pool = ½·q4 GPTQ-W4 + ¼·q8 GPTQ-W4 + ¼·q8 AWQ-W4 of the cell ratios. Intervals: crossed task × block (two-way random-effects ANOVA moments on the delta-method linearisation of the ratio, normal) and t over the 12 per-block ratios (centred at their mean); 95% two-sided here, 90% in the JSON.

## 1. G, H, F and paired differences (pp, divergent states; crossed 95%)

| cell | n st | G | H | F | G−H | F−G | F−H | I |
|---|---|---|---|---|---|---|---|---|
| q4:gptq_w4_d1 | 385 | -3.1 [-9.0, +2.8] | +0.5 [-5.4, +6.4] | +1.8 [-4.8, +8.4] | -3.6 [-9.1, +1.8] | +4.9 [-0.2, +10.1] | +1.3 [-4.7, +7.3] | -4.4 [-12.5, +3.7] |
| q8:gptq_w4_d1 | 399 | -5.8 [-10.2, -1.3] | -4.0 [-10.2, +2.2] | -5.3 [-11.6, +1.1] | -1.8 [-6.4, +2.9] | +0.5 [-5.0, +6.0] | -1.3 [-4.5, +2.0] | -4.5 [-10.4, +1.4] |
| q8:awq_w4 | 396 | -6.6 [-13.0, -0.1] | -8.3 [-15.3, -1.3] | -8.3 [-15.5, -1.2] | +1.8 [-3.3, +6.8] | -1.8 [-7.4, +3.8] | +0.0 [-3.8, +3.8] | -6.6 [-14.5, +1.4] |
| pool (½, ¼, ¼) | 1180 | -4.6 [-7.8, -1.5] | -2.8 [-6.3, +0.6] | -2.5 [-6.2, +1.3] | -1.8 [-4.8, +1.1] | +2.2 [-1.0, +5.3] | +0.3 [-3.3, +4.0] | -5.0 [-9.6, -0.4] |

## 2. Same, block t over 12 per-block ratios (95%)

| cell | G | H | F | G−H | F−G | F−H | I | off-diag % | strict reversals % |
|---|---|---|---|---|---|---|---|---|---|
| q4:gptq_w4_d1 | -3.0 [-8.4, +2.4] | +0.7 [-5.4, +6.7] | +2.0 [-4.5, +8.4] | -3.7 [-6.3, -1.0] | +4.9 [+1.4, +8.5] | +1.3 [-3.1, +5.6] | -4.3 [-11.2, +2.7] | +19.7 [+16.7, +22.7] | +3.4 [+1.2, +5.5] |
| q8:gptq_w4_d1 | -5.7 [-10.0, -1.4] | -4.0 [-9.0, +1.1] | -5.3 [-10.2, -0.3] | -1.7 [-6.9, +3.4] | +0.4 [-5.7, +6.5] | -1.3 [-4.4, +1.8] | -4.3 [-10.6, +1.9] | +19.5 [+17.8, +21.2] | +3.0 [+1.2, +4.8] |
| q8:awq_w4 | -6.6 [-12.9, -0.3] | -8.3 [-13.5, -3.2] | -8.3 [-12.0, -4.7] | +1.8 [-2.9, +6.4] | -1.8 [-6.9, +3.3] | +0.0 [-3.8, +3.8] | -6.6 [-15.0, +1.8] | +23.7 [+20.7, +26.8] | +1.0 [-0.7, +2.7] |
| pool (½, ¼, ¼) | -4.6 [-6.4, -2.7] | -2.7 [-5.6, +0.1] | -2.4 [-5.7, +0.9] | -1.8 [-4.4, +0.8] | +2.1 [-1.1, +5.4] | +0.3 [-2.1, +2.7] | -4.9 [-8.1, -1.6] | +20.7 [+19.0, +22.3] | +2.7 [+1.2, +4.2] |

## 3. Δ_Q × Δ_B table and the marginal-preserving pairing agreement control

Counts `(Δ_Q, Δ_B)` per cell (pool row: prereg-weighted shares, %). The control gives the off-diagonal share expected if Δ_Q and Δ_B were paired independently with their observed margins, and Cohen's κ; it is a marginal-preserving pairing agreement control, not a null for interaction.

| cell | (−1,−1) | (−1,0) | (−1,1) | (0,−1) | (0,0) | (0,1) | (1,−1) | (1,0) | (1,1) | off-diag % [crossed 95%] | expected off-diag % | κ | strict reversals % [crossed 95%] (n) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| q4:gptq_w4_d1 | 6 | 15 | 11 | 22 | 295 | 16 | 2 | 10 | 8 | +19.7 [+10.9, +28.6] | 27.0 | 0.269 | +3.4 [+0.5, +6.2] (13) |
| q8:gptq_w4_d1 | 2 | 32 | 7 | 17 | 315 | 8 | 5 | 9 | 4 | +19.5 [+12.2, +26.9] | 23.1 | 0.155 | +3.0 [+0.9, +5.1] (12) |
| q8:awq_w4 | 6 | 42 | 3 | 12 | 294 | 14 | 1 | 22 | 2 | +23.7 [+15.1, +32.3] | 26.0 | 0.088 | +1.0 [-0.5, +2.5] (4) |
| pool (½, ¼, ¼) | 1.3 | 6.6 | 2.1 | 4.7 | 76.6 | 3.5 | 0.6 | 3.3 | 1.4 | +20.7 [+13.7, +27.7] | 25.7 | 0.195 | +2.7 [+0.6, +4.7] |

Margins (share of states with Δ = −1 / 0 / +1):

- q4:gptq_w4_d1: Δ_Q 0.083 / 0.865 / 0.052; Δ_B 0.078 / 0.831 / 0.091
- q8:gptq_w4_d1: Δ_Q 0.103 / 0.852 / 0.045; Δ_B 0.060 / 0.892 / 0.048
- q8:awq_w4: Δ_Q 0.129 / 0.808 / 0.063; Δ_B 0.048 / 0.904 / 0.048
- pool: Δ_Q 0.099 / 0.848 / 0.053; Δ_B 0.066 / 0.865 / 0.069

## 4. 16 outcome patterns (bit order BB, BQ, QB, QQ; counts, pool = weighted %)

| cell | 0000 | 0001 | 0010 | 0011 | 0100 | 0101 | 0110 | 0111 | 1000 | 1001 | 1010 | 1011 | 1100 | 1101 | 1110 | 1111 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| q4:gptq_w4_d1 | 279 | 11 | 17 | 6 | 8 | 2 | 2 | 5 | 11 | 11 | 10 | 4 | 8 | 5 | 2 | 4 |
| q8:gptq_w4_d1 | 292 | 30 | 16 | 2 | 8 | 9 | 5 | 1 | 6 | 7 | 10 | 2 | 4 | 2 | 1 | 4 |
| q8:awq_w4 | 281 | 40 | 11 | 6 | 21 | 7 | 1 | 1 | 14 | 3 | 4 | 2 | 2 | 0 | 1 | 2 |
| pool (½, ¼, ¼) % | 72.3 | 5.8 | 3.9 | 1.3 | 2.9 | 1.3 | 0.6 | 0.8 | 2.7 | 2.1 | 2.2 | 0.8 | 1.4 | 0.8 | 0.4 | 0.9 |

## 5. Arm success rates (%, divergent states; crossed 95%)

| cell | Y_BB | Y_BQ | Y_QB | Y_QQ |
|---|---|---|---|---|
| q4:gptq_w4_d1 | +14.3 [+5.5, +23.1] | +9.4 [+3.7, +15.0] | +13.0 [+6.1, +19.9] | +12.5 [+4.7, +20.2] |
| q8:gptq_w4_d1 | +9.0 [+2.9, +15.1] | +8.5 [+3.9, +13.1] | +10.3 [+4.6, +16.0] | +14.3 [+7.3, +21.3] |
| q8:awq_w4 | +7.1 [+2.1, +12.0] | +8.8 [+4.3, +13.3] | +7.1 [+2.3, +11.8] | +15.4 [+7.8, +23.0] |
| pool (½, ¼, ¼) | +11.2 [+5.0, +17.4] | +9.0 [+4.8, +13.3] | +10.8 [+5.8, +15.9] | +13.7 [+8.0, +19.3] |

## 6. Inclusion

- q4:gptq_w4_d1: weight 0.5; 396 units, 385 divergent states (= confirmatory 385); tasks included 33; structurally excluded ['telecom:[mms_issue]bad_network_preference|break_app_sms_permission|user_abroad_roaming_disabled_on[PERSONA:Hard]']
- q8:gptq_w4_d1: weight 0.25; 408 units, 399 divergent states (= confirmatory 399); tasks included 34; structurally excluded none
- q8:awq_w4: weight 0.25; 396 units, 396 divergent states (= confirmatory 396); tasks included 33; structurally excluded ['telecom:[mobile_data_issue]airplane_mode_on|bad_network_preference|data_mode_off|user_abroad_roaming_disabled_on[PERSONA:Hard]']
