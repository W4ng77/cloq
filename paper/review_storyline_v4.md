**TL;DR** Storyline v4 is the most coherent framing this project has had, and the λ–c decomposition is a useful way to report the results. The headline claims, though, go further than the numbers. (a) "c follows method" does not survive a paired draw-and-task bootstrap on q4 (no difference from RTN excludes 0), is absent on q8, and is unidentified on q14/q30a3. The same-method calibration draw (GPTQ d1 vs d2: c 0.47 vs 0.27) and Gaussian seed-to-seed spread are as large as the between-method gaps. (b) "Re-rolls 20–40% of tasks, 5–10× the null" is measured against a prompt-nonce null. A function-preserving numerics change (rot_bf16) already re-rolls about 12% (λ). Against that floor, W4 is about 2× for breaks and about 1× for RTN fixes. On q14/q30a3, calibrated W4 λ is 0.01–0.17. (c) "λ follows size, not structure" is contradicted by the team's own r08: isotropic Gaussian at RTN norm has a higher λ than RTN, pooled +0.14 [0.01, 0.28]. (d) The "higher p̄ → more damage" prediction cannot be tested, because p̄ spans only 0.29–0.38. Score as-is: **2.5 / 5**, projected **3.5 (up to 4)** if the checkpoint-replication and held-out confirmatory runs are done and the claims are rescoped. Recommended reframing: "to an agent, W4 quantization behaves like a matched random perturbation: it re-rolls a model-specific fragile set at a method-invariant rate, and the net outcome is a checkpoint lottery that single-checkpoint method comparisons cannot resolve".

# Review of Storyline v4 (ARR Oct 2026 → NAACL long): storyline and contributions

Reviewer role: ARR reviewer plus area chair, adversarial but constructive. Date: 2026-09-29. Freeze 10-05, deadline 10-12.
Object: `docs/insights/STORYLINE_v4.md`. I checked it against `docs/RESEARCH_LOG.md` (W12–W16), `docs/FINAL_EXPERIMENTS.md`, `docs/insights/PLAN_iter4.md`, `docs/insights/NULL_RULE.md`, `analysis/insights/iter_3/r01_realloc.py`, `analysis/insights/iter_3/out/r01_realloc_{unfrozen,live,frozen}.json`, `out/r0{3,5,6,8}_frozen.log`, `paper/review_v2.md`, `docs/insights/SURVEY.md`, `manifests/task_split_v0.json` and the queue directory.

**Checks this reviewer ran (read-only):**
- A hierarchical bootstrap (tasks and draws both resampled, B = 2000, paired across families on the same task indices). It reuses `r01_realloc.stats/lamc`, on unfrozen data for q4/q8/q14. The script is `/tmp/claude-1064/.../scratchpad/chk.py`, a scratch file outside the repo. Its numbers are quoted below as "[HB]".
- arXiv API lookups of the competitor IDs, and one web query plus an abstract fetch for Flat Score.

---

## Part 1: Structured review

## Summary

The paper studies what weight quantization does to closed-loop tool-using agents on τ²-bench retail and airline. It uses 85 tasks, 5 Qwen3 sizes plus Llama-3.1-8B, greedy decoding under batch-invariant deterministic serving, and a fixed Qwen3-30B-A3B user simulator. The yardstick is the model's own BF16 "perturbation null": 8 prompt-nonce re-runs.

Tasks are stratified by their null success (always-ok / always-fail / coin). Each quantized family is then summarised by a shrink-to-attractor model, p_i' = (1−λ)p_i + λc. λ measures how much quantization re-rolls outcomes; c measures where the re-rolled tasks land. Net change follows Δ = λ(c − p̄).

The storyline claims four things:
- C1: a null-referenced equivalence protocol.
- C2: quantization *reallocates* rather than removes capability.
- C3: λ is set by error size, and c by the quantization method.
- C4: a cheap open-loop probe predicts λ, closed loop is needed for c, plus a failure taxonomy.

On infrastructure and integrity this is well above typical agent-evaluation papers:
- deterministic serving with canaries;
- a pre-registered null-admission rule;
- per-draw reporting;
- documented integrity incidents.

The scientific core is the decomposition of "same score, different tasks" into a turnover rate and a landing rate, measured against a proper null. The contribution depends on whether (i) λ is quantization-specific rather than generic perturbation chaos, and (ii) c is a property of the method rather than of the particular checkpoint. The current evidence supports (i) weakly, and only on the two smallest models. It does not yet support (ii).

## Strengths

- **[S1] The infrastructure makes a closed-loop null possible at all.**
  - Batch-invariant serving with canary hashes and cross-node determinism pairs (257/257, 303/303; FINAL_EXPERIMENTS B8).
  - Nonce-stratified nulls with a frozen admission rule (NULL_RULE NR1, sha recorded in manifests).
  - Few agent-quantization papers can separate re-roll noise from quantization this cleanly. Flat Score (arXiv 2607.27275), in the same benchmark and model family, cannot.
- **[S2] The estimator handles misclassification correctly under its own model.**
  - The reference set is always size n_ref = |U|−1 for both the null and the family draws, and nonce-mates are removed (`ref_sets`).
  - The b0/f0 correction is the right linear-model correction for "always-ok from 7 draws is not p = 1".
  - This is better than the pilot's LOO heuristic.
- **[S3] There is a built-in out-of-sample check.** λ and c are fit on the extreme strata only and then predict the coin stratum (`dcoin_pred`, `coin_resid_ci`). Where it works it is striking: q4 AWQ −0.012 observed vs −0.012 predicted, and RTN-W4 −0.067 vs −0.057 (`r01_realloc_unfrozen.json`). It should become a headline validation, not a column in a JSON file.
- **[S4] The method-invariance of λ at W4 is the most robust quantitative regularity in the data.**
  - q4: RTN 0.24, GPTQ 0.25, AWQ 0.25, rot_rtn 0.23, rot_gptq 0.23, MXFP4 0.22.
  - Pooled over 4 models (r08): RTN−GPTQ Δλ = +0.013 [−0.083, 0.115] and RTN−AWQ −0.010 [−0.141, 0.122].
  - Calibration and rotation do not reduce turnover. This is a clean, practically relevant, falsifiable statement.
- **[S5] Within-model fragility is shared across perturbation types, and it is model-specific.**
  - Breaks under quantizer X are predicted by breaks under Gaussian noise (AUC 0.82–0.84 on q4/q8/q14; `r03_frozen.log`).
  - Across models the AUC is about 0.5 (`r06_frozen.log`: 0.35–0.63).
  - This is new at task level in closed loop, and it contrasts with Hooker et al.'s "data-property" reading of compression-identified exemplars.
- **[S6] Reporting is honest in the right places:** per-draw λ lists, power/MDE of 6.5–13 pp, a written Risks section, and superseded numbers explicitly flagged (W15 "different metric … superseded").

## Weaknesses

- **[W1] FATAL (for the claim as worded): "c follows method" is not supported. The within-method checkpoint lottery is as large as the between-method gap.**
  - Evidence is q4 only. Each method is essentially one checkpoint: RTN is deterministic, and GPTQ/AWQ have ≤2 calibration draws. All draws of a family share the same weights and differ only by nonce.
  - The task bootstrap in r01 does not resample draws or checkpoints.
  - [HB] paired differences vs RTN on q4, Δc:

    | method | Δc vs RTN | one-sided P(≤0) |
    |---|---|---|
    | GPTQ | +0.26 [−0.07, 0.70] | 0.063 |
    | AWQ | +0.17 [−0.13, 0.47] | — |
    | rot_rtn | +0.19 [−0.27, 0.77] | — |
    | rot_gptq | +0.32 [−0.05, 1.05] | 0.042 |
    | MXFP4 | +0.23 [−0.18, 0.83] | — |
    | NF4 | +0.26 [−0.03, 0.59] | 0.037 |

    No two-sided 95% interval excludes 0. With 8–11 comparisons, nothing survives Holm.
  - **Same method, different calibration draw:** q4 GPTQ-W4 d1 has c = 0.47 and Δ = +4.6 pp. GPTQ-W4 d2 has c = 0.27 and Δ = −4.5 pp (`families["ckpt:gptq_w4_d1"|"ckpt:gptq_w4_d2"]`). The calibration draw moves c across p̄ ≈ 0.36, which is the same magnitude as the RTN (0.18) vs GPTQ (0.45) contrast the story rests on. Singh 2026 (arXiv 2608.15046) reports the calibration seed reversing GPTQ/AWQ rankings in 5/8 cells, so a reviewer will know this.
  - **Same size, different Gaussian seed:** q4 k=1 seeds s1–s5 give composed c of 0.22, 0.48, 0.04, 0.04 and 0.24. q8 k=1 seed s1 (fixed, 2 nonces) gives λ 0.27, while seeds s2–s5 give λ 0.58–0.67 (composed 0.52–0.62).
  - **q8:** c is flat across methods: RTN 0.20, GPTQ 0.22, AWQ 0.19–0.21. [HB] GPTQ−RTN Δc = 0.00 [−0.99, 0.60].
  - **q14/q30a3:** c is unidentified wherever λ is small. For example, q14 AWQ has c CI [−2.4, 2.6], and q30a3 GPTQ λ 0.013 gives c = 2.68 [−7.2, 7.5] (`r01_realloc_live.json`).
  - **Domain split:** c is not stable within a cell. q4 RTN has c = 0.22 on retail and −0.05 on airline. q8 RTN has 0.05 on retail and 0.89 on airline (`by_domain`).
  - Conclusion: with 3 draws of one checkpoint per cell, "c follows method" is not defensible. At best the data say "on q4, calibration-aware W4 checkpoints tended to land above RTN". The claim needs ≥3 independent checkpoints per method (see Revision Plan R1).

- **[W2] MAJOR: the "reallocation" magnitude is quoted against the wrong floor, and it fades with model size.**
  - "Re-rolls 20–40% of tasks" and "break/fix 5–10× the null rate" compare against the prompt-nonce null (q4 b0 = f0 ≈ 0.02). But a *function-preserving* numerics change already has λ = 0.12 [−0.01, 0.25] (q4 rot_bf16). The canonical prompt vs nonce has λ = 0.09 (q4 null_K) and 0.12 (q8). Tiny Gaussian noise (k = 0.001) has λ 0.15 (q4) and 0.09 (q8).
  - Implied break/fix rates (b = (1−λ)b0 + λ(1−c), f = (1−λ)f0 + λc) on q4:

    | cell | break | fix |
    |---|---|---|
    | RTN-W4 | 21.6% | 5.9% |
    | GPTQ-W4 | 15.3% | 12.8% |
    | rot_bf16 | 11.5% | 4.0% |

    Against a numerics floor, RTN breaks are about 1.9× and RTN fixes about 1.5×, not 5–10×. The pilot's "RTN fix 11%" in PLAN_iter4 is stale.
  - A skeptical reviewer will say the phenomenon reduces to "greedy agents are chaotic, and any bit-level change re-rolls ~10% of tasks". The project's own v3 floor story (hazard from 1-ulp noise, `review_v2.md` summary) supports that reading.
  - **Size trend:** calibrated W4 λ is 0.10–0.17 on q14 (live) and 0.01–0.11 on q30a3. RTN-W8 λ is −0.03 on both. So "20–40%" is a q4/q8 statement.
  - Fix: report λ in excess of a checkpoint-level floor (λ_composed against rot_bf16 / k = 0.001 seeds / null_K). Restate the headline as a dose-response *above the floor*: W8 ≈ floor, W4 ≈ 2× floor on small models, W3 ≫ floor.

- **[W3] MAJOR: "λ follows error size, not structure" overreaches and is partly contradicted.**
  - The r08 pooled result (4 models) is that isotropic Gaussian at RTN-W4 Frobenius norm has a higher λ than RTN: +0.139 [0.013, 0.276], p = 0.017, 4/4 models positive. On q8 the difference is +0.39 [0.02, 0.78] (`r08_frozen.log`). So Frobenius size does not determine λ.
  - The E17 controls that match *per-group* statistics also sit at or above RTN (q4 gshape −RTN +0.17, P(≤0) 0.049 [HB]; q8 rtnsign +0.22, P 0.056). The honest statement is one-sided: RTN's error structure is not specially harmful, and random error with matched per-group magnitude re-rolls at least as much.
  - That is Kennedy & Kennedy 2026's (arXiv 2609.33923) spectral-flatness and channel-energy account carried into behaviour. It is a nice confirmation, but it is not an independent discovery.
  - "CIs overlap" is being used as evidence of equality. Equality needs an equivalence test (TOST on Δλ with a declared margin, e.g. ±0.10), pooled across models.
  - The Gaussian dose ladder is non-monotone at small k on q4: 0.001 → 0.15, 0.01 → 0.27, 0.03 → 0.06, 0.1 → 0.09. A one-draw-per-seed ladder cannot establish that "λ tracks size".

- **[W4] MAJOR: the λ–c model is a saturated reparametrisation of (break, fix) on the extremes. Its testable content has to be put up front.**
  - Two moments (b, f) map one-to-one to (λ, c): λ ≈ corrected churn, and c ≈ f/(b+f), corrected. Δ = λ(c − p̄) then holds by construction for the average over tasks *if* the single-attractor assumption also holds on the coin stratum.
  - A reviewer will say: "λ is churn, c − p̄ is net Δ divided by churn. This is Dutta et al. 2024 flips plus Singh 2026 churn/|Δacc| ≈ 5.4, relabelled".
  - The defence is the falsifiable parts:
    - (i) the coin-stratum prediction;
    - (ii) the task-independence of c;
    - (iii) the base-rate prediction.
  - Status of each:
    - **(i)** Underpowered. It rejects in several cells: q8 gauss1 residual [0.056, 0.374], q8 GPTQ-W3 [0.012, 0.380], q14 GPTQ-W3 (live) [−0.443, −0.072], q30a3 RTN-W8 [0.016, 0.232]. It is not reported anywhere in the storyline.
    - **(ii)** Contradicted in spirit by S5. Break-proneness is task-specific (AUC 0.82–0.84), so λ is really λ_i. That is fine for a descriptive average, but the "attractor" language implies a mechanism the data do not show.
    - **(iii)** Untestable (W5).
  - Present λ, c as a *descriptive* two-number summary with a model check. Do not present them as a mechanism.

- **[W5] MAJOR: the "larger net damage at higher p̄" prediction has no leverage and is backed by non-evidence.**
  - Across models, p̄ is 0.29 (q8), 0.36 (q4, q14) and 0.38 (q30a3): a range of 9 pp.
  - The cited support ("W3 damage q8 −16.7 pp, q14 −14.5 pp") compares cells with different λ. On q4 (p̄ 0.36) RTN-W3 is −22.8 pp with λ 0.79. On q8 (p̄ 0.29) it is −15.8 pp with λ 0.57. That is λ-driven, not p̄-driven.
  - Within-model domain splits do not help: c itself swings wildly by domain (W1).
  - Drop the prediction, or test it properly. One option is to manipulate p̄ at fixed checkpoint, for example by success criterion (DB-match vs reward) or error budget (Flat Score's lever), and check whether Δ scales with (c − p̄). Otherwise it is a free parameter dressed as a prediction.

- **[W6] MAJOR: the evidence cited is ungated and incomplete.**
  - The storyline's numbers come from `r01_realloc_unfrozen.json`. Its `_snapshot` is `{"id": null, "path": null, "tag": "unfrozen"}`, i.e. no integrity gate, which contradicts the S1 policy.
  - That file contains **only q4 and q8**, while W15's table quotes q14 values (RTN 0.25 [0.06, 0.45], gshape 0.20, rtnsign 0.35) that are in no cited file.
  - The storyline's "partial ρ given dose 0.86" is A2-15 (`d01_matched_dose.json`, flip rate vs *per-decision hazard*, iteration 2, pre-dedup era). It is not a partial correlation for λ. The λ correlations are r05: ρ 0.83 (q4, 16 cells) and 0.76 (q8, 11 cells), across cells spanning the dose ladder, with no dose control.
  - This is the same failure review_v2 flagged as W-A. It is not fatal only because the freeze-and-regenerate step is already planned.

- **[W7] MAJOR: the task set is pre-filtered, and half the benchmark is unused.**
  - The 85 tasks are the `evaluation` split of `manifests/task_split_v0.json` (58 retail + 27 airline).
  - 57 calibration tasks (39 + 18), left over from the falsified CLOQ method, are not used.
  - 22 tasks were excluded as "unstable" because they terminated by max_steps or errors in the legacy BF16 run (`excluded_unstable`, `stability_rule`).
  - Filtering on BF16 termination removes the long-horizon, looping tasks where quantization failures (premature stop, loops, context overflow per W10/W11) concentrate. This probably shifts λ and the failure taxonomy.
  - It must be disclosed. The unused 57 tasks are the obvious venue for a **pre-registered confirmatory replication** (R2).

- **[W8] MAJOR: multiplicity and post-hoc selection.**
  - "c follows method" was noticed on q4 after W15 and then promoted to C3. Its caveat (q8 AWQ λ 0.39 vs RTN 0.19) already cuts the other way.
  - The contribution table implies ≥8 method families × 3–5 models × {λ, c, Δ, coin residual}, with no family-wise control and no pre-registration. NULL_RULE shows the team knows how to pre-register; do the same for the λ/c hypotheses before the frozen rerun.

- **[W9] MAJOR: generality threats.**
  - **One benchmark, one simulator.** τ² retail/airline with a fixed Qwen3-30B-A3B simulator. The simulator is itself an LLM whose responses depend on the agent's wording, so part of λ is the *simulator's* chaos. A reviewer will ask for a second simulator on a subset.
  - **Fake quantization.** Dequantised to bf16 with batch-invariant kernels. X1 (real FP8/AWQ weights, non-deployed kernels; AWQ with FP16 activations) is the partial answer. Keep review_v2 W-F's labelling.
  - **Greedy only.** With T > 0 sampling, the null *is* sampling variance and λ may be absorbed into it. That is the deployment-relevant question.
  - **Qwen-only if Llama fails.** l8 is low-capability (retail tool_err 0.67, W9). With few always-ok tasks, λ and c are unidentified there (q8 already has only 11.4 ok tasks, so one break moves b by 8.8 pp).

- **[W10] MINOR: C1 is useful but the least novel, and it competes on three fronts.**
  - Singh 2026 (TOST, declared margins, static tasks).
  - Noise Floor Audit (Chen et al. 2026, arXiv 2608.22331: "the choice of null dominates").
  - Flat Score (arXiv 2607.27275; same benchmark, Qwen, AWQ/FP8, equivalence tests, no score change survives correction).
  - The "v0 false positive" anecdote (+12 pp p = 0.02 → −3.5 pp) is good motivation. The protocol itself has to be positioned as "null = the model's own perturbation family, stratum-matched", which is what those papers lack.

- **[W11] MINOR: scope versus the queue.** At review time the queue held 183 todo, 22 running and 39 deferred, with simulators saturated (W16). KV-cache INT8/INT4+H, NF4/MXFP4 on q8/q14, telecom and l8 all compete with the two experiments that decide the paper (R1, R2).

- **[W12] MINOR: terminology.**
  - "Reallocation" implies conservation. Δ is ≈ 0 only when c ≈ p̄, so use "turnover" or "re-roll" for λ.
  - "Attractor" implies dynamics that are not shown.
  - "5–10×" and "20–40%" appear without their denominators.

## Answers to the six questions asked

**1. Is the one-sentence story compelling and novel?** It is compelling, but it is not novel as stated. "Quantization changes which items are solved at equal accuracy" is prior work:
- Dutta et al. 2024 flips (arXiv 2407.09141): W4 AWQ/GPTQ flips of 4–8%, balanced wrong→right ≈ right→wrong. That is literally "reallocation with c ≈ p̄".
- Hooker et al. 2019/2020: "compression cannibalizes a small subset".
- Vallecillos-Ruiz et al. 2026 (program repair): 58 vs 61 bugs with 29 overlapping.
- Singh 2026: churn 5.4× |Δacc|.
- Flat Score: same benchmark, amplified failures.

A skeptical reviewer's one-liner: *"flips are known; in a chaotic closed loop any perturbation re-rolls tasks (their own rot_bf16 does 12%); the λ–c model is churn and net Δ renamed."*

What is actually new and defensible:
- (a) turnover measured against the model's *own* closed-loop null, with misclassification correction;
- (b) turnover is method-invariant at fixed bit width (calibration and rotation don't buy stability);
- (c) the fragile set is shared across perturbation types within a model but does not transfer across models;
- (d) because the net is a checkpoint lottery, single-checkpoint method comparisons on agent benchmarks are unreliable.

(d) needs R1 but would be the most NAACL-relevant message.

**2. Statistical soundness of λ–c.**
- **Identifiability.** The model is exactly identified by (b, f), so the only checks are the coin residual and cross-condition stability. c = (f − (1−λ)f0)/λ is a ratio estimator: biased and heavy-tailed as λ → 0. It is unidentified for |λ| ≲ 0.15 at 85 tasks. Examples: q8 gauss0.03 c CIs [−11, 8]; q14 AWQ [−2.4, 2.6]. Report c only when the λ lower CI is above ~0.1, or report the landing fraction f_excess/(b_excess + f_excess) with a bounded CI.
- **Reference sets.** The size-matched construction is correct. But b0 and f0 come from 8 LOO draws with mostly 0 or 1 events each (q4 per-draw b0 ∈ {0, 0.053}), and their uncertainty enters only through task resampling. n_ref also differs by model (q14 had |U| = 4–5), so stratum composition, and the meaning of "always-ok", differ across models.
- **Base-rate/stratum confound.** λ is a per-stratum rate, so it is not mechanically confounded with p̄. But on q8 the ok stratum is 11.4 tasks, so b (and hence λ) is estimated from ~11 tasks; q4 has 18. Cross-model λ comparisons therefore have very different precision, and the ok/fail sizes shift with the model's base rate.
- **CIs vs claimed differences.** The task bootstrap ignores draw and checkpoint variance. [HB] widens the c intervals (q4 RTN c [−0.01, 0.54]). Every claimed method difference in c is inside the noise (W1).
- **"q4 with 3 draws per cell"** is not defensible for a method claim, because the unit of replication for "method" is the checkpoint, not the nonce.
- **Multiple comparisons.** No family-wise control over families × models × statistics (W8).

**3. Are C1–C4 separable, and which is strongest?**

| # | Separable? | Assessment |
|---|---|---|
| C1 | Yes | Solid but incremental; it is the yardstick. Keep it as the method section, and keep it *short*. |
| C2 | Merge with C3's λ half | The phenomenon without the "20–40%/5–10×" framing, plus λ invariance across W4 methods (pooled TOST) and the dose-response above the numerics floor. **Strongest** once rescoped. |
| C3 (λ) | Merge into C2 | "Not specially harmful vs matched random error" (one-sided), with Kennedy as mechanism. |
| C3 (c) | Demote or cut unless R1 succeeds | If R1 shows checkpoint variance ≳ method variance, flip it into the headline caution: method rankings from one checkpoint are unreliable. |
| C4 | Cut as a contribution | The probe's ρ is dose-confounded and the 0.86 is for hazard, not λ. The failure taxonomy (S8) is not done. Keep the within/cross-model fragility result (S5) as an analysis section. The probe and checklist become a 5-line recommendation. |

Net: three contributions. (1) A null-referenced protocol. (2) Turnover: method-invariant, dose-dependent above a floor, landing on a model-specific fragile set. (3) The net effect as a checkpoint lottery (conditional on R1), or else a descriptive λ/c table.

**4. Missing controls and experiments, ranked by value and feasibility before 10-05.** Details are in the Revision Plan. In order:
- R1: checkpoint replication per method.
- R2: a pre-registered held-out confirmatory run on the 57 unused tasks.
- R3: a checkpoint-level floor (rot_bf16 seeds, k = 0.001 seeds) as the λ denominator.
- R4: a paired, draw-resampled analysis with TOST on Δλ (0 GPU-h).
- R5: a T = 0.7 slice.
- R6: a simulator swap on a subset.
- R7: include the 22 "unstable" tasks.

**5. Threats.** Single benchmark (τ² retail/airline). Simulator dependence (W9). Fake quantization, partly answered by X1. Qwen-only in practice (l8 floor effects). The 85 pre-filtered tasks (W7). Power: MDE 6.5–13 pp per family. A reviewer will accept one benchmark if the paper (i) states scope explicitly, (ii) shows held-out-task replication (R2), and (iii) shows the effect is not a simulator artefact on a subset (R6). Telecom (B7) is nice-to-have, not decisive; don't let it crowd out R1/R2.

**6. Framing, title, Figure 1, abstract claim.**
- **Title (suggested):** *"Quantization Re-rolls LLM Agents: Measuring Task Turnover Against the Model's Own Noise"*, or *"Same Score, Different Tasks: …"*.
- **Figure 1:** a two-panel task × condition raster for q4, sorted by null p̂.
  - Left: BF16 nonce draws, rot_bf16 and RTN-W8, which are near-identical.
  - Right: RTN-W4, GPTQ-W4 d1, GPTQ-W4 d2, W3.
  - Break/fix counts are annotated, and a bar shows the aggregate score barely moving.
  - An inset plots λ vs weight-error size with the numerics-floor band shaded.
- **Abstract key claim (supportable today, pending freeze):** "On τ²-bench, 4-bit weight quantization of small Qwen3 agents changes the outcome of roughly twice as many tasks as function-preserving numeric changes (λ ≈ 0.22–0.25 vs 0.09–0.12 on 4B). This turnover is the same for RTN, GPTQ, AWQ, rotation and MXFP4, and it is no larger than for random weight noise of matched per-group magnitude. It lands on a model-specific set of fragile tasks, and whether it nets out to damage varies across checkpoints of the same method as much as across methods. Aggregate-score comparisons of quantizers from a single checkpoint and run therefore do not identify the better method." The last sentence needs R1.

## Questions for authors

- [Q1] How many independent checkpoints per method can you produce by 10-05 (GPTQ/AWQ calibration seeds d1–d4; rot_rtn with rotation seeds 0–3 as independent "RTN-like" checkpoints)? What is the pre-declared variance decomposition (method vs checkpoint vs nonce)?
- [Q2] Why is the nonce null, rather than a checkpoint-level null (rot_bf16 seeds, k = 0.001 seeds, eager/compiled), the denominator for "5–10×"? NR1-1 explicitly excludes these controls. Should a v2 rule add them as a "numerics floor" reference?
- [Q3] Were the 22 "excluded_unstable" tasks ever run under the a6k2 pipeline? What are their λ/c?
- [Q4] What is λ's definition in words for a reader: a fraction of tasks, or a shrinkage weight? The "re-rolls 20–40% of tasks" gloss is only valid under the mixture reading.
- [Q5] Does the coin-stratum check pass at a declared rate across all cells (count of residual CIs excluding 0 vs the ~5% expected)?
- [Q6] For l8, how many always-ok tasks are there? If < 10, λ/c should not be reported for l8.

## Verdict

**As-is: 2.5 / 5 (Borderline-weak / "Findings" territory). Confidence 4/5.**
- The engineering and null design are strong, and the λ-invariance and fragile-set results are interesting.
- But two of the three headline claims ("c follows method"; "λ follows size, not structure") are contradicted or unsupported by the project's own outputs.
- The magnitude claims ("20–40%", "5–10×") use a favourable denominator and hold only on 4B/8B.
- The key prediction (p̄) has no leverage, and the cited evidence is ungated and incomplete.

**Projected after R1–R4 plus rescoping: 3.5 / 5; 4 if R1 shows a clear checkpoint lottery and R2 confirms the pre-registered λ invariance.** The reframed paper makes a practically important, falsifiable and robust claim: turnover is method-invariant and the net is checkpoint-dependent, so single-checkpoint agent comparisons of quantizers mislead. It also carries a validation discipline (a held-out confirmatory split) that ARR reviewers rarely see.

Revision priority:
1. R1 and R2 (GPU, start now).
2. R4 and R3 (analysis).
3. Rescope C2–C4.
4. Everything else.

## Revision Plan (ranked by value / feasibility; freeze 10-05)

- **R1 (highest value; about 60–120 GPU-h; simulator-bound; start today): checkpoint replication.**
  - Scope: q4, and q8 if capacity allows.
  - Add independent checkpoints: GPTQ-W4 d3, d4; AWQ-W4 d3 (d2 exists); rot_rtn_w4 seeds 1, 2 (RTN-type error, independent checkpoints); rot_bf16 seeds 1, 2.
  - Run each checkpoint under 2 fresh nonces.
  - Pre-declare a random-effects decomposition of c and Δ into method / checkpoint / nonce, and the test "method variance > checkpoint variance".
  - Either outcome is publishable: "c follows method" survives, or "net effect is a checkpoint lottery" becomes the headline.
  - Deprioritise KV-cache cells, the q8/q14 NF4/MXFP4 breadth and telecom to make room.
- **R2 (high value; about 40–80 GPU-h): a pre-registered confirmatory replication on the 57 unused calibration tasks (+ the 22 unstable ones if they run).**
  - Scope: q4 and q8.
  - Cells: null n1–n8, RTN/GPTQ/AWQ-W4 ×3 fresh nonces, rot_bf16 ×3, RTN-W3 ×2.
  - Freeze hypotheses in a `PREREG_iter4.md` (sha into the manifest) *before* running:
    - H1: |λ_GPTQ − λ_RTN| < 0.10, and the same for AWQ;
    - H2: λ_W4 > λ_rot_bf16;
    - H3: coin residual within CI;
    - H4: fragile-task AUC > 0.7 from Gaussian breaks.
  - This single table answers the multiplicity (W8), selection (W7) and "85 tasks" (W9) critiques at once.
- **R3 (0–20 GPU-h): a numerics-floor denominator.**
  - Report every λ as λ_composed against the rot_bf16 / k = 0.001 / null_K floor.
  - Replace "5–10×" with break/fix rates relative to the floor.
  - Add rot_bf16 ×3 on q8/q14 if missing.
- **R4 (0 GPU-h): statistics.**
  - Resample draws, and when available checkpoints, in the bootstrap (as in [HB]).
  - Test paired differences, not overlapping CIs.
  - TOST on Δλ with a declared ±0.10 margin, pooled across models with a stratified bootstrap.
  - Holm over the pre-declared family.
  - Suppress c when the λ lower CI is ≤ 0.1.
  - Tabulate the coin-residual pass rate.
  - Run everything from a gated frozen snapshot, and make sure the JSON actually contains every model quoted (W6).
- **R5 (about 30–60 GPU-h, optional): a T = 0.7 slice.** q4 BF16 ×5 vs RTN-W4 ×5 and GPTQ-W4 ×5 under sampling. Does turnover survive when the null is sampling noise?
- **R6 (about 20 GPU-h, optional): a simulator swap.** Replay a 30-task subset of null ×4 and RTN/GPTQ-W4 ×2 with a different simulator (e.g. Qwen3-32B, or the 4B as a weak simulator). Report λ stability.
- **R7 (writing): rescope.**
  - Drop the p̄ prediction, or relegate it to the discussion as a model implication.
  - Rename "reallocation" to "turnover".
  - Cut C4 to a paragraph and a checklist.
  - Position against Dutta, Singh, Flat Score, Vallecillos-Ruiz, Hooker and Kennedy in one related-work table: columns for closed loop, own-null, task-level, cross-method λ, and checkpoint replication.
- **R8 (writing): disclose** the task filter (W7), fake-quant kernels (X1 labelling) and Qwen-only scope. Report l8 only for the null/λ if its ok-stratum has ≥10 tasks.

---

## Part 2: Inline annotations

> "Quantization on closed-loop agents mostly *reallocates* capability rather than removing it: it re-rolls the outcomes of 20–40% of tasks"

**[W2] MAJOR:** 20–40% holds only for q4/q8. On q14, calibrated W4 λ is 0.10–0.17, and on q30a3 it is 0.01–0.14 (`r01_realloc_live.json`). A function-preserving rotation already gives λ 0.12 (q4 rot_bf16). State the model range and the floor.

> "c (where it lands) depends on the quantization method."

**[W1] FATAL as worded:** On q4, no Δc vs RTN excludes 0 once draws are resampled [HB]. q8 has c ≈ 0.20 for all three methods. GPTQ d1/d2 differ by 0.20 in c (0.47 vs 0.27), with Δ of opposite sign. Replace with a checkpoint-replicated claim (R1) or drop.

> "Reallocation: break/fix rates on null-robust tasks are 5–10× the null rate (q4 null break/fix 1.8%/4.1% vs RTN-W4 20%/11%)."

**[W2] MAJOR:** These are pilot numbers. The current estimator implies RTN-W4 q4 break 21.6% and fix 5.9%, with null b0 = f0 = 2.0%. Against rot_bf16 (11.5% / 4.0%) the ratios are about 1.9× and 1.5×. Update the numbers and change the denominator.

> "λ is set by error size (E17): Gaussian with RTN per-group RMS and RTN magnitudes with random signs reallocate as much or more than RTN … CIs overlap."

**[W3] MAJOR:** Overlapping CIs do not show equality. Isotropic Gaussian at RTN norm is *higher* than RTN, pooled +0.14 [0.013, 0.276] (`r08_frozen.log`). Reword as one-sided ("RTN is not worse than matched random error"), add a TOST, and cite Kennedy & Kennedy 2026 as the mechanism.

> "W4 methods share λ≈0.22–0.25 (NF4 0.37) … stochastic rounding (1.41× RTN error) λ 0.35, c 0.12."

**[S4] / [W8]:** The λ invariance is the best result. Promote it with a pooled TOST. NF4 (0.37) and gshape (0.42) are exceptions within the same "size". Say so rather than parenthesising them.

> "Calibration and rotation do not reduce how many tasks are re-rolled; they change where they land."

**[W1]:** The first half is supported (pooled RTN−GPTQ Δλ 0.013 [−0.08, 0.11]). The second half is not (see above). Split the sentence.

> "Consequences: Δ = λ(c − p̄) predicts larger net damage at higher base success; W3 damage q8 −16.7 pp, q14 −14.5 pp."

**[W5] MAJOR:** p̄ spans 0.29–0.38 across models, so there is no leverage. The W3 numbers differ in λ (q4 0.79, q8 0.57), not in p̄. Drop, or test by manipulating p̄ at a fixed checkpoint.

> "Open-loop probe … predicts λ (ρ 0.75–0.83; partial ρ given dose 0.86)"

**[W6] MAJOR:** The 0.86 is A2-15: flip rate vs per-decision hazard (`d01_matched_dose.json`), not λ. The λ correlations (r05: 0.83 on 16 cells, 0.76 on 11) have no dose control. Compute a partial ρ for λ, or drop the parenthesis.

> "fragile-task set predictable within a model (AUC 0.75–0.83) but not across models (0.51)"

**[S5]:** Good, and underplayed. Note that break-prediction AUCs are 0.82–0.84 and fix AUCs 0.69–0.79 (`r03_frozen.log`). Say which. This result also argues that *which* tasks break is generic to weight perturbation, which is in tension with "c follows method".

> "Setting: τ²-bench retail+airline (85 dev tasks)"

**[W7] MAJOR:** Disclose that these are the evaluation split after excluding 22 BF16-"unstable" tasks, and that 57 calibration tasks are unused. Use them for R2.

> "Null = BF16 with prompt nonces n1–n8 (nonce stratum)."

**[Q2]:** The nonce null is a prompt-perturbation null. Checkpoint-level perturbations (rot_bf16, k = 0.001, eager/compiled) re-roll more (λ 0.09–0.15). Either justify the choice or add a floor reference (NR1 v2).

> "| C3 | λ follows error size; c follows method (… 8 method families incl. NF4, MXFP4, QuaRot rotation, stochastic rounding, fake KV-cache INT8/INT4+Hadamard) | M4, M5 | E17 done; methods q4 done, q8/q14 running |"

**[W3]/[W1]/[W11]:** Breadth does not substitute for replication. 8 families × 1 checkpoint cannot separate method from checkpoint. Trade KV-cache and q8/q14 breadth for R1.

> "| C4 | Practical: open-loop probe cheaply predicts λ; closed loop needed for c; failure taxonomy; reporting checklist | M6, S5, S8 | data exists; recompute on freeze |"

**[W6]/[W10]:** S8 (taxonomy) is "to do" in FINAL_EXPERIMENTS, and the probe claim is dose-confounded. Cut as a contribution and keep it as an analysis section.

> "Risks: 'c follows method' holds only on q4 → C3 shrinks to 'λ follows size'."

**[W1]/[W3]:** Both halves are at risk: c is not established even on q4, and "λ follows size" is contradicted by r08. The fallback should be "λ is method-invariant and not worse than matched random error" (supported), plus R1's outcome.

> Evidence: "`analysis/insights/iter_3/out/r01_realloc_unfrozen.json`"

**[W6]:** This file is ungated (`_snapshot.id = null`) and contains only q4 and q8. The q14 numbers in W15 are not in it.

## Sources

- Flat Score, Amplified Failures (arXiv 2607.27275): https://arxiv.org/abs/2607.27275 (abstract fetched: τ²-bench, Qwen/Gemma, BF16/FP8/INT4-AWQ, "failure set is the same at every precision (rank correlation ≥ 0.94, 0.18% novel events)")
- Accuracy is Not All You Need (Dutta et al. 2024): https://arxiv.org/abs/2407.09141
- Certifying Compressed Language Models (Singh 2026): https://arxiv.org/abs/2608.15046
- Smaller Models, Unexpected Costs (Vallecillos-Ruiz et al. 2026): https://arxiv.org/abs/2606.27205
- Quantization Error Is Spectrally Flat (Kennedy & Kennedy 2026): https://arxiv.org/abs/2609.33923
- Quantization Hurts Reasoning? (COLM 2025): https://arxiv.org/abs/2504.04823
- Same Request, Different Answer (Patodiya 2026): https://arxiv.org/abs/2609.04748
- Noise Floor Audit for Agent Benchmarks (Chen et al. 2026): https://arxiv.org/abs/2608.22331
- (All IDs above were confirmed to exist via the arXiv export API on 2026-09-29. Details beyond the Flat Score abstract are taken from `docs/insights/SURVEY.md` and were not re-verified.)
