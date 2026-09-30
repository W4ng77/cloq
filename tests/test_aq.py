"""Unit tests for cloq/aq.py (activation / KV fake-quant math, Hadamards) against the official reference code
(tests/ref_quant_official.py: QuaRot quant_utils / hadamard_utils, SmoothQuant fake_quant / smooth).
CPU, plain asserts. run: python tests/test_aq.py [--out analysis/ahook/unit_tests.json]

Acceptance step (1) of docs/insights/METHOD_FIDELITY.md: QDQ numerics incl. zero range, rounding boundaries (ties),
clipping, group tails; step (6): per-token scales never use other (future) tokens. Plus Hadamard constructions and
the offline/online identity used by cloq/quarot.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ref_quant_official as R  # noqa: E402
from cloq.aq import (fwht, had_factor, had_heads, had_transform, hadK_list, qdq, quarot_weight_params,  # noqa: E402
                     quarot_weight_qdq, sq_weight_per_channel_absmax)

RES: dict = {}
torch.manual_seed(0)


def cases(n=256, T=64):
    """Activation-like rows with the edge cases that matter."""
    g = torch.Generator().manual_seed(1)
    x = torch.randn(T, n, generator=g) * torch.linspace(0.1, 3, n)  # channel-scaled
    x[3] = 0.0  # zero row
    x[4] = 0.0
    x[4, 7] = -2.5  # single negative outlier
    x[5] = x[5].abs()  # all non-negative
    x[6] = -x[6].abs()  # all non-positive
    x[7, :] = 1e-7 * torch.randn(n, generator=g)  # tiny row (below SmoothQuant's 1e-5 scale floor)
    x[8, 0] = 300.0  # massive outlier channel (Qwen-like)
    x[9, :] = 0.75  # constant positive row
    return x


def ties_row(bits, n=256):
    """A row whose absmax is maxq, so every x = k + 0.5 lands exactly on a rounding tie (scale 1)."""
    maxq = 2 ** (bits - 1) - 1
    v = torch.arange(n, dtype=torch.float32) % (2 * maxq + 1) - maxq  # -maxq..maxq
    v = v + 0.5 * (torch.arange(n) % 2 == 1).float() * torch.sign(v + 0.1)
    v = v.clamp(-maxq, maxq)
    v[0] = maxq
    return v[None, :]


def eq(a, b):
    return torch.equal(a.float(), b.float())


def test_sym_quarot():
    out = {}
    for bits in (8, 4):
        for clip in (1.0, 0.9):
            for x in (cases(), ties_row(bits)):
                ref = R.ActQuantizer()
                ref.configure(bits, groupsize=-1, sym=True, clip_ratio=clip)
                ref.find_params(x)
                want = ref(x)
                got = qdq(x, bits, "sym_quarot", clip)
                assert eq(got, want), (bits, clip, (got - want).abs().max())
            # group-wise (groupsize divides n), reference needs (bsz, seq, hidden)
            x = cases()[None]
            ref = R.ActQuantizer()
            ref.configure(bits, groupsize=64, sym=True, clip_ratio=clip)
            ref.find_params(x)
            want = ref(x)
            got = qdq(x, bits, "sym_quarot", clip, group=64)
            assert eq(got, want), ("group", bits, clip)
            out[f"b{bits}_c{clip}"] = "exact"
    # clamp: with clip < 1 values beyond the clipped max saturate at maxq / -(maxq+1)
    x = torch.tensor([[-10.0, 10.0, 1.0, -1.0]])
    y = qdq(x, 4, "sym_quarot", 0.5)
    s = 10 * 0.5 / 7
    assert torch.allclose(y, torch.tensor([[-8 * s, 7 * s, round(1 / s) * s, -round(1 / s) * s]]))
    out["clip_saturation"] = "ok (+7 / -8 at 4 bits)"
    RES["sym_quarot_vs_QuaRot_ActQuantizer"] = out


def test_sym_sq():
    for bits in (8, 4):
        for x in (cases(), ties_row(bits)):
            want = R.sq_quantize_activation_per_token_absmax(x.clone(), bits)
            got = qdq(x, bits, "sym_sq")
            assert eq(got, want), (bits, (got - want).abs().max())
    # zero row -> 0; a tiny row (max < 1e-5) is quantized on the floor grid 1e-5/127, exactly as the reference
    x = cases()
    y = qdq(x, 8, "sym_sq")
    assert torch.all(y[3] == 0)
    s = 1e-5 / 127
    assert torch.allclose(y[7] / s, torch.round(y[7] / s), atol=1e-4)
    RES["sym_sq_vs_SmoothQuant_per_token_absmax"] = "exact (8, 4 bits; zero, tiny (scale floor), tie rows)"


def test_asym_quarot():
    out = {}
    for bits in (8, 4, 3):
        for clip in (1.0, 0.95):
            x = cases(128, 64)
            ref = R.ActQuantizer()
            ref.configure(bits, groupsize=-1, sym=False, clip_ratio=clip)
            ref.find_params(x)
            want = ref(x)
            got = qdq(x, bits, "asym_quarot_tok", clip)
            assert eq(got, want), ("tok", bits, clip, (got - want).abs().max())
            # group-wise (V path): reference = find_params_per_token_groupwise; exclude constant non-zero groups,
            # where the reference divides by zero (documented deviation)
            xg = cases(256, 64)
            ok_rows = [i for i in range(xg.shape[0]) if i != 9]
            xg = xg[ok_rows][None]
            ref = R.ActQuantizer()
            ref.configure(bits, groupsize=128, sym=False, clip_ratio=clip)
            ref.find_params(xg)
            want = ref(xg)
            got = qdq(xg, bits, "asym_quarot_grp", clip, group=128)
            assert eq(got, want), ("grp", bits, clip, (got - want).abs().max())
            out[f"b{bits}_c{clip}"] = "exact"
    # degenerate constant group: reference -> NaN; ours -> finite, zero-including range
    c = torch.full((1, 1, 128), 0.75)
    ref = R.ActQuantizer()
    ref.configure(4, groupsize=128, sym=False, clip_ratio=1.0)
    ref.find_params(c)
    ref_finite = bool(torch.isfinite(ref(c)).all())
    y = qdq(c, 4, "asym_quarot_grp", 1.0, group=128)
    assert torch.isfinite(y).all() and torch.allclose(y, c, atol=0.75 / 15)
    out["constant_group"] = (f"reference finite={ref_finite} (scale 0 -> x/0); ours finite (zero-including range), "
                             "documented deviation")
    RES["asym_quarot_vs_QuaRot_ActQuantizer"] = out


def naive_group(x, bits, fmt, clip, group):
    """Loop reference for group tails: quantize each consecutive chunk of each row on its own."""
    y = torch.empty_like(x)
    for i in range(x.shape[0]):
        for s in range(0, x.shape[1], group):
            y[i, s:s + group] = qdq(x[i:i + 1, s:s + group], bits, fmt, clip)[0]
    return y


def test_group_tails():
    x = cases(300, 16)  # 300 = 2 * 128 + 44
    for fmt, clip in (("sym_quarot", 1.0), ("sym_quarot", 0.9), ("sym_sq", 1.0), ("asym_quarot_tok", 0.95)):
        for bits in (8, 4):
            got = qdq(x, bits, fmt, clip, group=128)
            want = naive_group(x, bits, fmt, clip, 128)
            assert eq(got, want), (fmt, bits)
    RES["group_tails"] = "300 = 2x128 + 44: tail group quantized on its own, equals per-chunk loop (4 formats x 8/4 bits)"


def test_row_locality():
    """Step (6): a token's QDQ never depends on other rows (earlier, later, batch) -- per-token statistics only."""
    g = torch.Generator().manual_seed(3)
    x = torch.randn(40, 512, generator=g) * 3
    for fmt, kw in (("sym_quarot", {}), ("sym_quarot", {"clip": 0.9}), ("sym_sq", {}), ("asym_quarot_tok", {"clip": 0.95}),
                    ("asym_quarot_grp", {"group": 128})):
        full = qdq(x, 4, fmt, **kw)
        for t in (0, 7, 39):
            pref = qdq(x[:t + 1], 4, fmt, **kw)  # causal prefix only
            assert eq(pref, full[:t + 1]), (fmt, t)
            y = x.clone()
            y[t + 1:] *= 1000  # change all future tokens
            assert eq(qdq(y, 4, fmt, **kw)[:t + 1], full[:t + 1]), (fmt, t)
        perm = torch.randperm(40, generator=g)
        assert eq(qdq(x[perm], 4, fmt, **kw), full[perm]), fmt  # batch order
    # Hadamards are per row too
    assert eq(had_transform(x[:5].double(), 1, None), had_transform(x.double(), 1, None)[:5])
    RES["row_locality"] = "prefix / future-token change / permutation invariant for all formats and Hadamards"


def test_weights():
    g = torch.Generator().manual_seed(4)
    W = torch.randn(96, 320, generator=g) * torch.rand(96, 1, generator=g)
    W[5] = 0
    for bits, sym, mse in ((4, True, True), (4, True, False), (8, True, True), (4, False, True)):
        ref = R.WeightQuantizer()
        ref.configure(bits, perchannel=True, sym=sym, mse=mse)
        ref.find_params(W.clone())
        want = ref.quantize(W)
        s, z, maxq = quarot_weight_params(W, bits, sym=sym, mse=mse)
        got = quarot_weight_qdq(W, s, z, maxq, sym=sym)
        assert eq(got, want), (bits, sym, mse, (got - want).abs().max())
    want = R.sq_quantize_weight_per_channel_absmax(W.clone(), 8)
    assert eq(sq_weight_per_channel_absmax(W, 8), want)
    RES["weight_quantizers"] = "QuaRot WeightQuantizer (per-channel, sym/asym, w_clip MSE grid) and SmoothQuant W8 per-channel absmax: exact"


def test_smooth():
    from cloq.smoothquant import smooth_scales
    g = torch.Generator().manual_seed(5)
    ln = torch.rand(256, generator=g) + 0.5
    fcs = [torch.randn(64, 256, generator=g), torch.randn(32, 256, generator=g)]
    act = torch.rand(256, generator=g) * 10
    act[3] = 200
    for alpha in (0.5, 0.85):
        l2, f2 = ln.clone(), [f.clone() for f in fcs]
        want = R.sq_smooth_ln_fcs_llama_like(l2, f2, act, alpha)
        got = smooth_scales(act, fcs, alpha)
        assert eq(got, want), alpha
        assert eq(ln / got, l2) and all(eq(f * got[None, :], f2i) for f, f2i in zip(fcs, f2))
    RES["smooth_scales"] = "SmoothQuant smooth_ln_fcs_llama_like (fp32): exact for alpha 0.5, 0.85"


def test_hadamard():
    out = {}
    for n in (128, 1024, 2560, 4096, 9728, 12288):
        K, H = had_factor(n)
        E = torch.eye(n, dtype=torch.float64)
        M = had_transform(E, K, hadK_list(K, H))  # rows: had(e_i)
        err = float((M @ M.T - E).abs().max())
        # explicit kron H_K (x) Sylvester_{n/K}: had(x) = x @ (H_K kron S)^T / sqrt(n)
        S = torch.ones(1, 1, dtype=torch.float64)
        while S.shape[0] < n // K:
            S = torch.kron(S, torch.tensor([[1.0, 1.0], [1.0, -1.0]], dtype=torch.float64))
        full = torch.kron(H if H is not None else torch.ones(1, 1, dtype=torch.float64), S) / n ** 0.5
        kerr = float((M - full.T).abs().max())
        assert err < 1e-12 and kerr < 1e-12, (n, err, kerr)
        out[n] = {"K": K, "orth_err": err, "kron_err": kerr}
        if K in (1, 12):  # QuaRot's own CPU transform (matmul_hadU) for sizes its table supports
            x = torch.randn(3, n, dtype=torch.float64)
            ref = R.matmul_hadU(x, H, K)
            # the reference normalizes by torch.tensor(n).sqrt(), a float32 sqrt: agreement to fp32 rounding only
            d = float((ref - had_transform(x, K, hadK_list(K, H))).abs().max() / ref.abs().max())
            assert d < 1e-6, (n, d)
            out[n]["vs_quarot_matmul_hadU_rel"] = d
    # QuaRot o_proj identity: (I kron H_hd) applied offline to V/W_o, (H_nh kron I) online = full Sylvester H_{nh*hd}
    nh, hd = 32, 128
    x = torch.randn(4, nh * hd, dtype=torch.float64)
    per_head = fwht(x.reshape(4, nh, hd)).reshape(4, -1) / hd ** 0.5
    assert float((had_heads(per_head, nh) - had_transform(x, 1, None)).abs().max()) < 1e-10
    out["heads_identity"] = "(H_nh x I)(I x H_hd) = H_4096 (1e-10)"
    # offline weight transform + online activation transform leaves the linear unchanged
    for n in (9728, 12288):
        K, H = had_factor(n)
        L = hadK_list(K, H)
        W = torch.randn(16, n, dtype=torch.float64)
        xx = torch.randn(5, n, dtype=torch.float64)
        y0 = xx @ W.T
        y1 = had_transform(xx, K, L) @ had_transform(W, K, L).T
        assert float((y0 - y1).abs().max() / y0.abs().max()) < 1e-12
    out["offline_online_identity"] = "down_proj: had(x) . had(w) = x . w (fp64, 1e-12) for 9728 (K=76) and 12288 (K=12)"
    RES["hadamard"] = out


def test_gptq_quarot():
    from cloq.quarot import gptq_solve
    g = torch.Generator().manual_seed(6)
    W = torch.randn(48, 320, generator=g)
    X = torch.randn(2000, 320, generator=g) * torch.linspace(0.2, 4, 320)
    X[:, 5] = 0  # a dead input column
    H = 2 * X.T @ X / X.shape[0]
    ref = R.WeightQuantizer()
    ref.configure(4, perchannel=True, sym=True, mse=True)
    want = R.quarot_fasterquant(W, H, ref)
    got, _ = gptq_solve(W, H.clone(), 4)
    assert eq(got, want), (got - want).abs().max()
    RES["gptq_quarot"] = "cloq.quarot.gptq_solve == QuaRot GPTQ.fasterquant (W4 per-channel sym, w_clip MSE, blocksize 128, dead column): exact"


def test_quarot_tiny():
    """cloq.quarot transforms on a tiny random Qwen3 (fp32, intermediate 152 = 76 * 2 exercises H_76): with the online
    Hadamards as forward pre-hooks the transformed model reproduces the original logits."""
    import tempfile
    from transformers import AutoModelForCausalLM, Qwen3Config
    from cloq.quarot import add_online_had, transform
    torch.manual_seed(0)
    cfg = Qwen3Config(vocab_size=512, hidden_size=64, intermediate_size=152, num_hidden_layers=3, num_attention_heads=4,
                      num_key_value_heads=2, head_dim=32, tie_word_embeddings=True, max_position_embeddings=256)
    m = AutoModelForCausalLM.from_config(cfg).float().eval()
    with torch.no_grad():
        for n, p in m.named_parameters():
            if "norm" in n:
                p.copy_(1 + 0.3 * torch.randn_like(p))
    ids = torch.randint(0, 512, (2, 40))
    with tempfile.TemporaryDirectory() as td:
        src, out = Path(td, "src"), Path(td, "qr")
        m.save_pretrained(src, safe_serialization=True)
        out.mkdir()
        info = transform(src, out, 3, "cpu", None, lambda s: None)
        r = AutoModelForCausalLM.from_pretrained(out, dtype=torch.float32).eval()
        with torch.no_grad():
            a = torch.log_softmax(m(ids).logits.double(), -1)
            no_hooks = torch.log_softmax(r(ids).logits.double(), -1)
            hs = add_online_had(r, info["down_had_K"], hadK_list(*had_factor(152)), 4)
            b = torch.log_softmax(r(ids).logits.double(), -1)
        d, d0 = float((a - b).abs().max()), float((a - no_hooks).abs().max())
        assert info["down_had_K"] == 76 and d < 1e-3 and (a.argmax(-1) == b.argmax(-1)).all() and d0 > 1e-2, (d, d0)
        # RTN W4 on top writes on-grid weights
        out2 = Path(td, "qr4")
        out2.mkdir()
        info2 = transform(src, out2, 3, "cpu", 4, lambda s: None)
        assert info2["rtn_quantized"] == 3 * 7
    RES["quarot_tiny_invariance"] = {"max_abs_dlogprob_fp32_with_online_had": d, "without_online_had": d0, "down_had_K": 76}


def main():
    out = "analysis/ahook/unit_tests.json"
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name, flush=True)
    RES["torch"] = torch.__version__
    p = Path(__file__).resolve().parents[1] / out
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(RES, indent=1, default=str))
    print("all passed ->", p)


if __name__ == "__main__":
    main()
