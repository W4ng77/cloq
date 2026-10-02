"""Reference implementations for the KIVI gate (docs/RESEARCH_LOG.md W99t; analysis/fork/kivi_gate/GATE.md).

OfficialKIVI  literal port of the cache logic of the official KIVI attention (github.com/jy-yuan/KIVI,
              models/llama_kivi.py LlamaFlashAttention_KIVI.forward, commit 876b4d2): prefill and one-token decode
              branches, quantization by the official `triton_quantize_and_pack_along_last_dim` (quant/new_pack.py),
              packed codes unpacked by the official `unpack_tensor`. The only substitution: the official fused CUDA
              kernel `cuda_bmm_fA_qB_outer` (fA x dequant(qB)) is computed as unpack -> dequant (codes*scale+mn, the
              official unpack_and_dequant formula) -> matmul. GQA by repeat_kv as in the official class.
view_attention  closed form of the per-query view that the serving kernel implements: query t sees K_i quantized iff
              i < R*floor(t/R) (per-channel, G-token groups) and V_i quantized iff i < t-R (per-token, G-channel
              groups); its own k_t, v_t and the rest full precision. fp32, one query at a time.
"""
from __future__ import annotations

import math
import sys

import torch

KIVI_DIR = "/data/ziyangs/cloq_work/kivi_official"  # git clone https://github.com/jy-yuan/KIVI @ 876b4d2


def _official():
    if KIVI_DIR not in sys.path:
        sys.path.insert(0, KIVI_DIR)
    from quant.new_pack import quant_and_pack_vcache, triton_quantize_and_pack_along_last_dim, unpack_tensor
    return triton_quantize_and_pack_along_last_dim, unpack_tensor, quant_and_pack_vcache


def official_qdq_lastdim(x: torch.Tensor, group: int, bits: int):
    """Official quantize+pack along the last dim, then official unpack and dequant. x [B, nh, X, T].
    Returns (dequantized, int codes)."""
    qp, unpack, qp_torch = _official()
    if x.is_cuda:
        code, scale, mn = qp(x.contiguous(), group, bits)
    else:  # CPU: the official torch twin (same math: min/max over last-dim groups, (x-mn)/s, clamp, round, pack)
        code, scale, mn = qp_torch(x.contiguous(), group, bits)
        scale, mn = scale.squeeze(-1), mn.squeeze(-1)
    q = unpack(code, bits, pack_dim=3)
    sh = q.shape
    deq = (q.to(scale.dtype).view(*sh[:-1], sh[-1] // group, group) * scale[..., None] + mn[..., None]).view(sh)
    return deq, q


def repeat_kv(x, n_rep):
    return x if n_rep == 1 else x.repeat_interleave(n_rep, dim=1)


class OfficialKIVI:
    """Stateful KIVI cache, B=1. q [1, Hq, L, D]; k, v [1, Hkv, L, D] (post-RoPE)."""

    def __init__(self, kbits, vbits, group=32, resid=128):
        self.kb, self.vb, self.G, self.R = kbits, vbits, group, resid
        self.past = None

    def prefill(self, q, k, v):
        G, R = self.G, self.R
        n_rep = q.shape[1] // k.shape[1]
        L = k.shape[-2]
        att = torch.matmul(q, repeat_kv(k, n_rep).transpose(2, 3)) / math.sqrt(q.shape[-1])
        mask = torch.ones(L, L, dtype=torch.bool, device=q.device).tril()
        att = att.masked_fill(~mask, float("-inf"))
        att = torch.softmax(att, dim=-1, dtype=torch.float32).to(q.dtype)
        out = torch.matmul(att, repeat_kv(v, n_rep))
        # --- official prefill quantization (verbatim structure) ---
        if k.shape[-2] % R != 0:
            if k.shape[-2] < R:
                k_quant, k_full = None, k
            else:
                k_quant = k[:, :, :-(k.shape[-2] % R), :].contiguous()
                k_full = k[:, :, -(k.shape[-2] % R):, :].contiguous()
        else:
            k_quant, k_full = k, None
        self.kq_trans = None if k_quant is None else official_qdq_lastdim(k_quant.transpose(2, 3), G, self.kb)[0]
        self.k_full = k_full
        if v.shape[-2] <= R:
            self.vq, self.v_full = None, v
        else:
            self.vq = official_qdq_lastdim(v[:, :, :-R, :], G, self.vb)[0]
            self.v_full = v[:, :, -R:, :].contiguous()
        return out

    def decode(self, q, k, v):
        G, R = self.G, self.R
        n_rep = q.shape[1] // k.shape[1]
        d = q.shape[-1]
        att_qkquant = None if self.kq_trans is None else torch.matmul(q, repeat_kv(self.kq_trans, n_rep))
        self.k_full = k if self.k_full is None else torch.cat([self.k_full, k], dim=2)
        att_qkfull = torch.matmul(q, repeat_kv(self.k_full, n_rep).transpose(2, 3))
        att = (torch.cat([att_qkquant, att_qkfull], dim=-1) if att_qkquant is not None else att_qkfull) / math.sqrt(d)
        if self.k_full.shape[-2] == R:
            assert R % G == 0
            new = official_qdq_lastdim(self.k_full.transpose(2, 3), G, self.kb)[0]
            self.k_full = None
            self.kq_trans = new if self.kq_trans is None else torch.cat([self.kq_trans, new], dim=3)
        att = torch.softmax(att, dim=-1, dtype=torch.float32).to(q.dtype)
        self.v_full = torch.cat([self.v_full, v], dim=2)
        n_full = self.v_full.shape[-2]
        if self.vq is None:
            out = torch.matmul(att, repeat_kv(self.v_full, n_rep))
        else:
            out = torch.matmul(att[:, :, :, :-n_full], repeat_kv(self.vq, n_rep))
            out += torch.matmul(att[:, :, :, -n_full:], repeat_kv(self.v_full, n_rep))
        if n_full > R:
            assert n_full == R + 1
            new = official_qdq_lastdim(self.v_full[:, :, :1, :], G, self.vb)[0]
            self.v_full = self.v_full[:, :, 1:, :].contiguous()
            self.vq = new if self.vq is None else torch.cat([self.vq, new], dim=2)
        return out

    def state_split(self):
        """(n quantized keys, n full keys, n quantized values, n full values)."""
        nkq = 0 if self.kq_trans is None else self.kq_trans.shape[-1]
        nkf = 0 if self.k_full is None else self.k_full.shape[-2]
        nvq = 0 if self.vq is None else self.vq.shape[-2]
        return nkq, nkf, nvq, self.v_full.shape[-2]


def qdq_ref(x, mn, mx, bits):
    """fp32 quantizer of the serving kernel, in torch: s=(mx-mn)/L, q=round(clamp((x-mn)/s)), x^=q*s+mn (s=0: x^=mn)."""
    L = float(2 ** bits - 1)
    s = (mx - mn) / L
    safe = torch.where(s > 0, s, torch.ones_like(s))
    q = torch.round(torch.clamp((x - mn) / safe, 0.0, L))
    q = torch.where(s > 0, q, torch.zeros_like(q))
    return q * s + mn, q


def kq_all(k, bits, G):
    """k [L, H, D] fp32 -> per-channel G-token-group dequantized keys for complete groups (rest NaN)."""
    L = k.shape[0]
    out = torch.full_like(k, float("nan"))
    n = (L // G) * G
    if n:
        x = k[:n].reshape(n // G, G, *k.shape[1:])
        out[:n] = qdq_ref(x, x.amin(1, keepdim=True), x.amax(1, keepdim=True), bits)[0].reshape(n, *k.shape[1:])
    return out


def vq_all(v, bits, G):
    sh = v.shape
    x = v.reshape(*sh[:-1], sh[-1] // G, G)
    return qdq_ref(x, x.amin(-1, keepdim=True), x.amax(-1, keepdim=True), bits)[0].reshape(sh)


def view_attention(q, k, v, kbits, vbits, G=32, R=128, scale=None):
    """q [L, Hq, D]; k, v [L, Hkv, D] -> out [L, Hq, D], fp32, per-query KIVI decode view."""
    q, k, v = q.float(), k.float(), v.float()
    L, Hq, D = q.shape
    n_rep = Hq // k.shape[1]
    scale = scale or D ** -0.5
    KQ = kq_all(k, kbits, G) if kbits < 16 else k
    VQ = vq_all(v, vbits, G) if vbits < 16 else v
    out = torch.empty_like(q)
    idx = torch.arange(L, device=q.device)
    for t in range(L):
        kb = (t // R) * R if kbits < 16 else -1
        vb = t - R if vbits < 16 else -1 - R
        kk = torch.where((idx[: t + 1] < kb)[:, None, None], KQ[: t + 1], k[: t + 1])
        vv = torch.where((idx[: t + 1] < vb)[:, None, None], VQ[: t + 1], v[: t + 1])
        kk, vv = kk.repeat_interleave(n_rep, 1), vv.repeat_interleave(n_rep, 1)
        s = torch.einsum("hd,thd->ht", q[t], kk) * scale
        p = torch.softmax(s, -1)
        out[t] = torch.einsum("ht,thd->hd", p, vv)
    return out
