import pandas as pd, numpy as np
from pathlib import Path
O=Path(__file__).parent
T=pd.read_csv(O/"tasks.csv",dtype={"task_id":str}); H=pd.read_csv(O/"horizon.csv",dtype={"task_id":str})
T=T.merge(H); T["s"]=T.db_match.astype(float); T["long"]=T.horizon>11
bf=T[T.run=="bf16_v1"][["domain","task_id","s"]].rename(columns={"s":"sb"})
for r in ["rtn_eval","static_eval","fp_traj_eval","cloq_eval","bf16_rep_eval"]:
    x=T[T.run==r].merge(bf); x["g"]=x.sb-x.s
    gl=x[x.long].g.mean(); gs=x[~x.long].g.mean()
    print(f"{r:14s} SR {x.s.mean():.3f} long gap {gl:+.3f} short gap {gs:+.3f} amp {gl-gs:+.3f}  trunc-rate(dec) n/a")
D=pd.read_csv(O/"decisions.csv",dtype={"task_id":str})
print(D[D.run.isin(["rtn_eval","static_eval","fp_traj_eval","cloq_eval","bf16_rep_eval"])].groupby("run").truncated.mean().round(3))
