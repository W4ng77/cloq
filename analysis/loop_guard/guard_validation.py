"""Validation of the lg-v1 loop early-stop guard (cloq/loop_guard.py) on existing trajectories (W69, plan §8.4.3).

Subcommands
  freeze-sample  Build the frozen, configuration-blinded validation sample from completed runs and write
                 manifests/stress/loop_guard_validation_v1.json BEFORE the guard is scored on it. Selection uses only
                 trace content and an independent reference criterion, never the guard's output:
                   obvious loop (target 20): an episode of a stress run (W3 / KV4 / KV3 cells, incl. restoration arms)
                     that ended in max_steps or too_many_errors, whose last 16 agent decisions contain <= 2 distinct
                     canonical actions, and whose agent-side DB hash is unchanged over those 16 decisions;
                   legitimate repetition / long success (target 30: 15 from stress runs, 15 from BF16 runs): a
                     successful episode (DB success, normal ending) with >= 20 agent decisions, or with >= 3 calls of
                     one tool name on different arguments.
                 Within each pool, candidates are taken in sha256("cloq-lg-v1-validation|run|domain|task") order.
                 Configuration names are replaced by opaque ids in the blinded export.
  score          Run the guard on the frozen sample; report false positives (fires on a legitimate trace) and false
                 negatives (does not fire on an obvious loop); write a blinded trace export for human audit.
  scan           Premature-stopping scan: replay the guard over every episode of every existing stress run (and,
                 separately, BF16 runs) and list each episode the guard would have stopped that later succeeded.
Pre-declared pass rule: 0 false positives in the sample AND 0 guard stops on later-successful episodes in the scan.
False negatives are allowed (the rule is deliberately conservative) and reported.

usage: python analysis/loop_guard/guard_validation.py freeze-sample|score|scan [--procs 4]
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "analysis/fork"))
OUT = ROOT / "analysis/loop_guard/out"
SAMPLE = ROOT / "manifests/stress/loop_guard_validation_v1.json"
STRESS_RE = re.compile(r"^a6k2_(?:pert_)?(q\d+)_.*(rtn_w3|gptq_w3|awq_w3|kvq_int4|kvq_int3)")
BF16_RE = re.compile(r"^a6k2_(q\d+)_(bfpair|null)_")
DOMS = ("retail", "airline")


def hkey(*parts) -> str:
    return hashlib.sha256(("cloq-lg-v1-validation|" + "|".join(parts)).encode()).hexdigest()


def runs(pattern) -> list[str]:
    out = []
    for p in sorted((ROOT / "runs").iterdir()):
        if not pattern.match(p.name) or "_tel_" in p.name:
            continue
        for d in DOMS:
            st = p / d / "status.json"
            if (p / d / "trajectory.jsonl").exists() and st.exists() and json.load(open(st)).get("status") == "completed":
                out.append(f"{p.name}/{d}")
    return out


def load(rd: str) -> list[dict]:
    return [json.loads(x) for x in open(ROOT / "runs" / rd / "trajectory.jsonl") if x.strip()]


def n_decisions(t) -> int:
    from cloq.fork import prefix_len
    n0 = prefix_len(t["task"])
    return sum(1 for m in t["messages"][n0:] if m.get("role") == "assistant")


def is_loop_ref(t, dom) -> bool:
    from cloq import loop_guard as G
    from cloq.fork import prefix_len
    if t.get("termination_reason") not in ("max_steps", "too_many_errors"):
        return False
    n0 = prefix_len(t["task"])
    decs = G.decisions_from_messages(t["messages"], n0)
    last = decs[-16:]
    if len(last) < 16 or len({d["action"] for d in last}) > 2:
        return False
    h = env_hashes(t, dom, [last[0]["pos"], last[-1]["end"]])
    return None not in h and h[0] == h[1]


def env_hashes(t, dom, ks):
    from tau2.data_model.tasks import Task
    from cloq.fork import msg_from_dict, restore_env
    task = Task.model_validate(t["task"])
    out = []
    for k in ks:
        try:
            out.append(restore_env(dom, task, [msg_from_dict(m) for m in t["messages"][:k]]).get_db_hash())
        except Exception:
            out.append(None)
    return out


def is_legit_ref(t, dom) -> bool:
    from analyze_dev import success
    if not success(dom, t):
        return False
    if n_decisions(t) >= 20:
        return True
    calls = [(tc.get("name"), json.dumps(tc.get("arguments"), sort_keys=True))
             for m in t["messages"] if m.get("role") == "assistant" for tc in (m.get("tool_calls") or [])]
    by = Counter(n for n, _ in calls)
    return any(c >= 3 and len({a for n2, a in calls if n2 == n}) >= 2 for n, c in by.items())


def freeze_sample():
    if SAMPLE.exists():
        raise SystemExit(f"{SAMPLE} exists: the sample is frozen")
    cands = {"loop": [], "legit_stress": [], "legit_bf16": []}
    for rd in runs(STRESS_RE):
        for t in load(rd):
            k = hkey(rd, str(t["task_id"]))
            cands["loop"].append((k, rd, str(t["task_id"])))
            cands["legit_stress"].append((k, rd, str(t["task_id"])))
    for rd in runs(BF16_RE):
        for t in load(rd):
            cands["legit_bf16"].append((hkey(rd, str(t["task_id"])), rd, str(t["task_id"])))
    target = {"loop": 20, "legit_stress": 15, "legit_bf16": 15}
    cache = {}

    def traj(rd, tid):
        if rd not in cache:
            cache[rd] = {str(t["task_id"]): t for t in load(rd)}
        return cache[rd][tid]
    picked = {}
    for pool, lst in cands.items():
        got = []
        for k, rd, tid in sorted(lst):
            t = traj(rd, tid)
            dom = rd.split("/")[1]
            ok = is_loop_ref(t, dom) if pool == "loop" else is_legit_ref(t, dom)
            if ok:
                got.append({"blind_id": k[:10], "run": rd.split("/")[0], "domain": dom, "task_id": tid, "pool": pool})
            if len(got) >= target[pool]:
                break
        picked[pool] = got
    items = [x for v in picked.values() for x in v]
    rec = {"policy_under_test": "lg-v1", "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "selection": __doc__.split("Subcommands")[1].split("score ")[0].strip(),
           "pools_sizes": {k: len(v) for k, v in cands.items()}, "targets": target,
           "items": items, "items_sha256": hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest(),
           "note": "selected by trace content and the reference criterion only; the guard was not run on this sample "
                   "before freezing (an exploratory replay of one q4 RTN-W3 run preceded the freeze)"}
    SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    SAMPLE.write_text(json.dumps(rec, indent=1))
    print({k: len(v) for k, v in picked.items()}, "->", SAMPLE)


def _guard_one(args):
    rd, tid = args
    from cloq import loop_guard as G
    from analyze_dev import success
    dom = rd.split("/")[1]
    for t in load(rd):
        if str(t["task_id"]) == tid:
            ev = G.replay_episode(t, dom)
            return {"run": rd, "task_id": tid, "success": success(dom, t), "termination": t.get("termination_reason"),
                    "n_decisions": n_decisions(t), "fired": ev is not None, "evidence": ev}
    return None


def _guard_run(rd):
    from cloq import loop_guard as G
    from analyze_dev import success
    dom = rd.split("/")[1]
    out = []
    for t in load(rd):
        ev = G.replay_episode(t, dom)
        out.append({"run": rd, "task_id": str(t["task_id"]), "success": success(dom, t), "termination": t.get("termination_reason"),
                    "n_decisions": n_decisions(t), "fired": ev is not None,
                    "evidence": {k: ev[k] for k in ("cycle_len", "repeats", "stop_before_decision", "n_decisions_actual", "budget",
                                                    "env_hash", "actions")} if ev else None})
    return out


def score(procs):
    s = json.load(open(SAMPLE))
    with ProcessPoolExecutor(procs) as ex:
        res = list(ex.map(_guard_one, [(f"{x['run']}/{x['domain']}", x["task_id"]) for x in s["items"]]))
    rows = []
    for x, r in zip(s["items"], res):
        rows.append({**x, **{k: r[k] for k in ("fired", "success", "termination", "n_decisions")},
                     "evidence": r["evidence"] and {k: r["evidence"][k] for k in ("cycle_len", "repeats", "stop_before_decision")}})
    fp = [r for r in rows if r["pool"] != "loop" and r["fired"]]
    fn = [r for r in rows if r["pool"] == "loop" and not r["fired"]]
    n_loop = sum(r["pool"] == "loop" for r in rows)
    summ = {"policy": "lg-v1", "code_sha256": __import__("cloq.loop_guard", fromlist=["x"]).code_sha(),
            "sample": str(SAMPLE.relative_to(ROOT)), "sample_items_sha256": s["items_sha256"],
            "n_loop": n_loop, "n_legit": len(rows) - n_loop, "false_positives": len(fp), "false_negatives": len(fn),
            "sensitivity": round(1 - len(fn) / max(n_loop, 1), 3), "fp_items": [r["blind_id"] for r in fp],
            "fn_items": [r["blind_id"] for r in fn], "rows": rows}
    OUT.mkdir(parents=True, exist_ok=True)
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    (OUT / f"validation_{utc}.json").write_text(json.dumps(summ, indent=1))
    blind_export(s["items"], OUT / f"validation_blinded_{utc}.md")
    print(json.dumps({k: v for k, v in summ.items() if k != "rows"}, indent=1))


def blind_export(items, path):
    """Configuration-blinded view (opaque id, last 16 decisions) for human audit of the reference labels."""
    from cloq import loop_guard as G
    from cloq.fork import prefix_len
    L = ["# lg-v1 validation sample, blinded (opaque ids; run / configuration hidden)", ""]
    for x in sorted(items, key=lambda x: x["blind_id"]):
        rd = f"{x['run']}/{x['domain']}"
        t = next(t for t in load(rd) if str(t["task_id"]) == x["task_id"])
        decs = G.decisions_from_messages(t["messages"], prefix_len(t["task"]))
        L += [f"## {x['blind_id']} ({x['domain']}, {len(decs)} decisions, ended {t.get('termination_reason')})", ""]
        for d in decs[-16:]:
            L.append(f"- `{d['action'][:160]}` -> {d['evidence']}")
        L.append("")
    path.write_text("\n".join(L) + "\n")


def scan(procs):
    groups = {"stress": runs(STRESS_RE), "bf16": runs(BF16_RE)}
    OUT.mkdir(parents=True, exist_ok=True)
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    summ = {"policy": "lg-v1", "code_sha256": __import__("cloq.loop_guard", fromlist=["x"]).code_sha(), "utc": utc}
    for g, rds in groups.items():
        rows = []
        with ProcessPoolExecutor(procs) as ex:
            for r in ex.map(_guard_run, rds):
                rows += r
        with open(OUT / f"scan_{g}_{utc}.jsonl", "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        prem = [r for r in rows if r["fired"] and r["success"]]
        summ[g] = {"n_runs": len(rds), "n_episodes": len(rows), "n_fired": sum(r["fired"] for r in rows),
                   "fired_by_termination": dict(Counter(r["termination"] for r in rows if r["fired"])),
                   "premature_stops_on_successes": [{k: r[k] for k in ("run", "task_id", "termination", "n_decisions")} |
                                                    {"stop_before_decision": r["evidence"]["stop_before_decision"],
                                                     "cycle_len": r["evidence"]["cycle_len"]} for r in prem],
                   "decisions_saved": sum(r["n_decisions"] - r["evidence"]["stop_before_decision"] for r in rows if r["fired"]),
                   "decisions_total": sum(r["n_decisions"] for r in rows)}
    (OUT / f"scan_{utc}.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps({g: {k: v for k, v in summ[g].items() if k != "premature_stops_on_successes"} | {
        "n_premature": len(summ[g]["premature_stops_on_successes"])} for g in groups}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["freeze-sample", "score", "scan"])
    ap.add_argument("--procs", type=int, default=4)
    a = ap.parse_args()
    {"freeze-sample": freeze_sample, "score": lambda: score(a.procs), "scan": lambda: scan(a.procs)}[a.cmd]()


if __name__ == "__main__":
    main()
