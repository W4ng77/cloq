**TL;DR** v5 fixes most of what the v4 review flagged. "c follows method", "20–40% / 5–10×", the p̄ prediction and the 0.86 mis-citation are gone. The turnover claim now sits on a gated snapshot with a floor, a hierarchical bootstrap and Holm. That is a real improvement.

The new central claim goes further than the data, though. It says a quantized checkpoint is a reproducible behavioural variant, unlike size-matched random perturbations, nonces and sampling. On this snapshot, half of that claim is already contradicted by the team's own data, and the other half is weaker than v5 says.

1. **The fingerprint does not separate quantizers from random perturbations.** Fixed random perturbations of W4 size (gauss1_s1_fixed, gshape_w4, rtnsign_w4) have the same fingerprint as quantizers: same-minus-different cosine 0.44 vs 0.50. About half of F (0.44 → 0.22–0.25 when draw A and draw B use disjoint task halves) is only the same tasks being reproduced, which any fixed function under deterministic greedy decoding does.
2. **Coherence (φ) is weaker than stated.** For production W4 quantizers it is not significant (φ 2.14, p 0.087). It is absent on q8 and q30a3, only in retail (retail φ 3.81, p 0.0005; airline 1.07, p 0.43), and it hinges on one checkpoint: stochastic-rounding RTN, at 1.41× dose. Counted as a quantizer, the quantizer class gives φ 3.47 (p 0.0025) and matched random gives −0.58 (df 6). Counted as random, the two classes are 2.14 vs 2.10.
3. **Conformal testing is not load-bearing.** None of F1–F7 uses a conformal p-value, and the "Level 2" definition is not the test that was run.
4. **The queued sampling baseline cannot answer its question.** vLLM re-seeds every request with the same seed, so a "sampling seed" is a fixed perturbation. Each seed is also confounded 1:1 with a nonce.
5. **Nothing is confirmatory yet.** The cleanest evidence is the recalibration lottery (7 same-method pairs, φ 4.65, p 0.013, exploratory; 2 of the 7 pairs are nonce-stratum-confounded). All W19 cells are still in `todo`, so a pre-registration written today makes them a genuine confirmatory test.

Score as-is: **2.5 / 5** (soundness 2.5, excitement 3; confidence 4). Projected: **3.5**, if the paper is reframed around the checkpoint lottery and pre-registered E4-3 confirms it. **4** if a clean held-out task set and a working sampling/deployment check are added as well. **≤ 3** if the title and abstract keep "unlike Gaussian noise" and E4-4 comes back ambiguous, which is the likely outcome at df 6.

# Review of Storyline v5 (ARR Oct 2026 → NAACL): central claim, tests, queued experiments

Role: ARR reviewer plus area chair, adversarial but constructive. Date 2026-09-29; freeze 10-05, deadline 10-12.

Object: `docs/insights/STORYLINE_v5.md`.

Checked against:
- `docs/insights/iter_3_stats_R3.md` and `analysis/insights/iter_3/out/r10_turnover_stats_live_20260929T1937Z.json` (W17);
- `docs/insights/iter_4_disposition.md`, `analysis/insights/iter_4/{common4,p1_overdispersion,p2_dispositions,p5_dose_scaling,h00_holm}.py` and `out/*_live_20260929T1937Z.{json,log}` (W18);
- `docs/RESEARCH_LOG.md` W17–W19;
- `scripts/a6000/make_tasks_iter4.py` and `make_tasks_e42.py` (W19/W20);
- `cloq/config.py`, `configs/{frozen_v1,draws_extra}.json`;
- `docs/insights/{SURVEY,iter_2_conformal,iter_2_integrity}.md`;
- the queue state (`/data/ziyangs/cloq_work/queue/todo`: every E4-3/E4-4/S task is still todo; only `a6k2_q4_olk_rtn_w4` is running).

**Checks this reviewer ran.** All were read-only on a scratchpad copy of `analysis/insights/iter_{2,3,4}`, on the gated snapshot 20260929T1937Z. The script is `/tmp/claude-1064/-home-ziyangs/4a7ccb09-009e-4aee-b4c9-ef93691bb496/scratchpad/ins/iter_4/rv5_checks.py` (plus a `_b` variant with stochastic-rounding RTN counted as a quantizer). It reuses `pairs`, `stats`, `perm_T` and `cos` from the team's own scripts. Numbers are tagged **[RV]**.
- (a) **Split-task fingerprint.** Draw A's shift is computed on a random half of the tasks (stratified by domain) and draw B's on the other half. The permutation is P2's.
- (b) F without the outcome-linked features (n_asst, max_steps, too_many_err, err_rate, notfound_rate).
- (c) Same-minus-different cosine per unit class (quantizer vs fixed random perturbation).
- (d) P1 φ by class, by nonce stratum and by domain, with the P1 within-task permutation (B = 2000).
- (e) On q4, the break-rate vs fix-rate correlation across W4 checkpoints.
- (f) The vLLM 0.29 sampler source in `/data/ziyangs/cloq_work/envs/cloq/lib/python3.12/site-packages/vllm/` (`v1/worker/gpu_model_runner.py:1291`, `v1/sample/ops/topk_topp_sampler.py:203-210`).
- (g) Web and arXiv novelty checks (Sources).

---

## Part 1: Structured review

## Summary

The paper studies Qwen3 agents (4B–32B) on τ²-bench retail+airline (85 dev tasks). It uses deterministic greedy serving and a fixed simulator, and judges each quantized checkpoint against the model's own perturbation null (8 prompt-nonce BF16 draws, stratum-matched).

v5 makes two moves. First, it keeps a floor-referenced turnover result: W4 re-rolls more tasks than function-preserving numerics, pooled excess about +0.15 to +0.19 and Holm-significant (F1). RTN re-rolls no more than random-sign error of its own magnitude (F2). Second, it promotes a new central claim: a quantized checkpoint is a "different, reproducible agent", not "the original agent plus noise". This rests on:
- a behavioural fingerprint that persists across nonces (F3: F = 0.44);
- a net effect that is overdispersed relative to independent task landing (F4: φ);
- the asserted contrast that nonces, matched Gaussian noise and sampling do not behave this way (F5/F6 are hypotheses, queued as W19).

Conformal/permutation testing "at two levels" is presented as the formal instrument, and an open-loop act-vs-talk probe is offered as a cheap diagnostic (F7, q4 only).

The science that currently holds up is narrower and still useful:
- (i) W4 turnover above a numerics floor;
- (ii) on q4 (and weakly q14/q32), same-dose checkpoints differ in net success more than independent landing predicts, and the cleanest evidence is same-method recalibration;
- (iii) each fixed checkpoint, quantized or random, has a reproducible agentic behaviour profile across prompt nonces.

The discriminating part of the headline ("unlike matched random perturbations and sampling") has not been shown. For the fingerprint it is contradicted by existing data.

## Strengths

- **[S1] The v4 statistical debt is paid.**
  - Gated snapshot (`snapshot_live_20260929T1937Z.json`; 417 scanned / 325 frozen).
  - Hierarchical paired bootstrap over tasks, null draws, checkpoints and draws; floor-referenced excess; TOST/NI with a declared ±0.10 margin; Holm over 14 declared tests (`r10_…json` `holm_family`).
  - Every v4 overclaim is explicitly retracted in the "Dropped from v4" row. This is unusually honest and will read well to an area chair.
- **[S2] F1 is solid and well scoped.** RTN +0.19 [0.10, 0.30], GPTQ +0.15 [0.07, 0.24], AWQ +0.16 [0.07, 0.25], Holm p 0.007/0.007/0.036, pooled over 5 models against a floor built from rot_bf16/null_K/gauss0.001/0.003.
- **[S3] P1's permutation null is well chosen for its purpose.** It permutes checkpoint labels within task, which preserves each task's fragility and nonce noise and destroys only cross-task coherence (`p1_overdispersion.py` docstring). It handles task-level heterogeneity correctly, and the nonce-null baseline (φ_U 0.36–1.19, no p < 0.31) is a fair "prompt re-rolls are independent" check.
- **[S4] The recalibration contrast is the most interesting new fact.**
  - Calibration draws differ only in the row-sampling seed over the same 57 contexts (`configs/frozen_v1.json` `calibration.row_sampling`).
  - Yet q4 GPTQ-W4 d1 vs d2 differ by +9.6 pp [1.8, 17.4] in net success (W17), and the draws reproduce across nonces: d1 +5.6/+6.8 pp, d2 −4.0/−5.2 pp (`p1_…json` `models.q4.units`).
  - Static-benchmark work reports calibration-seed spreads of about ±0.3–0.5 points in aggregate accuracy (see Sources, "Beyond Activation Alignment"). A ~10 pp sign-flipping spread in an agent is a publishable contrast, if it replicates.
- **[S5] The declared families are good practice.** DECLARED is copied into every output. P4 was amended before any P4 number existed and says so. Failures (P3, F1) are reported, not buried.
- **[S6] The fingerprint is robust to feature choice.**
  - Leave-one-feature-out F stays in 0.42–0.51.
  - [RV] Dropping all five outcome-linked features together still gives F = 0.38 (p 0.0005).
  - [RV] Computing A and B on disjoint task halves still gives F = 0.22 (p 0.0005; mean of 20 splits 0.25).
  - So there *is* a cross-task behavioural direction per checkpoint. It is just smaller than reported and not quantizer-specific (W2).

## Weaknesses

- **[W1] FATAL for the claim as worded: "Random perturbations of the same size … re-roll task outcomes independently; a quantized checkpoint shifts them coherently, with a persistent behavioural fingerprint." The data already in hand do not support the contrast.**
  - **Fingerprint.** Three fixed random perturbations of W4 size with ≥2 nonce draws sit inside P2's 48 units: gauss1_s1_fixed (q4/q8/q14), gshape_w4 and rtnsign_w4 (q4/q8/q14). Their same-checkpoint cosines are 0.985/0.903/0.781 (Gaussian), 0.922/0.805/0.979 (gshape) and 0.842/0.945/0.875 (rtnsign) (`p2_…json` `models.*.units.*.cos_AB`).
    - [RV] Class means of same − different: W4 quantizers 0.50 (n 26, stochastic-rounding RTN counted as a quantizer) vs fixed random 0.44 (n 9).
    - A fixed Gaussian seed is as much a "distinct, reproducible behavioural variant" as GPTQ.
  - **Coherence.** F5 cites "φ 0.43 at k = 1" from `p5_dose_scaling`. That statistic is different from P1's:
    - canonical-prompt cells, one draw per seed, no nonce correction ("noise included in both terms");
    - 2–4 seeds per model, 8 df pooled;
    - never compared with quantizer φ (`iter_4_disposition.md` X6: "the difference was not tested").
  - [RV] With P1's own statistic on the fixed random units, the answer depends on one checkpoint, q4 rtnsr_w4 (stochastic rounding, 1.41× RTN error, net −14.6/−12.2 pp):

    | classification of rtnsr_w4 | quantizer-class φ | random-class φ |
    |---|---|---|
    | counted as random | 2.14 (p 0.087, df 20) | 2.10 (p 0.23, df 7) |
    | counted as quantizer | 3.47 (p 0.0025, df 21) | −0.58 (p 0.84, df 6) |

    A claim whose truth flips with the label of a dose outlier is not established.
  - **"Same size" is also wrong for nonces.** Prompt nonces re-roll λ ≈ 0.02–0.12, while W4 re-rolls λ ≈ 0.25. They are not a size-matched perturbation, so "unlike prompt nonces" confounds kind with size.
  - **Fix.**
    - Restate C2 in its present evidential form: "every fixed weight perturbation of W4 size, quantized or random, is a reproducible behaviour profile; whether quantizers are *more coherent* than random perturbations is open".
    - Make the class contrast a declared difference test, with rtnsr handled by a pre-declared dose rule.
    - v5's own Risks line ("any fixed weight perturbation is a variant") is the current state of evidence, not a fallback.

- **[W2] MAJOR: the fingerprint F is partly mechanical, its nonce baseline is an artefact, and "reproducible variant" alone is not novel.**
  - **Half of F is per-task reproducibility.** Under greedy, batch-invariant decoding a fixed checkpoint re-plays most trajectories under a new nonce (nonce λ is small). Any per-task idiosyncratic deviation therefore reappears in draw B, and the mean shift vectors correlate with no cross-task "disposition" at all. P2 computes A and B on the same tasks, so it cannot tell the two apart.
    - [RV] Split-task F per model: q4 0.65 → 0.39, q8 0.27 → 0.16, q14 0.38 → 0.20, q30a3 0.43 → 0.20, q32 0.17 → 0.05. Pooled: 0.44 → 0.22 (p 0.0005).
    - Report the split-task version as the primary statistic.
  - **The nonce-null analogue is uninformative.** "Nonce-null analogue −0.13 to −0.23" is the cosine between leave-one-out shifts of U draws. By construction it has expectation ≈ −1/(n−1): −0.14 for |U| = 8 and −0.25 for |U| = 5 (q14 −0.229). It says nothing about whether nonces carry a fingerprint.
    - A symmetric nonce test would hold the nonce fixed and vary something else, e.g. n1 under bf16 vs rot_bf16/eager.
    - `iter_2_integrity.md:157` already found that a fixed prompt (canonical vs nonce) "creates its own task profile" (p_churn 0.0099). A fixed nonce is itself a variant.
  - **Prior work.** Behavioural distinguishability of quantized variants is established:
    - Dutta et al. 2024 (reproducible flips);
    - Model Equality Testing (Gao et al., ICLR 2025);
    - Stability Monitor / behavioural fingerprints (Leshin et al. 2026, arXiv 2603.19022; lists quantization among detected identity changes);
    - Logit Fingerprinting (Logan & Bumgardner, AMIA 2026; 100% FP-vs-quantized discrimination, NF4 flip rate 21%);
    - AgentProv (arXiv 2609.00052; tool-use probes catch silently quantized or substituted backbones, 630/630 pairs);
    - Illusion of Equivalency (arXiv 2607.08734).

    None of these is closed-loop with an own-null coherence test. But "a quantized agent is a different agent" as a headline will be read as known.

- **[W3] MAJOR: F4 ("coherent net effect, established on q4/q32") is overstated.**
  - The declared P1 primary (φ 4.61, p_holm 0.001) is dominated by W3 blocks: q30a3 φ 37.5 and q8 16.5, which are RTN-W3 vs GPTQ-W3, a method/dose gap. The team says so (X1).
  - The rows that bear on the claim are exploratory and uncorrected: no-W3 φ 2.29 (p 0.017), W4 2.46 (p 0.017), W4 production only 2.14 (**p 0.080**), recalibration pairs 4.65 (p 0.013, df 7).
  - **Per model.** q8 W4 φ −0.14 and q30a3 −0.84, i.e. no checkpoint variance. q14 1.42. q32 3.05 with J = 3, and its only permutation test (all groups) has **p 0.155**. "Established on q32" has no test behind it.
  - **[RV] Domain.** Pooled over all groups, retail φ 3.81 (p 0.0005) vs airline φ 1.07 (p 0.43, df 38). The coherence is a retail phenomenon. State it and test it within domain.
  - **Dose heterogeneity inside the W4 block.** The within-task permutation also erases *how many* tasks each checkpoint turns over. So a block that mixes λ 0.22 (MXFP4) with λ 0.42 (gshape) and 1.41× error (rtnsr) gives φ > 1 from dose spread alone. Leaving rtnsr out drops pooled W4 φ to 1.60 (`w4_leave_one_ckpt_out_phi`), and my approximate q4 production-only φ without GPTQ-d1 is about 2.2.
    - A cheap discriminator between "directional landing" and "amount heterogeneity" is the cross-checkpoint correlation of break rate and fix rate. Direction predicts negative; amount predicts positive. [RV] On q4 W4 (13 checkpoints): Pearson −0.59 (p 0.035), Spearman −0.50 (p 0.08); without rtnsr, −0.38 (n.s.). This weakly favours direction, but a margin-preserving null is needed (Revision Plan R4).
  - **Recalibration pairs.**
    - Tasks overlap with calibration: the 57 calibration-split contexts feed GPTQ/AWQ, but evaluation is on the 85 dev tasks. That part is fine.
    - The 2 AWQ pairs (q4, q8) compare d1 on nonces n1/n2 with d2 on q1/q2 (`p1_…json` units). The recalibration contrast there is nonce-stratum-confounded.
    - [RV] Across all W4 units, q-stratum φ 3.13 (p 0.017) and n-stratum 1.85 (p 0.19), so stratum is not the driver overall. It still has to be balanced in E4-3 (W6).

- **[W4] MAJOR: the conformal/exchangeability framing is not load-bearing as written.**
  - **None of F1–F7 uses a conformal p-value.** F1/F2 use the hierarchical bootstrap; F3/F4 use label permutations.
  - **Level 1 cannot reject per model.** The per-draw conformal p has resolution 1/(n+1) ≥ 0.11 with 8 null draws. A two-draw family's minimum p is 1/C(10,2) = 0.022, and ±5 pp equivalence was unreachable per model in iter 2 (`iter_2_conformal.md` TL;DR). "Finite-sample valid with 6–9 null draws" is true but mostly powerless.
  - **Level 2 as defined is not what F3/F4 test.** "Draws of a checkpoint exchangeable with draws from the null (nonce, Gaussian seed, sampling seed)" would need null draws in the same permutation. P1 permutes checkpoint labels within task among *quantized* checkpoints. P2 permutes draw-B labels among checkpoints of a block. Neither includes nonce, Gaussian or sampling draws as exchangeable comparators.
  - **The claimed advantage is not real.** "Stating them as conformal gives validity with few checkpoints" adds nothing: permutation tests are already exact under their exchangeability hypotheses.
  - **The theory ask cannot land by 10-12.** Stratified or weighted exchangeability and a hierarchical test with few units per level are a research programme. If the paper promises it, a reviewer will ask where it is.
  - **Where conformal is genuinely load-bearing.**
    - (i) The iter-2 draw-level task-profile test, "quantized runs are not exchangeable with nonce-null runs" (pooled churn, Holm p ≤ 0.007). This is exactly the "not a nonce re-roll" statement.
    - (ii) A conformal prediction interval for the *next* checkpoint's net Δ from J exchangeable recalibration checkpoints. With J = 4 per method, [min, max] is a 60% interval; J = 9 gives 80%. This quantifies the lottery directly and is honest about J.
  - **Recommendation.** Call F3/F4 permutation tests of exchangeability. Keep "conformal" for the draw-level acceptance test and the next-checkpoint interval, both in the protocol section, not the title.

- **[W5] MAJOR: the sampling baseline S (W19), as queued, cannot test F6.**
  - **A fixed seed is a fixed perturbation.** `cloq/config.py:51-57` sends one seed per request for the whole run. In vLLM 0.29 each request gets `torch.Generator().manual_seed(seed)` (`gpu_model_runner.py:1291`), and sampling draws `q.exponential_(generator)` over the full vocabulary at each step (`topk_topp_sampler.py:209-210`). So every request in a run gets *the identical noise vector at output position j*.
    - A "sampling seed" is therefore a fixed, task-independent perturbation of the decoder. At position 0 it is a fixed bias on the first token, i.e. exactly the act-vs-talk fork P4 identifies.
    - This deserves a one-line empirical check (two different prompts, same seed, compare the realised q), but the source is unambiguous.
    - Under this design sampling may well look like a "variant". It would then refute F6 through an artefact.
  - **Seed and nonce are confounded 1:1** (seed i ↔ nonce qi, `make_tasks_iter4.py:88-93`). No seed has two nonce draws, so seed-level persistence (P2) and coherence (P1) cannot be computed. At T level (3 runs per T), a systematic temperature effect would read as a "fingerprint".
  - **It also misses the deployment question.** The v4 review's R5 asked whether a quantized checkpoint's identity survives T > 0. "Does i.i.d. sampling look like i.i.d. noise" is close to true by construction.

- **[W6] MAJOR: nothing is confirmatory, and the W19 design has avoidable confounds and too little power.**
  - **Everything is exploratory or post hoc.**
    - The W17 and W18 families were declared after the team had seen ungated numbers (both documents say so).
    - `configs/frozen_v1.json` re-designates the 85 tasks as "development data, not final test data".
    - There is no test set: 85 dev + 57 calibration + 22 excluded = all 164 retail+airline tasks.
  - **All W19 cells are still in `queue/todo`.** A pre-registration committed now (sha in the manifest, as NR1 was) turns E4-3/E4-4 into confirmatory tests of new units. For checkpoint-level claims, new checkpoints *are* the right replication unit.
  - **E4-3 nonce stratum.** d3/d4 run on q1/q2, but d1/d2 (GPTQ, and AWQ d1) ran on n1/n2. The pooled recalibration family will mix strata unless d1/d2 get q1/q2 draws, or d3/d4 get n1/n2.
  - **E4-4 power.** Seeds s1, s2, s4, s5 × 2 nonces give J = 4 per model (df 3; df 6 over q4+q8). The permutation 95% quantile for φ at df ~7 is about 3.6 (`recal` row: `phi_perm_q95` 3.59). E4-4 can therefore only *fail to reject* for Gaussian. That is not evidence that Gaussian is incoherent, and not a test of quantizer > Gaussian. It needs a declared difference statistic (T_quant − T_rand under class-label permutation), J ≥ 6–8 per class on q4, or an equivalence bound on φ_rand.
  - **Comparator choice.** Isotropic Gaussian is the harsher control (r08: +0.14 λ over RTN; Kennedy & Kennedy's channel-energy account). gshape (per-group-RMS-matched) seeds are the apples-to-apples random comparator, and none is queued.
  - **Held-out tasks.**
    - The 57 calibration tasks are contaminated for GPTQ/AWQ (their BF16 contexts are the calibration states), as v5 notes.
    - The 22 excluded "unstable" tasks are in neither split, so they are clean, but they were selected for max_steps/looping in legacy BF16 (slow, W11).
    - Telecom is fully clean and was deprioritised by +30 in W19.
    - One option is to split the calibration pool for *new* draws: build d5/d6 from 28 of the 57 contexts and evaluate on the other 29.

- **[W7] MAJOR: F1's wording and floors.**
  - "Largest on small models" is false for RTN: the excess is +0.17 on q4/q8/q14/q30a3 and **+0.29 on q32** (`r10` Holm table). It is true only for GPTQ/AWQ (q4/q8 +0.20–0.31 vs q14/q30a3 −0.02 to +0.13).
  - The floors on q14/q30a3/q32 are a single null_K run each, with λ −0.02/−0.03 on q30a3/q32, which inflates the excess there (W17 caveat). Add rot_bf16 × 2 on q14/q32, or scope the per-model excess to q4/q8.

- **[W8] MINOR: definitions and scope creep.**
  - "Different agent", "variant", "disposition", "fingerprint" and "coherent" need operational definitions tied to P1/P2 statistics.
  - Under deterministic greedy decoding, "reproducible" is nearly automatic for any fixed function. Say what non-trivial property is claimed: cross-task direction (split-task F) and cross-task correlation of landing (φ).
  - The 12 features are heuristic (confirm regex, "not found" as a hallucination proxy). Name them as such.

- **[W9] MINOR: C4/F7 rests on ungated inputs and one model.** E3 outputs are not integrity-gated, and cells were being written during the analysis (`iter_4_disposition.md` caveats). P4 does not replicate on q8/q30a3 (partial ρ 0.00/0.15), and s_act does not predict net Δ. Keep it as an analysis paragraph until E4-1/E4-2 (W20) land on ≥2 more models.

- **[W10] MINOR: generality threats carried over from v4 (W9 there) are unchanged.**
  - No simulator swap. This matters more now: coherence could be simulator-mediated, since the user model reacts to agent wording.
  - Fake quantization with batch-invariant kernels.
  - Qwen-only (l8 has no runs).
  - Greedy only.

- **[W11] MINOR: related-work positioning for C3.** C3 ("recalibration moves net success by about 10 pp") must cite:
  - Williams & Aletras, ACL 2024 (calibration source *and seed* change downstream results);
  - Singh 2026 (the calibration draw reverses the GPTQ/AWQ order in 5/8 cells);
  - Hu & Ramachandran 2026 (GPTQ seed spread 4–24%, AWQ 0–2%).

  Hu & Ramachandran predicts that AWQ pairs should *not* show a lottery, so the AWQ pairs are a built-in check. The novelty is magnitude and sign-flipping in closed loop against an own null. It is not that calibration matters.

## Answers to the six questions

### 1. Does v5 fix the v4 issues?

| v4 item | v5 status | Evidence / residual |
|---|---|---|
| W1 "c follows method" | **Fixed (dropped).** Correctly replaced by "checkpoint lottery". | W17: c unidentified for RTN everywhere |
| W2 wrong floor, 20–40%/5–10× | **Fixed.** F1 is floor-referenced and Holm-corrected. | Residual: "largest on small models" is wrong for RTN; weak floors on q14/q30a3/q32 (W7) |
| W3 "λ follows size" | **Fixed** → F2, one-sided NI (rtnsign only survives Holm). | But a new overreach ("random perturbations re-roll independently", W1) replaces it |
| W4 λ–c as mechanism | **Fixed (λ–c demoted).** | — |
| W5 p̄ prediction | **Fixed (dropped).** | — |
| W6 ungated evidence | **Fixed for closed loop** (gated 1937Z). | E3 open loop is still ungated (F7) |
| W7 task filter / 57 unused | **Disclosed, not solved.** | Contamination is recognised; no clean split is scheduled (W6) |
| W8 multiplicity / post hoc | **Partly.** Declared families and Holm are in place. | The v5 headline rests on exploratory rows (W3); no pre-registration yet |
| W9 generality | **Partly.** A sampling baseline is queued. | It is mis-designed (W5); no simulator swap |
| W10 C1 positioning | **Not addressed.** | v5 does not mention Singh, Flat Score, Noise Floor Audit or Model Equality Testing |
| W11 queue scope | **Fixed** (KV/telecom deprioritised). | Reconsider telecom as the held-out set |
| W12 terminology | **Fixed** for λ ("turnover"). | New undefined terms (W8) |
| R1 checkpoint replication | **Queued** (E4-3, q4/q8, d3/d4). | Nonce-stratum imbalance; not pre-registered |
| R2 held-out confirmatory | **Open.** | — |
| R3/R4 floor + statistics | **Done well.** | — |
| R5 T > 0 | **Replaced by S.** | Design flaw (W5) |
| R6 simulator swap | **Not planned.** | — |

Net: v5 fixes 8 of 12 v4 weaknesses and 2 of the 4 highest-priority revision items (R3, R4). R1 is in flight. R2 and R6 are open.

### 2. Is the central claim novel, compelling and adequately tested?

- **Compelling.** Yes, as a question: "unchanged score" can hide either a re-roll or a systematically different agent. The recalibration result (S4) is the most striking evidence and should lead.
- **Novel.** Partly.
  - A quantized model being behaviourally distinguishable and reproducibly different is known (W2 list).
  - Calibration-draw sensitivity is known on static tasks (W11).
  - New and defensible:
    - (a) closed-loop, own-null, **cross-task coherence** of a checkpoint's net effect (φ vs independent landing);
    - (b) same-method recalibration flipping the *sign* of agent net success by about 10 pp, comparable to or larger than method gaps;
    - (c) an agentic behaviour profile (act vs talk, transfer, confirm) that holds across prompts and across disjoint task halves.
  - "Unlike matched random perturbations" would be the genuinely new mechanistic claim, and it is the one with no support (W1).
- **Adequately tested.** Not yet. Soundness issues by statistic:

| test | sound for | confounds / problems |
|---|---|---|
| φ (P1) | task heterogeneity (preserved by within-task permutation) | dose heterogeneity within block (rtnsr, gshape, NF4 λ 0.37–0.42); the W3 method gap in the primary; domain (retail only); df: recal 7, W4 30, per-model J = 3–13; the nonce stratum balanced overall [RV] but not in AWQ pairs or E4-3 |
| F (P2) | "a checkpoint reproduces its own mean shift across nonces" | about half is per-task reproducibility (split-task F halves it); the nonce baseline is a construction artefact; not specific to quantizers (random units identical); outcome-linked features (turns, max_steps) partly restate failure, though removing them keeps F 0.38 |
| infra | — | checkpoint-specific infra failures: infra-error episodes are dropped per task (complete case), context overflow counts as failure (W10), and both draws of a checkpoint usually run in one queue task on one node/simulator. Cross-node determinism pairs (257/257, 303/303) argue this is small. Still, report the node/simulator per draw and run one cross-node draw pair per class in E4-3 |
| max_steps looping | — | coherence could be "this checkpoint loops". Report φ with max_steps/too_many_errors episodes as a separate outcome class, or as missing, as a sensitivity |

### 3. Is the conformal/exchangeability role well founded and load-bearing?

No, not as written (W4). The two-level idea is sound in spirit: level 1 is run exchangeability with the null, and level 2 is exchangeability of checkpoint labels within a perturbation class. But:
- no current finding uses conformal inference;
- Level 2 is not what P1/P2 test;
- the per-model power is structurally tiny;
- the theory ask is not deliverable by 10-12.

To make it load-bearing, use:
- (i) the draw-level churn exchangeability test as the formal "not a nonce re-roll" statement;
- (ii) a single, clearly stated hierarchical permutation test per claim, where the class contrast (quantizer vs gshape seeds vs nonces) is the test statistic with a declared margin;
- (iii) a conformal next-checkpoint interval for Δ as the practitioner-facing lottery number.

Do not put "conformal" in the title.

### 4. Are the queued decisive experiments sufficient? What is missing?

| queued | decides | sufficient? | change |
|---|---|---|---|
| E4-3 GPTQ/AWQ d3/d4 × 2 nonces, q4/q8 | checkpoint lottery (C3; the strongest claim) | **Nearly.** The highest-value item. | Balance nonce strata: add d1/d2 (and AWQ d1) × q1/q2, about 12 runs over q4/q8. Pre-register φ_recal > 1 and the "next-checkpoint" interval. Expect no AWQ lottery (Hu & Ramachandran), so declare the prediction per method |
| E4-4 Gaussian k = 1 s2/s4/s5 × 2 nonces | quantizer vs random coherence (C2) | **No** (df 6 per class; can only fail to reject) | Declare a class-difference test. Add gshape seeds s2–s4 × 2 nonces on q4 (6 runs; the matched comparator). Target J ≥ 6 per class on q4. Pre-declare how rtnsr is classed (dose group "W4 × 1.41" → excluded) |
| S sampling q4 T ∈ {0.2, 0.5, 0.8} × 3 seeds | "sampling is not a variant" | **No** (fixed-seed artefact; seed ⊥ nonce confound) | Per-request seed = hash(run_seed, task, turn), or unseeded plus logged. At one T* (λ closest to W4 from a 1-run pilot), BF16 × 4 runs on nonce q1 + 2 on q2. Deployment-relevant: GPTQ-d1 and GPTQ-d2 × 3 runs each at T*. Does the lottery survive sampling? About 12–15 runs |
| E4-1 open loop on q8/q14/q30a3/q32; W20 top-20 open loop | C4/F7 replication | Fine; cheap, no simulator | Gate the E3 outputs (sha manifest) before analysis |
| — | **held-out tasks** | **Missing** | For checkpoint-level claims, the pre-registered new checkpoints are the confirmation. For task generalisation, one small pre-registered block on clean tasks: telecom (40-task subset) or the 22 excluded tasks. q4: BF16 × 4 nonces, GPTQ d1–d4 × 2, gshape s1–s3 × 2, RTN × 2 (about 20 runs). If capacity is short, state the limitation instead |
| — | **0 GPU-h analyses** | **Missing** | Split-task F as primary; class-specific φ/F; domain-stratified φ; break–fix correlation / margin-preserving null; bootstrap CIs for φ (or report the SD in pp); max_steps sensitivity; per-model tables in the main text including the q8/q30a3 nulls |

Deprioritise before any of the above: W20 top-20 on q14/q32, KV-cache and NF4/MXFP4 breadth.

### 5. Framing, title, abstract, Figure 1

**Title.** Lead with what is best supported and most actionable, and keep the "different agent" metaphor out of the title until W1 is resolved. Options:
- "Same Method, Different Agent: Calibration Draws, Not Quantizers, Decide What a 4-bit Agent Gains or Loses" (if E4-3 confirms);
- "Quantized LLM Agents Are Checkpoint Lotteries: Measuring Turnover and Coherence Against the Model's Own Noise";
- the neutral fallback "Re-Roll or Re-Wire? Separating Noise from Checkpoint Effects in Quantized LLM Agents".

**Abstract (what is supportable today, with brackets for pending results).**
> On τ²-bench, 4-bit weight quantization of Qwen3 agents re-rolls more task outcomes than function-preserving numeric changes do (pooled excess turnover +0.15–0.19 over 5 models). Its net effect, however, is a property of the individual checkpoint, not of the method. Checkpoints of the same method that differ only in their calibration sample reproduce opposite-signed net changes across prompt re-draws (e.g. +6 vs −5 pp on 4B), and same-dose checkpoints disagree more than independent task-level re-rolls predict. [Pre-registered replication on N new checkpoints: …]. Each fixed perturbation, quantized or random, also carries a reproducible agentic behaviour profile (act-vs-talk, transfers, confirmations) that holds across prompts and disjoint task sets. [Whether quantizers are more coherent than matched random perturbations: …]. Single-checkpoint, single-run comparisons of quantizers on agent benchmarks therefore do not identify the better method. We give a draw-level exchangeability protocol and the number of checkpoints and runs needed to do so.

**Figure 1 (recommended).** A q4 scatter of each checkpoint's net Δ under nonce draw A (x) against draw B (y), in pp vs the stratum-matched null. It shows reproducibility (on the diagonal) and the lottery (spread along it) in one panel, and it is honest about random controls.
- Points: quantizer checkpoints coloured by method, with same-method recalibration draws joined by a line; fixed random controls (gshape, rtnsign, Gaussian) as open markers; nonce-null LOO draws as grey dots.
- Band: shaded ±2 SD of the independent-landing expectation (sd_indep 2.0 pp).
- Inset: split-task fingerprint cosines by class.
- Right panel: a q4 task × checkpoint raster (breaks/fixes) for GPTQ-d1 vs GPTQ-d2 vs RTN, with the aggregate score bar barely moving.

### 6. ARR score

- **As-is: 2.5 / 5** (soundness 2.5, excitement 3, reproducibility 4; confidence 4/5). The infrastructure and statistics are better than most agent-evaluation papers. But the headline contrast is not supported and is partly contradicted in the team's own P2 units, and the rest is exploratory.
- **Projected, per scenario:**

| scenario | score |
|---|---|
| Pre-register now; E4-3 confirms φ_recal > 1 on new checkpoints (q4 at least); reframe to "checkpoint lottery + turnover above floor + behaviour profile"; split-task F; conformal scoped | **3.5** |
| The above, plus a clean held-out task block and the fixed sampling/deployment check | **4.0** |
| The above, plus a significant quantizer > gshape-seed coherence difference (pre-registered) | **4.0–4.5** (the "different agent" title becomes earned) |
| Keep v5's "unlike Gaussian noise" framing and E4-4 is ambiguous | **≤ 3.0** |

## Questions for authors

- [Q1] How is rtnsr_w4 classified, and what is the rule? It is a random-rounding quantizer at 1.41× RTN error, and the quantizer-vs-random conclusion flips on it [RV].
- [Q2] With per-request seeding, have you verified that two different prompts under the same seed receive the same exponential noise at position j? If so, is S a sampling baseline or a "fixed decoder perturbation" baseline?
- [Q3] Which nonces will d1/d2 and d3/d4 share in the pooled recalibration family? Can d1/d2 get q1/q2 draws before the freeze?
- [Q4] What is the declared test for "quantizer more coherent than random", and what is its power at J = 4–8 per class?
- [Q5] Why is coherence retail-only (airline φ 1.07)? Is it the 27-task airline set (power), or a domain effect such as policy-heavy airline tasks?
- [Q6] Were draws A and B of each checkpoint served by the same node and simulator instance? Can one cross-node pair per class be added?
- [Q7] Is telecom (or the 22 excluded tasks) runnable before 10-05 as a pre-registered held-out block, at what GPU-h?

## Verdict

- **Research judgement.** A strong measurement paper is available. It combines turnover above a numerics floor, a checkpoint lottery in closed loop that single-checkpoint comparisons cannot resolve, and a draw-level protocol. v5's storyline reaches past it to a mechanistic contrast ("structure decides coherence; unlike Gaussian, unlike sampling"). The existing data do not support that contrast for the fingerprint, and are ambiguous for coherence. The queued tests are either mis-designed (S) or underpowered to decide it (E4-4).
- **Revision priority.**
  1. Pre-register today, before any W19 data land.
  2. Fix the S design and the E4-3 nonce balance before those tasks start.
  3. Run the 0 GPU-h reviewer analyses (split-task F, class φ/F, domain, break–fix).
  4. Reframe title and abstract to the lottery.
  5. Add a held-out block if capacity allows.
- **Confidence.** 4/5. I re-ran the key statistics on the gated snapshot, and the vLLM seeding behaviour is read from source rather than tested empirically.

## Revision plan (ordered by value and feasibility; freeze 10-05)

- **R1 (0 GPU-h, today): pre-register.** Write `docs/insights/PREREG_iter4b.md` and put its sha in the queue manifest before any E4-3/E4-4/S run completes. Fix the following:
  - H1: recalibration φ > 1 on the new units (d3/d4, + balanced d1/d2), per method, with AWQ predicted weaker.
  - H2: T_quant − T_rand > 0 under class-label permutation, using gshape + Gaussian seeds with rtnsr excluded; plus an equivalence bound if it does not reject.
  - H3: split-task F > 0 per class.
  - H4: sampling (fixed design) φ ≤ 1.
  - Draw selection, dose groups, features, domain handling and Holm family.
- **R2 (0 GPU-h, before the tasks start): fix W19.**
  - S: per-request seed hash(run_seed, task, turn), BF16 × 6 runs at one T*, plus GPTQ-d1/d2 × 3 at T*.
  - E4-3: add d1/d2 (AWQ d1) × q1/q2 on q4/q8.
  - E4-4: add gshape s2–s4 × 2 nonces on q4.
  - Record node and simulator per draw.
- **R3 (0 GPU-h): re-analysis.** Make split-task F the primary P2 statistic. Report per-class φ/F, domain-stratified φ, and the break–fix correlation plus a margin-preserving null (fix each checkpoint's turnover count, randomise which turned-over tasks are breaks vs fixes within task strata). Add bootstrap CIs or the pp-SD for φ, and a max_steps sensitivity. Put the per-model tables, including the q8/q30a3 nulls, in the main text.
- **R4 (writing): rescope the claims.**
  - C2 becomes "fixed perturbations are reproducible behaviour profiles; quantizer coherence vs random [H2 result]".
  - C3 (the lottery) becomes the headline.
  - C1 is framed as permutation/exchangeability, with a conformal next-checkpoint interval.
  - C4 goes to analysis.
  - Correct F1's "largest on small models".
- **R5 (about 20 runs, if capacity): a held-out block** on telecom (40 tasks) or the 22 excluded tasks, pre-registered, q4 only.
- **R6 (writing): related work.** One table with columns closed loop / own null / coherence test / recalibration replication / random-perturbation control. Rows: Dutta, Singh, Williams & Aletras, Hu & Ramachandran, Flat Score, AgentProv, Stability Monitor, Model Equality Testing, Kennedy & Kennedy, Noise Floor Audit.
- **R7 (optional, about 10 runs): simulator swap** on a 30-task subset for GPTQ d1/d2. Does the lottery survive a different user model?

---

## Part 2: Inline annotations

> "Claim: a quantized LLM agent is not the original agent plus noise, it is a *different, reproducible agent*. Random perturbations of the same size (prompt nonces, Gaussian weight noise) and sampling re-roll task outcomes independently; a quantized checkpoint shifts them coherently, with a persistent behavioural fingerprint."

**[W1] FATAL:** Fixed Gaussian, gshape and rtnsign checkpoints have fingerprints as persistent as the quantizers' (same − different 0.44 vs 0.50 [RV]; gauss1_s1_fixed cos_AB 0.985 on q4). Nonces are not "the same size" (λ 0.02–0.12 vs about 0.25). Sampling is untested. Restate this as what F3/F4 show, and move the contrast to a pending, pre-registered test.

> "Working title: *A Quantized Agent Is a Different Agent: …*"

**[W1]/[W2]:** Under greedy deterministic serving, every fixed perturbation is a "different agent", including a fixed prompt (`iter_2_integrity.md:157`). Title on the lottery instead (answer 5 in Part 1).

> "| F1 | … pooled excess RTN +0.19 [0.10, 0.30], GPTQ +0.15, AWQ +0.16 (Holm p ≤ 0.036); largest on small models |"

**[W7] MAJOR:** RTN excess is +0.29 on q32, the largest of the five models (`r10` Holm table). "Largest on small models" holds only for GPTQ/AWQ. The q14/q30a3/q32 floors are a single null_K run each.

> "| F3 | A checkpoint's behavioural fingerprint … persists across prompt nonces and differs between same-dose checkpoints: F=0.44, perm p=0.001, 48 checkpoints | established |"

**[W2] MAJOR:** Established as a *reproducibility* statement. About half of F is per-task re-play: split-task F is 0.22 (p 0.0005). The 48 units include Gaussian and E17 random controls, which show the same fingerprint. Report the split-task F and per-class values.

> "| F4 | … W4 φ 5.6 on q4, 3.1 on q32, ~1 on q8/q30a3; prompt nonces φ 0.36–1.19 (not coherent); same-method recalibration pairs φ 4.65 (df 7) … | established on q4/q32 |"

**[W3] MAJOR:**
- q32 has J = 3 and no significant test (all-groups perm p 0.155).
- q8 is −0.14 and q30a3 −0.84, not "~1".
- W4 production quantizers pooled p = 0.080.
- The coherence is retail-only (airline φ 1.07 [RV]).
- q4's 5.6 includes rtnsr (1.41× dose); without it, about 3.2–3.4.
- The recalibration row is exploratory, and 2 of its 7 pairs mix nonce strata.

Downgrade to "on q4 (retail); pending E4-3".

> "| F5 | Matched-size Gaussian seeds show no coherence (φ 0.43 at k=1) → structure decides *coherence*, size decides *turnover* | hypothesis (1 draw per seed) |"

**[W1]/[W6]:** The 0.43 comes from a different statistic (canonical cells, no nonce correction, df ≈ 8) and was never compared with quantizer φ. With P1's statistic, fixed random controls give φ 2.10 or −0.58 depending on how rtnsr is classified. E4-4 at df 6 cannot decide this. Drop "structure decides coherence" until a declared difference test passes.

> "| F6 | Sampling (BF16, T>0) behaves like nonce re-rolls, not like a checkpoint | hypothesis | sampling baseline S queued (W19) |"

**[W5] MAJOR:** As queued, each "seed" is a fixed per-position noise vector shared by every request (vLLM per-request `manual_seed`), and it is confounded with the nonce. Redesign before running.

> "| F7 | The open-loop act-vs-talk logit contrast predicts a checkpoint's closed-loop fingerprint (q4 partial ρ 0.62, Holm p=0.012) |"

**[W9] MINOR:** q4 only (q8 0.00, q30a3 0.15), on ungated E3 inputs. It does not predict Δ. Keep it as an analysis paragraph.

> "C1 … stratified permutation/conformal test at two levels … checkpoint identity (are repeated draws of a checkpoint exchangeable with draws of other checkpoints and of the null?)"

**[W4] MAJOR:** No current test includes null draws in the level-2 permutation. P1/P2 permute labels among perturbed checkpoints only. Either run that test (class-label permutation including nonce, gshape-seed and sampling units) or describe P1/P2 accurately.

> "Finite-sample valid with 6–9 null draws."

**[W4]:** Valid but nearly powerless. The per-draw p is ≥ 1/9, and ±5 pp is unreachable per model (`iter_2_conformal.md`). Say so, and give the n needed (≥ 19 for a single-run 5% test).

> "stating them as conformal/exchangeability tests gives validity with few checkpoints and draws."

**[W4]:** Permutation tests already have that validity. The conformal label adds nothing here and invites a "conformal-washing" critique.

> "Theory asked of the collaborator: validity under stratified/weighted exchangeability (nonce stratum), a hierarchical (checkpoint → nonce draw → task) exchangeability test with few units per level, and power with 85 tasks."

**[W4]:** Not deliverable by 10-12 as a contribution. Put it in future work, or restrict it to a stated proposition with a proof sketch for the stratified permutation actually used.

> "| C3 | **Consequence**: single-checkpoint quantizer comparisons conflate method with checkpoint identity (recalibration moves net success by ~10 pp on q4) |"

**[S4]/[W11]:** This is the paper's best claim. Make it the headline, cite Williams & Aletras 2024 / Singh 2026 / Hu & Ramachandran 2026, and confirm it on pre-registered d3/d4. The ~10 pp is one pair on one model (q4 GPTQ d1−d2 +9.6 [1.8, 17.4]); the other models give −8.1 to +7.1 with CIs covering 0.

> "F5/F6 fail (Gaussian or sampling also coherent) → C2 becomes 'any fixed weight perturbation is a variant; prompt nonces and sampling are not', still new but weaker on 'structure'."

**[W1]:** For the fingerprint this is already the case on existing data. It is the current finding, not a risk.

> "Held-out confirmation: the 57 calibration-split tasks are contaminated for calibrated methods … a clean confirmatory split is still open."

**[W6] MAJOR:** Correct, and more serious than a risk line: `frozen_v1` calls the 85 "development data" and there is no test set. Options:
- pre-registered new checkpoints (the right unit for C3);
- telecom or the 22 excluded tasks for task generalisation;
- split the calibration pool for new draws.

## Sources

- Accuracy is Not All You Need (Dutta et al., NeurIPS 2024): https://arxiv.org/abs/2407.09141
- Behavioral Fingerprints for LLM Endpoint Stability and Identity (Leshin, Shah, Timmis, Kang 2026): https://arxiv.org/abs/2603.19022 (abstract fetched; lists quantization among detected identity changes; single-turn fixed prompts)
- Logit Fingerprinting (Logan & Bumgardner, AMIA 2026): https://pmc.ncbi.nlm.nih.gov/articles/PMC13274300/ (fetched; 100% FP-vs-quantized discrimination; NF4 flip rate 21% with improved accuracy)
- AgentProv (2026): https://arxiv.org/abs/2609.00052 (abstract fetched; tool-use behaviour catches substituted, quantized or wrapped backbones, 630 pairs)
- The Illusion of Equivalency (Rababah et al. 2026): https://arxiv.org/html/2607.08734
- Model Equality Testing (Gao et al., ICLR 2025): https://arxiv.org/abs/2410.20247
- On the Impact of Calibration Data in Post-training Quantization and Pruning (Williams & Aletras, ACL 2024): https://aclanthology.org/2024.acl-long.544/ ; https://arxiv.org/abs/2311.09755
- Beyond Activation Alignment (task-aware quantization; calibration-seed stability ±0.3/±0.5 in aggregate accuracy, per search snippet only): https://arxiv.org/pdf/2607.00908
- Certifying Compressed LMs (Singh 2026): https://arxiv.org/abs/2608.15046 (from SURVEY.md, not re-verified)
- The Structure of Quantization Damage (Hu & Ramachandran 2026): https://arxiv.org/abs/2609.01587 (from SURVEY.md, not re-verified)
- Quantization Error Is Spectrally Flat (Kennedy & Kennedy 2026): https://arxiv.org/abs/2609.33923 (from SURVEY.md)
- Flat Score, Amplified Failures (2026): https://arxiv.org/html/2607.27275
- Quantization Hurts Reasoning? (2025): https://arxiv.org/abs/2504.04823
- vLLM 0.29 source as installed: `/data/ziyangs/cloq_work/envs/cloq/lib/python3.12/site-packages/vllm/v1/worker/gpu_model_runner.py:1291`, `.../v1/sample/ops/topk_topp_sampler.py:203-210`
