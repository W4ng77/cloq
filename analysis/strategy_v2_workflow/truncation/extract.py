"""Extract compact per-decision context records and per-task metrics/divergence for
bf16_v1 + 18 v1 quantized checkpoints (+ v0 single-draw runs for reference). Read-only on /home/xinyu/cloq."""
import json, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, "/home/xinyu/cloq")
from cloq.metrics import load_decisions

R = Path("/home/xinyu/cloq/runs")
OUT = Path(__file__).parent
ARMS = ["static", "fp_traj", "cloq_all", "cloq_novel", "cloq_matched_random", "cloq_matched_alt"]
RUNS = ["bf16_v1"] + [f"{a}_{c}_dev" for a in ARMS for c in ("c1", "c2", "c3")]
RUNS_V0 = ["static_eval", "fp_traj_eval", "cloq_eval", "rtn_eval", "bf16_rep_eval"]
split = json.load(open("/home/xinyu/cloq/manifests/task_split_v0.json"))

dec_rows, task_rows, div_rows = [], [], []
for run in RUNS + RUNS_V0:
    for dom in ("retail", "airline"):
        rd = R / run / dom
        ev = set(split["domains"][dom]["evaluation"])
        decs = load_decisions(rd)
        for d in decs:
            if d["task_id"] not in ev:
                continue
            c = d.get("context") or {}
            dec_rows.append(dict(run=run, domain=dom, task_id=d["task_id"], idx=d["decision_idx"],
                                 truncated=bool(c.get("truncated")), pre=c.get("pre_truncation_tokens"),
                                 post=c.get("post_truncation_tokens"), dropped=c.get("n_units_dropped"),
                                 units_total=c.get("n_units_total"), n_prompt=d.get("n_prompt_tokens"),
                                 prompt_sha=d.get("prompt_sha256"), is_tool=bool(d.get("tool_calls"))))
        m = json.load(open(rd / "metrics.json"))
        for t in m["per_task"]:
            if t["task_id"] in ev:
                task_rows.append(dict(run=run, domain=dom, **{k: t.get(k) for k in (
                    "task_id", "db_match", "termination_reason", "n_decisions", "n_tool_calls", "n_tool_errors",
                    "n_repeated_tool_calls", "n_truncated_contexts", "premature", "max_prompt_tokens")}))
        dv = rd / "divergence.json"
        if dv.exists():
            for t in json.load(open(dv))["per_task"]:
                div_rows.append(dict(run=run, domain=dom, **{k: t.get(k) for k in (
                    "task_id", "H_fp", "H_q", "t_star", "t_tool", "t_context", "t_render", "tool_diverged",
                    "fp_db_match", "q_db_match")}))
        print(run, dom, len(decs), flush=True)

pd.DataFrame(dec_rows).to_parquet(OUT / "decisions.parquet") if False else pd.DataFrame(dec_rows).to_csv(OUT / "decisions.csv", index=False)
pd.DataFrame(task_rows).to_csv(OUT / "tasks.csv", index=False)
pd.DataFrame(div_rows).to_csv(OUT / "divergence.csv", index=False)
hz = []
for dom in ("retail", "airline"):
    for tid in split["domains"][dom]["evaluation"]:
        hz.append(dict(domain=dom, task_id=tid, horizon=split["domains"][dom]["horizon_by_task"][tid],
                       quartile=split["domains"][dom]["quartile_by_task"][tid]))
pd.DataFrame(hz).to_csv(OUT / "horizon.csv", index=False)
