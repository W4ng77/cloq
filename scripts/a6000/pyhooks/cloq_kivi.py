"""KIVI KV-cache quantization (Liu et al., ICML 2024) for vLLM 0.29 serving, as fake quantization inside attention.
Imported by sitecustomize.py only when CLOQ_PYHOOKS=1 and CLOQ_KIVI_KBITS is set (docs/RESEARCH_LOG.md W99t).

KIVI, as in the official code (github.com/jy-yuan/KIVI models/llama_kivi.py, quant/new_pack.py), with group size G and
residual length R (paper: G=32, R=128):
  K  per-channel asymmetric INT-b, statistics over groups of G consecutive TOKENS. Keys stay full precision in a
     residual buffer and are flushed (quantized) R at a time, so after n tokens keys [0, R*floor(n/R)) are quantized.
  V  per-token asymmetric INT-b, statistics over groups of G consecutive CHANNELS. A sliding window of the last R
     values stays full precision, so after n tokens values [0, n-R) are quantized.
  Decode step at position t (the cache holds t tokens): q_t attends to K_i quantized iff i < R*floor(t/R) and to V_i
  quantized iff i < t-R; its own k_t, v_t are full precision (official decode branch: concat, attend, then flush).

The quantized/full split is a function of positions only. This module therefore keeps no side state: vLLM's paged cache
holds the full-precision BF16 K/V (unchanged write path), and the attention kernel reconstructs, for every query
position t, the exact view that KIVI's incremental decode would hold at step t:
  * K tiles are aligned to G tokens; a tile of keys i < R*floor(t/R) is a complete flushed group and is quantized on
    the fly from the 32 cached keys (per channel min/max over the tile);
  * V rows i < t-R are quantized on the fly per token (min/max over each G-channel group).
Each query's output depends only on (its position, the cached full-precision K/V of positions <= t), never on how the
history was chunked (prefill vs decode, chunked prefill, prefix-cache hits, batch composition, physical blocks). A
re-prefill of a frozen history reconstructs exactly the quantized/residual split of the original incremental decode,
and identical cache contents give identical quantized values (same deterministic per-tile arithmetic).
Deviation from the official code (documented in analysis/fork/kivi_gate/GATE.md): official prefill attends in full
precision inside the prompt (only the cache it leaves behind is quantized), so a re-prefilled history would differ from
the incremental one. Here every token, prompt or generated, gets the decode-step view, i.e. official KIVI run with a
1-token prefill followed by decode. This is what makes multi-turn serving and replay well defined.

Numerics: quantizer in fp32 as the official code runs on CUDA: scale (mx-mn)*fl32(1/L) (PyTorch divides by a CPU scalar
via its reciprocal), IEEE (x-mn)/s (div_rn), clamp, round-half-even, no FMA contraction (W99t-a2); a constant group (scale 0) dequantizes to its value (official code would divide by 0). Dequantized K/V are cast to
BF16 before the tensor-core dots (as the official kernels consume fp16 dequantized values). Scores in fp32, P in BF16.
One kernel configuration for all launches (fixed BLOCK_Q, TILE, warps, no autotune, no specialisation on runtime ints).

Patch point: vllm.v1.attention.backends.flash_attn.FlashAttentionImpl.forward (the FA2 backend these servers use). It
runs eagerly inside the unified_attention custom op (a splitting op, outside the Inductor graph) or inside the full
decode CUDA graphs; the kernel is graph-safe (all lengths read on device). The KV-cache write path is untouched.

env: CLOQ_KIVI_KBITS, CLOQ_KIVI_VBITS (16 = that side not quantized; both 16 = kernel-only null),
     CLOQ_KIVI_GROUP (32), CLOQ_KIVI_RESID (128).
"""
import os
import sys

KBITS = int(os.environ.get("CLOQ_KIVI_KBITS", "16"))
VBITS = int(os.environ.get("CLOQ_KIVI_VBITS", str(KBITS)))
GROUP = int(os.environ.get("CLOQ_KIVI_GROUP", "32"))
RESID = int(os.environ.get("CLOQ_KIVI_RESID", "128"))
assert RESID % GROUP == 0 and GROUP & (GROUP - 1) == 0, (GROUP, RESID)
TAG = f"kivi_k{KBITS}v{VBITS}_g{GROUP}_r{RESID}"
BLOCK_Q = 16  # query tokens per program (fixed for every launch)
NUM_WARPS = 4


def isolate_cache_root():
    root = os.environ.get("VLLM_CACHE_ROOT", os.path.expanduser("~/.cache/vllm"))
    if os.path.basename(root.rstrip("/")) != TAG:
        os.environ["VLLM_CACHE_ROOT"] = os.path.join(root, TAG)


def _build():
    from cloq_kivi_kernel import _qdq, kivi_attn_kernel
    return kivi_attn_kernel, _qdq


def kivi_attention(q, k_cache, v_cache, out, cu_q, seq_lens, block_table, scale, kbits=KBITS, vbits=VBITS,
                   group=GROUP, resid=RESID):
    """q/out [T, Hq, D] (row stride arbitrary, last dim contiguous); k_cache/v_cache [num_blocks, block_size, Hkv, D]
    (last dim contiguous); cu_q [S+1] int32; seq_lens [S] int32; block_table [S, max_blocks] int32."""
    import triton
    kern, _ = _build()
    T, Hq, D = q.shape
    Hkv = k_cache.shape[2]
    assert Hq % Hkv == 0 and q.stride(2) == 1 and out.stride(2) == 1 and k_cache.stride(3) == 1 and v_cache.stride(3) == 1
    assert k_cache.stride() == v_cache.stride(), (k_cache.stride(), v_cache.stride())
    assert D % group == 0 and resid % group == 0, (group, D, resid)
    S = cu_q.shape[0] - 1
    grid = (T // BLOCK_Q + S, Hkv)
    kern[grid](q, k_cache, v_cache, out, cu_q, seq_lens, block_table, float(scale), S, block_table.stride(0),
               q.stride(0), q.stride(1), out.stride(0), out.stride(1),
               k_cache.stride(0), k_cache.stride(1), k_cache.stride(2),
               D=D, GQ=Hq // Hkv, BLOCK_Q=BLOCK_Q, BS=k_cache.shape[1], TILE=group,
               KLEV=(2 ** kbits - 1) if kbits < 16 else 1, VLEV=(2 ** vbits - 1) if vbits < 16 else 1,
               QK=kbits < 16, QV=vbits < 16, R=resid, GROUPV=group, num_warps=NUM_WARPS, num_stages=1,
               enable_fp_fusion=False)
    return out


def install(mod):
    """Wrap FlashAttentionImpl.forward (decoder self-attention only)."""
    Impl = mod.FlashAttentionImpl
    if getattr(Impl, "_cloq_kivi", None):
        return
    orig = Impl.forward
    from vllm.v1.attention.backend import AttentionType  # noqa: F401  (import check)

    def forward(self, layer, query, key, value, kv_cache, attn_metadata, output, output_scale=None,
                output_block_scale=None):
        if attn_metadata is None or str(self.attn_type).lower().split(".")[-1] != "decoder":
            return orig(self, layer, query, key, value, kv_cache, attn_metadata, output, output_scale, output_block_scale)
        if (output_scale is not None or output_block_scale is not None or attn_metadata.use_cascade
                or self.alibi_slopes is not None or self.sinks is not None or self.logits_soft_cap
                or tuple(self.sliding_window) != (-1, -1) or getattr(self, "dcp_world_size", 1) > 1
                or str(self.kv_cache_dtype) != "auto" or attn_metadata.causal is not True):
            raise RuntimeError("cloq_kivi: unsupported attention configuration "
                               f"(cascade={attn_metadata.use_cascade}, window={self.sliding_window}, "
                               f"kv_dtype={self.kv_cache_dtype}, causal={attn_metadata.causal})")
        n = attn_metadata.num_actual_tokens
        key_cache, value_cache = kv_cache.transpose(1, 2).split(self.head_size, dim=-1)
        q = query[:n].view(n, self.num_heads, self.head_size)
        o = output[:n].view(n, self.num_heads, self.head_size)
        kivi_attention(q, key_cache, value_cache, o, attn_metadata.query_start_loc, attn_metadata.seq_lens,
                       attn_metadata.block_table, self.scale)
        return output

    Impl.forward = forward
    Impl._cloq_kivi = TAG
    orig_init = Impl.__init__
    count = [0]

    def __init__(self, *a, **k):
        orig_init(self, *a, **k)
        count[0] += 1
        print(f"[cloq_kivi] pid={os.getpid()} hooked attention #{count[0]} type={getattr(self, 'attn_type', None)} "
              f"heads={getattr(self, 'num_heads', None)}/{getattr(self, 'num_kv_heads', None)} "
              f"head_size={getattr(self, 'head_size', None)}", file=sys.stderr, flush=True)

    Impl.__init__ = __init__
    print(f"[cloq_kivi] pid={os.getpid()} wrapped {mod.__name__}.FlashAttentionImpl.forward: kbits={KBITS} "
          f"vbits={VBITS} group={GROUP} resid={RESID} tag={TAG} cache_root={os.environ.get('VLLM_CACHE_ROOT')}",
          file=sys.stderr, flush=True)
