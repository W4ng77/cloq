"""W100w (F3): queue outage re-run tasks for FAILED eval tasks (worker.py `rerun_outage`, cloq/rerun_outage.py).

For each failed eval task whose error is "N infrastructure_error episodes (outage)": select the run-domains that hold
>= 1 outage-classified episode and whose never-run episodes are no more than their outage ones (a mostly unrun run-domain is
a resume of the original task, not an outage re-run). The new task <id>_rro keeps the original model, arm, ckpt, runs
(run ids, task files, nonces, env), serve_env/serve_extra and deps, and adds rerun_outage (the run-domains), run_par and
max_concurrency (low load on the task's own agent server), priority and autopilot_retry (a failed re-run is left for a
human, never re-queued by the infra retry). A task is skipped when its estimate, started at --start-by, ends after
--deadline. Estimate (conservative): 0.5 h setup + per run-domain ceil(n / max_concurrency) rounds x p90 of that run-domain's
non-outage episode durations under the original load.

usage: python scripts/a6000/make_tasks_rerun_outage.py [ids ...] [--out plan.json] [--write]
"""
from __future__ import annotations

import argparse, json, math, os, statistics, sys, time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from cloq.rerun_outage import is_outage  # noqa: E402

ROOT, Q = Path("/data/ziyangs/cloq"), Path("/data/ziyangs/cloq_work/queue")
EVID = "analysis/status/gpu_fill_20261003/rerun_premise_det.json"
KEEP = ("kind", "model", "arm", "ckpt", "runs", "domains", "serve_env", "serve_extra", "deps", "gpus", "node")


def premise(t: dict, sides: set) -> str:
    se = t.get("serve_env") or {}
    if "--dtype" in " ".join(t.get("serve_extra") or []) or t["ckpt"].get("kind") == "awq":
        return "NOT verified: AWQ fp16 path diverges across det pairs (x1_awq)"
    if se.get("CLOQ_KVQ_BITS") or se.get("CLOQ_KIVI_KBITS") or se.get("CLOQ_AQ_BITS"):
        return ("UNVERIFIED closed loop: pyhook batch invariance shown only open-loop on q4 (8 prompts, batch-of-9 and "
                "prefix-hit = alone, analysis/kvq/validate_q4.json); closed-loop pair a6k2_det_q4_kvq_int4_rot has no _b")
    base = {"q4": "verified directly: q4 BF16 TP=1 pair 257/257",
            "q8": "verified directly: q8 BF16 telecom pair 1520/1520 (to 32k tokens)",
            "q14": "verified by kernel class: q14 TP=1 pair (x1_fp8, 366/366 to 27k tokens), q4 BF16 pair",
            "q32": "verified by kernel class: q32 TP=2 pair (x1_fp8, 290/290 to 14k tokens), q30a3 TP=2 pair (303/303 to 26k)"}
    s = base.get(t["model"], "UNVERIFIED: no det pair for this model")
    return s + ("; user simulator q30a3 pair 303/303" if "user" in sides else "") + f" ({EVID})"


def scan(rid: str, dom: str, task_file: str) -> dict:
    base = ROOT / "runs" / rid / dom
    mf = json.load(open(ROOT / task_file))
    n_task = len(mf[dom] if isinstance(mf, dict) else mf)
    st = json.load(open(base / "status.json")).get("status") if (base / "status.json").exists() else None
    res = base / "tau2_results.json"
    if not res.exists() or res.stat().st_size == 0:
        return {"status": st, "n_tasks": n_task, "n_outage": 0, "n_missing": None, "sides": []}
    sims = json.load(open(res)).get("simulations") or []
    out = [s for s in sims if is_outage(s)]
    dur = sorted(s.get("duration") or 0 for s in sims if str(s.get("termination_reason")) != "infrastructure_error")
    return {"status": st, "n_tasks": n_task, "n_sims": len(sims), "n_outage": len(out),
            "n_missing": n_task - len({str(s["task_id"]) for s in sims}),
            "sides": sorted({"agent" if "llm_agent.py" in str((s.get("info") or {}).get("error_traceback", "")) else "user" for s in out}),
            "dur_mean_s": round(statistics.mean(dur)) if dur else None, "dur_p90_s": dur[int(0.9 * (len(dur) - 1))] if dur else None,
            "dur_max_s": dur[-1] if dur else None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--priority", type=int, default=-21)
    ap.add_argument("--run-par", type=int, default=1)
    ap.add_argument("--max-concurrency", type=int, default=4)
    ap.add_argument("--start-by", default="2026-10-03T22:00:00-07:00", help="assumed latest start (GPU fill forecast)")
    ap.add_argument("--deadline", default="2026-10-04T21:00:00-07:00", help="evidence freeze (W100t)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--todo", default=str(Q / "todo"), help="where --write puts the tasks (a scratch dir for tests)")
    a = ap.parse_args()
    ids = a.ids or sorted(p.stem for p in (Q / "failed").glob("*.json")
                          if "infrastructure_error episodes (outage)" in str(json.load(open(p)).get("error", "")))
    budget_h = (datetime.fromisoformat(a.deadline) - datetime.fromisoformat(a.start_by)).total_seconds() / 3600
    plan = {"made": time.strftime("%F %T %Z"), "budget_h": budget_h, "args": vars(a), "tasks": {}}
    for tid in ids:
        t = json.load(open(Q / "failed" / f"{tid}.json"))
        if t.get("kind") != "eval" or t.get("env"):  # tau2 eval tasks only (task "env" = simulator-free external benchmark)
            print(f"{tid}: not a tau2 eval task; skipped")
            continue
        rd = {f"{r['run_id']}/{d}": scan(r["run_id"], d, r["task_file"]) for r in t["runs"] for d in t.get("domains", ("retail", "airline"))}
        sel = [k for k, v in rd.items() if v["n_outage"] and v["n_missing"] <= v["n_outage"]]
        est = 0.5 + sum(math.ceil((rd[k]["n_outage"] + rd[k]["n_missing"]) / a.max_concurrency) * (rd[k]["dur_p90_s"] or 3600) / 3600 for k in sel)
        sides = {s for k in sel for s in rd[k]["sides"]}
        new = f"{tid}_rro"
        exists = [s for s in ("todo", "running", "done", "failed", "deferred") if (Q / s / f"{new}.json").exists()]
        why = ("no run-domain qualifies" if not sel else f"estimate {est:.1f} h > budget {budget_h:.1f} h" if est > budget_h
               else f"{new} already in {exists}" if exists else None)
        rec = {"run_domains": rd, "selected": sel, "estimate_h": round(est, 1), "premise": premise(t, sides) if sel else None,
               "skip": why, "episodes": {k: {"outage": rd[k]["n_outage"], "missing": rd[k]["n_missing"]} for k in sel}}
        plan["tasks"][tid] = rec
        print(f"{tid:46s} sel={sel} est={est:.1f}h skip={why}")
        if why or not a.write:
            continue
        sel_runs = {k.split("/")[0] for k in sel}
        task = {k: t[k] for k in KEEP if k in t} | {
            "id": new, "runs": [r for r in t["runs"] if r["run_id"] in sel_runs], "rerun_outage": sel, "rerun_of": tid,
            "run_par": a.run_par, "max_concurrency": a.max_concurrency, "priority": a.priority,
            "autopilot_retry": "no (W100w: a failed outage re-run is left for a human; an infra retry would double-run it)",
            "coverage_only": True, "determinism_premise": rec["premise"], "estimate_h": rec["estimate_h"],
            "note": (f"W100w F3 (user-approved 2026-10-03 '都做'): re-run only the outage episodes (+ never-run ids) of {sel} at "
                     f"run_par {a.run_par} / max_concurrency {a.max_concurrency} on this task's own agent server; same run ids, "
                     "nonces, seeds, ckpt and serve_env; originals archived under runs/<id>/<domain>/rerun_outage/<tag>/orig. "
                     "Coverage/appendix cells only."),
            "created": time.strftime("%F %T")}
        tmp = Path(a.todo) / f".{new}.json.tmp"
        tmp.write_text(json.dumps(task, indent=1))
        os.replace(tmp, Path(a.todo) / f"{new}.json")
        print(f"  queued {new}")
    if a.out:
        Path(a.out).write_text(json.dumps(plan, indent=1))


if __name__ == "__main__":
    main()
