"""Bank U analysis (FORK_PROTOCOL §15 + amendment 1; W84; GPT-6.1 review 4 points 2/5/9 and the Feynman response review).

Inputs (discovered, so the script reruns unchanged when f02/f03 land):
  analysis/fork/bank_u/<model>_<cell>/<block>/bank_rows.jsonl (+ bank_summary.json, branches/)   native four arms
  analysis/fork/bank_u/q0/<model>_<cell>/<block>/q0_rows.jsonl (+ q0_summary.json)              common Q0 controller
  manifests/fork/bank_u_v1.json                                                                   frozen sampling manifest
A block directory is used only when its summary file exists (a finished task). The gate/ directory is never read.

What is reported (never pooled across the three state sources U1 / U2B / U2Q):
  1. Per model x cell x sub-bank: rows, unique state_ids, tasks, blocks k; r, d, M, G (= Y_BQ - Y_QQ), A, C, I, H, F and
     the exact-agreement rate. Primary target: equal weight per task, one uniformly drawn decision within the task (the
     plain mean over tasks within a block, then the mean over blocks). NOT multiplied by n_decisions. The per-decision
     (n_decisions-weighted, Hajek) estimand is a labelled secondary (point estimate + task-bootstrap interval).
     Intervals: k = 1 -> task-cluster bootstrap only (one block; no run-level uncertainty is captured);
                2 <= k < 10 -> t over block means (primary) + task-cluster bootstrap (new-task);
                k >= 10 -> block bootstrap (primary) + task-cluster bootstrap.
     Unique states: the GPTQ-W4 d1 cell's U2Q rows are the same states as 20 of its U1 rows (U2Q is sourced from GPTQ
     trajectories). Each sub-bank's estimate uses its own unique states; duplicates are listed, their Y concordance is
     checked, and every descriptive table that spans a cell's sub-banks counts unique states only.
  2. Action-difference taxonomy a_B vs a_Q: (i) full canonical message identical; (ii) same tool structure (names+args,
     or both talk) but different text [ii_act: same tool calls, different content; ii_talk: talk/stop with different
     text; ws_only flagged]; (iii) both act, different tool name/args/count; (iv) act/talk (kind) differs. Consequence
     composition per class (rescue r, damage d, both succeed, both fail). Cross-tab with the comparator category
     (`text_only` is a comparator class: same kind and different text; it is not a semantic class).
  3. Content split of class (ii) text differences with cheap programmatic features (question, confirmation request,
     commitment/claim of action, new numbers/ids, length difference). Descriptive only: no tests.
  4. Q0: same states, same continuation controller Q0 = <model> GPTQ-W4 d1; G_Q0 = Y(a_B -> Q0) - Y(a_c -> Q0). For
     the GPTQ cell the native BQ/QQ are the Q0 arms. Native and Q0 reported separately, on the same rows. Small n.
  5. Cross-quantizer transfer on shared states (U2B, U2Q: same state_id across cells of a model): does the same state
     flip (M = 1) under different quantizers?

usage: python analysis/fork/analyze_bank_u.py [--boot 2000]
"""
from __future__ import annotations

import argparse
import collections
import glob
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from cloq.fork import action_view, canon_msg  # noqa: E402

BANK = ROOT / "analysis" / "fork" / "bank_u"
OUT = ROOT / "analysis" / "fork" / "out"
MANIFEST = ROOT / "manifests" / "fork" / "bank_u_v1.json"
SUBS = ("U1", "U2B", "U2Q")
CELLS = ("gptq_w4_d1", "awq_w4", "kvq_int8")
Q0_CELL = "gptq_w4_d1"
ARMS = ("BB", "BQ", "QB", "QQ")
STATS = ("r", "d", "M", "G", "A", "C", "I", "H", "F", "exact")


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sha_dir(d: Path) -> dict:
    fs = sorted(d.glob("*.json")) if d.is_dir() else []
    h = hashlib.sha256()
    for f in fs:
        h.update(f.name.encode() + b"\0" + hashlib.sha256(f.read_bytes()).digest())
    return {"n_files": len(fs), "sha256_of_sorted_name_and_sha": h.hexdigest()}


# ----------------------------------------------------------------------------------------------------------------------
# loading
# ----------------------------------------------------------------------------------------------------------------------

def load(inputs: dict) -> tuple[list[dict], list[dict], dict]:
    man_sha = sha_file(MANIFEST)
    inputs[rel(MANIFEST)] = man_sha
    native, q0, notes = [], [], {"skipped_dirs": [], "missing_rows": [], "manifest_sha256": man_sha}
    for d in sorted(BANK.glob("q*_*/f*")):
        if d.parts[-2] in ("gate", "q0"):
            continue
        rows_p, sum_p = d / "bank_rows.jsonl", d / "bank_summary.json"
        if not (rows_p.exists() and sum_p.exists()):
            notes["skipped_dirs"].append(rel(d) + " (no finished bank_summary.json)")
            continue
        summ = json.loads(sum_p.read_text())
        if summ.get("manifest_sha256") != man_sha:
            raise SystemExit(f"{sum_p}: manifest sha {summ.get('manifest_sha256')} != {man_sha}")
        for p in (rows_p, sum_p):
            inputs[rel(p)] = sha_file(p)
        inputs[rel((d / "branches"))] = sha_dir(d / "branches")
        for line in rows_p.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if "Y" not in r or any(r["Y"].get(a) is None for a in ARMS):
                notes["missing_rows"].append({k: r.get(k) for k in ("model", "cell", "sub", "block", "state_key", "missing_reason", "error")})
                continue
            native.append(r)
    for d in sorted((BANK / "q0").glob("q*_*/f*")):
        rows_p, sum_p = d / "q0_rows.jsonl", d / "q0_summary.json"
        if not (rows_p.exists() and sum_p.exists()):
            notes["skipped_dirs"].append(rel(d) + " (no finished q0_summary.json)")
            continue
        summ = json.loads(sum_p.read_text())
        if summ.get("manifest_sha256") != man_sha:
            raise SystemExit(f"{sum_p}: manifest sha mismatch")
        for p in (rows_p, sum_p):
            inputs[rel(p)] = sha_file(p)
        inputs[rel((d / "branches"))] = sha_dir(d / "branches")
        for line in rows_p.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if "Y" not in r or any(v is None for v in r["Y"].values()):
                notes["missing_rows"].append({"q0": True, **{k: r.get(k) for k in ("model", "cell", "sub", "block", "state_key", "missing_reason", "error")}})
                continue
            q0.append(r)
    return native, q0, notes


# ----------------------------------------------------------------------------------------------------------------------
# per-row quantities
# ----------------------------------------------------------------------------------------------------------------------

def effects(Y: dict) -> dict:
    A, C = Y["BB"] - Y["QB"], Y["BB"] - Y["BQ"]
    I = Y["BQ"] + Y["QB"] - Y["BB"] - Y["QQ"]
    G, H, F = Y["BQ"] - Y["QQ"], Y["QB"] - Y["QQ"], Y["BB"] - Y["QQ"]
    r, d = int(Y["BQ"] == 1 and Y["QQ"] == 0), int(Y["BQ"] == 0 and Y["QQ"] == 1)
    return {"r": r, "d": d, "M": r + d, "G": G, "A": A, "C": C, "I": I, "H": H, "F": F,
            "both_succeed": int(Y["BQ"] == 1 and Y["QQ"] == 1), "both_fail": int(Y["BQ"] == 0 and Y["QQ"] == 0)}


def taxonomy(a_b: dict, a_q: dict) -> dict:
    vb, vq = action_view(a_b, {}), action_view(a_q, {})
    if canon_msg(a_b) == canon_msg(a_q):
        cls, sub = "i", "i_identical"
    elif vb["kind"] != vq["kind"]:
        cls, sub = "iv", f"iv_{vq['kind']}->{vb['kind']}"  # Q kind -> B kind, as the comparator writes it
    elif vb["kind"] == "act" and [c["norm"] for c in vb["calls"]] != [c["norm"] for c in vq["calls"]]:
        nb, nq = [c["name"] for c in vb["calls"]], [c["name"] for c in vq["calls"]]
        cls, sub = "iii", "iii_name_or_count" if nb != nq else "iii_args"
    else:
        cls = "ii"
        sub = "ii_act" if vb["kind"] == "act" else "ii_talk"
    ws_only = cls == "ii" and vb["text"] == vq["text"]
    return {"cls": cls, "sub_cls": sub, "ws_only": ws_only, "kind_B": vb["kind"], "kind_Q": vq["kind"]}


def text_of(m: dict) -> str:
    return " ".join((m.get("content") or "").split())


RE_CONFIRM = re.compile(r"\b(confirm|confirmation|would you like (me )?to|shall i|do you want (me )?to|should i (proceed|go ahead)|"
                        r"(please )?(reply|respond|answer) (with )?['\"]?yes|yes or no|yes/no|\(yes\)|is (that|this) correct|"
                        r"are you sure|go ahead\?|proceed\?|can you verify)", re.I)
RE_CLAIM = re.compile(r"\b(i have|i've|has been|have been|was successfully|were successfully|is now|are now)\b[^.?!]{0,60}?"
                      r"\b(cancel|modif|updat|exchang|return|book|chang|process|transfer|refund|submit|plac|upgrad|remov|add|switch)", re.I)
RE_COMMIT = re.compile(r"\b(i will|i'll|let me|i am going to|i'm going to|i can now)\b[^.?!]{0,40}?"
                       r"\b(cancel|modif|updat|exchang|return|book|chang|process|transfer|refund|submit|plac|upgrad|remov|add|switch|proceed)", re.I)
RE_ENT = re.compile(r"[\w.+-]+@[\w.-]+|\$\s?\d[\d,]*(\.\d+)?|#?[A-Za-z]*\d[\w\-]*")


def entities(t: str) -> set:
    """Numbers, ids, emails and amounts; bare 1-2 digit numbers (list markers, quantities) are ignored."""
    out = {m.group(0).rstrip(".,").lower() for m in RE_ENT.finditer(t)}
    return {e for e in out if not re.fullmatch(r"\d{1,2}", e)}


def text_features(a_b: dict, a_q: dict) -> dict:
    tb, tq = text_of(a_b), text_of(a_q)
    f = {}
    for name, fn in (("question", lambda t: "?" in t), ("confirm_request", lambda t: bool(RE_CONFIRM.search(t))),
                     ("claim_done", lambda t: bool(RE_CLAIM.search(t))), ("commit_future", lambda t: bool(RE_COMMIT.search(t)))):
        xb, xq = fn(tb), fn(tq)
        f[name] = {"B": xb, "Q": xq, "differs": xb != xq}
    cb, cq = f["claim_done"], f["commit_future"]
    f["commit_or_claim"] = {"B": cb["B"] or cq["B"], "Q": cb["Q"] or cq["Q"]}
    f["commit_or_claim"]["differs"] = f["commit_or_claim"]["B"] != f["commit_or_claim"]["Q"]
    eb, eq = entities(tb), entities(tq)
    f["new_entity"] = {"B_only": sorted(eb - eq)[:8], "Q_only": sorted(eq - eb)[:8], "differs": eb != eq}
    lb, lq = len(tb), len(tq)
    f["length"] = {"B": lb, "Q": lq, "abs_diff": abs(lb - lq), "rel_diff": abs(lb - lq) / max(lb, lq, 1)}
    return f


# ----------------------------------------------------------------------------------------------------------------------
# estimation
# ----------------------------------------------------------------------------------------------------------------------

def task_key(r: dict) -> str:
    return f"{r['domain']}|{r['task_id']}"


def estimate(units: list[dict], stats: tuple, rng: np.random.Generator, nboot: int, weight: str | None = None) -> dict:
    """units: dicts with 'block', 'task', 'w' (n_decisions) and the stat columns. Primary: equal weight per task within a
    block, mean over blocks. weight='n_decisions': Hajek per-decision secondary."""
    if not units:
        return {"n": 0}
    blocks = sorted({u["block"] for u in units})
    k = len(blocks)
    tasks = sorted({u["task"] for u in units})
    X = {s: np.array([float(u[s]) for u in units]) for s in stats}
    w = np.array([float(u["w"]) if weight else 1.0 for u in units])
    bidx = np.array([blocks.index(u["block"]) for u in units])
    tidx = np.array([tasks.index(u["task"]) for u in units])

    def point(mult_task: np.ndarray | None = None, mult_block: np.ndarray | None = None) -> dict:
        ww = w * (mult_task[tidx] if mult_task is not None else 1.0)
        out = {}
        bm = {}
        for s in stats:
            vals = []
            for b in range(k):
                m = bidx == b
                den = ww[m].sum()
                vals.append((ww[m] * X[s][m]).sum() / den if den > 0 else np.nan)
            vals = np.array(vals)
            bm[s] = vals
            bw = mult_block if mult_block is not None else np.ones(k)
            ok = ~np.isnan(vals)
            out[s] = float((bw[ok] * vals[ok]).sum() / bw[ok].sum()) if bw[ok].sum() > 0 else float("nan")
        return out, bm

    pt, bmeans = point()
    res = {"n": len(units), "n_tasks": len(tasks), "k_blocks": k, "blocks": blocks, "point": {s: round(pt[s], 4) for s in stats}}
    # task-cluster bootstrap (resample tasks; each task brings all its rows in every block)
    T = len(tasks)
    draws = {s: [] for s in stats}
    for _ in range(nboot):
        mult = np.bincount(rng.integers(0, T, T), minlength=T).astype(float)
        p, _ = point(mult_task=mult)
        for s in stats:
            draws[s].append(p[s])
    res["task_boot_95"] = {s: [round(float(np.nanpercentile(draws[s], 2.5)), 4), round(float(np.nanpercentile(draws[s], 97.5)), 4)] for s in stats}
    if k == 1:
        res["interval_primary"] = "task-cluster bootstrap (k = 1 block: no run-level/block uncertainty captured)"
    elif k < 10:
        from statistics import mean, stdev
        tcrit = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306}[k - 1]
        res["t_over_blocks_95"] = {}
        for s in stats:
            v = [x for x in bmeans[s] if not math.isnan(x)]
            m, se = mean(v), stdev(v) / math.sqrt(len(v))
            res["t_over_blocks_95"][s] = [round(m - tcrit * se, 4), round(m + tcrit * se, 4)]
        res["interval_primary"] = f"t over k = {k} block means (df = {k - 1}); task bootstrap = new-task interval"
    else:
        bd = {s: [] for s in stats}
        for _ in range(nboot):
            mult = np.bincount(rng.integers(0, k, k), minlength=k).astype(float)
            p, _ = point(mult_block=mult)
            for s in stats:
                bd[s].append(p[s])
        res["block_boot_95"] = {s: [round(float(np.nanpercentile(bd[s], 2.5)), 4), round(float(np.nanpercentile(bd[s], 97.5)), 4)] for s in stats}
        res["interval_primary"] = f"block bootstrap over k = {k} blocks; task bootstrap = new-task interval"
    return res


def ci(res: dict, s: str) -> list:
    for key in ("block_boot_95", "t_over_blocks_95", "task_boot_95"):
        if key in res:
            return res[key][s]
    return [float("nan")] * 2


# ----------------------------------------------------------------------------------------------------------------------
# analyses
# ----------------------------------------------------------------------------------------------------------------------

def build_units(native: list[dict]) -> list[dict]:
    us = []
    for r in native:
        e = effects(r["Y"])
        tx = taxonomy(r["a_B"], r["a_Q"])
        u = {"model": r["model"], "cell": r["cell"], "sub": r["sub"], "block": r["block"], "task": task_key(r),
             "state_id": r["state_id"], "state_key": r["state_key"], "w": r["n_decisions"], "q0": r.get("q0"),
             "exact": int(bool(r["exact_agreement"])), "comparator": r["agreement_category"], "Y": r["Y"], **e, **tx,
             "a_B_canon": json.dumps(canon_msg(r["a_B"]), sort_keys=True), "a_Q_canon": json.dumps(canon_msg(r["a_Q"]), sort_keys=True)}
        if tx["cls"] == "ii":
            u["feat"] = text_features(r["a_B"], r["a_Q"])
        us.append(u)
    return us


def uniqueness(us: list[dict]) -> dict:
    out = {}
    by = collections.defaultdict(list)
    for u in us:
        by[(u["model"], u["cell"], u["block"])].append(u)
    for (m, c, b), g in sorted(by.items()):
        ids = collections.defaultdict(list)
        for u in g:
            ids[u["state_id"]].append(u)
        dups = {sid: v for sid, v in ids.items() if len(v) > 1}
        out[f"{m}:{c}:{b}"] = {
            "rows": len(g), "unique_states": len(ids),
            "per_sub": {s: {"rows": sum(1 for u in g if u["sub"] == s), "unique": len({u["state_id"] for u in g if u["sub"] == s})} for s in SUBS},
            "duplicate_states": len(dups), "duplicate_sub_pairs": dict(collections.Counter("+".join(sorted(x["sub"] for x in v)) for v in dups.values())),
            "duplicate_Y_concordant": sum(1 for v in dups.values() if all(x["Y"] == v[0]["Y"] for x in v)),
            "duplicate_action_concordant": sum(1 for v in dups.values() if all(x["a_B_canon"] == v[0]["a_B_canon"] and x["a_Q_canon"] == v[0]["a_Q_canon"] for x in v))}
    return out


def mark_unique_for_pools(us: list[dict]) -> None:
    """Within each model x cell x block, a state that appears in several sub-banks is counted once in tables that span
    sub-banks; it is kept in U1 (its own-trajectory population) when present, else in U2B, else U2Q."""
    seen = {}
    order = {s: i for i, s in enumerate(SUBS)}
    for u in sorted(us, key=lambda x: order[x["sub"]]):
        k = (u["model"], u["cell"], u["block"], u["state_id"])
        u["dup_of"] = seen.get(k)
        seen.setdefault(k, u["sub"])


def per_cell_estimates(us: list[dict], rng, nboot: int) -> dict:
    out = {}
    for m in ("q4", "q8"):
        for c in CELLS:
            for s in SUBS:
                g = [u for u in us if u["model"] == m and u["cell"] == c and u["sub"] == s]
                if not g:
                    continue
                key = f"{m}:{c}:{s}"
                prim = estimate(g, STATS, rng, nboot)
                prim["n_unique_states"] = len({(u["block"], u["state_id"]) for u in g})
                prim["n_rows_also_in_other_sub"] = sum(1 for u in g if u.get("dup_of"))
                sec = estimate(g, ("r", "d", "M", "G"), rng, nboot, weight="n_decisions")
                nd = [u for u in g if not u["exact"]]
                out[key] = {"primary_task_equal": prim,
                            "secondary_per_decision_n_decisions_weighted": {"point": sec["point"], "task_boot_95": sec["task_boot_95"]},
                            "counts": {"rescue": sum(u["r"] for u in g), "damage": sum(u["d"] for u in g), "non_exact": len(nd),
                                       "M_given_non_exact": round(sum(u["M"] for u in nd) / len(nd), 3) if nd else None}}
    return out


def taxonomy_tables(us: list[dict]) -> dict:
    def comp(g):
        z = collections.Counter()
        for u in g:
            z["n"] += 1
            z["rescue"] += u["r"]
            z["damage"] += u["d"]
            z["both_succeed"] += u["both_succeed"]
            z["both_fail"] += u["both_fail"]
        return dict(z)

    out = {"per_cell_sub": {}, "per_sub_pooled_over_cells": {}, "outcome_changes_by_class": {}, "comparator_crosstab": {}}
    for m in ("q4", "q8"):
        for c in CELLS:
            for s in SUBS:
                g = [u for u in us if u["model"] == m and u["cell"] == c and u["sub"] == s]
                if g:
                    out["per_cell_sub"][f"{m}:{c}:{s}"] = {cl: comp([u for u in g if u["cls"] == cl]) for cl in ("i", "ii", "iii", "iv")}
    for s in SUBS:
        for m in ("q4", "q8", "all"):
            g = [u for u in us if u["sub"] == s and (m == "all" or u["model"] == m)]
            out["per_sub_pooled_over_cells"][f"{m}:{s}"] = {
                **{cl: comp([u for u in g if u["cls"] == cl]) for cl in ("i", "ii", "iii", "iv")},
                "subclasses": {sc: comp([u for u in g if u["sub_cls"] == sc]) for sc in sorted({u["sub_cls"] for u in g})},
                "ws_only_ii": sum(1 for u in g if u["ws_only"])}
    # composition of the outcome changes (M = 1) by class, per sub-bank, unique (cell, state) units
    for s in SUBS:
        for m in ("q4", "q8", "all"):
            g = [u for u in us if u["sub"] == s and u["M"] and (m == "all" or u["model"] == m)]
            out["outcome_changes_by_class"][f"{m}:{s}"] = {"n_M": len(g), **{cl: {"n": sum(1 for u in g if u["cls"] == cl),
                                                                                  "rescue": sum(u["r"] for u in g if u["cls"] == cl),
                                                                                  "damage": sum(u["d"] for u in g if u["cls"] == cl)}
                                                                             for cl in ("i", "ii", "iii", "iv")},
                                                           "subclasses": dict(collections.Counter(u["sub_cls"] for u in g))}
    # comparator category vs taxonomy (all rows, unique per cell x block x state)
    g = [u for u in us if not u.get("dup_of")]
    ct = collections.defaultdict(collections.Counter)
    for u in g:
        ct[u["comparator"]][u["sub_cls"]] += 1
    out["comparator_crosstab"] = {k: dict(v) for k, v in sorted(ct.items())}
    return out


FEATS = ("question", "confirm_request", "claim_done", "commit_future", "commit_or_claim", "new_entity")


def feature_tables(us: list[dict]) -> dict:
    out = {}
    for s in SUBS:
        for m in ("q4", "q8", "all"):
            g = [u for u in us if u["sub"] == s and u["cls"] == "ii" and (m == "all" or u["model"] == m)]
            if not g:
                continue
            t = {"n_pairs": len(g), "n_M": sum(u["M"] for u in g), "rescue": sum(u["r"] for u in g), "damage": sum(u["d"] for u in g)}
            for f in FEATS:
                yes = [u for u in g if u["feat"][f]["differs"]]
                no = [u for u in g if not u["feat"][f]["differs"]]
                row = {"differs": {"n": len(yes), "M": sum(u["M"] for u in yes), "r": sum(u["r"] for u in yes), "d": sum(u["d"] for u in yes)},
                       "same": {"n": len(no), "M": sum(u["M"] for u in no), "r": sum(u["r"] for u in no), "d": sum(u["d"] for u in no)}}
                if f != "new_entity":
                    for side in ("B", "Q"):  # feature present only in a_B / only in a_Q
                        only = [u for u in yes if u["feat"][f][side]]
                        row[f"{side}_only"] = {"n": len(only), "r": sum(u["r"] for u in only), "d": sum(u["d"] for u in only)}
                for part in ("differs", "same"):
                    row[part]["M_rate"] = round(row[part]["M"] / row[part]["n"], 3) if row[part]["n"] else None
                t[f] = row
            ld = np.array([u["feat"]["length"]["rel_diff"] for u in g])
            med = float(np.median(ld))
            big = [u for u in g if u["feat"]["length"]["rel_diff"] > med]
            small = [u for u in g if u["feat"]["length"]["rel_diff"] <= med]
            t["length"] = {"median_rel_diff": round(med, 3),
                           "above_median": {"n": len(big), "M": sum(u["M"] for u in big), "r": sum(u["r"] for u in big), "d": sum(u["d"] for u in big)},
                           "at_or_below_median": {"n": len(small), "M": sum(u["M"] for u in small), "r": sum(u["r"] for u in small), "d": sum(u["d"] for u in small)},
                           "median_abs_diff_chars_M1": float(np.median([u["feat"]["length"]["abs_diff"] for u in g if u["M"]])) if t["n_M"] else None,
                           "median_abs_diff_chars_M0": float(np.median([u["feat"]["length"]["abs_diff"] for u in g if not u["M"]]))}
            out[f"{m}:{s}"] = t
    # the flipping class-ii pairs themselves (for inspection)
    out["flipping_pairs"] = [{"model": u["model"], "cell": u["cell"], "sub": u["sub"], "block": u["block"], "state_key": u["state_key"],
                              "dir": "rescue" if u["r"] else "damage", "sub_cls": u["sub_cls"],
                              **{f: [int(u["feat"][f]["B"]), int(u["feat"][f]["Q"])] for f in ("question", "confirm_request", "claim_done", "commit_future")},
                              "new_entity_B_only": u["feat"]["new_entity"]["B_only"], "new_entity_Q_only": u["feat"]["new_entity"]["Q_only"],
                              "len_B": u["feat"]["length"]["B"], "len_Q": u["feat"]["length"]["Q"]}
                             for u in us if u["cls"] == "ii" and u["M"]]
    return out


def q0_analysis(us: list[dict], q0rows: list[dict]) -> dict:
    """Q0 arms per (model, cell, sub, block, state_id): B.Q0, c.Q0; GPTQ cell from native BQ / QQ on q0-flagged U2 rows."""
    nat = {(u["model"], u["cell"], u["sub"], u["block"], u["state_id"]): u for u in us}
    rows = []
    for r in q0rows:
        k = (r["model"], r["cell"], r["sub"], r["block"], r["state_id"])
        u = nat.get(k)
        rows.append({"model": r["model"], "cell": r["cell"], "sub": r["sub"], "block": r["block"], "state_id": r["state_id"], "task": task_key(r),
                     "yB": r["Y"]["B.Q0"], "yc": r["Y"]["c.Q0"], "Y_native": r["Y_native"], "exact": int(bool(r["exact_agreement"])),
                     "cls": u["cls"] if u else None, "source": "bank_u_q0", "native_consistent": bool(u) and u["Y"] == r["Y_native"]})
    for u in us:
        if u["cell"] == Q0_CELL and u["q0"] and u["sub"] in ("U2B", "U2Q"):
            rows.append({"model": u["model"], "cell": u["cell"], "sub": u["sub"], "block": u["block"], "state_id": u["state_id"], "task": u["task"],
                         "yB": u["Y"]["BQ"], "yc": u["Y"]["QQ"], "Y_native": u["Y"], "exact": u["exact"], "cls": u["cls"],
                         "source": "native BQ/QQ (Q0 = this cell)", "native_consistent": True})
    out = {"per_cell_sub": {}, "available_cells": sorted({f"{r['model']}:{r['cell']}" for r in rows}),
           "missing_cells": [f"{m}:{c}" for m in ("q4", "q8") for c in CELLS if not any(r["model"] == m and r["cell"] == c for r in rows)]}

    def summ(g, yb, yc):
        n = len(g)
        rr = sum(1 for x in g if yb(x) == 1 and yc(x) == 0)
        dd = sum(1 for x in g if yb(x) == 0 and yc(x) == 1)
        return {"n": n, "r": rr, "d": dd, "M": round((rr + dd) / n, 3) if n else None, "G": round((rr - dd) / n, 3) if n else None}

    for m in ("q4", "q8"):
        for c in CELLS:
            for s in ("U2B", "U2Q"):
                g = [x for x in rows if x["model"] == m and x["cell"] == c and x["sub"] == s]
                if not g:
                    continue
                out["per_cell_sub"][f"{m}:{c}:{s}"] = {
                    "source": g[0]["source"], "n_tasks": len({x["task"] for x in g}), "n_non_exact": sum(1 - x["exact"] for x in g),
                    "Q0": summ(g, lambda x: x["yB"], lambda x: x["yc"]),
                    "native_same_rows": summ(g, lambda x: x["Y_native"]["BQ"], lambda x: x["Y_native"]["QQ"]),
                    "native_vs_Q0_flip_table": dict(collections.Counter(
                        f"nat{'M' if x['Y_native']['BQ'] != x['Y_native']['QQ'] else '0'}/q0{'M' if x['yB'] != x['yc'] else '0'}" for x in g)),
                    "native_row_consistent": sum(x["native_consistent"] for x in g)}
    # same state, same a_B, same Q0: Y(a_B -> Q0) must agree across cells (determinism check); then compare a_c values
    by = collections.defaultdict(dict)
    for x in rows:
        by[(x["model"], x["sub"], x["block"], x["state_id"])][x["cell"]] = x
    cross = {}
    for m in ("q4", "q8"):
        for s in ("U2B", "U2Q"):
            st = [v for k, v in by.items() if k[0] == m and k[1] == s and len(v) >= 2]
            if not st:
                continue
            yb_cons = sum(1 for v in st if len({x["yB"] for x in v.values()}) == 1)
            yc_diff = sum(1 for v in st if len({x["yc"] for x in v.values()}) > 1)
            m_any = sum(1 for v in st if any(x["yB"] != x["yc"] for x in v.values()))
            m_all = sum(1 for v in st if all(x["yB"] != x["yc"] for x in v.values()))
            cross[f"{m}:{s}"] = {"states_with_>=2_cells": len(st), "cells_per_state": dict(collections.Counter(len(v) for v in st)),
                                  "Y_B.Q0_identical_across_cells": yb_cons,
                                  "Y_c.Q0_differs_across_cells": yc_diff, "M_Q0_in_any_cell": m_any, "M_Q0_in_every_cell_present": m_all}
    out["cross_cell_same_state"] = cross
    pooled = {}
    for m in ("q4", "q8"):
        for s in ("U2B", "U2Q"):
            g = [x for x in rows if x["model"] == m and x["sub"] == s]
            if g:
                pooled[f"{m}:{s}"] = {"weights": "equal per (cell, state) row; cells present: " + ",".join(sorted({x['cell'] for x in g})),
                                      "Q0": summ(g, lambda x: x["yB"], lambda x: x["yc"]),
                                      "native_same_rows": summ(g, lambda x: x["Y_native"]["BQ"], lambda x: x["Y_native"]["QQ"])}
    out["pooled_over_cells_stated_weights"] = pooled
    return out


def transfer(us: list[dict]) -> dict:
    out = {}
    for m in ("q4", "q8"):
        for s in SUBS:
            by = collections.defaultdict(dict)
            for u in us:
                if u["model"] == m and u["sub"] == s:
                    by[(u["block"], u["state_id"])][u["cell"]] = u
            shared = {k: v for k, v in by.items() if len(v) >= 2}
            if not shared:
                out[f"{m}:{s}"] = {"shared_states": 0, "note": "no state_id shared across cells (own-trajectory states)" if s == "U1" else "none"}
                continue
            full = {k: v for k, v in shared.items() if len(v) == len(CELLS)}
            nflip = collections.Counter(sum(x["M"] for x in v.values()) for v in full.values())
            pairs = {}
            for i, a in enumerate(CELLS):
                for b in CELLS[i + 1:]:
                    pp = [(v[a], v[b]) for v in shared.values() if a in v and b in v]
                    both = [(x, y) for x, y in pp if x["M"] and y["M"]]
                    na, nb = sum(x["M"] for x, _ in pp), sum(y["M"] for _, y in pp)
                    n = len(pp)
                    pairs[f"{a}~{b}"] = {"n": n, "M_a": na, "M_b": nb, "both": len(both), "neither": sum(1 for x, y in pp if not x["M"] and not y["M"]),
                                         "same_direction_when_both": sum(1 for x, y in both if x["G"] == y["G"]),
                                         "expected_both_if_independent": round(na * nb / n, 2) if n else None,
                                         "a_Q_identical": sum(1 for x, y in pp if x["a_Q_canon"] == y["a_Q_canon"]),
                                         "both_given_a_Q_identical": sum(1 for x, y in both if x["a_Q_canon"] == y["a_Q_canon"])}
            bb_cons = sum(1 for v in shared.values() if len({x["Y"]["BB"] for x in v.values()}) == 1)
            ab_cons = sum(1 for v in shared.values() if len({x["a_B_canon"] for x in v.values()}) == 1)
            out[f"{m}:{s}"] = {"shared_states": len(shared), "shared_by_all_3_cells": len(full),
                               "n_cells_flipping_per_state_(all3)": {str(k): nflip.get(k, 0) for k in range(len(CELLS) + 1)},
                               "pairwise": pairs, "a_B_identical_across_cells": ab_cons, "Y_BB_identical_across_cells": bb_cons,
                               "flip_states": [{"block": k[0], "state_id": k[1], **{c: (v[c]["G"] if c in v else None) for c in CELLS},
                                                **{f"cls_{c}": v[c]["cls"] for c in CELLS if c in v}}
                                               for k, v in sorted(shared.items()) if any(x["M"] for x in v.values())]}
    return out


# ----------------------------------------------------------------------------------------------------------------------
# report
# ----------------------------------------------------------------------------------------------------------------------

def fmt_ci(res, s):
    lo, hi = ci(res, s)
    return f"{res['point'][s]:+.3f} [{lo:+.3f}, {hi:+.3f}]" if s in ("G", "A", "C", "I", "H", "F") else f"{res['point'][s]:.3f} [{lo:.3f}, {hi:.3f}]"


def write_md(R: dict, path: Path) -> None:
    L = []
    w = L.append
    w(f"# Bank U analysis ({R['blocks_present']}) — {R['generated_utc']}\n")
    w("Script `analysis/fork/analyze_bank_u.py`; protocol FORK_PROTOCOL §15 + amendment 1; manifest sha256 "
      f"`{R['notes']['manifest_sha256']}`. Input sha256s are in the JSON (`inputs`).\n")
    w("**Rules.** U1 / U2B / U2Q are reported separately and never pooled. Primary estimand: equal weight per task, one "
      "uniformly drawn decision within the task (no n_decisions multiplication). Per-decision (n_decisions-weighted) is a "
      "labelled secondary. " + R["interval_note"] + "\n")
    w("## 1. Unique states\n")
    w("| model:cell:block | rows | unique states | U1 / U2B / U2Q unique | duplicated states (subs) | dup Y concordant |")
    w("|---|---|---|---|---|---|")
    for k, v in R["uniqueness"].items():
        ps = v["per_sub"]
        w(f"| {k} | {v['rows']} | {v['unique_states']} | {ps['U1']['unique']} / {ps['U2B']['unique']} / {ps['U2Q']['unique']} | "
          f"{v['duplicate_states']} {v['duplicate_sub_pairs'] or ''} | {v['duplicate_Y_concordant']}/{v['duplicate_states']} |")
    w("\nGPTQ-W4 d1's U2Q rows are its own U1 states (U2Q is GPTQ-sourced). Each sub-bank estimate below uses its own unique "
      "states; tables spanning sub-banks count each state once (kept in U1).\n")
    w("## 2. Native estimates per cell and sub-bank (primary: task-equal)\n")
    w("| model:cell:sub | n (unique) | tasks | k | exact | r | d | M | G | A | C | I | M (per-decision, secondary) | M given non-exact |")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for k, v in R["native"].items():
        p = v["primary_task_equal"]
        sec = v["secondary_per_decision_n_decisions_weighted"]
        w(f"| {k} | {p['n']} ({p['n_unique_states']}) | {p['n_tasks']} | {p['k_blocks']} | {p['point']['exact']:.2f} | "
          f"{v['counts']['rescue']} ({p['point']['r']:.3f}) | {v['counts']['damage']} ({p['point']['d']:.3f}) | {fmt_ci(p, 'M')} | {fmt_ci(p, 'G')} | "
          f"{fmt_ci(p, 'A')} | {fmt_ci(p, 'C')} | {fmt_ci(p, 'I')} | {sec['point']['M']:.3f} | {v['counts']['M_given_non_exact']} |")
    w("\nr and d columns give counts (rate). Intervals: " + R["interval_note"] + "\n")
    w("## 3. Action-difference taxonomy (a_B vs a_Q)\n")
    w("Classes: (i) canonical message identical; (ii) same tool structure (same calls, or both talk) but different text; "
      "(iii) both act, different tool name/args/count; (iv) action kind differs (act/talk/stop). The comparator's "
      "`text_only` is a comparator class (same kind, different whitespace-normalised text), not a semantic class; its "
      "`same` also contains act-act pairs whose calls match but whose content text differs (taxonomy ii_act).\n")
    w("### Outcome changes (M = 1) by class, per sub-bank (cells pooled within the sub-bank; rows are cell x state units)\n")
    w("| model:sub | n M | (i) | (ii) r/d | (iii) r/d | (iv) r/d | subclasses |")
    w("|---|---|---|---|---|---|---|")
    for k, v in R["taxonomy"]["outcome_changes_by_class"].items():
        w(f"| {k} | {v['n_M']} | {v['i']['n']} | {v['ii']['n']} ({v['ii']['rescue']}/{v['ii']['damage']}) | {v['iii']['n']} ({v['iii']['rescue']}/{v['iii']['damage']}) | "
          f"{v['iv']['n']} ({v['iv']['rescue']}/{v['iv']['damage']}) | {v['subclasses']} |")
    w("\n### Class composition and consequence per sub-bank (all rows)\n")
    w("| model:sub | class | n | rescue | damage | both succeed | both fail | M rate |")
    w("|---|---|---|---|---|---|---|---|")
    for k, v in R["taxonomy"]["per_sub_pooled_over_cells"].items():
        if k.startswith("all:"):
            continue
        for cl in ("i", "ii", "iii", "iv"):
            z = v[cl]
            if z.get("n"):
                w(f"| {k} | {cl} | {z['n']} | {z.get('rescue', 0)} | {z.get('damage', 0)} | {z.get('both_succeed', 0)} | {z.get('both_fail', 0)} | "
                  f"{(z.get('rescue', 0) + z.get('damage', 0)) / z['n']:.3f} |")
    w("\n### Per cell (class: n, r/d)\n")
    w("| model:cell:sub | (i) | (ii) | (iii) | (iv) |")
    w("|---|---|---|---|---|")
    for k, v in R["taxonomy"]["per_cell_sub"].items():
        w(f"| {k} | " + " | ".join(f"{v[c].get('n', 0)}: {v[c].get('rescue', 0)}/{v[c].get('damage', 0)}" for c in ("i", "ii", "iii", "iv")) + " |")
    w("\n### Comparator category vs taxonomy subclass (unique states)\n")
    w("```\n" + json.dumps(R["taxonomy"]["comparator_crosstab"], indent=1) + "\n```\n")
    w("## 4. Content split of class (ii) text differences (descriptive only)\n")
    w("Features are computed on a_B and a_Q text; 'differs' = present in exactly one. M rate = outcome-changing share. "
      "B_only / Q_only: the feature is present only in the BF16 / only in the quantized action (r = BF16 action wins, d = Q wins). "
      "Regex features are cheap and imperfect; no tests are run.\n")
    for k, t in R["text_features"].items():
        if k == "flipping_pairs" or not k.startswith(("q4", "q8")):
            continue
        w(f"**{k}**: {t['n_pairs']} class-(ii) pairs, M = {t['n_M']} (r {t['rescue']}, d {t['damage']}).\n")
        w("| feature | differs: n, M (rate), r/d | same: n, M (rate) | B_only r/d | Q_only r/d |")
        w("|---|---|---|---|---|")
        for f in FEATS:
            x = t[f]
            bo = f"{x['B_only']['n']}: {x['B_only']['r']}/{x['B_only']['d']}" if "B_only" in x else "-"
            qo = f"{x['Q_only']['n']}: {x['Q_only']['r']}/{x['Q_only']['d']}" if "Q_only" in x else "-"
            w(f"| {f} | {x['differs']['n']}, {x['differs']['M']} ({x['differs']['M_rate']}), {x['differs']['r']}/{x['differs']['d']} | "
              f"{x['same']['n']}, {x['same']['M']} ({x['same']['M_rate']}) | {bo} | {qo} |")
        ln = t["length"]
        w(f"| rel. length diff > median ({ln['median_rel_diff']}) | {ln['above_median']['n']}, {ln['above_median']['M']}, "
          f"{ln['above_median']['r']}/{ln['above_median']['d']} | {ln['at_or_below_median']['n']}, {ln['at_or_below_median']['M']} | - | - |\n")
        w(f"Median |Δlen| chars: M=1 {ln['median_abs_diff_chars_M1']}, M=0 {ln['median_abs_diff_chars_M0']}.\n")
    w("## 5. Q0 common continuation controller (reported separately from native; small n)\n")
    w(f"Cells with Q0 data: {R['q0']['available_cells']}; missing: {R['q0']['missing_cells']}. GPTQ-W4 d1 is Q0 itself, so its "
      "native BQ/QQ on the Q0-flagged U2 rows are the Q0 arms. G_Q0 = Y(a_B→Q0) − Y(a_c→Q0).\n")
    w("| model:cell:sub | n | non-exact | Q0: r/d, M, G | native (same rows): r/d, M, G | flip table | source |")
    w("|---|---|---|---|---|---|---|")
    for k, v in R["q0"]["per_cell_sub"].items():
        a, b = v["Q0"], v["native_same_rows"]
        w(f"| {k} | {a['n']} | {v['n_non_exact']} | {a['r']}/{a['d']}, {a['M']}, {a['G']:+} | {b['r']}/{b['d']}, {b['M']}, {b['G']:+} | "
          f"{v['native_vs_Q0_flip_table']} | {v['source']} |")
    w("\nSame state across cells under Q0:\n")
    w("```\n" + json.dumps(R["q0"]["cross_cell_same_state"], indent=1) + "\n```\n")
    w("Pooled over cells (equal weight per cell x state row; stated):\n")
    w("```\n" + json.dumps(R["q0"]["pooled_over_cells_stated_weights"], indent=1) + "\n```\n")
    w("## 6. Cross-quantizer transfer on shared states (native)\n")
    for k, v in R["transfer"].items():
        if not v.get("shared_states"):
            w(f"- **{k}**: {v.get('note')}")
            continue
        w(f"- **{k}**: {v['shared_states']} shared states ({v['shared_by_all_3_cells']} in all 3 cells); cells flipping per state "
          f"{v['n_cells_flipping_per_state_(all3)']}; a_B identical across cells {v['a_B_identical_across_cells']}/{v['shared_states']}, "
          f"Y_BB identical {v['Y_BB_identical_across_cells']}/{v['shared_states']}.")
        for pk, p in v["pairwise"].items():
            w(f"  - {pk}: n {p['n']}, M {p['M_a']} vs {p['M_b']}, both {p['both']} (independence expects {p['expected_both_if_independent']}), "
              f"same direction {p['same_direction_when_both']}/{p['both']}; a_Q identical {p['a_Q_identical']}/{p['n']} "
              f"(of the joint flips, {p['both_given_a_Q_identical']} have identical a_Q)")
    w("\n## Notes\n")
    w(f"- Skipped dirs: {R['notes']['skipped_dirs'] or 'none'}; missing/errored rows: {len(R['notes']['missing_rows'])}.")
    w("- Everything here is descriptive for f01 (k = 1). Cells and sub-banks are not pooled into a single population.")
    path.write_text("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=2000)
    args = ap.parse_args()
    rng = np.random.default_rng(20261001)
    inputs = {}
    native, q0rows, notes = load(inputs)
    us = build_units(native)
    mark_unique_for_pools(us)
    blocks = sorted({u["block"] for u in us})
    kmax = max((len({u["block"] for u in us if (u["model"], u["cell"], u["sub"]) == key}) for key in {(u["model"], u["cell"], u["sub"]) for u in us}), default=0)
    interval_note = ("k = 1 block (f01 only): intervals are task-cluster bootstraps (tasks resampled), so they ignore run-level "
                     "(nonce/block) uncertainty." if kmax == 1 else
                     "k < 10 blocks: t over block means is primary, task-cluster bootstrap is the new-task interval." if kmax < 10 else
                     "k >= 10 blocks: block bootstrap is primary; task-cluster bootstrap reported.")
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    R = {"generated_utc": stamp, "script": "analysis/fork/analyze_bank_u.py", "blocks_present": ",".join(blocks), "n_boot": args.boot,
         "interval_note": interval_note, "notes": notes, "inputs": inputs,
         "uniqueness": uniqueness(us), "native": per_cell_estimates(us, rng, args.boot),
         "taxonomy": taxonomy_tables(us), "text_features": feature_tables(us),
         "q0": q0_analysis(us, q0rows), "transfer": transfer(us)}
    OUT.mkdir(parents=True, exist_ok=True)
    tag = "_".join(blocks) if blocks else "none"
    jp, mp = OUT / f"bank_u_{tag}_{stamp}.json", OUT / f"bank_u_{tag}_{stamp}.md"
    jp.write_text(json.dumps(R, indent=1, default=str))
    write_md(R, mp)
    print(rel(jp))
    print(rel(mp))


if __name__ == "__main__":
    main()
