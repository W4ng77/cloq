<!--
TL;DR: maps every number in paper/perturbation-equivalence-closed-loop.md to a source file (path + field/section).
Paths are relative to the repo root /data/ziyangs/cloq. "verdicts" = docs/insights/iter_1_verdicts.md; "candidates" = docs/insights/iter_1_candidates.md.
Primary machine-readable outputs behind the verdicts are named where the verdicts cite them (analysis/insights/iter_1/verify/out/*.json, analysis/insights/iter_1/out/*.json).
-->

# Provenance: Perturbation Equivalence in Closed-Loop Agents (draft of 2026-09-28)

Status labels: **HELD** (stated plainly), **TENT** (tentative / hypothesis, stated conditionally), **RISK** (open question), **SETUP** (configuration fact), **LIT** (literature claim).

## Abstract and §1 Introduction

| Number in draft | Source | Field / section | Status |
|---|---|---|---|
| 85 tasks (58 retail + 27 airline) | analysis/coling/RESULTS.md | §1 ("25/58 retail + 12/27 airline = 37/85") | SETUP |
| serving numerics move canonical score 6–8 points; q4 0.412 → 0.329; q8 0.316 → 0.380; 21/85, 21/79 | verdicts | §I4 "Legacy → a6k2 canonical BF16" ← verify/out/v04_pooled_draws.json `*.canonical_legacy_vs_a6k2` | HELD (I4a) |
| "about a quarter" of task outcomes (25%, 27%) | verdicts | same | HELD |
| +0.121 (12-point) v0 gain; 58 retail tasks; 8 vs 1 discordant; one-sided p = 0.0195 | analysis/coling/RESULTS.md | §2 table and text (observed diff +0.1207; binomtest 0.01953) | HELD |
| −0.035 pooled replication, three draws | analysis/v1/FINDINGS_V1.md | §5 ("−0.035 pooled and −0.045 on long tasks") | HELD |
| divergence floor, RTN-W4 error scale, damage near 3-bit (abstract) | verdicts | §I1 table; §I2 table | I1 HELD-level q4; I2 TENT |
| 95% of trajectories re-rolled by autotune choice; 113 identical-prompt decisions | candidates §I1 Evidence (KM ≤ 12 = 0.95); docs/RESEARCH_LOG.md W3 ("20/20 tasks and 113/113 identical-prompt decisions shift") | — | HELD (described) |
| 257/257, 303/303 | docs/RESEARCH_LOG.md | W3 "Fix verified"; verdicts §I1 P1c ← verify/out/v02_a6k2_det.json | HELD |
| 18 GPTQ checkpoints, six strategies | analysis/v1/FINDINGS_V1.md §2; analysis/coling/RESULTS.md §1 | — | HELD |

## §2 Related Work (all LIT)

| Number | Source | Field / section |
|---|---|---|
| ACBench: 15 models; tool use −1–3%; real-world −10–15%; T = 0, one run | docs/insights/SURVEY.md T1 (ACBench); analysis/coling/RELATED_WORK.md item 1 |
| Flat Score: 4 trials/task; TOST ±7.5 pt from one repeat run; up to 2.5×; ~17 pt re-exposed; "token log-probabilities are not in our logs" | docs/insights/SURVEY.md T1 (Flat Score); survey_sweeps/margins_flips_divergence.md §B; survey_sweeps/equivalence_null_criteria.md §1 |
| tau2 #540: 7–8 pt retail / 10–11 pt airline | docs/insights/SURVEY.md T5; survey_sweeps/equivalence_null_criteria.md §Other entries |
| Bjarnason: 2.2–6.0 pp at T = 0 | docs/insights/SURVEY.md T5; survey_sweeps/compressed_agents_eval_noise.md §Flags(b) |
| Noise Floor Audit: 11–58× rerun SD; excludes multi-turn agents | docs/insights/SURVEY.md T4; analysis/coling/RELATED_WORK.md Corrections |
| Singh: churn ≈ 5× net delta; declared ±2 pt TOST | docs/insights/SURVEY.md T4; survey_sweeps/equivalence_null_criteria.md §4 |
| Replay Gap: FP8 control forks > 90%, AWQ nearly identical | docs/insights/SURVEY.md T1; survey_sweeps/margins_flips_divergence.md row 22 |
| Du et al.: 49–100% of prompts; Eq. 14 $P(\text{flip}) \lesssim P(\Delta_t<\sigma_z)$ | docs/insights/SURVEY.md T2; survey_sweeps/margins_flips_divergence.md §A |
| Integer Alibi: AUC 0.942 | docs/insights/SURVEY.md T2; survey_sweeps/margins_flips_divergence.md §D |
| Patodiya: 36.2% (16-bit), 75.0% (4-bit), 3.5% per turn vs 36.2% per episode | docs/insights/SURVEY.md T1; survey_sweeps/margins_flips_divergence.md §C |
| Table 2 entries | same sources as above; "This work" row from scripts/a6000/make_tasks.py (NONCES ×5; seeds s1,s2; 2 nonces per quantized cell) |

## §3 Framework

| Item | Source | Field / section | Status |
|---|---|---|---|
| per-step model $P(\text{flip}) \approx P(d<-m)$ | candidates §"What we inherit"; Du Eq. 14 | — | LIT (inherited) |
| composition $1-\prod(1-p_s)$, $p_s = 1-\prod_j P(d_j \ge -m_j)$ | candidates §I1 Mechanism (i) | — | framework |
| bf16 log-prob resolution ≈ 0.125 nats | verdicts §I1 rewritten statement | — | HELD-level q4 |
| P1/P2/P3 statements | docs/COLING_PLAN.md §2; verdicts §I1 v2, §I2 v2, §I3 | — | I1 REVISE→v2; I2 HYPOTHESIS; I3 HYPOTHESIS at risk |
| null family (nonce, gauss k = 0.03, eager) | candidates §I4 P4c, E5 contents; verdicts V1-A3 | — | framework |
| nonce = session-identifier line | candidates §Changes after discussion ("a 'Session ID' line; cloq/agent.py L93–96") | — | SETUP |
| Bernoulli SD formula | candidates §I4 Mechanism | — | framework |
| MDE ≈ 3.4 pp | candidates §I2 P2a | — | pre-registered |

## §4 Setup (SETUP)

| Item | Source |
|---|---|
| 32k harness; max-model-len 33,792; `CLOQ_MAX_PROMPT_TOKENS=32768`; greedy; `VLLM_BATCH_INVARIANT=1`, `VLLM_USE_FLASHINFER_SAMPLER=0` | docs/A6000_PLAN.md lines 17–18 |
| `TORCHINDUCTOR_DETERMINISTIC=1`; canary at every start | docs/RESEARCH_LOG.md W3 |
| model ids, revisions, parser, thinking disabled for q8/q14/q32, TP=2 for q30a3/q32 | scripts/a6000/models.json |
| simulator = q30a3 BF16 | scripts/a6000/noderunner.py (`--sim-model` default q30a3); analysis/determinism/canary_sim_q30a3.json; docs/A6000_PLAN.md line 63 |
| Gaussian definition $\lVert N\rVert_F = k\lVert\mathrm{RTN}_{W4}(W)-W\rVert_F$; embeddings/lm_head/norms/routers BF16 | cloq/compress.py lines 10–13, 75–78, 140 |
| k ∈ {0.03, 0.1, 0.3, 1, 3}; seeds s1,s2; 5 nonces; RTN W8/W4/W3 ×2 nonces; GPTQ W4 d1/d2, AWQ W4, GPTQ W3 ×2 nonces; eager; s3–s5 at k=0.03; det pairs node005/node004 | scripts/a6000/make_tasks.py lines 18–19, 37–53, 59–66, 85–106; candidates §E5 contents (q4, q8) |
| 20 det tasks | verdicts §I1 confound 4 ("11/20 det tasks"); candidates §I1 Evidence ("over 20 tasks") |
| 51/109 a6k2 run-domains; 54/112 legacy | docs/insights/LEDGER.md §Data snapshot; verdicts §Data snapshot |
| legacy flavour-mixed; only q4 bf16 + nonce nulls share a flavour | candidates §Data status |
| E3: 400 decisions, 33,836 tokens, ref a6k2_q4_bf16 | analysis/openloop/a6k2/q4/rtn_w4.json `n_decisions`, `n_tokens`, `ref_runs` |
| 4B study: 2×RTX 4080; 8k harness; simulator = same 4B | analysis/v1/FINDINGS_V1.md header; analysis/coling/RESULTS.md §6 |
| NVLink-pair restriction | docs/RESEARCH_LOG.md W4 |

## §5.1 P1

| Number | Source | Field | Status |
|---|---|---|---|
| episodes ≈ 12 decisions | verdicts §I1 ("runs/a6000_q4_bf16/retail/metrics.json mean_decisions 12.0") | — | fact |
| KM P(≤12) ≥ 0.96 for eager..W8 (clean q4) | verdicts §I1 clean table | verify/out/v01_legacy_recompute_a6k2.json `A_divergence` | HELD-level q4 |
| Table 3a (all rows: 0.125/0.17 [0.15,0.20]/0.96; 0.18–0.23/0.97–1.0; 0.21/0.23; 0.25/0.25–0.27/0.98–1.0; 0.28/0.29; 0.5/0.42/0.45 [0.35–0.55]; 1.75–2.0/0.73/0.78; 2.0–2.1/0.77/0.99; ≥2.6/1.0) | verdicts §I1 table | verify/out/v01_legacy_recompute_a6k2.json `A_divergence.*.hazard_per_decision` | HELD-level q4 |
| floor 0.17–0.23 (q4); 0.11–0.14 (q8); ~2× per decade of k up to 0.3 | verdicts §I1 | — | q4 HELD-level; q8 consistent |
| legacy q4: 0.18 [0.14,0.24]; 0.19–0.20; 0.39–0.42; 0.78–0.98 | verdicts §I1 | verify/out/v01_legacy_recompute.json | legacy |
| legacy q8: 0.12–0.14; nonce 0.21; 0.29–0.34; GPTQ 0.41–0.46; AWQ 0.51–0.56 | verdicts §I1 | same | legacy |
| q8 partial clean 79 tasks | verdicts §I1 Scope | — | — |
| clean q8 k=0.03 s1 KM 0.84 [0.75,0.93]; 0.85 target; 0.7 line | verdicts §I1 P1a | verify/out/v01_legacy_recompute_a6k2.json | TENT |
| text median min-margin 0.0 (q4,q30a3), 0.125–0.25 (q8,q14); 2.7–6.0 tokens < 0.5; tool 4.25–7.75; 0.06–0.65 | candidates §I1 Evidence "Two-tier margins in 4 models" | analysis/insights/iter_1/out/s03_margin_predictions.json `models.*.margins` | legacy BF16 runs |
| text 0.22–0.53, tool 0.02–0.08 at δ ≤ 0.1 (q4,q8) | verdicts §I1 rewritten statement | — | HELD-level q4 |
| ratio 5.8/5.7 (q4), 6.4/11.3 (q8) at k=0.3 | verdicts §I1 P1b | verify/out/v01_legacy_recompute_a6k2.json `B_flip_by_kind.*.text_over_tool` | clean |
| 72–82 of 77–85 wording/format | candidates §I1; verdicts §I1 recomputed | out/s02_trajectory_divergence_q4.json `first_div_type` | legacy |
| 257/257 (q4 pair), 303/303 (q30a3), 257/257 (bf16 vs det_b), 0 flips, 0/20 divergences | verdicts §I1 P1c | verify/out/v02_a6k2_det.json | HELD |
| eager vs compiled median \|d\| 0.125, KM 0.96 | verdicts §I1 P1c D≠0 arm | verify/out/v01_legacy_recompute_a6k2.json `a6k2_q4_bf16_eager` | clean |
| KM P(≤4) 0.54–0.69 → 0.78–0.79 | verdicts §I1 P1a | same | clean q4 |
| falsification lines 0.7 and 0.3 | candidates §I1 P1a | — | pre-registered |

## §5.2 P2

| Number | Source | Field | Status |
|---|---|---|---|
| pooled null of 10 draws | verdicts §I2 "New evidence" | verify/out/v04_pooled_draws.json `q4.families` | TENT |
| Table 4 (all rows incl. draws, Δ, CIs, wins/losses) | verdicts §I2 table | verify/out/v04_pooled_draws.json `q4.families` | TENT |
| hazard 0.17 eager; −16 pp; −14 pp; ~1.5 decades | verdicts §I2 | — | TENT |
| pooled free zone −0.2 [−5.0,+4.5]; −0.7 [−6.1,+4.6]; +1.9 [−2.6,+6.4]; −3.5 [−9.6,+1.9]; 2–3 nulls | verdicts §I2 | verify/out/v03_outcomes_pooled{,_a6k2}.json `pooled_free_zone` | TENT |
| clean W3 −8.5 / −9.3 pp on 39 / 25 tasks | verdicts §I2; §V1-E2 | verify/out/v03_outcomes_pooled_a6k2.json | TENT |
| q8 W3 −3.9 [−13.9,+6.9]; tool flips 0.76–0.88 | verdicts §I2 confound 2 | — | TENT |
| 11 families (gauss0.03 anomaly) | verdicts §I2 confound 5 | — | open |
| tool flips 0.19–0.42 (RTN-W4), 0.23–0.92 (k=1); Δ ≈ −2 | verdicts §I2 "Where the statement is off" | verify/out/v01_legacy_recompute{,_a6k2}.json `B_flip_by_kind` | TENT |
| recovery 0.21–0.35 (Q action write) vs 0.40–0.80 (Q action read/lookup), BF16-solved tasks | analysis/strategy_v2_workflow/mechanism/a567.out Q7 "recovery by (BF16 action, Q action) at t_tool" (write: 0.214, 0.300, 0.346; read/lookup: 0.398, 0.677, 0.800) | — | 4080, analysis-file only. Replaces verdict wording 0.68/0.21 (verification pass 2026-09-28) |
| process channels 15.1/16.9 vs 12.0–12.3; premature 0.034/0.069 vs 0; repeated calls 0.236 vs 0.04–0.07; 11.1–12.9 | candidates §I2 table | out/s06_pilot_delta_q4_{retail,airline}.json | legacy |
| max_steps 7/33, 8/32 vs 0 | verdicts §I2 | verify/out/v03_outcomes_pooled.json `q4.cells.a6000_q4_rtn_w3_n*.terminations` | legacy |

## §5.3 P3

| Number | Source | Field | Status |
|---|---|---|---|
| AUC 0.79–0.97 | candidates §What we inherit | out/s01_token_flip_margin_{q4,q8}.json | replication |
| Table 5 (n, flip, abs_d_median per bin) | analysis/openloop/a6k2/q4/rtn_w4.json | `flip_by_bf16_margin.*.{n,flip,abs_d_median}` (0.5736, 0.5563, 0.4624, 0.3368, 0.1955, 0.0631, 0.00328; 0.6507, 0.5593, 0.4329, 0.2638, 0.1153, 0.01056, 0.0) | pilot fact |
| BF16 self-replay flip 0.0 all bins | analysis/openloop/a6k2/q4/bf16.json | `flip_by_bf16_margin.*.flip`, `flip_rate` | pilot fact |
| 6.4% tokens flip; 30.2% shifted; 60.8% decisions; 19.3% first token | rtn_w4.json | `flip_rate` 0.0644, `frac_tokens_shifted` 0.3019, `decision_any_flip` 0.6075, `first_token_flip_rate` 0.1925 | pilot fact |
| BF16 \|d\| p99 4.9e-5 | bf16.json | `abs_d_quantiles["0.99"]` 4.876e-05 | pilot fact |
| RTN-W4 open-loop median 1.3e-6, p90 0.29, p99 3.76 | rtn_w4.json | `abs_d_quantiles` | pilot fact |
| closed-loop 1.75–2.0 (RTN-W4) | verdicts §I1 table | — | clean |
| q8 floor 0.11–0.14 vs ~0.2 | verdicts §I1 | — | — |
| pre-registered q14 0.25/0.77/0.99, q30a3 0.35/0.61/1.00 at k=0.3; ±0.15; under-prediction 0.1–0.15 | candidates §I3 P3c and Evidence | out/s03_margin_predictions.json `models.*.pred` | prediction |
| q4 = q8 median \|d\| 0.125/0.25/0.5 | verdicts §I3 | verify/out/v01_legacy_recompute_a6k2.json | clean, 2 models |
| 1.5× (P3a) | candidates §I3 P3a | — | prediction |
| q8 placement: GPTQ 0.75 (2.0–2.25); AWQ 1.5 (3.5); RTN 1.5 (4.1–4.25); k=1 1.625–1.75 (4.6–4.75); tool flips 0.38–0.41, 0.39–0.44, 0.35–0.41 | verdicts §I3 recomputed; candidates §I2/§I3 tables | verify/out/v01_legacy_recompute.json `B_flip_by_kind` | legacy |
| q8 RTN-W4 −10.5 [−17.3,−4.0], 7/25; k=1 0.0 [−7.2,+7.7]; AWQ +1.6 [−7.4,+10.7]; GPTQ −0.5 [−6.7,+5.6] | verdicts §I3 Threat | verify/out/v04_pooled_draws.json `q8.families` | RISK |
| q4 RTN-W4 −2.0 vs k=1 −2.3 | verdicts §I3 | same `q4.families` | TENT |

## §5.4 Consequences

| Number | Source | Field | Status |
|---|---|---|---|
| q4 0.412→0.329 (−8.2 pp, 21/85 = 25%, p = 0.19); q8 0.316→0.380 (+6.4, 21/79 = 27%, p = 0.38) | verdicts §I4a | verify/out/v04_pooled_draws.json `*.canonical_legacy_vs_a6k2` | HELD |
| simulator first message differs 11/20 | verdicts §I1 confound 4 | verify/out/v02_a6k2_det.json `decision0_prompt_mismatch` | fact |
| 4/20 (0.45 vs 0.55) | verdicts §I4 | out/s07_flavour_outcome.json | HELD |
| 11/69 = 16% eager vs compiled | verdicts §I4a | verify/out/v03_outcomes_pooled_a6k2.json `a6k2_q4_bf16_eager.mcnemar_vs_bf16` | HELD |
| null SD 2.9 vs 3.2 (6 draws); 3.75 vs 3.26 (4 draws); ratios 0.9, 1.15 | verdicts §I4a | verify/out/v04_pooled_draws.json `null_draw_sd`, `bernoulli_sd_run` | HELD |
| canonical +1.8 [−2.9,+6.6]; +1.9 [−3.0,+6.8] | verdicts §I4a | same `families["null:bf16"]` | HELD |
| naive McNemar p = 0.021; Δ −8.3 [−16.3, 0.0] | verdicts §I4 P4d | verify/out/v03_outcomes_pooled.json `q4.cells.a6000_q4_gauss0.3_s1` | pilot |
| cell-only wins 0/10, 0/8, 0/4, 0/7; 4–7 per 72; clean 3 vs 4, 3 vs 3 on 39/25 | verdicts §I4 P4e | same `mcnemar_vs_bf16`; verify/out/v03_outcomes_pooled_a6k2.json | pilot (not clean) |
| 0.271–0.424 pooled; BF16 0.376; long 0.054–0.270 vs 0.297; RTN 0.271 | analysis/coling/RESULTS.md §1 | out/01_checkpoint_success.json | HELD |
| arm perm p 0.683/0.368; draw perm 0.881/0.744 | analysis/coling/RESULTS.md §1; docs/PROGRESS_2026-09-28.md §2 | — | HELD |
| all arm-vs-arm CIs cross zero | analysis/v1/FINDINGS_V1.md §2 | crossed bootstrap table | HELD |
| FP-Traj long 0.054 → 0.243 | analysis/v1/FINDINGS_V1.md §6 | — | HELD |
| Spearman −0.124 (mean-of-ratios) / +0.054 (token-weighted); \|ρ\| ≤ 0.13 | analysis/coling/RESULTS.md §3 | — | HELD; **sign conflict flagged in source** |
| best NLL 0.0769; tool-call agreement 0.840; long SR 0.117 | analysis/v1/FINDINGS_V1.md §7 table (CLOQ-Novel) | — | HELD |
| AUC 0.93; 0.548 / 0.538 | docs/PROGRESS_2026-09-28.md §2 | — | HELD (4080, analysis-file) |
| 0.844 vs 0.292 | candidates §I1 "4080 W4 analogue" | analysis/strategy_v2_workflow/mechanism/a4.out (a) | 4080, raw-run check pending |
| arm × failure p = 0.94 | docs/PROGRESS_2026-09-28.md §2 | — | HELD |
| 150 premature; 36.7 / 35.3 / 20.0 / 8.0%; ≤ 0.009 (0.0088) | analysis/coling/RESULTS.md §4 | out/04_loop_attribution.json | HELD |
| net loss 0.044 [−0.038, 0.126]; churn 0.261; share 0.008 vs 0.490; gain rate 166/954 = 0.174 | candidates §I2 "4080 analogue", §I4 "4080"; verdicts header (checked against mechanism/*.out) | analysis/strategy_v2_workflow/mechanism/churn.out | 4080, analysis-file |
| "raw runs not on the current cluster" | docs/insights/LEDGER.md §Data snapshot | — | caveat |

## §6 Robustness

| Number | Source | Field | Status |
|---|---|---|---|
| Table 6 (all values) | docs/PROGRESS_2026-09-28.md | §2 table | HELD |
| +0.01–0.04; MatchedAlt above BF16 under both | docs/PROGRESS_2026-09-28.md §2; docs/RESEARCH_LOG.md V4 | — | HELD |
| strict budget ≤ 2 errors changes Δ ≤ 1.7 pp | verdicts §I2 confound 3; candidates §I2 ("at most 0.017") | out/s06_* | legacy pilot |
| 20/20 tasks, 113/113 decisions; R0_BLOCK 2048 vs 4096; node006 30/30; eager third flavour | docs/RESEARCH_LOG.md W3 | analysis/determinism/probe_q4.json; analysis/insights/iter_1/out/s04_node_floor.json | fact |
| median \|d\| 0.125; 59% tokens non-zero; KM 0.50/0.95; 4/20; p = 0.63 | candidates §I1 Evidence | out/s04_node_floor.json; out/s07_flavour_outcome.json | legacy fact |

## §7, Limitations, Appendices

| Number | Source |
|---|---|
| "about 3 points" run-level SE | verdicts §I4a (Bernoulli SD 3.2 / 3.26 pp; 2.8 pt pooled in §I4 recomputed) |
| 3.4 pp | candidates §I2 P2a |
| 0.68 vs 0.21 (open questions) | see §5.2 row |
| +5.1 pp | verdicts §I2 table |
| false-flag rate ≈ 1/3 | candidates §Changes after discussion (P2a restated) |
| [0.5, 2] band; 20 df | candidates §I4 P4a |
| 100,000 draws; p = 0.01953; two-sided 0.0389 | analysis/coling/RESULTS.md §2 |
| env flags, 33,792, 32768 | docs/A6000_PLAN.md lines 17–18 |
| calibration mapping d1→c1, d2→c2, awq/gptq_w3→c1, arm fp_traj | scripts/a6000/make_tasks.py lines 45–53 |
| Sources appendix URLs | analysis/insights/references_new.bib `url` fields; analysis/coling/references.bib; docs/insights/SURVEY.md (IFFC 2608.22472, Qamar 2609.07664, Lunardi 2509.04013, Sinha 2509.09677, tau2 #540); analysis/coling/RELATED_WORK.md (Wang 2605.00066, Kapoor 2407.01502, Zhu 2507.02825) |

## Source conflicts found while drafting

1. **v0 one-sided p.** Memo value 0.035 vs recomputed 0.0195 (analysis/coling/RESULTS.md §2, §7). Draft uses 0.0195, per docs/PROGRESS_2026-09-28.md §3.
2. **v0 replication.** −0.035 (three draws pooled, both domains; FINDINGS_V1 §5) vs −0.0862 (retail, draw c1 only; RESULTS §2). Draft uses −0.035 and names the design.
3. **NLL–success correlation sign.** −0.124 (mean-of-ratios) vs +0.054 (token-weighted) (RESULTS §3). Draft reports both; the convention must be fixed before submission (PROGRESS §3).
4. **Recovery after flips.** Verdicts: 0.68 after read/lookup vs 0.21 after write. Candidates: 0.677–1.0 after text-only vs 0.214–0.346 after write. Draft uses the verdict wording and marks it as analysis-file only.
5. **Shift under the autotune incident.** RESEARCH_LOG W3 says "every token shifted"; candidates report non-zero shifts on 59% of tokens. Draft avoids "every token" and states 113/113 decisions and 59% of tokens.
6. **Pooled Bernoulli SD.** Candidates ≈ 2.6 pt; verdicts correct it to 2.8 pt. Draft uses the verdict values (3.2 / 3.26 predicted per model).
7. **"BF16 self-replay D = 0" (outline).** bf16.json shows zero flips but non-zero shifts (median 2.4e-7, p99 4.9e-5). Draft states "no flips, shifts ≤ 4.9e-5 at p99", not D = 0.
8. **Definition of |d|.** Closed-loop median |d| (s01/v01; bf16 grid, identical-context unflipped tokens) and E3 open-loop |d| (all tokens) differ by orders of magnitude for q4 RTN-W4 (1.75–2.0 vs 1.3e-6). Draft flags them as not comparable.
9. **Number of models.** docs/COLING_PLAN.md and PROGRESS §4 say 6 models; the outline and scripts/a6000/models.json main set say 5 Qwen3 models (m24 is a fallback). Draft uses 5.
10. **Simulator.** Main A6000 matrix uses a q30a3 simulator; the 4B deep dive (4080) used the same 4B model as simulator with an 8k harness (RESULTS §6). Draft keeps them separate.
