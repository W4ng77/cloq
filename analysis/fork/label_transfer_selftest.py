"""Synthetic selftest for label_transfer.py (reads no fork output): tie-break expectation vs exact enumeration and Monte Carlo,
weights = replication, 1-D vs 2-D scoring paths, oracle identity (diagonal loss 0, off-diagonal loss >= 0), frame counts,
a hand-computed split-half case, random-selection reference (index 3), undiluted split-half BF16 proxy, tie-aware ordering."""
from __future__ import annotations
import itertools
import numpy as np
import label_transfer as LT
import label_transfer_report as RP


def enum_expect(S, V, k):
    """Exact: uniform over all top-k selections consistent with the order (every tie-break equally likely), integer k."""
    cnt = {}  # each permutation (tie-break order) equally likely; multiplicity per selected set
    for p in itertools.permutations(range(len(S))):
        key = tuple(sorted(sorted(range(len(S)), key=lambda i: (-S[i], p[i]))[:k]))
        cnt[key] = cnt.get(key, 0) + 1
    n = sum(cnt.values())
    return sum(c * V[list(s)].sum(0) for s, c in cnt.items()) / n


def run():
    rng = np.random.default_rng(1)
    # 1. analytic tie-break expectation == exact enumeration (n = 7, ternary scores, integer and fractional capacities)
    for _ in range(20):
        S, V = rng.integers(-1, 2, 7).astype(float), rng.normal(size=(7, 3))
        for k in range(8):
            E, _ = LT.expect(S, np.ones((1, 7)), np.array([k]), V)
            assert np.allclose(E[0], enum_expect(S, V, k)), (S, k)
        E2, _ = LT.expect(S, np.ones((1, 7)), np.array([2.5]), V)
        assert np.allclose(E2[0], (enum_expect(S, V, 2) + enum_expect(S, V, 3)) / 2)
    # 2. Monte Carlo random tie-break agrees (n = 40)
    S, V = rng.integers(-1, 2, 40).astype(float), rng.integers(-1, 2, (40, 1)).astype(float)
    mc = np.mean([V[np.lexsort((rng.random(40), -S))[:9]].sum() for _ in range(40000)])
    E, _ = LT.expect(S, np.ones((1, 40)), np.array([9.0]), V)
    assert abs(E[0, 0] - mc) < 0.05, (E, mc)
    # 3. integer weights == replicated units; 2-D path == 1-D path
    w = rng.integers(0, 3, 12).astype(float)
    S, V = rng.integers(-1, 2, 12).astype(float), rng.normal(size=(12, 2))
    rep = np.repeat(np.arange(12), w.astype(int))
    a, _ = LT.expect(S, w[None], np.array([5.0]), V)
    b, _ = LT.expect(S[rep], np.ones((1, len(rep))), np.array([5.0]), V[rep])
    c, _ = LT.expect(np.tile(S, (1, 1)), w[None], np.array([5.0]), V[None])
    assert np.allclose(a, b) and np.allclose(a, c)
    # 4. oracle identity on a synthetic four-arm frame; frame counts
    us = [{"task": f"t{i % 30}", "block": f"f0{i // 30 + 1}", "div": True, "Y": dict(zip(("BB", "BQ", "QB", "QQ"), rng.integers(0, 2, 4)))} for i in range(90)]
    for u in us:
        u["L"], u["bf"] = LT.labels(u["Y"]), LT.bf_proxy(3, 10)
    W = np.vstack([np.ones((1, 90)), rng.integers(0, 3, (5, 90))]).astype(float)
    A = LT.same_cell(us, W)
    for i in range(3):
        for y in range(3):
            orc = A[y, i, :, 4 * y]
            assert all((orc >= A[x, i, :, 4 * y] - 1e-12).all() for x in range(3))
            assert np.allclose(A[y, i, :, 4 * y + 1] - A[y, i, :, 4 * y + 2], orc)
        assert np.allclose(A[:, i, :, 3::4], [1.0, 6.0, 7.0])
        Lm = np.array([u["L"] for u in us], float)
        assert np.allclose(A[3, i, :, 0::4], LT.BUDGETS[i] * (W @ Lm) / W.sum(1)[:, None])  # random = b x weighted mean label
    n = LT.counts({"c": us + [{"task": "t0", "block": "f09", "div": False, "L": [0, 0, 0], "bf": [np.nan] * 3}]})["c"]
    assert n["states_4arm"] == 90 and n["units"] == 91 and n["tasks"] == 30 and len(n["blocks"]) == 4
    assert n["nG+"] == sum(u["L"][0] == 1 for u in us) and n["nF-"] == sum(u["L"][2] == -1 for u in us)
    # 5. split-half by hand: 4 tasks, blocks a (half 0) and b (half 1); select top 1 of 4 tasks (budget 25% via cap)
    toy = [{"task": t, "block": bk, "div": True, "L": L, "bf": [1.0, 2.0, 3.0]} for t, bk, L in
           [("t1", "a", [1, 0, 0]), ("t2", "a", [0, 1, 0]), ("t3", "a", [0, 1, 0]), ("t4", "a", [0, 0, 0]),
            ("t1", "b", [0, 1, 1]), ("t2", "b", [1, 0, 0]), ("t3", "b", [0, 0, -1]), ("t4", "b", [1, 1, 1])]]
    old, LT.BUDGETS = LT.BUDGETS, (0.25,)
    args = (["t1", "t2", "t3", "t4"], ["a", "b"], np.array([0, 1]), np.ones((1, 4)), np.ones((1, 1)), np.ones((1, 1)), 0)
    try:
        o = LT.split_cell(toy, *args)
        nd = LT.split_cell(toy + [{"task": "t1", "block": "b", "div": False, "L": [0, 0, 0], "bf": [np.nan] * 3}], *args)
    finally:
        LT.BUDGETS = old
    # X = G picks t1 -> executed on b: G 0, H 1/4, F 1/4.  X = H ties t2/t3 (1/2 each) -> G (1+0)/2/4, F (0-1)/2/4
    assert np.allclose(o[0, 0, 0, 0::4], [0, 0.25, 0.25]) and np.allclose(o[1, 0, 0, 0::4], [0.125, 0.0, -0.125])
    # X = F: all scores 0 -> uniform over 4 tasks: mean of b labels / 4 states
    assert np.allclose(o[2, 0, 0, 0::4], np.array([2, 2, 1]) / 4 / 4) and np.allclose(o[3, 0, 0, 0::4], o[2, 0, 0, 0::4])
    assert np.allclose(nd[0, 0, 0, 3::4], [1.0, 2.0, 3.0])  # BF16 proxy per selected DIVERGENT unit, not diluted by non-divergent ones
    assert RP.order(np.array([10.0, 3.0, 10.0])) == "G=F>H" and RP.order(np.array([1.0, 2.0, 3.0])) == "F>H>G"
    print("label_transfer selftest: PASS (tie-break enumeration, Monte Carlo, weights, 2-D path, oracle identity, counts, split-half)")
