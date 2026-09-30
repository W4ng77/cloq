"""Load-aware user-simulator routing (single replica per node on port 8000; multi-replica needs the instance registry, W34) for new tasks (docs/EXECUTION_PLAN_20260930.md §4.1).

Every PERIOD seconds, read each node's latest gpumon sample for the simulator (port 8000: running, waiting, KV use) and
rewrite queue/USER_BASE.<node>, which worker.py reads at task start (W16), so that an overloaded node's NEXT tasks use
the least-loaded replica. Running episodes are never moved. All replicas serve the same model with the same numerics
canary, so routing does not change outcomes. A node goes back to its own simulator once that is no longer busy.
Hysteresis: a node's route changes at most once per HOLD seconds. Every change is appended to logs/sim_balancer.log.

usage: nohup python scripts/a6000/sim_balancer.py >/dev/null 2>&1 &     (--once for a single pass, --dry to only print)
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

W = Path("/data/ziyangs/cloq_work")
Q = W / "queue"
LOG = W / "logs" / "sim_balancer.log"
PERIOD, HOLD, STALE = 300, 900, 240
BUSY, FREE = 10.0, 3.0            # load scores: redirect away from > BUSY, only onto <= FREE, return home when <= FREE
DEFAULT = {"node003": "node006"}  # nodes without a simulator: their runner's CLOQ_USER_BASE
last_change: dict[str, float] = {}


def sims(now: float) -> dict[str, float]:
    out = {}
    for f in (W / "gpumon").glob("node*.jsonl"):
        try:
            line = f.read_bytes().rstrip().rsplit(b"\n", 1)[-1]
            d = json.loads(line)
        except Exception:
            continue
        if now - d.get("ts", 0) > STALE:
            continue
        for s in d.get("srv", []):
            if s.get("port") == 8000:
                out[f.stem] = s["wait"] + 0.1 * s["run"] + 20 * max(0.0, s["kv"] - 0.8)
    return out


def agent_nodes() -> list[str]:
    return sorted({f.stem for f in (W / "gpumon").glob("node*.jsonl")})


def route(node: str) -> str | None:
    f = Q / f"USER_BASE.{node}"
    if f.exists() and f.read_text().strip():
        return f.read_text().strip().split("//")[1].split(":")[0]
    return None


def log(msg: str):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as fh:
        fh.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg + "\n")


def one_pass(dry: bool):
    now = time.time()
    load = sims(now)
    if not load:
        return
    for n in agent_nodes():
        home = n if n in load else DEFAULT.get(n)
        cur = route(n) or home
        if cur is None or now - last_change.get(n, 0) < HOLD:
            continue
        best = min(load, key=load.get)
        new = cur
        if load.get(cur, 99) > BUSY and load[best] <= FREE and best != cur:
            new = best
        elif cur != home and home in load and load[home] <= FREE:
            new = home
        if new == cur:
            continue
        msg = f"{n}: {cur} ({load.get(cur, -1):.1f}) -> {new} ({load[new]:.1f}); loads {json.dumps({k: round(v, 1) for k, v in load.items()})}"
        print(msg)
        if dry:
            load[new] += BUSY / 2
            continue
        f = Q / f"USER_BASE.{n}"
        if new == n:
            f.unlink(missing_ok=True)
        else:
            tmp = f.with_suffix(f".tmp{os.getpid()}")  # atomic replace: a worker never reads a half-written route
            tmp.write_text(f"http://{new}:8000/v1\n")
            os.replace(tmp, f)
        last_change[n] = now
        load[new] += BUSY / 2  # expected extra load, so one pass does not herd every busy node onto the same replica
        log(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    while True:
        one_pass(a.dry)
        if a.once or a.dry:
            return
        time.sleep(PERIOD)


if __name__ == "__main__":
    main()
