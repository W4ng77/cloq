"""Deterministic re-run check for the external-environment adapters: two runs of the same config must produce
identical trajectories (per item: every decision's prompt token ids, completion token ids, parsed actions and
environment observations, and the evaluator verdict). Tool-call ids (random per server response) are ignored;
they are not rendered into the Qwen3/hermes prompt, which the prompt-id equality confirms.

usage: python3 scripts/ext/compare_runs.py runs/<run_a>/<domain> runs/<run_b>/<domain> [--out file.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load(d: Path):
    decs: dict[str, list] = {}
    for l in (d / "decisions.jsonl").read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            decs.setdefault(r["task_id"], []).append(r)
    trs = {json.loads(l)["task_id"]: json.loads(l) for l in (d / "trajectory.jsonl").read_text().splitlines() if l.strip()}
    return decs, trs


def key(r: dict):
    return (r["prompt_token_ids"], r["completion_token_ids"], r.get("parsed_actions"), r.get("observations"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--out")
    a = ap.parse_args()
    da, ta = load(Path(a.a))
    db, tb = load(Path(a.b))
    items = sorted(set(ta) | set(tb))
    res = {}
    for i in items:
        xa = sorted(da.get(i, []), key=lambda r: r["decision_idx"])
        xb = sorted(db.get(i, []), key=lambda r: r["decision_idx"])
        first = next((k for k, (p, q) in enumerate(zip(xa, xb)) if key(p) != key(q)), None)
        same = len(xa) == len(xb) and first is None and i in ta and i in tb and ta[i]["success"] == tb[i]["success"]
        res[i] = {"identical": same, "n_decisions": [len(xa), len(xb)], "first_diff_decision": first,
                  "success": [ta.get(i, {}).get("success"), tb.get(i, {}).get("success")],
                  "hash": hashlib.sha256(json.dumps([key(r) for r in xa]).encode()).hexdigest()[:16]}
    out = {"a": a.a, "b": a.b, "n_items": len(items), "n_identical": sum(v["identical"] for v in res.values()),
           "all_identical": all(v["identical"] for v in res.values()), "items": res}
    print(json.dumps({k: v for k, v in out.items() if k != "items"}))
    for i, v in res.items():
        if not v["identical"]:
            print("DIFF", i, v)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
