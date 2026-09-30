"""Fork development analysis (protocol fork-v1, deterministic protocol A): coverage, rescue/damage table, G, A/C/I.

Estimands (docs/insights/EXTERNAL_REVIEW_GPT61_20260930.md §E; FORK_PROTOCOL.md §6c). Unit = task x block (one Q
closed-loop episode of a cell on one nonce). Y = success: retail/airline DB success (db_match and a normal
user_stop/agent_stop ending), telecom official task-basis success (official_reward == 1). L = 1 - Y. At the unit's
primary state (first semantic action divergence along Q's history, frozen before branches ran):
  G  = E[Y_BQ - Y_QQ] = h - b     h = P(Y_BQ=1, Y_QQ=0) rescue,  b = P(Y_BQ=0, Y_QQ=1) new damage
  A  = L_QB - L_BB     C = L_BQ - L_BB     I = L_QQ - L_QB - L_BQ + L_BB      L_QQ - L_BB = A + C + I
Y_QQ is the original episode (no-op replay verified on a 10% sample per fork task). Units without a primary divergence
enter with all four branches equal to the original outcome (zero effect). Excluded units (search / branch
infrastructure failures, Q block not admitted in the snapshot, quarantined fork task) leave the denominator and are
counted per reason; they are never coded as "no divergence".
  G_all (primary)       mean over the full task pool: task-level mean over its blocks, then the mean over tasks.
  G_div (secondary)     ratio form over divergent units only (sum of effects / number of states).
Intervals: hierarchical percentile bootstrap, tasks with replacement, then blocks with replacement within each drawn
task, B = 2000, seed 20261001. The draws are shared by all cells (tasks and nonces are crossed across cells), so the
pooled estimates (pre-declared equal weight per cell, within model and overall) carry valid intervals.
Thresholds (§F): g_min = eps = 3 pp. The lower one-sided 95% bound (5th percentile) is reported with flags
LB > 0 and LB > 3 pp. 5 pp is a sensitivity analysis only.
Quarantine (protocol A): a fork task (output directory) with any QQ no-op sample differing from its original
(suffix messages, prompt ids, termination, outcome, counters) is dropped whole and listed.
Divergence types: act->talk, talk->act, tool name, tool args, user-side device call (telecom: Q or B calls a tool that
belongs to the user's device toolset), other (tool count / order, stop, parse failure, invalid tool / args).

Pools: equal weight per cell within pre-declared families (W4 = gptq_w4_d1 + awq_w4; KV8 = kvq_int8; stress =
gptq_w3 + kvq_int4_rot), per model and across models; families are never pooled together.
Inputs: every directory under analysis/fork/{dev,kv,stress,restore,holdout}/ that holds search.json + states/ + branches/
(--include-gate also reads analysis/fork/gate/, whose states were selected, not searched over the full pool, for
testing only). Cell/model/block come from the Q run id a6k2_<model>_<cell>_<block>. The Q block (run, domain) must be
admitted (frozen) in the integrity-gated snapshot, and its trajectory.jsonl must still have the snapshot's sha256.
Idempotent: an output with the same input fingerprint (script, snapshot, every input file sha) is not rewritten.

usage: python analysis/fork/analyze_dev.py --snapshot <snapshot.json> [--cells gptq_w4_d1 awq_w4 ...] [--include-gate]
-> analysis/fork/out/dev_[gatetest_]<cells|all>_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis/fork/out"
ROOTS = ["analysis/fork/dev", "analysis/fork/kv", "analysis/fork/stress", "analysis/fork/telecom", "analysis/fork/restore", "analysis/fork/holdout"]
# Pre-declared pooling families (equal weight per cell within a family; families are never pooled together).
FAMILIES = {"W4": ("gptq_w4_d1", "awq_w4"), "KV8": ("kvq_int8",), "stress": ("gptq_w3", "kvq_int4_rot", "kvq_int4")}


def family(cell: str) -> str:
    return next((f for f, cs in FAMILIES.items() if cell in cs), "other")
B_BOOT, SEED, G_MIN = 2000, 20261001, 0.03
RUN_RE = re.compile(r"^a6k2_(q\d+|l8|m24)_(.+)_(q\d+|f\d\d|n\d+|h\d+)$")
TYPES = ["act->talk", "talk->act", "tool_name", "tool_args", "user_device_call", "other"]


def sha256(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def success(domain: str, rec: dict) -> int:
    if domain == "telecom":
        return int(rec.get("official_reward") == 1.0)
    return int(bool(rec.get("db_match")) and rec.get("termination_reason", rec.get("termination")) in ("user_stop", "agent_stop"))


_UT: dict = {}


def user_tools(domain: str) -> set:
    if domain not in _UT:
        names = set()
        if domain == "telecom":
            try:
                sys.path.insert(0, str(ROOT))
                from tau2.runner.build import build_environment
                env = build_environment("telecom")
                names = {t.name for t in (env.get_user_tools() or [])}
            except Exception:
                names = set()
        _UT[domain] = names
    return _UT[domain]


def dtype(st: dict) -> str:
    d = st.get("divergence") or {}
    cat = d.get("category") or ""
    names = {c.split('"name":"')[1].split('"')[0] for c in (d.get("q_calls") or []) + (d.get("b_calls") or []) if '"name":"' in c}
    if st["domain"] == "telecom" and names & user_tools("telecom"):
        return "user_device_call"
    if cat == "class:act->talk":
        return "act->talk"
    if cat == "class:talk->act":
        return "talk->act"
    if cat in ("tool_name", "tool_args"):
        return cat
    return "other"


def noop_ok(st: dict, r: dict) -> tuple[bool, dict]:
    if "error" in r:
        return False, {"error": r["error"]}
    o = st["orig"]
    prompts = [d["prompt_ids_sha"] for d in r.get("decisions", [])]
    c = {"suffix": r.get("suffix_sha") == o["suffix_sha"], "prompts": prompts == o["suffix_prompt_ids_sha"],
         "termination": r.get("termination_reason") == o["termination_reason"],
         "outcome": success(st["domain"], r) == success(st["domain"], {**o, "termination_reason": o["termination_reason"]}),
         "counters": [r.get("step_count_final"), r.get("num_errors_final")] == list(o["budget_final"])}
    return all(c.values()), c


# ----------------------------------------------------------------------------
# loading
# ----------------------------------------------------------------------------


def discover(include_gate: bool) -> list[Path]:
    roots = ROOTS + (["analysis/fork/gate"] if include_gate else [])
    out = []
    for r in roots:
        for p in sorted(glob.glob(str(ROOT / r / "**" / "search.json"), recursive=True)):
            d = Path(p).parent
            if (d / "states").is_dir() and (d / "branches").is_dir():
                out.append(d)
    return out


def load_dir(d: Path, snap: dict, traj_sha_cache: dict) -> dict:
    """Units of one fork output directory, with its quarantine status and input file hashes."""
    s = json.load(open(d / "search.json"))
    rows = s["rows"] if isinstance(s, dict) else s
    files = {str((d / "search.json").relative_to(ROOT)): sha256(d / "search.json")}
    bfiles = {}
    for p in sorted((d / "branches").glob("*.json")):
        stem = p.stem
        sid = stem.split("_")[0]
        kind = stem[len(sid) + 1:] if "_" in stem else ""
        if kind in ("", "fwd"):  # dev: <sid>.json; gate: <sid>_fwd.json (rev/conc/bbnoop are gate-only checks)
            bfiles[sid] = p
    units, noop = [], []
    for row in rows:
        if not isinstance(row, dict) or "run_id" not in row:
            continue
        m = RUN_RE.match(row["run_id"])
        if not m:
            continue
        model, cell, block = m.groups()
        cell = cell[4:] if cell.startswith("tel_") else cell  # telecom runs a6k2_<m>_tel_<cell>_<blk>: same cell, domain telecom
        dom = row["domain"]
        u = {"dir": str(d.relative_to(ROOT)), "model": model, "cell": cell, "block": block, "domain": dom,
             "task": f"{dom}:{row['task_id']}", "run_id": row["run_id"], "n_decisions": row.get("n_decisions")}
        fr = (snap["frozen"].get(row["run_id"]) or {}).get(dom)
        if fr is None:
            units.append({**u, "excluded": f"Q block {row['run_id']}/{dom} not admitted in snapshot"})
            continue
        key = (row["run_id"], dom)
        if key not in traj_sha_cache:
            tp = ROOT / "runs" / row["run_id"] / dom / "trajectory.jsonl"
            traj_sha_cache[key] = sha256(tp) if tp.exists() else None
        if traj_sha_cache[key] != fr["files"]["trajectory.jsonl"]["sha256"]:
            units.append({**u, "excluded": "trajectory.jsonl differs from the snapshot"})
            continue
        if row.get("exclusion") or "error" in row:
            units.append({**u, "excluded": f"search: {row.get('exclusion') or row.get('error')}"[:200]})
            continue
        y0 = success(dom, {"db_match": row.get("orig_db_match"), "official_reward": row.get("orig_official_reward"),
                           "termination_reason": row.get("orig_termination")})
        if row.get("t_star") is None:
            units.append({**u, "div": False, "Y": {"QQ": y0, "BB": y0, "BQ": y0, "QB": y0}})
            continue
        sid = row["state_id"]
        sp = d / "states" / f"{sid}.json"
        if sid not in bfiles or not sp.exists():
            units.append({**u, "excluded": "state without branches"})
            continue
        st = json.load(open(sp))
        r4 = json.load(open(bfiles[sid]))
        files[str(sp.relative_to(ROOT))] = sha256(sp)
        files[str(bfiles[sid].relative_to(ROOT))] = sha256(bfiles[sid])
        yq = success(dom, {**st["orig"], "termination_reason": st["orig"]["termination_reason"]})
        if yq != y0:
            units.append({**u, "excluded": "state orig outcome != search row outcome"})
            continue
        bad = [b for b in ("BB", "BQ", "QB") if b not in r4 or "error" in r4[b]]
        if bad:
            units.append({**u, "excluded": f"branch error {bad}"})
            continue
        if "QQ" in r4:
            ok, chk = noop_ok(st, r4["QQ"])
            noop.append({"state_id": sid, "ok": ok, "checks": chk})
        Y = {"QQ": yq, **{b: success(dom, r4[b]) for b in ("BB", "BQ", "QB")}}
        units.append({**u, "div": True, "state_id": sid, "t": st["decision_idx"], "type": dtype(st),
                      "category": st["divergence"]["category"], "steps_left": st["budget"]["steps_left"],
                      "errors_left": st["budget"]["errors_left"], "Y": Y})
    quarantined = any(not x["ok"] for x in noop)
    return {"dir": str(d.relative_to(ROOT)), "units": units, "noop": noop, "quarantined": quarantined, "files": files}


# ----------------------------------------------------------------------------
# estimation
# ----------------------------------------------------------------------------


def effects(Y: dict) -> dict:
    L = {k: 1 - v for k, v in Y.items()}
    return {"G": Y["BQ"] - Y["QQ"], "rescue": int(Y["BQ"] == 1 and Y["QQ"] == 0), "damage": int(Y["BQ"] == 0 and Y["QQ"] == 1),
            "both_succeed": int(Y["BQ"] == 1 and Y["QQ"] == 1), "both_fail": int(Y["BQ"] == 0 and Y["QQ"] == 0),
            "A": L["QB"] - L["BB"], "C": L["BQ"] - L["BB"], "I": L["QQ"] - L["QB"] - L["BQ"] + L["BB"],
            "Y_QQ": Y["QQ"], "Y_BB": Y["BB"], "Y_BQ": Y["BQ"], "Y_QB": Y["QB"]}


STATS = ["G", "rescue", "damage", "both_succeed", "both_fail", "A", "C", "I", "Y_QQ", "Y_BB", "Y_BQ", "Y_QB"]


class Boot:
    """Shared hierarchical draws: tasks with replacement, then blocks with replacement within each drawn task."""

    def __init__(self, tasks: list[str], blocks_of: dict[str, list[str]], B: int = B_BOOT, seed: int = SEED):
        self.tasks = tasks
        self.tix = {t: i for i, t in enumerate(tasks)}
        self.blocks = sorted({b for v in blocks_of.values() for b in v})
        self.bix = {b: i for i, b in enumerate(self.blocks)}
        T, K = len(tasks), len(self.blocks)
        rng = np.random.default_rng(seed)
        self.W = np.zeros((B, T))  # task multiplicity
        self.V = np.zeros((B, T, K))  # block multiplicity within task
        avail = [[self.bix[b] for b in sorted(blocks_of[t])] for t in tasks]
        for r in range(B):
            self.W[r] = np.bincount(rng.integers(0, T, T), minlength=T)
            for t in range(T):
                a = avail[t]
                if a:
                    self.V[r, t, a] = np.bincount(rng.integers(0, len(a), len(a)), minlength=len(a))
        self.W1 = np.ones(T)
        self.V1 = np.zeros((T, K))
        for t in range(T):
            self.V1[t, avail[t]] = 1

    def arrays(self, units: list[dict], key: str, mask_key=None):
        T, K = len(self.tasks), len(self.blocks)
        X, M = np.zeros((T, K)), np.zeros((T, K))
        for u in units:
            if mask_key and not u.get(mask_key):
                continue
            t, k = self.tix[u["task"]], self.bix[u["block"]]
            X[t, k] = u["E"][key]
            M[t, k] = 1
        return X, M

    def task_mean(self, X, M):
        """Point estimate and bootstrap draws of the task-hierarchical mean."""
        def est(W, V):
            den_tk = (V * M).sum(-1)
            tm = np.where(den_tk > 0, (V * M * X).sum(-1) / np.maximum(den_tk, 1e-12), 0.0)
            wt = W * (den_tk > 0)
            return (wt * tm).sum(-1) / np.maximum(wt.sum(-1), 1e-12)
        return float(est(self.W1, self.V1)), est(self.W, self.V)

    def ratio(self, X, M):
        """Ratio form over the masked units (secondary, conditional on divergence)."""
        def est(W, V):
            wv = W[..., None] * V
            return (wv * M * X).sum((-1, -2)) / np.maximum((wv * M).sum((-1, -2)), 1e-12)
        return float(est(self.W1, self.V1)), est(self.W, self.V)


def summarise(pt: float, draws: np.ndarray, pct: bool = True) -> dict:
    lo, hi = np.percentile(draws, [2.5, 97.5])
    lb = np.percentile(draws, 5)
    f = 100 if pct else 1
    return {"est": round(float(f * pt), 3), "ci95": [round(float(f * lo), 3), round(float(f * hi), 3)], "lb95_one_sided": round(float(f * lb), 3)}


def analyse(units: list[dict], boot: Boot, draws_out: dict | None = None, label: str = "") -> dict:
    div = [u for u in units if u["div"]]
    res = {"n_units": len(units), "n_tasks": len({u["task"] for u in units}), "n_blocks": len({u["block"] for u in units}),
           "n_states": len(div), "divergence_rate": round(len(div) / len(units), 4) if units else None}
    if not units:
        return res
    all_ = {}
    for s in STATS:
        X, M = boot.arrays(units, s)
        pt, dr = boot.task_mean(X, M)
        all_[s] = summarise(pt, dr)
        if draws_out is not None:
            draws_out.setdefault(label, {})[s] = (pt, dr)
    res["all_pp"] = all_
    g = all_["G"]
    res["G_all_decision"] = {"lb_gt_0": bool(g["lb95_one_sided"] > 0), "lb_gt_gmin": bool(g["lb95_one_sided"] > 100 * G_MIN),
                             "ub_lt_minus_gmin": bool(g["ci95"][1] < -100 * G_MIN), "g_min_pp": 100 * G_MIN}
    if div:
        cond = {}
        for s in ("G", "rescue", "damage", "both_succeed", "both_fail", "A", "C", "I"):
            X, M = boot.arrays(div, s)
            pt, dr = boot.ratio(X, M)
            cond[s] = summarise(pt, dr)
        res["conditional_on_divergence_pp"] = cond
        res["counts"] = {k: int(sum(u["E"][k] for u in div)) for k in ("rescue", "damage", "both_succeed", "both_fail")}
        ts = np.array([u["t"] for u in div])
        rel = np.array([u["t"] / max(1, u["n_decisions"] or 1) for u in div])
        res["t_star"] = {"quantiles": {str(q): float(np.quantile(ts, q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)},
                         "hist": {str(k): int(v) for k, v in zip(*np.unique(ts, return_counts=True))},
                         "rel_median": round(float(np.median(rel)), 3)}
        res["steps_left_median"] = float(np.median([u["steps_left"] for u in div]))
        res["errors_left_median"] = float(np.median([u["errors_left"] for u in div]))
    return res


def breakdown(units: list[dict], boot: Boot, field: str, levels: list[str]) -> dict:
    """Per divergence type / domain: counts, conditional effects, and the share of G_all it contributes."""
    out = {}
    div = [u for u in units if u["div"]]
    for lv in levels:
        sub = [u for u in div if u.get(field) == lv]
        if not sub:
            continue
        r = {"n_states": len(sub), "counts": {k: int(sum(u["E"][k] for u in sub)) for k in ("rescue", "damage", "both_succeed", "both_fail")}}
        for s in ("G", "A", "C", "I"):
            X, M = boot.arrays(sub, s)
            pt, dr = boot.ratio(X, M)
            r[f"{s}_cond_pp"] = summarise(pt, dr)
        # contribution to G_all: effect of this type's units, all other units counted as zero
        zu = [{**u, "E": {**u["E"], "G": u["E"]["G"] if (u["div"] and u.get(field) == lv) else 0}} for u in units]
        X, M = boot.arrays(zu, "G")
        pt, dr = boot.task_mean(X, M)
        r["G_all_contribution_pp"] = summarise(pt, dr)
        out[lv] = r
    return out


def pooled(draws: dict, labels: list[str]) -> dict:
    """Equal-weight pool over cells (pre-declared), on the shared bootstrap draws."""
    out = {}
    for s in ("G", "rescue", "damage", "A", "C", "I"):
        pts = [draws[l][s][0] for l in labels if l in draws]
        drs = [draws[l][s][1] for l in labels if l in draws]
        if pts:
            out[s] = summarise(float(np.mean(pts)), np.mean(drs, axis=0))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--cells", nargs="*", default=None)
    ap.add_argument("--include-gate", action="store_true", help="also read analysis/fork/gate (selected states; testing only)")
    ap.add_argument("--B", type=int, default=B_BOOT)
    a = ap.parse_args()
    t0 = time.time()
    try:  # tau2 (imported for the telecom user-tool list) logs at INFO on import
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    snap = json.load(open(a.snapshot))
    dirs = discover(a.include_gate)
    cache: dict = {}
    loaded = [load_dir(d, snap, cache) for d in dirs]
    units_all = [u for L in loaded for u in L["units"]]
    known = sorted({u["cell"] for u in units_all})
    if a.cells:
        miss = [c for c in a.cells if c not in known]
        if miss:
            print(f"analyze_dev: no fork outputs for cell(s) {miss} yet (cells with outputs: {known or 'none'}); nothing to do.")
        loaded_f = [{**L, "units": [u for u in L["units"] if u["cell"] in a.cells]} for L in loaded]
        loaded = [L for L in loaded_f if L["units"]]
        if not loaded:
            return
    if not loaded:
        print(f"analyze_dev: no fork output directories under {ROOTS}{' + gate' if a.include_gate else ''}; nothing to do.")
        return
    tag = ("gatetest_" if a.include_gate else "") + ("_".join(sorted(a.cells)) if a.cells else "all")
    script_sha = sha256(__file__)
    files = {k: v for L in loaded for k, v in L["files"].items()}
    fp = hashlib.sha256(json.dumps({"script": script_sha, "snapshot": sha256(a.snapshot), "files": files, "cells": a.cells,
                                    "gate": a.include_gate, "B": a.B}, sort_keys=True).encode()).hexdigest()[:16]
    OUT.mkdir(parents=True, exist_ok=True)
    for p in sorted(OUT.glob(f"dev_{tag}_*.json")):
        try:
            if json.load(open(p)).get("input_fingerprint") == fp:
                print(f"analyze_dev: unchanged inputs (fingerprint {fp}); existing output {p.relative_to(ROOT)}")
                return
        except Exception:
            continue
    quarantine = [L["dir"] for L in loaded if L["quarantined"]]
    units, seen, dups = [], set(), 0
    for L in loaded:  # a unit (Q run, domain, task) found in several output dirs is counted once (first dir, sorted)
        if L["quarantined"]:
            continue
        for u in L["units"]:
            k = (u["run_id"], u["domain"], u["task"])
            if k in seen:
                dups += 1
                continue
            seen.add(k)
            units.append(u)
    excluded = [u for u in units if "excluded" in u]
    ok = [u for u in units if "excluded" not in u]
    for u in ok:
        u["E"] = effects(u["Y"])
    # shared draws over the union of tasks and their blocks (crossed across cells)
    blocks_of: dict = defaultdict(set)
    for u in ok:
        blocks_of[u["task"]].add(u["block"])
    tasks = sorted(blocks_of)
    boot = Boot(tasks, {t: sorted(v) for t, v in blocks_of.items()}, B=a.B)
    draws: dict = {}
    cells = sorted({(u["model"], u["cell"]) for u in units})
    res_cells = {}
    for m, c in cells:
        cu = [u for u in ok if u["model"] == m and u["cell"] == c]
        lab = f"{m}:{c}"
        r = analyse(cu, boot, draws, lab)
        r["by_type"] = breakdown(cu, boot, "type", TYPES)
        r["by_domain"] = {d: analyse([u for u in cu if u["domain"] == d], boot) for d in sorted({u["domain"] for u in cu})}
        ex = defaultdict(int)
        for u in excluded:
            if u["model"] == m and u["cell"] == c:
                ex[u["excluded"].split(":")[0] if u["excluded"].startswith(("search", "branch error")) else u["excluded"]] += 1
        r["excluded"] = dict(ex)
        r["coverage"] = {"units_searched": len(cu) + sum(ex.values()), "units_analysed": len(cu), "states": r["n_states"],
                         "tasks": r["n_tasks"], "blocks": sorted({u["block"] for u in cu}),
                         "domains": {d: sum(1 for u in cu if u["domain"] == d) for d in sorted({u["domain"] for u in cu})}}
        res_cells[lab] = r
    models = sorted({m for m, _ in cells})
    pools = {}
    for fam in sorted({family(c) for _, c in cells}):
        fc = [(m, c) for m, c in cells if family(c) == fam]
        for m in models:
            labs = [f"{mm}:{c}" for mm, c in fc if mm == m]
            if labs:
                pools[f"{fam}:{m}:pooled_equal_weight"] = pooled(draws, labs)
        pools[f"{fam}:all:pooled_equal_weight"] = pooled(draws, [f"{m}:{c}" for m, c in fc])
    noop = [x for L in loaded for x in L["noop"]]
    res = {
        "protocol": "fork-v1 / protocol A", "analysis": "analysis/fork/analyze_dev.py", "input_fingerprint": fp,
        "snapshot": {"id": snap.get("snapshot_id"), "path": str(Path(a.snapshot).resolve()), "sha256": sha256(a.snapshot)},
        "script": {"path": str(Path(__file__).resolve()), "sha256": script_sha,
                   "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()},
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cells_filter": a.cells, "include_gate": a.include_gate,
        "bootstrap": {"B": a.B, "seed": SEED, "scheme": "tasks, then blocks within task; draws shared by all cells"},
        "thresholds": {"g_min_pp": 100 * G_MIN, "eps_pp": 100 * G_MIN, "sensitivity_pp": 5.0},
        "success_definition": {"retail/airline": "DB success (db_match and user_stop/agent_stop)", "telecom": "official task-basis success (official_reward == 1)"},
        "input_dirs": [L["dir"] for L in loaded], "quarantined_dirs": quarantine, "duplicate_units_dropped": dups,
        "noop_sample": {"n": len(noop), "n_pass": sum(x["ok"] for x in noop), "fails": [x for x in noop if not x["ok"]]},
        "cells": res_cells, "pooled": pools, "n_input_files": len(files), "input_files": files,
        "seconds": round(time.time() - t0, 1),
    }
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    jp = OUT / f"dev_{tag}_{utc}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    (OUT / f"dev_{tag}_{utc}.md").write_text(markdown(res, jp))
    print(f"analyze_dev: wrote {jp.relative_to(ROOT)} ({res['seconds']} s)")


def markdown(res: dict, jp: Path) -> str:
    def f(x):
        return f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}]"
    cells = res["cells"]
    tl = "; ".join(f"{k} G_all {f(v['all_pp']['G'])} pp (states {v['n_states']}/{v['n_units']})" for k, v in cells.items() if "all_pp" in v)
    L = [f"**TL;DR** Fork development analysis{' (INCLUDES GATE STATES: testing only)' if res['include_gate'] else ''}: {tl}. "
         f"No-op sample {res['noop_sample']['n_pass']}/{res['noop_sample']['n']}; quarantined dirs {len(res['quarantined_dirs'])}.",
         "", f"# Fork development analysis ({res['utc']})", "",
         f"Snapshot `{res['snapshot']['id']}` (sha {res['snapshot']['sha256'][:12]}), script sha {res['script']['sha256'][:12]}, "
         f"git {res['script']['git_head'][:10]}, fingerprint {res['input_fingerprint']}. Full numbers: `{jp.relative_to(ROOT)}`.",
         "Units = task x block; percentages in pp; 95% hierarchical bootstrap (tasks, blocks within task), B = "
         f"{res['bootstrap']['B']}. G_all is the primary endpoint (g_min = eps = 3 pp).", "",
         "| cell | units | states | G_all | rescue | damage | A | C | I | LB>0 | LB>3pp |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in cells.items():
        if "all_pp" not in v:
            continue
        a = v["all_pp"]
        L.append(f"| {k} | {v['n_units']} | {v['n_states']} | {f(a['G'])} | {a['rescue']['est']:.1f} | {a['damage']['est']:.1f} | "
                 f"{f(a['A'])} | {f(a['C'])} | {f(a['I'])} | {v['G_all_decision']['lb_gt_0']} | {v['G_all_decision']['lb_gt_gmin']} |")
    L += ["", "| pool (equal weight) | G_all | A | C | I |", "|---|---|---|---|---|"]
    for k, v in res["pooled"].items():
        if v:
            L.append(f"| {k} | {f(v['G'])} | {f(v['A'])} | {f(v['C'])} | {f(v['I'])} |")
    L += ["", "Consequence composition (divergent units: rescue / new damage / both succeed / both fail) and type breakdown:"]
    for k, v in cells.items():
        if v.get("counts"):
            L.append(f"- {k}: {v['counts']}; t* median {v['t_star']['quantiles']['0.5']}; excluded {v['excluded'] or 'none'}")
            for t, b in v["by_type"].items():
                L.append(f"  - {t}: n {b['n_states']}, {b['counts']}, G|type {f(b['G_cond_pp'])}, contribution to G_all {f(b['G_all_contribution_pp'])}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
