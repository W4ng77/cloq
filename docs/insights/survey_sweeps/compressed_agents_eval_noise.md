# Survey sweep: compressed tool agents, agent-eval noise, multi-turn degradation (2026-09-28)

29 papers, abstracts opened on arXiv (full texts NOT read); metadata from arXiv export API. Semantic Scholar/OpenAlex
rate-limited → ACL-Anthology-only / OpenReview-only work may be missing.

## Flags
(a) framing: **Replay Gap** (COLM 2026, https://arxiv.org/abs/2608.08239) uses same-model control forks as a null in
multi-step agents (SWE-bench); T=0 determinism is serving-dependent (FP8 controls >90% fork divergence, AWQ ~identical)
→ our null width may depend on quantization format; scope our novelty as compression (not model switching), closed-loop
τ² with a user simulator. **Quantization Inflates Reasoning** (https://arxiv.org/abs/2606.25519): INT4/INT3 keep
accuracy but lengthen reasoning incl. agent tool use — hidden-cost framing.
(b) must cite / compare: Replay Gap; On Randomness in Agentic Evals (2602.07150: pass@1 varies 2.2–6.0 pp, SD>1.5 pp at
T=0); Benchmarking the Benchmarks (2607.02577: audits τ²-Bench, 18.5% evaluator–human disagreement); Huang
2609.07785 (τ²-bench, close ranks unresolved) and 2607.12338 (τ-bench needs 25% of tasks); Mekala EMNLP 2025
(2505.20276: 8-bit −0.8%, 4-bit up to −59% on long inputs); UniComp EMNLP 2026 (2602.09130: instruction following degrades).

## Tests proposed on our data
- T1 (Replay Gap): control-divergence rate per quantization format (same-config reruns diverging at first action);
  report null width per arm, not a pooled null.
- T2 (Token inflation): tokens/turn, turns/episode, tool calls/episode, quantized vs BF16, on tasks passing in both;
  against the null spread; predict W4-RTN inflates more than AWQ/GPTQ.
- T3 (Lost in multi-turn, ERGO, Markov reliability): position of first divergent/erroneous turn vs turn index —
  does compression move the first error earlier rather than add errors uniformly? Hazard / absorbing-chain fit.
  T3b: entropy/low-margin spikes before failing turns (we log margins).
- T4 (False success 2606.09863, same benchmark): episodes where the agent claims success but DB check fails; does
  compression raise the false-success share beyond the null?
- T5 (Huang; Coding Agents Converged): per-task McNemar with Holm; task count needed to separate each arm at observed
  effect sizes (task-subsampling replay); test whether W4 pass sets nest inside BF16's.
- T6 (Quantization Undoes Alignment 2605.15208): per-task pass→fail / fail→pass flip matrices across seeds; W4
  "new failure" rate vs seed-only flip rate.

## Papers (abstract-level)
[1] Replay Gap, 2608.08239, COLM 2026 — model swap: +0.25–0.66 normalized edit distance over controls, 61–94% of
post-fork actions rewritten; early swaps diverge at first action 74–77% vs controls 6–35%; replay mispredicts every
success-relevant outcome call; FP8 controls >90% divergence, AWQ ~identical. Competes/precedes; we extend.
[2] Lian 2026, Quantization Inflates Reasoning, 2606.25519 — token inflation incl. agent tool-use; QAT best fix.
[3] Bjarnason 2026, On Randomness in Agentic Evals, 2602.07150 — 60k SWE-bench trajectories; 2–3 pp gains may be noise.
[4] Bhat 2026, Benchmarking the Benchmarks, 2607.02577 — τ²-Bench audited; brittle state matching, trajectory lock-in, wrong ground truths.
[5] Huang 2026, What Does an LLM-Agent Leaderboard Rank Compare?, 2609.07785, IEEE DSAA 2026 — τ²-bench, paired estimands.
[6] Huang 2026, How Many Tasks Are Enough, 2607.12338, KDD'26 workshop — τ-bench decision targets at 25% of tasks.
[7] Mekala 2025, quantization on long-context, 2505.20276, EMNLP 2025.
[8] von Rad 2026, UniComp, 2602.09130, EMNLP 2026 — reliability decoupled from retained performance.
[9] Laban 2025, Lost in Multi-Turn, 2505.06120 — 39% drop = small aptitude loss + large unreliability; no recovery.
[10] Liu 2026, Intent Mismatch, 2602.07338 — multi-turn loss from intent gap; user-sim variance confounds → null should vary user seed.
[11] Khalid 2025, ERGO, 2510.14077, UncertaiNLP 2025 — entropy-spike resets +56.6%.
[12] Tran-Truong 2026, Markov Chain Reliability, 2604.24579 — pass@k / pass^k as projections of one success-time distribution.
[13] Advani 2026, False Success, 2606.09863, FAGEN@ICML 2026 — 9,876 τ²-bench trajectories, false success 45–48% single-control.
[15] Liu 2026, Coding Agents Have Converged, 2609.17394, ADMA 2026 — McNemar separates 0/29 top pairs; nested solution sets.
[16] Rath 2026, Quantization Undoes Alignment, 2605.15208 — 3-bit makes 6–21% of items newly biased (5 seeds).
[17] Mix-Quant 2605.20315 — full quantization hurts agents; FP4 prefill + BF16 decode preserves.
[18] QuantClaw 2604.22577 — agent precision needs task-dependent.
[19] TriAxialKV 2605.17170; [20] KV compaction 2608.00902; [21] StepKV 2609.22158 — KV compression for agents (adjacent).
[22] IFFC 2608.22472 — function calling robust under quantization (open loop).
[23] AgentProv 2609.00052, EMNLP 2026 — providers silently quantize; tool-use probes detect substitution 100%.
[24] Zheng 2025, Qwen3 Quantization, 2505.02214 — same family; competitive at 4-bit statically.
[25] Zhang 2025/26, Reasoning Meets Compression, 2504.02010, ICLR 2026.
[26] Kurt 2026, llama.cpp quantization, 2601.14277.
[27] Bouguerra 2026, Less Precise Can Be More Reliable, 2509.21173, ICML 2026 — quantization can help → two-sided tests.
[28] Gupta 2026, ReliabilityBench, 2601.06112 — perturbation-intensity axis on tasks.
[29] Shu 2026, What Resolve Rate Hides, 2607.06184 — anti-patterns track difficulty; control for it.
[30] Zhang 2026, MAS efficiency evaluation, 2609.05933, EMNLP 2026.

## Self-null for compression in an agent loop?
Closest: Replay Gap (null, agents, but model switching, SWE-bench); Rath (seeds, static). Otherwise unclaimed at
abstract level (Flat Score and Noise Floor Audit covered in the other sweep).
Partial/not done: compounding-error-in-agents search (mostly robotics hits), pruning/distillation on agents, full texts.
Unread leads: 2602.18998, 2601.14888, 2510.18731, 2604.08782, 2608.14711, 2605.08137.
