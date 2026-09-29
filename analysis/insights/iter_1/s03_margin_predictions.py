"""Cross-model margin statistics and pre-registered divergence predictions (P1/P3).

1. For every model with a BF16 run on disk (eval tasks `a6000_<m>_bf16`, calibration tasks
   `a6000_<m>_bf16_cal`, or determinism runs `a6000_det_<m>_*`), tabulate the BF16 per-token margin
   distribution separately for text and tool-call decisions (tie density: P(margin < 0.25), < 0.5, < 1).
2. Take the per-token margin-shift distribution D(k) measured on q4 at each Gaussian level k
   (identical-context tokens, s01 logic, both seeds pooled) and ask whether it is model-independent by
   comparing with q8 where available.
3. Predict, for every model, (a) the identical-context decision-level divergence rate and (b) the
   first-divergence curve P(diverged by decision d) = 1 - E_task prod_{i<=d}(1 - p_i), where
   p_i = 1 - prod_tokens (1 - P(D < -m)), using that model's own BF16 margins and q4's D(k).
   The q4 row can be checked against s02; the other rows are predictions for the A6000 matrix.
"""
import re
from collections import defaultdict

import numpy as np

from common import a6000_runs, dump, load_both
from s01_token_flip_margin import hazard_fn, pair_stats

KS = ["0.03", "0.1", "0.3", "1"]
MODELS = ["q4", "q8", "q14", "q30a3", "q32"]


def bf16_sources(model):
    runs = a6000_runs()
    srcs = [r for r in (f"a6000_{model}_bf16", f"a6000_{model}_bf16_cal") if r in runs]
    srcs += [r for r in runs if r.startswith(f"a6000_det_{model}_")]
    return srcs


def shift_dist(model, k):
    ref = load_both(f"a6000_{model}_bf16")
    out = []
    for s in ("s1", "s2"):
        run = f"a6000_{model}_gauss{k}_{s}"
        if run in a6000_runs():
            sh, _, _ = pair_stats(ref, load_both(run), False)
            out += sh["retail"] + sh["airline"]
    return np.array(out)


def margin_table(dec):
    tab = {}
    for kind in ("text", "tool"):
        ms = np.array([m for r in dec.values() if r["kind"] == kind for m in r["margins"] if m is not None])
        mins = np.array([r["min_margin"] for r in dec.values() if r["kind"] == kind and r["min_margin"] is not None])
        if len(ms) == 0:
            continue
        tab[kind] = {
            "n_decisions": int(len(mins)), "n_tokens": int(len(ms)),
            "tok_p_lt_0.25": float((ms < 0.25).mean()), "tok_p_lt_0.5": float((ms < 0.5).mean()),
            "tok_p_lt_1": float((ms < 1).mean()),
            "dec_p_min_lt_0.25": float((mins < 0.25).mean()), "dec_p_min_lt_1": float((mins < 1).mean()),
            "dec_min_margin_median": float(np.median(mins)),
            "ties_per_decision_lt_0.5": float((ms < 0.5).sum() / len(mins)),
        }
    return tab


def predict(dec, D):
    h = hazard_fn(D)
    per_task = defaultdict(list)
    dec_p = {"text": [], "tool": []}
    for (dom, t, i), r in sorted(dec.items()):
        ms = [m for m in r["margins"] if m is not None]
        p = float(1 - np.prod(1 - h(np.array(ms)))) if ms else 0.0
        dec_p[r["kind"]].append(p)
        per_task[(dom, t)].append((i, p))
    curve = {}
    for d in (0, 1, 2, 4, 8, 12):
        vals = []
        for lst in per_task.values():
            lst = sorted(lst)
            vals.append(1 - np.prod([1 - p for i, p in lst if i <= d]))
        curve[f"<= {d}"] = round(float(np.mean(vals)), 3)
    return {"dec_div_text": round(float(np.mean(dec_p["text"])), 3) if dec_p["text"] else None,
            "dec_div_tool": round(float(np.mean(dec_p["tool"])), 3) if dec_p["tool"] else None,
            "first_div_curve": curve, "n_tasks": len(per_task)}


def main():
    res = {"shift_by_k": {}, "models": {}}
    D = {}
    for k in KS:
        D[k] = shift_dist("q4", k)
        row = {"q4_n": int(len(D[k])), "q4_abs_median": float(np.median(np.abs(D[k]))) if len(D[k]) else None,
               "q4_abs_p90": float(np.quantile(np.abs(D[k]), 0.9)) if len(D[k]) else None}
        d8 = shift_dist("q8", k) if "a6000_q8_bf16" in a6000_runs() else np.array([])
        if len(d8):
            row.update({"q8_n": int(len(d8)), "q8_abs_median": float(np.median(np.abs(d8))),
                        "q8_abs_p90": float(np.quantile(np.abs(d8), 0.9))})
        res["shift_by_k"][k] = row
        print("shift k=", k, row)
    for model in MODELS:
        for src in bf16_sources(model):
            dec = load_both(src)
            if not dec:
                continue
            entry = {"margins": margin_table(dec), "pred": {}}
            for k in KS:
                if len(D[k]):
                    entry["pred"][f"gauss{k}"] = predict(dec, D[k])
            res["models"][src] = entry
            mt = entry["margins"]
            print(f"\n{src}: " + " | ".join(f"{kd}: n={v['n_decisions']} tok<0.5={v['tok_p_lt_0.5']:.4f} ties/dec={v['ties_per_decision_lt_0.5']:.2f} "
                                             f"minmed={v['dec_min_margin_median']}" for kd, v in mt.items()))
            for k, p in entry["pred"].items():
                print(f"   {k:10s} text={p['dec_div_text']} tool={p['dec_div_tool']} curve={p['first_div_curve']}")
    dump("s03_margin_predictions.json", res)


if __name__ == "__main__":
    main()
