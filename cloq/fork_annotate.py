"""Per-fork process annotation (fork-annot-v1): three independent fields per state and branch.

The BF16 action is only a reference, so an action is never called wrong because it differs from B. The three fields
(EXTERNAL_REVIEW_GPT61_20260930.md, Round 2):
  1. defect      does the current action (a_Q and a_B, judged the same way) have a verifiable defect? Automatic checks:
                 invalid tool (not an agent tool of the domain), invalid arguments (schema: missing required / unknown
                 keys), execution error (the environment rejected the call: precondition or argument violation),
                 ungrounded ids (an id-valued argument that appears nowhere earlier in the conversation or tool
                 outputs), write without an explicit user confirmation in the last user turn (a proxy: a regex on the
                 user's words, never an authorisation verdict), malformed action (parse failure / empty), and an
                 episode-ending action (stop / handoff) that the branch then fails (premature end). `manual` is a
                 slot for human review.
  2. correction  for each automatic defect, the first later agent turn in the branch that addresses it (same tool
                 called again without an execution error / with grounded ids; for an unconfirmed write, a later user
                 objection and later writes are recorded, since a write cannot be undone by retrying). Evidence
                 only; `manual` slot.
  3. requirements which task requirements hold at the end: DB success (retail/airline) or official task-basis success
                 (telecom: official_reward == 1), each env assertion, each gold action check, each communicate check,
                 and the DB fields that differ from the gold DB (agent and user DB, recursive paths).
Tool types come from analysis/insights/iter_4/tool_types.py (verified against the tau2 source by its --check); the
file's sha256 is recorded in every annotation so the table can be frozen before confirmation.
Only "defect, then correction, then satisfied" supports a recovery claim.

usage: python -m cloq.fork_annotate --dir analysis/fork/gate/q4_gptq_w4_d1 [--glob '*_fwd.json']
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

from cloq import fork as F

VERSION = "fork-annot-v1"
ROOT = Path(__file__).resolve().parent.parent
TT_PATH = ROOT / "analysis/insights/iter_4/tool_types.py"
_spec = importlib.util.spec_from_file_location("tool_types", TT_PATH)
TT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(TT)
TT_SHA = hashlib.sha256(TT_PATH.read_bytes()).hexdigest()

CONFIRM_RE = re.compile(r"\b(yes|yeah|yep|confirm|confirmed|go ahead|proceed|please do|sure|correct|that'?s right|ok|okay|do it|sounds good)\b", re.I)
OBJECT_RE = re.compile(r"\b(no|don'?t|do not|cancel that|wrong|that'?s not|not what i)\b", re.I)


def _is_id_key(k: str) -> bool:
    return k.endswith("_id") or k.endswith("_ids") or k in ("user_id", "order_id", "reservation_id", "payment_method_id", "customer_id", "line_id")


def _id_values(args: dict) -> list[str]:
    out = []
    for k, v in (args or {}).items():
        if _is_id_key(k):
            for x in (v if isinstance(v, list) else [v]):
                if isinstance(x, (str, int)) and str(x):
                    out.append(str(x))
    return out


def _text_of(msgs: list[dict]) -> str:
    parts = []
    for m in msgs:
        parts.append(m.get("content") or "")
        for tc in m.get("tool_calls") or []:
            parts.append(json.dumps(tc.get("arguments"), default=str))
    return "\n".join(parts)


def defects(st: dict, action: dict, results: list[dict], schemas: dict) -> dict:
    """Automatic defect checks for one current action. `results`: the tool messages that answered it in a branch."""
    dom = st["domain"]
    view = F.action_view(action, schemas)
    hist = st["history"]
    seen = _text_of(hist)
    last_user = next((m.get("content") or "" for m in reversed(hist) if m["role"] == "user" and not m.get("tool_calls")), "")
    calls = []
    for i, tc in enumerate(action.get("tool_calls") or []):
        name = tc.get("name")
        a = F._args(tc.get("arguments"))
        a = a if isinstance(a, dict) else {}
        ttype = TT.tool_type(dom, name)
        res = results[i] if i < len(results) else None
        c = {"name": name, "type": ttype, "invalid_tool": ttype == "invalid",
             "invalid_args": bool(view["calls"][i]["invalid_args"]) if i < len(view["calls"]) else None,
             "exec_error": bool(res.get("error")) if res else None,
             "exec_error_text": (res.get("content") or "")[:300] if res and res.get("error") else None,
             "ungrounded_ids": [v for v in _id_values(a) if v not in seen],
             "write_unconfirmed_proxy": ttype == "write" and not CONFIRM_RE.search(last_user)}
        calls.append(c)
    ends = view["kind"] == "stop" or any(c["type"] == "handoff" for c in calls)
    flags = {
        "invalid_tool": any(c["invalid_tool"] for c in calls),
        "invalid_args": any(c["invalid_args"] for c in calls),
        "exec_error": any(c["exec_error"] for c in calls),
        "ungrounded_ids": any(c["ungrounded_ids"] for c in calls),
        "write_unconfirmed_proxy": any(c["write_unconfirmed_proxy"] for c in calls),
        "malformed": view["kind"] in ("parse_fail", "empty"),
        "ends_episode": ends,
    }
    return {"kind": view["kind"], "calls": calls, "flags": flags, "manual": None}


def _suffix_results(suffix: list[dict], n_calls: int) -> list[dict]:
    """Tool messages right after the forced action (suffix[0] is the forced action)."""
    out = []
    for m in suffix[1:]:
        if m["role"] != "tool" or len(out) >= n_calls:
            break
        out.append(m)
    return out


def correction(dfx: dict, suffix: list[dict], dom: str) -> dict:
    """Evidence of a later agent turn aimed at each automatic defect of the forced action (suffix[0])."""
    ev = {}
    later = suffix[1:]
    agent_idx = [i for i, m in enumerate(later) if m["role"] == "assistant"]
    seen = _text_of(later)

    def result_of(i, j):  # tool message answering call j of agent message later[i]
        k = i + 1 + j
        return later[k] if k < len(later) and later[k]["role"] == "tool" else None

    for c in dfx["calls"]:
        if c["exec_error"] or c["invalid_args"] or c["invalid_tool"]:
            hit = None
            for i in agent_idx:
                for j, tc in enumerate(later[i].get("tool_calls") or []):
                    same = tc.get("name") == c["name"] or (c["invalid_tool"] and TT.tool_type(dom, tc.get("name")) != "invalid")
                    r = result_of(i, j)
                    if same and r is not None and not r.get("error"):
                        hit = hit or {"turn": i, "tool": tc.get("name")}
            ev[f"{c['name']}:retry_ok"] = hit
        if c["ungrounded_ids"]:
            hit = None
            for i in agent_idx:
                for tc in later[i].get("tool_calls") or []:
                    a = F._args(tc.get("arguments"))
                    if tc.get("name") == c["name"] and isinstance(a, dict) and not set(_id_values(a)) & set(c["ungrounded_ids"]):
                        hit = hit or {"turn": i}
            ev[f"{c['name']}:regrounded"] = hit
        if c["write_unconfirmed_proxy"]:
            obj = next((i for i, m in enumerate(later) if m["role"] == "user" and OBJECT_RE.search(m.get("content") or "")), None)
            writes = [(i, tc.get("name")) for i in agent_idx for tc in (later[i].get("tool_calls") or [])
                      if TT.tool_type(dom, tc.get("name")) == "write"]
            ev[f"{c['name']}:after_unconfirmed_write"] = {"user_objection_turn": obj, "later_writes": writes[:10]}
    found = any(v for k, v in ev.items() if not k.endswith("after_unconfirmed_write"))
    return {"evidence": ev, "any_auto_correction": found if ev else None, "manual": None}


def _diff(a, b, path="", out=None, limit=60):
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append(f"{path}/{k}")
            else:
                _diff(a[k], b[k], f"{path}/{k}", out, limit)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            _diff(x, y, f"{path}[{i}]", out, limit)
    elif a != b:
        out.append(path or "/")
    return out


def requirements(st: dict, branch: dict) -> dict:
    """End-of-branch requirement status, per assertion / gold action / DB field."""
    from tau2.data_model.tasks import Task

    task = Task.model_validate(st["task"])
    full = st["history"] + branch["suffix"]
    pred = F.restore_env(st["domain"], task, [F.msg_from_dict(m) for m in full])
    mh = [F.msg_from_dict(m) for m in ((st["task"].get("initial_state") or {}).get("message_history") or [])]
    gold = F.restore_env(st["domain"], task, mh)
    for act in (task.evaluation_criteria.actions or []) if task.evaluation_criteria else []:
        try:
            gold.make_tool_call(tool_name=act.name, requestor=act.requestor, **act.arguments)
        except Exception:
            pass
    ri = branch.get("reward_info") or {}
    dbd = _diff(pred.tools.db.model_dump(mode="json"), gold.tools.db.model_dump(mode="json"))
    udbd = (_diff(pred.user_tools.db.model_dump(mode="json"), gold.user_tools.db.model_dump(mode="json"))
            if pred.user_tools is not None and getattr(pred.user_tools, "db", None) is not None else None)
    succ_name = "official task-basis success" if st["domain"] == "telecom" else "DB success"
    succ = (branch.get("official_reward") == 1.0) if st["domain"] == "telecom" else bool(branch.get("db_match")) and \
        branch.get("termination_reason") in ("user_stop", "agent_stop")
    return {
        "success_name": succ_name, "success": succ, "termination": branch.get("termination_reason"),
        "db_match": branch.get("db_match"), "db_diff_paths": dbd, "user_db_diff_paths": udbd,
        "env_assertions": [{"func": (x.get("env_assertion") or {}).get("func_name"), "met": x.get("met")} for x in ri.get("env_assertions") or []],
        "action_checks": [{"name": (x.get("action") or {}).get("name"), "match": x.get("action_match")} for x in ri.get("action_checks") or []],
        "communicate_checks": [{"info": x.get("info"), "met": x.get("met")} for x in ri.get("communicate_checks") or []],
    }


def annotate_state(st: dict, branches: dict[str, dict]) -> dict:
    schemas = F.tool_schemas(_tools(st["domain"]))
    out = {"version": VERSION, "tool_types_sha256": TT_SHA, "tool_types_path": str(TT_PATH.relative_to(ROOT)),
           "state_id": st["state_id"], "domain": st["domain"], "task_id": st["task_id"], "t": st["decision_idx"],
           "category": (st.get("divergence") or {}).get("category"), "budget": st["budget"], "branches": {}}
    for b, r in branches.items():
        if "error" in r:
            out["branches"][b] = {"error": r["error"]}
            continue
        first = r["first"]
        act = st["a_" + first]["message"]
        dfx = defects(st, act, _suffix_results(r["suffix"], len(act.get("tool_calls") or [])), schemas)
        req = requirements(st, r)
        dfx["flags"]["premature_end"] = bool(dfx["flags"]["ends_episode"] and not req["success"])
        out["branches"][b] = {"first": first, "controller": r["controller"], "defect": dfx,
                              "correction": correction(dfx, r["suffix"], st["domain"]), "requirements": req,
                              "steps_left_at_state": st["budget"]["steps_left"], "errors_left_at_state": st["budget"]["errors_left"]}
    return out


_TOOLS: dict = {}


def _tools(domain: str) -> list[dict]:
    if domain not in _TOOLS:
        from tau2.runner.build import build_environment

        _TOOLS[domain] = [t.openai_schema for t in build_environment(domain).get_tools()]
    return _TOOLS[domain]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="fork output dir with states/ and branches/")
    ap.add_argument("--glob", default="*.json")
    a = ap.parse_args()
    from loguru import logger

    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    d = ROOT / a.dir
    states = {p.stem: json.loads(p.read_text()) for p in (d / "states").glob("*.json")}
    rows = []
    for p in sorted((d / "branches").glob(a.glob)):
        sid = p.stem.split("_")[0]
        if sid not in states:
            continue
        rows.append({"file": p.name, **annotate_state(states[sid], json.loads(p.read_text()))})
    outp = d / "annotations.jsonl"
    outp.write_text("".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in rows))
    print(f"{len(rows)} annotated -> {outp}")


if __name__ == "__main__":
    main()
