"""Power for the context-length control, fixed-task (conditional) and task-resampling views.
Model: at the longer context, (task,ckpt) pairs that never truncated at 8k (in BF16 and in that ckpt's run)
reproduce their 8k outcome exactly (deterministic serving, identical prompts); every pair that truncated is
re-drawn as Bernoulli(task-level prob). BF16 outcomes on BF16-truncating tasks are also re-drawn (single run!).
We report the sd of the amplification estimate A = gap_long - gap_short; the mean is set by the scenario."""
import pandas as pd, numpy as np
from pathlib import Path
from scipy.stats import norm
O=Path(__file__).parent; rng=np.random.default_rng(7)
T=pd.read_csv(O/"tasks.csv",dtype={"task_id":str}); PT=pd.read_csv(O/"per_task_trunc.csv",dtype={"task_id":str})
H=pd.read_csv(O/"horizon.csv",dtype={"task_id":str}); H["key"]=H.domain+":"+H.task_id; lg=(H.horizon>11).values
for d in (T,PT): d["key"]=d.domain+":"+d.task_id
ck=sorted(r for r in T.run.unique() if r.endswith("_dev"))
S=lambda r: T[T.run==r].set_index("key").db_match.astype(float).reindex(H.key).values
TR=lambda r: (PT[PT.run==r].set_index("key").n_trunc.reindex(H.key).values>0)
bf=S("bf16_v1"); Q=np.array([S(r) for r in ck]); trb=TR("bf16_v1"); trq=np.array([TR(r) for r in ck])
pq=Q.mean(0)
# BF16 task prob: single deterministic observation; use Q-informed shrinkage: p_bf = (bf + m*pq_adj)/(1+m)
def A(bfv,Qm):
    g=(bfv[None,:]-Qm).mean(0); return g[lg].mean()-g[~lg].mean()
A8=A(bf,Q)
def sim_sd(K,m=1.0,B=4000,task_boot=False):
    out=[]
    for _ in range(B):
        idx=np.arange(len(bf))
        if task_boot:
            idx=np.r_[rng.choice(np.where(lg)[0],lg.sum()),rng.choice(np.where(~lg)[0],(~lg).sum())]
        kk=rng.choice(len(ck),K,replace=(K>len(ck)))
        pb=(bf+m*pq)/(1+m)
        redraw_q=trq[kk][:,idx]|trb[idx][None,:]
        Qn=np.where(redraw_q,(rng.random((K,len(idx)))<pq[idx][None,:]).astype(float),Q[kk][:,idx])
        Bn=np.where(trb[idx],(rng.random(len(idx))<pb[idx]).astype(float),bf[idx])
        g=(Bn[None,:]-Qn).mean(0); L=lg[idx]
        out.append(g[L].mean()-g[~L].mean())
    return np.std(out)
print(f"A_8k observed = {A8:.3f}")
rows=[]
for K in (3,6,9,18):
    for tb in (False,True):
        sd=sim_sd(K,task_boot=tb)
        # power: survival test H0 A_new=0 one-sided alpha .05, true A_new=A8
        p_surv=1-norm.cdf(1.645-A8/sd)
        # truncation test: H0 A_new=A8 (8k value treated fixed), one-sided, true A_new=0 or A8/2
        p_trunc0=norm.cdf(-1.645+A8/sd); p_trunchalf=norm.cdf(-1.645+0.5*A8/sd)
        rows.append((K,"task-resample" if tb else "tasks fixed",sd,2.49*sd,p_surv,p_trunc0,p_trunchalf))
print(pd.DataFrame(rows,columns=["K","inference","sd(A_new)","MDE80(one-sided)","power: survives (A=0.137 vs 0)","power: detect full removal","power: detect half removal"]).round(3).to_string(index=False))
# How much of sd is BF16 single-run redraw? fix BF16 (no redraw) for comparison
def sd_noBF(K,B=4000):
    out=[]
    for _ in range(B):
        kk=rng.choice(len(ck),K); rq=trq[kk]|trb[None,:]
        Qn=np.where(rq,(rng.random((K,len(bf)))<pq[None,:]).astype(float),Q[kk])
        g=(bf[None,:]-Qn).mean(0); out.append(g[lg].mean()-g[~lg].mean())
    return np.std(out)
print("sd with BF16 held fixed (no BF16 redraw): K=6 %.3f, K=18 %.3f  -> the single BF16 run is the floor"%(sd_noBF(6),sd_noBF(18)))
# Enlarged task set: scale task-resample sd by sqrt(85/N)
for N in (85,164,278):
    print(f"N tasks={N}: approx task-resample sd(A) at K=6 ~ {sim_sd(6,task_boot=True,B=2000)*np.sqrt(85/N):.3f}")
