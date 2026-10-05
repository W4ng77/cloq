"""Selftest for analysis/fork/commonstate_rd.py on synthetic data (writes nothing).
Checks: decomposition identity XN = XR - XD = K per state and in the estimate; hand-computed rescue/damage values;
frame counts; cross-tab bookkeeping; point estimate = mean over blocks of task-equal-weight block means.
Tie-break expectation and oracle identity are not applicable to Analysis 3 (no selection; protocol section 3): asserted
by the absence of any selection code path (rd_columns uses every admitted state).
usage: python analysis/fork/commonstate_rd_selftest.py
"""
from __future__ import annotations
import itertools, sys  # noqa: E401
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import commonstate_rd as R  # noqa: E402
import analyze_commonstate as AC  # noqa: E402


def unit(block, task, y1, yb, yq, c="d1", other=(0, 0, 0)):
    Y = {}
    for cc, (a, b, q) in ((c, (y1, yb, yq)), ("bf16" if c == "d1" else "d1", other)):
        Y |= {("d1", cc): a, ("bf16", cc): b, ("d2", cc): q}
    return {"block": block, "task": task, "Y": Y}


def main():
    # 1. hand cases (c = d1): all 8 outcome patterns of (Y1, YB, YQ)
    us = [unit("f01", f"t{i}", *p) for i, p in enumerate(itertools.product((0, 1), repeat=3))]
    C = R.rd_columns(us)
    want = {  # (y1, yb, yq) -> rB, dB, rQ, dQ, XR, XD, XN
        (0, 0, 0): (0, 0, 0, 0, 0, 0, 0), (0, 0, 1): (0, 0, 1, 0, -1, 0, -1), (0, 1, 0): (1, 0, 0, 0, 1, 0, 1), (0, 1, 1): (1, 0, 1, 0, 0, 0, 0),
        (1, 0, 0): (0, 1, 0, 1, 0, 0, 0), (1, 0, 1): (0, 1, 0, 0, 0, 1, -1), (1, 1, 0): (0, 0, 0, 1, 0, -1, 1), (1, 1, 1): (0, 0, 0, 0, 0, 0, 0)}
    for i, p in enumerate(itertools.product((0, 1), repeat=3)):
        got = tuple(C[f"{n}[d1]"][i] for n in ("rB", "dB", "rQ", "dQ", "XR", "XD", "XN"))
        assert got == want[p], (p, got)
        assert C["XN[d1]"][i] == (p[1] - p[0]) - (p[2] - p[0])
    ct = R.crosstab(us)["d1"]
    assert ct["Y1=0"] == {"both": 1, "BF16 only": 1, "Q' only": 1, "neither": 1} and ct["Y1=1"] == ct["Y1=0"]
    assert sum(C["XR[d1]"]) == ct["Y1=0"]["BF16 only"] - ct["Y1=0"]["Q' only"]
    # 2. random synthetic panel: frame counts, identity in the estimate, point = mean of block means
    rng = np.random.default_rng(7)
    blocks, tasks = ["f01", "f02", "f03"], [f"t{i}" for i in range(20)]
    us = []
    for b in blocks:
        for t in tasks:
            us.append(unit(b, t, *rng.integers(0, 2, 3), other=tuple(rng.integers(0, 2, 3))))  # 1 state per (task, block), as in the design
    R.check_unique(us)
    try:
        R.check_unique(us + us[:1])
        raise RuntimeError("check_unique missed a duplicate (task, block)")
    except AssertionError:
        pass
    fc = R.frame_counts(us)
    assert fc["k"] == 3 and fc["n_tasks"] == 20 and fc["n"] == len(us) == sum(fc["per_block"].values())
    C = R.rd_columns(us)
    assert all(len(v) == len(us) for v in C.values())
    E = AC.estimate(us, C, 50, 1)
    S = E["stats"]
    for c in AC.CONT + ("avg",):
        assert abs(S[f"XN[{c}]"]["point"] - (S[f"XR[{c}]"]["point"] - S[f"XD[{c}]"]["point"])) < 1e-12
        assert abs(S[f"XN[{c}]"]["point"] - (S[f"netB[{c}]"]["point"] - S[f"netQ[{c}]"]["point"])) < 1e-12
        assert S[f"XN[{c}]"]["point"] == S[f"K[{c}]"]["point"]
    bm = [np.mean([C["XR[d1]"][i] for i, u in enumerate(us) if u["block"] == b]) for b in blocks]
    # AC.estimate weights rows equally within a block; with 1 state per (task, block) this is the protocol's task-equal weighting
    assert abs(S["XR[d1]"]["point"] - float(np.mean(bm))) < 1e-12
    # 3. overall reading rule
    assert R.overall({"XR": "more", "XD": "not resolved"}).endswith("more rescues")
    assert R.overall({"XR": "not resolved", "XD": "fewer"}).endswith("fewer damages")
    assert R.overall({"XR": "not resolved", "XD": "not resolved"}).startswith("unresolved")
    assert R.overall({"XR": "more", "XD": "more"}).startswith("rescues and damages both higher")
    assert R.overall({"XR": "fewer", "XD": "fewer"}).startswith("unresolved")
    assert R.overall({"XR": "more", "XD": "fewer"}).startswith("both")
    print("commonstate_rd selftest OK (8 hand cases, identity, frame counts, cross-tab, block-mean point, unique (task, block), reading rule; nothing written)")


if __name__ == "__main__":
    main()
