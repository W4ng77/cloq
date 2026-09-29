"""One persistent runner per node (one Slurm job holding the node's GPUs; see the epilog hazard).

Starts the node's user simulator, then keeps every remaining GPU busy by claiming tasks from the
shared file queue (/data/ziyangs/cloq_work/queue/todo -> running, atomic rename) whose dependencies
are done, and running each in scripts/a6000/worker.py on 1 or 2 GPUs. Writes per-GPU status JSON
under /data/ziyangs/cloq_work/status/ for the dashboard.

Stops claiming when <queue>/STOP or <queue>/STOP.<node> exists, or when less than --min-left
seconds of the Slurm allocation remain; exits when nothing it can run is left and all workers are done.

usage (inside sbatch): python scripts/a6000/noderunner.py --sim-gpus 0,1 --sim-model q30a3
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
WORK = Path("/data/ziyangs/cloq_work")
Q = WORK / "queue"
STATUS = WORK / "status"
MODELS = json.load(open(ROOT / "scripts/a6000/models.json"))
sys.path.insert(0, str(ROOT / "scripts/a6000"))
from worker import healthy, snapshot, stop_server  # noqa: E402

NODE = socket.gethostname().split(".")[0]


def log(msg: str) -> None:
    print(f"[{time.strftime('%F %T')}] {NODE} {msg}", flush=True)


def set_status(gpu: str, rec: dict) -> None:
    p = STATUS / f"{NODE}-g{gpu}.json"
    rec = {"updated": time.time(), "host": NODE, "job": os.environ.get("SLURM_JOB_ID"), **rec}
    p.with_suffix(".tmp").write_text(json.dumps(rec))
    p.with_suffix(".tmp").replace(p)


def time_left() -> float:
    end = os.environ.get("CLOQ_JOB_END")
    return float(end) - time.time() if end else 1e9


def done_ids() -> set[str]:
    return {p.stem for p in (Q / "done").glob("*.json")}


def pending_tasks() -> list[tuple[Path, dict]]:
    out = []
    for p in (Q / "todo").glob("*.json"):
        try:
            out.append((p, json.load(open(p))))
        except Exception:
            continue
    return sorted(out, key=lambda x: (x[1].get("priority", 100), x[1]["id"]))


def gpus_needed(t: dict) -> int:
    if t["kind"] == "calib":
        return 0
    return int(MODELS[t["model"]]["gpus"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpus", default="0,1,2,3,4,5,6,7")
    ap.add_argument("--sim-gpus", default="0,1")
    ap.add_argument("--sim-model", default="q30a3")
    ap.add_argument("--sim-maxlen", type=int, default=65536)
    ap.add_argument("--min-left", type=float, default=3 * 3600)
    ap.add_argument("--idle-exit", type=float, default=1800)
    ap.add_argument("--only-models", default="", help="comma list; claim only these models' tasks")
    args = ap.parse_args()
    for d in ("todo", "running", "done", "failed"):
        (Q / d).mkdir(parents=True, exist_ok=True)
    STATUS.mkdir(parents=True, exist_ok=True)
    sim_gpus = [g for g in args.sim_gpus.split(",") if g]
    free = [g for g in args.gpus.split(",") if g not in sim_gpus]
    only = set(filter(None, args.only_models.split(",")))

    sim = None
    if sim_gpus:
        m = MODELS[args.sim_model]
        env = dict(os.environ, CLOQ_TOOL_PARSER=m["parser"])
        for g in sim_gpus:
            set_status(g, {"state": "setup", "task": "user simulator", "detail": f"starting {args.sim_model}"})
        slog = open(WORK / f"logs/sim_{NODE}_{os.environ.get('SLURM_JOB_ID', 'x')}.log", "a")
        sim = subprocess.Popen([str(ROOT / "scripts/a6000/serve.sh"), ",".join(sim_gpus), "8000",
                                snapshot(m["hf_id"], m["revision"]), "user", str(args.sim_maxlen)],
                               env=env, stdout=slog, stderr=subprocess.STDOUT, start_new_session=True)
        t0 = time.time()
        while not healthy(8000):
            if sim.poll() is not None or time.time() - t0 > 1800:
                log("user simulator failed to start")
                for g in sim_gpus:
                    set_status(g, {"state": "failed", "task": "user simulator", "detail": "did not start"})
                sys.exit(1)
            time.sleep(5)
        log(f"user simulator {args.sim_model} up on GPUs {sim_gpus}")
        for g in sim_gpus:
            set_status(g, {"state": "user", "task": "user simulator", "model": args.sim_model, "detail": "port 8000"})
    for g in free:
        set_status(g, {"state": "idle", "task": ""})

    workers: dict[int, tuple[subprocess.Popen, list[str], str]] = {}
    stopping = {"flag": False}

    def on_term(*_):
        stopping["flag"] = True
        log("SIGTERM: stopping workers")
        for p, gs, tid in workers.values():
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        time.sleep(20)
        for p, gs, tid in workers.values():  # requeue interrupted tasks
            rp = Q / "running" / f"{tid}.json"
            if rp.exists():
                rp.replace(Q / "todo" / f"{tid}.json")
        stop_server(sim, sim_gpus)
        sys.exit(0)

    signal.signal(signal.SIGTERM, on_term)
    idle_since = time.time()
    while True:
        for pid, (p, gs, tid) in list(workers.items()):
            if p.poll() is not None:
                log(f"task {tid} exited rc={p.returncode} on GPUs {gs}")
                free.extend(gs)
                for g in gs:
                    if p.returncode != 0:
                        set_status(g, {"state": "idle", "task": "", "detail": f"last task {tid} failed"})
                    else:
                        set_status(g, {"state": "idle", "task": ""})
                del workers[pid]
        if sim is not None and sim.poll() is not None:
            log("user simulator died; stopping claims")
            stopping["flag"] = True
        stop = stopping["flag"] or (Q / "STOP").exists() or (Q / f"STOP.{NODE}").exists() or time_left() < args.min_left
        claimed = False
        if not stop:
            ready = done_ids()
            for path, t in pending_tasks():
                if only and t.get("model") not in only:
                    continue
                if t.get("node") and t["node"] != NODE:
                    continue
                if not all(d in ready for d in t.get("deps", [])):
                    continue
                need = gpus_needed(t)
                if need > len(free):
                    continue
                if need == 0 and any(True for w in workers.values() if w[1] == []):
                    continue  # one CPU task at a time per node
                rp = Q / "running" / path.name
                try:
                    path.replace(rp)
                except FileNotFoundError:
                    continue
                gs = [free.pop(0) for _ in range(need)]
                port = 8001 + int(gs[0]) if gs else 0
                cmd = [sys.executable, str(ROOT / "scripts/a6000/worker.py"), str(rp), "--gpus", ",".join(gs),
                       "--port", str(port), "--status-prefix", str(STATUS / NODE)]
                p = subprocess.Popen(cmd, cwd=ROOT, start_new_session=True,
                                     stdout=open(WORK / "logs/tasks" / f"{t['id']}.worker.log", "a"), stderr=subprocess.STDOUT)
                workers[p.pid] = (p, gs, t["id"])
                log(f"claimed {t['id']} on GPUs {gs} port {port}")
                claimed = True
        if workers or claimed:
            idle_since = time.time()
        elif time.time() - idle_since > args.idle_exit or stop:
            log("nothing left to run; exiting")
            break
        time.sleep(15)
    stop_server(sim, sim_gpus)
    for g in args.gpus.split(","):
        set_status(g, {"state": "idle", "task": "", "detail": "runner exited"})


if __name__ == "__main__":
    (WORK / "logs/tasks").mkdir(parents=True, exist_ok=True)
    main()
