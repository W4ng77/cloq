"""r04: can the UNPERTURBED model's own decision margins predict which tasks a quantizer breaks / fixes?

Per task, from the nonce-null runs U of the reference BF16 model (decisions.jsonl token_margins, via the iter-2 cache):
  tool_min     min over tool-call decisions of the decision's min token margin (nats; low = fragile), mean over U draws
  write_min    same over state-changing tool calls (cancel|modify|return|exchange|book|update|send|transfer); 30 if none
  n_tool_nt1   number of tool-call decisions with min margin < 1.0, mean over U draws
  n_nt1        number of decisions (any kind) with min margin < 1.0
  n_dec        number of decisions (length control)
  n_tool       number of tool-call decisions (length control)
Target: breaks of reference-always-ok tasks (fixes of always-fail tasks) in every quantizer draw at <= 4 bits;
reference = U minus the draw's nonce-mates. AUC per draw, averaged per model. Direction: higher fragility score =
more likely to break (scores that are 'low = fragile' are negated).
Robustness for r03: the Gaussian->quantizer fragility AUC recomputed on a 'super-robust' task set: ok in every U draw,
both canonical null draws (bf16, bf16_eager) and every Gaussian k <= 0.03 draw (all near-null), to exclude
null-misclassified coin tasks.
Usage: CLOQ_SNAPSHOT=<manifest> python r04_margin_predict.py -> out/r04_margin_predict_<tag>.json
"""
import os
import re
from collections import defaultdict

import numpy as np

from common import WRITE_RE, load_many
from r_common import dump, load, rnd

MODELS = os.environ.get("CLOQ_MODELS", "q4,q8,q14,q30a3").split(",")
SCORES = ("tool_min", "write_min", "n_tool_nt1", "n_nt1", "n_dec", "n_tool")
NEG = {"tool_min", "write_min"}


def auc(score, y):
    pos, neg = score[y == 1], score[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def task_scores(D):
    """D: {(dom, task, i): rec} for one run -> {(dom, task): dict of scores}."""
    per = defaultdict(list)
    for (d, t, i), r in D.items():
        per[(d, t)].append(r)
    out = {}
    for k, recs in per.items():
        mm = [min([x for x in r["m"] if x is not None] or [30.0]) for r in recs]
        tool = [x for x, r in zip(mm, recs) if r["kind"] == "tool"]
        write = [x for x, r in zip(mm, recs) if r["kind"] == "tool" and any(WRITE_RE.match(c[0] or "") for c in r["calls"])]
        out[k] = dict(tool_min=min(tool) if tool else 30.0, write_min=min(write) if write else 30.0,
                      n_tool_nt1=sum(x < 1.0 for x in tool), n_nt1=sum(x < 1.0 for x in mm), n_dec=len(recs),
                      n_tool=len(tool))
    return out


def main():
    res = {"models": {}}
    for mdl in MODELS:
        Y, meta = load(mdl)
        U = sorted(r for r in Y if meta[r]["family"] == "null_U")
        Q = sorted(r for r in Y if meta[r]["kind"] == "quant" and "w8" not in r)
        G = sorted(r for r in Y if meta[r]["kind"].startswith("gauss") and float(re.search(r"gauss([\d.]+)", r).group(1)) >= 0.3)
        NEARNULL = sorted(r for r in Y if (meta[r]["family"] == "null_K") or
                          (meta[r]["kind"] == "gauss_canon" and float(re.search(r"gauss([\d.]+)", r).group(1)) <= 0.03))
        tasks = sorted(set.intersection(*[set(Y[r]) for r in U + Q + G + NEARNULL]))
        A = {r: np.array([Y[r][t] for t in tasks], float) for r in U + Q + G + NEARNULL}
        dec = load_many(U)
        S = {s: np.zeros(len(tasks)) for s in SCORES}
        for u in U:
            ts = task_scores(dec[u])
            for s in SCORES:
                S[s] += np.array([ts.get(t, {}).get(s, np.nan) for t in tasks], float) / len(U)
        per_draw = {}
        for q in Q:
            R = [u for u in U if meta[u]["nonce"] != meta[q]["nonce"]]
            pr = np.mean([A[u] for u in R], 0)
            ok, fl = (pr == 1) & np.isfinite(S["n_dec"]), (pr == 0) & np.isfinite(S["n_dec"])
            row = {"n_ok": int(ok.sum()), "n_break": int(((1 - A[q]) * ok).sum()), "n_fail": int(fl.sum()),
                   "n_fix": int((A[q] * fl).sum())}
            for s in SCORES:
                sc = -S[s] if s in NEG else S[s]
                row["break_" + s] = auc(sc[ok], (1 - A[q])[ok])
                row["fix_" + s] = auc(sc[fl], A[q][fl])
            per_draw[q] = row
        summ = {}
        for key in [f"{a}_{s}" for a in ("break", "fix") for s in SCORES]:
            v = [r[key] for r in per_draw.values() if r[key] is not None]
            summ[key] = dict(mean=rnd(np.mean(v)) if v else None, n=len(v), frac_gt_0_5=rnd(np.mean(np.array(v) > 0.5)) if v else None)
        # super-robust robustness check of the Gaussian -> quantizer fragility AUC
        sr_ok = np.all([A[r] == 1 for r in U + NEARNULL], 0)
        sr_fail = np.all([A[r] == 0 for r in U + NEARNULL], 0)
        gb = np.mean([1 - A[g] for g in G], 0) if G else None
        gf = np.mean([A[g] for g in G], 0) if G else None
        sr = [dict(q=q, auc_break=auc(gb[sr_ok], (1 - A[q])[sr_ok]), auc_fix=auc(gf[sr_fail], A[q][sr_fail]),
                   n_break=int(((1 - A[q]) * sr_ok).sum()), n_fix=int((A[q] * sr_fail).sum())) for q in Q] if G else []
        res["models"][mdl] = dict(U=U, quant_draws=Q, gauss_draws=G, near_null_draws=NEARNULL, n_tasks=len(tasks),
                                  auc_summary=summ, per_draw={k: {a: rnd(b) for a, b in v.items()} for k, v in per_draw.items()},
                                  super_robust=dict(n_ok=int(sr_ok.sum()), n_fail=int(sr_fail.sum()),
                                                    break_rate_quant=rnd(np.mean([x["n_break"] for x in sr]) / max(sr_ok.sum(), 1)) if sr else None,
                                                    fix_rate_quant=rnd(np.mean([x["n_fix"] for x in sr]) / max(sr_fail.sum(), 1)) if sr else None,
                                                    auc_break_from_gauss_mean=rnd(np.mean([x["auc_break"] for x in sr if x["auc_break"] is not None])) if sr else None,
                                                    auc_fix_from_gauss_mean=rnd(np.mean([x["auc_fix"] for x in sr if x["auc_fix"] is not None])) if sr else None,
                                                    per_draw=[{a: rnd(b) if isinstance(b, float) else b for a, b in x.items()} for x in sr]))
        print(mdl, {k: v["mean"] for k, v in summ.items()})
        print("   super-robust", {k: v for k, v in res["models"][mdl]["super_robust"].items() if k != "per_draw"})
    dump("r04_margin_predict", res)


if __name__ == "__main__":
    main()
