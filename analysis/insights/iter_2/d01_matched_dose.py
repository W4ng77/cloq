"""Matched-dose check for C3 (review v2 W-D): is rho(open-loop flip rate, closed-loop hazard) more than "both are
monotone in dose"?

Input: out/c02_openloop_conformal.json (cells = E3 open-loop cells with a closed-loop hazard on the frozen snapshot;
x.flip_rate = open-loop token flip rate, the recommended axis of A2-9; x.decision_any_flip; hazard = continuity-corrected
per-decision first-divergence hazard pooled over the cell's runs).
Dose = relative weight error, in RTN-W4 units (k_eq): gauss k by construction (||N||_F = k ||RTN_W4(W) - W||_F per linear,
cloq/compress.py), checked against quantization.json mean_rel_weight_err where present; RTN-Wb = sqrt(mean_rel_weight_err(Wb) /
mean_rel_weight_err(W4)) of the same model (measured; the stored error is a squared-norm ratio, checked on gauss cells); GPTQ/AWQ record no weight error, so they get the bit-matched RTN
k_eq ("nominal"; excluded in the sensitivity 'measured-dose cells only'). bf16_eager has no weight dose and is excluded.
Statistics:
  1. Spearman(flip, hazard), Spearman(dose, hazard), Spearman(dose, flip) over all dosed cells;
  2. partial Spearman(flip, hazard | log dose) (rank partial correlation), and the same with ranks taken within model
     (removes model offsets); 95% CI by cell bootstrap stratified by model (B = 4000);
  3. OLS logit(hazard) ~ logit(flip) + log10(dose) + model FE: flip coefficient with bootstrap CI and the R^2 gained by
     adding flip to dose + model;
  4. matched-dose strata (same model, k_eq within x1.25): flip rate and hazard of every cell, and the within-stratum rank
     correlation pooled over strata (ranks centred within stratum; one-sided permutation within strata), for all
     strata with >= 3 cells and for cross-family strata only.
Usage: CLOQ_SNAPSHOT=out/snapshot_<utc>.json python d01_matched_dose.py -> out/d01_matched_dose.json
"""
import json
import re
from collections import defaultdict

import numpy as np
from scipy.stats import rankdata, spearmanr

from common import OUT, RUNS, dump, now

rng = np.random.default_rng(20260929)


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def rel_err(run):
    p = RUNS / run / "quantization.json"
    if p.exists():
        return json.load(open(p)).get("mean_rel_weight_err")
    return None


def dose_table(model, cells):
    w4 = rel_err(f"a6k2_{model}_rtn_w4_n1")
    rtn = {}
    for b in (8, 4, 3):
        e = rel_err(f"a6k2_{model}_rtn_w{b}_n1") or rel_err(f"a6k2_{model}_rtn_w{b}_n2")
        # mean_rel_weight_err is a squared-norm ratio (gauss k = 0.1 -> 0.0102 x RTN-W4, k = 0.3 -> 0.090), so the
        # Frobenius-norm dose in RTN-W4 units is its square root
        rtn[b] = (e / w4) ** 0.5 if (e and w4) else {8: None, 4: 1.0, 3: None}[b]
    out = {}
    for stem, c in cells.items():
        m = re.match(r"gauss([\d.]+)_s\d+$", stem)
        if m:
            k = float(m.group(1)); run = c["runs"][0] if c["runs"] else None
            e = rel_err(run) if run else None
            out[stem] = {"family": "gauss", "k_eq": k, "source": "gauss k (by construction)",
                         "check_sqrt_rel_err_ratio": round((e / w4) ** 0.5, 4) if (e and w4) else None}
            continue
        m = re.match(r"(rtn|gptq|awq)_w(\d)", stem)
        if m:
            b = int(m.group(2)); kind = m.group(1)
            if b in rtn and rtn[b]:
                out[stem] = {"family": kind, "k_eq": rtn[b], "bits": b,
                             "source": "measured rel. weight error / RTN-W4" if kind == "rtn" else f"nominal: RTN-W{b} k_eq"}
    return out


def partial_spearman(x, y, z):
    rxy = spearmanr(x, y)[0]; rxz = spearmanr(x, z)[0]; ryz = spearmanr(y, z)[0]
    d = np.sqrt(max(1e-12, (1 - rxz ** 2) * (1 - ryz ** 2)))
    return float((rxy - rxz * ryz) / d)


def within_rank(v, g):
    out = np.zeros(len(v))
    for s in set(g):
        i = np.array([j for j in range(len(v)) if g[j] == s])
        out[i] = (rankdata(v[i]) - (len(i) + 1) / 2) / max(1, len(i))
    return out


def partial_within(x, y, z, g):
    """rank-partial correlation with ranks centred within model."""
    rx, ry, rz = within_rank(x, g), within_rank(y, g), within_rank(z, g)
    def res(a, b):
        A = np.c_[np.ones(len(b)), b]
        return a - A @ np.linalg.lstsq(A, a, rcond=None)[0]
    ex, ey = res(rx, rz), res(ry, rz)
    return float(np.corrcoef(ex, ey)[0, 1])


def ols_r2(X, y):
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    r = y - X @ beta
    return beta, 1 - (r @ r) / ((y - y.mean()) @ (y - y.mean()))


def design(fl, ds, g, with_flip=True):
    mods = sorted(set(g))
    cols = [np.ones(len(fl)), np.log10(ds)] + [np.array([1.0 if x == m else 0.0 for x in g]) for m in mods[1:]]
    if with_flip:
        cols.insert(1, logit(fl))
    return np.c_[tuple(cols)]


def analyse(rows, label):
    g = [r["model"] for r in rows]
    fl = np.array([r["flip_rate"] for r in rows]); hz = np.array([r["hazard"] for r in rows])
    ds = np.array([r["k_eq"] for r in rows])
    out = {"label": label, "n_cells": len(rows), "models": sorted(set(g)),
           "spearman_flip_hazard": round(float(spearmanr(fl, hz)[0]), 3),
           "spearman_dose_hazard": round(float(spearmanr(ds, hz)[0]), 3),
           "spearman_dose_flip": round(float(spearmanr(ds, fl)[0]), 3),
           "partial_spearman_flip_hazard_given_dose": round(partial_spearman(fl, hz, np.log10(ds)), 3),
           "partial_within_model": round(partial_within(fl, hz, np.log10(ds), g), 3)}
    yb = logit(hz)
    b1, r2_full = ols_r2(design(fl, ds, g, True), yb)
    b0, r2_dose = ols_r2(design(fl, ds, g, False), yb)
    out["ols_flip_coef"] = round(float(b1[1]), 3); out["r2_dose_model"] = round(float(r2_dose), 3)
    out["r2_dose_model_flip"] = round(float(r2_full), 3); out["delta_r2_flip"] = round(float(r2_full - r2_dose), 3)
    # stratified cell bootstrap
    idx_by = defaultdict(list)
    for i, m in enumerate(g):
        idx_by[m].append(i)
    ps, pw, co, dr = [], [], [], []
    for _ in range(4000):
        I = np.concatenate([rng.choice(v, len(v)) for v in idx_by.values()])
        if len(set(ds[I])) < 3 or len(set(fl[I])) < 3:
            continue
        try:
            ps.append(partial_spearman(fl[I], hz[I], np.log10(ds[I])))
            pw.append(partial_within(fl[I], hz[I], np.log10(ds[I]), [g[i] for i in I]))
            gi = [g[i] for i in I]
            b1b, r2f = ols_r2(design(fl[I], ds[I], gi, True), yb[I]); _, r2d = ols_r2(design(fl[I], ds[I], gi, False), yb[I])
            co.append(b1b[1]); dr.append(r2f - r2d)
        except Exception:
            continue
    q = lambda a: [round(float(np.nanpercentile(a, 2.5)), 3), round(float(np.nanpercentile(a, 97.5)), 3)] if a else None
    out["ci95"] = {"partial_spearman": q(ps), "partial_within_model": q(pw), "ols_flip_coef": q(co), "delta_r2_flip": q(dr),
                   "B_effective": len(ps)}
    return out


def main():
    c02 = json.load(open(OUT / "c02_openloop_conformal.json"))
    rows = []
    doses = {}
    for model, cells in c02["cells"].items():
        dt = dose_table(model, cells)
        doses[model] = dt
        for stem, c in cells.items():
            if stem not in dt or c.get("hazard") is None or c["x"].get("flip_rate") is None:
                continue
            rows.append({"model": model, "cell": stem, "family": dt[stem]["family"], "k_eq": dt[stem]["k_eq"],
                         "dose_source": dt[stem]["source"], "flip_rate": c["x"]["flip_rate"],
                         "decision_any_flip": c["x"]["decision_any_flip"], "hazard": c["hazard"],
                         "events": c["events"], "at_risk": c["at_risk"]})
    res = {"snapshot_utc": now(), "c02_snapshot_utc": c02.get("snapshot_utc"),
           "c02_frozen_snapshot": c02.get("_frozen_snapshot"), "dose": doses, "cells": rows}
    res["all_dosed"] = analyse(rows, "all dosed cells (gauss + RTN measured, GPTQ/AWQ nominal)")
    res["measured_dose_only"] = analyse([r for r in rows if not r["dose_source"].startswith("nominal")],
                                        "gauss + RTN only (measured dose)")
    res["gauss_only"] = analyse([r for r in rows if r["family"] == "gauss"], "gauss only (dose exact)")
    # matched-dose strata: same model, same nominal k_eq (within x1.25). Two readings:
    #   exact-dose strata with >= 3 cells (gauss seeds at one k, and the W4 band of gauss1/RTN/GPTQ/AWQ);
    #   cross-family strata only (the structure-vs-size question).
    bands = []
    for model in sorted({r["model"] for r in rows}):
        cs_m = sorted([r for r in rows if r["model"] == model], key=lambda r: r["k_eq"])
        used = set()
        for r in cs_m:
            if r["cell"] in used:
                continue
            grp = [c for c in cs_m if c["cell"] not in used and r["k_eq"] <= c["k_eq"] <= 1.25 * r["k_eq"]]
            used |= {c["cell"] for c in grp}
            if len(grp) >= 2:
                bands.append({"model": model, "k_eq": round(r["k_eq"], 4), "families": sorted({c["family"] for c in grp}),
                              "cells": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in c.items()
                                         if k in ("cell", "family", "k_eq", "flip_rate", "hazard", "events", "at_risk")} for c in grp]})

    def pooled_within(sel):
        xs, ys, sizes = [], [], []
        for b in sel:
            f = np.array([c["flip_rate"] for c in b["cells"]]); h = np.array([c["hazard"] for c in b["cells"]])
            xs += list(rankdata(f) - rankdata(f).mean()); ys += list(rankdata(h) - rankdata(h).mean()); sizes.append(len(f))
        out = {"n_strata": len(sizes), "n_cells": len(xs), "strata": [(b["model"], b["k_eq"], len(b["cells"])) for b in sel]}
        if len(xs) >= 5:
            xs, ys = np.array(xs), np.array(ys)
            obs = float(np.corrcoef(xs, ys)[0, 1]); out["within_stratum_rank_corr"] = round(obs, 3)
            cnt = 0; P = 4000
            for _ in range(P):
                yy = []; o = 0
                for n in sizes:
                    yy += list(rng.permutation(ys[o:o + n])); o += n
                cnt += np.corrcoef(xs, np.array(yy))[0, 1] >= obs - 1e-12
            out["p_one_sided_perm_within_strata"] = round(float((1 + cnt) / (P + 1)), 4)
        return out

    wb = {"all_exact_dose_strata_ge3": pooled_within([b for b in bands if len(b["cells"]) >= 3]),
          "cross_family_strata_ge3": pooled_within([b for b in bands if len(b["families"]) >= 2 and len(b["cells"]) >= 3])}
    res["within_dose_bands"] = {"bands": bands, "pooled": wb}
    dump("d01_matched_dose.json", res)
    for k in ("all_dosed", "measured_dose_only", "gauss_only"):
        print(k, res[k])
    print("within-band", wb)
    for b in bands:
        print(b["model"], b["k_eq"], [(c["cell"], round(c["flip_rate"], 4), round(c["hazard"], 3)) for c in b["cells"]])


if __name__ == "__main__":
    main()
