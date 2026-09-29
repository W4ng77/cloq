"""r03: are the tasks a perturbation breaks (or fixes) a property of the checkpoint, of the method, or of the task?

For every ordered pair of perturbed draws (a, b) of one model, reference = nonce nulls U minus nonce-mates of a and b.
On reference-always-ok tasks: P(b fails | a fails) and its lift over P(b fails); on always-fail tasks the same for fixes.
Pairs are grouped by relation:
  same_ckpt          same checkpoint, different nonce            (checkpoint-determined?)
  same_method_other  same method + bit width, other checkpoint   (GPTQ d1 vs d2; Gaussian k, other seed)
  quant_vs_quant     different quantizer methods                 (RTN vs GPTQ vs AWQ, any bits)
  quant_vs_gauss     a quantizer draw vs a Gaussian draw (k >= 0.3)
  null               two nonce nulls (reference = the other U draws)
Only perturbation draws with enough dose to break anything are used for the cross-method groups: quantizers at <= 4
bits and Gaussian k >= 0.3 (RTN-W8, k <= 0.1 are reported separately as 'small').
Fragility score (prediction test): for each model, score each reference-always-ok task by its break rate over all
Gaussian draws (canonical cells k >= 0.3 and fixed controls), then compute the AUC of that score for predicting the
breaks of every quantizer draw (and the symmetric fix-score AUC on always-fail tasks). Reference for the AUC: the
nonce nulls not sharing the quantizer draw's nonce; tasks classified on that reference.
Usage: CLOQ_SNAPSHOT=<manifest> python r03_fragility.py -> out/r03_fragility_<tag>.json
"""
import os
import re
from collections import defaultdict
from itertools import permutations

import numpy as np

from r_common import dump, load, rnd

MODELS = os.environ.get("CLOQ_MODELS", "q4,q8,q14,q30a3").split(",")


def kval(ck):
    m = re.match(r"gauss([\d.]+)_s", ck)
    return float(m.group(1)) if m else None


def method(k):
    if k["kind"].startswith("gauss"):
        return f"gauss{kval(k['ckpt'])}"
    return re.sub(r"_d\d$", "", k["ckpt"])


def big(k):
    if k["kind"].startswith("gauss"):
        return kval(k["ckpt"]) >= 0.3
    return not k["ckpt"].startswith("rtn_w8")


def relation(ka, kb):
    ga, gb = ka["kind"].startswith("gauss"), kb["kind"].startswith("gauss")
    ca = ka["ckpt"] + ("_fixed" if ka["kind"] == "gauss_fixed" else "")
    cb = kb["ckpt"] + ("_fixed" if kb["kind"] == "gauss_fixed" else "")
    same_ck = (ka["ckpt"] == kb["ckpt"])  # a fixed Gaussian control shares its checkpoint with the canonical seed cell
    if same_ck:
        return "same_ckpt"
    if not (big(ka) and big(kb)):
        return "small"
    if method(ka) == method(kb):
        return "same_method_other_ckpt"
    if not ga and not gb:
        return "quant_vs_quant"
    if ga != gb:
        return "quant_vs_gauss"
    return "gauss_vs_gauss_other_k"


def auc(score, y):
    pos, neg = score[y == 1], score[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    gt = (pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean()
    return float(gt)


def main():
    res = {"models": {}}
    for mdl in MODELS:
        Y, meta = load(mdl)
        U = sorted(r for r in Y if meta[r]["family"] == "null_U")
        P = sorted(r for r in Y if meta[r]["kind"] in ("quant", "gauss_fixed", "gauss_canon"))
        tasks = sorted(set.intersection(*[set(Y[r]) for r in U + P]))
        A = {r: np.array([Y[r][t] for t in tasks], float) for r in U + P}
        acc = defaultdict(lambda: np.zeros(8))  # nf, nff, n_ok_b, fails_b, nx, nxx, n_fl_b, fixes_b
        for a, b in permutations(P + U, 2):
            ka, kb = meta[a], meta[b]
            if (ka["family"] == "null_U") != (kb["family"] == "null_U"):
                continue
            rel = "null" if ka["family"] == "null_U" else relation(ka, kb)
            R = [u for u in U if u not in (a, b) and meta[u]["nonce"] not in (ka["nonce"], kb["nonce"])]
            if len(R) < 3:
                continue
            pr = np.mean([A[u] for u in R], 0)
            ok, fl = pr == 1, pr == 0
            ya, yb = A[a], A[b]
            acc[rel] += [((1 - ya) * ok).sum(), ((1 - ya) * (1 - yb) * ok).sum(), ok.sum(), ((1 - yb) * ok).sum(),
                         (ya * fl).sum(), (ya * yb * fl).sum(), fl.sum(), (yb * fl).sum()]
        groups = {}
        for rel, v in acc.items():
            pf, pfc = v[3] / v[2], (v[1] / v[0] if v[0] else np.nan)
            px, pxc = v[7] / v[6], (v[5] / v[4] if v[4] else np.nan)
            groups[rel] = dict(p_fail=rnd(pf), p_fail_given_fail=rnd(pfc), lift_break=rnd(pfc / pf if pf else np.nan),
                               p_fix=rnd(px), p_fix_given_fix=rnd(pxc), lift_fix=rnd(pxc / px if px else np.nan),
                               n_break_events=int(v[0]), n_fix_events=int(v[4]))
        # fragility-score AUC: Gaussian draws (k >= 0.3) -> quantizer draws
        G = [r for r in P if meta[r]["kind"].startswith("gauss") and big(meta[r])]
        Q = [r for r in P if meta[r]["kind"] == "quant"]
        aucs = {}
        for q in Q:
            R = [u for u in U if meta[u]["nonce"] != meta[q]["nonce"]]
            pr = np.mean([A[u] for u in R], 0)
            ok, fl = pr == 1, pr == 0
            gscore_b = np.mean([1 - A[g] for g in G], 0) if G else None
            gscore_f = np.mean([A[g] for g in G], 0) if G else None
            # quantizer -> quantizer (other methods only) score
            Qo = [r for r in Q if method(meta[r]) != method(meta[q])]
            qscore_b = np.mean([1 - A[r] for r in Qo], 0) if Qo else None
            qscore_f = np.mean([A[r] for r in Qo], 0) if Qo else None
            aucs[q] = dict(method=method(meta[q]), n_ok=int(ok.sum()), n_break=int(((1 - A[q]) * ok).sum()),
                           auc_break_from_gauss=rnd(auc(gscore_b[ok], (1 - A[q])[ok])) if G else None,
                           auc_fix_from_gauss=rnd(auc(gscore_f[fl], A[q][fl])) if G else None,
                           auc_break_from_other_quant=rnd(auc(qscore_b[ok], (1 - A[q])[ok])) if Qo else None,
                           auc_fix_from_other_quant=rnd(auc(qscore_f[fl], A[q][fl])) if Qo else None)
        summ = {}
        for key in ("auc_break_from_gauss", "auc_fix_from_gauss", "auc_break_from_other_quant", "auc_fix_from_other_quant"):
            vals = [v[key] for v in aucs.values() if v[key] is not None and "w8" not in v["method"]]
            summ[key] = dict(mean=rnd(np.mean(vals)) if vals else None, n=len(vals),
                             frac_gt_0_5=rnd(np.mean(np.array(vals) > 0.5)) if vals else None)
        res["models"][mdl] = dict(n_tasks=len(tasks), U=U, gauss_draws=G, groups=groups, auc_per_quant_draw=aucs,
                                  auc_summary_excl_w8=summ)
        print(mdl, {k: (v["p_fail_given_fail"], v["p_fail"], v["lift_break"], v["lift_fix"], v["n_break_events"]) for k, v in groups.items()})
        print("   AUC", summ)
    dump("r03_fragility", res)


if __name__ == "__main__":
    main()
