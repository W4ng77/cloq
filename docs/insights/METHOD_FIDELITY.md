# METHOD_FIDELITY — activation fake quantization: A8, SmoothQuant W8A8, QuaRot W4A4KV4

**TL;DR** All three steps pass acceptance on q4 (Qwen3-4B-Instruct-2507), 2026-09-30.
- **A8** (descriptive: per-token symmetric absmax INT8, dynamic). Hook at A16 reproduces the BF16 canary `c7343b60da095480`
  exactly. Coverage is 144/144 fused modules (36 each of QKVParallelLinear, MergedColumnParallelLinear, and RowParallelLinear o/down),
  with 0 excluded LinearBase. Batch, prefix-cache, chunked-vs-unchunked and causality checks are all identical.
  Open-loop mean |Δlogprob| is 0.041 at A8 and 6.72 at A4, with token flip 2.4% and 94%.
- **SmoothQuant W8A8** (named). α = 0.85 was picked by Pile-val perplexity (9.56 BF16 → 9.65; no smoothing 9.90).
  Mean |Δlogprob| is 0.030 with flip 2.0%; RTN-W8A8 without smoothing gives 0.043 and 2.5%.
- **QuaRot W4A4KV4** (named: GPTQ weights, clip 0.9 / 0.95). Mean |Δlogprob| is 0.43 with flip 11.6%; plain A4 with no rotation gives 5.96 and 89%.
  The rotation alone (W16A16) gives 0.0065 and 0.55%, i.e. the numerics floor. Monotone ladder: A16 0.0065 < A8 0.018 < A4 0.28, and W4A16 0.13 < W4A4KV4 0.43.
- Unit tests against the official QuaRot/SmoothQuant code are exact (quantizers, GPTQ solver, smoothing, Hadamards).
- **Deviations:** no embedding mean subtraction (a QuaRot code quirk for RMSNorm models); H_76 (Paley II) for Qwen3-4B's 9728; α chosen by us;
  fp32 QDQ/Hadamard, with dequantized weights stored in bf16.
Evidence: `analysis/ahook/`.

Engineering line 1 of `docs/EXECUTION_PLAN_20260930.md` (P3). Fake quantization = quantize-dequantize (QDQ) in fp32,
cast back to BF16, inside otherwise unchanged BF16 vLLM compute. References checked against:
SmoothQuant https://proceedings.mlr.press/v202/xiao23c.html, code github.com/mit-han-lab/smoothquant @ `c61476d`;
QuaRot https://arxiv.org/abs/2404.00456 (v2, §4–5, App. A.2), code github.com/spcl/QuaRot @ `5008669` (`fake_quant/`).

## 1 Implementation map

| piece | file | patch point / role |
|---|---|---|
| QDQ math, Hadamards, weight quantizers | `cloq/aq.py` | shared by hooks, builders, tests; row-local only |
| activation hook | `scripts/a6000/pyhooks/cloq_aq.py` | `LinearBase.__init__` (per-module decision + coverage line), `ColumnParallelLinear.forward` (→ `QKVParallelLinear` qkv_proj, `MergedColumnParallelLinear` gate_up_proj), `RowParallelLinear.forward` (o_proj, down_proj) |
| KV hook (QuaRot mode added) | `scripts/a6000/pyhooks/cloq_kvq.py` | `Attention.forward`; `CLOQ_KVQ_ROT=qk`, `CLOQ_KVQ_FMT=quarot`, `CLOQ_KVQ_KCLIP/VCLIP`; defaults unchanged (W13 tag and numerics) |
| hook loader, cache namespaces | `scripts/a6000/pyhooks/sitecustomize.py` | patches `vllm.model_executor.layers.linear` when `CLOQ_AQ_BITS` or `CLOQ_AQ_HAD` set; `VLLM_CACHE_ROOT/<kv tag>__<aq tag>` |
| SmoothQuant builder | `cloq/smoothquant.py` | act scales, smoothing, W8, alpha selection |
| QuaRot builder | `cloq/quarot.py` | fused norms, residual random Hadamard, V/O and down_proj Hadamards, W4 RTN or GPTQ |
| unit tests (step 1, 6) | `tests/test_aq.py`, refs `tests/ref_quant_official.py` | CPU, vs official code |
| GPU validation (steps 2–6) | `scripts/a6000/aq_validate.py` | per config: coverage, canary, det, chunk, causal, open-loop |
| worker / tasks | `scripts/a6000/worker.py` (kinds `smoothquant`, `quarot`; `serve_env` AQ record, `requires_serve_env` check), `scripts/a6000/make_tasks.py --only aq` | |

Kept high precision everywhere: embeddings, lm_head (`ParallelLMHead` is not a `LinearBase`, never wrapped), all
RMSNorms (incl. q_norm/k_norm), RoPE, softmax / attention (queries BF16), residual stream, SiLU·mul. MoE models are
refused (FusedMoE experts are not `LinearBase`; the hook raises at construction). TP > 1 is refused with online
Hadamards; without them a per-token scale under TP would be per rank (recorded as `tp=` on each coverage line).

## 2 Configuration records (what every run records)

`runs/<id>/quantization.json` gets `activations` {bits, fmt, clip, group, only, had, granularity "per token, dynamic",
scale_dtype fp32, hook} and, with KVQ, `kv_cache` {bits, rot_mode, fmt, kclip, vclip, which, granularity}; the
checkpoint builders record weight bits / granularity / symmetry / clipping / rounding / storage, calibration source,
token budget, token-id hash and seed, and the online half they require (`requires_serve_env`, checked by the worker).
Backend facts are taken from the validation server logs (below): vLLM 0.29.0, FLASH_ATTN (FlashAttention 2),
TP 1, prefix caching on, chunked prefill on (2048-token chunks), CUDA graphs FULL_AND_PIECEWISE, batch-invariant mode.

## 3 A8 (descriptive name: "A8 per-token symmetric absmax INT8, dynamic")

Inputs of qkv_proj, o_proj, gate_up_proj, down_proj: per token, symmetric, scale = max|x| / 127 (fp32; zero row →
scale 1), round half-even, clamp [−128, 127] (QuaRot `ActQuantizer`, clip 1.0). Weights BF16. Not a named method.

## 4 SmoothQuant W8A8 (named; checked against the reference)

| item | reference (Llama path) | here | status |
|---|---|---|---|
| act scales | `get_act_scales`: max\|x\| per input channel of each nn.Linear, 512 Pile-val docs (`dataset.shuffle(seed=42)`), truncation 512 | same docs (numpy `default_rng(42).permutation` = `datasets` shuffle, read from `pile-val-backup/val.jsonl.zst`, sha256 recorded), same truncation | same |
| smoothing | `smooth_ln_fcs_llama_like`: input_layernorm→q,k,v; post_attention_layernorm→gate,up; s = act^α / max_W^(1−α), clamp 1e-5 | same formula (unit test exact); o_proj, down_proj unsmoothed as in the reference | same (fp32 compute, bf16 storage; reference fp16) |
| α | per model (README 0.85 for Llama-2/3, 0.8 Mistral); none for Qwen3 | grid {0.5,…,0.9} by W8A8 ppl on 64 held-out Pile-val docs (positions 512–575 of the same order) | documented choice |
| W8 | `quantize_weight_per_channel_absmax` | same (unit test exact) | stored as dequantized bf16 (≤ 2⁻⁹ relative) |
| A8 | `quantize_activation_per_token_absmax`: clamp(max\|x\|, 1e-5)/127, round | `CLOQ_AQ_FMT=sym_sq`, identical formula (unit test exact incl. the 1e-5 floor) | same |
| BMM inputs | `quantize_bmm_input=False` for Llama | q/k/v outputs and attention BF16 | same |

## 5 QuaRot W4A4KV4 (named; checked against the reference)

| item | reference | here | status |
|---|---|---|---|
| norm fusion | `fuse_layer_norms` | same folding; reference additionally subtracts the embedding row mean (a LayerNorm step; it changes an RMSNorm model) — not done | deviation (keeps exact invariance) |
| residual rotation | `random_hadamard_matrix(d)` (random signs · Hadamard), seed 0 | `cloq.rotate.random_hadamard` diag(s) H_d/√d, seed 0 (Paley-20 ⊗ Sylvester for 2560) | equivalent family, different draw |
| V/O | `rotate_ov_proj`: v_proj output per-head H_hd; o_proj input full H | same (exact Hadamard, Sylvester); online H_nh across heads on o_proj input (`online_partial_had`) | same |
| down_proj | `rotate_mlp_output` + `online_full_had` with H_K ⊗ H_{n/K} (`matmul_hadU_cuda` layout) | same layout; K=12 for 12288 = QuaRot's `get_had12` verbatim; K=76 for 9728 (not in QuaRot's table) = Paley II, q=37 | same / extension |
| Q/K | `QKRotationWrapper`: H_hd on q and k after RoPE | `cloq_kvq` `CLOQ_KVQ_ROT=qk` | same |
| A4 | per-token symmetric, clip 0.9 (paper §5; `ActQuantizer`) | `CLOQ_AQ_BITS=4 CLOQ_AQ_CLIP=0.9`, exact vs `ActQuantizer` | same |
| KV4 | asymmetric, group 128, clip 0.95 (paper §5); K per (token, head) zero-including range, V `find_params_per_token_groupwise` | `CLOQ_KVQ_FMT=quarot` exact vs `ActQuantizer` (constant non-zero V group: reference divides by 0; ours falls back to the zero-including range) | same (+ degenerate-case guard) |
| W4 | GPTQ, per-channel symmetric, w_clip MSE grid (norm 2.4, grid 100, maxshrink 0.8), WikiText-2 train 128×2048, `random.seed(0)`, percdamp 0.01, no act-order, sequential k,v,q→o→up,gate→down, online Hadamards in the calibration forward | `cloq.quarot --wmethod gptq`: solver exact vs `GPTQ.fasterquant` (unit test); same data rule (WikiText-2 raw train arrow, sha256 recorded) | same (Qwen tokenizer) |
| Hadamard precision | fp16 online (fp32 with `--fp32_had`) | fp32 online, one bf16 rounding | = `--fp32_had` |
| lm_head | not quantized | BF16 | same |

## 6 Acceptance results (q4, Qwen3-4B-Instruct-2507)

Server provenance (all configs): vLLM 0.29.0, FLASH_ATTN (FlashAttention 2), TP 1, prefix caching on, chunked prefill
on, CUDA graphs FULL_AND_PIECEWISE, `VLLM_BATCH_INVARIANT=1`, `TORCHINDUCTOR_DETERMINISTIC=1`. Open loop: 150 BF16
reference decisions of `a6k2_q4_bf16` (12,288 teacher-forced tokens; ablations 30 decisions), `scripts/a6000/openloop_d.py`.
Coverage "q/h/p" = quantized / Hadamard-only / pass-through modules in the engine process (expected 144 = 36 layers x 4
kinds; 0 excluded LinearBase in every config; KV = decoder attention layers hooked, expected 36).

| config | ckpt | cov q/h/p, KV | canary | det batch / prefix-hit | unchunked = chunked | causal (3 x 1500 pos) | mean \|Δlp\| | flip | decisions with a flip |
|---|---|---|---|---|---|---|---|---|---|
| b16 (A16 hook on) | BF16 | 0/0/144 | **= BF16** | 8/8, 8/8 | 8/8 | 4500/4500 | 0.00001 | 0.00% | 0% |
| a8 | BF16 | 144/0/0 | ≠ | 8/8, 8/8 | 8/8 | 4500/4500 | 0.041 | 2.38% | 44% |
| a4 | BF16 | 144/0/0 | ≠ | 8/8, 8/8 | – | – | 6.72 | 93.6% | 100% |
| a4 only qkv / o / gate_up / down | BF16 | 36/0/108 each | all ≠ (4 distinct) | – | – | – | 2.84 / 0.21 / 2.73 / 0.98 | 53 / 6.8 / 48 / 22% | – |
| sq_w8a16 | SmoothQuant | 0/0/144 | ≠ | – | – | – | 0.014 | 1.07% | 33% |
| **sq_w8a8** | SmoothQuant | 144/0/0 | ≠ | 8/8, 8/8 | 8/8 | 4500/4500 | **0.030** | **1.96%** | 41% |
| rtn_w8a8_nosmooth | W8, no smoothing | 144/0/0 | ≠ | – | – | – | 0.043 | 2.50% | 44% |
| qr_w16a16 | QuaRot W16 | 0/72/72 | ≠ (rotated weights) | 8/8, 8/8 | – | – | 0.0065 | 0.55% | 27% |
| qr_w16a8 (clip 0.9) | QuaRot W16 | 144/0/0 | ≠ | – | – | – | 0.018 | 1.18% | 33% |
| qr_w16a4 | QuaRot W16 | 144/0/0 | ≠ | – | – | – | 0.28 | 8.68% | 68% |
| qr_w16a16kv4 | QuaRot W16 | 0/72/72, 36 | ≠ | – | – | – | 0.093 | 4.13% | 57% |
| qr_w4a16 | QuaRot GPTQ W4 | 0/72/72 | ≠ | – | – | – | 0.13 | 5.09% | 57% |
| **qr_w4a4kv4** | QuaRot GPTQ W4 | 144/0/0, 36 | ≠ | 8/8, 8/8 | 8/8 | 4500/4500 | **0.43** | **11.6%** | 85% |
| noqr_w16a4 (clip 0.9, no rotation) | BF16 | 144/0/0 | ≠ | – | – | – | 5.96 | 88.7% | 100% |

Step-by-step verdicts:
1. **QDQ numerics vs reference** — pass. `tests/test_aq.py`, `analysis/ahook/unit_tests.json`:
   - exact equality with QuaRot `ActQuantizer` (sym and asym, per token and group-wise, clip 1.0/0.9/0.95; 3/4/8 bits);
   - exact equality with SmoothQuant `quantize_activation_per_token_absmax`, including zero rows, rows below the 1e-5 scale floor and exact rounding ties;
   - group tails (300 = 2x128 + 44) equal a per-chunk loop;
   - weight quantizers exact (QuaRot `WeightQuantizer` with the w_clip MSE search; SmoothQuant W8 per channel);
   - QuaRot GPTQ solver exact vs `GPTQ.fasterquant`; SmoothQuant smoothing scales exact;
   - Hadamards: orthogonal to 1e-12 and equal to the explicit Kronecker matrix for 2560/4096/9728/12288; equal to QuaRot's `matmul_hadU` up to its float32 sqrt normalization (≤ 1e-6 relative);
   - a tiny Qwen3 with intermediate 152 = 76x2 is invariant under `cloq.quarot` plus the online Hadamards (max |Δlogprob| 4e-7 fp32; 0.90 without them).
2. **A16 hook = BF16 canary** — pass: `c7343b60da095480` with 144 wrapped modules passing through (also with unchunked prefill).
3. **Coverage** — pass: 144/144 (36 QKVParallelLinear qkv_proj, 36 MergedColumnParallelLinear gate_up_proj, 36
   RowParallelLinear o_proj, 36 RowParallelLinear down_proj) in every config. Each fused path is live in the
   compiled graph: quantizing only one kind at A4 changes the canary and the logprobs for each of the four kinds.
   KV: 36/36 decoder attention layers.
4. **Cache / chunking / batch invariance** — pass for b16, a8, sq_w8a8 and qr_w4a4kv4 (the configs with the most ops):
   - 8 real agent prompts give identical ids and logprobs alone, in a batch of 16, and after a prefix-cache hit;
   - an unchunked server (`--max-num-batched-tokens 34816`) gives identical results to the default 2048-token chunks;
   - compile-cache namespaces are separate per config (`<VLLM_CACHE_ROOT>/<tag>`). This separation is needed: vLLM's own
     compile hash is identical for A8 and A4 (`f854e0a454`) and for the four ablations (`4b30f92603`).
5. **Teacher-forced shift is monotone in precision** — pass:
   - A16 < A8 < A4 both without rotation (0.00001 < 0.041 < 6.72) and with QuaRot (0.0065 < 0.018 < 0.28);
   - W16A16 < W4A16 < W4A4KV4 (0.0065 < 0.13 < 0.43);
   - SmoothQuant W8A16 < W8A8 (0.014 < 0.030), and smoothing beats no smoothing (0.030 < 0.043).
6. **No future tokens in scales** — pass:
   - by construction (per-row statistics only);
   - unit test: prefix, future-token change and permutation invariance for every format and the Hadamards;
   - end to end: prompt logprobs of a 1500-token prefix are identical alone and inside a 2600-token prompt (2048 + 552 chunks), 3/3 prompts, 4500/4500 positions, for b16, a8, sq_w8a8 and qr_w4a4kv4.

Builds (`analysis/ahook/ckpt_q4_*.quantization.json`):
- **SmoothQuant**, 126 s: 512 Pile-val docs, 183,583 tokens; α grid ppl on 64 held-out docs (22,824 tokens):
  0.5 9.77, 0.6 9.71, 0.7 9.66, 0.75 9.69, 0.8 9.67, **0.85 9.65**, 0.9 9.66; BF16 9.56; no smoothing 9.90.
- **QuaRot W16 HF invariance check** (4 x 512 WikiText windows): fp32 top-1 agreement 99.5% (mean |Δlp| 0.004);
  bf16 98.3% (0.022). This is the bf16 numerics floor (W12: original bf16 vs fp32 agrees 98.7%, mean 0.013).
- **QuaRot GPTQ W4**, ~22 min on one A6000: 128 x 2048 WikiText-2 train tokens, seed 0; mean relative weight error 0.018
  (per-channel symmetric W4 with MSE clip).

Validation history: the first QuaRot run failed at server start. Building H_76 under vLLM's CUDA default-device context hit the
batch-invariant matmul override (float64 KeyError). Fix: build and check the matrices on the CPU without a GEMM. The
K-block mix was then changed from an unrolled 76x76 sum (14-minute compile) to a broadcast-multiply-reduce (100 s startup).
All QuaRot numbers above come from the rerun with the final code. Superseded partial rerun:
`analysis/ahook/superseded/validate_quarot_w16_q4.json`.

Not covered / unsupported: MoE models (q30a3; refused); TP > 1 with online Hadamards (refused); q8 validation not run
(H_12 path unit-tested only); static (calibrated) activation scales (SmoothQuant O2/O3) not implemented, only the
dynamic per-token variant used by the reference fake-quant code.

## 7 Evidence

- Unit tests: `analysis/ahook/unit_tests.json` (`python tests/test_aq.py`).
- GPU validation: `analysis/ahook/validate_{a8,sq,quarot}_q4.json`, open-loop `analysis/ahook/openloop_q4_*.json`,
  checkpoint records `analysis/ahook/ckpt_q4_*.quantization.json`; server/build logs `/data/ziyangs/cloq_work/logs/ahook/`.
- Queue tasks: `/data/ziyangs/cloq_work/queue/{done,failed}/ahook_validate_*_q4.json`.
