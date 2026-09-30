"""Fake activation quantization (and QuaRot's online Hadamards) for vLLM 0.29 serving (docs/insights/METHOD_FIDELITY.md).
Imported by sitecustomize.py only when CLOQ_PYHOOKS=1 and CLOQ_AQ_BITS is set.

Patch points (wrapped at import of vllm.model_executor.layers.linear, before model construction and torch.compile):
  LinearBase.__init__          decides, per constructed module (by its prefix), what the forward wrapper does, logs
                               one "[cloq_aq] module" line per LinearBase (coverage) and refuses unsupported layouts.
  ColumnParallelLinear.forward covers QKVParallelLinear (qkv_proj) and MergedColumnParallelLinear (gate_up_proj):
                               the fused modules quantize their single shared input once, which equals quantizing the
                               identical input of q/k/v (gate/up) separately with a per-token scale.
  RowParallelLinear.forward    covers o_proj and down_proj.
The input of each covered linear is (optionally Hadamard-rotated, then) quantize-dequantized in fp32 and cast back to
the compute dtype (bf16) before the unchanged BF16 GEMM. Norms, softmax, the residual stream, the embedding and the
lm_head (VocabParallelEmbedding / ParallelLMHead, not LinearBase) are never touched. Dynamo inlines the wrapper, so the
ops are compiled by Inductor and replayed inside the CUDA graphs; all statistics are per row (per token or per group
of one token), cloq/aq.py.

env
  CLOQ_AQ_BITS   16 = hook installed, pass-through (identity; the A16 control); 8 / 4 / ...
  CLOQ_AQ_FMT    sym_quarot (default; QuaRot ActQuantizer) | sym_sq (SmoothQuant per-token absmax)
  CLOQ_AQ_CLIP   constant clip ratio (default 1.0; QuaRot uses 0.9)
  CLOQ_AQ_GROUP  -1 = per token (default) or a group size along the hidden dim
  CLOQ_AQ_ONLY   comma list of kinds to quantize: qkv,o,gate_up,down (default all four)
  CLOQ_AQ_HAD    0 (default) | quarot: online Hadamard on the down_proj input (H_K kron H_{n/K}, full) and across heads
                 on the o_proj input (QuaRot online_full_had / online_partial_had). Applied regardless of CLOQ_AQ_ONLY:
                 a QuaRot checkpoint's weights expect the rotated inputs. Requires TP = 1.
The compile cache root is moved per config by sitecustomize (tag()).
"""
import os
import sys

from cloq.aq import had_factor, had_heads, had_transform, hadK_list, qdq

BITS = int(os.environ.get("CLOQ_AQ_BITS", "16"))
FMT = os.environ.get("CLOQ_AQ_FMT", "sym_quarot")
CLIP = float(os.environ.get("CLOQ_AQ_CLIP", "1.0"))
GROUP = int(os.environ.get("CLOQ_AQ_GROUP", "-1"))
ONLY = tuple(sorted(x for x in os.environ.get("CLOQ_AQ_ONLY", "qkv,o,gate_up,down").split(",") if x))
HAD = os.environ.get("CLOQ_AQ_HAD", "0")
KINDS = {"qkv_proj": "qkv", "o_proj": "o", "gate_up_proj": "gate_up", "down_proj": "down"}
assert FMT in ("sym_quarot", "sym_sq"), FMT
assert HAD in ("0", "quarot"), HAD
assert set(ONLY) <= set(KINDS.values()), ONLY
N = {"quant": 0, "had_only": 0, "pass": 0, "excluded": 0}


def tag() -> str:
    only = "all" if set(ONLY) == set(KINDS.values()) else "-".join(ONLY)
    return f"aq_b{BITS}_{FMT}_c{CLIP:g}_g{GROUP}_h{HAD}_{only}"


def _log(msg):
    print(f"[cloq_aq] pid={os.getpid()} {msg}", file=sys.stderr, flush=True)


def _apply(self, x):
    c = self._cloq_aq
    dt = x.dtype
    y = x.float()
    if c[1] == "full":
        y = had_transform(y, c[2], c[3])
    elif c[1] == "heads":
        y = had_heads(y, c[2])
    if c[0]:
        y = qdq(y, BITS, FMT, CLIP, GROUP)
    return y.to(dt)


def install(mod):
    LinearBase, Col, Row = mod.LinearBase, mod.ColumnParallelLinear, mod.RowParallelLinear
    if getattr(LinearBase, "_cloq_aq_installed", None):
        return
    init0, col0, row0 = LinearBase.__init__, Col.forward, Row.forward

    def __init__(self, *a, **kw):
        init0(self, *a, **kw)
        self._cloq_aq = None
        if not N.get("checked"):
            from vllm.config import get_current_vllm_config
            mc = get_current_vllm_config().model_config
            if mc is None:
                raise RuntimeError("cloq_aq: no current vLLM model config at LinearBase construction")
            hf = mc.hf_text_config
            if getattr(hf, "num_experts", 0) or getattr(hf, "n_routed_experts", 0):
                raise RuntimeError("cloq_aq: MoE experts (FusedMoE) are not LinearBase and would not be covered; "
                                   "activation quantization is unsupported for MoE models")
            N["checked"] = 1
        prefix = getattr(self, "prefix", "") or ""
        leaf = prefix.rsplit(".", 1)[-1]
        kind = KINDS.get(leaf)
        cls = type(self).__name__
        if kind is None:
            N["excluded"] += 1
            _log(f"module {prefix} {cls} in={self.input_size} out={self.output_size} kind=- action=excluded")
            return
        if type(self.quant_method).__name__ != "UnquantizedLinearMethod":
            raise RuntimeError(f"cloq_aq: {prefix} has quant method {type(self.quant_method).__name__}; only BF16 "
                               "(unquantized) linears are supported")
        tp = getattr(self, "tp_size", 1)
        had = None
        if HAD == "quarot" and kind in ("down", "o"):
            if tp != 1:
                raise RuntimeError(f"cloq_aq: online Hadamard needs TP=1 ({prefix} tp={tp})")
            if kind == "down":
                K, H = had_factor(self.input_size)
                had = ("full", K, hadK_list(K, H))
            else:
                from vllm.config import get_current_vllm_config
                hf = get_current_vllm_config().model_config.hf_text_config
                nh = int(hf.num_attention_heads)
                assert self.input_size % nh == 0 and nh & (nh - 1) == 0, (self.input_size, nh)
                had = ("heads", nh, None)
        quant = BITS < 16 and kind in ONLY
        if quant or had:
            self._cloq_aq = (quant,) + (had if had else (None, None, None))
        action = "quant" if quant else ("had_only" if had else "pass")
        N[action] += 1
        _log(f"module {prefix} {cls} in={self.input_size} out={self.output_size} kind={kind} tp={tp} action={action} "
             f"had={had[0] + str(had[1]) if had else '-'} n_quant={N['quant']} n_had_only={N['had_only']} n_pass={N['pass']}")

    def col_forward(self, input_):
        if self._cloq_aq is not None:
            input_ = _apply(self, input_)
        return col0(self, input_)

    def row_forward(self, input_):
        if self._cloq_aq is not None:
            input_ = _apply(self, input_)
        return row0(self, input_)

    LinearBase.__init__ = __init__
    Col.forward = col_forward
    Row.forward = row_forward
    LinearBase._cloq_aq_installed = tag()
    _log(f"wrapped {mod.__name__}: LinearBase.__init__, ColumnParallelLinear.forward, RowParallelLinear.forward "
         f"bits={BITS} fmt={FMT} clip={CLIP:g} group={GROUP} only={','.join(ONLY)} had={HAD} tag={tag()} "
         f"cache_root={os.environ.get('VLLM_CACHE_ROOT')}")
