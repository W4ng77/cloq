"""Key-order perturbation (docs/insights/KEYORDER_PERTURB_PROTOCOL.md, ko-v1): frozen transform + CPU eligibility scan.

Transform (frozen, exactly one): for every tool call of Q's recorded action, reverse the order of the TOP-LEVEL keys of its
arguments object. Values are copied unchanged (nested objects keep their own key order, arrays their element order);
tool names, the number of calls, call order, call ids and message content are untouched.
Eligibility (built before any key-order suffix exists; reads only states/*.json, never branches/ or any outcome field):
  a  Q's action is a tool call; every call has a dict arguments object; at least one call has >= 2 keys (order changes)
  b  parsed actions identical (dict equality and cloq.metrics.normalize_tool_call per call; fork compare_actions 'same')
  c  each action executed on its own freshly restored environment: identical tool messages (content, error, requestor),
     DB / user-DB hashes and (steps, errors) recount
  d  the original episode has a next Q decision, the locally rendered next prompt of the original action reproduces Q's
     recorded next prompt ids (render path check), and the transformed action's next prompt ids differ from it
usage: python scripts/a6000/keyorder_scan.py --out manifests/fork/keyorder_v1.json [--max N]   (CPU only)
       python scripts/a6000/keyorder_scan.py --selftest
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
VERSION, RULE = "ko-v1", "reverse-top-level-keys"
GROUPS = [f"analysis/fork/dev/q8_gptq_w4_d1/g{i}" for i in (1, 2, 3, 4)]  # Bank P q8 gptq_w4_d1: 20 blocks, 1473 states
MODEL = {"CLOQ_MODEL_ID": "Qwen/Qwen3-8B", "CLOQ_MODEL_REVISION": "b968826d9c46dd6066d109eabc6255188de91218",
         "CLOQ_CHAT_TEMPLATE_KWARGS": json.dumps({"enable_thinking": False}), "CLOQ_MAX_PROMPT_TOKENS": "32768",
         "HF_HOME": "/data/ziyangs/cloq_work/hf", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
FORBIDDEN = ("orig.reward", "orig.db_match", "orig.official_reward", "orig.termination_reason")  # never read here


def raw_sha(obj) -> str:
    """sha256 of JSON WITHOUT key sorting (cloq.fork.sha sorts keys and would equate the two orders)."""
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def transform(msg: dict) -> dict:
    out = copy.deepcopy(msg)
    for tc in out.get("tool_calls") or []:
        a = tc.get("arguments")
        if isinstance(a, dict):
            tc["arguments"] = {k: a[k] for k in reversed(list(a))}
    return out


def key_orders(msg: dict) -> list:
    return [list(tc["arguments"]) if isinstance(tc.get("arguments"), dict) else None for tc in msg.get("tool_calls") or []]


def execute(F, st: dict, action: dict) -> dict:
    """Run the action's tool calls on a freshly restored environment, exactly as Orchestrator._execute_tool_calls."""
    from tau2.data_model.tasks import Task

    env = F.restore_env(st["domain"], Task.model_validate(st["task"]), [F.msg_from_dict(m) for m in st["history"]])
    m = F.msg_from_dict(action)
    tools = [F.msg_to_dict(env.get_response(tc)) for tc in m.tool_calls]
    hist = st["history"] + [action] + tools
    return {"tools": tools, "tool_view": [(t["content"], bool(t["error"]), t["requestor"], t["id"]) for t in tools],
            "env": F.env_hashes(env), "budget": list(F.budget_used(hist, st["n_prefix"])), "hist": hist}


def next_ids(F, st: dict, hist: list) -> list[int]:
    return F.local_prompt_ids({**st, "history": hist})  # the forced a_Q of st only stands in for the next decision


def scan_state(F, st: dict) -> dict:
    from cloq.metrics import normalize_tool_call

    a_q = st["a_Q"]["message"]
    row = {"state_id": st["state_id"], "run_id": st["run_id"], "block": st["run_id"].rsplit("_", 1)[1], "domain": st["domain"],
           "task_id": st["task_id"], "t": st["decision_idx"], "history_sha": st["history_sha"],
           "prompt_ids_sha": st["q_decision"]["prompt_ids_sha"], "q_kind": st["divergence"]["q_kind"],
           "divergence_category": st["divergence"]["category"], "n_calls": len(a_q.get("tool_calls") or []),
           "eligible": False, "reason": None}
    tcs = a_q.get("tool_calls") or []
    if not tcs:
        return {**row, "reason": "a:not_tool_call"}
    if any(not isinstance(tc.get("arguments"), dict) for tc in tcs):
        return {**row, "reason": "a:arguments_not_object"}
    if max(len(tc["arguments"]) for tc in tcs) < 2:
        return {**row, "reason": "a:lt2_keys"}
    a_k = transform(a_q)
    row.update(q_key_order=key_orders(a_q), k_key_order=key_orders(a_k), a_Q_raw_sha=raw_sha(a_q["tool_calls"]),
               a_K_raw_sha=raw_sha(a_k["tool_calls"]), n_keys=[len(o) for o in key_orders(a_q)])
    norm = lambda m: [normalize_tool_call(tc["name"], tc["arguments"]) for tc in m["tool_calls"]]  # noqa: E731
    schemas = F.tool_schemas(json.loads(json.dumps(tools_schema(st["domain"]))))
    b = {"dict_equal": F.canon_msg(a_k) == F.canon_msg(a_q), "norm_equal": norm(a_k) == norm(a_q),
         "compare_same": F.compare_actions(a_q, a_k, schemas)["category"] == "same", "raw_differs": row["a_Q_raw_sha"] != row["a_K_raw_sha"]}
    row["check_b"] = b
    if not all(b.values()):
        return {**row, "reason": "b:parsed_actions_differ"}
    eq, ek = execute(F, st, a_q), execute(F, st, a_k)
    c = {"tool_messages": eq["tool_view"] == ek["tool_view"], "env_hash": eq["env"] == ek["env"], "budget": eq["budget"] == ek["budget"]}
    row.update(check_c=c, budget_after=eq["budget"], k_tool_view_sha=raw_sha(ek["tool_view"]))
    if not all(c.values()):
        return {**row, "reason": "c:execution_differs"}
    rec_next = (st["orig"].get("suffix_prompt_ids_sha") or [None, None])[1:2]  # prompt hashes only, never an outcome
    if not rec_next or rec_next[0] is None:
        return {**row, "reason": "d:no_next_decision"}
    iq, ik = next_ids(F, st, eq["hist"]), next_ids(F, st, ek["hist"])
    first = next((i for i, (x, y) in enumerate(zip(iq, ik)) if x != y), min(len(iq), len(ik)))
    d = {"q_render_matches_record": F.ids_sha(iq) == rec_next[0], "k_tokens_differ": iq != ik}
    row.update(check_d=d, q_next_ids_sha=F.ids_sha(iq), k_next_ids_sha=F.ids_sha(ik), n_next_q=len(iq), n_next_k=len(ik),
               first_diff_token=first, n_diff_positions=sum(x != y for x, y in zip(iq, ik)) + abs(len(iq) - len(ik)))
    if not d["q_render_matches_record"]:
        return {**row, "reason": "d:render_mismatch"}
    if not d["k_tokens_differ"]:
        return {**row, "reason": "d:tokens_identical"}
    return {**row, "eligible": True}


_TS: dict = {}


def tools_schema(domain: str) -> list:
    if domain not in _TS:
        from tau2.runner.build import build_environment
        _TS[domain] = [t.openai_schema for t in build_environment(domain).get_tools()]
    return _TS[domain]


def setup():
    for k, v in MODEL.items():
        os.environ.setdefault(k, v)
    sys.path.insert(0, str(ROOT))
    from loguru import logger
    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    from cloq import fork as F
    F.setup_tau2()
    return F


def scan(F, max_n: int = 0) -> dict:
    rows = []
    for g in GROUPS:
        for p in sorted((ROOT / g / "states").glob("*.json"))[: max_n or None]:
            st = json.loads(p.read_text())
            assert st["state_id"] == p.stem and st["max_prompt_tokens"] == 32768
            rows.append({"group": g, **scan_state(F, st)})
    reasons: dict = {}
    for r in rows:
        reasons[r["reason"] or "eligible"] = reasons.get(r["reason"] or "eligible", 0) + 1
    el = [r for r in rows if r["eligible"]]
    return {"version": VERSION, "rule": RULE, "protocol": "docs/insights/KEYORDER_PERTURB_PROTOCOL.md", "groups": GROUPS,
            "created": time.strftime("%F %T %Z"), "scanner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "inputs_read": "states/*.json only (history, a_Q, task, budget, prompt-id hashes); no branch file, no outcome field",
            "n_states": len(rows), "n_eligible": len(el), "reasons": reasons,
            "eligible_by_block": {b: sum(r["block"] == b for r in el) for b in sorted({r["block"] for r in rows})},
            "eligible_ids_sha256": raw_sha(sorted(r["state_id"] for r in el)), "rows": rows}


def selftest(F) -> None:
    m = {"role": "assistant", "content": None, "tool_calls": [{"id": "x", "name": "f", "requestor": "assistant",
         "arguments": {"a": 1, "b": {"y": 2, "x": [3, {"q": 1, "p": 2}]}, "c": "z"}}]}
    k = transform(m)
    assert list(k["tool_calls"][0]["arguments"]) == ["c", "b", "a"] and k["tool_calls"][0]["arguments"]["b"] == m["tool_calls"][0]["arguments"]["b"]
    assert list(k["tool_calls"][0]["arguments"]["b"]) == ["y", "x"] and F.canon_msg(k) == F.canon_msg(m) and raw_sha(k) != raw_sha(m)
    assert transform(k) == m and list(m["tool_calls"][0]["arguments"]) == ["a", "b", "c"]  # involution, input untouched
    res = scan(F, max_n=40)
    el = [r for r in res["rows"] if r["eligible"]]
    print(json.dumps({k: res[k] for k in ("n_states", "n_eligible", "reasons")}))
    assert el, "no eligible state in the selftest sample"
    assert all(r["check_d"]["q_render_matches_record"] for r in res["rows"] if "check_d" in r) or any(r["reason"] == "d:render_mismatch" for r in res["rows"])
    print("selftest ok:", el[0]["state_id"], el[0]["q_key_order"], "->", el[0]["k_key_order"], "first diff token", el[0]["first_diff_token"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--max", type=int, default=0, help="states per group (testing only)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    F = setup()
    if a.selftest:
        return selftest(F)
    p = ROOT / a.out
    if p.exists():
        raise SystemExit(f"{a.out} exists (frozen eligibility list); never rewritten")
    res = scan(F, a.max)
    print(json.dumps({k: res[k] for k in ("n_states", "n_eligible", "reasons", "eligible_by_block", "eligible_ids_sha256")}, indent=1))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
