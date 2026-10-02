"""QuaRot (Ashkboos et al., NeurIPS 2024; github.com/spcl/QuaRot fake_quant) offline half, as a fake-quant BF16
checkpoint for a dense Qwen3 / Llama model. The online half runs at serving time in vLLM:
  scripts/a6000/pyhooks/cloq_aq.py   CLOQ_AQ_HAD=quarot: Hadamard on the down_proj input (online_full_had) and across
                                     heads on the o_proj input (online_partial_had); CLOQ_AQ_BITS=4 CLOQ_AQ_CLIP=0.9:
                                     per-token symmetric INT4 inputs of every decoder linear.
  scripts/a6000/pyhooks/cloq_kvq.py  CLOQ_KVQ_ROT=qk: per-head Hadamard of q and k after RoPE; CLOQ_KVQ_BITS=4
                                     CLOQ_KVQ_FMT=quarot CLOQ_KVQ_KCLIP=0.95 CLOQ_KVQ_VCLIP=0.95: asymmetric K/V, group
                                     = head_dim.
docs/insights/METHOD_FIDELITY.md compares every step with the reference (rotation_utils.py, hadamard_utils.py,
quant_utils.py, gptq_utils.py, main.py).

Offline transforms (one fp64 pass per tensor, one bf16 rounding):
  fuse_layer_norms   RMSNorm weights folded into q/k/v, gate/up and lm_head, norms set to 1 (the reference also
                     subtracts the embedding mean, a LayerNorm step that changes an RMSNorm model; not done here).
  rotate_model       random Hadamard Q = diag(s) H_d / sqrt(d) (cloq.rotate.random_hadamard, seed): embed E Q,
                     readers W Q, writers Q^T W, lm_head W Q (a tied lm_head is untied).
  rotate_ov_proj     v_proj output: per-head Hadamard H_hd (apply_exact_had_to_linear(v, head_dim, output=True));
                     o_proj input: full Hadamard (apply_exact_had_to_linear(o, -1, output=False)).
  rotate_mlp_output  down_proj input: full Hadamard H_K kron H_{n/K} (n = intermediate), cloq.aq.had_transform.
Weights (w_bits < 16): per output channel, symmetric, clip ratio from the MSE grid search (WeightQuantizer, w_clip):
  --wmethod rtn   QuaRot-RTN (rtn_fwrd)
  --wmethod gptq  QuaRot (gptq_fwrd: GPTQ on the transformed model with the online Hadamards applied to the captured
                  inputs, 128 x 2048-token WikiText-2 train windows, random.seed(0), percdamp 0.01, act_order off,
                  true-sequential groups k,v,q -> o -> up,gate -> down, inputs propagated through quantized layers).
lm_head, embeddings, norms stay BF16 (lm_head quantization is skipped in the reference too).

SpinQuant (W99r): --rotations R.pt (cloq.spinquant learn) replaces the random Hadamard R1 and the per-head H_hd by the
learned R1 / per-layer R2 and keeps everything else (online Hadamards, GPTQ, calibration), so SpinQuant and QuaRot
differ only in the rotation (tests/test_spinquant.py; analysis/fork/rot_gate/GATE.md).

usage: python -m cloq.quarot --src <hf snapshot> --out <dir> [--wbits 4 --wmethod rtn|gptq] [--seed 0]
                             [--rotations R.pt --rotations-sha256 <sha>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import time
from pathlib import Path

import numpy as np
import torch
from safetensors import safe_open
from safetensors.torch import save_file

from cloq.aq import had_factor, had_heads, had_transform, hadK_list, quarot_weight_params, quarot_weight_qdq
from cloq.rotate import LAYER_RE, NORMS, READ_IN, UNCHANGED, WRITE_OUT, _text_cfg, random_hadamard

WIKITEXT = Path("/data/ziyangs/cloq_work/data/wikitext2/wikitext-train.arrow")
LIN = ("self_attn.q_proj", "self_attn.k_proj", "self_attn.v_proj", "self_attn.o_proj", "mlp.gate_proj", "mlp.up_proj",
       "mlp.down_proj")
SEQUENTIAL = [["self_attn.k_proj", "self_attn.v_proj", "self_attn.q_proj"], ["self_attn.o_proj"],
              ["mlp.up_proj", "mlp.gate_proj"], ["mlp.down_proj"]]


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 24), b""):
            h.update(c)
    return h.hexdigest()


def load_rotations(path: Path, d: int, hd: int, n_layers: int, sha256: str | None = None) -> tuple[torch.Tensor, list, dict]:
    """Learned rotations (cloq.spinquant learn -> R.pt: {"R1": [d, d], "R2": [n_layers x [hd, hd]]}), fp64 and
    projected onto the orthogonal group (polar factor U V^T of the SVD; the fp32 Cayley iterates drift ~1e-6 from it).
    Returns (R1, [R2_l], provenance)."""
    raw = Path(path).read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if sha256 and got != sha256:
        raise SystemExit(f"rotations {path}: sha256 {got} != expected {sha256}")
    R = torch.load(path, map_location="cpu")
    R1 = R["R1"].to(torch.float64)
    R2 = [r.to(torch.float64) for r in R["R2"]]
    assert R1.shape == (d, d) and len(R2) == n_layers and all(r.shape == (hd, hd) for r in R2), "rotation shapes"

    def polar(M):
        U, _, Vh = torch.linalg.svd(M)
        return U @ Vh

    I_d, I_h = torch.eye(d, dtype=torch.float64), torch.eye(hd, dtype=torch.float64)
    pre = {"R1": float((R1 @ R1.T - I_d).abs().max()), "R2_max": max(float((r @ r.T - I_h).abs().max()) for r in R2)}
    R1p, R2p = polar(R1), [polar(r) for r in R2]
    prov = {"path": str(path), "sha256": got, "orth_err_stored": pre,
            "polar_shift_max": {"R1": float((R1p - R1).abs().max()), "R2": max(float((a - b).abs().max()) for a, b in zip(R2p, R2))},
            "orth_err_used": {"R1": float((R1p @ R1p.T - I_d).abs().max()),
                              "R2_max": max(float((r @ r.T - I_h).abs().max()) for r in R2p)},
            "learn_meta": R.get("meta")}
    return R1p, R2p, prov


@torch.no_grad()
def transform(src: Path, out: Path, seed: int, dev: str, wbits: int | None, log, rotations: tuple | None = None) -> dict:
    """Streamed offline QuaRot transforms (+ optional QuaRot-RTN). Writes bf16 shards to out.
    rotations = (R1, [R2_l]) (load_rotations): SpinQuant's learned R1 replaces the random Hadamard Q, and the per-layer
    learned R2 replaces QuaRot's per-head H_hd on the v_proj output and on the o_proj input, keeping the rest of the
    QuaRot skeleton (across-head H_nh on the o_proj input, offline + online; H_K kron H_{n/K} on the down_proj input).
    With R1 = random_hadamard(d, seed) and R2 = H_hd / sqrt(hd) this is exactly the QuaRot transform
    (tests/test_spinquant.py)."""
    cfg = json.load(open(src / "config.json"))
    tc = _text_cfg(cfg)
    d, nh, n_kv = int(tc["hidden_size"]), int(tc["num_attention_heads"]), int(tc["num_key_value_heads"])
    hd = int(tc.get("head_dim") or d // nh)
    inter = int(tc["intermediate_size"])
    assert not tc.get("num_experts") and not tc.get("attention_bias"), "dense, bias-free layouts only"
    assert hd & (hd - 1) == 0 and nh & (nh - 1) == 0, "QuaRot's per-head / across-head Hadamards need powers of 2"
    K, HK = had_factor(inter)
    HKl = hadK_list(K, HK)
    Q = (rotations[0] if rotations else random_hadamard(d, seed)).to(dev, torch.float64)
    R2s = [r.to(dev, torch.float64) for r in rotations[1]] if rotations else None
    shards = sorted(src.glob("*.safetensors"))
    norms, embed_shard, has_head = {}, None, False
    for sh in shards:
        with safe_open(sh, framework="pt") as f:
            for n in f.keys():
                m = LAYER_RE.match(n)
                if (m and m.group(2) in NORMS) or n == "model.norm.weight":
                    norms[n] = f.get_tensor(n).to(dev, torch.float64)
                if n == "model.embed_tokens.weight":
                    embed_shard = sh
                has_head |= n == "lm_head.weight"
    tied = bool(tc.get("tie_word_embeddings", cfg.get("tie_word_embeddings", False)))
    assert tied or has_head
    stats, head_bytes, n_rot, n_q = {}, 0, 0, 0
    for sh in shards:
        tensors = {}
        with safe_open(sh, framework="pt") as f:
            meta = f.metadata()
            for name in f.keys():
                t = f.get_tensor(name)
                m = LAYER_RE.match(name)
                sub = m.group(2) if m else None
                W = None
                if name == "model.embed_tokens.weight":
                    E = t.to(dev, torch.float64)
                    W = E @ Q
                    if tied:
                        tensors["lm_head.weight"] = ((E * norms["model.norm.weight"][None, :]) @ Q).to(t.dtype).cpu()
                        head_bytes = tensors["lm_head.weight"].numel() * tensors["lm_head.weight"].element_size()
                    del E
                elif name == "lm_head.weight" and tied:
                    continue
                elif name == "lm_head.weight":
                    W = (t.to(dev, torch.float64) * norms["model.norm.weight"][None, :]) @ Q
                elif sub in READ_IN:
                    w = norms[f"model.layers.{m.group(1)}.{READ_IN[sub]}.weight"]
                    W = (t.to(dev, torch.float64) * w[None, :]) @ Q
                    if sub == "self_attn.v_proj.weight" and R2s is not None:  # SpinQuant R2: v_h <- v_h R2
                        W = (R2s[int(m.group(1))].T @ W.reshape(n_kv, hd, d)).reshape(n_kv * hd, d)
                    elif sub == "self_attn.v_proj.weight":  # rotate_ov_proj: H_hd on each kv head's output rows
                        Wv = W.reshape(n_kv, hd, d).transpose(1, 2)  # (kv, d, hd)
                        W = had_transform(Wv, 1, None).transpose(1, 2).reshape(n_kv * hd, d)
                elif sub in WRITE_OUT:
                    W = Q.T @ t.to(dev, torch.float64)
                    if sub == "self_attn.o_proj.weight" and R2s is not None:  # W (H_nh kron R2): R2 per head, H_nh across
                        assert W.shape[1] == nh * hd
                        W = had_heads((W.reshape(-1, nh, hd) @ R2s[int(m.group(1))]).reshape(-1, nh * hd), nh)
                    elif sub == "self_attn.o_proj.weight":  # rotate_ov_proj: full Hadamard on the input dim
                        assert W.shape[1] == nh * hd
                        W = had_transform(W, 1, None)
                    else:  # rotate_mlp_output: exact Hadamard on the down_proj input dim
                        assert W.shape[1] == inter
                        W = had_transform(W, K, HKl)
                elif sub in NORMS or name == "model.norm.weight":
                    t = torch.ones_like(t)
                elif sub in UNCHANGED:
                    pass
                else:
                    raise RuntimeError(f"quarot: unhandled tensor {name} {tuple(t.shape)}")
                if W is not None:
                    n_rot += 1
                    t = W.to(t.dtype)
                    if wbits and sub is not None and any(sub == n + ".weight" for n in LIN):
                        R = t.to(dev, torch.float32)
                        s, z, maxq = quarot_weight_params(R, wbits, sym=True, mse=True)
                        t = quarot_weight_qdq(R, s, z, maxq, sym=True).to(t.dtype)
                        err = t.float() - R
                        stats[name] = {"rel_weight_err": float((err ** 2).sum() / (R ** 2).sum().clamp_min(1e-12)),
                                       "mean_clip": float((s[:, 0] * maxq / R.abs().amax(1).clamp_min(1e-5)).mean())}
                        n_q += 1
                    t = t.cpu()
                    del W
                tensors[name] = t
        save_file(tensors, str(out / sh.name), metadata=meta or {"format": "pt"})
        log(f"shard {sh.name} done")
    for p in src.iterdir():
        if p.suffix != ".safetensors" and p.is_file():
            shutil.copy(p, out / p.name)
    if tied:
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
    return {"d": d, "num_heads": nh, "head_dim": hd, "num_kv_heads": n_kv, "intermediate": inter, "down_had_K": K,
            "tied_untied": tied, "rotated_tensors": n_rot, "rtn_quantized": n_q, "per_tensor": stats}


def add_online_had(model, K: int, HKl, nh: int) -> list:
    """Forward pre-hooks = the serving hook's online Hadamards (fp32, cast back to the activation dtype)."""
    hs = []
    for layer in model.model.layers:
        hs.append(layer.mlp.down_proj.register_forward_pre_hook(
            lambda m, a: (had_transform(a[0].float(), K, HKl).to(a[0].dtype),) + tuple(a[1:])))
        hs.append(layer.self_attn.o_proj.register_forward_pre_hook(
            lambda m, a: (had_heads(a[0].float(), nh).to(a[0].dtype),) + tuple(a[1:])))
    return hs


def wikitext_windows(tok, n: int, seqlen: int, seed: int) -> list[list[int]]:
    """QuaRot data_utils.get_wikitext2 (train): '\\n\\n'.join(text), random.seed(seed), n windows of seqlen."""
    import pyarrow as pa
    t = pa.ipc.open_stream(open(WIKITEXT, "rb")).read_all()
    ids = tok("\n\n".join(t.column("text").to_pylist()), return_tensors="pt").input_ids[0]
    random.seed(seed)
    out = []
    for _ in range(n):
        i = random.randint(0, ids.shape[0] - seqlen - 1)
        out.append(ids[i:i + seqlen].tolist())
    return out


@torch.no_grad()
def gptq_solve(W: torch.Tensor, H: torch.Tensor, bits: int, percdamp: float = 0.01, blocksize: int = 128) -> tuple[torch.Tensor, dict]:
    """QuaRot gptq_utils.GPTQ.fasterquant with groupsize -1, act_order off, WeightQuantizer(perchannel, sym, mse)."""
    W = W.clone().float()
    cols = W.shape[1]
    s, z, maxq = quarot_weight_params(W, bits, sym=True, mse=True)  # quantizer.find_params(W) before the loop
    dead = torch.diag(H) == 0
    H[dead, dead] = 1
    W[:, dead] = 0
    damp = percdamp * torch.mean(torch.diag(H))
    diag = torch.arange(cols, device=W.device)
    H[diag, diag] += damp
    H = torch.linalg.cholesky(H)
    H = torch.cholesky_inverse(H)
    Hinv = torch.linalg.cholesky(H, upper=True)
    Q = torch.zeros_like(W)
    loss = 0.0
    for i1 in range(0, cols, blocksize):
        i2 = min(i1 + blocksize, cols)
        W1 = W[:, i1:i2].clone()
        Q1 = torch.zeros_like(W1)
        Err1 = torch.zeros_like(W1)
        Hinv1 = Hinv[i1:i2, i1:i2]
        for i in range(i2 - i1):
            w = W1[:, i]
            dd = Hinv1[i, i]
            q = quarot_weight_qdq(w.unsqueeze(1), s, z, maxq, sym=True).flatten()
            Q1[:, i] = q
            loss += float(((w - q) ** 2 / dd ** 2).sum()) / 2
            err1 = (w - q) / dd
            W1[:, i:] -= err1.unsqueeze(1).matmul(Hinv1[i, i:].unsqueeze(0))
            Err1[:, i] = err1
        Q[:, i1:i2] = Q1
        W[:, i2:] -= Err1.matmul(Hinv[i1:i2, i2:])
    assert torch.isfinite(Q).all(), "NaN in GPTQ weights"
    return Q, {"gptq_loss": loss, "damp": float(damp)}


@torch.no_grad()
def run_gptq(rot_dir: Path, info: dict, bits: int, nsamples: int, seqlen: int, seed: int, dev: str, log) -> tuple[dict, dict, dict]:
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from cloq.gptq import GPTQLinear
    from cloq.quantize import capture_layer0_inputs

    tok = AutoTokenizer.from_pretrained(rot_dir)
    model = AutoModelForCausalLM.from_pretrained(rot_dir, dtype=torch.bfloat16, attn_implementation="sdpa").eval()
    model.config.use_cache = False
    K, HK = had_factor(info["intermediate"])
    hooks = add_online_had(model, K, hadK_list(K, HK), info["num_heads"])
    seqs = wikitext_windows(tok, nsamples, seqlen, seed)
    calib = {"source": "WikiText-2 raw v1 train (Salesforce/wikitext arrow)", "source_sha256": _sha256(WIKITEXT),
             "rule": "'\\n\\n'.join(text) tokenized; random.seed(seed); randint windows", "seed": seed,
             "n_samples": nsamples, "seq_len": seqlen, "n_tokens": nsamples * seqlen,
             "token_ids_sha256": hashlib.sha256(np.asarray(seqs, dtype=np.int64).tobytes()).hexdigest()}
    inputs = capture_layer0_inputs(model, seqs, dev, offload=False)
    new, stats = {}, {}
    t0 = time.time()
    for li, layer in enumerate(model.model.layers):
        layer.to(dev)
        for group in SEQUENTIAL:
            mods = {n: layer.get_submodule(n) for n in group}
            helpers = {n: GPTQLinear(mods[n]) for n in group}
            hs = [mods[n].register_forward_hook(lambda m, i, o, _n=n: helpers[_n].add_batch(i[0])) for n in group]
            for hid, kw in inputs.iter(dev):
                layer(hid, **kw)
            for h in hs:
                h.remove()
            for n in group:
                W0 = mods[n].weight.detach().float()
                Q, st = gptq_solve(W0, helpers[n].H, bits)
                helpers[n].H = None
                mods[n].weight.data.copy_(Q.to(mods[n].weight.dtype))
                st["rel_weight_err"] = float(((mods[n].weight.float() - W0) ** 2).sum() / (W0 ** 2).sum().clamp_min(1e-12))
                stats[f"model.layers.{li}.{n}.weight"] = st
                new[f"model.layers.{li}.{n}.weight"] = mods[n].weight.detach().cpu().clone()
            del helpers
        items = []
        for i, (hid, kw) in enumerate(inputs.iter(dev)):
            o = layer(hid, **kw)
            items.append(((o[0] if isinstance(o, tuple) else o).detach(), inputs.items[i][1]))
        inputs.items = items
        layer.cpu()
        torch.cuda.empty_cache()
        log(f"gptq layer {li} ({time.time() - t0:.0f}s) mean rel err "
            f"{np.mean([v['rel_weight_err'] for k, v in stats.items() if k.startswith(f'model.layers.{li}.')]):.4f}")
    for h in hooks:
        h.remove()
    return new, stats, calib


@torch.no_grad()
def invariance_check(src: Path, rot_dir: Path, info: dict, dev: str, n: int = 4, seqlen: int = 512) -> dict:
    """HF forward, bf16 and fp32 compute: original vs transformed + online Hadamards (16-bit weights). Next-token
    log-probs on n WikiText windows (seed 1, disjoint use from GPTQ's seed 0)."""
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(src)
    seqs = wikitext_windows(tok, n, seqlen, 1)
    res = {}
    for dt in (torch.float32, torch.bfloat16):
        lps = []
        for which in (src, rot_dir):
            m = AutoModelForCausalLM.from_pretrained(which, dtype=dt, attn_implementation="sdpa").to(dev).eval()
            hs = []
            if which == rot_dir:
                K, HK = had_factor(info["intermediate"])
                hs = add_online_had(m, K, hadK_list(K, HK), info["num_heads"])
            lps.append([torch.log_softmax(m(torch.tensor([s], device=dev)).logits[0].float(), -1).cpu() for s in seqs])
            for h in hs:
                h.remove()
            del m
            torch.cuda.empty_cache()
        a, b = torch.cat(lps[0]), torch.cat(lps[1])
        top = a.argmax(-1)
        d = (a.gather(-1, top[:, None]) - b.gather(-1, top[:, None])).abs()
        res[str(dt).split(".")[-1]] = {"positions": int(a.shape[0]), "top1_agreement": float((top == b.argmax(-1)).float().mean()),
                                       "mean_abs_dlogprob_top1": float(d.mean()), "max_abs_dlogprob_top1": float(d.max())}
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0, help="rotation seed")
    ap.add_argument("--wbits", type=int, default=16)
    ap.add_argument("--wmethod", choices=["rtn", "gptq"], default="gptq")
    ap.add_argument("--nsamples", type=int, default=128)
    ap.add_argument("--seqlen", type=int, default=2048)
    ap.add_argument("--calib-seed", type=int, default=0)
    ap.add_argument("--check", action="store_true", help="HF invariance check of the transforms (16-bit weights)")
    ap.add_argument("--rotations", default=None, help="SpinQuant learned R1/R2 (cloq.spinquant learn -> R.pt)")
    ap.add_argument("--rotations-sha256", default=None)
    ap.add_argument("--source-model", default=None)
    ap.add_argument("--source-revision", default=None)
    ap.add_argument("--no-sha", action="store_true")
    a = ap.parse_args(argv)
    src, out = Path(a.src), Path(a.out)
    if (out / "quantization.json").exists():
        print(f"{out} exists; skipping")
        return
    torch.backends.cuda.matmul.allow_tf32 = False
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    t0 = time.time()
    log = lambda s: print(f"[quarot {time.time() - t0:.0f}s] {s}", flush=True)  # noqa: E731
    out.mkdir(parents=True, exist_ok=True)
    rtn = a.wbits < 16 and a.wmethod == "rtn"
    gptq = a.wbits < 16 and a.wmethod == "gptq"
    stage = out.parent / (out.name + "_rot16") if gptq else out
    stage.mkdir(parents=True, exist_ok=True)
    rots, rot_prov = None, None
    if a.rotations:
        tc = _text_cfg(json.load(open(src / "config.json")))
        hd = int(tc.get("head_dim") or int(tc["hidden_size"]) // int(tc["num_attention_heads"]))
        R1, R2, rot_prov = load_rotations(Path(a.rotations), int(tc["hidden_size"]), hd, int(tc["num_hidden_layers"]),
                                          a.rotations_sha256)
        rots = (R1, R2)
        log(f"learned rotations {a.rotations} sha {rot_prov['sha256'][:12]} orth {rot_prov['orth_err_stored']}")
    info = transform(src, stage, a.seed, dev, a.wbits if rtn else None, log, rots)
    check = invariance_check(src, stage, info, dev) if (a.check and not rtn) else None
    calib, wstats = None, info.pop("per_tensor")
    if gptq:
        from cloq.quantize import write_checkpoint
        new, wstats, calib = run_gptq(stage, info, a.wbits, a.nsamples, a.seqlen, a.calib_seed, dev, log)
        write_checkpoint(stage, out, new, None, {"tmp": True}, sha=False)
        (out / "quantization.json").unlink()  # the final record is written below
        shutil.rmtree(stage, ignore_errors=True)
    rels = [v["rel_weight_err"] for v in wstats.values()]
    wq = None if a.wbits >= 16 else {
        "bits": a.wbits, "method": "GPTQ" if gptq else "RTN", "granularity": "per output channel", "sym": True,
        "maxq": 2 ** (a.wbits - 1) - 1, "clip": "MSE grid search (norm 2.4, grid 100, maxshrink 0.8) = --w_clip",
        "gptq": {"percdamp": 0.01, "blocksize": 128, "act_order": False, "groupsize": -1,
                 "sequential": SEQUENTIAL} if gptq else None,
        "modules": list(LIN), "storage": "dequantized bf16", "mean_rel_weight_err": float(np.mean(rels)) if rels else None}
    base = "SpinQuant" if rots else "QuaRot"
    meta = {
        "method": (base if gptq else base + "-RTN") if a.wbits < 16 else base + "-rotation (W16)",
        "wbits": a.wbits if a.wbits < 16 else None,
        "rotation": {"residual": "random Hadamard diag(s) H_d / sqrt(d) (cloq.rotate.random_hadamard)", "seed": a.seed,
                     "norms_fused": True, "embedding_mean_subtraction": False,
                     "v_proj_out": "per-head Hadamard H_hd", "o_proj_in": "full Hadamard H_{nh*hd} (offline) + H_nh across heads (online)",
                     "down_proj_in": f"H_{info['down_had_K']} kron H_{info['intermediate'] // info['down_had_K']} (offline + online)",
                     "qk": "per-head Hadamard after RoPE (online, cloq_kvq CLOQ_KVQ_ROT=qk)", **info,
                     **({"learned": {"R1": "learned (cloq.spinquant, replaces the random Hadamard; seed unused)",
                                     "R2": "learned per layer; replaces H_hd on v_proj out / o_proj in (H_nh across heads kept)",
                                     **rot_prov}} if rots else {})},
        "weight_quant": wq, "calibration": calib,
        "requires_serve_env": {"CLOQ_PYHOOKS": "1", "CLOQ_AQ_HAD": "quarot"},
        "forbids_serve_env": {"CLOQ_KVQ_ROT": "1"},
        "reference_serve_env_W4A4KV4": {"CLOQ_PYHOOKS": "1", "CLOQ_AQ_BITS": "4", "CLOQ_AQ_FMT": "sym_quarot",
                                        "CLOQ_AQ_CLIP": "0.9", "CLOQ_AQ_HAD": "quarot", "CLOQ_KVQ_BITS": "4",
                                        "CLOQ_KVQ_ROT": "qk", "CLOQ_KVQ_FMT": "quarot", "CLOQ_KVQ_KCLIP": "0.95",
                                        "CLOQ_KVQ_VCLIP": "0.95"},
        "invariance_check_hf": check,
        "source_model": a.source_model, "source_revision": a.source_revision, "source_dir": str(src),
        "storage": "fake-quant bf16", "seconds": time.time() - t0, "per_tensor": wstats,
    }
    if not a.no_sha:
        meta["weight_files"] = {p.name: _sha256(p) for p in sorted(out.glob("*.safetensors"))}
    (out / "quantization.json").write_text(json.dumps(meta, indent=1))
    log(f"{meta['method']} -> {out}; check={json.dumps(check)}")


if __name__ == "__main__":
    main()
