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


def _db_text(env) -> str:
    parts = [json.dumps(env.tools.db.model_dump(mode="json"), default=str)]
    if env.user_tools is not None and getattr(env.user_tools, "db", None) is not None:
        parts.append(json.dumps(env.user_tools.db.model_dump(mode="json"), default=str))
    return "\n".join(parts)


def _state_env(st: dict, extra: list[dict] | None = None):
    from tau2.data_model.tasks import Task

    return F.restore_env(st["domain"], Task.model_validate(st["task"]), [F.msg_from_dict(m) for m in st["history"] + (extra or [])])


def _db_dump(env) -> dict:
    d = {"db": env.tools.db.model_dump(mode="json")}
    if env.user_tools is not None and getattr(env.user_tools, "db", None) is not None:
        d["user_db"] = env.user_tools.db.model_dump(mode="json")
    return d


def defects(st: dict, action: dict, results: list[dict], schemas: dict, env_before=None, reqs_before: dict | None = None) -> dict:
    """Automatic verifiable events of one current action, each with a status and the raw record behind it.

    Statuses: "ok" / "violation" (verifiable from the environment: invalid tool, schema-invalid arguments, a call the
    environment rejected) / "needs_review" (rule support is not enough: an id not found in the DB, a write without an
    explicit confirmation in the last user turn, an episode-ending action in a branch that fails). Legitimate substitutes
    (e.g. an id found in the DB although never mentioned), existing authorisation earlier in the conversation, and a task
    already complete at the state are recorded next to the judgement instead of being ruled out by a string rule."""
    dom = st["domain"]
    view = F.action_view(action, schemas)
    hist = st["history"]
    seen = _text_of(hist)
    env_before = env_before if env_before is not None else _state_env(st)
    dbtxt = _db_text(env_before)
    last_user = next((m.get("content") or "" for m in reversed(hist) if m["role"] == "user" and not m.get("tool_calls")), "")
    any_user_confirm = [i for i, m in enumerate(hist) if m["role"] == "user" and CONFIRM_RE.search(m.get("content") or "")]
    calls = []
    for i, tc in enumerate(action.get("tool_calls") or []):
        name = tc.get("name")
        a = F._args(tc.get("arguments"))
        a = a if isinstance(a, dict) else {}
        ttype = TT.tool_type(dom, name)
        res = results[i] if i < len(results) else None
        ids = []
        for v in _id_values(a):
            in_db, in_conv = v in dbtxt, v in seen
            ids.append({"value": v, "in_db": in_db, "in_conversation": in_conv,
                        "status": "ok" if (in_db and in_conv) else "needs_review" if (in_db or in_conv) else "violation"})
        consent = None
        if ttype == "write":
            consent = {"last_user_turn": last_user[:300], "explicit_confirmation_last_turn": bool(CONFIRM_RE.search(last_user)),
                       "earlier_confirmation_turns": any_user_confirm[-3:],
                       "status": "ok" if CONFIRM_RE.search(last_user) else "needs_review"}
        c = {"name": name, "arguments": a, "type": ttype,
             "invalid_tool": {"status": "violation" if ttype == "invalid" else "ok"},
             "invalid_args": {"status": "violation" if (i < len(view["calls"]) and view["calls"][i]["invalid_args"]) else "ok",
                              "schema": schemas.get(name)},
             "execution": {"status": ("violation" if res.get("error") else "ok") if res else "not_executed",
                           "result": (res.get("content") or "")[:500] if res else None},
             "env_changing": ttype == "write" and bool(res) and not res.get("error"),
             "ids": ids, "consent_before_write": consent}
        calls.append(c)
    ends = view["kind"] == "stop" or any(c["type"] == "handoff" for c in calls)
    flags = {
        "invalid_tool": any(c["invalid_tool"]["status"] == "violation" for c in calls),
        "invalid_args": any(c["invalid_args"]["status"] == "violation" for c in calls),
        "exec_error": any(c["execution"]["status"] == "violation" for c in calls),
        "id_not_found": any(x["status"] == "violation" for c in calls for x in c["ids"]),
        "id_needs_review": any(x["status"] == "needs_review" for c in calls for x in c["ids"]),
        "write_consent_needs_review": any((c["consent_before_write"] or {}).get("status") == "needs_review" for c in calls),
        "malformed": view["kind"] in ("parse_fail", "empty"),
        "ends_episode": ends,
        "env_changing": any(c["env_changing"] for c in calls),
    }
    return {"kind": view["kind"], "text": (action.get("content") or "")[:1000], "calls": calls, "flags": flags,
            "task_complete_at_state": (reqs_before or {}).get("success"), "manual": None, "llm": None}


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
        bad_exec = c["execution"]["status"] == "violation" or c["invalid_args"]["status"] == "violation" or c["invalid_tool"]["status"] == "violation"
        if bad_exec:
            hit = None
            for i in agent_idx:
                for j, tc in enumerate(later[i].get("tool_calls") or []):
                    same = tc.get("name") == c["name"] or (c["invalid_tool"]["status"] == "violation" and TT.tool_type(dom, tc.get("name")) != "invalid")
                    r = result_of(i, j)
                    if same and r is not None and not r.get("error"):
                        hit = hit or {"turn": i, "tool": tc.get("name")}
            ev[f"{c['name']}:retry_ok"] = hit
        badids = [x["value"] for x in c["ids"] if x["status"] != "ok"]
        if badids:
            hit = None
            for i in agent_idx:
                for tc in later[i].get("tool_calls") or []:
                    a = F._args(tc.get("arguments"))
                    if tc.get("name") == c["name"] and isinstance(a, dict) and not set(_id_values(a)) & set(badids):
                        hit = hit or {"turn": i}
            ev[f"{c['name']}:regrounded"] = hit
        if (c["consent_before_write"] or {}).get("status") == "needs_review":
            obj = next((i for i, m in enumerate(later) if m["role"] == "user" and OBJECT_RE.search(m.get("content") or "")), None)
            writes = [(i, tc.get("name")) for i in agent_idx for tc in (later[i].get("tool_calls") or [])
                      if TT.tool_type(dom, tc.get("name")) == "write"]
            ev[f"{c['name']}:after_unconfirmed_write"] = {"user_objection_turn": obj, "later_writes": writes[:10]}
    found = any(v for k, v in ev.items() if not k.endswith("after_unconfirmed_write"))
    return {"evidence": ev, "any_auto_correction": found if ev else None, "manual": None, "llm": None}


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


def _gold_env(st: dict):
    from tau2.data_model.tasks import Task

    task = Task.model_validate(st["task"])
    mh = [F.msg_from_dict(m) for m in ((st["task"].get("initial_state") or {}).get("message_history") or [])]
    gold = F.restore_env(st["domain"], task, mh)
    for act in (task.evaluation_criteria.actions or []) if task.evaluation_criteria else []:
        try:
            gold.make_tool_call(tool_name=act.name, requestor=act.requestor, **act.arguments)
        except Exception:
            pass
    return task, gold


def _env_status(st: dict, pred, gold, task) -> dict:
    """Requirement status of an environment: DB paths differing from the gold DB, and each env assertion."""
    pd, gd = _db_dump(pred), _db_dump(gold)
    dbd = _diff(pd["db"], gd["db"])
    udbd = _diff(pd["user_db"], gd["user_db"]) if "user_db" in pd and "user_db" in gd else None
    ea = []
    for x in (task.evaluation_criteria.env_assertions or []) if task.evaluation_criteria else []:
        try:
            met = pred.run_env_assertion(x, raise_assertion_error=False)
        except Exception as e:
            met = f"error: {e!r}"[:200]
        ea.append({"func": x.func_name, "env_type": x.env_type, "met": met})
    return {"db_diff_paths": dbd, "user_db_diff_paths": udbd, "env_assertions": ea}


def state_requirements(st: dict) -> dict:
    """Requirements already satisfied at the fork state (is the task complete before the current action?)."""
    task, gold = _gold_env(st)
    s = _env_status(st, _state_env(st), gold, task)
    basis = [str(getattr(b, "value", b)) for b in (task.evaluation_criteria.reward_basis or [])] if task.evaluation_criteria else []
    ok_db = not s["db_diff_paths"] and not s["user_db_diff_paths"]
    ok_ea = all(x["met"] is True for x in s["env_assertions"])
    s["success"] = (ok_ea if st["domain"] == "telecom" else ok_db) if ("DB" in basis or "ENV_ASSERTION" in basis) else None
    s["note"] = "state-level check (DB / env assertions only; gold ACTION and COMMUNICATE checks need the full episode)"
    return s


def requirements(st: dict, branch: dict) -> dict:
    """End-of-branch requirement status, per assertion / gold action / DB field."""
    task, gold = _gold_env(st)
    pred = F.restore_env(st["domain"], task, [F.msg_from_dict(m) for m in st["history"] + branch["suffix"]])
    s = _env_status(st, pred, gold, task)
    ri = branch.get("reward_info") or {}
    succ_name = "official task-basis success" if st["domain"] == "telecom" else "DB success"
    succ = (branch.get("official_reward") == 1.0) if st["domain"] == "telecom" else bool(branch.get("db_match")) and \
        branch.get("termination_reason") in ("user_stop", "agent_stop")
    ac = [{"name": (x.get("action") or {}).get("name"), "arguments": (x.get("action") or {}).get("arguments"), "match": x.get("action_match")}
          for x in ri.get("action_checks") or []]
    cc = [{"info": x.get("info"), "met": x.get("met")} for x in ri.get("communicate_checks") or []]
    failing = ([f"db:{p}" for p in s["db_diff_paths"]] + [f"user_db:{p}" for p in (s["user_db_diff_paths"] or [])]
               + [f"env_assertion:{x['func']}" for x in s["env_assertions"] if x["met"] is not True]
               + [f"action:{x['name']}" for x in ac if not x["match"]] + [f"communicate:{x['info']}" for x in cc if not x["met"]])
    return {"success_name": succ_name, "success": succ, "termination": branch.get("termination_reason"),
            "db_match": branch.get("db_match"), **s, "action_checks": ac, "communicate_checks": cc, "failing": failing}


def annotate_state(st: dict, branches: dict[str, dict]) -> dict:
    schemas = F.tool_schemas(_tools(st["domain"]))
    env_before = _state_env(st)
    before = _db_dump(env_before)
    req0 = state_requirements(st)
    out = {"version": VERSION, "tool_types_sha256": TT_SHA, "tool_types_path": str(TT_PATH.relative_to(ROOT)),
           "state_id": st["state_id"], "domain": st["domain"], "task_id": st["task_id"], "t": st["decision_idx"],
           "category": (st.get("divergence") or {}).get("category"), "budget": st["budget"],
           "requirements_at_state": req0, "branches": {}}
    for b, r in branches.items():
        if "error" in r:
            out["branches"][b] = {"error": r["error"]}
            continue
        first = r["first"]
        act = st["a_" + first]["message"]
        n_calls = len(act.get("tool_calls") or [])
        res = _suffix_results(r["suffix"], n_calls)
        dfx = defects(st, act, res, schemas, env_before, req0)
        after = _db_dump(_state_env(st, r["suffix"][: 1 + len(res)])) if n_calls else before
        changed = {k: _diff(before[k], after[k]) for k in before if k in after}
        req = requirements(st, r)
        dfx["flags"]["premature_end"] = bool(dfx["flags"]["ends_episode"] and not req["success"])
        dfx["premature_end"] = None if not dfx["flags"]["ends_episode"] else {
            "status": "ok" if req["success"] else ("ok_task_already_complete" if req0.get("success") else "needs_review"),
            "branch_success": req["success"], "task_complete_at_state": req0.get("success")}
        out["branches"][b] = {"first": first, "controller": r["controller"], "defect": dfx, "changed_by_action": changed,
                              "correction": correction(dfx, r["suffix"], st["domain"]), "requirements": req,
                              "extra_steps_used": (r.get("step_count_final") or 0) - st["budget"]["steps_used"],
                              "steps_left_at_state": st["budget"]["steps_left"], "errors_left_at_state": st["budget"]["errors_left"]}
    return out


def review_export(rows: list[dict], states: dict, branch_files: dict, out_dir: Path, salt: str = "fork-review-v1") -> None:
    """Blinded review packets: model, precision, checkpoint, nonce and branch source are stripped; order is random
    (sha256(salt|state|branch)); the key (packet id -> state, branch) is written to a separate file for the analyst.
    Each packet: task instructions, the history at the state, the current action, the continuation, end status, the
    automatic events (reviewers may overrule), and empty label slots (defect / correction / failed requirements, each
    with an evidence-location field and "cannot judge")."""
    out_dir.mkdir(parents=True, exist_ok=True)
    packets, key = [], []
    for row in rows:
        st = states[row["state_id"]]
        for b, ann in row["branches"].items():
            if "error" in ann:
                continue
            br = branch_files[row["file"]][b]
            pid = F.sha(f"{salt}|{row['state_id']}|{b}|{row['file']}")[:12]
            strip = lambda m: {k: m.get(k) for k in ("role", "content", "tool_calls", "requestor", "error") if m.get(k) is not None}
            packets.append({"packet_id": pid, "domain": st["domain"],
                            "instructions": (st["task"].get("user_scenario") or {}), "history": [strip(m) for m in st["history"]],
                            "current_action": strip(br["suffix"][0]), "continuation": [strip(m) for m in br["suffix"][1:]],
                            "end": {"termination": ann["requirements"]["termination"], "success": ann["requirements"]["success"],
                                    "failing": ann["requirements"]["failing"]},
                            "auto_events": {"flags": ann["defect"]["flags"], "calls": ann["defect"]["calls"], "premature_end": ann["defect"].get("premature_end")},
                            "labels": {k: {"value": None, "evidence_location": None, "cannot_judge": False}
                                       for k in ("defect", "correction", "failed_requirements")}, "reviewer": None})
            key.append({"packet_id": pid, "state_id": row["state_id"], "branch": b, "file": row["file"]})
    packets.sort(key=lambda p: p["packet_id"])
    (out_dir / "packets.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False, default=str) + "\n" for p in packets))
    (out_dir / "KEY_unblinding.jsonl").write_text("".join(json.dumps(k) + "\n" for k in key))


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
    ap.add_argument("--review-export", action="store_true", help="also write blinded review packets (+ separate key)")
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
    if a.review_export:
        bfiles = {p.name: json.loads(p.read_text()) for p in sorted((d / "branches").glob(a.glob))}
        review_export(rows, states, bfiles, d / "review")
        print("review packets ->", d / "review")


if __name__ == "__main__":
    main()
