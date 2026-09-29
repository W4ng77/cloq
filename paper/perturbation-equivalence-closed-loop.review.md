**TL;DR**
- Scores now: Soundness 2.5, Novelty 3, Clarity 2.5, Overall 2.5 out of 5 (confidence 4/5). If the pending results come out as predicted: 3.5 / 3.5 / 3.5 / 3.5. That rise also needs the rewrite described below; the results alone will not get there.
- The strongest parts are the serving-numerics null (I4a), the determinism incident and the per-decision hazard table. The weakest part is that "equivalence" and "success stays at null level" are concluded from non-rejection, with intervals up to ±8 pp. Novelty is exposed to Du et al., Patodiya, Flat Score and Replay Gap.
- The cheapest high-value fixes cost nothing: a declared-margin TOST, a clean-only stratified Δ, an exact-tie analysis of the floor, and reconciling the draft with Replay Gap's zero control-fork outcome flips. Then run about 5 GPU-h of sub-grid and FP32-logit cells, and cut the draft to fit 8 pages.

# Review: "Perturbation Equivalence in Closed-Loop Agents: When Is a Compressed Agent Actually Worse?" (draft of 2026-09-28)

Role: COLING 2026 reviewer plus meta-reviewer. Inputs:
- `paper/perturbation-equivalence-closed-loop.md` (line numbers below refer to this file)
- `.provenance.md`, `.verification.md`
- `docs/insights/iter_1_verdicts.md`, `docs/insights/LEDGER.md`
- spot checks of `analysis/insights/iter_1/out/s03_margin_predictions.json` and `docs/insights/EXPERIMENTS.md` (for cost basis)
- the arXiv abstracts of [2], [6], [19] and [25]

[PENDING] blocks are not penalised. §6 judges each one by outcome.

---

## 0. Scores (ACL-style, 1–5)

| Dimension | Now | Projected: pending results as predicted **and** the rewrite in §5 | Projected: pending results as predicted, no rewrite |
|---|---|---|---|
| Soundness | 2.5 | 3.5 | 3 |
| Novelty / excitement | 3 | 3.5 | 3 |
| Clarity | 2.5 | 3.5 | 2.5 |
| Overall | 2.5 | 3.5 | 3 |
| Reviewer confidence | 4 | 4 | 4 |

Why these scores:
- **Soundness now.** The P1 table on clean q4 and the D≡0 determinism pairs are solid.
- The damage threshold and the matched-D claim, however, rest on flavour-mixed legacy draws, partial cells and one model.
- The central claims ("equivalent", "at null level") are inferred from confidence intervals that include zero, not from an equivalence test.
- **Novelty.** The per-step mechanism, cascades, outcome churn without an aggregate shift, and rerun or control nulls all exist in [2], [6], [19] and [25]. The new part is the synthesis plus three measured facts:
  - a per-decision hazard floor at the bf16 grid;
  - one perturbation axis that puts compiler numerics, nonces and W8 together;
  - the Bernoulli width of a reference-derived null.
- **Clarity.** The prose is careful, but it is written in project dialect: legacy/clean/a6k2, "flavour", cells, draws, "null majority", P1a–P4e. It is also about 2× over the 8-page long-paper budget.

---

## 1. Summary

The paper argues that under greedy decoding a closed-loop τ²-bench agent is re-rolled by any perturbation that moves logits by at least one bf16 grid step. The argument runs as follows:
- Text turns contain near-ties, so any such perturbation flips a token.
- A flip changes the context of every later turn, including the simulator's replies.
- Each task outcome is therefore a Bernoulli draw, and a single BF16 run is one sample from that distribution.

The authors propose *perturbation equivalence*: a compressed agent should be judged by the exchangeability of its task outcomes with a null built from the reference model's own sub-threshold perturbations (nonces, Gaussian noise at k = 0.03, eager vs compiled kernels).

The evidence is:
1. **Serving numerics.** Serving numerics alone move the canonical score by 6–8 pp (21/85 and 21/79 outcomes flip).
2. **Hazard table (clean q4).** It shows a per-decision hazard floor of about 0.17–0.23 at the grid step, rising with k.
3. **Damage (q4, pooled legacy + clean).** Success is not distinguishable from the null through RTN-W4 and k = 1, and falls at W3 and k = 3.
4. **Matched D on q8.** RTN-W4 underperforms Gaussian noise at matched closed-loop D, which puts D-sufficiency at risk.
5. **4B deep dive (RTX 4080).** In a separate study, 18 GPTQ checkpoints are indistinguishable, and NLL does not track success.
6. **Determinism incident.** An Inductor autotune choice re-rolled about 95% of trajectories; deterministic compilation plus a canary fixed it.

## 2. Strengths

- **[S1] The serving-numerics null is clean and well labelled.** Same weights and prompt, and the score moves −8.2 pp and +6.4 pp. The draft correctly relabels this as an "agent + simulator" null (L241). It adds an agent-only arm: eager on clean q4 flips 11/69 outcomes. This is the most citable result in the paper.
- **[S2] The D≡0 control is done properly.** Cross-node byte identity holds at 257/257 and 303/303 (L182). It turns "nondeterminism" into a measured perturbation with a zero point, which most prior agent-noise work lacks.
- **[S3] The per-decision hazard replaces the saturated KM P(≤12)** (Table 3a). It reflects an honest correction from the verifier pass: the verdicts' I1 note that "cannot rank" was wrong.
- **[S4] Falsification lines were declared in advance** (L184, L211, L237), and the fallback wordings are already written.
- **[S5] The provenance is unusually strong.** Every number maps to a JSON field, and the verification log re-derived the literature claims and fixed six of them.
- **[S6] The autotune incident (L277) is a practical finding.** It will matter to anyone running vLLM with torch.compile for agent evaluation.

## 3. Weaknesses, ranked (top 5 = the most serious)

### [W1] MAJOR (near-fatal for the title claim): "equivalence" and "stays at null level" are inferred from non-rejection

- **Where:** the abstract (L13), "success stays at null level through Gaussian weight noise at the RTN-W4 error scale"; L203, "database match stays at null level through k = 1 and RTN-W4"; L253, "not distinguishable from re-rolling"; the Definition (L94) and statistic 1 (L102).
- **Problem:** the intervals are too wide to support equivalence at any margin a practitioner would accept.
  - RTN-W4 is −2.0 [−7.6, +3.9], k = 1 is −2.3 [−8.7, +3.8], and clean q4 free zone is +1.9 [−2.6, +6.4].
  - A TOST at ±5 pp fails for every one of these, including the free zone itself.
  - At Flat Score's ±7.5 pp, RTN-W4 (95% CI) and k = 1 still fail; RTN-W4 passes only with a 90% CI.
- **MDE mismatch.** The 3.4 pp MDE quoted at L102 and L299 is for a *pooled five-model* free-zone test. The per-cell MDE with 85 tasks and 2–4 draws is about 8–10 pp, and the draft never says so.
- **Definition and statistic disagree.** The Definition requires exchangeability of columns, a distributional property. The only statistic actually reported, Δ, tests a mean. A cell could have Δ = 0 and still fail exchangeability (Flat Score shows exactly this kind of failure-channel shift). The φ test that would link the two (P4b, L104) has not been run.
- **Fix (0 GPU-h; about 1 day):**
  1. Declare an equivalence margin before looking at the clean cells. Use either a fixed value (±5 pp and ±7.5 pp to match [6]) or a null-scaled one (±2 × null-draw SD).
  2. Report TOST for every family with three verdicts: *equivalent*, *damaged*, *inconclusive*.
  3. Replace "stays at null level" everywhere with "not distinguishable from the null (95% CI …); equivalence at ±X pp is / is not established".
  4. Add a per-cell power line to the Limitations.
  5. Either demote the Definition to motivation and make Δ + TOST the operational criterion, or run P4b and report cases where the two disagree.

### [W2] MAJOR: the "floor" is under-identified, and may be a bf16 LM-head tie artifact rather than a general property

- **Where:** the abstract, "any perturbation that moves logits by at least the bf16 log-probability resolution meets a per-decision divergence floor"; L86; L178; L182, "Divergence is thus bimodal in D".
- **Problem 1: no perturbation below the grid step was tested.**
  - The smallest non-zero perturbation is already at the grid step (median closed-loop |d| = 0.125 is the smallest non-zero value the grid can record).
  - "Every perturbation whose median shift equals one grid step reaches the floor" is therefore close to true by construction.
  - "Bimodal in D" rests on two points: D ≡ 0, and everything at or above one grid step.
- **Problem 2: the "floor" is not flat.** Hazards go 0.17 → 0.18–0.23 → 0.21–0.23 → 0.25–0.27 (nonce) → 0.28–0.29 (k = 0.1). That looks more like a slowly rising curve with a large intercept than a floor.
  - The nonce null member sits *above* the claimed floor band, which the text passes over.
  - L182 says "saturated as soon as they reach the grid step", but the per-decision hazard is not saturated (0.17 vs 0.99). Only KM P(≤12) is.
- **Problem 3: the mechanism may be exact ties in bf16 logits.**
  - `s03_margin_predictions.json` shows that q4 text decisions have a median *minimum margin of exactly 0.0* (`dec_min_margin_median`), and 58% of them have a min margin below 0.25.
  - In other words, more than half of text decisions contain an **exact tie on the bf16 logit grid**, which argmax tie-breaking resolves.
  - The grid step is also not a fixed "log-probability resolution". 0.125 is the bf16 ulp for |logit| in [16, 32), so it depends on logit magnitude.
  - If the logits were computed in fp32, as with Du et al.'s own FP32 LM-head recompute [2], exact ties would largely disappear, and the floor could drop substantially.
  - That would turn the paper's "universal floor" into a property of bf16 logit serving. This is still important, but it is a different claim and a narrower one.
- **Fix:**
  1. **(0 GPU-h)** Split first divergences by whether the flipped token had reference margin exactly 0, 0.125, or ≥ 0.25.
  2. **(0 GPU-h)** Predict the floor as (fraction of decisions containing an exact tie) × P(flip | exact tie). Compare the prediction across q4 and q8. If it matches, this becomes a *quantitative* P3-style result, which is much stronger than the current verbal one.
  3. **(about 2.5 GPU-h)** Add Gaussian k ∈ {0.001, 0.003, 0.01} × 2 seeds on q4, at about 0.3–0.45 GPU-h per cell (EXPERIMENTS.md cost basis). This shows whether the hazard stays at about 0.17 below one ulp or falls toward 0.
  4. **(about 1–2 GPU-h)** Run an FP32-logits variant (lm_head in fp32) on q4 for bf16 and eager.
  5. Rewrite "bimodal" as "none at D ≡ 0; ≥ 0.17 per decision at the smallest measurable D".

### [W3] MAJOR: legacy + clean pooling is justified circularly, and the null family is not homogeneous

- **Where:** L152, "we treat the flavour as one more exchangeable perturbation, which is justified by P1"; L188 and Table 4; L205 (k = 0.03 at +5.1 pp); L92 (the null family includes k = 0.03).
- **Problem 1: circular pooling.** P1 is the claim under test, so it cannot also license pooling the data used to test it and P2.
  - The legacy → clean re-serve also changed the *simulator* (11/20 first messages differ).
  - The two passes have canonical scores 8 pp apart (0.412 vs 0.329).
  - The families contain different mixes of passes: k = 0.03 is 5/7 clean, while the W3 and k = 3 damage estimates are mostly legacy.
  - So Δ against a 10-draw mixed null partly reflects pass composition. That alone could produce the +5.1 [+1.4, +8.9] anomaly for k = 0.03.
- **Problem 2: the null family fails its own exchangeability test.** A declared null member (k = 0.03) is significantly *above* the pooled null, and nonces have a higher hazard than eager (0.25–0.27 vs 0.17).
- **Problem 3: the checklist and results disagree on null size.** The checklist (L287) says "five members is what we use", but Table 4 uses 10 draws.
- **Fix (0 GPU-h):**
  1. Compute Δ *within pass* (legacy family vs legacy null, clean vs clean) and combine by inverse variance or by a stratified task-cluster bootstrap. Report clean-only first and pooled as secondary.
  2. Treat "is k = 0.03 a valid null member?" as a result. Report the leave-one-family-out null and show how the verdicts in Table 4 change.
  3. If the within-pass analysis removes the +5.1 pp, say so. If it does not, the null definition needs a rule for excluding members.

### [W4] MAJOR: the damage threshold and free zone rest on one model, partial legacy cells and a coarse grid, and q8 contradicts part of the story

- **Where:** Table 4 (W3 "4, partial", k = 3 "4, partial" with 2/9 wins/losses); L203, "the zone ... spans about 1.5 decades of k"; L205; L237.
- **Problem:**
  - Clean W3 alone gives −8.5 and −9.3 pp with CIs that include 0.
  - The damage threshold is located between only k = 1 and k = 3.
  - On q8, W3 shows no significant damage, while RTN-W4 *does* (−10.5 [−17.3, −4.0]).
  - The clean q8 free-zone point estimate (−3.5 pp) is already past the −3.4 falsification value. Only the CI keeps the rule from firing.
  - The abstract and conclusion nonetheless generalise "falls only near 3-bit" as the headline.
- **Fix:**
  1. Finish the clean damage cells for q4 and q8 (in the queue).
  2. Add q4 k = 2 × 2 seeds (about 0.8 GPU-h) to locate the threshold.
  3. Add E6-style extra draws at q4 RTN-W4 and k = 1 (2 more each, about 1.6 GPU-h), which narrows the CIs that decide W1.
  4. Scope the abstract to "on Qwen3-4B" (it already does once, but the conclusion at L312 and the title question are general).
  5. Report the q8 RTN-W4 deficit in the abstract if it survives clean data. It is currently the only positive "compressed agent is worse" finding for a practically relevant format.

### [W5] MAJOR: novelty over [2], [6], [19] and [25] is thinner than the contribution list implies, and one prior result is in tension with the paper and is not discussed

- **Where:** contributions 1–2 (L27–28); related work (L35–41); Table 2.
- **Problem, by prior work** (details in §4):
  - **Du et al. [2].** Already states the per-step margin rule, notes that "a single token flip often cascades into trajectory-level divergence", and proposes FP32 LM-head recompute.
  - **Patodiya [25].** Already shows that 0/800 episodes differ when numerics are pinned, that divergence rises sharply at 4-bit, and that divergence reaches task outcomes "without shifting aggregate accuracy". The last point is the free-zone phenomenon, stated in outcome form.
  - **Flat Score [6].** Already runs TOST equivalence for quantized τ²-bench agents, with 456 episodes per cell against this paper's 85 × 2–4. It also shows that the failure *set* is the same at every precision (rank correlation ≥ 0.94), which is a re-roll/amplification account.
  - **Replay Gap [19].** Already uses same-model control forks as a null. It reports **zero outcome flips across 359 control forks**. That sits in direct tension with this paper's 16–27% outcome flips under numerics-only changes, and the draft does not discuss it.
  - **The paper itself.** It concedes that the composition is elementary (L80). The internal ledger rejected "horizon amplification" as obvious.
- **Fix (rewrite, plus one 0-GPU analysis):**
  1. Re-centre the contributions on what is measured and new:
     - the hazard floor tied to (exact) bf16 ties, and its predictability from tie density;
     - one axis on which a compiler autotune choice, a nonce and W8 are indistinguishable;
     - the Bernoulli width of a reference-derived, task-level null, and the demonstration that the canonical score is one draw;
     - the determinism recipe.
  2. Add a paragraph that reconciles the result with [19]: user simulator in the loop, greedy bf16 ties in free text, and τ²'s binary DB endpoint vs SWE outcomes.
  3. **Empirical payoff analysis (0 GPU-h):** run Flat Score's protocol (per-cell TOST ±7.5 against one reference) and Singh's paired test [18] on your cells. Show where their verdicts differ from yours. Without this, "a new criterion" has no demonstrated consequence beyond the v0 anecdote.

### Other weaknesses (not in the top 5)

- **[W6] MAJOR: the v0 example does not illustrate the failure mode it is cited for.**
  - L27 says it shows how "a reference-only comparison can produce false positives such as the one above". The v0 comparison was *arm vs arm* (FP-Traj vs Static), not compressed vs reference. It illustrates single-draw comparisons, not reference-only ones.
  - The intro also leads with a one-sided p (0.0195). The two-sided p is 0.039 (App. A). Report two-sided p in the main text, or say that one-sided was pre-registered.
- **[W7] MAJOR: the 4B deep dive (§5.4, about 1 page) comes from a different setup and cannot be re-checked from raw runs.**
  - It uses an 8k harness, the 4B model as its own simulator, and a different GPU. Its raw runs are absent.
  - It carries an unresolved NLL-correlation sign conflict (L248).
  - It dilutes the paper and invites "which setup is the paper about?".
  - Move it to an appendix. Keep only "18 checkpoints indistinguishable" plus the churn decomposition (0.044 net vs 0.261 churn) as corroboration.
- **[W8] MINOR: the benchmark setup departs from standard τ²-bench and is under-justified.** Four departures:
  - an 85-task "frozen dev split" (retail has 114 tasks, airline 50): how was it chosen, and is there a held-out test split?
  - a DB-match endpoint rather than the official reward;
  - a greedy Qwen3-30B-A3B simulator, which is also the q30a3 agent's own model (self-play);
  - thinking disabled for the hybrid models.

  Each changes the null width. Justify each in one sentence, and give the official-reward numbers for at least the BF16 runs.
- **[W9] MINOR: the Bernoulli-SD check (P4a) has little power.**
  - Observed SD comes from 4–6 draws (3–5 df). The 95% sampling range of observed/true SD is roughly [0.3, 1.8], so the [0.5, 2] band almost always passes.
  - The prediction uses p_t plug-in estimates from the same draws, which biases p(1−p) downward by (R−1)/R.
  - The informative quantity is the **fraction of tasks with non-degenerate p_t** and its distribution. Report that. Also call the ratio "consistent with", not "matches".
- **[W10] MINOR: the one-family and greedy-only scope is stated in the Limitations but not in the title or abstract.** "Closed-loop agents" in the title should become "greedy Qwen3 agents on τ²-bench", or at least the abstract should say so.
- **[W11] MINOR: two figures depend on a pending axis that may not work.**
  - Figures 2 and 3 will plot against *open-loop E3 median |d|* (L184, L211).
  - Table 5 shows the open-loop median |d| for RTN-W4 is 1.3e-6, so every cell will collapse near 0 on that axis.
  - Decide now to use the p90/p99, the flip rate in the [0, 0.5) margin bin, or a KL. Otherwise these figures will be unreadable.

## 4. Novelty risk vs the closest prior work

| Prior work | What it already has (from its abstract) | Overlap with this draft | What remains distinct | Risk |
|---|---|---|---|---|
| **Du et al. 2026 [2]** (margin model) | BF16 vs FP16 greedy diverges on 49–100% of prompts; flips are governed by the "top-two logit margin at the LM head"; "a single token flip often cascades into trajectory-level divergence"; FP32 LM-head recompute adds 22–36 pp exact agreement | per-step rule (acknowledged); cascade (not acknowledged; the draft credits Du only with the per-step rule); the LM-head precision lever (not used) | a closed loop with a simulator; per-decision hazard over episodes; a two-tier text/tool margin structure; outcome-level consequences; compressed weights | **High for P1** unless the paper (a) credits Du for cascades and (b) shows the floor survives, or quantitatively changes, under FP32 logits (W2). Otherwise a reviewer who knows [2] will read P1 as "Du in τ²-bench". |
| **Flat Score 2026 [6]** | quantized τ²-bench agents; 456 episodes per cell; TOST ±7.5; failure set same at every precision (ρ ≥ 0.94, 0.18% novel events); strict-budget diagnostic | benchmark; equivalence framing; process channels (L209, L275 explicitly follow it) | a reference-derived *perturbation* null instead of a declared margin; margins measured; D≡0 control; a Gaussian dose axis crossing into damage (W3, k = 3), which Flat Score never reaches | **High for the criterion.** Flat Score has more episodes per cell than this paper, and Table 2's "4 trials per task" vs "2–5 per cell" row makes this paper look stronger than it is. Fix Table 2 to count *episodes per cell*. Show a case where the null-referenced verdict differs from TOST ±7.5 (W5 fix 3). |
| **Replay Gap 2026 [19]** | same-model control forks as a noise floor for SWE agents; FP8-served controls diverge on > 90% of forks, AWQ near-identical; **0 outcome flips in 359 control forks** | "a null from the same model" is the same idea at a different granularity | task-level null for *compressed-model* evaluation; weight-only and numerics members; Bernoulli width | **Medium.** The idea overlaps, but the application differs. The **unaddressed contradiction** (0/359 outcome flips there vs 16–27% here) is the bigger risk: a reviewer will ask it first. |
| Patodiya 2026 [25] (not asked about, but close) | 0/800 divergence with cache off; 36.2% → 75.0% episode divergence from 16 to 4 bit; divergence reaches outcomes "without shifting aggregate accuracy" | D≡0 arm; quantization amplifies divergence; churn without an aggregate shift (≈ free zone) | per-decision hazard floor; dose-response to damage; null definition | **Medium-high for P2's first half.** Cite [25]'s single-turn-bridge result explicitly as prior evidence of churn without an aggregate shift, and claim the *damage threshold* as the addition. |

**Novelty verdict.** The individual phenomena are largely anticipated. The defensible novelty is:
1. the measured unification on one axis (a compiler autotune choice ≈ nonce ≈ k = 0.03 ≈ W8 at the per-decision floor);
2. the quantitative link from tie density to floor height (if W2 fix 2 works);
3. the demonstration, with a D ≡ 0 control, that the canonical BF16 score of a τ²-bench agent is a Bernoulli draw whose width is predictable;
4. the dose axis extending into damage.

Frame the paper as a *measurement and methodology* paper, not a new theory.

## 5. Placeholder outcomes: what breaks the story, and the fallback framing

Placeholders are grouped by the claim they serve. "Break" means the abstract or contribution list would become false.

| Placeholder(s) | Predicted outcome | Plausible adverse outcome | Consequence | Fallback framing |
|---|---|---|---|---|
| Table 1 counts, App. B table (L148, L337); five-model abstract sentence (L13) | all 5 models complete | **Most likely adverse outcome: q14, q30a3 and q32 do not finish by 10-05.** At the 09-29 snapshot they had only calibration and determinism runs; the queue shows 26 running, all q4/q8. | The paper becomes a two-model paper, and all "across models" sections are empty. | Write the q4 + q8 version **now** as the primary draft: "two models, clean, full matrix". Add a minimal cross-size slice (see §7, item 12). Put pending rows in an appendix. Do not submit with [PENDING] in the abstract. |
| Fig. 2, five-model hazard (L184); eager for all models (L281) | a floor at the grid step for all models | (a) A larger model (q32 with thinking off, q14) has KM P(≤12) < 0.7 at a nonce, which falsifies P1a for that model. (b) Floors differ widely across models. | (a) Breaks "any perturbation re-rolls almost every episode" (L23) as a universal claim. | (a) and (b) are both *good* outcomes if the floor tracks tie density (W2 fix 2): "floor height is predicted by the reference model's exact-tie rate". Pre-commit to this framing now. Only (a) without a tie-density explanation is damaging. |
| Clean damage re-test and Fig. 3 (L211); P4e clean (L243); strict-budget/empty audit (L275) | clean W3 and k = 3 significantly below the null; free zone within ±3.4 | (a) Clean W3 and k = 3 are not significant (the current clean draws are −8.5 and −9.3 with CIs that include 0). (b) The clean q8 free zone falls below −3.4 with the CI excluding 0 (the point estimate is already −3.5). (c) The empty-episode audit shows W3 damage partly scored as success. | (a) The damage threshold rests on legacy only, and the "free zone" becomes "no detectable damage anywhere", which is an absence-of-evidence claim. (b) The free zone is **refuted** on q8, and the abstract's q4 sentence is then a single-model claim. | (a) Report the result as a power finding: "with 85 tasks, even 3-bit damage of ~9 pp is not reliably detectable; single-run comparisons are hopeless". This supports contribution 1 even as P2 weakens. (b) Present P2 as model-dependent. Lead with I4a and P1, and move P2 to "tentative, q4". |
| Clean q8 matched-D (L237); E3 all cells (L233); P3a (L235) | the RTN-W4 gap disappears on clean data | The gap persists on clean data. | This breaks the implication that "all perturbations are the same once D is matched". It also *contradicts the abstract's practical reading* ("success stays at null level ... at the RTN-W4 error scale"), because on q8 RTN-W4 is worse. | The pre-written narrowing (GPTQ/AWQ sit on the Gaussian band, RTN does not) is fine. Lead the abstract with it; it is the paper's most actionable compression finding. |
| q14 and q30a3 pre-registered curves (L235) | within ±0.15 | missed | P3 margin predictability fails. | P3 is already demoted to "partly supported"; remove it from the contribution list and keep it in §5.3. Low damage. |
| φ permutation P4b (L104) | null–cell φ ≈ null–null φ for free-zone cells | Free-zone cells (RTN-W4, k = 1) have lower φ, i.e. the Δ test says equivalent but exchangeability fails. | The Definition and statistic 1 give different verdicts, and the criterion becomes ambiguous (W1). | Make Δ + TOST the operational criterion and φ a diagnostic of *distributional* change ("same rate, different tasks"). That would actually be a new finding, echoing [6]. |
| Canonical-prompt test P4c (L243) | no canonical-prompt effect | Weight-only (k = 0.03) and eager nulls sit systematically above the nonce null. | The null depends on its construction; a verdict can change with the choice of null (W3). | Recommend a canonical-prompt null only (weight-only + numerics). Report nonce-null verdicts as a sensitivity analysis. |
| P4a, 20 df (L322) | ratio in [0.5, 2] | outside | Unlikely; the test has little power (W9). | Report the fraction of tasks with non-degenerate p_t instead. |
| Marlin determinism E7 (L279) | byte-identical | not identical | Neither outcome breaks the story; non-identity strengthens it (more null sources). | Already written. |
| Write-flip annotation P2b (L207) | write-flip rate tracks Δ | it does not | The P2 mechanism sentence becomes unsupported. | State damage phenomenologically (the threshold exists) without a mechanism, and keep the recovery asymmetry as descriptive. |

**The single outcome that most threatens the paper:** clean W3 and k = 3 are not significant *and* clean q8 RTN-W4 shows damage. Then the only "compressed is worse" signal is the one that contradicts the q4 free zone.

**Mitigation:** the paper's core (I4a + P1 + determinism + a powered TOST criterion) survives any placeholder outcome. Lead the abstract with that core, not with P2.

## 6. Prioritised work before 2026-10-05 (cheapest first)

Costs: GPU-h from `docs/insights/EXPERIMENTS.md`, with 0.27–0.44 GPU-h per q4 run over 85 tasks and ×1.35 for q8.

| # | Item | Serves | Cost |
|---|---|---|---|
| 1 | Declared-margin TOST (±5, ±7.5, ±2·SD_null) for all families; equivalent / damaged / inconclusive table; per-cell MDE | W1 | 0 GPU-h, ~3 h |
| 2 | Within-pass (clean-only, legacy-only) Δ and stratified pooling; leave-one-family-out null; re-check the k = 0.03 +5.1 | W3, W4 | 0 GPU-h, ~3 h |
| 3 | Exact-tie analysis: share of text decisions with m = 0 and m = 0.125; first-divergence flips by reference margin bin; predicted floor = tie share × P(flip \| tie) vs observed hazard (q4, q8) | W2 | 0 GPU-h, ~4 h |
| 4 | Apply the Flat Score TOST ±7.5 and Singh-style paired tests vs the canonical run to every cell; list verdict disagreements with the null-referenced criterion | W5 | 0 GPU-h, ~2 h |
| 5 | Replay Gap reconciliation: split outcome flips by whether the simulator's text diverged first; report the agent-only flip rate (the eager 11/69 already exists) | W5 | 0 GPU-h, ~2 h |
| 6 | Hazard split by decision type (text vs tool) so the floor is a text-turn quantity, not a mix-dependent one | W2, clarity | 0 GPU-h, ~1 h |
| 7 | V1-A4: write/read/text annotation of first divergences plus an "undone within episode" flag; Spearman of Δ vs write-flip rate | P2b placeholder | 0 GPU-h, ~4 h |
| 8 | Report the fraction of tasks with non-degenerate p_t, and the SD-ratio CI | W9 | 0 GPU-h, ~1 h |
| 9 | Fix the Figure 2/3 x-axis to an E3 statistic that does not collapse (p90, or flip rate at margin < 0.5) | W11 | 0 GPU-h |
| 10 | **Sub-grid Gaussian cells** q4 k ∈ {0.001, 0.003, 0.01} × 2 seeds | W2 | ≈ 2.5 GPU-h |
| 11 | **FP32-logits variant** (lm_head/logits in fp32) for q4 bf16 + eager | W2, Du novelty | ≈ 1–2 GPU-h (plus engineering; skip if the vLLM change takes more than half a day) |
| 12 | Minimal cross-size slice if the full matrix will not finish: for q14 and q32, run bf16, bf16_eager, null_n1–n3, gauss0.03 s1, gauss0.3 s1, rtn_w4 n1, rtn_w3 n1 | fallback for Fig. 2/3 | q14 ≈ 9 × 0.45 ≈ 4 GPU-h; q32 (TP = 2) ≈ 9 × ~1.5 ≈ 14 GPU-h |
| 13 | q4 k = 2 × 2 seeds; +2 draws each for q4 RTN-W4 and k = 1 (E6) | W4, W1 | ≈ 2.5 GPU-h |
| 14 | Prioritise clean q8 RTN-W4, k = 1, AWQ, GPTQ plus E3 on those cells (V1-E1) | W4, P3 | in queue; E3 ≈ 1–2 GPU-h per cell |
| 15 | Official-reward rescoring of the BF16 and null runs; one sentence on how the 85-task split was chosen | W8 | 0 GPU-h |
| 16 | Cut to 8 pages: move the 4B deep dive, the autotune details, App. B and the Table 1 counts to appendices | clarity | ~1 day |

**Do not start** new model families or sampling-temperature studies before the deadline. Mention them as limitations.

## 7. Questions for authors

- **[Q1]** Are the agent's logits (lm_head output) bf16 in vLLM here? If so, is a median text-decision minimum margin of exactly 0.0 a bf16 tie? What is the floor under FP32 logits?
- **[Q2]** Was prefix caching enabled, and were tasks served concurrently? Patodiya [25] shows that cache state alone re-rolls 36% of episodes. The determinism pairs suggest the stack is safe, but say it explicitly.
- **[Q3]** How were the 85 tasks chosen, and is there a held-out split? Were any design decisions (k grid, null family, the 3.4 pp MDE) made after looking at these tasks?
- **[Q4]** Why do the Replay Gap's 359 control forks show zero outcome flips while your numerics-only change flips 16–27%?
- **[Q5]** Was the one-sided v0 test pre-registered as one-sided?
- **[Q6]** In Table 4, how is "null majority" defined with 10 draws when a task has exactly 5/10 passes?
- **[Q7]** Does the q30a3 agent evaluated against a q30a3 simulator behave differently (self-play)? Is it excluded from any pooled result?

## 8. Verdict (meta-review voice)

The paper has a real, useful core.
- A τ²-bench agent's canonical greedy BF16 score is one Bernoulli draw.
- A compiler kernel choice is as disruptive as a nonce or W8.
- Evaluators need a reference-derived null and deterministic serving.

The paper currently claims more than this core. The two biggest problems are:
- It infers equivalence from wide non-significant CIs (W1).
- It presents a bf16-grid floor as a general law without testing below the grid or under FP32 logits (W2).

The damage threshold and the D-sufficiency question are one-model or legacy-based and may flip (W4). The novelty case must be rebuilt against [2], [6], [19] and [25] (W5).

**Revision priority:** W1 > W3 > W2 > W5 > W4, then the page budget. Everything above the page-budget item is 0–5 GPU-h and fits before 10-05.

**If the pending cells come out as predicted and W1–W3 are fixed,** this is a solid measurement/methodology paper for a COLING audience (score about 3.5). **If they come out adversely,** the fallback framing in §5 still supports a paper about evaluation noise and power in quantized-agent evaluation (about 3).

Confidence: 4/5. I checked the provenance, the verification log, the verdicts and one raw summary JSON. I did not re-run the verify scripts.

---

## 9. Line-level clarity issues (top 10)

1. **L13 (abstract).** "we show that any perturbation that moves logits by at least the bf16 log-probability resolution meets a per-decision divergence floor". This is shown on clean q4, and is "consistent" on q8. Scope it, and define "resolution" (it is the bf16 ulp at typical logit magnitude, not a constant). The abstract is also about 230 words with a placeholder; target about 150.
2. **L27.** "which is why a reference-only comparison can produce false positives such as the one above". The v0 example was arm vs arm, not vs the reference (W6). Say "single-draw comparisons".
3. **L64 / L86 / L184.** Notation drifts among δ, D_π, |d|, "median |d|", k and "shift". Pick one axis symbol per figure. Tell the reader explicitly that k is the dose and median |d| is the measured shift.
4. **L45 vs L135.** Table 2 appears before Table 1. Renumber. Table 2's "Runs per cell" column should count episodes per cell (Flat Score: 456).
5. **L152 (and throughout).** Internal jargon: "legacy", "clean", "a6k2", "flavour", "cells", "draws", "det tasks", "re-rolled". Define these once in a small glossary box, or replace them with plain terms ("pass 1 (non-deterministic compile)" / "pass 2 (deterministic)").
6. **L162 and L324.** The per-decision hazard, the paper's main metric, is defined only in Appendix A. Move the one-line definition into §4 "Measurements", and say that KM P(≤12) saturates by construction because episodes are about 12 decisions long.
7. **L182.** "Divergence is thus bimodal in D: none when shifts are exactly zero, saturated as soon as they reach the grid step". The per-decision hazard is *not* saturated (0.17 vs 0.99). Only the episode-level KM is. Rewrite (W2).
8. **L193 / Table 4.** "wins / losses vs null majority" is undefined, and so is its tie rule for 10 draws (Q6). The "(4, partial)" rows need task counts.
9. **L203.** "database match stays at null level through k = 1 and RTN-W4". Replace with "is not distinguishable from the null (Δ −2.3 [−8.7, +3.8]; −2.0 [−7.6, +3.9]); equivalence at ±X pp is not established" (W1). Also, "the zone ... spans about 1.5 decades of k" gives a threshold that lies somewhere between k = 1 and k = 3, a gap of half a decade. State that resolution.
10. **L287 vs L188.** The checklist says "Five members is what we use", but Table 4 uses a 10-draw pooled null. The null family at L92 includes k = 0.03, which Table 4 shows is *not* exchangeable with the other members (+5.1 [+1.4, +8.9]). Reconcile these, or state the rule for admitting null members.

Runners-up:
- L19: the intro leads with a one-sided p; use two-sided (0.039).
- L209: the heading "Process channels move before success" appears under a table where RTN-W4 process channels do *not* move. Say "at k = 1".
- L241: "moves the canonical score by 6–8 points" should also give p = 0.19 and 0.38 in the same breath, so readers see the shift is within the null by design.
- L318: "false-flag rate of about one in three" has no support in the paper; add the computation or drop it.
- L312 (conclusion): "the questions the pending multi-model results will settle" will need to be rewritten whatever the outcome.

---

## Inline Annotations

> "On Qwen3-4B, success stays at null level through Gaussian weight noise at the RTN-W4 error scale and drops only near 3-bit, a tentative later damage threshold." (L13)

**[W1] MAJOR:** "Stays at null level" is concluded from CIs of about ±6–8 pp that include zero, which is not equivalence. **[W4]:** "drops only near 3-bit" rests mostly on partial legacy draws. The clean W3 draws are not significant.

> "we show that any perturbation that moves logits by at least the bf16 log-probability resolution meets a per-decision divergence floor set by near-ties in free-text turns" (L13)

**[W2] MAJOR:** No perturbation below one grid step was tested, so "floor" and "at least" are not identified. The near-ties are plausibly *exact* bf16 ties (median text min-margin = 0.0 in `s03_margin_predictions.json`), which makes the floor a property of bf16 logits, not of agents.

> "which is why a reference-only comparison can produce false positives such as the one above." (L27)

**[W6] MAJOR:** The "one above" (v0) compared two compressed arms, not a compressed arm against the reference.

> "This per-step account is established: Du et al. (2026) state it for BF16-versus-FP16 decoding [2]" (L23)

**[W5]:** Du et al. also state that a single flip "often cascades into trajectory-level divergence", and they propose FP32 LM-head recompute. Credit the cascade to them and position against the FP32 lever.

> "| Flat Score (2026) [6] | yes (τ²-bench) | FP8, AWQ-INT4 | 4 trials per task |" and "| **This work** | ... | 2–5 per cell, 5 nulls |" (Table 2)

**[W5] MINOR:** These counts are not comparable. Flat Score runs 456 episodes per cell; this work runs 85 × 2–4 per cell. Count episodes.

> "Where we pool the two, we treat the flavour as one more exchangeable perturbation, which is justified by P1 for cells above the floor, and we say so." (L152)

**[W3] MAJOR:** This is circular (P1 is under test), and the two passes also differ in simulator serving and in canonical score (0.412 vs 0.329). Stratify by pass.

> "Every perturbation whose median shift equals one bf16 log-probability grid step (0.125) reaches a floor of about 0.17–0.23 per decision" (L178)

**[W2]:** 0.125 is the smallest non-zero value the closed-loop median can take, so this is near-tautological. The nonce null (0.25–0.27) lies above the stated floor band; say so.

> "Divergence is thus bimodal in D: none when shifts are exactly zero, saturated as soon as they reach the grid step." (L182)

**[W2] / clarity 7:** The per-decision hazard is not saturated at the grid step. This sentence reverts to the KM-based claim that the verifier corrected.

> "| Gaussian k = 0.03 (7) | +5.1 [+1.4, +8.9] | 63 / 18 |" (Table 4)

**[W3] MAJOR:** A declared null member lies significantly above the null. Either the null is heterogeneous, or pass composition biases Δ (5 of the 7 draws are clean). Report within-pass Δ.

> "database match stays at null level through $k = 1$ and RTN-W4 and drops only at $k = 3$ (−16 pp) and RTN-W3 (−14 pp). On q4 the zone between the two thresholds spans about 1.5 decades of $k$." (L203)

**[W1]/[W4]:** Non-rejection is not equivalence. The damage threshold sits anywhere in (1, 3], based on partial cells with 2/9 wins/losses. Add k = 2 and state the resolution.

> "None meets the falsification rule (below −3.4 pp with a CI excluding zero)." (L203)

**[W4]:** Clean q8's point estimate (−3.5 pp) already exceeds the −3.4 threshold. Only its width (2–3 nulls, partial tasks) prevents the rule from firing. Flag this as the highest-risk placeholder.

> "the observed null-draw SD is 2.9 pp on q4 (6 near-complete draws; predicted 3.2) and 3.75 pp on q8 (4 draws; predicted 3.26), ratios of 0.9 and 1.15." (L241)

**[W9] MINOR:** With 3–5 df, almost any ratio falls in [0.5, 2], and plug-in p_t is biased. Report the fraction of tasks with 0 < p_t < 1.

> "changes the q4 canonical score from 0.412 to 0.329 (−8.2 pp; 21/85 tasks = 25% discordant; McNemar p = 0.19)" (L241)

**[W5]/[Q4]:** Reconcile this with Replay Gap [19], which reports 0 outcome flips across 359 same-model control forks.

> "Pooling the available q8 draws, RTN-W4 has Δ = −10.5 pp [−17.3, −4.0]" (L237)

**[W4]:** If this survives clean data, it conflicts with the abstract's "null level through ... the RTN-W4 error scale". The abstract must then be model-scoped, or lead with this result.

> "Figure 2's shift axis is open-loop E3 $|d|$" (L184)

**[W11] MINOR:** Table 5 gives an open-loop median |d| of 1.3e-6 for RTN-W4, so a median axis will collapse. Choose p90/p99 or a margin-conditioned flip rate now.

> "the Spearman correlation between teacher-forced NLL per token and pooled success is −0.124 (mean over decisions) or +0.054 (token-weighted) ... they disagree in sign, so we report both." (L248)

**[W7] MINOR:** Fix the convention before submission (provenance conflict 3), or report this only as |ρ| ≤ 0.13 with the bootstrap CI.

> "exact one-sided McNemar p = 0.0195" (L19)

**[Q5]:** Was one-sided pre-registered? If not, report two-sided (0.039) in the main text.

> "Five members is what we use." (L287)

**Clarity 10:** Table 4's null has 10 draws, and one null family is non-exchangeable. Reconcile.

> "The per-run rule used in an earlier version of our protocol ... had a false-flag rate of about one in three per run" (L318)

**MINOR:** This number is unsupported in the paper. Show the computation or drop it.

---

## Sources (additionally inspected during review)

- Du et al., *Greedy Decoding Is Not Precision-Invariant* — https://arxiv.org/abs/2609.26621 (abstract: cascades, LM-head margin, FP32 LM-head recompute)
- Jang et al., *Flat Score, Amplified Failures* — https://arxiv.org/abs/2607.27275 (abstract: 456 episodes per cell, TOST ±7.5, failure set ρ ≥ 0.94)
- Gonuguntla, *The Replay Gap* — https://arxiv.org/abs/2608.08239 (abstract: 0 outcome flips across 359 control forks; FP8 > 90% divergence)
- Patodiya, *Same Request, Different Answer* — https://arxiv.org/abs/2609.04748 (abstract: 0/800 with cache off; outcomes change without an aggregate shift)
- Local: `/data/ziyangs/cloq/analysis/insights/iter_1/out/s03_margin_predictions.json` (`models.a6000_q4_bf16.margins.text.dec_min_margin_median` = 0.0, `dec_p_min_lt_0.25` = 0.584)
- Local: `/data/ziyangs/cloq/docs/insights/EXPERIMENTS.md` (cost basis: q4 run 0.265–0.444 GPU-h); `/data/ziyangs/cloq/docs/a6000/QUEUE.md` (snapshot 2026-09-28: 26 running, all q4/q8)
