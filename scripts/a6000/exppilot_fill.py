"""GPU-fill helpers for scripts/a6000/exppilot.py (W100r): queue index, live runners, idle agent GPUs, runnable demand,
deferred-release candidates and failing task families. Everything here only reads, except release(), which moves one task
deferred/ -> todo/ atomically. Never touches queue/running/, never calls sbatch / scancel / kill.

Definitions (mirroring scripts/a6000/noderunner.py):
  live runner   a RUNNING Slurm job of ours named cloq-node (squeue, read-only); its node's status files carry its job id
  agent GPU     a status file of the live job whose card is not a user simulator
  idle GPU      an agent GPU with state idle and no task, not listed in DRAIN.<node>, node without STOP / STOP.<node>
  runnable      a todo task whose deps are all done, not kind sim, fitting a live runner (GPU count, node pin, known model)
  demand        sum of the GPUs of the runnable todo tasks (calib tasks = 0, as noderunner)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
WORK = Path("/data/ziyangs/cloq_work")
Q = WORK / "queue"
STATUS = WORK / "status"
DIRS = ("todo", "running", "done", "failed", "deferred")
# Stopped or stuck by the main session (never released), plus any task whose deferral note says "stopped".
STOPPED = {"pert_q4_rtn_w3_restore_early_q345", "a6k2_q32_tel_rtn_w4", "pert_q8_rtn_w3_restore_rand_attn_s3_q345"}
NOTE_KEYS = ("deferred_note", "deferred_reason", "defer_note")
EXCLUDE_RE = re.compile(r"ext_l8_|smoke|(^|_)l8(_|$)")
# Lines closed by a gate verdict: their remaining deferred tasks stay deferred.
HELD_MODELS = {"g12": "g12 not admitted (W100p gate FAIL); its gate tasks stay deferred"}
FILL_PRIORITY = -19


def index() -> dict:
    """task id -> queue dir over all five dirs."""
    return {p.stem: d for d in DIRS for p in (Q / d).glob("*.json")}


def load(d: str, tid: str) -> dict | None:
    try:
        return json.loads((Q / d / f"{tid}.json").read_text())
    except (OSError, ValueError):
        return None


def models() -> dict:
    return json.loads((ROOT / "scripts/a6000/models.json").read_text())


def gpus_needed(t: dict, M: dict) -> int:
    if t.get("kind") == "calib":
        return 0
    if t.get("gpus") is not None:
        return int(t["gpus"])
    return int(M[t["model"]]["gpus"]) if t.get("model") in M else 99


def live_runners() -> dict:
    """node -> job id of our running cloq-node runner jobs."""
    r = subprocess.run(["squeue", "-h", "-u", os.environ.get("USER", "ziyangs"), "-t", "R", "-n", "cloq-node", "-o", "%i %N"],
                       capture_output=True, text=True, timeout=60)
    return {x[1]: x[0] for x in (ln.split() for ln in r.stdout.splitlines()) if len(x) == 2}


def _drained(node: str) -> set:
    try:
        return {g.strip() for g in (Q / f"DRAIN.{node}").read_text().replace("\n", ",").split(",") if g.strip()}
    except OSError:
        return set()


def gpu_state(live: dict) -> dict:
    """node -> {"agent": [gpu], "idle": [gpu]} for the live runner nodes."""
    out = {n: {"agent": [], "idle": []} for n in live}
    for p in STATUS.glob("node*-g*.json"):
        node, g = p.stem.rsplit("-g", 1)
        try:
            s = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if node not in live or str(s.get("job")) != live[node] or s.get("state") == "user" or s.get("task") == "user simulator":
            continue
        out[node]["agent"].append(g)
        stop = (Q / "STOP").exists() or (Q / f"STOP.{node}").exists()
        if s.get("state") == "idle" and not s.get("task") and g not in _drained(node) and not stop:
            out[node]["idle"].append(g)
    return out


def runnable(t: dict, done: set, cap: dict, M: dict) -> bool:
    if t.get("kind") == "sim" or not all(d in done for d in t.get("deps") or []):
        return False
    need = gpus_needed(t, M)
    return need <= cap.get(t["node"], 0) if t.get("node") else need <= max(cap.values(), default=0)


def demand(idx: dict, cap: dict, M: dict) -> tuple[int, list]:
    done = {k for k, v in idx.items() if v == "done"}
    ids = [k for k, v in idx.items() if v == "todo" and (t := load("todo", k)) and runnable(t, done, cap, M)]
    return sum(gpus_needed(load("todo", k) or {}, M) for k in ids), ids


def place(t: dict, need: int, gs: dict) -> bool:
    """Reserve idle cards for t on one live node (its node pin respected; 1 card, or need/2 idle NVLink pairs (0,1)..(6,7),
    as noderunner places TP=2 and multi-pair tasks). Returns False, reserving nothing, when no node has room."""
    for n, v in gs.items():
        if t.get("node") not in (None, n):
            continue
        pairs = sorted({str(int(g) & ~1) for g in v["idle"] if str(int(g) ^ 1) in v["idle"]}, key=int)
        if need == 1 and v["idle"]:
            v["idle"].remove(v["idle"][0])
            return True
        if need >= 2 and need % 2 == 0 and len(pairs) >= need // 2:
            for p in pairs[:need // 2]:
                v["idle"].remove(p)
                v["idle"].remove(str(int(p) + 1))
            return True
    return False


def family(tid: str) -> str:
    return "_".join(tid.split("_")[:3])


def failing_families(window: float = 7200, limit: int = 3) -> dict:
    """task family -> failures within the window, for families with more than `limit` (failed_at, else file mtime)."""
    now, cnt = time.time(), {}
    for p in (Q / "failed").glob("*.json"):
        t = load("failed", p.stem) or {}
        try:
            ts = float(t.get("failed_at") or p.stat().st_mtime)
        except (OSError, ValueError):
            continue
        if now - ts <= window:
            cnt[family(p.stem)] = cnt.get(family(p.stem), 0) + 1
    return {f: n for f, n in cnt.items() if n > limit}


def excluded(t: dict) -> str | None:
    if t["id"] in STOPPED or any("stopped" in str(t.get(k, "")).lower() for k in NOTE_KEYS):
        return "stopped by main session"
    if EXCLUDE_RE.search(t["id"]):
        return "ext_l8_/smoke/l8"
    if t.get("model") in HELD_MODELS:
        return HELD_MODELS[t["model"]]
    if t.get("kind") == "sim":
        return "sim task"
    return None


def candidates(idx: dict, cap: dict, M: dict, blocked: set) -> tuple[list, dict]:
    """Deferred tasks releasable now, ordered by (priority, age); and why every other deferred task is held."""
    done = {k for k, v in idx.items() if v == "done"}
    ok, skip = [], {}
    for tid in sorted(k for k, v in idx.items() if v == "deferred"):
        t = load("deferred", tid)
        if t is None:
            continue
        why = excluded(t) or (f"family {family(tid)} failing" if family(tid) in blocked else None) \
            or (None if runnable(t, done, cap, M) else "deps not done or no live runner fits")
        if why:
            skip[tid] = why
            continue
        try:
            age = (Q / "deferred" / f"{tid}.json").stat().st_mtime
        except OSError:
            continue
        ok.append((float(t.get("priority", 100)), age, tid, t))
    ok.sort(key=lambda x: (x[0], x[1]))
    return [(tid, t) for _, _, tid, t in ok], skip


def release(tid: str, t: dict, stamp: str) -> None:
    """deferred/ -> todo/ (tmp + os.replace), priority -19, requeue_note; a gate_same fork gets fail_loud."""
    if any((Q / d / f"{tid}.json").exists() for d in ("todo", "running", "done", "failed")):
        raise FileExistsError(f"{tid} already outside deferred/")
    t = dict(t, priority=FILL_PRIORITY)
    t["requeue_note"] = (str(t.get("requeue_note", "")) + f" | exppilot fill {stamp}").strip(" |")
    if (t.get("fork") or {}).get("mode") == "gate_same":
        t["fork"] = dict(t["fork"], fail_loud=True)
    tmp = Q / "todo" / f".exppilot_{tid}.tmp"
    tmp.write_text(json.dumps(t, indent=1))
    os.replace(tmp, Q / "todo" / f"{tid}.json")
    os.remove(Q / "deferred" / f"{tid}.json")
