"""Conformal / permutation layer for perturbation equivalence (iter-2, conformal request; companion of p01 TOST).

H0(C): the runs of cell/family C are exchangeable with the null-family runs (bf16, eager, nonce nulls = null set A;
B = A + gauss0.03 as sensitivity). Unit = one closed-loop run (a draw of the perturbation); outcome vector
y_r(t) in {0,1} over the 85 dev tasks (common.outcomes: db_match AND normal termination; infrastructure_error = missing).
Eligibility: a run enters only if it covers >= MINCOV of the 85 tasks; tests use the tasks observed in every run of
the bag (complete case). Partial runs (being re-run as *_redo, or still running) are listed in `snapshot`.

1. Per-draw conformal p-value (full conformal, bag = nulls + draw, n+1 runs), randomised tie-breaking:
       p = (#{s_i > s_C} + U * #{s_i = s_C}) / (n+1),  U ~ Unif(0,1)   (exactly Unif under H0; also conservative U=1)
   scores (symmetric in the bag, so exchangeable under H0):
       net   s(r) = |rate_r - mean rate of bag|                (two-sided net shift)
       harm  s(r) = max(0, mean rate of bag\\r - rate_r)        (one-sided: C worse)
       churn s(r) = mean_t |y_r(t) - mean_{bag\\r} y(t)|        (task-profile distance: WHICH tasks succeed)
   granularity: p >= 1/(n+1).
2. Family exact permutation test over draw labels (m draws of the family + n nulls; all C(n+m, m) relabellings):
       T_net = |mean_t (ybar_C(t) - ybar_N(t))|, T_harm = mean_t (ybar_N(t) - ybar_C(t)),
       T_churn = mean_t |ybar_C(t) - ybar_N(t)|;  randomised and conservative p; p_min = 1/C(n+m, m).
3. Conformal e-values (soft rank): e_C = (n+1) s_C / sum_bag s_i (e=1 if all s=0); E[e] <= 1 under H0 by symmetry.
   Family: mean of per-draw e (valid under any dependence between draws sharing the null bag).
   Across tasks: per-task e_t with s = |y_r(t) - mean_bag y(t)|, averaged over t (valid under any dependence).
   Across models: product of family e-values (assumes the model-level experiments are independent); an e-value
   product can be extended as q30a3/q32 arrive without re-planning (optional continuation).
4. Pooled across models: stratified permutation (labels permuted within model), statistic = mean over models of the
   per-model signed net difference (Monte Carlo, B draws, p = (1 + #)/(B + 1)).
5. Equivalence (non-rejection is NOT equivalence): permutation confidence set for a location shift delta of the
   run-level success rate (Lehmann inversion: C rates - delta exchangeable with null rates). TOST at eps: reject
   delta <= -eps and delta >= +eps, each one-sided at 5% (= 90% set inside (-eps, eps)). eps_min = smallest eps on
   the grid for which this holds; "unattainable" when 1/C(n+m, m) > 0.05. Pooled: common shift across models.
6. Conditional task-wise permutation (labels permuted independently per task): valid only if tasks are independent
   within a run given the draw, i.e. no draw-level effect beyond Bernoulli noise (checked in p01 null_width_A).
   Reported to show how much power the draw-level exact test gives up.
7. Power of the exact one-sided draw-level test (Gaussian run-rate model, sigma = observed null-draw SD).
Also: conformal null band = [min, max] of null draw rates, coverage (n-1)/(n+1) for a new null draw.
Usage: python c01_conformal_equivalence.py  -> out/c01_conformal_equivalence.json
"""
import json
import os
import re
from collections import defaultdict
from itertools import combinations
from math import comb

import numpy as np

from common import OUT, ROOT, RUNS, dump, fam, now, outcomes, outcomes_both, runs_for, DOMS, INFRA

SEED = 20260929
rng = np.random.default_rng(SEED)
NTASK = 85
MINCOV = 0.9
MODELS = [m for m in os.environ.get("CLOQ_MODELS", "q4,q8,q14,q30a3,q32").split(",")]
NULLSETS = {"A": {"null:bf16", "null:eager", "null:nonce"},
            "S": {"null:bf16", "null:eager", "null:nonce"},    # prompt-stratum matched, see analyse()
            "B": {"null:bf16", "null:eager", "null:nonce", "gauss0.03"}}
POOL = os.environ.get("CLOQ_POOL", "q4,q8,q14").split(",")
FREE = ("gauss0.03", "gauss0.1", "rtn_w8")
GRID = np.round(np.arange(-0.40, 0.4001, 0.0025), 4)
EPS = (0.05, 0.075)
B_MC = 20000


def snapshot(models):
    """Which runs exist, their coverage and file mtimes, and which *_redo / running tasks may replace them."""
    q = "/data/ziyangs/cloq_work/queue"
    snap = {"utc": now(), "runs": {}, "redo_tasks": {}, "running_tasks": sorted(os.listdir(f"{q}/running"))}
    for d in ("todo", "running", "done"):
        snap["redo_tasks"][d] = sorted(f for f in os.listdir(f"{q}/{d}") if "redo" in f)
    for m in models:
        for r in runs_for(m):
            n = {}; mt = 0; infra = 0
            for d in DOMS:
                o = outcomes(r, d, True)
                n[d] = sum(1 for t, (y, tr) in o.items() if tr != INFRA)
                infra += sum(1 for t, (y, tr) in o.items() if tr == INFRA)
                for f in ("metrics.json", "tau2_results.json"):
                    p = RUNS / r / d / f
                    if p.exists():
                        mt = max(mt, p.stat().st_mtime)
            snap["runs"][r] = {"n_scored": sum(n.values()), "n_infra": infra,
                               "source_mtime_utc": __import__("datetime").datetime.fromtimestamp(mt, __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%MZ") if mt else None}
    return snap


_Y = {}


def load(model):
    """loaded once per model per invocation so every null set sees the same snapshot of the live runs"""
    if model in _Y:
        return _Y[model]
    Y = {}
    for r in runs_for(model):
        y = outcomes_both(r)
        if len(y) >= MINCOV * NTASK:
            Y[r] = y
    _Y[model] = Y
    return Y


def matrix(Y, runs):
    K = sorted(set.intersection(*[set(Y[r]) for r in runs]))
    return K, np.array([[Y[r][k] for k in K] for r in runs], float)


def conf_p(scores, c, u):
    """scores over the bag, c = index of the tested run."""
    s = np.asarray(scores); gt = (s > s[c]).sum(); eq = (s == s[c]).sum()
    return float((gt + u * eq) / len(s)), float((gt + eq) / len(s))


def soft_e(scores, c):
    s = np.asarray(scores, float); tot = s.sum()
    return 1.0 if tot <= 0 else float(len(s) * s[c] / tot)


def per_draw(Y, nulls, draw):
    runs = nulls + [draw]
    K, M = matrix(Y, runs)
    n1 = len(runs); c = n1 - 1
    rate = M.mean(1)
    loo = np.array([(M.sum(0) - M[i]) / (n1 - 1) for i in range(n1)])  # mean of bag\r per task
    s_net = np.abs(rate - rate.mean())
    s_harm = np.maximum(0, loo.mean(1) - rate)
    s_churn = np.abs(M - loo).mean(1)
    u = rng.uniform()
    out = {"n_null": len(nulls), "n_tasks": len(K), "rate": round(float(rate[c]), 4),
           "null_rates": [round(float(x), 4) for x in rate[:-1]], "p_min": round(1 / n1, 4), "U": round(u, 4)}
    for name, s in (("net", s_net), ("harm", s_harm), ("churn", s_churn)):
        pr, pc = conf_p(s, c, u)
        out[f"p_{name}"] = round(pr, 4); out[f"p_{name}_cons"] = round(pc, 4); out[f"e_{name}"] = round(soft_e(s, c), 4)
    # per-task e-values averaged over tasks
    dev = np.abs(M - M.mean(0))
    tot = dev.sum(0)
    et = np.where(tot > 0, n1 * dev[c] / np.where(tot > 0, tot, 1), 1.0)
    out["e_task_avg"] = round(float(et.mean()), 4)
    out["n_tasks_draw_disagrees_with_unanimous_null"] = int(((M[:-1].min(0) == M[:-1].max(0)) & (M[c] != M[0])).sum())
    return out


def fam_perm(M, m, u):
    """M: rows = runs, first m rows are the family draws. Exact enumeration over C(R, m)."""
    R = M.shape[0]
    tot = M.sum(0)
    stats = []
    for S in combinations(range(R), m):
        yc = M[list(S)].mean(0); yn = (tot - M[list(S)].sum(0)) / (R - m)
        d = yc - yn
        stats.append((d.mean(), np.abs(d).mean()))
    stats = np.array(stats)
    obs = stats[0]  # combinations() yields (0..m-1) first = the true labelling
    res = {"n_perm": len(stats), "p_min": round(1 / len(stats), 4)}
    for name, v, o in (("net", np.abs(stats[:, 0]), abs(obs[0])), ("harm", -stats[:, 0], -obs[0]), ("churn", stats[:, 1], obs[1])):
        gt = (v > o + 1e-12).sum(); eq = (np.abs(v - o) <= 1e-12).sum()
        res[f"p_{name}"] = round(float((gt + u * eq) / len(v)), 4)
        res[f"p_{name}_cons"] = round(float((gt + eq) / len(v)), 4)
    res["delta_obs"] = round(float(obs[0]), 4); res["churn_obs"] = round(float(obs[1]), 4)
    res["churn_null_median"] = round(float(np.median(stats[:, 1])), 4)
    return res


def shift_pvals(rates, m, grid=GRID):
    """Lehmann inversion on run-level rates; rates[:m] = family. Returns p_hi (H: shift <= delta), p_lo (>= delta)."""
    R = len(rates)
    combos = [list(S) for S in combinations(range(R), m)]
    I = np.zeros((len(combos), R), bool)
    for j, S in enumerate(combos):
        I[j, S] = True
    phi, plo = [], []
    for dl in grid:
        r = rates.copy(); r[:m] -= dl
        d = (I * r).sum(1) / m - (~I * r).sum(1) / (R - m)
        o = d[0]
        phi.append(float((d >= o - 1e-12).mean())); plo.append(float((d <= o + 1e-12).mean()))
    return np.array(phi), np.array(plo)


def equiv_from_p(phi, plo, grid=GRID, a=0.05):
    ok = (phi > a) & (plo > a)
    res = {"ci90": [float(grid[ok].min()), float(grid[ok].max())] if ok.any() else None}
    if res["ci90"] and (res["ci90"][0] <= grid[0] or res["ci90"][1] >= grid[-1]):
        res["ci90"] = None
    eq = {}
    for e in list(EPS):
        lo = np.argmin(np.abs(grid + e)); hi = np.argmin(np.abs(grid - e))
        eq[f"{e*100:g}pp"] = bool(phi[lo] <= a and plo[hi] <= a)
    res["tost"] = eq
    em = None
    for j, e in enumerate(grid[grid > 0]):
        lo = np.argmin(np.abs(grid + e)); hi = np.argmin(np.abs(grid - e))
        if phi[lo] <= a and plo[hi] <= a:
            em = float(e); break
    res["eps_min"] = em
    return res


def taskwise(M, m, B=B_MC):
    R, K = M.shape
    obs = M[:m].mean(0).mean() - M[m:].mean(0).mean()
    cnt = 0
    for _ in range(B // 2000):
        ranks = rng.random((2000, R, K)).argsort(1).argsort(1) < m  # True = assigned to family, per task
        yc = (ranks * M).sum(1) / m; yn = (~ranks * M).sum(1) / (R - m)
        d = (yc - yn).mean(1)
        cnt += (np.abs(d) >= abs(obs) - 1e-12).sum()
    return {"delta_obs": round(float(obs), 4), "p_net": round(float((1 + cnt) / (B + 1)), 5), "B": B}


def power(n, m, sigma, deltas=(-0.03, -0.05, -0.10, -0.15), sims=4000, a=0.05):
    R = n + m
    combos = [list(S) for S in combinations(range(R), m)]
    I = np.zeros((len(combos), R), bool)
    for j, S in enumerate(combos):
        I[j, S] = True
    out = {}
    for dl in deltas:
        x = rng.normal(0, sigma, (sims, R)); x[:, :m] += dl
        d = (x @ I.T) / m - (x @ (~I).T) / (R - m)          # sims x combos
        o = d[:, :1]
        gt = (-d > -o + 1e-12).sum(1); eq = (np.abs(d - o) <= 1e-12).sum(1)
        p = (gt + rng.uniform(size=sims) * eq) / len(combos)
        out[f"{dl*100:g}pp"] = round(float((p <= a).mean()), 3)
    return out


def analyse(model, Y, nullset, p01=None):
    nulls = sorted(r for r in Y if fam(r, model) in NULLSETS[nullset])
    if len(nulls) < 2:
        return None
    fams = defaultdict(list)
    for r in Y:
        f = fam(r, model)
        if f not in NULLSETS[nullset] and not f.startswith("null:"):
            fams[f].append(r)
    fz = [r for f in FREE if f not in NULLSETS[nullset] for r in fams.get(f, [])]
    if fz:
        fams["free_zone"] = fz
    K, MN = matrix(Y, nulls)
    null_rates = MN.mean(1)
    sd = float(null_rates.std(ddof=1))
    res = {"null_draws": nulls, "n_null": len(nulls), "null_rates_common_tasks": [round(float(x), 4) for x in null_rates],
           "null_sd": round(sd, 4), "null_band": [round(float(null_rates.min()), 4), round(float(null_rates.max()), 4)],
           "null_band_coverage": f"{len(nulls)-1}/{len(nulls)+1}", "families": {}}
    all_nulls = nulls
    for f, rs in sorted(fams.items()):
        rs = sorted(rs)
        m = len(rs)
        nulls = all_nulls
        if nullset == "S":
            hits = [re.search(r"_(n\d+)$", r) for r in rs]
            nonces = {x.group(1) for x in hits if x}
            if all(hits):      # nonce-prompt family: nonce nulls with other nonces
                nulls = [r for r in all_nulls if "_null_n" in r and not any(r.endswith(f"_null_{n}") for n in nonces)]
            elif not nonces:                            # canonical-prompt family: canonical-prompt nulls
                nulls = [r for r in all_nulls if "_null_n" not in r]
            else:
                continue
            if len(nulls) < 2:
                continue
        K, M = matrix(Y, rs + nulls)
        if len(K) < 40:
            continue
        u = rng.uniform()
        rates = M.mean(1)
        e = {"draws": rs, "m": m, "nulls_used": nulls, "n_tasks": len(K), "U": round(u, 4),
             "delta": round(float(rates[:m].mean() - rates[m:].mean()), 4),
             "per_draw": {r: per_draw(Y, nulls, r) for r in rs},
             "perm": fam_perm(M, m, u)}
        pd = e["per_draw"].values()
        e["e_family"] = {k: round(float(np.mean([x[f"e_{k}"] for x in pd])), 4) for k in ("net", "harm", "churn")}
        e["e_family"]["task_avg"] = round(float(np.mean([x["e_task_avg"] for x in pd])), 4)
        phi, plo = shift_pvals(rates, m)
        e["equiv"] = equiv_from_p(phi, plo)
        e["equiv"]["attainable"] = bool(1 / comb(len(rates), m) <= 0.05)
        e["taskwise_conditional"] = taskwise(M, m)
        e["power_exact_harm_test"] = power(len(nulls), m, sd)
        if p01 and nullset == "A":
            x = (((p01.get(model) or {}).get("clean") or {}).get("nullsets", {}).get("A", {}).get("families", {}).get(f))
            if x:
                e["p01_tost"] = {"delta": x["delta"], "ci90": x["ci90"], "verdict_5pp": x["verdicts"]["5pp"],
                                 "verdict_7.5pp": x["verdicts"]["7.5pp"], "m80_tost": x["m80_tost"]}
        res["families"][f] = e
        e["_rates"] = rates; e["_m"] = m; e["_M"] = M
    return res


def holm(ps):
    k = sorted(ps, key=ps.get); n = len(k); out = {}; run = 0.0
    for i, f in enumerate(k):
        run = max(run, min(1.0, (n - i) * ps[f])); out[f] = round(run, 5)
    return out


def pooled(per_model, fams, models):
    """stratified permutation across models (MC), common-shift equivalence, e-value product."""
    out = {}
    for f in fams:
        parts = {q: r["families"][f] for q, r in per_model.items() if r and q in models and f in r["families"]}
        if len(parts) < 2:
            continue
        # MC stratified permutation on signed net Δ (mean over models)
        obs = np.mean([p["delta"] for p in parts.values()])
        sims = np.zeros(B_MC)
        for q, p in parts.items():
            rates, m = p["_rates"], p["_m"]
            R = len(rates)
            perm = np.argsort(rng.random((B_MC, R)), 1)
            sims += (rates[perm[:, :m]].mean(1) - rates[perm[:, m:]].mean(1)) / len(parts)
        p_net = (1 + (np.abs(sims) >= abs(obs) - 1e-12).sum()) / (B_MC + 1)
        # stratified churn: mean over models of mean_t |ybar_C(t) - ybar_N(t)|
        csim = np.zeros(4000); cobs = 0.0
        for q, p in parts.items():
            M, m = p["_M"], p["_m"]; R = M.shape[0]
            perm = np.argsort(rng.random((4000, R)), 1)
            yc = M[perm[:, :m]].mean(1); yn = M[perm[:, m:]].mean(1)
            csim += np.abs(yc - yn).mean(1) / len(parts)
            cobs += np.abs(M[:m].mean(0) - M[m:].mean(0)).mean() / len(parts)
        p_churn = (1 + (csim >= cobs - 1e-12).sum()) / 4001
        p_harm = (1 + (-sims >= -obs - 1e-12).sum()) / (B_MC + 1)
        # common shift: MC distribution per delta
        phi, plo = [], []
        perms = {q: np.argsort(rng.random((4000, len(p["_rates"]))), 1) for q, p in parts.items()}
        for dl in GRID:
            s = np.zeros(4000); o = 0.0
            for q, p in parts.items():
                r = p["_rates"].copy(); m = p["_m"]; r[:m] -= dl
                pm = perms[q]
                s += (r[pm[:, :m]].mean(1) - r[pm[:, m:]].mean(1)) / len(parts)
                o += (r[:m].mean() - r[m:].mean()) / len(parts)
            phi.append((1 + (s >= o - 1e-12).sum()) / 4001); plo.append((1 + (s <= o + 1e-12).sum()) / 4001)
        eqv = equiv_from_p(np.array(phi), np.array(plo))
        prod = {k: round(float(np.prod([p["e_family"][k] for p in parts.values()])), 4) for k in ("net", "harm", "churn", "task_avg")}
        out[f] = {"models": sorted(parts), "delta_mean_over_models": round(float(obs), 4),
                  "p_net_stratified_mc": round(float(p_net), 5), "p_harm_stratified_mc": round(float(p_harm), 5),
                  "churn_obs": round(float(cobs), 4), "p_churn_stratified_mc": round(float(p_churn), 5),
                  "p_min_exact": float(1 / np.prod([p["perm"]["n_perm"] for p in parts.values()])),
                  "equiv_common_shift": eqv, "e_product": prod}
    return out


def main():
    p01 = json.load(open(OUT / "p01_equivalence.json"))
    for q in MODELS:
        load(q)
    res = {"snapshot": snapshot(MODELS), "runs_used_n_tasks": {r: len(y) for q in MODELS for r, y in _Y[q].items()},
           "seed": SEED, "mincov": MINCOV, "B_mc": B_MC,
           "p01_snapshot_utc": p01.get("snapshot_utc"), "nullsets": {},
           "note_S": ("S = prompt-stratum matched null: canonical-prompt families (gauss*) vs canonical-prompt nulls "
                      "(bf16, bf16_eager); nonce-prompt families (quantised, run with nonces n1/n2...) vs nonce nulls "
                      "whose nonce is not used by the family. A pools both strata (as p01); B = A + gauss0.03.")}
    for ns in NULLSETS:
        per = {}
        for q in MODELS:
            Y = load(q)
            if Y:
                per[q] = analyse(q, Y, ns, p01["models"] if ns == "A" else None)
        allf = sorted({f for r in per.values() if r for f in r["families"]})
        pl = pooled(per, allf, POOL)
        fams_h = [f for f in pl if f != "free_zone"]
        for key in ("p_harm_stratified_mc", "p_net_stratified_mc", "p_churn_stratified_mc"):
            h = holm({f: pl[f][key] for f in fams_h})
            for f in fams_h:
                pl[f][key + "_holm"] = h[f]
        pl_all = pooled(per, allf, list(per))
        for r in per.values():
            if r:
                for e in r["families"].values():
                    e.pop("_rates"); e.pop("_m"); e.pop("_M")
        res["nullsets"][ns] = {"members": sorted(NULLSETS[ns]), "models": per, "pooled_models": POOL, "pooled": pl,
                               "pooled_all_available": {f: {k: v for k, v in x.items()} for f, x in pl_all.items()}}
        print(f"== null set {ns}")
        for q, r in per.items():
            if not r:
                continue
            print(q, "nulls", r["n_null"], "sd", r["null_sd"], "band", r["null_band"])
            for f, e in r["families"].items():
                pr = e["perm"]
                print(f"  {f:10s} m={e['m']} K={e['n_tasks']} Δ={e['delta']:+.3f} perm p_net={pr['p_net']:.3f} "
                      f"p_harm={pr['p_harm']:.3f} p_churn={pr['p_churn']:.3f} (min {pr['p_min']:.3f}) "
                      f"e={e['e_family']} eq={e['equiv']['tost']} epsmin={e['equiv']['eps_min']} "
                      f"taskwise p={e['taskwise_conditional']['p_net']} pow={e['power_exact_harm_test']} "
                      f"p01={e.get('p01_tost', {}).get('verdict_5pp')}")
        for f, x in pl.items():
            print(f"  POOLED {f:10s} {x['models']} Δ={x['delta_mean_over_models']:+.3f} p_net={x['p_net_stratified_mc']} "
                  f"p_harm={x['p_harm_stratified_mc']} holm={x.get('p_harm_stratified_mc_holm')} churn={x['churn_obs']} p_churn={x['p_churn_stratified_mc']} holm={x.get('p_churn_stratified_mc_holm')} eq={x['equiv_common_shift']} e={x['e_product']}")
    dump("c01_conformal_equivalence.json", res)


if __name__ == "__main__":
    main()
