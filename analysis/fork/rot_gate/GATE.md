# Rotation gate (W99r): QuaRot vs SpinQuant on q8 (Qwen3-8B), weight + activation axis

**TL;DR (2026-10-02 04:15 PDT, end of the 6-hour feasibility window at ~06:10).**
- **QuaRot: PASS on every check.** This covers QuaRot-W4A16-KV16, QuaRot-W4A4-KV16 and the W16 transform-path control.
- **SpinQuant: rotation learned (04:15–05:36), but the served gate was NOT EVALUATED in the window. This is not a failure.**
  - The learning converged.
  - Its WikiText-2 perplexity at W16A4 fell from 11.04 (the QuaRot point) to 8.76, below BF16's 9.73. This is domain adaptation through the quantizer, not fidelity (see "Rotation optimisation").
  - The implementation is done and passes its CPU tests: Cayley-SGD learning of R1/R2, and export through the same QuaRot builder.
  - The GPU rotation-learning task `rot_spin_learn_q8` (1 GPU) was queued at 00:24 at priority −25. It had not been claimed by 04:15, for three reasons:
    - Higher- and equal-priority work was ahead of it: same-precision, Mistral, KIVI and BFCL tasks at −29…−25.
    - The runners' TP-2 and multi-pair anti-starvation rule reserves the upper NVLink pairs for waiting 2- and 4-GPU tasks, so a 1-GPU task can only take a freed card 2 or 3.
    - node008 stopped claiming new tasks.
- Everything downstream is queued. It is gated by frozen, effect-blind criteria (`scripts/a6000/rot_gate_check.py`), and the phase-1 panel tasks are released automatically only for cells that pass (see the last section).

Sources: `validate_qr_q8.json`, `validate_qr_q8_ppl.json`, `ckpt_q8_qr{16,4}.quantization.json`, `unit_tests.json`, `verdict.json` (this directory). The open-loop / top-k outputs are under `openloop/`. Queue: `/data/ziyangs/cloq_work/queue/{done,todo}/rot_*.json`.

## Configurations (q8, all KV16 with the online Q/K rotation on = the panel's "kv16r" serving config)

| Cell | Checkpoint | Serving hook env |
|---|---|---|
| QuaRot-W4A16-KV16 (`quarot_w4`) | `cloq.quarot` random Hadamard R1 (seed 0) + per-head H_hd, GPTQ-W4 (WikiText-2 128×2048, seed 0) | `CLOQ_AQ_BITS=16 CLOQ_AQ_HAD=quarot`, KV16r |
| QuaRot-W4A4-KV16 (`quarot_w4a4`) | same checkpoint | `CLOQ_AQ_BITS=4 sym_quarot clip 0.9 HAD=quarot`, KV16r |
| SpinQuant-W4A4-KV16 (`spinquant_w4a4`) | `cloq.quarot --rotations R.pt` (learned R1, per-layer R2), the same GPTQ | identical to QuaRot-W4A4 |
| Transform-path controls (`quarot_w16`, `spinquant_w16`) | the same rotations, W16 | A16, KV16r |

**Controlled comparison.** SpinQuant and QuaRot use:
- the same calibration windows (one token set, sha `ec0a043b2c48…`, used both for learning the rotations and for GPTQ);
- the same weight grid: per-channel symmetric W4, MSE clip search, percdamp 0.01, true-sequential;
- the same activation grid: per-token symmetric INT4, clip 0.9, on the inputs of q/k/v, o, gate/up and down;
- the same online Hadamards: H_12 ⊗ H_1024 on the down_proj input, H_32 across heads on the o_proj input;
- the same KV16r.

The only difference is R1/R2. The SpinQuant learner starts at the QuaRot point (R1 = QuaRot's Q, R2 = H_hd/√hd), so at step 0 the SpinQuant model *is* the QuaRot model. CPU test 1 (below) confirms this to 0.0 max difference.

## Rotation optimisation (SpinQuant, `cloq/spinquant.py learn`)

- **Cayley SGD on the Stiefel manifold.** This reimplements SpinQuant's `train_utils/optimizer.py` SGDG with stiefel=True (Li, Todorovic & Fuxin 2020):
  - momentum 0;
  - step size α = min(lr, 1/‖W‖₁);
  - 5 Cayley fixed-point iterations;
  - a QR retraction with probability 1/101.
- **Schedule.** lr 1.5, cosine to 0 with no warmup, 100 steps × batch 8 × 2048 tokens. These are the official `10_optimize_rotation.sh` settings.
- **Objective.** Next-token cross-entropy of the network at W16A4KV16.
  - The activations are fake-quantized with a straight-through estimator (SpinQuant `STEQuantize`).
  - This follows the README rule: when GPTQ is used for the weights, optimise R1/R2 with only the activations quantized.
- **Parameters.** R1 (4096²) and 36 × R2 (128²), fp32. Weights are rotated on the fly in fp32; SpinQuant uses fp64, which runs at 1/64 rate on an A6000.
- **Model and memory.** Norm-fused bf16 frozen weights, per-layer gradient checkpointing, and lm_head + CE computed in chunks. R1 cancels exactly at the unquantized lm_head input.
- **Deviations from the official pipeline, each made for the controlled contrast:**
  - Calibration: the 128 GPTQ windows (6.25 epochs) instead of 800 fresh blocks.
  - Activation grid: symmetric with clip 0.9, matching the serving grid. The official script uses asymmetric, clip 1.0, and groups o_proj by head_dim.
  - The QuaRot across-head H_32 on the o_proj input is kept. SpinQuant has no online o_proj Hadamard.
  - R2 is initialised at H_hd instead of a random-sign Hadamard.

  The official default pipeline is reserved as the separate, optional `spinqoff_w4` row. It is not built.
- **Export.** `cloq.quarot --rotations` projects R onto O(n) with the fp64 polar factor and pins it by sha256. It then runs the identical transform and GPTQ code path.
- **Ran on GPU at 04:15–05:36 PDT (`spin_learn_q8.json`, R sha `1f1719b5…`).**
  - 100 steps at 43 s/step, 30.7 GB peak, 81 min including the four perplexity passes.
  - Epoch-mean training CE over the same 128 windows: 2.435 → 2.278 → 2.260 → 2.243 → 2.234 → 2.228.
  - Grad norm 25 → about 5. R1 orthogonality error ≤ 5.2e-4 in fp32; 42 QR retractions; polar-projected at export.
- **WikiText-2 test perplexity, on-the-fly learner path (bf16):**

  | | init (= QuaRot point) | learned |
  |---|---|---|
  | A16 | 9.737 | 9.644 |
  | A4 | 11.043 | **8.761** |

  BF16 is 9.726.
- **Caution: this is not a fidelity gain.** The learned W16**A4** network has lower WikiText perplexity than BF16 itself, and lower than the same rotation at A16.
  - The rotation acts on the function only through the activation quantizer (A4) and bf16 rounding (A16); at A16 the loss is otherwise rotation-invariant.
  - R1/R2 (about 17M parameters) therefore work as an adaptation of the instruction-tuned Qwen3-8B to WikiText. They were learned on WikiText-2 *train* and evaluated on WikiText-2 *test*, the same domain.
  - So WikiText perplexity cannot show whether SpinQuant is closer to BF16. The gate's direction criteria P1/P2 (ppl-based, frozen before this was seen) are kept as frozen but are **uninformative**.
  - The meaningful direction is the agent-domain fidelity: act flip and first-token KL vs BF16 on 400 BF16 agent decisions, measured for SpinQuant W16A4 and W4A4 in `rot_gate_sp_q8`. It is reported next to QuaRot's, not used as a gate.
  - The same hazard applies to the official SpinQuant recipe (WikiText-2 train for rotations, WikiText-2 test for reporting) whenever the model is not a WikiText-like base LM.

## Gate checks

Frozen criteria are in `scripts/a6000/rot_gate_check.py` (committed 3fd9522 before any SpinQuant GPU output existed). Verdicts are written to `verdict.json`.

### 1. Implementation correctness

CPU tests on a tiny Qwen3 with d 64, intermediate 96 = 12 × 8 so that the H_12 path is exercised (`tests/test_spinquant.py`, results in `unit_tests.json`). All pass:

| Test | Result |
|---|---|
| (1) Learned-rotation export at the QuaRot point equals the QuaRot transform | max abs diff 0.0 over 25 tensors |
| (2) Random orthogonal R1/R2 + online Hadamards equals the original (fp32) | max abs Δlogit 3.3e-7 |
| (3) On-the-fly learner path at A16 equals the original | Δ NLL 0.0; finite non-zero grads on R1/R2 |
| (4) Learner path vs exported serving path at A4 | rel Δ NLL 0.0 |
| (5) Cayley SGD keeps R orthogonal | error 8.6e-5 after 50 steps; loss 64.9 → 4.0 |

Transform-path control, q8, served under the batch-invariant vLLM path:

| q8, served | WikiText-2 test ppl (HF, 146 × 2048) | act flip vs BF16 decision type (400) | first-token KL mean (median) | tool-name KL | teacher-forced token flip (Bank E3) |
|---|---|---|---|---|---|
| BF16 (served, no hooks) | 9.726 | 0.000 | 0 (0) | 0 | 0.000 |
| QuaRot W16A16 (transform only) | 9.749 (+0.24%) | 0.005 | 0.0026 (1e-5) | 0.0013 | 0.0037 |
| SpinQuant W16A16 | pending | pending | pending | pending | pending |

- **QuaRot transform control: PASS.**
  - T1 ppl ≤ 1.01 × BF16, T2 act flip ≤ 0.02 and T3 KL ≤ 0.01 all hold.
  - The rotation alone is not bit-identical to BF16: the bf16-rounded rotated weights give a canary mismatch and 15.8% of decisions with any teacher-forced token flip. It is numerically neutral at the decision level.
  - This is the floor that every rotation cell carries. That is why the panel contrasts each W4 cell against its own W16 control.
- **Published direction (SpinQuant error ≤ QuaRot error at W4A4): pending.** The criteria are P1 ppl(sp W4A4) ≤ 11.290 and P2 ppl(sp W16A4) ≤ 11.072.

### 2. Deterministic serving (batch-invariant path)

- **QuaRot, every served config: PASS.**
  - W16A16, W4A16 and W4A4: batch == alone == prefix-hit on 8/8 agent prompts (token ids and logprobs).
  - W4A4 also passes unchunked == chunked on 8/8 and causal prefix identity on 3/3 long prompts.
  - Hook coverage: 144/144 linears quantized at A4, 72 Hadamard-only at A16, Q/K rotation hooked in 36/36 attention layers.
- **QQ no-op replay across two server processes** is checked by the panel's `gate_same`. These tasks are queued: `nmp_gate_same_q8_{quarot_w4,quarot_w16,quarot_w4a4}` and `nmp_gate_bank_q8_*` (BB no-op on 10 U2B states), pinned to node004/005/007. They had not started by 04:15.
- **SpinQuant: pending.** It uses the identical hook path; only the weights differ.

### 3. Throughput

| q8 | gen tok/s (16 concurrent agent prompts, ≤ 256 tokens, warm prefix cache) | server startup |
|---|---|---|
| BF16 | 61.5 | 80 s |
| QuaRot W4A16 | 64.9 | 70 s |
| QuaRot W4A4 | 91.4 | 75 s |

- **QuaRot: PASS (R1 ≥ 0.5 × BF16).**
- The rates are confounded by generation length: W4A4 emits different, often shorter or longer, completions. They show only that fake quantization does not slow serving materially.
- The build costs are 1276 s for QuaRot GPTQ-W4. The SpinQuant learner's wall time is still unmeasured; the estimate is about 1 h.

### 4. Local fidelity (measured, not assumed to predict outcomes)

| q8 (KV16r) | ppl | act flip | first-token flip | first-token KL mean / median | tool-name KL | tool-name switch | E3 token flip / decisions with any flip |
|---|---|---|---|---|---|---|---|
| QuaRot W16A4 | 11.072 | 0.125 | 0.205 | 0.660 / 0.019 | 0.234 | 0.181 | 0.053 / 0.540 |
| QuaRot W4A16 | 9.914 | 0.075 | 0.135 | 0.307 / 0.004 | 0.098 | 0.086 | 0.030 / 0.455 |
| QuaRot W4A4 | 11.290 | 0.198 | 0.275 | 1.155 / 0.062 | 0.336 | 0.214 | 0.063 / 0.623 |
| SpinQuant W16A4 / W4A4 | pending | | | | | | |

**Reading.** Adding A4 to QuaRot-W4 multiplies the local action disagreement about 2.6× (act flip 0.075 → 0.198) and the first-token KL about 3.8×. W16A4 alone already damages fidelity more than W4A16 alone. Whether this local damage shows up in the current action or in the subsequent execution (research question 1) is answered only by the panel's D_cc vs G/H/F, not by these numbers.

## Verdict per check

| Check | QuaRot | SpinQuant |
|---|---|---|
| Implementation correctness (invariance) | PASS | CPU PASS; learning ran (GPU); served invariance pending |
| Published direction (ppl ≤ QuaRot at W4A4) | n/a | learner path: 8.76 ≤ 11.04, **but uninformative** (WikiText train→test adaptation); agent-domain KL pending |
| Deterministic serving (hook level) | PASS | pending |
| QQ no-op (gate_same) / BB no-op (bank gate) | queued | queued after the rotation gate |
| Throughput | PASS | pending |
| Local fidelity | measured | pending |

**Window verdict.** QuaRot is gate-passed. **The SpinQuant gate cannot pass within the 6-hour window because of queue capacity, not because of a failure.** As instructed, I am stopping here and reporting.

## What stays queued (automatic, effect-blind)

1. `rot_spin_learn_q8` → `rot_gate_sp_q8`: SpinQuant W16A16, W16A4 and W4A4 through the same probes.
2. `rot_release_gates_sp_q8`: runs `rot_gate_check.py release-gates`. If the SpinQuant family passes T1–T4, D1–D3, P1, P2 and R1, it queues the `spinquant_w16` / `spinquant_w4a4` nmp gates and a panel-release task.
3. `rot_release_panel_qr_q8`, and later `rot_release_panel_sp_q8`: once a cell's `gate_same` verdict passes and its bank gate is done, they queue that cell's phase-1 panel (f01–f03 bank_u, score, BFCL nmp1 run and four fork_ext dev).

Nothing reads a panel outcome. To stop the line, delete `todo/rot_*` and `todo/nmp_*_quarot_*`, `todo/nmp_*_spinquant_*`.
