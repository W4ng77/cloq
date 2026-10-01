# Evidence notes: storyline-v7 (2026-10-01)

**Literature** (`.drafts/storyline-v7-lit.md`, 32 papers with verified arXiv URLs):
- **Replay Gap (2608.08239):** forks SWE-bench runs and swaps only the continuation model (4B vs 14B), with same-model controls (0/359 flips). Its FP8 controls diverge on more than 90% of forks. This is the closest method.
- **Flat Score, Amplified Failures (2607.27275):** τ²-bench, BF16 vs INT4, a flat score that hides failure; the same failure set at every precision (rank correlation ≥ 0.94). No forks.
- **DMR (2602.02711):** per-step precision routing; no outcome counterfactuals.
- **Single-step action-swap papers** (CSO 2602.03412, Counterfactual Rollout Replay 2609.33875, Causal Agent Replay 2606.08275, AgenTracer 2509.03312): each swaps one side only.
- **Accuracy is Not All You Need (2407.09141):** two-sided flips in compressed models, single-turn only.
- **User-simulator sensitivity:** up to 9 pp (2601.17087) and 15.2 pp (2609.38043) on τ-bench.
- **Prefix caching changes trajectories:** 75% at 4-bit (2609.04748).
- **Conclusion:** none crosses action × controller at the first divergence, and none defines r/d/M/G. Novelty risk is medium.

**Determinism controls** (`docs/insights/FORK_PROTOCOL.md` L295–315):
- No-op Q→Q 20/20 and B→B 10/10 match every prompt-token hash, message, live and replay DB hash, termination, reward and counter.
- A 10% no-op sample runs in production forks; Bank U no-op checks pass 135/135 across 6 gates.
- The recovery replay audit passes 30/30 over 22 fields (W83).
- `det_probe.py` tests prefix caching on and off.

**Layer support:**
- **L1:** strong on dev (W70/W78: M 15–21%, G ±3 pp, fragility beyond baseline in 6 configurations × 2 directions, retail-driven). Confirmation is pending: the holdout is not yet run, and the prereg is being finalised (W86).
- **L2:** Bank U at f01 only (k = 1). Text-difference dominance is 41/58. Cross-quantizer same-state co-flip is 7 vs 1.4 expected. Q0 has n 6–21. f02/f03 are queued.
- **L3:** a null mean with turnover (W83). Manipulation is flawed for wrong_tool (argument errors) and premature_write (failure → failure). Table 4 is LLM-annotated.

**Model scale:** Qwen3 4B/8B only (q14 is a best-effort pending panel), and a single model family.
