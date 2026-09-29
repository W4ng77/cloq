import pandas as pd, numpy as np
from pathlib import Path
O=Path(__file__).parent
T=pd.read_csv(O/"timing.csv",dtype={"task_id":str}); S=pd.read_csv(O/"status.csv")
# only dev tasks
H=pd.read_csv(O/"horizon.csv",dtype={"task_id":str}); T=T.merge(H[["domain","task_id"]])
w=S.groupby("run").elapsed.sum()
print("wall per checkpoint (retail+airline, 85 tasks), seconds:")
print("  bf16_v1 %.0f; quantized 18: median %.0f mean %.0f min %.0f max %.0f; total 18 = %.1f h"%(w["bf16_v1"],w.drop("bf16_v1").median(),w.drop("bf16_v1").mean(),w.drop("bf16_v1").min(),w.drop("bf16_v1").max(),w.drop("bf16_v1").sum()/3600))
print("  per-task wall (elapsed/85): bf16 %.1f s, quantized median %.1f s"%(w["bf16_v1"]/85,w.drop("bf16_v1").median()/85))
ag=T.groupby("run").agg(dec=("gen_s","size"),agent_s=("gen_s","sum"),gen_tok=("n_gen","sum"),prompt_tok=("n_prompt","sum"))
ag["wall"]=w; ag["agent_busy_frac_of_8slots"]=ag.agent_s/(ag.wall*8); ag["s_per_dec"]=ag.agent_s/ag.dec; ag["gen_tok_per_dec"]=ag.gen_tok/ag.dec
print(ag.round(2).to_string())
# per-decision latency model
q=T.copy(); q["ctx_k"]=q.n_prompt/1000
A=np.column_stack([np.ones(len(q)),q.n_gen,q.n_gen*q.ctx_k,q.ctx_k]); b=np.linalg.lstsq(A,q.gen_s,rcond=None)[0]
print("\nlatency model gen_s = %.3f + %.4f*n_gen + %.6f*n_gen*ctx_k + %.4f*ctx_k"%tuple(b))
print("per-token decode at 5k ctx %.1f ms, at 8k %.1f ms, at 16k %.1f ms, at 32k %.1f ms"%tuple(1000*(b[1]+b[2]*c) for c in (5,8,16,32)))
# Project agent time under 16k/32k policies using pre-truncation context as the proxy context
for cap in (8192,16384,32768):
    ctx=np.minimum(q.pre,cap)/1000
    proj=b[0]+b[1]*q.n_gen+b[2]*q.n_gen*ctx+b[3]*ctx
    base=b[0]+b[1]*q.n_gen+b[2]*q.n_gen*q.ctx_k+b[3]*q.ctx_k
    print(f"cap {cap}: mean ctx {ctx.mean()*1000:.0f} tok, projected agent-time ratio vs 8k policy {proj.sum()/base.sum():.3f}")
