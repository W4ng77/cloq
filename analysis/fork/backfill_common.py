"""Shared helpers of the appendix backfill (analysis/fork/analyze_backfill.py, W100x): episode reading under the W6/W10
rules, joint task x block units of the perturb-v1 closed-loop arms, analyze_dev.Boot statistics and formatting."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
from analyze_dev import Boot, sha256, success, summarise, t_interval  # noqa: E402,F401
from cloq.fork import action_view  # noqa: E402

OUT = ROOT / "analysis/fork/out"
PERT_RE = re.compile(r"^a6k2_pert_(q\d+)_(rtn_w3|gptq_w3|gptq_w4_d1|awq_w4)_(.+)_(q\d+|f\d\d)$")
CELLS = [("q4", "rtn_w3"), ("q8", "rtn_w3"), ("q4", "gptq_w3"), ("q8", "gptq_w3"), ("q4", "gptq_w4_d1"), ("q8", "awq_w4")]
CELL_LABEL = {"rtn_w3": "RTN-W3", "gptq_w3": "GPTQ-W3", "gptq_w4_d1": "GPTQ-W4", "awq_w4": "AWQ-W4"}
CELL_BLOCKS = {"rtn_w3": ("q3", "q4", "q5"), "gptq_w3": ("q3", "q4", "q5"), "gptq_w4_d1": ("f01", "f02", "f03"), "awq_w4": ("f01", "f02", "f03")}
FAMILY = {"early": "rand_third", "middle": "rand_third", "late": "rand_third", "attn": "rand_attn", "mlp": "rand_mlp"}
SEEDS = ("s1", "s2", "s3")
ALPHAS = {"rtn_w3": (0.25, 0.5, 2.0), "gptq_w3": (0.25, 0.5, 2.0), "gptq_w4_d1": (0.25, 0.5, 2.0), "awq_w4": (0.25, 0.5, 2.0)}
DOMAINS = ("retail", "airline")
# tau2 ToolType.WRITE tools (third_party/tau2-bench/src/tau2/domains/{retail,airline}/tools.py @is_tool(ToolType.WRITE))
WRITE = {"retail": {"cancel_pending_order", "exchange_delivered_order_items", "modify_pending_order_address", "modify_pending_order_items",
                    "modify_pending_order_payment", "modify_user_address", "return_delivered_order_items"},
         "airline": {"book_reservation", "cancel_reservation", "send_certificate", "update_reservation_baggages",
                     "update_reservation_flights", "update_reservation_passengers"}}
TEXT_CALL = re.compile(r'\{\s*"name"\s*:\s*"([A-Za-z_]+)"\s*,\s*"arguments"\s*:')  # tool call written as plain text JSON

_EP: dict = {}
DEV = {d: {str(t) for t in ts} for d, ts in json.load(open(ROOT / "manifests/fork/splits_v1.json"))["splits"]["dev"]["tasks"].items()}


def git_head() -> str:
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def read_run(rid: str, dom: str, fr: dict) -> dict | None:
    """{task_id: episode} for one admitted run-domain; None if the trajectory differs from the snapshot."""
    key = (rid, dom)
    if key in _EP:
        return _EP[key]
    p = ROOT / "runs" / rid / dom / "trajectory.jsonl"
    want = fr["files"]["trajectory.jsonl"]["sha256"]
    if not p.exists() or sha256(p) != want:
        _EP[key] = None
        return None
    try:
        causes = json.load(open(p.parent / "infra_causes.json"))
    except Exception:
        causes = {}
    out = {}
    for ln in open(p):
        t = json.loads(ln)
        tid = str(t["task_id"])
        term = t.get("termination_reason")
        e = {"term": term, "cause": None, "data": True, "Y": None, "sig": None}
        if term == "infrastructure_error":
            c = causes.get(tid)
            e["cause"] = c if isinstance(c, str) else "infra_unknown"
            e["data"] = e["cause"] in ("context_overflow", "agent_parse_error", "agent_empty_output")
            e["Y"] = 0 if e["data"] else None
        else:
            e["Y"] = success(dom, t)
            dec = [m for m in t.get("messages") or [] if m.get("role") == "assistant" and m.get("turn_idx") != 0]
            views = [action_view(m, {}) for m in dec]
            e["sig"] = [json.dumps([v["kind"], [c["norm"] for c in v["calls"]]], sort_keys=True, default=str) for v in views]
            req = sorted({a.get("name") for a in (((t.get("task") or {}).get("evaluation_criteria") or {}).get("actions") or [])
                          if a.get("name") in WRITE.get(dom, set())})
            parsed = [c["name"] for v in views for c in v["calls"]]
            text_calls = [n for m, v in zip(dec, views) if v["kind"] != "act" for n in TEXT_CALL.findall(m.get("content") or "")]
            e["f"] = {"req": req, "writes": sorted({n for n in parsed if n in WRITE.get(dom, set())}),
                      "n_parsed": len(parsed), "n_text_calls": len(text_calls),
                      "n_markup_fail": sum(1 for v in views if v["kind"] == "parse_fail"), "n_dec": len(dec)}
        out[tid] = e
    _EP[key] = out
    return out


def first_act_div(x: list, b: list):
    for i, (dx, db) in enumerate(zip(x, b)):
        if dx != db:
            return i
    return min(len(x), len(b)) if len(x) != len(b) else None


# ------------------------------------------------------------------------------------------------ closed-loop arms
def cell_units(fz: dict, model: str, cell: str, arms: list[str], rule: str) -> tuple[list[dict], dict]:
    """Joint task x block units on which every listed arm (plus Q and BF16) has a data episode. arms use the run-id arm
    names (restore_attn, resid_a0.5, ...); 'Q' and 'B' are added. rule = 'w10' (overflow = failure) | 'allinfra'."""
    units, info = [], {"skipped": []}
    for blk in CELL_BLOCKS[cell]:
        rids = {a: f"a6k2_pert_{model}_{cell}_{a}_{blk}" for a in arms}
        rids["Q"], rids["B"] = f"a6k2_{model}_{cell}_{blk}", f"a6k2_{model}_bfpair_{blk}"
        for dom in DOMAINS:
            if not all(dom in (fz.get(r) or {}) for r in rids.values()):
                info["skipped"].append(f"{blk}/{dom}: not admitted " + ",".join(sorted(a for a, r in rids.items() if dom not in (fz.get(r) or {}))))
                continue
            nonces = {fz[r][dom].get("prompt_nonce") for r in rids.values()}
            if len(nonces) != 1:
                info["skipped"].append(f"{blk}/{dom}: nonce mismatch")
                continue
            ep = {a: read_run(r, dom, fz[r][dom]) for a, r in rids.items()}
            if any(v is None for v in ep.values()):
                info["skipped"].append(f"{blk}/{dom}: trajectory differs from snapshot")
                continue
            for tid in sorted(set.intersection(*[set(v) for v in ep.values()])):
                if tid not in DEV[dom]:  # W63 split boundary: retail/airline tasks are all dev; holdout is telecom only
                    info["skipped"].append(f"{blk}/{dom}/{tid}: not in dev split")
                    continue
                es = {a: ep[a][tid] for a in rids}
                if rule == "allinfra":
                    ok = all(e["term"] != "infrastructure_error" for e in es.values())
                else:
                    ok = all(e["data"] for e in es.values())
                if ok:
                    units.append({"task": f"{dom}:{tid}", "block": blk, "ep": es})
    return units, info


def boot_for(units_by_key: dict) -> Boot:
    bo = defaultdict(set)
    for us in units_by_key.values():
        for u in us:
            bo[u["task"]].add(u["block"])
    return Boot(sorted(bo), {k: sorted(v) for k, v in bo.items()})


def stat(boot: Boot, units: list[dict], fn) -> tuple:
    us = []
    for u in units:
        v = fn(u)
        if v is not None:
            us.append({"task": u["task"], "block": u["block"], "E": {"x": float(v)}})
    X, M = boot.arrays(us, "x")
    return boot.task_mean(X, M)


def summ(pair, pct=True) -> dict:
    s = summarise(*pair, pct=pct)
    return {k: s.get(k) for k in ("est", "ci95", "crossed_ci95", "n_blocks")}


def pool(pairs, pct=True) -> dict:
    """Equal-weight pool of per-cell (pt, Draws) on a shared Boot (analyze_pivot_arms.pool_delta)."""
    pt = float(np.mean([p[0] for p in pairs]))
    bm = np.mean(np.vstack([p[1].block_means for p in pairs]), axis=0)
    crossed = (pt, np.mean([p[1].crossed for p in pairs], axis=0))
    s = summarise(pt, np.mean([np.asarray(p[1]) for p in pairs], axis=0), pct=pct, t=t_interval(bm), crossed=crossed)
    return {k: s.get(k) for k in ("est", "ci95", "crossed_ci95", "n_blocks")}


def admitted_arms(fz: dict, model: str, cell: str) -> dict:
    """arm -> sorted list of admitted '<blk>/<dom>' run-domains."""
    out = defaultdict(list)
    for rid in fz:
        m = PERT_RE.match(rid)
        if m and m.group(1) == model and m.group(2) == cell:
            for dom in fz[rid]:
                out[m.group(3)].append(f"{m.group(4)}/{dom}")
    return {k: sorted(v) for k, v in out.items()}


def complete(adm: dict, arm: str, cell: str) -> bool:
    return set(adm.get(arm, [])) >= {f"{b}/{d}" for b in CELL_BLOCKS[cell] for d in DOMAINS}


def fmt(s: dict | None, dec=1, sign=True) -> str:
    if not s or s.get("est") is None:
        return "n/a"
    f = (lambda v: f"{v:+.{dec}f}") if sign else (lambda v: f"{v:.{dec}f}")
    out = f(s["est"])
    if s.get("ci95"):
        out += f" [{f(s['ci95'][0])}, {f(s['ci95'][1])}]"
    if s.get("crossed_ci95"):
        out += f" x[{f(s['crossed_ci95'][0])}, {f(s['crossed_ci95'][1])}]"
    return out


def excl0(s: dict | None, which="ci95") -> str:
    """'+' / '-' if the interval excludes 0 on that side, '0' if it covers 0, '?' if absent."""
    iv = (s or {}).get(which)
    if not iv:
        return "?"
    return "+" if iv[0] > 0 else "-" if iv[1] < 0 else "0"
