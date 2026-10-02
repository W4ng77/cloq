# Matched oracles and a post-hoc KL reference row for the frozen token trigger (20261002T024423Z)

## TL;DR

- **Action-replacement oracle** (same rows, same per-cell counts as the frozen rule; hindsight). On f02/f03 U1 (1020 rows; 38 rescues, 31 damages) it nets +34 / +38 / +38 at 5/10/20% (+3.33 / +3.73 / +3.73 pp of 1020). The frozen rule nets +4 / +2 / +5 and random +0.21 / +0.98 / +2.38. The rule captured 6/7/16 of the oracle's 34/38/38 rescues and added 2/5/11 damages. At 10% and 20% every rescue in the bank fits in the budget (76 and 184 zero-effect fill rows); at 5% the cells q4_awq_w4, q4_gptq_w4_d1, q4_kvq_int8, q8_kvq_int8 have fewer rescues than selections (16 fill rows).
- **Three-option menu oracle** (diagnostic only; hindsight AND a different replacement type allowed; not a same-cost deployment and not comparable to the action rule). On Bank P divergent states of the 6 core cells, E[max(G,H,F,0)] = 0.148–0.206 per cell (1343/7024 states pooled = 0.191); action-only E[max(G,0)] is 793/7024 = 0.113. On the Bank U U1 f02/f03 rows: 93/1020 = 0.091 (action-only 38/1020).
- **KL reference row** (post-hoc; needs BF16; not Q-only; not a DMR reproduction). Chosen on f01 U1: **KLu_max** (top-20-union KL(B||Q) + tail bucket). On f02/f03 U1: selected 72/126/257, net -1, +1, +3 vs random +0.45/+0.82/+1.59, exact p 0.8337/0.5483/0.3984, Holm(3) 1.0000/1.0000/1.0000; r/d 5/6, 8/7, 18/15; turnover captured 11/15/33 vs random 4.58/7.54/16.73 (p 0.0038/0.0048/0.0000). No row was missing a KL score (0 missing; nothing imputed).
- **Reading.** The frozen Q-only rule realises 4/34, 2/38 and 5/38 of the same-budget action-oracle net. The headroom is large because rescues are rare (38/1020) and the rule's selections are mostly zero-effect rows, plus damages that cancel most of its rescues. A BF16-informed KL score, chosen on f01 the same way, also captures turnover above chance (count-matched to the rule's per-cell budget: 7/15/32 vs the rule's 8/12/27) but does not select net-beneficial replacements either; the non-chosen KL candidates (KLu_0, KLu_mean) look better on f02/f03, but picking them now would be selection on validation data.

Frozen rule sha256 `335e737d54bf59b948022b8054897ba703a1b9df6665f55bf6ab19b70333c052` (chosen score S_mm), unchanged; the W98 primary numbers (50/114/222 selected, net +4/+2/+5, p .0345/.4169/.2617) are reproduced by the imported escalate() before anything else runs. Script `analysis/fork/oracle_trigger.py` sha256 `df8dfdf279ab0d7f…`; analyze_token_mech.py sha256 `a4a8a19aaff5b942…`; git HEAD at run `8148721be3`.

## 1a. Action-replacement oracle (direct upper bound for the trigger)

Same 1020 f02/f03 U1 rows; per cell the oracle selects exactly as many rows m_c as the frozen rule did at that budget, taking only rows with G = Y_BQ − Y_QQ > 0; if a cell has fewer rescues than m_c, all of them are taken and the rest are G = 0 rows ('zero fill'). It never selects a damage. Random = matched-count random-trigger expectation (exact). pp = count / 1020 × 100. Hindsight selection, not a policy.

| budget | selected | oracle r / d / net (pp) | zero fill | frozen r / d / net (pp) | random net (pp) | headroom oracle − frozen | frozen rescues / oracle rescues |
|---|---|---|---|---|---|---|---|
| 5% | 50 | 34 / 0 / +34 (+3.33) | 16 | 6 / 2 / +4 (+0.39) | +0.21 (+0.02) | +30 (+2.94) | 6/34 = 0.176 |
| 10% | 114 | 38 / 0 / +38 (+3.73) | 76 | 7 / 5 / +2 (+0.20) | +0.98 (+0.10) | +36 (+3.53) | 7/38 = 0.184 |
| 20% | 222 | 38 / 0 / +38 (+3.73) | 184 | 16 / 11 / +5 (+0.49) | +2.38 (+0.23) | +33 (+3.24) | 16/38 = 0.421 |

Total rescues available in the bank: 38 (damages 31, turnover 69).

Per cell (selected m_c; R = rescues in the cell; oracle net; frozen r/d/net; random net):

| cell | N | R | D | 5%: m, oracle, frozen r/d/net, random | 10%: m, oracle, frozen r/d/net, random | 20%: m, oracle, frozen r/d/net, random |
|---|---|---|---|---|---|---|
| q4_awq_w4 | 170 | 4 | 8 | 11, +4 (fill 7), 0/0/+0, -0.26 | 18, +4 (fill 14), 0/3/-3, -0.42 | 31, +4 (fill 27), 0/4/-4, -0.73 |
| q4_gptq_w4_d1 | 170 | 6 | 7 | 7, +6 (fill 1), 1/1/+0, -0.04 | 17, +6 (fill 11), 1/1/+0, -0.10 | 29, +6 (fill 23), 1/2/-1, -0.17 |
| q4_kvq_int8 | 170 | 4 | 6 | 10, +4 (fill 6), 1/0/+1, -0.12 | 16, +4 (fill 12), 1/0/+1, -0.19 | 26, +4 (fill 22), 2/2/+0, -0.31 |
| q8_awq_w4 | 170 | 12 | 6 | 9, +9, 2/0/+2, +0.32 | 18, +12 (fill 6), 3/0/+3, +0.64 | 34, +12 (fill 22), 5/0/+5, +1.20 |
| q8_gptq_w4_d1 | 170 | 8 | 3 | 7, +7, 2/1/+1, +0.21 | 22, +8 (fill 14), 2/1/+1, +0.65 | 50, +8 (fill 42), 7/3/+4, +1.47 |
| q8_kvq_int8 | 170 | 4 | 1 | 6, +4 (fill 2), 0/0/+0, +0.11 | 23, +4 (fill 19), 0/0/+0, +0.41 | 52, +4 (fill 48), 1/0/+1, +0.92 |

## 1b. Three-option menu oracle (extra diagnostic; NOT comparable to the action rule)

**Label:** hindsight outcome selection that ALSO allows different replacement types (replace only the continuation, H; or both action and continuation, F; or only the action, G). Replacing the continuation means running B for the rest of the episode, so this is neither the same intervention nor the same cost as one-step escalation. Y is binary, so max(G, H, F, 0) = 1 exactly when QQ fails and at least one of BQ, QB, BB succeeds; E[max(G,H,F,0)] therefore equals the share of states where some arm beats QQ. 95% Clopper–Pearson intervals over states (states are not independent across tasks/blocks; the interval is descriptive). Within-cell only; cross-cell comparisons are descriptive (each cell selects its own states).

### Bank P divergent states (W93 admission; analyze_ghf/analyze_dev loaders)

| cell | family | states | QQ success | E[max(G,H,F,0)] = share some arm beats QQ [CP 95%] | action-only E[max(G,0)] | G>0 / H>0 / F>0 | beats QQ only via H/F | E[G] / E[H] / E[F] | digest = dev_all |
|---|---|---|---|---|---|---|---|---|---|
| q4:awq_w4 | W4 | 1439 | 512 | 293 = 0.204 [0.183, 0.225] | 0.116 | 167 / 148 / 164 | 126 | -0.004 / +0.009 / -0.008 | True |
| q4:gptq_w3 | stress | 232 | 78 | 49 = 0.211 [0.161, 0.269] | 0.099 | 23 / 32 / 25 | 26 | -0.013 / +0.043 / +0.013 | True |
| q4:gptq_w4_d1 | W4 | 1102 | 415 | 215 = 0.195 [0.172, 0.220] | 0.105 | 116 / 96 / 111 | 99 | -0.029 / +0.007 / -0.025 | True |
| q4:kvq_int4_rot | stress | 233 | 70 | 71 = 0.305 [0.246, 0.368] | 0.129 | 30 / 34 / 47 | 41 | +0.051 / +0.094 / +0.124 | True |
| q4:kvq_int8 | KV8 | 593 | 218 | 89 = 0.150 [0.122, 0.181] | 0.098 | 58 / 24 / 68 | 31 | -0.010 / -0.025 / -0.012 | True |
| q8:awq_w4 | W4 | 1562 | 479 | 316 = 0.202 [0.183, 0.223] | 0.124 | 194 / 153 / 192 | 122 | +0.021 / -0.013 / +0.006 | True |
| q8:gptq_w3 | stress | 242 | 63 | 49 = 0.203 [0.154, 0.259] | 0.107 | 26 / 21 / 29 | 23 | +0.021 / +0.004 / +0.021 | True |
| q8:gptq_w4_d1 | W4 | 1473 | 404 | 303 = 0.206 [0.185, 0.227] | 0.120 | 177 / 101 / 208 | 126 | +0.033 / +0.004 / +0.054 | True |
| q8:kvq_int4_rot | stress | 239 | 67 | 59 = 0.247 [0.194, 0.307] | 0.126 | 30 / 21 / 34 | 29 | +0.034 / -0.008 / +0.046 | True |
| q8:kvq_int8 | KV8 | 855 | 231 | 127 = 0.148 [0.125, 0.174] | 0.095 | 81 / 33 / 87 | 46 | +0.013 / -0.004 / +0.025 | True |
| q8:rtn_w3 | stress | 255 | 34 | 80 = 0.314 [0.257, 0.375] | 0.031 | 8 / 45 / 58 | 72 | -0.004 / +0.153 / +0.184 | True |

Pooled over 6 core cells (W4 + KV8) (state-weighted, descriptive): some arm beats QQ 1343/7024 = 0.191 [0.182, 0.201]; action-only 793/7024 = 0.113.

Pooled over W4 core (4 cells) (state-weighted, descriptive): some arm beats QQ 1127/5576 = 0.202 [0.192, 0.213]; action-only 654/5576 = 0.117.

Stress cells (gptq_w3, kvq_int4_rot, rtn_w3; 3 blocks) are listed for completeness and are not pooled.

Winning arm sets when QQ fails (Bank P; keys = arms that succeed among BQ/QB/BB):

- q4:awq_w4: {'BB': 51, 'BQ': 50, 'BQBB': 44, 'BQQB': 22, 'BQQBBB': 51, 'QB': 57, 'QBBB': 18}
- q4:gptq_w3: {'BB': 8, 'BQ': 6, 'BQBB': 3, 'BQQB': 5, 'BQQBBB': 9, 'QB': 13, 'QBBB': 5}
- q4:gptq_w4_d1: {'BB': 32, 'BQ': 36, 'BQBB': 51, 'BQQB': 14, 'BQQBBB': 15, 'QB': 54, 'QBBB': 13}
- q4:kvq_int4_rot: {'BB': 19, 'BQ': 9, 'BQBB': 9, 'BQQB': 2, 'BQQBBB': 10, 'QB': 13, 'QBBB': 9}
- q4:kvq_int8: {'BB': 16, 'BQ': 8, 'BQBB': 41, 'BQQB': 2, 'BQQBBB': 7, 'QB': 11, 'QBBB': 4}
- q8:awq_w4: {'BB': 67, 'BQ': 53, 'BQBB': 43, 'BQQB': 33, 'BQQBBB': 65, 'QB': 38, 'QBBB': 17}
- q8:gptq_w3: {'BB': 10, 'BQ': 8, 'BQBB': 10, 'BQQB': 4, 'BQQBBB': 4, 'QB': 8, 'QBBB': 5}
- q8:gptq_w4_d1: {'BB': 75, 'BQ': 45, 'BQBB': 82, 'BQQB': 16, 'BQQBBB': 34, 'QB': 34, 'QBBB': 17}
- q8:kvq_int4_rot: {'BB': 16, 'BQ': 13, 'BQBB': 9, 'BQQB': 2, 'BQQBBB': 6, 'QB': 10, 'QBBB': 3}
- q8:kvq_int8: {'BB': 28, 'BQ': 20, 'BQBB': 46, 'BQQB': 5, 'BQQBBB': 10, 'QB': 15, 'QBBB': 3}
- q8:rtn_w3: {'BB': 32, 'BQ': 1, 'BQBB': 2, 'BQQB': 1, 'BQQBBB': 4, 'QB': 20, 'QBBB': 20}

### Same diagnostic on the Bank U U1 f02/f03 rows (all four arms exist on Bank U)

| cell | rows | QQ success | some arm beats QQ [CP 95%] | action-only (G>0) | G>0 / H>0 / F>0 | beats QQ only via H/F |
|---|---|---|---|---|---|---|
| q4_awq_w4 | 170 | 62 | 17 = 0.100 [0.059, 0.155] | 4 | 4 / 14 / 13 | 13 |
| q4_gptq_w4_d1 | 170 | 73 | 14 = 0.082 [0.046, 0.134] | 6 | 6 / 9 / 9 | 8 |
| q4_kvq_int8 | 170 | 63 | 14 = 0.082 [0.046, 0.134] | 4 | 4 / 8 / 11 | 10 |
| q8_awq_w4 | 170 | 52 | 20 = 0.118 [0.073, 0.176] | 12 | 12 / 12 / 17 | 8 |
| q8_gptq_w4_d1 | 170 | 53 | 12 = 0.071 [0.037, 0.120] | 8 | 8 / 6 / 7 | 4 |
| q8_kvq_int8 | 170 | 46 | 16 = 0.094 [0.055, 0.148] | 4 | 4 / 10 / 15 | 12 |
| pooled (6 cells) | 1020 | 349 | 93 = 0.091 [0.074, 0.111] | 38 | 38 / 59 / 72 | 55 |

Bank U U1 rows are sampled ordinary states of Q's own trajectory (most have identical B/Q actions), so the denominator differs from Bank P's divergent states; the two banks are not compared numerically.

## 2. KL reference row (post-hoc auxiliary baseline using BF16 information)

**Labels.** (i) Needs BF16: the score requires B's next-token distribution over Q's proposed action, i.e. a B forward (prefill) pass of the prompt plus a_Q at every decision (here a mean of 6709.3 prompt tokens + 82.3 a_Q tokens per U1 validation decision), in addition to Q's decode; it is not a Q-only trigger and costs a BF16 prefill at every step, not only at escalated steps. (ii) Post-hoc: the f02/f03 outcomes were seen in W98 before this baseline was specified, so this is not a prospective validation. (iii) KL definition: KLu(B||Q): KL over the union of B's and Q's top-20 next-token sets plus one tail bucket, per a_Q token, teacher-forced on the identical prompt ids (score_driver.py); truncated, not the full KL. (iv) Not a DMR reproduction (DMR trains a router; this is a fixed threshold on one divergence score).

**Fit (f01 U1 only, n = 510).** Candidates KLu_0, KLu_mean, KLu_max (tie-break as the frozen rule). Per-cell thresholds = f01 quantiles at 5/10/20% (analyze_token_mech.thresholds); choice by the frozen rule's criterion (max mean over rates of in-sample net − random expectation; tie: turnover captured − random). In-sample f01:

| candidate | 5% sel / net / r / d / random | 10% | 20% |
|---|---|---|---|
| KLu_0 | 24 / -3 / 0 / 3 / -0.38 | 48 / -4 / 1 / 5 / -0.75 | 102 / -6 / 5 / 11 / -1.60 |
| KLu_mean | 24 / -3 / 0 / 3 / -0.38 | 48 / -4 / 2 / 6 / -0.75 | 102 / -8 / 4 / 12 / -1.60 |
| KLu_max (chosen) | 24 / -2 / 0 / 2 / -0.38 | 48 / -1 / 3 / 4 / -0.75 | 102 / -3 / 5 / 8 / -1.60 |

**Validation f02/f03 U1 (1020 rows), same table format as W98** (exact one-sided hypergeometric p of net ≥ observed under a matched-count per-cell random trigger; Holm over the 3 budgets):

| row | rate | selected | net vs random (p; Holm) | r/d | turnover vs random (p) |
|---|---|---|---|---|---|
| frozen S_mm (Q-only; prospective) | 5% | 50 | +4 vs +0.21 (0.0345; 0.1035) | 6/2 | 8 vs 3.48 (0.0182) |
| frozen S_mm (Q-only; prospective) | 10% | 114 | +2 vs +0.98 (0.4169; 0.5234) | 7/5 | 12 vs 7.52 (0.0613) |
| frozen S_mm (Q-only; prospective) | 20% | 222 | +5 vs +2.38 (0.2617; 0.5234) | 16/11 | 27 vs 14.30 (0.0002) |
| KLu_0 (KL, not chosen; BF16; post-hoc) | 5% | 74 | +4 vs +0.59 (0.0814; 0.2442) | 7/3 | 10 vs 4.80 (0.0165) |
| KLu_0 (KL, not chosen; BF16; post-hoc) | 10% | 108 | +4 vs +0.67 (0.1258; 0.2442) | 11/7 | 18 vs 7.00 (0.0001) |
| KLu_0 (KL, not chosen; BF16; post-hoc) | 20% | 196 | +6 vs +1.13 (0.0846; 0.2442) | 19/13 | 32 vs 12.63 (0.0000) |
| KLu_mean (KL, not chosen; BF16; post-hoc) | 5% | 90 | +2 vs +0.63 (0.3479; 0.3479) | 10/8 | 18 vs 5.77 (0.0000) |
| KLu_mean (KL, not chosen; BF16; post-hoc) | 10% | 128 | +5 vs +0.87 (0.0876; 0.1752) | 13/8 | 21 vs 8.26 (0.0000) |
| KLu_mean (KL, not chosen; BF16; post-hoc) | 20% | 249 | +9 vs +1.82 (0.0284; 0.0852) | 23/14 | 37 vs 16.32 (0.0000) |
| KLu_max (KL chosen on f01; BF16; post-hoc) | 5% | 72 | -1 vs +0.45 (0.8337; 1.0000) | 5/6 | 11 vs 4.58 (0.0038) |
| KLu_max (KL chosen on f01; BF16; post-hoc) | 10% | 126 | +1 vs +0.82 (0.5483; 1.0000) | 8/7 | 15 vs 7.54 (0.0048) |
| KLu_max (KL chosen on f01; BF16; post-hoc) | 20% | 257 | +3 vs +1.59 (0.3984; 1.0000) | 18/15 | 33 vs 16.73 (0.0000) |
| KLu_max count-matched to frozen per cell (secondary; ranks on validation) | 5% | 50 | +1 vs +0.21 (0.4326; 0.8652) | 4/3 | 7 vs 3.48 (0.0519) |
| KLu_max count-matched to frozen per cell (secondary; ranks on validation) | 10% | 114 | +1 vs +0.98 (0.5722; 0.8652) | 8/7 | 15 vs 7.52 (0.0049) |
| KLu_max count-matched to frozen per cell (secondary; ranks on validation) | 20% | 222 | +6 vs +2.38 (0.1741; 0.5223) | 19/13 | 32 vs 14.30 (0.0000) |

The frozen row's Holm column is computed here for side-by-side reading (the frozen rule fixed no multiplicity rule; W98a). The non-chosen KL candidates are shown so the choice can be audited; only the chosen row is the KL baseline. The count-matched row ranks validation rows by the KL score (no outcome use) to put the KL row on the frozen rule's exact per-cell budget.

KL per cell (chosen score; selected / r / d / net / random):

| cell | 5% | 10% | 20% |
|---|---|---|---|
| q4_awq_w4 | 7 / 0 / 1 / -1 / -0.17 | 17 / 0 / 2 / -2 / -0.40 | 47 / 0 / 3 / -3 / -1.11 |
| q4_gptq_w4_d1 | 18 / 1 / 2 / -1 / -0.11 | 21 / 1 / 2 / -1 / -0.12 | 43 / 2 / 5 / -3 / -0.25 |
| q4_kvq_int8 | 12 / 1 / 1 / +0 / -0.14 | 21 / 2 / 1 / +1 / -0.25 | 37 / 3 / 2 / +1 / -0.43 |
| q8_awq_w4 | 10 / 2 / 2 / +0 / +0.35 | 13 / 2 / 2 / +0 / +0.46 | 36 / 5 / 3 / +2 / +1.27 |
| q8_gptq_w4_d1 | 6 / 0 / 0 / +0 / +0.18 | 15 / 0 / 0 / +0 / +0.44 | 39 / 4 / 1 / +3 / +1.15 |
| q8_kvq_int8 | 19 / 1 / 0 / +1 / +0.34 | 39 / 3 / 0 / +3 / +0.69 | 55 / 4 / 1 / +3 / +0.97 |

## Checks

- score_rows: 3420
- rows_without_acts: 0
- val_U1_rows: 1020
- kl_missing_rows (all blocks): 0
- w98_primary_reproduced: True
- Bank P units digests equal to `analysis/fork/out/dev_all_20261001T070326Z.json`: 11/11 cells

Inputs (sha256) in `oracle_trigger_20261002T024423Z.json`.
