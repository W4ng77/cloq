import json, sys, pandas as pd
from pathlib import Path
sys.path.insert(0, "/home/xinyu/cloq")
from cloq.metrics import load_decisions
R = Path("/home/xinyu/cloq/runs"); O = Path(__file__).parent
ARMS = ["static", "fp_traj", "cloq_all", "cloq_novel", "cloq_matched_random", "cloq_matched_alt"]
RUNS = ["bf16_v1"] + [f"{a}_{c}_dev" for a in ARMS for c in ("c1", "c2", "c3")]
rows=[]; st=[]; pref=[]
for run in RUNS:
    for dom in ("retail","airline"):
        decs = load_decisions(R/run/dom)
        for d in decs:
            rows.append(dict(run=run,domain=dom,task_id=d["task_id"],idx=d["decision_idx"],n_prompt=d["n_prompt_tokens"],
                             n_gen=d.get("n_completion_tokens"),gen_s=d.get("generation_seconds"),pre=d["context"]["pre_truncation_tokens"]))
        s=json.load(open(R/run/dom/"status.json")); st.append(dict(run=run,domain=dom,elapsed=s["elapsed_seconds"],n_tasks=s["n_tasks"]))
        if run=="bf16_v1":
            # shared prefix length: longest common prefix of prompt_token_ids across idx-0 prompts of this domain
            p0=[d["prompt_token_ids"] for d in decs if d["decision_idx"]==0]
            lcp=len(p0[0])
            for p in p0[1:]:
                k=0
                while k<min(lcp,len(p)) and p[k]==p0[0][k]: k+=1
                lcp=k
            pref.append(dict(domain=dom,shared_prefix=lcp,median_idx0=sorted(len(p) for p in p0)[len(p0)//2]))
pd.DataFrame(rows).to_csv(O/"timing.csv",index=False); pd.DataFrame(st).to_csv(O/"status.csv",index=False)
print(pd.DataFrame(pref))
