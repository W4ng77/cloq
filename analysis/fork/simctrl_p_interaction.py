"""EXPLORATORY interaction diagnostic under the Sonnet 5.5 user simulator (SIMCTRL-P; GPT-6.1 review 9, item B).

EXPLORATORY. No significance claim. Estimates the MEAN SQUARED interaction E[I_s^2] over the SIMCTRL-P states; it is NOT the
share of states with interaction, NOT a variance, and must NOT be converted to or compared with the deterministic W93
off-diagonal share (26.9%).

Sign convention (same as W93 / analyze_dev): Delta_Q = Y_BQ - Y_QQ, Delta_B = Y_BB - Y_QB, I = Delta_Q - Delta_B
  = Y_BQ + Y_QB - Y_BB - Y_QQ. Per state s with arm means Ybar_a,s over the n_a valid replicates (R = 5, none missing):
  Ihat_s = Ybar_BQ + Ybar_QB - Ybar_BB - Ybar_QQ   (probability-scale interaction; = Dhat_Q - Dhat_B exactly)
  U_s    = Ihat_s^2 - sum_a Ybar_a,s (1 - Ybar_a,s) / (n_a - 1)
U_s is unbiased for I_s^2 = (p_BQ + p_QB - p_BB - p_QQ)^2 when, given the state, the replicates within each arm are i.i.d.
Bernoulli(p_a,s) and the four arms are mutually independent: E[Ihat^2] = I^2 + sum_a p_a(1-p_a)/n_a and
E[Ybar(1-Ybar)/(n-1)] = p(1-p)/n. Negative U_s (and negative cell means) are kept, never truncated.
Reported per cell and pooled (equal weight over the 4 cells): mean Ihat, mean Ihat^2 (uncorrected), mean noise correction
sum_a Ybar(1-Ybar)/(n_a-1), and mean U (the estimate of E[I_s^2]).
Intervals (95% percentile, B = 2000, seed 20261001): (i) bootstrap over states stratified by cell; (ii) task-cluster
bootstrap (per cell: tasks within the cell resampled; pool: tasks resampled once across cells, since the same task appears
in several states and cells). Both reuse analyze_simctrl_p.Boots draws (imported).
Inputs: analyze_simctrl_p's loaders (imported: manifest sha gate, load_runs, verify_rows, state_record); arm means checked
against analysis/fork/out/simctrl_p_20261002T015200Z.json. The original-simulator outcomes are not used here.

usage: python analysis/fork/simctrl_p_interaction.py [--final analysis/fork/out/simctrl_p_20261002T015200Z.json] [--B 2000]
-> analysis/fork/out/simctrl_p_interaction_<UTC>.{md,json}
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_simctrl_p as SP  # noqa: E402

ROOT, OUT, ARMS, CELLS = SP.ROOT, SP.OUT, SP.ARMS, SP.CELLS
DEF_FINAL = "analysis/fork/out/simctrl_p_20261002T015200Z.json"
QUANTS = {"mean_I": "mean Î", "mean_I2": "mean Î² (uncorrected)", "mean_corr": "mean noise correction Σ_a Ȳ(1−Ȳ)/(n_a−1)",
          "mean_U": "mean U (estimate of E[I_s²])"}
ADVISOR = {"mean_I2": 0.110, "mean_corr": 0.060, "mean_U": 0.050}
LABEL = ("EXPLORATORY: no significance claim; estimates the mean squared interaction E[I_s²], NOT the share of states with "
         "interaction and NOT a variance; must NOT be converted to or compared with the deterministic 26.9%.")
ASSUMPTIONS = [
    "Given the state, the n_a replicates of each arm are i.i.d. Bernoulli(p_a,s) (the simulator and controllers are re-sampled "
    "independently per replicate; no shared cache or seed across replicates).",
    "The four arms of a state are mutually independent given the state (no shared randomness across arms).",
    "n_a ≥ 2 valid replicates per arm (here n_a = 5 for every arm: no missing replicate).",
    "Unbiasedness is per state and conditional on the state; the pooled mean of U estimates the equal-weight-over-cells average "
    "of I_s² over these 80 frozen states (20 per cell), not over any wider state population.",
    "Unexposed branches (10 BB, 10 QB arm-replicates with 0 user calls) keep their Y, as in the final SIMCTRL-P analysis.",
]


def per_state(s: dict) -> dict:
    m = s["mean"]
    n = {a: len(s["reps"][a]) for a in ARMS}
    I = m["BQ"] + m["QB"] - m["BB"] - m["QQ"]
    dq, db = m["BQ"] - m["QQ"], m["BB"] - m["QB"]
    assert abs(I - (dq - db)) < 1e-12
    corr = sum(m[a] * (1 - m[a]) / (n[a] - 1) for a in ARMS)
    return {"I": I, "I2": I * I, "corr": corr, "U": I * I - corr}


def cis(bo: SP.Boots, states: list[dict], vals: np.ndarray) -> dict:
    """Per-cell and pooled point + stratified-state and task-cluster bootstrap draws (raw scale, not pp)."""
    T = len(bo.tix)
    out, pp, pst, pcl = {}, [], [], []
    for c in bo.cells:
        ix = [i for i, s in enumerate(states) if s["cell_label"] == c]
        v = vals[ix]
        pt = float(v.mean())
        d_st = v[bo.strat[c]].mean(1)
        S, N = np.zeros(T), np.zeros(T)
        for i in ix:
            S[bo.tix[states[i]["task"]]] += vals[i]
            N[bo.tix[states[i]["task"]]] += 1
        den = bo.Wcell[c] @ N
        d_cl = np.where(den > 0, (bo.Wcell[c] @ S) / np.maximum(den, 1e-12), np.nan)
        denp = bo.Wpool @ N
        d_clp = np.where(denp > 0, (bo.Wpool @ S) / np.maximum(denp, 1e-12), np.nan)
        out[c] = {"n": len(ix), "n_tasks": len({states[i]["task"] for i in ix}), "est": round(pt, 4),
                  "ci95_states": q(d_st), "ci95_task_cluster": q(d_cl)}
        pp.append(pt)
        pst.append(d_st)
        pcl.append(d_clp)
    pc = np.mean(np.vstack(pcl), 0)
    out["pool"] = {"cells": bo.cells, "n": len(states), "n_tasks": len(bo.tix), "est": round(float(np.mean(pp)), 4),
                   "ci95_states": q(np.mean(np.vstack(pst), 0)), "ci95_task_cluster": q(pc),
                   "task_cluster_draws_dropped": int((~np.isfinite(pc)).sum())}
    return out


def q(d):
    d = np.asarray(d, float)
    d = d[np.isfinite(d)]
    return [round(float(x), 4) for x in np.percentile(d, [2.5, 97.5])] if d.size else [None, None]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", default="analysis/fork/simctrl_p")
    ap.add_argument("--final", default=DEF_FINAL)
    ap.add_argument("--B", type=int, default=2000)
    a = ap.parse_args()
    t0 = time.time()
    man_sha = SP.sha_file(ROOT / SP.MAN)
    if man_sha != SP.FROZEN_SHA:
        raise SystemExit(f"{SP.MAN}: sha {man_sha} != frozen {SP.FROZEN_SHA}")
    man = json.loads((ROOT / SP.MAN).read_text())
    Rn = int(man["replicates"])
    rows, gate_fail, _, inputs = SP.load_runs(ROOT / a.dir, [1, 2], man, man_sha)
    units = [u for u in man["units"] if u["batch"] in (1, 2)]
    row_fail, _ = SP.verify_rows(units, rows, Rn)
    if gate_fail or row_fail:
        raise SystemExit(f"gate failures: {(gate_fail + row_fail)[:10]}")
    states = [SP.state_record(u, rows.get(u["unit_id"]), {}, Rn) for u in units]
    if any(s["status"] != "ok" for s in states):
        raise SystemExit("not every state ok")
    # cross-check arm means against the final SIMCTRL-P analysis
    fin = json.load(open(ROOT / a.final))
    fr = {s["unit_id"]: s.get("reps") for s in fin["states"]}
    mism = [s["unit_id"] for s in states if s["reps"] != fr.get(s["unit_id"])]
    if mism or len(fr) != len(states):
        raise SystemExit(f"replicate outcomes differ from {a.final}: {mism[:5]}")
    nrep = sorted({len(s["reps"][x]) for s in states for x in ARMS})
    bo = SP.Boots(states, a.B)
    states = [s for s in bo.states]  # Boots keeps the given order
    ps = [per_state(s) for s in states]
    res = {}
    for k, key in (("mean_I", "I"), ("mean_I2", "I2"), ("mean_corr", "corr"), ("mean_U", "U")):
        res[k] = cis(bo, states, np.array([p[key] for p in ps]))
    pool = {k: res[k]["pool"]["est"] for k in QUANTS}
    check = {k: {"this": pool[k], "advisor": v, "abs_diff": round(abs(pool[k] - v), 4), "agree_to_3dp": round(pool[k], 3) == v}
             for k, v in ADVISOR.items()}
    per = [{"unit_id": s["unit_id"], "cell": s["cell_label"], "task": s["task"], "batch": s["batch"],
            "mean": s["mean"], "n_rep": {x: len(s["reps"][x]) for x in ARMS},
            **{k: round(v, 6) for k, v in p.items()}} for s, p in zip(states, ps)]
    neg = {c: sum(1 for p, s in zip(ps, states) if s["cell_label"] == c and p["U"] < 0) for c in bo.cells}
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    git = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    out = {"script": "analysis/fork/simctrl_p_interaction.py", "script_sha256": SP.sha_file(Path(__file__)),
           "analyze_simctrl_p_sha256": SP.sha_file(Path(SP.__file__)), "git_head": git, "utc": utc, "label": LABEL,
           "manifest": SP.MAN, "manifest_sha256": man_sha, "final_analysis": a.final, "replicates_match_final": True,
           "replicates": Rn, "n_valid_replicates_per_arm_values": nrep, "B": a.B, "seed": SP.SEED, "inputs": inputs,
           "sign_convention": "I = Delta_Q - Delta_B = Y_BQ + Y_QB - Y_BB - Y_QQ, Delta_Q = Y_BQ - Y_QQ, Delta_B = Y_BB - Y_QB",
           "estimator": {"Ihat": "Ybar_BQ + Ybar_QB - Ybar_BB - Ybar_QQ",
                         "U": "Ihat^2 - sum_a Ybar_a (1 - Ybar_a) / (n_a - 1)  (unbiased for I_s^2 under the assumptions)",
                         "pool": "equal weight over the 4 cells (20 states each)", "truncation": "none (negative values kept)"},
           "assumptions": ASSUMPTIONS,
           "intervals": {"states": "bootstrap over states stratified by cell (analyze_simctrl_p.Boots.strat)",
                         "task_cluster": "per cell: tasks within the cell resampled; pool: tasks resampled once across cells (Boots.Wcell / Wpool)"},
           "results": res, "n_states_U_negative": neg, "advisor_check": check, "states": per, "seconds": round(time.time() - t0, 1)}
    jp = OUT / f"simctrl_p_interaction_{utc}.json"
    jp.write_text(json.dumps(out, indent=1))
    (OUT / f"simctrl_p_interaction_{utc}.md").write_text(markdown(out, jp))
    print(f"simctrl_p_interaction: wrote {jp.relative_to(ROOT)} and .md ({out['seconds']} s)")


def markdown(r: dict, jp: Path) -> str:
    R = r["results"]

    def f(x, key):
        c = x[key]
        return f"[{c[0]:+.3f}, {c[1]:+.3f}]"

    p = {k: R[k]["pool"] for k in QUANTS}
    ck = r["advisor_check"]
    L = [f"**TL;DR** EXPLORATORY. Under the Sonnet 5.5 simulator (SIMCTRL-P, 80 states, 20 per cell, R = 5 per arm), pooled "
         f"(equal weight over 4 cells): mean Î = {p['mean_I']['est']:+.3f}, mean Î² = {p['mean_I2']['est']:.3f} (uncorrected), mean "
         f"noise correction = {p['mean_corr']['est']:.3f}, mean U = {p['mean_U']['est']:.3f} {f(p['mean_U'], 'ci95_states')} (states) / "
         f"{f(p['mean_U'], 'ci95_task_cluster')} (task cluster) — the estimate of the mean squared interaction E[I_s²] on the "
         f"probability scale. Advisor's first computation 0.110 / 0.060 / 0.050: "
         f"{'reproduced to 3 dp' if all(v['agree_to_3dp'] for v in ck.values()) else 'differs: ' + str({k: v['this'] for k, v in ck.items()})}. "
         f"{LABEL}", "",
         f"# SIMCTRL-P interaction diagnostic (EXPLORATORY) ({r['utc']})", "",
         f"Script `{r['script']}` (sha {r['script_sha256'][:12]}; imports analyze_simctrl_p sha {r['analyze_simctrl_p_sha256'][:12]}), "
         f"git {r['git_head'][:10]}. Manifest `{r['manifest']}` (sha {r['manifest_sha256'][:12]}, frozen). Rows "
         f"`analysis/fork/simctrl_p/<cell>/b{{1,2}}/simctrl_p_rows.jsonl` via analyze_simctrl_p's loaders (gate and row "
         f"re-verification pass); per-arm replicate outcomes equal those stored in `{r['final_analysis']}` for all 80 states. Full numbers: `{jp.relative_to(ROOT)}`.", "",
         f"**Label.** {LABEL}", "",
         "**Sign convention** (consistent with W93): Δ_Q = Y_BQ − Y_QQ, Δ_B = Y_BB − Y_QB, I = Δ_Q − Δ_B = Y_BQ + Y_QB − Y_BB − Y_QQ. "
         "Per state s, with arm means Ȳ_a,s over n_a = 5 valid replicates: Î_s = Ȳ_BQ + Ȳ_QB − Ȳ_BB − Ȳ_QQ (= Δ̂_Q − Δ̂_B exactly); "
         "U_s = Î_s² − Σ_a Ȳ_a,s(1 − Ȳ_a,s)/(n_a − 1). Since E[Î²] = I² + Σ_a p_a(1 − p_a)/n_a and E[Ȳ(1 − Ȳ)/(n − 1)] = p(1 − p)/n, "
         "U_s is unbiased for I_s². Negative U_s and negative cell means are kept (no truncation).", "",
         "**Independence assumptions.**", ""] + [f"- {x}" for x in r["assumptions"]] + [
         "", "**What it is not.** Mean U estimates E[I_s²], the mean squared probability-scale interaction over these states. It "
         "is not the share of states with I ≠ 0 (a state with |I_s| = 0.2 contributes 0.04), not a variance of anything, and "
         "carries no significance claim; it is not converted to or compared with the deterministic W93 off-diagonal 26.9%.", "",
         "## Per cell and pooled (raw probability scale; 95% intervals: stratified state bootstrap, then task-cluster bootstrap)", "",
         "| cell | states (tasks) | " + " | ".join(QUANTS.values()) + " | states with U < 0 |", "|---|---|---|---|---|---|---|"]
    for c in r["results"]["mean_U"]:
        if c == "pool":
            continue
        x = {k: R[k][c] for k in QUANTS}
        L.append(f"| {c} | {x['mean_U']['n']} ({x['mean_U']['n_tasks']}) | " + " | ".join(
            f"{x[k]['est']:+.3f}<br>{f(x[k], 'ci95_states')}<br>{f(x[k], 'ci95_task_cluster')}" for k in QUANTS) +
            f" | {r['n_states_U_negative'][c]} |")
    L.append(f"| **pool (equal weight, 4 cells)** | {p['mean_U']['n']} ({p['mean_U']['n_tasks']}) | " + " | ".join(
        f"{p[k]['est']:+.3f}<br>{f(p[k], 'ci95_states')}<br>{f(p[k], 'ci95_task_cluster')}" for k in QUANTS) +
        f" | {sum(r['n_states_U_negative'].values())} |")
    L += ["", f"Advisor check (pooled): " + "; ".join(f"{k} {v['this']:.4f} vs {v['advisor']:.3f}" for k, v in ck.items()) + ".",
          "Mean U = mean Î² − mean correction holds exactly per cell and pooled. Intervals are descriptive (EXPLORATORY).", ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
