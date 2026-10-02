**TL;DR** (INTERIM (before the 2026-10-03 evidence freeze); DESCRIPTIVE / exploratory (amendment A1.4); K = 6 blocks f01–f06, q4+q8, 1020 task×block units.) Of the units whose outcome flips under the precision replacement (M = 1: 171) and under the same-precision replacement (M′ = 1: 181), **107 flip under both** (10.5% of units; 63% of the BF16 flips, 59% of the d2 flips; unit Jaccard 0.44), vs 31 expected if the two flip sets were independent within cell×block. Only BF16 64, only d2 74, neither 775. Cohen's κ(M, M′) = 0.53 (block-bootstrap 95% [0.46, 0.58]; marginal-preserving null mean +0.004, 95% [-0.06, +0.07], p = 0.0001; κ_max given the marginals 0.97). All 107 both-flip units flip in the same direction (100%), which is forced by the shared Q episode (Y_QQ), not evidence. Task level: per-task flip rates correlate r = 0.68 (Spearman 0.72) between designs; at matched noise (disjoint block halves) cross-design r = 0.48 vs within-design replication 0.65 (precision) / 0.60 (same-precision), ratio 0.765. Within-task null (M′ permuted across blocks inside each task, task propensities kept): both 76 [69, 84] vs 107 observed (κ null 0.32, p = 0.0001). **Answer:** similar average M corresponds to substantially overlapping sensitive units and tasks (far above chance), not to disjoint ones: about 76% of the replicable task-level flip propensity is shared between the two replacements; beyond task propensity, the same Q episodes (task×block) flip under both. Still, 138 of 245 flipping units flip under only one replacement.

# Same-precision vs precision 2×2: unit and task overlap (20261002T143218Z)

INTERIM (before the 2026-10-03 evidence freeze); DESCRIPTIVE / exploratory (amendment A1.4). Script `analysis/fork/sameprec_overlap.py` sha c9ad7bf38979; protocol sha 89484d35c77c (amended, A1); analyze_sameprec ef4a9c5c8ef7; git f585ae3185; seed 20261002, 10000 permutations, B = 2000. Full numbers: `analysis/fork/out/sameprec_overlap_20261002T143218Z.json`. Complete prefix now: f01, f02, f03, f04, f05, f06.

Definitions: unit = task×block, admitted in both designs (the primary analysis set). M = 1 iff Y_BQ ≠ Y_QQ (BF16 action, Q continues; rescue = Y_BQ 1/Y_QQ 0, damage = 0/1; no divergence = 0). M′ the same with Q′ = GPTQ-W4 d2 in place of BF16. M_any (secondary): any B-involving arm (BB, BQ, QB) ≠ QQ.

## K = 6 (f01–f06) — interim

Y_QQ identical across designs on 1020/1020 units. Y_QQ is the same Q episode in both designs, so a unit flipping in both designs flips in the same direction by construction (rescue iff Y_QQ = 0).

### Overlap table (M vs M′; counts, share of units)

| scope | units | both | only BF16 | only d2 | neither | P(M′=1∣M=1) | P(M=1∣M′=1) | unit Jaccard |
|---|---|---|---|---|---|---|---|---|
| q4 | 510 | 43 (8.4%) | 41 (8.0%) | 38 (7.5%) | 388 (76.1%) | 51.2% | 53.1% | 0.352 |
| q8 | 510 | 64 (12.6%) | 23 (4.5%) | 36 (7.1%) | 387 (75.9%) | 73.6% | 64.0% | 0.520 |
| pooled | 1020 | 107 (10.5%) | 64 (6.3%) | 74 (7.2%) | 775 (76.0%) | 62.6% | 59.1% | 0.437 |

Directions (rescue / damage):

| scope | both (BF16/d2) | both same direction | only BF16 | only d2 | only-BF16 units where d2 diverged | only-d2 units where BF16 diverged |
|---|---|---|---|---|---|---|
| q4 | damage/damage 25, rescue/rescue 18 | 43/43 | damage 28, rescue 13 | damage 21, rescue 17 | 27 | 13 |
| q8 | damage/damage 26, rescue/rescue 38 | 64/64 | damage 10, rescue 13 | damage 14, rescue 22 | 17 | 27 |
| pooled | damage/damage 51, rescue/rescue 56 | 107/107 | damage 38, rescue 26 | damage 35, rescue 39 | 44 | 40 |

### Agreement (Cohen's κ on M vs M′)

| scope | κ | block-boot 95% | κ_max | p_o | p_e (marginals) | both obs | both exp (indep.) | null κ cell×block: mean [95%], p | null κ cell×block×Y_QQ: mean [95%], p | null within task: κ mean [95%], both mean, p | κ M_any |
|---|---|---|---|---|---|---|---|---|---|---|---|
| q4 | 0.429 | [0.33, 0.53] | 0.978 | 0.845 | 0.729 | 43 | 13.3 | +0.002 [-0.08, +0.10], 0.0001 | +0.031 [-0.05, +0.13], 0.0001 | +0.211 [+0.13, +0.30], 27.9, 0.0001 | 0.410 |
| q8 | 0.614 | [0.55, 0.66] | 0.915 | 0.884 | 0.700 | 64 | 17.1 | +0.003 [-0.08, +0.09], 0.0001 | +0.016 [-0.07, +0.10], 0.0001 | +0.409 [+0.34, +0.48], 48.3, 0.0001 | 0.520 |
| pooled | 0.526 | [0.46, 0.58] | 0.966 | 0.865 | 0.714 | 107 | 30.3 | +0.004 [-0.06, +0.07], 0.0001 | +0.023 [-0.04, +0.09], 0.0001 | +0.316 [+0.27, +0.37], 76.3, 0.0001 | 0.466 |

κ within Y_QQ strata (Y_QQ = 0: only rescues possible; Y_QQ = 1: only damages): q4: Y_QQ=0 κ 0.49 (n 303, both 18 vs 3.6 exp.), Y_QQ=1 κ 0.35 (n 207, both 25 vs 11.8 exp.); q8: Y_QQ=0 κ 0.63 (n 358, both 38 vs 8.6 exp.), Y_QQ=1 κ 0.58 (n 152, both 26 vs 9.5 exp.); pooled: Y_QQ=0 κ 0.58 (n 661, both 56 vs 11.8 exp.), Y_QQ=1 κ 0.45 (n 359, both 51 vs 21.3 exp.)

Overlap with M_any (any B-involving arm ≠ QQ), counts both / only BF16 / only d2 / neither: q4 80 / 67 / 53 / 310; q8 96 / 51 / 49 / 314; pooled 176 / 118 / 102 / 624

### Task-level concentration

| scope | tasks | r (Pearson) | perm null 95% (p) | Spearman | split-half within prec | within same | cross-design | cross/within | top-10% tasks' share of flips prec / same | tasks ever flip prec / same / both (exp.) | Jaccard ever-flip (exp.) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| q4 | 85 | 0.520 | [-0.21, +0.23] (0.0001) | 0.667 | 0.584 | 0.534 | 0.322 | 0.577 | 40.5% / 38.3% | 36 / 34 / 29 (14.4) | 0.707 (0.259) |
| q8 | 85 | 0.798 | [-0.20, +0.23] (0.0001) | 0.774 | 0.717 | 0.662 | 0.610 | 0.885 | 46.0% / 41.0% | 31 / 40 / 29 (14.6) | 0.691 (0.259) |
| pooled | 170 | 0.680 | [-0.14, +0.16] (0.0001) | 0.720 | 0.653 | 0.605 | 0.481 | 0.765 | 46.2% / 43.1% | 67 / 74 / 58 (29.2) | 0.699 (0.261) |

Split-half: all 10 balanced splits of the K blocks into two disjoint halves of 3 blocks; within = same design on the two halves, cross = precision on one half vs same-precision on the other (mean of both orientations). cross/within = cross / sqrt(within_prec × within_same).

Top tasks by combined flip rate (pooled): q8|retail|retail:113 1.00/1.00; q8|retail|retail:48 1.00/1.00; q8|retail|retail:78 1.00/0.83; q8|airline|airline:5 0.83/0.83; q8|retail|retail:77 0.83/0.83; q4|retail|retail:103 0.83/0.67; q8|airline|airline:25 0.67/0.67; q4|airline|airline:10 0.67/0.67; q8|retail|retail:46 0.67/0.67; q8|retail|retail:86 0.67/0.67

