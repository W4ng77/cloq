"""Same-state 2x2 forks on the simulator-free environments (protocol fork-ext-v1; W39-extfork).

Port of fork-v1 (docs/insights/FORK_PROTOCOL.md, scripts/a6000/fork_driver.py) to ALFWorld text and BFCL multi-turn.
Both environments are deterministic and have no LLM user, so a fork state is fully restored by re-executing the recorded
action prefix on a fresh environment (ALFWorld: reset the same game and replay the commands; BFCL: fresh backend class
instances from the entry's initial config, replay the calls through BFCL's own multi-turn loop).

Mechanism (one code path for every branch, search and replay): the adapters' episode functions
(alfworld_run.episode, bfcl_run.run_item) take a `policy(idx, messages, tools) -> raw response` in place of the server
call. A branch XY at state t uses
    idx < t   Q's recorded response (replay; no model call),
    idx == t  a_X (a_Q = Q's recorded response, a_B = B's greedy response at h_t, saved in the state file),
    idx > t   the controller Y's server, live, until the episode ends under the original budget
(ALFWorld 50 actions / 50 decisions counted from the start; BFCL 20 steps per turn, all turns).
Replay fidelity is checked at every replayed step: the messages sent (the agent's prompt) and the observations must equal
the recorded ones, and the backend-state hash (ALFWorld PDDL facts; BFCL canonical instance state) before every decision
must be identical across all branches of a state and equal to the search replay.

Divergence search (§3 of fork-v1): replay Q's recorded trajectory; at each decision send the identical request to the
B server (the harness's own chat request: same template, tool parser, frozen decoding). The server-returned prompt ids
must equal Q's recorded prompt ids (else the item is excluded, never coded as no divergence). The first semantic
divergence is the state: action class (act / talk / parse_fail / empty), tool count, tool name, or normalised arguments
(ALFWorld: the act() command, lower-cased and whitespace-collapsed; BFCL: tool name + JSON arguments, key order and
integral floats normalised). Text-only differences are recorded (text_only_before) but are not states. The Q server
then regenerates a_Q at h_t (checkpoint identity: completion ids must equal the recorded ones).

Modes (task["fork"]["mode"]): gate | gate_same | dev (search + BB/BQ/QB on every state + QQ on a hash sample).
Outputs mirror the tau2 fork files: <out>/states/<sid>.json, <out>/branches/<sid>[_tag].json, search.json,
branches.json (rows {state_id, outcomes{branch:{reward, db_match, official_reward, termination_reason, duration, error}}}),
gate.json / gate_same.json, and effects.jsonl (per state: Y cells, G = Y_BQ - Y_QQ, A = Y_QB - Y_BB, C = Y_BQ - Y_BB,
I = Y_QQ - Y_QB - Y_BQ + Y_BB; dev uses the original Y_QQ, which the QQ no-op sample verifies).

usage (inside a worker "fork" task with "env"; the benchmark venv's python):
  python scripts/ext/fork_ext.py --task <task.json> --b-base URL --q-base URL --servers <json>
"""

from __future__ import annotations

import argparse
import copy
import functools
import hashlib
import json
import multiprocessing as mp
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, ChatError, canonical_json, chat  # noqa: E402

PROTOCOL = "fork-ext-v1"
LOCK = threading.Lock()


def log(msg: str) -> None:
    with LOCK:  # the real stdout (main() silences sys.stdout: BFCL prints every step)
        print(f"[{time.strftime('%F %T')}] {msg}", file=sys.__stdout__, flush=True)


def sha(x) -> str:
    return hashlib.sha256((x if isinstance(x, str) else canonical_json(x)).encode()).hexdigest()


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str))
    tmp.replace(path)


class StopSearch(Exception):
    pass


class ReplayError(Exception):
    pass


# ----------------------------------------------------------------------------
# recorded blocks
# ----------------------------------------------------------------------------


@functools.lru_cache(maxsize=64)
def load_block(run_id: str, domain: str) -> dict:
    d = ROOT / "runs" / run_id / domain
    decs: dict[str, list] = {}
    for l in (d / "decisions.jsonl").read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            decs.setdefault(r["task_id"], []).append(r)
    for v in decs.values():
        v.sort(key=lambda r: r["decision_idx"])
    traj = {json.loads(l)["task_id"]: json.loads(l) for l in (d / "trajectory.jsonl").read_text().splitlines() if l.strip()}
    return {"run_id": run_id, "domain": domain, "decs": decs, "traj": traj,
            "config": json.loads((d / "config.json").read_text()), "environment": json.loads((d / "environment.json").read_text())}


def raw_from_rec(rec: dict) -> dict:
    """The server response a recorded decision came from (vLLM returns tool_calls [] for a text reply)."""
    return {"choices": [{"message": {"role": "assistant", "content": rec["raw_content"], "tool_calls": rec["tool_calls"] or []},
                         "token_ids": rec["completion_token_ids"], "finish_reason": rec["finish_reason"]}],
            "prompt_token_ids": rec["prompt_token_ids"],
            "usage": {"prompt_tokens": rec["n_prompt_tokens"], "completion_tokens": rec["n_completion_tokens"]}}


def msg_of(raw: dict) -> dict:
    m = raw["choices"][0]["message"]
    return {"content": m.get("content"), "tool_calls": m.get("tool_calls") or []}


def strip_ids(messages: list[dict]) -> list[dict]:
    """Messages without tool-call ids (random per server response; never rendered by the Qwen/hermes template)."""
    out = []
    for m in messages:
        m = {k: v for k, v in m.items() if k != "tool_call_id"}
        if m.get("tool_calls"):
            m["tool_calls"] = [{k: v for k, v in tc.items() if k != "id"} for tc in m["tool_calls"]]
        out.append(m)
    return out


# ----------------------------------------------------------------------------
# semantic action comparison
# ----------------------------------------------------------------------------


def _norm_val(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str):
        return " ".join(v.split())
    if isinstance(v, dict):
        return {k: _norm_val(x) for k, x in sorted(v.items())}
    if isinstance(v, list):
        return [_norm_val(x) for x in v]
    return v


def action(env: str, msg: dict) -> dict:
    tcs = msg.get("tool_calls") or []
    content = msg.get("content") or ""
    if not tcs:
        kind = "parse_fail" if "<tool_call>" in content else ("talk" if content.strip() else "empty")
        return {"kind": kind, "calls": [], "text": content}
    calls = []
    for tc in tcs:
        name, args = tc["function"]["name"], tc["function"].get("arguments")
        try:
            a = json.loads(args) if isinstance(args, str) else args
        except Exception:
            a = {"__unparsed__": str(args)}
        if env == "alfworld" and name == "act" and isinstance(a, dict) and isinstance(a.get("command"), str):
            calls.append(["act", " ".join(a["command"].lower().split())])
        else:
            calls.append([name, canonical_json(_norm_val(a))])
    return {"kind": "act", "calls": calls, "text": content}


def compare(env: str, q: dict, b: dict) -> str:
    aq, ab = action(env, q), action(env, b)
    if aq["kind"] != ab["kind"]:
        return f"class:{aq['kind']}->{ab['kind']}"
    if aq["kind"] != "act":
        return "same" if " ".join(aq["text"].split()) == " ".join(ab["text"].split()) else "text_only"
    if len(aq["calls"]) != len(ab["calls"]):
        return "tool_count"
    if aq["calls"] == ab["calls"]:
        return "same" if " ".join(aq["text"].split()) == " ".join(ab["text"].split()) else "text_only"
    if sorted(map(tuple, aq["calls"])) == sorted(map(tuple, ab["calls"])):
        return "multi_tool_order"
    if [c[0] for c in aq["calls"]] != [c[0] for c in ab["calls"]]:
        return "tool_name"
    return "command" if env == "alfworld" else "tool_args"


PRIMARY_EXCLUDE = {"same", "text_only"}


# ----------------------------------------------------------------------------
# engines (the adapters' own episode code)
# ----------------------------------------------------------------------------


@functools.lru_cache(maxsize=8)
def _bfcl_data(category: str):
    import bfcl_run as BR  # noqa: F401
    from bfcl_eval.utils import load_dataset_entry, load_ground_truth_entry
    E = {e["id"]: e for e in load_dataset_entry(category)}
    P = {e["id"]: e for e in load_dataset_entry(category, include_prereq=False, include_language_specific_hint=False)}
    G = {e["id"]: e["ground_truth"] for e in load_ground_truth_entry(category)}
    return E, P, G


def run_env(env: str, domain: str, item: str, policy, tag: str) -> tuple[dict, list[dict]]:
    meta = {"run_id": f"fork:{tag}", "arm": "fork", "domain": domain}
    if env == "alfworld":
        import alfworld_run as AR
        traj, decs, err = AR.episode(item, None, meta, policy=policy, track_state=True)
        if traj is None:
            raise ChatError("outage", err or "")
        return traj, decs
    import bfcl_run as BR
    category = "multi_turn_" + domain[len("bfcl_"):]
    E, P, G = _bfcl_data(category)
    mname = "cf_" + sha(tag)[:12]
    try:
        return BR.run_item(copy.deepcopy(E[item]), P[item], G[item], category, None, meta, policy=policy, model_name=mname,
                           track_state=True)
    finally:
        import re
        import bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils as MU
        for k in [k for k in list(vars(MU)) if k.startswith(re.sub(r"[-./:]", "_", mname + "_"))]:
            vars(MU).pop(k, None)


def outcome(env: str, traj: dict) -> dict:
    y = 1.0 if traj["success"] else 0.0
    o = {"reward": y, "official_reward": y, "db_match": None, "success": bool(traj["success"]),
         "termination_reason": traj["termination_reason"], "n_decisions": traj["n_decisions"]}
    if env == "bfcl":
        o["bfcl_result_sha"] = sha(json.loads(json.dumps(traj["bfcl_result"], default=str)))
        o["error_type"] = ((traj.get("evaluator") or {}).get("error") or {}).get("error_type")
    else:
        o["n_env_steps"] = traj["n_env_steps"]
        o["actions_sha"] = sha([[a["command"], a["observation"]] for a in traj["actions"]])
    return o


# ----------------------------------------------------------------------------
# policies (picklable: ALFWorld runs episodes in worker processes)
# ----------------------------------------------------------------------------


class BranchPolicy:
    def __init__(self, prefix: list[dict], t: int, forced: dict, base: str | None):
        self.prefix, self.t, self.forced, self.base = prefix, t, forced, base
        self.first_live: dict | None = None

    def __call__(self, idx, messages, tools):
        if idx < self.t:
            return self.prefix[idx], 0.0
        if idx == self.t:
            return self.forced, 0.0
        if self.base is None:
            raise ReplayError(f"decision {idx} beyond the replay and no controller")
        raw, dt = chat(self.base, messages, tools)
        return raw, dt


class SearchPolicy:
    """Replays Q's recorded trajectory; at each decision asks B the identical request and stops at the first primary
    divergence (the state is frozen from inside the replay: messages, tools, backend state)."""

    def __init__(self, env: str, recs: list[dict], b_base: str, q_base: str, max_t: int | None = None):
        self.env, self.recs, self.b_base, self.q_base, self.max_t = env, recs, b_base, q_base, max_t
        self.rows, self.found, self.text_only = [], None, []

    def __call__(self, idx, messages, tools):
        if idx >= len(self.recs):
            raise StopSearch("end_of_recorded")
        rec = self.recs[idx]
        if sha(messages) != sha(rec["messages"]):
            raise ReplayError(f"replayed messages differ from the recorded ones at decision {idx}")
        if self.max_t is not None and idx > self.max_t:
            raise StopSearch("max_t")
        t0 = time.time()
        rb, _ = chat(self.b_base, messages, tools)
        dt = time.time() - t0
        pid_ok = rb.get("prompt_token_ids") == rec["prompt_token_ids"]
        cat = compare(self.env, msg_of(raw_from_rec(rec)), msg_of(rb))
        self.rows.append({"t": idx, "category": cat, "prompt_ids_ok": pid_ok, "shadow_seconds": dt})
        if not pid_ok:
            raise StopSearch("prompt_ids_mismatch")
        if cat == "text_only":
            self.text_only.append(idx)
        if cat not in PRIMARY_EXCLUDE:
            rq, _ = chat(self.q_base, messages, tools)
            q_replay = {"completion_ids_ok": rq["choices"][0].get("token_ids") == rec["completion_token_ids"],
                        "prompt_ids_ok": rq.get("prompt_token_ids") == rec["prompt_token_ids"],
                        "action_ok": compare(self.env, msg_of(raw_from_rec(rec)), msg_of(rq)) == "same"}
            self.found = {"t": idx, "category": cat, "a_B": rb, "q_replay": q_replay, "messages": list(messages), "tools": tools,
                          "state_sha": getattr(self, "state_sha", None)}
            raise StopSearch("divergence")
        return raw_from_rec(rec), 0.0


# ----------------------------------------------------------------------------
# jobs (module level: run in threads for BFCL, in spawned processes for ALFWorld)
# ----------------------------------------------------------------------------


def search_job(job: dict) -> dict:
    env, run_id, domain, item = job["env"], job["run_id"], job["domain"], job["item"]
    blk = load_block(run_id, domain)
    recs = blk["decs"].get(item, [])
    tr = blk["traj"][item]
    res = {"run_id": run_id, "domain": domain, "task_id": item, "n_decisions_orig": len(recs)}
    if len(recs) != tr["n_decisions"]:
        return {**res, "status": "excluded", "reason": "decision_count_mismatch"}
    pol = SearchPolicy(env, recs, job["b_base"], job["q_base"], job.get("max_t"))
    t0 = time.time()
    stop = None
    try:
        run_env(env, domain, item, pol, f"search|{run_id}|{domain}|{item}")
    except StopSearch as e:
        stop = str(e)
    except ReplayError as e:
        return {**res, "status": "excluded", "reason": f"replay: {e}", "rows": pol.rows}
    res.update(rows=pol.rows, search_seconds=time.time() - t0, text_only_before=pol.text_only)
    if stop == "prompt_ids_mismatch":
        return {**res, "status": "excluded", "reason": "b_prompt_ids_mismatch"}
    if pol.found is None:
        return {**res, "status": "no_divergence", "stop": stop}
    f = pol.found
    t = f["t"]
    sid = sha([run_id, domain, item, t])[:16]
    rec = recs[t]
    state = {
        "protocol": PROTOCOL, "env": env, "state_id": sid, "run_id": run_id, "domain": domain, "task_id": item, "decision_idx": t,
        "n_decisions_orig": len(recs), "checkpoint": blk["config"].get("checkpoint"), "arm": blk["config"].get("arm"),
        "model": {"hf_id": blk["environment"].get("model_id"), "revision": blk["environment"].get("model_revision"),
                  "chat_template_kwargs": blk["environment"].get("chat_template_kwargs")},
        "history": f["messages"], "history_sha": sha(f["messages"]), "tools": f["tools"], "tools_sha": sha(f["tools"]),
        "state_sha": f["state_sha"],
        "q_decision": {"prompt_ids_sha": sha(rec["prompt_token_ids"]), "n_prompt_tokens": rec["n_prompt_tokens"],
                       "completion_ids_sha": sha(rec["completion_token_ids"]), "parser_error": rec["parser_error"],
                       "finish_reason": rec["finish_reason"]},
        "a_Q": {"raw": raw_from_rec(rec), "action": action(env, msg_of(raw_from_rec(rec))), "source": "decisions.jsonl"},
        "a_B": {"raw": {k: f["a_B"].get(k) for k in ("choices", "prompt_token_ids", "usage")},
                "action": action(env, msg_of(f["a_B"])), "prompt_ids_sha": sha(f["a_B"].get("prompt_token_ids")),
                "completion_ids_sha": sha(f["a_B"]["choices"][0].get("token_ids"))},
        "divergence": {"category": f["category"], "q_kind": action(env, msg_of(raw_from_rec(rec)))["kind"],
                       "b_kind": action(env, msg_of(f["a_B"]))["kind"], "t_star": t, "text_only_before": pol.text_only},
        "q_replay": f["q_replay"],
        "budget": {"decisions_used": t, **({"env_steps_used": recs[t - 1]["n_env_steps"] if t else 0, "max_env_steps": 50,
                                             "max_decisions": 50} if env == "alfworld" else
                                            {"turn_idx": rec.get("turn_idx"), "step_in_turn": rec.get("step_idx"), "max_steps_per_turn": 20})},
        "orig": {**outcome(env, tr), "suffix_prompt_ids_sha": [sha(r["prompt_token_ids"]) for r in recs[t:]],
                 "suffix_completion_ids_sha": [sha(r["completion_token_ids"]) for r in recs[t:]]},
        "created": time.time(),
    }
    out = Path(job["state_dir"]) / f"{sid}.json"
    dump(out, state)
    back = json.loads(out.read_text())  # save/load round trip
    io = {"history_sha_ok": sha(back["history"]) == state["history_sha"], "tools_sha_ok": sha(back["tools"]) == state["tools_sha"],
          "a_B_ok": sha(back["a_B"]["raw"]) == sha(state["a_B"]["raw"])}
    back["io_check"] = io
    dump(out, back)
    return {**res, "status": "state", "state_id": sid, "t": t, "category": f["category"], "q_replay": f["q_replay"], "io_check": io}


def branch_job(job: dict) -> dict:
    """Run one branch XY of a saved state; return its signature, fidelity checks and outcome."""
    st = json.loads(Path(job["state_path"]).read_text())
    env, br, t = st["env"], job["branch"], st["decision_idx"]
    blk = load_block(job.get("orig_run_id") or st["run_id"], st["domain"])
    recs = blk["decs"][st["task_id"]]
    prefix = [raw_from_rec(r) for r in recs[:t]]
    forced = st["a_Q"]["raw"] if br[0] == "Q" else st["a_B"]["raw"]
    base = job["bases"][br[1]]
    pol = BranchPolicy(prefix, t, forced, base)
    t0 = time.time()
    try:
        traj, decs = run_env(env, st["domain"], st["task_id"], pol, f"{job['tag']}|{st['state_id']}|{br}")
    except ChatError as e:
        return {"state_id": st["state_id"], "branch": br, "error": repr(e)[:500], "infrastructure": e.kind == "outage"}
    except Exception as e:
        return {"state_id": st["state_id"], "branch": br, "error": repr(e)[:500], "trace": traceback.format_exc()[-2000:]}
    mism = []
    for i in range(min(t, len(decs))):
        r0, r1 = recs[i], decs[i]
        if sha(r0["messages"]) != sha(r1["messages"]):
            mism.append([i, "messages"])
        if r0.get("observations") != r1.get("observations"):
            mism.append([i, "observations"])
        if env == "alfworld" and r0.get("admissible_commands_after") != r1.get("admissible_commands_after"):
            mism.append([i, "admissible"])
    fid = {"prefix_ok": not mism and len(decs) > t, "mismatch": mism[:10],
           "history_at_t_ok": len(decs) > t and sha(decs[t]["messages"]) == st["history_sha"],
           "state_at_t_ok": (len(decs) > t and decs[t].get("state_sha_before") == st.get("state_sha")) if st.get("state_sha") else None}
    dsig = [{"decision_idx": d["decision_idx"], "forced": d["decision_idx"] == t, "replayed": d["decision_idx"] < t,
             "prompt_ids_sha": sha(d["prompt_token_ids"]), "completion_ids_sha": sha(d["completion_token_ids"]),
             "obs_sha": sha(d.get("observations")), "state_sha_before": d.get("state_sha_before"),
             "api_base": None if d["decision_idx"] <= t else base} for d in decs]
    o = outcome(env, traj)
    suffix_msgs = strip_ids(traj["messages"][len(decs[t]["messages"]):]) if len(decs) > t else []
    return {"tag": f"{job['tag']}-{br}-{st['state_id']}", "state_id": st["state_id"], "branch": br, "first": br[0], "controller": br[1],
            "controller_base": base, **o, "final_state_sha": traj.get("final_state_sha"), "fidelity": fid, "decisions": dsig,
            "state_shas": [d.get("state_sha_before") for d in decs[:t + 1]],
            "suffix_sha": sha(suffix_msgs), "suffix_decisions_sha": sha([(d["prompt_ids_sha"], d["completion_ids_sha"], d["obs_sha"]) for d in dsig[t:]]),
            "duration": time.time() - t0, "n_live_decisions": sum(1 for d in dsig if d["decision_idx"] > t)}


# ----------------------------------------------------------------------------
# checks
# ----------------------------------------------------------------------------


def sig(r: dict) -> str:
    keys = ("reward", "termination_reason", "n_decisions", "final_state_sha", "suffix_sha", "suffix_decisions_sha",
            "bfcl_result_sha", "actions_sha")
    return sha({k: r.get(k) for k in keys})


def noop_check(st: dict, r: dict, recs: list[dict], tr_out: dict) -> dict:
    """The no-op branch (XX forcing X's own recorded action) must reproduce the original from t on."""
    t = st["decision_idx"]
    if r.get("error"):
        return {"ok": False, "error": r["error"]}
    d = r["decisions"]
    c = {
        "n_decisions": len(d) == len(recs),
        "prompt_token_ids": [x["prompt_ids_sha"] for x in d[t:]] == [sha(x["prompt_token_ids"]) for x in recs[t:]],
        "completion_token_ids": [x["completion_ids_sha"] for x in d[t:]] == [sha(x["completion_token_ids"]) for x in recs[t:]],
        "observations": [x["obs_sha"] for x in d] == [sha(x.get("observations")) for x in recs],
        "outcome": all(r.get(k) == tr_out.get(k) for k in ("reward", "termination_reason", "n_decisions", "bfcl_result_sha", "actions_sha")),
        "prefix": r["fidelity"]["prefix_ok"] and r["fidelity"]["history_at_t_ok"],
    }
    c["ok"] = all(c.values())
    return c


def reprefill_check(st: dict, rs: dict, recs: list[dict]) -> dict:
    t = st["decision_idx"]
    out = {}
    qb, bq, bb = rs.get("QB"), rs.get("BQ"), rs.get("BB")
    if qb and not qb.get("error") and len(qb["decisions"]) > t + 1 and len(recs) > t + 1:
        out["QB_first_prompt_eq_orig_Q_t+1"] = qb["decisions"][t + 1]["prompt_ids_sha"] == sha(recs[t + 1]["prompt_token_ids"])
    if bq and bb and not bq.get("error") and not bb.get("error") and len(bq["decisions"]) > t + 1 and len(bb["decisions"]) > t + 1:
        out["BQ_first_prompt_eq_BB_first"] = bq["decisions"][t + 1]["prompt_ids_sha"] == bb["decisions"][t + 1]["prompt_ids_sha"]
    out["ok"] = all(v for v in out.values()) if out else None
    return out


def replay_consistency(rs: dict, st: dict) -> dict:
    """Backend state before every replayed step (and at t) identical across branches and equal to the search replay."""
    shas = [r["state_shas"] for r in rs.values() if not r.get("error")]
    same = all(s == shas[0] for s in shas) if shas else False
    at_t = all(r["fidelity"].get("state_at_t_ok") in (True, None) for r in rs.values() if not r.get("error"))
    pref = all(r["fidelity"]["prefix_ok"] for r in rs.values() if not r.get("error"))
    return {"ok": bool(shas) and same and at_t and pref, "state_hash_equal_across_branches": same, "state_at_t_eq_search": at_t,
            "prefix_obs_messages_ok": pref, "n_steps_checked": len(shas[0]) if shas else 0}


def effects(st: dict, ys: dict) -> dict:
    y = {k: ys.get(k) for k in ("BB", "BQ", "QB", "QQ")}
    rec = {"state_id": st["state_id"], "env": st["env"], "domain": st["domain"], "task_id": st["task_id"], "run_id": st["run_id"],
           "t": st["decision_idx"], "category": st["divergence"]["category"], "Y": y}
    if None not in y.values():
        rec.update(G=y["BQ"] - y["QQ"], A=y["QB"] - y["BB"], C=y["BQ"] - y["BB"], I=y["QQ"] - y["QB"] - y["BQ"] + y["BB"])
    return rec


# ----------------------------------------------------------------------------
# execution helpers
# ----------------------------------------------------------------------------


def pmap(env: str, fn, jobs: list, conc: int) -> list:
    if not jobs:
        return []
    if env == "alfworld":  # TextWorld/PDDL engines in separate processes
        with mp.get_context("spawn").Pool(processes=min(conc, len(jobs)), maxtasksperchild=4) as pool:
            return pool.map(fn, jobs, chunksize=1)
    with ThreadPoolExecutor(conc) as ex:
        return list(ex.map(fn, jobs))


def items_of(spec: dict, run_id: str, domain: str) -> list[str]:
    blk = load_block(run_id, domain)
    ids = sorted(blk["traj"], key=lambda i: sha(f"order|{run_id}|{domain}|{i}"))
    return ids[: spec["n_items"]] if spec.get("n_items") else ids


def do_search(env, spec, bases, out) -> list[dict]:
    jobs = [{"env": env, "run_id": r, "domain": d, "item": i, "b_base": bases["B"], "q_base": bases["Q"],
             "state_dir": str(out / "states"), "max_t": spec.get("max_t")}
            for r, d in (x.split(":") for x in spec["q_blocks"]) for i in items_of(spec, r, d)]
    t0 = time.time()
    rows = pmap(env, search_job, jobs, spec.get("concurrency", 8))
    dump(out / "search.json", {"protocol": PROTOCOL, "spec": spec, "seconds": time.time() - t0, "rows": rows})
    log(f"search: {len(rows)} items, {sum(r['status'] == 'state' for r in rows)} states, "
        f"{sum(r['status'] == 'excluded' for r in rows)} excluded, {time.time() - t0:.0f}s")
    return rows


def run_branches(env, states: list[dict], branches: list[str], bases, tag, conc, out, orig_run=None) -> dict:
    jobs = [{"state_path": str(out / "states" / f"{s['state_id']}.json"), "branch": b, "bases": bases, "tag": tag,
             **({"orig_run_id": orig_run} if orig_run else {})} for s in states for b in branches]
    rs = pmap(env, branch_job, jobs, conc)
    res: dict = {}
    for j, r in zip(jobs, rs):
        res.setdefault(json.loads(Path(j["state_path"]).read_text())["state_id"], {})[j["branch"]] = r
    return res


# ----------------------------------------------------------------------------
# modes
# ----------------------------------------------------------------------------


def gate(env, spec, bases, servers, out, same=False) -> dict:
    t0 = time.time()
    res = {"protocol": PROTOCOL, "env": env, "spec": spec, "servers": servers, "bases": bases}
    conc = spec.get("concurrency", 8)
    if same:  # (b) both handles on the same checkpoint: no primary divergence may appear; force mid-episode states
        rows = do_search(env, spec, bases, out)
        res["search"] = {"n": len(rows), "n_states": sum(r["status"] == "state" for r in rows),
                         "n_no_divergence": sum(r["status"] == "no_divergence" for r in rows),
                         "excluded": [r for r in rows if r["status"] == "excluded"]}
        states = mid_states(env, spec, bases, out, spec["q_blocks"], spec.get("n_same", 6))
        four = run_branches(env, states, ["BB", "BQ", "QB", "QQ"], bases, "same", conc, out)
        res["states"] = []
        for s in states:
            rs = four[s["state_id"]]
            blk = load_block(s["run_id"], s["domain"])
            o = outcome(env, blk["traj"][s["task_id"]])
            sigs = {b: sig(r) for b, r in rs.items()}
            res["states"].append({"state_id": s["state_id"], "domain": s["domain"], "task_id": s["task_id"], "t": s["decision_idx"],
                                  "shadow_equals_a_Q": s["divergence"]["category"] in PRIMARY_EXCLUDE,
                                  "four_identical": len(set(sigs.values())) == 1,
                                  "equal_original": all(noop_check(s, r, blk["decs"][s["task_id"]], o)["ok"] for r in rs.values()),
                                  "replay": replay_consistency(rs, s)})
            dump(out / "branches" / f"{s['state_id']}_same.json", rs)
        v = {"no_divergence_all": res["search"]["n_states"] == 0 and not res["search"]["excluded"],
             "shadow_equals_a_Q": all(x["shadow_equals_a_Q"] for x in res["states"]),
             "four_identical": all(x["four_identical"] for x in res["states"]),
             "equal_original": all(x["equal_original"] for x in res["states"]),
             "replay": all(x["replay"]["ok"] for x in res["states"]), "n_states": len(res["states"])}
        v["pass"] = all(v[k] for k in ("no_divergence_all", "shadow_equals_a_Q", "four_identical", "equal_original", "replay")) and v["n_states"] > 0
        res["verdict"], res["seconds_total"] = v, time.time() - t0
        dump(out / "gate_same.json", res)
        log("verdict " + json.dumps(v))
        return res

    rows = do_search(env, spec, bases, out)
    res["search"] = {"n": len(rows), "n_states": sum(r["status"] == "state" for r in rows),
                     "n_no_divergence": sum(r["status"] == "no_divergence" for r in rows),
                     "excluded": [{k: r.get(k) for k in ("run_id", "domain", "task_id", "reason")} for r in rows if r["status"] == "excluded"],
                     "categories": sorted({r["category"] for r in rows if r["status"] == "state"})}
    sids = [r["state_id"] for r in rows if r["status"] == "state"][: spec.get("max_states", 12)]
    states = [json.loads((out / "states" / f"{s}.json").read_text()) for s in sids]
    tf = time.time()
    fwd = run_branches(env, states, ["QQ", "BB", "BQ", "QB"], bases, "fwd", conc, out)
    res["fwd_seconds"] = time.time() - tf
    iso_ids = set(sids[: spec.get("n_iso", 4)])
    iso = [s for s in states if s["state_id"] in iso_ids]
    rev = {}
    for s in iso:  # reversed order, one state at a time, sequential branches
        rev[s["state_id"]] = {}
        for b in ["QB", "BQ", "BB", "QQ"]:
            rev[s["state_id"]].update(run_branches(env, [s], [b], bases, "rev", 1, out)[s["state_id"]])
    conc4 = run_branches(env, iso, ["QQ", "BB", "BQ", "QB"], bases, "conc", 4 * max(1, len(iso)), out)
    res["states"], res["c_isolation"] = [], []
    for s in states:
        rs = fwd[s["state_id"]]
        dump(out / "branches" / f"{s['state_id']}_fwd.json", rs)
        blk = load_block(s["run_id"], s["domain"])
        recs = blk["decs"][s["task_id"]]
        o = outcome(env, blk["traj"][s["task_id"]])
        row = {"state_id": s["state_id"], "domain": s["domain"], "task_id": s["task_id"], "t": s["decision_idx"],
               "category": s["divergence"]["category"], "budget": s["budget"], "q_replay": s["q_replay"], "io_check": s.get("io_check"),
               "a_noop_QQ": noop_check(s, rs["QQ"], recs, o), "replay": replay_consistency(rs, s),
               "e_reprefill": reprefill_check(s, rs, recs),
               "outcomes": {b: {k: r.get(k) for k in ("reward", "official_reward", "termination_reason", "n_decisions", "duration", "error")}
                            for b, r in rs.items()}}
        res["states"].append(row)
        dump(out / "branches" / f"{s['state_id']}.json", rs)
        if s["state_id"] in iso_ids:
            f_s = {b: sig(r) for b, r in rs.items()}
            r_s = {b: sig(r) for b, r in rev[s["state_id"]].items()}
            c_s = {b: sig(r) for b, r in conc4[s["state_id"]].items()}
            dump(out / "branches" / f"{s['state_id']}_rev.json", rev[s["state_id"]])
            dump(out / "branches" / f"{s['state_id']}_conc.json", conc4[s["state_id"]])
            res["c_isolation"].append({"state_id": s["state_id"], "rev_equal": f_s == r_s, "conc_equal": f_s == c_s})
    # (a) B->B no-op on BF16 blocks at mid-episode states
    res["a_noop_BB"] = []
    if spec.get("b_blocks"):
        bst = mid_states(env, spec, bases, out, spec["b_blocks"], spec.get("n_bb", 4), role="B")
        bb = run_branches(env, bst, ["BB"], bases, "bbnoop", conc, out)
        for s in bst:
            blk = load_block(s["run_id"], s["domain"])
            r = bb[s["state_id"]]["BB"]
            dump(out / "branches" / f"{s['state_id']}_bbnoop.json", r)
            res["a_noop_BB"].append({"state_id": s["state_id"], "run_id": s["run_id"], "domain": s["domain"], "task_id": s["task_id"],
                                     "t": s["decision_idx"], "noop": noop_check(s, r, blk["decs"][s["task_id"]], outcome(env, blk["traj"][s["task_id"]]))})
    res["seconds_total"] = time.time() - t0
    res["verdict"] = verdict(res)
    res["throughput"] = throughput(res, rows, fwd)
    dump(out / "gate.json", res)
    log("verdict " + json.dumps(res["verdict"]))
    return res


def mid_states(env, spec, bases, out, blocks, n, role="Q") -> list[dict]:
    """No-op states that are not divergences: decision t = n_decisions // 2 of hash-ordered items of a block; the
    'shadow' action is the other handle's response at h_t (for B->B and same-checkpoint forks it must equal the
    recorded one). Built by replaying the recorded prefix (messages at t come from the replay itself)."""
    states = []
    for spec_b in blocks:
        r, d = spec_b.split(":")
        blk = load_block(r, d)
        for i in items_of({"n_items": 0}, r, d):
            if len(states) >= n:
                break
            recs = blk["decs"].get(i, [])
            if len(recs) < 3 or len(recs) != blk["traj"][i]["n_decisions"]:
                continue
            t = len(recs) // 2
            sid = sha(["mid", role, r, d, i, t])[:16]
            p = out / "states" / f"{sid}.json"
            if not p.exists():
                rec = recs[t]
                tools, ssha = state_tools(env, blk, i, t)
                rb, _ = chat(bases["B"], rec["messages"], tools)  # the B handle's action at h_t
                st = {"protocol": PROTOCOL, "env": env, "state_id": sid, "kind": f"mid_{role}", "run_id": r, "domain": d, "task_id": i,
                      "decision_idx": t, "n_decisions_orig": len(recs), "history_sha": sha(rec["messages"]),
                      "state_sha": ssha,
                      "a_Q": {"raw": raw_from_rec(rec)}, "a_B": {"raw": rb if role == "Q" else raw_from_rec(rec)},
                      "divergence": {"category": compare(env, msg_of(raw_from_rec(rec)), msg_of(rb)), "t_star": t},
                      "shadow_prompt_ids_ok": rb.get("prompt_token_ids") == rec["prompt_token_ids"],
                      "shadow_completion_ids_eq_recorded": rb["choices"][0].get("token_ids") == rec["completion_token_ids"]}
                dump(p, st)
            states.append(json.loads(p.read_text()))
    return states


class _ToT:
    """Replay the recorded prefix to decision t and capture the tools sent there and the backend-state hash."""

    def __init__(self, recs, t):
        self.recs, self.t, self.got = recs, t, {}

    def __call__(self, idx, messages, tools):
        if sha(messages) != sha(self.recs[idx]["messages"]):
            raise ReplayError(f"replayed messages differ at decision {idx}")
        if idx == self.t:
            self.got = {"tools": tools, "state_sha": getattr(self, "state_sha", None)}
            raise StopSearch("t")
        return raw_from_rec(self.recs[idx]), 0.0


def state_tools(env: str, blk: dict, item: str, t: int) -> tuple[list[dict], str | None]:
    pol = _ToT(blk["decs"][item], t)
    try:
        run_env(env, blk["domain"], item, pol, f"tools|{blk['run_id']}|{item}|{t}")
    except StopSearch:
        pass
    return pol.got["tools"], pol.got["state_sha"]


def verdict(res: dict) -> dict:
    st = [s for s in res["states"]]
    v = {
        "q_replay_at_state": all(all(s["q_replay"].values()) for s in st),
        "a_QQ": all(s["a_noop_QQ"]["ok"] for s in st),
        "a_BB": all(x["noop"]["ok"] for x in res["a_noop_BB"]) if res["a_noop_BB"] else None,
        "replay_fidelity": all(s["replay"]["ok"] for s in st),
        "c_isolation": all(x["rev_equal"] and x["conc_equal"] for x in res["c_isolation"]),
        "c_saveload": all(all((s["io_check"] or {}).values()) for s in st),
        "e_reprefill": all(s["e_reprefill"]["ok"] in (True, None) for s in st),
        "n_states": len(st), "n_bb_noop": len(res["a_noop_BB"]), "n_isolation": len(res["c_isolation"]),
        "n_search_excluded": len(res["search"]["excluded"]), "categories": res["search"]["categories"],
        "n_branch_errors": sum(1 for s in st for o in s["outcomes"].values() if o.get("error")),
    }
    v["pass"] = (v["n_states"] > 0 and v["n_branch_errors"] == 0 and v["a_BB"] is not False
                 and all(v[k] for k in ("q_replay_at_state", "a_QQ", "replay_fidelity", "c_isolation", "c_saveload", "e_reprefill")))
    return v


def throughput(res, rows, fwd) -> dict:
    import statistics as S
    shadow = [x["shadow_seconds"] for r in rows for x in r.get("rows", [])]
    durs = [r["duration"] for rs in fwd.values() for r in rs.values() if not r.get("error")]
    nb = sum(len(rs) for rs in fwd.values())
    return {"n_items_searched": len(rows), "n_states": sum(r["status"] == "state" for r in rows),
            "divergence_rate": (sum(r["status"] == "state" for r in rows) / len(rows)) if rows else None,
            "t_star": sorted(r["t"] for r in rows if r["status"] == "state"),
            "shadow_seconds_median": S.median(shadow) if shadow else None,
            "search_wall_per_item": (sum(r.get("search_seconds", 0) for r in rows) / len(rows)) if rows else None,
            "branch_duration_median": S.median(durs) if durs else None, "branch_duration_p90": sorted(durs)[int(0.9 * (len(durs) - 1))] if durs else None,
            "fwd_wall_per_branch": (res["fwd_seconds"] / nb) if nb else None, "n_fwd_branches": nb}


def dev(env, spec, bases, servers, out) -> dict:
    t0 = time.time()
    rows = do_search(env, spec, bases, out)
    ts = time.time() - t0
    states = [json.loads((out / "states" / f"{r['state_id']}.json").read_text()) for r in rows if r["status"] == "state"]
    noop = {s["state_id"] for s in states if int(sha("noop|" + s["state_id"])[:8], 16) / 16 ** 8 < spec.get("noop_frac", 0.1)}
    tb = time.time()
    jobs_states = {b: [s for s in states if b != "QQ" or s["state_id"] in noop] for b in ["BB", "BQ", "QB", "QQ"]}
    allr: dict = {}
    for b, sts in jobs_states.items():
        for sid, d in run_branches(env, sts, [b], bases, "dev", spec.get("concurrency", 8), out).items():
            allr.setdefault(sid, {}).update(d)
    tbr = time.time() - tb
    brow, eff, qq = [], [], []
    for s in states:
        rs = allr.get(s["state_id"], {})
        dump(out / "branches" / f"{s['state_id']}.json", rs)
        brow.append({"state_id": s["state_id"], "outcomes": {b: {k: r.get(k) for k in ("reward", "db_match", "official_reward", "termination_reason", "duration", "error")}
                                                             for b, r in rs.items()}})
        ys = {b: r.get("reward") for b, r in rs.items() if not r.get("error") and b != "QQ"}
        ys["QQ"] = s["orig"]["reward"]
        e = effects(s, ys)
        e["replay"] = replay_consistency(rs, s)["ok"]
        if "QQ" in rs:
            blk = load_block(s["run_id"], s["domain"])
            e["qq_noop"] = noop_check(s, rs["QQ"], blk["decs"][s["task_id"]], outcome(env, blk["traj"][s["task_id"]]))["ok"]
            qq.append(e["qq_noop"])
        eff.append(e)
    dump(out / "branches.json", {"protocol": PROTOCOL, "spec": spec, "servers": servers, "seconds": tbr, "rows": brow})
    (out / "effects.jsonl").write_text("".join(json.dumps(e) + "\n" for e in eff))
    n_items = len(rows)
    ok = [e for e in eff if "G" in e]
    summ = {"protocol": PROTOCOL, "env": env, "n_items": n_items, "n_states": len(states), "n_valid": len(ok),
            "n_excluded": sum(r["status"] == "excluded" for r in rows), "n_no_divergence": sum(r["status"] == "no_divergence" for r in rows),
            "qq_noop_ok": [sum(qq), len(qq)], "replay_ok": sum(e["replay"] for e in eff),
            "sum": {k: sum(e[k] for e in ok) for k in ("G", "A", "C", "I")} if ok else None,
            "G_all_per_item": (sum(e["G"] for e in ok) / n_items) if n_items else None,
            "mean_conditional": {k: sum(e[k] for e in ok) / len(ok) for k in ("G", "A", "C", "I")} if ok else None,
            "rescue_h": sum(1 for e in ok if e["Y"]["BQ"] == 1 and e["Y"]["QQ"] == 0),
            "damage_b": sum(1 for e in ok if e["Y"]["BQ"] == 0 and e["Y"]["QQ"] == 1),
            "search_seconds": ts, "branch_seconds": tbr, "n_branches": sum(len(v) for v in allr.values()),
            "wall_per_branch": tbr / max(1, sum(len(v) for v in allr.values()))}
    dump(out / "dev_summary.json", summ)
    log("dev " + json.dumps(summ))
    if qq and not all(qq):
        log("QQ no-op mismatch: output quarantined (protocol A)")
        (out / "QUARANTINE").write_text("QQ no-op mismatch\n")
    return {"verdict": {"qq_noop_ok": all(qq) if qq else None}, **summ}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--b-base", required=True)
    ap.add_argument("--q-base", required=True)
    ap.add_argument("--servers", default=None)
    a = ap.parse_args()
    task = json.load(open(a.task))
    spec, env = task["fork"], task["env"]
    servers = json.load(open(a.servers)) if a.servers else {}
    bases = {"B": a.b_base, "Q": a.q_base}
    out = ROOT / spec["out"]
    out.mkdir(parents=True, exist_ok=True)
    real = sys.stdout
    sys.stdout = open(os.devnull, "w")  # BFCL prints every step
    try:
        mode = spec["mode"]
        if mode == "gate":
            r = gate(env, spec, bases, servers, out)
        elif mode == "gate_same":
            r = gate(env, spec, bases, servers, out, same=True)
        elif mode == "dev":
            r = dev(env, spec, bases, servers, out)
        else:
            raise SystemExit(f"unknown mode {mode}")
    finally:
        sys.stdout = real
    print(json.dumps({"verdict": r.get("verdict")}, default=str))


if __name__ == "__main__":
    main()
