"""QuaRot-style residual-stream rotation of a dense Qwen3 / Llama checkpoint, streamed shard by shard.

Computational invariance (Ashkboos et al. 2024, QuaRot; Liu et al. 2025, SpinQuant): with an orthogonal Q and
RMSNorm (no mean subtraction), rms(x Q) = rms(x), so the network is unchanged if
  * every RMSNorm weight on the residual stream (input_layernorm, post_attention_layernorm, final norm) is fused
    into the linears that read it and set to 1,
  * readers of the stream (q/k/v, gate/up, lm_head) get W <- W diag(w_norm) Q,
  * writers to it (o_proj, down_proj) get W <- Q^T W, and the embedding table E <- E Q.
Qwen3's q_norm / k_norm act per head on the q/k projection *outputs*, whose basis is not rotated: unaffected.
A tied lm_head is untied (lm_head = E diag(w_final) Q differs from E Q) and config.json says so.

Q = diag(s) H_d / sqrt(d): H_d a Hadamard matrix (Sylvester 2^k, times Paley-I order 20 when d = 20 * 2^k, e.g.
2560 = q4, 5120 = q14), s i.i.d. random signs from --seed. Rotated weights are stored in the source dtype (bf16),
never un-rotated. --wbits applies RTN (g128 asym, cloq.compress.rtn_dequant) to the decoder linears of the
bf16-rounded rotated weights, i.e. rot_rtn = RTN(rot_bf16) exactly. GPTQ on the rotated model: run
cloq.quantize --src <rot_bf16 dir>.

usage:
  python -m cloq.rotate --src <hf snapshot dir> --out <dir> [--seed 0] [--wbits 4]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import time
from pathlib import Path

import torch
from safetensors import safe_open
from safetensors.torch import save_file

from cloq.compress import _sha256, is_target, rtn_dequant

LAYER_RE = re.compile(r"^model\.layers\.(\d+)\.(.+)$")
READ_IN = {"self_attn.q_proj.weight": "input_layernorm", "self_attn.k_proj.weight": "input_layernorm",
           "self_attn.v_proj.weight": "input_layernorm", "mlp.gate_proj.weight": "post_attention_layernorm",
           "mlp.up_proj.weight": "post_attention_layernorm"}
WRITE_OUT = {"self_attn.o_proj.weight", "mlp.down_proj.weight"}
NORMS = {"input_layernorm.weight", "post_attention_layernorm.weight"}
UNCHANGED = {"self_attn.q_norm.weight", "self_attn.k_norm.weight"}


def _paley20() -> torch.Tensor:
    """Hadamard matrix of order 20 (Paley construction I, q = 19 = 3 mod 4)."""
    q = 19
    sq = {(i * i) % q for i in range(1, q)}
    chi = lambda a: 0 if a % q == 0 else (1 if a % q in sq else -1)
    Qm = torch.tensor([[chi(j - i) for j in range(q)] for i in range(q)], dtype=torch.float64)
    S = torch.zeros(q + 1, q + 1, dtype=torch.float64)
    S[0, 1:] = 1
    S[1:, 0] = -1
    S[1:, 1:] = Qm
    return S + torch.eye(q + 1, dtype=torch.float64)


def hadamard(d: int) -> torch.Tensor:
    base = torch.ones(1, 1, dtype=torch.float64)
    n = d
    if d % 20 == 0 and (d // 20) & (d // 20 - 1) == 0:
        base, n = _paley20(), d // 20
    assert n & (n - 1) == 0, f"no Hadamard construction for d={d}"
    H = base
    h2 = torch.tensor([[1.0, 1.0], [1.0, -1.0]], dtype=torch.float64)
    while H.shape[0] < d:
        H = torch.kron(H, h2)
    assert H.shape[0] == d
    return H


def random_hadamard(d: int, seed: int) -> torch.Tensor:
    """Orthogonal Q = diag(s) H_d / sqrt(d) (float64)."""
    g = torch.Generator().manual_seed(int(seed))
    s = torch.randint(0, 2, (d,), generator=g, dtype=torch.int64).double() * 2 - 1
    Q = s[:, None] * hadamard(d) / d**0.5
    err = (Q @ Q.T - torch.eye(d, dtype=torch.float64)).abs().max().item()
    assert err < 1e-10, f"rotation not orthogonal: {err}"
    return Q


def _text_cfg(cfg: dict) -> dict:
    return cfg.get("text_config", cfg)


@torch.no_grad()
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--wbits", type=int, default=None, help="RTN g128 asym after rotation (default: none = rot_bf16)")
    ap.add_argument("--source-model", default=None)
    ap.add_argument("--source-revision", default=None)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--no-sha", action="store_true")
    args = ap.parse_args(argv)
    src, out = Path(args.src), Path(args.out)
    if (out / "quantization.json").exists():
        print(f"{out} exists; skipping")
        return
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    torch.backends.cuda.matmul.allow_tf32 = False
    cfg = json.load(open(src / "config.json"))
    tc = _text_cfg(cfg)
    d = int(tc["hidden_size"])
    assert not tc.get("num_experts") and not tc.get("attention_bias"), "rotation supports dense, bias-free layouts only"
    dev = args.device
    Q = random_hadamard(d, args.seed).to(dev, torch.float32)
    shards = sorted(src.glob("*.safetensors"))
    # pass 1: residual-stream norm weights (tiny) and where the embedding lives
    norms, embed_shard, has_head = {}, None, False
    for sh in shards:
        with safe_open(sh, framework="pt") as f:
            for n in f.keys():
                m = LAYER_RE.match(n)
                if (m and m.group(2) in NORMS) or n == "model.norm.weight":
                    norms[n] = f.get_tensor(n).to(dev, torch.float32)
                if n == "model.embed_tokens.weight":
                    embed_shard = sh
                has_head |= n == "lm_head.weight"
    tied = bool(tc.get("tie_word_embeddings", cfg.get("tie_word_embeddings", False)))
    assert tied or has_head, "untied config without lm_head.weight"
    assert embed_shard is not None and "model.norm.weight" in norms
    stats, n_rot, n_q, seen = {}, 0, 0, set()
    head_bytes = 0
    for sh in shards:
        tensors = {}
        with safe_open(sh, framework="pt") as f:
            meta = f.metadata()
            for name in f.keys():
                t = f.get_tensor(name)
                seen.add(name)
                m = LAYER_RE.match(name)
                sub = m.group(2) if m else None
                W = None
                if name == "model.embed_tokens.weight":
                    E = t.to(dev, torch.float32)
                    W = E @ Q
                    if tied:
                        H = (E * norms["model.norm.weight"][None, :]) @ Q
                        tensors["lm_head.weight"] = H.to(t.dtype).cpu()
                        head_bytes = tensors["lm_head.weight"].numel() * tensors["lm_head.weight"].element_size()
                        del H
                    del E
                elif name == "lm_head.weight" and tied:
                    continue  # redundant stored copy of a tied head; rebuilt from the embedding above
                elif name == "lm_head.weight":
                    W = (t.to(dev, torch.float32) * norms["model.norm.weight"][None, :]) @ Q
                elif sub in READ_IN:
                    w = norms[f"model.layers.{m.group(1)}.{READ_IN[sub]}.weight"]
                    W = (t.to(dev, torch.float32) * w[None, :]) @ Q
                elif sub in WRITE_OUT:
                    W = Q.T @ t.to(dev, torch.float32)
                elif sub in NORMS or name == "model.norm.weight":
                    t = torch.ones_like(t)
                elif sub in UNCHANGED:
                    pass
                else:
                    raise RuntimeError(f"rotate: unhandled tensor {name} {tuple(t.shape)}")
                if W is not None:
                    n_rot += 1
                    t = W.to(t.dtype)
                    if args.wbits and is_target(name):
                        R = t.to(dev, torch.float32)
                        Qw = rtn_dequant(R, args.wbits)
                        t = Qw.to(t.dtype)
                        err = t.float() - R
                        stats[name] = {"rel_weight_err": float((err**2).sum() / (R**2).sum().clamp_min(1e-12)),
                                       "err_fro": float(torch.linalg.vector_norm(err))}
                        n_q += 1
                    t = t.cpu()
                    del W
                tensors[name] = t
        save_file(tensors, str(out / sh.name), metadata=meta or {"format": "pt"})
        del tensors
    for p in src.iterdir():
        if p.suffix != ".safetensors" and p.is_file():
            shutil.copy(p, out / p.name)
    if tied:  # untie: config + shard index
        c = json.load(open(out / "config.json"))
        c["tie_word_embeddings"] = False
        if "text_config" in c:
            c["text_config"]["tie_word_embeddings"] = False
        (out / "config.json").write_text(json.dumps(c, indent=2))
        ix = out / "model.safetensors.index.json"
        if ix.exists():
            j = json.load(open(ix))
            j["weight_map"]["lm_head.weight"] = embed_shard.name
            if "total_size" in j.get("metadata", {}):
                j["metadata"]["total_size"] = int(j["metadata"]["total_size"]) + head_bytes
            ix.write_text(json.dumps(j, indent=2))
    if args.wbits:
        assert n_q > 0
    rels = [v["rel_weight_err"] for v in stats.values()]
    meta = {
        "method": "QuaRot-RTN" if args.wbits else "QuaRot-rotation",
        "wbits": args.wbits, "group_size": 128 if args.wbits else None, "sym": False if args.wbits else None,
        "rotation": {"kind": "random Hadamard diag(s) H_d / sqrt(d)", "d": d, "seed": args.seed,
                     "norms_fused": True, "untied_lm_head": tied, "stored": "rotated (not un-rotated)",
                     "rotated_tensors": n_rot},
        "source_model": args.source_model, "source_revision": args.source_revision, "source_dir": str(src),
        "storage": "fake-quant bf16", "n_quantized_tensors": n_q,
        "mean_rel_weight_err": (sum(rels) / len(rels)) if rels else 0.0, "seconds": time.time() - t0,
        "per_tensor": stats,
    }
    if not args.no_sha:
        meta["weight_files"] = {p.name: _sha256(p) for p in sorted(out.glob("*.safetensors"))}
    (out / "quantization.json").write_text(json.dumps(meta, indent=1))
    print(f"rotate(seed={args.seed}, wbits={args.wbits}) -> {out}: {n_rot} rotated, {n_q} quantized, tied={tied}, "
          f"{meta['seconds']:.0f}s")


if __name__ == "__main__":
    main()
