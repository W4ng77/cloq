"""Review item 9 (W11): pick an E3 open-loop statistic for the x-axis of Figures 2/3 that does not collapse.

For every E3 cell (analysis/openloop/a6k2/<model>/<cell>.{json,npz}, written by scripts/a6000/openloop_d.py) compute
candidate axes: |d| p50 / p90 / p99 / mean, token flip rate overall, flip rate at BF16 margin < 0.5, and
decision-any-flip. Score each by (a) dynamic range over non-reference cells (log10 max/min), (b) Spearman with the
closed-loop per-decision hazard of the same family (out/p02_ties.json, family mean), (c) Spearman with Gaussian k
(monotone dose axis), (d) whether the reference cell bf16 is at exactly 0 (D = 0 anchor).
Usage: python p05_e3_axis.py (after p02) -> out/p05_e3_axis.json
"""
import json
import re
from collections import defaultdict

import numpy as np
from scipy.stats import spearmanr

from common import OUT, ROOT, dump, fam, now


def stats(z):
    ad = np.abs(z["d"]); fl = z["flip"]; m = z["margin"]; dec = z["decision"]
    anyf = np.zeros(dec.max() + 1, bool)
    np.logical_or.at(anyf, dec, fl)
    lo = m < 0.5
    return {"abs_d_p50": float(np.quantile(ad, .5)), "abs_d_p90": float(np.quantile(ad, .9)),
            "abs_d_p99": float(np.quantile(ad, .99)), "abs_d_mean": float(ad.mean()),
            "flip_rate": float(fl.mean()), "flip_rate_m<0.5": float(fl[lo].mean()) if lo.any() else None,
            "decision_any_flip": float(anyf.mean())}


def main():
    p02 = json.load(open(OUT / "p02_ties.json"))
    res = {"snapshot_utc": now(), "models": {}}
    for model in ("q4", "q8"):
        base = ROOT / "analysis/openloop/a6k2" / model
        if not base.exists():
            continue
        cells = {f.stem: stats(np.load(f)) for f in sorted(base.glob("*.npz"))}
        hz = defaultdict(list)
        for r, v in p02["closed_loop"].get(model, {}).items():
            if v["hazard"] is not None:
                hz[fam(r, model)].append(v["hazard"])
        def fam_of(stem):
            return "null:eager" if stem == "bf16_eager" else "null:bf16" if stem == "bf16" else re.sub(r"_(s\d|d\d)$", "", stem)
        axes = {}
        keys = [k for k in next(iter(cells.values()))]
        for k in keys:
            xs = {c: v[k] for c, v in cells.items() if c != "bf16" and v[k] is not None}
            pos = [x for x in xs.values() if x > 0]
            pairs = [(xs[c], float(np.mean(hz[fam_of(c)]))) for c in xs if hz.get(fam_of(c))]
            gk = [(float(re.search(r"gauss([\d.]+)", c).group(1)), x) for c, x in xs.items() if c.startswith("gauss")]
            axes[k] = {"log10_range": round(float(np.log10(max(pos) / min(pos))), 2) if len(pos) > 1 else None,
                       "n_cells_zero": sum(1 for x in xs.values() if x == 0),
                       "spearman_vs_closed_loop_hazard": round(float(spearmanr(*zip(*pairs))[0]), 3) if len(pairs) > 4 else None,
                       "spearman_vs_gauss_k": round(float(spearmanr(*zip(*gk))[0]), 3) if len(gk) > 4 else None,
                       "bf16_value": cells.get("bf16", {}).get(k)}
        res["models"][model] = {"cells": cells, "axes": axes}
        print(model)
        for k, v in axes.items():
            print("  ", k, v)
    dump("p05_e3_axis.json", res)


if __name__ == "__main__":
    main()
