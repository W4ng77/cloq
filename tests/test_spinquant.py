"""CPU tests for SpinQuant in the QuaRot skeleton (cloq/spinquant.py, cloq/quarot.py --rotations) on a tiny random
Qwen3 (d 64, 4 heads x 16, 2 KV heads, intermediate 96 = 12 x 8 so the H_12 path is exercised, 2 layers), fp32.
  1 quarot.transform with rotations (QuaRot's R1, H_hd / sqrt(hd)) == the default QuaRot transform (same tensors)
  2 learned-style rotations (random orthogonal R1, per-layer R2): transformed model + online Hadamards == original
  3 RotModel (the learner's on-the-fly path) at A16 == original; R1/R2 receive finite gradients
  4 learner path at A4 == serving path at A4 (exported checkpoint + online Hadamards + per-token QDQ)
  5 CayleySGD keeps R orthogonal and decreases a smooth objective
run: python tests/test_spinquant.py [--out analysis/fork/rot_gate/unit_tests.json]
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cloq import quarot as QR  # noqa: E402
from cloq import spinquant as SQ  # noqa: E402
from cloq.rotate import hadamard, random_hadamard  # noqa: E402

RES: dict = {}


def tiny(dirp: Path) -> Path:
    from transformers import Qwen3Config, Qwen3ForCausalLM
    torch.manual_seed(0)
    cfg = Qwen3Config(vocab_size=128, hidden_size=64, intermediate_size=96, num_hidden_layers=2, num_attention_heads=4,
                      num_key_value_heads=2, head_dim=16, max_position_embeddings=256, tie_word_embeddings=False,
                      rms_norm_eps=1e-6)
    m = Qwen3ForCausalLM(cfg).float()
    with torch.no_grad():  # non-trivial norms
        for n, p in m.named_parameters():
            if "norm" in n:
                p.copy_(1 + 0.3 * torch.randn_like(p))
    src = dirp / "src"
    m.save_pretrained(src, safe_serialization=True)
    return src


def rand_orth(n, seed):
    g = torch.Generator().manual_seed(seed)
    q, r = torch.linalg.qr(torch.randn(n, n, generator=g, dtype=torch.float64))
    return q * torch.diag(r).sign()[None, :]


def logits(path, had: bool, ids):
    from transformers import AutoModelForCausalLM
    m = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32, attn_implementation="sdpa").eval()
    hs = []
    if had:
        K, HK = QR.had_factor(m.config.intermediate_size)
        hs = QR.add_online_had(m, K, QR.hadK_list(K, HK), m.config.num_attention_heads)
    with torch.no_grad():
        out = m(ids).logits
    for h in hs:
        h.remove()
    return out


def main():
    out_json = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    torch.set_grad_enabled(True)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        src = tiny(td)
        log = lambda s: None  # noqa: E731
        ids = torch.randint(0, 128, (2, 40), generator=torch.Generator().manual_seed(3))
        ref = logits(src, False, ids)
        # 1
        (td / "qr").mkdir()
        (td / "sp_eq").mkdir()
        QR.transform(src, td / "qr", 0, "cpu", None, log)
        H = hadamard(16) / 4.0
        QR.transform(src, td / "sp_eq", 0, "cpu", None, log, (random_hadamard(64, 0), [H.clone(), H.clone()]))
        from safetensors.torch import load_file
        a = load_file(str(next((td / "qr").glob("*.safetensors"))))
        b = load_file(str(next((td / "sp_eq").glob("*.safetensors"))))
        d1 = max(float((a[k] - b[k]).abs().max()) for k in a)
        RES["1_quarot_point_equals_quarot"] = {"max_abs_diff": d1, "n_tensors": len(a)}
        assert set(a) == set(b) and d1 < 1e-6, d1
        # 2
        R1, R2 = rand_orth(64, 1), [rand_orth(16, 2), rand_orth(16, 3)]
        torch.save({"R1": R1.float(), "R2": [r.float() for r in R2], "meta": {}}, td / "R.pt")
        R1p, R2p, prov = QR.load_rotations(td / "R.pt", 64, 16, 2)
        (td / "sp").mkdir()
        QR.transform(src, td / "sp", 0, "cpu", None, log, (R1p, R2p))
        got = logits(td / "sp", True, ids)
        d2 = float((got - ref).abs().max())
        RES["2_learned_rotation_invariance_fp32"] = {"max_abs_dlogit": d2, "logit_scale": float(ref.abs().max()),
                                                     "polar_shift": prov["polar_shift_max"]}
        assert d2 < 1e-3, d2
        # 3
        rm = SQ.RotModel(str(src), R1p.float(), [r.float() for r in R2p], "cpu", dtype=torch.float32)
        rm.model.eval()
        s, n = rm.nll(ids)
        base = torch.nn.functional.cross_entropy(ref[:, :-1].reshape(-1, 128), ids[:, 1:].reshape(-1), reduction="sum")
        s.backward()
        g1, g2 = rm.rots.R1.grad, rm.rots.R2[1].grad
        RES["3_learner_path_A16"] = {"nll": float(s), "nll_ref": float(base), "abs_diff": float((s - base).abs()),
                                     "grad_R1_norm": float(g1.norm()), "grad_R2_norm": float(g2.norm())}
        assert abs(float(s - base)) < 1e-3 * float(base), RES["3_learner_path_A16"]
        assert torch.isfinite(g1).all() and float(g1.norm()) > 0 and float(g2.norm()) > 0
        # 4
        rm.abits = 4
        with torch.no_grad():
            s4, _ = rm.nll(ids)
        srv = SQ.RotModel(str(td / "sp"), torch.eye(64), [], "cpu", rotate=False, dtype=torch.float32)
        for L in srv.model.model.layers:
            L.self_attn.o_proj._forward_pre_hooks.clear()
            L.mlp.down_proj._forward_pre_hooks.clear()
            L.self_attn.o_proj.register_forward_pre_hook(lambda mod, x: (SQ.ste_qdq(SQ.had_heads(x[0].float(), srv.nh), srv.abits),))
            L.mlp.down_proj.register_forward_pre_hook(lambda mod, x: (SQ.ste_qdq(SQ.had_transform(x[0].float(), srv.K, srv.HKl), srv.abits),))
        srv.abits = 4
        srv.model.eval()
        with torch.no_grad():
            t4, _ = srv.nll(ids)
        RES["4_learner_vs_serving_A4"] = {"nll_learner": float(s4), "nll_serving_path": float(t4), "nll_a16": float(s),
                                          "rel_diff": float(abs(s4 - t4) / t4)}
        assert abs(float(s4 - t4)) < 2e-3 * float(t4), RES["4_learner_vs_serving_A4"]
        assert float(s4) != float(s), "A4 must change the loss"
    # 5
    T = rand_orth(32, 9).float()
    X = torch.nn.Parameter(rand_orth(32, 10).float())
    opt = SQ.CayleySGD([X], lr=0.5)
    l0 = float(((X - T) ** 2).sum())
    for _ in range(50):
        opt.zero_grad()
        loss = ((X - T) ** 2).sum()
        loss.backward()
        opt.step()
    l1 = float(((X.detach() - T) ** 2).sum())
    orth = float((X.detach() @ X.detach().T - torch.eye(32)).abs().max())
    RES["5_cayley_sgd"] = {"loss0": l0, "loss50": l1, "orth_err": orth}
    assert l1 < 0.5 * l0 and orth < 1e-4, RES["5_cayley_sgd"]
    print(json.dumps(RES, indent=1))
    if out_json:
        Path(out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(out_json).write_text(json.dumps({"tests": RES, "all_pass": True}, indent=1))
    print("ALL PASS")


if __name__ == "__main__":
    main()
