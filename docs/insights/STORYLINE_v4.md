**TL;DR** Storyline v4 (2026-09-29), quantization-centred (PLAN_iter4). Quantization on closed-loop agents mostly
*reallocates* capability rather than removing it: it re-rolls the outcomes of 20–40% of tasks, and whether success
changes depends on where the re-rolled tasks land. λ (how much is re-rolled) tracks error size, not error structure;
c (where it lands) depends on the quantization method. Numbers are provisional (unfrozen snapshot) unless marked.

# Storyline v4 and expected contributions

Venue: ARR Oct 2026 → NAACL (8 pages, long). Freeze 10-05, deadline 10-12.
Setting: τ²-bench retail+airline (85 dev tasks), Qwen3 4B/8B/14B/30B-A3B/32B + Llama-3.1-8B, greedy, deterministic
batch-invariant vLLM serving, Qwen3-30B-A3B user simulator. Null = BF16 with prompt nonces n1–n8 (nonce stratum).

## One sentence
Quantization reallocates an agent's capability: it breaks some robustly-solved tasks and fixes some robustly-failed
ones, and aggregate success is unchanged when these cancel. Model: p_i' = (1−λ) p_i + λ c, so Δ = λ (c − p̄).

## Narrative
1. Problem: single BF16-vs-quantized comparisons mislead in closed loop (v0 false positive: +12 pp p=0.02 → −3.5 pp on replication).
2. Yardstick: the model's own perturbation null (BF16 + nonces). Method, not subject.
3. Reallocation: break/fix rates on null-robust tasks are 5–10× the null rate (q4 null break/fix 1.8%/4.1% vs RTN-W4 20%/11%).
4. λ is set by error size (E17): Gaussian with RTN per-group RMS and RTN magnitudes with random signs reallocate as much or more than RTN (3-model mean λ: RTN 0.23, gshape 0.26, rtnsign 0.34; CIs overlap).
5. c is set by method (q4 only so far): W4 methods share λ≈0.22–0.25 (NF4 0.37), c differs: RTN 0.18 < p̄≈0.36 (net damage), GPTQ 0.45, AWQ 0.36, rotated RTN 0.37, rotated GPTQ 0.49, MXFP4 0.42; stochastic rounding (1.41× RTN error) λ 0.35, c 0.12. "Calibration and rotation do not reduce how many tasks are re-rolled; they change where they land." Caveat: q8 AWQ λ 0.39 vs RTN 0.19.
6. Consequences: Δ = λ(c − p̄) predicts larger net damage at higher base success; W3 damage q8 −16.7 pp, q14 −14.5 pp. Open-loop probe (teacher-forced token flips, no simulator) predicts λ (ρ 0.75–0.83; partial ρ given dose 0.86) but not c or which tasks.
7. Where: breaks concentrate on writes, argument errors, hallucinated IDs, premature stop; fragile-task set predictable within a model (AUC 0.75–0.83) but not across models (0.51).

## Contributions
| # | Contribution | Experiments | Status |
|---|---|---|---|
| C1 | Evaluation protocol: equivalence test against the model's own perturbation null (stratified permutation/conformal, ε inversion, Holm, power/MDE 6.5–13 pp per family); single-run and Flat-Score-style verdicts shown to mislead | M1, M3 | test built; final table after freeze |
| C2 | Reallocation phenomenon + two-parameter λ–c model; prediction of larger net damage at higher p̄ | M2 | q4/q8/q14 hold; q30a3/q32/Llama running |
| C3 | λ follows error size; c follows method (E17 size/structure controls + 8 method families incl. NF4, MXFP4, QuaRot rotation, stochastic rounding, fake KV-cache INT8/INT4+Hadamard) | M4, M5 | E17 done; methods q4 done, q8/q14 running |
| C4 | Practical: open-loop probe cheaply predicts λ; closed loop needed for c; failure taxonomy; reporting checklist | M6, S5, S8 | data exists; recompute on freeze |

Conformal appears only inside C1 (equivalence verdicts + ε intervals), not in the title; a statistics collaborator
is writing the validity theory (stratified/weighted exchangeability).

## Risks
- "c follows method" holds only on q4 → C3 shrinks to "λ follows size".
- Llama shows a different pattern → scope limited to Qwen3.
- Higher-p̄-more-damage prediction fails → drop the prediction.

Evidence: `docs/RESEARCH_LOG.md` (W12–W16), `docs/FINAL_EXPERIMENTS.md`, `docs/insights/PLAN_iter4.md`,
`docs/insights/NULL_RULE.md`, `analysis/insights/iter_3/out/r01_realloc_unfrozen.json`, `analysis/insights/iter_3/*.py`,
`paper/review_v2.md` (previous internal review).
