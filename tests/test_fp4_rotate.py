"""Unit tests for cloq.compress nf4 / mxfp4 and cloq.rotate (CPU; plain asserts, run: python tests/test_fp4_rotate.py).

References
  NF4   bitsandbytes quantize_4bit / dequantize_4bit (quant_type="nf4", blocksize=64) when importable
        (set BNB_PATH to a --target install); always: the code table and exhaustive nearest-code rounding.
  MXFP4 an independent implementation from the OCP MX v1.0 spec using ml_dtypes' float4_e2m1fn (RNE, saturating)
        and float8_e8m0fnu scales.
  rotate a tiny random Qwen3 (tied embeddings, fp32 storage) must give the same logits after rotation.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cloq.compress import FP4_E2M1, NF4_CODE, mxfp4_dequant, nf4_dequant, rtn_dequant, rtnsr_dequant  # noqa: E402
from cloq.gptq import Quantizer  # noqa: E402
from cloq.rotate import hadamard, main as rotate_main, random_hadamard  # noqa: E402

RESULTS = {}


def test_nf4():
    torch.manual_seed(0)
    W = torch.randn(512, 1024) * 0.02
    W[3, :64] = 0  # all-zero block
    D = nf4_dequant(W)
    # every output is code * block absmax, and it is the nearest code (ties impossible for continuous data)
    blk, dblk = W.reshape(-1, 64), D.reshape(-1, 64)
    am = blk.abs().amax(-1, keepdim=True)
    code = torch.tensor(NF4_CODE)
    n = torch.where(am > 0, blk / am, torch.zeros_like(blk))
    nearest = code[(n[..., None] - code).abs().argmin(-1)] * am
    RESULTS["nf4_vs_bruteforce_maxabs"] = float((nearest - dblk).abs().max())
    assert torch.allclose(nearest, dblk, atol=1e-7, rtol=0)
    assert D[3, :64].abs().max() == 0
    bnb = os.environ.get("BNB_PATH")
    if bnb:
        sys.path.insert(0, bnb)
        import bitsandbytes.functional as F

        assert torch.allclose(F.get_4bit_type("nf4", device="cpu").float(), code), "NF4 table differs from bitsandbytes"
        for dt in (torch.float32, torch.bfloat16):
            Wb = W.to(dt)
            q, st = F.quantize_4bit(Wb, blocksize=64, quant_type="nf4")
            ref = F.dequantize_4bit(q, st).float()
            mine = nf4_dequant(Wb.float())
            RESULTS[f"nf4_vs_bnb_{dt}_exact_frac"] = float((ref == mine).float().mean())
            RESULTS[f"nf4_vs_bnb_{dt}_maxabs"] = float((ref - mine).abs().max())
            # bnb outputs in the input dtype: compare after rounding ours the same way
            RESULTS[f"nf4_vs_bnb_{dt}_exact_frac_rounded"] = float((ref == mine.to(dt).float()).float().mean())
            assert RESULTS[f"nf4_vs_bnb_{dt}_exact_frac_rounded"] > 0.9999


def mx_reference(W: np.ndarray, block: int = 32) -> np.ndarray:
    import ml_dtypes

    b = W.reshape(-1, block).astype(np.float32)
    amax = np.abs(b).max(-1, keepdims=True)
    with np.errstate(divide="ignore"):
        e = np.where(amax > 0, np.floor(np.log2(amax.astype(np.float64))) - 2, -127)
    e = np.clip(e, -127, 127)
    scale = (2.0 ** e).astype(np.float32).astype(ml_dtypes.float8_e8m0fnu).astype(np.float32)
    v = (b / scale).astype(ml_dtypes.float4_e2m1fn).astype(np.float32)  # RNE, saturating to +-6
    return (v * scale).reshape(W.shape)


def test_mxfp4():
    torch.manual_seed(1)
    W = torch.randn(256, 2048) * 0.03
    W[0, :32] = 0
    # block with amax 6 -> shared exp floor(log2 6) - 2 = 0 (scale 1): exact RNE ties
    ties = [6.0, 5.0, -5.0, 0.25, 0.75, 1.25, 1.75, 2.5, 3.5, 0.3, -0.75]
    W[1, :32] = torch.tensor(ties + [0.1] * (32 - len(ties)))
    # block with amax 7.9 -> scale 1 as well; 7.9 and 7 saturate to 6
    W[2, :32] = torch.tensor([7.9, 7.0, -6.5] + [0.0] * 29)
    D = mxfp4_dequant(W)
    R = torch.from_numpy(mx_reference(W.numpy()))
    RESULTS["mxfp4_vs_mlDtypes_exact_frac"] = float((D == R).float().mean())
    assert torch.equal(D, R), f"mismatch {int((D != R).sum())}"
    want = [6.0, 4.0, -4.0, 0.0, 1.0, 1.0, 2.0, 2.0, 4.0, 0.5, -1.0]
    assert D[1, :len(ties)].tolist() == want, D[1, :len(ties)].tolist()
    assert D[2, :3].tolist() == [6.0, 6.0, -6.0]
    assert D[0, :32].abs().max() == 0
    # every element is an E2M1 value times its block's power-of-two scale
    blk = D.reshape(-1, 32)
    am = W.reshape(-1, 32).abs().amax(-1, keepdim=True)
    _, e = torch.frexp(am)
    v = torch.ldexp(blk, -(e - 3)).abs()
    assert torch.isin(v, torch.tensor(FP4_E2M1)).all()


def test_rtnsr():
    torch.manual_seed(2)
    W = torch.randn(64, 1024) * 0.02
    D1 = rtnsr_dequant(W, 4, torch.Generator().manual_seed(5))
    assert torch.equal(D1, rtnsr_dequant(W, 4, torch.Generator().manual_seed(5)))  # seeded
    q = Quantizer(4)
    blk = W.reshape(-1, 128)
    q.find_params(blk)
    k = D1.reshape(-1, 128) / q.scale + q.zero
    assert (k - k.round()).abs().max() < 1e-3 and k.round().min() >= 0 and k.round().max() <= 15  # on the rtn grid
    R = rtn_dequant(W, 4).reshape(-1, 128)
    step = (D1.reshape(-1, 128) - R).abs() / q.scale
    assert step.max() < 1 + 1e-3  # at most one grid step from RTN
    # unbiased: mean over 64 draws -> W (inside the grid range)
    M = torch.stack([rtnsr_dequant(W, 4, torch.Generator().manual_seed(s)) for s in range(64)]).mean(0)
    bias = ((M - W).reshape(-1, 128) / q.scale).abs().mean()
    RESULTS["rtnsr_mean_abs_bias_in_steps_64draws"] = float(bias)
    RESULTS["rtnsr_frac_differs_from_rtn"] = float((step > 0.5).float().mean())
    RESULTS["rtnsr_vs_rtn_err_ratio"] = float((D1 - W).norm() / (rtn_dequant(W, 4) - W).norm())
    assert bias < 0.1


def test_hadamard():
    for d in (64, 2560, 4096, 5120):
        H = hadamard(d)
        assert torch.equal(H @ H.T, d * torch.eye(d, dtype=torch.float64)), d
    Q = random_hadamard(2560, 0)
    assert torch.equal(Q, random_hadamard(2560, 0)) and not torch.equal(Q, random_hadamard(2560, 1))


def test_rotation_invariance():
    from transformers import AutoModelForCausalLM, Qwen3Config

    torch.manual_seed(0)
    cfg = Qwen3Config(vocab_size=512, hidden_size=64, intermediate_size=160, num_hidden_layers=3, num_attention_heads=4,
                      num_key_value_heads=2, head_dim=32, tie_word_embeddings=True, max_position_embeddings=256)
    m = AutoModelForCausalLM.from_config(cfg).float().eval()
    with torch.no_grad():  # non-trivial norm weights so fusion is exercised
        for n, p in m.named_parameters():
            if "norm" in n:
                p.copy_(1 + 0.3 * torch.randn_like(p))
    with tempfile.TemporaryDirectory() as td:
        src, out = Path(td, "src"), Path(td, "rot")
        m.save_pretrained(src, safe_serialization=True)
        rotate_main(["--src", str(src), "--out", str(out), "--seed", "3", "--device", "cpu", "--no-sha"])
        assert json.load(open(out / "config.json"))["tie_word_embeddings"] is False
        r = AutoModelForCausalLM.from_pretrained(out, dtype=torch.float32).eval()
        assert not torch.equal(r.lm_head.weight, r.model.embed_tokens.weight)
        ids = torch.randint(0, 512, (2, 40))
        with torch.no_grad():
            a = torch.log_softmax(m(ids).logits.double(), -1)
            b = torch.log_softmax(r(ids).logits.double(), -1)
        RESULTS["tiny_qwen3_rot_max_dlogprob_fp32"] = float((a - b).abs().max())
        assert RESULTS["tiny_qwen3_rot_max_dlogprob_fp32"] < 1e-3
        assert (a.argmax(-1) == b.argmax(-1)).all()
        # the stored weights really are rotated (not the identity)
        assert not torch.allclose(r.model.embed_tokens.weight, m.model.embed_tokens.weight)
        # RTN after rotation writes a quantized checkpoint
        rotate_main(["--src", str(src), "--out", str(Path(td, "rotq")), "--seed", "3", "--wbits", "4", "--device", "cpu", "--no-sha"])
        qm = json.load(open(Path(td, "rotq", "quantization.json")))
        assert qm["n_quantized_tensors"] == 3 * 7 and qm["method"] == "QuaRot-RTN"


if __name__ == "__main__":
    for f in (test_nf4, test_mxfp4, test_rtnsr, test_hadamard, test_rotation_invariance):
        f()
        print("ok", f.__name__)
    print(json.dumps(RESULTS, indent=1))
