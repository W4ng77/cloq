import pandas as pd, numpy as np
from pathlib import Path
O = Path(__file__).parent
D = pd.read_csv(O / "decisions.csv", dtype={"task_id": str})
H = pd.read_csv(O / "horizon.csv", dtype={"task_id": str})
V1 = [r for r in D.run.unique() if r.endswith("_dev")]
D = D[D.run.isin(["bf16_v1"] + V1)]

# sanity: bf16_v1 horizon == manifest horizon
b = D[D.run == "bf16_v1"].groupby(["domain", "task_id"]).size().rename("H_v1").reset_index().merge(H)
print("bf16_v1 n_decisions == manifest horizon:", (b.H_v1 == b.horizon).mean(), "n=", len(b))

def per_task(g):
    tr = g[g.truncated]
    return pd.Series(dict(n_dec=len(g), onset=(tr.idx.min() if len(tr) else np.nan),
                          frac_trunc=g.truncated.mean(), max_pre=g.pre.max(), n_trunc=len(tr),
                          max_dropped=g.dropped.max()))
PT = D.groupby(["run", "domain", "task_id"]).apply(per_task).reset_index().merge(H)
PT["long"] = PT.horizon > 11
PT.to_csv(O / "per_task_trunc.csv", index=False)

print("\n== per-run summary (85 dev tasks) ==")
S = PT.groupby("run").agg(dec=("n_dec", "sum"), tasks_any_trunc=("n_trunc", lambda x: (x > 0).mean()),
                          med_onset=("onset", "median"), mean_frac=("frac_trunc", "mean"),
                          max_pre=("max_pre", "max"))
S["dec_trunc_rate"] = D.groupby("run").truncated.mean()
print(S.round(3).to_string())
q = PT[PT.run != "bf16_v1"]
print("\nquantized pooled over 18 ckpts: task-level any-trunc %.3f, decision-level trunc rate %.3f, N decisions %d"
      % ((q.n_trunc > 0).mean(), D[D.run != "bf16_v1"].truncated.mean(), (D.run != "bf16_v1").sum()))

print("\n== BF16 per-task truncation by long/short ==")
bb = PT[PT.run == "bf16_v1"]
for lg, g in bb.groupby("long"):
    print(f"long={lg}: n={len(g)}, any-trunc={ (g.n_trunc>0).mean():.3f}, mean frac={g.frac_trunc.mean():.3f}, "
          f"median onset={g.onset.median()}, onset/H median={(g.onset/g.horizon).median():.3f}")
print("spearman(horizon, frac_trunc) BF16 all 85:", bb[["horizon", "frac_trunc"]].corr("spearman").iloc[0, 1].round(3))
print("spearman(horizon, frac_trunc) BF16 long 37:", bb[bb.long][["horizon", "frac_trunc"]].corr("spearman").iloc[0, 1].round(3))
print("pearson(horizon, frac_trunc) BF16 all 85:", bb[["horizon", "frac_trunc"]].corr().iloc[0, 1].round(3))
print("BF16 truncation onset (decision idx) by domain:")
print(bb.groupby("domain").onset.describe().round(2).to_string())

print("\n== pre_truncation_tokens distribution (tokens needed so the policy never drops history) ==")
# prompt budget needed = pre; model len = pre + max_tokens(1024)
for name, sub in [("bf16_v1", D[D.run == "bf16_v1"]), ("18 quantized", D[D.run != "bf16_v1"]), ("all 19", D)]:
    p = sub.pre.values
    qs = np.percentile(p, [50, 90, 95, 99, 100])
    print(f"{name:13s} N={len(p):6d} p50={qs[0]:.0f} p90={qs[1]:.0f} p95={qs[2]:.0f} p99={qs[3]:.0f} max={qs[4]:.0f} "
          f"frac>8192={np.mean(p>8192):.3f} frac>16384={np.mean(p>16384):.4f} frac>32768={np.mean(p>32768):.5f}")
    for dom in ("retail", "airline"):
        p2 = sub[sub.domain == dom].pre.values
        qs = np.percentile(p2, [95, 99, 100])
        print(f"   {dom:7s} N={len(p2):6d} p95={qs[0]:.0f} p99={qs[1]:.0f} max={qs[2]:.0f} >16384={np.mean(p2>16384):.4f} >32768={np.mean(p2>32768):.5f}")
# task-level: fraction of tasks whose max_pre exceeds 16k/32k
for name, sub in [("bf16_v1", PT[PT.run == "bf16_v1"]), ("18 quantized", PT[PT.run != "bf16_v1"])]:
    print(f"{name}: tasks with max_pre>16384: {(sub.max_pre>16384).mean():.3f}, >32768: {(sub.max_pre>32768).mean():.4f}; n={len(sub)}")
bl = PT[(PT.run == "bf16_v1") & PT.long]
print("BF16 long tasks max_pre: median %.0f, p90 %.0f, max %.0f; >16384: %d/%d" % (bl.max_pre.median(), bl.max_pre.quantile(.9), bl.max_pre.max(), (bl.max_pre > 16384).sum(), len(bl)))
# note pre_truncation_tokens counts the whole un-truncated rendering; decisions that were never truncated have pre==post
print("check pre==post when not truncated:", (D[~D.truncated].pre == D[~D.truncated].post).mean())
# prefix-cache implication: fraction of truncated decisions (prefix after first user request changes)
