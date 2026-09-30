"""Local-precision restoration and quantization-residual dose checkpoints, derived from one fake-quant checkpoint Q
and its BF16 source W (execution plan P2, engineering line 3; protocol docs/insights/PERTURBATION_PROTOCOL.md).

Both builders stream the source shards (the model is never instantiated) and write the source safetensors layout, so
the result is served through the identical BF16 vLLM path as W and Q. They run on CPU: every value is produced by
separate IEEE fp32 ops (no fused kernels), so the output is identical on every node.

  restore  every decoder linear listed in an arm manifest is copied bit-for-bit from W, every other decoder linear
           bit-for-bit from Q. Arms (manifests/perturb/restore_v1/<model>/<arm>.json, written by `manifests`):
             early / middle / late   all 7 linears of the first / second / last third of the decoder layers
             attn / mlp              q,k,v,o (resp. gate,up,down) of every layer
             rand_<budget>_s<seed>   uniformly random linears whose BF16 parameter bytes match the structured arm(s)
                                     of that budget (third / attn / mlp) within RAND_TOL, seeds 1..3
             none / all              controls: bit-identical to Q / to W
  resid    W_a = W + a (W_Q - W) per decoder linear, fp32 then round-to-nearest BF16; a = 0 and a = 1 are the
           endpoint tensors themselves (bit-exactly W and Q). A residual intervention, not a bit width: a = 0.5 is not
           "W6" and a = 2 is not "W3".

Every non-target tensor (embeddings, norms, lm_head) is taken from W, after checking that Q's copy is bit-identical
(true for cloq.quantize gptq/awq and cloq.compress rtn outputs; rotated checkpoints are rejected).

usage:
  python -m cloq.perturb manifests --src <bf16 snapshot> --model q4 --revision <rev> --out-dir manifests/perturb/restore_v1/q4
  python -m cloq.perturb restore --src <bf16> --q <Q dir> --out <dir> --manifest <arm.json>
  python -m cloq.perturb resid   --src <bf16> --q <Q dir> --out <dir> --alpha 0.5
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import time
from pathlib import Path

import torch
from safetensors import safe_open
from safetensors.torch import save_file

from cloq.compress import GROUP, is_target

PROTOCOL = "perturb-v1"
MODULES = ["self_attn.q_proj", "self_attn.k_proj", "self_attn.v_proj", "self_attn.o_proj",
           "mlp.gate_proj", "mlp.up_proj", "mlp.down_proj"]
ATTN = MODULES[:4]
MLP = MODULES[4:]
KEY_RE = re.compile(r"layers\.(\d+)\.(self_attn\.[qkvo]_proj|mlp\.(?:gate|up|down)_proj)\.weight$")
RAND_TOL = 0.005  # pre-declared: |restored params(random) - restored params(structured)| <= 0.5% of the structured arm
SEEDS = (1, 2, 3)
ALPHAS = (0.0, 0.25, 0.5, 1.0, 2.0)

# Pre-declared simulated storage of a real (packed) W4 g128 asymmetric deployment of one [rows, cols] linear:
#   4-bit codes + per (row, 128-column group) one fp16 scale and one 4-bit zero point
#   + method side information: GPTQ act-order g_idx (int32 per input column); AWQ per-input-channel fp16 scale
#     (cloq.quantize folds it into the weight; a real kernel keeps it or folds it into the preceding op; counted).
# Restored linears are stored as BF16 (2 bytes / parameter), nothing else.
SCALE_BYTES, ZERO_BITS, CODE_BITS = 2, 4, 4
SIDE_BYTES_PER_COL = {"gptq": 4, "awq": 2, "rtn": 0}


def wq_bytes(rows: int, cols: int, method: str, bits: int = CODE_BITS) -> float:
    """Packed Wb g128 asym storage of one linear: b-bit codes + per (row, group) fp16 scale and b-bit zero + side info."""
    groups = rows * -(-cols // GROUP)
    return rows * cols * bits / 8 + groups * (SCALE_BYTES + bits / 8) + cols * SIDE_BYTES_PER_COL[method]


def w4_bytes(rows: int, cols: int, method: str) -> float:
    assert ZERO_BITS == CODE_BITS == 4
    return wq_bytes(rows, cols, method, 4)


def method_family(method: str | None) -> str:
    m = (method or "").lower()
    return "gptq" if "gptq" in m else "awq" if "awq" in m else "rtn"


def module_key(name: str) -> tuple[int, str]:
    m = KEY_RE.search(name)
    assert m, f"not a dense decoder linear: {name}"
    return int(m.group(1)), m.group(2)


def linear_shapes(src: Path) -> dict[str, tuple[int, int]]:
    """{tensor name: (rows, cols)} of every decoder linear, from the safetensors headers only (no weights read)."""
    out = {}
    for sh in sorted(Path(src).glob("*.safetensors")):
        with safe_open(sh, framework="pt") as f:
            for name in f.keys():
                if is_target(name):
                    shape = f.get_slice(name).get_shape()
                    if len(shape) == 2:
                        out[name] = (int(shape[0]), int(shape[1]))
    assert out, f"no decoder linears in {src}"
    assert not any("experts" in n for n in out), "MoE checkpoints are not supported by perturb-v1"
    return dict(sorted(out.items(), key=lambda kv: (module_key(kv[0])[0], MODULES.index(module_key(kv[0])[1]))))


def thirds(n_layers: int) -> list[list[int]]:
    """Equal-size contiguous thirds; with n % 3 != 0 the earlier thirds get the extra layer (numpy array_split)."""
    k, r = divmod(n_layers, 3)
    out, s = [], 0
    for i in range(3):
        e = s + k + (1 if i < r else 0)
        out.append(list(range(s, e)))
        s = e
    return out


def structured_arms(shapes: dict) -> dict[str, list[str]]:
    layers = sorted({module_key(n)[0] for n in shapes})
    assert layers == list(range(len(layers))), "non-contiguous layer indices"
    t = thirds(len(layers))
    sel = lambda pred: [n for n in shapes if pred(*module_key(n))]  # noqa: E731
    return {"none": [], "all": list(shapes),
            "early": sel(lambda l, m: l in t[0]), "middle": sel(lambda l, m: l in t[1]), "late": sel(lambda l, m: l in t[2]),
            "attn": sel(lambda l, m: m in ATTN), "mlp": sel(lambda l, m: m in MLP)}


def params(shapes: dict, names) -> int:
    return sum(shapes[n][0] * shapes[n][1] for n in names)


def random_arm(shapes: dict, target: int, key: str, tol: float = RAND_TOL, tries: int = 1000) -> list[str]:
    """Uniformly random decoder linears with sum(params) within tol*target of target (never above target + tol).

    random.Random(str) is seeded through sha512 of the string (Python >= 3.2), so the draw does not depend on
    PYTHONHASHSEED, the platform or the process. Try t uses key|t; the first try that lands within tolerance wins
    (random order, greedy fill with every module that still fits: the deficit ends below the smallest module)."""
    names = list(shapes)
    for t in range(tries):
        rng = random.Random(f"{key}|{t}")
        order = names[:]
        rng.shuffle(order)
        chosen, tot = [], 0
        for n in order:
            p = shapes[n][0] * shapes[n][1]
            if tot + p <= target:
                chosen.append(n)
                tot += p
        if abs(tot - target) <= tol * target:
            return sorted(chosen, key=lambda n: (module_key(n)[0], MODULES.index(module_key(n)[1])))
    raise RuntimeError(f"no random module set within {tol:.3%} of {target} params after {tries} tries ({key})")


def budget(shapes: dict, restored: list[str], method: str, bits: int = 4) -> dict:
    """Byte accounting for one arm (decoder linears only; embeddings/norms/lm_head are BF16 in every arm and in Q)."""
    rs = set(restored)
    p_all, p_rest = params(shapes, shapes), params(shapes, restored)
    w4_all = sum(wq_bytes(r, c, method, bits) for r, c in shapes.values())
    w4_kept = sum(wq_bytes(*shapes[n], method, bits) for n in shapes if n not in rs)
    sim = w4_kept + 2 * p_rest
    return {"n_linears": len(shapes), "n_restored": len(restored), "linear_params": p_all,
            "restored_params": p_rest, "restored_bf16_bytes": 2 * p_rest, "restored_param_frac": p_rest / p_all,
            "sim_storage_bytes": sim, "sim_storage_bytes_q": w4_all, "sim_storage_bytes_bf16": 2 * p_all,
            "sim_bits_per_linear_param": 8 * sim / p_all, "sim_overhead_vs_q": sim / w4_all - 1,
            "restored_by_module": {m: sum(1 for n in restored if module_key(n)[1] == m) for m in MODULES},
            "restored_layers": sorted({module_key(n)[0] for n in restored})}


def make_manifests(src: Path, model: str, revision: str, seeds=SEEDS) -> dict[str, dict]:
    """All restoration arm manifests of one model. Random families: one per distinct structured budget."""
    shapes = linear_shapes(src)
    arms = structured_arms(shapes)
    out = {}
    pt = [params(shapes, arms[a]) for a in ("early", "middle", "late")]
    fam = {"third": ["early", "middle", "late"]} if len(set(pt)) == 1 else {a: [a] for a in ("early", "middle", "late")}
    fam.update({"attn": ["attn"], "mlp": ["mlp"]})  # one random family per distinct structured budget
    for a, names in arms.items():
        out[a] = {"arm": a, "family": "control" if a in ("none", "all") else "structured", "modules": names, "seed": None}
    for b, members in fam.items():
        target = params(shapes, arms[members[0]])
        for s in seeds:
            key = f"cloq-{PROTOCOL}|restore|{model}|{revision}|{b}|{s}"
            names = random_arm(shapes, target, key)
            out[f"rand_{b}_s{s}"] = {"arm": f"rand_{b}_s{s}", "family": "random", "matched_to": members,
                                     "target_restored_params": target, "seed": s, "rng_key": key, "tol": RAND_TOL,
                                     "delta_params": params(shapes, names) - target,
                                     "delta_frac": (params(shapes, names) - target) / target, "modules": names}
    for a, m in out.items():
        m.update({"protocol": PROTOCOL, "model": model, "source_revision": revision,
                  "n_layers": len({module_key(n)[0] for n in shapes}),
                  "budget": {meth: budget(shapes, m["modules"], meth) for meth in SIDE_BYTES_PER_COL},
                  # W3 bases (damage regime, W50): same module sets (matched on BF16 parameter bytes, which do not
                  # depend on the base's bit width), budgets recomputed with 3-bit codes and 3-bit zero points
                  "budget_w3": {meth: budget(shapes, m["modules"], meth, 3) for meth in SIDE_BYTES_PER_COL},
                  "budget_rule": "W4 g128 asym: 4-bit codes + fp16 scale + 4-bit zero per (row, 128 cols) + GPTQ g_idx int32 "
                                 "per input col / AWQ fp16 per input col; restored linears BF16 (2 B/param)",
                  "budget_w3_rule": "as budget_rule with 3-bit codes and 3-bit zero points (W3 g128 asym base)"})
        m["modules_sha256"] = hashlib.sha256("\n".join(m["modules"]).encode()).hexdigest()
    return out


# ---------------------------------------------------------------------------------------------------- builders

def _bits(t: torch.Tensor) -> torch.Tensor:
    return t.contiguous().view(torch.uint8)


def same_bits(a: torch.Tensor, b: torch.Tensor) -> bool:
    return a.dtype == b.dtype and a.shape == b.shape and torch.equal(_bits(a), _bits(b))


def resid_tensor(W16: torch.Tensor, Q16: torch.Tensor, alpha: float) -> torch.Tensor:
    """W + alpha (Q - W): three separate fp32 ops, one RNE cast. alpha in {0, 1}: the endpoint tensor itself."""
    if alpha == 0:
        return W16.clone()
    if alpha == 1:
        return Q16.clone()
    W = W16.float()
    D = Q16.float() - W
    D = D * float(alpha)
    return (W + D).to(W16.dtype)


class ContentHash:
    """sha256 over (name, dtype, shape, raw bytes) of every tensor, in name order: independent of shard layout."""

    def __init__(self):
        self.items = {}

    def add(self, name: str, t: torch.Tensor):
        h = hashlib.sha256(f"{name}|{t.dtype}|{tuple(t.shape)}|".encode())
        h.update(_bits(t).numpy())
        self.items[name] = h.digest()

    def hexdigest(self) -> str:
        h = hashlib.sha256()
        for n in sorted(self.items):
            h.update(self.items[n])
        return h.hexdigest()


def build(src: Path, q: Path, out: Path, mode: str, restored: list[str] | None = None, alpha: float | None = None) -> dict:
    src, q, out = Path(src), Path(q), Path(out)
    shards = sorted(p.name for p in src.glob("*.safetensors"))
    assert shards and shards == sorted(p.name for p in q.glob("*.safetensors")), "W and Q shard layouts differ"
    qmeta = json.load(open(q / "quantization.json")) if (q / "quantization.json").exists() else {}
    assert "rotation" not in json.dumps({k: v for k, v in qmeta.items() if k not in ("per_tensor", "stats")}).lower(), \
        "rotated checkpoints differ from W outside the linears; not supported"
    rs = set(restored or [])
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    ch = ContentHash()
    n_target, n_rest, eq_w, eq_q, left = 0, 0, True, True, set(rs)
    dose_num = dose_den = move_num = 0.0
    per = {}
    for sh in shards:
        tensors = {}
        with safe_open(src / sh, framework="pt") as fw, safe_open(q / sh, framework="pt") as fq:
            assert set(fw.keys()) == set(fq.keys()), f"{sh}: W and Q tensor names differ"
            smeta = fw.metadata()
            for name in fw.keys():
                w, qt = fw.get_tensor(name), fq.get_tensor(name)
                if is_target(name) and w.dim() == 2:
                    n_target += 1
                    if mode == "restore":
                        t = w if name in rs else qt
                        n_rest += name in rs
                        left.discard(name)
                    else:
                        t = resid_tensor(w, qt, alpha)
                        e = qt.float() - w.float()
                        d = t.float() - w.float()
                        e2 = float((e * e).sum())
                        dose_num += float((d * e).sum())
                        dose_den += e2
                        move_num += float((d * d).sum())
                        per[name] = {"eff_alpha": float((d * e).sum()) / e2 if e2 > 0 else None,
                                     "rel_move": (float((d * d).sum()) / max(float((w.float() ** 2).sum()), 1e-30)) ** 0.5}
                else:
                    if not same_bits(w, qt):
                        raise RuntimeError(f"Q differs from W outside the decoder linears ({name}); not a mixable pair")
                    t = w
                eq_w &= same_bits(t, w)
                eq_q &= same_bits(t, qt)
                ch.add(name, t)
                tensors[name] = t
        save_file(tensors, str(out / sh), metadata=smeta or {"format": "pt"})
        del tensors
    assert not left, f"{len(left)} restored modules not found, e.g. {sorted(left)[:3]}"
    assert n_target > 0
    for p in src.iterdir():
        if p.suffix != ".safetensors" and p.is_file():
            shutil.copy(p, out / p.name)
    base = {k: v for k, v in qmeta.items() if k not in ("per_tensor", "stats", "weight_files")}
    meta = {"protocol": PROTOCOL, "storage": "fake-quant bf16", "n_decoder_linears": n_target,
            "base": base, "base_method": qmeta.get("method"), "source_model": qmeta.get("source_model"),
            "source_revision": qmeta.get("source_revision"), "source_dir": str(src), "q_dir": str(q),
            "content_sha256": ch.hexdigest(), "equals": "bf16" if eq_w else "q" if eq_q else None,
            "seconds": time.time() - t0}
    if mode == "restore":
        meta.update({"method": "restore", "wbits": None, "n_restored": n_rest,
                     "note": "local precision restoration: listed linears BF16 (from W), all others from Q; bit copies"})
    else:
        meta.update({"method": "residual-dose", "wbits": None, "alpha": alpha,
                     "note": "residual intervention W + alpha (W_Q - W) on every decoder linear; NOT a bit width",
                     "eff_alpha": dose_num / dose_den if dose_den else None,
                     "rel_residual_move": (move_num / dose_den) ** 0.5 if dose_den else None,
                     "per_tensor": per})
    (out / "quantization.json").write_text(json.dumps(meta, indent=1))
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["manifests", "restore", "resid"])
    ap.add_argument("--src", required=True)
    ap.add_argument("--q")
    ap.add_argument("--out")
    ap.add_argument("--manifest")
    ap.add_argument("--alpha", type=float)
    ap.add_argument("--model")
    ap.add_argument("--revision")
    ap.add_argument("--out-dir")
    ap.add_argument("--extra-meta", default="{}", help="json merged into quantization.json (worker: spec, tag, base sha)")
    a = ap.parse_args()
    torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
    if a.mode == "manifests":
        od = Path(a.out_dir)
        od.mkdir(parents=True, exist_ok=True)
        for arm, m in make_manifests(Path(a.src), a.model, a.revision).items():
            p = od / f"{arm}.json"
            if p.exists() and json.load(open(p))["modules_sha256"] != m["modules_sha256"]:
                raise SystemExit(f"{p} exists with a different module set; manifests are frozen, not regenerated")
            p.write_text(json.dumps(m, indent=1))
            b = m["budget"]["gptq"]
            print(f"{arm:16s} n={b['n_restored']:3d} params={b['restored_params']:>11d} frac={b['restored_param_frac']:.4f} "
                  f"sim_bits={b['sim_bits_per_linear_param']:.3f} delta={m.get('delta_frac', 0):+.5f}")
        return
    out = Path(a.out)
    if (out / "quantization.json").exists():
        print(f"{out} exists; skipping")
        return
    if a.mode == "restore":
        man = json.load(open(a.manifest))
        assert hashlib.sha256("\n".join(man["modules"]).encode()).hexdigest() == man["modules_sha256"], "manifest corrupted"
        meta = build(Path(a.src), Path(a.q), out, "restore", restored=man["modules"])
        meta.update({"arm": man["arm"], "family": man["family"], "seed": man.get("seed"), "manifest": a.manifest,
                     "manifest_modules_sha256": man["modules_sha256"],
                     "budget": man["budget" if (meta.get("base") or {}).get("wbits", 4) == 4 else f"budget_w{meta['base']['wbits']}"][
                         method_family(meta.get("base_method"))]})
        exp = {"none": "q", "all": "bf16"}.get(man["arm"])
        assert meta["equals"] == exp or (exp is None and meta["equals"] is None), f"arm {man['arm']}: equals={meta['equals']}"
    else:
        assert a.alpha is not None
        meta = build(Path(a.src), Path(a.q), out, "resid", alpha=a.alpha)
        exp = {0.0: "bf16", 1.0: "q"}.get(a.alpha)
        assert meta["equals"] == exp, f"alpha {a.alpha}: equals={meta['equals']} (expected {exp})"
    meta.update(json.loads(a.extra_meta))
    (out / "quantization.json").write_text(json.dumps(meta, indent=1))
    print(f"{a.mode} -> {out}: equals={meta['equals']} content={meta['content_sha256'][:16]} {meta['seconds']:.0f}s")


if __name__ == "__main__":
    main()
