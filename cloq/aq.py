"""Activation / KV fake-quantization math shared by the vLLM hooks (scripts/a6000/pyhooks/cloq_aq.py, cloq_kvq.py),
the offline builders (cloq/smoothquant.py, cloq/quarot.py) and the unit tests (tests/test_aq.py).
docs/insights/METHOD_FIDELITY.md documents every choice against the reference code.

Everything here is row-local: a statistic (max, min) is taken over the last dim of one row (one token, or one group
of one token), never across rows. So a token's quantized value cannot depend on other tokens of the batch, on later
tokens, on chunked-prefill boundaries or on the prefix cache.

Quantizers (x is converted to fp32; the caller casts the dequantized value back to its compute dtype, bf16):
  sym_quarot   QuaRot ActQuantizer / WeightQuantizer, symmetric (github.com/spcl/QuaRot fake_quant/quant_utils.py):
               xmax = max(|min(x,0)|, max(x,0)) * clip; s = xmax / (2^(b-1)-1); s = 1 where xmax == 0;
               q = clamp(round(x / s), -2^(b-1), 2^(b-1)-1); x_hat = s q
  sym_sq       SmoothQuant fake_quant.py quantize_activation_per_token_absmax / quantize_weight_per_channel_absmax
               (github.com/mit-han-lab/smoothquant): s = clamp(max|x|, 1e-5) / (2^(b-1)-1); x_hat = round(x / s) s
               (no clamp: |x / s| <= 2^(b-1)-1 by construction)
  asym_quarot_tok  QuaRot asymmetric per-row (ActQuantizer.find_params, groupsize -1; used for K):
               xmin = min(x,0) clip, xmax = max(x,0) clip; both 0 -> -1/+1; s = (xmax - xmin) / (2^b - 1);
               z = round(-xmin / s); q = clamp(round(x / s) + z, 0, 2^b - 1); x_hat = s (q - z)
  asym_quarot_grp  QuaRot asymmetric group-wise (find_params_per_token_groupwise; used for V, group = head_dim):
               like asym_quarot_tok but xmin = min(x) clip, xmax = max(x) clip (zero NOT forced into the range).
               Reference divides by s = 0 for a constant non-zero group (NaN); here such a group falls back to the
               zero-including range of asym_quarot_tok (documented deviation, degenerate input only).
Group-wise (group > 0): the row is split into consecutive groups of `group`; a trailing partial group (n % group)
is quantized as its own group (the references assert divisibility; the tail rule is ours and unit-tested).
Rounding is torch.round (round half to even) as in both references. Scales are fp32.

Hadamard transforms (QuaRot fake_quant/hadamard_utils.py):
  had(x) over the last dim n = K * 2^m: x.view(..., K, n/K) -> Walsh-Hadamard (Sylvester order) over the last dim,
  then H_K (K x K, +-1) mixes the K blocks, all / sqrt(n). This is matmul_hadU_cuda's layout (H = H_K kron H_{n/K}).
  Weights take the same transform on their input dim (rows w -> had(w)), so had(w) . had(x) = w . x.
  H_K: K = 12 is QuaRot's get_had12 (Sloane's library) verbatim; K = 20 is Paley I (q = 19, as cloq/rotate.py);
  K = 76 (Qwen3-4B intermediate 9728 = 76 * 128; not in QuaRot's table) is Paley II with q = 37.
  The K-block mix is a broadcast multiply + sum over the K blocks (no GEMM): one fused fixed-length reduction per
  output element inside Inductor-compiled graphs, independent of the batch / token count.
"""

from __future__ import annotations

import math

import torch

# ----------------------------------------------------------------------------------------------------------------
# Hadamard matrices
# ----------------------------------------------------------------------------------------------------------------

_HAD12_QUAROT = [  # QuaRot fake_quant/hadamard_utils.py get_had12 (Apache-2.0), from N. J. A. Sloane's library
    [+1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [+1, +1, -1, +1, -1, -1, -1, +1, +1, +1, -1, +1],
    [+1, +1, +1, -1, +1, -1, -1, -1, +1, +1, +1, -1],
    [+1, -1, +1, +1, -1, +1, -1, -1, -1, +1, +1, +1],
    [+1, +1, -1, +1, +1, -1, +1, -1, -1, -1, +1, +1],
    [+1, +1, +1, -1, +1, +1, -1, +1, -1, -1, -1, +1],
    [+1, +1, +1, +1, -1, +1, +1, -1, +1, -1, -1, -1],
    [+1, -1, +1, +1, +1, -1, +1, +1, -1, +1, -1, -1],
    [+1, -1, -1, +1, +1, +1, -1, +1, +1, -1, +1, -1],
    [+1, -1, -1, -1, +1, +1, +1, -1, +1, +1, -1, +1],
    [+1, +1, -1, -1, -1, +1, +1, +1, -1, +1, +1, -1],
    [+1, -1, +1, -1, -1, -1, +1, +1, +1, -1, +1, +1],
]


def _chi(q: int):
    sq = {(i * i) % q for i in range(1, q)}
    return lambda a: 0 if a % q == 0 else (1 if a % q in sq else -1)


def paley1(q: int) -> torch.Tensor:
    """Hadamard matrix of order q + 1, q prime, q = 3 mod 4 (Paley construction I)."""
    assert q % 4 == 3
    chi = _chi(q)
    Qm = torch.tensor([[chi(j - i) for j in range(q)] for i in range(q)], dtype=torch.float64)
    S = torch.zeros(q + 1, q + 1, dtype=torch.float64)
    S[0, 1:] = 1
    S[1:, 0] = -1
    S[1:, 1:] = Qm
    return S + torch.eye(q + 1, dtype=torch.float64)


def paley2(q: int) -> torch.Tensor:
    """Hadamard matrix of order 2(q + 1), q prime, q = 1 mod 4 (Paley construction II)."""
    assert q % 4 == 1
    chi = _chi(q)
    Qm = torch.tensor([[chi(j - i) for j in range(q)] for i in range(q)], dtype=torch.float64)
    C = torch.zeros(q + 1, q + 1, dtype=torch.float64)  # symmetric conference matrix
    C[0, 1:] = 1
    C[1:, 0] = 1
    C[1:, 1:] = Qm
    A = torch.tensor([[1.0, -1.0], [-1.0, -1.0]], dtype=torch.float64)
    B = torch.tensor([[1.0, 1.0], [1.0, -1.0]], dtype=torch.float64)
    I = torch.eye(q + 1, dtype=torch.float64)
    return torch.kron(C, B) + torch.kron(I, A)


_HAD_BUILDERS = {12: lambda: torch.tensor(_HAD12_QUAROT, dtype=torch.float64), 20: lambda: paley1(19),
                 76: lambda: paley2(37)}


def is_pow2(n: int) -> bool:
    return n > 0 and n & (n - 1) == 0


def had_factor(n: int) -> tuple[int, torch.Tensor | None]:
    """(K, H_K) with n = K * 2^m; K = 1 -> H_K None. Checks H_K H_K^T = K I. Always built and checked on the CPU
    (vLLM constructs models under a CUDA default-device context with batch-invariant matmul overrides)."""
    if is_pow2(n):
        return 1, None
    for K in sorted(_HAD_BUILDERS, reverse=True):
        if n % K == 0 and is_pow2(n // K):
            with torch.device("cpu"):
                H = _HAD_BUILDERS[K]().cpu()
                G = (H[:, None, :] * H[None, :, :]).sum(-1)  # H H^T without a GEMM
                assert torch.equal(G, K * torch.eye(K, dtype=torch.float64)), f"H_{K} is not Hadamard"
            return K, H
    raise ValueError(f"no Hadamard construction for n = {n}")


def fwht(x: torch.Tensor) -> torch.Tensor:
    """Unnormalized Walsh-Hadamard transform (Sylvester order) over the last dim (a power of 2)."""
    d = x.shape[-1]
    lead = x.shape[:-1]
    h = 1
    while h < d:
        y = x.reshape(*lead, d // (2 * h), 2, h)
        a, b = y[..., 0, :], y[..., 1, :]
        x = torch.stack((a + b, a - b), dim=-2).reshape(*lead, d)
        h *= 2
    return x


def had_mix(x: torch.Tensor, HK: list[list[int]]) -> torch.Tensor:
    """y[..., k, :] = sum_j HK[k][j] x[..., j, :] (HK entries +-1) as a broadcast multiply + sum over j, no GEMM: under
    Inductor one fused reduction of fixed length K per output element (order independent of the token count)."""
    Hm = torch.tensor(HK, dtype=x.dtype, device=x.device)
    return (Hm[:, :, None] * x.unsqueeze(-3)).sum(-2)


def had_transform(x: torch.Tensor, K: int, HK: list[list[int]] | None) -> torch.Tensor:
    """Normalized H_K kron H_{n/K} over the last dim (QuaRot matmul_hadU_cuda layout). fp32 in, fp32 out."""
    n = x.shape[-1]
    if K == 1:
        return fwht(x) * (n ** -0.5)
    lead = x.shape[:-1]
    y = fwht(x.reshape(*lead, K, n // K))
    y = had_mix(y, HK)
    return y.reshape(*lead, n) * (n ** -0.5)


def had_heads(x: torch.Tensor, n_heads: int) -> torch.Tensor:
    """QuaRot online_partial_had (K = 1): Walsh-Hadamard across the head index, per within-head position.
    x: (..., n_heads * head_dim) -> same shape; normalized by 1/sqrt(n_heads)."""
    lead, n = x.shape[:-1], x.shape[-1]
    hd = n // n_heads
    y = x.reshape(*lead, n_heads, hd).transpose(-1, -2)
    y = fwht(y) * (n_heads ** -0.5)
    return y.transpose(-1, -2).reshape(*lead, n)


# ----------------------------------------------------------------------------------------------------------------
# Quantizers (fp32)
# ----------------------------------------------------------------------------------------------------------------


def _groups(x: torch.Tensor, group: int, fn) -> torch.Tensor:
    """Apply a per-row quantizer fn over groups of the last dim; a trailing partial group is its own group."""
    n = x.shape[-1]
    if group <= 0 or group >= n:
        return fn(x)
    lead = x.shape[:-1]
    main = (n // group) * group
    parts = []
    if main:
        parts.append(fn(x[..., :main].reshape(*lead, n // group, group)).reshape(*lead, main))
    if main < n:
        parts.append(fn(x[..., main:]))
    return torch.cat(parts, dim=-1) if len(parts) > 1 else parts[0]


def _sym_quarot_row(x: torch.Tensor, bits: int, clip: float) -> torch.Tensor:
    maxq = float(2 ** (bits - 1) - 1)
    xmax = torch.maximum(x.amax(-1, keepdim=True).clamp_min(0.0), (-x.amin(-1, keepdim=True)).clamp_min(0.0))
    if clip != 1.0:
        xmax = xmax * clip
    s = torch.where(xmax == 0, torch.ones_like(xmax), xmax / maxq)
    return torch.clamp(torch.round(x / s), -(maxq + 1), maxq) * s


def _sym_sq_row(x: torch.Tensor, bits: int, clip: float) -> torch.Tensor:
    assert clip == 1.0, "SmoothQuant's per-token quantizer has no clipping"
    maxq = float(2 ** (bits - 1) - 1)
    s = x.abs().amax(-1, keepdim=True).clamp_min(1e-5) / maxq
    return torch.round(x / s) * s


def _asym_quarot_row(x: torch.Tensor, bits: int, clip: float, include_zero: bool) -> torch.Tensor:
    maxq = float(2 ** bits - 1)
    xmin = x.amin(-1, keepdim=True)
    xmax = x.amax(-1, keepdim=True)
    if include_zero:
        xmin, xmax = xmin.clamp_max(0.0), xmax.clamp_min(0.0)
    else:  # degenerate constant non-zero group: the reference would divide by zero; use the zero-including range
        const = xmax == xmin
        xmin = torch.where(const, xmin.clamp_max(0.0), xmin)
        xmax = torch.where(const, xmax.clamp_min(0.0), xmax)
    if clip != 1.0:
        xmin, xmax = xmin * clip, xmax * clip
    both0 = (xmin == 0) & (xmax == 0)
    xmin = torch.where(both0, -torch.ones_like(xmin), xmin)
    xmax = torch.where(both0, torch.ones_like(xmax), xmax)
    s = (xmax - xmin) / maxq
    z = torch.round(-xmin / s)
    q = torch.clamp(torch.round(x / s) + z, 0.0, maxq)
    return s * (q - z)


def qdq(x: torch.Tensor, bits: int, fmt: str = "sym_quarot", clip: float = 1.0, group: int = -1) -> torch.Tensor:
    """Quantize-dequantize every row (or group) of x over the last dim. Returns fp32."""
    x = x.float()
    if bits >= 16:
        return x
    if fmt == "sym_quarot":
        fn = lambda t: _sym_quarot_row(t, bits, clip)  # noqa: E731
    elif fmt == "sym_sq":
        fn = lambda t: _sym_sq_row(t, bits, clip)  # noqa: E731
    elif fmt == "asym_quarot_tok":
        fn = lambda t: _asym_quarot_row(t, bits, clip, True)  # noqa: E731
    elif fmt == "asym_quarot_grp":
        fn = lambda t: _asym_quarot_row(t, bits, clip, False)  # noqa: E731
    else:
        raise ValueError(fmt)
    return _groups(x, group, fn)


# ----------------------------------------------------------------------------------------------------------------
# Weight quantizers used by the offline builders
# ----------------------------------------------------------------------------------------------------------------


@torch.no_grad()
def quarot_weight_params(W: torch.Tensor, bits: int, sym: bool = True, mse: bool = True, norm: float = 2.4,
                         grid: int = 100, maxshrink: float = 0.8) -> tuple[torch.Tensor, torch.Tensor, float]:
    """QuaRot WeightQuantizer.find_params (per-channel = per output row), incl. the w_clip MSE grid search.
    Returns (scale [rows,1], zero [rows,1], maxq)."""
    W = W.float()
    dev = W.device
    maxq = float(2 ** (bits - 1) - 1) if sym else float(2 ** bits - 1)
    tmp = torch.zeros(W.shape[0], device=dev)
    xmin = torch.minimum(W.min(1)[0], tmp)
    xmax = torch.maximum(W.max(1)[0], tmp)
    if sym:
        xmax = torch.maximum(torch.abs(xmin), xmax).clamp(min=1e-5)
        scale = xmax / maxq
        zero = torch.zeros_like(scale)
    else:
        t = (xmin == 0) & (xmax == 0)
        xmin[t], xmax[t] = -1, +1
        scale = (xmax - xmin).clamp(min=1e-5) / maxq
        zero = torch.round(-xmin / scale)
    if mse:
        best = torch.full([W.shape[0]], float("inf"), device=dev)
        for i in range(int(maxshrink * grid)):
            p = 1 - i / grid
            xmin1, xmax1 = p * xmin, p * xmax
            if sym:
                scale1 = xmax1 / maxq
                zero1 = torch.zeros_like(scale1)
                q = torch.clamp(torch.round(W / scale1.unsqueeze(1)), -(maxq + 1), maxq) * scale1.unsqueeze(1)
            else:
                scale1 = (xmax1 - xmin1) / maxq
                zero1 = torch.round(-xmin1 / scale1)
                q = scale1.unsqueeze(1) * (torch.clamp(torch.round(W / scale1.unsqueeze(1)) + zero1.unsqueeze(1), 0, maxq)
                                           - zero1.unsqueeze(1))
            q -= W
            q.abs_()
            q.pow_(norm)
            err = torch.sum(q, 1)
            t = err < best
            if torch.any(t):
                best[t] = err[t]
                scale[t] = scale1[t]
                zero[t] = zero1[t]
    return scale.reshape(-1, 1), zero.reshape(-1, 1), maxq


def quarot_weight_qdq(w: torch.Tensor, scale: torch.Tensor, zero: torch.Tensor, maxq: float, sym: bool = True) -> torch.Tensor:
    if sym:
        return torch.clamp(torch.round(w / scale), -(maxq + 1), maxq) * scale
    return scale * (torch.clamp(torch.round(w / scale) + zero, 0, maxq) - zero)


@torch.no_grad()
def sq_weight_per_channel_absmax(W: torch.Tensor, bits: int = 8) -> torch.Tensor:
    """SmoothQuant quantize_weight_per_channel_absmax (fp32 here; the reference runs in the model dtype)."""
    W = W.float()
    s = W.abs().amax(dim=-1, keepdim=True).clamp(min=1e-5) / float(2 ** (bits - 1) - 1)
    return torch.round(W / s) * s


def hadK_list(K: int, H: torch.Tensor | None) -> list[list[int]] | None:
    return None if H is None else [[int(v) for v in row] for row in H.tolist()]


def is_close_orthogonal(n: int) -> float:
    """max |H H^T / n - I| of the normalized transform of size n (for tests / provenance)."""
    K, H = had_factor(n)
    E = torch.eye(n, dtype=torch.float64)
    M = had_transform(E, K, hadK_list(K, H))
    return float((M @ M.T - E).abs().max())


__all__ = ["qdq", "had_transform", "had_heads", "had_factor", "hadK_list", "fwht", "paley1", "paley2",
           "quarot_weight_params", "quarot_weight_qdq", "sq_weight_per_channel_absmax", "is_pow2"]

