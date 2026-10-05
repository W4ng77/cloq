"""Selftest for trigger_ghf_core on synthetic data: tie-break expectation (vs exhaustive enumeration), oracle identity,
frame counts with missing arms, point/bootstrap consistency. usage: python analysis/fork/trigger_ghf_selftest.py"""
from __future__ import annotations

import itertools
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trigger_ghf_core as C  # noqa: E402


def synth(seed: int, n_cells=3, n_tasks=8, blocks=("f02", "f03"), p_missing=0.0):
    rnd = random.Random(seed)
    rows = []
    for c in range(n_cells):
        for t in range(n_tasks):
            for b in blocks:
                Y = {a: int(rnd.random() < 0.35) for a in ("BB", "BQ", "QB", "QQ")}
                if rnd.random() < p_missing:
                    Y[rnd.choice(("BB", "QB"))] = None
                r = {"c": f"c{c}", "task": f"t{t}", "block": b, "key": f"{c}|{t}|{b}", **C.labels(Y)}
                r["sel"] = rnd.random() < 0.25
                rows.append(r)
    return rows


def brute_oracle(xs, m, mode):
    """Expectation over all top-m subsets consistent with sorting by label (uniform over valid subsets)."""
    xs = [r for r in xs if r[mode] is not None]
    best = sorted((r[mode] for r in xs), reverse=True)[:m]
    target = sum(best)
    subs = [s for s in itertools.combinations(range(len(xs)), m) if sum(xs[i][mode] for i in s) == target]
    return {q: np.mean([sum(xs[i][q] for i in s if xs[i][q] is not None) for s in subs]) for q in C.MODES}


def main():
    ok = 0
    # 1. tie-break expectation equals exhaustive enumeration over all optimal subsets (uniform)
    for seed in range(6):
        rows = [r for r in synth(seed, n_cells=1, n_tasks=6) if C.four_arm(r)]
        for m in (1, 3, 5, 8):
            for mode in C.MODES:
                o, bf = C.oracle_cell(rows, m, mode), brute_oracle(rows, m, mode)
                for q in C.MODES:
                    assert abs(o[f"net_{q}"] - bf[q]) < 1e-9, (seed, m, mode, q, o, bf)
                ok += 1
    # 2. oracle identity: own-mode net is tie-invariant and equals min(m,R) - max(0, m-(N-D))
    for seed in range(20):
        rows = synth(seed, n_cells=1, n_tasks=10)
        for mode in C.MODES:
            xs = [r for r in rows if r[mode] is not None]
            N, R, D = len(xs), sum(r[mode] == 1 for r in xs), sum(r[mode] == -1 for r in xs)
            for m in range(0, N + 1, 3):
                assert abs(C.oracle_cell(xs, m, mode)[f"net_{mode}"] - C.oracle_identity(N, R, D, m)) < 1e-9
                ok += 1
    assert C.oracle_identity(10, 2, 3, 9) == 2 - 2 and C.oracle_identity(10, 2, 3, 10) == -1
    # 3. frame counts: rows missing an arm drop out of that mode only and of the four-arm bootstrap
    rows = synth(7, p_missing=0.3)
    n4 = sum(C.four_arm(r) for r in rows)
    nG = sum(r["G"] is not None for r in rows)
    assert nG == len(rows) and 0 < n4 < len(rows), (nG, n4, len(rows))
    for mode in C.MODES:
        assert C.point(rows, mode)["pooled"]["N"] == sum(r[mode] is not None for r in rows)
    bt = C.Boot(rows, B=50, seed=1)
    assert bt.L.shape[0] == n4
    ok += 1
    # 4. point estimates from the bootstrap object equal the direct computation on four-arm rows
    rows = [r for r in synth(11) if C.four_arm(r)]
    bt = C.Boot(rows, B=200, seed=2)
    s = bt.summary([r for r in rows if r["sel"]])
    for mode in C.MODES:
        p = C.point(rows, mode)["pooled"]
        assert abs(s[f"net_pp_{mode}"]["point"] - round(100 * p["net"] / len(rows), 3)) < 1e-3
        assert abs(s[f"adj_pp_{mode}"]["point"] - round(100 * (p["net"] - p["rand"]) / len(rows), 3)) < 1e-3
        for kind in ("task", "crossed"):
            lo, hi = s[f"adj_pp_{mode}"][kind]
            assert lo <= hi
    assert abs(s["net_pp_H-G"]["point"] - (s["net_pp_H"]["point"] - s["net_pp_G"]["point"])) < 2e-3
    # 5. random expectation is the exact mean over random m-subsets (enumeration on a tiny cell)
    xs = [r for r in synth(3, n_cells=1, n_tasks=4) if C.four_arm(r)]
    m = 3
    for mode in C.MODES:
        brute = np.mean([sum(xs[i][mode] for i in s) for s in itertools.combinations(range(len(xs)), m)])
        for i, r in enumerate(xs):
            r["sel"] = i < m
        assert abs(C.point(xs, mode)["pooled"]["rand"] - brute) < 1e-9
    # 6. holm
    assert C.holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]
    print(f"trigger_ghf selftest OK ({ok} oracle/identity cases + frame, bootstrap, random, holm checks)")


if __name__ == "__main__":
    main()
