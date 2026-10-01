"""Token-scoring tasks for Bank U states (W88): worker kind "fork" with fork.driver = "score" (scripts/a6000/score_driver.py).

One task per model x cell x block, reading analysis/fork/bank_u/<m>_<cell>/<blk>/bank_rows.jsonl and writing
analysis/fork/token_scores/<m>_<cell>/<blk>/. B = BF16, Q = the cell's exact serving config (make_tasks_bank_u.qrole:
GPTQ/AWQ-W4 c1 rebuilt by the same deterministic quantizer, KV8 = BF16 + the CLOQ_KVQ_BITS=8 hook). Single prefill passes
(prompt_logprobs), so minutes per task. q4 on 1 GPU (B+Q, GPU_UTIL 0.44), q8 on 2 GPUs; no node pins; priority -15.
A block whose bank task has not finished gets a dependency on it (bank_u_<m>_<cell>_<blk>).

  --dry              one 5-state dry-run task on q4 AWQ-W4 f01 (U1 flip, U2B flip, U2Q differing, U1 exact, U2B differing)
  --blocks f01 ...   the scoring tasks
usage: python scripts/a6000/make_tasks_score.py (--dry | --blocks f01 [f02 f03]) [--write]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
Q = Path("/data/ziyangs/cloq_work/queue")
sys.path.insert(0, str(ROOT / "scripts/a6000"))
from make_tasks_bank_u import qrole  # noqa: E402

CELLS = ("gptq_w4_d1", "awq_w4", "kvq_int8")


def task(m, c, blk, tid, out, extra=None, deps=()):
    spec = {"driver": "score", "mode": "score_states", "model": m, "cell": c, "blocks": [blk],
            "bank_out": f"analysis/fork/bank_u/{m}_{c}/{blk}", "out": out, "concurrency": 4, **(extra or {})}
    return {"id": tid, "kind": "fork", "model": m, "gpus": 1 if m == "q4" else 2, **({"gpu_util": 0.44} if m == "q4" else {}),
            "priority": -15, "deps": list(deps), "B": {"ckpt": {"kind": "bf16"}}, "Q": qrole(m, c), "fork": spec,
            "note": "W88 token-level scoring of Bank U states (make_tasks_score.py; scripts/a6000/score_driver.py)"}


def dry_keys() -> list[str]:
    rows = [json.loads(x) for x in open(ROOT / "analysis/fork/bank_u/q4_awq_w4/f01/bank_rows.jsonl")]
    rows.sort(key=lambda r: r["state_key"])
    flip = lambda r: r["Y"]["BQ"] != r["Y"]["QQ"]  # noqa: E731
    picks = [next(r for r in rows if r["sub"] == "U1" and flip(r)),
             next(r for r in rows if r["sub"] == "U2B" and flip(r)),
             next(r for r in rows if r["sub"] == "U2Q" and not r["exact_agreement"]),
             next(r for r in rows if r["sub"] == "U1" and r["exact_agreement"]),
             next(r for r in rows if r["sub"] == "U2B" and not r["exact_agreement"] and not flip(r))]
    return [r["state_key"] for r in picks]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--blocks", nargs="*", default=[])
    ap.add_argument("--models", nargs="*", default=["q4", "q8"])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    T = []
    if a.dry:
        T.append(task("q4", "awq_w4", "f01", "score_dry_q4_awq_w4_f01", "analysis/fork/token_scores/dry/q4_awq_w4/f01",
                      {"only_state_keys": dry_keys()}))
    for blk in a.blocks:
        for m in a.models:
            for c in CELLS:
                bank = ROOT / f"analysis/fork/bank_u/{m}_{c}/{blk}/bank_summary.json"
                deps = () if bank.exists() else (f"bank_u_{m}_{c}_{blk}",)
                T.append(task(m, c, blk, f"score_{m}_{c}_{blk}", f"analysis/fork/token_scores/{m}_{c}/{blk}", deps=deps))
    for t in T:
        print(t["id"], t["gpus"], t["deps"], t["fork"].get("only_state_keys", ""))
    if a.write:
        n = 0
        for t in T:
            if not any((Q / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed", "deferred")):
                json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)
                n += 1
        print("wrote", n)


if __name__ == "__main__":
    main()
