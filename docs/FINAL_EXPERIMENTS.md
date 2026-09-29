**TL;DR** The complete experiment list for the ARR/NAACL submission (freeze 2026-10-05, deadline 10-12), organised as
main results / ablations / supporting analyses, each with its cells, runs, status and where it lands in the paper.
Framing: PLAN_iter4 (what quantization does to closed-loop agents; the BF16 perturbation null is the yardstick).
Status as of 2026-09-29 11:30 PDT. Queue: `/data/ziyangs/cloq_work/queue/`. Analyses: `analysis/insights/iter_{2,3}/`.

# Final experiment list

Common protocol: τ²-bench retail+airline (85 dev tasks), 32k context, greedy decoding, batch-invariant deterministic
serving with numerics canary, and the Qwen3-30B-A3B user simulator. Test cells use fresh nonces (q1–q5), never the null
nonces. Nulls are BF16 with nonces n1–n8 (nonce stratum, NULL_RULE.md).

## A. Main results (in the 8-page body)

| id | Result | Cells | Runs | Status | Paper |
|---|---|---|---|---|---|
| M1 | **Null yardstick**: how much a single run varies; single-run comparisons mislead (v0 false positive; the luck of the BF16 reference sets the sign) | BF16 canonical + nonce n1–n8, 6 models | 9 per model | q4/q8/q14 done; q30a3/q32/l8 n6–n8 queued | §2 motivation, Fig 1 |
| M2 | **Quantization reallocates capability**: breaks robustly-solved tasks and fixes robustly-failed ones at 3–10× the null rate. The attractor model Δ = λ(c − p̄) explains "unchanged success" and predicts net damage at higher base rate | RTN W8/W4/W3, GPTQ W4 (2 calib draws)/W3, AWQ W4 × q4/q8/q14/q30a3/q32/l8 | 3–5 per cell (`*_qx` fresh-nonce draws) | q4/q8/q14 mostly done; q30a3/q32 core running; l8 queued | §4 headline, Fig 2 (λ, c per cell), Tab 1 |
| M3 | **Equivalence verdicts**: which quantizers are ε-equivalent to their own model (exact permutation/conformal test in the nonce stratum, ε-inversion, Holm) vs single-run and Flat-Score-style verdicts | all cells in M2 + M4 + M5 | as M2 | test built (c01); final run on the frozen snapshot after the queue drains | §4, Tab 2 (verdict comparison, 40+ families) |
| M4 | **Size vs structure (E17)**: isotropic Gaussian with RTN-W4's norm vs Gaussian with RTN's per-group RMS (gshape) vs RTN magnitudes with random signs (rtnsign) vs RTN | q4/q8/q14 | 3 each | q8 gshape, q14 rtnsign done; 4 running | §5, Fig 3 |
| M5 | **Method families (breadth)**: NF4, MXFP4 (grid shape); QuaRot-rotated RTN/GPTQ W4 (error made isotropic by rotation) + rotated-BF16 control; official FP8 and AWQ checkpoints (X1); fake KV-cache INT4/INT3 (+Hadamard) | q4/q8/q14 (X1 on all 5 Qwen) | 3 each | agents implementing (W12, W13); X1 17/34 done | §5, Tab 3 |
| M6 | **Where damage comes from**: the task/decision type of breaks (write vs read, argument errors, hallucinated IDs, premature stop, context overflow W10) and the fragile-task set (noise-mapped, AUC 0.75–0.83 for predicting quantizer breaks, not transferable across models) | existing runs | — | analyses r03/r07 (iter 3), to be re-run frozen | §6, Fig 4 |

## B. Ablations / robustness (body if space, else appendix)

| id | What | Cells | Status |
|---|---|---|---|
| B1 | Bit-width dose within quantization: RTN W8/W6/W5/W4/W3, GPTQ W5/W4/W3 | q4/q8/q14 | W5/W6 queued |
| B2 | Gaussian dose ladder k = 0.001…3 as the size-only reference (canonical stratum descriptive; k=0.3, k=1 fresh-nonce draws E22 for testing) | q4/q8/q14 (+q30a3/q32 up to k=1) | mostly done; E22 queued |
| B3 | Calibration-draw sensitivity: GPTQ W4 d1 vs d2 | all Qwen | done / running |
| B4 | Fixed-checkpoint churn controls (churnctl k=0.03, churnctl_k1): is reallocation a property of the checkpoint or of the nonce | q4/q8/q14 | 5/6 done |
| B5 | Serving-numerics null: eager vs compiled; FP32 LM head (E8), which asks whether the floor comes from bf16 logit ties | q4 (+eager q8) | E8 3/6 done |
| B6 | Second model family: Llama-3.1-8B-Instruct core slice | l8 | queued (pinned to updated runners) |
| B7 | Third environment: τ² telecom (dual control) core slice | q8/q14 | det pair running; go/no-go 10-01 |
| B8 | Cross-node determinism pairs (fix validation) | q4, q30a3, X1 formats, KV quant | q4/q30a3 done (257/257, 303/303) |
| B9 | 8k vs 32k harness (4080 data) | q4 | done (E4) |

## C. Supporting analyses (no GPU)

| id | Analysis | Supports | Status |
|---|---|---|---|
| S1 | Integrity gate + frozen snapshot + number diff (one command) | everything | built (iter_2/integrity.py, run_all.sh) |
| S2 | Robust/coin task decomposition, λ and c estimation with CIs, null LOO baseline | M2 | pilot done; formal version in iter_3 r01 |
| S3 | Conformal/permutation equivalence test in the nonce stratum, ε-inversion, Holm across statistics, per-model e-values (no cross-model product) | M3 | c01 built; the collaborator's theory (stratified/weighted exchangeability) to be added |
| S4 | Null admission rule (pre-registered) and canonical-vs-nonce exchangeability test | M1, M3 | done (NULL_RULE.md, p=0.0099) |
| S5 | Open-loop E3 probe → λ (ρ 0.75–0.83; partial ρ given dose 0.86); what it cannot predict (which tasks, net Δ) | M2/M4 practitioner guidance | done provisional; E3 queue for q14/q30a3/q32/l8 prioritised |
| S6 | Per-decision divergence hazard and the tie floor (methods section only) | Methods | done |
| S7 | Power/MDE per family and pooled | M3 | done (6.5–13 pp per family at 85 tasks) |
| S8 | Failure-mode taxonomy of breaks (write/read, error types, context overflow) | M6 | to do on the frozen snapshot |
| S9 | Reference-luck analysis (first-divergence sign vs single BF16 draw) | M1 | pilot done |

## D. Dropped / deferred (with reason)

- LiveCodeBench code loop (branch `codeloop`): thin dynamic range (q4 0.20, q8 0.10), feedback changes only 5% of outcomes. Kept for the follow-up paper.
- Real FP8 KV cache: unsupported on SM86; replaced by fake KV quant (M5).
- W4A4 activation quantization: needs a vLLM forward change; listed under Limitations.
- Closed-loop gauss k=3 on q32/l8, extra Llama Gaussian levels and d2, telecom on q30a3/q32: moved to `queue/deferred/` (W11 cost).
- Mistral-Small-3.2 (multimodal checkpoint path), GLM-4-9B (no vLLM tool parser).

## E. Scheduling rule (to avoid simulator waiting)

- Simulator-free work (E3 open-loop, checkpoint builds) is interleaved at priority −1.5 among the simulator-heavy tasks, so that saturated simulators (node001/004/005 at ~298 W) do not leave agent GPUs idle.
- If simulator queues stay above ~10 waiting requests after the key cells finish, add a second simulator replica on node004/node005 at the next runner restart.
