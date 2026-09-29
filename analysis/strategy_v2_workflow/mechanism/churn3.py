"""Neutral task-difficulty split: number of required actions / required writes in the task spec (independent of any run)."""
import pickle, sys, numpy as np, pandas as pd
from pathlib import Path
OUT = Path(__file__).resolve().parent; ROOT = Path("/home/xinyu/cloq"); sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(OUT))
from cloq.metrics import read_jsonl
from build import WRITE
d = pickle.load(open(OUT / "tables.pkl", "rb")); C, CK = d["C"], d["CKPTS"]
M = C.pivot_table(index=["domain", "task_id"], columns="ck", values="q_success").astype(float)[CK]
bf = C.groupby(["domain", "task_id"]).bf16_success.first().astype(float).loc[M.index]
Hf = C.groupby(["domain", "task_id"]).H_fp.first().loc[M.index]
spec = {}
for dom in ["retail", "airline"]:
    for t in read_jsonl(ROOT / "runs/bf16_v1" / dom / "trajectory.jsonl"):
        a = t["task"]["evaluation_criteria"]["actions"] or []
        spec[(dom, t["task_id"])] = (len(a), sum(x["name"] in WRITE for x in a))
na = np.array([spec[k][0] for k in M.index]); nw = np.array([spec[k][1] for k in M.index])
print("Spearman H_fp vs n_req_actions: %.3f; vs n_req_writes: %.3f" % (pd.Series(Hf.values).corr(pd.Series(na), method="spearman"), pd.Series(Hf.values).corr(pd.Series(nw), method="spearman")))
for lab, mask in [("n_req_actions>=6", na >= 6), ("n_req_actions<6", na < 6), ("n_req_writes>=2", nw >= 2), ("n_req_writes<=1", nw <= 1)]:
    Mm, b = M.values[mask], bf.values[mask]
    lost = ((b[:, None] == 1) & (Mm == 0)).sum(); gained = ((b[:, None] == 0) & (Mm == 1)).sum()
    print(f"{lab}: tasks={mask.sum()} BF16 {b.mean():.3f} (count {int(b.sum())}) Q mean {Mm.mean():.3f}; Q counts {sorted(Mm.sum(0).astype(int).tolist())}; lost {lost}/{(b==1).sum()*18} ({lost/max(1,(b==1).sum()*18):.3f}) gained {gained}/{(b==0).sum()*18} ({gained/max(1,(b==0).sum()*18):.3f})")
rng = np.random.default_rng(4)
for lab, mask in [("n_req_writes>=2", nw >= 2), ("n_req_writes<=1", nw <= 1)]:
    dd = bf.values[mask] - M.values[mask].mean(1)
    bs = [dd[rng.integers(0, len(dd), len(dd))].mean() for _ in range(10000)]
    print(f"BF16 - mean Q, {lab}: {dd.mean():.3f} task-bootstrap 95% CI [{np.percentile(bs,2.5):.3f},{np.percentile(bs,97.5):.3f}] n={mask.sum()}")
# difference-in-differences: (BF16-Q | >=2 writes) - (BF16-Q | <=1 write)
d1 = bf.values - M.values.mean(1); g = nw >= 2; bs = []
for _ in range(10000):
    a = rng.choice(np.where(g)[0], g.sum()); b = rng.choice(np.where(~g)[0], (~g).sum()); bs.append(d1[a].mean() - d1[b].mean())
print("interaction (gap in >=2-write tasks minus gap in <=1-write tasks): %.3f CI [%.3f,%.3f]" % (d1[g].mean() - d1[~g].mean(), *np.percentile(bs, [2.5, 97.5])))
