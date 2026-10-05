"""Takeover-window panel tasks (docs/insights/TAKEOVER_WINDOW_PROTOCOL.md, tw-v1). Writes nothing without --write.

  manifest  build manifests/fork/takeover_window_v1.json: the q8 U2B rows f01-f06 of newmethod_panel_v1.json (verbatim),
            the endpoint block of every (config, block), the template task of each and the row-list sha256 values
  gate      one gate task per config: fork mode takeover_window on 8 f01 states (the same states for both configs),
            windows L = 1, 4 and all four endpoints re-run (repro "all"), switch-point checks, at the panel concurrency;
            both gates name the same simulator replica and wait for each other (co_gate), so the rate is measured at
            two fork tasks per replica
  handback  outcome-blind check of gate criterion 6: prints only the per-decision server sequence (B/Q) and counters
  decide    scale decision from the two gate summaries (throughput and pass fields only; no outcome field is read):
            6 blocks iff now + SAFETY * projected wall <= DEADLINE, else 3; written once, refused if it exists
  panel     endpoint tasks (spinquant_w4a4 f04-f06, mode bank_u, only if the decision says 6) and one window task per
            config x block, every one depending on its config's gate, chained so at most S_eff run at once
usage: python scripts/a6000/make_tasks_takeover.py {manifest|gate|handback|decide|panel} [--write] [--nodes n1,n2] [--slots S]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT, WORK = Path("/data/ziyangs/cloq"), Path("/data/ziyangs/cloq_work")
QD = WORK / "queue"
PANEL, PANEL_SHA = "manifests/fork/newmethod_panel_v1.json", "7534c6907fa68bc8dab48061d7a2944a719e6e2fa123b639e7a0674c5a6ca201"
BANKU_SHA = "e236ee6483e723ffe8acd743ff2f5af8c1f92b49a39a7e721359c960ee12a907"
MAN = "manifests/fork/takeover_window_v1.json"
OUT = "analysis/fork/takeover"
BLOCKS = ("f01", "f02", "f03", "f04", "f05", "f06")
CELLS = ("gptq_w4_d1", "spinquant_w4a4")
DEADLINE = dt.datetime(2026, 10, 5, 21, 0, tzinfo=dt.timezone(dt.timedelta(hours=-7)))  # 21:00 PDT
SAFETY, CONCURRENCY, PRIORITY, REPRO = 1.5, 6, -21, 0.1
KEEP = ("kind", "model", "gpus", "B", "Q")  # copied from the endpoint task (roles verbatim, incl. serve_env); nothing stale
GATE_USER_BASE, WAIT_OK, GATE_MAX_S = "http://node005:8000/v1", 4.0, 7200


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rows_sha(rows: list[dict]) -> str:
    """sha256 of the frozen row list: [state_key, block, domain, task_id, t, source_run] sorted by state_key, compact JSON."""
    v = sorted([r["state_key"], r["block"], r["domain"], r["task_id"], r["t"], r["source_run"]] for r in rows)
    return hashlib.sha256(json.dumps(v, separators=(",", ":")).encode()).hexdigest()


def endpoint(cell: str, blk: str) -> dict:
    if cell == "gptq_w4_d1":
        if blk <= "f03":
            return {"src_out": f"analysis/fork/bank_u/q8_gptq_w4_d1/{blk}", "src_manifest_sha256": BANKU_SHA, "template": f"bank_u_q8_gptq_w4_d1_{blk}"}
        return {"src_out": f"analysis/fork/commonstate/q8/ref_d1/{blk}", "src_manifest_sha256": PANEL_SHA, "template": f"cs_ref_q8_gptq_w4_d1_{blk}"}
    if blk <= "f03":
        rr = f"analysis/fork/newmethod/tau2_recovery/q8_spinquant_w4a4/{blk}/rr1"
        return {"src_out": f"analysis/fork/newmethod/tau2/q8_spinquant_w4a4/{blk}", "src_manifest_sha256": PANEL_SHA,
                "rr_out": rr if (ROOT / rr / "recovery_summary.json").exists() else None, "template": f"nmp_tau2_q8_spinquant_w4a4_{blk}"}
    return {"src_out": f"{OUT}/endpoints/q8_spinquant_w4a4/{blk}", "src_manifest_sha256": PANEL_SHA, "template": "nmp_tau2_q8_spinquant_w4a4_f01",
            "new_endpoint_task": f"tw_ep_q8_spinquant_w4a4_{blk}"}


def build_manifest() -> dict:
    assert sha_file(ROOT / PANEL) == PANEL_SHA
    rows = [r for r in json.loads((ROOT / PANEL).read_text())["rows"] if r["model"] == "q8" and r["sub"] == "U2B"]
    assert len(rows) == 510 and not any(r["missing_reason"] for r in rows)
    return {"version": "tw-v1", "model": "q8", "protocol": "docs/insights/TAKEOVER_WINDOW_PROTOCOL.md", "created": time.strftime("%F %T %Z"),
            "panel_manifest": PANEL, "panel_manifest_sha256": PANEL_SHA, "cells": list(CELLS), "windows": [1, 4], "sources": ["B", "Q"],
            "rows_sha256": {"f01-f03": rows_sha([r for r in rows if r["block"] <= "f03"]), "f01-f06": rows_sha(rows)},
            "endpoints": {c: {b: endpoint(c, b) for b in BLOCKS} for c in CELLS}, "rows": rows}


def man() -> tuple[dict, str]:
    p = ROOT / MAN
    return json.loads(p.read_text()), sha_file(p)


def differs(cell: str) -> dict:
    """state_key -> current actions a_B, a_Q render differently, from the f01 endpoint rows (action fields only)."""
    sys.path.insert(0, str(ROOT))
    import takeover_window as TW
    rs = [json.loads(x) for x in (ROOT / endpoint(cell, "f01")["src_out"] / "bank_rows.jsonl").read_text().splitlines() if x.strip()]
    return {x["state_key"]: TW.raw_key(x["a_B"]) != TW.raw_key(x["a_Q"]) for x in rs if x.get("sub") == "U2B" and "a_Q" in x}


def gate_keys(m: dict) -> list[str]:
    """8 f01 states in hash order among those whose BF16 source episode has > 5 decisions after t (so an L = 4 window can
    hand back): 4 retail + 2 airline, plus the first 2 others whose current actions differ for BOTH cells (non-reused
    BQ/QB endpoints, non-trivial B vs Q windows); structure and actions only."""
    f01 = sorted((r for r in m["rows"] if r["block"] == "f01" and r["n_decisions"] - r["t"] - 1 > 5),
                 key=lambda r: hashlib.sha256(f"tw-v1-gate|{r['state_key']}".encode()).hexdigest())
    k = [r["state_key"] for r in f01 if r["domain"] == "retail"][:4] + [r["state_key"] for r in f01 if r["domain"] == "airline"][:2]
    d = [differs(c) for c in CELLS]
    return sorted(k + [r["state_key"] for r in f01 if r["state_key"] not in k and all(x.get(r["state_key"]) for x in d)][:2])


def task(cell: str, blk: str, tid: str, fork: dict, deps: list, node, prio: int, note: str) -> dict:
    ep = endpoint(cell, blk)
    tpl = json.loads((QD / "done" / f"{ep['template']}.json").read_text())
    srv = json.loads((WORK / "logs/tasks" / f"{ep['template']}.servers.json").read_text())
    expect = {r: {k: srv[r].get(k) for k in ("canary", "ckpt_sha256", "effective_config_sha")} for r in ("B", "Q")}
    if fork["mode"] == "takeover_window":
        fork = {**fork, "expect": expect}
    return {**{k: tpl[k] for k in KEEP if k in tpl}, "id": tid, "node": node, "priority": prio, "deps": deps, "fork": fork,
            "autopilot_retry": "no (tw-v1: a failed task is left for a human)", "note": note, "created": time.strftime("%F %T")}


def window_fork(cell: str, blk: str, m_sha: str, **kw) -> dict:
    ep = endpoint(cell, blk)
    f = {"mode": "takeover_window", "manifest": MAN, "manifest_sha256": m_sha, "model": "q8", "cell": cell, "block": blk,
         "src_out": ep["src_out"], "src_manifest_sha256": ep["src_manifest_sha256"], "windows": [1, 4], "sources": ["B", "Q"],
         "repro": REPRO, "shadow_check": True, "concurrency": CONCURRENCY, "out": f"{OUT}/q8_{cell}/{blk}"}
    if ep.get("rr_out"):
        f["rr_out"] = ep["rr_out"]
    return {**f, **kw}


def put(t: dict, write: bool) -> None:
    if any((QD / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed", "deferred")):
        print(f"exists, skipped: {t['id']}")
        return
    print(t["id"], t["fork"]["mode"], t["fork"].get("block") or t["fork"].get("blocks"), "deps", t["deps"], "node", t["node"], "->", t["fork"]["out"])
    if write:
        p = QD / "todo" / f"{t['id']}.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(t, indent=1))
        tmp.rename(p)


def decide(slots: int, now: dt.datetime) -> dict:
    """Throughput-only scale rule (protocol §6). Reads window_summary.json pass/throughput fields and the gate tasks' wall
    seconds. Capacity is bounded by the simulator: S_eff = min(S, fork tasks per replica validated at gate load x live replicas)."""
    import simreg
    g, iv = {}, {}
    for c in CELLS:
        s = json.loads((ROOT / OUT / "gate" / f"q8_{c}" / "window_summary.json").read_text())
        d = json.loads((QD / "done" / f"tw_gate_q8_{c}.json").read_text())
        if not s["gate_pass"]:
            raise SystemExit(f"gate {c} did not pass; no panel")
        if d["seconds"] > GATE_MAX_S:
            raise SystemExit(f"gate {c} took {d['seconds']:.0f} s > {GATE_MAX_S} s (protocol §5); no panel")
        tp = s["throughput"]
        cap = tp["concurrency"] * tp["pool_efficiency"] * 3600  # suffix-seconds per task-hour at gate load
        g[c] = {"suffixes_per_hour": tp["suffixes_per_hour"], "overhead_h": max(d["seconds"] - tp["job_seconds"], 0) / 3600,
                "block_h": 85 * (4 * tp["mean_W_seconds"] + 4 * REPRO * tp["mean_R_seconds"]) / cap, "endpoint_block_h": 85 * 3 * tp["mean_R_seconds"] / cap,
                "user_base": tp["user_base"], "sim_waiting_p90": tp["sim_load"]["waiting_p50_p90_max"][1]}
        iv[c] = (tp["jobs_start_unix"], tp["jobs_end_unix"])
    (a0, a1), (b0, b1) = iv.values()
    overlap = max(0.0, min(a1, b1) - max(a0, b0)) / max(min(a1 - a0, b1 - b0), 1e-9)
    shared = len({g[c]["user_base"] for c in CELLS}) == 1 and overlap >= 0.5 and all(g[c]["sim_waiting_p90"] is not None and g[c]["sim_waiting_p90"] <= WAIT_OK for c in CELLS)  # no load samples: not shown
    replicas = sorted(r["url"] for r in simreg.all_instances().values() if simreg.is_live(r))
    s_eff = max(1, min(slots, (2 if shared else 1) * len(replicas)))
    plan = {}
    for k in (3, 6):
        tasks = [(c, "block_h") for c in CELLS for _ in range(k)] + ([("spinquant_w4a4", "endpoint_block_h")] * 3 if k == 6 else [])
        work = sum(g[c]["overhead_h"] + g[c][h] for c, h in tasks)
        chain = max(g[c]["overhead_h"] + g[c][h] for c, h in tasks) * (2 if k == 6 else 1)
        wall = SAFETY * max(work / s_eff, chain)
        plan[k] = {"n_tasks": len(tasks), "task_hours": work, "longest_chain_h": chain, "projected_wall_h": wall,
                   "projected_finish": (now + dt.timedelta(hours=wall)).isoformat(), "fits": now + dt.timedelta(hours=wall) <= DEADLINE}
    blocks = 6 if plan[6]["fits"] else 3
    return {"rule": "6 blocks iff now + SAFETY * max(task-hours / S_eff, longest chain) <= DEADLINE, else 3 (protocol §6); decided once",
            "now": now.isoformat(), "deadline": DEADLINE.isoformat(), "SAFETY": SAFETY, "slots": slots, "gate": g, "plan": plan,
            "simulator": {"live_replicas": replicas, "gate_overlap": overlap, "two_per_replica_validated": shared, "WAIT_OK": WAIT_OK},
            "S_eff": s_eff,
            "blocks": list(BLOCKS[:blocks]), "alpha2_capacity_h": (DEADLINE - now).total_seconds() / 3600 - plan[blocks]["projected_wall_h"],
            "inputs_read": "window_summary.json gate_pass + throughput, gate task seconds, simulator registry only"}


def handback(cell: str) -> None:
    """Gate criterion 6 without outcomes: per window suffix, which server answered each generated decision and the
    counters. Prints nothing else from branches/ (protocol §5)."""
    for f in sorted((ROOT / OUT / "gate" / f"q8_{cell}" / "branches").glob("*.json")):
        for arm, r in sorted(json.loads(f.read_text()).items()):
            w = r.get("window") or {}
            if not arm.startswith("W_") or not w:
                continue
            seq = "".join("-" if not d.get("api_base") else "Q" if d["api_base"] == w["base_after"] else "B"
                          for d in r.get("decisions") or [] if not d.get("forced"))
            print(f.stem, arm, "L", w["L"], "n_cont", w["n_cont"], "switch_idx", w["switch_decision_idx"], "servers", seq)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("manifest", "gate", "handback", "decide", "panel"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--nodes", default="", help="comma list, assigned round robin (empty: unpinned)")
    ap.add_argument("--slots", type=int, default=0, help="decide: parallel 2-GPU fork slots the queue can give this panel")
    ap.add_argument("--priority", type=int, default=PRIORITY)
    a = ap.parse_args()
    nodes = [n for n in a.nodes.split(",") if n] or [None]
    if a.cmd == "manifest":
        if (ROOT / MAN).exists():
            raise SystemExit(f"{MAN} exists (frozen); never rewritten")
        m = build_manifest()
        print(json.dumps({k: m[k] for k in ("rows_sha256", "endpoints")}, indent=1))
        if a.write:
            (ROOT / MAN).write_text(json.dumps(m, indent=1))
            print(MAN, sha_file(ROOT / MAN))
        return
    m, m_sha = man()
    if a.cmd == "gate":
        keys = gate_keys(m)
        for i, c in enumerate(CELLS):
            f = window_fork(c, "f01", m_sha, repro="all", state_keys=keys, switch_env_check=True, gate=True, out=f"{OUT}/gate/q8_{c}",
                            co_gate=f"tw_gate_q8_{CELLS[1 - i]}")
            t = task(c, "f01", f"tw_gate_q8_{c}", f, [], nodes[i % len(nodes)], a.priority - 1,
                     "tw-v1 gate (TAKEOVER_WINDOW_PROTOCOL §5): windows + all endpoint re-runs on 8 f01 states; throughput for §6")
            put({**t, "user_base": GATE_USER_BASE}, a.write)  # both gates on one replica: rate at two tasks per replica
        return
    if a.cmd == "handback":
        for c in CELLS:
            handback(c)
        return
    dp = ROOT / OUT / "scale_decision.json"
    if a.cmd == "decide":
        if dp.exists():
            raise SystemExit(f"{dp} exists: the scale is decided once")
        if a.slots <= 0:
            raise SystemExit("--slots required")
        d = decide(a.slots, dt.datetime.now(dt.timezone.utc))
        print(json.dumps(d, indent=1))
        if a.write:
            dp.parent.mkdir(parents=True, exist_ok=True)
            dp.write_text(json.dumps(d, indent=1))
        return
    dec = json.loads(dp.read_text())
    blocks, s_eff, ids = dec["blocks"], dec["S_eff"], []
    chain = lambda deps: deps + ([ids[-s_eff]] if len(ids) >= s_eff else [])  # noqa: E731  at most S_eff panel tasks at once
    k = 0
    for blk in blocks:  # block-major: the blocks complete at the deadline are complete for both configs
        for c in CELLS:
            ep, deps = endpoint(c, blk), [f"tw_gate_q8_{c}"]
            if ep.get("new_endpoint_task"):
                ef = {"mode": "bank_u", "manifest": PANEL, "manifest_sha256": PANEL_SHA, "model": "q8", "cell": c, "blocks": [blk],
                      "subs": ["U2B"], "noop_frac": 0.1, "concurrency": CONCURRENCY, "out": ep["src_out"]}
                put(task(c, blk, ep["new_endpoint_task"], ef, chain(deps), nodes[k % len(nodes)], a.priority,
                         "tw-v1 endpoint arms (BB/BQ/QB/QQ, bank_u semantics) at a block without SpinQuant endpoints; never enters a NEWMETHOD analysis"), a.write)
                ids.append(ep["new_endpoint_task"])
                deps = deps + [ep["new_endpoint_task"]]
                k += 1
            put(task(c, blk, f"tw_q8_{c}_{blk}", window_fork(c, blk, m_sha), chain(deps), nodes[k % len(nodes)], a.priority,
                     "tw-v1 window panel (TAKEOVER_WINDOW_PROTOCOL): L = 1, 4 x source B, Q; 10% endpoint re-run sample"), a.write)
            ids.append(f"tw_q8_{c}_{blk}")
            k += 1


if __name__ == "__main__":
    sys.exit(main())
