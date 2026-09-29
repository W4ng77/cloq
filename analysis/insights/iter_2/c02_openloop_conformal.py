"""Open-loop -> closed-loop conformal prediction (iter-2, conformal request, part 2). Re-runnable: picks up every model
that has E3 open-loop cells in analysis/openloop/a6k2/<m>/*.json (q4, q8 at the time of writing; q14/q30a3/q32 when
their `*_ol_*` tasks finish).

Unit = one E3 cell (a checkpoint served in open loop on the BF16 reference contexts, scripts/a6000/openloop_d.py).
Features (cell json): decision_any_flip, flip_rate, first_token_flip_rate, flip | bf16 margin in [0,0.25) / [0.25,0.5).
Targets (closed loop, the cell's own runs; gauss*_sN -> that run; awq_w4 / gptq_w4_dK / rtn_wB -> all nonce draws):
  hazard  = per-decision first-divergence hazard vs the run's reference (p02_ties.pair, pooled events / at-risk over
            the cell's runs; infrastructure_error tasks dropped);
  delta   = success rate - task-level null mean (null set A, leave-one-out for null members), mean over the cell's
            eligible runs (>= 90% task coverage).
Predictors: H0 identity  h_hat = decision_any_flip (zero parameters: an open-loop flip probability read as the
            closed-loop hazard); H1 logit-linear  logit h = a + b logit(decision_any_flip);
            D1 linear  delta = a + b log10(flip_rate).
Conformal: (i) pooled jackknife+ over cells (leave-one-cell-out), (ii) leave-one-model-out split conformal:
  fit + calibrate (CV+ residuals) on the other models, predict every cell of the held-out model; report the
  empirical coverage at 80% / 90%. Guarantees need exchangeable cells; cells are design points (a dose grid) and
  models differ, so the coverage reported is empirical, not guaranteed. Hazard intervals are built on the logit scale.
Usage: python c02_openloop_conformal.py -> out/c02_openloop_conformal.json
"""
import json
import re
from collections import defaultdict

import numpy as np

from common import ROOT, dump, exists_frozen, fam, infra_tasks, load_many, now, outcomes_both, ref_for, runs_for
from p02_ties import pair

OL = ROOT / "analysis/openloop/a6k2"
NT = 85
ALPHAS = (0.2, 0.1)
NULL_A = {"null:bf16", "null:eager", "null:nonce"}


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def expit(x):
    return 1 / (1 + np.exp(-x))


def runs_of_cell(model, stem, runs):
    if stem == "bf16_eager":
        return [r for r in runs if r == f"a6k2_{model}_bf16_eager"]
    pat = re.compile(rf"^a6k2_{model}_{re.escape(stem)}(_n\d+)?$")
    return [r for r in runs if pat.match(r)]


def closed_loop(model):
    runs = runs_for(model)
    Y = {r: outcomes_both(r) for r in runs}
    nulls = [r for r in runs if fam(r, model) in NULL_A and len(Y[r]) >= 0.9 * NT]
    cells = {}
    for f in sorted(OL.joinpath(model).glob("*.json")):
        stem = f.stem
        if stem == "bf16":
            continue
        rs = runs_of_cell(model, stem, runs)
        if not rs:
            continue
        cells[stem] = {"ol": json.load(open(f)), "runs": rs}
    need = sorted({r for c in cells.values() for r in c["runs"]} |
                  {ref_for(model, r, runs)[0] for c in cells.values() for r in c["runs"]})
    D = load_many([r for r in need if exists_frozen(r)])
    out = {}
    for stem, c in cells.items():
        ev = risk = 0; used = []
        deltas = []
        for r in c["runs"]:
            rr, key = ref_for(model, r, runs)
            if D.get(r) and D.get(rr):
                o, _, _ = pair(D[rr], D[r], key, infra_tasks(r) | infra_tasks(rr))
                if o["n_tasks"] >= 40 and o["decisions_at_risk"]:
                    ev += o["events"]; risk += o["decisions_at_risk"]; used.append(r)
            if len(Y[r]) >= 0.9 * NT:
                ns = [x for x in nulls if x != r]
                d = [Y[r][k] - np.mean([Y[x][k] for x in ns if k in Y[x]]) for k in Y[r]
                     if sum(1 for x in ns if k in Y[x]) >= 2]
                deltas.append(float(np.mean(d)))
        ol = c["ol"]
        fb = ol.get("flip_by_bf16_margin", {})
        out[stem] = {"runs": c["runs"], "hazard_runs": used,
                     # continuity-corrected (ev + 0.5) / (risk + 1) so saturated cells (rtn_w3: 136/136) stay finite on logit
                     "hazard": (ev + 0.5) / (risk + 1) if risk else None, "hazard_raw": ev / risk if risk else None,
                     "events": ev, "at_risk": risk,
                     "delta": float(np.mean(deltas)) if deltas else None, "n_delta_runs": len(deltas),
                     "x": {"decision_any_flip": (ol["decision_any_flip"] * ol["n_decisions"] + 0.5) / (ol["n_decisions"] + 1), "flip_rate": ol["flip_rate"],
                           "first_token_flip_rate": ol.get("first_token_flip_rate"),
                           "flip_m<0.25": (fb.get("[0,0.25)") or {}).get("flip"),
                           "flip_m0.25-0.5": (fb.get("[0.25,0.5)") or {}).get("flip")}}
    return out


def fit_h1(x, y):
    A = np.c_[np.ones(len(x)), logit(x)]
    return np.linalg.lstsq(A, y, rcond=None)[0]  # y already on the logit scale


def pred_h1(b, x):
    return b[0] + b[1] * logit(x)


def fit_d1(x, y):
    A = np.c_[np.ones(len(x)), np.log10(np.maximum(x, 1e-6))]
    return np.linalg.lstsq(A, y, rcond=None)[0]


def pred_d1(b, x):
    return b[0] + b[1] * np.log10(np.maximum(x, 1e-6))


def q_conf(r, a):
    """split-conformal quantile: ceil((1-a)(n+1))-th smallest; inf if not enough points."""
    n = len(r); k = int(np.ceil((1 - a) * (n + 1)))
    return float(np.sort(r)[k - 1]) if k <= n else float("inf")


def jackknife_plus(x, y, fit, pred, a):
    """Barber et al. 2021 jackknife+; returns per-point [lo, hi] for each held-out i (LOO coverage estimate)."""
    n = len(x); out = []
    for i in range(n):
        idx = [j for j in range(n) if j != i]
        los, his = [], []
        for j in idx:
            tr = [k for k in idx if k != j]
            b = fit(x[tr], y[tr])
            rj = abs(y[j] - pred(b, x[j:j + 1])[0])
            mi = pred(b, x[i:i + 1])[0]
            los.append(mi - rj); his.append(mi + rj)
        n1 = len(los); k = int(np.ceil((1 - a) * (n1 + 1)))
        lo = np.sort(los)[n1 - k] if k <= n1 else -np.inf
        hi = np.sort(his)[k - 1] if k <= len(his) else np.inf
        out.append((float(lo), float(hi)))
    return out


def main():
    models = sorted(p.name for p in OL.iterdir() if p.is_dir() and any(p.glob("*.json")))
    res = {"snapshot_utc": now(), "models": models, "cells": {}, "identity": {}, "jackknife_plus": {}, "lomo": {}}
    rows = []
    for m in models:
        cl = closed_loop(m)
        res["cells"][m] = cl
        for stem, c in cl.items():
            rows.append((m, stem, c))
    # --- targets
    tasks = {"hazard": ("decision_any_flip", "logit"), "delta": ("flip_rate", "raw")}
    for tgt, (feat, scale) in tasks.items():
        R = [(m, s, c["x"][feat], c[tgt]) for m, s, c in rows if c[tgt] is not None and c["x"][feat] is not None]
        if len(R) < 6:
            continue
        mods = np.array([r[0] for r in R]); x = np.array([r[2] for r in R], float); y = np.array([r[3] for r in R], float)
        fit, pred = (fit_h1, pred_h1) if tgt == "hazard" else (fit_d1, pred_d1)
        yt = logit(y) if scale == "logit" else y
        back = expit if scale == "logit" else (lambda v: v)
        # identity predictor (hazard only): residual on the logit scale, no fitting
        if tgt == "hazard":
            r_id = np.abs(yt - logit(x))
            ident = {"n_cells": len(R), "median_abs_logit_resid": round(float(np.median(r_id)), 3),
                     "mean_signed_logit_resid(obs-pred)": round(float(np.mean(yt - logit(x))), 3),
                     "spearman": round(float(__import__("scipy.stats", fromlist=["spearmanr"]).spearmanr(x, y)[0]), 3)}
            for a in ALPHAS:
                cov = []
                for mo in sorted(set(mods)):
                    cal = r_id[mods != mo]; te = mods == mo
                    if len(cal) < 3:
                        continue
                    qh = q_conf(cal, a)
                    cov.append((mo, int(te.sum()), float((r_id[te] <= qh).mean()), round(qh, 3)))
                ident[f"lomo_split_{int((1-a)*100)}"] = [{"held_out": c[0], "n": c[1], "coverage": round(c[2], 3), "q_logit": c[3]} for c in cov]
            res["identity"][tgt] = ident
        # pooled jackknife+
        jk = {}
        for a in ALPHAS:
            iv = jackknife_plus(x, y, fit, pred, a) if tgt == "delta" else \
                [(lo, hi) for lo, hi in jackknife_plus(x, yt, fit, pred, a)]
            inside = [lo <= yt[i] <= hi for i, (lo, hi) in enumerate(iv)]
            width = [back(hi) - back(lo) for lo, hi in iv if np.isfinite(lo) and np.isfinite(hi)]
            jk[f"{int((1-a)*100)}"] = {"coverage_loo": round(float(np.mean(inside)), 3), "n": len(iv),
                                       "median_width": round(float(np.median(width)), 4) if width else None}
        b = fit(x, yt)
        jk["fit_all"] = [round(float(v), 4) for v in b]
        jk["resid_sd"] = round(float(np.std(yt - pred(b, x), ddof=2)), 4)
        jk["y_sd"] = round(float(np.std(yt, ddof=1)), 4)
        res["jackknife_plus"][tgt] = jk
        # leave-one-model-out: fit on other models, calibrate with CV+ (leave-one-cell-out residuals within them)
        lomo = {}
        for mo in sorted(set(mods)):
            tr = np.where(mods != mo)[0]; te = np.where(mods == mo)[0]
            if len(tr) < 5:
                continue
            b = fit(x[tr], yt[tr])
            cvr = []
            for j in tr:
                bj = fit(x[[k for k in tr if k != j]], yt[[k for k in tr if k != j]])
                cvr.append(abs(yt[j] - pred(bj, x[j:j + 1])[0]))
            cvr = np.array(cvr)
            e = {"n_train": int(len(tr)), "n_test": int(len(te)), "fit": [round(float(v), 4) for v in b]}
            for a in ALPHAS:
                qh = q_conf(cvr, a)
                p = pred(b, x[te])
                inside = np.abs(yt[te] - p) <= qh
                e[f"{int((1-a)*100)}"] = {"coverage": round(float(inside.mean()), 3), "q": round(qh, 4),
                                          "median_width": round(float(np.median(back(p + qh) - back(p - qh))), 4)}
            e["cells"] = {s: {"obs": round(float(y[i]), 4), "pred": round(float(back(pred(b, x[i:i + 1])[0])), 4)}
                          for i, s in zip(te, [R[i][1] for i in te])}
            lomo[mo] = e
        res["lomo"][tgt] = lomo
        print(tgt, "jackknife+", jk, "\n  lomo", {k: {a: v[a] for a in ("80", "90")} for k, v in lomo.items()},
              "\n  identity", res["identity"].get(tgt))
    dump("c02_openloop_conformal.json", res)


if __name__ == "__main__":
    main()
