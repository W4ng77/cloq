"""CLOQ code loop: a second closed-loop benchmark with deterministic execution feedback (no LLM user simulator).

The model gets a hard competitive-programming problem (LiveCodeBench v5/v6 increments), writes a Python solution,
a subprocess sandbox runs the public example tests and returns the verdict / error, and the model revises, for up to
T turns. Success = the final program passes all tests (public + hidden). Logging follows cloq.agent / cloq.run_arm so
the existing decision-level analyses (margins, divergence, first-divergence) run unchanged on runs/<run_id>/code/.
"""
