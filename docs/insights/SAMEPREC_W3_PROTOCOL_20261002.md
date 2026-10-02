**TL;DR** Dated pre-registration (2026-10-02) of a W3 same-precision pair: Q = GPTQ-W3 d1 (calibration c1), Q′ = GPTQ-W3
d2 (calibration c2), cells q4 and q8, exactly the design of `docs/insights/SAMEPREC_PROTOCOL.md` (sameprec-v1 with
Amendment A1: TOST at ±3 pp) except for the precision, the blocks and the gate block. Blocks are fixed to q3, q4, q5,
the only W3 d1 blocks with a precision (BF16 vs W3) dev fork (`analysis/fork/stress/<m>_gptq_w3/`, 255/255 units searched,
0 excluded, per cell), so K = 3 and the units pair one to one. Formal tasks are queued only after the build and replay
gates pass and only if they can finish before 2026-10-04 12:00 PDT. Written before any GPTQ-W3 d2 checkpoint, run or
fork outcome existed.

# W3 same-precision 2×2 fork ("Q vs Q′" at W3) — protocol sameprec-w3-v1

Written 2026-10-02 08:00 PDT. Work item W100a (second priority; docs/RESEARCH_LOG.md). The sha256 of this file is recorded
in `manifests/fork/sameprec_w3_v1.json`.

## 1. Question

As SAMEPREC §1, at 3-bit weights: how much of the W3 precision fork's turnover M and controller dependence is
precision-specific, and how much is generic trajectory sensitivity? W3 is the stress precision (larger M than W4), so it
tests whether the W4 same-precision reading (W99l) holds where quantization damage is larger.

## 2. Design (differences from SAMEPREC §2 only)

- **Checkpoints.** Q = `{"kind": "gptq", "wbits": 3, "calib": "manifests/a6k2/<m>/calib_fp_traj_c1.json"}` (the checkpoint
  behind `a6k2_<m>_gptq_w3_{n1,n2,q3,q4,q5}` and the stress precision forks). Q′ = the same with
  `calib_fp_traj_c2.json` (the calibration draw of GPTQ-W4 d2; never built at W3 before this protocol). Both are built
  inside each fork task by the worker, as for every GPTQ fork.
- **Q′ build run.** One eval run of Q′ (`a6k2_<m>_gptq_w3_d2_n1`, `manifests/eval_tasks_v0.json`, nonce `3f9a1c07`, the
  nonce of every `_n1` run) gives Q′ its own recorded decisions for the identity check and the Q′Q′ no-op. Its outcomes
  are not part of any estimate.
- **Blocks (fixed, not chosen by outcome).** q3, q4, q5 (each retail 58 + airline 27). The precision side is the existing
  dev fork of the same blocks `analysis/fork/stress/<m>_gptq_w3/` (B = BF16, Q = W3 d1; the same Q episodes, so the QQ arm
  is shared). K = 3 is the whole analysis set; all three blocks must be complete in both cells (strict rule of SAMEPREC §2
  and §4); if any is not complete or is quarantined at the evidence freeze, only per-block numbers are reported.
- **Formal tasks.** Mode `dev`, one task per cell × block (6 tasks), priority −27; q4 1 GPU (gpu_util 0.44), q8 2 GPUs
  (node004/005/007 in rotation). Outputs `analysis/fork/sameprec_w3/<m>_gptq_w3_d1_vs_d2/<blk>/`.
- Everything else (pipeline, arm mapping BB = Q′Q′, BQ = Q′Q, QB = QQ′, QQ = QQ, divergence rule, Q′ prompt-id rule, Q
  replay, no-op sample, resume) is SAMEPREC §2 unchanged.

## 3. Gates (all before any formal task is queued)

1. **Build gate.** The Q′ eval run finishes with its 85 tasks; its server canary differs from Q's (W3 d1) canary.
2. **Replay gate.** fork_driver mode `gate` per cell, Q blocks `a6k2_<m>_gptq_w3_n1` (retail, airline; not in the analysis
   set; replaces SAMEPREC's q3, which is an analysis block here), Q′ own blocks `a6k2_<m>_gptq_w3_d2_n1`, output
   `analysis/fork/sameprec_w3/gate/<m>/`. Checks 1–5 of SAMEPREC §3 (identity of Q and Q′ bit-exact on 16 recorded
   decisions each and distinct canaries; Q′ prompt ids equal Q's; search finds states; QQ and Q′Q′ no-ops bit-exact; Q
   replay, save/load, budget, re-prefill, isolation). Pass iff the driver verdict `pass` is true and check 2 holds.
3. **Time gate.** The formal tasks are queued only if, at the time both gates pass, the six tasks can plausibly finish
   before 2026-10-04 12:00 PDT (q8 ≈ 1.5 h and q4 ≈ 1 h per block-task once claimed). Otherwise nothing formal is queued
   and the reason is reported.
If any gate fails, nothing formal is queued and the failure is reported.

## 4. Admission, estimands, interpretation

SAMEPREC §4 (admission), §5 (estimands; the precision side recomputed on q3–q5 from `analysis/fork/stress/<m>_gptq_w3/`
with the same code) and §6 as amended by A1 (A1.2 TOST at ±3 pp on ΔM, ΔG_all and Δoff; A1.3 reading: an interval that
includes 0 is never read as equivalence) apply unchanged, with K = 3: primary interval t over the 3 pooled block means
(df = 2), crossed task × block bootstrap alongside (B = 2000, seed 20261001). The W3 result is reported next to the W4
result, never pooled with it.

## 5. Outputs

The SAMEPREC analysis code (`analysis/fork/analyze_sameprec.py`), extended additively to take this manifest (cell
`gptq_w3`, blocks q3–q5, the stress precision directories) before any formal W3 outcome exists, writes
`analysis/fork/out/sameprec_w3_<UTC>.{md,json}`, TL;DR first. Gate result: `analysis/fork/sameprec_w3/GATE.md`.
