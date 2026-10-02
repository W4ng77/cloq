**TL;DR** (INTERIM (before the 2026-10-03 evidence freeze); DESCRIPTIVE / exploratory (amendment A1.4); K = 6 blocks f01–f06, q4+q8, 1020 task×block units, the units of sameprec_overlap.py.) **Action-side (G) flip volume similar; the flipping units overlap above chance but are not identical.** Action-side (G) flips: BF16 171 vs d2 181 (Δ -1.0 [-3.9, +1.9] pp); rescues 82 vs 95, shared 56 (κ 0.60); harms 89 vs 86, shared 51 (κ 0.54). 56% of the units that flip under either substitution flip under only one (138 of 245; block-boot 95% [51, 63]%), vs 72% if the d2 flags were shuffled across blocks within task. Net G: BF16 -7 = shared (56 r − 51 h) + specific (26 r − 38 h); d2 +9 = same shared part + specific (39 r − 35 h); ΔG -1.6 [-6.2, +3.0] pp comes entirely from the design-specific units (Δ specific rescue -1.3 [-3.8, +1.3], Δ specific harm +0.3 [-2.6, +3.2] pp). Continuation side (H) agrees less (κ rescue 0.20, harm 0.45) than the action side; full substitution (F) κ rescue 0.34, harm 0.35. Controller dependence (off-diagonal Δ_Q ≠ Δ_B, 697 units divergent in both designs): 170 vs 177, shared 81, κ 0.29 [0.20, 0.40]; 26.5% of these states are off-diagonal under one design only (70% of the off-diagonal set). Cross-direction (rescued under one design, harmed under the other): 0 for every contrast pair, forced by the shared Y_QQ. Trigger link: only 20/394 BF16 fork states, 30/390 d2 fork states on the scored blocks coincide with a Bank U U1 state carrying the frozen S_mm score, so enrichment under d2 cannot be assessed (numbers below, descriptive only). **Answer:** flip volume: G similar (Δflips -1.0 [-3.9, +1.9] pp), H similar (Δflips -2.2 [-5.1, +0.8] pp), F DIFFERENT (Δflips +4.3 [+0.4, +8.3] pp). On the action side (G) the two substitutions share a large core of rescued and harmed units, well above independence and above a within-task shuffle, yet 56% of the flipping units are design-specific (within-task null 72%). Unit overlap beyond task propensity and the shared Y_QQ (within task×Y_QQ shuffle, p < 0.05): G rescue, G harm, H harm; not beyond it: H rescue, F rescue, F harm. Controller dependence is mostly design-specific: κ 0.29, 70% of off-diagonal units are off-diagonal under one design only (within-task null 73%). Read: different units mainly where the overlap is not beyond the task×Y_QQ shuffle (H rescue, F rescue, F harm) and for the off-diagonal (controller-dependent) set; the action contrast G shares a substantial unit core. Net: ΔG -1.6 [-6.2, +3.0] pp, the difference of the design-specific rescues and harms.

## Figure-panel table (pooled q4+q8; counts of units, pp of all units in parentheses)

| contrast | set | BF16 | d2 | shared | BF16 only | d2 only | exp. shared (indep.) | exp. shared (within-task shuffle) | κ [block-boot 95%] |
|---|---|---|---|---|---|---|---|---|---|
| G | rescue | 82 (8.0) | 95 (9.3) | 56 | 26 | 39 | 8.4 | 37.2 [32, 42] | 0.60 [0.54, 0.65] |
| G | harm | 89 (8.7) | 86 (8.4) | 51 | 38 | 35 | 7.7 | 25.0 [19, 31] | 0.54 [0.45, 0.61] |
| G | flip | 171 (16.8) | 181 (17.7) | 107 | 64 | 74 | 30.9 | 76.3 [69, 84] | 0.53 [0.46, 0.58] |
| H | rescue | 66 (6.5) | 73 (7.2) | 18 | 48 | 55 | 4.8 | 11.5 [7, 16] | 0.20 [0.09, 0.31] |
| H | harm | 59 (5.8) | 74 (7.3) | 32 | 27 | 42 | 4.2 | 15.0 [10, 20] | 0.45 [0.30, 0.60] |
| H | flip | 125 (12.3) | 147 (14.4) | 50 | 75 | 97 | 18.2 | 38.9 [32, 46] | 0.27 [0.18, 0.39] |
| F | rescue | 101 (9.9) | 76 (7.5) | 35 | 66 | 41 | 8.5 | 25.5 [21, 31] | 0.34 [0.26, 0.45] |
| F | harm | 92 (9.0) | 73 (7.2) | 33 | 59 | 40 | 7.0 | 21.2 [16, 27] | 0.35 [0.24, 0.44] |
| F | flip | 193 (18.9) | 149 (14.6) | 68 | 125 | 81 | 28.4 | 62.7 [55, 70] | 0.28 [0.23, 0.33] |
| off-diag. | states div. in both (n 697) | 170 | 177 | 81 | 89 | 96 | 44.7 | 73.0 | 0.29 [0.20, 0.40] |

# Same-precision split: which units each substitution rescues and harms (20261002T145148Z)

INTERIM (before the 2026-10-03 evidence freeze); DESCRIPTIVE / exploratory (amendment A1.4). Script `analysis/fork/sameprec_split.py` sha fca2641c0c48; protocol sha 89484d35c77c (A1); sameprec_overlap c9ad7bf38979; analyze_sameprec ef4a9c5c8ef7; git 694fe3a07e; seed 20261002, 10000 permutations, B = 2000. Full numbers: `analysis/fork/out/sameprec_split_20261002T145148Z.json`. Complete prefix now: f01, f02, f03, f04, f05, f06. Units digest 45672ed6c997.

Definitions: contrast c ∈ {G: BQ vs QQ (action side), H: QB vs QQ (continuation side), F: BB vs QQ (full substitution)}; rescue = Y_arm 1 / Y_QQ 0, harm = Y_arm 0 / Y_QQ 1; no divergence = no flip. 'BF16' = precision design (B = BF16), 'd2' = same-precision design (B role = GPTQ-W4 d2). Q = GPTQ-W4 d1 and the QQ episode are shared.

## 1. Rescue and harm sets

| contrast | set | sizes / shared / nulls / κ | within task×Y_QQ shuffle: shared mean [95%], p | share design-specific (% of union) [boot 95%] vs within-task null |
|---|---|---|---|---|
| G | rescue | 82 vs 95; shared 56 (Jaccard 0.46); exp. indep. 8, within-task shuffle 37 [32, 42]; κ 0.60 [0.54, 0.65] | 46.0 [42, 50], 0.0001 | 53.7 [48.0, 59.6] vs 73.4 |
| G | harm | 89 vs 86; shared 51 (Jaccard 0.41); exp. indep. 8, within-task shuffle 25 [19, 31]; κ 0.54 [0.45, 0.61] | 42.5 [38, 47], 0.0001 | 58.9 [52.4, 67.5] vs 83.4 |
| G | flip | 171 vs 181; shared 107 (Jaccard 0.44); exp. indep. 31, within-task shuffle 76 [69, 84]; κ 0.53 [0.46, 0.58] | 88.5 [83, 95], 0.0001 | 56.3 [50.8, 62.6] vs 72.3 |
| H | rescue | 66 vs 73; shared 18 (Jaccard 0.15); exp. indep. 5, within-task shuffle 12 [7, 16]; κ 0.20 [0.09, 0.31] | 18.4 [14, 23], 0.6652 | 85.1 [77.9, 92.4] vs 91.0 |
| H | harm | 59 vs 74; shared 32 (Jaccard 0.32); exp. indep. 4, within-task shuffle 15 [10, 20]; κ 0.45 [0.30, 0.60] | 28.6 [25, 32], 0.0347 | 68.3 [54.6, 79.2] vs 87.3 |
| H | flip | 125 vs 147; shared 50 (Jaccard 0.23); exp. indep. 18, within-task shuffle 39 [32, 46]; κ 0.27 [0.18, 0.39] | 47.0 [42, 52], 0.1781 | 77.5 [68.7, 83.7] vs 83.3 |
| F | rescue | 101 vs 76; shared 35 (Jaccard 0.25); exp. indep. 8, within-task shuffle 26 [21, 31]; κ 0.34 [0.26, 0.45] | 34.5 [31, 39], 0.4985 | 75.3 [66.9, 81.1] vs 83.2 |
| F | harm | 92 vs 73; shared 33 (Jaccard 0.25); exp. indep. 7, within-task shuffle 21 [16, 27]; κ 0.35 [0.24, 0.44] | 33.5 [29, 38], 0.6656 | 75.0 [68.1, 82.5] vs 85.3 |
| F | flip | 193 vs 149; shared 68 (Jaccard 0.25); exp. indep. 28, within-task shuffle 63 [55, 70]; κ 0.28 [0.23, 0.33] | 68.0 [62, 74], 0.5631 | 75.2 [71.5, 79.1] vs 77.6 |

Cross-direction counts (rescued under one design, harmed under the other), same contrast: G: 0 / 0; H: 0 / 0; F: 0 / 0. Across contrast pairs: G_BF16/G_d2 0, G_BF16/H_d2 0, G_BF16/F_d2 0, H_BF16/G_d2 0, H_BF16/H_d2 0, H_BF16/F_d2 0, F_BF16/G_d2 0, F_BF16/H_d2 0, F_BF16/F_d2 0. Y_QQ mismatches between designs: 0. Y_QQ is the same Q episode in both designs, so rescue (needs Y_QQ = 0) and harm (needs Y_QQ = 1) are mutually exclusive across designs and contrasts: every cross-direction count is 0 by construction, not by evidence.

Per cell (G): q4: flips 84/81, shared r 18 h 25, specific r 13/17 h 28/21, net -22/-11, κ r 0.51 h 0.45; q8: flips 87/100, shared r 38 h 26, specific r 13/22 h 10/14, net +15/+20, κ r 0.65 h 0.66

## 2. Controller dependence (off-diagonal: Δ_Q = Y_BQ − Y_QQ ≠ Δ_B = Y_BB − Y_QB)

| subset | states | off-diag BF16 / d2 (%) | shared | BF16 only | d2 only | κ [boot 95%] | within-task shuffle shared | off-diag under one design only (% of states) | Δ off-diag rate (pp) | action flips in both: same Δ_B / off only BF16 / only d2 / both |
|---|---|---|---|---|---|---|---|---|---|---|
| both_divergent | 697 | 24.4 / 25.4 | 81 | 89 | 96 | 0.29 [0.20, 0.40] | 73.0 [66, 80] | 26.5 (+26.5 [+21.7, +31.3]) | -1.0 [-4.5, +2.6] | 46/107 · 16 / 30 / 44 |
| same_decision | 404 | 27.0 / 26.5 | 55 | 54 | 52 | 0.33 [0.26, 0.41] | 49.6 [44, 55] | 26.2 (+26.2 [+22.0, +30.4]) | +0.4 [-5.0, +5.8] | 37/85 · 12 / 23 / 34 |

States differ between designs when the first divergence is at a different decision (t); 'same_decision' keeps t_BF16 = t_d2.

## 3. Net decomposition (counts; pp of 1020 units with t over block means 95% and block-bootstrap 95%)

| contrast | shared rescue | shared harm | BF16-only rescue | BF16-only harm | d2-only rescue | d2-only harm | net BF16 | net d2 | Δnet (pp) | Δflips (pp) | Δ specific rescue (pp) | Δ specific harm (pp) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| G | 56 | 51 | 26 | 38 | 39 | 35 | -7 (-0.7) | +9 (+0.9) | -1.6 [-6.2, +3.0]; boot [-5.0, +1.4] | -1.0 [-3.9, +1.9] | -1.3 [-3.8, +1.3] | +0.3 [-2.6, +3.2] |
| H | 18 | 32 | 48 | 27 | 55 | 42 | +7 (+0.7) | -1 (-0.1) | +0.8 [-3.2, +4.7]; boot [-2.1, +3.4] | -2.2 [-5.1, +0.8] | -0.7 [-3.0, +1.6] | -1.5 [-4.1, +1.1] |
| F | 35 | 33 | 66 | 59 | 41 | 40 | +9 (+0.9) | +3 (+0.3) | +0.6 [-3.4, +4.6]; boot [-2.2, +3.2] | +4.3 [+0.4, +8.3] | +2.5 [+0.7, +4.2] | +1.9 [-1.7, +5.5] |

Identity: net = shared rescue + design-specific rescue − shared harm − design-specific harm (asserted); the shared parts cancel in Δnet. Consistency: G ΔG -1.57 pp should equal analyze_sameprec's pooled ΔG_all; G Δflips -0.98 pp its ΔM.

## 4. Trigger link (frozen Q-only trigger)

Score S_mm (rule sha 335e737d54bf); scored U1 blocks f01, f02, f03 (f01 is the rule's development block (in-sample); f02/f03 validation); 510 U1 rows for gptq_w4_d1. Bank U Y vs precision-fork Y at the linked states: 20/20 identical.

| design | divergent fork states on scored blocks | linked | rate | triggered / not | flip % trig / not | Fisher p (greater) | net G triggered (r/h) |
|---|---|---|---|---|---|---|---|
| BF16 | 394 | 20 | 0.05 | 1 / 19 | 100.0 / 15.8 | 0.2 | -1 (0/1) |
| BF16 | 394 | 20 | 0.1 | 2 / 18 | 50.0 / 16.7 | 0.3684 | -1 (0/1) |
| BF16 | 394 | 20 | 0.2 | 4 / 16 | 25.0 / 18.8 | 0.6244 | -1 (0/1) |
| d2 | 390 | 30 | 0.05 | 2 / 28 | 50.0 / 17.9 | 0.3655 | -1 (0/1) |
| d2 | 390 | 30 | 0.1 | 4 / 26 | 25.0 / 19.2 | 0.6123 | -1 (0/1) |
| d2 | 390 | 30 | 0.2 | 9 / 21 | 11.1 / 23.8 | 0.9086 | -1 (0/1) |

Linked states are the fork states whose decision index happens to equal the sampled Bank U U1 state of the same Q episode; tiny n, the first-divergence states are a selected subset, and f01 is in-sample for the rule. Descriptive only; not an evaluation of the trigger under d2.

## Caveats

- INTERIM and descriptive (A1.4); the frozen analysis uses the longest complete prefix at the 2026-10-03 freeze; re-run this script then.
- Forks are deterministic replays, so there is no within-design unit-level replication benchmark: the within-task shuffle and independence nulls are the only references for 'how much overlap is a lot'. Task-level replication (split-half) is in sameprec_overlap.
- Direction agreement is forced by the shared QQ episode; only the *which-units* question is informative.
- K = 6 blocks: t intervals over 6 block means are wide; κ and share intervals are percentile block bootstraps over 6 clusters.
- States differ between designs when the first divergence lands on a different decision; off-diagonal agreement is reported both on all doubly divergent units and on the same-decision subset.

