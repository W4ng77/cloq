"""Streaming layer-wise GPTQ / AWQ-style quantization for any HF decoder (Qwen3, Qwen3-MoE, Llama).

Input: a calibration buffer (list of token-id sequences, batch size 1, no padding; optionally a fixed
set of activation rows per sequence, protocol v1). Output: a fake-quant BF16 checkpoint in the
*source* safetensors layout: every source shard is copied with only the quantized decoder linears
replaced, so vLLM serves it through the identical BF16 path as the source model. Plus
quantization.json.

Methods
  gptq  GPTQ W{3,4,8}, g128, asymmetric, percdamp 0.01, blocksize 128, act-order, true-sequential
        inside each decoder layer (q,k,v -> o -> gate,up -> down). Unchanged from v1.
  awq   AWQ-style activation-aware scaling, then RTN on the same g128 asymmetric grid. For every
        linear, s = mean|x|^alpha (normalised), alpha on a 20-point grid in [0, 1), chosen to
        minimise ||X W^T - X (Q(W diag(s)) diag(s)^-1)^T||^2 on a fixed row sample of the
        calibration activations. Because checkpoints are fake-quant, the scale is folded back into
        the weight instead of into the preceding op, so q/k/v need not share one scale (a mild
        generalisation of AutoAWQ; no clipping search). alpha = 0 is plain RTN.
  rtn   round-to-nearest (no calibration); cloq.compress does the same without loading the model.

Every method runs sequentially: later layers are calibrated on inputs produced by the already
quantized earlier layers. MoE (Qwen3-MoE): GPTQ / AWQ act on attention only; expert weights are
RTN-quantized at write time (docs/A6000_PLAN.md section 3), and the calibration forward keeps
the experts in BF16. Embeddings, lm_head, norms and the router stay BF16.

usage:
  python -m cloq.quantize --method gptq --calib manifests/a6000/q8/calib_fp_traj_c1.json --out <dir> [--wbits 4]
  python -m cloq.quantize --method awq  --calib ... --out <dir>
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import re
import time
from pathlib import Path

import torch
import torch.nn as nn
from loguru import logger
from safetensors import safe_open
from safetensors.torch import save_file

from cloq import config as C
from cloq.compress import LINEAR_RE, rtn_dequant
from cloq.gptq import GPTQLinear, rtn_quantize_linear

SEQUENTIAL_GROUPS = [
    ["self_attn.q_proj", "self_attn.k_proj", "self_attn.v_proj"],
    ["self_attn.o_proj"],
    ["mlp.gate_proj", "mlp.up_proj"],
    ["mlp.down_proj"],
]
ATTN_GROUPS = SEQUENTIAL_GROUPS[:2]
EXPERT_RE = re.compile(r"\.mlp\.experts\.\d+\.(gate|up|down)_proj\.weight$")


def _get_module(root: nn.Module, name: str) -> nn.Module:
    m = root
    for p in name.split("."):
        m = getattr(m, p)
    return m


def source_dir() -> Path:
    from huggingface_hub import snapshot_download

    return Path(snapshot_download(C.MODEL_ID, revision=C.MODEL_REVISION, local_files_only=True))


def load_bf16_model(device: str = "cuda", src: str | None = None):
    from transformers import AutoModelForCausalLM

    kw = {"revision": C.MODEL_REVISION} if src is None else {}
    model = AutoModelForCausalLM.from_pretrained(
        src or C.MODEL_ID, dtype=torch.bfloat16, attn_implementation="sdpa", **kw
    )
    model.eval()
    model.config.use_cache = False
    return model


def is_moe(layer: nn.Module) -> bool:
    return hasattr(layer, "mlp") and hasattr(layer.mlp, "experts")


def groups_for(layer: nn.Module) -> list[list[str]]:
    return ATTN_GROUPS if is_moe(layer) else SEQUENTIAL_GROUPS


def load_calib_sequences(manifest_path: Path) -> tuple[list[list[int]], list[list[int]] | None, dict]:
    """Return (sequences, per-sequence activation-row indices or None, manifest)."""
    man = json.load(open(manifest_path))
    seqs = [c["prompt_token_ids"] for c in man["contexts"]]
    rows = None
    if all("row_idx" in c for c in man["contexts"]):
        rows = [c["row_idx"] for c in man["contexts"]]
        for ix, sq in zip(rows, seqs):
            assert len(set(ix)) == len(ix), "row indices must be unique within a context"
            assert max(ix) < len(sq) and min(ix) >= 0, "row index out of range for its context"
    return seqs, rows, man


def _to(x, device):
    if torch.is_tensor(x):
        return x.to(device, non_blocking=True)
    if isinstance(x, tuple):
        return tuple(_to(v, device) for v in x)
    if isinstance(x, list):
        return [_to(v, device) for v in x]
    if isinstance(x, dict):
        return {k: _to(v, device) for k, v in x.items()}
    return x


class Inputs:
    """Per-sequence (hidden, kwargs) for the current layer; kept on CPU when they would not fit."""

    def __init__(self, items, offload: bool):
        self.offload = offload
        self.items = items

    def __len__(self):
        return len(self.items)

    def iter(self, device):
        for h, kw in self.items:
            yield (_to(h, device), _to(kw, device)) if self.offload else (h, kw)


@torch.no_grad()
def capture_layer0_inputs(model, seqs: list[list[int]], device: str, offload: bool) -> Inputs:
    """Run embeddings + rotary once per sequence; capture (hidden, kwargs) for layer 0."""
    layers = model.model.layers
    captured = []

    class Catcher(nn.Module):
        def __init__(self, module):
            super().__init__()
            self.module = module
            self.attention_type = getattr(module, "attention_type", "full_attention")

        def forward(self, hidden_states, **kwargs):
            item = (hidden_states.detach(), dict(kwargs))
            captured.append((_to(item[0], "cpu"), _to(item[1], "cpu")) if offload else item)
            raise ValueError("captured")

    orig = layers[0]
    layers[0] = Catcher(orig)
    model.model.embed_tokens.to(device)
    model.model.rotary_emb.to(device)
    for ids in seqs:
        x = torch.tensor([ids], dtype=torch.long, device=device)
        try:
            model(input_ids=x, use_cache=False)
        except ValueError as e:
            if "captured" not in str(e):
                raise
    layers[0] = orig
    model.model.embed_tokens.cpu()
    torch.cuda.empty_cache()
    return Inputs(captured, offload)


@torch.no_grad()
def awq_search(lin: nn.Linear, xmean: torch.Tensor, X: torch.Tensor, wbits: int, groupsize: int, grid: int = 20) -> dict:
    W = lin.weight.detach().float()
    Y = X @ W.t()
    base = xmean.clamp(min=1e-4)
    best = (float("inf"), None, None)
    for r in range(grid):
        a = r / grid
        s = base.pow(a)
        s = s / (s.max() * s.min()).sqrt()
        Wq = rtn_dequant(W * s.unsqueeze(0), wbits, groupsize) / s.unsqueeze(0)
        err = float(((X @ Wq.t() - Y) ** 2).mean())
        if err < best[0]:
            best = (err, a, Wq)
    err0 = float(((X @ rtn_dequant(W, wbits, groupsize).t() - Y) ** 2).mean())
    rel = float(((best[2] - W) ** 2).sum() / (W**2).sum().clamp_min(1e-12))
    lin.weight.data.copy_(best[2].to(lin.weight.dtype))
    return {"alpha": best[1], "out_mse": best[0], "out_mse_rtn": err0, "rel_weight_err": rel}


@torch.no_grad()
def quantize_model(model, seqs, method: str, wbits: int, groupsize: int, percdamp: float, blocksize: int,
                   actorder: bool, sym: bool, device: str = "cuda", row_idx=None, awq_rows: int = 4096,
                   offload: bool | None = None) -> tuple[dict, dict]:
    """Sequential layer-wise GPTQ / AWQ. Returns (stats, {disk tensor name: new bf16 weight})."""
    layers = model.model.layers
    n_tokens = sum(len(s) for s in seqs)
    hidden = model.config.get_text_config().hidden_size
    if offload is None:
        offload = n_tokens * hidden * 2 > 12e9
    inputs = capture_layer0_inputs(model, seqs, device, offload)
    idx_t = None
    if row_idx is not None:
        assert len(row_idx) == len(seqs), "row_idx must have one entry per sequence"
        idx_t = [torch.as_tensor(ix, dtype=torch.long, device=device) for ix in row_idx]
        n_rows = sum(len(ix) for ix in row_idx)
    else:
        n_rows = n_tokens
    logger.info(f"{method}: {len(inputs)} sequences, {n_tokens} tokens, {n_rows} rows, offload={offload}")
    gen = torch.Generator().manual_seed(0)
    awq_pick = torch.randperm(n_rows, generator=gen)[:awq_rows].sort().values if method == "awq" else None
    stats, new_weights = {}, {}
    t_start = time.time()
    for li, layer in enumerate(layers):
        layer.to(device)
        layer_stats = {}
        for group in groups_for(layer):
            seq_pos = {"i": 0}
            handles = []
            if method == "gptq":
                helpers = {name: GPTQLinear(_get_module(layer, name)) for name in group}
            else:
                helpers = {name: {"sum": None, "n": 0, "rows": []} for name in group}
            for name in group:
                mod = _get_module(layer, name)

                def hook(m, inp, out, _name=name):
                    x = inp[0]
                    if idx_t is not None:
                        x = x.index_select(-2, idx_t[seq_pos["i"]])
                    x = x.reshape(-1, x.shape[-1])
                    if method == "gptq":
                        helpers[_name].add_batch(x)
                    else:
                        h = helpers[_name]
                        a = x.float().abs().sum(0)
                        h["sum"] = a if h["sum"] is None else h["sum"] + a
                        h["n"] += x.shape[0]
                        h["rows"].append(x.to("cpu", torch.bfloat16))

                handles.append(mod.register_forward_hook(hook))
            for si, (hid, kw) in enumerate(inputs.iter(device)):
                seq_pos["i"] = si
                layer(hid, **kw)
            for hd in handles:
                hd.remove()
            for name in group:
                lin = _get_module(layer, name)
                if method == "gptq":
                    layer_stats[name] = helpers[name].run_gptq(wbits=wbits, groupsize=groupsize, blocksize=blocksize,
                                                               percdamp=percdamp, actorder=actorder, sym=sym)
                    helpers[name].free()
                else:
                    h = helpers[name]
                    X = torch.cat(h["rows"])[awq_pick.clamp(max=h["n"] - 1)].to(device, torch.float32)
                    layer_stats[name] = awq_search(lin, h["sum"] / h["n"], X, wbits, groupsize)
                    del X
                    h["rows"] = None
                new_weights[f"model.layers.{li}.{name}.weight"] = lin.weight.detach().to("cpu").clone()
            del helpers
        # propagate through the (now quantized) layer
        new_items = []
        for i, (hid, kw) in enumerate(inputs.iter(device)):
            out = layer(hid, **kw)
            if isinstance(out, tuple):
                out = out[0]
            out = out.detach()
            new_items.append((out.cpu() if inputs.offload else out, inputs.items[i][1]))
        inputs.items = new_items
        layer.cpu()
        torch.cuda.empty_cache()
        stats[f"layers.{li}"] = layer_stats
        mean_rel = sum(v["rel_weight_err"] for v in layer_stats.values()) / len(layer_stats)
        logger.info(f"layer {li:2d} done ({time.time() - t_start:.0f}s) mean rel weight err {mean_rel:.4f}")
    del inputs
    gc.collect()
    torch.cuda.empty_cache()
    return ({"per_layer": stats, "n_sequences": len(seqs), "n_tokens": n_tokens,
             "n_activation_rows": n_rows, "awq_rows": awq_rows if method == "awq" else None,
             "seconds": time.time() - t_start}, new_weights)


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def write_checkpoint(src: Path, out_dir: Path, new_weights: dict, expert_rtn_bits: int | None, meta: dict,
                     sha: bool = True) -> None:
    """Copy the source checkpoint shard by shard, replacing only the quantized tensors."""
    out_dir.mkdir(parents=True, exist_ok=True)
    left = set(new_weights)
    n_expert = 0
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    for sh in sorted(src.glob("*.safetensors")):
        tensors = {}
        with safe_open(sh, framework="pt") as f:
            smeta = f.metadata()
            for name in f.keys():
                t = f.get_tensor(name)
                if name in new_weights:
                    w = new_weights[name]
                    assert w.shape == t.shape and w.dtype == t.dtype, f"{name}: {w.shape}/{w.dtype} vs {t.shape}/{t.dtype}"
                    t = w
                    left.discard(name)
                elif expert_rtn_bits and EXPERT_RE.search(name) and LINEAR_RE.search(name):
                    t = rtn_dequant(t.to(dev, torch.float32), expert_rtn_bits).to(t.dtype).cpu()
                    n_expert += 1
                tensors[name] = t
        save_file(tensors, str(out_dir / sh.name), metadata=smeta or {"format": "pt"})
        del tensors
    assert not left, f"{len(left)} quantized tensors not found in the source shards, e.g. {sorted(left)[:3]}"
    for p in src.iterdir():
        if p.suffix != ".safetensors" and p.is_file():
            (out_dir / p.name).write_bytes(p.read_bytes())
    meta["n_expert_tensors_rtn"] = n_expert
    if sha:
        meta["weight_files"] = {p.name: _sha256_file(p) for p in sorted(out_dir.glob("*.safetensors"))}
    (out_dir / "quantization.json").write_text(json.dumps(meta, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=["gptq", "awq", "rtn"], default="gptq")
    ap.add_argument("--calib", default=None, help="calibration manifest json (from cloq.calib_v1)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--wbits", type=int, default=int(C.FROZEN["quantization"]["wbits"]))
    ap.add_argument("--rtn", action="store_true", help="alias for --method rtn (v0/v1 scripts)")
    ap.add_argument("--awq-rows", type=int, default=4096)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--no-sha", action="store_true")
    ap.add_argument("--src", default=None, help="local BF16 checkpoint dir to quantize instead of the pinned source "
                    "model (e.g. a cloq.rotate output); its quantization.json is recorded as pre_transform")
    args = ap.parse_args()
    method = "rtn" if args.rtn else args.method
    q = C.FROZEN["quantization"]
    out = Path(args.out)
    if (out / "quantization.json").exists():
        print(f"{out} exists; skipping")
        return
    torch.manual_seed(0)
    model = load_bf16_model(src=args.src)
    meta = {
        "method": "AWQ-style" if method == "awq" else method.upper(), "wbits": args.wbits,
        "group_size": q["group_size"], "sym": q["sym"], "percdamp": q["percdamp"], "blocksize": q["blocksize"],
        "act_order": q["act_order"], "true_sequential": q["true_sequential"],
        "source_model": C.MODEL_ID, "source_revision": C.MODEL_REVISION, "storage": "fake-quant bf16",
        "calibration_manifest": args.calib,
        "moe_experts": "RTN (same grid)" if is_moe(model.model.layers[0]) else None,
    }
    if args.src:
        meta["source_dir"] = args.src
        pq = Path(args.src) / "quantization.json"
        if pq.exists():
            meta["pre_transform"] = {k: v for k, v in json.load(open(pq)).items() if k not in ("per_tensor", "weight_files")}
            if "rotation" in meta["pre_transform"]:
                meta["method"] = "QuaRot-" + meta["method"]
    t0 = time.time()
    if method == "rtn":
        stats, new = {}, {}
        for li, layer in enumerate(model.model.layers):
            for group in groups_for(layer):
                for name in group:
                    lin = _get_module(layer, name)
                    stats[f"layers.{li}.{name}"] = rtn_quantize_linear(lin, wbits=args.wbits, groupsize=q["group_size"], sym=q["sym"])
                    new[f"model.layers.{li}.{name}.weight"] = lin.weight.detach().clone()
        meta["stats"] = {"per_linear": stats}
    else:
        seqs, rows, man = load_calib_sequences(Path(args.calib))
        meta["calibration"] = {k: v for k, v in man.items() if k != "contexts"}
        meta["calibration"]["manifest_sha256"] = _sha256_file(Path(args.calib))
        meta["stats"], new = quantize_model(
            model, seqs, method=method, wbits=args.wbits, groupsize=q["group_size"], percdamp=q["percdamp"],
            blocksize=q["blocksize"], actorder=q["act_order"], sym=q["sym"], device=args.device,
            row_idx=rows, awq_rows=args.awq_rows,
        )
    del model
    gc.collect()
    meta["seconds_quantize"] = time.time() - t0
    moe = meta["moe_experts"] is not None
    write_checkpoint(Path(args.src) if args.src else source_dir(), out, new, args.wbits if moe else None, meta, sha=not args.no_sha)
    print(f"saved {out} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
