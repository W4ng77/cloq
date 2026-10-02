"""Bank P four-arm simulator control (W97 SIMCTRL-P; manifest manifests/fork/simctrl_p_v1.json; GPT-6.1 review 7).

ROBUSTNESS CHECK ONLY. Same frozen first tool-structure divergence states, same forced a_B / a_Q, same controllers; only the
user simulator after h_t changes (Sonnet 5.5 via simrelay-v2, R = 5 replicates per arm). n = 20 states per cell (10 per
batch) cannot confirm or refute few-pp G/H/F effects; nothing here is a confirmation of a few-pp advantage.

Per state s and arm XY: Ybar_s,XY = mean over the valid replicates (an errored replicate or one whose protocol check
failed is missing, counted, never imputed). Per-state contrasts, then equal-weight means over states:
  G = BQ - QQ, H = QB - QQ, F = BB - QQ, G-H = BQ - QB, F-G = BB - BQ, F-H = BB - QB.
Original simulator, SAME states: the single-run BB/BQ/QB/QQ outcomes of the frozen dev fork (QQ = the recorded original
continuation), loaded through the exact admission that froze the manifest (make_tasks_simctrl_p.admitted_units, which
imports analyze_ghf / analyze_dev; units digests re-checked against dev_all_20261001T070326Z). Paired change per state:
(new contrast - original contrast).
Scopes: per cell, the equal-weight pool of the cells (all 4 once present), for every batch present ("all") and for
batch 1 alone (pre-planned).
Intervals (pp): (i) bootstrap over states stratified by cell (B = 2000, seed 20261001; the pool resamples each cell's
states independently); (ii) task-cluster bootstrap (a task contributes several states within a cell and the same task
appears in several cells: per cell, tasks within the cell are resampled; for the pool, tasks are resampled once across
cells). Proportions over states (replicate disagreement, unexposed) get exact Clopper-Pearson 95% intervals.
Variability: per arm, share of states whose valid replicates are not all equal; per-state correlation (Pearson) between
the original arm outcome and the Sonnet arm mean (stratified bootstrap CI). The four per-state outcomes are NOT summarised
as an off-diagonal share and are NOT compared with W93's 26.9% (noise alone creates arm disagreement).
Unexposed branches (exposed: false, 0 user calls) keep their Y; counts per arm; sensitivity S1 excludes every state with
any unexposed arm-replicate, S2 computes arm means over exposed replicates only.
Integrity: every summary's manifest sha must equal the frozen sha (always fatal). Protocol gate: every expected
cell x batch summary exists with pass = true, protocol_ok, no missing / errored states or arms, and the rows re-verify
(state checks, all v2 relay checks, unique request ids). Any failure refuses to run unless --allow-partial, in which case
the output is labelled INTERIM.

usage: python analysis/fork/analyze_simctrl_p.py                          # final: batches 1 and 2, all 4 cells
       python analysis/fork/analyze_simctrl_p.py --allow-partial          # interim look (output labelled INTERIM)
       python analysis/fork/analyze_simctrl_p.py --batches 1              # batch 1 only (if batch 2 is never run)
       [--dir analysis/fork/simctrl_p] [--B 2000] [--tag x]
-> analysis/fork/out/simctrl_p[_interim][_<tag>]_<UTC>.{md,json}
Run with /data/ziyangs/cloq_work/envs/cloq/bin/python (numpy, scipy).
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "analysis" / "fork"))
sys.path.insert(0, str(ROOT / "scripts" / "a6000"))
OUT = ROOT / "analysis" / "fork" / "out"
MAN = "manifests/fork/simctrl_p_v1.json"
FROZEN_SHA = "fa3dbf366b8584d837cc5231378e683f4a39615b024b662e5bbbb9d79e5a48a3"
CELLS = ["q4:gptq_w4_d1", "q4:awq_w4", "q8:gptq_w4_d1", "q8:awq_w4"]
ARMS = ["BB", "BQ", "QB", "QQ"]
EST = {"G": ("BQ", "QQ"), "H": ("QB", "QQ"), "F": ("BB", "QQ"), "GmH": ("BQ", "QB"), "FmG": ("BB", "BQ"), "FmH": ("BB", "QB")}
LABEL = {"G": "G", "H": "H", "F": "F", "GmH": "G−H", "FmG": "F−G", "FmH": "F−H"}
V2_CHECKS = ["v2_all_calls", "v2_integrity_ok", "v2_answer_model", "v2_template", "relay_all_answered"]
SEED = 20261001
CAVEATS = [
    "Robustness check only: whether the sign/size picture of G/H/F/G−H on these states survives a change of user simulator. "
    "It cannot confirm or refute few-pp G/H/F effects (W93 intervals are a few pp; n ≤ 80 states, 20 per cell).",
    "Histories up to h_t are fixed and come from the original user simulator; only the simulator after h_t changes.",
    "The new simulator (Sonnet 5.5 via headless `claude -p`, Claude Code default sampling) is stochastic; the original "
    "arm outcomes are single runs, so per-state original contrasts are in {−1, 0, 1} and carry the original simulator's "
    "sampling noise; part of any new − original change is noise, not a simulator effect.",
    "Says nothing about rates under the new simulator beyond these states; not a benchmark re-run.",
    "The per-state four outcomes are NOT summarised as an off-diagonal share and NOT compared with W93's 26.9% "
    "(with R = 5 replicate means, sampling noise alone creates arm disagreement).",
    "Cross-cell comparisons are descriptive (each cell selects its own divergent states).",
]


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def cp(k: int, n: int) -> list:
    if n == 0:
        return [None, None]
    lo = 0.0 if k == 0 else float(beta.ppf(0.025, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(0.975, k + 1, n - k))
    return [round(lo, 3), round(hi, 3)]


def ci(draws: np.ndarray) -> list:
    d = draws[np.isfinite(draws)]
    if d.size == 0:
        return [None, None]
    return [round(float(np.percentile(d, 2.5)), 2), round(float(np.percentile(d, 97.5)), 2)]


# ---------------------------------------------------------------------------- inputs and gate


def load_runs(base: Path, batches: list[int], man: dict, man_sha: str) -> tuple[dict, list, dict, dict]:
    """Rows per unit_id, gate failures, per cell x batch status, input file hashes."""
    rows, fails, status, inputs = {}, [], {}, {}
    expect = collections.defaultdict(list)
    for u in man["units"]:
        expect[(f"{u['model']}:{u['cell']}", u["batch"])].append(u["unit_id"])
    for lab in CELLS:
        for b in batches:
            d = base / lab.replace(":", "_") / f"b{b}"
            sp, rp = d / "simctrl_p_summary.json", d / "simctrl_p_rows.jsonl"
            key = f"{lab}|b{b}"
            nbr = len(list((d / "branches").glob("*.json"))) if (d / "branches").is_dir() else 0
            if not sp.exists() or not rp.exists():
                status[key] = {"state": "not finished" if d.exists() else "not started", "branch_files": nbr,
                               "expected_units": len(expect[(lab, b)])}
                fails.append(f"{key}: no summary/rows ({status[key]['state']}, {nbr} branch files)")
                continue
            s = json.loads(sp.read_text())
            if s.get("manifest_sha256") != man_sha or (s.get("spec") or {}).get("manifest_sha256") != man_sha:
                raise SystemExit(f"{sp}: manifest sha {s.get('manifest_sha256')} != frozen {man_sha} (always fatal)")
            if f"{s['spec']['model']}:{s['spec']['cell']}" != lab or sorted(s["spec"]["unit_ids"]) != sorted(expect[(lab, b)]):
                raise SystemExit(f"{sp}: spec cell/unit ids differ from the manifest batch {b} of {lab}")
            if s.get("dry"):
                raise SystemExit(f"{sp}: dry run output")
            inputs[str(sp.relative_to(ROOT))] = sha_file(sp)
            inputs[str(rp.relative_to(ROOT))] = sha_file(rp)
            st = {k: s.get(k) for k in ("n_units", "n_ran", "n_state_ok", "n_missing", "n_errors", "n_branches", "n_arm_errors",
                                        "n_unexposed", "unexposed_by_arm", "protocol_ok", "termination", "user_llm_usage",
                                        "seconds", "pass")}
            st["state"] = "finished"
            st["n_protocol_failures"] = len(s.get("protocol_failures") or [])
            status[key] = st
            for k in ("pass", "protocol_ok"):
                if s.get(k) is not True:
                    fails.append(f"{key}: summary {k} = {s.get(k)}")
            for k in ("n_missing", "n_errors", "n_arm_errors"):
                if s.get(k):
                    fails.append(f"{key}: summary {k} = {s.get(k)}")
            for line in rp.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    rows[r["unit_id"]] = r
    return rows, fails, status, inputs


def verify_rows(units: list[dict], rows: dict, R: int) -> tuple[list, dict]:
    """Independent re-check of each row; returns failures and the integrity tallies."""
    fails = []
    v2 = collections.defaultdict(lambda: collections.Counter())
    reqs = collections.Counter()
    for u in units:
        r = rows.get(u["unit_id"])
        if r is None:
            continue
        for k in ("state_id", "run_id", "domain", "task_id", "t", "block", "batch"):
            if str(r.get(k)) != str(u[k]):
                fails.append(f"{u['unit_id']}: row {k} {r.get(k)} != manifest {u[k]}")
        if "Y" not in r:
            fails.append(f"{u['unit_id']}: state missing ({r.get('missing_reason') or r.get('error') or r.get('skipped')})"[:300])
            continue
        if not all((r.get("state_checks") or {}).values()) or len(r.get("state_checks") or {}) < 11:
            fails.append(f"{u['unit_id']}: state checks {r.get('state_checks')}")
        want = {f"{a}#{i}" for a in ARMS for i in range(R)}
        if set(r["Y"]) != want:
            fails.append(f"{u['unit_id']}: arm-replicate keys {sorted(set(r['Y']) ^ want)}")
        for ar, p in r["protocol"].items():
            if not p.get("ok"):
                fails.append(f"{u['unit_id']} {ar}: protocol failed {p.get('error') or {k: v for k, v in (p.get('checks') or {}).items() if not v}}"[:300])
            if r["exposed"].get(ar):
                for c in V2_CHECKS:
                    v2[c][bool((p.get("checks") or {}).get(c))] += 1
                if len(r["request_ids"].get(ar) or []) != r["n_user_calls"].get(ar):
                    fails.append(f"{u['unit_id']} {ar}: request ids {len(r['request_ids'].get(ar) or [])} != user calls {r['n_user_calls'].get(ar)}")
            elif r["exposed"].get(ar) is False and r["n_user_calls"].get(ar):
                fails.append(f"{u['unit_id']} {ar}: unexposed with {r['n_user_calls'][ar]} user calls")
            for q in r["request_ids"].get(ar) or []:
                reqs[q] += 1
    dup = [q for q, n in reqs.items() if n > 1 or not str(q).startswith("v2-")]
    if dup:
        fails.append(f"{len(dup)} request ids duplicated or not v2: {dup[:5]}")
    tallies = {c: {"pass": v2[c][True], "fail": v2[c][False]} for c in V2_CHECKS}
    return fails, {"v2_checks_over_exposed_branches": tallies, "n_request_ids": sum(reqs.values()),
                   "n_unique_request_ids": len(reqs), "request_id_duplicates_or_non_v2": len(dup)}


def original_outcomes(man: dict) -> tuple[dict, dict]:
    """Original single-run arm outcomes for every manifest unit, via the admission that froze the manifest."""
    import make_tasks_simctrl_p as MT
    ok, meta, AD, G = MT.admitted_units()
    bad = {k: v for k, v in meta["units_digest_check_vs_reference"].items() if not v["match"]}
    if bad:
        raise SystemExit(f"admitted units digest differs from the reference for {sorted(bad)}")
    idx = collections.defaultdict(list)
    for u in ok:
        if u.get("div"):
            idx[(u["run_id"], u["domain"], u["state_id"])].append(u)
    orig, fchk = {}, {}
    for mu in man["units"]:
        L = idx.get((mu["run_id"], mu["domain"], mu["state_id"]), [])
        if len(L) != 1 or L[0]["dir"] != mu["dir"] or L[0]["task"] != f"{mu['domain']}:{mu['task_id']}":
            raise SystemExit(f"manifest unit {mu['unit_id']} not uniquely admitted ({len(L)} matches)")
        okf = sha_file(ROOT / mu["state_file"]) == mu["state_file_sha256"] and sha_file(ROOT / mu["dev_branch_file"]) == mu["dev_branch_file_sha256"]
        if not okf:
            raise SystemExit(f"manifest unit {mu['unit_id']}: dev state/branch file sha differs from the frozen manifest")
        fchk[mu["unit_id"]] = okf
        orig[mu["unit_id"]] = {a: int(L[0]["Y"][a]) for a in ARMS}
    meta = {k: meta[k] for k in ("snapshot", "snapshot_sha256", "reference", "reference_sha256", "units_digest_check_vs_reference",
                                 "quarantined_dirs", "analyze_dev_sha256", "analyze_ghf_sha256", "splits_sha256")}
    meta["dev_state_and_branch_file_sha_ok"] = f"{sum(fchk.values())}/{len(fchk)}"
    return orig, meta


# ---------------------------------------------------------------------------- per-state quantities


def state_record(u: dict, r: dict | None, orig: dict, R: int) -> dict:
    x = {k: u[k] for k in ("unit_id", "model", "cell", "block", "domain", "task_id", "batch", "state_id", "divergence_type")}
    x["cell_label"] = f"{u['model']}:{u['cell']}"
    x["task"] = f"{u['domain']}:{u['task_id']}"
    x["orig"] = orig
    if r is None or "Y" not in r:
        x["status"] = "not run" if r is None else "missing"
        return x
    reps, reps_exp, n_missing_rep = {}, {}, {}
    for a in ARMS:
        ys, ye, miss = [], [], 0
        for i in range(R):
            k = f"{a}#{i}"
            y, p = r["Y"].get(k), (r["protocol"].get(k) or {})
            if y is None or not p.get("ok"):
                miss += 1
                continue
            ys.append(int(y))
            if r["exposed"].get(k):
                ye.append(int(y))
        reps[a], reps_exp[a], n_missing_rep[a] = ys, ye, miss
    x["reps"], x["n_missing_rep"] = reps, n_missing_rep
    x["unexposed"] = {a: sum(1 for i in range(R) if r["exposed"].get(f"{a}#{i}") is False) for a in ARMS}
    x["n_user_calls"] = {a: [r["n_user_calls"].get(f"{a}#{i}") for i in range(R)] for a in ARMS}
    x["termination"] = {a: [r["termination"].get(f"{a}#{i}") for i in range(R)] for a in ARMS}
    x["cost_usd"] = sum((v or {}).get("cost_usd", 0) or 0 for v in r["user_llm_usage"].values())
    x["n_calls"] = sum((v or {}).get("n_calls", 0) or 0 for v in r["user_llm_usage"].values())
    x["context_overflow_arms"] = r.get("context_overflow_arms") or []
    x["budget_fail"] = [k for k, v in (r.get("budget_ok") or {}).items() if not v]
    if any(not reps[a] for a in ARMS):
        x["status"] = "missing (an arm without any valid replicate)"
        return x
    x["status"] = "ok"
    x["mean"] = {a: float(np.mean(reps[a])) for a in ARMS}
    x["mean_exposed"] = {a: (float(np.mean(reps_exp[a])) if reps_exp[a] else None) for a in ARMS}
    x["disagree"] = {a: len(set(reps[a])) > 1 for a in ARMS}
    return x


def contrasts(m: dict) -> dict:
    return {e: m[a] - m[b] for e, (a, b) in EST.items()}


# ---------------------------------------------------------------------------- estimation


class Boots:
    """Stratified-by-cell state bootstrap and task-cluster bootstrap over a fixed list of states."""

    def __init__(self, states: list[dict], B: int):
        self.states, self.B = states, B
        self.cells = [c for c in CELLS if any(s["cell_label"] == c for s in states)]
        rng = np.random.default_rng(SEED)
        self.strat = {}
        for c in self.cells:
            n = sum(1 for s in states if s["cell_label"] == c)
            self.strat[c] = rng.integers(0, n, (B, n))
        tasks = sorted({s["task"] for s in states})
        self.tix = {t: i for i, t in enumerate(tasks)}
        T = len(tasks)
        self.Wpool = np.stack([np.bincount(rng.integers(0, T, T), minlength=T) for _ in range(B)]).astype(float)
        self.Wcell = {}
        for c in self.cells:
            tc = sorted({s["task"] for s in states if s["cell_label"] == c})
            loc = rng.integers(0, len(tc), (B, len(tc)))
            W = np.zeros((B, T))
            for j, t in enumerate(tc):
                W[:, self.tix[t]] = (loc == j).sum(1)
            self.Wcell[c] = W

    def stat(self, vals: dict) -> dict:
        """vals: unit_id -> value (None = excluded). Returns per-cell and pooled estimates with both interval types (pp)."""
        out, pool_pt, pool_strat, pool_clu, pool_clu_ok = {}, [], [], [], True
        T = len(self.tix)
        for c in self.cells:
            sc = [s for s in self.states if s["cell_label"] == c]
            v = np.array([np.nan if vals.get(s["unit_id"]) is None else vals[s["unit_id"]] for s in sc], float)
            ok = np.isfinite(v)
            if not ok.any():
                out[c] = {"n": 0}
                pool_clu_ok = False
                continue
            pt = float(v[ok].mean()) * 100
            vv, oo = np.where(ok, v, 0.0), ok.astype(float)
            I = self.strat[c]
            d_st = vv[I].sum(1) / np.maximum(oo[I].sum(1), 1e-12) * 100
            d_st[oo[I].sum(1) == 0] = np.nan
            S, N = np.zeros(T), np.zeros(T)
            for s, x, o in zip(sc, vv, oo):
                S[self.tix[s["task"]]] += x
                N[self.tix[s["task"]]] += o
            den = self.Wcell[c] @ N
            d_cl = np.where(den > 0, (self.Wcell[c] @ S) / np.maximum(den, 1e-12), np.nan) * 100
            denp = self.Wpool @ N
            d_clp = np.where(denp > 0, (self.Wpool @ S) / np.maximum(denp, 1e-12), np.nan) * 100
            ntask = len({s["task"] for s, o in zip(sc, ok) if o})
            out[c] = {"n": int(ok.sum()), "n_tasks": ntask, "est": round(pt, 2), "ci95_states": ci(d_st), "ci95_task_cluster": ci(d_cl)}
            pool_pt.append(pt)
            pool_strat.append(d_st)
            pool_clu.append(d_clp)
        if pool_pt:
            ps = np.mean(np.vstack(pool_strat), 0)
            pc = np.mean(np.vstack(pool_clu), 0)
            out["pool"] = {"cells": [c for c in self.cells if out[c].get("n")], "n": sum(out[c].get("n", 0) for c in self.cells),
                           "n_tasks": len({s["task"] for s in self.states if vals.get(s["unit_id"]) is not None}),
                           "est": round(float(np.mean(pool_pt)), 2), "ci95_states": ci(ps), "ci95_task_cluster": ci(pc),
                           "task_cluster_draws_dropped": int((~np.isfinite(pc)).sum())}
        return out


def corr_stat(states: list[dict], B: int) -> dict:
    """Per arm: Pearson correlation over states between the original outcome and the Sonnet arm mean (all cells pooled,
    stratified-by-cell bootstrap), plus the mean Sonnet arm success given original 1 / 0."""
    rng = np.random.default_rng(SEED + 1)
    by = collections.defaultdict(list)
    for i, s in enumerate(states):
        by[s["cell_label"]].append(i)
    draws = [np.concatenate([np.array(ix)[rng.integers(0, len(ix), len(ix))] for ix in by.values()]) for _ in range(B)]
    res = {}
    for a in ARMS:
        o = np.array([s["orig"][a] for s in states], float)
        n = np.array([s["mean"][a] for s in states], float)

        def r_(ix):
            oo, nn = o[ix], n[ix]
            if oo.std() == 0 or nn.std() == 0:
                return np.nan
            return float(np.corrcoef(oo, nn)[0, 1])

        pt = r_(np.arange(len(states)))
        d = np.array([r_(ix) for ix in draws])
        dd = d[np.isfinite(d)]
        res[a] = {"n": len(states), "pearson_r": None if not np.isfinite(pt) else round(pt, 3),
                  "ci95": [round(float(np.percentile(dd, 2.5)), 3), round(float(np.percentile(dd, 97.5)), 3)] if dd.size else [None, None],
                  "n_orig_1": int(o.sum()), "n_orig_0": int(len(o) - o.sum()),
                  "sonnet_mean_given_orig_1": round(float(n[o == 1].mean()), 3) if (o == 1).any() else None,
                  "sonnet_mean_given_orig_0": round(float(n[o == 0].mean()), 3) if (o == 0).any() else None,
                  "mean_abs_diff": round(float(np.abs(o - n).mean()), 3),
                  "orig_rate": round(float(o.mean()), 3), "sonnet_rate": round(float(n.mean()), 3)}
    return res


def analyse_scope(states: list[dict], B: int) -> dict:
    ok = [s for s in states if s["status"] == "ok"]
    if not ok:
        return {"n_states": 0}
    bo = Boots(ok, B)
    res = {"n_states": len(ok), "cells": bo.cells, "estimands": {}}
    for e in EST:
        new = {s["unit_id"]: contrasts(s["mean"])[e] for s in ok}
        old = {s["unit_id"]: contrasts(s["orig"])[e] for s in ok}
        chg = {k: new[k] - old[k] for k in new}
        res["estimands"][e] = {"sonnet": bo.stat(new), "original": bo.stat(old), "change": bo.stat(chg)}
    res["arm_rates"] = {a: {"sonnet": bo.stat({s["unit_id"]: s["mean"][a] for s in ok}),
                            "original": bo.stat({s["unit_id"]: s["orig"][a] for s in ok})} for a in ARMS}
    # S1: drop states with any unexposed arm-replicate; S2: arm means over exposed replicates only
    s1 = [s for s in ok if not any(s["unexposed"].values())]
    s2 = {s["unit_id"]: s["mean_exposed"] for s in ok if all(v is not None for v in s["mean_exposed"].values())}
    res["sensitivity"] = {
        "S1_exclude_states_with_unexposed": {"n_states": len(s1), "n_excluded": len(ok) - len(s1),
                                             "estimands": {e: {"sonnet": bo.stat({s["unit_id"]: contrasts(s["mean"])[e] for s in s1}),
                                                               "original": bo.stat({s["unit_id"]: contrasts(s["orig"])[e] for s in s1})}
                                                           for e in EST} if len(s1) < len(ok) else "identical (no unexposed branch)"},
        "S2_exposed_replicates_only": {"n_states": len(s2), "n_excluded": len(ok) - len(s2),
                                       "estimands": {e: {"sonnet": bo.stat({k: contrasts(m)[e] for k, m in s2.items()})} for e in EST}
                                       if any(any(s["unexposed"].values()) for s in ok) else "identical (no unexposed branch)"}}
    # variability (within-simulator) and per-state agreement with the original
    var = {}
    for a in ARMS:
        per = {}
        for c in bo.cells + ["all"]:
            g = [s for s in ok if c == "all" or s["cell_label"] == c]
            k = sum(1 for s in g if s["disagree"][a])
            per[c] = {"disagree": k, "n": len(g), "share": round(k / len(g), 3) if g else None, "ci95": cp(k, len(g)),
                      "n_rep_success_dist": dict(sorted(collections.Counter(int(sum(s["reps"][a])) for s in g).items()))}
        var[a] = per
    res["variability"] = var
    res["correlation_original_vs_sonnet"] = corr_stat(ok, B)
    res["n_states_any_arm_disagree"] = {"k": sum(1 for s in ok if any(s["disagree"].values())), "n": len(ok)}
    return res


def ops(states: list[dict], R: int) -> dict:
    """Unexposed counts, termination, user-call counts, cost (over every state that ran)."""
    ran = [s for s in states if "reps" in s]
    unexp = {}
    for a in ARMS:
        k_br = sum(s["unexposed"][a] for s in ran)
        k_st = sum(1 for s in ran if s["unexposed"][a])
        unexp[a] = {"branches": k_br, "n_branches": R * len(ran), "states_with_any": k_st, "n_states": len(ran),
                    "states_ci95": cp(k_st, len(ran))}
    term = {a: dict(collections.Counter(t for s in ran for t in s["termination"][a])) for a in ARMS}
    calls = {}
    for a in ARMS:
        v = [c for s in ran for c in s["n_user_calls"][a] if c is not None]
        calls[a] = {"n_branches": len(v), "total": int(sum(v)), "mean": round(float(np.mean(v)), 2) if v else None,
                    "median": float(np.median(v)) if v else None, "max": int(max(v)) if v else None, "zero": sum(1 for c in v if c == 0)}
    ncalls = sum(s["n_calls"] for s in ran)
    cost = sum(s["cost_usd"] for s in ran)
    return {"n_states_ran": len(ran), "unexposed": unexp, "termination": term, "user_calls": calls,
            "missing_replicates": {a: sum(s["n_missing_rep"][a] for s in ran) for a in ARMS},
            "context_overflow_branches": sum(len(s["context_overflow_arms"]) for s in ran),
            "budget_check_failures": sum(len(s["budget_fail"]) for s in ran),
            "cost_usd": round(cost, 3), "n_calls": ncalls, "cost_per_call": round(cost / ncalls, 5) if ncalls else None}


# ---------------------------------------------------------------------------- output


def fmt(x: dict | None, key: str = "ci95_states") -> str:
    if not x or not x.get("n"):
        return "—"
    lo, hi = x[key]
    lo, hi = (None, None) if lo is None else (lo + 0.0, hi + 0.0)
    return f"{x['est'] + 0.0:+.1f} [{lo:+.1f}, {hi:+.1f}]" if lo is not None else f"{x['est']:+.1f}"


def scope_tables(L: list, sc: dict, title: str) -> None:
    if not sc.get("n_states"):
        L += [f"### {title}", "", "No complete states.", ""]
        return
    cols = sc["cells"] + ["pool"]
    L += [f"### {title} (n = {sc['n_states']} states)", "",
          "Point estimate [95% stratified state bootstrap] in pp; the task-cluster interval is in the second table. "
          "Original = the single-run dev-fork outcomes of the same states; change = mean over states of (Sonnet contrast − original contrast).", ""]
    for c in cols:
        lab = "pool (equal weight over " + ", ".join(sc["estimands"]["G"]["sonnet"]["pool"]["cells"]) + ")" if c == "pool" else c
        n = sc["estimands"]["G"]["sonnet"][c]["n"]
        L += [f"**{lab}** (n = {n})", "", "| estimand | original | Sonnet 5.5 (R = 5 mean) | change (Sonnet − original) |", "|---|---|---|---|"]
        for e in EST:
            E = sc["estimands"][e]
            L.append(f"| {LABEL[e]} | {fmt(E['original'][c])} | {fmt(E['sonnet'][c])} | {fmt(E['change'][c])} |")
        L.append("")
    L += ["Task-cluster bootstrap intervals (pp; tasks resampled within cell, and across cells for the pool):", "",
          "| cell | n states / tasks | " + " | ".join(f"{LABEL[e]} Sonnet" for e in ("G", "H", "F", "GmH")) + " | "
          + " | ".join(f"{LABEL[e]} change" for e in ("G", "H", "F", "GmH")) + " |", "|---|---|" + "---|" * 8]
    for c in cols:
        x = sc["estimands"]["G"]["sonnet"][c]
        L.append(f"| {c} | {x['n']} / {x.get('n_tasks', '—')} | "
                 + " | ".join(fmt(sc["estimands"][e]["sonnet"][c], "ci95_task_cluster") for e in ("G", "H", "F", "GmH")) + " | "
                 + " | ".join(fmt(sc["estimands"][e]["change"][c], "ci95_task_cluster") for e in ("G", "H", "F", "GmH")) + " |")
    L += ["", "Arm success rates (%, mean over states):", "", "| cell | " + " | ".join(f"{a} orig / Sonnet" for a in ARMS) + " |", "|---|" + "---|" * 4]
    for c in cols:
        L.append(f"| {c} | " + " | ".join(f"{sc['arm_rates'][a]['original'][c]['est']:.0f} / {sc['arm_rates'][a]['sonnet'][c]['est']:.0f}"
                                         for a in ARMS) + " |")
    L.append("")


def markdown(R: dict) -> str:
    interim = R["interim"]
    tl = R["tldr"]
    L = [f"# SIMCTRL-P — Bank P four-arm simulator control{' — INTERIM (partial data; protocol gate not met)' if interim else ''} — {R['utc']}", "",
         "**TL;DR.** " + tl, "",
         "- **Robustness check only.** n is small (≤ 20 states per cell); nothing here confirms or refutes a few-pp G/H/F advantage.",
         f"- **Data:** {R['data_line']}",
         f"- **Integrity:** {R['integrity_line']}",
         f"- **Unexposed:** {R['unexposed_line']}",
         "- **Evidence:** `analysis/fork/analyze_simctrl_p.py`; this file and its .json; inputs (with sha256) in the json `inputs`; "
         "`docs/insights/SIMCTRL_P_PROTOCOL.md`; `manifests/fork/simctrl_p_v1.json`.", ""]
    if interim:
        L += ["> **INTERIM.** Run with `--allow-partial`. Gate failures:", ""] + [f"> - {f}" for f in R["gate_failures"]] + [""]
    L += ["## 1. Inputs and protocol status", "", "| cell × batch | state | units ran / expected | state ok | branches | arm errors | unexposed | protocol_ok | pass | user calls | cost $ |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in R["runs"].items():
        if v["state"] != "finished":
            L.append(f"| {k} | {v['state']} ({v['branch_files']} branch files) | 0 / {v['expected_units']} | | | | | | | | |")
        else:
            u = v["user_llm_usage"] or {}
            L.append(f"| {k} | finished | {v['n_ran']} / {v['n_units']} | {v['n_state_ok']} | {v['n_branches']} | {v['n_arm_errors']} | "
                     f"{v['n_unexposed']} {v['unexposed_by_arm'] or ''} | {v['protocol_ok']} | {v['pass']} | {u.get('n_calls')} | {u.get('cost_usd', 0):.2f} |")
    I = R["integrity"]
    L += ["", f"Row re-verification failures: {len(R['row_failures'])}" + ("" if not R["row_failures"] else ": " + "; ".join(R["row_failures"][:10])), "",
          "Relay v2 checks over exposed branches: " + ", ".join(f"{c} {v['pass']}/{v['pass'] + v['fail']}" for c, v in I["v2_checks_over_exposed_branches"].items())
          + f". Request ids: {I['n_request_ids']} ({I['n_unique_request_ids']} unique; duplicates/non-v2: {I['request_id_duplicates_or_non_v2']}).", "",
          f"Original outcomes: admission re-run (units digests vs reference: "
          + ", ".join(f"{k} {'ok' if v['match'] else 'DIFF'}" for k, v in R["original_meta"]["units_digest_check_vs_reference"].items())
          + f"); dev state + branch file sha vs manifest {R['original_meta']['dev_state_and_branch_file_sha_ok']}.", "",
          f"States: {R['state_counts']}.", ""]
    L += ["## 2. G/H/F/G−H: original vs Sonnet 5.5 on the same states", ""]
    for name, sc in R["scopes"].items():
        scope_tables(L, sc, name)
    L += ["## 3. Within-simulator variability and agreement with the original", "",
          "Share of states whose 5 Sonnet replicates of the arm are not all equal (exact 95%). This is sampling variability of the "
          "new simulator; it is not an off-diagonal share and is not comparable with W93's 26.9%.", ""]
    main = R["scopes"][R["primary_scope"]]
    if main.get("n_states"):
        cols = main["cells"] + ["all"]
        L += ["| arm | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
        for a in ARMS:
            L.append(f"| {a} | " + " | ".join(f"{main['variability'][a][c]['disagree']}/{main['variability'][a][c]['n']} "
                                                f"{main['variability'][a][c]['ci95']}" for c in cols) + " |")
        L += ["", "Distribution of the number of successful replicates (0–5) per state, all cells: "
              + "; ".join(f"{a} {main['variability'][a]['all']['n_rep_success_dist']}" for a in ARMS), "",
              "Per-state agreement, original single-run outcome vs Sonnet arm mean (all cells pooled; Pearson r with a stratified bootstrap 95% CI):", "",
              "| arm | r [95%] | orig = 1 / 0 (states) | Sonnet mean given orig 1 | given orig 0 | mean abs diff | orig rate | Sonnet rate |", "|---|---|---|---|---|---|---|---|"]
        for a, v in main["correlation_original_vs_sonnet"].items():
            L.append(f"| {a} | {v['pearson_r']} {v['ci95']} | {v['n_orig_1']} / {v['n_orig_0']} | {v['sonnet_mean_given_orig_1']} | "
                     f"{v['sonnet_mean_given_orig_0']} | {v['mean_abs_diff']} | {v['orig_rate']} | {v['sonnet_rate']} |")
        L.append("")
    L += ["## 4. Unexposed branches and sensitivity", ""]
    O = R["ops"]
    L += ["| arm | unexposed branches | states with any (exact 95%) |", "|---|---|---|"]
    for a, v in O["unexposed"].items():
        L.append(f"| {a} | {v['branches']}/{v['n_branches']} | {v['states_with_any']}/{v['n_states']} {v['states_ci95']} |")
    if main.get("n_states"):
        for k, v in main["sensitivity"].items():
            if isinstance(v["estimands"], str):
                L += ["", f"{k}: {v['estimands']}."]
            else:
                L += ["", f"{k} (n = {v['n_states']}, excluded {v['n_excluded']}), pool: "
                      + "; ".join(f"{LABEL[e]} Sonnet {fmt(v['estimands'][e]['sonnet'].get('pool'))}" for e in ("G", "H", "F", "GmH"))]
    L += ["", "## 5. Operations", "", "| arm | termination | user calls total / mean / median / max | branches with 0 calls | missing replicates |", "|---|---|---|---|---|"]
    for a in ARMS:
        c = O["user_calls"][a]
        L.append(f"| {a} | {O['termination'][a]} | {c['total']} / {c['mean']} / {c['median']} / {c['max']} | {c['zero']} | {O['missing_replicates'][a]} |")
    L += ["", f"Context-overflow branches: {O['context_overflow_branches']}; budget-check failures: {O['budget_check_failures']}. "
          f"Sonnet usage: {O['n_calls']} calls, ${O['cost_usd']:.2f} (${O['cost_per_call']} per call).", "",
          "## 6. Caveats (protocol §9)", ""] + [f"- {c}" for c in CAVEATS] + [""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", default="analysis/fork/simctrl_p")
    ap.add_argument("--batches", default="1,2", help="batches expected for a final analysis (default 1,2)")
    ap.add_argument("--allow-partial", action="store_true", help="run despite gate failures; output labelled INTERIM")
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    t0 = time.time()
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    man_sha = sha_file(ROOT / MAN)
    if man_sha != FROZEN_SHA:
        raise SystemExit(f"{MAN}: sha {man_sha} != frozen {FROZEN_SHA}")
    man = json.loads((ROOT / MAN).read_text())
    Rn = int(man["replicates"])
    batches = [int(b) for b in a.batches.split(",")]
    rows, gate_fail, runs, inputs = load_runs(ROOT / a.dir, batches, man, man_sha)
    units = [u for u in man["units"] if u["batch"] in batches]
    row_fail, integ = verify_rows(units, rows, Rn)
    gate_fail = gate_fail + [f"row check: {f}" for f in row_fail]
    if gate_fail and not a.allow_partial:
        raise SystemExit("protocol gate failed (use --allow-partial for an INTERIM look):\n  " + "\n  ".join(gate_fail[:40]))
    interim = bool(gate_fail)
    orig, ometa = original_outcomes(man)
    states = [state_record(u, rows.get(u["unit_id"]), orig[u["unit_id"]], Rn) for u in units]
    sc = collections.Counter(s["status"] for s in states)
    scopes = {}
    present = sorted({s["batch"] for s in states if s["status"] == "ok"})
    if len(present) > 1:
        scopes["all batches (" + "+".join(f"b{b}" for b in present) + ")"] = analyse_scope(states, a.B)
    scopes["batch 1 (pre-planned)"] = analyse_scope([s for s in states if s["batch"] == 1], a.B)
    if 2 in present:
        scopes["batch 2"] = analyse_scope([s for s in states if s["batch"] == 2], a.B)
    primary = next(iter(scopes))
    O = ops(states, Rn)
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    git = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    inputs[MAN] = man_sha
    P = scopes[primary]
    if P.get("n_states"):
        pool = lambda e, k: P["estimands"][e][k]["pool"]  # noqa: E731
        tl = (f"{'INTERIM look, ' if interim else ''}{P['n_states']} complete states in {len(P['cells'])} of 4 cells ({primary}). "
              "Pooled, original → Sonnet 5.5 (pp, [95% state bootstrap]): "
              + "; ".join(f"{LABEL[e]} {fmt(pool(e, 'original'))} → {fmt(pool(e, 'sonnet'))} (change {fmt(pool(e, 'change'))})"
                          for e in ("G", "H", "F", "GmH")) + ". Robustness check only; per-cell tables below.")
    else:
        tl = "No complete states."
    unexp_tot = sum(v["branches"] for v in O["unexposed"].values())
    res = {"script": "analysis/fork/analyze_simctrl_p.py", "script_sha256": sha_file(__file__), "git_head": git, "utc": utc,
           "interim": interim, "gate_failures": gate_fail, "manifest": MAN, "manifest_sha256": man_sha, "batches_expected": batches,
           "replicates": Rn, "B": a.B, "seed": SEED, "inputs": inputs, "runs": runs, "row_failures": row_fail, "integrity": integ,
           "original_meta": ometa, "state_counts": dict(sc), "primary_scope": primary, "scopes": scopes, "ops": O,
           "notation": {e: f"Ybar_{x} - Ybar_{y}" for e, (x, y) in EST.items()}, "caveats": CAVEATS, "tldr": tl,
           "data_line": f"{sc.get('ok', 0)}/{len(units)} expected states complete ({dict(sc)}); "
                        + ", ".join(f"{k} {v['state']}" for k, v in runs.items()) + ".",
           "integrity_line": (f"row re-verification failures {len(row_fail)}; v2 checks "
                              + ("all pass" if all(v["fail"] == 0 for v in integ["v2_checks_over_exposed_branches"].values()) else "FAILURES")
                              + f" over {integ['v2_checks_over_exposed_branches']['v2_integrity_ok']['pass'] + integ['v2_checks_over_exposed_branches']['v2_integrity_ok']['fail']} exposed branches; "
                              f"{integ['n_unique_request_ids']} unique request ids; missing replicates {sum(O['missing_replicates'].values())}."),
           "unexposed_line": f"{unexp_tot} unexposed branches ({ {k: v['branches'] for k, v in O['unexposed'].items()} }); Y kept.",
           "states": [{k: s.get(k) for k in ("unit_id", "cell_label", "batch", "domain", "task_id", "state_id", "divergence_type", "status",
                                             "orig", "reps", "unexposed", "n_missing_rep")} for s in states],
           "seconds": round(time.time() - t0, 1)}
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"simctrl_p{'_interim' if interim else ''}{'_' + a.tag if a.tag else ''}_{utc}"
    (OUT / f"{stem}.json").write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    (OUT / f"{stem}.md").write_text(markdown(res))
    print(f"analysis/fork/out/{stem}.json")
    print(f"analysis/fork/out/{stem}.md")
    if interim:
        print(f"INTERIM: {len(gate_fail)} gate failures")


if __name__ == "__main__":
    main()
