**TL;DR**
- After iteration 1: 4 insights live and none killed. I1 needs its rewrite (v2: a per-decision hazard floor). I2 and I3 are HYPOTHESIS, and I3 is at risk from q8 RTN-W4. I4 is HYPOTHESIS, with sub-claim I4a HELD (the canonical score is one draw).
- Next decisive step: finish a6k2 q4/q8 (5 nulls + damage cells), then run `analysis/insights/iter_1/verify/v03_outcomes_pooled.py a6k2` and `v04_pooled_draws.py`.
- Latest verdicts are in `docs/insights/iter_1_verdicts.md`; this file is the running index across iterations.

# Insight ledger

Stable ids persist across iterations. The history of each id is in `docs/insights/iter_<N>_{candidates,discussion,verdicts}.md`
and `docs/RESEARCH_LOG.md` (V6).

## All insights ever proposed

| id | one-line principle (latest wording) | latest verdict | iter | reason / evidence |
|---|---|---|---|---|
| I1 | Any perturbation ≥ the bf16 log-prob resolution meets a per-decision divergence-hazard floor set by text-turn near-ties, so episode-level divergence saturates and cannot rank δ; the per-decision hazard and the tool-turn flip rate can (v2) | **REVISE** (v2 is HELD-level on q4 clean; 5-model claim is HYPOTHESIS) | 1 | "cannot rank" was wrong for the per-decision hazard, which ranks δ with separated CIs; the D≡0 arm is confirmed (257/257); `docs/insights/iter_1_verdicts.md#i1`; `analysis/insights/iter_1/verify/out/v01_legacy_recompute_a6k2.json`, `v02_a6k2_det.json` |
| I2 | A free zone separates divergence onset from damage onset; damage needs unrecovered state-changing action flips (v2 mechanism) | **HYPOTHESIS** | 1 | On q4 (legacy + a6k2 pooled), db_match is at null level through k = 1 and RTN-W4 and drops at k = 3 (−16 pp) and W3 (−14 pp). Tool-flip onset precedes damage, so P2b needs the write-flip predictor. `iter_1_verdicts.md#i2`; `verify/out/v04_pooled_draws.json` |
| I3 | Perturbations at matched output-logit shift D give matched closed-loop outcomes, whatever their structure; D(k) is model-size independent | **HYPOTHESIS (at risk)** | 1 | Small-k D matches on q4 = q8 clean. Legacy q8 RTN-W4 is −10.5 pp [−17.3, −4.0] vs gauss1 0.0 at matched D. `iter_1_verdicts.md#i3`; `verify/out/v04_pooled_draws.json` `q8` |
| I4 | Under greedy decoding the canonical score is one Bernoulli(p_t) draw; judge compressed agents by exchangeability with a weight-only / numerics null | **HYPOTHESIS** | 1 | The criterion (P4b) is untested. `iter_1_verdicts.md#i4` |
| I4a | Sub-threshold serving numerics alone (same weights and prompt) move the canonical τ² db_match by ±8 pp (21/85 and 21/79 tasks flip); null-draw SD matches the Bernoulli prediction (q4 2.9 vs 3.2 pp; q8 3.75 vs 3.26 pp); no canonical-prompt advantage | **HELD** (scope q4, q8; greedy; τ² retail + airline) | 1 | `verify/out/v04_pooled_draws.json` `canonical_legacy_vs_a6k2`, `null_draw_sd`; `out/s07_flavour_outcome.json` |
| (r1) horizon amplification | 1 − ∏(1 − p_s) grows with horizon | rejected (obvious) | 1 | `docs/insights/iter_1_candidates.md#rejected-or-merged-carried-from-round-1` |
| (r1) open-loop ≠ closed-loop | open-loop fidelity does not predict closed-loop outcomes | merged into I2/P2b (occupied) | 1 | same |
| (r1) calibration data irrelevant at W4 | calibration draws are exchangeable | subsumed by I3 | 1 | same |
| (r1) CLOQ occupancy repair; loop attribution | method claim; engineering fact | killed (method falsified; engineering) | 1 | same; `docs/RESEARCH_LOG.md` V3 |
| (r1) token inflation (T2), false success (T4) | — | not insights; T2 is used as the P2e process channel | 1 | same |

## Requested experiments and analyses

Candidate ids (E*) follow `docs/insights/EXPERIMENTS.md`; verifier ids are V1-*.

| id | what | serves | status | evidence |
|---|---|---|---|---|
| E2 | a6k2 rerun under `TORCHINDUCTOR_DETERMINISTIC=1` plus canary; det pairs per model | all | running. q4 det pair and q30a3 det pair are verified byte-identical | `verify/out/v02_a6k2_det.json` |
| E4 | analyses a–f on legacy and a6k2 | I1–I4 | a done; the verifier did b (clean pairs via a6k2), c (partly: terminations), d (null SD vs Bernoulli) and f (partly: P4e pilot) | `verify/v01`–`v04` |
| E5 | numerics-flavour + weight-only nulls | P1c, P4c | **revise per V1-A3**: legacy-vs-a6k2 also changes the user simulator; `bf16_eager` is the agent-only null | `verify/out/v02_a6k2_det.json` `decision0_prompt_mismatch` |
| E3 | open-loop D per cell on its own server | I3, P2b | proposed; now also needed for the q8 RTN-W4 threat | `EXPERIMENTS.md` E3 |
| E7 | Marlin det pairs for q8 awq/gptq | P1c per format | proposed | `iter_1_candidates.md` §Experiments |
| E6 | extra seeds at k = 0.3 and k = 1 | P2d | deferred | `EXPERIMENTS.md` E6 |
| V1-A1 | per-decision hazard with CI as the I1 metric | I1 | proposed (0 GPU-h) | `verify/v01_legacy_recompute.py` |
| V1-A2 | pooled P2a Δ with a task-cluster bootstrap, leave-one-out for null members | I2 | implemented | `verify/v03_outcomes_pooled.py` |
| V1-A3 | E5 relabel; add `bf16_eager` for q14, q30a3 and q32 | I1-P1c, I4 | proposed (≈0.3 GPU-h per model) | `verify/out/v02_a6k2_det.json` |
| V1-A4 | annotate first divergences as write / read / text and whether they are undone; write-flip rate as the P2b predictor | I2 | proposed (0 GPU-h) | `analysis/strategy_v2_workflow/mechanism/a567.out` Q7 |
| V1-A5 | cell-only win rate against the null band as the P4e statistic | I4 | proposed (0 GPU-h); pilot positive on legacy, not yet on clean W3 | `verify/out/v03_outcomes_pooled{,_a6k2}.json` |
| V1-E1 | prioritise a6k2 q8 rtn_w4 ×2, gauss1 ×2, awq_w4 ×2, gptq_w4 ×4, then E3 on them | I3 | proposed (in matrix) | `verify/out/v04_pooled_draws.json` `q8` |
| V1-E2 | finish a6k2 q4/q8 damage cells (gauss3, rtn_w3, gptq_w3) before other models' tails | I2 | proposed (in matrix) | `verify/out/v03_outcomes_pooled_a6k2.json` |

## Open questions for survey

Full wording is in `docs/insights/SURVEY.md#open-questions-for-survey`.
- **V1-Q1.** Is the user simulator's serving numerics a known perturbation in agent benchmarks?
- **V1-Q2.** Any prior report of a divergence-hazard floor at the log-prob resolution?
- **V1-Q3.** Does RTN carry damage beyond its logit shift, compared with GPTQ/AWQ at matched output-KL?
- **V1-Q4.** Published agent recovery rates after a wrong tool call?
- **V1-Q5.** Compiler/autotune-level numerics effects on agent trajectories or scores?
- **V1-Q6.** Decisions per episode against a noise null; matched-KL quantizer comparisons in agents.
- Carried over: full text of Acharyya and Koobs & Koning; full text of AgentDiff; lead 2606.02965.

## Data snapshot

data snapshot: 2026-09-29T02:36Z.
- runs/a6000_*: 54/112 run-domains completed (legacy flavour-mixed; q4 bf16 + nulls clean).
- runs/a6k2_*: 51/109 run-domains completed (q4 near complete; q8 partial; q14, q30a3 and q32 only cal/det).
- 4080 raw runs: **not present** (`data-4080` not unpacked). 4080 numbers were checked against `analysis/strategy_v2_workflow/mechanism/*.out` only.
