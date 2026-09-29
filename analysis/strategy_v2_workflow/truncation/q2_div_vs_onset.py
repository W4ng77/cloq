"""Q2: is the first divergence at/after truncation onset more often than chance?"""
import pandas as pd, numpy as np
from pathlib import Path
from scipy.optimize import minimize
O = Path(__file__).parent
rng = np.random.default_rng(0)
D = pd.read_csv(O / "decisions.csv", dtype={"task_id": str})
PT = pd.read_csv(O / "per_task_trunc.csv", dtype={"task_id": str})
V = pd.read_csv(O / "divergence.csv", dtype={"task_id": str})
V = V[V.run.str.endswith("_dev")].copy()
bo = PT[PT.run == "bf16_v1"][["domain", "task_id", "onset", "horizon", "frac_trunc"]].rename(columns={"onset": "onset_fp", "frac_trunc": "frac_fp"})
qo = PT[PT.run != "bf16_v1"][["run", "domain", "task_id", "onset"]].rename(columns={"onset": "onset_q"})
V = V.merge(bo).merge(qo)
V["long"] = V.horizon > 11
div = V[V.t_tool.notna()].copy()
print("checkpoint-task pairs: %d, with tool divergence: %d" % (len(V), len(div)))

for label, sub in [("all", div), ("long", div[div.long]), ("short", div[~div.long])]:
    for col, oc in [("t_tool", "onset_fp"), ("t_tool", "onset_q"), ("t_context", "onset_fp"), ("t_render", "onset_fp")]:
        s = sub[sub[col].notna()]
        after = (s[col] >= s[oc]).fillna(False)  # never-truncating trajectory -> onset NaN -> not after
        has_on = s[oc].notna()
        print(f"[{label:5s}] {col:9s} >= {oc:8s}: {after.mean():.3f} ({after.sum()}/{len(s)}); "
              f"among trajectories that truncate at all: {after[has_on].mean():.3f} ({after[has_on].sum()}/{has_on.sum()})")
# t_tool relative to onset, long tasks with BF16 truncation
s = div[div.long & div.onset_fp.notna()]
print("\nlong tasks with BF16 truncation: t_tool - onset_fp distribution:", s.eval("t_tool-onset_fp").describe().round(2).to_dict())
print("t_tool: median %.1f; onset_fp median %.1f; n=%d" % (s.t_tool.median(), s.onset_fp.median(), len(s)))

# Null model: where would divergences fall relative to onset if the divergence step were drawn from the
# empirical distribution of t_tool among other tasks with the same horizon (+-1)? Permutation of onsets among
# tasks with equal horizon: keeps depth structure, breaks any task-specific onset alignment.
def stat(df):
    return (df.t_tool >= df.onset_fp).fillna(False).mean()
obs = stat(div)
tasks = bo.set_index(["domain", "task_id"])
hbin = tasks.horizon.clip(upper=40)
perm = []
keys = list(tasks.index)
groups = {}
for k in keys:
    groups.setdefault(int(hbin[k]), []).append(k)
for b in range(2000):
    mp = {}
    for h, ks in groups.items():
        # pool with neighbours if singleton
        pool = [kk for hh in (h - 1, h, h + 1) for kk in groups.get(hh, [])]
        vals = tasks.loc[pool, "onset_fp"].values
        for k in ks:
            mp[k] = rng.choice(vals)
    on = np.array([mp[(d, t)] for d, t in zip(div.domain, div.task_id)])
    perm.append(np.mean(np.nan_to_num(div.t_tool.values >= on, nan=0) & ~np.isnan(on)))
perm = np.array(perm)
print(f"\nPermutation (onsets shuffled among tasks with horizon +-1): observed frac(t_tool>=onset_fp)={obs:.4f}, "
      f"null mean={perm.mean():.4f}, 95% null interval [{np.percentile(perm,2.5):.4f},{np.percentile(perm,97.5):.4f}], "
      f"p(one-sided, null>=obs)={np.mean(perm>=obs):.3f}")

# Discrete-time hazard of first tool divergence vs Q's own truncation state at that decision,
# controlling for decision index (dummies 0..14+) and domain; cluster bootstrap over tasks.
Dq = D[D.run.str.endswith("_dev")][["run", "domain", "task_id", "idx", "truncated"]]
Dfp = D[D.run == "bf16_v1"][["domain", "task_id", "idx", "truncated"]].rename(columns={"truncated": "trunc_fp"})
rows = []
Vi = V.set_index(["run", "domain", "task_id"])
g = Dq.merge(Dfp, how="left", on=["domain", "task_id", "idx"])
g = g.merge(V[["run", "domain", "task_id", "t_tool", "H_fp", "H_q"]], on=["run", "domain", "task_id"])
end = np.where(g.t_tool.notna(), g.t_tool, np.minimum(g.H_fp, g.H_q) - 1)
g = g[g.idx <= end].copy()
g["event"] = (g.idx == g.t_tool).astype(int)
g["trunc_fp"] = g.trunc_fp.fillna(False).astype(bool)
print("\nhazard risk set: %d decision rows, %d events, truncated rows (Q ctx) %d, events on truncated rows %d"
      % (len(g), g.event.sum(), g.truncated.sum(), g[g.truncated].event.sum()))
g["didx"] = g.idx.clip(upper=12)
tab = g.groupby(["didx", "truncated"]).agg(n=("event", "size"), ev=("event", "sum"))
tab["haz"] = tab.ev / tab.n
print(tab.unstack().round(3).to_string())

def fit(df):
    X = pd.get_dummies(df.didx, prefix="d", drop_first=False).astype(float)
    X["trunc"] = df.truncated.astype(float).values
    X["airline"] = (df.domain == "airline").astype(float).values
    X = X.values; y = df.event.values.astype(float)
    def nll(b):
        z = X @ b
        return np.sum(np.logaddexp(0, z) - y * z) + 1e-4 * b @ b
    r = minimize(nll, np.zeros(X.shape[1]), method="L-BFGS-B")
    return r.x[-2]
b0 = fit(g)
tk = g[["domain", "task_id"]].drop_duplicates().values.tolist()
gi = g.set_index(["domain", "task_id"])
bs = []
for b in range(300):
    samp = [tuple(tk[i]) for i in rng.integers(0, len(tk), len(tk))]
    df = pd.concat([gi.loc[[k]] for k in samp]).reset_index()
    try:
        bs.append(fit(df))
    except Exception:
        pass
bs = np.array(bs)
print(f"hazard log-odds for Q-context truncated (depth dummies + domain): {b0:.3f}, OR={np.exp(b0):.2f}, "
      f"task-cluster bootstrap 95% CI [{np.percentile(bs,2.5):.3f},{np.percentile(bs,97.5):.3f}] (B={len(bs)})")
