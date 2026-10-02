"""SpinQuant (Liu et al., ICLR 2025; github.com/facebookresearch/SpinQuant @ 8f47aa3) rotation learning for a dense
Qwen3 model, in the QuaRot skeleton of cloq/quarot.py, plus a WikiText-2 perplexity probe for the gate (W99r).

What is learned (optimize_rotation.py / train_utils): R1 (d x d, residual stream) and one R2 per layer (head_dim x
head_dim, v_proj output / o_proj input), on the Stiefel manifold with Cayley SGD (train_utils/optimizer.py SGDG,
stiefel=True, momentum 0, after Li, Todorovic & Fuxin, ICLR 2020), lr 1.5 cosine to 0 without warmup, 100 steps,
batch 8 x 2048 tokens, next-token cross-entropy of the network with fake activation quantization (straight-through
estimator: the gradient passes the quantizer unchanged, STEQuantize) and 16-bit weights. The weights are rotated on
the fly in every step (QuantizeLinear: W R1, R1^T W, per-head R2), so the gradient reaches R1/R2 through every
quantized linear input.

Controlled variant (the default here, docs/insights/METHOD_FIDELITY.md §7 and analysis/fork/rot_gate/GATE.md):
everything except "R1/R2 learned vs random" is QuaRot's, so a SpinQuant-vs-QuaRot difference is the rotation only.
  * same skeleton: norms fused, online H_K kron H_{n/K} on the down_proj input (= SpinQuant R4), online H_nh across
    heads on the o_proj input (QuaRot online_partial_had; not in SpinQuant), R2 in place of QuaRot's per-head H_hd;
  * same activation grid while learning as when serving: per-token symmetric INT4, clip 0.9 (sym_quarot) on the inputs
    of q/k/v, o, gate/up, down (SpinQuant's script learns with asymmetric, clip 1.0, o_proj grouped by head_dim);
  * same calibration data: the 128 WikiText-2 train windows x 2048 tokens (random.seed(0)) that GPTQ uses
    (cloq.quarot.wikitext_windows); 100 steps x 8 = 800 draws, i.e. 6.25 epochs (SpinQuant draws 800 distinct blocks);
  * init at the QuaRot point: R1 = random_hadamard(d, seed) (QuaRot's Q), R2 = H_hd / sqrt(hd) (QuaRot's per-head
    Hadamard), so step 0 is exactly QuaRot and the loss curve measures what learning adds (SpinQuant inits R2 with a
    random-sign Hadamard per layer);
  * KV16 (no K/V quantization while learning, as in the KV16 serving config); W16 while learning; GPTQ afterwards in
    cloq.quarot with the same windows, percdamp, MSE clip and true-sequential order.
Numerics while learning: bf16 frozen weights (norm-fused; down_proj and o_proj pre-multiplied by their fixed Hadamard
parts once), fp32 R1/R2 and fp32 weight rotation (SpinQuant uses fp64; A6000 fp64 is ~1/64 rate), fp32 Hadamards and
QDQ as in the serving hook, bf16 GEMMs, sdpa attention, per-layer gradient checkpointing, chunked lm_head + CE (R1
cancels exactly at the unquantized lm_head input, so logits use h R1^T with the norm-fused lm_head).

Outputs (learn): <out>/R.pt {"R1": fp32 [d,d], "R2": [L x fp32 [hd,hd]], "meta"}, <out>/learn.json (per-step loss, lr,
step size, orthogonality, seconds; WikiText-2 test perplexity at init and after learning, A16 and A4).

usage:
  python -m cloq.spinquant learn --model-dir <hf snapshot> --out <dir> [--steps 100 --lr 1.5 --batch 8 --micro 8]
  python -m cloq.spinquant ppl --ckpt <cloq.quarot output dir> --abits 4 --out <json>   (online Hadamards + A-QDQ)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import time
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.utils.parametrize as P
from torch.utils.checkpoint import checkpoint

from cloq.aq import fwht, had_factor, had_heads, had_transform, hadK_list, qdq
from cloq.rotate import random_hadamard

WIKITEXT_TEST = Path("/data/ziyangs/cloq_work/data/wikitext2/wikitext-test.parquet")
A_FMT, A_CLIP = "sym_quarot", 0.9


# ------------------------------------------------------------------------------------------------------------------
# Cayley SGD on the Stiefel manifold (SpinQuant train_utils/optimizer.py SGDG with stiefel=True; momentum 0 default)
# ------------------------------------------------------------------------------------------------------------------


class CayleySGD(torch.optim.Optimizer):
    """Per square parameter X (rows normalized, as `unit`), Euclidean gradient G:
         V = mom * V - G^T;  W_hat = V X - 1/2 X^T (X V X);  W = W_hat - W_hat^T  (skew)
         alpha = min(lr, 1 / (||W||_1 + eps));  Y = X^T + alpha V;  5 x  Y = X^T + alpha W (X^T + Y) / 2
         X <- Y^T;  V <- W X^T
       with a QR re-orthonormalization of X before the step with probability 1/101 (as the reference)."""

    def __init__(self, params, lr: float, momentum: float = 0.0, rng: random.Random | None = None):
        super().__init__(params, dict(lr=lr, momentum=momentum))
        self.rng = rng or random.Random(0)
        self.last = {}

    @torch.no_grad()
    def step(self, closure=None):
        alphas, qr = [], 0
        for group in self.param_groups:
            for p in group["params"]:
                if p.grad is None:
                    continue
                X = p.data.view(p.size(0), -1)
                X = X / (X.norm(dim=1, keepdim=True) + 1e-8)
                if self.rng.randint(1, 101) == 1:  # qr_retraction
                    q, r = torch.linalg.qr(X.t())
                    q = q * torch.diag(r).sign().unsqueeze(0)
                    X = q.t()
                    qr += 1
                g = p.grad.data.view(p.size(0), -1)
                st = self.state[p]
                if "V" not in st:
                    st["V"] = torch.zeros_like(g.t())
                V = group["momentum"] * st["V"] - g.t()
                MX = V @ X
                XMX = X @ MX
                XXMX = X.t() @ XMX
                W_hat = MX - 0.5 * XXMX
                W = W_hat - W_hat.t()
                alpha = min(0.5 * 2 / (W.abs().sum(0).max().item() + 1e-8), group["lr"])
                Xt = X.t()
                Y = Xt + alpha * V
                for _ in range(5):
                    Y = Xt + alpha * (W @ (0.5 * (Xt + Y)))
                p.data.copy_(Y.t().view(p.size()))
                st["V"] = W @ Xt
                alphas.append(alpha)
        self.last = {"alpha_min": min(alphas), "alpha_max": max(alphas), "qr_retractions": qr}


# ------------------------------------------------------------------------------------------------------------------
# Rotated, fake-quantized Qwen3 (HF) with R1 / R2 as the only trainable tensors
# ------------------------------------------------------------------------------------------------------------------


class Rots(nn.Module):
    def __init__(self, R1: torch.Tensor, R2: list[torch.Tensor]):
        super().__init__()
        self.R1 = nn.Parameter(R1.float())
        self.R2 = nn.ParameterList([nn.Parameter(r.float()) for r in R2])


class _Read(nn.Module):  # q/k/gate/up (and v): W diag(norm) R1 [then per-head R2^T on v's output rows]
    def __init__(self, rots, li=None, n_kv=0, hd=0):
        super().__init__()
        self.ref, self.li, self.n_kv, self.hd = [rots], li, n_kv, hd

    def forward(self, W):
        r = self.ref[0]
        Wf = W.float() @ r.R1
        if self.li is not None:
            Wf = (r.R2[self.li].t() @ Wf.reshape(self.n_kv, self.hd, -1)).reshape(W.shape)
        return Wf.to(W.dtype)


class _WriteO(nn.Module):  # o_proj: R1^T [W (H_nh kron I)] (I kron R2); the H_nh part is pre-applied to the stored weight
    def __init__(self, rots, li, nh, hd):
        super().__init__()
        self.ref, self.li, self.nh, self.hd = [rots], li, nh, hd

    def forward(self, W):
        r = self.ref[0]
        Wf = (W.float().reshape(-1, self.nh, self.hd) @ r.R2[self.li]).reshape(W.shape)
        return (r.R1.t() @ Wf).to(W.dtype)


class _WriteD(nn.Module):  # down_proj: R1^T [W H_down]; H_down pre-applied
    def __init__(self, rots):
        super().__init__()
        self.ref = [rots]

    def forward(self, W):
        return (self.ref[0].R1.t() @ W.float()).to(W.dtype)


def had_light(x: torch.Tensor, K: int, HK: list | None) -> torch.Tensor:
    """cloq.aq.had_transform with the K-block mix as a GEMM: the serving form (broadcast multiply + sum) materializes
    (tokens, K, K, n/K) fp32, ~10 GB at 16k tokens. Same transform up to fp32 summation order (tests/test_spinquant.py 4)."""
    if K == 1:
        return had_transform(x, 1, None)
    n = x.shape[-1]
    y = fwht(x.reshape(*x.shape[:-1], K, n // K))
    Hm = torch.tensor(HK, dtype=x.dtype, device=x.device)
    return torch.matmul(Hm, y).reshape(x.shape) * (n ** -0.5)


def ste_qdq(x: torch.Tensor, bits: int) -> torch.Tensor:
    """Fake quantization with a straight-through gradient (SpinQuant STEQuantize). fp32 in/out."""
    if bits >= 16:
        return x
    return x + (qdq(x.detach(), bits, A_FMT, A_CLIP) - x).detach()


class RotModel:
    """HF Qwen3ForCausalLM, norm-fused, with parametrized (rotated) linears and the serving hook's online transforms +
    activation QDQ as forward pre-hooks. abits can be changed between calls (16 = transform path only)."""

    def __init__(self, model_dir: str, R1: torch.Tensor, R2: list[torch.Tensor], dev: str, rotate: bool = True,
                 dtype: torch.dtype = torch.bfloat16):
        from transformers import AutoModelForCausalLM
        self.model = AutoModelForCausalLM.from_pretrained(model_dir, dtype=dtype, attn_implementation="sdpa").to(dev)
        self.dtype = dtype
        m, cfg = self.model, self.model.config
        assert not getattr(cfg, "tie_word_embeddings", False), "untied lm_head expected (Qwen3-8B)"
        self.nh, self.n_kv = cfg.num_attention_heads, cfg.num_key_value_heads
        self.hd = getattr(cfg, "head_dim", None) or cfg.hidden_size // self.nh
        self.K, HK = had_factor(cfg.intermediate_size)
        self.HKl = hadK_list(self.K, HK)
        self.abits, self.rotate = 16, rotate
        for p in m.parameters():
            p.requires_grad_(False)
        self.rots = Rots(R1, R2).to(dev)
        if rotate:
            with torch.no_grad():
                for L in m.model.layers:
                    a, f = L.self_attn, L.mlp
                    for lin, nw in ((a.q_proj, L.input_layernorm), (a.k_proj, L.input_layernorm), (a.v_proj, L.input_layernorm),
                                    (f.gate_proj, L.post_attention_layernorm), (f.up_proj, L.post_attention_layernorm)):
                        lin.weight.copy_((lin.weight.float() * nw.weight.float()[None, :]).to(lin.weight.dtype))
                    L.input_layernorm.weight.fill_(1.0)
                    L.post_attention_layernorm.weight.fill_(1.0)
                    a.o_proj.weight.copy_(had_heads(a.o_proj.weight.float(), self.nh).to(dtype))
                    f.down_proj.weight.copy_(had_light(f.down_proj.weight.float(), self.K, self.HKl).to(dtype))
                m.lm_head.weight.copy_((m.lm_head.weight.float() * m.model.norm.weight.float()[None, :]).to(dtype))
                m.model.norm.weight.fill_(1.0)
            for li, L in enumerate(m.model.layers):
                a, f = L.self_attn, L.mlp
                for lin in (a.q_proj, a.k_proj, f.gate_proj, f.up_proj):
                    P.register_parametrization(lin, "weight", _Read(self.rots), unsafe=True)
                P.register_parametrization(a.v_proj, "weight", _Read(self.rots, li, self.n_kv, self.hd), unsafe=True)
                P.register_parametrization(a.o_proj, "weight", _WriteO(self.rots, li, self.nh, self.hd), unsafe=True)
                P.register_parametrization(f.down_proj, "weight", _WriteD(self.rots), unsafe=True)
            m.model.embed_tokens.register_forward_hook(lambda mod, i, o: (o.float() @ self.rots.R1).to(o.dtype))
        for L in m.model.layers:
            a, f = L.self_attn, L.mlp
            for lin in (a.q_proj, a.k_proj, a.v_proj, f.gate_proj, f.up_proj):
                lin.register_forward_pre_hook(lambda mod, x: (ste_qdq(x[0].float(), self.abits).to(x[0].dtype),))
            if rotate:
                a.o_proj.register_forward_pre_hook(
                    lambda mod, x: (ste_qdq(had_heads(x[0].float(), self.nh), self.abits).to(x[0].dtype),))
                f.down_proj.register_forward_pre_hook(
                    lambda mod, x: (ste_qdq(had_light(x[0].float(), self.K, self.HKl), self.abits).to(x[0].dtype),))
            else:
                for lin in (a.o_proj, f.down_proj):
                    lin.register_forward_pre_hook(lambda mod, x: (ste_qdq(x[0].float(), self.abits).to(x[0].dtype),))
        m.config.use_cache = False

    def nll(self, ids: torch.Tensor, chunk: int = 2048) -> tuple[torch.Tensor, int]:
        """Summed next-token NLL over the batch (B, T) and the token count; lm_head + CE chunked and checkpointed."""
        h = self.model.model(input_ids=ids, use_cache=False).last_hidden_state  # final norm (weight 1) applied, rotated basis
        if self.rotate:
            h = (h.float() @ self.rots.R1.t()).to(self.dtype)
        h = h[:, :-1].reshape(-1, h.shape[-1])
        y = ids[:, 1:].reshape(-1)
        W = self.model.lm_head.weight

        def ce(hc, yc):
            return nn.functional.cross_entropy((hc @ W.t()).float(), yc, reduction="sum")

        tot = 0.0
        for i in range(0, h.shape[0], chunk):
            hc, yc = h[i:i + chunk], y[i:i + chunk]
            tot = tot + (checkpoint(ce, hc, yc, use_reentrant=False) if torch.is_grad_enabled() else ce(hc, yc))
        return tot, int(y.numel())


def wikitext_test_windows(tok, seqlen: int = 2048) -> list[list[int]]:
    """QuaRot / SpinQuant ppl eval: '\\n\\n'.join(test text), consecutive non-overlapping windows of seqlen."""
    import pyarrow.parquet as pq
    txt = "\n\n".join(pq.read_table(WIKITEXT_TEST).column("text").to_pylist())
    ids = tok(txt, return_tensors="pt").input_ids[0]
    n = ids.numel() // seqlen
    return [ids[i * seqlen:(i + 1) * seqlen].tolist() for i in range(n)]


@torch.no_grad()
def ppl(rm: RotModel, wins: list[list[int]], dev: str, bs: int = 4) -> float:
    tot, n = 0.0, 0
    with P.cached():  # rotated weights computed once per call, not per batch
        for i in range(0, len(wins), bs):
            s, k = rm.nll(torch.tensor(wins[i:i + bs], device=dev))
            tot += float(s)
            n += k
    return math.exp(tot / n)


def learn(a) -> None:
    from transformers import AutoTokenizer

    from cloq.quarot import _sha256, wikitext_windows
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.manual_seed(a.seed)
    dev = "cuda"
    t0 = time.time()
    log = lambda s: print(f"[spinquant {time.time() - t0:.0f}s] {s}", flush=True)  # noqa: E731
    cfg = json.load(open(Path(a.model_dir) / "config.json"))
    d, nh, L = cfg["hidden_size"], cfg["num_attention_heads"], cfg["num_hidden_layers"]
    hd = cfg.get("head_dim") or d // nh
    from cloq.rotate import hadamard
    R1 = random_hadamard(d, a.rot_seed).float()
    H = (hadamard(hd) / hd ** 0.5).float()
    rm = RotModel(a.model_dir, R1, [H.clone() for _ in range(L)], dev)
    rm.model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    tok = AutoTokenizer.from_pretrained(a.model_dir)
    seqs = wikitext_windows(tok, a.nsamples, a.seqlen, a.calib_seed)
    calib = {"source": "WikiText-2 raw v1 train (cloq.quarot.wikitext_windows; = the GPTQ windows)",
             "source_sha256": _sha256(Path("/data/ziyangs/cloq_work/data/wikitext2/wikitext-train.arrow")),
             "seed": a.calib_seed, "n_samples": a.nsamples, "seq_len": a.seqlen,
             "token_ids_sha256": hashlib.sha256(torch.tensor(seqs, dtype=torch.int64).numpy().tobytes()).hexdigest()}
    test = wikitext_test_windows(tok, a.seqlen)[: a.ppl_windows or None]
    rec = {"method": "SpinQuant rotation learning (controlled: QuaRot skeleton and grid)", "args": vars(a), "calibration": calib,
           "abits_train": a.abits, "a_fmt": A_FMT, "a_clip": A_CLIP, "kv_bits": 16, "w_bits_train": 16,
           "init": {"R1": f"random_hadamard(d, seed={a.rot_seed}) = QuaRot Q", "R2": "H_hd / sqrt(hd) = QuaRot per-head Hadamard"},
           "wikitext_test": {"n_windows": len(test), "seq_len": a.seqlen, "sha256": _sha256(WIKITEXT_TEST)}, "steps": []}
    rm.model.eval()
    ppl0 = {}
    for ab in (16, a.abits):
        rm.abits = ab
        ppl0[f"a{ab}"] = ppl(rm, test, dev)
        log(f"init (QuaRot point) wikitext2-test ppl A{ab}: {ppl0[f'a{ab}']:.4f}")
    rec["ppl_init"] = ppl0
    rm.abits = a.abits
    rm.model.train()
    params = [rm.rots.R1] + list(rm.rots.R2)
    opt = CayleySGD(params, lr=a.lr, rng=random.Random(a.seed))
    order = []
    rng = random.Random(a.seed)
    while len(order) < a.steps * a.batch:
        perm = list(range(len(seqs)))
        rng.shuffle(perm)
        order += perm
    for step in range(a.steps):
        lr = a.lr * 0.5 * (1 + math.cos(math.pi * step / a.steps))  # HF cosine, no warmup (lr at step 0 = a.lr)
        for g in opt.param_groups:
            g["lr"] = lr
        opt.zero_grad(set_to_none=True)
        idx = order[step * a.batch:(step + 1) * a.batch]
        tot, ntok, ts = 0.0, 0, time.time()
        n_all = (a.seqlen - 1) * len(idx)
        for j in range(0, len(idx), a.micro):
            ids = torch.tensor([seqs[i] for i in idx[j:j + a.micro]], device=dev)
            s, k = rm.nll(ids)
            (s / n_all).backward()
            tot += float(s)
            ntok += k
        gn = float(torch.sqrt(sum((p.grad.float() ** 2).sum() for p in params)))
        opt.step()
        with torch.no_grad():
            I = torch.eye(d, device=dev)
            orth = float((rm.rots.R1 @ rm.rots.R1.t() - I).abs().max())
        row = {"step": step, "loss": tot / ntok, "lr": lr, "grad_norm": gn, **opt.last, "orth_err_R1": orth,
               "seconds": time.time() - ts, "max_mem_gb": torch.cuda.max_memory_allocated() / 2 ** 30}
        rec["steps"].append(row)
        log(json.dumps(row))
        if step == 0 or (step + 1) % 10 == 0:
            (out / "learn.json").write_text(json.dumps(rec, indent=1))
    rm.model.eval()
    ppl1 = {}
    for ab in (16, a.abits):
        rm.abits = ab
        ppl1[f"a{ab}"] = ppl(rm, test, dev)
        log(f"learned wikitext2-test ppl A{ab}: {ppl1[f'a{ab}']:.4f}")
    rec["ppl_learned"] = ppl1
    meta = {k: rec[k] for k in ("method", "args", "calibration", "abits_train", "a_fmt", "a_clip", "init")}
    torch.save({"R1": rm.rots.R1.detach().cpu(), "R2": [r.detach().cpu() for r in rm.rots.R2], "meta": meta}, out / "R.pt")
    rec["R_sha256"] = _sha256(out / "R.pt")
    rec["seconds"] = time.time() - t0
    (out / "learn.json").write_text(json.dumps(rec, indent=1))
    log(f"saved {out / 'R.pt'} sha {rec['R_sha256']}")


def ppl_ckpt(a) -> None:
    """WikiText-2 test ppl of a (transformed, fake-quant) checkpoint with the serving hook's online half emulated:
    --had quarot adds the online Hadamards (down: H_K kron H_{n/K}; o: H_nh across heads); --abits 4 adds per-token
    sym INT4 clip 0.9 on the inputs of all decoder linears (KV16). Untransformed BF16: --had 0 --abits 16."""
    from transformers import AutoTokenizer
    torch.backends.cuda.matmul.allow_tf32 = False
    dev = "cuda"
    d = json.load(open(Path(a.ckpt) / "config.json"))["hidden_size"]
    rm = RotModel(a.ckpt, torch.eye(d), [], dev, rotate=False)
    if a.had == "quarot":  # weights already carry the offline half; add only the online Hadamards before the QDQ
        for L in rm.model.model.layers:
            L.self_attn.o_proj._forward_pre_hooks.clear()
            L.mlp.down_proj._forward_pre_hooks.clear()
            L.self_attn.o_proj.register_forward_pre_hook(
                lambda mod, x: (ste_qdq(had_heads(x[0].float(), rm.nh), rm.abits).to(x[0].dtype),))
            L.mlp.down_proj.register_forward_pre_hook(
                lambda mod, x: (ste_qdq(had_light(x[0].float(), rm.K, rm.HKl), rm.abits).to(x[0].dtype),))
    rm.model.eval()
    tok = AutoTokenizer.from_pretrained(a.ckpt)
    test = wikitext_test_windows(tok, 2048)[: a.ppl_windows or None]
    res = json.load(open(a.out)) if Path(a.out).exists() else {}
    for ab in [int(x) for x in str(a.abits).split(",")]:
        rm.abits = ab
        t0 = time.time()
        v = ppl(rm, test, dev)
        res[f"{a.name}_a{ab}"] = {"ckpt": a.ckpt, "had": a.had, "abits": ab, "a_fmt": A_FMT, "a_clip": A_CLIP,
                                  "ppl": v, "n_windows": len(test), "seconds": time.time() - t0}
        print(f"[spinquant ppl] {a.name} A{ab} had={a.had}: {v:.4f}", flush=True)
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(res, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("learn")
    l.add_argument("--model-dir", required=True)
    l.add_argument("--out", required=True)
    l.add_argument("--steps", type=int, default=100)
    l.add_argument("--lr", type=float, default=1.5)
    l.add_argument("--batch", type=int, default=8)
    l.add_argument("--micro", type=int, default=4)
    l.add_argument("--abits", type=int, default=4)
    l.add_argument("--nsamples", type=int, default=128)
    l.add_argument("--seqlen", type=int, default=2048)
    l.add_argument("--calib-seed", type=int, default=0)
    l.add_argument("--rot-seed", type=int, default=0, help="R1 init = random_hadamard(d, rot_seed) (QuaRot's seed)")
    l.add_argument("--seed", type=int, default=0, help="data order / QR-retraction draws")
    l.add_argument("--ppl-windows", type=int, default=0, help="0 = all WikiText-2 test windows")
    q = sub.add_parser("ppl")
    q.add_argument("--ckpt", required=True)
    q.add_argument("--name", required=True)
    q.add_argument("--had", choices=["0", "quarot"], default="quarot")
    q.add_argument("--abits", default="4")
    q.add_argument("--ppl-windows", type=int, default=0)
    q.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    learn(a) if a.cmd == "learn" else ppl_ckpt(a)


if __name__ == "__main__":
    main()
