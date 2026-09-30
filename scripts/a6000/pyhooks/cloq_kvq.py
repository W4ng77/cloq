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
WHICH = os.environ.get("CLOQ_KVQ_WHICH", "kv")
ACTIVE_Q = BITS < 16
# QuaRot mode (docs/insights/METHOD_FIDELITY.md): CLOQ_KVQ_ROT=qk rotates q and k online only (V is rotated offline by a
# cloq.quarot checkpoint: v_proj output per head, undone in o_proj); CLOQ_KVQ_FMT=quarot uses QuaRot's quantizers
# (cloq/aq.py): K asymmetric per (token, head) with zero in the range, V asymmetric per group of head_dim, integer zero
# point, constant clip ratios CLOQ_KVQ_KCLIP / CLOQ_KVQ_VCLIP (QuaRot: 0.95). Defaults keep the W13 behaviour and tag.
ROT_MODE = os.environ.get("CLOQ_KVQ_ROT", "0")
assert ROT_MODE in ("0", "1", "qk"), ROT_MODE
ROT = ROT_MODE != "0"  # q and k rotated online
ROT_V = ROT_MODE == "1"  # V rotated online and rotated back
FMT = os.environ.get("CLOQ_KVQ_FMT", "minmax")
assert FMT in ("minmax", "quarot"), FMT
KCLIP = float(os.environ.get("CLOQ_KVQ_KCLIP", "1.0"))
VCLIP = float(os.environ.get("CLOQ_KVQ_VCLIP", "1.0"))
if FMT == "minmax":
    assert KCLIP == 1.0 and VCLIP == 1.0, "clip ratios need CLOQ_KVQ_FMT=quarot"
TAG = f"kvq_b{BITS}_r{int(ROT)}_{WHICH}"
if ROT_MODE == "qk" or FMT != "minmax":
    TAG = f"kvq_b{BITS}_r{ROT_MODE}_{WHICH}_{FMT}_kc{KCLIP:g}_vc{VCLIP:g}"


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


def _qdq(x, bits, which="k"):
    import torch
    if FMT == "quarot":
        from cloq.aq import qdq
        return qdq(x, bits, "asym_quarot_tok" if which == "k" else "asym_quarot_grp", KCLIP if which == "k" else VCLIP)
    L = float(2 ** bits - 1)
    mn = x.amin(dim=-1, keepdim=True)
    mx = x.amax(dim=-1, keepdim=True)
    s = ((mx - mn) / L).clamp_min(1e-12)
    q = torch.clamp(torch.round((x - mn) / s), 0.0, L)
    return q * s + mn


def _rot(t, d):
    return _fwht(t.reshape(-1, d).float()).to(t.dtype).reshape(t.shape)


def _kv(t, d, rotate, unrotate, quant, which="k"):
    if not (rotate or unrotate or (quant and ACTIVE_Q)):
        return t
    shp, dt = t.shape, t.dtype
    x = t.reshape(-1, d).float()
    if rotate:
        x = _fwht(x)
    if quant and ACTIVE_Q:
        x = _qdq(x, BITS, which)
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
                assert d & (d - 1) == 0 and (dv & (dv - 1) == 0 or not ROT_V), f"Hadamard needs power-of-2 head_dim, got {d}/{dv}"
                if output_dtype is None:
                    output_dtype = query.dtype
                query = _rot(query, d)
            key = _kv(key, d, ROT, False, "k" in WHICH, "k")  # K stays in the rotated basis (matches the rotated q)
            if "v" in WHICH:
                value = _kv(value, dv, ROT_V, ROT_V, True, "v")
        return orig(self, query, key, value, output_shape, output_dtype)

    Attention.forward = forward
    Attention._cloq_kvq = TAG
    # Coverage record (fork acceptance, docs/insights/FORK_PROTOCOL.md §5): one line per Attention instance built in this
    # process, at model construction (plain Python, before compile; numerics unaffected).
    orig_init = Attention.__init__
    count = [0]

    def __init__(self, *a, **k):
        orig_init(self, *a, **k)
        count[0] += 1
        print(f"[cloq_kvq] pid={os.getpid()} hooked attention #{count[0]} type={getattr(self, 'attn_type', None)} "
              f"prefix={k.get('prefix', '')}", file=sys.stderr, flush=True)

    Attention.__init__ = __init__
    print(f"[cloq_kvq] pid={os.getpid()} wrapped {mod.__name__}.Attention.forward: bits={BITS} rot={int(ROT)} "
          f"rot_mode={ROT_MODE} fmt={FMT} kclip={KCLIP:g} vclip={VCLIP:g} tag={TAG} "
          f"which={WHICH} cache_root={os.environ.get('VLLM_CACHE_ROOT')}", file=sys.stderr, flush=True)
