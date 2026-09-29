"""Fake KV-cache quantization for vLLM 0.29 serving (docs/RESEARCH_LOG.md W13). Imported by sitecustomize.py only when
CLOQ_PYHOOKS=1 and CLOQ_KVQ_BITS is set; A6000s cannot run a real FP8/INT KV cache under our frozen numerics (W7).

Patch point: `vllm.model_executor.layers.attention.attention.Attention.forward`, wrapped at import time (before model
construction and torch.compile). Qwen3Attention / Qwen3MoeAttention / LlamaAttention call `self.attn(q, k, v)` after
k_norm and RoPE, so the wrapper sees exactly the K/V that unified_kv_cache_update writes to the paged cache (and that the
attention kernel reads back). Dynamo inlines the wrapper into the model graph, so the quantize-dequantize ops land in
the Inductor-compiled piecewise subgraph in front of the attention custom op and are replayed inside the CUDA graphs.

Per (token, kv-head) row of head_dim values x (fp32):
  optional rotation  x <- H x, H = normalized Sylvester Hadamard (fast Walsh-Hadamard butterflies, exact fp32 adds)
  asymmetric INT-b   s = (max x - min x) / (2^b - 1);  x_hat = clamp(round((x - min x) / s), 0, 2^b - 1) * s + min x
Only per-row ops (no statistic across tokens, heads or batch), so the stored K/V of a token does not depend on the batch,
on chunked-prefill boundaries or on whether its block came from the prefix cache.
Rotation (CLOQ_KVQ_ROT=1, QuaRot-KV): q and k are both rotated (H orthogonal, so q.k is unchanged before quantization)
and the cache holds the rotated, quantized K. V is quantized in the rotated basis and rotated back (H = H^-1), which
equals QuaRot's rotating V via W_v and undoing it in W_o. The attention output is therefore in the original basis.

env: CLOQ_KVQ_BITS (16 = off: the wrapper is installed but passes through; 8/4/3/...), CLOQ_KVQ_ROT (0/1),
     CLOQ_KVQ_WHICH ("kv" default, or "k" / "v").
The compile caches of vLLM (incl. the AOT Dynamo artifact) are keyed by config and traced source, not by these env vars,
so sitecustomize moves VLLM_CACHE_ROOT to a per-config subdirectory: a KVQ server can never load (or leave behind) a
BF16 server's compiled graph.
"""
import os
import sys

BITS = int(os.environ.get("CLOQ_KVQ_BITS", "16"))
ROT = os.environ.get("CLOQ_KVQ_ROT", "0") == "1"
WHICH = os.environ.get("CLOQ_KVQ_WHICH", "kv")
ACTIVE_Q = BITS < 16
TAG = f"kvq_b{BITS}_r{int(ROT)}_{WHICH}"


def isolate_cache_root():
    root = os.environ.get("VLLM_CACHE_ROOT", os.path.expanduser("~/.cache/vllm"))
    if os.path.basename(root.rstrip("/")) != TAG:  # idempotent across the API server and its EngineCore children
        os.environ["VLLM_CACHE_ROOT"] = os.path.join(root, TAG)


def _fwht(x):
    """Normalized Walsh-Hadamard transform over the last dim (power of 2). Self-inverse."""
    import torch
    d = x.shape[-1]
    lead = x.shape[:-1]
    h = 1
    while h < d:
        y = x.reshape(*lead, d // (2 * h), 2, h)
        a, b = y[..., 0, :], y[..., 1, :]
        x = torch.stack((a + b, a - b), dim=-2).reshape(*lead, d)
        h *= 2
    return x * (d ** -0.5)


def _qdq(x, bits):
    import torch
    L = float(2 ** bits - 1)
    mn = x.amin(dim=-1, keepdim=True)
    mx = x.amax(dim=-1, keepdim=True)
    s = ((mx - mn) / L).clamp_min(1e-12)
    q = torch.clamp(torch.round((x - mn) / s), 0.0, L)
    return q * s + mn


def _rot(t, d):
    return _fwht(t.reshape(-1, d).float()).to(t.dtype).reshape(t.shape)


def _kv(t, d, rotate, unrotate, quant):
    if not (rotate or unrotate or (quant and ACTIVE_Q)):
        return t
    shp, dt = t.shape, t.dtype
    x = t.reshape(-1, d).float()
    if rotate:
        x = _fwht(x)
    if quant and ACTIVE_Q:
        x = _qdq(x, BITS)
    if unrotate:
        x = _fwht(x)
    return x.to(dt).reshape(shp)


def install(mod):
    Attention = mod.Attention
    if getattr(Attention, "_cloq_kvq", None):
        return
    orig = Attention.forward

    def forward(self, query, key, value, output_shape=None, output_dtype=None):
        if key is not None and value is not None and self.attn_type == "decoder" and (ACTIVE_Q or ROT):
            d, dv = self.head_size, self.head_size_v
            if ROT:
                assert d & (d - 1) == 0 and dv & (dv - 1) == 0, f"Hadamard needs power-of-2 head_dim, got {d}/{dv}"
                if output_dtype is None:
                    output_dtype = query.dtype
                query = _rot(query, d)
            key = _kv(key, d, ROT, False, "k" in WHICH)  # K stays in the rotated basis (matches the rotated q)
            if "v" in WHICH:
                value = _kv(value, dv, ROT, ROT, True)
        return orig(self, query, key, value, output_shape, output_dtype)

    Attention.forward = forward
    Attention._cloq_kvq = TAG
    print(f"[cloq_kvq] pid={os.getpid()} wrapped {mod.__name__}.Attention.forward: bits={BITS} rot={int(ROT)} "
          f"which={WHICH} cache_root={os.environ.get('VLLM_CACHE_ROOT')}", file=sys.stderr, flush=True)
