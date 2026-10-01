"""Can the pivot be detected? Decision-time uncertainty of Q at the first divergence, and the value of escalating (W55).

Positives: Q's decision at the primary fork state t* (first semantic action divergence from B at the identical prompt).
Negatives: Q's decisions before t* in divergent units and every decision of fully searched non-divergent units (at
each of them B's full action was generated and matched Q's). Decisions after t* are never compared with B, so they are
not labelled. Units, inputs, exclusions and quarantine as analysis/fork/analyze_dev.py (dev / kv / stress / telecom).
Signals (from the Q run's decisions.jsonl, top-5 logprobs at serving time; score = larger means "more pivot-like"):
  -first_token_margin   top-1 minus top-2 logprob of the first generated token
  -min_margin           smallest top-1/top-2 gap over the generated tokens
  -mean_logprob         mean log-probability of the generated tokens (mean NLL)
  -min_logprob          largest single-token NLL
  n_low_margin          number of generated tokens with margin < 1 nat
  (entropy is not available: only chosen-token logprobs and top-1/top-2 margins were logged)
AUROC per model x cell: (i) all decisions, (ii) matched: pairs compared only within the same (domain, decision index).
Intervals for (i) per analyze_dev.Boot (W63): blocks resampled whole (block bootstrap if >= 10 blocks, else t over
per-block AUROCs) and the crossed task x block bootstrap; B = 500.
Threshold rule "first_token_margin < theta" (thresholds at escalation-rate targets over ALL of Q's decisions): escalation
rate vs pivots caught, and an ORACLE UPPER-BOUND PROXY E[1(pivot caught)(Y_BQ - Y_QQ)]. This is not a policy value: it
counts only hits on true pivots and does not simulate false triggers, later triggers or the new trajectories they create
(and semantically equal actions can still differ in wording). An end-to-end evaluation is designed in FORK_PROTOCOL §14.
Three oracle contrasts on the full pool, reported separately:
  replace the current action only      Y_BQ - Y_QQ
  keep Q's action, then switch to BF16 Y_QB - Y_QQ = C + I
  BF16 action and suffix               Y_BB - Y_QQ = A + C + I   (oracle intervention value, not an escalation effect)
EXPLORATORY for development data.

usage: python analysis/fork/analyze_pivot.py --snapshot <snapshot.json> [--cells ...]
-> analysis/fork/out/pivot_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD  # noqa: E402

ROOT, OUT = AD.ROOT, AD.OUT
CACHE = ROOT / "analysis/fork/.cache/pivot"
SIGNALS = ["neg_first_token_margin", "neg_min_margin", "neg_mean_logprob", "neg_min_logprob", "n_low_margin"]
RATES = [0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5]


def features(d: dict) -> dict:
    lp = [x for x in (d.get("token_logprobs") or []) if x is not None]
    mg = [x for x in (d.get("token_margins") or []) if x is not None]
    big = 99.0  # no alternative in the top-k: maximally confident
    ftm = d.get("first_token_margin")
    mm = d.get("min_margin")
    return {"neg_first_token_margin": -(ftm if ftm is not None else big), "neg_min_margin": -(mm if mm is not None else big),
            "neg_mean_logprob": -(float(np.mean(lp)) if lp else 0.0), "neg_min_logprob": -(min(lp) if lp else 0.0),
            "n_low_margin": float(sum(1 for x in mg if x < 1.0)), "has_margins": bool(mg)}


def run_features(run_id: str, dom: str, sha: str) -> dict:
    """task -> [features per decision] for the final attempt (W8), cached by trajectory sha."""
    cp = CACHE / f"{run_id}__{dom}__{sha[:16]}.json"
    if cp.exists():
        return json.loads(cp.read_text())
    recs = []
    with open(ROOT / "runs" / run_id / dom / "decisions.jsonl") as f:
        for ln in f:
            d = json.loads(ln)
            recs.append((d["task_id"], d["trajectory_id"], d["decision_idx"], features(d)))
    last = {}
    for t, tr, _, _ in recs:
        last[t] = tr
    out = defaultdict(dict)
    for t, tr, i, fe in recs:
        if last[t] == tr:
            out[f"{dom}:{t}"][i] = fe
    res = {k: [v[i] for i in sorted(v)] for k, v in out.items()}
    CACHE.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps(res))
    return res


def wauc(s, y, w):
    """Weighted AUROC (ties = 1/2)."""
    o = np.argsort(s, kind="mergesort")
    s, y, w = s[o], y[o], w[o]
    wp, wn = (w * y).sum(), (w * (1 - y)).sum()
    if wp <= 0 or wn <= 0:
        return np.nan
    uniq, idx = np.unique(s, return_index=True)
    bounds = list(idx) + [len(s)]
    below, acc = 0.0, 0.0
    for a, b in zip(bounds[:-1], bounds[1:]):
        pw = (w[a:b] * y[a:b]).sum()
        nw = (w[a:b] * (1 - y[a:b])).sum()
        acc += pw * (below + 0.5 * nw)
        below += nw
    return acc / (wp * wn)


def matched_auc(s, y, strata):
    num = den = 0.0
    for st in np.unique(strata):
        m = strata == st
        sp, sn = s[m & (y == 1)], s[m & (y == 0)]
        if len(sp) and len(sn):
            c = (sp[:, None] > sn[None, :]).sum() + 0.5 * (sp[:, None] == sn[None, :]).sum()
            num += c
            den += len(sp) * len(sn)
    return num / den if den else np.nan


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--cells", nargs="*", default=None)
    ap.add_argument("--B", type=int, default=AD.B_BOOT)
    ap.add_argument("--B-auc", type=int, default=500)
    ap.add_argument("--split", default="dev")
    a = ap.parse_args()
    t0 = time.time()
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    snap = json.load(open(a.snapshot))
    loaded = [AD.load_dir(d, snap, {}) for d in AD.discover(False)]
    split_info = AD.split_guard([u for L in loaded for u in L["units"]], a.split, "analyze_pivot")
    _all, _ = AD.dedupe_units([u for L in loaded for u in L["units"] if not L["quarantined"]])
    split_info["incomplete_blocks"] = AD.mark_incomplete_blocks(_all, a.split, strict=True)
    units = [u for u in _all if "excluded" not in u and (not a.cells or u["cell"] in a.cells)]
    if not units:
        print("analyze_pivot: no analysable fork units; nothing to do.")
        return
    files = {k: v for L in loaded for k, v in L["files"].items()}
    fp = hashlib.sha256(json.dumps({"script": AD.sha256(__file__), "dev": AD.sha256(AD.__file__), "snapshot": AD.sha256(a.snapshot),
                                    "files": files, "cells": a.cells, "B": [a.B, a.B_auc], "split": a.split, "splits": AD.sha256(AD.SPLITS)}, sort_keys=True).encode()).hexdigest()[:16]
    OUT.mkdir(parents=True, exist_ok=True)
    for p in sorted(OUT.glob("pivot_*.json")):
        try:
            if json.load(open(p)).get("input_fingerprint") == fp:
                print(f"analyze_pivot: unchanged inputs; existing output {p.relative_to(ROOT)}")
                return
        except Exception:
            continue
    feats = {}
    for u in units:
        k = (u["run_id"], u["domain"])
        if k not in feats:
            feats[k] = run_features(*k, snap["frozen"][u["run_id"]][u["domain"]]["files"]["trajectory.jsonl"]["sha256"])
    res_cells = {}
    for m, c in sorted({(u["model"], u["cell"]) for u in units}):
        cu = [u for u in units if u["model"] == m and u["cell"] == c]
        for u in cu:
            u["E"] = AD.effects(u["Y"], u["div"])
        rows, all_ftm, miss = [], [], 0  # labelled decisions: (task, block, domain, t, label, feats)
        for u in cu:
            fl = feats[(u["run_id"], u["domain"])].get(u["task"])
            if not fl:
                miss += 1
                continue
            all_ftm += [-f["neg_first_token_margin"] for f in fl]
            lim = u["t"] if u["div"] else len(fl) - 1
            for t in range(min(lim, len(fl) - 1) + 1):
                if u["div"] and t > u["t"]:
                    break
                rows.append((u["task"], u["block"], u["domain"], t, int(u["div"] and t == u["t"]), fl[t]))
        y = np.array([r[4] for r in rows])
        strata = np.array([f"{r[2]}|{r[3]}" for r in rows])
        tasks = sorted({r[0] for r in rows})
        tix = {t: i for i, t in enumerate(tasks)}
        blocks = sorted({r[1] for r in rows})
        bix = {b: i for i, b in enumerate(blocks)}
        ti = np.array([tix[r[0]] for r in rows])
        bi = np.array([bix[r[1]] for r in rows])
        bo = defaultdict(set)
        for u in cu:
            bo[u["task"]].add(u["block"])
        boot = AD.Boot(sorted(bo), {k: sorted(v) for k, v in bo.items()}, B=a.B)
        ti = np.array([boot.tix[r[0]] for r in rows])
        bi = np.array([boot.bix[r[1]] for r in rows])
        wb = boot.unit_weights(ti, bi, "block")[: a.B_auc]
        wc = boot.unit_weights(ti, bi, "crossed")[: a.B_auc]
        auc = {}
        for sgn in SIGNALS:
            s = np.array([r[5][sgn] for r in rows], float)
            pt = wauc(s, y, np.ones(len(s)))
            db = np.array([wauc(s, y, w) for w in wb])
            dc = np.array([wauc(s, y, w) for w in wc])
            per_block = [wauc(s[bi == k], y[bi == k], np.ones(int((bi == k).sum()))) for k in np.unique(bi)]
            rep = AD.summarise(pt, db[np.isfinite(db)], pct=False, t=AD.t_interval([v for v in per_block if np.isfinite(v)]),
                               crossed=(pt, dc[np.isfinite(dc)]))
            auc[sgn] = {"auroc": round(float(pt), 4), "ci95": rep["ci95"], "primary": rep["primary"], "t_ci95": rep.get("t_ci95"),
                        "block_boot_ci95": rep["block_boot_ci95"], "crossed_ci95": rep.get("crossed_ci95"),
                        "auroc_matched_domain_index": round(float(matched_auc(s, y, strata)), 4)}
        # escalation policy on first_token_margin
        all_ftm = np.array(all_ftm)
        piv = {id(u): -feats[(u["run_id"], u["domain"])][u["task"]][u["t"]]["neg_first_token_margin"]
               for u in cu if u["div"] and feats[(u["run_id"], u["domain"])].get(u["task"]) and u["t"] < len(feats[(u["run_id"], u["domain"])][u["task"]])}
        policy = []
        for r in RATES:
            th = float(np.quantile(all_ftm, r))
            caught = [v < th for v in piv.values()]
            for u in cu:
                u["E"]["V_policy"] = u["E"]["G"] if (u["div"] and piv.get(id(u), 99) < th) else 0
            X, M = boot.arrays(cu, "V_policy")
            policy.append({"escalation_rate_target": r, "theta_first_token_margin": round(th, 4),
                           "escalation_rate": round(float((all_ftm < th).mean()), 4),
                           "pivot_recall": round(float(np.mean(caught)), 4) if caught else None,
                           "oracle_upper_bound_proxy_pp": AD.summarise(*boot.task_mean(X, M))})
        vals = {}
        for key in ("G", "H_policy", "F_policy"):
            X, M = boot.arrays(cu, key)
            vals[key] = AD.summarise(*boot.task_mean(X, M))
        dv = [u for u in cu if u["div"]]
        for key in ("G", "H", "F"):
            X, M = boot.arrays(dv, key)
            vals[f"{key}_cond"] = AD.summarise(*boot.ratio(X, M))
        res_cells[f"{m}:{c}"] = {"n_units": len(cu), "n_pivots": int(y.sum()), "n_negatives": int((1 - y).sum()),
                                 "n_units_without_decisions": miss, "auroc": auc,
                                 "threshold_rule_oracle_upper_bound_proxy": {
                                     "note": ("NOT a policy value: counts only hits on true pivots (value = Y_BQ - Y_QQ there); ignores false "
                                              "triggers, later triggers and the new trajectories they create, and semantically equal "
                                              "actions can still differ in wording. Oracle upper-bound proxy only."),
                                     "rows": policy},
                                 "oracle_contrasts_all_pp": {
                                     "replace_current_action_only G = Y_BQ-Y_QQ (full pool, pivot policy)": vals["G"],
                                     "keep_Q_action_then_BF16 H = Y_QB-Y_QQ = C+I (full pool, pivot policy H_policy)": vals["H_policy"],
                                     "BF16_action_and_suffix F = Y_BB-Y_QQ = A+C+I (full pool, pivot policy F_policy; oracle intervention value, not an escalation-policy effect)": vals["F_policy"]},
                                 "oracle_contrasts_conditional_on_divergence_pp": {"G": vals["G_cond"], "H": vals["H_cond"], "F": vals["F_cond"]}}
    res = {"label": "EXPLORATORY (development data)", "analysis": "analysis/fork/analyze_pivot.py", "input_fingerprint": fp,
           "snapshot": {"id": snap.get("snapshot_id"), "sha256": AD.sha256(a.snapshot), "path": str(Path(a.snapshot).resolve())},
           "script": {"sha256": AD.sha256(__file__), "analyze_dev_sha256": AD.sha256(AD.__file__),
                      "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()},
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "split": split_info, "cells": res_cells, "seconds": round(time.time() - t0, 1)}
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    jp = OUT / f"pivot_{utc}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))

    def f(x):
        return f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}]"
    L = ["**TL;DR** EXPLORATORY pivot detection (no policy-value claim): AUROC of -first_token_margin for 'first divergence' = " +
         "; ".join(f"{k} {v['auroc']['neg_first_token_margin']['auroc']:.2f} (matched {v['auroc']['neg_first_token_margin']['auroc_matched_domain_index']:.2f})"
                   for k, v in res_cells.items()) + ".", "", f"# Pivot detection and escalation value ({res['utc']})", "",
         f"Snapshot `{res['snapshot']['id']}`; full numbers `{jp.relative_to(ROOT)}`.", "",
         "| cell | pivots / negatives | AUROC -ftm [primary CI] | -min_margin | -mean_lp | -min_lp | n_low |", "|---|---|---|---|---|---|---|"]
    for k, v in res_cells.items():
        au = v["auroc"]
        L.append(f"| {k} | {v['n_pivots']} / {v['n_negatives']} | {au[SIGNALS[0]]['auroc']:.2f} [{au[SIGNALS[0]]['ci95'][0]:.2f}, {au[SIGNALS[0]]['ci95'][1]:.2f}] | "
                 + " | ".join(f"{au[s]['auroc']:.2f}" for s in SIGNALS[1:]) + " |")
    L += ["", "Oracle contrasts on the full pool (pp; primary CI per analyze_dev.Boot). These are intervention values at the true pivot, "
          "not escalation-policy effects:", "",
          "| cell | replace current action only (Y_BQ-Y_QQ) | keep Q action, then BF16 (Y_QB-Y_QQ = C+I) | BF16 action and suffix (Y_BB-Y_QQ, oracle) |",
          "|---|---|---|---|"]
    for k, v in res_cells.items():
        vv = list(v["oracle_contrasts_all_pp"].values())
        L.append(f"| {k} | " + " | ".join(f(x) for x in vv) + " |")
    L += ["", "Threshold rule (first-token margin < theta), ORACLE UPPER-BOUND PROXY only (true-pivot hits; no false/later triggers "
          "simulated): escalation rate / pivots caught / proxy (pp):"]
    for k, v in res_cells.items():
        L.append(f"- {k}: " + "; ".join(f"{p['escalation_rate']:.2f} / {p['pivot_recall']:.2f} / {f(p['oracle_upper_bound_proxy_pp'])}"
                                        for p in v["threshold_rule_oracle_upper_bound_proxy"]["rows"]))
    (OUT / f"pivot_{utc}.md").write_text("\n".join(L) + "\n")
    print(f"analyze_pivot: wrote {jp.relative_to(ROOT)} ({res['seconds']} s)")


if __name__ == "__main__":
    main()
