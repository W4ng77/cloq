import pandas as pd, numpy as np, re, glob, json
from pathlib import Path
O=Path(__file__).parent; rng=np.random.default_rng(3)
cfg=json.load(open(glob.glob("/home/xinyu/.cache/huggingface/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots/*/config.json")[0]))
L,KVH,HD=cfg["num_hidden_layers"],cfg["num_key_value_heads"],cfg["head_dim"]
bpt=2*L*KVH*HD*2
print(f"layers {L}, kv heads {KVH}, head_dim {HD}: KV bytes/token bf16 = {bpt} ({bpt/1024:.0f} KiB)")
for n in (9216,16384,17408,32768,33792):
    print(f"  {n:6d} tokens -> {n*bpt/2**30:.3f} GiB")
cap=42816; print(f"logged KV pool {cap} tokens = {cap*bpt/2**30:.3f} GiB (log says 5.88 GiB available)")
for util,extra in ((0.92,0),(0.95,0.03*15.57)):
    c=cap+int(extra*2**30/bpt)
    print(f"util {util}: pool ~{c} tokens; worst-case concurrency (no prefix sharing) 17408:{c/17408:.2f}x 33792:{c/33792:.2f}x; with 4.85k shared prefix: 17408:{(c-4850)/(17408-4850):.2f}x 33792:{(c-4850)/(33792-4850):.2f}x")
# running-request distribution from closed-loop logs (bf16 + cloq_novel c1..c3 are closed-loop phases)
R=[];K=[]
for f in ["vllm_agent_bf16.log","vllm_agent_cloq_novel_c1.log","vllm_agent_cloq_novel_c2.log","vllm_agent_cloq_novel_c3.log"]:
    for l in open("/home/xinyu/cloq/logs/v1/"+f,errors="ignore"):
        m=re.search(r"Running: (\d+) reqs, Waiting: (\d+) reqs, GPU KV cache usage: ([\d.]+)%",l)
        if m: R.append(int(m.group(1))); K.append(float(m.group(3)))
R=np.array(R); K=np.array(K)
print(f"closed-loop log snapshots n={len(R)}: running mean {R.mean():.2f}, P(R>=6) {np.mean(R>=6):.3f}, P(R=8) {np.mean(R==8):.3f}; KV usage p50 {np.percentile(K,50):.1f}% p95 {np.percentile(K,95):.1f}% max {K.max():.1f}%")
D=pd.read_csv(O/"decisions.csv",dtype={"task_id":str}); D=D[D.run.str.endswith("_dev")|(D.run=="bf16_v1")]
pre=D.pre.values; post=D.post.values
SP=4850
def sim(ctxs, Rs, capacity, gen=100):
    over=[];use=[]
    for r in Rs:
        if r==0: use.append(0); over.append(False); continue
        c=rng.choice(ctxs,r)
        tot=SP+np.sum(c-SP+gen)
        use.append(tot/capacity); over.append(tot>capacity)
    return np.array(use),np.array(over)
Rs=rng.choice(R[R>0],20000)
for name,ctx in (("8k (observed post)",post),("16k policy (min(pre,16384))",np.minimum(pre,16384)),("32k policy (min(pre,32768))",np.minimum(pre,32768))):
    u,o=sim(ctx,Rs,cap)
    u8,o8=sim(ctx,np.full(20000,8),cap)
    print(f"{name:30s} running~logs: KV use p50 {np.percentile(u,50)*100:.0f}% p95 {np.percentile(u,95)*100:.0f}% P(over pool) {o.mean():.4f} | all 8 slots busy: P(over) {o8.mean():.3f}")
