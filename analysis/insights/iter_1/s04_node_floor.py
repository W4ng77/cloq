"""Numerical-floor control: BF16 vs BF16 on different nodes/servers (determinism runs).

Pairs every a6000_det_<m>_a / _b run with each other and with the eval-task BF16 run, and reports
first-divergence statistics (s02 logic) and identical-context token shift scale (s01 logic).
A non-zero divergence here is a pure numerical perturbation (no weight or prompt change).
"""
import json
from itertools import combinations
import numpy as np
from common import RUNS, a6000_runs, dump, load_both
from s01_token_flip_margin import pair_stats
from s02_trajectory_divergence import first_divergence, km


def host(run):
    p = RUNS / run / "retail" / "environment.json"
    e = json.load(open(p)) if p.exists() else {}
    return e.get("hostname"), e.get("user_api_base")


res = {}
for m in ("q4", "q8", "q14", "q30a3", "q32"):
    runs = [r for r in a6000_runs() if r.startswith(f"a6000_det_{m}_") or r == f"a6000_{m}_bf16"]
    data = {r: load_both(r) for r in runs}
    for a, b in combinations(runs, 2):
        rows = first_divergence(data[a], data[b], False)
        sh, _, decs = pair_stats(data[a], data[b], False)
        s = np.abs(np.array(sh["retail"] + sh["airline"]))
        ev = [r for r in rows if r["event"]]
        out = {"hosts": [host(a), host(b)], "n_tasks": len(rows), "n_diverged": len(ev), "km": km(rows),
               "flip_margin_median": float(np.median([r["ref_margin_at_flip"] for r in ev if r["ref_margin_at_flip"] is not None])) if ev else None,
               "identical_ctx_decisions": len(decs), "shift_abs_median": float(np.median(s)) if len(s) else None,
               "frac_tokens_shift_nonzero": float((s > 0).mean()) if len(s) else None}
        res[f"{a} vs {b}"] = out
        print(f"{a} vs {b}: {out}")
dump("s04_node_floor.json", res)
