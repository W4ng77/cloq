**TL;DR**
- Iteration 3 (quantization-centred; T9 and "Answers for iteration 3"). I5 and I7 are sharper versions of static flip/churn and open-vs-closed-loop results (Dutta https://arxiv.org/abs/2407.09141; Singh https://arxiv.org/abs/2608.15046). I6 is new at task level and contradicts margin accounts. I8 is partly anticipated by Flat Score's budget-exhaustion count.
- Most important new paper: Kennedy & Kennedy 2026 (https://arxiv.org/abs/2609.33923). RTN error is spectrally flat, and isotropic Gaussian probes over-excite high-energy channels (29% vs 17%). That predicts our isotropic > RTN ≈ gshape ordering.
- Experiment changes: add a channel-energy-share statistic, a valid stochastic-rounding control (AdaRound), and an AWQ calibration-seed control. Flat Score's ρ ≥ 0.94 is per tool-name, not per task.

# SURVEY: living literature map for the CLOQ COLING paper

Paper: *Perturbation Equivalence in Closed-Loop Agents: When Is a Compressed Agent Actually Worse?* (`docs/COLING_PLAN.md`).
Base map: `analysis/coling/RELATED_WORK.md`. BibTeX: `analysis/coling/references.bib` plus `analysis/insights/references_new.bib`.
Last update: 2026-09-29, iteration 3 round 1 (T9; insight ids I5–I8 from `docs/insights/iter_3_candidates.md`). Previously: iteration 2 conformal pass (T8) and iteration 1 round 1 (I1–I4, `docs/insights/iter_1_candidates.md`).

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

### T8. Conformal methods in LLM and agent evaluation (iter 2)

A conformal-layer pass on 2026-09-29 used 7 web queries. Each entry below gives the verification level:
- **[abs]**: the arXiv abs page was opened in this pass.
- **[snippet]**: only the search-result abstract text was read.

Use: `docs/insights/iter_2_conformal.md#3-novelty`.

- **S-C1. Conformal Elo.** Kargi, Salinas 2026. https://arxiv.org/abs/2606.13221 [abs]
  - Split conformal on LLM-vs-human Elo residuals, with **models as the exchangeable unit** (55 held-out LMArena models).
  - **Relation:** the closest precedent for our leave-one-model-out open→closed intervals. Ours works in closed loop and has 2–5 models.
- **S-C2. Compression + conformal uncertainty.** Tong et al. 2026. https://arxiv.org/abs/2606.01850 [abs]
  - CP measures the *compressed model's own* uncertainty. Uncertainty inflation is threshold-like.
  - It is not a compressed-vs-full equivalence test and has no agents.
  - **Relation:** cite as adjacent. Its threshold finding is consistent with our two thresholds.
- **S-C3. Role-stratified conformal risk control for tool calls.** Rahman et al. 2026. https://arxiv.org/abs/2607.24343 [abs]
  - Controls risk per argument role of a tool call.
  - **Relation:** agent-side CRC at single-call granularity, not closed-loop equivalence.
- **S-C4. Conformal agent error attribution.** Feng et al. 2026. https://arxiv.org/abs/2605.06788 [abs]
  - Filtration-based CP sets over agent trajectories.
  - **Relation:** sequential CP inside one trajectory. Ours ranks whole runs against a null family.
- **S-C5. E-valuator.** Sadhuka et al. 2025/2026. https://arxiv.org/abs/2512.03109 [abs]
  - Agent verifier scores become e-processes with false-alarm control.
  - **Relation:** e-values in agent evaluation. It is the precedent for our e-value product across models.
- **S-C6. LLM-as-a-judge conformal intervals.** EMNLP 2025. https://aclanthology.org/2025.emnlp-main.569/ [snippet]
  - Extended to judge ensembles in https://arxiv.org/abs/2609.06367 [snippet].
  - **Relation:** conformal in evaluation, on judge scores.
- **S-C7. E-values expand conformal prediction.** Gauthier, Bach, Jordan 2025. https://arxiv.org/abs/2503.13050 [snippet]
  - Also: **S-C8. BB-predictor / e-test statistics.** Balinsky & Balinsky, COPA 2024. https://arxiv.org/abs/2403.19082 [snippet].
  - **Relation:** statistical basis for the soft-rank conformal e-values in `analysis/insights/iter_2/c01_conformal_equivalence.py`.
- **S-C9. UQ for LLM agents: taxonomy and protocol.** 2026. https://arxiv.org/abs/2609.07395 [snippet]
  - **Relation:** check before submission whether it includes run-level exchangeability tests.

**Novelty statement.** No entry above treats a compressed checkpoint's closed-loop run as a draw to be ranked against a perturbation-null family (a conformal equivalence test). None gives conformal intervals from open-loop to closed-loop behaviour. The sweep was shallow, so re-sweep S-C9 and ACL Anthology 2026 before submission.

### T9. Quantization reallocation, error size vs structure, fragile sets (iter 3)

This pass ran on 2026-09-29, with about 30 web queries. Verification levels:
- **[full]**: the full text or HTML was read;
- **[abs]**: the abs page was read;
- **[html-q]**: targeted questions were answered from the HTML.

Tag `own-i3` = opened by the survey lead in this pass. Use: `docs/insights/iter_3_discussion.md#survey-round-1`.

**T9a. Same accuracy, different items (flips, churn, solved-set drift).** Newest first.
- **Before the Flip.** Saha et al. 2026, a NeurIPS 2026 workshop submission. https://arxiv.org/abs/2609.06922 [abs] (own-i3)
  - LLaVA 4-bit changes only 265/9,000 VQA answers. The yes/no score gaps nevertheless shift toward the replacement output, more at 4-bit than at 8-bit.
  - **Relation:** supports I5/I7. Hidden margin shift precedes flips; the setting is static.
- **Illusion of Equivalency.** Rababah et al. 2026. https://arxiv.org/abs/2607.08734 [abs] (own-i3; already in T4)
  - Uses "Correctness Agreement". Behaviour shifts "even when accuracy and perplexity are preserved", with a breakpoint at low bits.
  - q/k projections are more sensitive than v/o.
  - **Relation:** supports I5 on static tasks; no null.
- **Smaller Models, Unexpected Costs (program repair).** Vallecillos-Ruiz et al., ICSME 2026. https://arxiv.org/abs/2606.27205 [html-q] (own-i3)
  - Llama-8B quanto4 solves 58 vs 61 Defects4J bugs with only 29 overlapping. They introduce the Jaccard Consistency Rate.
  - Methods: AQLM, AWQ, bitsandbytes, HQQ, Quanto, at 2–8 bits and on the KV cache. Drift is method- and family-dependent.
  - Fixed seed, T = 0.1, no rerun null.
  - **Relation:** the closest agent-adjacent precedent for I5. We extend it with the null and the attractor.
- **Certifying Compressed LMs.** Singh 2026. https://arxiv.org/abs/2608.15046 [html-q] (own-i3; T4)
  - Median churn / median |Δacc| = 5.40 over 1,707 cells. GPTQ vs AWQ on GSM8K: 9.1% right→wrong, 8.5% wrong→right.
  - The calibration draw alone reverses the GPTQ–AWQ ranking in 5/8 cells.
  - No cross-method item overlap and no rerun null.
  - **Relation:** supports I5. Its calibration-seed result is a threat to our "AWQ > RTN" claim.
- **Exploring the Trade-Offs (IJCAI 2025).** Lee et al. https://www.ijcai.org/proceedings/2025/0902.pdf [full] (own-i3)
  - "hard tasks do not always experience the largest accuracy losses … quantization magnifies a model's inherent weaknesses".
  - AWQ generally beats GPTQ; FP8 is the most robust.
  - **Relation:** supports I6 c (model-specific), at dataset level.
- **Accuracy Is Not All You Need.** Dutta et al., NeurIPS 2024. https://arxiv.org/abs/2407.09141 [html-q] (own-i3; T6)
  - Flips at W4: AWQ 4.05–7.66%, GPTQ 4.26–8.26%, BnB-W4A4 5.65–10.90%, SmoothQuant-W8A8 up to 13.62%. GPTQ-W8A16 is lowest at 0.26–1.40%.
  - Flips are balanced (wrong→right ≈ right→wrong).
  - Mechanism: low top-margin answers flip, and "correct (incorrect) answers have higher (lower) top margin".
  - KL ↔ flips Spearman 0.981 (MMLU). Perplexity misses this because token-probability losses and gains cancel.
  - **Relation:** the main baseline for I5. I7 extends its KL↔flips amount result. **I6 d contradicts its margin mechanism at task level in closed loop.**
- **Characterising Bias in Compressed Models.** Hooker et al. 2020. https://arxiv.org/abs/2010.03058 [abs] (own-i3)
  - Compression Identified Exemplars (CIEs) are a small subset of examples with disproportionate error.
  - **Relation:** precedent for fragile sets (I6).
- **What Do Compressed DNNs Forget?** Hooker et al. 2019. https://arxiv.org/abs/1911.05248 [full] (own-i3, pdftotext)
  - PIEs are defined as modal-label disagreement between populations of **30 independently trained** pruned and unpruned models, so the null there is init variation.
  - "Compression cannibalizes performance on a small subset of classes to preserve a similar overall top-line accuracy". PIEs are atypical or noisy.
  - Quantization (int8, float16) has far less disparate impact than pruning: 119 vs 637 significant classes.
  - **No random-weight-noise control and no cross-architecture transfer test.**
  - **Relation:** the anchor for I5/I6. Our null-population design is in its spirit, and I6 c (no cross-model transfer) contrasts with its "data-property" reading.
- **Prediction churn.** Bhojanapalli et al. 2021. https://arxiv.org/abs/2102.03349 [abs] (own-i3)
  - Two independently trained models disagree, and low-confidence predictions churn more.
  - **Relation:** background; confidence-based, like Dutta.

**T9b. Error size vs structure of quantization error.**
- **Quantization Error Is Spectrally Flat.** Kennedy & Kennedy 2026. https://arxiv.org/abs/2609.33923 [html-q] (own-i3)
  - RTN error has an effective dimensionality 0.93–0.96× the i.i.d. value over 1,683 tensors, invariant from 2 to 8 bits.
  - One Gaussian probe gives an unbiased ‖error‖_F² estimate.
  - Isotropic Gaussian probes **over-excite the few high-energy residual channels** (29% vs 17% of energy, Qwen3-8B). They therefore overestimate absolute output damage but preserve the ranking. The propagated probe tracks the GPTQ objective (ρ 0.81–0.83).
  - **Relation: supports I5 and supplies its mechanism.** Isotropic noise > RTN at equal norm is a channel-energy effect, and gshape (per-group RMS) ≈ RTN follows. The paper covers output space and perplexity only; we show the behaviour-level consequence.
- **The Structure of Quantization Damage.** Hu & Ramachandran 2026, a NeurIPS 2026 workshop submission. https://arxiv.org/abs/2609.01587 [html-q] (own-i3)
  - Damage is diffuse: recovering 75% of the gap needs about half the layers.
  - Granularity (per-row → g128) is worth +0.095 CORE; GPTQ and AWQ add only +0.020/+0.017 on top.
  - AWQ is calibration-seed-stable (spread 0–2%), GPTQ is not (4–24%, App. F).
  - **Relation:** supports "per-group scale is the sufficient statistic" (gshape ≈ RTN). The seed spread bears on I5 method comparisons.
- **Quantization Degradation: A Signal–Noise Perspective.** Zhou et al. 2026. https://arxiv.org/abs/2608.08188 [abs] (own-i3; in S-mfd as a lead)
  - Degradation depends on weight-error magnitude, task-signal strength and the *alignment* of the error with task-specific activations. Errors are attenuated, preserved or amplified across layers.
  - **Relation:** the alignment term is a structure effect. It predicts task-specific fragility (I6), and it is the candidate reason AWQ ≠ RTN at equal perplexity.
- **Stochastic Rounding Increases Small Singular Values.** Ma, Yu, Drineas 2026. https://arxiv.org/abs/2606.00312 [abs] (own-i3)
  - Stochastic rounding lifts tail singular-value clusters, so random rounding differs spectrally from nearest rounding.
  - **Relation:** theory for why rtnsign (random signs) ≠ RTN.
- **Is (Selective) RTN All You Need?** Kogan 2025. https://arxiv.org/abs/2505.15909 [abs] (own-i3)
  - RTN reaches accuracy similar to advanced methods, at lower cost.
  - **Relation:** context for "method ≠ damage".
- **Taming Sensitive Weights (NPFT).** Wang & Yang, CPAL 2025. https://arxiv.org/abs/2412.06858 [abs] (own-i3)
  - Noise-perturbation fine-tuning lowers the Hessian trace on outliers, and RTN then matches GPTQ.
  - **Relation:** noise as a quantization proxy.
- **QuIP.** Chee et al. 2023. https://arxiv.org/abs/2307.13304 [abs] (own-i3)
  - Quantization "benefits from *incoherent* weight and Hessian matrices". Random orthogonal pre/post-processing makes error noise-like.
  - **Relation:** incoherence is the condition under which size-generic behaviour should hold.
- **DiffQ.** Défossez, Adi, Synnaeve 2021. https://arxiv.org/abs/2104.09987 [abs] (own-i3)
  - Independent pseudo-quantization (uniform) noise stands in for the quantizer during training.
  - **Relation:** the classical additive-noise proxy in DNNs.
- **AdaRound.** Nagel et al., ICML 2020. https://arxiv.org/abs/2004.10568 [full] (own-i3, pdftotext)
  - The diagonal Hessian terms see only |Δw|, while the off-diagonal terms see the *sign*. Nearest rounding ignores them.
  - ResNet18 layer 1 at 4-bit: nearest 52.29%; 100 stochastic roundings 52.06 ± 5.52% (48/100 beat nearest; best 63.06%); ceil or floor 0.10%.
  - **Relation:** the anchor for "structure (sign correlation) matters at equal magnitude". Consistent with q14 rtnsign λ 0.175 > RTN 0.098. That comparison is provisional, from one seed and 2 nonces; the difference is ≈ 1.5 single-draw null SDs (`analysis/insights/iter_3/out/r08_size_generic_live.json` `null_single_draw_lam_sd`).
  - Caveat: our rtnsign is off-grid (`cloq/compress.py:128-147`), so it is not a valid rounding.
- **HAWQ.** Dong et al., ICCV 2019. https://arxiv.org/abs/1905.03696 [abs]
  - The Hessian spectrum sets layer sensitivity.
  - Together with **GPTQ** (Frantar et al., ICLR 2023, https://arxiv.org/abs/2210.17323 [abs]; second-order compensation) and **AWQ** (Lin et al., MLSys 2024, https://arxiv.org/abs/2306.00978 [abs]; protects the 1% activation-salient channels by per-channel scaling). (own-i3)
  - **Relation:** Hessian or activation-weighted error, as opposed to ‖·‖_F. This is the reason matching on weight norm is a crude size variable.
- **Statistical Theory of Quantization.** Widrow, Kollár, Liu, IEEE TIM 1996. https://isl.stanford.edu/~widrow/papers/j1996statisticaltheory.pdf [abs] (own-i3)
  - Uniform quantization "can often be modeled by an additive noise that is uniformly distributed, uncorrelated with the input signal, and has a white spectrum", under stated conditions.
  - **Relation:** the classical anchor for size-generic behaviour.
- **Adversarial bound on "size-generic".**
  - Egashira et al. 2024. https://arxiv.org/abs/2405.18137 [abs]: behaviour hidden in the full-precision model activates only after quantization, via PGD inside the quantization-equivalence region.
  - **AGENTQ.** Liu & Yan, EMNLP 2026. https://arxiv.org/abs/2609.14060 [abs]: quantization-conditioned backdoors in *agents*, up to 100% post-quantization attack success (NF4, FP4, INT8). (own-i3)
  - **Relation: competes with an unscoped I5.** Scope I5 to non-adversarial PTQ.
- **Noise Injection Degrades Safety Guardrails.** Shahani et al. 2025. https://arxiv.org/abs/2505.13500 [abs] (own-i3)
  - Gaussian noise (in activations) raises harmful output by up to 27%.
  - **Relation:** a noise perturbation shifts behaviour classes; no quantization comparison.

**T9c. Where compression damage lands, and the fragile set.**
- **Perplexity Can Miss SAE Feature Damage.** Duan 2026, submitted to TMLR. https://arxiv.org/abs/2606.03002 [abs] (own-i3)
  - RTN and matched-perplexity magnitude pruning damage overlapping SAE feature sets: Jaccard 0.79–0.86, damage Spearman 0.98.
  - Survival is predictable from FP statistics (AUC 0.92–0.97; peak activation).
  - **Relation:** supports I6 b (shared across perturbation types) at feature level. Contrasts with I6 d: task fate is *not* FP-predictable in closed loop.
- **Hidden Language Consistency.** Shafique & Marchisio 2026. https://arxiv.org/abs/2608.08447 [abs] (own-i3)
  - Quantization changes output-language consistency "independently of its effect on accuracy". GPTQ and AWQ beat AutoRound.
  - **Relation:** method differences that do not appear in accuracy (question 3).
- **Interpreting the Effects of Quantization.** Singh & Sajjad, AACL 2025. https://arxiv.org/abs/2508.16785 [abs] (own-i3)
  - Calibration changes are minor, and internal changes are model- and task-dependent.
  - **Relation:** consistent with I6 d; the confidence layer barely moves.
- **Through a Compressed Lens.** Wang et al., TrustNLP @ ACL 2026. https://arxiv.org/abs/2505.13963 [abs] (own-i3)
  - Quantization usually lowers factual recall but "occasionally … may even enhance" it; this is method-dependent.
  - **Relation:** two-sided change, as in I5.
- **Compressing LLMs: The Truth Is Rarely Pure.** Jaiswal et al., ICLR 2024. https://arxiv.org/abs/2310.01382 [abs] (own-i3)
  - Perplexity hides knowledge loss (LLM-KICK); quantization is gentler than pruning.
  - **Relation:** perplexity ≠ behaviour (question 3).
- **Example-level anchors** (own-i3; all [abs]):
  - Toneva et al., ICLR 2019, https://arxiv.org/abs/1812.05159: examples are forgotten at predictable rates.
  - Baldock et al. 2021, https://arxiv.org/abs/2106.09647: example difficulty is consistent *across architectures*. **Counterpoint to I6 c.**
  - Neyshabur et al. 2017, https://arxiv.org/abs/1706.08947: scale-normalised sharpness and margin, via PAC-Bayes. The precedent for the I6 "normalised margin" (S6-d); it is per-model, not per-example.

**T9d. Quantized agents and open- vs closed-loop prediction (additions to T1 and T3).**
- **Flat Score** (T1), re-read for units via [html-q]:
  - The "failure set preserved" correlation is over **per-tool-name hallucination frequencies** (0.97, Gemma-4-31B telecom; 3/1,646 INT4 hallucinations are novel).
  - Per task: "4-bit worse on 33, better on 26, tied on 55" (4 trials per task).
  - Error-budget exhaustions: 5 (BF16) → 46 (INT4); no episode hits max_steps. No rerun null for any of these.
- **Dynamic Mixed-Precision Routing.** Li et al. 2026. https://arxiv.org/abs/2602.02711 [abs] (own-i3)
  - Multi-step LLM interaction shows "diverse sensitivities among interaction steps". Step-level routing between high- and low-precision models is learned with KL.
  - **Relation:** step-level analogue of I6 critical decisions.
- **Do Open-Loop Metrics Predict Closed-Loop Driving?** Wang et al. 2026. https://arxiv.org/abs/2605.00066 [abs] (own-i3)
  - NAVSIM PDMS vs Bench2Drive: ρ = 0.90 with a reduced formula, "clear ranking inversions" and a "snowball effect".
  - **Relation:** supports I7 (amount yes, fine ordering no).
- **On Offline Evaluation of Vision-based Driving Models.** Codevilla et al., ECCV 2018. https://arxiv.org/abs/1809.04843 [abs] (own-i3)
  - Offline error "is not necessarily correlated with driving quality". Models with identical prediction error drive very differently.
  - **Relation:** the seminal anchor for I7.

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

## Answers for iteration 3

Calls: **(a)** new; **(b)** sharper or more general version; **(c)** already shown with the same scope.

Provisional main-session facts used here (2026-09-29 09:30 PDT, not frozen):
- λ at W4 is 0.05–0.15 vs a null of 0.02–0.05;
- isotropic λ is 0.13–0.15;
- q8 gshape 0.049 vs RTN 0.052;
- q14 rtnsign 0.175 vs RTN 0.098;
- AWQ 0.12–0.15 vs RTN 0.05–0.09 on q4/q8;
- W3 costs q8 −17 pp and q14 −15 pp.

evidence: queue records `/data/ziyangs/cloq_work/queue/done/a6k2_q8_gshape_w4.json` and `/data/ziyangs/cloq_work/queue/done/a6k2_q14_rtnsign_w4.json`; the λ values will live in `analysis/insights/iter_3/out/r08_size_generic_live.json` once re-run (E21).

### I5: size-generic reallocation toward an attractor. **(b)**

- **Closest prior work.** Dutta https://arxiv.org/abs/2407.09141: balanced flips at equal accuracy, margin-driven, static.
  - Singh https://arxiv.org/abs/2608.15046: churn ≈ 5.4× net.
  - Hooker https://arxiv.org/abs/1911.05248: "cannibalizes … a small subset … to preserve a similar overall top-line accuracy".
  - Vallecillos-Ruiz https://arxiv.org/abs/2606.27205: program-repair solved-set drift.
- **What we add.**
  - Closed loop.
  - Robust-task decomposition against a re-roll null, with misclassification correction.
  - Δ = λ(c − p̄). Dutta's balance is c ≈ p̄, and the model predicts loss when c collapses (W3).
  - Matched-size controls.
- **S5-a.** No paper compares a quantizer's flip set with matched-norm isotropic noise *behaviourally*.
  - At output level, Kennedy https://arxiv.org/abs/2609.33923 shows isotropic probes over-excite high-energy channels (29% vs 17%). That predicts "noise > RTN at equal ‖·‖_F", and gshape ≈ RTN confirms it. **Cite as the mechanism**; our result is its behavioural consequence.
- **S5-b.** Flat Score's ρ is per tool-name hallucination frequency, not per task (T9d). It does not conflict with λ.
- **S5-c.** No published mixture or shrink-to-attractor model of per-item success under weight perturbation was found. Bhojanapalli https://arxiv.org/abs/2102.03349 and Dutta give confidence-based accounts only. Call (a) for the model itself.
- **Structure caveats.**
  - AdaRound https://arxiv.org/abs/2004.10568: sign correlation matters at equal magnitude, consistent with rtnsign > RTN.
  - Egashira https://arxiv.org/abs/2405.18137 and AGENTQ https://arxiv.org/abs/2609.14060: rounding structure can carry arbitrary behaviour adversarially.
  - So "size-generic" must read "non-adversarial PTQ, at per-group energy granularity".

### I6: latent (model, task) fragile set. **(a)** at task level for agents; **(b)** relative to PIEs

- **Closest prior work.** Hooker PIEs/CIEs https://arxiv.org/abs/1911.05248, https://arxiv.org/abs/2010.03058: shared across compression levels; atypical examples; init-population null; no noise control; no cross-architecture test.
  - Duan https://arxiv.org/abs/2606.03002: quant ↔ pruning share SAE-feature damage (Jaccard 0.79–0.86) *and* it is FP-predictable (AUC 0.92–0.97).
- **S6-a.** No PIE-style work tests random weight noise. **Answered: no.**
- **S6-b.** No cross-architecture transfer test was found. Baldock https://arxiv.org/abs/2106.09647 reports difficulty consistent across architectures, the opposite expectation to I6 c.
- **S6-c.** Predicting which items a quantized model gets wrong from FP confidence:
  - Dutta (qualitative: low top margin flips, no AUC);
  - Integer Alibi https://arxiv.org/abs/2608.13756 (token-level AUC 0.942);
  - Duan (feature-level AUC 0.92–0.97).
  - At task level in closed loop, ours is AUC 0.43–0.60 (`analysis/insights/iter_3/out/r04_margin_predict_live.json`). **We contradict the extrapolation.**
- **S6-d.** "Normalised margin" as sharpness or margin scaled by norm is in Neyshabur https://arxiv.org/abs/1706.08947, at the model level. No per-example weight-perturbation use was found, so it is (a) as a per-task score.

### I7: open loop predicts how much, not which, not net. **(b)**

- **Closest prior work.** Dutta: KL ↔ flips ρ = 0.981 (amount, static).
  - Codevilla https://arxiv.org/abs/1809.04843: offline error is not correlated with driving quality.
  - Wang https://arxiv.org/abs/2605.00066: ρ = 0.90 in aggregate, with ranking inversions.
- **What we add.** The amount/identity/net split with Δ = λ(c − p̄).
- **S7-a.** No agent or RL-compression paper predicts closed-loop *outcome churn* from open-loop divergence. **Answered: not found.**
- **S7-b.** Saturation of per-token flips as a predictor: only Patodiya https://arxiv.org/abs/2609.04748 ("saturates at the coarsest settings", episode level). Still open.

### I8: attractor collapse with loud control failures. **(b)**, partly anticipated

- **Closest prior work.** Flat Score https://arxiv.org/abs/2607.27275: budget exhaustions 5 → 46 at INT4, no max_steps hits, tool-name hallucination up to 2.5×, no rerun null.
  - Advani https://arxiv.org/abs/2606.09863: silent false success.
  - Lian https://arxiv.org/abs/2606.25519: token inflation.
- **S8-a.** Termination reasons against a same-model re-roll baseline: **not found.** Flat Score reports budget exhaustion without a null.
- **S8-b.** The silent vs loud split is documented for agent reliability (Advani), but not as a function of perturbation size.
- **What we add.** Loud failures are tied to c, and the silent share at W4 is measured against the null.

## Ideas from recent work

Iteration 3 replaces the iteration-1 list. The old items 1–5 are archived at the end of this section: they are done, or they have moved to experiments E2, E5 and E17.

1. **(Kennedy 2609.33923) Channel-energy share as the size variable.**
   - For each checkpoint delta, measure the share of the propagated output perturbation in the top-k energy residual channels. Use one forward pass on E3 contexts, or a Gaussian-probe estimate as in the paper.
   - Prediction: at equal ‖·‖_F it orders λ as isotropic > rtnsign > gshape ≈ RTN. With output KL it explains AWQ > RTN (q4/q8).
   - Falsified if the ordering by energy share disagrees with the λ ordering on 2 of 3 models.
   - evidence: https://arxiv.org/abs/2609.33923; `cloq/compress.py:128-152`.
2. **(AdaRound 2004.10568, Ma et al. 2606.00312) Valid stochastic rounding.**
   - Build W4 checkpoints on RTN's grid and scales with random up/down rounding (2 seeds), on q14 and q8.
   - Prediction: mean λ ≈ RTN with a spread larger than the null pair SD, and the same fragile set F (I6 b).
   - If λ(stochastic) ≈ rtnsign > RTN, sign correlation, not off-grid-ness, is what protects RTN.
   - evidence: https://arxiv.org/abs/2004.10568 (Table 1); `analysis/insights/iter_3/out/r08_size_generic_live.json` `null_pair_lam_sd`.
3. **(Singh 2608.15046; Hu & Ramachandran 2609.01587 App. F; Williams & Aletras 2311.09755) Calibration-seed control.**
   - Build AWQ-W4 and GPTQ-W4 with a second calibration seed on q4/q8.
   - Prediction from those papers: GPTQ λ moves more than AWQ λ. I6 predicts the fragile set F stays shared across seeds.
   - If AWQ's λ moves by more than 0.05, the "AWQ reallocates more than RTN" claim is a calibration draw.
   - evidence: https://arxiv.org/abs/2608.15046, https://arxiv.org/abs/2609.01587.
4. **(Dutta 2407.09141, Tice 2412.01784) The attractor predicts the *sign* of Δ from p̄.**
   - Where p̄ < c (weak model, hard domain or airline subset), the same perturbation should *raise* the score. Tice's noise-unmasks-sandbagging is the extreme case of a low p̄ and a higher c.
   - Test: split tasks by domain or by null p̄ bins on existing cells, and check sign(Δ_bin) = sign(c − p̄_bin). 0 GPU-h.
   - evidence: https://arxiv.org/abs/2407.09141, https://arxiv.org/abs/2412.01784; `analysis/insights/iter_3/out/r01_realloc_live.json`.
5. **(Flat Score 2607.27275, Duan 2606.03002) "Amplify the existing failure".**
   - Test whether I6 fragile tasks are those whose null draws already show error events (tool errors, hallucinated IDs, repeated calls) even while succeeding.
   - Flat Score's account predicts that breaks concentrate there, with AUC > 0.7 from null-draw error-event counts. I6 d predicts that BF16-visible signals fail (≈ 0.5).
   - 0 GPU-h on the existing trajectories.
   - evidence: https://arxiv.org/abs/2607.27275; `analysis/insights/iter_3/out/r04_margin_predict_live.json`.

<details><summary>Archived iteration-1 ideas</summary>


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

</details>

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
- Pruning and distillation on agents: not yet swept. (Iteration 3: only Duan 2606.03002, feature-level quant ↔ pruning overlap; still open for agents.)
- Unread leads: 2602.18998, 2601.14888, 2510.18731, 2604.08782, 2608.14711, 2605.08137 (S-cae, end).
- *(added by cloq-verify, iter 1; evidence `docs/insights/iter_1_verdicts.md`)* **V1-Q1 (I4, E5).** Has any agent-benchmark paper treated the *user simulator's* serving numerics as a perturbation? Legacy→a6k2 re-serving changed the simulator's first user message in 11/20 det tasks, the same tasks for q4 and q30a3 (`analysis/insights/iter_1/verify/out/v02_a6k2_det.json`).
- **V1-Q2 (I1).** Any prior report of a per-decision divergence-hazard *floor* that is flat below a resolution scale (e.g. the bf16 log-prob grid, 0.125 nats) and rises only above it? (Patodiya's 3.5% per turn vs 36% per episode is the nearest; check Du 2609.26621 §5 and Islam 2604.13206.)
- **V1-Q3 (I3).** RTN vs GPTQ/AWQ at *matched output-logit shift*: evidence that RTN carries damage beyond its shift (systematic/outlier-channel error vs noise-like error)? Legacy q8 RTN-W4 Δ −10.5 pp vs Gaussian k=1 0.0 pp at matched median |d| (`verify/out/v04_pooled_draws.json`).
- **V1-Q4 (I2).** Agent self-correction after a wrong tool call: published recovery rates besides Flat Score's 55%? Our q4 shows tool-turn flip rates 0.2–0.9 (k=1, RTN-W4) with no measurable db_match loss.
- **V1-Q5 (I1, I4; carried from candidates).** Divergence or benchmark-score change from a compiler/autotune-level numerics change (not batch or kernel swap) in multi-turn agents.
- **V1-Q6 (I2; carried).** Agent-quantization work reporting decisions/turns per episode against a noise null; matched-output-KL quantizer comparisons in agents (I3-Q4 re-check before submission).
- *(iteration 3)* ~~S5-a matched-norm isotropic noise vs a quantizer's flip set~~. No behavioural precedent. Kennedy 2609.33923 gives the output-level mechanism (see Answers for iteration 3, I5).
- ~~S5-b Flat Score ρ unit~~. It is per tool-name hallucination frequency, not per task (T9d).
- ~~S5-c shrink-to-attractor model~~. Not found. Confidence-based churn accounts only.
- ~~S6-a PIEs vs random noise~~. Not tested in PIE work. ~~S6-b cross-architecture~~: not tested; Baldock is a counterpoint.
- ~~S6-c FP confidence → quantized errors~~. Token-level and feature-level AUC 0.92–0.97; task-level ours 0.43–0.60.
- ~~S6-d normalised margin~~. Neyshabur 2017, model level only.
- ~~S7-a open-loop → closed-loop churn~~. Not found in agents or RL compression; the driving analogues are Codevilla 2018 and Wang 2605.00066.
- S7-b: saturation of per-token flips as a predictor at 4 bits. Only Patodiya (episode level). **Open.**
- ~~S8-a termination reasons vs re-roll~~. Not found (Flat Score: 5 → 46 budget exhaustions, no null). ~~S8-b silent vs loud~~: Advani (not perturbation-indexed).
- **New (iteration 3).**
  - Q9-1: Does any PTQ paper report per-item flips for **stochastic vs nearest rounding** in LLMs? AdaRound is CNN, one layer.
  - Q9-2: Full text of Zhou 2608.08188. Does its "error–activation alignment" term give a per-task fragility score we can compute?
  - Q9-3: Full text of Vallecillos-Ruiz 2606.27205. Is its program-repair loop multi-turn, and do they give per-method JCR numbers we should quote?
  - Q9-4: Re-sweep before submission. Kennedy (2609.33923, 2 days old) and Before-the-Flip are very recent; check for follow-ups on isotropic vs quantization behaviour.

