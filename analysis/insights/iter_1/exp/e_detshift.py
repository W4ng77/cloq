"""Where does a BF16-vs-BF16 cross-server difference show up? (read-only over runs/)

For two runs of the same BF16 config, take every decision whose prompt token ids are byte-identical and compare
the per-token margins on the common completion prefix. Intermittent scheduling effects (prefix-cache hit or
miss, chunked-prefill boundaries) would shift only some decisions; a server-wide numerics difference (a different
compiled kernel) shifts nearly every decision from the first generated token on.
usage: python e_detshift.py a6000_det_q4_a a6000_det_q4_b [more pairs as A,B ...]  -> out/detshift.json
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

RUNS = Path("/data/ziyangs/cloq/runs")
HERE = Path(__file__).parent


def load(r):
    out = {}
    for d in ("retail", "airline"):
        p = RUNS / r / d / "decisions.jsonl"
        if p.exists():
            for line in open(p):
                x = json.loads(line)
                out[(d, x["task_id"], x["decision_idx"])] = x
    return out


def compare(ra, rb):
    A, B = load(ra), load(rb)
    rows = []
    for k in sorted(set(A) & set(B)):
        a, b = A[k], B[k]
        if a["prompt_token_ids"] != b["prompt_token_ids"]:
            continue
        ca, cb = a["completion_token_ids"], b["completion_token_ids"]
        n = 0
        while n < min(len(ca), len(cb)) and ca[n] == cb[n]:
            n += 1
        f = lambda v: np.array([np.nan if x is None else x for x in v[:n]], dtype=float)
        d = np.nan_to_num(np.abs(f(a["token_margins"]) - f(b["token_margins"])), nan=0.0)
        rows.append({"idx": k[2], "n_common": n, "same_completion": ca == cb,
                     "first_token_differs": n == 0, "any_shift": bool((d > 0).any()) or n == 0,
                     "first_token_shift": bool(d[0] > 0) if n else None,
                     "frac_tokens_shifted": float((d > 0).mean()) if n else None})
    by = defaultdict(list)
    for r in rows:
        by[r["idx"]].append(r["any_shift"])
    return {"pair": [ra, rb], "identical_prompt_decisions": len(rows),
            "identical_completions": sum(r["same_completion"] for r in rows),
            "decisions_with_any_shift_or_first_token_flip": sum(r["any_shift"] for r in rows),
            "first_generated_token_shifted_or_flipped": sum(bool(r["first_token_shift"]) or r["first_token_differs"] for r in rows),
            "median_frac_tokens_shifted_in_shifted_decisions":
                float(np.median([r["frac_tokens_shifted"] for r in rows if r["any_shift"] and r["frac_tokens_shifted"] is not None]))
                if any(r["any_shift"] for r in rows) else 0.0,
            "frac_decisions_shifted_by_decision_idx": {i: round(float(np.mean(v)), 3) for i, v in sorted(by.items())}}


pairs = [tuple(p.split(",")) for p in sys.argv[1:]] or [("a6000_det_q4_a", "a6000_det_q4_b"),
                                                        ("a6000_det_q4_b", "a6000_q4_bf16"),
                                                        ("a6000_det_q30a3_a", "a6000_det_q30a3_b")]
res = [compare(a, b) for a, b in pairs]
(HERE / "out").mkdir(exist_ok=True)
(HERE / "out/detshift.json").write_text(json.dumps(res, indent=1))
for r in res:
    print({k: v for k, v in r.items() if k != "frac_decisions_shifted_by_decision_idx"})
