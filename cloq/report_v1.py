"""v1 analysis: per-draw tables and crossed-bootstrap contrasts (plan sections 9, 10, 16).

The crossed bootstrap resamples the calibration draw first and then, within the resampled draw,
resamples tasks stratified by domain. That propagates both sources of uncertainty v0 could not
separate: which calibration states were drawn, and which tasks the dev set happens to contain.

usage: python -m cloq.report_v1
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from cloq import config as C
from cloq.metrics import resolved_db_match

V1 = json.load(open(C.PROJECT_ROOT / "configs" / "frozen_v1.json"))
DRAWS = sorted(V1["calibration"]["draws"])
ARMS = ["static", "fp_traj", "cloq_all", "cloq_novel"]
LONG_H = int(V1["evaluation"]["long_horizon_threshold"])
ANALYSIS = C.PROJECT_ROOT / "analysis" / "v1"


def load_arm(run_id: str, eval_ids: dict[str, list[str]]) -> dict[str, float] | None:
    """task key -> db_match, or None when the run is missing or incomplete."""
    out = {}
    for dom, ids in eval_ids.items():
        p = C.RUNS_DIR / run_id / dom
        if not (p / "metrics.json").exists():
            return None
        st = json.load(open(p / "status.json"))
        if st.get("status") != "completed":
            return None
        for r in json.load(open(p / "metrics.json"))["per_task"]:
            if r["task_id"] in set(ids):
                out[f"{dom}/{r['task_id']}"] = float(bool(r["db_match"]))
    return out


def crossed_bootstrap(a: dict[str, dict[str, float]], b: dict[str, dict[str, float]],
                      strata: dict[str, str], n_boot: int = 10000, seed: int = 0, ci: float = 0.95) -> dict:
    """mean(a) - mean(b), resampling draws then tasks within domain.

    `a` and `b` map draw -> {task: value}. Draws present in both are used.
    """
    draws = sorted(set(a) & set(b))
    if not draws:
        return {"n_draws": 0}
    ids = sorted(set.intersection(*[set(a[d]) for d in draws], *[set(b[d]) for d in draws]))
    if not ids:
        return {"n_draws": len(draws), "n": 0}
    by_dom = defaultdict(list)
    for t in ids:
        by_dom[strata[t]].append(t)
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    dom_keys = sorted(by_dom)
    for k in range(n_boot):
        d = draws[int(rng.integers(len(draws)))]
        picked = []
        for dom in dom_keys:
            pool = by_dom[dom]
            picked.extend(pool[i] for i in rng.integers(0, len(pool), size=len(pool)))
        diffs[k] = np.mean([a[d][t] - b[d][t] for t in picked])
    point = float(np.mean([np.mean([a[d][t] - b[d][t] for t in ids]) for d in draws]))
    lo, hi = np.quantile(diffs, [(1 - ci) / 2, 1 - (1 - ci) / 2])
    per_draw = {d: float(np.mean([a[d][t] - b[d][t] for t in ids])) for d in draws}
    return {
        "n_draws": len(draws), "n": len(ids), "diff": point,
        "ci_lo": float(lo), "ci_hi": float(hi),
        "p_le_0": float((diffs <= 0).mean()),
        "per_draw": per_draw,
        "all_draws_positive": all(v > 0 for v in per_draw.values()),
        "n_boot": n_boot,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default=str(C.MANIFEST_DIR / "task_split_v0.json"))
    ap.add_argument("--bf16-run", default="bf16_v1")
    ap.add_argument("--out", default=str(ANALYSIS))
    a = ap.parse_args()
    split = json.load(open(a.split))
    domains = list(split["domains"].keys())
    eval_ids = {d: split["domains"][d]["evaluation"] for d in domains}
    strata, horizon = {}, {}
    for d in domains:
        for t in eval_ids[d]:
            strata[f"{d}/{t}"] = d
            horizon[f"{d}/{t}"] = split["domains"][d]["horizon_by_task"].get(t)
    out_dir = Path(a.out); out_dir.mkdir(parents=True, exist_ok=True)

    bf = load_arm(a.bf16_run, eval_ids)
    if bf is None:
        raise SystemExit(f"{a.bf16_run} is missing or incomplete")
    data: dict[str, dict[str, dict[str, float]]] = {}
    for arm in ARMS:
        for dr in DRAWS:
            v = load_arm(f"{arm}_{dr}_dev", eval_ids)
            if v is not None:
                data.setdefault(arm, {})[dr] = v
    bfd = {dr: bf for dr in DRAWS}  # BF16 does not depend on the calibration draw

    longs = [t for t in bf if horizon.get(t) is not None and horizon[t] > LONG_H]
    shorts = [t for t in bf if horizon.get(t) is not None and horizon[t] <= LONG_H]

    def mean_over(v: dict[str, float], keys) -> float | None:
        ks = [k for k in keys if k in v]
        return float(np.mean([v[k] for k in ks])) if ks else None

    rows = []
    for arm in ["bf16"] + ARMS:
        src = bfd if arm == "bf16" else data.get(arm, {})
        for dr in (["-"] if arm == "bf16" else DRAWS):
            v = src.get(DRAWS[0]) if arm == "bf16" else src.get(dr)
            if v is None:
                continue
            rows.append({
                "arm": arm, "draw": dr,
                "retail": mean_over(v, [t for t in v if t.startswith("retail/")]),
                "airline": mean_over(v, [t for t in v if t.startswith("airline/")]),
                "pooled": mean_over(v, list(v)),
                "long": mean_over(v, longs), "short": mean_over(v, shorts),
            })

    contrasts = {}
    pairs = [("fp_traj", "static"), ("cloq_all", "fp_traj"), ("cloq_novel", "fp_traj"),
             ("cloq_novel", "cloq_all"), ("cloq_novel", "static"), ("cloq_all", "static")]
    for x, y in pairs:
        if x not in data or y not in data:
            continue
        contrasts[f"{x} - {y}"] = {
            "pooled": crossed_bootstrap(data[x], data[y], strata),
            "long": crossed_bootstrap({d: {k: v for k, v in data[x][d].items() if k in set(longs)} for d in data[x]},
                                      {d: {k: v for k, v in data[y][d].items() if k in set(longs)} for d in data[y]}, strata),
        }
    for arm in ARMS:
        if arm in data:
            contrasts[f"bf16 - {arm}"] = {
                "pooled": crossed_bootstrap({d: bf for d in data[arm]}, data[arm], strata),
                "long": crossed_bootstrap({d: {k: v for k, v in bf.items() if k in set(longs)} for d in data[arm]},
                                          {d: {k: v for k, v in data[arm][d].items() if k in set(longs)} for d in data[arm]}, strata),
            }

    # pre-registered selection rule (plan section 16)
    sel = None
    if "cloq_novel" in data and "cloq_all" in data:
        def arm_mean(arm, keys):
            return float(np.mean([mean_over(data[arm][d], keys) for d in sorted(data[arm])]))
        ln, la = arm_mean("cloq_novel", longs), arm_mean("cloq_all", longs)
        pn, pa = arm_mean("cloq_novel", list(bf)), arm_mean("cloq_all", list(bf))
        if abs(ln - la) < 0.01:
            choice, why = "cloq_all", "long-task means differ by less than 1 point; the tie rule prefers the simpler arm"
        elif ln > la and pn >= pa - 0.02:
            choice, why = "cloq_novel", "higher long-task mean and pooled mean not worse by more than 2 points"
        else:
            choice, why = "cloq_all", "cloq_novel did not satisfy both selection conditions"
        sel = {"selected": choice, "reason": why, "long_cloq_novel": ln, "long_cloq_all": la,
               "pooled_cloq_novel": pn, "pooled_cloq_all": pa}

    res = {"rows": rows, "contrasts": contrasts, "selection": sel,
           "n_long": len(longs), "n_short": len(shorts), "long_threshold": LONG_H,
           "draws_present": {arm: sorted(data.get(arm, {})) for arm in ARMS}}
    (out_dir / "results_v1.json").write_text(json.dumps(res, indent=2))

    L = ["# CLOQ v1 development results", "",
         f"Dev set: {len(bf)} tasks ({len(longs)} with BF16 horizon > {LONG_H}). "
         f"Three calibration draws per arm.", "",
         "| arm | draw | retail | airline | pooled | long |", "|---|---|---|---|---|---|"]
    f = lambda x: "n/a" if x is None else f"{x:.3f}"
    for r in rows:
        L.append(f"| {r['arm']} | {r['draw']} | {f(r['retail'])} | {f(r['airline'])} | {f(r['pooled'])} | {f(r['long'])} |")
    L += ["", "## Crossed bootstrap (resample draw, then tasks within domain)", "",
          "| contrast | pooled diff | 95% CI | long diff | 95% CI | all draws positive (long) |",
          "|---|---|---|---|---|---|"]
    for name, c in contrasts.items():
        p, lg = c["pooled"], c["long"]
        L.append(f"| {name} | {f(p.get('diff'))} | [{f(p.get('ci_lo'))}, {f(p.get('ci_hi'))}] | "
                 f"{f(lg.get('diff'))} | [{f(lg.get('ci_lo'))}, {f(lg.get('ci_hi'))}] | {lg.get('all_draws_positive')} |")
    if sel:
        L += ["", "## Pre-registered method selection (plan section 16)", "",
              f"Selected: **{sel['selected']}**. {sel['reason']}.", "",
              f"long-task means: cloq_novel {sel['long_cloq_novel']:.3f} vs cloq_all {sel['long_cloq_all']:.3f}; "
              f"pooled: {sel['pooled_cloq_novel']:.3f} vs {sel['pooled_cloq_all']:.3f}."]
    (out_dir / "REPORT_V1.md").write_text("\n".join(L))
    print("\n".join(L[:40]))
    print(f"\nwrote {out_dir/'results_v1.json'} and {out_dir/'REPORT_V1.md'}")


if __name__ == "__main__":
    main()
