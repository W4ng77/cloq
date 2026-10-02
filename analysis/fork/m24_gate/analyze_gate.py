"""W99p: m24 (Mistral-Small-3.2-24B, text-only, mistral tokenizer/parser) gate -- evidence summary (CPU only).

Reads the gate evals (runs/a6k2_m24_{bf16,rtn_w4}_g1/{retail,airline}, runs/ext_m24_{bf16,rtn_w4}_bfcl_gate_m24/bfcl_*),
the fork gate outputs under analysis/fork/m24_gate/{tau2_rtn_w4,tau2_same_rtn_w4,bfcl_rtn_w4,bfcl_same_rtn_w4}/ and the
queue records, and writes analysis/fork/m24_gate/gate_summary.json. Per check:
  serving   : prompt ids from server, local==server prompt ids (tau2), tool calls parsed, parser errors (unparsed
              [TOOL_CALLS]), infra causes, unknown-tool calls (BFCL), item terminations
  capability: BF16 tau2 success (normal stop and DB match) on the 20 gate tasks vs Qwen BF16 on the same tasks (the
              a6k2_<q>_bf16_cal runs cover the gate tasks of the calibration split); BFCL success on the 20 gate items vs
              Qwen q4/q8/q14 BF16 eval runs on the same items
  forks     : verdicts of gate / gate_same (tau2 and BFCL); tau2_rtn_w4_r2 = the tau2 gate rerun with the chat identity
              probe (7009bec), which supersedes tau2_rtn_w4 (r1, /v1/completions probe)
  throughput: queue seconds per task, per-episode wall time
usage: python3 analysis/fork/m24_gate/analyze_gate.py
"""
from __future__ import annotations

import json
import math
import statistics as S
from collections import Counter
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
G = ROOT / "analysis/fork/m24_gate"
QD = Path("/data/ziyangs/cloq_work/queue")
DOMS = ["bfcl_base", "bfcl_miss_param", "bfcl_miss_func", "bfcl_long_context"]
TAU = json.load(open(ROOT / "manifests/a6k2/m24/gate_tau2_v1.json"))
BF = json.load(open(ROOT / "manifests/bfcl/bfcl_mt_m24_v1.json"))["categories"]


def jl(p: Path):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def wilson(k: int, n: int) -> list:
    if not n:
        return [None, None]
    z, p = 1.96, k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(c - h, 4), round(c + h, 4)]


NAME_OK = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")  # the function-name rule mistral_common enforces when re-rendering a turn


def bad_names(decs: list[dict]) -> int:
    """Decisions whose parsed tool calls include an invalid function name (empty, prose, ...): mistral_common refuses to
    render that turn at the next request (HTTP 400), so the episode ends there (agent_parse_error, W27 rule)."""
    n = 0
    for d in decs:
        for c in d.get("tool_calls") or []:
            nm = c.get("name") if "name" in c else (c.get("function") or {}).get("name")
            if not NAME_OK.match(nm or ""):
                n += 1
                break
    return n


def invalid_name_rates() -> dict:
    out = {}
    for rid, doms in (("a6k2_m24_bf16_g1", ("retail", "airline")), ("a6k2_m24_rtn_w4_g1", ("retail", "airline")),
                      ("a6k2_m24_bf16_cal", ("retail", "airline")), ("ext_m24_bf16_bfcl_gate_m24", DOMS),
                      ("ext_m24_rtn_w4_bfcl_gate_m24", DOMS)):
        nd = ne = nb = 0
        eps = set()
        for d in doms:
            decs = jl(ROOT / "runs" / rid / d / "decisions.jsonl")
            nd += len(decs)
            eps |= {(d, x["task_id"]) for x in decs}
            for x in decs:
                if bad_names([x]):
                    nb += 1
                    ne += 0
            ne = len({(d, x["task_id"]) for d in doms for x in jl(ROOT / "runs" / rid / d / "decisions.jsonl") if bad_names([x])})
        out[rid] = {"decisions": nd, "decisions_with_invalid_name": nb, "episodes": len(eps), "episodes_with_invalid_name": ne}
    return out


def ok_tau(t: dict) -> int:
    return int(bool(t.get("db_match")) and t.get("termination_reason") in ("user_stop", "agent_stop"))


def tau_run(rid: str) -> dict:
    out = {"run": rid, "domains": {}}
    for d in ("retail", "airline"):
        rd = ROOT / "runs" / rid / d
        tr, dec = jl(rd / "trajectory.jsonl"), jl(rd / "decisions.jsonl")
        if not tr:
            out["domains"][d] = None
            continue
        tcs = [d_ for d_ in dec if d_.get("tool_calls")]
        ids = [c["id"] for d_ in tcs for c in d_["tool_calls"]]
        out["domains"][d] = {
            "n_tasks": len(tr), "success": {str(t["task_id"]): ok_tau(t) for t in tr},
            "termination": dict(Counter(t["termination_reason"] for t in tr)),
            "n_decisions": len(dec), "n_tool_call_decisions": len(tcs), "n_tool_calls": len(ids),
            "multi_call_decisions": sum(len(d_["tool_calls"]) > 1 for d_ in tcs),
            "parser_errors": sum(bool(d_.get("parser_error")) for d_ in dec),
            "prompt_ids_from_server": sum(bool(d_.get("prompt_ids_from_server")) for d_ in dec),
            "prompt_ids_match_local": sum(d_.get("prompt_ids_match_local") is True for d_ in dec),
            "tool_call_ids_deterministic": all(len(i) == 9 and i.startswith("d") for i in ids),
            "finish_length": sum(d_.get("finish_reason") == "length" for d_ in dec),
            "infra_causes": json.load(open(rd / "infra_causes.json")) if (rd / "infra_causes.json").exists() else {},
            "episode_seconds_median": S.median([t["duration"] for t in tr if t.get("duration")]) if tr else None,
        }
    return out


def bfcl_run(rid: str) -> dict:
    out = {"run": rid, "domains": {}}
    for d in DOMS:
        rd = ROOT / "runs" / rid / d
        tr, dec = jl(rd / "trajectory.jsonl"), jl(rd / "decisions.jsonl")
        if not tr:
            out["domains"][d] = None
            continue
        tcs = [x for x in dec if x.get("tool_calls")]
        out["domains"][d] = {
            "n_items": len(tr), "success": {t["task_id"]: int(bool(t.get("success"))) for t in tr},
            "termination": dict(Counter(t["termination_reason"] for t in tr)),
            "n_decisions": len(dec), "n_tool_call_decisions": len(tcs),
            "n_tool_calls": sum(len(x["tool_calls"]) for x in tcs),
            "unknown_tool_calls": sum(not all(x.get("actions_known_tool") or [True]) for x in tcs),
            "decode_errors_on_tool_calls": sum(x.get("decode_error") not in (None, "None", "") for x in tcs),
            "parser_errors": sum(bool(x.get("parser_error")) for x in dec),
            "prompt_ids_from_server": sum(bool(x.get("prompt_ids_from_server")) for x in dec),
            "item_seconds_median": S.median([t["duration"] for t in tr if t.get("duration")]) if tr else None,
        }
    return out


def qwen_tau(task_ids: dict) -> dict:
    res = {}
    for q in ("q4", "q8", "q14", "q32"):
        k = n = 0
        for d in ("retail", "airline"):
            for t in jl(ROOT / "runs" / f"a6k2_{q}_bf16_cal" / d / "trajectory.jsonl"):
                if str(t["task_id"]) in task_ids[d]:
                    k, n = k + ok_tau(t), n + 1
        res[q] = {"k": k, "n": n, "rate": round(k / n, 4) if n else None}
    return res


def qwen_bfcl(ids: set) -> dict:
    res = {}
    for q in ("q4", "q8", "q14"):
        k = n = 0
        for d in DOMS:
            for t in jl(ROOT / "runs" / f"ext_{q}_bf16_bfcl_eval" / d / "trajectory.jsonl"):
                if t["task_id"] in ids:
                    k, n = k + int(bool(t.get("success"))), n + 1
        res[q] = {"k": k, "n": n, "rate": round(k / n, 4) if n else None}
    return res


def fork_verdict(sub: str) -> dict | None:
    for name in ("gate.json", "gate_same.json"):
        p = G / sub / name
        if p.exists():
            g = json.load(open(p))
            return {"file": str(p.relative_to(ROOT)), "verdict": g.get("verdict")}
    return None


def qrec(tid: str) -> dict:
    for s in ("done", "failed", "running", "todo"):
        p = QD / s / f"{tid}.json"
        if p.exists():
            t = json.load(open(p))
            return {"state": s, "seconds": t.get("seconds"), "host": t.get("host"), "error": t.get("error")}
    return {"state": None}


def main():
    s = {"tau2": {a: tau_run(f"a6k2_m24_{a}_g1") for a in ("bf16", "rtn_w4")},
         "bfcl": {a: bfcl_run(f"ext_m24_{a}_bfcl_gate_m24") for a in ("bf16", "rtn_w4")}}
    cap = {}
    for a in ("bf16", "rtn_w4"):
        doms = [v for v in s["tau2"][a]["domains"].values() if v]
        k, n = sum(sum(v["success"].values()) for v in doms), sum(v["n_tasks"] for v in doms)
        bd = [v for v in s["bfcl"][a]["domains"].values() if v]
        kb, nb = sum(sum(v["success"].values()) for v in bd), sum(v["n_items"] for v in bd)
        cap[a] = {"tau2": {"k": k, "n": n, "rate": round(k / n, 4) if n else None, "wilson95": wilson(k, n)},
                  "bfcl": {"k": kb, "n": nb, "rate": round(kb / nb, 4) if nb else None, "wilson95": wilson(kb, nb)}}
    cal = set(json.load(open(ROOT / "manifests/cal_tasks_v0.json"))["retail"]) , set(json.load(open(ROOT / "manifests/cal_tasks_v0.json"))["airline"])
    gate_cal = {"retail": [i for i in TAU["retail"] if i in cal[0]], "airline": [i for i in TAU["airline"] if i in cal[1]]}
    m24_on_cal = {}
    for a in ("bf16",):
        k = n = 0
        for d in ("retail", "airline"):
            v = s["tau2"][a]["domains"].get(d) or {"success": {}}
            for i in gate_cal[d]:
                if i in v["success"]:
                    k, n = k + v["success"][i], n + 1
        m24_on_cal[a] = {"k": k, "n": n, "rate": round(k / n, 4) if n else None}
    cap["comparison_tau2_gate_tasks_in_cal_split"] = {"tasks": gate_cal, "m24": m24_on_cal, "qwen_bf16_cal_runs": qwen_tau(gate_cal)}
    ids = {i for c in BF.values() for i in c["gate_m24"]}
    cap["comparison_bfcl_gate_items"] = {"m24_bf16": cap["bf16"]["bfcl"], "qwen_bf16_eval_runs": qwen_bfcl(ids)}
    s["capability"] = cap
    s["invalid_tool_names"] = invalid_name_rates()
    s["forks"] = {k: fork_verdict(k) for k in ("tau2_rtn_w4", "tau2_rtn_w4_r2", "tau2_same_rtn_w4", "bfcl_rtn_w4", "bfcl_same_rtn_w4")}
    s["queue"] = {t: qrec(t) for t in ("a6k2_m24_bf16_gate", "a6k2_m24_rtn_w4_gate", "ext_m24_bf16_bfcl_gate_m24",
                                       "ext_m24_rtn_w4_bfcl_gate_m24", "fork_gate_m24_rtn_w4", "fork_gate_m24_rtn_w4_r2", "fork_gate_same_m24_rtn_w4",
                                       "fork_ext_gate_m24_rtn_w4_bfcl", "fork_ext_gate_same_m24_rtn_w4_bfcl", "a6k2_m24_bf16_cal",
                                       "a6k2_m24_calib_c1")}
    (G / "gate_summary.json").write_text(json.dumps(s, indent=1) + "\n")
    print(json.dumps({"capability": cap, "invalid_tool_names": s["invalid_tool_names"], "forks": s["forks"], "queue": s["queue"]}, indent=1))


if __name__ == "__main__":
    main()
