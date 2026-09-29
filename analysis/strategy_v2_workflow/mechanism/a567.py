"""Q5 failure taxonomy, Q6 fragile vs robust tasks, Q7 recovery; plus user-reply check after first rewording."""
import pickle, json, os, sys
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np, pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score
os.environ["CUDA_VISIBLE_DEVICES"] = ""
ROOT = Path("/home/xinyu/cloq"); sys.path.insert(0, str(ROOT))
from cloq.metrics import read_jsonl, _canon_value
OUT = Path(__file__).resolve().parent
d = pickle.load(open(OUT / "tables.pkl", "rb")); C, CK, ARMS = d["C"], d["CKPTS"], d["ARMS"]
S = pickle.load(open(OUT / "S_with_flip.pkl", "rb"))
sys.path.insert(0, str(OUT)); from build import WRITE
rng = np.random.default_rng(2); res = {}
pd.set_option("display.width", 250)


def load_traj(run, dom):
    return {t["task_id"]: t for t in read_jsonl(ROOT / "runs" / run / dom / "trajectory.jsonl")}
TR = {(ck, dom): load_traj(f"{ck}_dev", dom) for ck in CK for dom in ["retail", "airline"]}
TB = {dom: load_traj("bf16_v1", dom) for dom in ["retail", "airline"]}


def calls(traj, ok_only=True):
    msgs = traj["messages"]; err = {m.get("id"): bool(m.get("error")) for m in msgs if m.get("role") == "tool"}
    out = []
    for m in msgs:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                e = err.get(tc.get("id"), None)
                if ok_only and e: continue
                out.append((tc["name"], tc.get("arguments") or {}, e))
    return out


def args_match(exp, got):
    ca = exp.get("compare_args")
    ea, ga = _canon_value(exp["arguments"] or {}), _canon_value(got)
    if ca is None: return ea == ga
    return all(ea.get(k) == ga.get(k) for k in ca)


def taxonomy(traj):
    exp = [a for a in traj["task"]["evaluation_criteria"]["actions"] or [] if a["name"] in WRITE]
    got_ok = [c for c in calls(traj, True) if c[0] in WRITE]
    got_any = [c for c in calls(traj, False) if c[0] in WRITE]
    missing = wrong = 0; used = set()
    for e in exp:
        hit = [i for i, g in enumerate(got_ok) if g[0] == e["name"] and args_match(e, g[1]) and i not in used]
        if hit: used.add(hit[0]); continue
        if any(g[0] == e["name"] for g in got_any): wrong += 1
        else: missing += 1
    extra = len([i for i in range(len(got_ok)) if i not in used])
    return dict(n_exp_writes=len(exp), missing=missing, wrong_args=wrong, extra_writes=extra, n_ok_writes=len(got_ok))


print("=== Q5: failure taxonomy on tasks BF16 solves but a quantized checkpoint fails ===")
rows = []
for r in C.itertuples():
    if not (r.bf16_success and not r.q_success): continue
    t = TR[(r.ck, r.domain)][r.task_id]
    if r.q_premature:
        cat = "premature:" + r.q_term; tx = dict(n_exp_writes=None, missing=None, wrong_args=None, extra_writes=None)
    else:
        tx = taxonomy(t)
        if tx["missing"] > 0 and tx["wrong_args"] == 0: cat = "missing write"
        elif tx["wrong_args"] > 0: cat = "wrong-args write" + (" (+missing)" if tx["missing"] else "")
        elif tx["extra_writes"] > 0: cat = "extra write only"
        else: cat = "all writes correct, DB still wrong"
        if cat != "all writes correct, DB still wrong" and tx["extra_writes"] > 0 and cat != "extra write only": cat += " +extra"
    rows.append(dict(ck=r.ck, arm=r.arm, domain=r.domain, task_id=r.task_id, cat=cat, **tx))
F = pd.DataFrame(rows)
print("n failure pairs:", len(F), "over", F.task_id.nunique(), "tasks; BF16-solved tasks:", C[C.ck == CK[0]].bf16_success.sum())
print(F.cat.value_counts().to_string())
res["q5_counts"] = F.cat.value_counts().to_dict()
F["coarse"] = F.cat.map(lambda c: "premature" if c.startswith("premature") else ("missing" if c.startswith("missing") else ("wrong_args" if c.startswith("wrong") else ("extra_only" if c.startswith("extra") else "other"))))
ct = pd.crosstab(F.arm, F.coarse); print("\nby arm:"); print(ct.to_string())
chi = stats.chi2_contingency(ct.values); print("chi2 arm x coarse cat: %.2f dof %d p=%.3f (pairs share tasks; descriptive)" % (chi[0], chi[2], chi[1]))
res["q5_by_arm"] = ct.to_dict()
print("\nby domain:"); print(pd.crosstab(F.domain, F.coarse).to_string())
# BF16 reference: same taxonomy on BF16 failures (for contrast)
bf = []
for dom in ["retail", "airline"]:
    for tid, t in TB[dom].items():
        m = C[(C.ck == CK[0]) & (C.domain == dom) & (C.task_id == tid)]
        if len(m) == 0 or m.bf16_success.iloc[0]: continue
        if m.fp_term.iloc[0] != "user_stop": bf.append("premature"); continue
        tx = taxonomy(t); bf.append("missing" if tx["missing"] and not tx["wrong_args"] else "wrong_args" if tx["wrong_args"] else "extra_only" if tx["extra_writes"] else "other")
print("BF16's own failures on dev (for reference):", Counter(bf))
# missing write: did Q stop early (fewer decisions) or transfer?
mw = F[F.coarse == "missing"]
print("\nmissing-write failures: Q called transfer_to_human_agents in %.2f of them" % np.mean(
    [any(c[0] == "transfer_to_human_agents" for c in calls(TR[(r.ck, r.domain)][r.task_id], False)) for r in mw.itertuples()]))

print("\n=== Q6: fragile vs robust tasks ===")
T = C.groupby(["domain", "task_id"]).agg(bf16=("bf16_success", "first"), nq=("q_success", "sum"), H=("H_fp", "first")).reset_index()
feat = []
for (dom, tid), g in S.groupby(["domain", "task_id"]):
    tool = g[g.kind == "tool"]
    feat.append(dict(domain=dom, task_id=tid, max_nlltok=g.nlltok.max(), max_nll=g.nll.max(), max_nlltok_tool=tool.nlltok.max() if len(tool) else 0,
                     sum_tool_nlltok=tool.nlltok.sum(), n_lowconf_tool=(tool.nlltok > 0.0055).sum(),
                     exp_beh_flips=g.flip_beh.sum(), ol_survival=np.prod(1 - g.flip_beh.values),
                     n_req_writes=len([a for a in TB[dom][tid]["task"]["evaluation_criteria"]["actions"] or [] if a["name"] in WRITE]),
                     n_req_actions=len(TB[dom][tid]["task"]["evaluation_criteria"]["actions"] or [])))
T = T.merge(pd.DataFrame(feat), on=["domain", "task_id"])
Ts = T[T.bf16].copy(); Ts["fail_rate"] = 1 - Ts.nq / 18
print("BF16-solved tasks:", len(Ts), " distribution of #ckpts solving (0..18):", np.bincount(Ts.nq.astype(int), minlength=19).tolist())
Ts["group"] = np.where(Ts.nq <= 3, "fragile", np.where(Ts.nq >= 15, "robust", "mid"))
print(Ts.group.value_counts().to_dict())
cols = ["H", "n_req_writes", "n_req_actions", "max_nlltok", "max_nll", "max_nlltok_tool", "sum_tool_nlltok", "n_lowconf_tool", "exp_beh_flips", "ol_survival"]
g2 = Ts[Ts.group != "mid"]
print(Ts.groupby("group")[cols].median().round(4).to_string())
print("domain x group:"); print(pd.crosstab(Ts.domain, Ts.group).to_string())
y = (g2.group == "fragile").astype(int)
out6 = {}
for c in cols:
    s = g2[c] if c != "ol_survival" else -g2[c]
    auc = roc_auc_score(y, s)
    mw_ = stats.mannwhitneyu(g2[g2.group == "fragile"][c], g2[g2.group == "robust"][c])
    rho = stats.spearmanr(Ts[c], Ts.fail_rate)
    # partial Spearman controlling horizon
    rx, ry, rz = stats.rankdata(Ts[c]), stats.rankdata(Ts.fail_rate), stats.rankdata(Ts.H)
    ex = rx - np.polyval(np.polyfit(rz, rx, 1), rz); ey = ry - np.polyval(np.polyfit(rz, ry, 1), rz)
    pr = np.corrcoef(ex, ey)[0, 1]; n = len(Ts); tstat = pr * np.sqrt((n - 3) / (1 - pr ** 2)); pp = 2 * stats.t.sf(abs(tstat), n - 3)
    out6[c] = dict(auc_fragile=round(auc, 3), mw_p=float(mw_.pvalue), rho_failrate=round(rho.statistic, 3), rho_p=float(rho.pvalue), partial_rho_given_H=round(pr, 3), partial_p=float(pp))
    print(f"{c:18s} AUC(fragile vs robust)={auc:.3f} MW p={mw_.pvalue:.3g} | Spearman w/ failure rate (n={n}) rho={rho.statistic:.3f} p={rho.pvalue:.3g} | partial|H rho={pr:.3f} p={pp:.3g}")
print(f"n fragile={y.sum()}, robust={(1-y).sum()}")
# bootstrap CI for AUC of max_nlltok_tool and max_nlltok
for c in ["max_nlltok", "max_nlltok_tool", "H", "ol_survival"]:
    bs = []
    for b in range(2000):
        ix = rng.integers(0, len(g2), len(g2)); yy = y.values[ix]
        if yy.min() == yy.max(): continue
        s = g2[c].values[ix] * (-1 if c == "ol_survival" else 1); bs.append(roc_auc_score(yy, s))
    print(f"AUC {c}: bootstrap 95% CI [{np.percentile(bs,2.5):.3f}, {np.percentile(bs,97.5):.3f}]")
    out6[c]["auc_ci"] = np.percentile(bs, [2.5, 97.5]).tolist()
res["q6"] = out6
res["q6_groups"] = Ts.group.value_counts().to_dict()
Ts.to_csv(OUT / "task_table.csv", index=False)
# success-count dispersion across 18 checkpoints vs binomial (is failure a property of the task?)
p = Ts.nq.mean() / 18
print("BF16-solved tasks: var(#ckpts solving)=%.2f vs binomial var=%.2f (overdispersion => task-determined)" % (Ts.nq.var(), 18 * p * (1 - p)))
# within-arm (draw-to-draw) vs between-arm agreement on task success, all 85 tasks
M = C.pivot_table(index=["domain", "task_id"], columns="ck", values="q_success").astype(float)[CK].values
w, bb = [], []
for i in range(18):
    for j in range(i + 1, 18):
        ph = np.corrcoef(M[:, i], M[:, j])[0, 1]
        (w if CK[i].rsplit("_", 1)[0] == CK[j].rsplit("_", 1)[0] else bb).append(ph)
print("task-success phi between checkpoints: within-arm %.3f (n=%d) vs between-arm %.3f (n=%d)" % (np.mean(w), len(w), np.mean(bb), len(bb)))
res["q6_success_phi"] = (np.mean(w), np.mean(bb))
# agreement with BF16
bfv = C.pivot_table(index=["domain", "task_id"], columns="ck", values="bf16_success").astype(float)[CK[0]].values
print("phi(ckpt success, BF16 success): mean %.3f" % np.mean([np.corrcoef(M[:, i], bfv)[0, 1] for i in range(18)]))

print("\n=== Q7: recovery after a tool divergence ===")
D = C[C.t_tool.notna()].copy(); D["tn"] = D.t_tool / D.H_fp
D["early"] = D.tn < 0.5
def clus_ci(df, col="q_success", B=3000):
    gi = list(df.groupby(["domain", "task_id"]).indices.values()); vals = df[col].astype(float).values; bs = []
    for b in range(B):
        ix = np.concatenate([gi[k] for k in rng.integers(0, len(gi), len(gi))]); bs.append(vals[ix].mean())
    return np.percentile(bs, [2.5, 97.5])
def summ(df, lab):
    ci = clus_ci(df); print(f"{lab:55s} n={len(df):4d} tasks={df.task_id.nunique():3d} success={df.q_success.mean():.3f} [{ci[0]:.3f},{ci[1]:.3f}]")
    return dict(n=len(df), success=float(df.q_success.mean()), ci=ci.tolist())
o7 = {}
B1 = D[D.bf16_success]; B0 = D[~D.bf16_success]
o7["all_bf16solved_div"] = summ(B1, "BF16-solved, diverged (any t_tool)")
o7["nodiv_bf16solved"] = summ(C[C.t_tool.isna() & C.bf16_success], "BF16-solved, no tool divergence")
o7["bf16failed_div"] = summ(B0, "BF16-failed, diverged (rescue rate)")
o7["early"] = summ(B1[B1.early], "BF16-solved, early divergence (t_tool/H<0.5)")
o7["late"] = summ(B1[~B1.early], "BF16-solved, late divergence (t_tool/H>=0.5)")
# early-late difference with task-cluster bootstrap (tasks contributing to both)
tasks = B1[["domain", "task_id"]].drop_duplicates().apply(tuple, axis=1).tolist(); gi = B1.groupby(["domain", "task_id"]).indices
diffs = []
for b in range(3000):
    ix = np.concatenate([gi[tasks[k]] for k in rng.choice(len(tasks), len(tasks))]); sub = B1.iloc[ix]
    e, l = sub[sub.early].q_success.mean(), sub[~sub.early].q_success.mean(); diffs.append(l - e)
print("late - early recovery: %.3f, task-cluster 95%% CI [%.3f, %.3f]" % (B1[~B1.early].q_success.mean() - B1[B1.early].q_success.mean(), *np.percentile(diffs, [2.5, 97.5])))
o7["late_minus_early_ci"] = np.percentile(diffs, [2.5, 97.5]).tolist()
# logistic-free: recovery by t_tool tertile, and by H (long vs short)
B1 = B1.assign(tn_bin=pd.cut(B1.tn, [-0.01, 0.2, 0.4, 0.6, 0.8, 1.01]))
print(B1.groupby("tn_bin", observed=True).q_success.agg(["mean", "size"]).round(3).to_string())
B1 = B1.assign(long=B1.H_fp > 11)
print(B1.groupby(["long", "early"]).q_success.agg(["mean", "size"]).round(3).to_string())
print("by arm (BF16-solved, diverged):"); print(B1.groupby("arm").q_success.agg(["mean", "size"]).round(3).to_string())
print("by arm x early:"); print(B1.pivot_table(index="arm", columns="early", values="q_success", aggfunc="mean").round(3).to_string())
# by type of divergence
def qf(c):
    return "Q write" if c == "T:write" else "Q read/lookup" if c in ("T:read", "T:identity", "T:calculate") else "Q ended" if c == "END" else "Q transfer" if c == "T:transfer" else "Q text"
def ff(c):
    return "BF16 write" if c == "T:write" else "BF16 read/lookup" if c in ("T:read", "T:identity", "T:calculate") else "BF16 ended" if c == "END" else "BF16 transfer" if c == "T:transfer" else "BF16 text"
B1 = B1.assign(qf=B1.q_tool_cat.map(qf), ff=B1.fp_tool_cat.map(ff))
print("recovery by (BF16 action, Q action) at t_tool:"); print(B1.groupby(["ff", "qf"]).q_success.agg(["mean", "size"]).round(3).to_string())
print("recovery when divergence is on the exact BF16 state (t_tool<t_context) vs after rewording drift:")
print(B1.groupby("tool_at_same_ctx").q_success.agg(["mean", "size"]).round(3).to_string())
res["q7"] = o7

print("\n=== extra: after the first rewording (t_render=0), is the user simulator's next reply identical? ===")
same = []; n = 0
for r in C[C.t_render == 0].itertuples():
    qt = TR[(r.ck, r.domain)][r.task_id]["messages"]; bt = TB[r.domain][r.task_id]["messages"]
    def first_user_after_agent(ms, k):
        # messages: assistant greeting, user, then agent decisions; find user message following the (k+1)-th agent generated message
        cnt = -1
        for i, m in enumerate(ms):
            if m["role"] == "assistant" and i > 0: cnt += 1
            if cnt == k and m["role"] == "user" and i > 0: return m["content"]
        return None
    a, b = first_user_after_agent(qt, 0), first_user_after_agent(bt, 0)
    if a is None or b is None: continue
    n += 1; same.append(a == b)
print("user reply after step 0 identical to BF16's: %.3f (n=%d)" % (np.mean(same), n))
res["user_reply_same_after_step0"] = (float(np.mean(same)), n)
json.dump(res, open(OUT / "res_a567.json", "w"), indent=1, default=float)
