"""Closed-loop first divergence per perturbation (A6000, live snapshot).

For each task, walk decisions 0,1,2,... while perturbed run P and its reference R have identical context
and identical action. The first decision where the action differs is the trajectory's first divergence
(its context is still identical, so the BF16 margin at the first differing token is well defined).
Tasks where either run has not yet produced the next decision are right-censored (live runs).

Reported per config: Kaplan-Meier P(diverged by decision d), the type of the first divergence
(wording = both text; args = same tool names, different arguments; behaviour = text<->tool or different
tool names), and the reference-model margin at the flipped token.
Also a BF16-vs-BF16 re-run control (determinism floor).

Usage: python s02_trajectory_divergence.py [model]
"""
import re
import sys
from collections import Counter, defaultdict

import numpy as np

from common import a6000_runs, dump, load_both

MODEL = sys.argv[1] if len(sys.argv) > 1 else "q4"
REF = f"a6000_{MODEL}_bf16"


def first_divergence(ref, pert, nonce):
    key = "ctx_key" if nonce else "prompt_sha"
    tasks = sorted({(d, t) for d, t, _ in ref} & {(d, t) for d, t, _ in pert})
    rows = []
    for dom, t in tasks:
        i = 0
        while True:
            b, p = ref.get((dom, t, i)), pert.get((dom, t, i))
            if b is None or p is None:
                rows.append({"task": f"{dom}/{t}", "event": 0, "idx": i})  # censored at i
                break
            if b[key] != p[key]:
                rows.append({"task": f"{dom}/{t}", "event": 0, "idx": i, "ctx_mismatch_without_action_flip": True})
                break
            if b["action"] != p["action"]:
                a, c = b["ids"], p["ids"]
                n = min(len(a), len(c))
                j = next((k for k in range(n) if a[k] != c[k]), n)
                mb = b["margins"]
                flip_m = mb[j] if j < len(mb) else None
                bk, pk = b["action"][0], p["action"][0]
                if bk == pk == "text":
                    typ = "wording"
                elif bk == pk == "tool" and [x[0] for x in b["action"][1]] == [x[0] for x in p["action"][1]]:
                    typ = "args"
                else:
                    typ = "behaviour"
                rows.append({"task": f"{dom}/{t}", "event": 1, "idx": i, "type": typ, "ref_kind": bk,
                             "flip_token_pos": j, "ref_margin_at_flip": flip_m, "ref_min_margin": b["min_margin"]})
                break
            i += 1
    return rows


def km(rows, horizon=(0, 1, 2, 4, 8, 12)):
    """Kaplan-Meier P(first divergence at decision <= d)."""
    ev = sorted((r["idx"], r["event"]) for r in rows)
    out, surv = {}, 1.0
    times = sorted({i for i, _ in ev})
    for tm in times:
        at_risk = sum(1 for i, _ in ev if i >= tm)
        d = sum(1 for i, e in ev if i == tm and e == 1)
        if at_risk:
            surv *= 1 - d / at_risk
        for h in horizon:
            if tm <= h:
                out[h] = 1 - surv
    return {f"<= {h}": round(out.get(h, 0.0), 3) for h in horizon}


def summarise(name, rows, refname):
    evs = [r for r in rows if r["event"]]
    fm = [r["ref_margin_at_flip"] for r in evs if r["ref_margin_at_flip"] is not None]
    s = {
        "reference": refname,
        "n_tasks": len(rows),
        "n_first_divergences": len(evs),
        "ctx_mismatch_without_action_flip": sum(1 for r in rows if r.get("ctx_mismatch_without_action_flip")),
        "km_diverged_by_decision": km(rows),
        "first_div_type": dict(Counter(r["type"] for r in evs)),
        "first_div_idx_median": float(np.median([r["idx"] for r in evs])) if evs else None,
        "ref_margin_at_flip_median": float(np.median(fm)) if fm else None,
        "ref_margin_at_flip_quartiles": [float(x) for x in np.quantile(fm, [0.25, 0.75])] if fm else None,
        "rows": rows,
    }
    print(f"{name:28s} tasks={s['n_tasks']:3d} div={s['n_first_divergences']:3d} KM={s['km_diverged_by_decision']} "
          f"types={s['first_div_type']} flip-margin med={s['ref_margin_at_flip_median']} q={s['ref_margin_at_flip_quartiles']} "
          f"ctxmis={s['ctx_mismatch_without_action_flip']}")
    return s


def main():
    runs = a6000_runs(f"a6000_{MODEL}_")
    bf16 = load_both(REF)
    res = {"model": MODEL, "configs": {}}
    det = f"a6000_det_{MODEL}_a"
    if det in a6000_runs("a6000_det_"):
        res["configs"][det] = summarise(det + " (BF16 re-run)", first_divergence(bf16, load_both(det), False), REF)
    for run in runs:
        if run == REF or run.endswith("_cal"):
            continue
        m = re.search(r"_n(\d+)$", run)
        if "_null_" in run:
            ref, nonce, refname = bf16, True, REF
        elif m and f"a6000_{MODEL}_null_n{m.group(1)}" in runs:
            refname = f"a6000_{MODEL}_null_n{m.group(1)}"
            ref, nonce = load_both(refname), False
        elif m:
            ref, nonce, refname = bf16, True, REF + " (composite)"
        else:
            ref, nonce, refname = bf16, False, REF
        rows = first_divergence(ref, load_both(run), nonce)
        if rows:
            res["configs"][run] = summarise(run, rows, refname)
    dump(f"s02_trajectory_divergence_{MODEL}.json", res)


if __name__ == "__main__":
    main()
