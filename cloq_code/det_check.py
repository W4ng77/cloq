"""Compare two code-loop runs decision by decision (determinism check).

Identity is checked on the model-facing content only: prompt_token_ids, completion_token_ids, token_logprobs,
token_margins, feedback, public/hidden verdicts (run_id, trajectory_id and timings differ by construction).

usage: python -m cloq_code.det_check runs/<a>/code runs/<b>/code [--out file.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FIELDS = ["prompt_token_ids", "completion_token_ids", "token_logprobs", "token_margins", "feedback",
          "public_verdicts", "hidden_verdicts", "finish_reason"]


def load(d: Path) -> dict:
    out = {}
    for ln in open(d / "decisions.jsonl"):
        r = json.loads(ln)
        out[(r["task_id"], r["decision_idx"])] = r
    return out


def canon(r: dict) -> str:
    return json.dumps({k: r.get(k) for k in FIELDS}, sort_keys=True, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    A, B = load(Path(a.a)), load(Path(a.b))
    keys = sorted(set(A) | set(B))
    diff = [k for k in keys if k not in A or k not in B or canon(A[k]) != canon(B[k])]
    tasks = sorted({k[0] for k in keys})
    first_div = {}
    for k in diff:
        first_div[k[0]] = min(first_div.get(k[0], 10**9), k[1])
    ta = {json.loads(l)["task_id"]: json.loads(l) for l in open(Path(a.a) / "trajectory.jsonl")}
    tb = {json.loads(l)["task_id"]: json.loads(l) for l in open(Path(a.b) / "trajectory.jsonl")}
    ha = hashlib.sha256("".join(canon(A[k]) for k in sorted(A)).encode()).hexdigest()
    hb = hashlib.sha256("".join(canon(B[k]) for k in sorted(B)).encode()).hexdigest()
    res = {
        "run_a": a.a, "run_b": a.b, "n_decisions_a": len(A), "n_decisions_b": len(B), "n_tasks": len(tasks),
        "n_decisions_differ": len(diff), "n_tasks_diverged": len(first_div), "first_divergence": first_div,
        "outcome_mismatch": sorted(t for t in ta if t in tb and ta[t]["success"] != tb[t]["success"]),
        "hash_a": ha, "hash_b": hb, "identical": ha == hb and not diff,
    }
    print(json.dumps(res, indent=1))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
