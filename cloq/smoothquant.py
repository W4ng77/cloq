"""SmoothQuant W8A8 (Xiao et al., ICML 2023; github.com/mit-han-lab/smoothquant) as a fake-quant BF16 checkpoint for a
dense Qwen3 / Llama model. The activation half (per-token dynamic symmetric INT8) runs at serving time in vLLM through
scripts/a6000/pyhooks/cloq_aq.py with CLOQ_AQ_BITS=8 CLOQ_AQ_FMT=sym_sq. docs/insights/METHOD_FIDELITY.md.

Follows the official code path for Llama-like models:
  act scales    get_act_scales: per input channel max|x| over every token of 512 Pile-validation documents
                (datasets.shuffle(seed=42) order = numpy default_rng(42).permutation, reproduced without `datasets`),
                each tokenized with truncation to 512 tokens; hooks on every nn.Linear input.
  smoothing     smooth_lm / smooth_ln_fcs_llama_like: input_layernorm -> [q, k, v], post_attention_layernorm ->
                [gate, up]; s_j = max|X_j|^a / max_i |W_ij|^(1-a) (weights of all fcs sharing the norm), clamp 1e-5;
                norm weight / s, fc weight * s. o_proj and down_proj are not smoothed (as the reference).
  W8            quantize_llama_like(weight_quant="per_channel"): every q/k/v/o/gate/up/down weight, symmetric absmax
                per output channel, 8 bits (fake_quant.quantize_weight_per_channel_absmax).
  A8            act_quant="per_token": every input of those linears, dynamic symmetric absmax per token (serving hook).
                quantize_bmm_input=False (the Llama default): q/k/v outputs and the attention BMMs stay BF16.
  alpha         the reference uses a per-model alpha (README: 0.85 for Llama-2/3 7-13B, 0.8 Mistral). None is given for
                Qwen3; we choose alpha from a fixed grid by W8A8 perplexity on 64 held-out Pile-validation documents
                (the next 64 of the same permutation, disjoint from the calibration 512), recorded per alpha.
Differences (recorded in quantization.json): scales/smoothing computed in fp32 and stored in bf16 (reference: the
model dtype, fp16); weights are dequantized and stored as bf16 (the W8 grid holds up to bf16 rounding, <= 2^-9 relative).
lm_head, embeddings, the final norm stay BF16. Tied embeddings stay tied (not touched).

usage: python -m cloq.smoothquant --src <hf snapshot> --out <dir> [--alpha auto|0.85] [--source-model ...]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from cloq.aq import qdq, sq_weight_per_channel_absmax

PILE_VAL = Path("/data/ziyangs/cloq_work/data/pile_val/val.jsonl")
ALPHA_GRID = (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9)
LIN = ("self_attn.q_proj", "self_attn.k_proj", "self_attn.v_proj", "self_attn.o_proj", "mlp.gate_proj", "mlp.up_proj",
       "mlp.down_proj")


def smooth_scales(act_scales: torch.Tensor, fc_weights: list[torch.Tensor], alpha: float) -> torch.Tensor:
    """smooth_ln_fcs_llama_like's s (fp32)."""
    act = act_scales.float()
    ws = torch.cat([w.float().abs().max(dim=0, keepdim=True)[0] for w in fc_weights], dim=0).max(dim=0)[0].clamp(min=1e-5)
    return (act.pow(alpha) / ws.pow(1 - alpha)).clamp(min=1e-5)


def pile_docs(n_skip: int, n: int, seed: int = 42) -> tuple[list[str], list[int]]:
    """Documents perm[n_skip : n_skip + n] of the Pile validation set in datasets.shuffle(seed) order."""
    offs = []
    with open(PILE_VAL, "rb") as f:
        pos = 0
        for line in f:
            offs.append(pos)
            pos += len(line)
    perm = np.random.default_rng(seed).permutation(len(offs))
    idx = [int(i) for i in perm[n_skip:n_skip + n]]
    out = []
    with open(PILE_VAL, "rb") as f:
        for i in idx:
            f.seek(offs[i])
            out.append(json.loads(f.readline())["text"])
    return out, idx


def _layers(model):
    return model.model.layers


def _mod(layer, name):
    m = layer
    for p in name.split("."):
        m = getattr(m, p)
    return m


@torch.no_grad()
def act_scales(model, ids_list, device) -> dict:
    scales = {}
    hooks = []

    def hook(name):
        def f(m, x, y):
            x = x[0] if isinstance(x, tuple) else x
            c = x.reshape(-1, x.shape[-1]).abs().float().amax(0).cpu()
            scales[name] = torch.maximum(scales[name], c) if name in scales else c
        return f

    for li, layer in enumerate(_layers(model)):
        for n in LIN:
            hooks.append(_mod(layer, n).register_forward_hook(hook(f"{li}.{n}")))
    for ids in ids_list:
        model(torch.tensor([ids], device=device))
    for h in hooks:
        h.remove()
    return scales


@torch.no_grad()
def ppl(model, ids_list, device) -> float:
    nll, n = 0.0, 0
    for ids in ids_list:
        x = torch.tensor([ids], device=device)
        logits = model(x).logits.float()
        lp = torch.log_softmax(logits[0, :-1], -1).gather(-1, x[0, 1:, None])[:, 0]
        nll -= float(lp.sum())
        n += len(ids) - 1
    return float(np.exp(nll / n))


@torch.no_grad()
def apply_sq(model, orig: dict, scales: dict, alpha: float | None, wbits: int = 8) -> dict:
    """Load orig (CPU fp32/bf16 state of the touched tensors), smooth with alpha (None = no smoothing), W8 per channel.
    Returns {param name: new bf16 tensor} for the touched tensors."""
    new = {}
    for li, layer in enumerate(_layers(model)):
        pre = f"model.layers.{li}."
        W = {n: orig[pre + n + ".weight"].to(layer.self_attn.q_proj.weight.device, torch.float32) for n in LIN}
        ln1 = orig[pre + "input_layernorm.weight"].float().to(W[LIN[0]].device)
        ln2 = orig[pre + "post_attention_layernorm.weight"].float().to(W[LIN[0]].device)
        if alpha is not None:
            for ln_name, ln, fcs in (("input_layernorm", ln1, LIN[:3]), ("post_attention_layernorm", ln2, LIN[4:6])):
                s = smooth_scales(scales[f"{li}.{fcs[0]}"].to(ln.device), [W[n] for n in fcs], alpha)
                lnw = (ln / s).to(torch.bfloat16)
                new[pre + ln_name + ".weight"] = lnw
                for n in fcs:
                    W[n] = (W[n] * s[None, :]).to(torch.bfloat16).float()  # stored smoothed bf16, then quantized
        else:
            new[pre + "input_layernorm.weight"] = ln1.to(torch.bfloat16)
            new[pre + "post_attention_layernorm.weight"] = ln2.to(torch.bfloat16)
        for n in LIN:
            new[pre + n + ".weight"] = sq_weight_per_channel_absmax(W[n], wbits).to(torch.bfloat16)
        for k, v in new.items():
            if k.startswith(pre):
                name = k[len("model."):]
                t = model.model
                parts = name.split(".")
                for p in parts[:-1]:
                    t = getattr(t, p)
                getattr(t, parts[-1]).data.copy_(v.to(getattr(t, parts[-1]).device))
    return new


class A8Hooks:
    """Per-token dynamic A-bit QDQ (sym_sq) on every decoder-linear input: the serving hook's numerics in HF."""

    def __init__(self, model, bits=8, fmt="sym_sq"):
        self.h = []
        for layer in _layers(model):
            for n in LIN:
                self.h.append(_mod(layer, n).register_forward_pre_hook(
                    lambda m, a: (qdq(a[0], bits, fmt).to(a[0].dtype),) + tuple(a[1:])))

    def remove(self):
        for h in self.h:
            h.remove()


def _ids_hash(ids_list) -> str:
    h = hashlib.sha256()
    for ids in ids_list:
        h.update(np.asarray(ids, dtype=np.int64).tobytes())
    return h.hexdigest()


@torch.no_grad()
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--alpha", default="auto")
    ap.add_argument("--n-calib", type=int, default=512)
    ap.add_argument("--seq-len", type=int, default=512)
    ap.add_argument("--n-eval", type=int, default=64)
    ap.add_argument("--source-model", default=None)
    ap.add_argument("--source-revision", default=None)
    ap.add_argument("--no-sha", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out)
    if (out / "quantization.json").exists():
        print(f"{out} exists; skipping")
        return
    t0 = time.time()
    torch.backends.cuda.matmul.allow_tf32 = False
    from transformers import AutoModelForCausalLM, AutoTokenizer
    dev = "cuda"
    tok = AutoTokenizer.from_pretrained(a.src)
    model = AutoModelForCausalLM.from_pretrained(a.src, dtype=torch.bfloat16, attn_implementation="sdpa").to(dev).eval()
    cfg = model.config.get_text_config()
    assert not getattr(cfg, "num_experts", 0), "dense models only"
    docs, idx = pile_docs(0, a.n_calib)
    calib = [tok(t, max_length=a.seq_len, truncation=True)["input_ids"] for t in docs]
    calib = [c for c in calib if len(c) > 0]
    edocs, eidx = pile_docs(a.n_calib, a.n_eval)
    evals = [e for e in (tok(t, max_length=a.seq_len, truncation=True)["input_ids"] for t in edocs) if len(e) > 1]
    scales = act_scales(model, calib, dev)
    orig = {}
    for k, v in model.state_dict().items():
        if k.startswith("model.layers.") and (k.endswith("layernorm.weight") or any(k.endswith(n + ".weight") for n in LIN)):
            orig[k] = v.detach().cpu().clone()
    sweep = {"bf16": ppl(model, evals, dev)}
    hooks = A8Hooks(model)
    apply_sq(model, orig, scales, None)
    sweep["w8a8_no_smoothing"] = ppl(model, evals, dev)
    grid = ALPHA_GRID if a.alpha == "auto" else () if a.alpha == "none" else (float(a.alpha),)
    for al in grid:
        apply_sq(model, orig, scales, al)
        sweep[f"alpha_{al:g}"] = ppl(model, evals, dev)
        print(f"alpha {al:g}: ppl {sweep[f'alpha_{al:g}']:.4f}", flush=True)
    alpha = min(grid, key=lambda al: sweep[f"alpha_{al:g}"]) if grid else None  # none: W8 per channel, no smoothing
    new = apply_sq(model, orig, scales, alpha)
    hooks.remove()
    from cloq.quantize import write_checkpoint
    meta = {
        "method": "SmoothQuant-W8A8" if alpha is not None else "W8A8 per-channel/per-token absmax, no smoothing (SmoothQuant quantizers)",
        "wbits": 8, "abits": 8, "alpha": alpha,
        "weight_quant": {"granularity": "per output channel", "sym": True, "rule": "absmax / 127, round half-even",
                         "modules": list(LIN), "storage": "dequantized bf16"},
        "act_quant": {"granularity": "per token (dynamic)", "sym": True, "rule": "clamp(absmax, 1e-5) / 127, no clip",
                      "applied_by": "scripts/a6000/pyhooks/cloq_aq.py (fmt sym_sq)", "bmm_inputs": "BF16 (quantize_bmm_input=False)"},
        "smoothing": {"input_layernorm": ["q_proj", "k_proj", "v_proj"], "post_attention_layernorm": ["gate_proj", "up_proj"],
                      "not_smoothed": ["o_proj", "down_proj"], "compute": "fp32, stored bf16"},
        "high_precision": ["embed_tokens", "lm_head", "all RMSNorms (smoothed norm weights bf16)", "softmax", "residual"],
        "calibration": {"source": "Pile validation (mit-han-lab/pile-val-backup val.jsonl.zst)",
                        "source_sha256": (PILE_VAL.parent / "val.jsonl.zst.sha256").read_text().split()[0],
                        "order": "numpy default_rng(42).permutation (datasets.shuffle(seed=42))",
                        "n_docs": len(calib), "doc_indices_sha256": hashlib.sha256(json.dumps(idx).encode()).hexdigest(),
                        "max_len": a.seq_len, "n_tokens": int(sum(len(c) for c in calib)), "token_ids_sha256": _ids_hash(calib)},
        "alpha_selection": {"grid": list(grid), "criterion": "W8A8 perplexity (min)", "eval_docs": len(evals),
                            "eval_doc_positions": [a.n_calib, a.n_calib + a.n_eval], "eval_tokens": int(sum(len(e) for e in evals)),
                            "eval_token_ids_sha256": _ids_hash(evals), "ppl": sweep},
        "requires_serve_env": {"CLOQ_PYHOOKS": "1", "CLOQ_AQ_BITS": "8", "CLOQ_AQ_FMT": "sym_sq"},
        "source_model": a.source_model, "source_revision": a.source_revision, "source_dir": a.src,
        "storage": "fake-quant bf16", "seconds": None,
    }
    if alpha is None:
        meta["smoothing"] = None
        meta["requires_serve_env"] = {"CLOQ_PYHOOKS": "1", "CLOQ_AQ_BITS": "8", "CLOQ_AQ_FMT": "sym_sq"}
    del model
    torch.cuda.empty_cache()
    meta["seconds"] = time.time() - t0
    write_checkpoint(Path(a.src), out, new, None, meta, sha=not a.no_sha)
    print(f"SmoothQuant alpha={alpha} -> {out} ({meta['seconds']:.0f}s) ppl {json.dumps(sweep)}")


if __name__ == "__main__":
    main()
