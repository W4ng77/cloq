"""Verifier recompute for iteration 1 (legacy runs/a6000_*), independent of s01/s02/s06.

Re-implements, from runs/<run>/<domain>/decisions.jsonl and tau2_results.json:
  A. first divergence per task (raw completion tokens differ on identical context) -> KM P(<=0/4/12) with a
     task-bootstrap 95% CI, and the per-decision divergence hazard (events / decisions at risk) with CI;
  B. identical-context decision flip rates split by the reference decision kind (text / tool), Wilson CI,
     and the text/tool ratio (P1b on legacy);
  C. AWQ vs gauss k=1 on q8 at matched task subsets (checks the I3 "d=0 does not line up" hint);
  D. outcomes: per-task db_match read from tau2_results.json (premature -> fail, as cloq.metrics), validated
     against metrics.json; q4/q8 null spread, Bernoulli SD, pooled; damage cells (gauss3, rtn_w3) on partial
     tasks vs the null mean on the same tasks (does the endpoint register damage at all?).
Pairing rules follow s02 (nonce cells vs their same-nonce null on prompt_sha; nulls vs bf16 on context excl. system).
Usage: python v01_legacy_recompute.py [a6000|a6k2]
Writes analysis/insights/iter_1/verify/out/v01_legacy_recompute[_a6k2].json
"""
import hashlib
import json
import sys
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path("/data/ziyangs/cloq")
RUNS = ROOT / "runs"
OUT = ROOT / "analysis/insights/iter_1/verify/out"
OUT.mkdir(parents=True, exist_ok=True)
DOMS = ("retail", "airline")
PFX = sys.argv[1] if len(sys.argv) > 1 and __name__ == "__main__" else "a6000"  # a6000 (legacy) or a6k2 (clean)
TAG = "" if PFX == "a6000" else "_" + PFX
rng = np.random.default_rng(1)
B = 2000


def strip(x):
    if isinstance(x, dict):
        return {k: strip(v) for k, v in x.items() if k not in ("id", "tool_call_id")}
    if isinstance(x, list):
        return [strip(v) for v in x]
    return x


def load(run):
    out = {}
    for dom in DOMS:
        p = RUNS / run / dom / "decisions.jsonl"
        if not p.exists():
            continue
        for line in open(p):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            ctx = hashlib.sha1(json.dumps([strip(m) for m in r.get("messages") or [] if m.get("role") != "system"],
                                          sort_keys=True, default=str).encode()).hexdigest()
            out[(dom, str(r["task_id"]), int(r["decision_idx"]))] = dict(
                sha=r.get("prompt_sha256"), ctx=ctx, ids=r.get("completion_token_ids") or [],
                m=r.get("token_margins") or [], kind="tool" if r.get("tool_calls") else "text")
    return out


def ref_for(model, run, runs):
    m = re.search(r"_n(\d+)$", run)
    if "_null_" in run:
        return f"{PFX}_{model}_bf16", "ctx"
    if m and f"{PFX}_{model}_null_n{m.group(1)}" in runs:
        return f"{PFX}_{model}_null_n{m.group(1)}", "sha"
    return f"{PFX}_{model}_bf16", ("ctx" if m else "sha")


def first_div(R, P, key):
    rows = []
    for dom, t in sorted({k[:2] for k in R} & {k[:2] for k in P}):
        i = 0
        while True:
            b, p = R.get((dom, t, i)), P.get((dom, t, i))
            if b is None or p is None or b[key] != p[key]:
                rows.append((f"{dom}/{t}", i, 0)); break
            if b["ids"] != p["ids"]:
                rows.append((f"{dom}/{t}", i, 1)); break
            i += 1
    return rows


def km(rows, h):
    s = 1.0
    for tm in sorted({i for _, i, _ in rows}):
        if tm > h:
            break
        risk = sum(1 for _, i, _ in rows if i >= tm)
        d = sum(1 for _, i, e in rows if i == tm and e)
        s *= 1 - d / risk if risk else 1
    return 1 - s


def hazard(rows):
    ev = sum(e for _, _, e in rows)
    expo = sum(i + 1 if e else i for _, i, e in rows)
    return ev / expo if expo else None


def boot(rows, f):
    idx = np.arange(len(rows))
    vals = [f([rows[j] for j in rng.choice(idx, len(idx))]) for _ in range(B)]
    vals = [v for v in vals if v is not None]
    return [round(float(np.quantile(vals, 0.025)), 3), round(float(np.quantile(vals, 0.975)), 3)]


def wilson(k, n):
    if n == 0:
        return None
    p, z = k / n, 1.96
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    w = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(c - w, 3), round(c + w, 3)]


def flips(R, P, key):
    c = defaultdict(lambda: [0, 0])
    shifts = []
    for k, b in R.items():
        p = P.get(k)
        if p is None or b[key] != p[key] or not b["ids"] or not p["ids"]:
            continue
        c[b["kind"]][0] += int(b["ids"] != p["ids"])
        c[b["kind"]][1] += 1
        a, q = b["ids"], p["ids"]
        j = next((x for x in range(min(len(a), len(q))) if a[x] != q[x]), min(len(a), len(q)))
        shifts += [p["m"][x] - b["m"][x] for x in range(min(j, len(b["m"]), len(p["m"])))
                   if b["m"][x] is not None and p["m"][x] is not None]
    out = {kd: {"flips": v[0], "n": v[1], "rate": round(v[0] / v[1], 3), "wilson95": wilson(*v)} for kd, v in c.items()}
    s = np.abs(np.array(shifts)) if shifts else None
    out["shift_abs_median"] = float(np.median(s)) if s is not None else None
    out["shift_abs_p90"] = float(np.quantile(s, 0.9)) if s is not None else None
    if "text" in out and "tool" in out and out["tool"]["rate"] > 0:
        out["text_over_tool"] = round(out["text"]["rate"] / out["tool"]["rate"], 1)
    return out


def outcomes(run, dom):
    """per-task db_match from tau2_results.json (works for partial runs); premature (non-normal) -> 0."""
    p = RUNS / run / dom / "tau2_results.json"
    if not p.exists():
        return {}
    y = {}
    for s in json.load(open(p)).get("simulations", []):
        db = ((s.get("reward_info") or {}).get("db_check") or {}).get("db_match")
        norm = s.get("termination_reason") in ("user_stop", "agent_stop")
        y[str(s["task_id"])] = int(bool(db) and norm)
    return y


def main():
    res = {"A_divergence": {}, "B_flip_by_kind": {}, "C_awq_vs_gauss1": {}, "D_outcomes": {}}
    for model in ("q4", "q8"):
        runs = sorted(p.name for p in RUNS.iterdir() if p.name.startswith(f"{PFX}_{model}_") and not p.name.endswith("_cal"))
        cache = {}
        get = lambda r: cache.setdefault(r, load(r))
        pairs = [(f"{PFX}_det_{model}_a", f"{PFX}_{model}_bf16", "sha")] if (RUNS / f"{PFX}_det_{model}_a").exists() else []
        pairs += [(r, *ref_for(model, r, runs)) for r in runs if r != f"{PFX}_{model}_bf16"]
        for run, ref, key in pairs:
            rows = first_div(get(ref), get(run), key)
            if not rows:
                continue
            res["A_divergence"][run] = {
                "ref": ref, "n_tasks": len(rows), "n_events": sum(e for *_, e in rows),
                **{f"km<={h}": round(km(rows, h), 3) for h in (0, 4, 12)},
                "km<=4_ci": boot(rows, lambda r: km(r, 4)), "km<=12_ci": boot(rows, lambda r: km(r, 12)),
                "hazard_per_decision": round(hazard(rows), 3), "hazard_ci": boot(rows, hazard)}
            res["B_flip_by_kind"][run] = flips(get(ref), get(run), key)
            print(run, res["A_divergence"][run], res["B_flip_by_kind"][run])
        if model == "q8":
            g1 = {r: first_div(get(f"{PFX}_q8_bf16"), get(r), "sha") for r in (f"{PFX}_q8_gauss1_s1", f"{PFX}_q8_gauss1_s2")}
            for awq in (f"{PFX}_q8_awq_w4_n1", f"{PFX}_q8_awq_w4_n2", f"{PFX}_q8_rtn_w4_n1"):
                ref, key = ref_for("q8", awq, runs)
                ra = first_div(get(ref), get(awq), key)
                tasks = {t for t, *_ in ra}
                d = {"n_tasks": len(ra), "km<=0": round(km(ra, 0), 3), "km<=0_ci": boot(ra, lambda r: km(r, 0))}
                for g, rg in g1.items():
                    sub = [x for x in rg if x[0] in tasks]
                    d[g + "_same_tasks_km<=0"] = round(km(sub, 0), 3)
                    d[g + "_same_tasks_km<=0_ci"] = boot(sub, lambda r: km(r, 0))
                # decision-0 only: is the reference decision-0 margin different between bf16 and the null?
                res["C_awq_vs_gauss1"][awq] = d
                print("C", awq, d)
        # D. outcomes
        for dom in DOMS:
            Y = {r: outcomes(r, dom) for r in runs}
            Y = {r: y for r, y in Y.items() if y}
            val = {}
            for r in Y:
                mp = RUNS / r / dom / "metrics.json"
                if mp.exists():
                    pt = {str(t["task_id"]): int(bool(t["db_match"]) and not t.get("premature")) for t in json.load(open(mp))["per_task"]}
                    val[r] = sum(pt[t] != Y[r].get(t) for t in pt)
            nulls = [r for r in Y if re.search(r"_(bf16|null_n\d)$", r) and len(Y[r]) >= 0.9 * max(len(v) for v in Y.values())]
            if len(nulls) < 2:
                res["D_outcomes"][f"{model}/{dom}"] = {"note": "fewer than 2 (near-)complete nulls", "sizes": {r: len(v) for r, v in Y.items()}}
                continue
            T = sorted(set.intersection(*[set(Y[r]) for r in nulls]))
            N = np.array([[Y[r][t] for t in T] for r in nulls], float)
            pbar = N.mean(0)
            dis = [float(np.mean(N[i] != N[j])) for i in range(len(N)) for j in range(i + 1, len(N))]
            d = {"n_tasks": len(T), "nulls": {r: round(float(N[i].mean()), 3) for i, r in enumerate(nulls)},
                 "null_sd": round(float(N.mean(1).std(ddof=1)), 3),
                 "bernoulli_sd_run": round(float(np.sqrt(np.mean(pbar * (1 - pbar)) / len(T))), 4),
                 "null_pair_disagreement": [round(min(dis), 3), round(max(dis), 3)],
                 "metrics_json_mismatches": val, "cells": {}}
            for r, y in Y.items():
                if r in nulls:
                    continue
                Tt = [t for t in T if t in y]
                if len(Tt) < 5:
                    continue
                diff = np.array([y[t] - pbar[T.index(t)] for t in Tt])
                bs = [diff[rng.choice(len(diff), len(diff))].mean() for _ in range(B)]
                d["cells"][r] = {"n": len(Tt), "db": round(float(np.mean([y[t] for t in Tt])), 3),
                                 "null_mean_same_tasks": round(float(np.mean([pbar[T.index(t)] for t in Tt])), 3),
                                 "delta": round(float(diff.mean()), 3),
                                 "ci95": [round(float(np.quantile(bs, .025)), 3), round(float(np.quantile(bs, .975)), 3)]}
            res["D_outcomes"][f"{model}/{dom}"] = d
            print("D", model, dom, {k: v for k, v in d.items() if k != "cells"})
            for r, c in d["cells"].items():
                print("   ", r, c)
    # pooled q4 Bernoulli run SD over both domains
    q4 = [res["D_outcomes"].get(f"q4/{d}") for d in DOMS]
    if all(x and "n_tasks" in x for x in q4):
        n = sum(x["n_tasks"] for x in q4)
        var = sum((x["bernoulli_sd_run"] ** 2) * x["n_tasks"] ** 2 for x in q4) / n ** 2
        res["D_outcomes"]["q4_pooled_bernoulli_sd_run"] = round(float(np.sqrt(var)), 4)
        res["D_outcomes"]["q4_pooled_n_tasks"] = n
    json.dump(res, open(OUT / f"v01_legacy_recompute{TAG}.json", "w"), indent=1)
    print("wrote", OUT / f"v01_legacy_recompute{TAG}.json")


if __name__ == "__main__":
    main()
