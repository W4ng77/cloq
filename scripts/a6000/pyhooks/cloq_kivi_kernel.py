"""Triton kernel of the KIVI serving hook (cloq_kivi.py; semantics and numerics documented there)."""
import triton
import triton.language as tl


@triton.jit
def _rint(x):
    """Round half to even (torch.round), exact for finite x >= 0: floor and the fraction are exact in fp32."""
    r = tl.floor(x)
    f = x - r
    odd = (r - 2.0 * tl.floor(r * 0.5)) == 1.0
    up = (f > 0.5) | ((f == 0.5) & odd)
    return tl.where(up, r + 1.0, r)


@triton.jit
def _qdq(x, mn, mx, LEVELS: tl.constexpr):
    """KIVI asymmetric quantize-dequantize, fp32: s=(mx-mn)/L; q=round(clamp((x-mn)/s, 0, L)); x^=q*s+mn.
    IEEE division (div_rn); the kernel is compiled with enable_fp_fusion=False, so q*s+mn is a rounded multiply then a
    rounded add (as torch). A constant group (s=0) returns mn (= x)."""
    s = tl.div_rn(mx - mn, LEVELS * 1.0)
    safe = tl.where(s > 0, s, 1.0)
    q = tl.div_rn(x - mn, safe)
    q = _rint(tl.minimum(tl.maximum(q, 0.0), LEVELS * 1.0))
    q = tl.where(s > 0, q, 0.0)
    return q * s + mn


@triton.jit(do_not_specialize=["num_seqs", "bt_stride", "q_s0", "q_s1", "o_s0", "o_s1", "c_s0", "c_s1", "c_s2"])
def kivi_attn_kernel(Q, Kc, Vc, O, cu_q, seq_lens, block_table, sm_scale, num_seqs, bt_stride,
                     q_s0, q_s1, o_s0, o_s1, c_s0, c_s1, c_s2,
                     D: tl.constexpr, GQ: tl.constexpr, BLOCK_Q: tl.constexpr, BS: tl.constexpr,
                     TILE: tl.constexpr, KLEV: tl.constexpr, VLEV: tl.constexpr, QK: tl.constexpr,
                     QV: tl.constexpr, R: tl.constexpr, GROUPV: tl.constexpr):
    BLOCK_M: tl.constexpr = BLOCK_Q * GQ
    pid = tl.program_id(0)
    kvh = tl.program_id(1)
    # sequence of this q block: binary search over cu_q in q-block units (q-block grid as vLLM's unified kernel)
    lo = 0
    hi = num_seqs
    while lo < hi:
        mid = (lo + hi) // 2
        v = tl.load(cu_q + mid) // BLOCK_Q + mid
        if v <= pid:
            lo = mid + 1
        else:
            hi = mid
    seq = lo - 1
    q_start = tl.load(cu_q + seq)
    q_len = tl.load(cu_q + seq + 1) - q_start
    qblk = pid - (q_start // BLOCK_Q + seq)
    if qblk * BLOCK_Q < q_len:
        seq_len = tl.load(seq_lens + seq)
        ctx = seq_len - q_len
        offs_m = tl.arange(0, BLOCK_M)
        tok = qblk * BLOCK_Q + offs_m // GQ
        head = kvh * GQ + offs_m % GQ
        row_ok = tok < q_len
        pos = ctx + tok
        offs_d = tl.arange(0, D)
        q = tl.load(Q + (q_start + tok)[:, None] * q_s0 + head[:, None] * q_s1 + offs_d[None, :],
                    mask=row_ok[:, None], other=0.0)
        # KIVI view boundaries per query row (decode-step semantics at position pos)
        last_tok = tl.minimum(qblk * BLOCK_Q + BLOCK_Q, q_len) - 1
        pos_hi = ctx + last_tok
        pos_lo = ctx + qblk * BLOCK_Q
        if QK:
            kb = (pos // R) * R
            kb_hi = (pos_hi // R) * R
            kb_lo = (pos_lo // R) * R
        else:
            kb = pos * 0 - 1
            kb_hi = pos_hi * 0 - 1
            kb_lo = pos_hi * 0 - 1
        if QV:
            vb = pos - R
            vb_hi = pos_hi - R
        else:
            vb = pos * 0 - 1 - R
            vb_hi = pos_hi * 0 - 1 - R
        m_i = tl.full([BLOCK_M], float("-inf"), tl.float32)
        l_i = tl.zeros([BLOCK_M], tl.float32)
        acc = tl.zeros([BLOCK_M, D], tl.float32)
        qk_scale = sm_scale * 1.4426950408889634
        n_tiles = (pos_hi + TILE) // TILE
        offs_t = tl.arange(0, TILE)
        for j in range(0, n_tiles):
            kp = j * TILE + offs_t
            kv_ok = kp < seq_len
            phys = tl.load(block_table + seq * bt_stride + kp // BS, mask=kv_ok, other=0).to(tl.int64)
            base = phys[:, None] * c_s0 + (kp % BS)[:, None] * c_s1 + kvh * c_s2 + offs_d[None, :]
            k = tl.load(Kc + base, mask=kv_ok[:, None], other=0.0)
            v = tl.load(Vc + base, mask=kv_ok[:, None], other=0.0)
            tile_lo = j * TILE
            tile_hi = j * TILE + TILE
            s_f = tl.zeros([BLOCK_M, TILE], tl.float32)
            s_q = tl.zeros([BLOCK_M, TILE], tl.float32)
            if tile_hi > kb_lo:  # some row needs full-precision keys of this tile
                s_f = tl.dot(q, tl.trans(k))
            if tile_lo < kb_hi:  # some row sees this tile as a flushed (quantized) key group
                kf = k.to(tl.float32)
                kmn = tl.min(kf, axis=0)
                kmx = tl.max(kf, axis=0)
                kq = _qdq(kf, kmn[None, :], kmx[None, :], KLEV).to(k.dtype)
                s_q = tl.dot(q, tl.trans(kq))
            s = tl.where(kp[None, :] < kb[:, None], s_q, s_f) * qk_scale
            vis = (kp[None, :] <= pos[:, None]) & row_ok[:, None]
            s = tl.where(vis, s, float("-inf"))
            m_new = tl.maximum(m_i, tl.max(s, axis=1))
            m_use = tl.where(m_new == float("-inf"), 0.0, m_new)
            p = tl.exp2(s - m_use[:, None])
            alpha = tl.exp2(m_i - m_use)
            l_i = l_i * alpha + tl.sum(p, axis=1)
            pb = p.to(v.dtype)
            use_vq = kp[None, :] < vb[:, None]
            pv = tl.dot(tl.where(use_vq, 0.0, pb).to(v.dtype), v)
            if tile_lo < vb_hi:  # some row sees quantized values in this tile
                vf = tl.reshape(v.to(tl.float32), [TILE, D // GROUPV, GROUPV])
                vmn = tl.min(vf, axis=2)
                vmx = tl.max(vf, axis=2)
                vq = _qdq(vf, vmn[:, :, None], vmx[:, :, None], VLEV)
                vq = tl.reshape(vq, [TILE, D]).to(v.dtype)
                pv = pv + tl.dot(tl.where(use_vq, pb, 0.0).to(v.dtype), vq)
            acc = acc * alpha[:, None] + pv
            m_i = m_new
        l_safe = tl.where(l_i > 0, l_i, 1.0)
        out = acc / l_safe[:, None]
        tl.store(O + (q_start + tok)[:, None] * o_s0 + head[:, None] * o_s1 + offs_d[None, :],
                 out.to(O.dtype.element_ty), mask=row_ok[:, None])
