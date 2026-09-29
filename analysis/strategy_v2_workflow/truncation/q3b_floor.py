import pandas as pd, numpy as np
from pathlib import Path
O=Path(__file__).parent; rng=np.random.default_rng(2)
X=pd.read_csv(O/"task_level.csv",dtype={"task_id":str})
X["hbin"]=pd.cut(X.horizon,[0,7,9,11,14,18,200])
print("gap by horizon bin (task-level means)")
print(X.groupby("hbin",observed=True).agg(n=("gap","size"),ft=("frac_trunc","mean"),bf16_sr=("fail_fp",lambda v:1-v.mean()),q_sr=("fail_q",lambda v:1-v.mean()),gap=("gap","mean")).round(3).to_string())
# retention: among BF16-success tasks, Q success rate (floor-free)
S=X[X.fail_fp==0].copy()
print("\nBF16-success tasks: n=%d (long %d)"%(len(S),S.long.sum()))
def bm(v):
    v=np.asarray(v); b=rng.choice(v,(10000,len(v))).mean(1); return f"{v.mean():.3f} [{np.percentile(b,2.5):.3f},{np.percentile(b,97.5):.3f}] n={len(v)}"
print(" Q success | BF16 success, short:", bm(1-S[~S.long].fail_q))
print(" Q success | BF16 success, long :", bm(1-S[S.long].fail_q))
for lab,g in [("long, BF16 never trunc",S[S.long&(S.frac_trunc==0)]),("long, BF16 trunc<=0.384",S[S.long&(S.frac_trunc>0)&(S.frac_trunc<=0.384)]),("long, BF16 trunc>0.384",S[S.long&(S.frac_trunc>0.384)]),
              ("short, BF16 never trunc",S[~S.long&(S.frac_trunc==0)]),("short, BF16 trunc",S[~S.long&(S.frac_trunc>0)])]:
    if len(g): print(f"  {lab:28s} Q success={bm(1-g.fail_q)}  horizon med {g.horizon.median()}")
# OLS on BF16-success subset: Q fail ~ horizon + ft
def ols(df,cols,y):
    A=np.column_stack([np.ones(len(df))]+[df[c].values.astype(float) for c in cols]); yv=df[y].values
    return np.linalg.lstsq(A,yv,rcond=None)[0]
S["h10"]=S.horizon/10
b=ols(S,["h10","frac_trunc"],"fail_q"); bs=np.array([ols(S.iloc[rng.integers(0,len(S),len(S))],["h10","frac_trunc"],"fail_q") for _ in range(5000)])
print("\nBF16-success subset: Q fail ~ h10 + ft: h10 %.3f [%.3f,%.3f], ft %.3f [%.3f,%.3f]"%(b[1],*np.percentile(bs[:,1],[2.5,97.5]),b[2],*np.percentile(bs[:,2],[2.5,97.5])))
print("corr(h, ft) in subset %.3f"%S[["horizon","frac_trunc"]].corr().iloc[0,1])
# BF16-failure tasks: Q succeeds? (reverse gap)
F=X[X.fail_fp==1]
print("\nBF16-failure tasks: Q success rate short %.3f (n=%d), long %.3f (n=%d)"%(1-F[~F.long].fail_q.mean(),(~F.long).sum(),1-F[F.long].fail_q.mean(),F.long.sum()))
