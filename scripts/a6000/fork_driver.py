"""Fork driver (protocol fork-v1): identity checks, divergence search, fork branches and the engineering gate.

Runs inside a worker task of kind "fork" (scripts/a6000/worker.py::run_fork), which builds the checkpoints, serves B
and Q on two separate vLLM servers, passes their URLs, and stops them afterwards. The CPU-only restoration check
(`cpucheck`) needs no server. Protocol: docs/insights/FORK_PROTOCOL.md; library: cloq/fork.py.

modes (task["fork"]["mode"]):
  gate       (a) no-op Q->Q and B->B, (c) order/concurrency isolation and save/load hashes, (d) budget accounting,
             (e) re-prefill after a controller switch, on states from a divergence search over the q_blocks.
  gate_same  (b) B and Q handles on two servers of the SAME checkpoint: all four branches must agree.
  search     divergence search only (states + search log), for development forks.
  branches   BB/BQ/QB (+ optional QQ no-op sample) on saved states.
  simctrl    W90 simulator control: Bank U BQ/QQ on manifests/fork/simctrl_v1.json units with the user simulator replaced
             by a user_llm override (Sonnet 5.5 via cloq/user_llm.py).
usage:
  python scripts/a6000/fork_driver.py --task <task.json> --b-base URL --q-base URL --user-base URL --servers <json>
  python scripts/a6000/fork_driver.py --cpucheck --block RUN:DOMAIN [--block ...] --out analysis/fork/gate/cpucheck_x.json
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import random
import statistics
import sys
import threading
import time
import traceback
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(os.environ.get("CLOQ_ROOT", "/data/ziyangs/cloq"))
sys.path.insert(0, str(ROOT))

from cloq import fork as F  # noqa: E402

LOCK = threading.Lock()


def log(msg: str) -> None:
    with LOCK:
        print(f"[{time.strftime('%F %T')}] {msg}", flush=True)


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str))
    tmp.replace(path)


def hsel(key: str) -> str:
    return F.sha(key)


# ----------------------------------------------------------------------------
# server helpers
# ----------------------------------------------------------------------------


def metrics(base: str) -> dict:
    """Prefix-cache and request counters of one vLLM server (per-process by construction)."""
    url = base.rsplit("/v1", 1)[0] + "/metrics"
    out = {}
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            for line in r.read().decode().splitlines():
                if line.startswith("#"):
                    continue
                for key in ("vllm:prefix_cache_queries_total", "vllm:prefix_cache_hits_total", "vllm:prompt_tokens_total",
                            "vllm:generation_tokens_total", "vllm:request_success_total"):
                    if line.startswith(key):
                        out[key] = out.get(key, 0.0) + float(line.rsplit(" ", 1)[1])
    except Exception as e:
        out["error"] = repr(e)
    return out


def complete_ids(base: str, prompt_ids: list[int], max_tokens: int, seed: int) -> list[int]:
    body = {"model": "agent", "prompt": prompt_ids, "max_tokens": max_tokens, "temperature": 0.0, "top_p": 1.0,
            "top_k": -1, "seed": seed, "return_token_ids": True, "skip_special_tokens": False}
    req = urllib.request.Request(base + "/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        c = json.load(r)["choices"][0]
    return c.get("token_ids")


def idcheck(base: str, blocks: list[F.Block], n: int, label: str) -> dict:
    """Checkpoint identity: the server regenerates n recorded decisions of the blocks (prompt ids -> completion ids)."""
    pool = [(b, d) for b in blocks for v in b.dec.values() for d in v if d.get("completion_token_ids")]
    pool.sort(key=lambda x: hsel(f"{x[0].run_id}|{x[0].domain}|{x[1]['task_id']}|{x[1]['decision_idx']}"))
    pool = pool[:n]

    def one(x):
        b, d = x
        seed = b.traj[d["task_id"]]["seed"]
        got = complete_ids(base, d["prompt_token_ids"], len(d["completion_token_ids"]), seed)
        return {"run_id": b.run_id, "domain": b.domain, "task_id": d["task_id"], "t": d["decision_idx"],
                "n_prompt": len(d["prompt_token_ids"]), "n_completion": len(d["completion_token_ids"]),
                "match": got == d["completion_token_ids"]}

    with ThreadPoolExecutor(8) as ex:
        rows = list(ex.map(one, pool))
    res = {"label": label, "base": base, "n": len(rows), "n_match": sum(r["match"] for r in rows), "rows": rows}
    res["ok"] = res["n"] > 0 and res["n_match"] == res["n"]
    log(f"idcheck {label}: {res['n_match']}/{res['n']}")
    return res


# ----------------------------------------------------------------------------
# divergence search
# ----------------------------------------------------------------------------


def search_task(block: F.Block, task_id: str, bases: dict, user_base: str, state_dir: Path, q_check: bool = True) -> dict:
    """Walk Q's decisions; at each, B generates its full action from the identical prompt; stop at the first semantic
    divergence (frozen as the primary state before any fork outcome)."""
    tr = block.traj[task_id]
    msgs = tr["messages"]
    n0 = F.prefix_len(tr["task"])
    pos = F.agent_positions(msgs, n0)
    decs = block.dec[task_id]
    row = {"run_id": block.run_id, "domain": block.domain, "task_id": task_id, "n_decisions": len(pos),
           "orig_termination": tr["termination_reason"], "orig_official_reward": tr.get("official_reward"),
           "orig_db_match": tr.get("db_match"), "steps": [], "t_star": None, "category": None, "exclusion": None}
    if len(pos) != len(decs):
        row["exclusion"] = f"decision/trajectory count mismatch {len(decs)} vs {len(pos)}"
        return row
    if tr["termination_reason"] not in ("user_stop", "agent_stop", "max_steps", "too_many_errors"):
        cause = None
        ic = ROOT / "runs" / block.run_id / block.domain / "infra_causes.json"
        if tr["termination_reason"] == "infrastructure_error" and ic.exists():
            cause = json.loads(ic.read_text()).get(str(task_id))
        if cause in ("context_overflow", "agent_parse_error"):
            row["orig_infra_cause"] = cause  # W10/W70: agent-side failure of the frozen policy, a valid failure outcome (Y_QQ = 0)
        else:
            row["exclusion"] = f"termination {tr['termination_reason']} (infrastructure{', ' + cause if cause else ''})"
            return row
    t_search = 0.0
    for t in range(len(pos)):
        st = F.make_state(block, task_id, t)
        tag = f"shadowB-{st['state_id']}"
        t0 = time.time()
        try:
            a_b, rec_b = F.shadow(st, bases["B"], tag)
        except Exception as e:
            row["exclusion"] = f"shadow failed at t={t}: {e!r}"[:500]
            return row
        dt = time.time() - t0
        t_search += dt
        ids_ok = F.ids_sha(rec_b.get("prompt_token_ids")) == st["q_decision"]["prompt_ids_sha"]
        if not ids_ok:  # never code an infrastructure/state failure as "no divergence"
            row["exclusion"] = f"B prompt ids differ from Q's recorded prompt at t={t} (from_server={rec_b.get('prompt_ids_from_server')})"
            return row
        schemas = F.tool_schemas(json.loads(json.dumps(_tools_schema(st))))
        cmp = F.compare_actions(st["a_Q"]["message"], a_b, schemas)
        row["steps"].append({"t": t, "category": cmp["category"], "shadow_seconds": dt,
                             "n_prompt": len(rec_b["prompt_token_ids"]), "n_completion_b": rec_b.get("n_completion_tokens")})
        if cmp["primary"]:
            st["a_B"] = {"message": a_b, "source": "shadow B at identical prompt ids",
                         "record": {k: rec_b.get(k) for k in ("prompt_sha256", "n_prompt_tokens", "finish_reason", "parser_error",
                                                              "prompt_ids_from_server", "prompt_ids_match_local", "n_completion_tokens")},
                         "prompt_ids_sha": F.ids_sha(rec_b["prompt_token_ids"]), "completion_ids_sha": F.ids_sha(rec_b.get("completion_token_ids"))}
            st["divergence"] = {**cmp, "t_star": t, "text_only_before": [s["t"] for s in row["steps"] if s["category"] == "text_only"]}
            if q_check:  # Q regenerates a_Q at the fork state: checkpoint identity + state restoration at h_t
                a_q2, rec_q2 = F.shadow(st, bases["Q"], f"shadowQ-{st['state_id']}")
                st["q_replay"] = {"completion_ids_ok": F.ids_sha(rec_q2.get("completion_token_ids")) == st["q_decision"]["completion_ids_sha"],
                                  "prompt_ids_ok": F.ids_sha(rec_q2.get("prompt_token_ids")) == st["q_decision"]["prompt_ids_sha"],
                                  "action_ok": F.canon_msg(a_q2) == F.canon_msg(st["a_Q"]["message"])}
            st["search"] = {"shadow_seconds_total": t_search, "n_shadow": t + 1}
            st["io_check"] = F.state_io_check(st, state_dir / f"{st['state_id']}.json")
            row.update({"t_star": t, "category": cmp["category"], "state_id": st["state_id"], "q_replay": st.get("q_replay"),
                        "io_check": st["io_check"], "budget": st["budget"]})
            F.state_io_check(st, state_dir / f"{st['state_id']}.json")  # final write includes io_check
            break
    row["shadow_seconds_total"] = t_search
    row["no_divergence"] = row["t_star"] is None
    return row


_TOOLS_CACHE: dict = {}


def _tools_schema(st: dict) -> list[dict]:
    d = st["domain"]
    if d not in _TOOLS_CACHE:
        from tau2.runner.build import build_environment

        _TOOLS_CACHE[d] = [t.openai_schema for t in build_environment(d).get_tools()]
    return _TOOLS_CACHE[d]


def pick_tasks(block: F.Block, k: int, prefer_user_tools: bool = False) -> list[str]:
    ids = sorted(block.traj, key=lambda t: hsel(f"fork-v1-gate|{block.run_id}|{block.domain}|{t}"))
    if prefer_user_tools:
        ids = sorted(ids, key=lambda t: -int((block.traj[t].get("n_user_tool_calls") or 0) > 0))
    return ids[:k]


# ----------------------------------------------------------------------------
# comparisons
# ----------------------------------------------------------------------------


def orig_final_hash(st: dict, block: F.Block) -> dict:
    from tau2.data_model.tasks import Task

    msgs = block.traj[st["task_id"]]["messages"]
    env = F.restore_env(st["domain"], Task.model_validate(st["task"]), [F.msg_from_dict(m) for m in msgs])
    return F.env_hashes(env)


def noop_check(st: dict, r: dict, orig_hash: dict) -> dict:
    """Branch replaying the recorded action with the recorded controller must reproduce the original suffix."""
    if "error" in r:
        return {"ok": False, "error": r["error"]}
    o = st["orig"]
    prompts = [d["prompt_ids_sha"] for d in r["decisions"]]
    checks = {
        "suffix_messages": r["suffix_sha"] == o["suffix_sha"],
        "prompt_token_ids": prompts == o["suffix_prompt_ids_sha"],
        "termination": r["termination_reason"] == o["termination_reason"],
        "reward": r["reward"] == o["reward"], "db_match": r["db_match"] == o["db_match"],
        "official_reward": r["official_reward"] == o["official_reward"],
        "budget_final": [r["step_count_final"], r["num_errors_final"]] == list(o["budget_final"]),
        "env_hash_final_vs_orig_replay": r["env_hash_final"] == orig_hash,
        "env_hash_replay_vs_live": r.get("env_hash_replay") == r["env_hash_final"],
        "env_hash_init": r["env_hash_init_ok"], "history_prefix": r["prefix_ok"],
    }
    out = {"ok": all(checks.values()), **checks, "n_prompts": len(prompts), "n_prompts_orig": len(o["suffix_prompt_ids_sha"])}
    if not checks["prompt_token_ids"]:
        first = next((i for i, (a, b) in enumerate(zip(prompts, o["suffix_prompt_ids_sha"])) if a != b), min(len(prompts), len(o["suffix_prompt_ids_sha"])))
        out["first_prompt_mismatch"] = first
    return out


def budget_check(st: dict, r: dict) -> dict:
    if "error" in r:
        return {"ok": False, "error": r["error"]}
    live = [r["step_count_final"], r["num_errors_final"]]
    rec = r["budget_recount"]
    lim = [st["budget"]["max_steps"], st["budget"]["max_errors"]]
    term = r["termination_reason"]
    term_ok = ((term != "max_steps" or live[0] >= lim[0]) and (term != "too_many_errors" or live[1] >= lim[1]))
    return {"ok": live == rec and term_ok and r["counters_tau2_default"] == [0, 0], "live": live, "recount": rec,
            "state_used": [st["budget"]["steps_used"], st["budget"]["errors_used"]], "termination": term, "term_consistent": term_ok,
            "note": "tau2 would restart the counters at 0 (counters_tau2_default); the fork restores them"}


def reprefill_check(st: dict, res: dict) -> dict:
    """QB: B's first request carries the full context the original Q saw at t+1 (same history + a_Q + same observation).
    BQ: Q's first request equals BB's first continuation request (same history + a_B + same observation)."""
    out = {}
    qb, bq, bb = res.get("QB"), res.get("BQ"), res.get("BB")

    def first_cont(r):
        ds = [d for d in (r or {}).get("decisions", []) if not d["forced"]]
        return ds[0] if ds else None

    d = first_cont(qb)
    if d is not None and len(st["orig"]["suffix_prompt_ids_sha"]) > 1:
        out["QB_first_prompt_eq_orig_Q_t+1"] = d["prompt_ids_sha"] == st["orig"]["suffix_prompt_ids_sha"][1]
        out["QB_first_from_server"] = bool(d["prompt_ids_from_server"]) and bool(d["prompt_ids_match_local"])
        out["QB_first_api_base"] = d["api_base"]
        out["QB_first_n_prompt"] = d["n_prompt_tokens"]
    d1, d2 = first_cont(bq), first_cont(bb)
    if d1 is not None and d2 is not None:
        out["BQ_first_prompt_eq_BB_first"] = d1["prompt_ids_sha"] == d2["prompt_ids_sha"]
        out["BQ_first_from_server"] = bool(d1["prompt_ids_from_server"]) and bool(d1["prompt_ids_match_local"])
        out["BQ_first_api_base"] = d1["api_base"]
    vals = [v for k, v in out.items() if isinstance(v, bool)]
    out["ok"] = bool(vals) and all(vals)
    out["applicable"] = bool(vals)
    return out


# ----------------------------------------------------------------------------
# gate
# ----------------------------------------------------------------------------


def run_4(st, bases, user_base, order, label, concurrent=False):
    tags = {b: f"{label}-{b}-{st['state_id']}" for b in order}
    if concurrent:
        with ThreadPoolExecutor(len(order)) as ex:
            futs = {b: ex.submit(F.run_branch, st, b[0], b[1], bases, user_base, tags[b]) for b in order}
            return {b: f.result() for b, f in futs.items()}
    return {b: F.run_branch(st, b[0], b[1], bases, user_base, tags[b]) for b in order}


def load_blocks(pairs) -> list[F.Block]:
    return [F.Block(ROOT, r, d) for r, d in pairs]


def gate(spec: dict, bases: dict, user_base: str, servers: dict, out: Path) -> dict:
    t_all = time.time()
    qb = load_blocks(spec["q_blocks"])
    bb = load_blocks(spec.get("b_blocks", []))
    res = {"protocol": F.PROTOCOL, "spec": spec, "servers": servers, "bases": bases, "user_base": user_base,
           "metrics_start": {k: metrics(v) for k, v in bases.items()}}
    res["idcheck_Q"] = idcheck(bases["Q"], qb, spec.get("idcheck_n", 16), "Q")
    if bb:
        res["idcheck_B"] = idcheck(bases["B"], bb, spec.get("idcheck_n", 16), "B")
    dump(out / "gate_partial.json", res)
    # divergence search
    sdir = out / "states"
    jobs = [(b, t) for b in qb for t in pick_tasks(b, spec.get("search_tasks_per_block", 10), b.domain == "telecom")]
    t0 = time.time()
    with ThreadPoolExecutor(spec.get("concurrency", 8)) as ex:
        rows = list(ex.map(lambda x: _safe(search_task, x[0], x[1], bases, user_base, sdir), jobs))
    res["search"] = {"seconds": time.time() - t0, "rows": rows}
    dump(out / "search.json", res["search"])
    log(f"search: {sum(1 for r in rows if r.get('t_star') is not None)} states from {len(rows)} tasks")
    # choose states: round robin over (domain, category)
    found = [r for r in rows if r.get("t_star") is not None]
    groups: dict = {}
    for r in sorted(found, key=lambda r: hsel("pick|" + r["state_id"])):
        groups.setdefault((r["domain"], r["category"]), []).append(r)
    chosen = []
    while len(chosen) < spec.get("n_states", 12) and any(groups.values()):
        for k in sorted(groups):
            if groups[k] and len(chosen) < spec.get("n_states", 12):
                chosen.append(groups[k].pop(0))
    states = [json.loads((sdir / f"{r['state_id']}.json").read_text()) for r in chosen]
    blk = {(b.run_id, b.domain): b for b in qb + bb}
    order = ["QQ", "BB", "BQ", "QB"]

    def per_state(st):
        r4 = run_4(st, bases, user_base, order, "fwd")
        oh = orig_final_hash(st, blk[(st["run_id"], st["domain"])])
        rec = {"state_id": st["state_id"], "domain": st["domain"], "task_id": st["task_id"], "t": st["decision_idx"],
               "category": st["divergence"]["category"], "budget": st["budget"], "q_replay": st.get("q_replay"),
               "io_check": st.get("io_check"), "a_noop_QQ": noop_check(st, r4["QQ"], oh),
               "d_budget": {b: budget_check(st, r4[b]) for b in order}, "e_reprefill": reprefill_check(st, r4),
               "outcomes": {b: {k: r4[b].get(k) for k in ("termination_reason", "reward", "db_match", "official_reward",
                                                          "step_count_final", "num_errors_final", "duration", "error")} for b in order}}
        dump(out / "branches" / f"{st['state_id']}_fwd.json", r4)
        return rec, r4

    t0 = time.time()
    with ThreadPoolExecutor(spec.get("concurrency", 8)) as ex:
        outs = list(ex.map(lambda s: _safe(per_state, s), states))
    res["fwd_seconds"] = time.time() - t0
    res["states"] = [o[0] if isinstance(o, tuple) else o for o in outs]
    fwd = {s["state_id"]: o[1] for s, o in zip(states, outs) if isinstance(o, tuple)}
    dump(out / "gate_partial.json", res)
    # (c) isolation: reversed order and all four concurrently, on n_iso states
    iso = []
    for st in states[: spec.get("n_iso", 4)]:
        if st["state_id"] not in fwd:
            continue
        rv = run_4(st, bases, user_base, list(reversed(order)), "rev")
        cc = run_4(st, bases, user_base, order, "conc", concurrent=True)
        dump(out / "branches" / f"{st['state_id']}_rev.json", rv)
        dump(out / "branches" / f"{st['state_id']}_conc.json", cc)
        cmp = {b: {"reversed": F.branch_signature(rv[b]) == F.branch_signature(fwd[st["state_id"]][b]),
                   "concurrent": F.branch_signature(cc[b]) == F.branch_signature(fwd[st["state_id"]][b])} for b in order}
        iso.append({"state_id": st["state_id"], "domain": st["domain"], "cmp": cmp,
                    "ok": all(v["reversed"] and v["concurrent"] for v in cmp.values())})
    res["c_isolation"] = iso
    # (a) B->B no-op on B's own trajectory
    bnoop = []
    if bb:
        cand = []
        for b in bb:
            for tid in pick_tasks(b, spec.get("n_bb_noop", 4), b.domain == "telecom")[: max(1, spec.get("n_bb_noop", 4) // len(bb))]:
                n = len(b.dec[tid])
                if n:
                    cand.append((b, tid, n // 2))

        def bb_one(x):
            b, tid, t = x
            st = F.make_state(b, tid, t)
            r = F.run_branch(st, "Q", "B", bases, user_base, f"bbnoop-{st['state_id']}")  # recorded (B) action, B controller
            dump(out / "branches" / f"{st['state_id']}_bbnoop.json", r)
            return {"state_id": st["state_id"], "run_id": b.run_id, "domain": b.domain, "task_id": tid, "t": t, "budget": st["budget"],
                    "noop": noop_check(st, r, orig_final_hash(st, b)), "d_budget": budget_check(st, r),
                    "io_check": F.state_io_check(st, out / "states_bnoop" / f"{st['state_id']}.json")}

        with ThreadPoolExecutor(spec.get("concurrency", 8)) as ex:
            bnoop = list(ex.map(lambda x: _safe(bb_one, x), cand))
    res["a_noop_BB"] = bnoop
    res["metrics_end"] = {k: metrics(v) for k, v in bases.items()}
    res["seconds_total"] = time.time() - t_all
    res["verdict"] = verdict(res)
    res["throughput"] = throughput(res, out)
    dump(out / "gate.json", res)
    (out / "gate_partial.json").unlink(missing_ok=True)
    log("verdict " + json.dumps(res["verdict"]))
    return res


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        log(f"{fn.__name__} failed: {e!r}")
        return {"error": repr(e), "trace": traceback.format_exc()[-3000:]}


def verdict(res: dict) -> dict:
    sts = [s for s in res.get("states", []) if "error" not in s]
    bn = [s for s in res.get("a_noop_BB", []) if "error" not in s]
    v = {
        "idcheck": res.get("idcheck_Q", {}).get("ok") and res.get("idcheck_B", {"ok": True}).get("ok"),
        "a_QQ": bool(sts) and all(s["a_noop_QQ"]["ok"] for s in sts),
        "a_BB": bool(bn) and all(s["noop"]["ok"] for s in bn),
        "q_replay_at_state": bool(sts) and all((s.get("q_replay") or {}).get("completion_ids_ok") for s in sts),
        "c_isolation": bool(res.get("c_isolation")) and all(x["ok"] for x in res["c_isolation"]),
        "c_saveload": bool(sts) and all(s["io_check"]["env_hash_ok"] and s["io_check"]["history_sha_ok"] for s in sts)
                      and all(s["io_check"]["env_hash_ok"] for s in bn),
        "d_budget": bool(sts) and all(all(x["ok"] for x in s["d_budget"].values()) for s in sts) and all(s["d_budget"]["ok"] for s in bn),
        "e_reprefill": bool(sts) and all(s["e_reprefill"]["ok"] for s in sts if s["e_reprefill"]["applicable"]),
        "n_states": len(sts), "n_state_errors": len(res.get("states", [])) - len(sts),
        "n_bb_noop": len(bn), "n_bb_errors": len(res.get("a_noop_BB", [])) - len(bn),
        "domains": sorted({s["domain"] for s in sts} | {s["domain"] for s in bn}),
        "categories": sorted({s["category"] for s in sts}),
    }
    v["pass"] = all(v[k] for k in ("idcheck", "a_QQ", "a_BB", "q_replay_at_state", "c_isolation", "c_saveload", "d_budget", "e_reprefill")) \
        and v["n_state_errors"] == 0 and v["n_bb_errors"] == 0
    return v


def throughput(res: dict, out: Path) -> dict:
    """Suffix durations per branch, per-decision shadow cost, simulator calls (from the forward branches)."""
    durs, n_user, n_dec, shadow = [], [], [], []
    for p in sorted((out / "branches").glob("*_fwd.json")):
        r4 = json.loads(p.read_text())
        for b, r in r4.items():
            if b == "QQ" or "error" in r:
                continue
            durs.append(r["duration"])
            n_user.append(r["n_user_msgs"])
            n_dec.append(sum(1 for d in r["decisions"] if not d["forced"]))
    for r in res.get("search", {}).get("rows", []):
        shadow += [s["shadow_seconds"] for s in r.get("steps", [])]

    def q(v, p):
        return sorted(v)[min(len(v) - 1, int(p * len(v)))] if v else None

    return {"n_branches": len(durs), "suffix_seconds_median": statistics.median(durs) if durs else None,
            "suffix_seconds_p90": q(durs, 0.9), "user_msgs_per_branch_mean": statistics.mean(n_user) if n_user else None,
            "agent_decisions_per_branch_mean": statistics.mean(n_dec) if n_dec else None,
            "shadow_seconds_per_decision_median": statistics.median(shadow) if shadow else None,
            "shadow_seconds_per_decision_p90": q(shadow, 0.9), "n_shadow": len(shadow),
            "search_decisions_per_task_mean": statistics.mean([len(r.get("steps", [])) for r in res.get("search", {}).get("rows", []) if "steps" in r]) if res.get("search") else None,
            "search_wall_seconds": res.get("search", {}).get("seconds"), "fwd_wall_seconds": res.get("fwd_seconds"),
            "note": "wall times under concurrency 8 on one node, shared simulator; branch = BB/BQ/QB (QQ excluded)"}


def crosscheck(bases: dict, blocks: list, n: int) -> dict:
    """Same-config handles without an original run of that config: both servers regenerate n recorded prompts (of
    another config's block) and must produce identical completion ids."""
    pool = [(b, d) for b in blocks for v in b.dec.values() for d in v if d.get("completion_token_ids")]
    pool.sort(key=lambda x: hsel(f"x|{x[0].run_id}|{x[0].domain}|{x[1]['task_id']}|{x[1]['decision_idx']}"))
    rows = []
    for b, d in pool[:n]:
        seed = b.traj[d["task_id"]]["seed"]
        ids = [complete_ids(bases[h], d["prompt_token_ids"], 256, seed) for h in ("B", "Q")]
        rows.append({"task_id": d["task_id"], "t": d["decision_idx"], "match": ids[0] == ids[1], "n": len(ids[0] or [])})
    res = {"label": "cross-handle (same config, foreign prompts)", "n": len(rows), "n_match": sum(r["match"] for r in rows), "rows": rows}
    res["ok"] = res["n"] > 0 and res["n_match"] == res["n"]
    log(f"crosscheck: {res['n_match']}/{res['n']}")
    return res


def gate_same(spec: dict, bases: dict, user_base: str, servers: dict, out: Path) -> dict:
    """(b): both handles serve the same checkpoint (two servers). At states along Q's trajectory, the 'B' shadow must
    reproduce a_Q, and all four branches must agree with each other and with the original continuation."""
    qb = load_blocks(spec["q_blocks"])
    foreign = bool(spec.get("foreign_states"))  # states from another config's block (no original run of this config yet)
    res = {"protocol": F.PROTOCOL, "spec": spec, "servers": servers, "bases": bases, "foreign_states": foreign}
    if foreign:
        res["idcheck_Q"] = crosscheck(bases, qb, spec.get("idcheck_n", 8))
        res["idcheck_Bhandle"] = res["idcheck_Q"]
    else:
        res["idcheck_Q"] = idcheck(bases["Q"], qb, spec.get("idcheck_n", 8), "Q")
        res["idcheck_Bhandle"] = idcheck(bases["B"], qb, spec.get("idcheck_n", 8), "B-handle (same ckpt)")
    cand = []
    for b in qb:
        for tid in pick_tasks(b, spec.get("n_per_block", 3), b.domain == "telecom"):
            n = len(b.dec[tid])
            cand.append((b, tid, (n - 1) // 3))
    order = ["QQ", "BB", "BQ", "QB"]

    def one(x):
        b, tid, t = x
        st = F.make_state(b, tid, t)
        a_b, rec_b = F.shadow(st, bases["B"], f"sameB-{st['state_id']}")
        st["a_B"] = {"message": a_b, "source": "shadow via B handle (same checkpoint)"}
        if foreign:  # this config's own current action from the Q handle; must equal the B handle's, token for token
            a_q, rec_q = F.shadow(st, bases["Q"], f"sameQ-{st['state_id']}")
            shadow_eq = F.canon_msg(a_b) == F.canon_msg(a_q) and rec_b.get("completion_token_ids") == rec_q.get("completion_token_ids")
            st["a_Q"] = {"message": a_q, "source": "shadow via Q handle (foreign state)"}
        else:
            shadow_eq = F.canon_msg(a_b) == F.canon_msg(st["a_Q"]["message"])
        r4 = run_4(st, bases, user_base, order, "same")
        dump(out / "branches" / f"{st['state_id']}_same.json", r4)
        sig = {k: F.branch_signature(v) for k, v in r4.items()}
        row = {"state_id": st["state_id"], "domain": b.domain, "task_id": tid, "t": t, "shadow_eq_aQ": shadow_eq,
               "shadow_prompt_ok": F.ids_sha(rec_b["prompt_token_ids"]) == st["q_decision"]["prompt_ids_sha"],
               "all_four_equal": all(sig[k] == sig["QQ"] for k in order),
               "differs": [k for k in order if sig[k] != sig["QQ"]],
               "budget_ok": all(budget_check(st, r4[k])["ok"] for k in order)}
        if foreign:
            row["noop_vs_orig"] = {"not_applicable": True}  # no original run of this config
        else:
            oh = orig_final_hash(st, b)
            row["noop_vs_orig"] = {k: noop_check(st, r4[k], oh)["ok"] for k in order}
        return row

    with ThreadPoolExecutor(spec.get("concurrency", 8)) as ex:
        rows = list(ex.map(lambda x: _safe(one, x), cand))
    res["rows"] = rows
    ok = [r for r in rows if "error" not in r]
    res["verdict"] = {"b_same_ckpt": bool(ok) and len(ok) == len(rows)
                      and all(r["all_four_equal"] and r["shadow_eq_aQ"] and r["shadow_prompt_ok"] and r["budget_ok"]
                              and all(r["noop_vs_orig"].values()) for r in ok),
                      "n_states": len(ok), "n_errors": len(rows) - len(ok), "domains": sorted({r["domain"] for r in ok}),
                      "idcheck": res["idcheck_Q"]["ok"] and res["idcheck_Bhandle"]["ok"]}
    res["verdict"]["pass"] = res["verdict"]["b_same_ckpt"] and res["verdict"]["idcheck"]
    dump(out / "gate_same.json", res)
    log("verdict " + json.dumps(res["verdict"]))
    return res


# ----------------------------------------------------------------------------
# development modes
# ----------------------------------------------------------------------------


def search_mode(spec, bases, user_base, servers, out):
    qb = load_blocks(spec["q_blocks"])
    jobs = []
    for b in qb:
        ids = spec.get("task_ids", {}).get(f"{b.run_id}|{b.domain}") or sorted(b.traj, key=lambda t: hsel(f"order|{b.run_id}|{t}"))
        jobs += [(b, t) for t in ids]
    t0 = time.time()
    with ThreadPoolExecutor(spec.get("concurrency", 8)) as ex:
        rows = list(ex.map(lambda x: _safe(search_task, x[0], x[1], bases, user_base, out / "states", spec.get("q_check", True)), jobs))
    res = {"protocol": F.PROTOCOL, "spec": spec, "servers": servers, "seconds": time.time() - t0, "rows": rows,
           "metrics": {k: metrics(v) for k, v in bases.items()}}
    dump(out / "search.json", res)
    return res


def dev_mode(spec, bases, user_base, servers, out):
    """Development forks: divergence search over every task of the blocks; all states are frozen (written) before any
    branch runs; then BB/BQ/QB on every state plus the QQ no-op on a hash-selected sample (noop_frac)."""
    s = search_mode(spec, bases, user_base, servers, out)
    b = branches_mode({**spec, "states_dir": str((out / "states").relative_to(ROOT))}, bases, user_base, servers, out)
    return {"search_seconds": s["seconds"], "branches_seconds": b["seconds"], "n_states": len(b["rows"])}


def pivot_arms(spec, bases, user_base, servers, out):
    """W55 step 2: at frozen fork states (the pivot t*), each served arm (one per handle: spec["arms"]["B"/"Q"]) makes
    Q's decision once from the identical prompt; its full action is compared semantically with a_B and a_Q.
    States: every state file under spec["states_globs"] with a primary divergence, sampled by sha256(salt|state_id)."""
    import glob as _g
    files = sorted({p for g in spec["states_globs"] for p in _g.glob(str(ROOT / g))})
    states = []
    for p in files:
        st = json.loads(Path(p).read_text())
        if st.get("a_B") and st.get("divergence"):
            states.append(st)
    states.sort(key=lambda st: hsel(f"{spec.get('salt', 'pivot-arms-v1')}|{st['state_id']}"))
    states = states[: spec.get("n_states", 150)]
    log(f"pivot_arms: {len(states)} states from {len(files)} files; arms {spec['arms']}")

    def one(st, h):
        arm = spec["arms"][h]
        a, rec = F.shadow(st, bases[h], f"piv-{arm}-{st['state_id']}")
        sch = F.tool_schemas(_tools_schema(st))
        cb = F.compare_actions(st["a_B"]["message"], a, sch)
        cq = F.compare_actions(st["a_Q"]["message"], a, sch)
        return {"arm": arm, "state_id": st["state_id"], "run_id": st["run_id"], "domain": st["domain"], "task": f"{st['domain']}:{st['task_id']}",
                "t": st["decision_idx"], "divergence": st["divergence"]["category"],
                "prompt_ok": F.ids_sha(rec.get("prompt_token_ids")) == st["q_decision"]["prompt_ids_sha"],
                "eq_B": not cb["primary"], "eq_Q": not cq["primary"], "cat_vs_B": cb["category"], "cat_vs_Q": cq["category"],
                "exact_B": F.canon_msg(a) == F.canon_msg(st["a_B"]["message"]), "exact_Q": F.canon_msg(a) == F.canon_msg(st["a_Q"]["message"]),
                "completion_ids_sha": F.ids_sha(rec.get("completion_token_ids")), "finish_reason": rec.get("finish_reason"), "action": a}

    t0 = time.time()
    res = {"protocol": F.PROTOCOL, "spec": spec, "servers": servers, "n_states": len(states), "arms": {}}
    for h in ("B", "Q"):
        if h not in spec["arms"] or (h == "Q" and spec["arms"]["Q"] == spec["arms"].get("B")):
            continue
        with ThreadPoolExecutor(spec.get("concurrency", 8)) as ex:
            rows = list(ex.map(lambda st: _safe(one, st, h), states))
        arm = spec["arms"][h]
        (out / f"{arm}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        ok = [r for r in rows if "error" not in r]
        res["arms"][arm] = {"n": len(ok), "n_errors": len(rows) - len(ok), "prompt_ok": sum(r["prompt_ok"] for r in ok),
                            "eq_B": sum(r["eq_B"] for r in ok), "eq_Q": sum(r["eq_Q"] for r in ok),
                            "other": sum(1 for r in ok if not r["eq_B"] and not r["eq_Q"]),
                            "exact_B": sum(r["exact_B"] for r in ok), "exact_Q": sum(r["exact_Q"] for r in ok)}
        log(f"pivot_arms {arm}: {json.dumps(res['arms'][arm])}")
    res["seconds"] = time.time() - t0
    dump(out / f"pivot_arms_{'_'.join(spec['arms'][h] for h in sorted(spec['arms']))}.json", res)
    return res


def _y(domain: str, rec: dict) -> int | None:
    """Success under the domain's evaluator (retail/airline DB success, telecom official task-basis success)."""
    if rec is None:
        return None
    if domain == "telecom":
        return int(rec.get("official_reward") == 1.0)
    return int(bool(rec.get("db_match")) and rec.get("termination_reason") in ("user_stop", "agent_stop"))


def bank_u(spec, bases, user_base, servers, out):
    """Bank U (FORK_PROTOCOL §15 + amendment 1, W70). Servers: B = BF16, Q = the cell's configuration.
    Rows from the frozen manifest for this model, cell and blocks: U1 (this cell's own trajectories), U2B (BF16-sourced
    shared states), U2Q (Q-sourced shared states). Native four arms; reuse only between token-identical current actions
    and of the source's own original continuation (U1: QQ, U2B: BB, U2Q with this cell = source: QQ), validated by running
    that arm on a 10% hash sample (spec noop_frac; the gate uses 1.0)."""
    man_path = ROOT / spec["manifest"]
    import hashlib as _h
    man_sha = _h.sha256(man_path.read_bytes()).hexdigest()
    if spec.get("manifest_sha256") and spec["manifest_sha256"] != man_sha:
        raise SystemExit(f"bank_u: manifest sha {man_sha} != frozen {spec['manifest_sha256']}")
    man = json.loads(man_path.read_text())
    m, cell = spec["model"], spec["cell"]
    rows = [r for r in man["rows"] if r["model"] == m and r["block"] in spec["blocks"] and r["sub"] in spec.get("subs", ["U1", "U2B", "U2Q"])
            and (r["sub"] != "U1" or r["cell"] == cell)]
    if spec.get("limit_per_sub"):
        lim = spec["limit_per_sub"]
        rows = [r for sub in ("U1", "U2B", "U2Q") for r in sorted([x for x in rows if x["sub"] == sub], key=lambda x: x["state_key"])[:lim]]
    blocks = {}
    src_cell = "gptq_w4_d1"

    def one(r):
        rec = {k: r[k] for k in ("state_key", "sub", "model", "block", "domain", "task_id", "t", "n_decisions", "selection_probability", "q0", "source_run")}
        rec["cell"] = cell
        if r["missing_reason"]:
            return {**rec, "missing_reason": r["missing_reason"]}
        k = (r["source_run"], r["domain"])
        if k not in blocks:
            blocks[k] = F.Block(ROOT, *k)
        st = F.make_state(blocks[k], r["task_id"], r["t"])
        recorded = st["a_Q"]["message"]  # the source run's own action at t
        noop = int(_h.sha256(f"bank-u-noop-v1|{r['state_key']}|{cell}".encode()).hexdigest()[:8], 16) / 16 ** 8 < spec.get("noop_frac", 0.1)
        orig_y = _y(r["domain"], {**st["orig"], "termination_reason": st["orig"]["termination_reason"]})
        checks = {}
        tagb = f"bu-{cell}-{r['state_key']}"
        if r["sub"] == "U1":
            a_b, rb = F.shadow(st, bases["B"], tagb + "-sB")
            checks["B_prompt_ok"] = F.ids_sha(rb.get("prompt_token_ids")) == st["q_decision"]["prompt_ids_sha"]
            a_q, orig_arm = recorded, "QQ"
        elif r["sub"] == "U2B":
            a_q, rq = F.shadow(st, bases["Q"], tagb + "-sQ")
            checks["Q_prompt_ok"] = F.ids_sha(rq.get("prompt_token_ids")) == st["q_decision"]["prompt_ids_sha"]
            a_b, orig_arm = recorded, "BB"
        else:  # U2Q
            a_b, rb = F.shadow(st, bases["B"], tagb + "-sB")
            checks["B_prompt_ok"] = F.ids_sha(rb.get("prompt_token_ids")) == st["q_decision"]["prompt_ids_sha"]
            if cell == src_cell:
                a_q, orig_arm = recorded, "QQ"
            else:
                a_q, rq = F.shadow(st, bases["Q"], tagb + "-sQ")
                checks["Q_prompt_ok"] = F.ids_sha(rq.get("prompt_token_ids")) == st["q_decision"]["prompt_ids_sha"]
                orig_arm = None
        if not all(checks.values()):
            return {**rec, "missing_reason": f"prompt id mismatch {checks}"}
        st["a_B"] = {"message": a_b}
        st["a_Q"] = {"message": a_q}
        exact = F.canon_msg(a_b) == F.canon_msg(a_q)
        sch = F.tool_schemas(_tools_schema(st))
        cmpc = F.compare_actions(a_q, a_b, sch)
        # which arms to run (never impute a suffix effect; reuse only identical actions or the source's original arm)
        need = {"BB", "BQ", "QB", "QQ"}
        reuse = {}
        if orig_arm and not noop:
            need.discard(orig_arm)
            reuse[orig_arm] = "orig"
        if exact:  # identical current action: B-first and Q-first arms with the same controller are identical
            for a1, a2 in (("BB", "QB"), ("BQ", "QQ")):
                if a1 in need and a2 in need:
                    keep, drop = (a1, a2) if (noop and a1 == orig_arm) else (a2, a1)  # a no-op sample always runs the original arm
                    need.discard(drop)
                    reuse[drop] = f"={keep}"
                elif a1 in need and a2 in reuse:
                    need.discard(a1)
                    reuse[a1] = f"={a2}"
                elif a2 in need and a1 in reuse:
                    need.discard(a2)
                    reuse[a2] = f"={a1}"
        res = {}
        for arm in ("BB", "BQ", "QB", "QQ"):
            if arm in need:
                br = F.run_branch(st, arm[0], arm[1], bases, user_base, f"{tagb}-{arm}")
                res[arm] = br
        Y, src = {}, {}
        for arm in ("BB", "BQ", "QB", "QQ"):
            if arm in res:
                Y[arm] = None if "error" in res[arm] else _y(r["domain"], res[arm])
                src[arm] = "run" if "error" not in res[arm] else f"error: {res[arm]['error'][:120]}"
        for arm, how in reuse.items():
            if how == "orig":
                Y[arm], src[arm] = orig_y, "orig"
        for arm, how in reuse.items():
            if how.startswith("="):
                Y[arm], src[arm] = Y.get(how[1:]), f"reuse{how}"
        if noop and orig_arm and orig_arm in res and "error" not in res[orig_arm]:
            checks["noop_" + orig_arm] = noop_check(st, res[orig_arm], orig_final_hash(st, blocks[k]))
        rec.update({"state_id": st["state_id"], "history_sha": st["history_sha"], "prompt_ids_sha": st["q_decision"]["prompt_ids_sha"],
                    "steps_left": st["budget"]["steps_left"], "exact_agreement": exact, "agreement_category": cmpc["category"],
                    "Y": Y, "arm_source": src, "noop_sample": noop, "checks": checks, "budget_ok": {a: budget_check(st, b)["ok"] for a, b in res.items() if "error" not in b},
                    "context_overflow_arms": [a for a, b in res.items() if b.get("infra_cause") == "context_overflow"],
                    "durations": {a: b.get("duration") for a, b in res.items()}, "a_B": a_b, "a_Q": a_q})
        dump(out / "branches" / f"{r['state_key']}.json", res)
        return rec

    t0 = time.time()
    with ThreadPoolExecutor(spec.get("concurrency", 8)) as ex:
        recs = list(ex.map(lambda r: _safe(one, r), rows))
    out.mkdir(parents=True, exist_ok=True)
    (out / "bank_rows.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False, default=str) + "\n" for x in recs))
    ok = [x for x in recs if "Y" in x]
    noops = [x for x in ok if any(k.startswith("noop_") for k in x["checks"])]
    res = {"protocol": "bank_u_v1 (FORK_PROTOCOL §15 + amendment 1)", "manifest_sha256": man_sha, "spec": spec, "servers": servers,
           "n_rows": len(rows), "n_ok": len(ok), "n_missing": sum(1 for x in recs if "missing_reason" in x), "n_errors": sum(1 for x in recs if "error" in x),
           "n_exact_agreement": sum(1 for x in ok if x["exact_agreement"]),
           "noop": {"n": len(noops), "n_pass": sum(1 for x in noops if all(v["ok"] for kk, v in x["checks"].items() if kk.startswith("noop_")))},
           "budget_ok": all(all(x["budget_ok"].values()) for x in ok),
           "n_branches_run": sum(sum(1 for v in x["arm_source"].values() if v == "run") for x in ok),
           "branch_seconds": [d for x in ok for d in x["durations"].values() if d], "seconds": time.time() - t0}
    res["gate_pass"] = res["n_errors"] == 0 and res["n_missing"] == 0 and res["noop"]["n"] > 0 and res["noop"]["n_pass"] == res["noop"]["n"] and res["budget_ok"]
    dump(out / "bank_summary.json", res)
    log(f"bank_u {m}:{cell} {spec['blocks']}: ok {res['n_ok']}/{res['n_rows']}, exact {res['n_exact_agreement']}, noop {res['noop']}, "
        f"branches {res['n_branches_run']}, {res['seconds']:.0f} s, gate_pass {res['gate_pass']}")
    if spec.get("limit_per_sub") and not res["gate_pass"]:  # gate task: fail loudly so queue deps on it never release (W76)
        raise RuntimeError(f"bank_u gate failed for {m}:{cell}: see {out / 'bank_summary.json'}")
    return res


def _user_protocol(st: dict, br: dict) -> dict:
    """W90 acceptance checks on one branch run with a user_llm override (cloq/user_llm.py records every user call)."""
    from tau2.runner.build import build_environment, build_user
    from tau2.data_model.tasks import Task
    from tau2.user.user_simulator import OUT_OF_SCOPE, STOP, TRANSFER
    from tau2.user.user_simulator_base import is_valid_user_history_message
    from tau2.utils.llm_utils import to_litellm_messages

    calls = br.get("user_llm_calls") or []
    want_model = "anthropic/" + br["user_llm"]["model"]
    task = Task.model_validate(st["task"])
    env = build_environment(st["domain"])
    u = build_user(st["run_config"].get("user", "user_simulator"), env, task, llm="expected", llm_args={})
    hist = [F.msg_from_dict(m) for m in st["history"]]
    us = u.get_init_state(message_history=[m for m in hist if is_valid_user_history_message(m)])
    exp = to_litellm_messages(us.system_messages + us.flip_roles())
    rc = lambda m: (m.get("role"), m.get("content"))  # noqa: E731
    exp_sys, exp_prefix = exp[0]["content"], [rc(m) for m in exp[1:]]
    c0 = calls[0] if calls else None
    req = (c0 or {}).get("request_messages") or []
    toks = (STOP, TRANSFER, OUT_OF_SCOPE)
    umsgs = [m for m in (br.get("suffix") or []) if m["role"] == "user"]
    has_tok = [any(t in (m.get("content") or "") for t in toks) for m in umsgs]
    term = br.get("termination_reason")
    chk = {
        "n_calls_eq_user_msgs": len(calls) == len(umsgs),
        "all_calls_model": all(c.get("model") == want_model for c in calls),
        "all_calls_request_id": all(c.get("request_id") for c in calls) and len(calls) > 0,
        "no_call_errors": not any("error" in c for c in calls),
        "seed_dropped_only": all(set(c.get("dropped_params") or {}) <= {"seed"} for c in calls),
        "system_prompt_identical": bool(c0) and bool(req) and req[0].get("role") == "system" and req[0].get("content") == exp_sys,
        "instructions_in_system": str(task.user_scenario) in exp_sys and bool(c0) and str(task.user_scenario) in (req[0].get("content") or ""),
        "history_prefix_identical": bool(c0) and [rc(m) for m in req[1:1 + len(exp_prefix)]] == exp_prefix,
        "user_tools_none": u.tools is None and all(not c.get("tools") for c in calls),
        "env_hash_init_ok": bool(br.get("env_hash_init_ok")), "prefix_ok": bool(br.get("prefix_ok")),
        "stop_token_only_last": not any(has_tok[:-1]),
        "user_stop_has_token": term != "user_stop" or (bool(has_tok) and has_tok[-1]),
    }
    return {"ok": all(chk.values()), "checks": chk, "termination_reason": term, "n_user_calls": len(calls),
            "expected_system_sha256": F.sha(exp_sys), "n_expected_prefix": len(exp_prefix)}


def simctrl(spec, bases, user_base, servers, out):
    """W90 simulator robustness control (manifests/fork/simctrl_v1.json; GPT-6.1 review 5 option A). For each manifest
    unit (Bank U f01 class (ii) flips + matched non-flip controls) of this model x cell: rebuild the fork state, check it
    against the Bank U row (history and prompt-id sha; B regenerates a_B and Q regenerates a_Q exactly), then run the
    original native arms BQ and QQ with the recorded a_B / a_Q forced and the cell's Q continuing, with ONLY the user
    simulator replaced by spec["user_llm"] (Sonnet 5.5). spec["gate"]: write gate.json and fail unless every check
    passes. spec["dry"]: CPU dry run (mock servers): the regeneration check is replaced by the local prompt-id render,
    and only the first spec["branch_limit"] units run branches."""
    import hashlib as _h
    from cloq import user_llm as UL

    man_path = ROOT / spec["manifest"]
    man_sha = _h.sha256(man_path.read_bytes()).hexdigest()
    if spec.get("manifest_sha256") and spec["manifest_sha256"] != man_sha:
        raise SystemExit(f"simctrl: manifest sha {man_sha} != frozen {spec['manifest_sha256']}")
    man = json.loads(man_path.read_text())
    ul = dict(spec["user_llm"])
    if ul != man["user_llm"] and not spec.get("dry"):
        raise SystemExit(f"simctrl: task user_llm {ul} != manifest {man['user_llm']}")
    if not ul.get("api_base"):
        UL.load_key()  # raises without the key file; never printed
    elif not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = "mock-not-a-key"
    UL.install()
    want = list(spec["unit_ids"])
    units = [u for u in man["units"] if u["unit_id"] in set(want)]
    if len(units) != len(want) or any((u["model"], u["cell"]) != (spec["model"], spec["cell"]) for u in units):
        raise SystemExit("simctrl: unit ids missing from the manifest or from another model x cell")
    units.sort(key=lambda u: want.index(u["unit_id"]))
    rows = {}
    for b in sorted({u["block"] for u in units}):
        p = ROOT / "analysis/fork/bank_u" / f"{spec['model']}_{spec['cell']}" / b / "bank_rows.jsonl"
        if _h.sha256(p.read_bytes()).hexdigest() != man["source"]["bank_rows_sha256"][str(p.relative_to(ROOT))]:
            raise SystemExit(f"simctrl: {p} changed since the freeze")
        for line in p.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                rows[(r["block"], r["sub"], r["state_key"])] = r
    blocks = {}
    canon_sha = lambda m: _h.sha256(json.dumps(F.canon_msg(m), sort_keys=True).encode()).hexdigest()  # noqa: E731
    lim = spec.get("branch_limit") if spec.get("dry") else None

    def one(i_u):
        i, u = i_u
        rec = {k: u[k] for k in ("unit_id", "role", "pair_id", "model", "cell", "block", "sub", "sub_cls", "state_key", "domain",
                                 "task_id", "t", "Y_orig", "direction_orig")}
        r = rows[(u["block"], u["sub"], u["state_key"])]
        a_b, a_q = r["a_B"], r["a_Q"]
        k = (u["source_run"], u["domain"])
        if k not in blocks:
            blocks[k] = F.Block(ROOT, *k)
        st = F.make_state(blocks[k], u["task_id"], u["t"])
        chk = {"a_B_sha": canon_sha(a_b) == u["a_B_sha"], "a_Q_sha": canon_sha(a_q) == u["a_Q_sha"],
               "history_sha": st["history_sha"] == u["history_sha"] == r["history_sha"],
               "prompt_ids_sha": st["q_decision"]["prompt_ids_sha"] == u["prompt_ids_sha"]}
        tag = f"sc-{u['unit_id']}"
        if spec.get("dry"):  # diagnostic only: the local chat-template render differs from the server's prompt ids when a
            # history message has text + tool call with trailing whitespace (W88); the GPU run checks the servers' ids
            ws = any(m["role"] == "assistant" and m.get("tool_calls") and (m.get("content") or "") != (m.get("content") or "").rstrip()
                     for m in st["history"])
            rec["dry_local_prompt_ids"] = {"match": F.ids_sha(F.local_prompt_ids(st)) == u["prompt_ids_sha"], "history_has_text_toolcall_ws": ws}
        else:
            gb, rb = F.shadow(st, bases["B"], tag + "-sB")
            gq, rq = F.shadow(st, bases["Q"], tag + "-sQ")
            chk.update({"B_prompt_ids": F.ids_sha(rb.get("prompt_token_ids")) == u["prompt_ids_sha"],
                        "Q_prompt_ids": F.ids_sha(rq.get("prompt_token_ids")) == u["prompt_ids_sha"],
                        "B_regenerates_a_B": F.canon_msg(gb) == F.canon_msg(a_b), "Q_regenerates_a_Q": F.canon_msg(gq) == F.canon_msg(a_q)})
        rec["state_checks"] = chk
        if not all(chk.values()):
            return {**rec, "missing_reason": f"state check failed {chk}"}
        if lim is not None and i >= lim:
            return {**rec, "skipped": "dry run: state checks only"}
        st["a_B"], st["a_Q"] = {"message": a_b}, {"message": a_q}
        res, Y, proto = {}, {}, {}
        for arm in spec.get("arms", ["BQ", "QQ"]):
            br = F.run_branch(st, arm[0], arm[1], bases, user_base, f"{tag}-{arm}", user_llm=ul)
            res[arm] = br
            Y[arm] = None if "error" in br else _y(u["domain"], br)
            proto[arm] = _user_protocol(st, br) if "error" not in br else {"ok": False, "error": br["error"][:300]}
        dump(out / "branches" / f"{u['unit_id']}.json", {"state_id": st["state_id"], "history_sha": st["history_sha"], "arms": res})
        usage = {a: b.get("user_llm_usage") for a, b in res.items()}
        return {**rec, "Y_sonnet": Y, "protocol": proto, "termination": {a: b.get("termination_reason") for a, b in res.items()},
                "user_llm_usage": usage, "request_ids": {a: [c.get("request_id") for c in b.get("user_llm_calls") or []] for a, b in res.items()},
                "durations": {a: b.get("duration") for a, b in res.items()}}

    t0 = time.time()
    with ThreadPoolExecutor(spec.get("concurrency", 6)) as ex:
        recs = list(ex.map(lambda x: _safe(one, x), list(enumerate(units))))
    out.mkdir(parents=True, exist_ok=True)
    (out / "simctrl_rows.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False, default=str) + "\n" for x in recs))
    ran = [x for x in recs if "Y_sonnet" in x]
    tot = lambda f: sum((v or {}).get(f, 0) for x in ran for v in x["user_llm_usage"].values())  # noqa: E731
    res = {"protocol": "simctrl_v1 (W90)", "manifest_sha256": man_sha, "spec": {k: v for k, v in spec.items()}, "servers": servers,
           "n_units": len(units), "n_ran": len(ran), "n_state_ok": sum(1 for x in recs if "state_checks" in x and all(x["state_checks"].values())),
           "n_missing": sum(1 for x in recs if "missing_reason" in x), "n_errors": sum(1 for x in recs if "error" in x),
           "n_arm_errors": sum(1 for x in ran for v in x["Y_sonnet"].values() if v is None),
           "protocol_ok": all(p["ok"] for x in ran for p in x["protocol"].values()) and len(ran) > 0,
           "protocol_failures": [{"unit_id": x["unit_id"], "arm": a, **p} for x in ran for a, p in x["protocol"].items() if not p["ok"]],
           "termination": dict(collections.Counter(t for x in ran for t in x["termination"].values())),
           "user_llm_usage": {"n_calls": tot("n_calls"), "prompt_tokens": tot("prompt_tokens"), "completion_tokens": tot("completion_tokens"),
                              "cost_usd": tot("cost_usd")},
           "seconds": time.time() - t0, "dry": bool(spec.get("dry"))}
    res["pass"] = res["n_errors"] == 0 and res["n_missing"] == 0 and res["n_arm_errors"] == 0 and res["protocol_ok"]
    dump(out / "simctrl_summary.json", res)
    if spec.get("gate"):
        dump(out / "gate.json", {"verdict": "PASS" if res["pass"] else "FAIL", **res})
    log(f"simctrl {spec['model']}:{spec['cell']}: ran {res['n_ran']}/{res['n_units']}, state ok {res['n_state_ok']}, protocol_ok {res['protocol_ok']}, "
        f"usage {res['user_llm_usage']}, pass {res['pass']}")
    if spec.get("gate") and not res["pass"]:
        raise RuntimeError(f"simctrl gate failed: see {out / 'gate.json'}")
    return res


def bank_u_q0(spec, bases, user_base, servers, out):
    """Bank U Q0 controller (FORK_PROTOCOL §15 amendment 1, W70): on the frozen Q0 subsample of U2 rows (manifest q0 = true),
    both current actions recorded by the native bank_u run of `cell` (a_B, a_Q) are followed by the common continuation
    controller Q0 = <model> GPTQ-W4 d1. Servers: B = BF16 (prompt-id check only), Q = Q0. Arms: "B.Q0", "c.Q0". For
    cell = gptq_w4_d1 the native BQ / QQ are already the Q0 arms (no task needed). Reported separately from native."""
    import hashlib as _h
    man_sha = _h.sha256((ROOT / spec["manifest"]).read_bytes()).hexdigest()
    if spec.get("manifest_sha256") and spec["manifest_sha256"] != man_sha:
        raise SystemExit(f"bank_u_q0: manifest sha {man_sha} != frozen {spec['manifest_sha256']}")
    nat_dir = ROOT / spec["native_out"]
    nat_sum = json.loads((nat_dir / "bank_summary.json").read_text())
    if nat_sum.get("manifest_sha256") != man_sha:
        raise SystemExit("bank_u_q0: native run used a different manifest")
    nat = [json.loads(l) for l in (nat_dir / "bank_rows.jsonl").read_text().splitlines() if l.strip()]
    rows = [r for r in nat if r.get("q0") and r["sub"] in ("U2B", "U2Q")]
    blocks = {}

    def one(r):
        rec = {k: r.get(k) for k in ("state_key", "sub", "model", "block", "domain", "task_id", "t", "n_decisions", "selection_probability", "source_run", "cell")}
        rec["controller"] = f"{r['model']}:gptq_w4_d1"
        if "Y" not in r:
            return {**rec, "missing_reason": "native row missing: " + str(r.get("missing_reason") or r.get("error"))[:200]}
        k = (r["source_run"], r["domain"])
        if k not in blocks:
            blocks[k] = F.Block(ROOT, *k)
        st = F.make_state(blocks[k], r["task_id"], r["t"])
        if st["state_id"] != r["state_id"]:
            return {**rec, "missing_reason": "state id differs from native row"}
        _, rb = F.shadow(st, bases["B"], f"bq0-{r['state_key']}-sB")
        if F.ids_sha(rb.get("prompt_token_ids")) != st["q_decision"]["prompt_ids_sha"]:
            return {**rec, "missing_reason": "prompt id mismatch (B shadow)"}
        st["a_B"], st["a_Q"] = {"message": r["a_B"]}, {"message": r["a_Q"]}
        res, Y, src = {}, {}, {}
        res["B.Q0"] = F.run_branch(st, "B", "Q", bases, user_base, f"bq0-{r['cell']}-{r['state_key']}-B")
        if r["exact_agreement"]:
            Y["c.Q0"], src["c.Q0"] = None, "reuse=B.Q0"
        else:
            res["c.Q0"] = F.run_branch(st, "Q", "Q", bases, user_base, f"bq0-{r['cell']}-{r['state_key']}-c")
        for arm, br in res.items():
            Y[arm] = None if "error" in br else _y(r["domain"], br)
            src[arm] = "run" if "error" not in br else f"error: {br['error'][:120]}"
        if src.get("c.Q0") == "reuse=B.Q0":
            Y["c.Q0"] = Y["B.Q0"]
        rec.update({"state_id": st["state_id"], "exact_agreement": r["exact_agreement"], "Y": Y, "arm_source": src,
                    "Y_native": r["Y"], "budget_ok": {a: budget_check(st, b)["ok"] for a, b in res.items() if "error" not in b},
                    "context_overflow_arms": [a for a, b in res.items() if b.get("infra_cause") == "context_overflow"],
                    "durations": {a: b.get("duration") for a, b in res.items()}})
        dump(out / "branches" / f"{r['state_key']}.json", res)
        return rec

    t0 = time.time()
    with ThreadPoolExecutor(spec.get("concurrency", 8)) as ex:
        recs = list(ex.map(lambda r: _safe(one, r), rows))
    out.mkdir(parents=True, exist_ok=True)
    (out / "q0_rows.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False, default=str) + "\n" for x in recs))
    ok = [x for x in recs if "Y" in x]
    res = {"protocol": "bank_u_v1 Q0 controller (FORK_PROTOCOL §15 amendment 1)", "manifest_sha256": man_sha, "spec": spec,
           "servers": servers, "native_summary_sha256": _h.sha256((nat_dir / "bank_summary.json").read_bytes()).hexdigest(),
           "n_rows": len(rows), "n_ok": len(ok), "n_missing": sum(1 for x in recs if "missing_reason" in x),
           "n_errors": sum(1 for x in recs if "error" in x), "budget_ok": all(all(x["budget_ok"].values()) for x in ok),
           "n_branches_run": sum(sum(1 for v in x["arm_source"].values() if v == "run") for x in ok),
           "branch_seconds": [d for x in ok for d in x["durations"].values() if d], "seconds": time.time() - t0}
    dump(out / "q0_summary.json", res)
    log(f"bank_u_q0 {spec['model']}:{spec['cell']}: ok {res['n_ok']}/{res['n_rows']}, branches {res['n_branches_run']}, {res['seconds']:.0f} s")
    return res

def rerun_episode(block: F.Block, task_id: str, bases: dict, user_base: str, tag: str) -> dict:
    """W70: deterministically re-execute Q's original episode from the start (same task dump, simulation seed, nonce, tau2
    config, Q server) when its saved trajectory was lost (tau2 stores no messages for an episode that raised). An
    agent-side context-window error is caught and the partial trajectory kept. The re-run is accepted only if every
    re-run decision's prompt ids equal the originally recorded ones (and the counts agree)."""
    from tau2.data_model.tasks import Task
    from tau2.runner.build import build_text_orchestrator

    tr = block.traj[task_id]
    task = Task.model_validate(tr["task"])
    cfg = F.run_config(block.run_config, bases["Q"], user_base)
    orch = build_text_orchestrator(cfg, task, seed=tr["seed"])
    A = F.fork_agent_cls()
    orch.agent = A(tools=orch.environment.get_tools(), domain_policy=orch.environment.get_policy(), llm=cfg.llm_agent,
                   llm_args=json.loads(json.dumps(cfg.llm_args_agent)), task=task, nonce=block.nonce, forced=None, tag=tag, decision_idx=0)
    err = None
    try:
        orch.run()
    except Exception as e:
        err = repr(e)
    recs = F._W.pop(tag)
    msgs = [F.msg_to_dict(m) for m in sorted(orch.trajectory, key=lambda x: x.timestamp)]
    orig = block.dec[task_id]
    same = len(recs) == len(orig) and all(F.ids_sha(r.get("prompt_token_ids")) == F.ids_sha(o["prompt_token_ids"]) for r, o in zip(recs, orig))
    return {"messages": msgs, "error": err, "n_decisions_rerun": len(recs), "n_decisions_orig": len(orig), "reproduces_original": same,
            "agent_side": bool(err and "ContextWindowExceeded" in err)}


def repair_mode(spec, bases, user_base, servers, out):
    """W70: complete fork units that the original task could not finish.
      kind "branches": the state was frozen but a branch failed with a context-window error (now a recorded failure):
                       the state file is copied unchanged and branched again.
      kind "search":   the original episode ended in an agent-side context overflow and tau2 kept no messages, so no
                       state could be built: the episode is re-executed deterministically (rerun_episode), accepted only if
                       it reproduces every recorded prompt, and then searched with the dev-fork rule (Y_QQ = failure).
    spec["units"] = [{"dir", "run_id", "domain", "task_id", "kind"}]. analyze_dev reads analysis/fork/repair/ and prefers a
    unit's non-excluded record."""
    import shutil
    rows, sdir = [], out / "states"
    sdir.mkdir(parents=True, exist_ok=True)
    blocks, reruns = {}, {}
    for unit in spec["units"]:
        od = ROOT / unit["dir"]
        orig = next((r for r in json.load(open(od / "search.json"))["rows"]
                     if r.get("run_id") == unit["run_id"] and r.get("domain") == unit["domain"] and str(r.get("task_id")) == str(unit["task_id"])), None)
        if unit["kind"] == "branches" and orig is not None and orig.get("state_id"):
            shutil.copy(od / "states" / f"{orig['state_id']}.json", sdir / f"{orig['state_id']}.json")
            rows.append({**orig, "repair": "branches re-run"})
            continue
        k = (unit["run_id"], unit["domain"])
        if k not in blocks:
            blocks[k] = F.Block(ROOT, *k)
        b = blocks[k]
        tid = str(unit["task_id"])
        rr = _safe(rerun_episode, b, tid, bases, user_base, f"rerun-{unit['run_id']}-{tid}")
        reruns[f"{unit['run_id']}|{unit['domain']}|{tid}"] = {kk: v for kk, v in rr.items() if kk != "messages"}
        if "error" in rr and "messages" not in rr or not rr.get("reproduces_original") or not rr.get("agent_side"):
            rows.append({**(orig or {}), "run_id": unit["run_id"], "domain": unit["domain"], "task_id": tid,
                         "exclusion": f"repair: re-run not accepted ({ {kk: rr.get(kk) for kk in ('reproduces_original', 'agent_side', 'n_decisions_rerun', 'n_decisions_orig')} })",
                         "repair": "re-run rejected"})
            continue
        b.traj[tid] = {**b.traj[tid], "messages": rr["messages"], "n_messages": len(rr["messages"])}
        r = _safe(search_task, b, tid, bases, user_base, sdir, spec.get("q_check", True))
        rows.append({**r, "repair": "episode re-executed (reproduces original prompts) and searched"})
    dump(out / "search.json", {"rows": rows, "repair_of": spec["units"], "reruns": reruns})
    b = branches_mode({**spec, "states_dir": str(sdir.relative_to(ROOT)), "branches": ["BB", "BQ", "QB"], "noop_frac": 0.1}, bases, user_base, servers, out)
    return {"n_units": len(rows), "n_states": len(list(sdir.glob("*.json"))), "branches": len(b["rows"])}


def branches_mode(spec, bases, user_base, servers, out):
    sdir = ROOT / spec["states_dir"]
    states = [json.loads(p.read_text()) for p in sorted(sdir.glob("*.json"))]
    order = spec.get("branches", ["BB", "BQ", "QB"])
    # noop membership is decided on the full state set (before sharding), so shards reproduce the unsharded design
    noop_ids = {s["state_id"] for s in states if int(hsel("noop|" + s["state_id"])[:8], 16) / 16 ** 8 < spec.get("noop_frac", 0.1)}
    shard = spec.get("shard")  # W72: [k, n] -> this task branches only states with hash(state_id) % n == k
    if shard:
        k, n = shard
        states = [s for s in states if int(hsel("shard|" + s["state_id"])[:8], 16) % n == k]

    def done_file(st):  # W72 resume: a complete branch file (every requested branch present, none errored) is reused
        p = out / "branches" / f"{st['state_id']}.json"
        if not spec.get("resume") or not p.exists():
            return None
        try:
            r = json.loads(p.read_text())
        except Exception:
            return None
        need = order + (["QQ"] if st["state_id"] in noop_ids else [])
        return r if all(b in r and "error" not in r[b] for b in need) else None

    def one(st):
        r = done_file(st)
        if r is None:
            r = run_4(st, bases, user_base, order + (["QQ"] if st["state_id"] in noop_ids else []), "dev")
            dump(out / "branches" / f"{st['state_id']}.json", r)
        return {"state_id": st["state_id"], "outcomes": {b: {k: v.get(k) for k in ("reward", "db_match", "official_reward", "termination_reason", "duration", "error")} for b, v in r.items()}}

    t0 = time.time()
    with ThreadPoolExecutor(spec.get("concurrency", 8)) as ex:
        rows = list(ex.map(lambda s: _safe(one, s), states))
    res = {"protocol": F.PROTOCOL, "spec": spec, "servers": servers, "seconds": time.time() - t0, "rows": rows}
    dump(out / (f"branches_shard{shard[0]}of{shard[1]}.json" if shard else "branches.json"), res)
    return res


# ----------------------------------------------------------------------------
# CPU-only restoration check
# ----------------------------------------------------------------------------


def cpucheck(blocks: list[str], out: Path, every: int = 1, max_tasks: int = 0) -> dict:
    """For every (sampled) decision: rebuild h_t from trajectory.jsonl, replay the environment strictly, rebuild the
    agent state and render its prompt locally; it must equal Q's recorded (server-side) prompt ids. Also checks that
    the step/error recount reproduces tau2's termination on every max_steps / too_many_errors episode."""
    res = {"protocol": F.PROTOCOL, "blocks": []}
    for spec in blocks:
        run_id, dom = spec.split(":")
        b = F.Block(ROOT, run_id, dom)
        n = ok = mism = 0
        bad, term = [], []
        tids = sorted(b.traj)[: max_tasks or None]
        for tid in tids:
            tr = b.traj[tid]
            n0 = F.prefix_len(tr["task"])
            pos = F.agent_positions(tr["messages"], n0)
            if len(pos) != len(b.dec[tid]):
                mism += 1
                continue
            for t in range(0, len(pos), every):
                st = F.make_state(b, tid, t)
                good = F.ids_sha(F.local_prompt_ids(st)) == st["q_decision"]["prompt_ids_sha"]
                n += 1
                ok += good
                if not good:
                    bad.append([tid, t])
            s, e = F.budget_used(tr["messages"], n0)
            if tr["termination_reason"] in ("max_steps", "too_many_errors"):
                lim = b.run_config["max_steps"] if tr["termination_reason"] == "max_steps" else b.run_config["max_errors"]
                term.append({"task_id": tid, "termination": tr["termination_reason"], "steps": s, "errors": e,
                             "consistent": (s >= lim) if tr["termination_reason"] == "max_steps" else (e >= lim)})
        rec = {"block": spec, "n_tasks": len(tids), "n_count_mismatch": mism, "n_states": n, "n_prompt_match": ok, "bad": bad[:20],
               "n_budget_terminations": len(term), "n_budget_consistent": sum(x["consistent"] for x in term)}
        log(json.dumps(rec))
        res["blocks"].append(rec)
    res["ok"] = all(r["n_prompt_match"] == r["n_states"] and r["n_budget_consistent"] == r["n_budget_terminations"] for r in res["blocks"])
    dump(out, res)
    return res


def reverdict(out: Path) -> dict:
    """Recompute the gate checks offline from the saved state and branch files (no server). Used after a comparator
    fix; every change is recorded under `reverdict` with the reason, and the original verdict is kept."""
    g = json.loads((out / "gate.json").read_text())
    old = g["verdict"]
    blk_cache: dict = {}

    def blk(st):
        k = (st["run_id"], st["domain"])
        if k not in blk_cache:
            blk_cache[k] = F.Block(ROOT, *k)
        return blk_cache[k]

    for s in g.get("a_noop_BB", []):
        if "error" in s:
            continue
        b = blk({"run_id": s["run_id"], "domain": s["domain"]})
        st = F.make_state(b, s["task_id"], s["t"])  # current make_state (official_reward recomputed when absent)
        r = json.loads((out / "branches" / f"{st['state_id']}_bbnoop.json").read_text())
        s["noop"] = noop_check(st, r, orig_final_hash(st, b))
        s["orig_official_reward_source"] = st["orig"]["official_reward_source"]
    for s in g.get("states", []):
        if "error" in s:
            continue
        st = json.loads((out / "states" / f"{s['state_id']}.json").read_text())
        st["orig"]["official_reward"] = F.official_from_traj(blk(st).traj[st["task_id"]])
        r4 = json.loads((out / "branches" / f"{s['state_id']}_fwd.json").read_text())
        s["a_noop_QQ"] = noop_check(st, r4["QQ"], orig_final_hash(st, blk(st)))
    g["verdict"] = verdict(g)
    g.setdefault("reverdict", []).append({"time": time.time(), "old_verdict": old, "reason":
        "original runs written before trajectory.jsonl carried official_reward (e.g. a6k2_q4_null_n1) had None on the "
        "original side; the original official_reward is now recomputed from the stored reward_info with basis_reward's formula "
        "(validated: 335/335 episodes with the field reproduce it)"})
    dump(out / "gate.json", g)
    log("reverdict " + json.dumps(g["verdict"]))
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reverdict", default=None, help="fork out dir: recompute gate checks from saved files")
    ap.add_argument("--task")
    ap.add_argument("--b-base")
    ap.add_argument("--q-base")
    ap.add_argument("--user-base", default="http://127.0.0.1:8000/v1")
    ap.add_argument("--servers", default=None)
    ap.add_argument("--cpucheck", action="store_true")
    ap.add_argument("--block", action="append", default=[])
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--max-tasks", type=int, default=0)
    ap.add_argument("--out")
    a = ap.parse_args()
    from loguru import logger

    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    F.setup_tau2()
    if a.reverdict:
        reverdict(ROOT / a.reverdict)
        return
    if a.cpucheck:
        r = cpucheck(a.block, ROOT / a.out, a.every, a.max_tasks)
        print(json.dumps({"ok": r["ok"]}))
        sys.exit(0 if r["ok"] else 1)
    task = json.load(open(a.task))
    spec = task["fork"]
    servers = json.load(open(a.servers)) if a.servers else {}
    bases = {"B": a.b_base, "Q": a.q_base}
    out = ROOT / spec["out"]
    out.mkdir(parents=True, exist_ok=True)
    fn = {"gate": gate, "gate_same": gate_same, "search": search_mode, "branches": branches_mode, "dev": dev_mode, "pivot_arms": pivot_arms, "bank_u": bank_u, "bank_u_q0": bank_u_q0, "repair": repair_mode, "simctrl": simctrl}[spec["mode"]]
    r = fn(spec, bases, a.user_base, servers, out)
    v = r.get("verdict")
    print(json.dumps({"verdict": v}, default=str))


if __name__ == "__main__":
    main()
