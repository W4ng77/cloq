"""Key-order perturbation tasks (docs/insights/KEYORDER_PERTURB_PROTOCOL.md, ko-v1). Writes nothing without --write.

One fork task per Bank P directory of q8 gptq_w4_d1 (g1-g4, 20 blocks), mode keyorder, on the eligible states of the
frozen manifest manifests/fork/keyorder_v1.json. Roles (kind, model, gpus, q_ckpt / b_ckpt) are copied verbatim from the
Bank P task that produced the directory, and the servers must reproduce its canaries, checkpoint sha and effective
config (expect). Simulator: by default every task depends on the six takeover-window panel tasks (tw-v1 has priority and
the two live replicas until its deadline) and then uses node005 / node006 round robin, at most one key-order task per
replica; --user-base names another live replica instead (never node005:8000 / node006:8000 while tw-v1 runs).
--write refuses unless the protocol and the manifest are committed and unmodified (protocol §Deadline and freeze).
usage: python scripts/a6000/make_tasks_keyorder.py [--write] [--priority P] [--nodes n1,n2] [--user-base URL]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

ROOT, WORK = Path("/data/ziyangs/cloq"), Path("/data/ziyangs/cloq_work")
QD = WORK / "queue"
PROTO, MAN = "docs/insights/KEYORDER_PERTURB_PROTOCOL.md", "manifests/fork/keyorder_v1.json"
GROUPS = ("g1", "g2", "g3", "g4")
TW_TASKS = [f"tw_q8_{c}_{b}" for b in ("f01", "f02", "f03") for c in ("gptq_w4_d1", "spinquant_w4a4")]
TW_REPLICAS = ("http://node005:8000/v1", "http://node006:8000/v1")
PRIORITY, CONCURRENCY, NOOP = -15, 6, 0.1  # -15 runs after tw-v1 (-21): lower value = earlier in noderunner
KEEP = ("kind", "model", "gpus", "gpus_per_role", "q_ckpt", "b_ckpt", "B", "Q")


def committed(path: str) -> bool:
    ok = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", path], capture_output=True).returncode == 0
    clean = subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "HEAD", "--", path]).returncode == 0
    return ok and clean


def task(g: str, m_sha: str, deps: list, node, prio: int, user_base: str) -> dict:
    tid = f"fork_dev_q8_gptq_w4_d1_{g}"
    tpl = json.loads((QD / "done" / f"{tid}.json").read_text())
    srv = json.loads((WORK / "logs/tasks" / f"{tid}.servers.json").read_text())
    expect = {r: {k: srv[r].get(k) for k in ("canary", "ckpt_sha256", "effective_config_sha")} for r in ("B", "Q")}
    group = f"analysis/fork/dev/q8_gptq_w4_d1/{g}"
    assert tpl["fork"]["out"] == group, (tpl["fork"]["out"], group)
    fork = {"mode": "keyorder", "manifest": MAN, "manifest_sha256": m_sha, "group": group, "noop_frac": NOOP, "shadow_check": True,
            "resume": True, "concurrency": CONCURRENCY, "expect": expect, "out": f"analysis/fork/keyorder/q8_gptq_w4_d1/{g}"}
    return {**{k: tpl[k] for k in KEEP if k in tpl}, "id": f"ko_q8_gptq_w4_d1_{g}", "node": node, "priority": prio, "deps": deps,
            "fork": fork, "user_base": user_base, "autopilot_retry": "no (ko-v1: a failed task is left for a human)",
            "note": "ko-v1 key-order arm KQ + 10% QQ no-op on eligible Bank P states (KEYORDER_PERTURB_PROTOCOL.md)",
            "created": time.strftime("%F %T")}


def put(t: dict, write: bool) -> None:
    if any((QD / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed", "deferred")):
        print(f"exists, skipped: {t['id']}")
        return
    print(t["id"], t["fork"]["group"], "deps", t["deps"], "node", t["node"], "user_base", t["user_base"], "prio", t["priority"])
    if write:
        p = QD / "todo" / f"{t['id']}.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(t, indent=1))
        tmp.rename(p)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--priority", type=int, default=PRIORITY)
    ap.add_argument("--nodes", default="", help="comma list, round robin (empty: unpinned)")
    ap.add_argument("--user-base", default="", help="a live simulator replica other than the tw-v1 ones; then no tw-v1 deps")
    ap.add_argument("--manifest", default=MAN, help="dry run only: another manifest path (--write needs the frozen one)")
    a = ap.parse_args()
    mp = ROOT / a.manifest
    man = json.loads(mp.read_text())
    m_sha = hashlib.sha256(mp.read_bytes()).hexdigest()
    if a.write and a.manifest != MAN:
        raise SystemExit(f"--write needs --manifest {MAN}")
    el = [r for r in man["rows"] if r["eligible"]]
    print(f"manifest {a.manifest} sha {m_sha}: {man['n_eligible']} eligible of {man['n_states']} states", {g: sum(r["group"].endswith(g) for r in el) for g in GROUPS})
    if a.priority <= -21:
        raise SystemExit("priority must be lower than tw-v1's (-21): use a value > -21")
    if a.user_base:
        import sys
        sys.path.insert(0, str(ROOT / "scripts/a6000"))
        import simreg
        r = simreg.by_url(a.user_base)
        if a.user_base in TW_REPLICAS or r is None or not simreg.is_live(r):
            raise SystemExit(f"{a.user_base}: not a live replica outside tw-v1's {TW_REPLICAS}")
    if a.write and not (committed(PROTO) and committed(MAN)):
        raise SystemExit(f"--write needs {PROTO} and {MAN} committed and unmodified (the lead commits the protocol first)")
    nodes = [n for n in a.nodes.split(",") if n] or [None]
    ids: list[str] = []
    for i, g in enumerate(GROUPS):
        if a.user_base:
            deps, ub = [], a.user_base
            deps += [ids[-1]] if ids else []  # one replica: one key-order task at a time
        else:
            deps, ub = list(TW_TASKS), TW_REPLICAS[i % 2]
            deps += [ids[-2]] if len(ids) >= 2 else []  # at most one key-order task per replica
        t = task(g, m_sha, deps, nodes[i % len(nodes)], a.priority, ub)
        put(t, a.write)
        ids.append(t["id"])


if __name__ == "__main__":
    main()
