import pickle, numpy as np, pandas as pd
from pathlib import Path
from scipy import stats
OUT = Path(__file__).resolve().parent
S = pickle.load(open(OUT / "S_with_flip.pkl", "rb"))
g = S.groupby("cat").agg(n=("idx", "size"), bf16_nlltok_median=("nlltok", "median"), flip_full=("flip_full", "mean"), flip_beh=("flip_beh", "mean"),
                         frac_lowconf=("nlltok", lambda v: np.mean(v > 0.0055)))
print(g.round(4).to_string())
t = S[S.kind == "tool"].copy(); t["is_write"] = t.cat == "T:write"
print("tool states: write vs non-write flip:", t.groupby("is_write").flip_full.mean().round(3).to_dict(), stats.mannwhitneyu(t[t.is_write].flip_full, t[~t.is_write].flip_full).pvalue)
# within write states, does NLL still predict?
w = t[t.is_write]; print("write states Spearman flip vs nlltok: %.3f p=%.2g n=%d" % (*stats.spearmanr(w.nlltok, w.flip_full), len(w)))
# truncated contexts in BF16 states: flip rate
print("BF16 state truncated vs not, tool flip:", t.groupby("truncated").flip_full.agg(["mean", "size"]).round(3).to_dict())
print("BF16 state truncated vs not, all behavioural flip:", S.groupby("truncated").flip_beh.agg(["mean", "size"]).round(3).to_dict())
t["nb"] = pd.qcut(t.nlltok.rank(method="first"), 4, labels=False)
print(t.pivot_table(index="nb", columns="truncated", values="flip_full", aggfunc=["mean", "size"]).round(3).to_string())
# Mantel-Haenszel-like: mean within-stratum difference weighted by n
diffs = []; ws = []
for k, gg in t.groupby("nb"):
    a, b = gg[gg.truncated].flip_full, gg[~gg.truncated].flip_full
    if len(a) and len(b): diffs.append(a.mean() - b.mean()); ws.append(min(len(a), len(b)))
print("NLL-stratified truncated-minus-not flip difference: %.3f" % np.average(diffs, weights=ws))
print("Spearman nlltok vs truncated (tool):", stats.spearmanr(t.nlltok, t.truncated).statistic.round(3), " idx vs truncated:", stats.spearmanr(t.idx, t.truncated).statistic.round(3))
