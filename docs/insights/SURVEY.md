**TL;DR**
- Each of I1–I4 is new or a sharper version of prior work; the closest competitor is Flat Score (https://arxiv.org/abs/2607.27275, τ²-bench, verbal margin account, TOST from one rerun).
- The per-step margin → flip model is published (Du Eq. 14 at https://arxiv.org/abs/2609.26621; Integer Alibi, AUC 0.94) and must be cited as inherited.
- Experiment-changing findings: null width is serving-dependent (Replay Gap); canonical prompts beat paraphrases on static benchmarks (threat to P4c); τ² single-run noise is 7–11 pt (tau2 issue #540).

# SURVEY: living literature map for the CLOQ COLING paper

Paper: *Perturbation Equivalence in Closed-Loop Agents: When Is a Compressed Agent Actually Worse?* (`docs/COLING_PLAN.md`).
Base map: `analysis/coling/RELATED_WORK.md`. BibTeX: `analysis/coling/references.bib` plus `analysis/insights/references_new.bib`.
Last update: 2026-09-28, iteration 1, round 1. Insight ids follow `docs/insights/iter_1_candidates.md`.

## How to read the evidence tags

Every entry has the paper URL, which was opened, plus a source tag saying where the claim was extracted.

| tag | file and section |
|---|---|
| `S-mfd §CC` | `docs/insights/survey_sweeps/margins_flips_divergence.md` §Close competitors |
| `S-mfd §OE` | same file, §Other entries |
| `S-mfd §Nov` | same file, §Novelty against the P-claims |
| `S-cae §Flags` | `docs/insights/survey_sweeps/compressed_agents_eval_noise.md` §Flags |
| `S-cae §Papers` | same file, §Papers |
| `S-cae §Tests` | same file, §Tests proposed on our data |
| `S-enc §Close` | `docs/insights/survey_sweeps/equivalence_null_criteria.md` §How close prior work gets |
| `S-enc §OE` | same file, §Other entries |
| `own` | opened by the survey lead in this pass; the verification level follows the tag |
| `map` | `analysis/coling/RELATED_WORK.md` |

Verification levels:
- **[full]**: full text read.
- **[abs]**: only the abs page or export-API abstract was read.

Nothing here is cited from memory. Most close competitors date from May–Sep 2026, so **re-sweep before submission.**

---

## Literature map (by theme, newest first)

### T1. Compressed LLMs as agents, tool use, multi-turn

- **Flat Score, Amplified Failures.** Jang, Yang, Lim, Park. 2026, preprint. https://arxiv.org/abs/2607.27275 [full]
  (evidence: own; S-mfd §CC-B; S-enc §Close-1)
  - **Setup.** τ²-bench retail and telecom, 114 tasks each, 4 trials per task (456 episodes per cell), agent T = 0.
    Models: Gemma-4 31B and 26B-A4B, Qwen-3.6 27B and 35B-A3B, Qwen-3.5 27B and 9B, at BF16, FP8 and AWQ-INT4 on real Marlin kernels.
  - **Aggregate.** No change survives multiple-comparison correction. They use **TOST at ±7.5 pt**, a margin set at ≈ 1.3× a floor
    estimated from **one** repeat run (≈ 1.5 pt, "coarse").
  - **Failures.** Tool-name hallucination rises up to 2.5× (19.5 → 38.3%). The failure set is preserved (rank correlation ≥ 0.94;
    0.18% of events are novel). Recovery is 55% at both precisions. An error budget of 2 instead of 10 re-exposes ≈ 17 pt.
  - **Mechanism.** A verbal margin account (m′ = m + η). "Token log-probabilities are not in our logs". No divergence measurement,
    no perturbation null.
  - **Relation:** competes on every axis; we extend it.
- **The Replay Gap.** Gonuguntla et al. 2026, COLM 2026. https://arxiv.org/abs/2608.08239 [full] (evidence: S-mfd §OE-22; S-cae §Flags(a), §Papers-1)
  - Same-model control forks serve as the null in SWE agents.
  - A model swap rewrites 61–94% of post-fork actions. Early swaps diverge at the first action 74–77% of the time, against 6–35% for controls.
  - **FP8 control forks diverge > 90%, while AWQ controls are nearly identical.**
  - **Relation:** precedes our null (model swap, not compression). Its null width depends on the serving format.
- **Same Request, Different Answer.** Patodiya 2026, submitted to IEEE Access. https://arxiv.org/abs/2609.04748 [full] (evidence: S-mfd §CC-C)
  - 80 multi-turn tool episodes. Prefix caching changes 36.2% of trajectories at 16-bit and 75.0% at 4-bit.
  - "Amplification saturates at the coarsest settings" (Q4_K_M ≈ Q3_K_M ≈ 68.8%).
  - Divergence is 3.5% for a single turn and 36.2% per episode (chaining is stated in words).
  - **Relation:** a partial P1 in words; we extend it.
- **Quantization Inflates Reasoning.** Lian 2026. https://arxiv.org/abs/2606.25519 [abs] (evidence: S-cae §Flags(a), §Papers-2)
  - INT4 and INT3 keep accuracy but lengthen reasoning, including in agent tool use.
  - **Relation:** a hidden-cost framing; a secondary endpoint.
- **Mix-Quant.** 2026. https://arxiv.org/abs/2605.20315 [abs] (evidence: S-cae §Papers-17)
  - Full quantization hurts agents; FP4 prefill with BF16 decode preserves them.
  - **Relation:** context.
- **QuantClaw.** 2026. https://arxiv.org/abs/2604.22577 [abs] (evidence: S-cae §Papers-18)
  - The precision an agent needs is task-dependent.
  - **Relation:** context.
- **Quantization Undoes Alignment.** Rath 2026. https://arxiv.org/abs/2605.15208 [abs] (evidence: S-cae §Papers-16, §Tests-T6)
  - At 3 bits, 6–21% of items become newly biased over 5 seeds, measured against seed flips.
  - **Relation:** supports new-failure-versus-seed-flip accounting.
- **AgentProv.** 2026, EMNLP 2026. https://arxiv.org/abs/2609.00052 [abs] (evidence: S-cae §Papers-23)
  - Providers silently quantize, and tool-use probes detect it 100% of the time.
  - **Relation:** detectability is not damage.
- **IFFC.** 2026. https://arxiv.org/abs/2608.22472 [abs] (evidence: S-cae §Papers-22)
  - Function calling is robust under quantization (open loop).
  - **Relation:** consistent with high tool-turn margins (I1/I2).
- **UniComp.** von Rad 2026, EMNLP 2026. https://arxiv.org/abs/2602.09130 [abs] (evidence: S-cae §Flags(b), §Papers-8)
  - Instruction following degrades, and reliability decouples from retained performance.
  - **Relation:** supports.
- **Less Precise Can Be More Reliable.** Bouguerra 2026, ICML 2026. https://arxiv.org/abs/2509.21173 [abs] (evidence: S-cae §Papers-27)
  - Quantization can help.
  - **Relation:** use two-sided tests.
- **KV-cache compression for agents.** TriAxialKV https://arxiv.org/abs/2605.17170, KV compaction https://arxiv.org/abs/2608.00902,
  StepKV https://arxiv.org/abs/2609.22158 [abs] (evidence: S-cae §Papers-19–21)
  - **Relation:** adjacent; out of scope.
- **Qwen3 Quantization.** Zheng 2025. https://arxiv.org/abs/2505.02214 [abs] (evidence: S-cae §Papers-24)
  - Qwen3 is competitive at 4-bit on static tasks.
  - **Relation:** same model family.
- **Long-context quantization.** Mekala 2025, EMNLP 2025. https://arxiv.org/abs/2505.20276 [abs] (evidence: S-cae §Flags(b), §Papers-7)
  - 8-bit costs −0.8%; 4-bit costs up to −59% on long inputs.
  - **Relation:** supports the harness-length (32k vs 8k) section.
- **ACBench.** Dong et al. 2025, ICML 2025. https://arxiv.org/abs/2505.19433 [full html] (evidence: own; map item 1)
  - 15 models ≤ 8B; GPTQ, AWQ and SmoothQuant at 4 and 8 bits; SparseGPT and Wanda. T = 0, one run, no variance.
  - Tool use drops 1–3%; real-world tasks drop 10–15%. ERank, top-k and energy diagnostics are single-step and descriptive.
  - **Relation:** baseline.
- **Context.** Quantization Hurts Reasoning https://arxiv.org/abs/2504.04823; Reasoning Meets Compression https://arxiv.org/abs/2504.02010;
  VLAQuantBench https://arxiv.org/abs/2609.25376; Anatomy of a Closed-Loop Collapse https://arxiv.org/abs/2609.23048 (evidence: map; S-cae §Papers-25)

### T2. Numerical nondeterminism and margin-predicted flips (the per-step model, inherited)

- **Greedy Decoding Is Not Precision-Invariant.** Du et al. 2026, TMLR. https://arxiv.org/abs/2609.26621 [full] (evidence: S-mfd §CC-A)
  - BF16 versus FP16 greedy decoding diverges on 49–100% of prompts (6 models, 1.1B–7B).
  - **Eq. 14: P(flip at t) ≲ P(Δ_t < σ_z)**, with σ_z ≈ 0.026. Median margin is 0.039 for diverged tokens and 5.73 for agreed ones.
  - CoT concentrates small margins.
  - **Relation:** our per-step model *is* this; we extend it to the closed loop, several families, the step product and cross-model prediction.
- **The Integer Alibi.** Chen 2026. https://arxiv.org/abs/2608.13756 [full] (evidence: own; S-mfd §CC-D)
  - Swapping the INT8 kernel leaves 0/N sequences in agreement. Under teacher forcing, 4.7% of positions flip.
  - The flip rate is 34% in the lowest-margin decile and 0 above a margin of ≈ 9. **AUC 0.942**; margin-to-flip calibration Brier score 0.035.
  - **Relation:** supports; a benchmark for s01.
- **MarginGate.** Chu et al. 2026. https://arxiv.org/abs/2605.30218 [full] (evidence: S-mfd §CC-E)
  - Batch-induced flips occur on 0.3–1.3% of steps.
  - Gating on low-margin steps restores 100% determinism.
  - **Relation:** supports.
- **Illusion of Equivalence.** Chodavarapu, Xu 2026. https://arxiv.org/abs/2604.15409 [abs] (evidence: own)
  - FP16 KV-cache ON versus OFF diverges on 100% of sequences, and FP32 removes it.
  - Cache-ON is more accurate in 8/9 conditions.
  - **Relation:** supports P1 (the smallest δ already saturates).
- **Numerical Instability and Chaos.** Islam 2026. https://arxiv.org/abs/2604.13206 [full] (evidence: S-mfd §OE-11)
  - An ε sweep, single step, with stable, chaotic and signal regimes.
  - **Relation:** a partial P1.
- **Background Temperature.** Messina 2026. https://arxiv.org/abs/2604.22411 [abs] (evidence: S-mfd §OE-10)
  - Implementation noise acts as an effective temperature.
  - **Relation:** framing.
- **Token Probabilities Expose Nondeterminism.** Fu 2026. https://arxiv.org/abs/2601.06118 [abs] (evidence: S-mfd §OE-9)
  - Impact can be estimated from one run's token probabilities.
  - **Relation:** the closest in spirit to P3 (single model).
- **Quantized Reasoning Models Think Longer.** Lotfi 2026. https://arxiv.org/abs/2606.00206 [abs] (evidence: S-mfd §OE-14)
  - KL(quantized ‖ full precision) tracks next-token entropy.
  - **Relation:** supports.
- **Numerical sources of nondeterminism.** Yuan 2025. https://arxiv.org/abs/2506.09501 [full] (evidence: S-mfd §OE-6)
  - Batch and GPU configuration change greedy BF16 accuracy by up to 9%.
  - **Relation:** an anchor.
- **Defeating Nondeterminism.** He / Thinking Machines 2025. https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/ [full] (evidence: S-mfd §OE-7)
  - Batch-invariant kernels give 1000/1000 identical outputs.
  - **Relation:** the D ≡ 0 regime (P1c).
- **Quantization Meets Reasoning.** Li 2025. https://arxiv.org/abs/2505.11574 [abs] (evidence: S-mfd §OE-15)
  - The first vulnerable step flips and cascades.
  - **Relation:** supports P1d.
- **Smaller = Weaker?** Fang 2025. https://arxiv.org/abs/2506.22776 [abs] (evidence: S-mfd §Optional)
  - Quantized models respond differently to Gaussian weight noise.
  - **Relation:** apply the Gaussian ladder to BF16 weights only.
- **Anchors.** Atil 2024 https://arxiv.org/abs/2408.04667; LLM-42 https://arxiv.org/abs/2601.17768; HEAL https://arxiv.org/abs/2606.21023 (evidence: S-mfd §OE-8, §Optional)

### T3. Trajectory divergence, forking tokens, multi-turn compounding

- **AgentDiff.** Zhang, Guo 2026. https://arxiv.org/abs/2605.25981 [abs] (evidence: own; S-mfd §OE-23)
  - Meaning-bearing rewrites cause +19.7 pp more inconsistency than presentation changes.
  - The first action is preserved and later steps diverge.
  - **Relation:** the perturbation *kind* matters, and our nonce is a presentation-type change.
- **Grounded Scaling.** Ding, Wang 2026. https://arxiv.org/abs/2606.22495 [abs] (evidence: own)
  - k-step success is δ^k.
  - **Relation:** an analogue of the product law, on the environment side.
- **Markov-chain reliability.** Tran-Truong 2026. https://arxiv.org/abs/2604.24579 [abs] (evidence: S-cae §Papers-12)
  - pass@k and pass^k are projections of one success-time distribution.
  - **Relation:** supports the KM framing.
- **Intent Mismatch.** Liu 2026. https://arxiv.org/abs/2602.07338 [abs] (evidence: S-cae §Papers-10)
  - Variance in the user simulator confounds multi-turn loss.
  - **Relation:** the null should vary the user seed.
- **ERGO.** Khalid 2025, UncertaiNLP. https://arxiv.org/abs/2510.14077 [abs] (evidence: S-cae §Papers-11)
  - Resets triggered by entropy spikes give +56.6%.
  - **Relation:** supports.
- **Lost in Multi-Turn.** Laban 2025. https://arxiv.org/abs/2505.06120 [abs] (evidence: S-cae §Papers-9; S-mfd §OE-26)
  - The 39% drop is small aptitude loss plus large unreliability.
  - **Relation:** supports.
- **Illusion of Diminishing Returns.** Sinha et al., ICLR 2026. https://arxiv.org/abs/2509.09677 (evidence: map, Corrections)
- **Token-level anchors.** Forking Paths https://arxiv.org/abs/2412.07961; High-Entropy Minority Tokens https://arxiv.org/abs/2506.01939 (NeurIPS 2025); Critical Tokens https://arxiv.org/abs/2411.19943 (evidence: S-mfd §OE-16–18)
- **Older anchors.** DAgger https://arxiv.org/abs/1011.0686; Scheduled Sampling https://arxiv.org/abs/1506.03099; MIXER https://arxiv.org/abs/1511.06732; Randomized Smoothing https://arxiv.org/abs/1902.02918 (evidence: S-mfd §OE-29–32)

### T4. Perturbation nulls, equivalence testing, model-difference testing

- **Calibrated LLM-judge instrument.** Kaplan 2026. https://arxiv.org/abs/2609.18005 [abs] (evidence: S-enc §Close-2)
  - A two-run "null condition, provably identical in distribution" calibrates the instrument; 4-bit is indistinguishable at ±0.3.
  - **Relation:** single-turn, judge-scored.
- **Certifying Compressed LMs.** Singh 2026. https://arxiv.org/abs/2608.15046 [full html] (evidence: own; S-enc §Close-4)
  - Paired TOST at a **declared** ±2 pp margin, on static benchmarks.
  - Churn is ≈ 5.4× the net delta (1,707 cells). 0/16 claims declare a margin. The GPTQ/AWQ order flips with the calibration seed in 5/8 cells.
  - **Relation:** competes on the equivalence layer.
- **Noise Floor Audit.** Chen et al. 2026. https://arxiv.org/abs/2608.22331 (evidence: map + Corrections; S-enc §Close-3)
  - BFCL at T = 0: reruns ever-flip 0.7–2.7%, and prompt perturbations have 11–58× the rerun SD.
  - **The choice of null dominates.**
  - **Relation:** a methodological competitor.
- **Illusion of Equivalency.** Rababah 2026. https://arxiv.org/abs/2607.08734 [abs] (evidence: S-enc §Close, P2 paragraph)
  - Equal scores hide changed behaviour.
  - **Relation:** a point observation in P2's direction.
- **Compared to What?** Yang, Levy, Goldberg, Wallace 2026, COLM 2026. https://arxiv.org/abs/2605.01048 [abs] (evidence: own)
  - Gender counterfactuals flip 14.9% of MedQA answers and paraphrase flips 14.1%, which is indistinguishable.
  - **Relation:** the closest precedent for the neutral-perturbation null (input counterfactuals).
- **Equivalence testing with data-dependent margins.** Koobs, Koning 2026. https://arxiv.org/abs/2603.16213 [abs] (evidence: own)
  - Gives post-hoc, data-dependent equivalence margins that remain valid (e-values).
  - **Relation:** statistical basis for a null-derived margin.
- **Per-sample McNemar.** Kübler 2026. https://arxiv.org/abs/2602.10144 [abs] (evidence: S-enc §OE)
  - Detects degradation of 0.3%.
  - **Relation:** a paired-test baseline.
- **Composite null.** Acharyya, Priebe, Helm 2025. https://arxiv.org/abs/2509.10963 [abs] (evidence: own; S-enc §OE)
  - A composite null of semantically irrelevant query perturbations, used to test response differences.
  - **Relation:** statistical precedent.
- **Model Equality Testing.** Gao et al., ICLR 2025. https://arxiv.org/abs/2410.20247 [abs] (evidence: S-enc §OE)
  - An MMD test detects swapped endpoints easily.
  - **Relation:** distributional difference is not damage.
- **Auditing model substitution.** Cai 2025. https://arxiv.org/abs/2504.04715 [abs] (evidence: S-enc §OE)
  - Nondeterminism hides quantized substitution.
- **Noise injection unmasks sandbagging.** Tice 2024/NeurIPS 2025. https://arxiv.org/abs/2412.01784 [abs] (evidence: S-enc §Close, P2 paragraph)
  - A weight-noise dose-response, measured on accuracy only.
- **Statistical-practice anchors.** Signal and Noise https://arxiv.org/abs/2508.13144; Madaan https://arxiv.org/abs/2406.10229; Miller https://arxiv.org/abs/2411.00640; Bouthillier https://arxiv.org/abs/2103.03098 (evidence: S-enc §OE; map)

### T5. Agent-evaluation variance and τ²-bench validity

- **tau2-bench issue #540.** https://github.com/sierra-research/tau2-bench/issues/540 [full] (evidence: S-enc §OE)
  - A single run must differ by **10–11 pt (airline) / 7–8 pt (retail)** to exceed noise.
  - **32–55% of tasks reverse** across identical runs.
- **What does a leaderboard rank compare?** Huang 2026, DSAA. https://arxiv.org/abs/2609.07785 [abs] (evidence: S-cae §Papers-5)
  - On τ²-bench, close ranks stay unresolved.
- **How many tasks are enough?** Huang 2026. https://arxiv.org/abs/2607.12338 [abs] (evidence: S-cae §Papers-6)
  - τ-bench decisions are reached with 25% of the tasks.
- **Coding agents have converged.** Liu 2026, ADMA. https://arxiv.org/abs/2609.17394 [abs] (evidence: S-cae §Papers-15)
  - McNemar separates 0/29 top pairs, and the solution sets are nested.
  - **Relation:** a precedent for pass-set nestedness (P4e).
- **False success.** Advani 2026, FAGEN@ICML. https://arxiv.org/abs/2606.09863 [abs] (evidence: S-cae §Papers-13)
  - 45–48% of single-control τ² successes are false.
- **Benchmarking the Benchmarks.** Bhat 2026. https://arxiv.org/abs/2607.02577 [abs] (evidence: S-cae §Flags(b), §Papers-4)
  - An audit of τ²: brittle state matching and 18.5% evaluator–human disagreement.
- **On randomness in agentic evals.** Bjarnason 2026. https://arxiv.org/abs/2602.07150 [abs] (evidence: S-cae §Papers-3)
  - pass@1 moves 2.2–6.0 pp at T = 0.
- **What resolve rate hides.** Shu 2026. https://arxiv.org/abs/2607.06184 [abs] (evidence: S-cae §Papers-29)
  - Control for difficulty.
- **ReliabilityBench.** Gupta 2026. https://arxiv.org/abs/2601.06112 [abs] (evidence: S-cae §Papers-28)
  - A perturbation-intensity axis on inputs.
- **Agentic Benchmark Checklist (ABC).** Zhu 2025. https://arxiv.org/abs/2507.02825 (evidence: S-enc §OE; map)
  - **"TAU-bench counts empty responses as successful."**
- **Other variance references.** Mustahsan https://arxiv.org/abs/2512.06710 (ICC, 8–16 trials); HAL https://arxiv.org/abs/2510.11977; AI Agents That Matter https://arxiv.org/abs/2407.01502 (evidence: S-enc §OE; map)

### T6. Churn, flips, fidelity metrics

- **Accuracy is Not Enough (divergence-based fidelity).** Qamar et al. 2026. https://arxiv.org/abs/2609.07664 [abs] (evidence: own)
  - JSD and TV distance instead of accuracy. Accuracy is non-monotone under progressive quantization.
  - Quantizers are compared at equal memory, not at equal divergence.
- **YAQA (Model-Preserving Adaptive Rounding).** Tseng, Sun, De Sa 2025. https://arxiv.org/abs/2505.22988 [abs] (evidence: own)
  - Rounds so that the output distribution stays close end to end, with ≈ 30% less error than GPTQ.
- **Jacobian-guided noise injection.** Pandey et al. 2026, AdaptFM@ICML. https://arxiv.org/abs/2608.20988 [abs] (evidence: own)
  - Gaussian noise as a *training* proxy for quantization, with no matched comparison.
- **Accuracy is Not All You Need.** Dutta 2024. https://arxiv.org/abs/2407.09141 (evidence: S-mfd §OE-12; map)
  - Flips up to 13.6% at equal accuracy.
- **Divergent Token Metrics.** Deiseroth 2023. https://arxiv.org/abs/2311.01544 (evidence: S-mfd §OE-13)
  - A first-divergent-token metric for compression.
- **Prediction churn.** Bhojanapalli 2021. https://arxiv.org/abs/2102.03349 (evidence: S-enc §OE)

### T7. Prompt sensitivity and the canonical-prompt advantage

- **Robustness of benchmark-based evaluation.** Lunardi et al. 2025, ECAI 2025. https://arxiv.org/abs/2509.04013 [abs] (evidence: own)
  - Paraphrased questions **lower absolute scores significantly** across 34 models and 6 benchmarks; rankings stay stable.
- **State of What Art?** Mizrahi et al. 2024, TACL. https://arxiv.org/abs/2401.00595 [full] (evidence: own, pdftotext §divergence)
  - Scores on the original template deviate from the paraphrase mean by > 1 SD.
  - Alpaca-13B's original template beats its paraphrase average by more than 1 SD in 7/10 LM-Entry tasks.
- **Zero-shot robustness of instruction-tuned LMs.** Sun, Shaib, Wallace 2023. https://arxiv.org/abs/2306.11270 [abs] (evidence: own)
  - Unseen but appropriate phrasings "consistently degrade" performance.
- **Other prompt-sensitivity anchors.** FormatSpread https://arxiv.org/abs/2310.11324 (up to 76 pt); Butterfly Effect https://arxiv.org/abs/2401.03729 (evidence: S-mfd §OE-19–20; map)

---

## Answers for iteration 1

Calls: **(a)** new; **(b)** sharper or more general version of prior work; **(c)** already shown with the same scope.
The framing-pass answers for P1–P3 and the criterion are superseded by I1–I4 below.

### I1: divergence set by tie density

- **I1-Q1 (saturation in δ, or matched by hardware noise, in agents).** Partial prior work only.
  - Patodiya reports "saturates at the coarsest settings" (68.8% at Q4 ≈ Q3), and the 16-bit cache path is already at 36%.
  - Replay Gap: FP8 controls diverge > 90%, AWQ controls do not.
  - Islam: an ε sweep, single step only.
  - Nobody puts float noise, nonce, Gaussian and RTN on one δ axis.
  - **Call: (b).**
  - evidence: https://arxiv.org/abs/2609.04748 (S-mfd §CC-C); https://arxiv.org/abs/2608.08239 (S-mfd §OE-22); https://arxiv.org/abs/2604.13206 (S-mfd §OE-11); S-mfd §Nov-3.
- **I1-Q2 (margins split by free text vs tool call).** Nothing measures this split or links it to divergence.
  - The adjacent observation is SimpleTool's "structured outputs exhibit substantial token redundancy (delimiters, parameter names)".
  - IFFC: function calling is robust to quantization.
  - **Call: (a).**
  - evidence: https://arxiv.org/abs/2603.00030 (own [abs]); https://arxiv.org/abs/2608.22472 (S-cae §Papers-22).
- **I1-Q3 (do flip papers scale flips with bit-width?).**
  - Dutta: flips are near zero only for GPTQ W8A16, a contrast rather than a sweep.
  - Singh: churn ≈ 5× the delta, with no bit-width curve.
  - Flat Score counts failures, not flips (INT4 > FP8).
  - Patodiya: 36% → 75%, saturating at Q4 ≈ Q3.
  - Qamar: accuracy is non-monotone while divergence grows.
  - Nobody reports flat flip rates at high bits in agents.
  - evidence: https://arxiv.org/abs/2407.09141 (map); https://arxiv.org/abs/2608.15046 (own); https://arxiv.org/abs/2607.27275 (own); https://arxiv.org/abs/2609.04748 (S-mfd §CC-C); https://arxiv.org/abs/2609.07664 (own).
- **I1-Q4 (margin-threshold model predicting which tokens flip).** **Yes, and it is inherited.**
  - Du Eq. 14.
  - Integer Alibi: AUC 0.942 with a calibrated mapping (Brier 0.035).
  - MarginGate.
  - All single-turn, one perturbation each. s01 is a closed-loop, multi-family replication.
  - **Call: (c)** for the per-step model.
  - evidence: https://arxiv.org/abs/2609.26621, https://arxiv.org/abs/2608.13756, https://arxiv.org/abs/2605.30218 (S-mfd §CC-A, D, E; §Nov-1).

### I2: later damage threshold set by action-decision margins

- **I2-Q1 ("free zone" or two thresholds).** Not found as a measurement.
  - Point observations only: Dutta, Singh, Rababah, Patodiya, Flat Score.
  - The closest δ sweep is Tice (weight noise vs accuracy, sandbagging).
  - **Call: (a).**
  - evidence: S-enc §Close, P2 paragraph; https://arxiv.org/abs/2412.01784.
- **I2-Q2 (margin of a flipped decision → downstream cost).** No direct statement found.
  - Adjacent: Critical Tokens and Forking Paths (decisive tokens); ERGO (entropy spikes precede derailment); Li 2505.11574 (the first
    vulnerable step cascades); Flat Score's Δp(m); DAgger (compounding without confidence weighting).
  - **Call: (a).**
  - evidence: https://arxiv.org/abs/2411.19943, https://arxiv.org/abs/2412.07961 (S-mfd §OE); https://arxiv.org/abs/2510.14077 (S-cae §Papers-11); https://arxiv.org/abs/2505.11574 (S-mfd §OE-15).
  - Search gap: this search returned only blogs; one lead, https://arxiv.org/abs/2606.02965, is **not opened**.
- **I2-Q3 (do Flat Score or ACBench split failures by tool/write vs text, or use the tool-call flip rate as a predictor?).** No.
  - Flat Score splits by failure type (tool-name hallucination), shows positional uniformity and a recovery rate of 55%, and has no logprobs.
  - ACBench splits by capability (tool use −1–3%, real-world −10–15%) and has single-step top-k/energy diagnostics.
  - evidence: https://arxiv.org/abs/2607.27275, https://arxiv.org/abs/2505.19433 (own [full html]).
- **I2-Q4 (action-level fidelity metric for agents).** None.
  - The closest: Deiseroth (first divergent token), Dutta (flips), Qamar (JSD/TV).
  - **Call: (a).**
  - evidence: https://arxiv.org/abs/2311.01544 (S-mfd §OE-13); https://arxiv.org/abs/2609.07664 (own).

### I3: D as a sufficient statistic, transferable across models

- **I3-Q1 (quantization error ≈ norm-matched Gaussian noise).**
  - The noise view is used only as a *training proxy*: Jacobian-guided noise injection, with no matched comparison.
  - Fang studies noise *on* quantized models.
  - No behavioural equivalence test at matched shift exists.
  - **Call: (a).** Risk: GPTQ/AWQ/YAQA minimize output error, so match on D, not on weight norm (I3 does this).
  - evidence: https://arxiv.org/abs/2608.20988, https://arxiv.org/abs/2505.22988 (own); https://arxiv.org/abs/2506.22776 (S-mfd §Optional).
- **I3-Q2 (size-independent scaling of logit shift with relative noise).** Not found.
  - **Call: (a).**
  - evidence: negative search result (own).
- **I3-Q3 (predicting robustness from BF16 margins across models).**
  - Fu: impact estimable from one run's token probabilities, single model.
  - Du: "depends primarily on the margin distribution", in words.
  - Lotfi: KL tracks entropy, within one model.
  - **Call: (b)** for the principle; **(a)** for pre-registered cross-model closed-loop curves.
  - evidence: https://arxiv.org/abs/2601.06118, https://arxiv.org/abs/2609.26621, https://arxiv.org/abs/2606.00206 (S-mfd §OE-9, §CC-A, §OE-14; §Nov-4).
- **I3-Q4 (iso-KL or iso-shift quantizer comparisons in agents).** None.
  - Qamar compares quantizers at equal memory.
  - **Call: (a).**
  - evidence: https://arxiv.org/abs/2609.07664 (own).

### I4: the reference run is one draw; equivalence means exchangeability

- **I4-Q1 (cross-hardware changes to the reference in agent evals; nonce ≡ hardware rate).** Partial prior work.
  - Patodiya: the 16-bit cache path changes 36% of episodes.
  - Replay Gap: FP8 controls diverge > 90%.
  - Yuan: up to 9% accuracy change, single-turn.
  - tau2 issue #540: 32–55% of tasks reverse across identical runs.
  - Bjarnason: 2.2–6.0 pp at T = 0.
  - Nobody shows that nonce and hardware divergence rates are equal.
  - **Call: (b).**
  - evidence: S-mfd §CC-C, §OE-6, §OE-22; S-enc §OE (issue #540); S-cae §Papers-3.
- **I4-Q2 (do Noise Floor Audit or Singh define equivalence as exchangeability with a perturbation null?).** **No.**
  - Singh: TOST at a declared fixed margin.
  - Noise Floor Audit: reports floors and warns that the choice of null dominates, but defines no criterion.
  - Flat Score: TOST margin of ±7.5 pt scaled from one rerun.
  - Statistical precedents: Acharyya (a composite perturbation null for response distributions); Koobs & Koning (data-dependent margins).
  - **Call: (b).**
  - evidence: https://arxiv.org/abs/2608.15046 (own); https://arxiv.org/abs/2608.22331 (S-enc §Close-3); https://arxiv.org/abs/2607.27275 (S-enc §Close-1); https://arxiv.org/abs/2509.10963, https://arxiv.org/abs/2603.16213 (own).
- **I4-Q3 (canonical-prompt advantage).** **Yes, on static benchmarks.**
  - Lunardi: paraphrases significantly lower absolute scores across 34 models.
  - Mizrahi: the original template is > 1 SD above the paraphrase mean in 7/10 LM-Entry tasks for Alpaca-13B.
  - Sun et al.: unseen phrasings degrade performance.
  - AgentDiff: meaning-bearing rewrites destabilize agents.
  - Nothing tests meaning-null nonces on agents. **P4c is a live risk.**
  - evidence: https://arxiv.org/abs/2509.04013, https://arxiv.org/abs/2401.00595, https://arxiv.org/abs/2306.11270, https://arxiv.org/abs/2605.25981 (own).
- **I4-Q4 (task × run φ or clustering to separate damage from re-roll).** Not found.
  - Adjacent: Rath (new failures vs seed flips); Coding Agents Converged (nested solution sets); Singh (churn next to delta).
  - **Call: (a)** for φ exchangeability; **(b)** for nestedness.
  - evidence: https://arxiv.org/abs/2605.15208, https://arxiv.org/abs/2609.17394 (S-cae §Papers-15, 16).

---

## Ideas from recent work

1. **(Replay Gap) Format-dependent null width.** Measure rerun (control) divergence per serving path *and per quantized format*.
   - Prediction: AWQ/GPTQ reruns on one node give D ≡ 0 with no divergence, and non-batch-invariant paths saturate.
   - Report null width per arm.
   - evidence: https://arxiv.org/abs/2608.08239 (S-cae §Tests-T1); `analysis/insights/iter_1/out/s04_*` (I1 P1c).
2. **(tau2 issue #540) Anchor the null SD externally.** Compare our 5-nonce greedy null SD with #540's released-trajectory estimate
   (7–11 pt single-run noise).
   - If they match, I4's "a single run is a draw" is anchored on public data.
   - evidence: https://github.com/sierra-research/tau2-bench/issues/540 (S-enc §OE); `analysis/insights/iter_1/out/s05_pilot_success_q4_airline.json`.
3. **(Integer Alibi, Du Eq. 14) One margin → flip calibration for every family.** Fit the calibration (Brier score) on the node-floor pair.
   Apply it unchanged to nonce, Gaussian and RTN after δ scaling.
   - One curve fitting all families is token-level evidence for I3's sufficiency claim.
   - evidence: https://arxiv.org/abs/2608.13756; `analysis/insights/iter_1/s01_token_flip_margin.py`.
4. **(Lunardi, Mizrahi) Test for a canonical-prompt effect before P4c.** Compare canonical-prompt weight-noise runs (Gaussian
   k = 0.03, no nonce) with nonce runs.
   - If canonical-prompt runs sit systematically higher, build the null from weight-side perturbations or model a prompt term.
   - evidence: https://arxiv.org/abs/2509.04013, https://arxiv.org/abs/2401.00595.
5. **(Flat Score, ABC) Process-error channels and empty-response artifacts.**
   - Test P2e on `tool_error_rate` and repeated calls against the null band.
   - Audit db_match for empty or terminated episodes in damage cells.
   - evidence: https://arxiv.org/abs/2607.27275; https://arxiv.org/abs/2507.02825 (S-enc §OE).

## Open questions for survey

- ~~Divergence saturation or hardware-matched divergence in agents?~~ Answered: I1-Q1.
- ~~Margin-threshold flip model published?~~ Yes: I1-Q4.
- ~~Does Singh or Noise Floor Audit define equivalence as exchangeability?~~ No: I4-Q2.
- ~~Canonical-prompt advantage?~~ Yes, on static benchmarks: I4-Q3.
- ~~Flat Score per-configuration details~~ Done: T1.
- Full text of Acharyya 2509.10963 and Koobs & Koning 2603.16213. Which one is the formal basis for a null-derived margin?
- Full text of Patodiya 2609.04748: the "0/800 bit-identical reruns" wording is ambiguous (S-mfd §CC-C).
- Full text of AgentDiff 2605.25981: first-divergence step statistics, for P1d.
- Confidence-weighted compounding cost in agents: search ACL Anthology and OpenReview directly; lead 2606.02965 is unopened.
- Pruning and distillation on agents: not yet swept.
- Unread leads: 2602.18998, 2601.14888, 2510.18731, 2604.08782, 2608.14711, 2605.08137 (S-cae, end).
- *(added by cloq-verify, iter 1; evidence `docs/insights/iter_1_verdicts.md`)* **V1-Q1 (I4, E5).** Has any agent-benchmark paper treated the *user simulator's* serving numerics as a perturbation? Legacy→a6k2 re-serving changed the simulator's first user message in 11/20 det tasks, the same tasks for q4 and q30a3 (`analysis/insights/iter_1/verify/out/v02_a6k2_det.json`).
- **V1-Q2 (I1).** Any prior report of a per-decision divergence-hazard *floor* that is flat below a resolution scale (e.g. the bf16 log-prob grid, 0.125 nats) and rises only above it? (Patodiya's 3.5% per turn vs 36% per episode is the nearest; check Du 2609.26621 §5 and Islam 2604.13206.)
- **V1-Q3 (I3).** RTN vs GPTQ/AWQ at *matched output-logit shift*: evidence that RTN carries damage beyond its shift (systematic/outlier-channel error vs noise-like error)? Legacy q8 RTN-W4 Δ −10.5 pp vs Gaussian k=1 0.0 pp at matched median |d| (`verify/out/v04_pooled_draws.json`).
- **V1-Q4 (I2).** Agent self-correction after a wrong tool call: published recovery rates besides Flat Score's 55%? Our q4 shows tool-turn flip rates 0.2–0.9 (k=1, RTN-W4) with no measurable db_match loss.
- **V1-Q5 (I1, I4; carried from candidates).** Divergence or benchmark-score change from a compiler/autotune-level numerics change (not batch or kernel swap) in multi-turn agents.
- **V1-Q6 (I2; carried).** Agent-quantization work reporting decisions/turns per episode against a noise null; matched-output-KL quantizer comparisons in agents (I3-Q4 re-check before submission).
