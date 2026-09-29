"""Partial perturbation null (4080, stopped early): BF16 + system-prompt nonce vs canonical bf16_v1.
Completed: null_bf16_n1, null_bf16_n2 (retail+airline), null_bf16_n3 (retail only). 8k harness.
Reports success, per-task outcome flips, and tool-level divergence against the canonical BF16 run,
side by side with the same statistics for the 18 W4 GPTQ dev checkpoints."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import RUNS, ARMS, DRAWS, task_db_match
from cloq.divergence import load_decisions_by_task, analyze_task

DOMAINS = ["retail", "airline"]
canon = {d: task_db_match(RUNS / "bf16_v1" / d) for d in DOMAINS}

def completed(run, d):
    p = RUNS / run / d / "status.json"
    return p.exists() and json.load(open(p)).get("status") == "completed"

def stats(run, domains):
    succ, flips, n, div = 0, 0, 0, 0
    for d in domains:
        y = task_db_match(RUNS / run / d)
        ids = sorted(set(y) & set(canon[d]))
        fp = load_decisions_by_task("bf16_v1", d, set(ids))
        q = load_decisions_by_task(run, d, set(ids))
        for t in ids:
            n += 1; succ += y[t]; flips += y[t] != canon[d][t]
            a = analyze_task(fp.get(t, []), q.get(t, []))
            div += a.get("t_tool") is not None
    return {"n": n, "success": round(succ / n, 3), "outcome_flip": round(flips / n, 3), "tool_divergence": round(div / n, 3)}

out = {}
for run in ["null_bf16_n1", "null_bf16_n2", "null_bf16_n3"]:
    doms = [d for d in DOMAINS if completed(run, d)]
    if doms: out[run] = {"domains": doms, **stats(run, doms)}
for a in ARMS:
    for c in DRAWS:
        out[f"{a}_{c}_dev"] = {"domains": DOMAINS, **stats(f"{a}_{c}_dev", DOMAINS)}
Path(__file__).parent.joinpath("out").mkdir(exist_ok=True)
json.dump(out, open(Path(__file__).parent / "out" / "null_partial.json", "w"), indent=1)
for k, v in out.items(): print(k, v)
