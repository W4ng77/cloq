"""Calibration-free weight perturbations for the A6000 multi-model matrix, streamed shard by shard.

The model is never instantiated: every safetensors shard of the BF16 source is read, the decoder-layer
linear weights in it are rewritten, and the shard is saved under the same name. All other files
(config, tokenizer, chat template, shard index) are copied, so the output is served through the
identical BF16 vLLM path as the source model (fake-quant: only the weight values change).

Modes (docs/A6000_PLAN.md section 3):
  rtn    round-to-nearest, asymmetric, group 128, the same grid as cloq.gptq (W8 / W4 / W3)
  gauss  W + N, N i.i.d. Gaussian per linear, rescaled so ||N||_F = k * ||RTN_W4(W) - W||_F

Quantized tensors: every q/k/v/o and gate/up/down projection inside a decoder layer, including MoE
experts. Embeddings, lm_head, norms, MoE routers and any vision tower stay BF16.

usage:
  python -m cloq.compress rtn   --src <hf snapshot dir> --out <dir> --wbits 4
  python -m cloq.compress gauss --src <hf snapshot dir> --out <dir> --k 0.3 --seed 1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
import zlib
from pathlib import Path

import torch
from safetensors import safe_open
from safetensors.torch import save_file

from cloq.gptq import Quantizer, quantize

LINEAR_RE = re.compile(
    r"(^|\.)layers\.\d+\."
    r"(self_attn\.(q|k|v|o)_proj|mlp\.(gate|up|down)_proj|mlp\.experts\.\d+\.(gate|up|down)_proj)\.weight$"
)
GROUP = 128


def is_target(name: str) -> bool:
    return bool(LINEAR_RE.search(name)) and "vision" not in name


@torch.no_grad()
def rtn_dequant(W: torch.Tensor, wbits: int, groupsize: int = GROUP) -> torch.Tensor:
    """Fake-quant RTN of a [rows, cols] fp32 weight; bit-identical to cloq.gptq.rtn_quantize_linear."""
    rows, cols = W.shape
    q = Quantizer(wbits, sym=False)
    if cols % groupsize == 0:
        blk = W.reshape(rows * (cols // groupsize), groupsize)
        q.find_params(blk)
        return quantize(blk, q.scale, q.zero, q.maxq).reshape(rows, cols)
    Q = torch.empty_like(W)
    for g in range(0, cols, groupsize):
        b = W[:, g:g + groupsize]
        q.find_params(b)
        Q[:, g:g + groupsize] = quantize(b, q.scale, q.zero, q.maxq)
    return Q


def tensor_seed(seed: int, name: str) -> int:
    return (int(seed) * 1_000_003 + zlib.crc32(name.encode())) % (2**63 - 1)


@torch.no_grad()
def perturb(name: str, W16: torch.Tensor, args, device: str) -> tuple[torch.Tensor, dict]:
    W = W16.to(device=device, dtype=torch.float32)
    if args.mode == "rtn":
        Q = rtn_dequant(W, args.wbits)
    elif args.mode in ("gshape", "rtnsign"):
        # E17 (docs/insights/iter_3_candidates.md): separate error SIZE from error STRUCTURE.
        # gshape: Gaussian noise whose per-group (1 x 128) RMS equals that of the RTN-W<wbits> error, times k.
        # rtnsign: the exact RTN error magnitudes with i.i.d. random signs (same per-element size, no rounding correlation).
        E = rtn_dequant(W, args.wbits) - W
        g = torch.Generator(device=device).manual_seed(tensor_seed(args.seed, name))
        rows, cols = W.shape
        if args.mode == "rtnsign":
            sgn = torch.randint(0, 2, W.shape, generator=g, device=device, dtype=torch.int8).float() * 2 - 1
            Q = W + E * sgn * args.k
        else:
            N = torch.randn(W.shape, generator=g, device=device, dtype=torch.float32)
            if cols % GROUP == 0:
                rms = E.reshape(rows, cols // GROUP, GROUP).pow(2).mean(-1, keepdim=True).sqrt()
                Q = W + (N.reshape(rows, cols // GROUP, GROUP) * rms).reshape(rows, cols) * args.k
            else:
                Q = W.clone()
                for c0 in range(0, cols, GROUP):
                    e = E[:, c0:c0 + GROUP]
                    Q[:, c0:c0 + GROUP] += N[:, c0:c0 + GROUP] * e.pow(2).mean(-1, keepdim=True).sqrt() * args.k
    else:
        target = torch.linalg.vector_norm(rtn_dequant(W, 4) - W) * args.k
        g = torch.Generator(device=device).manual_seed(tensor_seed(args.seed, name))
        N = torch.randn(W.shape, generator=g, device=device, dtype=torch.float32)
        Q = W + N * (target / torch.linalg.vector_norm(N))
    out = Q.to(W16.dtype)
    err = out.float() - W
    st = {"rel_weight_err": float((err**2).sum() / (W**2).sum().clamp_min(1e-12)),
          "err_fro": float(torch.linalg.vector_norm(err))}
    return out.cpu(), st


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["rtn", "gauss", "gshape", "rtnsign"])
    ap.add_argument("--src", required=True, help="local BF16 snapshot directory")
    ap.add_argument("--out", required=True)
    ap.add_argument("--wbits", type=int, default=4)
    ap.add_argument("--k", type=float, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--source-model", default=None, help="hf id recorded in quantization.json")
    ap.add_argument("--source-revision", default=None)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--no-sha", action="store_true", help="skip output shard hashing (ephemeral node-local copies)")
    args = ap.parse_args()
    if args.mode in ("gauss", "gshape", "rtnsign"):
        assert args.k is not None and args.seed is not None, f"{args.mode} needs --k and --seed"
    src, out = Path(args.src), Path(args.out)
    if (out / "quantization.json").exists():
        print(f"{out} exists; skipping")
        return
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    stats, n_target = {}, 0
    shards = sorted(src.glob("*.safetensors"))
    assert shards, f"no safetensors in {src}"
    for sh in shards:
        tensors = {}
        with safe_open(sh, framework="pt") as f:
            meta = f.metadata()
            for name in f.keys():
                t = f.get_tensor(name)
                if is_target(name) and t.dim() == 2:
                    t, stats[name] = perturb(name, t, args, args.device)
                    n_target += 1
                tensors[name] = t
        save_file(tensors, str(out / sh.name), metadata=meta or {"format": "pt"})
        del tensors
    for p in src.iterdir():
        if p.suffix != ".safetensors" and p.is_file():
            shutil.copy(p, out / p.name)
    assert n_target > 0, "no decoder linear weights matched; unknown checkpoint layout"
    rels = [v["rel_weight_err"] for v in stats.values()]
    meta = {
        "method": "RTN" if args.mode == "rtn" else "gaussian",
        "wbits": args.wbits if args.mode == "rtn" else None,
        "group_size": GROUP, "sym": False,
        "gauss_k": args.k, "gauss_seed": args.seed,
        "gauss_reference": "per-linear ||N||_F = k * ||RTN_W4 g128 asym(W) - W||_F" if args.mode == "gauss" else None,
        "source_model": args.source_model, "source_revision": args.source_revision, "source_dir": str(src),
        "storage": "fake-quant bf16", "n_quantized_tensors": n_target,
        "mean_rel_weight_err": sum(rels) / len(rels), "seconds": time.time() - t0,
        "per_tensor": stats,
    }
    if not args.no_sha:
        meta["weight_files"] = {p.name: _sha256(p) for p in sorted(out.glob("*.safetensors"))}
    (out / "quantization.json").write_text(json.dumps(meta, indent=1))
    print(f"{args.mode} -> {out}: {n_target} tensors, mean rel err {meta['mean_rel_weight_err']:.5f}, {meta['seconds']:.0f}s")


if __name__ == "__main__":
    main()
