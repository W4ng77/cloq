# Survey sweep: margins, flips, divergence (2026-09-28)

Verified against arXiv export API (title/authors/date/abstract); full text read for 2609.26621, 2607.27275,
2608.13756, 2609.04748, 2506.09501, 2407.09141, 2605.30218, 2604.13206, 2608.08239 and the Thinking Machines blog.
"abstract only" = body not read.

## Close competitors

A. **Du et al. 2026, TMLR — "Greedy Decoding Is Not Precision-Invariant"** (https://arxiv.org/abs/2609.26621).
   BF16 vs FP16 greedy: 49–100% of prompts diverge (6 models 1.1B–7B, 4 families, 12B probe); one flip cascades.
   Mechanism verbatim: "A token flips between BF16 and FP16 when some competitor's differential perturbation exceeds
   its original logit gap … flips concentrate where the top-two margin is small relative to the per-logit
   perturbation scale (σz ≈ 0.026)"; appendix formula **P(flip at t) ≲ P(∆t < σz)**, "depends primarily on the margin
   distribution". TinyLlama margins: diverged median 0.039 vs agreed 5.733. CoT concentrates margin mass at small values.
   Scope: single-turn, BF16 vs FP16 only; no δ sweep, no multi-step product, no agents, no cross-model prediction.
   → Our per-step model is their Eq. 14: cite and EXTEND (closed loop, perturbation families, step product, P1, P3).
B. **Jang et al. 2026 — "Flat Score, Amplified Failures"** (https://arxiv.org/abs/2607.27275), preprint.
   τ²-bench telecom+retail, 456 episodes/cell; Gemma-4-31B, Gemma-4-26B-A4B, Qwen-3.6-27B, Qwen-3.6-35B-A3B at
   BF16/FP8/AWQ-INT4. No score change survives multiple-comparison correction; tool-name hallucination up to 2.5×
   (19.5→38.3%, Gemma-4 dense telecom); failure set preserved (rank corr ≥ 0.94, 0.18% novel); error budget 10→2
   re-exposes ~17 pt gap; one repeat run moved the mean ~1.5 pt. Conceptual margin account
   "Δp(m)=E_η[σ(−(m+η)/τ)]−σ(−m/τ)", "quantization noise flips only thin-margin argmax decisions" — but
   "token log-probabilities are not in our logs"; no divergence vs BF16, no nonce/seed null. → COMPETES on
   "is a quantized agent actually worse?"; we add measured margins, equivalent-perturbation null, divergence model.
C. **Patodiya 2026 — "Same Request, Different Answer"** (https://arxiv.org/abs/2609.04748), submitted to IEEE Access.
   80-episode multi-turn tool-use (from BFCL), llama.cpp + vLLM. Prefix caching changes trajectories in 36.2% of
   episodes at 16-bit, 75.0% at 4-bit; caching off: 0/800 bit-identical reruns (i.e. all identical — check wording).
   "Amplification saturates at the coarsest settings" (Q4_K_M ≈ Q3_K_M ≈ 68.8%); "coarser quantization compresses
   the gaps between competing token logits"; single-turn 3.5% vs episode 36.2% "because an episode chains about ten
   requests and a single changed token propagates" (compounding in words, no formula). → partial P1; we EXTEND.
D. **Chen 2026 — "The Integer Alibi"** (https://arxiv.org/abs/2608.13756). INT8 kernel swap in vLLM: 0/N sequences
   agree (Qwen3-1.7B, 8B). Teacher-forced: 769/16,384 positions flip (4.7%); flip rate 34% in lowest-margin decile → 0
   above margin ≈ 9; ROC-AUC 0.942 [0.935, 0.949]; calibrated margin→flip Brier 0.035 vs 0.044. First teacher-forced
   flip ≠ first free-running divergence position. → SUPPORTS per-step calibration; AUC benchmark.
E. **Chu et al. 2026 — "MarginGate"** (https://arxiv.org/abs/2605.30218). Batch-induced flips on 0.3–1.3% of decode
   steps (0.48% Llama-3.1-8B MATH500); low top-1/top-2 margins expose most flip risk; verifying only low-margin steps
   restores 100% determinism at 15–19% trigger rate. → SUPPORTS; single-turn, batch nondeterminism only.

## Other entries
| # | Paper | URL | Venue | Claim | Relation |
|---|---|---|---|---|---|
| 6 | Yuan 2025, Numerical Sources of Nondeterminism | https://arxiv.org/abs/2506.09501 | – | batch/GPU config changes greedy BF16 outputs (≤9% acc); flips when variation exceeds top-2 gap | supports, anchor |
| 7 | He / Thinking Machines 2025 blog | https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/ | blog | batch-invariant kernels → 1000/1000 identical | noise-floor anchor |
| 8 | Atil 2024 | https://arxiv.org/abs/2408.04667 | – | accuracy varies ≤15% across runs at "deterministic" settings | supports (abstract only) |
| 9 | Fu 2026, Token Probabilities Expose Nondeterminism | https://arxiv.org/abs/2601.06118 | – | variation large for p in 0.1–0.9; impact estimable from one run's token probs | close in spirit to P3 (abstract only) |
| 10 | Messina 2026, Background Temperature | https://arxiv.org/abs/2604.22411 | – | implementation noise as effective temperature | framing |
| 11 | Islam 2026, Numerical Instability and Chaos | https://arxiv.org/abs/2604.13206 | – | stable / chaotic / signal regimes under ε sweep, single step | partial P1 |
| 12 | Dutta 2024, Accuracy is Not All You Need | https://arxiv.org/abs/2407.09141 | – | flips at equal accuracy (≤13.6%); low top margin → answer changes | supports, anchor |
| 13 | Deiseroth 2023, Divergent Token Metrics | https://arxiv.org/abs/2311.01544 | – | first divergent token metric for compression | anchor |
| 14 | Lotfi 2026, Quantized Reasoning Models Think Longer | https://arxiv.org/abs/2606.00206 | – | KL(quant‖fp) tracks next-token entropy | supports |
| 15 | Li 2025, Quantization Meets Reasoning | https://arxiv.org/abs/2505.11574 | – | first vulnerable step flips and cascades; restore local margins | supports |
| 16 | Bigelow 2024, Forking Paths | https://arxiv.org/abs/2412.07961 | – | sparse forking tokens | anchor |
| 17 | Wang 2025, High-Entropy Minority Tokens | https://arxiv.org/abs/2506.01939 | NeurIPS 2025 | ~20% CoT tokens are forks | anchor |
| 18 | Lin 2024, Critical Tokens Matter | https://arxiv.org/abs/2411.19943 | – | critical tokens drive wrong outcomes | anchor |
| 19 | Salinas 2024, Butterfly Effect of Altering Prompts | https://arxiv.org/abs/2401.03729 | – | trailing space changes labels | nonce anchor |
| 20 | Sclar 2023, Prompt formatting sensitivity | https://arxiv.org/abs/2310.11324 | ICLR 2024 | ≤76 pt spread from formatting | anchor |
| 21 | Chen 2026, Noise Floor Audit for Agent Benchmarks | https://arxiv.org/abs/2608.22331 | – | BFCL T=0 rerun ever-flip 0.7–2.7%; prompt perturbations 11–58× rerun SD | supports; slight competitor |
| 22 | Gonuguntla 2026, The Replay Gap | https://arxiv.org/abs/2608.08239 | COLM 2026 | model swap rewrites 61–94% of post-fork actions; FP8 control forks diverge >90%, AWQ ~identical | supports; **noise floor is configuration-dependent — complicates "any sufficiently large perturbation re-rolls"** |
| 23 | Zhang 2026, AgentDiff | https://arxiv.org/abs/2605.25981 | – | meaning-bearing rewrites +19.7 pp inconsistency vs presentation changes; "stealth divergence" | partly contradicts pure re-roll view |
| 24 | Dong 2025, ACBench | https://arxiv.org/abs/2505.19433 | ICML 2025 | compression benchmark for agents | baseline |
| 25 | Liu 2025, Quantization Hurts Reasoning? | https://arxiv.org/abs/2504.04823 | COLM 2025 | quantized reasoning study | context |
| 26 | Laban 2025, Lost in Multi-Turn | https://arxiv.org/abs/2505.06120 | – | 39% multi-turn drop, no recovery | supports compounding |
| 27 | Barres 2025, τ²-Bench | https://arxiv.org/abs/2506.07982 | – | benchmark | ours |
| 28 | Yao 2024, τ-bench | https://arxiv.org/abs/2406.12045 | – | pass^k | reliability anchor |
| 29 | Cohen 2019, Randomized Smoothing | https://arxiv.org/abs/1902.02918 | ICML 2019 | margin vs noise-radius certificate | theory analogue |
| 30 | Ross 2011, DAgger | https://arxiv.org/abs/1011.0686 | AISTATS 2011 | compounding error | anchor |
| 31 | Bengio 2015, Scheduled Sampling | https://arxiv.org/abs/1506.03099 | – | exposure bias | anchor |
| 32 | Ranzato 2015, MIXER | https://arxiv.org/abs/1511.06732 | – | exposure bias | anchor |
Optional: Rabanser 2026 (https://arxiv.org/abs/2602.16666, ICML 2026), Gupta 2026 ReliabilityBench
(https://arxiv.org/abs/2601.06112), Fang 2025 Smaller=Weaker? (https://arxiv.org/abs/2506.22776; quantized models
withstand Gaussian weight noise better — matters for Gaussian as a comparison perturbation), Zhou 2026
(https://arxiv.org/abs/2608.08188), LLM-42 (https://arxiv.org/abs/2601.17768), HEAL (https://arxiv.org/abs/2606.21023),
Token Inflation (https://arxiv.org/abs/2606.25519).

## Novelty against the P-claims
1. Per-step margin flip model: NOT new (Du 2026 Eq. 14; Yuan, Dutta, Jang qualitative; Chen, Chu empirical AUC 0.94).
   Present as inherited.
2. Multi-step product 1−∏(1−P(m_s<δ)) for closed-loop agents: no explicit statement found (Patodiya in words only).
3. P1 saturation across perturbation types on one δ axis for agents: not found; partial (Patodiya cache path,
   Islam single-step). Replay Gap: noise floor is configuration-dependent → report δ per serving path.
4. P3 cross-model prediction from BF16 margins: no direct precedent (closest Fu 2026, Du 2026 in words).
5. "Is a compressed agent actually worse?" competes with Jang 2026 on the same benchmark.
Caveat: field moving fast (most competitors May–Sep 2026, several single-author preprints) — re-sweep before submission.
