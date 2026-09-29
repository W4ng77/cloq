"""Calibration-free weight perturbations for the A6000 multi-model matrix, streamed shard by shard.

The model is never instantiated: every safetensors shard of the BF16 source is read, the decoder-layer
linear weights in it are rewritten, and the shard is saved under the same name. All other files
(config, tokenizer, chat template, shard index) are copied, so the output is served through the
identical BF16 vLLM path as the source model (fake-quant: only the weight values change).

Modes (docs/A6000_PLAN.md section 3):
  rtn    round-to-nearest, asymmetric, group 128, the same grid as cloq.gptq (W8 / W4 / W3)
  gauss  W + N, N i.i.d. Gaussian per linear, rescaled so ||N||_F = k * ||RTN_W4(W) - W||_F
  nf4    QLoRA NormalFloat-4 (bitsandbytes code table), blockwise absmax, block 64, fp32 absmax (no double quant)
  mxfp4  OCP Microscaling MXFP4: FP4 E2M1 elements (round-to-nearest-even, saturating), one shared E8M0
         power-of-two scale per 32 elements, X = 2^(floor(log2 amax) - 2) (OCP MX v1.0 section 6.3)
  rtnsr  RTN-W<wbits> g128 asym on the SAME grid as rtn (scale/zero from Quantizer.find_params) but stochastic
         rounding q = clamp(floor(x/scale + zero + u), 0, maxq), u ~ U[0,1) seeded by tensor_seed(seed, name):
         on-grid, unbiased control for rtn (rtnsign is off-grid)
  (rotated QuaRot-style checkpoints: cloq.rotate)

Quantized tensors: every q/k/v/o and gate/up/down projection inside a decoder layer, including MoE
experts. Embeddings, lm_head, norms, MoE routers and any vision tower stay BF16.

usage:
  python -m cloq.compress rtn   --src <hf snapshot dir> --out <dir> --wbits 4
  python -m cloq.compress gauss --src <hf snapshot dir> --out <dir> --k 0.3 --seed 1
  python -m cloq.compress nf4   --src <hf snapshot dir> --out <dir>
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


# bitsandbytes NF4 code (bitsandbytes/functional.py get_4bit_type("nf4"); QLoRA appendix E), ascending.
NF4_CODE = [-1.0, -0.6961928009986877, -0.5250730514526367, -0.39491748809814453, -0.28444138169288635,
            -0.18477343022823334, -0.09105003625154495, 0.0, 0.07958029955625534, 0.16093020141124725,
            0.24611230194568634, 0.33791524171829224, 0.44070982933044434, 0.5626170039176941,
            0.7229568362236023, 1.0]
NF4_BLOCK = 64
FP4_E2M1 = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]  # magnitudes; index parity = mantissa bit (RNE tie-break)
MX_BLOCK = 32
FP4_EMAX = 2  # exponent of the largest normal E2M1 value (6 = 1.5 * 2^2)


def _blocks(W: torch.Tensor, block: int) -> torch.Tensor:
    assert W.numel() % block == 0, f"numel {W.numel()} not a multiple of block {block}"
    return W.reshape(-1, block)  # row-major flat blocks, as bitsandbytes / MX do (== per-row groups when cols % block == 0)


@torch.no_grad()
def nf4_dequant(W: torch.Tensor, block: int = NF4_BLOCK) -> torch.Tensor:
    """bitsandbytes quantize_4bit(quant_type="nf4", blocksize=block) followed by dequantize_4bit, in fp32."""
    code = torch.tensor(NF4_CODE, device=W.device, dtype=torch.float32)
    mids = (code[1:] + code[:-1]) / 2  # bnb dQuantizeNF4: x > midpoint -> upper code
    blk = _blocks(W.float(), block)
    absmax = blk.abs().amax(-1, keepdim=True)
    inv = torch.where(absmax > 0, 1.0 / absmax, torch.zeros_like(absmax))  # bnb multiplies by 1/absmax
    idx = torch.bucketize(blk * inv, mids, right=False)
    return (code[idx] * absmax).reshape(W.shape)


@torch.no_grad()
def mxfp4_dequant(W: torch.Tensor, block: int = MX_BLOCK) -> torch.Tensor:
    """OCP MX v1.0 MXFP4 quantize + dequantize, in fp32."""
    grid = torch.tensor(FP4_E2M1, device=W.device, dtype=torch.float32)
    mids = (grid[1:] + grid[:-1]) / 2
    blk = _blocks(W.float(), block)
    amax = blk.abs().amax(-1, keepdim=True)
    _, e = torch.frexp(amax)  # amax = m * 2^e, m in [0.5, 1) -> floor(log2 amax) = e - 1 (exact)
    shared = torch.where(amax > 0, e - 1 - FP4_EMAX, torch.full_like(e, -127)).clamp(-127, 127)  # E8M0 range
    v = torch.ldexp(blk, -shared)  # exact: power-of-two scale
    a = v.abs().clamp(max=FP4_E2M1[-1])  # saturate to +-6
    idx = torch.bucketize(a, mids, right=False)  # at a tie this is the lower code ...
    tie = (idx < len(FP4_E2M1) - 1) & (a == mids[idx.clamp(max=len(FP4_E2M1) - 2)]) & (idx % 2 == 1)
    idx = idx + tie.long()  # ... round half to even (even index = even mantissa)
    return torch.ldexp(torch.sign(v) * grid[idx], shared).reshape(W.shape)


@torch.no_grad()
def rtnsr_dequant(W: torch.Tensor, wbits: int, g: torch.Generator, groupsize: int = GROUP) -> torch.Tensor:
    """rtn_dequant's grid (same scale/zero per 1 x groupsize block), stochastic instead of nearest rounding."""
    rows, cols = W.shape
    q = Quantizer(wbits, sym=False)
    assert cols % groupsize == 0, f"rtnsr needs cols % {groupsize} == 0"
    blk = W.reshape(rows * (cols // groupsize), groupsize)
    q.find_params(blk)
    u = torch.rand(blk.shape, generator=g, device=W.device, dtype=torch.float32)
    k = torch.clamp(torch.floor(blk / q.scale + q.zero + u), 0, q.maxq)
    return (q.scale * (k - q.zero)).reshape(rows, cols)


def tensor_seed(seed: int, name: str) -> int:
    return (int(seed) * 1_000_003 + zlib.crc32(name.encode())) % (2**63 - 1)


@torch.no_grad()
def perturb(name: str, W16: torch.Tensor, args, device: str) -> tuple[torch.Tensor, dict]:
    W = W16.to(device=device, dtype=torch.float32)
    if args.mode == "rtn":
        Q = rtn_dequant(W, args.wbits)
    elif args.mode == "rtnsr":
        g = torch.Generator(device=device).manual_seed(tensor_seed(args.seed, name))
        Q = rtnsr_dequant(W, args.wbits, g)
    elif args.mode == "nf4":
        Q = nf4_dequant(W)
    elif args.mode == "mxfp4":
        Q = mxfp4_dequant(W)
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
    ap.add_argument("mode", choices=["rtn", "gauss", "gshape", "rtnsign", "nf4", "mxfp4", "rtnsr"])
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
    if args.mode == "rtnsr":
        assert args.seed is not None, "rtnsr needs --seed"
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
    fmt = {"nf4": {"method": "NF4", "wbits": 4, "group_size": NF4_BLOCK, "sym": True,
                   "format": "bitsandbytes NF4 code, blockwise absmax (fp32, no double quant)"},
           "rtnsr": {"method": "RTN-stochastic", "wbits": args.wbits, "gauss_k": None, "sr_seed": args.seed,
                     "format": "rtn grid (g128 asym, Quantizer.find_params), q = clamp(floor(x/s + z + u)), u~U[0,1)"},
           "mxfp4": {"method": "MXFP4", "wbits": 4, "group_size": MX_BLOCK, "sym": True,
                     "format": "OCP MX v1.0: FP4 E2M1 (RNE, saturating) x shared E8M0 2^(floor(log2 amax)-2)"}}
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
    if args.mode in fmt:
        meta.update(fmt[args.mode])
    if not args.no_sha:
        meta["weight_files"] = {p.name: _sha256(p) for p in sorted(out.glob("*.safetensors"))}
    (out / "quantization.json").write_text(json.dumps(meta, indent=1))
    print(f"{args.mode} -> {out}: {n_target} tensors, mean rel err {meta['mean_rel_weight_err']:.5f}, {meta['seconds']:.0f}s")


if __name__ == "__main__":
    main()
