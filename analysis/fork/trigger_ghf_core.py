"""Pure functions for trigger_ghf.py (frozen Q-only trigger read under G / H / F). EXPLORATORY, POST HOC.

Protocol: docs/insights/TRIGGER_GHF_POSTHOC.md. A row is a dict with keys c (cell), task, block, G, H, F (int in
{-1, 0, 1} or None when an arm is missing), sel (bool, frozen trigger selection at one rate).
"""
from __future__ import annotations

import collections

import numpy as np

MODES = ("G", "H", "F")


def labels(Y: dict) -> dict:
    """G = BQ - QQ, H = QB - QQ, F = BB - QQ; a label is None if one of its two arms is missing or not 0/1."""
    ok = {a: (Y.get(a) in (0, 1)) for a in ("BB", "BQ", "QB", "QQ")}
    out = {}
    for m, a in (("G", "BQ"), ("H", "QB"), ("F", "BB")):
        out[m] = int(Y[a] - Y["QQ"]) if ok[a] and ok["QQ"] else None
    return out


def four_arm(r: dict) -> bool:
    return all(r[m] is not None for m in MODES)


def by_cell(rows):
    d = collections.defaultdict(list)
    for r in rows:
        d[r["c"]].append(r)
    return dict(sorted(d.items()))


def oracle_identity(N: int, R: int, D: int, m: int) -> int:
    """Net of the best m of N rows with R (+1), D (-1), N-R-D (0) labels."""
    return min(m, R) - max(0, m - (N - D))


def oracle_cell(xs: list[dict], m: int, mode: str) -> dict:
    """Hindsight oracle of one mode in one cell: top-m rows by label; boundary ties broken uniformly at random,
    returned as the exact expectation of every mode's sum (and rescues/damages) over the selected set."""
    xs = [r for r in xs if r[mode] is not None]
    m = min(m, len(xs))
    out = {f"{k}_{q}": 0.0 for q in MODES for k in ("net", "r", "d")}
    left = m
    for v in (1, 0, -1):
        cls = [r for r in xs if r[mode] == v]
        if not cls or left == 0:
            continue
        frac = min(left, len(cls)) / len(cls)
        left -= min(left, len(cls))
        for q in MODES:
            vals = [r[q] for r in cls if r[q] is not None]
            out[f"net_{q}"] += frac * sum(vals)
            out[f"r_{q}"] += frac * sum(1 for x in vals if x == 1)
            out[f"d_{q}"] += frac * sum(1 for x in vals if x == -1)
    out["m"] = m
    return out


def point(rows: list[dict], mode: str) -> dict:
    """Trigger rescues/damages/net and the matched-count random expectation, per cell and pooled (rows with label)."""
    per, tot = {}, collections.Counter()
    for c, xs in by_cell(rows).items():
        xs = [r for r in xs if r[mode] is not None]
        N, sel = len(xs), [r for r in xs if r["sel"]]
        R, D, m = sum(r[mode] == 1 for r in xs), sum(r[mode] == -1 for r in xs), len(sel)
        e = {"N": N, "R": R, "D": D, "m": m, "r": sum(r[mode] == 1 for r in sel), "d": sum(r[mode] == -1 for r in sel)}
        e["net"] = e["r"] - e["d"]
        e["rand"] = m * (R - D) / N if N else 0.0
        e["any_pos"] = sum(max(r[q] for q in MODES) > 0 for r in sel if four_arm(r))
        per[c] = e
        for k, v in e.items():
            tot[k] += v
    return {"per_cell": per, "pooled": dict(tot)}


class Boot:
    """Task-cluster and crossed task x block bootstrap with selections held fixed. Both are new-task readings: the task
    interval is a new-task reading conditional on the 2 observed blocks; no fixed-pool (block) interval exists with K = 2
    (amendment 2026-10-05 b). Statistic per draw and mode:
    net_pp = 100 sum(w sel L)/sum(w); adj_pp = 100 sum_c [sum(w sel L) - sum(w sel) sum(w L)/sum(w)]_c / sum(w)."""

    def __init__(self, rows: list[dict], B: int, seed: int):
        rows = [r for r in rows if four_arm(r)]
        cells = sorted({r["c"] for r in rows})
        tasks = sorted({r["task"] for r in rows})
        blocks = sorted({r["block"] for r in rows})
        self.ci = np.array([cells.index(r["c"]) for r in rows])
        self.ti = np.array([tasks.index(r["task"]) for r in rows])
        self.bi = np.array([blocks.index(r["block"]) for r in rows])
        self.L = np.array([[r[q] for q in MODES] for r in rows], float)  # n x 3
        self.anyp = np.array([float(max(r[q] for q in MODES) > 0) for r in rows])
        self.C = np.eye(len(cells))[self.ci]  # n x C
        rng = np.random.default_rng(seed)
        nt, nb = len(tasks), len(blocks)
        tc = np.stack([np.bincount(rng.integers(0, nt, nt), minlength=nt) for _ in range(B)])
        bc = np.stack([np.bincount(rng.integers(0, nb, nb), minlength=nb) for _ in range(B)])
        self.W = {"task": tc[:, self.ti].astype(float), "crossed": (tc[:, self.ti] * bc[:, self.bi]).astype(float)}
        self.W["none"] = np.ones((1, len(rows)))
        self.keys = [(r["c"], r["task"], r["block"], r.get("key")) for r in rows]
        assert len(set(self.keys)) == len(self.keys), "duplicate bootstrap keys"

    def stats(self, sel: np.ndarray, kind: str) -> dict:
        W = self.W[kind]  # B x n
        tot = W.sum(1)
        out = {}
        for j, q in enumerate(MODES + ("any",)):
            L = self.anyp if q == "any" else self.L[:, j]
            s_sel = (W * sel * L) @ self.C  # B x C
            w_sel = (W * sel) @ self.C
            s_all, w_all = (W * L) @ self.C, W @ self.C
            rand = np.divide(w_sel * s_all, w_all, out=np.zeros_like(s_all), where=w_all > 0)
            out[f"net_pp_{q}"] = 100 * s_sel.sum(1) / tot
            out[f"adj_pp_{q}"] = 100 * (s_sel - rand).sum(1) / tot
        for a, b in (("H", "G"), ("F", "G"), ("F", "H")):
            out[f"net_pp_{a}-{b}"] = out[f"net_pp_{a}"] - out[f"net_pp_{b}"]
            out[f"adj_pp_{a}-{b}"] = out[f"adj_pp_{a}"] - out[f"adj_pp_{b}"]
        return out

    def summary(self, sel_rows: list[dict]) -> dict:
        sk = {(r["c"], r["task"], r["block"], r.get("key")) for r in sel_rows}
        sel = np.array([float(k in sk) for k in self.keys])
        pt = {k: float(v[0]) for k, v in self.stats(sel, "none").items()}
        res, st = {}, {kind: self.stats(sel, kind) for kind in ("task", "crossed")}
        for k in pt:
            res[k], raw = {"point": round(pt[k], 3)}, []
            for kind in ("task", "crossed"):
                lo, hi = (float(x) for x in np.percentile(st[kind][k], [2.5, 97.5]))
                raw.append((lo, hi))
                res[k][kind] = [round(lo, 3), round(hi, 3)]
            res[k]["resolved"] = all(not (lo <= 0 <= hi) for lo, hi in raw)  # unrounded bounds
        return res


def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for j, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - j) * ps[i]))
        adj[i] = round(run, 4)
    return adj
