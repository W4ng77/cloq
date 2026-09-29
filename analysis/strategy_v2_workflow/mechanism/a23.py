"""Q2 divergence anatomy, Q3 open-loop margin hypothesis."""
import pickle, json, os
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats
os.environ["CUDA_VISIBLE_DEVICES"] = ""
OUT = Path(__file__).resolve().parent
d = pickle.load(open(OUT / "tables.pkl", "rb")); S, C, CK, ARMS = d["S"], d["C"], d["CKPTS"], d["ARMS"]
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
res = {}

print("=== Q2: divergence anatomy ===")
print("n rows", len(C), "tool_diverged", C.t_tool.notna().sum(), " no tool divergence", C.t_tool.isna().sum())
print("t_context distribution:", C.t_context.value_counts().sort_index().to_dict())
print("t_tool on identical context (t_tool < t_context):", (C.tool_at_same_ctx).sum(), "/", C.t_tool.notna().sum())
print("BF16 category at t_render (the decision that split the context):")
print(C.fp_rend_cat.value_counts().to_dict())
Dv = C[C.t_tool.notna()].copy()
Dv["pair"] = Dv.fp_tool_cat + " -> " + Dv.q_tool_cat
print("\nBF16 action at t_tool:"); print(Dv.fp_tool_cat.value_counts().to_dict())
print("Quantized action at t_tool:"); print(Dv.q_tool_cat.value_counts().to_dict())
print("\nTop transitions:"); print(Dv.pair.value_counts().head(20).to_string())
# coarse families
def fam(c):
    if c in ("T:write",): return "BF16 write"
    if c in ("T:identity", "T:read", "T:calculate"): return "BF16 read/lookup"
    if c == "T:transfer": return "BF16 transfer"
    if c == "END": return "BF16 ended"
    if c == "X:confirm_q": return "BF16 confirm-question"
    return "BF16 other text"
def qfam(c):
    if c == "T:write": return "Q write"
    if c in ("T:identity", "T:read", "T:calculate"): return "Q read/lookup"
    if c == "T:transfer": return "Q transfer"
    if c == "END": return "Q ended"
    if c == "X:confirm_q": return "Q confirm-question"
    return "Q other text"
Dv["ff"] = Dv.fp_tool_cat.map(fam); Dv["qf"] = Dv.q_tool_cat.map(qfam)
ct = pd.crosstab(Dv.ff, Dv.qf, margins=True); print("\nfamily transition (all 18 ckpts):"); print(ct.to_string())
# same-kind tool mismatch: same tool name different args vs different tool
tt = Dv[(Dv.fp_tool_kind == "tool") & (Dv.q_tool_kind == "tool")]
print("\nboth tool at t_tool: n", len(tt), " same tool name(s), different args:", (tt.fp_tool_names == tt.q_tool_names).sum())
# by arm
arm_tab = pd.crosstab(Dv.arm, Dv.ff)
print("\nBF16 family at t_tool by arm (counts):"); print(arm_tab.to_string())
chi = stats.chi2_contingency(arm_tab.values); print("chi2 arm x BF16-family: chi2=%.2f dof=%d p=%.3f (obs not independent: same tasks)" % (chi[0], chi[2], chi[1]))
arm_tab2 = pd.crosstab(Dv.arm, Dv.qf); print("\nQ family at t_tool by arm:"); print(arm_tab2.to_string())
chi2 = stats.chi2_contingency(arm_tab2.values); print("chi2 arm x Q-family: chi2=%.2f dof=%d p=%.3f" % (chi2[0], chi2[2], chi2[1]))
# permutation test of arm x family independence, permuting arm labels among the 6 arms within (task, draw) -> keeps task structure
rng = np.random.default_rng(0)
def chistat(df, col):
    return stats.chi2_contingency(pd.crosstab(df.arm, df[col]).values)[0]
def chi_np(a_codes, c_codes, na, nc):
    T = np.zeros((na, nc)); np.add.at(T, (a_codes, c_codes), 1)
    E = T.sum(1, keepdims=True) * T.sum(0, keepdims=True) / T.sum(); m = E > 0
    return (((T - E) ** 2)[m] / E[m]).sum()
grp = Dv.groupby(["domain", "task_id", "draw"]).indices
a_codes0 = pd.Categorical(Dv.arm).codes
for col in ["ff", "qf"]:
    cc = pd.Categorical(Dv[col]).codes; na, nc = a_codes0.max() + 1, cc.max() + 1
    obs = chi_np(a_codes0, cc, na, nc); cnt = 0; B = 2000
    for b in range(B):
        a2 = a_codes0.copy()
        for ix in grp.values():
            a2[ix] = rng.permutation(a2[ix])
        cnt += chi_np(a2, cc, na, nc) >= obs
    print(f"permutation (arm labels shuffled within task x draw) chi2={obs:.2f} p for arm x {col}: {(cnt+1)/(B+1):.3f}")
    res[f"q2_perm_p_{col}"] = (cnt + 1) / (B + 1)
print("\nmedian t_tool / H_fp by arm:", Dv.assign(n=Dv.t_tool / Dv.H_fp).groupby("arm").n.median().round(3).to_dict())
res["q2_fp_family"] = Dv.ff.value_counts().to_dict(); res["q2_q_family"] = Dv.qf.value_counts().to_dict()
res["q2_transition"] = {f"{a}|{b}": int(v) for (a, b), v in pd.crosstab(Dv.ff, Dv.qf).stack().items()}

# truncation at the tool divergence step
x = Dv[Dv.q_trunc_at_ttool.notna()]
print("\nQ context truncated at t_tool: %.3f (n=%d); fraction of all Q decisions truncated (mean over runs): %.3f" %
      (x.q_trunc_at_ttool.astype(float).mean(), len(x), C.q_trunc_frac_all.mean()))
print("t_tool before first Q truncation: %.3f" % np.mean([(r.q_trunc_first is None or np.isnan(r.q_trunc_first) or r.t_tool < r.q_trunc_first) for r in x.itertuples()]))

print("\n=== Q3: open-loop flip vs BF16 confidence ===")
S["flip_full"] = 1 - S[[f"fam__{c}" for c in CK]].astype(float).mean(1)
S["flip_beh"] = S[[f"bflip__{c}" for c in CK]].astype(float).mean(1)
S["n_beh"] = S[[f"bflip__{c}" for c in CK]].astype(int).sum(1)
S["n_full"] = 18 - S[[f"fam__{c}" for c in CK]].astype(int).sum(1)
S["q_nll_mean"] = S[[f"qnll__{c}" for c in CK]].mean(1)
tool = S[S.kind == "tool"]; text = S[S.kind == "text"]
print("states: %d (tool %d, text %d); rendered!=generated excluded? no (n=%d)" % (len(S), len(tool), len(text), (~S.rend_eq).sum()))
print("mean full-action flip rate: tool %.3f text %.3f ; behavioural flip: tool %.3f text %.3f" %
      (tool.flip_full.mean(), text.flip_full.mean(), tool.flip_beh.mean(), text.flip_beh.mean()))
out3 = {}
for nm, sub, col in [("tool_exact_flip", tool, "flip_full"), ("text_exact_flip", text, "flip_full"),
                     ("text_beh_flip(text->tool)", text, "flip_beh"), ("all_beh_flip", S, "flip_beh")]:
    for x in ["nlltok", "nll"]:
        r = stats.spearmanr(sub[x], sub[col]); out3[f"{nm}~{x}"] = (round(r.statistic, 3), float(r.pvalue), len(sub))
        print(f"Spearman {nm} vs BF16 {x}: rho={r.statistic:.3f} p={r.pvalue:.2g} n={len(sub)}")
# partial: text flip vs nll controlling length
for nm, sub in [("tool", tool), ("text", text)]:
    rx = stats.rankdata(sub.nlltok); ry = stats.rankdata(sub.flip_full); rz = stats.rankdata(sub.ntok)
    ex = rx - np.polyval(np.polyfit(rz, rx, 1), rz); ey = ry - np.polyval(np.polyfit(rz, ry, 1), rz)
    print(f"partial Spearman ({nm}) flip_full vs nlltok | ntok: {np.corrcoef(ex, ey)[0,1]:.3f}; flip vs ntok rho={stats.spearmanr(sub.ntok, sub.flip_full).statistic:.3f}")
res["q3_spearman"] = out3
# binned tables
for nm, sub, cols in [("TOOL states", tool, ["flip_full"]), ("TEXT states", text, ["flip_full", "flip_beh"])]:
    sub = sub.copy(); sub["bin"] = pd.qcut(sub.nlltok, 5, labels=False, duplicates="drop")
    g = sub.groupby("bin").agg(n=("nlltok", "size"), nlltok_lo=("nlltok", "min"), nlltok_hi=("nlltok", "max"),
                               **{c: (c, "mean") for c in cols}, frac_all18_agree=("n_full", lambda v: np.mean(v == 0)),
                               frac_state_flips_in_ge9=("n_full", lambda v: np.mean(v >= 9)))
    print(f"\n{nm}: quintiles of BF16 NLL/token"); print(g.round(4).to_string())
    res[f"q3_bins_{nm}"] = g.round(4).reset_index().to_dict("records")
# decile table for tool states with extreme top
tool2 = tool.copy(); tool2["bin"] = pd.qcut(tool2.nlltok, 10, labels=False, duplicates="drop")
print("\nTOOL deciles:"); print(tool2.groupby("bin").agg(n=("nlltok", "size"), hi=("nlltok", "max"), flip=("flip_full", "mean")).round(4).to_string())
# AUC of BF16 nlltok for 'state ever flips (>=1 of 18)' and for 'state flips in majority'
from sklearn.metrics import roc_auc_score
for nm, sub in [("tool", tool), ("text-beh", text)]:
    col = "n_full" if nm == "tool" else "n_beh"
    for thr in [1, 9]:
        y = (sub[col] >= thr).astype(int)
        if 0 < y.sum() < len(y):
            print(f"AUC BF16 nlltok -> {nm} flips in >= {thr}/18: {roc_auc_score(y, sub.nlltok):.3f} (pos {y.sum()}/{len(y)})")
            res[f"q3_auc_{nm}_ge{thr}"] = round(roc_auc_score(y, sub.nlltok), 3)

# overdispersion: are flips a property of the state (shared across checkpoints) or checkpoint-specific?
print("\n--- flip-count distribution across 18 checkpoints (tool states, exact tool-call flip) ---")
M = 1 - tool[[f"fam__{c}" for c in CK]].astype(int).values  # states x 18
p_ck = M.mean(0)
# null: independent flips with per-checkpoint rate -> Poisson-binomial on counts
sim = (rng.random((20000, 18)) < p_ck).sum(1)
obs_hist = np.bincount(M.sum(1), minlength=19) / len(M); null_hist = np.bincount(sim, minlength=19) / len(sim)
print("count k:   ", list(range(19)))
print("observed:  ", np.round(obs_hist, 3).tolist())
print("indep null:", np.round(null_hist, 3).tolist())
res["q3_tool_flipcount_obs"] = np.round(obs_hist, 4).tolist(); res["q3_tool_flipcount_null"] = np.round(null_hist, 4).tolist()
print("var of per-state count obs %.2f vs null %.2f" % (M.sum(1).var(), sim.var()))
# pairwise agreement within arm vs between arm (phi on flip indicators, tool states) and text behavioural flips
def pair_stats(Mat):
    names = CK; phi_w, phi_b = [], []
    for i in range(18):
        for j in range(i + 1, 18):
            a, b = Mat[:, i], Mat[:, j]
            if a.std() == 0 or b.std() == 0: continue
            ph = np.corrcoef(a, b)[0, 1]
            (phi_w if names[i].rsplit("_", 1)[0] == names[j].rsplit("_", 1)[0] else phi_b).append(ph)
    return np.mean(phi_w), len(phi_w), np.mean(phi_b), len(phi_b)
pw = pair_stats(M); print("tool-state exact flips: mean phi within-arm pairs %.3f (n=%d) vs between-arm pairs %.3f (n=%d)" % pw)
Mb = S[[f"bflip__{c}" for c in CK]].astype(int).values
pb = pair_stats(Mb); print("all-state behavioural flips: phi within %.3f (n=%d) vs between %.3f (n=%d)" % pb)
res["q3_phi_tool"] = pw; res["q3_phi_beh"] = pb
# Jaccard of flip sets between checkpoints
J = []
for i in range(18):
    for j in range(i + 1, 18):
        a, b = M[:, i].astype(bool), M[:, j].astype(bool); J.append((a & b).sum() / max(1, (a | b).sum()))
print("tool exact-flip set Jaccard between checkpoints: mean %.3f range [%.3f, %.3f]; per-ckpt flip rate range [%.3f, %.3f]" % (np.mean(J), min(J), max(J), p_ck.min(), p_ck.max()))
# per-arm tool flip rate
print("per-arm open-loop tool exact flip rate:", {a: round(float(np.mean([p_ck[CK.index(f"{a}_{dd}")] for dd in ['c1','c2','c3']])), 4) for a in ARMS})
# does quantized-model perturbation (Q NLL on BF16 action) add beyond BF16 margin? logistic on tool states, long format
from sklearn.linear_model import LogisticRegression
rows = []
for c in CK:
    rows.append(pd.DataFrame({"flip": 1 - tool[f"fam__{c}"].astype(int).values, "lb": np.log(tool.nlltok.values + 1e-6),
                              "dq": ((tool[f"qnll__{c}"] - tool.nll) / tool.ntok).values, "state": np.arange(len(tool))}))
L = pd.concat(rows, ignore_index=True)
def fitc(df, cols):
    m = LogisticRegression(C=1e6, max_iter=2000).fit(df[cols].values, df.flip.values); return m.coef_[0]
coef = fitc(L, ["lb"]); bs = []
ids = np.arange(len(tool)); gi = L.groupby("state").indices
for b in range(200):
    samp = rng.choice(ids, len(ids)); ix = np.concatenate([gi[k] for k in samp]); bs.append(fitc(L.iloc[ix], ["lb"])[0])
print("\nlogit(tool flip) ~ log BF16 nll/tok: coef %.3f, state-cluster bootstrap 95%% CI [%.3f, %.3f], n=%d rows / %d states" % (coef[0], *np.percentile(bs, [2.5, 97.5]), len(L), len(tool)))
res["q3_logit_lb"] = (float(coef[0]), *map(float, np.percentile(bs, [2.5, 97.5])))
pickle.dump(S, open(OUT / "S_with_flip.pkl", "wb"))
json.dump(res, open(OUT / "res_a23.json", "w"), indent=1, default=float)
