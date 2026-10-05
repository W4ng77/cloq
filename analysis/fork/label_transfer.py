"""EXPLORATORY, POST HOC (these data have been seen): upgrade-label transfer matrix, label-transfer-v1.
Protocol: docs/insights/LABEL_TRANSFER_POSTHOC.md (frames, budgets, tie rule, intervals and readings fixed before computing).
Labels per four-arm state: G = Y_BQ - Y_QQ, H = Y_QB - Y_QQ, F = Y_BB - Y_QQ. Select the top-b states by label X (budget filled,
uniform tie-break inside the boundary tie group, expectation computed analytically), execute mode Y, report rescues / damages /
net of Y in pp of all states in the frame, oracle_Y = select by Y, loss = oracle_Y - executed; selection index 3 = random selection
(all scores tied, amendment 2026-10-05b), the reference for excess over random and retained share. A hindsight label-mismatch
diagnostic, NOT a deployable router. Split-half variant: rank tasks on one block half, evaluate on the other (same-task replication).
Frames: Bank U U1 (primary), U2B (sensitivity) via analyze_bank_u.load; Bank P via offdiag_null.load_tau2 (no holdout read).
usage: python analysis/fork/label_transfer.py [--B 2000] [--selftest] -> analysis/fork/out/label_transfer_<UTC>.{json,md}"""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, time  # noqa: E401
from collections import defaultdict
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
MODES, BUDGETS, SEED = ("G", "H", "F"), (0.05, 0.10, 0.20), 20261001
CELLS = [f"{m}:{c}" for m in ("q4", "q8") for c in ("gptq_w4_d1", "awq_w4", "kvq_int8")]
POOLS = {"W4": [c for c in CELLS if "kvq" not in c], "KV8": [c for c in CELLS if "kvq" in c]}
ROOT = Path(__file__).resolve().parents[2]
LABEL = "EXPLORATORY, POST HOC (data already seen). Hindsight label-mismatch diagnostic, not a deployable router."


def labels(Y: dict) -> list:
    return [Y["BQ"] - Y["QQ"], Y["QB"] - Y["QQ"], Y["BB"] - Y["QQ"]]


def bf_proxy(t, n) -> list:
    """BF16 decisions per state, PROXY from the source Q trajectory (t 0-based): G 1, H n - t - 1, F n - t."""
    return [1.0, float(n - t - 1), float(n - t)] if t is not None and n is not None and 0 <= t < n else [1.0, np.nan, np.nan]


def expect(S, w, cap, V):
    """Expected sum over a top-cap selection by score S with uniform tie-break. S (n,) or (D,n); w (D,n) weights; cap (D,);
    V (n,m) or (D,n,m). Inclusion p = clip((cap - weight strictly above) / weight of the tie group, 0, 1). Returns (D,m), w*p."""
    S, w = np.round(np.asarray(S, float), 9), np.atleast_2d(np.asarray(w, float))
    if S.ndim == 1:
        u, inv = np.unique(S, return_inverse=True)
        Wg = np.stack([w[:, inv == g].sum(1) for g in range(len(u))], 1)
        Wab, Weq = (Wg[:, ::-1].cumsum(1)[:, ::-1] - Wg)[:, inv], Wg[:, inv]
    else:
        Wab = np.einsum("dij,dj->di", (S[:, None, :] > S[:, :, None]).astype(float), w)
        Weq = np.einsum("dij,dj->di", (S[:, None, :] == S[:, :, None]).astype(float), w)
    wp = w * np.clip((np.asarray(cap, float)[:, None] - Wab) / np.maximum(Weq, 1e-12), 0, 1)
    return (wp @ V if np.ndim(V) == 2 else np.einsum("dn,dnm->dm", wp, V)), wp


def vcols(L, bf):
    """Columns per mode j: [net, rescue, damage, bf proxy] -> (..., 12)."""
    L = np.asarray(L, float)
    return np.concatenate([np.stack([L[..., j], L[..., j] == 1, L[..., j] == -1, bf[..., j]], -1) for j in range(3)], -1)


def same_cell(us, W):
    """us: units with L, bf; W (D,n) weights. -> (4 X [G, H, F, random], 3 b, D, 12): fractions of all frame states; bf per selected."""
    L, bf = np.array([u["L"] for u in us], float), np.array([u["bf"] for u in us], float)
    V, Nw, out = vcols(L, bf), W.sum(1), np.zeros((4, len(BUDGETS), W.shape[0], 12))
    for x in range(4):
        for i, b in enumerate(BUDGETS):
            E, wp = expect(L[:, x] if x < 3 else np.zeros(len(L)), W, b * Nw, V)
            out[x, i] = E / Nw[:, None]
            out[x, i][:, 3::4] = E[:, 3::4] / wp.sum(1)[:, None]
    return out


def same_draw(frame: dict, B: int):
    """One analyze_dev.Boot PER POOL over that pool's own blocks (amendment 2026-10-05b), shared by the pool's cells."""
    import analyze_dev as AD
    res, meta = {}, {}
    for p, cs in POOLS.items():
        sub = {c: d for c in cs if (d := [u for u in frame.get(c, []) if u["div"]])}
        if not sub:
            continue
        bo = defaultdict(set)
        [bo[u["task"]].add(u["block"]) for d in sub.values() for u in d]
        bt = AD.Boot(sorted(bo), {t: sorted(v) for t, v in bo.items()}, B=B, seed=SEED)
        def wts(us):
            ti, ki = np.array([bt.tix[u["task"]] for u in us]), np.array([bt.bix[u["block"]] for u in us])
            return np.vstack([np.ones((1, len(us))), bt.Vb[:, ki], bt.Wc[:, ti] * bt.Vc[:, ki]])
        res |= {c: same_cell(d, wts(d)) for c, d in sub.items()}
        com = set.intersection(*[{u["block"] for u in d} for d in sub.values()])
        meta[p] = {"k_blocks": len(bt.blocks), "n_tasks": len(bt.tasks), "common_blocks": len(com)}
        if len(sub) >= 2:
            res[f"pool {p}"] = np.mean([res[c] if all(u["block"] in com for u in d) else same_cell(dd, wts(dd))
                                        for c, d in sub.items() if (dd := [u for u in d if u["block"] in com])], 0)
    return res, meta


def split_cell(us, tasks, blocks, H, Wt, VD, VE, dh, chunk=400):
    """Rank tasks by mean X on half dh, evaluate Y on the other half. Wt (D,T), VD (D,KD), VE (D,KE). -> (3, 3, D, 12)."""
    T, K, ti, bi = len(tasks), len(blocks), {t: i for i, t in enumerate(tasks)}, {b: i for i, b in enumerate(blocks)}
    lab, bfs, ns, nd = np.zeros((3, T, K)), np.zeros((3, T, K)), np.zeros((T, K)), np.zeros((T, K))
    rd = np.zeros((2, 3, T, K))
    for u in us:
        i, k = ti[u["task"]], bi[u["block"]]
        ns[i, k] += 1
        if u["div"]:
            nd[i, k] += 1
            lab[:, i, k] += u["L"]
            bfs[:, i, k] += u["bf"]
            rd[0, :, i, k] += np.array(u["L"]) == 1
            rd[1, :, i, k] += np.array(u["L"]) == -1
    Di, Ei = np.where(H == dh)[0], np.where(H != dh)[0]
    pres, tpres = (ns.sum(0) > 0).astype(float), (ns.sum(1) > 0).astype(float)
    w = Wt * tpres[None, :]
    nsE, ndE = (ns[:, Ei] @ VE.T).T, (nd[:, Ei] @ VE.T).T
    V = np.concatenate([np.stack([(a[j][:, Ei] @ VE.T).T for a in (lab, rd[0], rd[1], bfs)], -1) for j in range(3)], -1)
    out = np.zeros((4, len(BUDGETS), Wt.shape[0], 12))
    for x in range(4):  # x = 3: random selection (all task scores tied)
        S = (lab[x][:, Di] @ VD.T).T / np.maximum(VD @ pres[Di], 1e-12)[:, None] if x < 3 else np.zeros((Wt.shape[0], T))
        for i, b in enumerate(BUDGETS):
            for s in range(0, len(S), chunk):
                sl = slice(s, s + chunk)
                E, wp = expect(S[sl], w[sl], b * w[sl].sum(1), V[sl])
                out[x, i, sl] = E / (w[sl] * nsE[sl]).sum(1)[:, None]
                out[x, i, sl, 3::4] = E[:, 3::4] / np.maximum((wp * ndE[sl]).sum(1), 1e-12)[:, None]
    return out


def split_half(frame: dict, B: int, half):
    """Per pool over that pool's own blocks (amendment 2026-10-05b); pooled cells must share one block set."""
    res, meta = {"A->B": {}, "B->A": {}}, {}
    for p, cs in POOLS.items():
        if not (sub := {c: frame[c] for c in cs if c in frame}):
            continue
        bsets = {frozenset(u["block"] for u in us) for us in sub.values()}
        assert len(bsets) == 1, f"split-half pool {p}: cells differ in block sets"
        r, meta[p] = split_pool(sub, B, half)
        for d in r:
            res[d] |= r[d] | ({f"pool {p}": np.mean([r[d][c] for c in sub], 0)} if len(sub) >= 2 else {})
    res["mean of directions"] = {c: (res["A->B"][c] + res["B->A"][c]) / 2 for c in res["A->B"]}
    return res, meta


def split_pool(frame: dict, B: int, half):
    tasks = sorted({u["task"] for us in frame.values() for u in us})
    blocks = sorted({u["block"] for us in frame.values() for u in us})
    H, rng = np.array([half(b) for b in blocks]), np.random.default_rng(SEED)
    T, KD = len(tasks), [int((H == h).sum()) for h in (0, 1)]
    one = lambda n: np.ones((1, n))  # noqa: E731
    Wt = np.vstack([one(T), np.ones((B, T)), np.stack([np.bincount(rng.integers(0, T, T), minlength=T) for _ in range(B)])])
    Vh = {h: np.vstack([one(KD[h]), *[np.stack([np.bincount(rng.integers(0, KD[h], KD[h]), minlength=KD[h]) for _ in range(B)])] * 2]) for h in (0, 1)}
    res = {}
    for dh in (0, 1):
        tag = f"{'AB'[dh]}->{'AB'[1 - dh]}"
        res[tag] = {c: split_cell(us, tasks, blocks, H, Wt, Vh[dh], Vh[1 - dh], dh) for c, us in frame.items()}
    return res, {"blocks_by_half": {h: [b for b, x in zip(blocks, H) if x == h] for h in (0, 1)}, "n_tasks": T}


def load_frames():
    import analyze_bank_u as AB, offdiag_null as ON, analyze_dev as AD  # noqa: E401
    inputs, F = {}, {"U1": defaultdict(list), "U2B": defaultdict(list), "P": defaultdict(list)}
    native, _, notes = AB.load(inputs)
    for r in native:
        if r["sub"] in F and (c := f"{r['model']}:{r['cell']}") in CELLS:
            F[r["sub"]][c].append({"task": f"{r['domain']}|{r['task_id']}", "block": r["block"], "div": True, "L": labels(r["Y"]), "bf": bf_proxy(r.get("t"), r.get("n_decisions"))})
    cu = ON.load_tau2()
    for c in CELLS:
        F["P"][c] = [{"task": u["task"], "block": u["block"], "div": bool(u["div"]), "L": labels(u["Y"]) if u["div"] else [0, 0, 0],
                      "bf": bf_proxy(u.get("t"), u.get("n_decisions")) if u["div"] else [np.nan] * 3} for u in cu.get(c, [])]
    dg = {"bank_u_inputs_digest": hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(), "bank_u_missing_rows": len(notes["missing_rows"]),
          "bank_p_units_digest": {c: AD.units_digest(cu[c])[:16] for c in CELLS if c in cu}}
    return {k: {c: v for c, v in d.items() if v} for k, d in F.items()}, dg


def counts(frame):
    return {c: {"states_4arm": sum(u["div"] for u in us), "units": len(us), "tasks": len({u["task"] for u in us}), "blocks": sorted({u["block"] for u in us}),
                **{f"n{m}{s}": sum(1 for u in us if u["div"] and u["L"][j] == v) for j, m in enumerate(MODES) for s, v in (("+", 1), ("-", -1))}} for c, us in frame.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--B", type=int, default=2000), ap.add_argument("--selftest", action="store_true")
    a, t0 = ap.parse_args(), time.time()
    if a.selftest:
        return __import__("label_transfer_selftest").run()
    import label_transfer_report as RP, task_fragility as TF  # noqa: E401
    F, dg = load_frames()
    R = {k: {"counts": counts(fr), "same_draw": same_draw(fr, a.B), "split_half": split_half(fr, a.B, TF.half)} for k, fr in F.items()}
    src = [f"analysis/fork/{x}.py" for x in ("label_transfer", "label_transfer_report", "label_transfer_selftest", "analyze_bank_u", "offdiag_null", "analyze_dev", "task_fragility")]
    o = {"label": LABEL, "utc": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), "B": a.B, "seed": SEED, "budgets": BUDGETS, "inputs": dg,
         "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "sources_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in src + ["docs/insights/LABEL_TRANSFER_POSTHOC.md"]}}
    RP.write(o, R, ROOT / "analysis/fork/out", time.time() - t0)


if __name__ == "__main__":
    main()
