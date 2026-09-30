# CLOQ research log — every version, insight and work item, with TL;DR and evidence

**TL;DR** — The calibration method (CLOQ) was falsified at v1. The paper is now about *perturbation equivalence*:
judge a compressed agent against the model's own perturbation null. The A6000 multi-model matrix has been running
since 2026-09-28 18:10. The live dashboard is https://claude.ai/artifact/PqFrT9bVufKqdkD43u5c1B.

Paths are relative to the repo root unless they start with `/data/` (cluster only; not in git). Stable ids:
versions `V*`, insights `I*` (iteration-scoped in `docs/insights/`), experiment proposals `E*`, work items `W*`.
Newest first.

---

## W31 — Review round 2: old main line retired; fork deliverables and annotation fields defined (2026-09-30)
**TL;DR** "Success-equivalent, behaviourally distinct" retired. The random-perturbation fingerprint is kept as an exploratory, post-hoc finding; no W4 fingerprint was detected. Main line: consequences and sources of quantized action substitutions on identical histories. The BF16 action is only a reference; defects are judged from tool preconditions, task requirements, authorisation and state. No research gate on the sign of G. The development evidence gate needs coverage, consequence composition, G and A/C/I with intervals, process evidence and precision. Per-fork annotation: defect, correction, requirements satisfied. Freeze the tool-type table. Report the fixed pool and new tasks separately. Our addition: telecom dev split (80 tasks) joins development forks.
Evidence: `docs/insights/EXTERNAL_REVIEW_GPT61_20260930.md` (Round 2), `docs/insights/STORYLINE_v6.md`.

## W29 — P0 statistics and measurement fixes; corrected H3; audit record (2026-09-30)
**TL;DR** The review's §B/§C issues were all confirmed in the code; fixes were implemented as new scripts and outputs. The original results are kept as history, and everything below on the 28 runs is a corrected (post-hoc) re-analysis.
- **H3.** The pre-registered test was invalid: its true-pair scaling rejects 33–42% of exchangeable null datasets. The corrected test (pairing-invariant pooled scale) is calibrated: 4.4% ± 0.3% against a nominal ≤ 4%.
  - Corrected H3: pooled F 0.136, p 0.013 (was 0.260, 0.0008); RAND 0.283, p 0.028; q4 0.088, p 0.125; q8 0.184, p 0.049.
  - RECAL alone: F 0.025, p 0.30 (was 0.118, p 0.005). Random checkpoints carry 90% of the pooled F.
  - The quantizer fingerprint (STORYLINE_v6 B3) is not detected.
- **p1/H1 crossed nonce model.** H1 p is unchanged (0.744, exact invariance). φ is 0.33–0.47 against the pre-registered 0.40. Crossed variance components for q4: checkpoint 3.69 pp, residual 2.62 pp; method not estimable (1 df, negative moment estimate).
- **Success non-inferiority.** The scaffold is ready: ε = 3 pp (5 pp sensitivity), TOST, D/V U-statistics with the Hamming cross-check, and task-clustered generalisation. Real mode waits for `bfpair`; the dev mode uses stand-ins and is not a result.
- **Measurement.**
  - `p_act` bounds and a missing flag: means move < 0.001.
  - `topk_kl` renamed to `approx_topk_kl`; a coarse-grained exact-KL lower bound was added.
  - `name_mass` is now a proxy with measured error terms; `confirm_bw` is renamed `confirm_request_proxy` (values unchanged).
  - Tool-type table from the tau2 decorators: the write regex misses 5 of 6 telecom write tools.
  - Endpoint naming: DB success for retail/airline; tau2's official deterministic basis success for telecom.
  - `nl_judge` is unused in scoring and not thread-safe; left unchanged.
- **Act/talk "blurring" (B5).** Mostly a selection effect: the q4 RTN P(act|talked) rise 0.014 → 0.088 is matched by a sign-symmetric null (0.080). The directional part is small (unconditional ΔP(act) −0.10 to +0.005 on q4/q8) and random controls are as large or larger.

Evidence: `docs/insights/METHODOLOGY_REVISION.md`; `analysis/insights/iter_4/{h3_corrected,p1_crossed,success_ni,act_talk_selection,tool_types}.py`; `analysis/insights/iter_4/out/{h3_corrected,h3_corrected_sim*,p1_crossed,success_ni_DEV,act_talk_selection,tool_types_features}_20260930T0044Z.json`, `out/tool_types.json`; `analysis/openloop/a6k2/*/topk/*.v2.json`; `scripts/a6000/openloop_topk.py` (`--schema 2`), `analysis/insights/iter_4/common4.py`, `cloq/metrics.py`; snapshot `analysis/insights/iter_3/out/snapshot_live_20260930T0044Z.json`.

## W29a — Fork development blocks queued; Llama deprioritised (2026-09-30)
**TL;DR** Primary fork checkpoints fixed by a pre-stated completeness rule (most existing fresh-nonce draws; tie → lowest calibration draw): GPTQ-W4 d1 and AWQ-W4 d1 (calibration c1) on q4 and q8. Development blocks: existing q3–q5 + 17 new nonces f01–f17 (sha256-derived, disjoint from every used nonce) = 20 blocks; queued Q runs for the 4 cells and BF16 on the same nonces (36 tasks, 102 runs, priority −8), which also give paired Q−B success. 28 Llama (l8) tasks moved +40 per the external review's priorities. Workstreams launched: P0 statistics/measurement fixes (→ W29) and fork replay engineering with the 10-01 gate (→ W30).
Evidence: `manifests/fork/dev_blocks_v1.json`, `queue/todo/a6k2_{q4,q8}_{gptq_w4_d1,awq_w4,bfpair}_fdev*.json`.

## W28 — External review (GPT-6.1) adopted: fork mechanism study; P0 fixes; BF16 pairing (2026-09-30)
**TL;DR** New main line: same-state 2×2 fork (current action B/Q × continuation B/Q) to separate current-decision and subsequent-execution effects of quantization; mechanism/measurement paper, no repair method this round; conformal out of the core. Verified in code before adopting: H3 `split_cos` scales by true-pair differences (permutation invalid as implemented), p1 nonce term includes shared nonce main effect (H1 p-value unaffected, φ estimate biased), `p_act` treats tool-start outside top-20 as 0, q8 AWQ d3 +5.29 pp. Queued `a6k2_{q4,q8}_bfpair` (BF16 on the W4 fresh nonces q1–q5; nonces verified from environment.json) for paired non-inferiority. Thresholds 3 pp (g_min, ε, equivalence). Replay go/no-go 10-01 evening; telecom holdout (34 tasks, untouched) for confirmation.
Evidence: `docs/insights/EXTERNAL_REVIEW_GPT61_20260930.md`, `queue/todo/a6k2_{q4,q8}_bfpair.json`.

## W27 — Llama multi-tool-call parse errors are agent failures, not outages (2026-09-30)
**TL;DR** `a6k2_l8_gauss0.03_s2` failed on 1 "outage": vLLM's llama3_json parser rejects a turn with several tool calls ("This model only supports single tool-calls at once!"). That is the agent's own output, so like context overflow (W10) it now counts as a task failure: worker labels it `agent_parse_error` in infra_causes.json (not an outage, no task abort) and `iter_2/common.py` relabels `AGENT_SIDE = {context_overflow, agent_parse_error}` as failures, keeping the true cause as the termination reason. Task resume-requeued.
Evidence: `scripts/a6000/worker.py` (W6/W10 guard), `analysis/insights/iter_2/common.py` (AGENT_SIDE), `runs/a6k2_l8_gauss0.03_s2/airline/tau2_results.json` task 14.

## W26 — Storyline v6 (two lines) and review packet update (2026-09-30)
**TL;DR** `docs/insights/STORYLINE_v6.md` records Line A (checkpoint lottery, refuted by the pre-registered H1/H2, W25) and Line B (success-equivalent but behaviourally distinct: B1 success equivalence, B2 turnover above the floor, B3 persistent fingerprint (confirmed), B4 fingerprint generic to fixed perturbations, B5 what changes, B6 damage regime; open B7 "does it matter"). `docs/REVIEW_PACKET.md` updated for the external reviewer (new §4b pre-registered result, both lines, experiment record, revised questions).
Evidence: `docs/insights/STORYLINE_v6.md`, `docs/REVIEW_PACKET.md`.

## W25 — Pre-registered confirmatory result (2026-09-30)
**TL;DR** Ran `prereg_h1_h4.py` once on snapshot 20260930T0044Z (all 28 confirmatory runs admitted). H1 recalibration lottery NOT supported (pooled φ 0.40, p 0.74; q4 φ −0.30, q8 0.94). H2 net effect replicating across nonces NOT supported (r 0.42, p_holm 0.42; q4 r −0.52, q8 0.94). H3 split-task behavioural fingerprint SUPPORTED (F_split 0.26, p_holm 0.0024; q4 0.19, q8 0.33). Random fixed checkpoints have fingerprints at least as persistent as quantizers (same-checkpoint cosine RAND 0.51/0.77 vs RECAL 0.32/0.38). H4 not detected (−0.83 [−7.1, 4.2]). Secondary: new q4 recalibrations d3/d4 all land at net +1.5 to +3.9 pp; including d1/d2, checkpoint SD 3.65 pp vs nonce 2.51 pp, method ≈ 0. Per PREREG §6: the checkpoint lottery is dropped as a headline (the exploratory q4 d1 vs d2 gap did not replicate on new checkpoints); the paper leads with turnover above the numerics floor plus a persistent behavioural fingerprint that is generic to fixed weight perturbations.
Evidence: `analysis/insights/iter_4/out/prereg_h1_h4_CONF_20260930T0044Z.json`, `analysis/insights/iter_3/out/snapshot_live_20260930T0044Z.json`, `docs/insights/PREREG_iter4.md`.

## W24 — Pre-registration amendment 1 (2026-09-30)
**TL;DR** PREREG_iter4 §7 amendment 1 records the 18 implementation clarifications (A1–A18) made while writing the confirmatory script on stand-in checkpoints, before any confirmatory outcome was computed or inspected. Most important: the confirmatory set is 14 checkpoints × 2 draws = 28 runs (the original text miscounted "40"). No hypothesis, statistic, unit, α or Holm family changed. New prereg sha256[:16] a991e2e5ca2d6098 (original 0d5e8385c911824f), updated in `prereg_h1_h4.py`.
Evidence: `docs/insights/PREREG_iter4.md` §7, `docs/insights/PREREG_iter4_analysis.md`, `analysis/insights/iter_4/prereg_h1_h4.py`.

## W23 — Confirmatory analysis script for PREREG iter4 (2026-09-29)
**TL;DR** `analysis/insights/iter_4/prereg_h1_h4.py` implements PREREG_iter4 §2–§4:
- **Primary.** H1 (φ, P1 estimator unchanged, B = 5000), H2 (r, exact within-model relabelling) and H3 (F_split, 100 task halves, 12 P2 features), with Holm over H1–H3.
- **Secondary.** H4 two-sided with a CI; per-model and per-domain versions; max_steps and overflow sensitivity; variance components.
- **Guards.** The script asserts PREREG sha16 0d5e8385c911824f. It refuses unless all 28 confirmatory runs are admitted with their registered nonces, the script was committed before the snapshot, no earlier snapshot already admitted them, and the analysis has not run before. `--deadline-mode` is accepted only on or after 10-05.
- **Development.** Built only on non-confirmatory stand-ins (`--dev`). No confirmatory outcome was opened. Stand-in Δ matches P2 exactly, and the permutation tests are calibrated on synthetic nulls.
- **Ambiguities.** A1–A18 need to be logged as §7 amendments. The most important is A1: §1 says 40 runs but enumerates 28. A16: amending §7 changes the hash, so `PREREG_SHA16` must be updated in a commit before the confirmatory snapshot.

Evidence: `docs/insights/PREREG_iter4_analysis.md`, `analysis/insights/iter_4/prereg_h1_h4.py`, `analysis/insights/iter_4/out/prereg_h1_h4_DEV.{json,log}`.

## W22 — Iteration-4 pre-registration (2026-09-29)
**TL;DR** Pre-registered H1 (recalibration lottery, φ>1), H2 (net effect replicates across nonces), H3 (split-task fingerprint), Holm over H1–H3; H4 (quantizer vs random coherence) secondary. Confirmatory units: GPTQ/AWQ-W4 d3/d4 and Gaussian k=1 seeds s2/s4/s5 on q4/q8 × nonces q1/q2 (40 runs). Written while these runs were running; no closed-loop outcome of them had been analysed (q4 churnctl_k1_s2 had finished, not opened). sha256[:16] of the registered file: 0d5e8385c911824f.
Evidence: `docs/insights/PREREG_iter4.md`.

## W21 — Review packet, v5 review, sampling baseline pulled (2026-09-29)
**TL;DR** Storyline v5 reviewed: 2.5/5 as-is, 3.5 if reframed around the checkpoint lottery with confirmatory recalibration draws (`paper/review_storyline_v5.md`). The review found the W19 sampling baseline mis-designed (vLLM re-seeds every request with the same seed, so a fixed seed acts as a fixed perturbation); `a6k2_q4_samp_T*` moved to `queue/deferred/` before any run started. All results, open-loop outputs, determinism canaries, calibration manifests and docs committed; analysis caches git-ignored. `docs/REVIEW_PACKET.md` is a self-contained entry point for external reviewers (methodology, results, reviews, open questions), linked from README.
Evidence: `docs/REVIEW_PACKET.md`, `paper/review_storyline_v5.md`, `queue/deferred/a6k2_q4_samp_T{0.2,0.5,0.8}.json`.

## W20 — E4-2 fork-alternative open loop implemented, smoke-tested and queued (2026-09-29 14:40 PDT)
**TL;DR** New `scripts/a6000/openloop_topk.py` records the served cell's top-20 alternatives (token id + logprob) at every BF16 decision start and at the tool-name tokens of BF16 tool calls. It uses the same 400-decision sample as E3, plus the first token of all BF16 decisions. BF16 is run as its own cell, so the contrasts are served-vs-served: Δlogit P(`<tool_call>`), KL(BF16‖cell), and the mass on each tool name.
- **Integrity.** The BF16 cell reproduces the closed-loop first-token logprobs within the log's 4-decimal rounding. `prompt_logprobs` and generation agree bit for bit.
- **Smoke, q4 RTN-W4 vs BF16.**
  - Mean P(act) at decision starts: 0.540 → 0.492.
  - Split by what BF16 did, it falls from 0.956 to 0.831 at tool starts and rises from 0.016 to 0.065 at text starts, so RTN blurs the fork rather than shifting it one way. Δlogit mean −0.90.
  - The act/talk argmax flips at 11.75% of starts.
  - First-token KL: median 0.009, q90 2.8.
  - P(BF16's tool name) falls from 0.991 to 0.896, and the tool-name switch rate rises from 0.4% to 10.8%.
- **Queued.** 50 tasks `a6k2_<m>_olk_<cell>` at priority −8: q4 19, q8 17, q14 6, q32 6 (cell list in the iter-4 doc).
- **Code changes.** `worker.py` passes `openloop.topk` / `positions` / `first_all` / `ref` through to the new script. Tasks without `topk` are unchanged, and `openloop_d.py` is untouched.

Evidence: `scripts/a6000/{openloop_topk,make_tasks_e42,worker}.py`; `analysis/openloop/a6k2/q4/topk/{bf16,rtn_w4}.{json,npz,names.json}`; `docs/insights/iter_4_disposition.md` ("E4-2 implementation"); `/data/ziyangs/cloq_work/queue/*/a6k2_*_olk_*.json`; logs `/data/ziyangs/cloq_work/logs/tasks/a6k2_q4_olk_{bf16,rtn_w4}.log`.

## W19 — Iteration-4 experiments queued: checkpoint variant vs sampling (2026-09-29, user go-ahead)
**TL;DR** Tests whether a quantized checkpoint is a reproducible behavioural variant (coherent net effect, persistent fingerprint; W18) unlike nonce/Gaussian perturbations and sampling. Queued via `scripts/a6000/make_tasks_iter4.py`: E4-1 open-loop probes for existing checkpoints on q8/q14/q30a3/q32 (20 reprioritised to −8, 6 new); E4-3 calibration draws c3/c4 → GPTQ/AWQ-W4 d3/d4 on q4/q8 × 2 fresh nonces (8 cells, 16 runs, + open-loop); E4-4 fixed Gaussian k=1 seeds s2/s4/s5 on q4/q8 × 2 fresh nonces (12 runs); S sampling baseline q4 BF16 T∈{0.2,0.5,0.8} × seeds 1–3 on fresh nonces (9 runs). KV-cache quant and q8 new-method closed-loop cells moved +30 (telecom already at 40–60). Code: per-run `env` in worker.py; `CLOQ_AGENT_TEMPERATURE`/`CLOQ_AGENT_SEED` in cloq/config.py (frozen greedy stays the default; recorded in each run's config.json llm_args_agent); extra calibration draws c4/c5 in `configs/draws_extra.json` (frozen_v1 untouched; calib_v1 refuses to redefine a frozen draw). Pending: E4-2 (top-20 open-loop variant) and E4-5 (57 calibration-split tasks).
Evidence: `scripts/a6000/make_tasks_iter4.py`; `queue/todo/a6k2_{q4,q8}_{gptq,awq}_w4_d{3,4}.json`, `a6k2_{q4,q8}_churnctl_k1_s{2,4,5}.json`, `a6k2_q4_samp_T*.json`; `docs/insights/iter_4_disposition.md`.

## W18 — Iteration-4 disposition hypothesis: P1–P4, F1 (2026-09-29 13:30 PDT)
**TL;DR** Tests "quantization shifts dispositions at near-tied policy forks; a checkpoint's fixed bias makes the net effect a coherent lottery" on gated snapshot 20260929T1937Z, with Holm over 5 declared tests.
- **Supported.**
  - **P2** Each checkpoint has a reproducible behavioural fingerprint across nonce draws: F 0.44, p_holm 0.001. tool_share is the most checkpoint-specific feature.
  - **P1** Checkpoint net Δ is over-dispersed vs independent task landing: φ 4.6, p_holm 0.001. Excluding the W3 method gap: φ 2.3, p 0.017. Recalibration pairs: φ 4.7, p 0.013. The effect is carried by q4/q32; q8 and q30a3 show none. Prompt nonces are not coherent (φ_U 0.36–1.19).
  - **P4** On q4, an open-loop act-vs-talk logprob contrast predicts the closed-loop tool-call shift beyond dose: partial ρ 0.62, p_holm 0.012. q8/q30a3 do not replicate (they have no RTN/GPTQ E3 cells).
- **Not supported.**
  - **P3** The fingerprint does not predict the sign of Δ: ρ 0.12, p 0.32.
  - **F1** Near-tied BF16 first tokens do not mark fragile tasks: ρ −0.12.
- **Exploratory.** Shift size tracks λ (ρ 0.67). Gaussian seeds show no lottery at any k.
- **Proposed next (not queued).** E4-1 (E3 cells for existing checkpoints on the other models) and E4-2 (a fork-alternative open-loop spec with top-20 logprobs).

Evidence: `docs/insights/iter_4_disposition.md`; `analysis/insights/iter_4/{common4,p1_overdispersion,p2_dispositions,p4_openloop_forks,f1_fragile_forks,p5_dose_scaling,h00_holm}.py`, `run_all.sh`; `analysis/insights/iter_4/out/*_live_20260929T1937Z.{json,log}` (Holm: `out/h00_holm_live_20260929T1937Z.json`); `analysis/insights/iter_3/out/snapshot_live_20260929T1937Z.json`.

## W17 — R3/R4 statistics for λ–c turnover: floor, hierarchical bootstrap, TOST/NI, Holm (2026-09-29 12:55 PDT)
**TL;DR** Addresses review_storyline_v4 R3/R4 and W6/W7. Run on a fresh integrity-gated snapshot (20260929T1937Z) for q4/q8/q14/q30a3/q32 (l8: no runs), with a hierarchical paired bootstrap (tasks, null draws, checkpoints and draws resampled).
- **Survives Holm.**
  - W4 turnover above a numerics floor (rot_bf16/null_K/gauss0.001/0.003), pooled over 5 models: RTN +0.19 [0.10, 0.30], GPTQ +0.15 [0.07, 0.24], AWQ +0.16 [0.07, 0.25].
  - RTN re-rolls no more than random-sign error of RTN magnitude (NI, margin 0.10, p_holm 0.038).
- **Fails.** "20–40%" and "5–10×": against the floor, q4 RTN break is 2.2× [0.9, 8.9] and fix 1.2× [0.4, 3.7].
- **Not established.** λ-equivalence of W4 methods at ±0.10. The pooled Δλ vs RTN is only −0.05 to +0.13, but no TOST passes.
- **Unidentified.** "c follows method": RTN's c is unidentified (λ 2.5% bound ≤ 0.10) on every model, so none of the 14 Δc tests can be run.
- **Checkpoint lottery.** The same-method checkpoint gap exceeds the method gaps: q4 GPTQ d1−d2 ΔΔ +9.6 pp [1.8, 17.4], while every method-vs-RTN ΔΔ CI covers 0. The checkpoint variance of Δ exceeds the method variance on q4/q14/q32 (1–2 df; tests need R1).
- **Coin check.** Passes in 81/83 cells, but it is weak (median CI width 0.39).
- **Provenance.**
  - "Partial ρ 0.86" was flip vs per-decision *hazard* (A2-15). For λ it is 0.39 [−0.03, 0.73]: the probe is mostly a dose proxy.
  - The 85 tasks are the `evaluation` split of `manifests/task_split_v0.json` after 22 BF16-unstable exclusions; the 57 calibration tasks are unused.
  - `r01_realloc_unfrozen.json` (q4,q8 only, ungated) is left unchanged. The gated all-model r01 is `r01_realloc_live_20260929T1937Z.json`.
  - `r_common.py` gains a `CLOQ_TAG` output-tag override.

Evidence: `docs/insights/iter_3_stats_R3.md`; `analysis/insights/iter_3/r10_turnover_stats.py`; `analysis/insights/iter_3/out/{r10_turnover_stats,r01_realloc}_live_20260929T1937Z.json`, `out/snapshot_live_20260929T1937Z.json`, `out/integrity_live_20260929T1937Z.log`; `paper/review_storyline_v4.md`.

## W16 — Simulator rebalancing without runner restarts (2026-09-29 12:30 PDT)
**TL;DR** node005's simulator stayed KV-bound (4 running, 36–38 waiting) while node001/node004 simulators were idle. (1) Stopped `a6k2_q4_gauss3_s2_redo` (26/85 tasks after 13 h; k=3 loops to max_steps, W11) and moved it to `queue/deferred/` (finished episodes kept, resume-safe); `a6k2_q4_gauss3_s1_redo` (54/85) continues. (2) `worker.py` now reads `queue/USER_BASE.<node>` at task start, so a node's new tasks can use another node's simulator without restarting its runner; `USER_BASE.node005` → node004. All simulators are the same model with the same canary hash, so outcomes are unaffected. (3) `gputop.py` sums non-negative counter increments (server restarts gave negative cluster tok/s).
Evidence: `queue/deferred/a6k2_q4_gauss3_s2_redo.json`; `queue/USER_BASE.node005`; `scripts/a6000/{worker,gputop}.py`; `gpumon/node005.jsonl`.

## W15 — E17 size-vs-structure complete; r_common family regex fix (2026-09-29)
**TL;DR** `iter_3/r_common.QUANT_RE` recognised only rtn/awq/gptq, so r01–r09 silently dropped every E17 control and every new method (gshape, rtnsign, rtnsr, nf4, mxfp4, rot_*, kvq_*). Fixed. With all 3 draws per control on q4/q8/q14 (attractor-model λ, nonce null, task bootstrap, unfrozen):

| model | RTN W4 | gshape (RTN per-group RMS, Gaussian) | rtnsign (RTN magnitudes, random signs) | Gaussian k=1 (fixed ckpt) |
|---|---|---|---|---|
| q4 | 0.24 [0.09, 0.42] | 0.42 [0.22, 0.62] | 0.24 [0.12, 0.37] | 0.34 [0.16, 0.56] |
| q8 | 0.19 [0.01, 0.41] | 0.17 [0.02, 0.38] | 0.42 [0.17, 0.70] | 0.27 [0.07, 0.52] |
| q14 | 0.25 [0.06, 0.45] | 0.20 [−0.01, 0.41] | 0.35 [0.13, 0.58] | 0.30 [0.09, 0.49] |

No ordering holds across models and every CI overlaps: RTN's specific error structure reallocates no more than size-matched random error; the controls reallocate as much or more (3-model means: RTN 0.23, gshape 0.26, rtnsign 0.34). Supports "reallocation is set by error size, not quantizer structure" (M4). Provisional until the frozen-snapshot rerun. Earlier E17 numbers in chat (q8 gshape 0.049, q14 rtnsign 0.175) were a different metric (fate-change fraction) from an ad hoc script and are superseded.
Evidence: `analysis/insights/iter_3/out/r01_realloc_unfrozen.json`; `analysis/insights/iter_3/r_common.py` (QUANT_RE); runs `runs/a6k2_{q4,q8,q14}_{gshape,rtnsign}_w4_q{1,2,3}`.

**Addendum (AWQ calibration control, q4).** AWQ d2 (3 fresh-nonce runs) λ 0.23–0.26 vs d1 0.12–0.36 (mean 0.29): calibration draw does not matter. On q4, λ is method-independent (RTN 0.24, AWQ 0.25, GPTQ 0.25) while the attractor c differs (RTN 0.18, AWQ 0.36, GPTQ 0.45, p̄≈0.36), which by Δ = λ(c − p̄) is why RTN damages and GPTQ does not. Candidate insight: calibration-aware quantizers change *where* reallocated tasks land, not *how many* are reallocated. Caveat: q8 AWQ λ 0.39 vs RTN 0.19, so check across models on the frozen snapshot.

**Addendum (new methods, q4, 3 fresh-nonce runs each).** λ / c: rot_bf16 0.12 (≈ serving null_K 0.09); RTN 0.24/0.18; rot_rtn 0.23/0.37; GPTQ 0.25/0.45; rot_gptq 0.23/0.49; MXFP4 0.22/0.42; NF4 0.37/0.45; rtnsr (1.41× RTN error) 0.35/0.12. Rotation, like calibration, leaves λ unchanged and moves c above p̄ (≈0.36), which removes RTN's net damage; stochastic rounding raises λ and lowers c. q8/q14 queued. Evidence: `analysis/insights/iter_3/out/r01_realloc_unfrozen.json`.

## W14 — KV-quant scheduling (2026-09-29)
**TL;DR** Plain KV INT4/INT3 destroys q4 (token flip 79%/90% vs 4.3% with Hadamard rotation, 0.75% at INT8), so its closed-loop cells would loop to max_steps for hours (W11) and add nothing beyond gauss k=3. Deferred the 6 plain INT4/INT3 cells, added KV INT8 cells on q4/q8/q14 (fresh nonces q1–q3) as the free-zone deployed-analog point, and made the cross-node det pair INT4+rotation.
Evidence: `analysis/kvq/validate_q4.json`; `queue/deferred/a6k2_{q4,q8,q14}_kvq_{int4,int3}.json`; `queue/todo/a6k2_{q4,q8,q14}_kvq_{int8,int4_rot}.json`, `a6k2_det_q4_kvq_int4_rot_{a,b}.json`.

## W13 · Fake KV-cache quantization (KVQ) in the live pipeline (2026-09-29 12:30 PDT)
**TL;DR** Real FP8/INT KV caches cannot run on A6000 under our frozen numerics (W7), so KV quantization is faked:
a sitecustomize hook wraps vLLM 0.29's `Attention.forward` (used by Qwen3, Qwen3-MoE and Llama) before model
construction. It quantize-dequantizes K (after k_norm and RoPE) and V, i.e. exactly what is written to the paged cache.
The scheme is per token, per KV head, one asymmetric INT-b group over head_dim. An optional QuaRot-KV variant applies a
fixed Hadamard: q and k are rotated, V is quantized in the rotated basis and rotated back. Dynamo inlines the wrapper,
so the ops are compiled by Inductor and replayed inside the CUDA graphs. They are row-local, so they stay batch-invariant.
Validation on q4 (`analysis/kvq/validate_q4.json`):
(a) bits=16 through the hook reproduces the BF16 canary `c7343b60da095480` exactly.
(b)/(c) Open-loop |Δlogprob| on 150 BF16 reference decisions (12,288 tokens) is monotone in precision:

| cell | mean \|Δlogprob\| | token flip rate |
|---|---|---|
| INT8 | 0.010 | 0.75% |
| INT4 + Hadamard | 0.119 | 4.3% |
| INT4 | 5.00 | 79% |
| INT3 | 6.45 | 90% |

(d) Under every config, 8 real agent prompts gave identical token ids and logprobs in three settings: alone,
in one concurrent batch with 8 fillers, and again after a prefix-cache hit (8/8).
**Plain per-token INT4/INT3 destroys Qwen3-4B.** The cause is K outlier channels: one group spans them and zeroes the
rest. The Hadamard rotation largely rescues it, which is the QuaRot result. Expect `kvq_int4`/`kvq_int3` agents to loop
to max_steps. Those cells are likely GPU sinks (W11); defer them if the queue backs up.
- Code: `scripts/a6000/pyhooks/cloq_kvq.py` (the hook). `scripts/a6000/pyhooks/sitecustomize.py` installs it only when
  `CLOQ_PYHOOKS=1` and `CLOQ_KVQ_BITS` is set. Other env: `CLOQ_KVQ_ROT`, `CLOQ_KVQ_WHICH`.
- Compile-cache isolation: the hook moves `VLLM_CACHE_ROOT` to `<root>/kvq_b<b>_r<rot>_<which>`. vLLM keys its compile
  and AOT caches by config and traced source, not by env, so without this a KVQ server and a BF16 server could share a
  compiled graph.
- Worker changes (`scripts/a6000/worker.py`): the BF16 canary is skipped when `serve_env` enables KVQ, and
  `runs/<id>/quantization.json` records `kv_cache`.
- Generator: `scripts/a6000/make_tasks.py --only kvq`. Arm `kvq`, ckpt bf16.
- Validation: script `scripts/a6000/kvq_validate.py`; task `/data/ziyangs/cloq_work/queue/done/kvq_validate_q4.json`.
  Server logs are in `/data/ziyangs/cloq_work/logs/kvq/`, open-loop outputs in `analysis/kvq/openloop_q4_*.json`.
  The INT8 canary (`42f358a11e348a84`) differs from BF16, as intended.
- Queued (priority −2): `a6k2_{q4,q8,q14}_kvq_{int4,int3,int4_rot}`, each 3 runs `_q1.._q3` with fresh nonces
  6d1f0b3e/f07a5c21/4c8e1a7f. Det pair `a6k2_det_q4_kvq_int4_{a,b}` is pinned to node005/node004.

## W12 · More weight-only 4-bit formats: NF4, MXFP4, QuaRot rotation (+RTN/GPTQ), stochastic-rounding RTN (2026-09-29 12:00 PDT)
**TL;DR** Six new fake-quant cells go into the live pipeline, each dequantized back to bf16 and served through the
identical vLLM path. They are `nf4` (QLoRA NormalFloat-4, absmax block 64), `mxfp4` (OCP MX: E2M1 elements with a
shared E8M0 scale per 32), and the QuaRot-style `rot_bf16` (fused RMSNorm plus a seeded random-Hadamard residual
rotation, no quantization, a control). On top of that rotation come `rot_rtn_w4` and `rot_gptq_w4`. `rtnsr_w4` is
RTN's own grid with stochastic rounding: an on-grid, unbiased control, where `rtnsign` is off-grid. This adds the
method list of the COLM 2025 "Quantization Hurts Reasoning?" paper and extends E17 (error size vs structure).
- Unit tests pass on CPU (`tests/test_fp4_rotate.py`, run with `BNB_PATH=/data/ziyangs/cloq_work/tmp/bnbref`):
  - NF4 matches bitsandbytes 0.50.2 `quantize_4bit`/`dequantize_4bit` 100% (fp32 and bf16 inputs).
  - MXFP4 matches an ml_dtypes `float4_e2m1fn`/`float8_e8m0fnu` reference 100%, with hand-checked round-to-nearest-even ties and saturation to 6.
  - Hadamard: H H^T = dI for d = 2560, 4096 and 5120 (Paley order 20 ⊗ Sylvester).
  - A tiny tied Qwen3 stored in fp32 gives max |Δlogprob| 6.4e-7 after rotation.
  - rtnsr stays on the RTN grid, is unbiased (0.04 steps after 64 draws), and its error is 1.41× RTN's.
- q4 rotation check (`analysis/rotation/verify_q4.json`; task `a6k2_w12_verify_rot_q4`; `scripts/a6000/verify_rotation.py`).
  It uses 20 calibration contexts (40,960 positions) and compares rot_bf16 with the original:
  - fp32 compute: top-1 agreement 99.55%, mean |Δlp(top1)| 0.006. Here only the bf16 storage of the rotated weights differs.
  - bf16 compute: 98.4%, mean 0.018. This is the size of the bf16 numerics floor: the original model in bf16 vs fp32 compute agrees 98.7%, mean 0.013.
  - Max |Δlp| is 0.8–0.9 at near-tie positions (the numerics reference reaches 1.1). The last position agrees 20/20.
  - vLLM serves the untied checkpoint (`tie_word_embeddings=false`, explicit `lm_head.weight`). Greedy 48-token outputs are identical on 3/6 prompts; the other 3 diverge at a near-tie (token 0 or 13).
  - q_norm/k_norm act per head on the projection outputs, so the rotation leaves them unchanged.
- q4 smoke (task = production cell, fresh nonces q1–q3, overall db_match over 85 tasks). References:
  - fresh-nonce and n-nonce references: RTN-W4 q* 0.306, GPTQ-W4-d1 q* 0.408, AWQ-W4 q* 0.404, null n* 0.359.
  - new cells: nf4 0.341/0.365/0.376, mxfp4 0.341/0.353/0.329, rot_bf16 0.341/0.388/0.365, rot_rtn_w4 0.318/0.306/0.376,
    rot_gptq_w4 0.400/0.400/0.412, rtnsr_w4 0.212/0.235/0.294. Mean relative weight error: nf4 0.0086,
    mxfp4 0.0137, rot_rtn 0.0102 (RTN-W4 ≈ 0.0107), rtnsr 0.0212.
- Queued (priority −2; rtnsr −3): q8 and q14 × all 6 cells (runs `a6k2_<m>_<cell>_q1..q3`, nonces 6d1f0b3e/f07a5c21/4c8e1a7f).
  Also E3 open-loop tasks `a6k2_<m>_ol_<cell>` for q4/q8/q14 (ref `a6k2_<m>_bf16`, out `analysis/openloop/a6k2/<m>/<cell>`).
  q14's open-loop tasks wait on `a6k2_q14_bf16` (in todo), as the existing q14 E3 cells do.
- Code: `cloq/compress.py` (modes nf4, mxfp4, rtnsr), `cloq/rotate.py` (new), `cloq/quantize.py --src` (GPTQ on a local
  rotated checkpoint; records `pre_transform`), `scripts/a6000/worker.py` (kinds nf4, mxfp4, rtnsr, rot_bf16, rot_rtn, rot_gptq),
  `scripts/a6000/make_tasks.py --only w12`. Logs: `/data/ziyangs/cloq_work/logs/tasks/a6k2_q4_{nf4,mxfp4,rot_*,rtnsr_w4}.log`.
- Caveats:
  - NF4 stores fp32 absmax with no double quantization. Double quantization of the scales is not modelled.
  - Rotation uses a single seed (0), and rot_* keeps embeddings and lm_head rotated in BF16. QuaRot additionally rotates
    per head in attention and applies online Hadamards for activations; neither matters for weight-only quantization.
    Only the residual rotation is applied.

## V6 · Insight loop, iteration 1 (2026-09-29, in discussion)
**TL;DR** Four candidates (I1–I4), repositioned against the literature. The per-step margin model is inherited
from Du et al. 2026. Our claims are the closed-loop composition, saturation along δ, a later damage threshold, and
cross-model transfer.
- Candidates: `docs/insights/iter_1_candidates.md`. Scripts: `analysis/insights/iter_1/s0*.py`.
  Outputs: `analysis/insights/iter_1/out/*.json` (snapshot `s00_snapshot.json`, 2026-09-29T01:26Z).
- Literature: `docs/insights/SURVEY.md`, `docs/insights/survey_sweeps/{margins_flips_divergence,compressed_agents_eval_noise,equivalence_null_criteria}.md`,
  `analysis/insights/references_new.bib`.
- Discussion (survey + experiment round 1): `docs/insights/iter_1_discussion.md`. Plan: `docs/insights/EXPERIMENTS.md`.
- Agent roles: `~/.claude/agents/cloq-{insight,survey,experiment,verify}.md` (on the cluster login node).
- **Verifier (iter 1, 2026-09-29 02:36Z):** I1 REVISE (v2: per-decision hazard floor), I2 HYPOTHESIS, I3 HYPOTHESIS (at risk: q8 RTN-W4), I4 HYPOTHESIS with I4a HELD (serving numerics move the canonical score ±8 pp). Also: legacy→a6k2 changed the user simulator (11/20 det tasks), so E5 needs the eager null. `docs/insights/iter_1_verdicts.md`, `docs/insights/LEDGER.md`, scripts `analysis/insights/iter_1/verify/v0{1..4}_*.py`.

## W9 · Llama-3.1-8B (l8) in the τ²-bench harness (2026-09-28 23:59 PDT)
**TL;DR** The l8 smoke run's 5 `infrastructure_error` episodes ("object of type 'NoneType' has no len()") were our
local prompt rendering, not the server. tau2's `to_litellm_messages` gives every assistant text turn `tool_calls: None`.
The Llama-3.1 template tests `'tool_calls' in message` and then takes `tool_calls|length`, so it crashed. The Qwen
template only tests truthiness. vLLM drops a None `tool_calls` and parses string `arguments` into dicts before it
renders, so it never crashed. Fix: `cloq/context_policy.template_view` applies the same normalisation before every
local render. Local prompt ids now equal the server's (smoke v1 17.5% → v2 100%). Qwen is byte-identical: 960 replayed
q4/q8/q30a3 decisions give the same text and match the server ids. l8 now uses the official meta repo, pinned. It also
sets `tools_in_user_message=false`, because by default the template relabels tau2's assistant greeting as a user turn
that carries the tool list. vLLM's `examples/tool_chat_template_llama3.1_json.jinja` is not in the wheel. We did not
adopt it: it has the same `tool_calls` test, and it stamps `strftime_now` (today's date) into the prompt. Smoke v2
(20 det tasks): no infra errors. airline db 0.2 / reward 0.2 / tool_err 0.22; retail db 0.2 / reward 0.0 /
tool_err 0.67 (q4: 0.04 / 0.16). The retail tool errors come from the model: it invents identifiers (21/38 "User not
found") and passes JSON arrays as strings (11/38). The template ablation gives the same retail rate (0.67).
- Code: `cloq/context_policy.py` (`template_view`, used by `render_prompt`/`render_prompt_ids`). Test:
  `tests/test_template_view.py` replays logged decisions (Qwen: identical text and 100% server-id match; l8: the raw path
  crashes on 165/165, `template_view` matches the server on 165/165). A synthetic case reproduces the crash.
- Model: `scripts/a6000/models.json` l8 = `meta-llama/Llama-3.1-8B-Instruct@0e9e39f249a16976918f6564b8830bc894c89659`.
  The 4 safetensors sha256 equal the unsloth mirror's (2b1879f3…, 09d433f6…, fc1cdddd…, 92ecfe1a…), and
  `hf cache verify` checked 14 files. The tokenizer encodes identically (57/57 prompts). The unsloth config/generation_config
  differ only in eos/pad metadata. The agent canary hash equals the unsloth one (`cbabe9a77c80c825`; old ref kept as
  `analysis/determinism/canary_agent_l8.unsloth.json`). The unsloth mirror was removed with `hf cache rm`. It freed only
  17 MB, because the shared blob store already deduplicated the weights with the meta repo.
- Runs: `/data/ziyangs/cloq/runs/a6k2_smoke_l8_v2/` (fix + `tools_in_user_message=false`) and
  `/data/ziyangs/cloq/runs/a6k2_smoke_l8tum/` (fix + default template, ablation: airline db 0.3 / tool_err 0.16 /
  16 tool calls per task with one max_steps; retail db 0.1 / tool_err 0.67). The ablation code `l8tum` was removed from
  models.json. Failed v1: `/data/ziyangs/cloq_work/queue/failed/a6k2_smoke_l8.json`, `/data/ziyangs/cloq_work/logs/tasks/a6k2_smoke_l8.log`.
- Consequence: l8's high retail tool-error rate belongs to the model, not to the harness. Treat l8 as a
  low-capability family (floor effects on db_match) when reading its perturbation nulls.

## W11 · Heavy-perturbation cells are GPU sinks; closed-loop k=3 deferred on q32/l8 (2026-09-29 04:55 PDT)
**TL;DR** From 01:22 to 04:53 only ~18 tasks finished. The reason: 7 slots were occupied for 5–6 h by k≥2 Gaussian and
redo cells, whose agents loop to max_steps with ~30k-token contexts. The batch-invariant kernels then run at ~50–80
generated tok/s and ~2k prefill tok/s per server. These were not hung (logs and metrics advance). Closed-loop gauss3 on
q32 and l8 (4 tasks) is moved to `/data/ziyangs/cloq_work/queue/deferred/`: it is a control under the
quantization-centred framing (PLAN_iter4) and costs roughly 6–10 GPU-h each. Their open-loop E3 cells stay queued (6 min each).
- Evidence: `/data/ziyangs/cloq_work/logs/tasks/a6k2_q4_gauss3_s1_redo.log` (8 sims running 40–100 min each),
  `.vllm.log` throughput lines; status snapshot in session.

## W10 · Context-window overflow is a task failure, not an outage (2026-09-29 03:00 PDT)
**TL;DR** `a6k2_q8_gauss2_s2` failed the W6 guard with 2 infrastructure_error episodes. They were not outages: a
heavily perturbed agent looped until the dialogue exceeded the simulator's 65,536-token window. That is the agent's own
failure. The worker now classifies each infrastructure_error from tau2's `info.error` into
`runs/<run>/<dom>/infra_causes.json` (context_overflow vs outage) and fails the task only on outages. Analyses
(`analysis/insights/iter_2/common.py`) count context_overflow as failure. The task was re-queued.
- Evidence: `/data/ziyangs/cloq_work/logs/tasks/a6k2_q8_gauss2_s2.log` (ContextWindowExceededError); fix `scripts/a6000/worker.py`.

## W8 · Duplicate decision records from resumed runs; more infra-error runs (2026-09-28 23:45 PDT)
**TL;DR** tau2's `auto_resume` and retries re-run a simulation, but `cloq.agent` appends to decisions.jsonl. So an
interrupted or retried task kept the records of its abandoned attempt (6,724 records in 52 run-domains). Outcomes were
unaffected (trajectory.jsonl is rebuilt from the final results), but per-decision analyses were polluted. Fix:
`scripts/a6000/dedup_decisions.py` keeps the last attempt per task (applied to all a6k2 runs; the remaining count
mismatches are only infrastructure-error episodes), and `cloq/run_arm.py` now does the same at the end of every run.
The rescan found 6 more runs with simulator-outage episodes from before the W6 guard; they were deleted and re-queued
(`*_redo`). Also: the runners on node004/005/007 crashed on an unknown model code (l8) after my W5 change. Their tasks
were re-queued, the runners resubmitted (49671–49673), and the runner now re-reads models.json (unknown model = not
claimable).
- Evidence: dry-run log in session; `scripts/a6000/dedup_decisions.py`; `/data/ziyangs/cloq_work/logs/node_node004_49664.out` (KeyError 'l8').
- Consequence: iter_2 analyses (p0x, c01, c02) must be re-run after the redos finish.

## W7 · X1 real deployed formats in the live pipeline (2026-09-28 23:50 PDT)
**TL;DR** Official Qwen3 AWQ-INT4 (q8/q14/q32) and FP8 (q4/q8/q14/q30a3/q32) checkpoints are served with vLLM
0.29 kernels in the a6k2 pipeline. Each cell gets canonical + 2 nonces, a node005/node004 det pair and E3 open-loop:
32 tasks, `make_tasks.py --only x1`. **KV-FP8 and bitsandbytes cannot run here** and are not queued.
Under our frozen numerics (`VLLM_BATCH_INVARIANT=1`), vLLM swaps the "deployed" kernels for batch-invariant ones:
- FP8 uses the Humming FP8 kernel (not FP8 Marlin, which vLLM rejects in batch-invariant mode).
- AWQ uses `awq_dequantize` + matmul (not awq_marlin), and it must run with FP16 activations.
The weights are the real deployed ones; the GEMM kernels are not. Smokes passed for both formats; q30a3 FP8 det pair
275/275 decisions identical so far.
- Checkpoints (HF cache `/data/ziyangs/cloq_work/hf`, pinned in `scripts/a6000/make_tasks.py::X1_HF`):
  Qwen3-8B-AWQ `4da05a8e`, 14B-AWQ `31c69efc`, 32B-AWQ `0499c3ac`, 4B-Instruct-2507-FP8 `85918040`, 8B-FP8 `220b46e3`,
  14B-FP8 `9a283b4a`, 30B-A3B-Instruct-2507-FP8 `5a5a7763`, 32B-FP8 `aa55da1e`. There is no official AWQ for the 2507
  models (q4/q30a3), so they have no AWQ cell.
- Same model variant: `analysis/x1/verify_checkpoints.py` → `analysis/x1/checkpoint_verification.json`. For all 8, the
  model card's `base_model` is exactly our BF16 repo. tokenizer.json, vocab, added/special tokens, chat_template and
  generation_config are hash-identical to our BF16 snapshot; config.json differs only in `torch_dtype` (AWQ: float16).
  The same `chat_template_kwargs` are passed: worker `model_env` is keyed by task model, so enable_thinking=false
  applies for q8/q14/q32. Smoke check: server-side prompt ids equal local BF16-tokenizer ids, 312/312 decisions; no
  thinking content.
- Code: `worker.py` ckpt kind `hf` (serve `hf_id@revision`; `runs/<id>/quantization.json` records the repo, revision
  and quantization_config) plus per-task `serve_env`; `make_tasks.py::x1` (priority 30+model; det −6; E3 ref `a6k2_<m>_bf16`,
  out `analysis/openloop/a6k2/<m>/<fmt>`); arms `x1_awq` / `x1_fp8`.
- Fix 1, FP8: Humming reads NVML device index 0 regardless of CUDA_VISIBLE_DEVICES. On node003 index 0 is the faulty card,
  so the server died with `NVMLError_Unknown`. `scripts/a6000/pyhooks/sitecustomize.py`, enabled only by
  `CLOQ_PYHOOKS=1` (FP8 tasks' `serve_env`; `env.sh` adds the dir to PYTHONPATH), remaps index i → CUDA_VISIBLE_DEVICES[i]
  inside humming only. Log: `/data/ziyangs/cloq_work/logs/x1/smoke1_failed_nvml.json`.
- Fix 2, AWQ: with BF16 activations the batch-invariant path crashes (`awq_dequantize` expects Half,
  `/data/ziyangs/cloq_work/logs/tasks/a6k2_det_q14_x1_awq_b.vllm.log`). AWQ cells therefore add `--dtype float16`, which is the
  checkpoints' config dtype and vLLM's default. This is a second difference from BF16 besides the weights. FP8 stays BF16.
- Dropped formats:
  - kv_fp8: on SM86, Triton attention refuses an FP8 KV cache ("native FP8 requires SM89+",
    `/data/ziyangs/cloq_work/logs/x1/withdrawn_kv_fp8/`). FA2 has FP8 KV only on SM90+, FlexAttention has none, and
    FlashInfer is not batch-invariant, so it is excluded under our protocol (vllm `v1/attention/backend.py:321`).
  - bnb: `--quantization bitsandbytes` was removed in vLLM 0.29 (not in `QUANTIZATION_METHODS`), and bitsandbytes is
    not installed.
- Smokes: `runs/a6k2_smoke_x1_q8_fp8` (det tasks, node005; retail 0.30, airline 0.10) and `runs/a6k2_smoke_x1_q8_awq`
  (node003; retail 0.20, airline 0.10; 1226 s vs 251 s for FP8, because the dequant path is slow). Downloads: `/data/ziyangs/cloq_work/logs/x1/download.{py,log}`.
- Open: an X1 variant with `CLOQ_BATCH_INVARIANT=0` would run the actual Marlin kernels, at the cost of batch-dependent
  numerics. `serve_env` supports it. A BF16 + TRITON_ATTN control would matter only if KV-FP8 ever becomes possible.

## W6 · Simulator outages scored as agent failures (2026-09-28 23:10 PDT)
**TL;DR** node003 uses node004's user simulator. When I restarted node004 (19:43 and ~21:50), node003 episodes ended in
`infrastructure_error`, yet the tasks exited rc=0. 11 run-families had ≥2 such episodes (q4 nulls n3–n5 were 100%).
Scored as failures, they would have fabricated +8–16 pp "gains" and a −23 pp q8 W3 "loss". Fix: those runs were
deleted and re-queued as `*_redo`, pinned to nodes with their own simulator. The worker now fails any run with an
infrastructure_error. Analyses treat such episodes as missing (`analysis/insights/iter_2/common.py` INFRA).
- Evidence: `docs/insights/iter_2_prep.md` §0 F1; `/data/ziyangs/cloq_work/logs/tasks/a6k2_q4_bf16.log` ("Connection
  refused"); fix `scripts/a6000/worker.py` (termination_reasons check).
- Also queued: E8 FP32-head control (`a6k2_*fp32h*`, spec in `docs/insights/iter_2_prep.md` §E8).

## W5 · TP=2 starvation fix (2026-09-28 22:00 PDT)
**TL;DR** A freed card was always taken by a 1-GPU task, so no NVLink pair ever became free. At 21:49, q30a3 and q32
main cells stood at 5 and 3 done with 0 running. Fix: while a runnable 2-GPU task waits, the upper agent pairs
(4,5)(6,7) take only 2-GPU tasks. Runners on node004/005/007 were restarted (jobs 49664/49665/49666).
- Evidence: queue counts at 21:49 in this entry. Fix: `scripts/a6000/noderunner.py` (`tp2_wait`, `reserved`).

## W4 · TP=2 on NVLink pairs only (2026-09-28 20:45 PDT)
**TL;DR** `a6k2_q32_bf16_cal` hung in NCCL init on node005 GPUs 5,6, a cross-switch pair with no NVLink. The runner now
gives 2-GPU tasks only NVLink pairs (0,1)(2,3)(4,5)(6,7), and single-GPU tasks prefer broken pairs. This likely also
explains the earlier node007 TP=2 hangs. Runners on node004–007 were restarted (jobs 49638/49639/49641/49642; node006
is down to 4 GPUs because mg546924 took 4).
- Evidence: `/data/ziyangs/cloq_work/logs/tasks/a6k2_q32_bf16_cal.vllm.log` (stops after `pynccl.py:113`), topology
  from `nvidia-smi topo -m` (NV4 within pairs, NODE/SYS across). Fix: `scripts/a6000/noderunner.py` (allocation).

## W3 · Cross-node determinism incident (2026-09-29, root cause found, fix deployed)
**TL;DR** torch Inductor picked the reduction config for the fused residual+RMSNorm kernel by timing it at compile
time: R0_BLOCK 2048 on node005 vs 4096 elsewhere. The summation order changed, so every token shifted, and vLLM batch
invariance does not cover this. Fix: `TORCHINDUCTOR_DETERMINISTIC=1` plus a numerics canary at every server start.
The whole matrix is re-run as `a6k2_*`; old `a6000_*` runs are kept as a legacy "numerics flavour" null (E5).
- Symptom: `runs/a6000_det_q4_a` (node005) vs `runs/a6000_det_q4_b` (node004): 20/20 tasks and 113/113
  identical-prompt decisions shift; `analysis/insights/iter_1/out/s04_node_floor.json`,
  `analysis/insights/iter_1/exp/e_detshift.py`.
- Kernels are identical across nodes: `/data/ziyangs/cloq_work/numtest.py` (hash `932e7dab8e342639` on node004–007).
- Runtime is not the cause: `analysis/determinism/probe_q4.json`. On node006, cold / warm / concurrent / no-prefix-cache
  all match node004 30/30; eager is a third flavour (A 14/30, B 16/30). Script `scripts/a6000/det_probe.py`.
- Root cause (experiment agent): `analysis/insights/iter_1/exp/e_bestconfig.sh`, `e_server_flavour.py`;
  discussion `docs/insights/iter_1_discussion.md` (Experiment round 1), plan E1–E6 `docs/insights/EXPERIMENTS.md`.
- Fix: `scripts/a6000/env.sh` (flag), `scripts/a6000/worker.py::check_canary`; references in
  `analysis/determinism/canary_{agent,sim}_<model>.json`; per-start log `/data/ziyangs/cloq_work/logs/canary.log`.
- **Fix verified (2026-09-28 20:00 PDT):** `runs/a6k2_det_q4_a` (node005) vs `runs/a6k2_det_q4_b` (node004): 257/257 decisions
  byte-identical (prompt + completion), identical metrics. q30a3 pair 303/303 identical. Canary log
  `/data/ziyangs/cloq_work/logs/canary.log`: sim + q4/q8/q30a3 agents match on every node so far.
- Rerun: `scripts/a6000/make_tasks.py --prefix a6k2`. Old unfinished tasks archived in
  `/data/ziyangs/cloq_work/queue/legacy_v1/`.

## W2 · A6000 matrix running (2026-09-28 18:10 →)
**TL;DR** 5 models × 30 configs + determinism pairs; 110 tasks on node003–007 (38 GPUs). Checkpoints live only in
node RAM disk.
- Plan: `docs/A6000_PLAN.md` §3. Generator: `scripts/a6000/make_tasks.py`. Runner/worker: `scripts/a6000/{noderunner,worker}.py`.
- Live queue: `docs/a6000/QUEUE.md` (snapshot pushed every 30 min); `/data/ziyangs/cloq_work/queue/{todo,running,done,failed}/`.
- Logs: `/data/ziyangs/cloq_work/logs/node_<node>_<job>.out` (runner), `.../logs/tasks/<task>.log` (worker + run_arm),
  `.../logs/tasks/<task>.vllm.log`, `.../logs/sim_<node>_<job>.log` (user simulator).
- Per-run artifacts: `runs/a6000_<model>_<config>/<domain>/{metrics,status,config,environment,model}.json`
  (in git), `decisions.jsonl` / `trajectory.jsonl` (cluster only).

## W1 · Phase 0 + environment (2026-09-28)
**TL;DR** Driver 550 cannot run the pinned cu130 stack, so we built the cu129 builds of the same versions. Code is
model-generic with per-token margins. RTN is bit-identical to v1. Smoke test passed.
- Commits `3313d01`, `724b3dc` (and later). Env notes: `env/README_A6000.md`.
- Smoke test: `/data/ziyangs/cloq_work/logs/smoke/49592.out` (3 retail tasks, 83 s, 35/35 decisions with margins,
  server/local prompt ids identical).
- RTN equivalence check (vectorized vs `cloq/gptq.rtn_quantize_linear`, W8/W4/W3 on q4 layer 0): identical — command
  in session log; code `cloq/compress.py`.
- Node GPU faults: node003 PCI 01:00.0 and E1:00.0 (probe in `scripts/a6000/node.sbatch`; log
  `/data/ziyangs/cloq_work/logs/node_node003_49601.out`).

## V5 · Perturbation null on 4B (4080, 2026-09-28 → 09-29)
**TL;DR** BF16 × 5 nonces; Static / FP-Traj / RTN × 3 nonces; 8k harness. Results arrive with release `data-4080`.
- Script: `scripts/null_rerolls.sh`. Handoff: `docs/HANDOFF_4080_FINAL.md` (when pushed).

## V4 · E4 8k vs 32k context control (4080, 2026-09-28)
**TL;DR** Removing truncation lifts every model by 0.01–0.04 and leaves the ranking almost unchanged, so the main
harness moved to 32k. A W4 checkpoint beats BF16 under both harnesses, which is a live example of re-roll noise.
- Evidence: `docs/PROGRESS_2026-09-28.md` §2 (table); script `scripts/ctx_control.sh`; runs `runs/ctx32k_*`
  (4080; in `data-4080`).

## V3 · Strategy pivot to evaluation science (2026-09-28)
**TL;DR** A 48-agent strategy workflow plus an independent recompute. Flips are decided by the state (AUC 0.93).
Open-loop NLL does not track closed-loop success (|r| ≤ 0.13). Failures are write-dominated. Loops are mostly
agent-side.
- Strategy: `docs/STRATEGY_v2.md`. Recompute: `analysis/coling/RESULTS.md` + `analysis/coling/0[1-5]_*.py`.
- Workflow analyses: `analysis/strategy_v2_workflow/{mechanism,truncation,variance}/` (e.g. `mechanism/res_churn.json`).
- Loop attribution: `analysis/coling/04_loop_attribution.py`. Retired claims / reporting conventions: `docs/PROGRESS_2026-09-28.md` §3.

## V2 · v1: 3 draws × 6 arms (4080, 2026-09-16 → 09-27)
**TL;DR** The six calibration arms cannot be told apart in closed loop (arm permutation p = 0.683 pooled / 0.368
long). The CLOQ method claim is falsified. Draw variance is amplified by the closed loop.
- Evidence: `analysis/v1/FINDINGS_V1.md`, `analysis/v1/REPORT_V1.md`, `analysis/v1/results_v1.json`,
  `analysis/V1_STATUS_2026-09-16.md`, amendments `analysis/amendments/`. Protocol: `docs/PLAN_v1.md`, `configs/frozen_v1.json`.

## V1 · v0: single draw, 4 arms (4080, ≤ 2026-09-16)
**TL;DR** Horizon amplification (short 0.000 vs long 0.189, p = 0.039). Open-loop fidelity does not predict
closed-loop success. Support shifts after the first divergence. FP-Traj +0.121 later proved a false positive
(McNemar p = 0.0195; replication −0.035).
- Evidence: `analysis/FINDINGS.md`, `analysis/REPORT.md`, `analysis/results.json`, `analysis/occupancy_obs.json`,
  figures `analysis/fig2_horizon.png`, `analysis/fig6_openloop_vs_closedloop.png`; false-positive recompute
  `analysis/coling/02_v0_gap.py` → `analysis/coling/RESULTS.md`. Protocol: `docs/PLAN_v0.md`, `configs/frozen_v0.json`.
