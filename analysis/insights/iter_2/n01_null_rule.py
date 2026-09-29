"""Null-admission rule NR1 (docs/insights/NULL_RULE.md, pre-declared) applied to the frozen snapshot.

Per model: eligible null draws (NR1-1/2: a6k2 bf16, bf16_eager, null_n*; frozen; >= 77/85 tasks scored), strata
K = canonical prompt {bf16, bf16_eager}, U = nonce prompt {null_n*}. Exact permutation test of the stratum labels
(all C(n, |K|) relabellings) with T_net = |rate(K) - rate(U)| and T_churn = mean_t |ybar_K(t) - ybar_U(t)| on the
complete-case tasks; conservative p (ties against us). Pooled: stratified MC permutation (B = 20000), statistic =
mean over models. Decision NR1-5: A primary for model M iff p_min <= 0.10 and both conservative p > 0.10 and both
pooled p > 0.10; otherwise S primary. Also (report only, NR1-6): leave-one-out conformal p of each null draw vs the
rest (net, churn).
Usage: CLOQ_SNAPSHOT=out/snapshot_<utc>.json python n01_null_rule.py -> out/n01_null_rule.json
"""
import os
from itertools import combinations
from math import comb

import numpy as np

from common import SNAP, dump, fam, now, outcomes_both, runs_for

MODELS = os.environ.get("CLOQ_MODELS", "q4,q8,q14,q30a3,q32").split(",")
MIN_TASKS = 77
ALPHA = 0.10
B = 20000
rng = np.random.default_rng(20260929)


def eligible(model):
    Y = {}
    for r in runs_for(model):
        if fam(r, model).startswith("null:"):
            y = outcomes_both(r)
            if len(y) >= MIN_TASKS:
                Y[r] = y
    return Y


def mat(Y, runs):
    K = sorted(set.intersection(*[set(Y[r]) for r in runs]))
    return K, np.array([[Y[r][k] for k in K] for r in runs], float)


def stats(M, idx):
    a = M[idx].mean(0); b = np.delete(M, idx, 0).mean(0)
    return abs(a.mean() - b.mean()), np.abs(a - b).mean()


def main():
    res = {"snapshot_utc": now(), "rule": "docs/insights/NULL_RULE.md (NR1 v1)",
           "null_rule_sha256_in_snapshot": (SNAP or {}).get("null_rule"), "alpha": ALPHA, "models": {}}
    pooled_parts = {}
    for m in MODELS:
        Y = eligible(m)
        Kr = sorted(r for r in Y if fam(r, m) in ("null:bf16", "null:eager"))
        Ur = sorted(r for r in Y if fam(r, m) == "null:nonce")
        e = {"canonical": Kr, "nonce": Ur}
        if len(Kr) < 1 or len(Ur) < 1 or len(Kr) + len(Ur) < 3:
            e["verdict"] = "untestable (need both strata, n >= 3)"; e["primary"] = "S"
            res["models"][m] = e
            continue
        runs = Kr + Ur
        T, M = mat(Y, runs)
        k = len(Kr); n = len(runs)
        obs = stats(M, list(range(k)))
        allp = np.array([stats(M, list(S)) for S in combinations(range(n), k)])
        p = [float((allp[:, j] >= obs[j] - 1e-12).mean()) for j in (0, 1)]
        pmin = 1 / comb(n, k)
        rates = M.mean(1)
        # NR1-6: leave-one-out conformal p per draw (report only)
        loo = {}
        for i, r in enumerate(runs):
            rest = np.delete(M, i, 0).mean(0)
            s_net = [abs(M[j].mean() - np.delete(M, j, 0).mean()) for j in range(n)]
            s_ch = [np.abs(M[j] - np.delete(M, j, 0).mean(0)).mean() for j in range(n)]
            loo[r] = {"rate": round(float(rates[i]), 4),
                      "p_net_cons": round(float(np.mean(np.array(s_net) >= s_net[i] - 1e-12)), 3),
                      "p_churn_cons": round(float(np.mean(np.array(s_ch) >= s_ch[i] - 1e-12)), 3)}
        e.update({"n_tasks": len(T), "n": n, "rate_K": round(float(rates[:k].mean()), 4),
                  "rate_U": round(float(rates[k:].mean()), 4), "delta_K_minus_U": round(float(rates[:k].mean() - rates[k:].mean()), 4),
                  "T_net": round(float(obs[0]), 4), "T_churn": round(float(obs[1]), 4),
                  "churn_perm_median": round(float(np.median(allp[:, 1])), 4),
                  "p_net_cons": round(p[0], 4), "p_churn_cons": round(p[1], 4), "p_min": round(pmin, 4),
                  "informative": bool(pmin <= ALPHA), "loo_conformal": loo})
        pooled_parts[m] = (M, k, (rates[:k].mean() - rates[k:].mean()), obs[1])
        res["models"][m] = e
    # pooled stratified MC
    if len(pooled_parts) >= 2:
        sn = np.zeros(B); sc = np.zeros(B); on = oc = 0.0
        for m, (M, k, d, c) in pooled_parts.items():
            n = M.shape[0]
            perm = np.argsort(rng.random((B, n)), 1)
            a = M[perm[:, :k]].mean(1); b = M[perm[:, k:]].mean(1)
            sn += (a.mean(1) - b.mean(1)) / len(pooled_parts); sc += np.abs(a - b).mean(1) / len(pooled_parts)
            on += d / len(pooled_parts); oc += c / len(pooled_parts)
        res["pooled"] = {"models": sorted(pooled_parts), "delta_mean": round(float(on), 4), "churn_mean": round(float(oc), 4),
                         "p_net": round(float((1 + (np.abs(sn) >= abs(on) - 1e-12).sum()) / (B + 1)), 5),
                         "p_churn": round(float((1 + (sc >= oc - 1e-12).sum()) / (B + 1)), 5), "B": B}
    pl = res.get("pooled")
    pooled_ok = bool(pl and pl["p_net"] > ALPHA and pl["p_churn"] > ALPHA)
    for m, e in res["models"].items():
        if "p_net_cons" not in e:
            continue
        ok = e["informative"] and e["p_net_cons"] > ALPHA and e["p_churn_cons"] > ALPHA and pooled_ok
        e["primary"] = "A" if ok else "S"
        why = []
        if not e["informative"]:
            why.append(f"uninformative (p_min {e['p_min']} > {ALPHA})")
        if e["p_net_cons"] <= ALPHA:
            why.append(f"net rejects (p {e['p_net_cons']})")
        if e["p_churn_cons"] <= ALPHA:
            why.append(f"churn rejects (p {e['p_churn_cons']})")
        if not pooled_ok:
            why.append("pooled test rejects or unavailable")
        e["verdict"] = "A admissible" if ok else "S primary: " + "; ".join(why)
    dump("n01_null_rule.json", res)
    for m, e in res["models"].items():
        print(m, {k: e.get(k) for k in ("canonical", "nonce", "n_tasks", "delta_K_minus_U", "T_churn", "churn_perm_median",
                                         "p_net_cons", "p_churn_cons", "p_min", "verdict")})
    print("pooled", res.get("pooled"))


if __name__ == "__main__":
    main()
