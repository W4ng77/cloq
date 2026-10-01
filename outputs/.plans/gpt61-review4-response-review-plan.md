# Review plan: gpt61-review4-response
- **Artifact:** GPT-6.1 review 4 (as relayed by the author, 2026-10-01) of `docs/REPORT_GPT61_20261001_0700.md` (commit 1542f21), plus the main session's draft response plan. Source type: Markdown and local data.
- **Criteria:** claims validity (each of the six points), empirical rigor, statistical estimands, cost and feasibility before the 10-05 freeze, novelty implications, and what is missing.
- **Checks:**
  1. Recompute the recovery per-state numbers from `analysis/recovery/inject_q4/inject.json`.
  2. Recompute the Bank U change composition and duplicates from `analysis/fork/bank_u/*/f01/bank_rows.jsonl`.
  3. Inspect the 'same'-category changes for nondeterminism.
  4. Check which fields the replay check actually records (`scripts/a6000/inject_driver.py`).
  5. Measure the telecom GPU-h per cell-block from runner logs and fork outputs.
  6. Check the W78 wording against `w67_audit_v2`.
