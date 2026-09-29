**TL;DR**
- Data integrity first: 20 a6k2 run-domains (≥10% of episodes; 27 with any) are silently broken by `infrastructure_error` episodes (node003's remote simulator died twice), including q4 nulls n3–n5 and q8 RTN-W3/k=1 s1 and several newly queued sub-grid cells. Counting them as failures, as iter-1 did, would fabricate "q4 cells +10–16 pp above null" and "q8 RTN-W3 −23 pp". Re-queue them (E9) and add a worker guard (E11).
- On clean data with infra errors treated as missing, the review's no-GPU items mostly help. The floor is flat from k = 0.001 (2.6% of weights moved by one ulp) to k = 0.03, and the q4→q8/q14 floor ratio is predicted from margins within 7%. W3 damage is confirmed on clean q4/q14, and the q8 RTN-W4 "deficit" disappears (−0.5 pp). A null-referenced TOST at ±7.5 declares equivalence for 11/40 non-null families, against 2/40 for the Flat-Score protocol. Per-family ±5 pp equivalence is out of reach at 85 tasks.
- Exact bf16 logit ties carry about 40–50% of the floor, not all of it. The FP32-head control (E8, ≈1.6 GPU-h, a one-flag change in vLLM 0.29) is the only way to settle W2 against Du et al.; the spec is below.

# Iteration 2 prep: the review's no-GPU analyses (items 1–9)

Input: `paper/perturbation-equivalence-closed-loop.review.md` §6 items 1–9.
Scripts: `analysis/insights/iter_2/` (`run_all.sh`; read-only over `runs/` and `analysis/openloop/`). Outputs go to `analysis/insights/iter_2/out/`.

Snapshot: 2026-09-29T05:06Z (= 09-28 22:06 PDT). Evidence: `out/p00_snapshot.json` `snapshot_utc`, `runs`. At this time:
- q4 and q8 clean (a6k2) cover 85/85 tasks for every cell except k ∈ {0.001, 0.003, 0.01, 2, 3}, k = 1 s3–s5, RTN-W4 n3–n5 and the RTN-W3 draws, which are partial.
- q14 is near-complete except k = 3, the W3 cells and nulls n3/n4.
- q30a3 and q32 have calibration runs only.

Task counts per run are in `out/p01_equivalence.json` `models.<m>.clean.runs`.

**Convention change (applies to all numbers below):** an episode that ends in `infrastructure_error` is treated as *missing*, not as a failure.
- Implemented in `analysis/insights/iter_2/common.py` (`INFRA`, `outcomes`, `infra_tasks`). `CLOQ_INFRA_AS_FAIL=1` restores the iter-1 convention.
- Divergence analyses drop those tasks as well.

Stable ids used here:
- A2-1…A2-9: the review items 1–9, as analyses.
- F1, F2: data flags.
- E8–E11: new proposals, tracked in `docs/insights/EXPERIMENTS.md`.

---

## 0. Data flags (fix before any number goes into the paper)

### F1: infrastructure_error episodes are silently scored as failures

Which run-domains are affected (evidence: `out/p00_snapshot.json` `infra_error_runs`; `runs/<run>/<dom>/metrics.json` `termination_reasons`):

| run-domain | episodes with infrastructure_error |
|---|---|
| a6k2_q4_null_n3 (retail / airline) | 25/58, 2/27 |
| a6k2_q4_null_n4 | 85/85 |
| a6k2_q4_null_n5 | 85/85 |
| a6k2_q8_gauss1_s1/retail | 29/58 |
| a6k2_q8_rtn_w3_n1 | 63/85 |
| a6k2_q8_rtn_w3_n2 | 60/85 |
| a6k2_q4_gauss0.003_s1 (newly queued) | 65/85 |
| a6k2_q4_gauss1_s4 (newly queued) | 72/85 |
| a6k2_q4_gauss2_s2 (newly queued) | 73/85 |
| a6k2_q4_gauss3_s1 | 72/85 |
| a6k2_q8_gauss0.001_s2 (newly queued) | 79/85 |
| single episodes | q4 null_n2, gptq_w4_d1_n1/n2 airline; q14 gauss3_s1 (2) |

Cause:
- Every heavily affected task ran on node003, which uses a remote simulator. The commit message for `scripts/a6000/` is "remote simulator for NVML-broken node003" (git `1ede29c`).
- The simulator stopped answering twice: at 19:43:43 PDT (`/data/ziyangs/cloq_work/logs/tasks/a6k2_q4_bf16.log` line 1257, "[Errno 111] Connection refused") and again at ≈21:50 (`logs/tasks/a6k2_q4_gauss2_s2.log` line 381).
- The tasks still exited rc=0 (`/data/ziyangs/cloq_work/logs/node_node003_49626.out`) and sit in `queue/done/`.
- Tasks claimed after 21:51 look healthy (`runs/a6k2_q4_gauss0.001_s2/*/tau2_results.json`: only user_stop).

Consequences if the episodes are scored as failures:
- The q4 null A mean is deflated: draw rates are 0.0 for n4 and n5 (`out/p01_equivalence.json` from the first run is not kept; reproduce with `CLOQ_INFRA_AS_FAIL=1 python p01_equivalence.py`).
- Every q4 family then appears +8 to +16 pp above the null, and the nonce family appears −5.2 pp below it.
- q8 RTN-W3 appears at −23.4 pp and q8 k = 1 at −9.9 pp.
- None of these effects survive once the episodes are treated as missing (§1–2).
- Iter-1's `verify/out/v04_pooled_draws.json` predates n4/n5, but it includes `a6000_q4_null_n4` as a null draw: 0/6 tasks, a partial run stopped by the STOP file (`runs/a6000_q4_null_n4/retail/tau2_results.json`, 6 simulations; no airline directory).

Fix: E9 (re-queue) and E11 (worker guard), in §3.

### F2: iter-1's first-divergence typing misreads tool calls

- `analysis/insights/iter_1/common.py` `action_key` reads `tc["function"]`. `decisions.jsonl` stores tau2-style calls `{"name", "arguments"}` at top level (checked on `runs/a6k2_q4_bf16` and `runs/a6000_q4_bf16`, first tool decision). Every tool action therefore normalises to `(None, None)`.
- `s02_trajectory_divergence.py` consequently labels tool-call argument or tool changes as "format". The draft's "72–82 of 77–85 first divergences are wording or format" (paper L178 area; provenance §5.1 row "72–82") rests on this label.
- Corrected typing (`analysis/insights/iter_2/p04_write_flips.py`; `out/p04_write_flips.json` `models.<m>.cells.<run>.first_div_class`) for the clean floor members:
  - q4 eager: 73 text→text, 3 text↔tool, 2 read→read, 1 write-involved, 6 never diverged.
  - q4 nonce n1: 69 text→text, 8 text↔tool, 6 read→read, 1 write.
  - q8 eager: 61 text→text, 7 read→read, 8 write.
- The "mostly wording" statement survives (86–87% text→text of diverged tasks on q4, 72–80% on q8), but it must be re-sourced to p04.

---

## 1. Results by review item

### A2-1 (W1): declared-margin TOST, per family and per cell. Verdict: W1 **confirmed** for single families; **partly resolved** for pooled statistics

Method (`p01_equivalence.py`):
- Δ = mean over (draw, task) of y − ȳ_null(t), with a task-cluster bootstrap (B = 4000).
- The primary null set is A = {canonical bf16, eager, nonces}, with leave-one-out for null members.
- Margins were declared by the review before this script ran: ±5 pp, ±7.5 pp, and ±2·SD_null.
- A family is "equivalent" if its 90% CI lies inside ±M. It is "below" or "above" if the 95% CI excludes 0.

Clean q4 (null A = 5 draws; SD_null = 1.7 pp), from `out/p01_equivalence.json` `models.q4.clean.nullsets.A.families`:

| family (draws, tasks) | Δ pp [95% CI] | TOST ±5 | TOST ±7.5 | M80 (pp) |
|---|---|---|---|---|
| nonce (3, 85) | +0.2 [−3.1, +3.5] | equivalent | equivalent | 4.9 |
| k = 0.001 (2, 85) | +5.6 [−0.8, +12.0] | inconclusive | inconclusive | 9.6 |
| k = 0.01 (2, 85) | −0.7 [−6.9, +6.0] | inconclusive | equivalent | 9.7 |
| k = 0.03 (5, 85) | +5.0 [+0.8, +9.5] | above-null (p_boot 0.015) | above-null | 6.5 |
| k = 0.1 (2, 85) | −0.8 [−5.9, +4.2] | inconclusive | equivalent | 7.6 |
| RTN-W8 (2, 85) | +0.4 [−5.5, +6.0] | inconclusive | equivalent | 8.6 |
| k = 0.3 (2, 85) | +3.9 [−2.5, +10.6] | inconclusive | inconclusive | 9.9 |
| GPTQ-W4 (4, 85) | +2.6 [−4.2, +9.7] | inconclusive | inconclusive | 10.3 |
| AWQ-W4 (2, 85) | +1.0 [−7.6, +9.9] | inconclusive | inconclusive | 13.1 |
| RTN-W4 (5; n3–n5 partial) | −2.1 [−9.5, +5.2] | inconclusive | inconclusive | 11.1 |
| k = 1 (5; s3–s5 partial) | −0.7 [−7.3, +5.7] | inconclusive | equivalent | 10.0 |
| k = 2 (2, 27 tasks) | −18.9 [−35.6, −2.5] | below | below | 25.1 |
| GPTQ-W3 (2, 85) | +2.1 [−6.7, +10.7] | inconclusive | inconclusive | 13.2 |
| RTN-W3 (2, 74) | −19.3 [−29.2, −9.3] | below beyond margin | below beyond margin | 15.2 |

Clean q8 (null A = 7 draws; SD_null = 2.7 pp), from `models.q8.clean.nullsets.A.families`:
- Equivalent at ±5: k = 0.03 (−0.3 [−4.7, +4.1]), k = 0.1 (+0.1 [−4.5, +4.7]) and nonce (−0.9 [−3.0, +1.2]).
- Equivalent at ±7.5 only: RTN-W4 (−0.5 [−7.1, +6.3]), RTN-W8 (−1.7 [−7.1, +3.6]), k = 0.3 (+1.8 [−5.0, +8.3]), GPTQ-W3 (+0.7 [−7.8, +9.1]) and k = 0.003.
- Inconclusive: k = 1 (−5.1 [−12.3, +2.3]), GPTQ-W4 (−2.9 [−9.1, +3.1]) and AWQ-W4 (−2.9 [−11.0, +5.5]).
- RTN-W3 is inconclusive on only 29 valid tasks, because of F1.

Clean q14 (null A = 5 draws, 2 of them partial; no eager yet), from `models.q14.clean.nullsets.A.families`:
- RTN-W3: −14.6 [−24.9, −5.1], below.
- Every other family is inconclusive, with negative point estimates from −1.4 to −7.4. The canonical q14 run sits +4.0 above its own null (`null:bf16`).

Pooled free zone (pre-registered: k ≤ 0.1 and W8, non-null draws), from `models.<m>.clean.pooled_free_zone.A`:

| model | Δ pp [95% CI] | TOST ±5 | TOST ±7.5 | pre-registered falsification (Δ < −3.4 and CI < 0)? |
|---|---|---|---|---|
| q4 | +2.7 [−1.0, +6.4] | inconclusive | **equivalent** | no |
| q8 | −0.5 [−4.0, +3.0] | **equivalent** | **equivalent** | no |
| q14 | −4.8 [−8.9, −0.7] | below | below | **yes, under null A**. Not under null B (−3.0 [−6.3, 0.0]) or C (−2.7 [−6.4, +1.0]) |

Power:
- The smallest margin TOST passes with 80% power at a true Δ = 0 is M80 = 2.93·SE.
- For a 2-draw family on 85 tasks, M80 is 7.6–13 pp. The best case is 6.5 pp (q4 k = 0.03, 5 draws) and 6.6 pp (q8 k = 0.03, 5 draws). Evidence: `families.<f>.m80_tost`.
- **±5 pp per-family equivalence is out of reach at 85 tasks with ≤ 5 draws. Report it as a limitation.**
- ±7.5 pp needs about 4–5 draws per family.
- The pooled free zone reaches ±5 on q8 because it stacks 9 draws.

What this means for the paper:
- Replace "stays at null level" with "not distinguishable (95% CI); equivalence established at ±7.5 pp for {list}, not at ±5 pp".
- Use the pooled free zone as the only ±5 pp claim, on q8 only (q4 at ±7.5).
- The Definition-vs-statistic gap (W1, φ test P4b) remains open. It is not run here.

### A2-2 (W3, W4): within-pass stratification, null-set sensitivity, and the k = 0.03 anomaly. Verdict: W3 **resolved** as a pass-composition artifact claim, **confirmed** as null heterogeneity; W4 **largely resolved** on q8, **confirmed** as a model-scope issue

1. **Pass composition does not explain the k = 0.03 anomaly.**
   - q4 k = 0.03 is +5.0 pp clean and +5.7 legacy (heterogeneity z = −0.19).
   - The inverse-variance-weighted (IVW) combination is +5.2 [+1.6, +8.8], the same as the mixed-pass v04 value of +5.1.
   - Evidence: `models.q4.stratified.gauss0.03`.
   - The anomaly is null-set dependent:
     - null A (nonce-heavy): +5.0, above;
     - null D (nonces only): +3.3 [−2.0, +9.1];
     - null B (A + k = 0.03 members): +2.6 [+0.4, +5.0];
     - null C (canonical-prompt only): +1.7 [−0.1, +3.5], equivalent at ±5.
     - Evidence: `models.q4.clean.nullsets.{B,C,D}.families.gauss0.03`.
   - q4 k = 0.001 is also +5.6 [−0.8, +12.0] under null A.
   - Reading: q4 canonical-prompt weight-noise draws sit a few pp above the nonce draws. At p_boot = 0.015 among 18 q4 families, the family-wise evidence is weak (Bonferroni threshold 0.0028).
   - On q8 there is no such effect (k = 0.03: −0.3; `models.q8.clean.nullsets.A.families.gauss0.03`).
   - Paper action: state the null-set sensitivity (Table 4 with columns A/C), not a pass artefact.
2. **Clean W3 damage is now significant.**
   - q4 RTN-W3: −19.3 [−29.2, −9.3] (74 tasks). IVW with legacy gives −18.8 [−26.8, −10.7], with heterogeneity z = −0.17 (`stratified.rtn_w3`).
   - q14 RTN-W3: −14.6 [−24.9, −5.1].
   - q4 k = 2 is −18.9 on only 27 tasks. Its s2 run is F1-broken.
   - The damage threshold on q4 is still located only as "between k = 1 and 2–3, and at W3".
3. **The q8 RTN-W4 deficit was a legacy/mixed-pass artifact.**
   - Clean q8 RTN-W4 is −0.5 [−7.1, +6.3]. Legacy is −5.9, and the mixed-pass v04 value was −10.5 [−17.3, −4.0].
   - IVW: −2.7 [−7.9, +2.6] (`models.q8.stratified.rtn_w4`; `iter_1/verify/out/v04_pooled_draws.json` `q8.families.rtn_w4`).
   - The single "compressed is worse" finding at W4 that the review flagged (W4 §5 row 4) does not survive clean data.
   - The I3 matched-D threat on q8 is therefore weakened: RTN-W4 −0.5, k = 1 −5.1, AWQ −2.9, GPTQ −2.9, all inconclusive.
4. **The clean q8 free zone is not refuted.** Its −3.5 pp in the draft came from 2–3 nulls on partial tasks. It is now −0.5 [−4.0, +3.0] (item A2-1).
5. **q14 is the new at-risk model.**
   - All q14 families point negative against a null that contains a high canonical run (0.434) and only partial n3/n4 (`models.q14.clean.null_width_A.draw_rates`).
   - Its free zone fires the falsification rule under null A only.
   - Needed before any q14 claim: the q14 eager run and completion of n3–n5 (V1-A3; in the queue).
6. **Leave-one-family-out (null A):**
   - Dropping bf16 or eager moves q4 RTN-W4 between −4.7 and −3.5 and q4 RTN-W3 between −19.6 and −18.6, with no verdict change at ±5 (`models.q4.clean.lofo_nullset_A`).
   - Dropping the nonces leaves fewer than 3 draws per task, so it is not computed.

### A2-3 (W2): exact ties and the floor. Verdict: W2 problem 1 **resolved**, problem 2 **resolved**, problem 3 **partly confirmed**

Method: `p02_ties.py` (closed loop) and E3 npz (open loop, teacher-forced on the bf16 contexts). Margins of exactly 0.0 are exact bf16 logit ties:
- the lm_head runs in bf16 by default in vLLM 0.29 (`vllm/model_executor/layers/logits_processor.py` `_apply_head`, `vllm/config/model.py` `head_dtype`);
- margins are logged to 1e-4 (`cloq/agent.py` `_token_margins`).

1. **Tie density.** The share of text decisions with at least one exact tie is:
   - 0.49 (q4), 0.37 (q8), 0.50 (q14), 0.55 (q30a3), 0.65 (q32).
   - For tool decisions it is 0.018–0.025.
   - The smallest non-zero margin is 0.125 in every model.
   - Evidence: `out/p02_ties.json` `tie_density.<m>.{text,tool}.frac_dec_with_exact_tie`, `smallest_nonzero_margins`.
2. **The floor is flat below the grid (problem 1).** q4 per-decision hazard with task-bootstrap 95% CI (`closed_loop.q4.<run>.hazard`, `hazard_ci95_task_boot`):

   | cell | hazard [95% CI] |
   |---|---|
   | k = 0.001 | 0.183 [0.159, 0.215] and 0.154 [0.130, 0.180] |
   | k = 0.003 | 0.165 [0.142, 0.191] (s2; s1 is F1-broken) |
   | k = 0.01 | 0.172 / 0.173 |
   | k = 0.03 (×5) | 0.179–0.227 |
   | eager | 0.170 [0.148, 0.197] |
   | RTN-W8 | 0.211 / 0.223 |
   | then k = 0.1 | 0.280 / 0.285 |
   | D ≡ 0 (det_q4_a) | 0.0 |

   - q8 shows the same pattern: k = 0.001–0.03 and eager all fall between 0.085 and 0.118; k = 0.1 is 0.147 / 0.180.
   - At k = 0.001 only 2.6–6.2% of bf16 weights change, each by one ulp. At k = 0.03 it is 55–65% (`out/p06_weight_ulp.json`).
   - **The hazard is the same whether 3% or 60% of weights move by an ulp.** That is the bimodality claim, now with points below the grid. Rewrite "bimodal" as "0 at D ≡ 0; 0.15–0.23 (q4) / 0.09–0.12 (q8) from the smallest measurable perturbation up to k = 0.03".
3. **Nonce sits above the floor because its shift is larger (problem 2).**
   - Nonce hazards are 0.25–0.27 (q4) and 0.16–0.20 (q8), with text hazards of 0.47–0.52 against 0.35–0.43 for the floor cells (`closed_loop.<m>.a6k2_<m>_null_n*.hazard_text`).
   - The draft's closed-loop median |d| is 0.25 for nonces against 0.125 for the floor (provenance §5.1, Table 3a).
   - The floor band is therefore {eager, k ≤ 0.03, W8}. Nonces are above it.
4. **What exact ties explain (problem 3).**
   - Open loop, P(flip | m = 0) (`open_loop.<m>.<cell>."flip|m in 0"`):
     - q4: eager 0.26, k = 0.03 0.26–0.32, W8 0.33;
     - q8: eager 0.19, k = 0.03 0.17–0.24.
   - Adjacent-grid near-ties flip at similar rates: at (0.125, 0.25], q4 0.16–0.19. So ties are not special beyond being the densest margin bin.
   - Share of flipped decisions that include an exact-tie flip (`share_flipped_decisions_with_tie_flip`): q4 floor 0.42–0.52, q8 0.32–0.45.
   - Closed loop, share of first flips at m = 0 (`share_first_flips_exact_tie`): q4 floor 0.26–0.38, q8 0.29–0.48.
   - The tie-only hazard prediction is 0.06–0.09 (q4) against an observed 0.15–0.23 (`pred_hazard_tie_only` vs `hazard`).
   - **Exact ties carry about 40–50% of the floor. The rest comes from 1–2-ulp near-ties.** The floor is a property of the *bf16 logit grid* (ties plus grid-adjacent near-ties), which strengthens the review's suspicion but does not make it a tie-only artefact. Only E8 (fp32 head) can tell whether the floor survives without the grid.
5. **The floor is predicted across models from margins alone (review fix 2).**
   - Take q4's pooled floor token hazards by margin bin (`floor_token_hazard_pooled.q4`) and apply them to each model's bf16 reference decisions. The predicted hazard is 0.241 (q4), 0.154 (q8) and 0.193 (q14) (`cross_model.<m>.pred_all_decisions_q4_floor_h`).
   - Scale by q4's observed/predicted ratio (0.1887 / 0.2414). This gives predicted floors of **0.120 (q8; observed median 0.113)** and **0.151 (q14; observed 0.152)** (`cross_model.<m>.observed_floor_hazard_median`).
   - This is a quantitative P3-style result.
   - Caveats: the calibration uses q4 itself; the q14 floor set lacks eager and sub-grid cells and contains nonces; it covers three models.
   - Next: pre-register the same computation for q30a3 and q32 from their calibration runs. The inputs are already in `tie_density`.

### A2-4 (W5): Flat Score and Singh protocols on our cells. Verdict: W5 fix 3 **resolved**; this is the criterion's demonstrated consequence

Method (`p01_equivalence.py` `paired_vs_canon`):
- Each family's per-task mean is compared with the single canonical BF16 run, paired by task.
- Flat-Score-style: TOST ±7.5 (90% CI). Singh-style: TOST ±2. Plus an exact two-sided McNemar per draw.
- Flat Score's own reference had 4 trials per task; ours has 1. State this.
- Evidence: `models.<m>.clean.reference_only.<family>`.

Across 40 non-null family verdicts (q4, q8, q14 clean; evidence: `out/p07_protocol_tally.json` `total`, written by `p07_protocol_tally.py` from `p01_equivalence.json`):
- **Flat-Score-style declares equivalence 2 times; the null-referenced ±7.5 TOST declares it 11 times.**
- **Singh-style ±2 declares it 0 times.**
- Below-null verdicts: 4 for Flat-Score-style against 3 for the null-referenced TOST.
- The per-family rows, with a `disagree` flag, are in `models.<m>`.

Why the protocols diverge:
- The canonical run is not the centre of the null. q8 canonical is +6.3 pp above its own null (`models.q8.clean.nullsets.A.families.null:bf16`), so every q8 cell looks 3.5–7 pp worse than "the reference".
  - Example: q8 RTN-W4 is −5.9 pp vs canonical (FS inconclusive) and −0.5 [−7.1, +6.3] vs the null (equivalent at ±7.5).
- On q14 the canonical run is +4.0 above its null. FS flags k = 1 (−10.0) and RTN-W4 (−9.4) as "below", while the null-referenced test gives −7.4 / −7.4, inconclusive.

McNemar vs canonical flags 10 of 98 non-null draws at p < 0.05 (`p07_protocol_tally.json` `total.mcnemar_flags`; per draw in `p01_equivalence.json` `reference_only.*.mcnemar_per_draw`):
- 4 are the RTN-W3 draws on q4 and q14, which are damaged under both tests.
- 6 are in families that are not below the null: q4 k = 0.3 s2, q8 k = 1 s2, q14 k = 1 s1, q14 GPTQ-W4 d1 n1/n2, q14 RTN-W8 n2.
- 6/94 non-damaged draws is about the nominal 5%. The reference-only false flags are thus visible at the per-draw level.

### A2-5 (W5, Q4): reconciling with Replay Gap's 0/359. Verdict: tension **reduced, not removed**

Method: `p03_replay_gap.py`. Every clean cell is compared with the canonical run, paired on the conversation excluding the system prompt. Infra tasks are dropped. Evidence: `out/p03_replay_gap.json` `models.<m>`.

1. **No outcome flips without divergence.** 0/72 (q4), 0/126 (q8) and 0/65 (q14) task pairs that never diverged changed outcome (`agent_only.never_diverged`). Scoring is deterministic.
2. **The simulator is not needed for flips.**
   - In clean pairs, 0 first divergences are simulator/environment-first (`agent_only.diverged_ctx_first.n` = 0). Every flip is agent-initiated.
   - Agent-only perturbations flip 17.5% (q4, n = 1,341 task pairs), 18.9% (q8, 1,420) and 16.7% (q14, 540) of outcomes (`agent_only.overall`).
   - This is the same rate as the legacy→clean canonical pair, where the simulator first differs on 64% (q4) and 62% (q8) of tasks at decision 0: 24.7% and 26.8% flips (`legacy_vs_clean_canonical.share_ctx_first_at_decision0`, `overall`).
   - Paper wording: the I4a number is an agent + simulator null, but the agent-only rate is similar.
3. **Fork depth matters.** Outcome-flip rate by where the first divergence falls in the episode (`agent_only.by_rel_depth`):

   | model | first quarter | last quarter |
   |---|---|---|
   | q4 | 0.215 | 0.056 (n = 54) |
   | q8 | 0.304 | 0.000 (n = 108) |
   | q14 | 0.333 | 0.033 (n = 61) |

   Divergences in the last quarter almost never flip the outcome.
4. **Depth alone does not reproduce 0/359.** The flip rate for divergences past mid-episode is 0.143 / 0.084 / 0.063, which makes P(0 flips in 359) between 1e-24 and 6e-11 (`late_fork_flip_rate`, `P_zero_flips_in_359_at_late_rate`). Only q8's last-quarter bin reaches 0.
5. **Remaining differences we cannot test here:**
   - SWE-bench's unit-test endpoint (many paths pass, many tasks are unsolvable) against τ²'s exact DB-state match;
   - outcome degeneracy: only 32% (q4), 42% (q8) and 23% (q14) of our tasks have 0 < p̂_t < 1 (A2-8), and tasks with degenerate outcomes cannot flip;
   - Replay Gap's fork placement.
6. Paragraph for the paper: "flips require early divergence on a task whose success probability is non-degenerate; late forks and degenerate tasks, which dominate a replay-fork design on SWE-bench, give ≈0 flips in our data too (q8 last-quarter 0/108)".

### A2-6 (W2, clarity): text vs tool hazard. Verdict: **resolved**. The floor is a text-turn quantity

Floor cells, per-decision hazard by the kind of the reference decision (`closed_loop.<m>.<run>.hazard_text`, `hazard_tool`):

| model | text | tool |
|---|---|---|
| q4 | 0.32–0.44 | 0.010–0.051 |
| q8 | 0.16–0.24 | 0.010–0.034 |
| q14 | 0.31 (k = 0.03), 0.35–0.37 (W8) | 0.016–0.035 |

- Text/tool ratios at the floor are about 7–30×.
- The mixture explains part of q8's lower overall floor: q8 has 973 tool vs 663 text reference decisions, while q4 has 513 vs 429 (`tie_density.<m>.*.n_decisions`).
- Report the text-turn hazard as the floor quantity and the overall hazard as mixture-dependent.

### A2-7 (P2b): write-flip annotation. Verdict: the P2b write-flip predictor is **not supported**; the mechanism sentence should be withdrawn

Method: `p04_write_flips.py`. Write = a call matching `cancel|modify|return|exchange|book|update|send|transfer*`.

1. **Sanity check.** When the multiset of write calls equals BF16's, the outcome flips in 4/884 (q4), 0/597 (q8) and 1/565 (q14) task pairs (`models.<m>.cells.*.outcome_flip_given_same_writes`). The DB endpoint is a function of the writes.
2. **Write sets change at the null level.**
   - Floor cells already change the write multiset on 55–75% of tasks (q4 k = 0.03: 0.64; eager: 0.62; nonce n1: 0.68). RTN-W3 changes it on 0.72–0.73 (q4) (`families[*].write_set_change`, `cells.*.write_set_change_rate`).
   - So "write flips" are mostly re-rolls, not damage.
3. **Spearman across families of Δ against:**

   | predictor | q4 | q8 | q14 |
   |---|---|---|---|
   | write-set change | −0.40 (p 0.14) | −0.18 | −0.44 |
   | overall hazard | −0.62 (p 0.013) | −0.09 | −0.39 |
   | tool hazard | −0.60 (p 0.018) | — | — |

   - On q4 the correlation is driven by the saturated W3/k ≥ 2 cells (`spearman`).
   - No divergence statistic ranks damage below saturation.
4. Paper action:
   - Drop "damage requires unrecovered flips of state-changing actions" as a stated mechanism.
   - State damage phenomenologically: success falls only where tool-turn hazard saturates, at W3 and k ≥ 2.
   - Add that re-rolls change the write set on about 2/3 of tasks without changing the success rate.
   - The "undone within episode" flag is not implemented; it is left open.

### A2-8 (W9): null width. Verdict: W9 **confirmed**. Report non-degeneracy, not the SD ratio

From `models.<m>.clean.null_width_A`, over near-complete clean null draws. The SD column gives the observed SD with its chi-square CI; "predicted SD" is the Bernoulli prediction with the (R−1)/R bias corrected.

| model | draws | observed SD pp [95% CI] | predicted SD pp | ratio [95% CI] | tasks with 0 < p̂_t < 1 |
|---|---|---|---|---|---|
| q4 | 4 | 2.0 [1.2, 7.6] | 3.2 | 0.63 [0.36, 2.34] | 0.32 (27/84; 40 never pass, 17 always pass) |
| q8 | 7 | 2.7 [1.7, 6.0] | 3.35 | 0.81 [0.52, 1.78] | 0.42 |
| q14 | 3 | 3.9 [2.0, 24] | 3.0 | 1.28 [0.67, 8.0] | 0.23 |

- Every CI covers most of the [0.5, 2] band, so the check has no power, exactly as the review says.
- The observed non-degenerate fraction is a lower bound: a task with p = 0.2 looks degenerate in 4 draws with probability 0.41.
- The draft's q4 "6 near-complete draws" figure mixes passes, and its nulls n4/n5 are F1-broken.
- Note: mean pairwise discordance equals 2·mean unbiased p̂(1−p̂) identically (`note` field). It is not a test.

### A2-9 (W11): the E3 axis for Figures 2 and 3. Verdict: W11 **confirmed and resolved**

- Open-loop |d| p50 collapses. On q8 it is exactly 0 for 13 of 14 non-reference cells (`out/p05_e3_axis.json` `models.q8.axes.abs_d_p50.n_cells_zero`). On q4 it is at or below 1.3e-6 for every cell below k = 3.
- **Recommended axis: open-loop token flip rate.**
  - The bf16 self-replay has exactly 0, which gives the D ≡ 0 anchor.
  - It spans 2 decades: q4 eager 0.0042, k = 0.03 0.0048, W8 0.0065, k = 0.1 0.0089, k = 0.3 0.023, RTN-W4 0.064, k = 1 0.076, k = 3 0.41.
  - Spearman with the closed-loop hazard is 0.986 (q4) and 0.978 (q8); with k it is 0.97 (`axes.flip_rate`).
- |d| mean and p99 rank as well, but they have a logging-rounding floor of about 5e-5 at bf16.
- decision-any-flip should not be used as the x-axis of a hazard plot, because it is the open-loop analogue of the y-axis.
- E3 for the new sub-grid cells is missing. That is E10 below.

---

## 2. Scorecard against the review's weaknesses

| review item | this iteration | status |
|---|---|---|
| W1 (equivalence from non-rejection) | A2-1: TOST table; M80 per family 6.5–13 pp; pooled free zone equivalent at ±5 (q8), ±7.5 (q4) | confirmed per family; partly resolved (pooled) |
| W2 (floor under-identified / tie artefact) | A2-3, A2-6: flat hazard from k = 0.001 (2.6% weights moved) to 0.03; ties = 40–50% of floor; cross-model floor ratio predicted within 7% | problems 1–2 resolved; problem 3 partly confirmed, needs E8 |
| W3 (circular pooling, heterogeneous null) | A2-2: pass composition ruled out (het z −0.19); k = 0.03 anomaly is null-set dependent (A +5.0 → C +1.7) | resolved / reframed |
| W4 (one model, q8 contradiction) | A2-2: q8 RTN-W4 deficit gone on clean data (−0.5); clean W3 damage significant on q4 and q14; q14 at risk | largely resolved; new risk q14 |
| W5 (novelty; Replay Gap tension) | A2-4: 11 vs 2 equivalence verdicts (of 40); A2-5: depth + degeneracy account | resolved (fix 3); tension reduced |
| W9 | A2-8 | confirmed; report non-degeneracy |
| W11 | A2-9 | resolved (token flip rate) |
| P2b placeholder | A2-7 | predictor not supported; withdraw the mechanism sentence |
| new | F1, F2 | must fix before submission |

---

## 3. Proposals (GPU and code), for main

Cost basis (`/data/ziyangs/cloq_work/queue/done/*.json` `seconds`):
- q4 single eval run 0.19–0.49 h (a6k2_q4_gauss0.03_s2…s5; eager 0.42);
- det task 0.09 h (a6k2_det_q4_a, 323 s);
- E3 cell 0.10–0.11 h (a6k2_q4_ol_*).

### E8: FP32-head control (the review's item 11). **Essential** for W2 and for positioning against Du et al.

- The fp32 head is a one-flag change: vLLM 0.29 supports `--hf-overrides '{"head_dtype": "float32"}'` for generation models (`vllm/config/model.py` `head_dtype` docstring; `logits_processor.py` `_apply_head` uses `torch.mm(..., out_dtype=float32)` for an unquantized lm_head).
- `worker.py` already forwards `serve_extra` to `serve.sh` and skips the canary for it (lines 189–201).
- Cost: ≈1.6 GPU-h (2 det tasks × 0.09 h + 4 eval runs × ≈0.35 h).

Pre-registered predictions, stated before any run:
- (a) The det pair is byte-identical. If it is not, the fp32-head GEMM breaks batch invariance: stop and report.
- (b) The share of text decisions with an exact tie falls from 0.49 to < 0.02.
- (c) The eager-vs-compiled hazard under the fp32 head is ≤ 0.12 (bf16 head: 0.170 [0.148, 0.197]).
- (d) Under the fp32 head, hazard at k = 0.001 < hazard at k = 0.03, i.e. a dose-response appears below the grid.

Falsification: if (c) fails with a hazard ≥ 0.15, the floor is not a bf16-logit property, and the paper can say so against Du et al.

Order: det pair first; the rest depends on it.
```json
{"id": "a6k2_det_q4_fp32h_a", "kind": "eval", "model": "q4", "arm": "bf16", "ckpt": {"kind": "bf16"},
 "runs": [{"run_id": "a6k2_det_q4_fp32h_a", "task_file": "manifests/a6000/det_tasks.json", "nonce": null}],
 "priority": -10, "deps": [], "node": "node005", "serve_extra": ["--hf-overrides", "{\"head_dtype\": \"float32\"}"]}
{"id": "a6k2_det_q4_fp32h_b", "kind": "eval", "model": "q4", "arm": "bf16", "ckpt": {"kind": "bf16"},
 "runs": [{"run_id": "a6k2_det_q4_fp32h_b", "task_file": "manifests/a6000/det_tasks.json", "nonce": null}],
 "priority": -10, "deps": [], "node": "node004", "serve_extra": ["--hf-overrides", "{\"head_dtype\": \"float32\"}"]}
{"id": "a6k2_q4_bf16_fp32h", "kind": "eval", "model": "q4", "arm": "bf16", "ckpt": {"kind": "bf16"},
 "runs": [{"run_id": "a6k2_q4_bf16_fp32h", "task_file": "manifests/eval_tasks_v0.json", "nonce": null}],
 "priority": 5, "deps": ["a6k2_det_q4_fp32h_a", "a6k2_det_q4_fp32h_b"], "serve_extra": ["--hf-overrides", "{\"head_dtype\": \"float32\"}"]}
{"id": "a6k2_q4_bf16_eager_fp32h", "kind": "eval", "model": "q4", "arm": "bf16", "ckpt": {"kind": "bf16"},
 "runs": [{"run_id": "a6k2_q4_bf16_eager_fp32h", "task_file": "manifests/eval_tasks_v0.json", "nonce": null}],
 "priority": 5, "deps": ["a6k2_det_q4_fp32h_a", "a6k2_det_q4_fp32h_b"], "serve_extra": ["--enforce-eager", "--hf-overrides", "{\"head_dtype\": \"float32\"}"]}
{"id": "a6k2_q4_gauss0.001_s1_fp32h", "kind": "eval", "model": "q4", "arm": "gauss", "ckpt": {"kind": "gauss", "k": 0.001, "seed": 1},
 "runs": [{"run_id": "a6k2_q4_gauss0.001_s1_fp32h", "task_file": "manifests/eval_tasks_v0.json", "nonce": null}],
 "priority": 5, "deps": ["a6k2_det_q4_fp32h_a", "a6k2_det_q4_fp32h_b"], "serve_extra": ["--hf-overrides", "{\"head_dtype\": \"float32\"}"]}
{"id": "a6k2_q4_gauss0.03_s1_fp32h", "kind": "eval", "model": "q4", "arm": "gauss", "ckpt": {"kind": "gauss", "k": 0.03, "seed": 1},
 "runs": [{"run_id": "a6k2_q4_gauss0.03_s1_fp32h", "task_file": "manifests/eval_tasks_v0.json", "nonce": null}],
 "priority": 5, "deps": ["a6k2_det_q4_fp32h_a", "a6k2_det_q4_fp32h_b"], "serve_extra": ["--hf-overrides", "{\"head_dtype\": \"float32\"}"]}
```

Analysis:
- `python analysis/insights/iter_2/p02_ties.py` with the pair list extended to (eager_fp32h, gauss*_fp32h) → ref `a6k2_q4_bf16_fp32h` (sha pairing), plus the det pair. This is a small edit to `pairs` in `main()`; I will add it once the runs exist.
- Check that the fp32h reference is not scored against the bf16 canary, and that `a6k2_q4_bf16_fp32h` never enters null set A.

### E9: re-queue the F1-broken runs (≈4.5 GPU-h)

- Main first moves the broken run directories aside (for example to `runs/_infra_broken/`, so that nothing is overwritten), then re-enqueues.
- The following tasks can be re-enqueued unchanged from `queue/done/<id>.json`, with the `result` / `finished` / `seconds` / `host` fields dropped:
  - a6k2_q8_gauss1_s1, a6k2_q8_rtn_w3 (n1, n2);
  - a6k2_q4_gauss0.003_s1, a6k2_q4_gauss1_s4, a6k2_q4_gauss2_s2, a6k2_q4_gauss3_s1;
  - a6k2_q8_gauss0.001_s2.
- Pin all of them away from node003 (`"node"` ≠ node003) until its remote simulator is stable.
- The q4 nulls need a new task, because the original task also holds bf16 and n1/n2:
```json
{"id": "a6k2_q4_null_fix", "kind": "eval", "model": "q4", "arm": "bf16", "ckpt": {"kind": "bf16"},
 "runs": [{"run_id": "a6k2_q4_null_n3", "task_file": "manifests/eval_tasks_v0.json", "nonce": "5c0d7e3a"},
          {"run_id": "a6k2_q4_null_n4", "task_file": "manifests/eval_tasks_v0.json", "nonce": "e21f6b48"},
          {"run_id": "a6k2_q4_null_n5", "task_file": "manifests/eval_tasks_v0.json", "nonce": "9a7c4f15"}],
 "priority": 1, "deps": [], "node": "node005"}
```
- The nonces are copied from `queue/done/a6k2_q4_bf16.json` `runs`.
- This task passes the bf16 canary (no `serve_extra`), so the nonce draws share the canonical flavour.
- Cost: 3 × ≈0.4 + 7 tasks (8 runs) × ≈0.35–1 h ≈ 4.5 GPU-h.

### E10: E3 open-loop D for the sub-grid and new cells (≈0.8 GPU-h for q4, ≈1.6 GPU-h for q4 + q8)

- Cells: `make_tasks.py --only e3` for q4 and q8 at k ∈ {0.001, 0.003, 0.01, 2} × s1/s2.
- Cost: 8 cells × 0.10 h per model ≈ 1.6 GPU-h if both models are run; ≈0.8 GPU-h for q4 only.
- It puts the sub-grid points on the Figure 2 x-axis (A2-9). The prediction is that the token flip rate at k = 0.001 is 0.003–0.005, like eager.

### E11: worker guard against silent infrastructure failures (code change for main, 0 GPU-h)

- After each run, `worker.py` should read `runs/<run>/<dom>/metrics.json` `termination_reasons`. If `infrastructure_error` > 0, it should move the task to `failed/`, or retry the run, instead of `done/`.
- It should also probe the simulator's `/models` between runs.
- The iter-1 verify scripts (`v01`, `v03`, `v04`) should drop `infrastructure_error` episodes the same way `analysis/insights/iter_2/common.py` does.

### Not proposed / dropped

- Review item 13 (k = 2 × 2 and +2 draws for RTN-W4 and k = 1) is already queued. Its k = 2 s2 and k = 1 s4 draws are F1-broken and are covered by E9.
- More per-family draws aimed at ±5 pp are dropped: M80 is ≥ 6.5 pp even with 5 draws, so it is not affordable. Use pooled statistics instead.
