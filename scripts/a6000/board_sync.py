"""Snapshot cluster + matrix state into JSON documents for the CLOQ Paper Console artifact.

Writes <out>/cluster.json: the whole live state (gpus, nodes, matrix, queue note) as one document for
status/cluster in the artifact database.

usage: python scripts/a6000/board_sync.py [--out /data/ziyangs/cloq_work/board]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
WORK = Path("/data/ziyangs/cloq_work")
NODES = [f"node00{i}" for i in range(1, 10)]
MODEL_ORDER = {"q4": 1, "q8": 2, "l8": 3, "m24": 3, "q14": 4, "q30a3": 5, "q32": 6}
HF = {"q4": "Qwen/Qwen3-4B-Instruct-2507", "q8": "Qwen/Qwen3-8B", "q14": "Qwen/Qwen3-14B",
      "q30a3": "Qwen/Qwen3-30B-A3B-Instruct-2507 (MoE, TP=2)", "q32": "Qwen/Qwen3-32B (TP=2)",
      "l8": "meta-llama/Llama-3.1-8B-Instruct (gated: access requested)", "m24": "Mistral-Small-3.2-24B"}


def iso(t: float) -> str:
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat()


def cell_of(run_id: str) -> tuple[str, str] | None:
    m = re.match(r"a6k2_([a-z0-9]+)_(.+)$", run_id)  # current matrix only; a6000_* = legacy numerics flavour (W3)
    if not m or "_det_" in run_id:
        return None
    model, rest = m.groups()
    if rest == "bf16_cal":
        return model, "bf16_cal"
    if rest == "bf16":
        return model, "bf16"
    if rest.startswith("null_n"):
        return model, "null_nonce"
    g = re.match(r"gauss([0-9.]+)_s\d+$", rest)
    if g:
        return model, f"gauss_{g.group(1)}"
    for c in ("rtn_w8", "rtn_w4", "rtn_w3", "gptq_w4_d1", "gptq_w4_d2", "awq_w4", "gptq_w3"):
        if rest.startswith(c + "_"):
            return model, c
    return None


def run_state(run_id: str) -> tuple[str, float | None, int]:
    """(state, pooled db_match, n_tasks) over retail + airline."""
    tot, hit, states = 0, 0.0, []
    for d in ("retail", "airline"):
        sp = ROOT / "runs" / run_id / d / "status.json"
        st = json.load(open(sp)).get("status") if sp.exists() else None
        states.append(st)
        mp = ROOT / "runs" / run_id / d / "metrics.json"
        if st == "completed" and mp.exists():
            m = json.load(open(mp))
            if m.get("db_match_rate") is not None:
                tot += m["n_tasks"]
                hit += m["db_match_rate"] * m["n_tasks"]
    if all(s == "completed" for s in states):
        return "done", (hit / tot if tot else None), tot
    if any(s for s in states):
        return "running", None, tot
    return "todo", None, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(WORK / "board"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.json"):
        f.unlink()
    docs = {}

    # GPUs: per-node documents with 8 slots
    slots = defaultdict(dict)
    for p in (WORK / "status").glob("node*-g*.json"):
        node, g = p.stem.split("-g")
        try:
            s = json.load(open(p))
        except Exception:
            continue
        slots[node][g] = {"state": s.get("state"), "task": s.get("task"), "model": s.get("model"),
                          "detail": s.get("detail"), "progress": s.get("progress"),
                          "updated": iso(s["updated"]) if s.get("updated") else None}
    # which of my jobs are alive where
    mine = {}
    try:
        q = subprocess.check_output(["squeue", "-u", "ziyangs", "-h", "-o", "%i|%T|%N|%M"], text=True)
        for line in q.strip().splitlines():
            jid, st, node, el = line.split("|")
            if node:
                mine[node] = f"{jid} {st.lower()} {el}"
    except Exception:
        pass
    # cluster occupancy (other users)
    nodes = {}
    try:
        s = subprocess.check_output(["sinfo", "-N", "-h", "-O", "NodeList:12,CPUsState:20,GresUsed:40"], text=True)
        for line in s.strip().splitlines():
            parts = line.split()
            node, cpus, gres = parts[0], parts[1], parts[2] if len(parts) > 2 else ""
            alloc = int(cpus.split("/")[0])
            used = set()
            m = re.search(r"IDX:([0-9,\-]+)", gres)
            if m:
                for rng in m.group(1).split(","):
                    lo, _, hi = rng.partition("-")
                    used.update(str(i) for i in range(int(lo), int(hi or lo) + 1))
            nodes[node] = {"cpus_alloc": alloc, "used_idx": used}
    except Exception:
        pass
    for n in NODES:
        info = nodes.get(n, {"cpus_alloc": None, "used_idx": set()})
        live = n in mine and "running" in mine[n]
        myslots = {g: v for g, v in slots.get(n, {}).items()} if live else {}
        other = sorted(int(i) for i in info["used_idx"] if i not in myslots or not live)
        if live:
            other = sorted(int(i) for i in info["used_idx"] if i not in myslots)
        docs[f"gpus__{n}"] = {"slots": myslots}
        nd = {"cpus_alloc": info["cpus_alloc"], "other_gpus": other if not live else []}
        if n in mine:
            nd["job"] = mine[n]
        if n == "node009":
            nd["job"] = (nd.get("job", "") + " · reported bad GPUs, excluded").strip(" ·")
        docs[f"nodes__{n}"] = nd

    # matrix from task files + run statuses
    cells = defaultdict(lambda: defaultdict(lambda: {"done": 0, "total": 0, "scores": [], "running": 0}))
    queue_state = {}
    for d in ("todo", "running", "done", "failed"):
        for p in (WORK / "queue" / d).glob("*.json"):
            try:
                t = json.load(open(p))
            except Exception:
                continue
            queue_state[t["id"]] = d
            for r in t.get("runs", []):
                c = cell_of(r["run_id"])
                if not c:
                    continue
                st, score, _ = run_state(r["run_id"])
                x = cells[c[0]][c[1]]
                x["total"] += 1
                if st == "done":
                    x["done"] += 1
                    if score is not None:
                        x["scores"].append(score)
                elif st == "running" or d == "running":
                    x["running"] += 1
                if d == "failed":
                    x["failed"] = True
    for model, cs in cells.items():
        out_cells = {}
        for c, x in cs.items():
            status = "failed" if x.get("failed") else "running" if x["running"] else None
            cell = {"done": x["done"], "total": x["total"]}
            if status:
                cell["status"] = status
            if x["scores"]:
                cell["score"] = round(sum(x["scores"]) / len(x["scores"]), 4)
            out_cells[c] = cell
        docs[f"matrix__{model}"] = {"order": MODEL_ORDER.get(model, 9), "hf_id": HF.get(model, model), "cells": out_cells}

    n_busy = sum(1 for n in slots for g in slots[n].values() if g.get("state") not in (None, "idle"))
    counts = {d: sum(1 for v in queue_state.values() if v == d) for d in ("todo", "running", "done", "failed")}
    docs["status__cluster"] = {"updated": iso(dt.datetime.now().timestamp()),
                               "note": f"queue: {counts['running']} running · {counts['todo']} waiting · {counts['done']} done · {counts['failed']} failed"}
    # one document carries all live state, so each sync is a single pinned write
    live = dict(docs["status__cluster"])
    live["gpus"] = {k.split("__")[1]: v["slots"] for k, v in docs.items() if k.startswith("gpus__")}
    live["nodes"] = {k.split("__")[1]: v for k, v in docs.items() if k.startswith("nodes__")}
    live["matrix"] = {k.split("__")[1]: v for k, v in docs.items() if k.startswith("matrix__")}
    (out / "cluster.json").write_text(json.dumps(live))
    print(json.dumps({"busy_gpus": n_busy, **counts}))


if __name__ == "__main__":
    main()
