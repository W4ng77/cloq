**TL;DR** User direction (2026-09-29): centre the paper on QUANTIZATION and TASKS, not on full-precision model
behaviour. The BF16 perturbation null is the yardstick, not the subject. The floor, serving numerics and determinism
material shrinks to a Methods section. New headline candidate: quantization reallocates capability. It breaks
robustly-solved tasks and fixes robustly-failed ones (5–10× the null rate), and a shrink-to-attractor model explains
why aggregate success often looks unchanged.

# Plan, iteration 4 (supersedes the framing of PLAN_iter3; the experiments listed there still run)

Working title: *What Does Quantization Do to an LLM Agent? Capability Reallocation Measured Against the Model's Own Re-Roll Noise*

| RQ | Question | Evidence so far |
|---|---|---|
| RQ1 measurement | How large are quantization effects relative to the agent's own re-roll noise, and how do single-run comparisons mislead? | v0 false positive; first-divergence sign follows the luck of the single BF16 reference (q4 unlucky → perturbations look helpful; q8 lucky → harmful) |
| RQ2 what changes | Quantization reallocates capability: P(break \| always-ok under null) and P(fix \| always-fail) are far above the null rate. Model: p_i' = (1-λ) p_i + λ c, so Δ = λ (c − p̄). This predicts net damage grows with base success. | pilot below |
| RQ3 where | Which tasks and decisions break (writes, argument values, hallucinated IDs, premature stops, horizon length)? How do RTN/GPTQ/AWQ/official FP8/AWQ and bit width differ? | to do (existing data) |
| RQ4 prediction | Can cheap probes (E3 open-loop flips at tool/write decisions, perplexity) predict break/fix rates and λ, c? | E3 data exists |

Pilot (main session, 2026-09-29 00:30 PDT, pre-freeze data; script scratch `decomp.py`, to be moved into
analysis/insights/iter_3/):

| model | null LOO break / fix | RTN-W4 break / fix | AWQ-W4 break / fix | GPTQ-W4 d1 break / fix | gauss k=0.03 break / fix |
|---|---|---|---|---|---|
| q4 (18 ok, 38 fail, 28 coin) | 1.8% / 4.1% | 20% / 11% | 25% / 14% | 19% / 20% | 3% / 6% |
| q8 (11 ok, 39 fail, 35 coin) | 5.3% / 4.4% | 23% / 4% | 41% / 10% | 32% / 4% | 2% / 3% |

- q4 AWQ gives λ≈0.39, c≈0.36, and p̄≈0.35, so Δ≈0.
- Caveats: 2–5 draws per cell; "always" is estimated from 6 null draws (the LOO baseline accounts for part of the misclassification).

Experiments added for this framing (queued 2026-09-29 00:40, priority −2/−1):
- 3 more fresh-nonce draws (q3–q5) for RTN-W4/W3, AWQ-W4, GPTQ-W4-d1, GPTQ-W3 on q4/q8/q14. Tasks `a6k2_<m>_<cell>_qx`.
- Bit-width dose within quantization: RTN W5/W6 and GPTQ W5 (fresh nonces q1/q2). Gaussian noise becomes a control.
- Unchanged: X1 official FP8/AWQ, Llama-3.1-8B, telecom (gate 10-01), code loop (gate 10-01).

Instructions for the insight loop (iteration 3+): propose insights about what quantization does to agents (RQ2–RQ4),
using the null only as a reference. Reject insights whose subject is BF16 behaviour unless they are needed as method.
