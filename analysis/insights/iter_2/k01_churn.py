"""Churn checks (review v2 W-B, Q1/Q2/Q5): is task-profile churn a compression effect, a prompt-stratum artefact,
or a fixed-checkpoint effect?

Churn of a family C against a reference null set N (run-level, complete-case tasks of the bag):
    churn = mean_t |ybar_C(t) - ybar_N(t)|;  exact permutation over all C(n+m, m) relabellings of the bag;
    excess churn = churn_obs - median of the permutation distribution (the part not explained by run-to-run noise);
    95% CI of the excess by task bootstrap (B = 2000; tasks resampled jointly across models, relabelling
    distribution recomputed on every resample; assumes tasks exchangeable, which the run-level p does not).
Strata (docs/insights/NULL_RULE.md NR1-3), always stratum-matched here:
    canonical-prompt families (gauss*, no nonce)      vs K = {bf16, bf16_eager};
    nonce-prompt families (quantised, nonces n1/n2)   vs U minus the family's nonce-mates (e.g. n3..n8);
    fixed-checkpoint control (a6k2_<m>_gauss0.03_s1_q1/_q2, fresh nonces 6d1f0b3e/f07a5c21; included automatically
    once both runs pass the integrity gate) vs U (all nonce nulls) AND vs the same U the quantised families use.
Negative controls: rtn_w8 (fixed checkpoint, tiny dose, nonce stratum); gauss0.03 (canonical stratum; 2-5 seeds =
different checkpoints); the fixed-checkpoint control above (Q1).
Null-vs-null calibration: every pair of nonce nulls as a pseudo-family vs the remaining nonce nulls (excess churn).
Flat-Score-style agreement (Q5): Pearson r between per-task success rates ybar_C(t) and ybar_N(t) (and null vs null).
Pooled over models: stratified permutation (MC, B = 20000) of the mean-over-models churn and net difference.
Multiplicity: Holm across ALL (family x {net, churn}) pooled tests of this script (primary), and per model.

Pre-declared reading (written before this snapshot was analysed): churn of family C "survives" only if
    (a) pooled stratum-matched churn p (Holm-all) <= 0.05, and
    (b) the pooled excess-churn 95% CI lies above 0, and
    (c) the pooled excess exceeds the fixed-checkpoint control's pooled excess (CI lower bound of C > point excess of
        the control) - if the control is not in the snapshot yet, (c) is "pending" and churn is at most "provisional".
Usage: CLOQ_SNAPSHOT=out/snapshot_<utc>.json python k01_churn.py -> out/k01_churn.json
"""
import json
import os
import re
from collections import defaultdict
from itertools import combinations
from math import comb

import numpy as np

from common import CTL_RE, RUNS, SNAP, dump, fam, now, outcomes_both, runs_for

MODELS = os.environ.get("CLOQ_MODELS", "q4,q8,q14,q30a3,q32").split(",")
MIN_TASKS = 77
BOOT = 2000
B_MC = 20000
SEED = 20260929
rng = np.random.default_rng(SEED)
NEG = ("rtn_w8", "gauss0.03", "ctl:gauss0.03_s1")


def nonce_of(run):
    for d in ("retail", "airline"):
        p = RUNS / run / d / "environment.json"
        if p.exists():
            return json.load(open(p)).get("prompt_nonce")
    return None


def family(run, model):
    if CTL_RE.search(run):
        return "ctl:" + CTL_RE.sub("", re.sub(rf"^a6k2_{model}_", "", run))
    return fam(run, model)


def load(model):
    Y, meta = {}, {}
    for r in runs_for(model, ctl=True):
        y = outcomes_both(r)
        if len(y) >= MIN_TASKS:
            Y[r] = y
            meta[r] = {"fam": family(r, model), "nonce": nonce_of(r)}
    return Y, meta


class Bag:
    """family rows first (m), reference rows after; all relabellings enumerated."""

    def __init__(self, Y, fam_runs, ref_runs):
        runs = fam_runs + ref_runs
        self.tasks = sorted(set.intersection(*[set(Y[r]) for r in runs]))
        self.M = np.array([[Y[r][k] for k in self.tasks] for r in runs], float)
        self.m, self.n = len(fam_runs), len(ref_runs)
        R = self.m + self.n
        self.combos = list(combinations(range(R), self.m))
        I = np.zeros((len(self.combos), R), bool)
        for j, S in enumerate(self.combos):
            I[j, list(S)] = True
        yc = (I.astype(float) @ self.M) / self.m
        yn = ((~I).astype(float) @ self.M) / self.n
        self.D = yc - yn                     # relabellings x tasks, signed per-task difference
        self.A = np.abs(self.D)

    def summary(self, u):
        churn = self.A.mean(1); net = self.D.mean(1)
        o_c, o_n = churn[0], net[0]
        gt = (churn > o_c + 1e-12).sum(); eq = (np.abs(churn - o_c) <= 1e-12).sum()
        gtn = (np.abs(net) > abs(o_n) + 1e-12).sum(); eqn = (np.abs(np.abs(net) - abs(o_n)) <= 1e-12).sum()
        yc = self.M[:self.m].mean(0); yn = self.M[self.m:].mean(0)
        r = float(np.corrcoef(yc, yn)[0, 1]) if yc.std() > 0 and yn.std() > 0 else None
        return {"m": self.m, "n_ref": self.n, "n_tasks": len(self.tasks), "n_perm": len(self.combos),
                "p_min": round(1 / len(self.combos), 4),
                "delta": round(float(o_n), 4), "p_net_cons": round(float((gtn + eqn) / len(net)), 4),
                "churn_obs": round(float(o_c), 4), "churn_perm_median": round(float(np.median(churn)), 4),
                "excess_churn": round(float(o_c - np.median(churn)), 4),
                "p_churn_cons": round(float((gt + eq) / len(churn)), 4),
                "p_churn_rand": round(float((gt + u * eq) / len(churn)), 4),
                "flatscore_r_task_rates": round(r, 4) if r is not None else None}


def excess_boot(bags, task_universe, B=BOOT):
    """Joint task bootstrap: resample the task universe once per replicate, apply to every bag (shared tasks)."""
    pos = {t: i for i, t in enumerate(task_universe)}
    T = len(task_universe)
    W = rng.multinomial(T, np.full(T, 1 / T), size=B).astype(float)     # B x T weights
    out = []
    for bag in bags:
        cols = np.array([pos[t] for t in bag.tasks])
        w = W[:, cols]                                                  # B x T_bag
        ws = w.sum(1, keepdims=True); ws[ws == 0] = 1
        ch = (bag.A @ w.T) / ws.T                                       # perms x B
        out.append(ch[0] - np.median(ch, 0))
    return np.mean(out, 0)


def ci(x):
    return [round(float(np.percentile(x, 2.5)), 4), round(float(np.percentile(x, 97.5)), 4)]


def holm(ps):
    k = sorted(ps, key=ps.get); n = len(k); out = {}; run = 0.0
    for i, f in enumerate(k):
        run = max(run, min(1.0, (n - i) * ps[f])); out[f] = round(run, 5)
    return out


def main():
    res = {"snapshot_utc": now(), "seed": SEED, "boot": BOOT, "min_tasks": MIN_TASKS, "models": {},
           "controls_present": {}, "rule": __doc__.split("Pre-declared reading")[1].split("Usage")[0].strip()}
    bags = defaultdict(dict)       # (family, ref_label) -> model -> Bag
    allY = {}
    for model in MODELS:
        Y, meta = load(model)
        if not Y:
            continue
        allY[model] = Y
        K = sorted(r for r in Y if meta[r]["fam"] in ("null:bf16", "null:eager"))
        U = sorted(r for r in Y if meta[r]["fam"] == "null:nonce")
        fams = defaultdict(list)
        for r in Y:
            if not meta[r]["fam"].startswith("null:"):
                fams[meta[r]["fam"]].append(r)
        mres = {"K": K, "U": U, "U_nonces": {r: meta[r]["nonce"] for r in U}, "families": {}, "null_vs_null": None}
        quant_nonces = {meta[r]["nonce"] for f, rs in fams.items() if not f.startswith(("gauss", "ctl:")) for r in rs}
        for f, rs in sorted(fams.items()):
            rs = sorted(rs)
            nonces = {meta[r]["nonce"] for r in rs}
            refs = {}
            if nonces == {None}:
                refs["S_canonical"] = K
            elif None not in nonces:
                refs["S_nonce"] = [r for r in U if meta[r]["nonce"] not in nonces]
                if f.startswith("ctl:"):
                    refs["S_nonce_as_quant"] = [r for r in U if meta[r]["nonce"] not in quant_nonces]
            else:
                continue
            fe = {"draws": rs, "nonces": sorted(map(str, nonces))}
            for lab, ref in refs.items():
                if len(ref) < 2:
                    fe[lab] = {"ref": ref, "skipped": "fewer than 2 reference draws"}
                    continue
                bag = Bag(Y, rs, ref)
                if len(bag.tasks) < 40:
                    fe[lab] = {"ref": ref, "skipped": f"only {len(bag.tasks)} common tasks"}
                    continue
                fe[lab] = {"ref": ref, **bag.summary(rng.uniform())}
                bags[(f, lab)][model] = bag
            mres["families"][f] = fe
        # null-vs-null calibration in the nonce stratum: every pair of nonce nulls vs the rest
        if len(U) >= 4:
            ex, pc = [], []
            for S in combinations(U, 2):
                rest = [r for r in U if r not in S]
                b = Bag(Y, list(S), rest)
                s = b.summary(0.5); ex.append(s["excess_churn"]); pc.append(s["p_churn_cons"])
            mres["null_vs_null"] = {"n_pairs": len(ex), "excess_mean": round(float(np.mean(ex)), 4),
                                    "excess_max": round(float(np.max(ex)), 4), "excess_min": round(float(np.min(ex)), 4),
                                    "share_p_churn_le_0.05": round(float(np.mean(np.array(pc) <= 0.05)), 3),
                                    "flatscore_r_null_split": None}
        # Flat-Score reference: nonce nulls split in halves
        if len(U) >= 2:
            T = sorted(set.intersection(*[set(Y[r]) for r in U]))
            M = np.array([[Y[r][k] for k in T] for r in U], float)
            h = len(U) // 2
            a, b = M[:h].mean(0), M[h:].mean(0)
            mres["flatscore_r_null_halves"] = round(float(np.corrcoef(a, b)[0, 1]), 4) if a.std() > 0 and b.std() > 0 else None
        res["models"][model] = mres
        res["controls_present"][model] = sorted(f for f in fams if f.startswith("ctl:"))
    # pooled over models per (family, reference)
    universe = sorted(set().union(*[set(y) for Y in allY.values() for y in Y.values()]))
    pooled = {}
    for (f, lab), per in sorted(bags.items()):
        u = rng.uniform()
        oc = np.mean([b.A[0].mean() for b in per.values()])
        on = np.mean([b.D[0].mean() for b in per.values()])
        sc = np.zeros(B_MC); sn = np.zeros(B_MC)
        for b in per.values():
            j = rng.integers(0, len(b.combos), B_MC)
            sc += b.A.mean(1)[j] / len(per); sn += b.D.mean(1)[j] / len(per)
        exb = excess_boot(list(per.values()), universe)
        ex = float(np.mean([b.A[0].mean() - np.median(b.A.mean(1)) for b in per.values()]))
        pooled[f"{f}|{lab}"] = {"family": f, "ref": lab, "models": sorted(per), "delta_mean": round(float(on), 4),
                                "p_net": round(float((1 + (np.abs(sn) >= abs(on) - 1e-12).sum()) / (B_MC + 1)), 5),
                                "churn_mean": round(float(oc), 4),
                                "p_churn": round(float((1 + (sc >= oc - 1e-12).sum()) / (B_MC + 1)), 5),
                                "excess_mean": round(ex, 4), "excess_ci95": ci(exb),
                                "p_min_exact": float(1 / np.prod([len(b.combos) for b in per.values()]))}
    # Holm across all (family x {net, churn}) pooled tests (primary references only: S_canonical / S_nonce)
    prim = {k: v for k, v in pooled.items() if v["ref"] in ("S_canonical", "S_nonce")}
    h = holm({(k, s): prim[k][f"p_{s}"] for k in prim for s in ("net", "churn")})
    for (k, s), v in h.items():
        pooled[k][f"p_{s}_holm_all"] = v
    res["holm_all_m"] = len(h)
    # per model Holm across all (family x {net, churn}) on conservative exact p
    for model, mres in res["models"].items():
        ps = {}
        for f, fe in mres["families"].items():
            for lab in ("S_canonical", "S_nonce"):
                if lab in fe and "p_churn_cons" in fe[lab]:
                    ps[(f, lab, "net")] = fe[lab]["p_net_cons"]; ps[(f, lab, "churn")] = fe[lab]["p_churn_cons"]
        for (f, lab, s), v in holm(ps).items():
            mres["families"][f][lab][f"p_{s}_cons_holm_all"] = v
    # verdicts
    ctl = pooled.get("ctl:gauss0.03_s1|S_nonce_as_quant") or pooled.get("ctl:gauss0.03_s1|S_nonce")
    verdict = {}
    for k, v in pooled.items():
        if v["ref"] not in ("S_canonical", "S_nonce"):
            continue
        a = v.get("p_churn_holm_all", 1) <= 0.05
        b = v["excess_ci95"][0] > 0
        if v["family"].startswith("ctl:"):
            c = "n/a (control)"
        elif ctl is None:
            c = "pending (fixed-checkpoint control not in snapshot)"
        else:
            c = bool(v["excess_ci95"][0] > ctl["excess_mean"])
        surv = a and b and (c is True)
        verdict[k] = {"a_holm_p_churn<=0.05": a, "b_excess_ci_above_0": b, "c_exceeds_fixed_ckpt_control": c,
                      "survives": "yes" if surv else ("provisional (a,b hold; c pending)" if a and b and isinstance(c, str) and c.startswith("pending") else "no")}
    res["pooled"] = pooled; res["verdict"] = verdict
    dump("k01_churn.json", res)
    for model, mres in res["models"].items():
        print("==", model, "K", len(mres["K"]), "U", len(mres["U"]), "null_vs_null", mres["null_vs_null"],
              "fs_r_null", mres.get("flatscore_r_null_halves"))
        for f, fe in mres["families"].items():
            for lab in ("S_canonical", "S_nonce", "S_nonce_as_quant"):
                x = fe.get(lab)
                if x and "churn_obs" in x:
                    print(f"  {f:18s} {lab:16s} m={x['m']} n={x['n_ref']} T={x['n_tasks']} d={x['delta']:+.3f} "
                          f"churn={x['churn_obs']:.3f} med={x['churn_perm_median']:.3f} ex={x['excess_churn']:+.3f} "
                          f"p={x['p_churn_cons']:.3f} (min {x['p_min']:.3f}) r={x['flatscore_r_task_rates']}")
                elif x:
                    print(f"  {f:18s} {lab:16s} {x.get('skipped')}")
    for k, v in pooled.items():
        print("POOLED", k, v["models"], "d", v["delta_mean"], "ex", v["excess_mean"], v["excess_ci95"], "p_churn", v["p_churn"],
              "holm", v.get("p_churn_holm_all"), verdict.get(k, {}).get("survives"))


if __name__ == "__main__":
    main()
