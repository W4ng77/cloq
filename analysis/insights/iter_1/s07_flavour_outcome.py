"""Outcome effect of the compiled-kernel numerics flavour alone (BF16 weights, canonical prompt, same tasks).

det_q4_a (node005, R0_BLOCK=2048 flavour) vs det_q4_b (node004, canonical 4096 flavour; bitwise = q4_bf16):
per-task db_match on the 20 determinism tasks, discordant pairs and exact McNemar p.
evidence for the flavour mechanism: docs/insights/iter_1_discussion.md#experiment-round-1 (D1-D5).
"""
import json
from scipy.stats import binomtest
from common import RUNS, dump

res = {}
for m in ("q4", "q30a3"):
    ys = {}
    for side in ("a", "b"):
        y = {}
        for dom in ("retail", "airline"):
            p = RUNS / f"a6000_det_{m}_{side}" / dom / "metrics.json"
            if p.exists():
                for t in json.load(open(p))["per_task"]:
                    y[(dom, str(t["task_id"]))] = int(bool(t["db_match"]) and not t.get("premature", False))
        ys[side] = y
    common = sorted(set(ys["a"]) & set(ys["b"]))
    if not common:
        continue
    a = [ys["a"][k] for k in common]; b = [ys["b"][k] for k in common]
    ab = sum(1 for x, y in zip(a, b) if x and not y); ba = sum(1 for x, y in zip(a, b) if y and not x)
    p = binomtest(ab, ab + ba, 0.5).pvalue if ab + ba else 1.0
    res[m] = {"n_tasks": len(common), "db_match_a": sum(a) / len(a), "db_match_b": sum(b) / len(b),
              "a_only": ab, "b_only": ba, "task_disagreement": (ab + ba) / len(common), "mcnemar_p": p}
    print(m, res[m])
dump("s07_flavour_outcome.json", res)
