**TL;DR**
- First-review weaknesses: W1 partly resolved (TOST and a run-level test exist, but only pooled ±5 pp under a mixed null, and churn now *rejects* exchangeability, which is the paper's own Definition). W2 partly (sub-grid done; E8 fp32-head is half-run and decides it). W3 resolved as a pass artefact, but the null heterogeneity has moved into the conformal null. W4 partly (clean W3 damage holds; q8 RTN-W4 deficit gone; q14 now at risk). W5 partly (the protocol comparison is done; churn is newly exposed to Patodiya and Flat Score).
- New risks: churn is not yet a finding (it is confounded by prompt strata, a fixed-checkpoint effect and nonce reuse, and Gaussian families churn too); every hazard and C3 number predates the W8 dedup and must be recomputed; C4 is refuted for damage; X1 and l8 still reuse the null nonces; the scope is spread too thin for 10-05. Scores are 2.5/3/2/2.5 (confidence 4) now and 3.5/3.5/3.5/3.5 projected. Reframe to three contributions; cut C4, LiveCodeBench, telecom and Mistral.

# Second internal review: CLOQ storyline v3 (ARR / NAACL 2027 standards)

Reviewer role: adversarial internal reviewer, verification mode. Date: 2026-09-29. The experiment freeze is 10-05; ARR is 10-12 (`docs/insights/PLAN_iter3.md` TL;DR).

The object under review is storyline v3, as defined by:
- `docs/insights/PLAN_iter3.md` (C1–C4, X1–X5);
- `docs/insights/iter_2_prep.md` (A2-1…A2-9, F1/F2, E8–E11);
- `docs/insights/iter_2_conformal.md` (A2-10, A2-11, E12/E13);
- `docs/RESEARCH_LOG.md` W6–W9.

Context documents: `paper/perturbation-equivalence-closed-loop.review.md` (review v1) and `paper/perturbation-equivalence-closed-loop.md` / `paper/latex/` (still the v2 story; not reviewed line by line).

Spot checks performed by this reviewer:
- `analysis/insights/iter_2/out/c01_conformal_equivalence.json`: `snapshot.utc` = 2026-09-29T05:45Z. The null draws in `nullsets.A.models.*.null_draws` are:
  - q4 = {bf16, bf16_eager, null_n1, null_n2};
  - q14 = {bf16, null_n1, null_n2};
  - q8 = 7 draws.
- `scripts/a6000/make_tasks.py` L18/L44/L53: `NONCES` n1/n2 are reused by every RTN/GPTQ/AWQ cell.
- `/data/ziyangs/cloq_work/queue/todo/*x1*.json` carry nonces `3f9a1c07` and `b84e2d91`, which are n1/n2 again.
- Queue counts at review time: todo 212, running 22, done 182, failed 2.
  - fp32h: det pair done (identical metrics), 4 eval runs pending or running.
  - X1: 11 done, 21 todo. l8: 1 done, 48 todo. q30a3: 23 done / 32 todo. q32: 5 done / 54 todo.
  - Telecom and code (LiveCodeBench) are smoke-only (`x3_telecom_smoke_q4`, `code_smoke2_q{4,8}`). No Mistral (m24) tasks are queued.

---

## Part 1: Structured review

## Summary

Storyline v3 reframes the paper around four contributions:
- **C1, a measurement floor.** Greedy bf16 agents on τ²-bench diverge at a per-decision hazard of about 0.15–0.23 (q4) or 0.09–0.12 (q8). This holds from 1-ulp weight noise (k = 0.001, 2.6% of weights moved) through kernel reduction order to k = 0.03. The floor can be predicted across models from margin histograms (within 7% on q8/q14), and serving numerics alone move the canonical score by about 8 pp.
- **C2, a criterion.** An exact run-level permutation ("conformal") test of exchangeability with a null family, plus ε-equivalence by test inversion.
- **C3, two thresholds.** Divergence is predicted by open-loop flip rate (Spearman 0.99), while damage comes later (RTN-W3 about −15 to −19 pp; k ≥ 2).
- **C4, a protocol.** An open-loop gate, then a conformal interval, then closed loop only when needed.

New in v3: real FP8/AWQ checkpoints (X1), Llama-3.1-8B (W9), τ² telecom (X3), a LiveCodeBench code loop, and a "task-profile churn" result. The churn result says rate-equivalent quantized families change *which* tasks succeed (pooled Holm p ≤ 0.007).

The analysis layer is a big step up from the v2 draft:
- the declared-margin TOST;
- the sub-grid floor;
- the protocol comparison;
- the Replay Gap reconciliation;
- the honest power statements.

Three problems block the storyline as written:
1. The new headline (churn) is not yet separable from design artefacts.
2. Every per-decision number was computed before a data-integrity fix (W8 dedup) and before the infra-error redos.
3. C4 has been falsified for damage by the team's own analysis (A2-11).

In addition, the plan multiplies environments and families six days before freeze, when the existing three models are not yet frozen.

## Strengths

- **[S1] Power is reported honestly.** The draft states that per-family ±5 pp equivalence is unreachable at 85 tasks and ≤ 5 draws (M80 = 6.5–13 pp, `iter_2_prep.md` A2-1), and that a 2-draw conformal test cannot reject at 5% on q4/q14 (p_min 0.067/0.10, `iter_2_conformal.md` §1.2). Few agent-eval papers say this.
- **[S2] The floor is now identified below the grid.** Hazard 0.154–0.183 at k = 0.001 vs 0.179–0.227 at k = 0.03 vs 0 at D ≡ 0 (`iter_2_prep.md` A2-3 item 2; `out/p06_weight_ulp.json`). Review v1's W2 problems 1–2 are closed.
- **[S3] The cross-model floor prediction is quantitative:** 0.120 predicted vs 0.113 observed (q8), 0.151 vs 0.152 (q14) (A2-3 item 5). It is pre-registrable for q30a3/q32, and it is the paper's most "scientific" result.
- **[S4] The protocol comparison gives the criterion a consequence.** The null-referenced TOST declares 11/40 families equivalent vs 2/40 for Flat-Score-style; the canonical run sits +6.3 pp above its own null on q8 (A2-4, `out/p07_protocol_tally.json`).
- **[S5] Integrity incidents were caught, root-caused and logged:** F1/W6 (simulator outage scored as failure), F2 (tool-call typing bug), W3 (Inductor autotune), W8 (dedup), W9 (Llama template). The would-be fabricated results (+8–16 pp, −23 pp) are documented. This is a genuine strength *if* the paper includes an integrity appendix.
- **[S6] E8 has pre-registered predictions (a)–(d) with a falsification line** (`iter_2_prep.md` §3 E8). The det pair has run with identical metrics.
- **[S7] A2-7 withdraws a mechanism claim (write flips) that the data did not support.** This is good epistemic hygiene.

## Weaknesses

### Status of review v1 W1–W5

| v1 item | Status | Evidence | What is still open |
|---|---|---|---|
| W1: equivalence from non-rejection | **Partly** | `iter_2_prep.md` A2-1 (TOST, M80); `iter_2_conformal.md` §1.3–1.4 (`c01…json` `pooled.*.equiv_common_shift`) | Only pooled ±5 pp under null A. Under the stratum-matched null S, no family is ±5 pp-equivalent. Churn rejects exchangeability for AWQ/GPTQ/RTN-W4, so under the paper's own Definition these are *not* perturbation-equivalent (see W-B). |
| W2: floor under-identified / tie artefact | **Partly** | A2-3, A2-6; `out/p02_ties.json`; E8 det pair done (`queue/done/a6k2_det_q4_fp32h_{a,b}.json`) | Exact ties carry about 40–50% of the floor. Whether it is a bf16-grid property rests on E8, which is not yet evaluated. All hazards predate the W8 dedup (W-C). |
| W3: circular pooling, heterogeneous null | **Resolved** (pass artefact) / **not** (heterogeneity) | A2-2 (het z −0.19); `c01…json` `note_S` | The heterogeneity has moved into the prompt strata of the conformal null (canonical-prompt draws sit a few pp above nonce draws on q4). The "admission rule for null members" in C2 is promised but not specified. |
| W4: one model; q8 contradiction | **Partly** | A2-2 items 2–5 | The q8 RTN-W4 deficit is gone (−0.5 pp). Clean W3 damage is significant on q4/q14. q14 is now at risk (canonical +4 pp over null; free zone fires under A). The threshold lies only somewhere in (k = 1, k = 2–3]. The second family is not run. |
| W5: novelty vs Du / Flat Score / Replay Gap / Patodiya | **Partly** | A2-4, A2-5 | The Du positioning depends on E8. The Replay Gap tension is reduced, not removed. The new churn claim collides with Patodiya (outcomes change without an aggregate shift) and with Flat Score (failure set ρ ≥ 0.94 across precisions). Neither is positioned. |

### New weaknesses introduced by v3

- **[W-A] FATAL (until recomputed): C1/C3 numbers rest on a stale snapshot.**
  - The per-decision hazards (C1 floor, A2-3/A2-6, p02) and the ρ = 0.989 / jackknife+ coverage (C3, A2-11) come from snapshots at 05:06Z and 05:45Z on 09-29.
  - The W8 dedup ("6,724 records in 52 run-domains") was applied at 23:45 PDT = 06:45Z, *after* both snapshots. W8 itself says "iter_2 analyses (p0x, c01, c02) must be re-run".
  - W8 also deleted 6 more outage-affected runs, and the q4 nulls n3–n5 plus 7 cell redos were still in flight (`iter_2_conformal.md` §0).
  - q4 null A therefore has n = 4, of which 2 are canonical and 2 are the nonce-mates of every quantized cell.
  - Consequences:
    - Outcome-level numbers (TOST, c01 net/harm/churn) are probably stable, because dedup does not touch outcomes. But the run sets change, so they must be regenerated too.
    - Hazard-level numbers could move in either direction: abandoned attempts add decisions to the risk set, and they add first divergences.
  - No number from `iter_2_*` can go into the paper until a single frozen, post-dedup, post-redo snapshot has been regenerated and diffed.
- **[W-B] MAJOR: "Task churn" is not yet a finding. It has four confounds, and one of them is logical.**
  1. **Fixed-checkpoint effect.** Each quantized family is one checkpoint × 2 nonces, so its draws share weights. Every null draw shares the *reference* weights.
     - Churn therefore tests "p_t(Q) ≠ p_t(ref)". Any fixed weight change at or above the floor could do that, including a null-scale one.
     - There is no control in which a *null-scale fixed checkpoint* (for example k = 0.001 s1 or k = 0.03 s1) is run under ≥ 2 fresh nonces and tested for churn.
     - Without that control, "quantization re-allocates successes" cannot be told apart from "any fixed checkpoint has its own task profile". The latter is actually the v3 title's thesis, and it would make churn trivially true.
  2. **Prompt strata.** Gaussian families are canonical-prompt; nulls are nonce-heavy. Gaussian k = 0.3 also churns (pooled Holm 0.033) and k = 0.03 has raw p = 0.024 (`iter_2_conformal.md` §1.4). That pattern suggests part of the signal is stratum mismatch, not compression.
     - The "conservative" argument (§1.4) is explicitly "an argument, not a theorem".
     - The stratum-matched test S was reported only for gauss families. Quantized families under S exist on q8 today (null n3–n5 are unused by families) and have not been reported.
  3. **Nonce reuse.** Quantized cells reuse the nonces of null_n1/n2. On q4 and q14 these are 2 of 4 and 2 of 3 null draws (`c01…json` `null_draws`). Paired draws violate exchangeability within the bag. Their direction is argued, not shown.
     - X1 and l8 are about to repeat the mistake: the todo X1 tasks carry nonces n1/n2, against E13's own rule.
  4. **Logical tension.** The Definition of perturbation equivalence *is* exchangeability. If churn rejects for AWQ, GPTQ and RTN-W4, those formats are **not** perturbation-equivalent under the paper's own criterion, even though they are pooled rate-equivalent. The storyline presents both as findings without choosing which criterion is operational.
  - **Effect size.** Observed churn 0.18–0.26 vs permutation medians 0.13–0.17 is an excess of about 0.05. Most churn is null churn. Report excess churn, not raw churn.
  - **Infra-error redos and dedup are not the cause.** Dedup does not touch outcomes, and infra episodes are treated as missing with complete-case task sets. But complete-case task sets differ across bags, so a per-bag churn value is not comparable across families until every run is 85/85.
- **[W-C] MAJOR: the validity of the C2 test under a mixed null is overstated.**
  - "The test is exact under H0 without assuming independence across tasks" holds only if the *null draws are exchangeable among themselves*.
  - They demonstrably are not:
    - q4 canonical-prompt draws sit above nonce draws (A2-2 item 1);
    - q14 canonical is +4.0 above its null (A2-4);
    - q8 canonical is +6.3 (A2-4).
  - Other problems:
    - Multiplying e-values across models assumes independent model-level experiments. The models share tasks, nonces, the simulator and the harness. Use the stratified permutation as primary and drop the e-product, or average the e-values instead.
    - Holm is applied across families but not across the three statistics (net, harm, churn). With churn promoted to headline after it was seen, the multiplicity is at least ×3.
    - The pooled equivalence assumes a common shift across models, but q14 has point estimates of −1.4 to −7.4 everywhere.
    - "Conformal" is a rebrand of a two-sample permutation test with n = 3–7. ARR stats reviewers will say so. Call it an exact run-level permutation test and mention the conformal reading once.
- **[W-D] MAJOR: C4 is refuted for damage by the authors' own analysis, and C3's predictor is largely dose ordering.**
  - A2-11 gives residual SD of Δ = 0.0391 vs outcome SD 0.0389. Leave-one-model-out coverage is 0.58–0.63 at nominal 0.80/0.90, with only 2 models.
  - The ρ = 0.989 between open-loop flip rate and closed-loop hazard is over cells that span 3 decades of k. Spearman with k alone is 0.97 (A2-9). The "prediction" may be mostly "both are monotone in dose".
  - Needed:
    - a within-band (matched-k) or partial correlation;
    - the X1 formats at their own k-equivalent, which is the real test of structure vs size.
  - C4 as a contribution should be cut. Keep a 5-line "recommended protocol" in the discussion: a divergence screen, then a closed-loop damage test against a null.
- **[W-E] MAJOR: scope creep 6 days before freeze.**
  - v3 adds X1 (two formats × 5 models), l8, telecom, LiveCodeBench, and (planned) Mistral, Wanda and T = 0.7.
  - The core three models are not frozen: redos are in flight, q14 has no eager run, q30a3/q32 main cells are partial, and q32 has 54 tasks in todo.
  - Every new axis so far brought its own harness failure: W7 (AWQ needs FP16 activations; kernels are not the deployed ones), W9 (Llama template crash), and a smoke-only telecom and code loop.
  - Specific problems with the new axes:
    - **LiveCodeBench** is not a closed loop with a simulator. It changes the object of study, and it appears in no v3 contribution row.
    - **Telecom** needs harness work (`STRATEGY_v2.md` L400: "no cloq adapter").
    - **l8** is low-capability (retail tool_err 0.67; W9). Its tasks will be mostly degenerate, so it adds little power; q4 already has only 32% non-degenerate tasks (A2-8).
    - **Mistral** is not queued.
  - Compute is not the constraint. Analysis, integrity checking and writing are, and each new axis dilutes them.
- **[W-F] MAJOR: X1 is "real weights, non-deployed kernels", and AWQ carries a dtype confound.**
  - Under `VLLM_BATCH_INVARIANT=1`, FP8 runs Humming (not Marlin) and AWQ runs `awq_dequantize` + matmul with FP16 activations (W7).
  - "Real deployed formats" is therefore half true. AWQ differs from BF16 in both weights *and* activation dtype, so it cannot cleanly test "structure vs size" (C3) against BF16-activation noise.
  - State this in the title of the X1 table, and treat AWQ-X1 as confounded unless a BF16-weights + FP16-activation null cell is added (1 run per model).
- **[W-G] MINOR: the free-zone grouping is favourable.** The pooled free zone {k = 0.03, k = 0.1, RTN-W8} passes ±5 pp, while RTN-W8 alone fails ±5 pp pooled ([−5.5, +0.25]). Pre-declare the grouping or report the members separately.
- **[W-H] MINOR: the Flat Score comparison is partly a straw man.** Flat Score used 4 reference trials per task; the comparison used 1 (A2-4 notes it). Rerun "Flat-Score-style" with the mean of the canonical + eager runs as the reference, to show that the gap is not only the 1-trial reference.
- **[W-I] MINOR: the clarity debt is growing.** The v3 statistics stack (TOST, permutation, randomized vs conservative p, e-values, jackknife+, LOMO, null sets A/B/C/D/S) is not 8-page material. The LaTeX is still v2. Pick one primary test plus one sensitivity analysis; everything else goes to the appendix.

## Questions for authors

- **[Q1]** What is the churn p-value for a null-scale *fixed* checkpoint under fresh nonces? Does RTN-W8 (Holm 0.22, no churn) serve as this control, and why does W8 not churn while k = 0.3 does?
- **[Q2]** Under null S on q8 (n3–n5), what are the churn p-values for AWQ, GPTQ-W3/W4 and RTN-W4?
- **[Q3]** Which criterion is operational: rate ε-equivalence or exchangeability? If rate, what is the Definition for?
- **[Q4]** After the dedup, do the q4/q8 floor hazards and ρ change beyond the third decimal? Are A2-3 item 5 predictions (0.120/0.151) re-derived?
- **[Q5]** What is our failure-set rank correlation across precisions, measured the way Flat Score does (their ρ ≥ 0.94)? Does churn contradict it or not?
- **[Q6]** Is the E8 det pair byte-identical (prediction a), or only metric-identical?
- **[Q7]** Why is LiveCodeBench in the plan when no contribution row uses it?

## Verdict

The measurement core is stronger than in v1 and is close to publishable as a careful evaluation-methodology paper:
- the floor below the grid;
- the cross-model prediction;
- serving numerics as a null;
- the protocol comparison;
- the honest power statements.

The v3 storyline, however, spends its risk budget in the wrong places:
- a headline (churn) that lacks its control;
- a contribution (C4) that its own data refute;
- four new axes, while the core snapshot is stale after two integrity incidents.

**Revision priority:**
1. integrity recompute (W-A);
2. churn controls, or demote churn (W-B);
3. the E8 verdict;
4. cutting C4 and scope (W-D, W-E);
5. statistics cleanup (W-C).

Scores (ACL 1–5):

| | Now | Projected (the must-do list below is done, E8 lands either way, scope is cut) | Projected (v3 as planned, all axes) |
|---|---|---|---|
| Soundness | 2.5 | 3.5 | 2.5–3 |
| Novelty | 3 | 3.5 (4 if E8 shows that the fp32 head removes the floor) | 3 |
| Clarity | 2 | 3.5 | 2.5 |
| Overall | 2.5 | 3.5 | 2.5–3 |
| Confidence | 4 | 4 | 4 |

The confidence is 4, not 5, for two reasons. I re-read the JSON keys only for the null draws and the snapshot times, and I did not re-run any script.

## Recommended framing

**Title:** *Every Checkpoint Is a Re-Roll: Judging Compressed LLM Agents Against Their Own Perturbation Null*. Keep "re-roll" only if churn is controlled. If churn turns out to be a fixed-checkpoint effect, the title becomes more true, not less.

Three contributions:
1. **The floor (C1).** The per-decision divergence hazard is flat from a 1-ulp perturbation up to k = 0.03, is carried by bf16 logit-grid near-ties, is predicted across models from margin histograms, and is either removed or not by an fp32 head (E8).
   - Include serving numerics as a null (±8 pp; about 1/4 of outcomes) and the determinism recipe (Inductor autotune).
2. **Null-referenced evaluation (C2, trimmed).** An exact run-level test with ε-inversion and a stated power/MDE. It changes verdicts relative to reference-only protocols: 11 vs 2 of 40 equivalent, and the canonical run sits up to +6 pp off-centre.
3. **Divergence ≠ damage (C3).** Open-loop flip rate screens for divergence. Damage appears only at W3 / k ≥ 2 and is not predictable open-loop. Hence a checklist: screen, then run a closed-loop damage test against the null.

Cut or demote:
- C4 as a contribution (keep the checklist);
- the e-value product, LOMO/jackknife+ coverage claims, and the "conformal" branding (one sentence);
- LiveCodeBench, telecom (unless the smoke is clean and there are ≥ 50 tasks by 10-01), Mistral, Wanda, T = 0.7;
- the 4B deep dive (to the appendix);
- churn as the headline: it becomes a diagnostic paragraph until Q1/Q2 are answered.

## Revision plan (ranked, cheapest first; everything before 10-05)

1. **(0 GPU-h, today) Regenerate X1 and l8 tasks with fresh nonces disjoint from null n1–n5** (E13). 21 X1 and 48 l8 tasks are in todo with n1/n2. Fixing this now costs nothing; fixing it later costs a rerun.
2. **(0 GPU-h) Integrity gate.** Write a script that asserts, for every run in the analysis set:
   - 0 infra errors;
   - dedup applied;
   - 85/85 tasks;
   - canary pass;
   - one frozen snapshot id.

   Then re-run `analysis/insights/iter_2/run_all.sh` after the redos, and diff every number in `iter_2_prep.md` and `iter_2_conformal.md`. Put the gate's output in an appendix (W-A).
3. **(0 GPU-h) Churn diagnostics from existing data** (W-B):
   - q8 null-S churn for the quantized families (Q2);
   - excess churn over the permutation median;
   - null-vs-null leave-two-out churn;
   - the RTN-W8 negative control;
   - a Flat-Score-style failure-set ρ (Q5).

   Also add Holm across statistics.
4. **(0 GPU-h) Statistics cleanup** (W-C):
   - primary = stratified permutation plus ε-inversion, reported under both A and S;
   - drop or average the e-values;
   - write the null-admission rule as a pre-declared test (null draws vs each other, including canonical vs nonce);
   - state the loss of exactness under a heterogeneous null.
5. **(0 GPU-h) Matched-dose check for C3.** Partial Spearman(flip rate, hazard | k), or a within-band correlation. Reword ρ = 0.99 accordingly (W-D).
6. **(about 1.6 GPU-h, running) Finish E8** and check byte identity (Q6). Write both outcomes of C1 now.
7. **(about 2.4 GPU-h) E12 nonce nulls n6–n8** (the null_extra tasks are running), **plus a fixed-checkpoint churn control.** Run k = 0.03 s1 and RTN-W8 under 2 fresh nonces on q4/q8, about 1.5 GPU-h (Q1). This single experiment decides whether churn stays in the paper.
8. **(about 2 GPU-h) q14 eager run plus completion of n3–n5**, to settle the q14 at-risk free zone (W4).
9. **(about 30 GPU-h, already queued) X1 FP8 on all models;** keep AWQ but label it confounded. Add one BF16 + `--dtype float16` null cell per AWQ model if cheap (W-F).
10. **(queued) q30a3/q32 core slice** (bf16, eager, nulls, k ∈ {0.001, 0.03, 0.3, 1, 3}, RTN W8/W4/W3, E3) for the pre-registered floor prediction. Deprioritise the remaining q32 cells.
11. **(queued, lowest) l8 core slice only:** bf16, nulls, k ∈ {0.03, 0.3, 1, 3}, GPTQ W4/W3, E3. Report non-degeneracy. Scope the paper as "Qwen3 + one Llama control".
12. **(writing, 10-05 → 10-12)** Rewrite the LaTeX to v3 in 8 pages: 3 contributions, one statistics box, an integrity appendix, and a Limitations section (greedy only, τ² only, batch-invariant kernels, simulator in the loop).

**Drop:** LiveCodeBench, telecom (unless the gate above passes by 10-01), Mistral, Wanda (X4), T = 0.7 (X5), C4 as a contribution, the cross-model e-products and the LOMO coverage claims.

---

## Part 2: Inline annotations

> "C4 | **Protocol.** Open-loop probe → conformal interval for closed-loop risk → run closed loop only when the interval straddles the tolerance." (`PLAN_iter3.md` §1)

**[W-D] MAJOR:** `iter_2_conformal.md` §2 shows that the residual SD of Δ equals the outcome SD, and LOMO under-covers (0.58–0.63). The interval cannot straddle a ±5 pp tolerance informatively. Cut C4 as a contribution.

> "The new finding is task-profile churn. Quantized families that are rate-equivalent still change *which* tasks succeed ... The churn statistic is the one to headline." (`iter_2_conformal.md` TL;DR)

**[W-B] MAJOR:** There is no fixed-checkpoint null control. Gaussian k = 0.3 also churns (Holm 0.033). Quantized cells share nonces with 2/4 (q4) and 2/3 (q14) null draws. The observed excess over the null median is only about 0.05. Promoting churn to headline *after* seeing it also inflates multiplicity. Demote it to a diagnostic until Q1/Q2 are answered.

> "Because the run, not the task, is the exchangeable unit, the test is exact under H0 without assuming independence across tasks." (`iter_2_conformal.md` §4)

**[W-C] MAJOR:** The test is exact only if the null draws are exchangeable among themselves. Canonical and nonce strata differ (q4 +a few pp; q8 canonical +6.3; q14 +4.0). Add "given an exchangeable null family" and report the S-stratum results next to these.

> "Across models, e-values are **multiplied**; this assumes independent model-level experiments." (`iter_2_conformal.md` §1.1)

**[W-C]:** The models share tasks, nonces, the simulator and the harness, so they are not independent. Average the e-values or drop them. The headline "e-value 21.7" for k = 1 should not appear in the abstract.

> "Pooling the three models by stratified permutation, AWQ-W4, GPTQ-W3/W4 and Gaussian k ≤ 0.3 are ±5 pp-equivalent" (`iter_2_conformal.md` §4, results)

**[W1 partly] / [W-B]:** The same paragraph then says these families fail exchangeability through churn. Under the Definition in the framework paragraph, they are not perturbation-equivalent. State which criterion governs (Q3). Also add "under the mixed null A; not under S".

> "Spearman(open-loop flip, closed-loop hazard) = 0.989 over 31 cells." (`iter_2_conformal.md` §2)

**[W-D]:** The cells span k = 0.001–3, and flip rate vs k alone is 0.97 (`iter_2_prep.md` A2-9). Report a partial or matched-dose correlation. This number is also pre-dedup (W-A).

> "The weights are the real deployed ones; the GEMM kernels are not." (`RESEARCH_LOG.md` W7)

**[W-F] MAJOR:** Good disclosure, but `PLAN_iter3.md` X1 still sells "real deployed formats" against the attack "fake-quant is not what is deployed". AWQ also switches activations to FP16. Title the table "deployed checkpoints, batch-invariant kernels" and flag AWQ as confounded.

> "Consequence: iter_2 analyses (p0x, c01, c02) must be re-run after the redos finish." (`RESEARCH_LOG.md` W8)

**[W-A] FATAL until done:** The c01 snapshot is 05:45Z and the dedup landed at 06:45Z. Every hazard number in C1/C3 is pre-dedup. This must be a gated step with a diff, not a note.

> "q14 | 3 | 3.87 pp" (`iter_2_conformal.md` §0 null table)

**[W4 partly]:** A q14 null of {bf16, n1, n2} has no eager run, and two of its three draws are the nonce-mates of every q14 quantized cell. No q14 equivalence or churn statement is interpretable yet.

> "The pooled free zone (gauss0.03 + gauss0.1 + rtn_w8) ... [−3.0, +1.0] ... yes / yes" (`iter_2_conformal.md` §1.4)

**[W-G] MINOR:** RTN-W8 alone fails ±5 pp pooled ([−5.5, +0.25]). Declare the grouping in advance or report the members separately.

> "Flat-Score-style declares equivalence 2 times; the null-referenced ±7.5 TOST declares it 11 times." (`iter_2_prep.md` A2-4)

**[W-H] MINOR:** The Flat-Score reference had 4 trials per task and ours has 1. Add a variant that uses a 2-draw reference (canonical + eager) so the gap is not only due to reference size.

> "X2 | **Second family:** Mistral-Small-3.2-24B ... optionally GLM-4-9B-0414" (`PLAN_iter3.md` §2)

**[W-E]:** Llama-3.1-8B replaced this in practice (W9), and no m24 task is queued. Update the plan. One second family is enough, scoped as a control with floor effects (retail tool_err 0.67).

> "Not doing: a no-simulator benchmark (BFCL multi-turn / AppWorld). The integration risk is too high for 10-05" (`PLAN_iter3.md` §2)

**[W-E]:** The same reasoning applies to the LiveCodeBench code loop now in the queue (`code_smoke2_q{4,8}`). It is also a no-simulator loop that no contribution uses. Drop it for this submission.

> "Exact bf16 logit ties carry about 40–50% of the floor, not all of it." (`iter_2_prep.md` TL;DR)

**[W2 partly]:** Correct and honest. The C1 wording in `PLAN_iter3.md` ("floor set by near-ties on the bf16 logit grid") must wait for E8 prediction (c). Write both versions now.

---

## Sources

Local artifacts inspected for this review:
- `/data/ziyangs/cloq/analysis/insights/iter_2/out/c01_conformal_equivalence.json` (`snapshot.utc`, `nullsets.A.models.*.null_draws`)
- `/data/ziyangs/cloq/scripts/a6000/make_tasks.py` (L18 `NONCES`, L44, L53)
- `/data/ziyangs/cloq_work/queue/{todo,running,done,failed}/` (counts; `done/a6k2_det_q4_fp32h_{a,b}.json` results; todo X1 nonces)
- `/data/ziyangs/cloq/docs/insights/{PLAN_iter3,iter_2_prep,iter_2_conformal}.md`, `/data/ziyangs/cloq/docs/RESEARCH_LOG.md`, `/data/ziyangs/cloq/docs/STRATEGY_v2.md` L400

External (as cited in review v1):
- https://arxiv.org/abs/2609.26621
- https://arxiv.org/abs/2607.27275
- https://arxiv.org/abs/2608.08239
- https://arxiv.org/abs/2609.04748
