# KIVI feasibility gate (W99t)

**TL;DR** `kivi_k2v2` (the primary KIVI cell) **passes** every gate criterion and its phase 1 (f01–f03 τ², scores, BFCL) is queued at −24. `kivi_k4v4` (secondary) passes everything except the original toy T2 mean-error ratio: 0.0547 against a 0.05 bound. That residual is BF16 serving precision; official KIVI run at BF16 scores 0.0496 against its own fp32 path. The cell passes the amended serving-precision T2 (0.0467), but it is **held, not queued**, pending a decision. The GPU toy failure was a real numerics mismatch, now fixed (W99t-a2): the kernel computed the scale with an IEEE division, while official KIVI on CUDA multiplies by the fp32 reciprocal. The rc=−9 kills were the worker's `stop_server` SIGKILLing the gate process, not OOM.

## 1. What is implemented

| Item | Value |
|---|---|
| Method | KIVI (Liu et al., ICML 2024), official code github.com/jy-yuan/KIVI @ 876b4d2 (`models/llama_kivi.py`, `quant/new_pack.py`) |
| Cells | `kivi_k4v4` (K4V4), `kivi_k2v2` (K2V2, stress). Weights and activations BF16 |
| Group size G / residual R | 32 / 128 (paper's main setting; official `config.group_size`, `config.residual_length`) |
| K | per-channel asymmetric INT-b, min/max over groups of G consecutive tokens; flushed R tokens at a time |
| V | per-token asymmetric INT-b, min/max over groups of G consecutive channels; sliding window of the last R values in full precision |
| Hook env | `CLOQ_PYHOOKS=1 CLOQ_KIVI_KBITS=b CLOQ_KIVI_VBITS=b CLOQ_KIVI_GROUP=32 CLOQ_KIVI_RESID=128` |
| Code | `scripts/a6000/pyhooks/cloq_kivi.py` (patch + launcher), `cloq_kivi_kernel.py` (Triton kernel), `sitecustomize.py` (install, compile-cache namespace `kivi_k{b}v{b}_g32_r128`); reference `cloq/kivi_ref.py`; gate `scripts/a6000/kivi_gate.py`; role support `scripts/a6000/fork_serve.py` (`kivi`, bits, hook coverage) |

### 1.1 Statefulness and replay determinism: how it is solved

KIVI's cache state is a quantized part plus a full-precision residual. Which tokens are in which part depends only on
positions. In the official decode loop, after n tokens:
- keys `[0, R·⌊n/R⌋)` are quantized (in G-token groups aligned to absolute positions, since R is a multiple of G);
- values `[0, n−R)` are quantized (per token).

The decode step at position t attends with exactly that state plus its own full-precision k_t, v_t. The gate checks this
position rule against the official class step by step (T2 `official_state_split_matches_position_rule`).

So the stateful adapter holds **no side state**. vLLM's paged cache keeps the full-precision BF16 K/V, written by the
unchanged write path. The attention kernel rebuilds, for every query position t, the view that KIVI's incremental decode
holds at step t:
- **K.** Key tiles are aligned to G = 32 tokens. A tile entirely below R·⌊t/R⌋ is a flushed group, so the kernel
  quantizes it on the fly from its 32 cached keys (per-channel min/max over the tile).
- **V.** Rows i < t−R are quantized on the fly per token.

Consequences:
- A query's output is a function of (t, cached full-precision K/V at positions ≤ t) only. That holds for every way of
  reaching it: decode or prefill, any chunked-prefill boundary, prefix-cache hit or miss, any batch composition and any
  physical block layout.
- The persistent "state" is the token history itself, so it survives prefix caching, preemption/recompute and
  cross-server re-prefill. Two sequences sharing a cached block can never disagree on a group's quantization, because
  the group's statistics are recomputed from the group's own cached tokens.
- A re-prefill of a frozen history reconstructs exactly the original incremental decode's quantized/residual split. The
  same cached values give bit-identical quantized values: the same deterministic per-tile arithmetic, a fixed kernel
  configuration, no autotune, no runtime-int specialisation and no FMA contraction.

**One documented deviation from the official code.** Official KIVI's prefill attends in full precision inside the
prompt; only the cache it leaves behind is quantized. Under that rule a re-prefilled history would not equal the
incremental one, so replay could never be exact. Here every token, prompt or generated, gets the decode-step view. This
equals official KIVI run with a 1-token prefill followed by decode. Official decode steps are reproduced exactly
(T2 `official_prefill300_decode_rows_vs_kernel`); only official prefill rows differ, by construction.

Numerics:
- The quantizer runs in fp32, as `(x−mn)/s`, then clamp, then round-half-even, then `q·s+mn`, with IEEE division. It
  equals the official quantize/pack/unpack bit for bit on fp32 data (T1).
- A constant group (s = 0) dequantizes to its value; the official code divides by zero there.
- Dequantized K/V are cast to BF16 before the tensor-core dots.
- The memory saving is not realised: this is fake quantization (numerics only), like the KV8/KV4 hook.

## 2. GPU failures and fixes (2026-10-02)

**rc=−9 (kivi_gate_q8, node008, twice).** This was not OOM.
- The task log shows the toy phase, then bf16 det/chain/tput, then the kill.
- The kill came at the first `stop_server`. `worker.stop_server` SIGKILLs every pid on the task's GPUs. The gate process held a CUDA context from the toy phase, so it was one of those pids.
- Fix: run the toy and server phases as separate tasks. `kivi_gate_q8_r2` runs `--phases server`, which never touches CUDA, and it completed every config.

**Toy T1/T2 false on GPU (gate_q8.json, gate_q8_toy2.json). The cause was the scale, not BF16 noise.**
- The official `(mx - mn) / (2 ** bit - 1)` runs on CUDA with a Python-int divisor. PyTorch computes a division by a CPU scalar as `a * (1/b)` in fp32, and `kivi_ref.qdq_ref` did the same on GPU. The kernel used IEEE `div_rn`.
- The two scales differ by 1 ulp on 32–63% of groups (T1: 127377/262144 values bit-equal at int4, 189296/262144 at int2).
- BF16 data have many exact ties in `(x-mn)/s`, so the 1-ulp scale difference flips codes: 531 of 655 360 K codes at int4 and 209 at int2.
- A CPU emulation (IEEE vs reciprocal scale, same seed and shapes) reproduces the GPU kernel-vs-view max errors exactly: 0.0478 vs 0.04777 (k4v4) and 0.1915 vs 0.19167 (k2v2).
- Fix (f585ae3, W99t-a2): the kernel scale is `(mx-mn) * fl32(1/L)`, and `qdq_ref` uses the same on every device.
- Diagnostic `kivi_diag_q8` (diag_q8.json, fixed kernel): every quantized config now has exactly the null kernel's error vs the view reference: max 0.0093 BF16 and 0.0011 FP16, the same for K-only, V-only and both.
- Consequence for the CPU toy: `toy_cpu_interp_fp16.json` was produced with the IEEE scale, against the CPU official twin, which divides exactly. That file stays as the record of the pre-fix kernel.

## 3. Toy gate on GPU, fixed kernel (`gate_q8_toy3.json`, node006, BF16, Hq 32 / Hkv 8 / D 128)

| Check | k4v4 | k2v2 | Bound |
|---|---|---|---|
| T1 kernel = official quantize/pack/unpack, bit for bit (int4 / int2) | 262144/262144 K and V | 262144/262144 K and V | all |
| T2 official state split = position rule | true | true | true |
| T2 kernel vs official (fp32) decode, max abs | 0.0093 | 0.0093 | < 0.25 × quant effect (0.0337 / 0.159) |
| T2 kernel vs official, mean / quant-effect mean (**original**) | **0.0547** | 0.0103 | < 0.05 |
| T2 kernel vs official at serving precision, mean ratio (amended) | 0.0467 | 0.0092 | < 0.05 |
| official at serving precision vs official fp32, mean ratio (for scale) | 0.0496 | 0.0094 | — |
| T2 official prefill-300, decode rows vs kernel, max | 0.0045 | 0.0038 | < 0.25 × effect |
| k16v16 null kernel vs exact, max | 0.0093 | | < 0.02 |
| T3 invariance (decode-by-token, random chunks batched, prefill-half + batched decode), 9 seqs | 9/9 bitwise, all 3 | 9/9 bitwise, all 3 | all |

- `verdict`: T1 true, T2 **false** (only k4v4's mean ratio), T3 true.
- `verdict_amended`: T1 true, T2_servingprec true.
- Per cell, `kivi_k2v2` meets every original toy criterion.
- k4v4's original-T2 excess is the kernel's BF16 output and P rounding. The kernel's error against fp32 official (2.76e-4 mean) is the same size as official KIVI's own error at BF16 against its fp32 path (2.50e-4). The k16v16 null kernel's error vs exact is 1.8e-4 (diag).

## 4. Server gate on q8 (`gate_q8.json` server section, task kivi_gate_q8_r2, fixed kernel)

| Config | hooked attn | det batch_eq_alone / prefixhit_eq_alone | chain cold_reprefill / reverse_order (n_turns) | batch-16 tok/s | single-stream tok/s | cold prefill 17k (s) |
|---|---|---|---|---|---|---|
| bf16 (FA2) | 0 | 8/8, 8/8 | 32/32, 32/32 (32) | 117.0 | 12.9 | 3.6 |
| k16v16 (kernel null) | 36 | 8/8, 8/8 | 32/32, 32/32 (32) | 44.2 | 4.9 | 11.1 |
| k4v4 | 36 | 8/8, 8/8 | 32/32, 32/32 (32) | 13.0 | 1.8 | 41.1 |
| k2v2 | 36 | 8/8, 8/8 | 32/32, 32/32 (32) | 13.0 | 1.8 | 41.1 |

**Fidelity vs the BF16 server.** The data are 200 recorded closed-loop decisions of `a6k2_q8_bf16`; the BF16 server reproduces 200/200.

| Config | exact completion | first token | action | tool call (n=128) | first-token KL mean / median / q90 |
|---|---|---|---|---|---|
| k16v16 | 0.910 | 0.995 | 0.910 | 0.969 | 0.0010 / 1.3e-6 / 0.0019 |
| k4v4 | 0.735 | 0.970 | 0.735 | 0.852 | 0.0149 / 2.8e-5 / 0.031 |
| k2v2 | 0.495 | 0.900 | 0.500 | 0.648 | 0.398 / 0.0031 / 0.856 |

Notes:
- The kernel path itself (k16v16) changes 9% of completions vs FA2, because it uses a different but deterministic accumulation order. P3 (KIVI − KV8) therefore carries a kernel-path component.
- k16v16 is the natural transform-path control. It is not a registered cell; report it as context.
- Throughput is about 9× below FA2 at K/V quantization, since the kernel re-quantizes every flushed tile per query block. Panel tasks of the KIVI cells will be correspondingly slow.

## 5. Protocol gates (§2.4; `analysis/fork/newmethod/gate/q8_<cell>/`)

| Cell | gate_same (6 states, 0 errors, idcheck Q 8/8, B 8/8) | bank_u (10/10 ok, 0 missing, 0 errors) |
|---|---|---|
| kivi_k2v2 | pass | pass (gate_pass true) |
| kivi_k4v4 | pass | pass (gate_pass true) |

**Disclosure.** Both protocol gates ran on the pre-fix kernel (hook_version b82dfa5a). The fix changes one fp32 constant in the scale. It does not touch any path that the gates' determinism properties depend on: position rule, tiling, launch configuration, or the absence of side state. The server-phase det and replay checks above ran on the fixed kernel. The gates were not re-run.

## Verdict

- **kivi_k2v2: PASS.** It meets the toy verdict criteria per cell (original and amended), chain 32/32 and 32/32, det 8/8 and 8/8, and gate_same and bank pass. Phase 1 is queued (`make_tasks_kivi.py --cells kivi_k2v2 --write`, 11 tasks, −24).
- **kivi_k4v4: HELD.** It fails the original toy T2 on mean ratio only (0.0547 > 0.05, at the BF16 floor) and passes everything else, including the amended T2. Queue it with `make_tasks_kivi.py --cells kivi_k4v4 --write` if the amended serving-precision criterion is accepted for the secondary cell.

