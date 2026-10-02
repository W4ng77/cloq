"""KIVI feasibility gate (docs/RESEARCH_LOG.md W99t; analysis/fork/kivi_gate/GATE.md). One GPU, run as a queue cmd task.

Phases (--phases, comma list):
  toy     kernel (scripts/a6000/pyhooks/cloq_kivi.py) on toy tensors, Qwen3-8B attention shapes (8 KV heads, GQA 4,
          head_dim 128, block 16), K4V4 / K2V2 (G=32, R=128) and the K16V16 null:
          T1 quantizer: kernel quantizer vs the official KIVI quantize+pack/unpack on fp32 data (codes and values).
          T2 semantics: kernel vs the official stateful KIVI decode (cloq/kivi_ref.OfficialKIVI) step by step, and vs
             the closed-form view (kivi_ref.view_attention); error relative to the size of the quantization effect.
          T3 invariance (bit-exact): the same sequences through the kernel token by token (decode), as one prefill,
             in random chunks, batched with other sequences in random order, with permuted physical blocks.
  server  one vLLM server per config on this GPU (bf16 = plain FA2 serving; k16v16 = kernel null; k4v4; k2v2):
          canary, determinism (cold / batched / prefix-hit), multi-turn chain replay (incremental decode + prefix
          hits vs cold re-prefill after /reset_prefix_cache, forward and reverse order), throughput, and local
          fidelity on N sampled BF16 closed-loop decisions (greedy completion agreement with the BF16 server,
          first-token top-20 KL(BF16 || cell), action-type and tool-call agreement).

usage: python scripts/a6000/kivi_gate.py --phases toy,server --model q8 --out analysis/fork/kivi_gate/gate_q8.json
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
WORK = Path("/data/ziyangs/cloq_work")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/a6000"))
sys.path.insert(0, str(ROOT / "scripts/a6000/pyhooks"))

CONFIGS = {
    "bf16": {},
    "k16v16": {"CLOQ_PYHOOKS": "1", "CLOQ_KIVI_KBITS": "16", "CLOQ_KIVI_VBITS": "16"},
    "k4v4": {"CLOQ_PYHOOKS": "1", "CLOQ_KIVI_KBITS": "4", "CLOQ_KIVI_VBITS": "4"},
    "k2v2": {"CLOQ_PYHOOKS": "1", "CLOQ_KIVI_KBITS": "2", "CLOQ_KIVI_VBITS": "2"},
}


# ----------------------------------------------------------------------------------------------------------- toy
def paged(k, v, BS, nblk_extra, gen):
    """Write k, v [L, H, D] into a paged cache with a random physical block order."""
    import torch
    L, H, D = k.shape
    nb = (L + BS - 1) // BS
    NB = nb + nblk_extra
    perm = torch.randperm(NB, generator=gen)[:nb].to(torch.int32)
    kc = torch.zeros(NB, BS, H, D, dtype=k.dtype, device=k.device)
    vc = torch.zeros_like(kc)
    kc.view(NB * BS, H, D).fill_(float("nan"))  # unwritten slots are NaN: any read of them shows up
    vc.view(NB * BS, H, D).fill_(float("nan"))
    pos = torch.arange(L)
    slots = perm[pos // BS].long() * BS + pos % BS
    kc.view(NB * BS, H, D)[slots.to(k.device)] = k
    vc.view(NB * BS, H, D)[slots.to(k.device)] = v
    return kc, vc, perm.to(k.device)


def run_schedule(seqs, schedule, kb, vb, BS=16, extra=7, seed=0):
    """seqs: list of (q [L,Hq,D], k, v). schedule: list of steps; each step is a list of (seq_idx, start, end) chunks
    launched together (one kernel call, in the given order). Returns per-seq outputs [L, Hq, D]."""
    import torch
    from cloq_kivi import kivi_attention
    gen = torch.Generator().manual_seed(seed)
    dev = seqs[0][0].device
    caches = []
    for (q, k, v) in seqs:  # the cache holds every token up front; the kernel may only read positions < seq_len
        caches.append(paged(k, v, BS, extra, gen))
    # one shared pool: concatenate per-seq pools, offset block ids
    kcs = torch.cat([c[0] for c in caches]); vcs = torch.cat([c[1] for c in caches])
    offs, o = [], 0
    for c in caches:
        offs.append(o); o += c[0].shape[0]
    maxb = max(c[2].numel() for c in caches)
    outs = [torch.full_like(s[0], float("nan")) for s in seqs]
    for step in schedule:
        qs, cu, sl, bt = [], [0], [], []
        for (i, a, b) in step:
            qs.append(seqs[i][0][a:b]); cu.append(cu[-1] + (b - a)); sl.append(b)
            row = torch.zeros(maxb + 3, dtype=torch.int32, device=dev)
            row[:caches[i][2].numel()] = caches[i][2] + offs[i]
            bt.append(row)
        qq = torch.cat(qs)
        out = torch.full_like(qq, float("nan"))
        kivi_attention(qq, kcs, vcs, out, torch.tensor(cu, dtype=torch.int32, device=dev),
                       torch.tensor(sl, dtype=torch.int32, device=dev), torch.stack(bt), qq.shape[-1] ** -0.5,
                       kbits=kb, vbits=vb)
        for j, (i, a, b) in enumerate(step):
            outs[i][a:b] = out[cu[j]:cu[j + 1]]
    return outs


def toy(dev, quick=False, dt=None):
    import torch
    from cloq import kivi_ref
    import cloq_kivi
    dt = dt or torch.bfloat16
    res = {"shapes": {"Hq": 32, "Hkv": 8, "D": 128, "BS": 16, "G": 32, "R": 128}, "device": dev, "dtype": str(dt)}
    torch.manual_seed(0)
    Hq, Hkv, D = 32, 8, 128
    # ---------------- T1 quantizer
    from cloq_kivi_kernel import qdq_k_test as _kq_test, qdq_v_test as _vq_test

    t1 = {}
    for bits in (2, 4):
        x = (torch.randn(64, 32, D, device=dev) * torch.rand(1, 1, D, device=dev) * 3).float()  # 64 groups of 32 tokens
        x[0, :, 5] = 0.7  # a constant channel group (scale 0)
        yk = torch.empty_like(x)
        _kq_test[(64,)](x, yk, LEV=2 ** bits - 1, T=32, DD=D, enable_fp_fusion=False)
        # official K path: transpose to [B, nh, D, T], quantize along T in groups of 32
        offk, codes_k = kivi_ref.official_qdq_lastdim(x.permute(0, 2, 1).unsqueeze(0), 32, bits)
        offk = offk.squeeze(0).permute(0, 2, 1)
        ok_mask = ~torch.isnan(offk)  # official divides by scale 0 -> NaN on the constant group
        refk, _ = kivi_ref.qdq_ref(x, x.amin(1, keepdim=True), x.amax(1, keepdim=True), bits)
        yv = torch.empty_like(x)
        _vq_test[(64,)](x, yv, LEV=2 ** bits - 1, T=32, DD=D, G=32, enable_fp_fusion=False)
        offv, _ = kivi_ref.official_qdq_lastdim(x.unsqueeze(0), 32, bits)
        offv = offv.squeeze(0)
        okv = ~torch.isnan(offv)
        t1[f"int{bits}"] = {
            "K_kernel_eq_official_bitwise": int((yk[ok_mask] == offk[ok_mask]).sum()), "K_n": int(ok_mask.sum()),
            "K_official_nan_on_constant_group": int((~ok_mask).sum()),
            "K_kernel_eq_torchref_bitwise_all": bool((yk == refk).all()),
            "V_kernel_eq_official_bitwise": int((yv[okv] == offv[okv]).sum()), "V_n": int(okv.sum()),
            "K_max_abs_vs_official": float((yk[ok_mask] - offk[ok_mask]).abs().max()),
            "V_max_abs_vs_official": float((yv[okv] - offv[okv]).abs().max()),
        }
    res["T1_quantizer"] = t1
    t1_ok = all(v["K_kernel_eq_official_bitwise"] == v["K_n"] and v["V_kernel_eq_official_bitwise"] == v["V_n"]
                and v["K_kernel_eq_torchref_bitwise_all"] for v in t1.values())

    # ---------------- T2 semantics vs official stateful decode
    L = 300 if quick else 700
    t2 = {}
    for name, kb, vb in (("k4v4", 4, 4), ("k2v2", 2, 2), ("k16v16", 16, 16)):
        g = torch.Generator(device="cpu").manual_seed(1)
        q = torch.randn(L, Hq, D, generator=g).to(dev).to(dt)
        k = (torch.randn(L, Hkv, D, generator=g) + torch.randn(1, Hkv, D, generator=g) * 2).to(dev).to(dt)  # outlier channels
        v = torch.randn(L, Hkv, D, generator=g).to(dev).to(dt)
        out_dec = run_schedule([(q, k, v)], [[(0, t, t + 1)] for t in range(L)], kb, vb)[0].float()
        exact = kivi_ref.view_attention(q, k, v, 16, 16)  # no quantization
        r = {"quant_effect_max_abs": None}
        if kb < 16:
            view = kivi_ref.view_attention(q, k, v, kb, vb)
            # official: 1-token prefill then decode every token (fp32 on the bf16-rounded tensors)
            off = kivi_ref.OfficialKIVI(kb, vb, 32, 128)
            Q, K, V = (x.float().permute(1, 0, 2).unsqueeze(0) for x in (q, k, v))
            outs = [off.prefill(Q[:, :, :1], K[:, :, :1], V[:, :, :1])]
            splits = []
            for t in range(1, L):
                outs.append(off.decode(Q[:, :, t:t + 1], K[:, :, t:t + 1], V[:, :, t:t + 1]))
                splits.append(off.state_split())
            off_out = torch.cat(outs, 2).squeeze(0).permute(1, 0, 2)
            # official with a real multi-token prefill (L0 = 300): its decode steps match, its prefill rows do not
            L0 = 300 if L > 300 else L // 2
            off2 = kivi_ref.OfficialKIVI(kb, vb, 32, 128)
            o2 = [off2.prefill(Q[:, :, :L0], K[:, :, :L0], V[:, :, :L0])]
            for t in range(L0, L):
                o2.append(off2.decode(Q[:, :, t:t + 1], K[:, :, t:t + 1], V[:, :, t:t + 1]))
            off2_out = torch.cat(o2, 2).squeeze(0).permute(1, 0, 2)
            exp_split = [((n // 128) * 128, n - (n // 128) * 128, max(0, n - 128), min(n, 128)) for n in range(2, L + 1)]
            r.update({
                "official_state_split_matches_position_rule": splits == exp_split,
                "kernel_vs_official_decode_max_abs": float((out_dec - off_out).abs().max()),
                "kernel_vs_view_max_abs": float((out_dec - view).abs().max()),
                "view_vs_official_max_abs": float((view - off_out).abs().max()),
                "quant_effect_max_abs": float((off_out - exact).abs().max()),
                "quant_effect_mean_abs": float((off_out - exact).abs().mean()),
                "kernel_vs_official_mean_abs": float((out_dec - off_out).abs().mean()),
                "official_prefill300_decode_rows_vs_kernel_max_abs": float((off2_out[L0:] - out_dec[L0:]).abs().max()),
                "official_prefill300_prefill_rows_vs_kernel_max_abs": float((off2_out[:L0] - out_dec[:L0]).abs().max()),
                "official_prefill300_prefill_rows_vs_exact_max_abs": float((off2_out[:L0] - exact[:L0]).abs().max()),
            })
            r["ratio_err_to_effect"] = r["kernel_vs_official_mean_abs"] / max(r["quant_effect_mean_abs"], 1e-12)
        else:
            r["kernel_null_vs_exact_max_abs"] = float((out_dec - exact).abs().max())
        t2[name] = r
    res["T2_semantics"] = t2
    t2_ok = all(r.get("kernel_null_vs_exact_max_abs", 0) < 2e-2 for r in t2.values()) and all(
        r["official_state_split_matches_position_rule"] and r["ratio_err_to_effect"] < 0.05
        and r["kernel_vs_official_decode_max_abs"] < 0.25 * r["quant_effect_max_abs"]
        and r["official_prefill300_decode_rows_vs_kernel_max_abs"] < 0.25 * r["quant_effect_max_abs"]
        for r in t2.values() if "ratio_err_to_effect" in r)

    # ---------------- T3 invariance, bit-exact
    t3 = {}
    rng = random.Random(0)
    Ls = [5, 130, 257, 300, 513] if quick else [5, 127, 128, 129, 257, 300, 513, 700, 1100]
    for name, kb, vb in (("k4v4", 4, 4), ("k2v2", 2, 2), ("k16v16", 16, 16)):
        g = torch.Generator(device="cpu").manual_seed(2)
        seqs = []
        for L_ in Ls:
            seqs.append(tuple(torch.randn(L_, h, D, generator=g).to(dev).to(dt) * s
                              for h, s in ((Hq, 1.0), (Hkv, 1.5), (Hkv, 1.0))))
        base = run_schedule(seqs, [[(i, 0, L_)] for i, L_ in enumerate(Ls)], kb, vb, seed=1)  # one prefill each
        variants = {}
        variants["decode_token_by_token"] = run_schedule(
            seqs, [[(i, t, t + 1)] for i, L_ in enumerate(Ls) for t in range(L_)], kb, vb, seed=2)
        # random chunking, all sequences interleaved in random batches, different physical blocks
        chunks = []
        for i, L_ in enumerate(Ls):
            a = 0
            while a < L_:
                b = min(L_, a + rng.choice([1, 1, 2, 3, 7, 16, 17, 31, 64, 100, 128, 129, 250]))
                chunks.append((i, a, b)); a = b
        steps, pend = [], {i: [c for c in chunks if c[0] == i] for i in range(len(Ls))}
        while any(pend.values()):
            avail = [i for i in pend if pend[i]]
            rng.shuffle(avail)
            steps.append([pend[i].pop(0) for i in avail[:rng.randint(1, len(avail))]])
        variants["random_chunks_batched"] = run_schedule(seqs, steps, kb, vb, seed=3)
        # prefill half, then the rest decoded token by token, all sequences batched in each decode step
        st = [[(i, 0, L_ // 2) for i, L_ in enumerate(Ls)]]
        for t in range(max(Ls)):
            step = [(i, t, t + 1) for i, L_ in enumerate(Ls) if L_ // 2 <= t < L_]
            if step:
                st.append(step)
        variants["prefill_half_then_batched_decode"] = run_schedule(seqs, st, kb, vb, seed=4)
        t3[name] = {}
        for vn, outs in variants.items():
            eq = [bool(torch.equal(a.view(torch.int16), b.view(torch.int16))) for a, b in zip(base, outs)]
            nan = [bool(torch.isnan(o).any()) for o in outs]
            t3[name][vn] = {"bitwise_equal_seqs": sum(eq), "n_seqs": len(eq), "any_nan": any(nan),
                            "max_abs": max(float((a.float() - b.float()).abs().max()) for a, b in zip(base, outs))}
    res["T3_invariance"] = t3
    t3_ok = all(x["bitwise_equal_seqs"] == x["n_seqs"] and not x["any_nan"] for d in t3.values() for x in d.values())
    res["verdict"] = {"T1_quantizer": t1_ok, "T2_semantics": t2_ok, "T3_invariance": t3_ok}
    return res


# ----------------------------------------------------------------------------------------------------- server
def post(port, path, body=None, timeout=1800):
    import urllib.request
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body or {}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        txt = r.read()
    try:
        return json.loads(txt)
    except Exception:
        return txt.decode(errors="replace")


def complete(port, ids, max_tokens=256, logprobs=1, ignore_eos=False):
    body = {"model": "agent", "prompt": ids, "max_tokens": max_tokens, "temperature": 0.0, "seed": 0,
            "logprobs": logprobs, "return_token_ids": True, "ignore_eos": ignore_eos}
    c = post(port, "/v1/completions", body)["choices"][0]
    toks = c.get("token_ids") or (c.get("provider_specific_fields") or {}).get("token_ids")
    lp = c["logprobs"]
    return {"ids": toks, "lp": lp["token_logprobs"], "top": lp.get("top_logprobs"), "finish": c.get("finish_reason")}


def reset_cache(port):
    return post(port, "/reset_prefix_cache")


def load_decisions(model, n, seed=0):
    run = f"a6k2_{model}_bf16"
    ds = []
    for d in ("retail", "airline"):
        for line in open(ROOT / "runs" / run / d / "decisions.jsonl"):
            x = json.loads(line)
            if x.get("prompt_token_ids") and x.get("completion_token_ids") is not None:
                ds.append({k: x[k] for k in ("domain", "task_id", "trajectory_id", "decision_idx", "prompt_token_ids",
                                             "completion_token_ids", "finish_reason", "tool_calls")})
    by_traj = {}
    for x in ds:
        by_traj.setdefault((x["domain"], x["trajectory_id"]), []).append(x)
    rnd = random.Random(seed)
    sample = list(ds)
    rnd.shuffle(sample)
    return run, sample[:n], by_traj


def chains(by_traj, n_chains, turns, seed=0):
    """Multi-turn chains from BF16 trajectories: turn k+1 prompt = turn k prompt + completion_k + suffix_k, where
    suffix_k = the BF16 next prompt after BF16's completion_k (the tool result / user turn). Unlike the chat template
    (which drops the empty <think> block from history), the chain keeps every generated token at its decode
    position, so the cold re-prefill recomputes exactly the tokens that were decoded (strictest replay case). The cell's own completions replace
    BF16's, so the history is generated under the cell (as in a closed loop)."""
    out = []
    keys = sorted(by_traj)
    random.Random(seed).shuffle(keys)
    for key in keys:
        ds = sorted(by_traj[key], key=lambda x: x["decision_idx"])
        sfx = []
        for a, b in zip(ds, ds[1:]):
            ap, ac, bp = a["prompt_token_ids"], a["completion_token_ids"], b["prompt_token_ids"]
            j = None
            for delta in (0, 4):  # Qwen3's template drops the generation prompt's empty <think> block from history
                n0 = len(ap) - delta
                if bp[:n0] == ap[:n0] and bp[n0:n0 + len(ac)] == ac:
                    j = n0 + len(ac)
                    break
            if j is None:
                break
            sfx.append(bp[j:])
        if len(sfx) >= turns - 1:
            out.append({"key": list(key), "p0": ds[0]["prompt_token_ids"], "suffixes": sfx[:turns - 1]})
        if len(out) == n_chains:
            break
    return out


def chain_test(port, chs, max_tokens=200):
    """Incremental (turn by turn, prefix hits on the cell's own decoded history) vs cold re-prefill of each turn's
    full prompt after /reset_prefix_cache, and vs a reverse-order pass (longest first: other prefix-hit boundaries)."""
    rec = []
    reset_cache(port)
    for ch in chs:
        p = list(ch["p0"])
        turns = []
        for k in range(len(ch["suffixes"]) + 1):
            r = complete(port, p, max_tokens)
            turns.append({"prompt": list(p), "ids": r["ids"], "lp": r["lp"]})
            if k < len(ch["suffixes"]):
                p = p + r["ids"] + ch["suffixes"][k]
        rec.append(turns)
    n = eq_cold = eq_rev = 0
    mism = []
    allt = [(i, k) for i in range(len(rec)) for k in range(len(rec[i]))]
    for (i, k) in allt:
        reset_cache(port)
        r = complete(port, rec[i][k]["prompt"], max_tokens)
        n += 1
        ok = r["ids"] == rec[i][k]["ids"] and r["lp"] == rec[i][k]["lp"]
        eq_cold += ok
        if not ok:
            mism.append({"chain": i, "turn": k, "kind": "cold", "n_prompt": len(rec[i][k]["prompt"])})
    reset_cache(port)
    for (i, k) in sorted(allt, key=lambda x: -len(rec[x[0]][x[1]]["prompt"])):
        r = complete(port, rec[i][k]["prompt"], max_tokens)
        ok = r["ids"] == rec[i][k]["ids"] and r["lp"] == rec[i][k]["lp"]
        eq_rev += ok
        if not ok:
            mism.append({"chain": i, "turn": k, "kind": "reverse", "n_prompt": len(rec[i][k]["prompt"])})
    lens = [len(t["prompt"]) for c in rec for t in c]
    return {"n_turns": n, "cold_reprefill_eq_incremental": eq_cold, "reverse_order_eq_incremental": eq_rev,
            "prompt_len_min_max": [min(lens), max(lens)], "r128_boundaries_crossed_by_decode":
                sum((len(t["prompt"]) + len(t["ids"])) // 128 - len(t["prompt"]) // 128 for c in rec for t in c),
            "mismatches": mism[:20]}


def det_test(port, ps, fill, max_tokens=64):
    from concurrent.futures import ThreadPoolExecutor
    reset_cache(port)
    alone_cold = [complete(port, p, max_tokens) for p in ps]
    with ThreadPoolExecutor(len(ps) + len(fill)) as ex:
        batch = list(ex.map(lambda p: complete(port, p, max_tokens), ps + fill))[:len(ps)]
    alone_hit = [complete(port, p, max_tokens) for p in ps]
    same = lambda A, B: sum(a["ids"] == b["ids"] and a["lp"] == b["lp"] for a, b in zip(A, B))  # noqa: E731
    return {"n": len(ps), "batch_eq_alone": same(batch, alone_cold), "prefixhit_eq_alone": same(alone_hit, alone_cold)}


def throughput(port, ps):
    from concurrent.futures import ThreadPoolExecutor
    long = max(ps, key=len)
    reset_cache(port)
    t0 = time.time(); complete(port, long, 1); t_prefill = time.time() - t0
    t0 = time.time(); r = complete(port, long, 512, ignore_eos=True); t_dec = time.time() - t0
    reset_cache(port)
    batch = ps[:16]
    t0 = time.time()
    with ThreadPoolExecutor(len(batch)) as ex:
        outs = list(ex.map(lambda p: complete(port, p, 256, ignore_eos=True), batch))
    t_b = time.time() - t0
    ntok = sum(len(o["ids"]) for o in outs)
    return {"long_prompt_tokens": len(long), "cold_prefill_s": round(t_prefill, 3),
            "single_stream_decode_tok_s": round(len(r["ids"]) / max(t_dec, 1e-9), 2),
            "batch16_gen_tokens": ntok, "batch16_wall_s": round(t_b, 2),
            "batch16_tok_s": round(ntok / t_b, 2), "batch16_mean_prompt": sum(map(len, batch)) / len(batch)}


def fidelity_collect(port, sample, max_tokens=512):
    from concurrent.futures import ThreadPoolExecutor
    reset_cache(port)

    def one(x):
        r = complete(port, x["prompt_token_ids"], max_tokens, logprobs=20)
        return {"ids": r["ids"], "lp": r["lp"], "top0": (r["top"] or [None])[0], "finish": r["finish"]}
    with ThreadPoolExecutor(8) as ex:
        return list(ex.map(one, sample))


def server_phase(model, configs, out_res, outpath, n_fid, n_chains, turns):
    import subprocess
    from worker import MODELS, canary, healthy, snapshot, stop_server
    m = MODELS[model]
    port = int(os.environ["CLOQ_TASK_PORT"])
    gpus = os.environ["CUDA_VISIBLE_DEVICES"]
    run, sample, by_traj = load_decisions(model, max(n_fid, 40))
    chs = chains(by_traj, n_chains, turns)
    ps = [x["prompt_token_ids"] for x in sample[:8]]
    fill = [x["prompt_token_ids"] for x in sample[8:16]]
    logdir = WORK / "logs/kivi"
    logdir.mkdir(parents=True, exist_ok=True)
    fid_dir = ROOT / "analysis/fork/kivi_gate/fid"
    fid_dir.mkdir(parents=True, exist_ok=True)
    out_res.setdefault("server", {"ref_run": run, "n_fid": n_fid, "n_chains": len(chs), "turns": turns,
                                  "configs": {}})
    for name in configs:
        env = dict(os.environ, CLOQ_TOOL_PARSER=m["parser"], VLLM_SERVER_DEV_MODE="1", **CONFIGS[name])
        if not CONFIGS[name]:
            env.pop("CLOQ_PYHOOKS", None)
        vlog = logdir / f"gate_{model}_{name}.vllm.log"
        t0 = time.time()
        p = subprocess.Popen([str(ROOT / "scripts/a6000/serve.sh"), gpus, str(port), snapshot(m["hf_id"], m["revision"]),
                              "agent", "33792"], env=env, stdout=open(vlog, "w"), stderr=subprocess.STDOUT,
                             start_new_session=True)
        r = {"env": CONFIGS[name]}
        try:
            while not healthy(port):
                if p.poll() is not None:
                    raise RuntimeError(f"server {name} died; see {vlog}")
                if time.time() - t0 > 2400:
                    raise RuntimeError("server startup timeout")
                time.sleep(5)
            r["startup_s"] = round(time.time() - t0)
            txt = vlog.read_text(errors="replace")
            hl = [ln for ln in txt.splitlines() if "[cloq_kivi]" in ln]
            r["hook_wrapped_lines"] = [ln[-300:] for ln in hl if "wrapped" in ln][:3]
            r["hook_attention_instances"] = sum("hooked attention" in ln for ln in hl)
            r["canary"] = canary(port, model)
            print(name, "up", r["startup_s"], "s", flush=True)
            r["det"] = det_test(port, ps, fill)
            print(name, "det", r["det"], flush=True)
            r["chain"] = chain_test(port, chs)
            print(name, "chain", {k: v for k, v in r["chain"].items() if k != "mismatches"}, flush=True)
            r["throughput"] = throughput(port, [x["prompt_token_ids"] for x in sample[:16]])
            print(name, "tput", r["throughput"], flush=True)
            fid = fidelity_collect(port, sample[:n_fid])
            json.dump(fid, open(fid_dir / f"{model}_{name}.json", "w"))
            r["fidelity_file"] = str((fid_dir / f"{model}_{name}.json").relative_to(ROOT))
            r["errors_in_log"] = [ln[-300:] for ln in vlog.read_text(errors="replace").splitlines()
                                  if "Traceback" in ln or "cloq_kivi: unsupported" in ln][:5]
        except Exception as e:
            r["error"] = repr(e)
            print(name, "ERROR", repr(e), flush=True)
        finally:
            stop_server(p, gpus.split(","))
        out_res["server"]["configs"][name] = r
        Path(outpath).write_text(json.dumps(out_res, indent=1))
    out_res["server"]["fidelity"] = fidelity_summary(model, sample[:n_fid], list(configs))
    Path(outpath).write_text(json.dumps(out_res, indent=1))


def _kl_top(ref_top, cell_top):
    """KL(ref || cell) on first-token top-20 dicts {token: logprob} (union; a missing token takes that side's minimum
    listed logprob, a 'rest' bucket holds the remaining mass)."""
    import math
    if not ref_top or not cell_top:
        return None
    U = set(ref_top) | set(cell_top)
    fr, fc = min(ref_top.values()), min(cell_top.values())
    pr = {t: math.exp(ref_top.get(t, fr)) for t in U}
    pc = {t: math.exp(cell_top.get(t, fc)) for t in U}
    rr, rc = max(1 - sum(pr.values()), 1e-12), max(1 - sum(pc.values()), 1e-12)
    kl = sum(pr[t] * (math.log(pr[t]) - math.log(pc[t])) for t in U) + rr * (math.log(rr) - math.log(rc))
    return max(kl, 0.0)


def _tool(ids, tok):
    """(is_tool_call, normalized tool calls or text) of a completion."""
    txt = tok.decode(ids, skip_special_tokens=False)
    if "<tool_call>" not in txt:
        return False, txt.replace("<|im_end|>", "").strip()
    calls = []
    for seg in txt.split("<tool_call>")[1:]:
        body = seg.split("</tool_call>")[0].strip()
        try:
            j = json.loads(body)
            calls.append(json.dumps({"name": j.get("name"), "arguments": j.get("arguments")}, sort_keys=True))
        except Exception:
            calls.append("UNPARSED:" + body)
    return True, calls


def fidelity_summary(model, sample, configs):
    import statistics
    from transformers import AutoTokenizer
    from worker import MODELS, snapshot
    m = MODELS[model]
    tok = AutoTokenizer.from_pretrained(snapshot(m["hf_id"], m["revision"]))
    fid_dir = ROOT / "analysis/fork/kivi_gate/fid"
    F = {c: json.load(open(fid_dir / f"{model}_{c}.json")) for c in configs if (fid_dir / f"{model}_{c}.json").exists()}
    if "bf16" not in F:
        return {"error": "no bf16 reference"}
    ref = F["bf16"]
    out = {"bf16_server_eq_recorded_closed_loop": sum(r["ids"] == x["completion_token_ids"] for r, x in zip(ref, sample)),
           "n": len(sample)}
    rparse = [_tool(r["ids"], tok) for r in ref]
    for c, cell in F.items():
        if c == "bf16":
            continue
        kls = [_kl_top(a["top0"], b["top0"]) for a, b in zip(ref, cell)]
        kls = [k for k in kls if k is not None]
        cp = [_tool(r["ids"], tok) for r in cell]
        n = len(cell)
        same_ids = sum(a["ids"] == b["ids"] for a, b in zip(ref, cell))
        first = sum(a["ids"][:1] == b["ids"][:1] for a, b in zip(ref, cell))
        typ = sum(a[0] == b[0] for a, b in zip(rparse, cp))
        act = sum(a == b for a, b in zip(rparse, cp))
        tool_ref = [i for i, a in enumerate(rparse) if a[0]]
        tool_act = sum(rparse[i] == cp[i] for i in tool_ref)
        ks = sorted(kls)
        out[c] = {"n": n, "exact_completion_agree": same_ids / n, "first_token_agree": first / n,
                  "action_type_agree": typ / n, "action_agree": act / n,
                  "tool_call_agree_on_bf16_tool_decisions": tool_act / max(len(tool_ref), 1), "n_bf16_tool": len(tool_ref),
                  "kl_first_mean": statistics.fmean(ks) if ks else None, "kl_first_median": ks[len(ks) // 2] if ks else None,
                  "kl_first_q90": ks[int(0.9 * (len(ks) - 1))] if ks else None}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phases", default="toy,server")
    ap.add_argument("--model", default="q8")
    ap.add_argument("--configs", default="bf16,k16v16,k4v4,k2v2")
    ap.add_argument("--n-fid", type=int, default=200)
    ap.add_argument("--n-chains", type=int, default=8)
    ap.add_argument("--turns", type=int, default=4)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    outpath = ROOT / a.out
    outpath.parent.mkdir(parents=True, exist_ok=True)
    res = json.load(open(outpath)) if outpath.exists() else {}
    res.update({"host": os.uname().nodename, "gpus": os.environ.get("CUDA_VISIBLE_DEVICES"), "started": time.time()})
    if "toy" in a.phases:
        import torch
        dev = "cuda" if torch.cuda.is_available() and os.environ.get("TRITON_INTERPRET") != "1" else "cpu"
        t0 = time.time()
        res["toy"] = toy(dev, quick=a.quick)
        res["toy"]["seconds"] = round(time.time() - t0, 1)
        print(json.dumps(res["toy"]["verdict"]), flush=True)
        outpath.write_text(json.dumps(res, indent=1))
    if "server" in a.phases:
        server_phase(a.model, a.configs.split(","), res, outpath, a.n_fid, a.n_chains, a.turns)
    if "fidsum" in a.phases:
        run, sample, _ = load_decisions(a.model, max(a.n_fid, 40))
        res.setdefault("server", {})["fidelity"] = fidelity_summary(a.model, sample[:a.n_fid], a.configs.split(","))
    outpath.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
