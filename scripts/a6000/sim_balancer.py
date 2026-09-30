"""Load-aware user-simulator routing by instance URL (docs/EXECUTION_PLAN_20260930.md §4.1, W34-infra).

Replicas come from the instance registry (scripts/a6000/simreg.py: cloq_work/sims/<node>-<port>.json; several per node
are allowed). Every PERIOD seconds: per-instance load = waiting + 0.1 * running + 20 * max(0, KV - 0.8), read from the
node's latest gpumon sample for that port (fallback: the replica's /metrics). Only live instances (state up, fresh ok
health) are routable. For every agent node the route file queue/USER_BASE.<node> (read by worker.py user_base() at
each run start, W16) is rewritten atomically so that the node's NEXT runs use a lightly loaded replica:
  - the current route is a dead/draining/unknown instance -> move now (no hysteresis);
  - current load > BUSY and some replica <= FREE           -> move (a free local replica first);
  - routed away from home and a local replica is <= FREE    -> back home.
Hysteresis: a node's route changes at most once per HOLD seconds. No herding: a move adds BUSY/2 to the target's
expected load for the rest of the pass. Running episodes are never moved (route is read at run start; leases keep a
draining replica up until its clients finish). Every change is appended to logs/sim_balancer.log. The balancer also
refreshes the health record of `adopted` replicas (started by pre-registry runners, which do not heartbeat).

usage: nohup python scripts/a6000/sim_balancer.py >/dev/null 2>&1 &     (--once for a single pass, --dry to only print)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import simreg  # noqa: E402

W = simreg.WORK
Q = W / "queue"
LOG = W / "logs" / "sim_balancer.log"
PERIOD, HOLD, STALE = 300, 900, 240
BUSY, FREE = 10.0, 3.0            # load scores: redirect away from > BUSY, only onto <= FREE, return home when <= FREE
DEFAULT = {"node003": "node006"}  # nodes without a simulator: their runner's CLOQ_USER_BASE host (port 8000)
last_change: dict[str, float] = {}


def score(s: dict) -> float:
    return s["wait"] + 0.1 * s["run"] + 20 * max(0.0, s["kv"] - 0.8)


def samples(now: float) -> dict[tuple[str, int], dict]:
    out = {}
    for f in (W / "gpumon").glob("node*.jsonl"):
        try:
            with open(f, "rb") as fh:
                fh.seek(max(0, f.stat().st_size - 8192))
                d = json.loads(fh.read().rstrip().rsplit(b"\n", 1)[-1])
        except Exception:
            continue
        if now - d.get("ts", 0) > STALE:
            continue
        for s in d.get("srv", []):
            out[(f.stem, int(s["port"]))] = s
    return out


def metrics_direct(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(url.rsplit("/v1", 1)[0] + "/metrics", timeout=5) as r:
            m = r.read().decode()
    except Exception:
        return None
    v = {}
    for key, name in (("run", "vllm:num_requests_running"), ("wait", "vllm:num_requests_waiting"), ("kv", "vllm:kv_cache_usage_perc")):
        vals = [float(ln.rsplit(" ", 1)[1]) for ln in m.splitlines() if ln.startswith(name + "{") or ln.startswith(name + " ")]
        v[key] = vals[-1] if vals else 0.0
    return v


def live_loads(now: float, dry: bool) -> tuple[dict[str, float], dict[str, dict]]:
    smp = samples(now)
    loads, inst = {}, {}
    for iid, r in simreg.all_instances().items():
        if r.get("owner", {}).get("kind") == "adopted" and r.get("state") == "up" and not dry:
            ok = simreg.healthy_url(r["url"])
            simreg.heartbeat(iid, ok, "balancer probe" if ok else "balancer probe FAILED")
            r = simreg.read(iid) or r
        if not simreg.is_live(r, now):
            continue
        s = smp.get((r["host"], int(r["port"]))) or metrics_direct(r["url"])
        if s is None:
            continue
        loads[iid], inst[iid] = score(s), r
    return loads, inst


def agent_nodes() -> list[str]:
    return sorted({f.stem for f in (W / "gpumon").glob("node*.jsonl")})


def current(node: str, inst: dict[str, dict]) -> tuple[str | None, str]:
    """(instance id the node's next run would use, URL); instance id None if that URL is not a live instance."""
    f = Q / f"USER_BASE.{node}"
    url = f.read_text().strip() if f.exists() else ""
    if not url:
        host = node if any(r["host"] == node and r["port"] == 8000 for r in simreg.all_instances().values()) else DEFAULT.get(node)
        url = simreg.base_url(host, 8000) if host else ""
    for iid, r in inst.items():
        if r["url"].rstrip("/") == url.rstrip("/"):
            return iid, url
    return None, url


def log(msg: str):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as fh:
        fh.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg + "\n")


def set_route(node: str, r: dict) -> None:
    f = Q / f"USER_BASE.{node}"
    if r["host"] == node and int(r["port"]) == 8000:
        f.unlink(missing_ok=True)  # the node's default: its own replica on :8000
        return
    tmp = f.with_name(f".{f.name}.tmp{os.getpid()}")  # atomic replace: a worker never reads a half-written route
    tmp.write_text(r["url"] + "\n")
    os.replace(tmp, f)


def one_pass(dry: bool):
    now = time.time()
    load, inst = live_loads(now, dry)
    if not load:
        return
    hosts = {r["host"] for r in inst.values()}
    for n in sorted(agent_nodes(), key=lambda n: (n not in hosts, n)):  # nodes with a replica pick first (own replica)
        cur, cur_url = current(n, inst)
        invalid = cur is None
        if not invalid and now - last_change.get(n, 0) < HOLD:
            continue
        local = sorted((i for i in load if inst[i]["host"] == n), key=load.get)
        best = min(load, key=load.get)
        home = local[0] if local else None
        new = cur
        if invalid:
            new = home if home and load[home] <= BUSY else best
        elif load[cur] > BUSY and load[best] <= FREE and best != cur:
            new = home if home and load[home] <= FREE else best
        elif home and inst[cur]["host"] != n and load[home] <= FREE:
            new = home
        if new == cur:
            continue
        msg = (f"{n}: {cur or cur_url + ' (not live)'} ({load.get(cur, -1):.1f}) -> {new} ({load[new]:.1f}); "
               f"loads {json.dumps({k: round(v, 1) for k, v in sorted(load.items())})}")
        print(msg)
        load[new] += BUSY / 2  # expected extra load, so one pass does not herd every busy node onto the same replica
        if dry:
            continue
        set_route(n, inst[new])
        last_change[n] = now
        log(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    while True:
        try:
            one_pass(a.dry)
        except Exception as e:  # never die silently in the background
            log(f"pass failed: {e!r}")
        if a.once or a.dry:
            return
        time.sleep(PERIOD)


if __name__ == "__main__":
    main()
