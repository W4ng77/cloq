"""Reference quantizers copied (verbatim logic, trimmed to what tests/test_aq.py needs) from the official code.

QuaRot  github.com/spcl/QuaRot @ 5008669b08c1f11f9b64d52d16fddd47ca754c5a, fake_quant/quant_utils.py and
        fake_quant/hadamard_utils.py (Apache-2.0). Only torch.nn buffers / utils.cleanup_memory removed.
SmoothQuant github.com/mit-han-lab/smoothquant @ c61476d728e42ae0d8a35e7e78494edcac3237b5, smoothquant/fake_quant.py
        and smoothquant/smooth.py (MIT).
Used only by the unit tests; never imported by serving or builders.
"""
import torch


# ---------------- QuaRot quant_utils.py ----------------
def get_minq_maxq(bits, sym):
    if sym:
        maxq = torch.tensor(2**(bits-1)-1)
        minq = -maxq - 1
    else:
        maxq = torch.tensor(2**bits - 1)
        minq = 0
    return minq, maxq


def asym_quant(x, scale, zero, maxq):
    scale = scale.to(x.device)
    zero = zero.to(x.device)
    q = torch.clamp(torch.round(x / scale) + zero, 0, maxq)
    return q, scale, zero


def asym_dequant(q, scale, zero):
    return scale * (q - zero)


def asym_quant_dequant(x, scale, zero, maxq):
    return asym_dequant(*asym_quant(x, scale, zero, maxq))


def sym_quant(x, scale, maxq):
    scale = scale.to(x.device)
    q = torch.clamp(torch.round(x / scale), -(maxq+1), maxq)
    return q, scale


def sym_dequant(q, scale):
    return scale * q


def sym_quant_dequant(x, scale, maxq):
    return sym_dequant(*sym_quant(x, scale, maxq))


class ActQuantizer:
    def __init__(self):
        self.maxq = torch.tensor(0)
        self.scale = torch.zeros(1)
        self.zero = torch.zeros(1)
        self.bits = 16

    def __call__(self, x):
        x_dtype = x.dtype
        if self.bits == 16:
            return x
        elif self.sym:
            return sym_quant_dequant(x, self.scale, self.maxq).to(x_dtype)
        return asym_quant_dequant(x, self.scale, self.zero, self.maxq).to(x_dtype)

    def configure(self, bits, groupsize=-1, sym=False, clip_ratio=1.0):
        _, self.maxq = get_minq_maxq(bits, sym)
        self.bits = bits
        self.groupsize = groupsize
        self.sym = sym
        self.clip_ratio = clip_ratio

    def find_params_per_token_groupwise(self, x):
        init_shape = x.shape
        reshaped_x = x.reshape(-1, x.shape[-2], x.shape[-1] // self.groupsize, self.groupsize)
        xmax = torch.amax(reshaped_x, dim=3, keepdim=True) * self.clip_ratio
        xmin = torch.amin(reshaped_x, dim=3, keepdim=True) * self.clip_ratio
        if self.sym:
            xmax = torch.maximum(torch.abs(xmin), xmax)
            tmp = xmax == 0
            self.scale = xmax / self.maxq
            self.scale[tmp] = 1
            self.zero = torch.zeros_like(self.scale)
        else:
            tmp = (xmin == 0) & (xmax == 0)
            xmin[tmp] = -1
            xmax[tmp] = +1
            self.scale = (xmax - xmin) / self.maxq
            self.zero = torch.round(-xmin / self.scale)
        self.scale = self.scale.repeat(1, 1, 1, self.groupsize).reshape(init_shape)
        self.zero = self.zero.repeat(1, 1, 1, self.groupsize).reshape(init_shape)

    def find_params(self, x):
        if self.bits == 16:
            return
        dev = x.device
        self.maxq = self.maxq.to(dev)
        init_shape = x.shape
        if self.groupsize > 0:
            self.find_params_per_token_groupwise(x)
            return
        reshaped_x = x.reshape((-1, x.shape[-1]))
        tmp = torch.zeros(reshaped_x.shape[0], device=dev)
        xmin = torch.minimum(reshaped_x.min(1)[0], tmp) * self.clip_ratio
        xmax = torch.maximum(reshaped_x.max(1)[0], tmp) * self.clip_ratio
        if self.sym:
            xmax = torch.maximum(torch.abs(xmin), xmax)
            tmp = xmax == 0
            self.scale = (xmax / self.maxq).unsqueeze(1).repeat(1, reshaped_x.shape[-1])
            self.scale[tmp] = 1
            self.scale = self.scale.reshape(init_shape)
            self.zero = torch.zeros_like(self.scale)
        else:
            tmp = (xmin == 0) & (xmax == 0)
            xmin[tmp] = -1
            xmax[tmp] = +1
            self.scale = (xmax - xmin) / self.maxq
            self.zero = torch.round(-xmin / self.scale)
            self.scale = self.scale.unsqueeze(1).repeat(1, reshaped_x.shape[-1]).reshape(init_shape)
            self.zero = self.zero.unsqueeze(1).repeat(1, reshaped_x.shape[-1]).reshape(init_shape)


class WeightQuantizer:
    def configure(self, bits, perchannel=False, sym=True, mse=False, norm=2.4, grid=100, maxshrink=.8):
        self.bits = bits
        self.perchannel = perchannel
        self.sym = sym
        self.mse = mse
        self.norm = norm
        self.grid = grid
        self.maxshrink = maxshrink
        if sym:
            self.maxq = torch.tensor(2**(bits-1)-1)
        else:
            self.maxq = torch.tensor(2**bits - 1)

    def find_params(self, x):
        dev = x.device
        self.maxq = self.maxq.to(dev)
        shape = x.shape
        if self.perchannel:
            x = x.flatten(1)
        else:
            x = x.flatten().unsqueeze(0)
        tmp = torch.zeros(x.shape[0], device=dev)
        xmin = torch.minimum(x.min(1)[0], tmp)
        xmax = torch.maximum(x.max(1)[0], tmp)
        if self.sym:
            xmax = torch.maximum(torch.abs(xmin), xmax).clamp(min=1e-5)
            self.scale = xmax / self.maxq
            self.zero = torch.zeros_like(self.scale)
        else:
            tmp = (xmin == 0) & (xmax == 0)
            xmin[tmp] = -1
            xmax[tmp] = +1
            self.scale = (xmax - xmin).clamp(min=1e-5) / self.maxq
            self.zero = torch.round(-xmin / self.scale)
        if self.mse:
            best = torch.full([x.shape[0]], float('inf'), device=dev)
            for i in range(int(self.maxshrink * self.grid)):
                p = 1 - i / self.grid
                xmin1 = p * xmin
                xmax1 = p * xmax
                if self.sym:
                    scale1 = xmax1 / self.maxq
                    zero1 = torch.zeros_like(scale1)
                    q = sym_quant_dequant(x, scale1.unsqueeze(1), self.maxq)
                else:
                    scale1 = (xmax1 - xmin1) / self.maxq
                    zero1 = torch.round(-xmin1 / scale1)
                    q = asym_quant_dequant(x, scale1.unsqueeze(1), zero1.unsqueeze(1), self.maxq)
                q -= x
                q.abs_()
                q.pow_(self.norm)
                err = torch.sum(q, 1)
                tmp = err < best
                if torch.any(tmp):
                    best[tmp] = err[tmp]
                    self.scale[tmp] = scale1[tmp]
                    self.zero[tmp] = zero1[tmp]
        shape = [-1] + [1] * (len(shape) - 1)
        self.scale = self.scale.reshape(shape)
        self.zero = self.zero.reshape(shape)

    def quantize(self, x):
        if self.sym:
            return sym_quant_dequant(x, self.scale, self.maxq)
        return asym_quant_dequant(x, self.scale, self.zero, self.maxq)


# ---------------- QuaRot hadamard_utils.py (CPU path) ----------------
def matmul_hadU(X, hadK, K):
    """matmul_hadU with get_hadK's (hadK, K) passed in (the reference looks them up by n)."""
    n = X.shape[-1]
    input = X.clone().view(-1, n, 1)
    output = input.clone()
    while input.shape[1] > K:
        input = input.view(input.shape[0], input.shape[1] // 2, 2, input.shape[2])
        output = output.view(input.shape)
        output[:, :, 0, :] = input[:, :, 0, :] + input[:, :, 1, :]
        output[:, :, 1, :] = input[:, :, 0, :] - input[:, :, 1, :]
        output = output.view(input.shape[0], input.shape[1], -1)
        (input, output) = (output, input)
    del output
    if K > 1:
        input = hadK.view(1, K, K).to(input) @ input
    return input.view(X.shape) / torch.tensor(n).sqrt()


# ---------------- SmoothQuant fake_quant.py / smooth.py ----------------
@torch.no_grad()
def sq_quantize_weight_per_channel_absmax(w, n_bits=8):
    scales = w.abs().max(dim=-1, keepdim=True)[0]
    q_max = 2 ** (n_bits - 1) - 1
    scales.clamp_(min=1e-5).div_(q_max)
    w.div_(scales).round_().mul_(scales)
    return w


@torch.no_grad()
def sq_quantize_activation_per_token_absmax(t, n_bits=8):
    t_shape = t.shape
    t.view(-1, t_shape[-1])
    scales = t.abs().max(dim=-1, keepdim=True)[0]
    q_max = 2 ** (n_bits - 1) - 1
    scales.clamp_(min=1e-5).div_(q_max)
    t.div_(scales).round_().mul_(scales)
    return t


@torch.no_grad()
def sq_smooth_ln_fcs_llama_like(ln_weight, fc_weights, act_scales, alpha=0.5):
    """smooth_ln_fcs_llama_like on raw tensors (ln.weight, [fc.weight]); modifies them in place."""
    device, dtype = fc_weights[0].device, fc_weights[0].dtype
    act_scales = act_scales.to(device=device, dtype=dtype)
    weight_scales = torch.cat([w.abs().max(dim=0, keepdim=True)[0] for w in fc_weights], dim=0)
    weight_scales = weight_scales.max(dim=0)[0].clamp(min=1e-5)
    scales = (act_scales.pow(alpha) / weight_scales.pow(1 - alpha)).clamp(min=1e-5).to(device).to(dtype)
    ln_weight.div_(scales)
    for w in fc_weights:
        w.mul_(scales.view(1, -1))
    return scales


# ---------------- QuaRot gptq_utils.py: GPTQ.fasterquant (groupsize -1, static_groups False) ----------------
def quarot_fasterquant(W, H, quantizer, blocksize=128, percdamp=.01, actorder=False):
    """Body of GPTQ.fasterquant on explicit (W, H) instead of a layer; quantizer = configured WeightQuantizer."""
    W = W.clone().float()
    columns = W.shape[1]
    quantizer.find_params(W)
    H = H.clone()
    dead = torch.diag(H) == 0
    H[dead, dead] = 1
    W[:, dead] = 0
    if actorder:
        perm = torch.argsort(torch.diag(H), descending=True)
        W = W[:, perm]
        H = H[perm][:, perm]
        invperm = torch.argsort(perm)
    Q = torch.zeros_like(W)
    damp = percdamp * torch.mean(torch.diag(H))
    diag = torch.arange(columns, device=W.device)
    H[diag, diag] += damp
    H = torch.linalg.cholesky(H)
    H = torch.cholesky_inverse(H)
    H = torch.linalg.cholesky(H, upper=True)
    Hinv = H
    for i1 in range(0, columns, blocksize):
        i2 = min(i1 + blocksize, columns)
        count = i2 - i1
        W1 = W[:, i1:i2].clone()
        Q1 = torch.zeros_like(W1)
        Err1 = torch.zeros_like(W1)
        Hinv1 = Hinv[i1:i2, i1:i2]
        for i in range(count):
            w = W1[:, i]
            d = Hinv1[i, i]
            q = quantizer.quantize(w.unsqueeze(1)).flatten()
            Q1[:, i] = q
            err1 = (w - q) / d
            W1[:, i:] -= err1.unsqueeze(1).matmul(Hinv1[i, i:].unsqueeze(0))
            Err1[:, i] = err1
        Q[:, i1:i2] = Q1
        W[:, i2:] -= Err1.matmul(Hinv[i1:i2, i2:])
    if actorder:
        Q = Q[:, invperm]
    return Q
