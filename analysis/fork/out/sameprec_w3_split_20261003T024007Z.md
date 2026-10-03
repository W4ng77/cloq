**TL;DR** (INTERIM (before the 2026-10-03 evidence freeze); DESCRIPTIVE / exploratory (amendment A1.4); K = 3 blocks q3–q5, q4+q8, 510 task×block units, the units of sameprec_overlap.py.) **Action-side (G) flip volume similar; the flipping units overlap above chance but are not identical.** Action-side (G) flips: BF16 96 vs d2 88 (Δ +1.6 [-0.7, +3.8] pp); rescues 49 vs 42, shared 29 (κ 0.60); harms 47 vs 46, shared 33 (κ 0.68). 49% of the units that flip under either substitution flip under only one (60 of 122; block-boot 95% [40, 62]%), vs 70% if the d2 flags were shuffled across blocks within task. Net G: BF16 +2 = shared (29 r − 33 h) + specific (20 r − 14 h); d2 -4 = same shared part + specific (13 r − 13 h); ΔG +1.2 [-0.3, +2.6] pp comes entirely from the design-specific units (Δ specific rescue +1.4 [-0.3, +3.1], Δ specific harm +0.2 [-0.6, +1.0] pp). Continuation side (H) agrees less (κ rescue 0.40, harm 0.31) than the action side; full substitution (F) κ rescue 0.46, harm 0.37. Controller dependence (off-diagonal Δ_Q ≠ Δ_B, 443 units divergent in both designs): 119 vs 123, shared 68, κ 0.40 [0.32, 0.47]; 23.9% of these states are off-diagonal under one design only (61% of the off-diagonal set). Cross-direction (rescued under one design, harmed under the other): 0 for every contrast pair, forced by the shared Y_QQ. Trigger link: not feasible. **Answer:** flip volume: G similar (Δflips +1.6 [-0.7, +3.8] pp), H similar (Δflips +2.9 [-2.9, +8.8] pp), F similar (Δflips +1.0 [-9.8, +11.8] pp). On the action side (G) the two substitutions share a large core of rescued and harmed units, well above independence and above a within-task shuffle, yet 49% of the flipping units are design-specific (within-task null 70%). Unit overlap beyond task propensity and the shared Y_QQ (within task×Y_QQ shuffle, p < 0.05): G rescue, G harm, H rescue; not beyond it: H harm, F rescue, F harm. Controller dependence is mostly design-specific: κ 0.40, 61% of off-diagonal units are off-diagonal under one design only (within-task null 66%). Read: different units mainly where the overlap is not beyond the task×Y_QQ shuffle (H harm, F rescue, F harm) and for the off-diagonal (controller-dependent) set; the action contrast G shares a substantial unit core. Net: ΔG +1.2 [-0.3, +2.6] pp, the difference of the design-specific rescues and harms.

## Figure-panel table (pooled q4+q8; counts of units, pp of all units in parentheses)

| contrast | set | BF16 | d2 | shared | BF16 only | d2 only | exp. shared (indep.) | exp. shared (within-task shuffle) | κ [block-boot 95%] |
|---|---|---|---|---|---|---|---|---|---|
| G | rescue | 49 (9.6) | 42 (8.2) | 29 | 20 | 13 | 4.7 | 15.7 [11, 20] | 0.60 [0.51, 0.68] |
| G | harm | 47 (9.2) | 46 (9.0) | 33 | 14 | 13 | 4.4 | 19.0 [14, 24] | 0.68 [0.50, 0.75] |
| G | flip | 96 (18.8) | 88 (17.3) | 62 | 34 | 26 | 17.4 | 42.6 [37, 49] | 0.60 [0.46, 0.68] |
| H | rescue | 53 (10.4) | 36 (7.1) | 20 | 33 | 16 | 3.7 | 11.7 [8, 16] | 0.40 [0.33, 0.48] |
| H | harm | 42 (8.2) | 44 (8.6) | 16 | 26 | 28 | 3.6 | 9.3 [6, 13] | 0.31 [0.14, 0.52] |
| H | flip | 95 (18.6) | 80 (15.7) | 36 | 59 | 44 | 14.7 | 31.6 [27, 37] | 0.29 [0.16, 0.41] |
| F | rescue | 54 (10.6) | 48 (9.4) | 26 | 28 | 22 | 5.7 | 18.7 [15, 22] | 0.46 [0.32, 0.52] |
| F | harm | 46 (9.0) | 47 (9.2) | 20 | 26 | 27 | 4.2 | 12.0 [8, 16] | 0.37 [0.32, 0.43] |
| F | flip | 100 (19.6) | 95 (18.6) | 46 | 54 | 49 | 18.9 | 38.0 [32, 44] | 0.35 [0.28, 0.40] |
| off-diag. | states div. in both (n 443) | 119 | 123 | 68 | 51 | 55 | 33.9 | 61.7 | 0.40 [0.32, 0.47] |

# Same-precision split: which units each substitution rescues and harms (20261003T024007Z)

INTERIM (before the 2026-10-03 evidence freeze); DESCRIPTIVE / exploratory (amendment A1.4). Script `analysis/fork/sameprec_split.py` sha e55e33b820a6; protocol sha aeb6b29b35e5 (A1); sameprec_overlap c9ad7bf38979; analyze_sameprec aa96f605c21d; git 034f248b65; seed 20261002, 10000 permutations, B = 2000. Full numbers: `analysis/fork/out/sameprec_w3_split_20261003T024007Z.json`. Complete prefix now: q3, q4, q5. Units digest bcfd3cd530ef.

Definitions: contrast c ∈ {G: BQ vs QQ (action side), H: QB vs QQ (continuation side), F: BB vs QQ (full substitution)}; rescue = Y_arm 1 / Y_QQ 0, harm = Y_arm 0 / Y_QQ 1; no divergence = no flip. 'BF16' = precision design (B = BF16), 'd2' = same-precision design (B role = GPTQ-W3 d2). Q = GPTQ-W3 d1 and the QQ episode are shared.

## 1. Rescue and harm sets

| contrast | set | sizes / shared / nulls / κ | within task×Y_QQ shuffle: shared mean [95%], p | share design-specific (% of union) [boot 95%] vs within-task null |
|---|---|---|---|---|
| G | rescue | 49 vs 42; shared 29 (Jaccard 0.47); exp. indep. 5, within-task shuffle 16 [11, 20]; κ 0.60 [0.51, 0.68] | 22.0 [19, 25], 0.0001 | 53.2 [44.0, 61.9] vs 79.2 |
| G | harm | 47 vs 46; shared 33 (Jaccard 0.55); exp. indep. 4, within-task shuffle 19 [14, 24]; κ 0.68 [0.50, 0.75] | 30.0 [28, 32], 0.0132 | 45.0 [36.4, 63.2] vs 74.3 |
| G | flip | 96 vs 88; shared 62 (Jaccard 0.51); exp. indep. 17, within-task shuffle 43 [37, 49]; κ 0.60 [0.46, 0.68] | 52.0 [48, 56], 0.0001 | 49.2 [40.4, 62.5] vs 69.8 |
| H | rescue | 53 vs 36; shared 20 (Jaccard 0.29); exp. indep. 4, within-task shuffle 12 [8, 16]; κ 0.40 [0.33, 0.48] | 17.2 [15, 20], 0.0417 | 71.0 [65.0, 75.0] vs 84.9 |
| H | harm | 42 vs 44; shared 16 (Jaccard 0.23); exp. indep. 4, within-task shuffle 9 [6, 13]; κ 0.31 [0.14, 0.52] | 16.3 [14, 18], 0.7634 | 77.1 [60.9, 88.0] vs 87.8 |
| H | flip | 95 vs 80; shared 36 (Jaccard 0.26); exp. indep. 15, within-task shuffle 32 [27, 37]; κ 0.29 [0.16, 0.41] | 33.5 [30, 37], 0.1379 | 74.1 [65.9, 81.1] vs 77.9 |
| F | rescue | 54 vs 48; shared 26 (Jaccard 0.34); exp. indep. 6, within-task shuffle 19 [15, 22]; κ 0.46 [0.32, 0.52] | 23.3 [21, 26], 0.0557 | 65.8 [60.9, 77.3] vs 77.6 |
| F | harm | 46 vs 47; shared 20 (Jaccard 0.27); exp. indep. 4, within-task shuffle 12 [8, 16]; κ 0.37 [0.32, 0.43] | 19.2 [17, 22], 0.4021 | 72.6 [68.2, 75.9] vs 85.2 |
| F | flip | 100 vs 95; shared 46 (Jaccard 0.31); exp. indep. 19, within-task shuffle 38 [32, 44]; κ 0.35 [0.28, 0.40] | 42.5 [39, 46], 0.0585 | 69.1 [64.2, 75.0] vs 75.8 |

Cross-direction counts (rescued under one design, harmed under the other), same contrast: G: 0 / 0; H: 0 / 0; F: 0 / 0. Across contrast pairs: G_BF16/G_d2 0, G_BF16/H_d2 0, G_BF16/F_d2 0, H_BF16/G_d2 0, H_BF16/H_d2 0, H_BF16/F_d2 0, F_BF16/G_d2 0, F_BF16/H_d2 0, F_BF16/F_d2 0. Y_QQ mismatches between designs: 0. Y_QQ is the same Q episode in both designs, so rescue (needs Y_QQ = 0) and harm (needs Y_QQ = 1) are mutually exclusive across designs and contrasts: every cross-direction count is 0 by construction, not by evidence.

Per cell (G): q4: flips 49/45, shared r 12 h 20, specific r 11/5 h 6/8, net -3/-11, κ r 0.57 h 0.71; q8: flips 47/43, shared r 17 h 13, specific r 9/8 h 8/5, net +5/+7, κ r 0.63 h 0.64

## 2. Controller dependence (off-diagonal: Δ_Q = Y_BQ − Y_QQ ≠ Δ_B = Y_BB − Y_QB)

| subset | states | off-diag BF16 / d2 (%) | shared | BF16 only | d2 only | κ [boot 95%] | within-task shuffle shared | off-diag under one design only (% of states) | Δ off-diag rate (pp) | action flips in both: same Δ_B / off only BF16 / only d2 / both |
|---|---|---|---|---|---|---|---|---|---|---|
| both_divergent | 443 | 26.9 / 27.8 | 68 | 51 | 55 | 0.40 [0.32, 0.47] | 61.7 [56, 67] | 23.9 (+24.0 [+12.0, +35.9]) | -0.8 [-17.5, +15.9] | 27/62 · 9 / 13 / 36 |
| same_decision | 189 | 28.6 / 31.2 | 36 | 18 | 23 | 0.48 [0.40, 0.57] | 32.6 [29, 37] | 21.7 (+21.4 [+7.9, +34.9]) | -3.0 [-18.8, +12.8] | 16/34 · 5 / 3 / 24 |

States differ between designs when the first divergence is at a different decision (t); 'same_decision' keeps t_BF16 = t_d2.

## 3. Net decomposition (counts; pp of 510 units with t over block means 95% and block-bootstrap 95%)

| contrast | shared rescue | shared harm | BF16-only rescue | BF16-only harm | d2-only rescue | d2-only harm | net BF16 | net d2 | Δnet (pp) | Δflips (pp) | Δ specific rescue (pp) | Δ specific harm (pp) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| G | 29 | 33 | 20 | 14 | 13 | 13 | +2 (+0.4) | -4 (-0.8) | +1.2 [-0.3, +2.6]; boot [+0.6, +1.8] | +1.6 [-0.7, +3.8] | +1.4 [-0.3, +3.1] | +0.2 [-0.6, +1.0] |
| H | 20 | 16 | 33 | 26 | 16 | 28 | +11 (+2.2) | -8 (-1.6) | +3.7 [-3.0, +10.5]; boot [+0.6, +5.3] | +2.9 [-2.9, +8.8] | +3.3 [-2.8, +9.4] | -0.4 [-2.1, +1.3] |
| F | 26 | 20 | 28 | 26 | 22 | 27 | +8 (+1.6) | +1 (+0.2) | +1.4 [-4.5, +7.3]; boot [-1.2, +3.5] | +1.0 [-9.8, +11.8] | +1.2 [-7.0, +9.3] | -0.2 [-3.2, +2.8] |

Identity: net = shared rescue + design-specific rescue − shared harm − design-specific harm (asserted); the shared parts cancel in Δnet. Consistency: G ΔG +1.18 pp should equal analyze_sameprec's pooled ΔG_all; G Δflips +1.57 pp its ΔM.

## 4. Trigger link (frozen Q-only trigger)

Trigger link skipped (--w3): the frozen Q-only rule is defined for gptq_w4_d1 on Bank U f01-f03, not for GPTQ-W3 blocks q3-q5.

## Caveats

- INTERIM and descriptive (A1.4); the frozen analysis uses the longest complete prefix at the 2026-10-03 freeze; re-run this script then.
- Forks are deterministic replays, so there is no within-design unit-level replication benchmark: the within-task shuffle and independence nulls are the only references for 'how much overlap is a lot'. Task-level replication (split-half) is in sameprec_overlap.
- Direction agreement is forced by the shared QQ episode; only the *which-units* question is informative.
- K = 3 blocks: t intervals over 3 block means are wide; κ and share intervals are percentile block bootstraps over 3 clusters.
- States differ between designs when the first divergence lands on a different decision; off-diagonal agreement is reported both on all doubly divergent units and on the same-decision subset.

