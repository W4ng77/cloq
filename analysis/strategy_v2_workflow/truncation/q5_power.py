import pandas as pd, numpy as np
from pathlib import Path
O=Path(__file__).parent; rng=np.random.default_rng(5)
T=pd.read_csv(O/"tasks.csv",dtype={"task_id":str}); PT=pd.read_csv(O/"per_task_trunc.csv",dtype={"task_id":str})
T=T[T.run.str.endswith("_dev")|(T.run=="bf16_v1")].copy(); T["s"]=T.db_match.astype(float)
H=pd.read_csv(O/"horizon.csv",dtype={"task_id":str}); H["long"]=H.horizon>11
H["key"]=H.domain+":"+H.task_id; T["key"]=T.domain+":"+T.task_id
bf=T[T.run=="bf16_v1"].set_index("key").s.reindex(H.key).values
ck=sorted(r for r in T.run.unique() if r!="bf16_v1")
Q=np.array([T[T.run==r].set_index("key").s.reindex(H.key).values for r in ck])  # 18 x 85
lg=H.long.values
def amp(bfv,Qm,lgv):
    g=bfv[None,:]-Qm  # K x N
    gm=g.mean(0)
    return gm[lgv].mean()-gm[~lgv].mean(), gm[lgv].mean()
A8,G8=amp(bf,Q,lg); print(f"observed 8k: amplification {A8:.3f}, long gap {G8:.3f}, n_long={lg.sum()}, n_short={(~lg).sum()}, K=18")
# two-way bootstrap (tasks within long/short strata, checkpoints) for SE with K checkpoints
res={}
for K in (3,6,9,18):
    As=[];Gs=[]
    for b in range(4000):
        il=rng.choice(np.where(lg)[0],lg.sum()); is_=rng.choice(np.where(~lg)[0],(~lg).sum()); idx=np.r_[il,is_]
        kk=rng.choice(len(ck),K)
        a,g=amp(bf[idx],Q[kk][:,idx],lg[idx]); As.append(a); Gs.append(g)
    As=np.array(As);Gs=np.array(Gs); res[K]=(As.std(),Gs.std())
    print(f"K={K:2d}: SE(amplification)={As.std():.3f}  SE(long gap)={Gs.std():.3f}  95%CI amp [{np.percentile(As,2.5):.3f},{np.percentile(As,97.5):.3f}]  P(amp<=0)={np.mean(As<=0):.3f}")
# checkpoint-only SE (tasks fixed): relevant for a paired within-task comparison
for K in (3,6,9):
    As=[amp(bf,Q[rng.choice(len(ck),K)],lg)[0] for _ in range(4000)]
    print(f"K={K}: checkpoint-draw-only SE(amp) with tasks fixed = {np.std(As):.3f}")
# Power for the context control. Estimand: DeltaA = A(32k) - A(8k), same tasks, same K checkpoints.
# Scenario model: at the new context, long-task gap shrinks by fraction f for truncating tasks only.
# Outcomes simulated per (task, ckpt) as Bernoulli with task-level success probs:
#   p_bf(task): BF16 success (observed 0/1 -> shrink toward domain-horizon base rate), p_q(task) = mean over 18 ckpts.
# Simplification: tasks that never truncate in BF16 AND whose checkpoint runs never truncate are copied (identical outcome).
pb=PT[PT.run=="bf16_v1"].set_index(PT[PT.run=="bf16_v1"].domain+":"+PT[PT.run=="bf16_v1"].task_id).frac_trunc.reindex(H.key).values
tr_q=np.array([PT[PT.run==r].set_index(PT[PT.run==r].domain+":"+PT[PT.run==r].task_id).n_trunc.reindex(H.key).values>0 for r in ck])
print(f"(task,ckpt) pairs with any truncation: long {tr_q[:,lg].mean():.3f}, short {tr_q[:,~lg].mean():.3f}; BF16 long tasks truncating {np.mean(pb[lg]>0):.3f}")
pq=Q.mean(0)
# smoothed BF16 success prob: posterior mean with the long/short base rate as prior (weight 2)
base=np.where(lg,bf[lg].mean(),bf[~lg].mean()); pbf=(bf+2*base)/3
def power(K,f,B=2000,alpha=0.05,rule="amp"):
    hits=0; dA=[]
    for b in range(B):
        il=rng.choice(np.where(lg)[0],lg.sum()); is_=rng.choice(np.where(~lg)[0],(~lg).sum()); idx=np.r_[il,is_]
        kk=rng.choice(len(ck),K)
        L=lg[idx]; Q8=Q[kk][:,idx]; B8=bf[idx]
        # new-context outcomes: redraw for pairs that truncate; long-task quantized success moves toward BF16 by f*gap
        trunc=tr_q[kk][:,idx]|(pb[idx]>0)[None,:]
        pqn=pq[idx]+f*(pbf[idx]-pq[idx])*L
        Qn=np.where(trunc,rng.random(Q8.shape)<pqn[None,:],Q8).astype(float)
        Bn=np.where(pb[idx]>0,(rng.random(len(idx))<pbf[idx]).astype(float),B8)
        a8=amp(B8,Q8,L)[0]; an=amp(Bn,Qn,L)[0]; dA.append(an-a8)
    dA=np.array(dA); return dA
for K in (3,6,9):
    for f in (0.0,0.5,1.0):
        dA=power(K,f)
        print(f"K={K} shrink f={f}: E[A_new-A_8k]={dA.mean():+.3f}, sd={dA.std():.3f}; P(A_new-A_8k < -1.96*sd0) ~ {np.mean(dA< -1.96*0.0+0*dA - 1.96*dA.std()) if f==0 else np.mean(dA < -1.96*res.get(K,(0.07,))[0]):.2f}")
