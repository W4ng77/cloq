"""Controlled recovery intervention (EXECUTION_PLAN_20260930.md §5.5; CONSEQUENCE_ANALYSIS_PLAN.md §8; W71).

At identical frozen ordinary Q states (one block per model), inject a matched INVALID action, its matched VALID
counterpart, and a negative-control (NC) action, then continue to the end under B and under Q with the restored
step/error budget. Reuses the fork branch machinery unchanged (cloq.fork.make_state / run_branch: the forced current
action is st["a_<X>"]); scripts/a6000/fork_driver.py is not touched (Bank U work, agent a5468c1, edits it).

Error categories (frozen; the most frequent automatically checkable defect types among development fork actions,
analysis/annotation/wp5/events.jsonl and fork_annotate):
  wrong_id        Q's recorded action is one read call with an id argument that is grounded (in DB and conversation).
                  INVALID = the same call with that id replaced by a well-formed id absent from the DB (deterministic
                  digit/letter rotation, checked absent); VALID = the recorded call.
  wrong_tool      Q's recorded action is one read call. INVALID = a plausible but wrong read tool of the same domain
                  (fixed map below) with the same arguments; VALID = the recorded call.
  premature_write Q's recorded action is a text message that asks for confirmation (confirm / proceed / shall I / ...)
                  and Q's next agent action in the original episode (after one user turn) is a write call whose every
                  argument value already appears in the history at t (no information from the future). INVALID = that
                  write issued now, before the user's reply (no consent); VALID = the recorded confirmation request.
  NC (all states) a repeat of the most recent successful read call in the history (same tool and arguments): it
                  changes no requirement and no DB state.
VALID with controller Q is the original episode (built-in no-op check: it must reproduce Q's recorded outcome).
Branches per state: {INV, VAL, NC} x {B, Q} = 6.

State selection (CPU, frozen before any branch): per model, Q block a6k2_<m>_gptq_w4_d1_q3 (retail + airline);
eligible decision t per category as above, at least one earlier successful read call (for NC), t >= 1, steps left
>= 20; per category 10 states in sha256(salt|run|domain|task|t) order, at most one state per task across
categories. -> manifests/recovery/inject_v1.json

usage:
  python scripts/a6000/inject_driver.py --select [--write]                # CPU: eligibility counts / frozen manifest
  python scripts/a6000/inject_driver.py --task <task.json> --b-base URL --q-base URL --user-base URL --servers <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(os.environ.get("CLOQ_ROOT", "/data/ziyangs/cloq"))
sys.path.insert(0, str(ROOT))
MAN = ROOT / "manifests/recovery/inject_v1.json"
SALT = "inject-v1"
BLOCK = "a6k2_{m}_gptq_w4_d1_q3"
N_PER_CAT = 10
CATS = ("wrong_id", "wrong_tool", "premature_write")
WRONG_TOOL = {  # recorded read tool -> plausible wrong read tool (same domain)
    "retail": {"get_order_details": "get_product_details", "get_product_details": "get_order_details",
               "get_user_details": "get_order_details", "find_user_id_by_name_zip": "find_user_id_by_email",
               "find_user_id_by_email": "find_user_id_by_name_zip", "list_all_product_types": "get_product_details"},
    "airline": {"get_reservation_details": "get_user_details", "get_user_details": "get_reservation_details",
                "search_direct_flight": "search_onestop_flight", "search_onestop_flight": "search_direct_flight",
                "get_flight_status": "get_reservation_details", "list_all_airports": "get_user_details"},
}


def sha(x) -> str:
    return hashlib.sha256((x if isinstance(x, str) else json.dumps(x, sort_keys=True, default=str)).encode()).hexdigest()


def _rot(v: str) -> str:
    out = []
    for ch in v:
        if ch.isdigit():
            out.append(str((int(ch) + 7) % 10))
        elif ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            out.append(chr(base + (ord(ch) - base + 11) % 26))
        else:
            out.append(ch)
    return "".join(out)


CONSENT_ASK = __import__("re").compile(r"\b(confirm|proceed|shall i|should i|would you like me to|do you want me to|yes)\b", 2)


def _scalars(o) -> list:
    if isinstance(o, dict):
        return [y for v in o.values() for y in _scalars(v)]
    if isinstance(o, list):
        return [y for v in o for y in _scalars(v)]
    return [o] if isinstance(o, (str, int)) and not isinstance(o, bool) and str(o) not in ("", "0", "1") else []


def candidates(m: str) -> list[dict]:
    from cloq import fork as F
    from cloq.fork_annotate import TT, _id_values, _is_id_key
    out = []
    run = BLOCK.format(m=m)
    for dom in ("retail", "airline"):
        b = F.Block(ROOT, run, dom)
        for tid, tr in b.traj.items():
            msgs = tr["messages"]
            n0 = F.prefix_len(tr["task"])
            pos = F.agent_positions(msgs, n0)
            if len(pos) != len(b.dec[tid]):
                continue
            for t, p in enumerate(pos):
                if t < 1:
                    continue
                steps, _ = F.budget_used(msgs[:p], n0)
                if 200 - steps < 20:
                    continue
                hist = msgs[:p]
                prior_reads = []
                for i, x in enumerate(hist):
                    if x.get("role") == "assistant" and x.get("tool_calls") and len(x["tool_calls"]) == 1:
                        tc = x["tool_calls"][0]
                        res = hist[i + 1] if i + 1 < len(hist) else None
                        if TT.tool_type(dom, tc["name"]) == "read" and res and res.get("role") == "tool" and not res.get("error"):
                            prior_reads.append(tc)
                if not prior_reads:
                    continue
                a = msgs[p]
                tcs = a.get("tool_calls") or []
                base = {"model": m, "run_id": run, "domain": dom, "task_id": tid, "t": t, "nc_call": prior_reads[-1]}
                text = " ".join(str(x.get("content") or "") for x in hist)
                if len(tcs) == 1 and TT.tool_type(dom, tcs[0]["name"]) == "read":
                    tc = tcs[0]
                    args = F._args(tc.get("arguments")) or {}
                    ids = [(k, v) for k, v in args.items() if _is_id_key(k) and isinstance(v, str) and v in text]
                    if ids:
                        out.append({**base, "category": "wrong_id", "id_key": ids[0][0], "id_value": ids[0][1]})
                    if tc["name"] in WRONG_TOOL[dom]:
                        out.append({**base, "category": "wrong_tool", "wrong_tool": WRONG_TOOL[dom][tc["name"]]})
                if not tcs and (a.get("content") or "").strip():
                    later = [x for x in msgs[p + 1:] if x.get("role") == "assistant"]
                    users_between = [x for x in msgs[p + 1:] if x.get("role") == "user"][:1]
                    if later and users_between and later[0].get("tool_calls") and len(later[0]["tool_calls"]) == 1 \
                            and TT.tool_type(dom, later[0]["tool_calls"][0]["name"]) == "write" \
                            and CONSENT_ASK.search(a.get("content") or "") \
                            and all(str(v) in text for v in _scalars(F._args(later[0]["tool_calls"][0].get("arguments")) or {})):
                        out.append({**base, "category": "premature_write", "write_call": later[0]["tool_calls"][0]})
    return out


def select(write: bool) -> dict:
    from cloq import fork as F
    F.setup_tau2()
    res = {"manifest": "inject_v1", "salt": SALT, "rule": __doc__.split("State selection")[1].split("usage:")[0].strip(), "models": {}}
    for m in ("q4", "q8"):
        cands = candidates(m)
        elig = {c: sum(1 for x in cands if x["category"] == c) for c in CATS}
        chosen, used = [], set()
        for c in CATS:
            got = 0
            for x in sorted([x for x in cands if x["category"] == c], key=lambda x: sha(f"{SALT}|{x['run_id']}|{x['domain']}|{x['task_id']}|{x['t']}")):
                if got >= N_PER_CAT or (x["domain"], x["task_id"]) in used:
                    continue
                used.add((x["domain"], x["task_id"]))
                x["state_key"] = sha(f"{SALT}|{x['run_id']}|{x['domain']}|{x['task_id']}|{x['t']}|{c}")[:16]
                chosen.append(x)
                got += 1
        res["models"][m] = {"block": BLOCK.format(m=m), "eligible": elig, "n": len(chosen),
                            "by_category": {c: sum(1 for x in chosen if x["category"] == c) for c in CATS},
                            "by_domain": {d: sum(1 for x in chosen if x["domain"] == d) for d in ("retail", "airline")}, "states": chosen}
    if write:
        if MAN.exists():
            raise SystemExit(f"{MAN} exists; frozen")
        MAN.parent.mkdir(parents=True, exist_ok=True)
        res["created_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        MAN.write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({m: {k: v for k, v in r.items() if k != "states"} for m, r in res["models"].items()}, indent=1))
    return res


# ----------------------------------------------------------------------------
# branches (GPU task; worker kind "fork" with fork.driver = "inject")
# ----------------------------------------------------------------------------


def build_state(x: dict) -> dict:
    """Ordinary Q state at (task, t) with the three injected actions as a_INV / a_VAL / a_NC."""
    from cloq import fork as F
    from cloq.fork_annotate import _db_text, _state_env
    b = F.Block(ROOT, x["run_id"], x["domain"])
    st = F.make_state(b, x["task_id"], x["t"])
    aq = st["a_Q"]["message"]
    mk = lambda tcs, content=None: {"role": "assistant", "content": content, "tool_calls": tcs, "requestor": "assistant"}
    tc0 = (aq.get("tool_calls") or [None])[0]
    if x["category"] == "wrong_id":
        args = dict(F._args(tc0["arguments"]))
        bad = _rot(x["id_value"])
        dbt = _db_text(_state_env(st))
        while bad in dbt:
            bad = _rot(bad)
        args[x["id_key"]] = bad
        inv = mk([{**tc0, "id": "inj-inv", "arguments": args}])
        st["injection"] = {"category": "wrong_id", "key": x["id_key"], "valid_value": x["id_value"], "invalid_value": bad}
    elif x["category"] == "wrong_tool":
        inv = mk([{**tc0, "id": "inj-inv", "name": x["wrong_tool"]}])
        st["injection"] = {"category": "wrong_tool", "valid_tool": tc0["name"], "invalid_tool": x["wrong_tool"]}
    else:
        inv = mk([{**x["write_call"], "id": "inj-inv"}])
        st["injection"] = {"category": "premature_write", "write_call": x["write_call"]}
    st["a_INV"] = {"message": inv, "source": "injected"}
    st["a_VAL"] = {"message": aq, "source": "recorded a_Q"}
    st["a_NC"] = {"message": mk([{**x["nc_call"], "id": "inj-nc"}]), "source": "repeat of the last successful read"}
    st["inject_key"] = x["state_key"]
    return st


def run_task(spec: dict, bases: dict, user_base: str, servers: dict, out: Path) -> dict:
    from cloq import fork as F
    F.setup_tau2()
    man = json.loads(MAN.read_text())
    xs = man["models"][spec["model"]]["states"]
    out.mkdir(parents=True, exist_ok=True)
    states = []
    for x in xs:
        st = build_state(x)
        (out / "states").mkdir(parents=True, exist_ok=True)
        (out / "states" / f"{x['state_key']}.json").write_text(json.dumps(st, default=str))
        states.append(st)
    jobs = [(st, f, c) for st in states for f in ("INV", "VAL", "NC") for c in ("B", "Q")]
    t0 = time.time()

    def one(j):
        st, f, c = j
        try:
            r = F.run_branch(st, f, c, bases, user_base, f"inj-{st['inject_key']}-{f}{c}")
        except Exception as e:
            r = {"error": repr(e)[:500]}
        return st["inject_key"], f + c, r

    with ThreadPoolExecutor(spec.get("concurrency", 8)) as ex:
        res = list(ex.map(one, jobs))
    per = {}
    for k, b, r in res:
        per.setdefault(k, {})[b] = r
    for k, rs in per.items():
        (out / "branches").mkdir(parents=True, exist_ok=True)
        (out / "branches" / f"{k}.json").write_text(json.dumps(rs, default=str))
    rows = []
    for st in states:
        rs = per[st["inject_key"]]
        orig = st["orig"]
        rows.append({"state_key": st["inject_key"], "category": st["injection"]["category"], "domain": st["domain"], "task_id": st["task_id"],
                     "t": st["decision_idx"], "Y": {b: r.get("official_reward") if st["domain"] == "telecom" else
                                                    int(bool(r.get("db_match")) and r.get("termination_reason") in ("user_stop", "agent_stop"))
                                                    for b, r in rs.items() if "error" not in r},
                     "errors": {b: r["error"] for b, r in rs.items() if "error" in r},
                     "noop_VALQ": {"reward_eq": rs.get("VALQ", {}).get("reward") == orig.get("reward"),
                                   "termination_eq": rs.get("VALQ", {}).get("termination_reason") == orig.get("termination_reason"),
                                   "suffix_eq": rs.get("VALQ", {}).get("suffix_sha") == orig.get("suffix_sha")}})
    summ = {"protocol": "inject-v1", "model": spec["model"], "seconds": time.time() - t0, "n_states": len(states), "n_branches": len(jobs),
            "servers": servers, "rows": rows,
            "noop_VALQ_ok": sum(all(r["noop_VALQ"].values()) for r in rows)}
    (out / "inject.json").write_text(json.dumps(summ, indent=1, default=str))
    return summ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--select", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--task")
    ap.add_argument("--b-base")
    ap.add_argument("--q-base")
    ap.add_argument("--user-base", default="http://127.0.0.1:8000/v1")
    ap.add_argument("--servers")
    a = ap.parse_args()
    from loguru import logger
    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    if a.select:
        select(a.write)
        return
    task = json.load(open(a.task))
    spec = task["fork"]
    r = run_task(spec, {"B": a.b_base, "Q": a.q_base}, a.user_base, json.load(open(a.servers)) if a.servers else {}, ROOT / spec["out"])
    print(json.dumps({k: v for k, v in r.items() if k not in ("rows", "servers")}))


if __name__ == "__main__":
    main()
