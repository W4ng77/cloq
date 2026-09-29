"""CLOQ code loop: a second closed-loop benchmark with deterministic execution feedback (no LLM user simulator).

The model gets a hard competitive-programming problem (LiveCodeBench v5/v6 increments), writes a Python solution,
a subprocess sandbox runs the public example tests and returns the verdict / error, and the model revises, for up to
T turns. Success = the final program passes all tests (public + hidden). Logging follows cloq.agent / cloq.run_arm so
the existing decision-level analyses (margins, divergence, first-divergence) run unchanged on runs/<run_id>/code/.

Pre-registered deviation (2026-09-29, before any main run): replies use max_tokens 4096 instead of the frozen 1024
(hard-only smoke: 45% of replies were cut at 1024). All other generation settings are frozen_v0 generation_agent.
Recorded in the manifests (generation_deviation), config.json and metrics.json.
Problem set: manifests/code/lcb_emh_v5v6.json (easy+medium+hard, 342) is the main set, because medium+hard gave q4
pass@end 0.10 < 0.15 on the 20-problem smoke (coordinator rule); lcb_mh_v5v6.json / lcb_hard_v5v6.json are kept.
"""
