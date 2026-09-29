"""Review item 7 (P2b placeholder, V1-A4): write/read/text annotation of first divergences, write-set changes, and
which divergence statistic tracks damage (Δ) across families.

Per clean cell vs the canonical BF16 run (conversation-excluding-system pairing; infrastructure_error tasks dropped):
  * first divergence class: text->text (wording), text<->tool, read->read (different lookup/args), write-involved
    (either side is a state-changing call: cancel/modify/return/exchange/book/update/send/transfer*);
  * write-set change: the multiset of write calls (name + normalised args) over the episode differs from BF16's;
  * sanity: outcome flip rate when the write multiset is identical (the DB end state is a function of the writes).
Per family: mean of these rates over draws; Spearman across families (per model) of Δ (p01, null set A) against
write-set-change rate, write-involved first-divergence rate, tool-turn hazard and overall hazard (p02).
Not implemented: an "undone within episode" flag (needs per-write inverse matching); stated as open.
Usage: python p04_write_flips.py (after p01, p02) -> out/p04_write_flips.json
"""
import json
from collections import Counter, defaultdict

import numpy as np
from scipy.stats import spearmanr

from common import OUT, WRITE_RE, dump, fam, first_div, infra_tasks, load_many, now, outcomes_both, runs_for


def cls(rec):
    if rec["kind"] == "text":
        return "text"
    names = [c[0] or "" for c in rec["calls"]]
    return "write" if any(WRITE_RE.match(n) for n in names) else "read"


def writes(D, dom, t):
    ws = Counter()
    i = 0
    while (dom, t, i) in D:
        for n, a in D[(dom, t, i)]["calls"]:
            if n and WRITE_RE.match(n):
                ws[(n, a)] += 1
        i += 1
    return ws


def main():
    p01 = json.load(open(OUT / "p01_equivalence.json"))
    p02 = json.load(open(OUT / "p02_ties.json"))
    res = {"snapshot_utc": now(), "models": {}}
    for model in ("q4", "q8", "q14"):
        runs = runs_for(model)
        ref = f"a6k2_{model}_bf16"
        D = load_many(runs)
        Yr = outcomes_both(ref)
        cells = {}
        for run in runs:
            if run == ref:
                continue
            drop = infra_tasks(run) | infra_tasks(ref)
            Y = outcomes_both(run)
            fd = Counter(); ws_diff = []; flip_same_ws = []; flip_diff_ws = []
            for dom, t, i, e, kind, L, why in first_div(D[ref], D[run], "ctx"):
                if (dom, t) in drop or (dom, t) not in Y or (dom, t) not in Yr:
                    continue
                if why == "agent":
                    a, b = cls(D[ref][(dom, t, i)]), cls(D[run][(dom, t, i)])
                    c = "write-involved" if "write" in (a, b) else "text->text" if a == b == "text" else \
                        "read->read" if a == b == "read" else "text<->tool"
                    fd[c] += 1
                else:
                    fd["none/" + why] += 1
                d = writes(D[ref], dom, t) != writes(D[run], dom, t)
                ws_diff.append(d)
                fl = int(Y[(dom, t)] != Yr[(dom, t)])
                (flip_diff_ws if d else flip_same_ws).append(fl)
            n = sum(fd.values())
            if n < 10:
                continue
            nd = sum(v for k, v in fd.items() if not k.startswith("none"))
            cells[run] = {"family": fam(run, model), "n_tasks": n, "first_div_class": dict(fd),
                          "first_div_write_rate": round(fd["write-involved"] / nd, 4) if nd else 0.0,
                          "write_set_change_rate": round(float(np.mean(ws_diff)), 4),
                          "outcome_flip_given_same_writes": round(float(np.mean(flip_same_ws)), 4) if flip_same_ws else None,
                          "n_same_writes": len(flip_same_ws),
                          "outcome_flip_given_changed_writes": round(float(np.mean(flip_diff_ws)), 4) if flip_diff_ws else None}
        fams = defaultdict(list)
        for r, c in cells.items():
            fams[c["family"]].append(r)
        A = p01["models"][model]["clean"]["nullsets"]["A"]["families"]
        cl = p02["closed_loop"].get(model, {})
        rows = []
        for f, rs in sorted(fams.items()):
            if f not in A or f.startswith("null:"):
                continue
            hz = [cl[r]["hazard"] for r in rs if r in cl and cl[r]["hazard"] is not None]
            ht = [cl[r]["hazard_tool"] for r in rs if r in cl and cl[r]["hazard_tool"] is not None]
            rows.append({"family": f, "delta": A[f]["delta"], "n_tasks_delta": A[f]["n_tasks"],
                         "write_set_change": float(np.mean([cells[r]["write_set_change_rate"] for r in rs])),
                         "first_div_write": float(np.mean([cells[r]["first_div_write_rate"] for r in rs])),
                         "hazard_tool": float(np.mean(ht)) if ht else None, "hazard": float(np.mean(hz)) if hz else None})
        corr = {}
        for k in ("write_set_change", "first_div_write", "hazard_tool", "hazard"):
            xs = [(r[k], r["delta"]) for r in rows if r[k] is not None]
            if len(xs) >= 5:
                rho, p = spearmanr([x for x, _ in xs], [y for _, y in xs])
                corr[k] = {"spearman_rho_vs_delta": round(float(rho), 3), "p": round(float(p), 4), "n_families": len(xs)}
        res["models"][model] = {"cells": cells, "families": rows, "spearman": corr}
        print(model, corr)
        for r in rows:
            print("  ", r)
    dump("p04_write_flips.json", res)


if __name__ == "__main__":
    main()
