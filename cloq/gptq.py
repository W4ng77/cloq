"""GPTQ core (weight-only, asymmetric, grouped, optional act-order).

Ported from tim-gptq `implementations/whisper_qwen/src/gptq.py` + `quant.py`
(same Hessian accumulation, damping, Cholesky inverse, block updates), with the
QEP / rotation / FP4 branches removed. Only nn.Linear is supported here.
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn

torch.backends.cuda.matmul.allow_tf32 = False
torch.backends.cudnn.allow_tf32 = False


# ----------------------------------------------------------------------------
# Uniform asymmetric quantizer (from tim-gptq quant.py, weight/per-row only)
# ----------------------------------------------------------------------------


def quantize(x: torch.Tensor, scale: torch.Tensor, zero: torch.Tensor, maxq: int) -> torch.Tensor:
    q = torch.clamp(torch.round(x / scale) + zero, 0, maxq)
    return scale * (q - zero)


class Quantizer:
    def __init__(self, wbits: int, sym: bool = False):
        self.maxq = 2**wbits - 1
        self.sym = sym
        self.scale = None
        self.zero = None

    def find_params(self, x: torch.Tensor) -> None:
        """x: [rows, cols]; per-row min/max over cols."""
        dev = x.device
        tmp = torch.zeros(x.shape[0], device=dev, dtype=x.dtype)
        xmin = torch.minimum(x.min(1)[0], tmp)
        xmax = torch.maximum(x.max(1)[0], tmp)
        if self.sym:
            xmax = torch.maximum(torch.abs(xmin), xmax)
            neg = xmin < 0
            if torch.any(neg):
                xmin[neg] = -xmax[neg]
        both_zero = (xmin == 0) & (xmax == 0)
        xmin[both_zero] = -1
        xmax[both_zero] = +1
        self.scale = (xmax - xmin) / self.maxq
        if self.sym:
            self.zero = torch.full_like(self.scale, (self.maxq + 1) / 2)
        else:
            self.zero = torch.round(-xmin / self.scale)
        self.scale = self.scale.unsqueeze(1)
        self.zero = self.zero.unsqueeze(1)

    def ready(self) -> bool:
        return self.scale is not None


# ----------------------------------------------------------------------------
# Damped Cholesky (identical to tim-gptq)
# ----------------------------------------------------------------------------


def _damped_cholesky(hessian: torch.Tensor, percdamp: float, max_retries: int = 8, damp_multiplier: float = 10.0):
    diagonal_mean = torch.diagonal(hessian).abs().mean().clamp_min(1e-12)
    base_damp = max(float(percdamp), 1e-8) * float(diagonal_mean)
    diagonal = torch.arange(hessian.shape[0], device=hessian.device)
    last_error = None
    for retry in range(max_retries):
        damp = base_damp * (damp_multiplier**retry)
        damped = hessian.clone()
        damped[diagonal, diagonal] += damp
        try:
            return torch.linalg.cholesky(damped), damp
        except RuntimeError as error:
            if "cholesky" not in str(error).lower():
                raise
            last_error = error
    raise RuntimeError(f"Cholesky failed after {max_retries} damping attempts; last error: {last_error}")


def gptq_inverse_factor(hessian: torch.Tensor, percdamp: float):
    factor, damp = _damped_cholesky(hessian, percdamp)
    inverse = torch.cholesky_inverse(factor)
    return torch.linalg.cholesky(inverse, upper=True), damp


# ----------------------------------------------------------------------------
# Per-layer helper: Hessian accumulation + GPTQ solve
# ----------------------------------------------------------------------------


class GPTQLinear:
    """Accumulate H = 2/N * sum x x^T for one nn.Linear, then quantize it."""

    def __init__(self, layer: nn.Linear):
        assert isinstance(layer, nn.Linear)
        self.layer = layer
        self.device = layer.weight.device
        cols = layer.weight.shape[1]
        self.H = torch.zeros((cols, cols), device=self.device, dtype=torch.float32)
        self.nsamples = 0  # number of token rows accumulated
        self.ntokens = 0

    @torch.no_grad()
    def add_batch(self, inp: torch.Tensor) -> None:
        """inp: [..., in_features]; every row is one token (no padding)."""
        x = inp.reshape(-1, inp.shape[-1]).t().float()  # [cols, tokens]
        n_new = x.shape[1]
        if n_new == 0:
            return
        old = self.nsamples
        self.nsamples += n_new
        self.ntokens += n_new
        self.H *= old / self.nsamples
        x = math.sqrt(2 / self.nsamples) * x
        self.H += x @ x.t()

    @torch.no_grad()
    def run_gptq(
        self,
        wbits: int = 4,
        groupsize: int = 128,
        blocksize: int = 128,
        percdamp: float = 0.01,
        actorder: bool = True,
        sym: bool = False,
    ) -> dict:
        W = self.layer.weight.detach().clone().float()  # [rows, cols]
        H = self.H.clone()
        del self.H
        quantizer = Quantizer(wbits, sym=sym)

        dead = torch.diag(H) == 0
        H[dead, dead] = 1
        W[:, dead] = 0

        if actorder:
            perm = torch.argsort(torch.diag(H), descending=True)
            W = W[:, perm]
            H = H[perm][:, perm]
            invperm = torch.argsort(perm)

        Hinv, damp = gptq_inverse_factor(H, percdamp)
        Q = torch.zeros_like(W)
        Losses = torch.zeros_like(W)
        n_cols = W.shape[1]

        for i1 in range(0, n_cols, blocksize):
            i2 = min(i1 + blocksize, n_cols)
            count = i2 - i1
            W1 = W[:, i1:i2].clone()
            Q1 = torch.zeros_like(W1)
            Err1 = torch.zeros_like(W1)
            Losses1 = torch.zeros_like(W1)
            Hinv1 = Hinv[i1:i2, i1:i2]
            for i in range(count):
                w = W1[:, i]
                d = Hinv1[i, i]
                if groupsize != -1 and (i1 + i) % groupsize == 0:
                    quantizer.find_params(W[:, (i1 + i):(i1 + i + groupsize)])
                elif not quantizer.ready():
                    quantizer.find_params(W)
                q = quantize(w.unsqueeze(1), quantizer.scale, quantizer.zero, quantizer.maxq).flatten()
                Q1[:, i] = q
                Losses1[:, i] = (w - q) ** 2 / d**2
                err1 = (w - q) / d
                W1[:, i:] -= err1.unsqueeze(1).matmul(Hinv1[i, i:].unsqueeze(0))
                Err1[:, i] = err1
            Q[:, i1:i2] = Q1
            Losses[:, i1:i2] = Losses1 / 2
            W[:, i2:] -= Err1.matmul(Hinv[i1:i2, i2:])

        if actorder:
            Q = Q[:, invperm]

        W0 = self.layer.weight.detach().float()
        rel = float(((Q - W0) ** 2).sum() / (W0**2).sum().clamp_min(1e-12))
        self.layer.weight.data.copy_(Q.to(self.layer.weight.dtype))
        return {"gptq_loss": float(Losses.sum()), "rel_weight_err": rel, "damp": float(damp), "ntokens": int(self.ntokens)}

    def free(self) -> None:
        if hasattr(self, "H"):
            del self.H
        torch.cuda.empty_cache()


@torch.no_grad()
def rtn_quantize_linear(layer: nn.Linear, wbits: int = 4, groupsize: int = 128, sym: bool = False) -> dict:
    """Round-to-nearest baseline with the same grid (no calibration)."""
    W = layer.weight.detach().clone().float()
    q = Quantizer(wbits, sym=sym)
    Q = torch.zeros_like(W)
    n_cols = W.shape[1]
    for g in range(0, n_cols, groupsize):
        blk = W[:, g:g + groupsize]
        q.find_params(blk)
        Q[:, g:g + groupsize] = quantize(blk, q.scale, q.zero, q.maxq)
    rel = float(((Q - W) ** 2).sum() / (W**2).sum().clamp_min(1e-12))
    layer.weight.data.copy_(Q.to(layer.weight.dtype))
    return {"rel_weight_err": rel}
