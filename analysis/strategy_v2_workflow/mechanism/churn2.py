"""Robustness: define 'long' without using BF16's own trajectory (median quantized horizon; # required actions)."""
import pickle, numpy as np, pandas as pd
from pathlib import Path
OUT = Path(__file__).resolve().parent
d = pickle.load(open(OUT / "tables.pkl", "rb")); C, CK = d["C"], d["CKPTS"]
T = pd.read_csv(OUT / "task_table.csv", dtype={"task_id": str})  # BF16-solved only; need all tasks -> recompute req actions from C? use H_q median
M = C.pivot_table(index=["domain", "task_id"], columns="ck", values="q_success").astype(float)[CK]
bf = C.groupby(["domain", "task_id"]).bf16_success.first().astype(float).loc[M.index]
Hq = C.groupby(["domain", "task_id"]).H_q.median().loc[M.index]
Hf = C.groupby(["domain", "task_id"]).H_fp.first().loc[M.index]
print("Spearman H_fp vs median H_q:", pd.Series(Hf.values).corr(pd.Series(Hq.values), method="spearman").round(3))
for thr in [11, 13]:
    mask = (Hq > thr).values
    Mm, b = M.values[mask], bf.values[mask]
    lost = ((b[:, None] == 1) & (Mm == 0)).sum(); gained = ((b[:, None] == 0) & (Mm == 1)).sum()
    print(f"long by median quantized horizon > {thr}: tasks={mask.sum()} BF16 {b.mean():.3f} (count {int(b.sum())}) Q mean {Mm.mean():.3f}, Q counts {sorted(Mm.sum(0).astype(int).tolist())}; lost {lost}/{(b==1).sum()*18} gained {gained}/{(b==0).sum()*18}")
    mask = ~mask; Mm, b = M.values[mask], bf.values[mask]
    print(f"   complement: tasks={mask.sum()} BF16 {b.mean():.3f} Q mean {Mm.mean():.3f}")
