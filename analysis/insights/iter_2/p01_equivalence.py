"""Review items 1, 2, 4, 8 (paper/perturbation-equivalence-closed-loop.review.md §6): equivalence, within-pass
stratification, reference-only protocols, null-width diagnostics.

1. TOST per family (all draws pooled) and per single draw, against the task-level null mean
   (Δ = mean over (draw, task) of y − ybar_null(t); leave-one-out for null members; task-cluster bootstrap).
   Margins were declared by the review before this script ran: ±5 pp, ±7.5 pp (Flat Score), ±2·SD_null.
   Verdicts: equivalent (90% CI inside ±M) / below (95% CI upper < 0) / above (95% CI lower > 0) / inconclusive.
   Power: SE, MDE80 = 2.8·SE (two-sided 5%, 80% power), M80 = 2.93·SE (smallest margin TOST passes with 80% power
   when the true Δ is 0).
2. Within-pass: clean (a6k2) family vs clean null; legacy (a6000) family vs legacy null; inverse-variance combination;
   compared with the mixed-pass pooling of verify/out/v04_pooled_draws.json. Null-set sensitivity:
   A = {bf16, eager, nonce} (v04 convention, primary); B = A + gauss0.03 (paper §3.4 definition);
   C = canonical-prompt {bf16, eager, gauss0.03}; D = nonce only; plus leave-one-family-out of A.
4. Reference-only protocols against the canonical BF16 run: Flat-Score-style paired TOST ±7.5 pp (90% CI), Singh-style
   paired TOST ±2 pp, exact two-sided McNemar per draw. Applied to null members too (false-flag check).
8. Null width: fraction of tasks with 0 < p̂_t < 1, observed null-draw SD with chi-square 95% CI, Bernoulli
   prediction with the (R-1)/R plug-in bias corrected.
Usage: python p01_equivalence.py   -> out/p01_equivalence.json
"""
import json
from collections import defaultdict

import numpy as np
from scipy.stats import binomtest, chi2

from common import DOMS, OUT, ROOT, dump, fam, now, outcomes_both, runs_for, boot_mean_clusters

rng = np.random.default_rng(20260928)
B = 4000
MARGINS = {"5pp": 0.05, "7.5pp": 0.075}
NULLSETS = {"A": {"null:bf16", "null:eager", "null:nonce"},
            "B": {"null:bf16", "null:eager", "null:nonce", "gauss0.03"},
            "C": {"null:bf16", "null:eager", "gauss0.03"},
            "D": {"null:nonce"}}


def ci(bs, a):
    return [round(float(np.quantile(bs, a / 2)), 4), round(float(np.quantile(bs, 1 - a / 2)), 4)]


def verdict(c90, c95, M):
    eq = -M < c90[0] and c90[1] < M
    below, above = c95[1] < 0, c95[0] > 0
    if eq:
        return "equivalent" + (" (shift significant)" if below or above else "")
    if below:
        return "below-null" + (" beyond margin" if c90[1] < -M else "")
    if above:
        return "above-null"
    return "inconclusive"


def load_Y(model, pfx):
    Y = {}
    for r in runs_for(model, pfx):
        y = outcomes_both(r)
        if y:
            Y[r] = y
    return Y


def null_mean(Y, nulls):
    per = defaultdict(list)
    for r in nulls:
        for k, v in Y[r].items():
            per[k].append(v)
    return {k: float(np.mean(v)) for k, v in per.items() if len(v) >= 3}


def delta(Y, rs, nulls, pbar):
    clusters = defaultdict(list)
    for r in rs:
        for k, v in Y[r].items():
            if k not in pbar:
                continue
            if r in nulls:
                o = [Y[x][k] for x in nulls if x != r and k in Y[x]]
                if len(o) < 2:
                    continue
                ref = float(np.mean(o))
            else:
                ref = pbar[k]
            clusters[k].append(v - ref)
    if len(clusters) < 10:
        return None
    d, bs = boot_mean_clusters(clusters, rng, B)
    se = float(bs.std(ddof=1))
    p_boot = float(min(1.0, 2 * min((bs <= 0).mean(), (bs >= 0).mean())))
    return {"delta": round(d, 4), "ci90": ci(bs, 0.10), "ci95": ci(bs, 0.05), "se": round(se, 4), "p_boot": round(p_boot, 4),
            "mde80": round(2.8 * se, 4), "m80_tost": round(2.93 * se, 4),
            "n_tasks": len(clusters), "n_rows": int(sum(len(v) for v in clusters.values())), "_bs": bs}


def paired_vs_canon(Y, rs, canon):
    """Flat-Score/Singh style: per task, mean over the family's draws minus the canonical run."""
    clusters = {}
    for k in Y[canon]:
        vals = [Y[r][k] for r in rs if k in Y[r]]
        if vals:
            clusters[k] = [float(np.mean(vals)) - Y[canon][k]]
    if len(clusters) < 10:
        return None
    d, bs = boot_mean_clusters(clusters, rng, B)
    c90, c95 = ci(bs, 0.10), ci(bs, 0.05)
    out = {"delta_vs_canonical": round(d, 4), "ci90": c90, "ci95": c95, "n_tasks": len(clusters),
           "flatscore_7.5pp": verdict(c90, c95, 0.075), "singh_2pp": verdict(c90, c95, 0.02)}
    mc = []
    for r in rs:
        ks = [k for k in Y[r] if k in Y[canon]]
        a = sum(1 for k in ks if Y[r][k] and not Y[canon][k]); b = sum(1 for k in ks if Y[canon][k] and not Y[r][k])
        mc.append({"run": r, "cell_only": a, "canon_only": b, "discordant_frac": round((a + b) / len(ks), 3) if ks else None,
                   "p_two_sided": round(binomtest(a, a + b).pvalue, 4) if a + b else 1.0})
    out["mcnemar_per_draw"] = mc
    out["mcnemar_flags_p<0.05"] = sum(1 for x in mc if x["p_two_sided"] < 0.05)
    return out


def null_width(Y, nulls):
    full_keys = set.intersection(*[set(Y[r]) for r in nulls]) if nulls else set()
    R = len(nulls)
    if R < 3 or not full_keys:
        return None
    M = np.array([[Y[r][k] for k in sorted(full_keys)] for r in nulls], float)
    p = M.mean(0)
    rates = M.mean(1)
    s = float(rates.std(ddof=1))
    n = len(full_keys)
    pq_plug = float(np.mean(p * (1 - p)))
    pq_unb = pq_plug * R / (R - 1)
    pred_plug, pred_unb = np.sqrt(pq_plug / n), np.sqrt(pq_unb / n)
    lo_sd = s * np.sqrt((R - 1) / chi2.ppf(0.975, R - 1)); hi_sd = s * np.sqrt((R - 1) / chi2.ppf(0.025, R - 1))
    # expected fraction of degenerate tasks if all p_t were 1/2 vs observed
    hist = {f"{j}/{R}": int((np.round(p * R) == j).sum()) for j in range(R + 1)}
    return {"null_draws": nulls, "R": R, "n_tasks_common": n, "draw_rates": {r: round(float(x), 4) for r, x in zip(nulls, rates)},
            "sd_obs": round(s, 4), "sd_obs_ci95_chi2": [round(float(lo_sd), 4), round(float(hi_sd), 4)],
            "sd_pred_plugin": round(float(pred_plug), 4), "sd_pred_bias_corrected": round(float(pred_unb), 4),
            "ratio_obs_over_pred_bc": round(s / pred_unb, 3) if pred_unb else None,
            "ratio_ci95": [round(float(lo_sd / pred_unb), 3), round(float(hi_sd / pred_unb), 3)] if pred_unb else None,
            "frac_tasks_nondegenerate": round(float(np.mean((p > 0) & (p < 1))), 4),
            "n_tasks_always_pass": int((p == 1).sum()), "n_tasks_always_fail": int((p == 0).sum()),
            "pass_count_histogram": hist,
            "pairwise_discordance_mean": round(float(np.mean([np.mean(M[i] != M[j]) for i in range(R) for j in range(i + 1, R)])), 4),
            "pairwise_discordance_pred_2pq_unbiased": round(float(2 * pq_unb), 4),
            "note": "mean pairwise discordance == 2*mean unbiased p(1-p) is an algebraic identity, not a test"}


def analyse(model, pfx, v04=None):
    Y = load_Y(model, pfx)
    if not Y:
        return None
    fams = defaultdict(list)
    for r in Y:
        fams[fam(r, model)].append(r)
    canon = f"{pfx}_{model}_bf16"
    out = {"runs": {r: len(y) for r, y in Y.items()}, "nullsets": {}}
    for ns, members in NULLSETS.items():
        nulls = [r for r in Y if fam(r, model) in members]
        pbar = null_mean(Y, nulls)
        if len(pbar) < 20:
            continue
        # SD over near-complete null draws (>= 90% of null-mean tasks), as v04
        full = [r for r in nulls if sum(1 for k in Y[r] if k in pbar) >= 0.9 * len(pbar)]
        rates = [np.mean([Y[r][k] for k in Y[r] if k in pbar]) for r in full]
        sd_null = float(np.std(rates, ddof=1)) if len(rates) > 1 else None
        margins = dict(MARGINS)
        if sd_null:
            margins["2sd"] = 2 * sd_null
        fres, cres = {}, {}
        for f, rs in sorted(fams.items()):
            d = delta(Y, rs, nulls, pbar)
            if d is None:
                continue
            d.pop("_bs")
            d["draws"] = rs
            d["verdicts"] = {m: verdict(d["ci90"], d["ci95"], M) for m, M in margins.items()}
            fres[f] = d
            if ns == "A":
                for r in rs:
                    c = delta(Y, [r], nulls, pbar)
                    if c is not None:
                        c.pop("_bs")
                        c["verdicts"] = {m: verdict(c["ci90"], c["ci95"], M) for m, M in margins.items()}
                        cres[r] = c
        free = [r for f, rs in fams.items() if f in ("gauss0.03", "gauss0.1", "rtn_w8") for r in rs]
        fz = delta(Y, free, nulls, pbar) if free else None
        if fz:
            fz.pop("_bs")
            fz["draws"] = free
            fz["verdicts"] = {m: verdict(fz["ci90"], fz["ci95"], M) for m, M in margins.items()}
            fz["preregistered_falsified"] = bool(fz["delta"] < -0.034 and fz["ci95"][1] < 0)
        out.setdefault("pooled_free_zone", {})[ns] = fz
        out["nullsets"][ns] = {"members": sorted(members), "null_draws": nulls, "n_tasks_null_mean": len(pbar),
                               "sd_null_draws": round(sd_null, 4) if sd_null else None, "near_complete_null_draws": full,
                               "margins": {k: round(v, 4) for k, v in margins.items()}, "families": fres}
        if cres:
            out["nullsets"][ns]["cells"] = cres
    # leave-one-family-out of null set A
    lofo = {}
    for drop in sorted(NULLSETS["A"]):
        nulls = [r for r in Y if fam(r, model) in NULLSETS["A"] - {drop}]
        pbar = null_mean(Y, nulls)
        if len(pbar) < 20:
            continue
        lofo[drop] = {}
        for f, rs in sorted(fams.items()):
            d = delta(Y, rs, nulls, pbar)
            if d:
                lofo[drop][f] = {"delta": d["delta"], "ci95": d["ci95"], "v5pp": verdict(d["ci90"], d["ci95"], 0.05)}
    out["lofo_nullset_A"] = lofo
    # reference-only protocols
    if canon in Y:
        out["reference_only"] = {f: paired_vs_canon(Y, [r for r in rs if r != canon], canon)
                                 for f, rs in sorted(fams.items()) if [r for r in rs if r != canon]}
    nulls_A = [r for r in Y if fam(r, model) in NULLSETS["A"]]
    out["null_width_A"] = null_width(Y, [r for r in nulls_A if len(Y[r]) >= 0.97 * max(len(Y[x]) for x in nulls_A)])
    return out


def stratify(clean, legacy, v04m):
    """inverse-variance combination of within-pass Δ (null set A); compare with v04 mixed pooling."""
    res = {}
    fa = clean["nullsets"]["A"]["families"] if clean and "A" in clean["nullsets"] else {}
    fb = legacy["nullsets"]["A"]["families"] if legacy and "A" in legacy["nullsets"] else {}
    for f in sorted(set(fa) | set(fb)):
        a, b = fa.get(f), fb.get(f)
        r = {"clean": {k: a[k] for k in ("delta", "ci95", "n_tasks", "n_rows")} if a else None,
             "legacy": {k: b[k] for k in ("delta", "ci95", "n_tasks", "n_rows")} if b else None}
        if a and b and a["se"] > 0 and b["se"] > 0:
            w1, w2 = 1 / a["se"] ** 2, 1 / b["se"] ** 2
            d = (w1 * a["delta"] + w2 * b["delta"]) / (w1 + w2); se = (w1 + w2) ** -0.5
            r["ivw"] = {"delta": round(d, 4), "ci95": [round(d - 1.96 * se, 4), round(d + 1.96 * se, 4)],
                        "ci90": [round(d - 1.645 * se, 4), round(d + 1.645 * se, 4)],
                        "het_z": round((a["delta"] - b["delta"]) / np.hypot(a["se"], b["se"]), 2)}
            r["ivw"]["v5pp"] = verdict(r["ivw"]["ci90"], r["ivw"]["ci95"], 0.05)
            r["ivw"]["v7.5pp"] = verdict(r["ivw"]["ci90"], r["ivw"]["ci95"], 0.075)
        if v04m and f in v04m.get("families", {}):
            x = v04m["families"][f]
            r["v04_mixed"] = {"delta": x["delta_vs_null"], "ci95": x["ci95_task_cluster"], "draws": len(x["draws"])}
        res[f] = r
    return res


def main():
    v04 = json.load(open(ROOT / "analysis/insights/iter_1/verify/out/v04_pooled_draws.json"))
    res = {"snapshot_utc": now(), "margins_declared_by": "paper/perturbation-equivalence-closed-loop.review.md §3 W1 fix 1",
           "models": {}}
    for model in ("q4", "q8", "q14"):
        clean = analyse(model, "a6k2")
        legacy = analyse(model, "a6000") if model in ("q4", "q8") else None
        res["models"][model] = {"clean": clean, "legacy": legacy,
                                "stratified": stratify(clean, legacy, v04.get(model)) if legacy else None}
        if clean:
            print(model, "clean families (null A):")
            for f, d in clean["nullsets"]["A"]["families"].items():
                print(f"  {f:14s} {len(d['draws'])} Δ={d['delta']:+.3f} 95%{d['ci95']} n={d['n_tasks']} "
                      f"MDE={d['mde80']:.3f} M80={d['m80_tost']:.3f} {d['verdicts']}")
    dump("p01_equivalence.json", res)


if __name__ == "__main__":
    main()
