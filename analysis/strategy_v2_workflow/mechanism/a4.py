"""Q4 closed-loop margin hypothesis: is the first divergence step a low-confidence BF16 state?"""
import pickle, json, os
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats
os.environ["CUDA_VISIBLE_DEVICES"] = ""
OUT = Path(__file__).resolve().parent
d = pickle.load(open(OUT / "tables.pkl", "rb")); C, CK = d["C"], d["CKPTS"]
S = pickle.load(open(OUT / "S_with_flip.pkl", "rb"))
rng = np.random.default_rng(1)
res = {}
traj = {k: g.sort_values("idx") for k, g in S.groupby(["domain", "task_id"])}


def rank_stat(vals, j, prev_mask=None):
    """normalised mid-rank of vals[j] among vals[0..j] (1 = highest NLL = least confident).
    Returns (u, is_max, k) where u in [0,1], null mean 0.5; k = number of comparison steps."""
    prev = vals[:j] if prev_mask is None else vals[:j][prev_mask[:j]]
    k = len(prev)
    if k == 0: return None
    u = (np.sum(prev < vals[j]) + 0.5 * np.sum(prev == vals[j])) / k
    return u, float(vals[j] > prev.max()), k


def analyse(rows, label):
    """rows: list of (task_key, u, is_max, k). Task-cluster bootstrap for mean(u)-0.5 and P(max)-E[P(max)]."""
    df = pd.DataFrame(rows, columns=["task", "u", "ismax", "k"])
    df["e_max"] = 1 / (df.k + 1)
    obs_u = df.u.mean(); obs_m = df.ismax.mean(); exp_m = df.e_max.mean()
    # exact within-trajectory permutation null: divergence position drawn uniformly among its k+1 candidate steps
    # (Monte Carlo over rows; rows keep their own NLL vectors via stored null draws)
    tasks = df.task.unique(); gi = df.groupby("task").indices
    bs_u, bs_m = [], []
    for b in range(4000):
        ix = np.concatenate([gi[t] for t in rng.choice(tasks, len(tasks))])
        bs_u.append(df.u.values[ix].mean()); bs_m.append(df.ismax.values[ix].mean() - df.e_max.values[ix].mean())
    ci_u = np.percentile(bs_u, [2.5, 97.5]); ci_m = np.percentile(bs_m, [2.5, 97.5])
    # p-value: bootstrap-t style via cluster SE
    se = np.std(bs_u); z = (obs_u - 0.5) / se; p = 2 * stats.norm.sf(abs(z))
    print(f"{label}: n={len(df)} (ckpt,task) pairs over {len(tasks)} tasks; mean rank u={obs_u:.3f} (null 0.5) "
          f"95% task-cluster CI [{ci_u[0]:.3f},{ci_u[1]:.3f}] z={z:.2f} p={p:.2g}; divergence step is the least-confident so far: "
          f"{obs_m:.3f} vs null {exp_m:.3f} (diff CI [{ci_m[0]:.3f},{ci_m[1]:.3f}])")
    return dict(n=len(df), n_tasks=len(tasks), mean_u=obs_u, ci_u=ci_u.tolist(), z=z, p=p, p_max=obs_m, p_max_null=exp_m, ci_diff_max=ci_m.tolist())




for metric in ["nll", "nlltok"]:
    print(f"\n######## BF16 confidence proxy = {metric} ########")
    # (a) t_render: the decision that split the context; state is IDENTICAL to BF16's (verified by prompt hash)
    rows, rv = [], []
    for r in C.itertuples():
        if r.t_render is None or np.isnan(r.t_render): continue
        j = int(r.t_render); g = traj[(r.domain, r.task_id)]
        if j >= len(g) or j < 1: continue
        v = g[metric].values; s = rank_stat(v, j)
        if s: rows.append(((r.domain, r.task_id), *s)); rv.append((v, j))
    res[f"render_{metric}"] = analyse(rows, "(a) t_render=t_context-1 [exact BF16 state], rank among all preceding steps")
    # same-kind comparison: rank among preceding steps of the same BF16 action kind
    rows = []
    for r in C.itertuples():
        if r.t_render is None or np.isnan(r.t_render): continue
        j = int(r.t_render); g = traj[(r.domain, r.task_id)]
        if j >= len(g) or j < 1: continue
        kinds = g.kind.values; v = g[metric].values; s = rank_stat(v, j, kinds == kinds[j])
        if s: rows.append(((r.domain, r.task_id), *s))
    res[f"render_samekind_{metric}"] = analyse(rows, "(a') t_render, rank among preceding steps of same kind")
    # (b) t_tool: first behavioural divergence. Exact only if t_tool < t_context.
    for sub, lab in [(C[C.tool_at_same_ctx], "exact-state subset (t_tool < t_context)"), (C, "all (index-matched BF16 state; context may differ by rewording)")]:
        rows = []; rows_sk = []
        for r in sub.itertuples():
            if r.t_tool is None or np.isnan(r.t_tool): continue
            j = int(r.t_tool); g = traj[(r.domain, r.task_id)]
            if j >= len(g) or j < 1: continue
            v = g[metric].values; kinds = g.kind.values
            s = rank_stat(v, j)
            if s: rows.append(((r.domain, r.task_id), *s))
            s2 = rank_stat(v, j, kinds == kinds[j])
            if s2: rows_sk.append(((r.domain, r.task_id), *s2))
        res[f"ttool_{lab[:5]}_{metric}"] = analyse(rows, f"(b) t_tool {lab}, all preceding")
        res[f"ttool_{lab[:5]}_samekind_{metric}"] = analyse(rows_sk, f"(b') t_tool {lab}, same-kind preceding")

# (c) open-loop fragility at the divergence step vs preceding steps: 18-checkpoint behavioural flip rate of the BF16 state
print("\n######## (c) open-loop fragility (18-ckpt behavioural flip rate) at t_tool vs preceding steps ########")
rows = []
for r in C.itertuples():
    if r.t_tool is None or np.isnan(r.t_tool): continue
    j = int(r.t_tool); g = traj[(r.domain, r.task_id)]
    if j >= len(g) or j < 1: continue
    s = rank_stat(g.flip_beh.values, j)
    if s: rows.append(((r.domain, r.task_id), *s))
res["ttool_olfrag"] = analyse(rows, "(c) rank of open-loop behavioural flip rate at t_tool")

# (d) does closed-loop behaviour diverge where the open-loop replay of THE SAME checkpoint would?
print("\n######## (d) first open-loop behavioural flip along BF16 path (same checkpoint) vs closed-loop t_tool ########")
rec = []
for r in C.itertuples():
    g = traj[(r.domain, r.task_id)]
    fl = g[f"bflip__{r.ck}"].values.astype(bool)
    f_ol = int(np.argmax(fl)) if fl.any() else None
    tt = None if (r.t_tool is None or np.isnan(r.t_tool)) else int(r.t_tool)
    rec.append(dict(ck=r.ck, f_ol=f_ol, t_tool=tt, H=len(g), same_ctx=r.tool_at_same_ctx, H_q=r.H_q))
R = pd.DataFrame(rec)
both = R[R.f_ol.notna() & R.t_tool.notna()]
print("pairs:", len(R), " open-loop flips somewhere:", R.f_ol.notna().sum(), " closed-loop t_tool defined:", R.t_tool.notna().sum())
print("t_tool == first open-loop flip: %.3f ; t_tool < f_ol (closed loop diverged EARLIER than open-loop predicts): %.3f ; t_tool > f_ol: %.3f (n=%d)" %
      ((both.t_tool == both.f_ol).mean(), (both.t_tool < both.f_ol).mean(), (both.t_tool > both.f_ol).mean(), len(both)))
nf = R[R.f_ol.isna() & R.t_tool.notna()]
print("closed-loop behavioural divergence although the checkpoint never flips open-loop on this BF16 path: %d / %d pairs with no OL flip" % (len(nf), R.f_ol.isna().sum()))
res["d"] = dict(eq=float((both.t_tool == both.f_ol).mean()), earlier=float((both.t_tool < both.f_ol).mean()), later=float((both.t_tool > both.f_ol).mean()), n=len(both),
                no_ol_flip_but_diverged=int(len(nf)), no_ol_flip=int(R.f_ol.isna().sum()))
# hazard comparison: closed-loop step-wise behavioural divergence hazard vs open-loop per-state flip rate at the same index
print("step-wise hazard: closed-loop P(t_tool = i | t_tool >= i) vs mean open-loop behavioural flip rate at BF16 state i, pooled over pairs")
hz = []
for i in range(0, 20):
    at_risk = C[(C.t_tool.isna()) | (C.t_tool >= i)]
    at_risk = at_risk[at_risk.H_fp > i]
    if len(at_risk) < 30: break
    h = (at_risk.t_tool == i).mean()
    ol = np.mean([traj[(r.domain, r.task_id)].flip_beh.values[i] for r in at_risk.itertuples()])
    hz.append((i, len(at_risk), round(h, 3), round(ol, 3)))
print(pd.DataFrame(hz, columns=["step", "n_at_risk", "closed_hazard", "openloop_flip_rate"]).to_string(index=False))
res["hazard"] = hz
json.dump(res, open(OUT / "res_a4.json", "w"), indent=1, default=float)
