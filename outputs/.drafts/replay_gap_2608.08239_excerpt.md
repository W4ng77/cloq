**TL;DR** Verbatim excerpts of arXiv 2608.08239v1 (The Replay Gap, Gonuguntla, COLM 2026 Efficient Reasoning Workshop), used to position the paper (W100j). Source: https://arxiv.org/abs/2608.08239 (PDF text extracted 2026-10-02).

## Abstract

LLM routers promise efficiency by matching each request to the cheapest
adequate model, and are increasingly applied per step inside multi-step
agents. Yet agentic routers are evaluated like single-turn routers: by replaying logged trajectories and substituting another model’s recorded outputs,
assuming the rest of the trajectory is unaffected. We test this assumption
with branching rollouts: we fork live SWE-bench agent trajectories at controlled points, rebuild the environment, continue each fork with a different
model, and compare against same-model control forks that isolate sampling
and replay noise. Across six paired runs (∼900 rollouts), swaps exceed
their matched control floors by +0.25 to +0.66 normalized edit distance
(multiplicity-corrected CIs exclude zero), rewriting 61–94% of post-fork
actions; 74–77% of early swaps diverge at the first post-fork action, versus
6–35% of controls — leaving only 3% of replayed states valid. Divergence
decreases with fork depth in both directions. All five outcome flips we
observe occur in swap arms — upgrades rescuing unsolved instances, a
downgrade losing the sole solve — and zero occur across 359 control forks.
Scoring these same swaps with a log-stitching replay evaluator, replay
mispredicts every success-relevant outcome call and predicts patches with
0.00–0.11 similarity to reality. Auditing the noise floor, temperature-0 “determinism” is configuration-dependent: FP8-served controls diverge on
over 90% of forks while AWQ-served ones remain near-identical; and under tight budgets the stronger model more often exhausts its steps without
submitting. Replay-based benchmarks score the wrong world for agentic
routing; we release our harness and all trajectories.

## Method (Setup, Branching protocol)

Setup. We use the mini-SWE-agent scaffold (Lieret et al., 2025) — a minimal bash-only
ReAct loop — on SWE-bench Verified (Jimenez et al., 2024) with the official per-instance
Docker images, a 50-step budget, and a 28k-token context. Our pool contains a small model
S (Qwen3-4B-Instruct, FP8) and a large model L (Qwen3-14B, AWQ, thinking disabled)
(Yang et al., 2025), served by vLLM (Kwon et al., 2023) on a single 24 GB GPU at temperature
0. This deliberately mirrors the resource-constrained serving regime where routing matters
most.
Branching protocol. For each instance we run a base trajectory with the base model to
termination. We then select fork steps at 30% and 70% of the base trajectory’s length. For
each fork: (i) start a fresh container; (ii) re-execute the recorded actions of all pre-fork steps,
logging return-code agreement with the recorded observations (replay fidelity: across 11,702
replayed actions in 708 branches, 99.99% of return codes match and 707/708 branches
reconstruct exactly — Appendix B, so environment reconstruction error is not a plausible
source of the divergence we report); (iii) seed the agent’s message history with the recorded
prefix, so the branch model sees exactly what the base model saw; (iv) continue the rollout
with the branch model to termination. Each fork point receives two arms: a swap arm
(the other model) and a same-model control arm, which absorbs sampler nondeterminism,
batching effects, and environment-replay drift. Divergence attributable to the model swap
is read relative to the control.
