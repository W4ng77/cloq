"""User-simulator instance registry (W34-infra; docs/insights/RESOURCE_PLAN.md).

One JSON file per simulator replica: /data/ziyangs/cloq_work/sims/<instance_id>.json, instance_id = <node>-<port>.
Written by the process that owns the replica (noderunner.py for its start-up replicas, worker.py for a `kind: sim`
task, `simreg.py adopt` for replicas started by runners older than the registry). Fields:
  instance_id, url (http://<node>:<port>/v1), host, port, gpus, model, served_name, hf_id, revision,
  canary (numerics canary hash; must equal analysis/determinism/canary_sim_<model>.json), noop (identical-request check
  against a reference replica), throughput (concurrent probe before going live), started, owner {kind, job, pid, task},
  state (starting | up | draining | stopped | dead), health {ok, checked, detail}.
Only `state == up` with a fresh, ok health record receives new routes. `draining` = no new routes; the replica stops
only when no lease (a live run_arm/fork_driver process started with its URL) refers to it any more, so running episodes
keep their endpoint until they finish.

Leases: /data/ziyangs/cloq_work/sims/leases/<key>.json {url, host, pid, run, started}; the worker refreshes the file's
mtime every ~10 s while the process runs and deletes it when the process ends. A lease older than LEASE_STALE is dead.

CLI (login node or any node):
  python scripts/a6000/simreg.py list
  python scripts/a6000/simreg.py adopt [--nodes node001,...] [--port 8000]   # register runner-started replicas (live canary)
  python scripts/a6000/simreg.py noop <url> <ref_url> [--n 4]                # identical requests -> identical answers?
  python scripts/a6000/simreg.py throughput <url> [--conc 16]
  python scripts/a6000/simreg.py leases [<url>]
  python scripts/a6000/simreg.py retire <instance_id>                       # SIMSTOP flag: drain, then stop (sim tasks)
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import socket
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
WORK = Path(os.environ.get("CLOQ_SIMREG_WORK", "/data/ziyangs/cloq_work"))  # override only for tests
SIMS = WORK / "sims"
LEASES = SIMS / "leases"
HEALTH_STALE = 180    # s: an owner heartbeat older than this is not healthy
LEASE_STALE = 600     # s: a lease not refreshed for this long belongs to a dead process
NODE = socket.gethostname().split(".")[0]

CANARY_TEXT = ("You are a careful assistant for an airline. Policy: verify identity before any change, never refund "
               "without a reservation id, and summarise the customer's request before acting. ") * 40
# Identical-request (no-op) probes: user-simulator-shaped prompts, greedy, exact logprobs compared.
NOOP_PROMPTS = [
    ("You are a customer talking to an airline agent. Your goal: change reservation ABC123 to Friday; you are Mia "
     "Li, born 1990-04-02. Reply with only your next message.", "Hello, how can I help you today?"),
    ("You are a retail customer. You want to return the blue kettle from order #W123 and get a refund to your gift "
     "card. Reply with only your next message.", "Hi! What can I do for you?"),
    ("You are a customer. You want to cancel order #W999 because you ordered it by mistake; do not accept store "
     "credit. Reply with only your next message.", "I can help with that. Could you give me your email address?"),
    ("You are a customer. You are unsure whether your checked bag allowance covers two bags on reservation XK4Q; ask "
     "about it and stop when answered. Reply with only your next message.", "Sure. May I have your user id?"),
]


def instance_id(host: str, port: int) -> str:
    return f"{host}-{port}"


def path_of(iid: str) -> Path:
    return SIMS / f"{iid}.json"


def _atomic_write(p: Path, rec: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(rec, indent=1))
    os.replace(tmp, p)


def read(iid: str) -> dict | None:
    try:
        return json.load(open(path_of(iid)))
    except Exception:
        return None


def all_instances() -> dict[str, dict]:
    out = {}
    for f in SIMS.glob("*.json"):
        try:
            r = json.load(open(f))
        except Exception:
            continue
        out[r.get("instance_id", f.stem)] = r
    return out


def write(rec: dict) -> None:
    _atomic_write(path_of(rec["instance_id"]), rec)


def update(iid: str, **fields) -> dict | None:
    """Read-modify-write of one instance file. Only the owner calls this (single writer per file)."""
    r = read(iid)
    if r is None:
        return None
    r.update(fields)
    write(r)
    return r


def heartbeat(iid: str, ok: bool, detail: str = "") -> None:
    update(iid, health={"ok": bool(ok), "checked": time.time(), "detail": detail})


def is_live(r: dict, now: float | None = None) -> bool:
    """Routable: state up and an ok health record younger than HEALTH_STALE."""
    now = now or time.time()
    h = r.get("health") or {}
    return r.get("state") == "up" and bool(h.get("ok")) and now - float(h.get("checked", 0)) <= HEALTH_STALE


def by_url(url: str) -> dict | None:
    u = url.strip().rstrip("/")
    for r in all_instances().values():
        if r.get("url", "").rstrip("/") == u:
            return r
    return None


def base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/v1"


# ---------------------------------------------------------------- probes
def _post(base: str, body: dict, timeout: float = 300) -> dict:
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def healthy_url(base: str, timeout: float = 5) -> bool:
    try:
        with urllib.request.urlopen(base.rstrip("/") + "/models", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def completion_hash(base: str, messages: list, name: str = "user", max_tokens: int = 48, extra: dict | None = None) -> str:
    """Hash of a greedy completion including token ids and exact top-5 logprobs (same recipe as worker.canary)."""
    body = {"model": name, "temperature": 0.0, "max_tokens": max_tokens, "seed": 0, "logprobs": True, "top_logprobs": 5,
            "messages": messages, "return_token_ids": True, **(extra or {})}
    c = _post(base, body)["choices"][0]
    lp = [(t["token"], t["logprob"], [(a["token"], a["logprob"]) for a in t["top_logprobs"]]) for t in c["logprobs"]["content"]]
    return hashlib.sha256(json.dumps([c.get("token_ids"), lp]).encode()).hexdigest()[:16]


def canary_url(base: str, name: str = "user", extra: dict | None = None) -> str:
    msgs = [{"role": "system", "content": CANARY_TEXT},
            {"role": "user", "content": "My reservation is ABC123; I want to change my flight to Friday."}]
    return completion_hash(base, msgs, name, 48, extra)


def reference_canary(model: str, role: str = "sim") -> str | None:
    p = ROOT / "analysis/determinism" / f"canary_{role}_{model}.json"
    return json.load(open(p))["hash"] if p.exists() else None


def noop_check(new: str, ref: str, n: int = 4, name: str = "user") -> dict:
    """Send identical requests to both replicas (sequential pairs, greedy, 64 tokens); all hashes must match."""
    rows = []
    for sys_p, agent_msg in NOOP_PROMPTS[:n]:
        msgs = [{"role": "system", "content": sys_p}, {"role": "user", "content": agent_msg}]
        a, b = completion_hash(new, msgs, name, 64), completion_hash(ref, msgs, name, 64)
        rows.append({"new": a, "ref": b, "same": a == b})
    return {"ref": ref, "n": len(rows), "identical": sum(r["same"] for r in rows), "ok": all(r["same"] for r in rows),
            "rows": rows, "checked": time.time()}


def throughput(base: str, conc: int = 16, max_tokens: int = 256, name: str = "user") -> dict:
    """Concurrent probe: `conc` simultaneous user-simulator-shaped requests; aggregate generated tok/s and latency."""
    def one(i):
        sys_p, agent_msg = NOOP_PROMPTS[i % len(NOOP_PROMPTS)]
        body = {"model": name, "temperature": 0.0, "max_tokens": max_tokens, "seed": i, "ignore_eos": True,
                "messages": [{"role": "system", "content": CANARY_TEXT + sys_p + f" (probe {i})"},
                             {"role": "user", "content": agent_msg}]}
        t = time.time()
        u = _post(base, body, timeout=600)["usage"]
        return time.time() - t, u["completion_tokens"], u["prompt_tokens"]
    t0 = time.time()
    with cf.ThreadPoolExecutor(conc) as ex:
        res = list(ex.map(one, range(conc)))
    wall = time.time() - t0
    lat = sorted(r[0] for r in res)
    return {"conc": conc, "max_tokens": max_tokens, "wall_s": round(wall, 2), "gen_tok_s": round(sum(r[1] for r in res) / wall, 1),
            "prompt_tokens": sum(r[2] for r in res), "p50_s": round(lat[len(lat) // 2], 2), "max_s": round(lat[-1], 2),
            "checked": time.time()}


# ---------------------------------------------------------------- leases
def lease_open(key: str, url: str, run: str) -> Path:
    p = LEASES / f"{key}.json"
    _atomic_write(p, {"url": url, "host": NODE, "pid": os.getpid(), "run": run, "started": time.time()})
    return p


def lease_touch(p: Path) -> None:
    try:
        os.utime(p)
    except FileNotFoundError:
        pass


def lease_close(p: Path) -> None:
    try:
        p.unlink()
    except FileNotFoundError:
        pass


def active_leases(url: str | None = None) -> list[dict]:
    now, out = time.time(), []
    for f in LEASES.glob("*.json"):
        try:
            age = now - f.stat().st_mtime
            r = json.load(open(f))
        except Exception:
            continue
        if age > LEASE_STALE:
            continue
        if url is None or r.get("url", "").rstrip("/") == url.rstrip("/"):
            out.append({**r, "key": f.stem, "age_s": round(age)})
    return out


# ---------------------------------------------------------------- CLI
def cmd_adopt(nodes: list[str], port: int, model: str) -> None:
    """Register replicas started by pre-registry runners. Live canary (must equal the fixed reference)."""
    want = reference_canary(model)
    for n in nodes:
        base = base_url(n, port)
        iid = instance_id(n, port)
        if not healthy_url(base):
            print(f"{iid}: not answering, skipped")
            continue
        old = read(iid)
        if old and old.get("owner", {}).get("kind") != "adopted" and old.get("state") in ("starting", "up", "draining"):
            print(f"{iid}: already registered by {old['owner']}, skipped")
            continue
        h = canary_url(base)
        rec = {"instance_id": iid, "url": base, "host": n, "port": port, "gpus": None, "model": model, "served_name": "user",
               "canary": h, "canary_ref": want, "canary_ok": h == want, "started": None,
               "owner": {"kind": "adopted", "by": "simreg.py adopt", "at": time.time()},
               "state": "up" if h == want else "dead",
               "health": {"ok": h == want, "checked": time.time(), "detail": "adopt: canary " + ("ok" if h == want else "MISMATCH")}}
        write(rec)
        print(f"{iid}: canary {h} ({'ok' if h == want else 'MISMATCH vs ' + str(want)}) -> {rec['state']}")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("list")
    a = sp.add_parser("adopt"); a.add_argument("--nodes", default="node001,node004,node005,node006,node007")
    a.add_argument("--port", type=int, default=8000); a.add_argument("--model", default="q30a3")
    b = sp.add_parser("noop"); b.add_argument("url"); b.add_argument("ref"); b.add_argument("--n", type=int, default=4)
    c = sp.add_parser("throughput"); c.add_argument("url"); c.add_argument("--conc", type=int, default=16)
    c.add_argument("--max-tokens", type=int, default=256)
    d = sp.add_parser("leases"); d.add_argument("url", nargs="?")
    e = sp.add_parser("retire"); e.add_argument("iid")
    a = ap.parse_args()
    if a.cmd == "list":
        now = time.time()
        for iid, r in sorted(all_instances().items()):
            h = r.get("health") or {}
            print(f"{iid:14s} {r.get('state','?'):9s} live={is_live(r, now)!s:5s} gpus={r.get('gpus')} canary={r.get('canary')} "
                  f"owner={r.get('owner', {}).get('kind')} health={'ok' if h.get('ok') else 'BAD'} {now - float(h.get('checked', 0)):.0f}s ago "
                  f"leases={len(active_leases(r.get('url')))}")
    elif a.cmd == "adopt":
        cmd_adopt([x for x in a.nodes.split(",") if x], a.port, a.model)
    elif a.cmd == "noop":
        print(json.dumps(noop_check(a.url, a.ref, a.n), indent=1))
    elif a.cmd == "throughput":
        print(json.dumps(throughput(a.url, a.conc, a.max_tokens), indent=1))
    elif a.cmd == "leases":
        for l in active_leases(a.url):
            print(json.dumps(l))
    elif a.cmd == "retire":
        (WORK / "queue" / f"SIMSTOP.{a.iid}").write_text(time.strftime("%F %T") + "\n")
        print(f"flag written: queue/SIMSTOP.{a.iid} (only `kind: sim` task replicas honour it)")


if __name__ == "__main__":
    sys.exit(main())
