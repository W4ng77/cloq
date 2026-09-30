"""Automatic analysis scheduling and board feed (2026-09-30, W35).

Every PERIOD seconds:
  1. For each experiment in docs/insights/EXPERIMENT_REGISTRY.json, count its queue tasks (todo / running / done /
     failed / deferred) and runs by the registry's task-id regexes.
  2. Run CPU analyses whose trigger holds ("all_done": every task of the experiment done and none pending;
     "new_done": the done set changed since the last run; "script_exists_and_new_done": as new_done, once the script
     exists). Analyses that need a GPU are ordinary single-GPU queue tasks and are not run here. A CPU run first builds
     one fresh integrity-gated snapshot per cycle (analysis/insights/iter_2/integrity.py, low priority, few processes).
  3. Write analysis/status/board_feed.json (main line, experiments with role/fit/progress/last analysis, queue
     totals) for the dashboard sync, and append every analysis run to analysis/status/analysis_runs.jsonl.
Runs on the login node under `nice`; analysis outputs are not committed here (the main session commits them).

usage: nohup python scripts/a6000/analysis_daemon.py >/dev/null 2>&1 &     (--once for one cycle)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
Q = Path("/data/ziyangs/cloq_work/queue")
REG = ROOT / "docs/insights/EXPERIMENT_REGISTRY.json"
OUT = ROOT / "analysis/status"
STATE = OUT / "analysis_daemon_state.json"
PERIOD, TIMEOUT = 600, 3600
DIRS = ("todo", "running", "done", "failed", "deferred")


def queue_index():
    idx = {}
    for d in DIRS:
        for f in (Q / d).glob("*.json"):
            try:
                t = json.load(open(f))
            except Exception:
                continue
            idx[f.stem] = (d, len(t.get("runs", [])), t.get("finished"))
    return idx


def match(exp, idx):
    pats = [re.compile(p) for p in exp.get("patterns", [])]
    excl = [re.compile(p) for p in exp.get("exclude", [])]
    return {k: v for k, v in idx.items() if pats and any(p.search(k) for p in pats) and not any(e.search(k) for e in excl)}


def snapshot(cache):
    if "path" in cache:
        return cache["path"]
    utc = time.strftime("%Y%m%dT%H%MZ", time.gmtime())
    path = ROOT / f"analysis/insights/iter_3/out/snapshot_auto_{utc}.json"
    r = subprocess.run(["nice", "-n", "10", "python", "analysis/insights/iter_2/integrity.py", "--out", str(path), "--procs", "6"],
                       cwd=ROOT, capture_output=True, text=True, timeout=TIMEOUT)
    cache["path"] = str(path) if r.returncode == 0 and path.exists() else None
    return cache["path"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--feed-only", action="store_true", help="write progress without running analyses")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    while True:
        if not a.feed_only and not a.once:
            subprocess.run(["python", __file__, "--feed-only", "--once"], cwd=ROOT)  # progress first, analyses after
        reg = json.load(open(REG))
        state = json.load(open(STATE)) if STATE.exists() else {}
        idx = queue_index()
        snap = {}
        feed = {"updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "mainline": reg["mainline"],
                "queue": {d: sum(1 for v in idx.values() if v[0] == d) for d in DIRS}, "experiments": []}
        for e in reg["experiments"]:
            m = match(e, idx)
            cnt = {d: sum(1 for v in m.values() if v[0] == d) for d in DIRS}
            runs = {d: sum(v[1] for v in m.values() if v[0] == d) for d in DIRS}
            done_ids = sorted(k for k, v in m.items() if v[0] == "done")
            dhash = hashlib.sha1("|".join(done_ids).encode()).hexdigest()[:12]
            an = e.get("analysis", {})
            st = state.get(e["id"], {})
            rec = {"id": e["id"], "title": e["title"], "role": e["role"], "fit": e["fit"], "done_note": e.get("done_note"),
                   "tasks": cnt, "runs": runs, "analysis": an.get("name"), "analysis_mode": an.get("run"),
                   "last_analysis": st.get("last")}
            if an.get("run") == "cpu" and not a.feed_only:
                script_ok = (ROOT / an["script"]).exists()
                pending = cnt["todo"] + cnt["running"]
                trig = an.get("trigger")
                due = (trig == "all_done" and done_ids and not pending) or \
                      (trig == "new_done" and done_ids) or \
                      (trig == "script_exists_and_new_done" and script_ok and done_ids)
                if not script_ok:
                    rec["analysis_state"] = "waiting for script " + an["script"]
                elif not due:
                    rec["analysis_state"] = "waiting for data" if not done_ids or trig == "all_done" else "up to date"
                elif st.get("dhash") == dhash:
                    rec["analysis_state"] = "up to date"
                else:
                    sp = snapshot(snap)
                    if sp is None:
                        rec["analysis_state"] = "snapshot failed"
                    else:
                        cmd = an["cmd"].replace("{snapshot}", sp)
                        t0 = time.time()
                        try:
                            r = subprocess.run(["nice", "-n", "10", "bash", "-c", cmd], cwd=ROOT, capture_output=True, text=True, timeout=TIMEOUT)
                            rc, tail = r.returncode, (r.stdout + r.stderr)[-1500:]
                        except subprocess.TimeoutExpired:
                            rc, tail = -1, "timeout"
                        last = {"when": feed["updated"], "rc": rc, "seconds": round(time.time() - t0), "snapshot": sp, "cmd": cmd, "tail": tail}
                        with open(OUT / "analysis_runs.jsonl", "a") as fh:
                            fh.write(json.dumps({"exp": e["id"], **last}) + "\n")
                        state[e["id"]] = {"dhash": dhash if rc == 0 else st.get("dhash"), "last": last}
                        rec["last_analysis"] = last
                        rec["analysis_state"] = "ran ok" if rc == 0 else f"failed rc={rc}"
            elif an.get("run") == "cpu":
                rec["analysis_state"] = st.get("last") and ("ran ok" if st["last"].get("rc") == 0 else "last run failed") or "pending (next cycle)"
            else:
                rec["analysis_state"] = {"queue": "single-GPU queue tasks", "agent": "engineering agent", "done": "done",
                                         "none": "none"}.get(an.get("run"), an.get("run"))
            feed["experiments"].append(rec)
        if not a.feed_only:
            json.dump(state, open(STATE, "w"), indent=1)
        (OUT / "board_feed.json").write_text(json.dumps(feed, indent=1))
        if a.once:
            return
        time.sleep(PERIOD)


if __name__ == "__main__":
    main()
