**TL;DR**
- Verdicts: **I1 REVISE** (the rewritten claim holds on q4 clean and q8 legacy + partial clean data), **I2 HYPOTHESIS** (two thresholds seen on q4 when all draws are pooled; the mechanism sentence needs correcting), **I3 HYPOTHESIS, at risk** (q8 RTN-W4 is worse than Gaussian noise at matched D), **I4 HYPOTHESIS** (its sub-claim I4a is HELD: serving numerics alone move the canonical score by ±8 pp). No KILL.
- Every quoted s01/s02/s04/s07 number was reproduced exactly by independent code. Clean a6k2 data confirm the D≡0 arm of P1c: det pairs are 257/257 and 303/303 byte-identical.
- Top request: finish a6k2 q4/q8 with 5 nulls plus the damage cells, then run `verify/v03` and `verify/v04` on them. Also add a clean agent-only numerics null (eager). The legacy→a6k2 "flavour null" also changed the user simulator.

# Verifier verdicts: iteration 1

Owner: cloq-verify (iteration N=1). Inputs: `docs/insights/iter_1_candidates.md` (round 2), `docs/insights/iter_1_discussion.md`,
`docs/insights/SURVEY.md`, `analysis/insights/iter_1/`.

Recompute scripts are in `analysis/insights/iter_1/verify/`. Each is read-only over `runs/`, and re-running it refreshes its output:

| script | output | what |
|---|---|---|
| `v01_legacy_recompute.py [a6000\|a6k2]` | `verify/out/v01_legacy_recompute.json`, `…_a6k2.json` | independent re-implementation of first divergence (KM + per-decision hazard, task-bootstrap CIs), identical-context text/tool flip rates, AWQ-vs-gauss1 matched tasks, outcomes from `tau2_results.json` (checked against `metrics.json`: 0 mismatches) |
| `v02_a6k2_det.py` | `verify/out/v02_a6k2_det.json` | P1c det pairs under the flag; legacy-vs-a6k2 same-node pairs; early a6k2 pairs |
| `v03_outcomes_pooled.py [a6000\|a6k2]` | `verify/out/v03_outcomes_pooled.json`, `…_a6k2.json` | P2a Δ pooled over domains (leave-one-out for null members, task-cluster bootstrap), naive McNemar vs canonical (P4d), terminations audit (E4c) |
| `v04_pooled_draws.py` | `verify/out/v04_pooled_draws.json` | legacy + a6k2 draws of each config family pooled against a pooled null (I4/R1 premise); canonical legacy vs a6k2; null-draw SD vs Bernoulli |

Data snapshot: a6k2 was read live at 2026-09-29T02:31–02:36Z.
- a6k2 status: 51/109 run-domains completed. q4 was nearly complete: every sub-threshold cell had ≥ 63 of 85 tasks. q8 was partial.
- Legacy status: 54/112 run-domains completed.
- a6k2 numbers below are live-snapshot values. Re-run the scripts once the runs finish.
- 4080 numbers were checked only against `analysis/strategy_v2_workflow/mechanism/{a23,a4,churn,a567}.out`. They match: 1466/1530 = 0.958, 0.908/0.051, 0.844 vs 0.292, 0.044 [−0.038, 0.126], 0.008/0.490, 166/954.
- The raw `data-4080` runs are not on disk.

---

## I1: closed-loop divergence is set by tie density. Verdict: **REVISE**

**Recomputed numbers.**
- Every KM value, flip rate and |d| in the candidates' I1 tables matches `v01` exactly.
  evidence: `verify/out/v01_legacy_recompute.json` `A_divergence`, `B_flip_by_kind` vs `out/s0{1,2}_*_{q4,q8}.json`.
- The "72–82 of 77–85 wording/format" count is correct. evidence: `out/s02_trajectory_divergence_q4.json` `first_div_type`.

**Where the statement is wrong.** "Divergence … cannot rank perturbations" holds only for the *episode-level* quantity, KM P(≤ 12). Episodes last about 12 decisions (`runs/a6000_q4_bf16/retail/metrics.json` `mean_decisions` 12.0), so KM ≤ 12 saturates by construction. The **per-decision hazard** does rank δ, with CIs that separate the floor band from the higher-δ bands.

Clean q4 (a6k2) hazard per decision, with 95% CI. evidence: `verify/out/v01_legacy_recompute_a6k2.json` `A_divergence.*.hazard_per_decision`.

| a6k2 q4 configuration | median \|d\| | hazard per decision | KM ≤ 12 |
|---|---|---|---|
| eager BF16 (agent-only numerics flavour) | 0.125 | 0.17 [0.15, 0.20] | 0.96 |
| gauss 0.03 ×5 | 0.125 | 0.18–0.23 | 0.97–1.0 |
| RTN W8 ×2 | 0.125 | 0.21 / 0.23 | 1.0 |
| nonce n1–n3 | 0.25 | 0.25–0.27 | 0.98–1.0 |
| gauss 0.1 ×2 | 0.25 | 0.28 / 0.29 | 1.0 |
| gauss 0.3 ×2 | 0.5 | 0.42 / 0.45 [0.35–0.55] | 1.0 |
| RTN W4 ×2 | 1.75–2.0 | 0.73 / 0.78 | 1.0 |
| gauss 1 ×2 | 2.0–2.1 | 0.77 / 0.99 | 1.0 |
| gauss 3, RTN W3 | ≥ 2.6 | 1.0 | 1.0 |

- The legacy numbers show the same structure.
  - q4: kernel flavour 0.18 [0.14, 0.24]; k = 0.03 0.19–0.20; k = 0.3 0.39–0.42; k = 1 0.78–0.98.
  - q8: k = 0.03 0.12–0.14; nonce 0.21; k = 0.3 0.29–0.34; GPTQ W4 0.41–0.46; AWQ W4 0.51–0.56.
  - evidence: `verify/out/v01_legacy_recompute.json`.
- So there is a **hazard floor** of about 0.17–0.23 (q4) or 0.11–0.14 (q8) per decision. It is reached by every perturbation whose median shift equals the bf16 log-prob grid step (0.125): an eager-vs-compiled change, k = 0.03, and RTN-W8.
- Above the floor the hazard grows only about 2× per decade of k up to k = 0.3. It jumps once tool turns start flipping.

**Rewritten statement (I1, v2).**
> In a greedy closed-loop agent, any perturbation that moves logits by at least the bf16 log-prob resolution (≈ 0.125 nats) incurs a per-decision divergence hazard floor (q4 ≈ 0.2, q8 ≈ 0.11–0.14). The floor is set by near-ties in free-text turns: at δ ≤ 0.1, text turns flip 0.22–0.53 per decision and tool turns 0.02–0.08 (q4, q8). Over an episode of about 12 decisions, this makes episode-level divergence ≥ 0.84 for every such perturbation, from a compiled-vs-eager kernel change to RTN-W8. Episode-level divergence therefore carries no information about perturbation size. The per-decision hazard and the tool-turn flip rate do.

Scope:
- HELD-level on q4 (clean a6k2, 85 tasks, 5 k = 0.03 seeds).
- Consistent on q8 (legacy, plus a6k2 partial at 79 tasks).
- The five-model universal claim is a HYPOTHESIS.

**Prediction status on the clean data so far.**
- **P1a.**
  - q4 passes. KM ≤ 12 is 0.96–1.0 for nonce, k = 0.03 ×5, k = 0.1 ×2 and W8 ×2. KM ≤ 4 rises 0.54–0.69 → 0.78–0.79 from k = 0.03 to k = 0.1, a rise below 0.3.
  - q8 k = 0.03 s1 is 0.84 [0.75, 0.93]. That misses the 0.85 target but not the 0.7 falsification line; legacy q8 was 0.844.
  - Keep q8 as the model to watch. Report the CI, not the point estimate.
  - evidence: `verify/out/v01_legacy_recompute_a6k2.json`.
- **P1b (text/tool ≥ 5 at k ≤ 0.3).**
  - Clean q4 k = 0.3 gives 5.8 / 5.7 and clean q8 gives 6.4 / 11.3, so it passes, but q4 only narrowly.
  - The one legacy violation, q8 gauss0.3_s1 at 3.8, is a flavour-mixed cell.
  - Recommendation: pre-register the ratio with its CI, or restate it as "tool-turn flip ≤ 0.1 whenever k ≤ 0.1". The ratio falls mechanically as text flips saturate at 1.
  - evidence: `verify/out/v01_legacy_recompute{,_a6k2}.json` `B_flip_by_kind.*.text_over_tool`.
- **P1c, D≡0 arm: confirmed.**
  - a6k2_det_q4_a (node005) vs _b (node004): 257/257 identical-context decisions, 0 flips, |d| = 0, 0/20 divergences.
  - q30a3: 303/303. a6k2_q4_bf16 vs a6k2_det_q4_b: 257/257.
  - evidence: `verify/out/v02_a6k2_det.json`; also RESEARCH_LOG W3 "Fix verified".
- **P1c, D≠0 arm.** Clean eager-vs-compiled q4 has median |d| 0.125 and KM ≤ 12 of 0.96 ≥ 0.85, so it passes.
  - evidence: `verify/out/v01_legacy_recompute_a6k2.json` `a6k2_q4_bf16_eager`.

**Confounds.**
1. *Episode length* is the reason KM ≤ 12 saturates. Handled: the claim is restated on the per-decision hazard.
2. *Definition sensitivity.* Format and wording events count as divergence. This is by design, and the claim is about raw re-rolls. Also report behaviour-only divergence as a secondary curve.
3. *Legacy flavour mixing* at small k. Resolved for q4 by the a6k2 cells above.
4. **New: the legacy→a6k2 "flavour null" (E5) is not agent-only.**
   - The a6k2 re-serve also changed the *user simulator*: decision-0 prompts, which differ only in the first user message, differ in 11/20 det tasks (6 retail, 5 airline). The same 11 tasks differ for q4 and for q30a3, so the change is on the simulator side.
   - As a result, only 42 identical-context agent decisions exist in `a6000_det_q4_b` vs `a6k2_det_q4_b`.
   - Use `a6k2_<m>_bf16_eager` (agent-only, same simulator) as the clean numerics null for P1c. Label legacy-vs-a6k2 as an "agent + simulator serving" null.
   - evidence: `verify/out/v02_a6k2_det.json`, pairs "a6000_det_{q4,q30a3}_b vs a6k2_det_*_b", fields `decision0_prompt_mismatch` and `identical_ctx_decisions`; example in `runs/{a6000,a6k2}_det_q4_b/retail/decisions.jsonl`, task 101, decision 0, last user message.

**Novelty.** Survey call (b). Patodiya states saturation in words (https://arxiv.org/abs/2609.04748). Du shows single-prompt divergence (https://arxiv.org/abs/2609.26621).
- What v2 adds:
  - a measured hazard floor tied to the log-prob grid;
  - the two-tier text/tool tie structure (survey I1-Q2, call (a));
  - one δ axis that includes a compiled-vs-eager kernel change.
- Open survey question: V1-Q2 in `SURVEY.md#open-questions-for-survey`.

**Deciding cells.** a6k2 q8, q14, q30a3 and q32: bf16, bf16_eager, null_n1–n5, gauss0.03 ×2 (×5 for q4/q8), gauss0.1 ×2, rtn_w8 ×2. Run `v01 a6k2` on each.

---

## I2: damage has a later threshold (the free zone). Verdict: **HYPOTHESIS** (mechanism sentence to be corrected)

**Recomputed numbers.**
- The tool-turn flip table matches exactly. evidence: `verify/out/v01_legacy_recompute.json` `B_flip_by_kind`.
- **Correction to the pilot:** with 4 airline nulls now available, legacy q4 airline gauss0.1_s1 has Δ −0.15 [−0.26, −0.05]. That is 1 nominal flag among about 20 tests.
  - Pooled over domains it is −5.6 pp [−13.2, +2.1].
  - Always test P2a pooled, and state the multiplicity.
  - evidence: `verify/out/v01_legacy_recompute.json` `D_outcomes.q4/airline`; `verify/out/v03_outcomes_pooled.json`.

**New evidence: two thresholds on q4, all draws pooled.** Legacy and a6k2 draws are treated as exchangeable (R1). Each row is Δdb_match against the pooled null (10 draws: bf16, nonce, eager, both prefixes), with a task-cluster bootstrap.
evidence: `verify/out/v04_pooled_draws.json` `q4.families`.

| q4 family (draws) | Δ pp [95% CI] | wins / losses vs null majority |
|---|---|---|
| gauss 0.03 (7) | +5.1 [+1.4, +8.9] | 63 / 18 |
| gauss 0.1 (4) | −1.5 [−5.1, +2.0] | 27 / 18 |
| RTN W8 (4) | +1.2 [−2.8, +5.4] | 33 / 17 |
| gauss 0.3 (4) | +1.0 [−3.7, +5.7] | 37 / 24 |
| RTN W4 (4) | −2.0 [−7.6, +3.9] | 33 / 24 |
| gauss 1 (4) | −2.3 [−8.7, +3.8] | 41 / 35 |
| **RTN W3 (4, partial)** | **−14.0 [−26.3, −2.4]** | 7 / 22 |
| **gauss 3 (4, partial)** | **−16.1 [−31.8, −0.7]** | 2 / 9 |

- Pooled free zone (k ≤ 0.1 and W8), P2a statistic.
  - Legacy q4: −0.2 pp [−5.0, +4.5]. Legacy q8: −0.7 pp [−6.1, +4.6].
  - Clean a6k2: q4 +1.9 pp [−2.6, +6.4]; q8 −3.5 pp [−9.6, +1.9], with 2–3 nulls and partial tasks.
  - None meets the falsification rule (< −3.4 pp with a CI excluding 0).
  - evidence: `verify/out/v03_outcomes_pooled{,_a6k2}.json` `pooled_free_zone`.
- So on q4, divergence reaches its floor at the smallest δ (a hazard of 0.17 for eager), while db_match stays at null level through k = 1 and RTN-W4 and drops only at k = 3 / W3.
  - This is the two-threshold shape, with a free zone spanning about 1.5 decades of k.
  - The W3/k = 3 estimate comes mostly from legacy draws; the a6k2 W3 draws alone are −8.5 / −9.3 pp, with CIs that include 0, on 39 / 25 tasks. It is **not yet clean**.
- The damage at W3 is partly **process failure**. `max_steps` ends 7/33 and 8/32 of the finished legacy RTN-W3 episodes, against 0 in the nulls. This is consistent with P2e.
  - Premature endings are scored as failures (`cloq/metrics.py::resolved_db_match`), so they cannot inflate the score.
  - The ABC concern (empty responses scored as successes) was **not** audited here and is still open in E4c.
  - evidence: `verify/out/v03_outcomes_pooled.json` `q4.cells.a6000_q4_rtn_w3_n*.terminations`.

**Where the statement is off (mechanism and P2b).** I2 says damage starts "once its logit shift reaches the margins of action decisions", and that the action-turn flip rate "tracks damage". On q4 this is not what happens:
- Tool-turn flips are already 0.19–0.42 (RTN-W4) and 0.23–0.92 (k = 1), yet Δ ≈ −2 pp and not significant.
- Damage appears only where tool flips are about 1.0 (k = 3, W3).
- evidence: `verify/out/v01_legacy_recompute{,_a6k2}.json` `B_flip_by_kind`; `verify/out/v04_pooled_draws.json`.
- Most action flips are therefore **recovered by the loop**. This matches the 4080 recovery data: 0.68 after a read/lookup flip vs 0.21 after a write flip (`analysis/strategy_v2_workflow/mechanism/a567.out` Q7).

Proposed wording (I2, v2):
> Damage requires unrecovered flips of state-changing actions. The free zone extends beyond the onset of action-turn flips. The predictor to test (P2b) is the flip rate of *write* actions, or of flips not undone within the episode, not the overall tool-turn flip rate.

Keep P2b as pre-registered, and add the write-flip predictor next to it.

**Confounds.**
1. *Task-subset bias in the partial damage cells.* The Δ is taken against the null mean on the same tasks, which handles it.
2. *Low base rate (q8 null ≈ 0.30–0.38).* This can mask damage. It is open, and could explain why q8 W3 shows −3.9 pp [−13.9, +6.9] despite tool flips of 0.76–0.88.
3. *Lenient endpoint.* Strict budget ≤ 2 changes Δ by ≤ 1.7 pp (`out/s06_*`). It is handled on the pilot and still needs re-checking on the damage cells.
4. *Multiplicity* in per-cell tests. Handled by the pooled statistic.
5. *Anomaly to watch:* q4 gauss0.03 sits **above** the null (+5.1 pp; 5 of its 7 draws are a6k2). It could be chance among 11 families, or a canonical-prompt effect *against* the nonce. P4c decides it.

**Novelty.** Survey call (a) for the two-threshold dose-response (I2-Q1). The nearest work is point observations (Flat Score https://arxiv.org/abs/2607.27275, Singh https://arxiv.org/abs/2608.15046) and Tice's noise sweep on accuracy (https://arxiv.org/abs/2412.01784). Open question: V1-Q4.

**Deciding cells.**
- Finish a6k2 q4/q8 null_n1–n5, gauss0.03/0.1 ×2, rtn_w8 ×2 (free zone), and gauss1/gauss3 ×2, rtn_w3 ×2, gptq_w3 (damage).
- Then do the same for q14, q30a3 and q32.
- Score with `verify/v03 a6k2` (pooled P2a) and `verify/v04` (families).
- E3 is needed for P2b, plus a write-flip annotation of the s02 events (E4-g, below).

---

## I3: D is a sufficient statistic and transfers across models. Verdict: **HYPOTHESIS** (at risk)

**Recomputed numbers.**
- The q8 placement table matches: GPTQ W4 median |d| 0.75 (p90 2.0–2.25); AWQ 1.5 (3.5); RTN W4 1.5 (4.1–4.25); gauss 1 1.625–1.75 (4.6–4.75). evidence: `verify/out/v01_legacy_recompute.json` `B_flip_by_kind`.
- New clean evidence for the small-k match: on a6k2, q4 and q8 have identical median |d| at k = 0.03 / 0.1 / 0.3 (0.125 / 0.25 / 0.5). The flavour confound is now gone, but the evidence is partial and covers only 2 models.
  - evidence: `verify/out/v01_legacy_recompute_a6k2.json`.
- **The "d = 0 does not line up" hint is weaker than stated.** On matched task subsets, AWQ n1 has KM ≤ 0 of 0.27 [0.14, 0.39] vs gauss1 0.37 [0.25, 0.51] and 0.43 [0.31, 0.57]. The CIs overlap, and the references differ (nonce-matched null vs bf16).
  - evidence: `verify/out/v01_legacy_recompute.json` `C_awq_vs_gauss1`.

**Threat found (outcome level, q8, all draws pooled).**
- RTN W4 (4 draws): Δ **−10.5 pp [−17.3, −4.0]**, wins/losses 7/25.
- gauss 1, at matched median |d| and matched tool flips 0.35–0.41 vs 0.39–0.44: 0.0 [−7.2, +7.7].
- AWQ W4: +1.6 [−7.4, +10.7]. GPTQ W4: −0.5 [−6.7, +5.6].
- evidence: `verify/out/v04_pooled_draws.json` `q8.families`.
- If this holds on clean cells, it is quantization-specific damage at matched D. That is P3b's falsifier (the COLING_PLAN §6 fallback), at least for RTN.
  - Candidate explanation: the p90 differs (4.1–4.25 vs 4.6–4.75, so not in RTN's disfavour), which suggests the sign or *structure* of the shift matters, for example systematic rather than zero-mean error.
  - Open survey question: V1-Q3.
- q4 shows no such effect: RTN W4 −2.0 vs gauss1 −2.3.

**Level check.** "D is sufficient for flip hazards" is almost true by construction within the inherited per-step model (Du Eq. 14). The non-trivial content is the closed-loop part:
- structured quantization error acts like isotropic noise *at matched D* on outcomes and process channels;
- D(k) does not depend on model size.

Rewrite P3's headline around those two points. Do not claim hazard sufficiency, which s01 already shows as a replication.

**Confounds.**
1. Median |d| sits on a 0.125 grid, so "0.5 vs 0.5" is 4 grid steps. Report p50, p90 and the full CDF (E3).
2. Survivorship: D is measured only on unflipped prefix tokens, and n drops to 87–163 decisions at k = 1. E3 fixes this.
3. Legacy q8 flavour mixing. Negligible at D ≥ 1.5.
4. Only 2 models. Scope is stated.

**Novelty.** Survey call (a) for matched-D and iso-shift comparisons (I3-Q1, I3-Q4) and for size-independent D(k) (I3-Q2). Fu (https://arxiv.org/abs/2601.06118) is (b) for the principle.

**Deciding cells.**
- a6k2 q8: rtn_w4_n1/n2 vs gauss1_s1/s2 vs awq_w4_n1/n2 vs gptq_w4 d1/d2, on outcomes and process channels, with D from E3.
- P3a: q14, q30a3 and q32 gauss0.1/0.3/1 vs q4.
- If the q8 RTN-W4 gap survives on clean cells at matched p50 **and** p90, revise I3 to "error-minimising quantizers (GPTQ, AWQ) sit on the Gaussian band; RTN does not".

---

## I4: the reference run is one draw; equivalence means exchangeability. Verdict: **HYPOTHESIS**, with sub-claim **I4a HELD**

**Recomputed numbers.**
- s07 is correct: 4/20 tasks flip (1 vs 3), db_match 0.45 vs 0.55, McNemar p = 0.625. evidence: `out/s07_flavour_outcome.json`.
- Retail: 3 nulls all at 0.345, Bernoulli SD 0.034, correct.
- Null-pair disagreement is 0.14–0.28 per pair; the candidates quote 0.195 as a mean.
- Pooled Bernoulli SD per run is **2.8 pt** (83 tasks, 4 airline nulls), not 2.6.
- evidence: `verify/out/v01_legacy_recompute.json` `D_outcomes`.

**I4a (HELD, scope q4 and q8, greedy, τ² retail + airline).** The canonical BF16 score is one Bernoulli draw per task. Changing serving numerics alone, with the same weights and prompt, moves it by as much as a nonce does:
- **Legacy → a6k2 canonical BF16** (agent + simulator serving numerics):
  - q4 0.412 → 0.329 (−8.2 pp; 21/85 tasks = 25% discordant; McNemar p = 0.19);
  - q8 0.316 → 0.380 (+6.4 pp; 21/79 = 27%; p = 0.38).
  - evidence: `verify/out/v04_pooled_draws.json` `*.canonical_legacy_vs_a6k2`.
- **Agent-only numerics.**
  - Legacy det pair: 4/20 tasks flip (`out/s07_flavour_outcome.json`).
  - a6k2 eager vs compiled: 11/69 = 16% (`verify/out/v03_outcomes_pooled_a6k2.json` `a6k2_q4_bf16_eager.mcnemar_vs_bf16`).
- **Null-draw SD vs Bernoulli prediction.** q4: 2.9 pp over 6 near-complete draws, predicted 3.2. q8: 3.75 pp over 4 draws, predicted 3.26. Ratios are 0.9 and 1.15, inside the P4a band [0.5, 2].
  - evidence: `verify/out/v04_pooled_draws.json` `null_draw_sd`, `bernoulli_sd_run`.
- **No systematic canonical-prompt advantage (R2 upheld).**
  - Canonical draws vs the other nulls: q4 +1.8 pp [−2.9, +6.6]; q8 +1.9 [−3.0, +6.8].
  - The canonical run was top of the q4 legacy null set and bottom-ish of the q4 a6k2 set.
  - evidence: `verify/out/v04_pooled_draws.json` `families["null:bf16"]`.
- Why HELD: the numbers check out; there is no open confound (the flip rate is the same whether the change is simulator-inclusive, agent-only or a nonce); and it is novel as a sharper, quantified version.
  - Prior: tau2 #540 7–11 pt *under sampling* (https://github.com/sierra-research/tau2-bench/issues/540); Bjarnason 2.2–6 pp at T = 0 (https://arxiv.org/abs/2602.07150); Yuan up to 9% single-turn (https://arxiv.org/abs/2506.09501).
  - What we add: the Bernoulli(p_t) account, the identification of sub-threshold numerics (including a compile mode) as the source, and matching null SDs across null families.

**I4 overall (HYPOTHESIS): "judge by exchangeability with a weight-only / numerics null".**
- *P4d pilot, positive.* A naive McNemar against canonical flags legacy q4 gauss0.3_s1 (p = 0.021). Its null-referenced Δ is −8.3 pp [−16.3, 0.0], so a vs-reference test over-flags a sub-threshold cell.
  - evidence: `verify/out/v03_outcomes_pooled.json` `q4.cells.a6000_q4_gauss0.3_s1`.
- *P4e pilot, positive.* The q4 damage cells have nested pass sets. Cell-only wins vs canonical are 0/10 and 0/8 (RTN-W3) and 0/4 and 0/7 (gauss 3). Free-zone cells show 4–7 cell-only wins per 72 tasks.
  - evidence: same file, `mcnemar_vs_bf16`.
  - Caveat: clean a6k2 RTN-W3 does **not** show it yet (3 vs 4 and 3 vs 3 on 39 / 25 tasks; `verify/out/v03_outcomes_pooled_a6k2.json`). The cell-only win rate against the null's own win-rate band is the cheapest damage signature and should become the primary P4e statistic, but it is unconfirmed on clean data.
- P4b (the φ permutation) has not been run. P4c is now mostly answered by pooling across flavours, above. Keep E5's weight-only seeds, because gauss0.03 sits at +5.1 pp (I2, confound 5).

**Confounds.**
1. The legacy→a6k2 pair also changed the simulator (see I1 confound 4). For I4 this is harmless, because weights and prompt are fixed, but label it.
2. The 4080 numbers are not raw-verified.
3. Only 2 models.

**Deciding experiments.**
- P4a pooled over 5 models (20 df).
- P4b permutation on a6k2 task × run matrices.
- P4e cell-only-win statistic on the a6k2 damage cells.
- All come from `verify/v04` plus E4-f.

---

## Requested experiments and analyses (new ids V1-*)

| id | what | serves | cost | evidence |
|---|---|---|---|---|
| V1-A1 | Make the **per-decision hazard** (with CI) the I1 metric; KM ≤ 12 becomes secondary | I1 | 0 | `verify/v01_legacy_recompute.py` `hazard` |
| V1-A2 | P2a pooled Δ with a **task-cluster** bootstrap across cells (not a row bootstrap), leave-one-out for null members | I2 | 0 | `verify/v03_outcomes_pooled.py` |
| V1-A3 | **Relabel E5.** Legacy-vs-a6k2 is an "agent + simulator serving" null. The agent-only numerics null is `bf16_eager` (already running for q4/q8); add it for q14, q30a3 and q32 | I1-P1c, I4 | ≈0.3 GPU-h per model | `verify/out/v02_a6k2_det.json` |
| V1-A4 | Annotate s02 first-divergence events as write / read / text, plus "undone within the episode"; test the write-flip rate as the P2b predictor | I2 | 0 | `analysis/strategy_v2_workflow/mechanism/a567.out` Q7 |
| V1-A5 | Cell-only win rate against the null's band as the P4e statistic | I4 | 0 | `verify/out/v03_outcomes_pooled.json` `mcnemar_vs_bf16` |
| V1-E1 | Priority completion of a6k2 q8 rtn_w4 ×2, gauss1 ×2, awq_w4 ×2, gptq_w4 ×4, then E3 open-loop D on those cells | I3 (threat) | in matrix + E3 | `verify/out/v04_pooled_draws.json` `q8` |
| V1-E2 | Finish a6k2 q4/q8 damage cells (gauss3, rtn_w3, gptq_w3) before other models' tails. Clean W3 is only −8.5 / −9.3 pp, not significant, so far | I2 | in matrix | `verify/out/v03_outcomes_pooled_a6k2.json` |

The candidates' E4 → E2 → E5 → E3 → E7 order stands. E5 changes as in V1-A3.

**Top request:** complete a6k2 q4/q8 with 5 nulls and the damage cells, then run `verify/v03 a6k2` and `verify/v04`. That decides the I2 free zone, P4c and the q8 RTN-W4 threat to I3.
