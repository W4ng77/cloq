# CLAIM_AUDIT — CLOQ paper, pre-evidence-freeze claim audit (2026-10-01)

**TL;DR.** 91 claims audited (abstract 14, introduction 13, R1 8, R2 11, R3 20, R4 10, discussion 10; plus 5 method/limitations claims that carry headline numbers). There is no separate conclusion section; the discussion was audited as the conclusion. Most numbers match their `% src:` files. The ranked list below has **37 problems**: 9 must-fix (S1), 17 strong (S2) and 11 minor (S3). IDs P34 and P36 are unused. The most serious ones:
- **P1:** R3 says the holdout "confirms ... no positive average benefit". The pre-registered primary reading is *inconclusive*.
- **P2:** R1 attaches the holdout S2 pass to claims that S2 did not test (concentration, direction).
- **P3:** R3 says "simple content features do not separate" flips. Its own appendix (f01–f03) shows that length difference does.
- **P4:** The discussion labels 15.5–20.9% as turnover of Bank P *states*. It is turnover of task×block *units*.
- **P5:** The introduction points to a §discussion example that does not exist.
- **P6:** "Stress cells reach W4-like turnover" is false for q8 RTN-W3 (6.7%).
- **P7:** The R4 claims "only q4 U2B" and "one exception" omit q4 U2Q and two per-cell exceptions.
- **P8/P9:** Two `src` pointers go to the superseded f01-only Bank U output. The "135/135 production" Bank U no-op figure is the gate run; production f01–f03 is 328/328.

One `\todo{}` remains (appendix.tex:397). The paper was not edited.

Evidence: every number below was checked against the committed file named in the paper's `% src:` comment, at `/data/ziyangs/cloq/analysis/fork/out/` unless a path is given. I never opened `analysis/fork/holdout/`. I read only the committed holdout *outputs* in `analysis/fork/out/holdout_*`.

---

## 0. Abbreviations used in the table

**Sample units**
- **U-tb**: task×block unit of one cell. This is the full pool, and units without a Bank P state count 0. The 85 tasks repeat in every block and are shared across cells. Blocks (nonces) are the independent replicate. Tasks are a fixed pool, not a sample.
- **U-st**: Bank P state, the first *tool-structure* divergence of one task×block×cell (text-only differences are skipped). States of the same task repeat across blocks, so they are not independent within a task.
- **U-row**: Bank U cell×state row. Rows repeat tasks across the 3 blocks. U2B/U2Q states are *identical across the 3 cells of a model*.
- **U-item**: a BFCL/ALFWorld item, with one run per item.
- **U-ho**: holdout task×block unit: 34 tasks × 12 blocks × 3 cells. 1200 of the 1224 units were analysed (2 task×cell structural exclusions).

**Intervals**
- **FP**: fixed task pool. Block bootstrap with ≥10 blocks, otherwise t over block means.
- **CR**: crossed task×block bootstrap. This is the new-task interval.
- **IT**: item bootstrap within stratum.
- **SB**: state bootstrap.

**Scope**
- **S-τ** (default scope): Qwen3-4B-Instruct / Qwen3-8B (no-think), fake-quantized W4 (GPTQ, AWQ) or KV8 with BF16 compute, τ² retail+airline 85-task development pool, one greedy Qwen3-30B-A3B user simulator, first-tool-structure-divergence forks.
- In every scope, nonce blocks ≠ new tasks.

**Status**
- **CONF**: confirmatory. Only the telecom pre-registered G_all, S1 and S2 qualify.
- **EXPL**: exploratory.
- **DESC**: descriptive.
- **PH**: post hoc.

---

## 1. Claim table

### Abstract (abstract.tex)

| # | Claim (short quote) | Source checked → match | Unit / independence | Estimand, denominator | Interval / test | Scope | Status | Problems |
|---|---|---|---|---|---|---|---|---|
| A1 | l.2 "the answer depends on the state and on the controller that continues, so average success, action divergence and the gain ... need to be measured separately" | Synthesis of R1/R2 | — | — | — | S-τ | EXPL (framing) | P17 |
| A2 | l.2 "frozen, bit-exactly replayable state" | docs/insights/FORK_PROTOCOL.md §8; dev_all_20261001T070326Z.md (no-op 924/924) → match | gate states; sampled QQ no-ops | no-op identity | count, no interval | dev gate + production sample | DESC (engineering) | P27, P28 |
| A3 | l.2 "replacing a W4 agent's first divergent action changes the task outcome in 15.5–20.9% of task-block units, in both directions" | dev_all_20261001T070326Z.md two-sided table (M 15.5/19.9/17.9/20.9) → match | U-tb, 85×20, blocks independent, tasks repeat | M = r + d, full pool | FP (and CR in JSON) | S-τ, 4 W4 cells | EXPL/DESC | P10 ("first divergent") |
| A4 | l.2 "net gain is between −1.9 and +2.9 pp" | same → match (−1.9, −0.3, +2.9, +1.9) | U-tb | G_all = r − d, full pool | FP; CR all cover 0 | S-τ | EXPL | — |
| A5 | l.3 "about a quarter of the divergent states ... (pooled 26.9%; new-task interval 22.1–32.0%)" | ghf_20261001T211519Z.md §2 pool W4:all (26.9 [25.7, 28.1], crossed [22.1, 32.0]) → match | U-st, equal weight over 4 cells | P(Δ_Q ≠ Δ_B), divergent-only | FP + CR | S-τ, W4 | EXPL/DESC | P17 |
| A6 | l.3 "Strict sign reversals are only 1.2–4.2% of states in the W4 and KV8 cells" | ghf §2 (3.1, 2.6, 4.2, 2.7; KV8 1.2, 1.2) → match | U-st | share of (+1,−1) and (−1,+1) | FP | S-τ W4 + KV8 | DESC | — |
| A7 | l.3 "dependence in the two directions is about equally frequent, so the mean interaction is near zero" | ghf §2 W4 pool P(I>0) 13.6, P(I<0) 13.4, E[I] +0.0 [−1.9, +2.0] → match for the dev W4 pool | U-st | E[I], divergent-only | FP | S-τ, W4 pool only (KV8 pool −1.9 [−4.6, +0.6]; holdout post hoc −5.0 [−9.6, −0.4]) | DESC | **P14** |
| A8 | l.3 "our results do not establish an ordering ... that transfers across configurations, tasks and user simulators" | ghf_multiplicity; simctrl_p → consistent | — | G − H | Holm (4), CR | — | EXPL | — (good) |
| A9 | l.4 "At outcome-independent states, most outcome-changing differences ... are text differences with the same tool structure" | `src` = bank_u_f01_20261001T134456Z.md (**superseded**). The f01–f03 file gives 150/208 rows = 72.1% → claim holds on f01–f03 | U-row, not independent (blocks repeat tasks; U2B/U2Q states shared by 3 cells) | class-(ii) share of M = 1 rows | none | S-τ Bank U, 6 cells | DESC | **P8**, P20 |
| A10 | l.4 "These outcome labels did not reproduce reliably under an alternative, stochastic relay simulator" | simctrl_20261001T212742Z.md (7/39 retained) → match | 39 f01 class-(ii) flip states + 39 controls | sign of replicate-mean flip | Clopper–Pearson | f01 class-(ii) flips only; Sonnet 5.5 relay | EXPL (frozen control) | — |
| A11 | l.4 "Quantized-model uncertainty marks where actions diverge" | token_mech_20261001T185031Z.md §1b differing vs exact AUC 0.66–0.91 (pooled; per cell down to 0.59) → match | U-row, f01 | AUC of Htk_Q_0 | task-cluster bootstrap | f01 dev, 6 cells | EXPL | P23 |
| A12 | l.4 "a frozen uncertainty trigger enriches outcome-changing decisions on later blocks but has not been shown to select net-beneficial replacements" | token_mech_20261002T003130Z.md §3 Validation: turnover p .0182/.0613/.0002, net p .0345/.417/.262 → numbers match | U-row, f02/f03 (same 85 tasks) | turnover captured; net count | exact hypergeometric, no level pre-fixed | same tasks, 2 nonce blocks | EXPL (frozen rule, validated) | **P15** |
| A13 | l.5 "On 34 unseen telecom tasks ... −4.6 pp (90% CI −7.2 to −2.0); ... inconclusive" | holdout_confirm_20261002T012353Z.md → match | U-ho, CR decisional | G_all, weights ½, ¼, ¼ | crossed 90%, frozen readings | telecom, 3 W4 cells, same simulator | **CONF** (reading: inconclusive) | P33 |
| A14 | l.5 "two-sided-consequence and fragility-repeatability endpoints pass" | same (S1 True; S2 ρ 0.5883, p 0.0001) → match | U-ho | r > 0 and d > 0; Spearman over halves | crossed / permutation | as above | **CONF** | — |

### Introduction (introduction.tex)

| # | Claim | Source → match | Unit | Estimand | Interval | Scope | Status | Problems |
|---|---|---|---|---|---|---|---|---|
| I1 | l.4 "−0.2 to +4.2 pp ... ±6–7 pp wide, so an equivalence test at ±3 pp fails everywhere" | analysis/insights/iter_4/out/success_ni_ALIGNED_20260930T213009Z.md → numbers match on the crossed 95%/90% CIs. On fixed-task 90% CIs, q8 GPTQ [−1.6, +1.0] and q8 AWQ [−0.3, +2.8] lie inside ±3 | U-tb (q4 AWQ 1699 units; older snapshot 20260930T2115Z) | Q − BF16 success | CR (TOST) | S-τ | DESC | **P16** |
| I2 | l.7 case (q4 AWQ-W4, airline 31, f13, decision 1/12): only BB succeeds | ghf §4 Case 5 (pattern 1000) → match | 1 state | 4 arms | — | 1 state | DESC (illustration) | — |
| I3 | l.8 "a handover to B after Q's error damages a task that Q would have recovered by itself (§discussion)" | **Not in discussion.tex**. The closest evidence is ghf §4 Case 6 (q4 AWQ retail 61, pattern 1101) | 1 state | — | — | — | DESC | **P5** |
| I4 | l.8 "must therefore be measured separately" | inference from one case | — | — | — | — | framing | P19 |
| I5 | l.14 R1 bullet: 15.5–20.9% units; "rescuing about as often as damaging"; −1.9 to +2.9 | dev_all 070326Z → match | U-tb | M, r, d, G_all | FP | S-τ | EXPL | P10 |
| I6 | l.15 "about a quarter ... (pooled 26.9%) ... strict reversals are rare and the mean interaction is near zero" | ghf §2 → match | U-st | off-diagonal share, E[I] | FP | S-τ W4 | DESC | P14 |
| I7 | l.15 "on 80 re-run states, G−H −2.5 ... −8.5 ... (change −6.0 [−16.2, +4.2]); no ordering is established that transfers" | simctrl_p_20261002T015200Z.md pool → match | 80 states (20/cell; 49 tasks) | G − H | SB | 4 W4 cells, Sonnet 5.5 | EXPL | — (good) |
| I8 | l.16 Bank U text; labels did not reproduce | bank_u_f01_f02_f03 §3; simctrl → match | U-row; 39 + 39 states | composition share | — | S-τ | DESC/EXPL | P20 |
| I9 | l.16 holdout: rescues and damages, fragility repeats, −4.6 (−7.2, −2.0), inconclusive | holdout_confirm → match | U-ho | G_all, S1, S2 | CR 90% | telecom, 3 cells | CONF | — |
| I10 | l.16 "Two-sided turnover also appears on BFCL and ALFWorld" | ext_20261001T135106Z.md → match | U-item, one run | r, d | IT | BFCL q4/q8; ALFWorld q8 only | EXPL | P24 |
| I11 | l.17 R4 bullet: uncertainty locates divergences; trigger enriches; not shown net-beneficial | token_mech ×2 → match (with P15 caveat) | U-row | AUC; captured turnover | hypergeometric | f01 → f02/f03, same tasks | EXPL | P15, P23 |
| I12 | l.20 Contribution (1): protocol with bit-exact replay acceptance, paired estimands, fixed-pool vs new-task inference; "the 2×2 crossing itself is a standard factorial design" | FORK_PROTOCOL §8 → match | — | — | — | — | methodological | P27 |
| I13 | l.20 Contribution (2): weight, KV-cache and stress quantization, two sizes, three benchmarks | coverage (ghf §5) → match. ALFWorld is q8 only; KV/stress are not on every benchmark | — | — | — | — | DESC | — |

### R1 (results_r1.tex)

| # | Claim | Source → match | Unit | Estimand | Interval | Scope | Status | Problems |
|---|---|---|---|---|---|---|---|---|
| R1.1 | Table 1, all rows (r, d, M, G_all, FP, CR, div.) | dev_all 070326Z → **all 11 rows + W4 pool match** | U-tb | full pool | FP / CR | S-τ, 11 cells | EXPL/DESC | P28 |
| R1.2 | l.31 heading "Two-sided turnover, small net gain"; M 15.5–20.9% of units | → match | U-tb | M | FP | S-τ W4 | EXPL | — |
| R1.3 | l.32 r 6.8–11.4, d 7.5–10.1, G_all −1.9…+2.9; two FP intervals exclude 0; no CR does | → match (W4 cells) | U-tb | r, d, G_all | FP / CR, unadjusted | S-τ W4 | EXPL | — |
| R1.4 | l.32 W4 pool +0.7 [−0.3, +1.6], M 18.6 | → match | U-tb, equal weight | G_all | FP | S-τ | EXPL | — |
| R1.5 | l.33 "KV8 turns over fewer outcomes (6.5–8.1%), and the stress cells reach W4-like turnover with only three blocks" | KV8 matches. **Stress: 19.2, 18.8, 18.4, 20.4 and q8 RTN-W3 6.7** | U-tb | M | FP (t, 2 df) | cross-cell | DESC | **P6**, P26 |
| R1.6 | l.34 "A small net gain thus coexists with substantial two-sided turnover"; G_all ≠ end-to-end | → consistent | — | — | — | S-τ | EXPL | — |
| R1.7 | l.36 "top 20% of tasks hold 57–71% of all flips ... turnover and its direction repeat across disjoint halves" | consequence_v2_20261001T070850Z.json (0.566–0.713) → match. The direction-repeat half has **no src**; see direction_replication_v2_20261001T0600Z_20261001T070500Z.json ("INTERNAL REPLICATION ... not confirmation") | tasks (85), development outcomes already viewed | share in top 20% tasks; split-half | permutation (Freedman–Lane) | S-τ W4 + KV8 | EXPL, retrospective | P31 |
| R1.8 | l.38 "on unseen telecom tasks, its pre-registered test passed (ρ=0.59, p=.0001)" | holdout_confirm S2 → number matches. **S2 tests only cross-half repeatability of per-task turnover, with no "beyond difficulty" claim (PREREG §1 C3). It does not test concentration or direction** | U-ho tasks | Spearman(m_A, m_B) | persona-stratified permutation | telecom, 3 cells | CONF (S2 only) | **P2** |

### R2 (results_r2.tex)

| # | Claim | Source → match | Unit | Estimand | Interval | Scope | Status | Problems |
|---|---|---|---|---|---|---|---|---|
| R2.1 | Table 2 + crossed table + 16 patterns + Fig. 3×3 counts | ghf §1–§3; agreement_control §2 → **all match** (figure counts are count-summed; header shares are equal-weight) | U-st | G, H, F, differences; off-diagonal; reversals; E[I] | FP / CR | S-τ, 11 cells | EXPL/DESC | P38, P39 |
| R2.2 | l.31 heading "On average over W4 cells, no option has a detectable gain": G +0.5, H +0.2, F +0.7, all and their differences cover 0 | ghf pools W4:all → match | U-st | divergent-only | FP | S-τ W4 | DESC | — |
| R2.3 | l.34 heading "Within cells, the paired gains differ" (q8 GPTQ G +3.3, G−H +2.9, F +5.4, F−G +2.1; q8 AWQ G−H +3.4; q4 GPTQ G −2.9, G−H −3.6; q8 RTN-W3; q4 KV8 H −2.5) | ghf §1 → **all match** | U-st | within-cell paired | FP, unadjusted (Holm only for 4 G−H) | S-τ | EXPL | P12 |
| R2.4 | l.36 Holm over 4 W4 cells: q8 p = .013, .012; q4 GPTQ p = .069; CR G−H covers 0 in all 4; "exploratory" | ghf_multiplicity_20261001T225727Z.md → match | U-st | G − H | t + Holm (m = 4), CR | S-τ W4 | EXPL, PH (multiplicity added W96) | — (good) |
| R2.5 | l.37 "Cells select different states, so an ordering across cells is descriptive and cannot be attributed to the quantizer or the bit width alone" | ghf header → match | — | — | — | — | DESC | — (good) |
| R2.6 | l.39 heading "A BF16 reference action can lower success": q4 GPTQ G −2.9; "similarly under B's (Δ_B −3.2 [−6.4, +0.2])" | ghf §1 → numbers match. Δ_B CI covers 0; CR for G is [−10.3, +4.2] | U-st | G, Δ_B | FP, unadjusted | 1 cell | EXPL | P21 |
| R2.7 | l.70 heading "The action's consequence often depends on who continues": 26.9 [25.7, 28.1]; per cell 22.9–30.5; KV8 15.3 [13.2, 17.3]; W4−KV8 descriptive | ghf §2 → match | U-st | P(I ≠ 0) | FP | S-τ | DESC | P17 |
| R2.8 | l.71 pairing control 38.0 [36.7, 39.0], κ 0.29 [0.27, 0.32] (CR [0.22, 0.36]); KV8 33.6, κ 0.55; "agree more than random cross-state pairing" | agreement_control_20261002T024240Z.md §2 → match | U-st | p_e, κ (equal weight) | FP / CR | S-τ | DESC, PH (review 9) | — (correctly not called a null) |
| R2.9 | l.72 "This control is not a no-interaction null ... I ≠ 0 is a non-additive interaction ... does not by itself establish a recovery or quantization-specific mechanism, or a deployment gain" | → consistent with source wording | — | — | — | deterministic setting | interpretive | P17 |
| R2.10 | l.73 reversals 3.2% pooled; 1.2–4.2% per cell; 8–14% of off-diagonal mass | ghf §2; derived 45/422 = 10.7, 29/276 = 10.5, 66/476 = 13.9, 40/337 = 11.9, 7/93 = 7.5, 10/127 = 7.9 → match after rounding | U-st | share | FP | S-τ W4 + KV8 | DESC | — |
| R2.11 | l.75 "Why the mean interaction is near zero" (13.6 vs 13.4; E[I] +0.0 [−1.9, +2.0]; new-task 22.1–32.0); "value of a fixed replacement policy is E[G], E[H] or E[F], not E[I]" | ghf §2 → match | U-st | E[I], P(I ≠ 0) | FP / CR | S-τ W4 pool | DESC | P14 |

### R3 (results_r3.tex)

| # | Claim | Source → match | Unit | Estimand | Interval | Scope | Status | Problems |
|---|---|---|---|---|---|---|---|---|
| R3.1 | l.6 heading "Ordinary states turn over less, mostly through text": M .078–.090 (q4 W4 U1/U2B), .047–.090 (q8 W4), ≤ .047 (KV8); net within ±.028 / ±.050; all intervals cover 0 | bank_u_f01_f02_f03_20261002T003037Z.md §2 → **all match** | U-row (task-equal), 3 blocks | M, G per sub-bank | t over 3 block means (2 df) | S-τ Bank U | DESC | P25 |
| R3.2 | l.7 "Identical actions never change the outcome, as determinism implies" | §3 class (i) M = 0.000 in all 6 → match | U-row | — | — | — | DESC (check) | — |
| R3.3 | l.7 150/208 rows ≈ 72.1% class (ii); 26 tool/arg; "the rows are not independent states, since the three blocks repeat the same tasks" | §3; derivations re-done (150 = 158 − 8 U2Q duplicates; 208 = 216 − 8; 26; class iv 32; 150 + 26 + 32 = 208) → match | U-row | composition share | none | S-τ | DESC | P20 |
| R3.4 | l.8 per-instance rates 14.4 / 18.2 / 18.9%; 1045 of 1357; "not because each text difference matters more" | derived 150/1045, 26/143, 32/169 → match | U-row | flip rate per class | none | S-τ | DESC | — |
| R3.5 | l.9 "Simple content features do not separate flipping from non-flipping text pairs (Appendix)" | §4 says "no tests are run". **appendix.tex:200 (f01–f03) says above-median length difference co-occurs with outcome change in all four sub-bank×model groups (30/154 vs 15/155; 22/101 vs 6/101; 33/138 vs 11/139; 16/99 vs 9/100)** | U-row | — | none | S-τ | DESC | **P3** |
| R3.6 | l.12–13 frozen control; 7/39 retained (0.075–0.335), 6 reverse, 26 vanish (15/2/9); 11/39 new (0.15–0.45); replicate disagreement 41%, 21–26% | simctrl_20261001T212742Z.md → match | 39 + 39 f01 states | sign of replicate mean | Clopper–Pearson | f01 class-(ii) flips; Sonnet 5.5 relay, R = 3 | EXPL (frozen manifest) | P29 (provenance) |
| R3.7 | l.14 bold "did not reproduce reliably under this alternative relay setting"; "not evidence that text consequences are simulator artefacts" | → consistent | — | — | — | — | EXPL | — (good) |
| R3.8 | l.16–17 80 states sampled before running; 7896 calls; integrity passed; r = 0.63–0.68; Sonnet G −3.0, H +5.5, G−H −8.5 [−14.8, −2.8]; original −2.5 [−11.2, +6.2]; change −6.0 [−16.2, +4.2] | simctrl_p_20261002T015200Z.md → match (r 0.628–0.683; 20 unexposed branches kept per protocol) | 80 U-st (49 tasks) | divergent-only, equal weight | SB | 4 W4 cells, Sonnet 5.5, R = 5 | EXPL (frozen; batch 2 launched on capacity per protocol) | — |
| R3.9 | l.18 "too small to test ...; even the original simulator gives G−H = 0.0 for both q8 W4 cells ... neither confirmed nor shown to reverse" | → match | — | — | — | — | EXPL | — (good, (g) respected) |
| R3.10 | l.19 E[I_s²] = 0.050 [0.004, 0.107] (uncorrected 0.110); not a share | simctrl_p_interaction_20261002T024357Z.md → match | 80 states | mean squared interaction | SB | Sonnet only | EXPL, PH | — |
| R3.11 | l.21 holdout design (34 × 12 × 3; weights ½, ¼, ¼; crossed 90% vs ±3 pp); "All 12 blocks were complete" | PREREG_FORK_CONFIRM §0; holdout_confirm → match (1200/1224 units; 2 structural task×cell exclusions disclosed only in the appendix) | U-ho | — | — | telecom | CONF design | P33 |
| R3.12 | l.22 G_all −4.57 [−7.17, −1.96] (block-t [−6.08, −3.05]); readings → inconclusive | holdout_confirm → match | U-ho | G_all | CR 90% decisional | telecom, 3 cells | **CONF** | — |
| R3.13 | l.22 "Descriptively, the interval lies entirely below zero: ... replacing ... lowered average success" | → numerically true; not a pre-registered reading | U-ho | G_all | CR | telecom | DESC beyond the prereg readings | P35 |
| R3.14 | l.22 S1 r +5.21 [+3.30, +7.11], d +9.77 [+6.45, +13.10]; S2 ρ 0.59, p .0001 | → match | U-ho | r, d; ρ | CR; permutation | telecom | **CONF** | — |
| R3.15 | l.23 post hoc R2: G −4.6 [−7.8, −1.5], H −2.8, F −2.5, G−H −1.8, mean I −5.0 [−9.6, −0.4]; 20.7% vs 25.7% expected, κ 0.19 | holdout_r2_posthoc_20261002T024414Z.md §1, §3 pool → match | 1180 U-st | divergent-only, prereg weights | CR 95% | telecom | DESC, **PH** | P22, P14 |
| R3.16 | l.24 "This G conditions on divergence; it nearly equals G_all ... because 1180 of 1200 units diverge" | → match (385 + 399 + 396; 396 + 408 + 396) | — | — | — | — | DESC | — |
| R3.17 | l.25 "The holdout confirms two-sided consequences and repeatable task fragility, as pre-specified, **and no positive average benefit**; it does not confirm the paper's other development results" | holdout_confirm readings: positive_gain = false is *not* a confirmed "no benefit"; the frozen reading is inconclusive | U-ho | — | — | telecom | **overreach of CONF** | **P1** |
| R3.18 | l.27 BFCL/ALFWorld: "changes the outcome in 5.2–24.6% of items, in both directions"; net covers 0 except BFCL q4 AWQ −3.8 [−6.5, −1.3] | ext_20261001T135106Z.md → match (W4 cells) | U-item, one run | M, G_all, full pool | IT | BFCL q4/q8, ALFWorld q8 | EXPL | — |
| R3.19 | l.28 "Two-sided turnover is therefore not specific to a user simulator" | inference | — | — | — | 2 environments, item-level | EXPL | P24 |
| R3.20 | l.29 ext R2: off-diagonal 4.7–17.1 (pool 10.3), 32.8–40.0 (pool 36.4); κ 0.44–0.71 / 0.10–0.24; ALFWorld GPTQ-W3 H +38.5, G−H −34.6 [−43.5, −25.4]; KV4 reduce to H | ext_r2_20261002T024433Z.md → match | U-item, divergent | off-diagonal, κ | IT | BFCL, ALFWorld | EXPL, **PH** | — |

### R4 (results_r4.tex)

| # | Claim | Source → match | Unit | Estimand | Interval | Scope | Status | Problems |
|---|---|---|---|---|---|---|---|---|
| R4.1 | l.4 1140 cell×state rows, 58 flips; truncated top-20 entropy/KL | token_mech_20261001T185031Z.md §0 → match | U-row f01 | — | — | f01 dev | EXPL | — |
| R4.2 | l.7 heading "Uncertainty locates divergence": AUC 0.66–0.91 per sub-bank and model; U1 margin AUC 0.31 [0.22, 0.40] (q4), 0.24 [0.13, 0.36] (q8) | §1b pooled rows; §1a all_states mQ_min → match | U-row | AUC | task-cluster bootstrap | f01 | EXPL | P23 |
| R4.3 | l.9 heading "Among divergent states, it does not reliably identify consequences"; "In U1 the effect vanishes: no Q-visible statistic has an interval excluding 0.5" | §1a U1 differing_only → true (21 and 9 flips) | U-row | AUC | bootstrap | f01 | EXPL | P18 |
| R4.4 | l.9 "Only q4 U2B keeps a moderate signal (mean entropy over a_Q, AUC 0.73 [0.53, 0.89])" | 0.73 matches. **q4 U2Q differing_only: Htk_Q_0 AUC 0.90 [0.67, 1.00], mQ_0 0.10 [0.00, 0.33] (10 unique states, 4 flips) also exclude 0.5** | U-row | AUC | bootstrap | f01 | EXPL | **P7** |
| R4.5 | l.9 "At the first divergent token, entropy and KL do not separate flips from non-flips, with one exception on 4 flips (q4 U2Q, KL AUC 0.80 [0.65, 0.93])" | KL 0.80 matches. **Same q4 U2Q row: Htk_Q_k 0.25 [0.07, 0.48], mQ_k 0.74 [0.55, 0.92]; per cell: U1 q4 GPTQ Htk_Q_k 0.30 [0.13, 0.48]; U2B q4 KV8 KLu_k 0.10 [0.00, 0.27] (opposite direction)** | U-row | AUC | bootstrap, unadjusted | f01 | EXPL (diagnostic) | **P7** |
| R4.6 | l.9 no class reproduces the Lotfi marker enrichment; q4 other_lexical RR 1.89, Fisher p = .019 uncorrected | §2 → match (q8 "confirmation" RR 9.56, p = .017 on 3 rows, not mentioned) | U-row | rate ratio | Fisher, unadjusted | f01 | EXPL | — |
| R4.7 | l.10 "uncertainty thus marks *where* ... much better than *which* changes matter" | synthesis | — | — | — | f01 dev | EXPL | P23 |
| R4.8 | l.12–13 frozen S_mm trigger; 50/114/222 escalated; net +4/+2/+5 (6/2, 7/5, 16/11) vs +0.21/+0.98/+2.38 (p .0345/.417/.262); captured 8/12/27 vs 3.48/7.52/14.30 (p .0182/.0613/.0002) | token_mech_20261002T003130Z.md §3 Validation U1 S_mm PRIMARY → **all match** | 1020 U-row f02/f03 (same 85 tasks) | counts | exact hypergeometric | 6 cells | EXPL (frozen on f01) | P15 |
| R4.9 | l.14 nominal .05 only at 5% and not after Holm; at 20% 0.49 vs 0.23 pp, +0.26 pp | derived → match | — | — | Holm(3) | — | EXPL | — |
| R4.10 | l.17–18 oracle +3.33/+3.73/+3.73 pp; rule 4/34, 2/38, 5/38; menu oracle 0.202 vs 0.117; KL row 33 vs 16.7, Holm p 1.0 | oracle_trigger_20261002T024423Z.md §1a, §1b, §2 → match (menu oracle pool is **state-weighted**) | U-row / U-st | — | exact / Clopper–Pearson | — | EXPL, **PH** | P30 |

### Discussion (discussion.tex; serves as the conclusion)

| # | Claim | Source → match | Unit | Estimand | Interval | Scope | Status | Problems |
|---|---|---|---|---|---|---|---|---|
| D1 | l.4 "Average success, action divergence and replacement gain answer different questions and can disagree" | synthesis | — | — | — | S-τ | framing | — |
| D2 | l.4 "The four W4 cells have small end-to-end differences with wide intervals" | success_ni_ALIGNED → match | U-tb | Q − B success | CR | S-τ | DESC | — |
| D3 | l.4 "Their **Bank P states** replace actions with 15.5–20.9% turnover, but the pooled replacement gains are near zero" | dev_all: 15.5–20.9 is **per task×block unit (full pool)**; per Bank P state, M is 24.0/23.6/20.7/22.7 | U-tb, mislabelled as U-st | M | FP | S-τ W4 | DESC | **P4** |
| D4 | l.5 "Reporting only the first two cannot tell whether a BF16 fallback is worth its cost" | cost is out of scope (limitations l.8) | — | — | — | — | framing | P32 |
| D5 | l.5 text actions need a simulator control; recommend r, d, M with denominators; keep FP and CR apart | → consistent | — | — | — | — | recommendation | — |
| D6 | l.7 "The best unit of replacement is not universal. On the fixed task pool, the q8 W4 cells favour replacing the current action and a severe W3 cell the continuation ..., but these orderings are exploratory and unconfirmed" | ghf / multiplicity / simctrl_p → numbers OK; "not universal" is a cross-cell claim | U-st | G − H | FP | cross-cell | DESC | **P13** |
| D7 | l.7 "Measure G, H and F per configuration and environment" | recommendation | — | — | — | — | — | — |
| D8 | l.9 "Escalation can hurt. Replacements damage as well as rescue" | dev_all, holdout S1 → match | U-tb / U-ho | d > 0 | FP / CONF S1 | S-τ + telecom | EXPL + CONF | — |
| D9 | l.9 "B continuing lowers success in q4 KV8" | ghf H −2.5 [−4.5, −0.5] FP; **CR [−6.4, +1.1]**; unadjusted, 1 of ~66 cell×contrast intervals | U-st | H | FP, unadjusted | 1 cell | EXPL | **P12** |
| D10 | l.9 "on unseen telecom tasks action replacement lowers it by 4.6 pp" | holdout_confirm −4.57 → number matches, but the frozen reading is inconclusive and "lowers" is not a pre-registered reading | U-ho | G_all | CR 90% | telecom, 3 cells | CONF endpoint, DESC reading | **P11** |

### Extra rows: method/limitations claims that carry headline numbers

| # | Claim | Source → match | Status | Problems |
|---|---|---|---|---|
| X1 | method.tex:31 "an engineering gate ... passed every check. Q→Q 20/20, B→B 10/10" | FORK_PROTOCOL §8 l.314–315 → counts match. The B→B set **first failed on `official_reward`** (stale field) and was re-verdicted offline | DESC | P27 |
| X2 | method.tex:32 "In production, a sampled QQ no-op passed 924/924 units ..., and the outcome-independent bank passed 135/135 no-ops" | 924/924 matches dev_all 070326Z; later dev_all (…093944Z) shows 928/928. **135/135 = analysis/fork/bank_u/gate/*/f01 (noop_frac 1.0); production f01–f03 summaries: 328/328** | DESC | **P9**, P28 |
| X3 | method.tex:8 "The user simulator is one greedy Qwen3-30B-A3B-Instruct model" | /data/ziyangs/cloq_work/sims/*.json (hf_id Qwen/Qwen3-30B-A3B-Instruct-2507) → **correct**. But every fork state file's `simulator.user_model_id` and the SIMCTRL header say Qwen3-4B-Instruct-2507 (stale default of cloq/config.py; RESEARCH_LOG l.235) | DESC | P29 |
| X4 | limitations.tex:3 "equivalence tests at ±3 pp fail" | as I1 (crossed only) | DESC | P16 |
| X5 | limitations.tex:14 "Its negative average gain is specific to telecom, these cells and this simulator" | "specific to" asserts non-generality that was not tested | — | P11 |

**Count: 14 + 13 + 8 + 11 + 20 + 10 + 10 = 86 scoped claims, + 5 extra = 91 audited.**

---

## 2. Ranked problem list with fixes

Severity: **S1** = must fix before the evidence freeze (misstatement, internal contradiction, a pre-registration overreach, or a number or pointer that is wrong); **S2** = strong (wording stronger than the evidence, unit or scope drift); **S3** = minor (provenance, labels, polish). Category letters follow the task brief (a–i).

### S1 — must fix

**P1 (f, i). The holdout is said to "confirm ... no positive average benefit".** results_r3.tex:25: "The holdout confirms two-sided consequences and repeatable task fragility, as pre-specified, and no positive average benefit; it does not confirm the paper's other development results."
- The pre-registered positive-gain reading failed. Failing to confirm a gain is not confirming its absence. The frozen rule reads the primary endpoint as *inconclusive*, and "no positive benefit" is not one of the pre-specified readings. This also contradicts abstract l.5 and intro l.16 ("inconclusive under the frozen readings").
- Fix: "The holdout confirms, as pre-specified, two-sided consequences (S1) and repeatable task fragility (S2). Its primary endpoint is inconclusive under the frozen readings. Descriptively, its estimate is negative. It does not confirm any other development result."

**P2 (f, i). The R1 concentration and direction claim borrows the holdout S2 pass.** results_r1.tex:38: "This is a retrospective association on viewed development data ...; on unseen telecom tasks, its pre-registered test passed (ρ=0.59, p=.0001)."
- S2 tests only whether per-task turnover repeats across the two nonce halves. Its honest description is "real task pairing is more consistent than persona-preserving random pairing" (PREREG §1 C3). It tests neither concentration in the top 20% of tasks nor direction, and it makes no beyond-difficulty claim.
- The direction-repeat half has no src (see P31).
- Fix: "This is a retrospective association on viewed development data (Appendix~\ref{app:concentration}). On unseen telecom tasks, the pre-registered repeatability test (S2) passed: per-task turnover in one half of the nonce blocks predicts turnover in the other half better than persona-preserving random pairing (ρ=0.59, p=.0001; \S\ref{sec:r3}). S2 does not test concentration or direction, and it does not rule out task-difficulty explanations."

**P3 (b, e, i). The main text contradicts its own appendix on content features.** results_r3.tex:9: "Simple content features do not separate flipping from non-flipping text pairs (Appendix~\ref{app:banku})."
- appendix.tex:200 (f01–f03) says that above-median relative length difference *co-occurs with outcome change* in all four U1/U2B × model groups (30/154 vs 15/155; 22/101 vs 6/101; 33/138 vs 11/139; 16/99 vs 9/100). The appendix also notes that "In f01 alone this was visible only for q4".
- The main-text sentence is an f01-era survivor. The source (bank_u_f01_f02_f03 §4) runs *no tests*, so "do not separate" also reads an untested result as no effect.
- Fix: "Among simple content features, only an above-median length difference between the two texts co-occurs with outcome change (in all four U1/U2B × model groups); question, confirmation-request and new-entity flags show no consistent association. These are untested regular-expression features (Appendix~\ref{app:banku}). Bank P cannot see these differences by design."

**P4 (c, i). The discussion mislabels the turnover denominator.** discussion.tex:4: "Their Bank P states replace actions with 15.5–20.9\% turnover, but the pooled replacement gains are near zero."
- 15.5–20.9% is M on the **full pool of task×block units**, where units without a Bank P state count 0. On Bank P states themselves, M is 24.0 / 23.6 / 20.7 / 22.7% (dev_all, "Conditional on divergence").
- method.tex:45 says "We use three denominators and never mix them".
- Fix: "Replacing their first tool-structure-divergent action turns over 15.5--20.9\% of task$\times$block units (full pool), but the pooled net gain is near zero ($+0.7$ [$-0.3$, $+1.6$]\pp{})."

**P5 (i). The introduction cross-references an example that does not exist.** introduction.tex:8: "elsewhere, a handover to B after Q's error damages a task that Q would have recovered by itself (\S\ref{sec:discussion})."
- discussion.tex has no such example; nothing in it mentions recovery. The supporting evidence is ghf_20261001T211519Z.md §4 **Case 6** (q4 AWQ-W4, retail 61, block q3, decision 3 of 10, pattern 1101): QQ recovers from Q's failed write and succeeds, while QB fails.
- Fix: "In another recorded state, the reverse happens: after Q's failed write, B taking over fails while Q, continuing, recovers and succeeds (q4 AWQ-W4, retail task 61; \S\ref{app:patterns}, pattern \texttt{1101})." Add `% src: analysis/fork/out/ghf_20261001T211519Z.md (§4 Case 6)`. Alternatively, delete the clause.

**P6 (b). "Stress cells reach W4-like turnover" is false for one cell.** results_r1.tex:33: "and the stress cells reach W4-like turnover with only three blocks."
- dev_all gives q8 RTN-W3 M = 6.7% (KV8-like). The other four stress cells are 18.4–20.4%.
- Fix: "four of the five stress cells reach W4-like turnover ($M=18.4$--$20.4\%$) with only three blocks; q8 RTN-W3, in which Q rarely succeeds, turns over $6.7\%$."

**P7 (b). The R4 exceptions are under-reported.** results_r4.tex:9: "Only q4 U2B keeps a moderate signal ... At the first divergent token, entropy and KL do not separate flips from non-flips, with one exception on 4 flips (q4 U2Q, KL AUC 0.80 [0.65, 0.93])."
- token_mech_20261001T185031Z.md §1a, q4 U2Q differing_only (10 unique states, 4 flips): Htk_Q_0 AUC 0.90 [0.67, 1.00] and mQ_0 0.10 [0.00, 0.33] also exclude 0.5.
- §1b, first divergent token: the same q4 U2Q row also has Htk_Q_k 0.25 [0.07, 0.48] and mQ_k 0.74 [0.55, 0.92]. Per cell, U1 q4 GPTQ-W4 has Htk_Q_k 0.30 [0.13, 0.48], and U2B q4 KV8 has KLu_k 0.10 [0.00, 0.27], which runs in the *opposite* direction. All of these are unadjusted.
- Fix: "Only small sub-banks keep a signal: q4 U2B (mean entropy over $a_{\mathrm{Q}}$, AUC 0.73 [0.53, 0.89]) and q4 U2Q (entropy and margin at the action start, AUC 0.90 and 0.10; 10 states, 4 flips). At the first divergent token, pooled entropy and KL do not separate flips from non-flips except in q4 U2Q (KL AUC 0.80 [0.65, 0.93], entropy 0.25 [0.07, 0.48]; 4 flips). Per cell, two further unadjusted intervals exclude 0.5, in opposite directions (U1 q4 GPTQ-W4 entropy 0.30; U2B q4 KV8 KL 0.10)."

**P8 (b). Two `src` pointers go to the superseded f01-only Bank U output.**
- abstract.tex:4: `% src: analysis/fork/out/bank_u_f01_20261001T134456Z.md; ...`
- method.tex:40: `% src: analysis/fork/out/bank_u_f01_20261001T134456Z.md; ...`
- The f01–f03 output (bank_u_f01_f02_f03_20261002T003037Z.md) now exists, and R3, method.tex:49 and the appendix all use it. The appendix (l.156) says f01–f03 "supersedes the single-block f01 table".
- The abstract claim ("most ... are text differences") still holds on f01–f03 (150/208).
- Fix: replace both pointers with `analysis/fork/out/bank_u_f01_f02_f03_20261002T003037Z.md (§3)` (abstract) and `(§1, §2)` (method). Keep the f01 file only where the analysis is f01 by design: R4 token analysis, SIMCTRL.

**P9 (b, c). The Bank U no-op count is the gate run, labelled as production.** method.tex:32: "In production, ... the outcome-independent bank passed 135/135 no-ops. % src: ...; analysis/fork/bank_u/gate/*/f01/bank_summary.json"
- 135/135 is the **gate** run (`analysis/fork/bank_u/gate/*/f01`, noop_frac 1.0), not production.
- Production Bank U summaries over f01–f03 (`analysis/fork/bank_u/<cell>/f0{1,2,3}/bank_summary.json`, noop_frac 0.1) report 328/328 sampled no-ops, all passing (f01 alone: 121/121).
- Fix: "In production, a sampled QQ no-op passed 924/924 units of the development analysis and 328/328 sampled Bank U states over f01--f03; the Bank U gate passed a further 135/135 no-ops." Use src `analysis/fork/bank_u/*/f0{1,2,3}/bank_summary.json (noop); analysis/fork/bank_u/gate/*/f01/bank_summary.json`.

### S2 — strong

**P10 (c, i). "First divergent decision" vs. first tool-structure divergence.** abstract.tex:2 says "and forks at the first divergent decision" and "replacing a W4 agent's first divergent action" (the same wording appears at introduction.tex:14 and results_r1.tex:31).
- Bank P is the first **tool-structure** divergence, and text-only differences are skipped (method.tex:38, bold).
- A reader of the abstract will take "first divergent decision" literally. R3 then shows that text differences dominate turnover at ordinary states, which makes the distinction material.
- Fix (abstract): "...one greedy user simulator, and forks at the first decision where the two models' actions differ in tool structure (text-only differences are skipped)." Then use "first tool-structure-divergent action" at the first mention in intro l.14 and R1 l.31.

**P11 (a, f). The holdout estimate is stated without its status, and limitations over-scopes it.**
- discussion.tex:9: "and on unseen telecom tasks action replacement lowers it by 4.6\pp{}". This is unqualified: there is no "estimated", no interval and no "inconclusive". The discussion's sources do not show a definite size of effect.
- limitations.tex:14: "Its negative average gain is specific to telecom, these cells and this simulator". "Specific to" asserts that it does not generalise, which was not tested.
- Fix (discussion): "and on 34 unseen telecom tasks the estimated effect of replacing the first divergent action is $-4.6$\pp{} (crossed 90\% CI $-7.2$ to $-2.0$; the pre-registered primary reading is inconclusive)."
- Fix (limitations): "Its negative estimate is established only for telecom, these three cells and this simulator, and its pre-specified readings did not include a negative-gain category."

**P12 (a, multiplicity). One unadjusted fixed-pool interval becomes a discussion finding.** discussion.tex:9: "B continuing lowers success in q4 KV8 (\S\ref{sec:r2})". (results_r2.tex:34 says the same as a plain statement.)
- H = −2.5 [−4.5, −0.5] is a fixed-pool, unadjusted interval. It is one of about 66 cell×contrast intervals in Table 2. Its new-task interval is [−6.4, +1.1].
- Fix (discussion): "in q4 KV8, B continuing after Q's action has a negative estimated effect on the fixed task pool ($H=-2.5$ [$-4.5$, $-0.5$]\pp{}, unadjusted; new-task interval covers zero)".
- Fix (R2 l.34): append "(fixed pool, unadjusted; exploratory)".

**P13 (d, g). A cross-cell comparison becomes a claim that the best option varies.** discussion.tex:7: "The best unit of replacement is not universal. On the fixed task pool, the q8 W4 cells favour replacing the current action and a severe W3 cell the continuation".
- "Not universal" asserts heterogeneity of the best option across cells. That rests on comparing cells that select different state populations (method.tex:47 says such comparisons are descriptive).
- The q4 GPTQ-W4 G−H fails Holm. All four W4 G−H new-task intervals cover 0. SIMCTRL-P gives G−H = 0.0 for both q8 cells on its sample.
- Fix: "We found no replacement unit that is best in every cell. On the fixed task pool, $G-H$ is positive in the two q8 W4 cells (Holm $p=.013$, $.012$) and strongly negative in the severe q8 RTN-W3 stress cell; these within-cell orderings are exploratory, their new-task intervals mostly cover zero, a second simulator neither confirms nor reverses them, and cells differ in their state populations, so the contrast between cells is descriptive. Measure $G$, $H$ and $F$ per configuration and environment."

**P14 (a, i). "Mean interaction near zero" is stated without scope.** abstract.tex:3: "...dependence in the two directions is about equally frequent, so the mean interaction is near zero." (introduction.tex:15 and results_r2.tex:75 say the same.)
- This holds for the **development W4 pool** (E[I] = +0.0 [−1.9, +2.0]). It is weaker in the KV8 pool (−1.9 [−4.6, +0.6]) and *fails* in the post hoc telecom holdout: E[I] = −5.0 [−9.6, −0.4] (crossed 95%, holdout_r2_posthoc §1).
- The abstract discusses the holdout two sentences later, so an unscoped "near zero" invites the generalisation.
- Fix (abstract): "...in the pooled development W4 states, dependence in the two directions is about equally frequent, so the mean interaction is near zero there (not in the post hoc telecom holdout analysis)." In R3 l.23, add after "mean $I=-5.0$ [...]": "unlike the near-zero development W4 pool".

**P15 (a). The trigger's "enrichment" is stated without its rates and p-values.** abstract.tex:4 says "a frozen uncertainty trigger enriches outcome-changing decisions on later blocks" (introduction.tex:17 and results_r4.tex:15 say the same).
- Validation p = .0182 / .0613 / .0002 at 5/10/20%. No rate was fixed in advance, and the 10% rate is not significant.
- The "later blocks" are 2 nonce blocks over the **same 85 tasks**. The rows are tasks repeated across blocks and cells, but the hypergeometric test treats rows as exchangeable within a cell.
- Fix (abstract): "a frozen uncertainty trigger captured more outcome-changing decisions than matched random selection at two of three escalation rates on two later nonce blocks of the same tasks, but has not been shown to select net-beneficial replacements."

**P16 (a). "Equivalence fails everywhere" holds only for the crossed intervals.** introduction.tex:4: "Its intervals are about $\pm$6--7\pp{} wide, so an equivalence test at $\pm$3\pp{} fails everywhere". (limitations.tex:3 makes the same claim.)
- This is true for the crossed (new-task) intervals. On fixed-task 90% intervals, q8 GPTQ-W4 [−1.6, +1.0] and q8 AWQ-W4 [−0.3, +2.8] lie inside ±3 pp (success_ni_ALIGNED).
- The source snapshot (20260930T2115Z; q4 AWQ 1699 units) is also older than the fork snapshot (20261001T0600Z; 1700 units).
- Fix (intro): "Its new-task (crossed) intervals are about $\pm$6--7\pp{} wide, so an equivalence test at $\pm$3\pp{} fails in every cell (Appendix~\ref{app:e2e})."
- Fix (limitations): "equivalence tests at $\pm$3\pp{} on new-task intervals fail."
- Consider re-running success_ni on the 0600Z snapshot, or stating the snapshot.

**P17 (a). The off-diagonal share is read as controller dependence without a same-precision perturbation baseline.** abstract.tex:3 says "the outcome effect of the same action swap changes with the controller that continues". results_r2.tex:70 heading: "The action's consequence often depends on who continues".
- In a deterministic system, P(I ≠ 0) counts every state whose continuation outcome is sensitive to *any* change of controller, not to the precision of the controller as such.
- No same-precision perturbation 2×2 exists (for example, B vs. B under a different nonce): the coverage matrix shows no F4 forks for null or Gaussian configs.
- SIMCTRL-P shows how much noise alone produces (uncorrected E[Î²] 0.110 vs. corrected 0.050). The q8 RTN-W3 cell has κ = −0.016, no more agreement than random pairing.
- The R2 l.72 caveat ("does not by itself establish a recovery or quantization-specific mechanism") is good but does not reach the abstract.
- Fix (abstract, after the 26.9% sentence): "In this deterministic setting, this includes sensitivity of the continuation to any change of controller; we have no same-precision perturbation control that separates the two."
- Fix (limitations, add): "We did not run a same-precision perturbation $2\times2$ (e.g.\ B versus B under another nonce), so the off-diagonal share is not calibrated against controller-independent sensitivity."

**P18 (e). "Vanishes" reads a non-detection as no effect.** results_r4.tex:9: "In U1 the effect vanishes: no Q-visible statistic has an interval excluding 0.5."
- Fix: "In U1 the signal is not detectable: no Q-visible statistic has an interval excluding 0.5 (21 and 9 flips; f01)."

**P19 (a). "Must therefore" rests on one illustrated state.** introduction.tex:8: "\textbf{Average success, action divergence and precision-replacement gain must therefore be measured separately.}"
- Fix: "\textbf{This case illustrates why average success, action divergence and precision-replacement gain should be measured separately; R1 and R2 quantify how often it matters.}"

**P20 (c). The dependence of Bank U rows is understated.** results_r3.tex:7: "the rows are not independent states, since the three blocks repeat the same tasks".
- There is a second source of dependence. U2B and U2Q states are *the same state* in all three cells of a model. The 208 rows pool U1, U2B and U2Q, both models and all three blocks.
- Fix: "the rows are not independent states: the three blocks repeat the same tasks, and each U2B/U2Q state appears once per cell of a model".

**P21 (e, reverse). A non-significant Δ_B is read as an effect.** results_r2.tex:39: "B's action lowers success under Q's continuation ($G=-2.9$\pp{}) and similarly under B's ($\DB=-3.2$ [$-6.4$, $+0.2$])".
- The Δ_B interval covers 0. G's new-task interval is [−10.3, +4.2], and G's fixed-pool interval is unadjusted.
- Fix: "In q4 GPTQ-W4, B's action lowers success under Q's continuation on the fixed task pool ($G=-2.9$ [$-5.7$, $-0.2$]\pp{}, unadjusted; new-task interval covers zero), with a similar point estimate under B's ($\DB=-3.2$ [$-6.4$, $+0.2$]); the reference action itself is not reliably better here." Optionally add: "On the telecom holdout, $G=-4.6$ [$-7.8$, $-1.5$] (post hoc)."

**P22 (h). The holdout's "expected" share can be read as a null.** results_r3.tex:23: "and 20.7\% off-diagonal against 25.7\% expected ($\kappa=0.19$)". Unnamed, "expected" can be read as a chance or no-interaction baseline.
- Fix: "and 20.7\% off-diagonal, against 25.7\% under the marginal-preserving pairing agreement control ($\kappa=0.19$; not a no-interaction null)".

**P23 (a). "Marks"/"locates" is stronger than the AUCs support.** abstract.tex:4 says "Quantized-model uncertainty marks where actions diverge". results_r4.tex:7 heading: "Uncertainty locates divergence". results_r4.tex:10: "marks *where* ... much better than *which*".
- The AUCs are 0.66–0.91 pooled (0.59 in one cell), on f01 development data only.
- Fix (abstract): "Quantized-model uncertainty at the start of an action is associated with whether the two models' actions differ (AUC 0.66--0.91, development block)".
- Fix (R4 l.10): "On development data, uncertainty is associated with \emph{where} quantization changes the action more strongly than with \emph{which} changes matter."

**P24 (a). "Therefore not specific to a user simulator" over-reaches.** results_r3.tex:28: "Two-sided turnover is therefore not specific to a user simulator."
- The evidence is item-level, one run per item, with ALFWorld covering q8 only.
- Fix: "Two-sided turnover thus also occurs in two environments without a simulated user (one run per item; ALFWorld q8 only)."

**P25 (d). Bank U vs. Bank P is a descriptive cross-bank comparison.** results_r3.tex:6: "At ordinary states, replacing Q's action changes the outcome less often than at first divergences."
- The two banks are different state populations, and there is no interval on the difference.
- Fix: "Descriptively, at ordinary states replacing Q's action changes the outcome less often than at first tool-structure divergences (different state populations; no interval on the difference)."

**P26 (d). KV8 vs. W4 turnover is a cross-cell comparison.** results_r1.tex:33: "KV8 turns over fewer outcomes ($M=6.5$--$8.1$\%)".
- Fix: "KV8 cells turn over fewer outcomes ($M=6.5$--$8.1$\%; a descriptive comparison across cells)".

### S3 — minor, provenance and polish

**P27 (a). "Passed every check" omits a re-verdict.** method.tex:31: "an engineering gate on real divergence states in retail, airline and telecom passed every check."
- The B→B set first failed on `official_reward` (a stale trajectory field), which was recomputed and re-verdicted offline (FORK_PROTOCOL §8, l.315).
- Fix: "...passed every check (one B$\rightarrow$B field, \texttt{official\_reward}, was missing from older trajectories and was recomputed from the stored reward information before re-verdicting)".

**P28 (b). dev_all snapshots are mixed across the paper's evidence chain.**
- The paper cites dev_all_20261001T070326Z (snapshot 0600Z; no-op 924/924). Later dev_all outputs (…071025Z, …075557Z, …084525Z, …093944Z) have identical estimates but 926 to 928 sampled no-ops.
- ext_20261001T135106Z.md takes its τ² pool from …093944Z.
- 070326Z is the right anchor: ghf and agreement_control digests are pinned to it. Fix: add "snapshot 20261001T0600Z" next to "924/924" in method.tex:32, and note in the appendix that later snapshots reproduce the estimates.

**P29 (provenance). The fork files carry a stale simulator label.**
- method.tex:8 is correct (30B-A3B, per `/data/ziyangs/cloq_work/sims/*.json`).
- But every fork state file has `simulator.user_model_id = Qwen/Qwen3-4B-Instruct-2507`. That is the default of `cloq/config.py:33`, not the served model. The SIMCTRL report header (simctrl_20261001T212742Z.md l.3) inherits it.
- Fix: change the src to `% src: /data/ziyangs/cloq_work/sims/*.json (hf_id); docs/RESEARCH_LOG.md (stale user_model_id field)`. Add one appendix sentence: "Fork state files record a stale default \texttt{user\_model\_id}; the served simulator is identified from the replica registry."

**P30 (c). The menu-oracle pool is state-weighted.** results_r4.tex:17: "reaches 0.202 on W4 Bank P divergent states against 0.117".
- These are state-weighted pools, while every other pool in the paper is equal-weight over cells.
- Fix: "reaches 0.202 (state-weighted over the four W4 cells) against 0.117".

**P31 (b, missing src). The direction-repeat claim has no source.** results_r1.tex:36: "...and task-level turnover and its direction repeat across disjoint halves of the nonce blocks."
- Fix: add `% src: analysis/fork/out/direction_replication_v2_20261001T0600Z_20261001T070500Z.json (internal replication, viewed data)`.

**P32 (a, scope). "Worth its cost" contradicts the limitations.** discussion.tex:5: "Reporting only the first two cannot tell whether a BF16 fallback is worth its cost." limitations.tex:8 says cost is out of scope.
- Fix: "...cannot tell whether a BF16 fallback would raise success."

**P33 (c). The holdout intervention is not described precisely.** abstract.tex:5: "replacing the current action has an estimated effect of $-4.6$\pp{}".
- Fix: "replacing the first tool-structure-divergent action of three W4 cells (weighted $\tfrac12,\tfrac14,\tfrac14$) has an estimated effect of $-4.6$\pp{}". Also mention in R3 l.21 that 1200 of 1224 units were analysed, with 2 structural task×cell exclusions (Appendix~\ref{app:prereg}).

**P35 (f, polish). Label the holdout's descriptive reading.** results_r3.tex:22: "Descriptively, the interval lies entirely below zero: ... lowered average success."
- Fix: "Descriptively (this is not one of the pre-registered readings), the interval lies entirely below zero: on these unseen tasks, replacing the first divergent action with BF16's lowered average success."

**P37 (polish). Bank U units differ from the rest of R3.** Bank U figures in R3 l.6 are fractions (.078–.090), while every other figure is in pp or %. Convert them (7.8–9.0\%) or mark the unit.

**P38 (polish). Table 2 lacks a KV8 pool row.** Table 2 (tab:ghf) has a W4 pool row but no KV8 pool row, while the crossed table (gen_ghf_crossed) and the 3×3 figure both have one. Add a KV8 pool row from ghf pools KV8:all: G +0.1 [−2.8, +3.0], H −1.4 [−2.7, −0.1], F +0.6, G−H +1.6, F−G +0.5, F−H +2.1, off-diagonal 15.3, reversals 1.2, mean I −1.9.

**P39 (c, polish). The figure's shares and counts use different weightings.** In the 3×3 figure, the panel header gives the equal-weight off-diagonal share (26.9%) above count-summed cells, whose off-diagonal share is 27.1%; for KV8 it is 15.3% vs. 15.2%.
- Fix (caption): "Cell counts are summed over cells (summed off-diagonal 27.1\% and 15.2\%); headers give equal-weight cell averages."

---

## 3. Questions for authors (not wording fixes)

- **Q1.** Frozen trigger thresholds (manifests/fork/token_trigger_rule_v1.json) are about 4e-10 to 8.5e-10 at 5/10%, and **−0.25** for q8 GPTQ-W4 and q8 KV8 at 20%. A minimum margin of order 1e-9 means the rule fires on exact or near ties. Is −0.25 a sentinel? Every a_Q token is Q's argmax (1140/1140), which would make negative margins impossible. Please document the tie handling before freeze.
- **Q2.** The hypergeometric p-values treat the 1020 f02/f03 rows as exchangeable within a cell, but each task appears twice (2 blocks). Is a task-clustered permutation available?
- **Q3.** Is there any budget for a same-precision perturbation 2×2 (B under two nonces, or Q under a Gaussian null) on about 100 Bank P states, to calibrate P(I ≠ 0) (P17)?

## 4. Remaining `\todo{}` placeholders

- `paper/latex/sections/appendix.tex:397` — `\todo{RESTORE: the q8 RTN-W3 attention vs.\ byte-matched random-attention result (one seed) is cited only after its restoration output is checked; it is not used for any claim}`. This is the only one; main.tex:6, 30 and 32 only define the macro.

## 5. Verified correct (no action)

- **Table 1** (all 11 cells + W4 pool), **Table 2** (all 11 cells + W4 pool), the crossed table, the 16-pattern table and the 3×3 figure counts all equal ghf/dev_all.
- **Holm p-values**, **agreement control** (38.0 / κ 0.29 / KV8 33.6 / κ 0.55), **SIMCTRL** (7/6/26; 11/39; 41%, 21–26%), **SIMCTRL-P** (all pooled values; r 0.63–0.68; 7896 calls), **E[I_s²]** and all **holdout CONF numbers** (−4.57 [−7.17, −1.96]; S1; S2 ρ 0.5883 p 0.0001) match their sources.
- **Holdout post hoc R2**, **ext/ext_r2**, the **R4 trigger, oracle and KL-row numbers** and the **Bank U** composition derivations (150, 208, 26, 1045, 1357, 14.4/18.2/18.9) also match.
- **Intro case study** = ghf §4 Case 5.
- **The advisor's two governing statements are respected**: (1) the abstract and intro do not claim an ordering that transfers; (2) the pairing control is never called a null in R2.

---

## 6. Resolution (W99e, 2026-10-01)

Fixes applied to `paper/latex/sections/*.tex`. Each was checked against the source named above before it was applied. 36 of 37 fixed; P28 partly applied; one replacement wording (P5) was wrong, so the audit's alternative fix was used instead.

- **P1** fixed: R3 holdout summary rewritten as proposed. It now says S1/S2 are confirmed, the primary endpoint is inconclusive and the estimate is descriptively negative.
- **P2** fixed: R1 now describes S2 as a repeatability test against persona-preserving random pairing, and says it does not test concentration or direction.
- **P3** fixed: R3 now reports the length-difference association (untested regex features), as in the appendix.
- **P4** fixed: the discussion now says task×block units (full pool), with the W4 pool net +0.7 [−0.3, +1.6].
- **P5** fixed, but not with the proposed wording. That wording is factually wrong. In ghf §4 Case 6 (q4 AWQ retail 61, pattern 1101), Q's pivot action is *text*, and the failed `modify_pending_order_items` write is made by whichever controller continues. B, continuing, makes the failed write itself and fails; Q, continuing, makes the same failed write, recovers and succeeds. There is no "Q's failed write" before B takes over. The audit's alternative was applied instead: the clause and its dangling §discussion pointer were deleted.
- **P6** fixed, with one change. "in which Q rarely succeeds" became "whose own success is low": q8 RTN-W3 Q success is 9–26% per block-domain (queue/done/a6k2_q8_rtn_w3_qx.json), which is low but not rare.
- **P7** fixed as proposed: all AUCs were re-checked in token_mech_20261001T185031Z.md §1a/§1b and per-cell rows.
- **P8** fixed: the abstract and method src now point to bank_u_f01_f02_f03_20261002T003037Z.md. The f01 file stays cited in the appendix, where it is a required source.
- **P9** fixed: 924/924 production, then 328/328 Bank U production no-ops over f01–f03 (summed from analysis/fork/bank_u/*/f0*/bank_summary.json; f01 alone 121), then 135/135 gate.
- **P10** fixed: the abstract uses "the first decision where the two models' actions differ in tool structure (text-only differences are skipped)". The intro R1 bullet uses the same phrase, and R1/the discussion use "first tool-structure-divergent action".
- **P11** fixed: discussion and limitations, as proposed.
- **P12** fixed: discussion and R2.
- **P13** fixed, with one scope change. "a second simulator neither confirms nor reverses them" became "a second simulator (W4 cells only) neither confirms nor reverses the q8 orderings", because SIMCTRL-P has no RTN-W3 states.
- **P14** fixed: abstract and R3.
- **P15** fixed: the abstract is as proposed. The intro bullet now says "captures more outcome-changing decisions than random selection at two of three rates", and R4 no longer says "enriched".
- **P16** fixed: intro and limitations. The success_ni snapshot was not re-run.
- **P17** fixed: there is a short caveat in the abstract, and Limitations has the proposed sentence plus the deterministic-setting clause.
- **P18** fixed. 21/9 flips were verified.
- **P19** fixed.
- **P20** fixed.
- **P21** fixed. The optional holdout sentence was not added (it is already in R3).
- **P22** fixed.
- **P23** fixed: abstract, R4 heading ("Uncertainty is associated with divergence") and R4 closing sentence. The intro bullet was softened the same way.
- **P24** fixed: merged into the BFCL/ALFWorld sentence ("one run per item"; "ALFWorld: q8 only").
- **P25** fixed.
- **P26** fixed.
- **P27** fixed. The re-verdict was verified in FORK_PROTOCOL §8.
- **P28** partly applied: "snapshot 20261001T0600Z" was added next to 924/924 in the method. The proposed appendix note ("later snapshots reproduce the estimates") was **not applied**, because I could not verify the later dev_all outputs in this session.
- **P29** fixed: the method src now points to /data/ziyangs/cloq_work/sims/*.json (hf_id) and the RESEARCH_LOG. One sentence was added to Appendix "Fork mechanics".
- **P30** fixed: the menu oracle moved to Appendix H (page fit), labelled "state-weighted".
- **P31** fixed: src added.
- **P32** fixed.
- **P33** fixed: abstract and R3. R3 adds "1200 of the 1224 units ... 2 structural task×cell exclusions".
- **P35** fixed.
- **P37** fixed: Bank U M and net gain in R3 are now in % and pp.
- **P38** fixed: KV8 pool row added to Table 2 from ghf §1 KV8:all and §2.
- **P39** fixed: the 3×3 caption gives summed off-diagonal 27.1% / 15.2% (derived from the figure counts) and equal-weight headers.
- **§4 `\todo{RESTORE}`** (appendix.tex): replaced with a plain statement. The q8 RTN-W3 restored-attention vs byte-matched random-attention comparison was not completed. The attention arm and random-attention seed 1 ran (queue/done); seeds 2 and 3 are in queue/deferred (restoration line paused, W67/W74). The restoration output was never checked, and no result is reported.
