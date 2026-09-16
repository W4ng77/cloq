"""Streaming layer-wise GPTQ for Qwen3 (transformers 5.x) on one 16 GB GPU.

Input: a calibration buffer (list of token-id sequences, batch size 1, no
padding). Output: a fake-quant BF16 checkpoint (dequantized W4 weights in the
original safetensors layout) + quantization.json.

Protocol (frozen_v0.json / quantization): GPTQ W4, g128, asymmetric,
percdamp 0.01, blocksize 128, act-order, true-sequential inside each decoder
layer (q,k,v -> o -> gate,up -> down), all 36 decoder layers' linears;
embeddings / lm_head / norms stay BF16. Always starts from the original BF16
checkpoint.

usage:
  python -m cloq.quantize --calib manifests/calib_static.json --out ckpts/static_w4 [--wbits 4]
  python -m cloq.quantize --rtn --out ckpts/rtn_w4
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

import torch
import torch.nn as nn
from loguru import logger

from cloq import config as C
from cloq.gptq import GPTQLinear, rtn_quantize_linear

SEQUENTIAL_GROUPS = [
    ["self_attn.q_proj", "self_attn.k_proj", "self_attn.v_proj"],
    ["self_attn.o_proj"],
    ["mlp.gate_proj", "mlp.up_proj"],
    ["mlp.down_proj"],
]


def _get_module(root: nn.Module, name: str) -> nn.Module:
    m = root
    for p in name.split("."):
        m = getattr(m, p)
    return m


def load_bf16_model(device: str = "cuda"):
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(
        C.MODEL_ID, revision=C.MODEL_REVISION, dtype=torch.bfloat16, attn_implementation="sdpa"
    )
    model.eval()
    model.config.use_cache = False
    return model


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


@torch.no_grad()
def capture_layer0_inputs(model, seqs: list[list[int]], device: str):
    """Run embeddings + rotary once per sequence; capture (hidden, kwargs) for layer 0."""
    layers = model.model.layers
    captured = []

    class Catcher(nn.Module):
        def __init__(self, module):
            super().__init__()
            self.module = module

        def forward(self, hidden_states, **kwargs):
            captured.append((hidden_states.detach(), {k: v for k, v in kwargs.items()}))
            raise ValueError("captured")

    orig = layers[0]
    layers[0] = Catcher(orig)
    model.model.embed_tokens.to(device)
    model.model.rotary_emb.to(device)
    layers[0].to(device)
    for ids in seqs:
        x = torch.tensor([ids], dtype=torch.long, device=device)
        try:
            model(input_ids=x, use_cache=False)
        except ValueError as e:
            if "captured" not in str(e):
                raise
    layers[0] = orig
    layers[0].cpu()
    model.model.embed_tokens.cpu()
    torch.cuda.empty_cache()
    return captured


@torch.no_grad()
def quantize_model(
    model,
    seqs: list[list[int]],
    wbits: int,
    groupsize: int,
    percdamp: float,
    blocksize: int,
    actorder: bool,
    sym: bool,
    device: str = "cuda",
    row_idx: list[list[int]] | None = None,
) -> dict:
    """Streaming layer-wise GPTQ.

    `row_idx[i]` optionally restricts sequence i to a fixed set of token positions when the
    Hessian is accumulated (protocol v1: each calibration context contributes an exact quota of
    activation rows, drawn once and reused at every quantized layer). The forward pass always
    runs over the full sequence, so the hidden states that reach later layers are unchanged;
    only which rows enter the Gram matrix is restricted.
    """
    layers = model.model.layers
    inputs = capture_layer0_inputs(model, seqs, device)
    n_tokens = sum(len(s) for s in seqs)
    idx_t = None
    if row_idx is not None:
        assert len(row_idx) == len(seqs), "row_idx must have one entry per sequence"
        idx_t = [torch.as_tensor(ix, dtype=torch.long, device=device) for ix in row_idx]
        n_rows = sum(len(ix) for ix in row_idx)
        logger.info(f"captured {len(inputs)} sequences, {n_tokens} tokens, {n_rows} activation rows")
    else:
        n_rows = n_tokens
        logger.info(f"captured {len(inputs)} sequences, {n_tokens} tokens (all rows)")
    stats = {}
    t_start = time.time()
    for li, layer in enumerate(layers):
        layer.to(device)
        layer_stats = {}
        for group in SEQUENTIAL_GROUPS:
            helpers = {name: GPTQLinear(_get_module(layer, name)) for name in group}
            handles = []
            seq_pos = {"i": 0}
            for name, h in helpers.items():
                mod = _get_module(layer, name)

                def hook(m, inp, out, _h=h):
                    x = inp[0]
                    if idx_t is not None:
                        x = x.index_select(-2, idx_t[seq_pos["i"]])
                    _h.add_batch(x)

                handles.append(mod.register_forward_hook(hook))
            for si, (hidden, kw) in enumerate(inputs):
                seq_pos["i"] = si
                layer(hidden, **kw)
            for hd in handles:
                hd.remove()
            for name, h in helpers.items():
                layer_stats[name] = h.run_gptq(wbits=wbits, groupsize=groupsize, blocksize=blocksize, percdamp=percdamp, actorder=actorder, sym=sym)
                h.free()
        # propagate through the (now quantized) layer
        new_inputs = []
        for hidden, kw in inputs:
            out = layer(hidden, **kw)
            if isinstance(out, tuple):
                out = out[0]
            new_inputs.append((out.detach(), kw))
        inputs = new_inputs
        layer.cpu()
        torch.cuda.empty_cache()
        stats[f"layers.{li}"] = layer_stats
        mean_rel = sum(v["rel_weight_err"] for v in layer_stats.values()) / len(layer_stats)
        logger.info(f"layer {li:2d} done ({time.time() - t_start:.0f}s) mean rel weight err {mean_rel:.4f}")
    del inputs
    gc.collect()
    torch.cuda.empty_cache()
    return {"per_layer": stats, "n_sequences": len(seqs), "n_tokens": n_tokens,
            "n_activation_rows": n_rows, "seconds": time.time() - t_start}


@torch.no_grad()
def rtn_model(model, wbits: int, groupsize: int, sym: bool) -> dict:
    stats = {}
    for li, layer in enumerate(model.model.layers):
        for group in SEQUENTIAL_GROUPS:
            for name in group:
                stats[f"layers.{li}.{name}"] = rtn_quantize_linear(_get_module(layer, name), wbits=wbits, groupsize=groupsize, sym=sym)
    return {"per_linear": stats}


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save_checkpoint(model, out_dir: Path, meta: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir, safe_serialization=True)
    # copy tokenizer files from the frozen revision so vLLM/HF load the identical template
    from huggingface_hub import snapshot_download

    src = Path(snapshot_download(C.MODEL_ID, revision=C.MODEL_REVISION, allow_patterns=["*.json", "*.txt", "*.jinja"]))
    for fn in ["tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt", "generation_config.json"]:
        if (src / fn).exists():
            shutil.copy(src / fn, out_dir / fn)
    meta["weight_files"] = {p.name: _sha256_file(p) for p in sorted(out_dir.glob("*.safetensors"))}
    (out_dir / "quantization.json").write_text(json.dumps(meta, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calib", default=None, help="calibration manifest json (from cloq.calib)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--wbits", type=int, default=int(C.FROZEN["quantization"]["wbits"]))
    ap.add_argument("--rtn", action="store_true")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()
    q = C.FROZEN["quantization"]
    out = Path(args.out)
    if (out / "quantization.json").exists():
        print(f"{out} exists; skipping")
        return
    torch.manual_seed(0)
    model = load_bf16_model()
    meta = {
        "method": "RTN" if args.rtn else "GPTQ",
        "wbits": args.wbits, "group_size": q["group_size"], "sym": q["sym"], "percdamp": q["percdamp"],
        "blocksize": q["blocksize"], "act_order": q["act_order"], "true_sequential": q["true_sequential"],
        "source_model": C.MODEL_ID, "source_revision": C.MODEL_REVISION, "storage": "fake-quant bf16",
        "calibration_manifest": args.calib, "quantized_modules": q["quantized_modules"],
    }
    t0 = time.time()
    if args.rtn:
        meta["stats"] = rtn_model(model, args.wbits, q["group_size"], q["sym"])
    else:
        seqs, rows, man = load_calib_sequences(Path(args.calib))
        meta["calibration"] = {k: v for k, v in man.items() if k != "contexts"}
        meta["calibration"]["manifest_sha256"] = _sha256_file(Path(args.calib))
        meta["stats"] = quantize_model(
            model, seqs, wbits=args.wbits, groupsize=q["group_size"], percdamp=q["percdamp"],
            blocksize=q["blocksize"], actorder=q["act_order"], sym=q["sym"], device=args.device,
            row_idx=rows,
        )
    meta["seconds_total"] = time.time() - t0
    save_checkpoint(model, out, meta)
    print(f"saved {out} in {meta['seconds_total']:.0f}s")


if __name__ == "__main__":
    main()
