"""Q3: horizon vs truncation as explanations of the BF16-minus-quantized gap."""
import pandas as pd, numpy as np
from pathlib import Path
O = Path(__file__).parent
rng = np.random.default_rng(1)
T = pd.read_csv(O / "tasks.csv", dtype={"task_id": str})
PT = pd.read_csv(O / "per_task_trunc.csv", dtype={"task_id": str})
T = T[T.run.isin(["bf16_v1"] + [r for r in T.run.unique() if r.endswith("_dev")])]
T["fail"] = 1 - T.db_match.astype(float)
bf = T[T.run == "bf16_v1"][["domain", "task_id", "fail"]].rename(columns={"fail": "fail_fp"})
q = T[T.run != "bf16_v1"]
qa = q.groupby(["domain", "task_id"]).fail.mean().rename("fail_q").reset_index()
tr = PT[PT.run == "bf16_v1"][["domain", "task_id", "horizon", "frac_trunc", "n_trunc", "max_pre", "onset", "max_dropped"]]
qtr = PT[PT.run != "bf16_v1"].groupby(["domain", "task_id"]).frac_trunc.mean().rename("frac_trunc_q").reset_index()
X = bf.merge(qa).merge(tr).merge(qtr)
X["gap"] = X.fail_q - X.fail_fp          # quantized failure minus BF16 failure (= BF16 SR - Q SR)
X["long"] = X.horizon > 11
X["airline"] = (X.domain == "airline").astype(float)
X.to_csv(O / "task_level.csv", index=False)
print("N tasks", len(X), "long", X.long.sum())
print("overall gap %.3f; long %.3f (n=%d); short %.3f (n=%d); amplification %.3f" % (
    X.gap.mean(), X[X.long].gap.mean(), X.long.sum(), X[~X.long].gap.mean(), (~X.long).sum(),
    X[X.long].gap.mean() - X[~X.long].gap.mean()))

def boot_mean(v, B=10000):
    v = np.asarray(v); bs = rng.choice(v, (B, len(v))).mean(1)
    return v.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5)

# strata of long tasks by BF16 truncation fraction
L = X[X.long].copy()
med = L[L.frac_trunc > 0].frac_trunc.median()
L["stratum"] = np.where(L.frac_trunc == 0, "0 none", np.where(L.frac_trunc <= med, "1 light", "2 heavy"))
print(f"\nLong tasks stratified by BF16 truncated-decision fraction (light/heavy split at median of truncating tasks = {med:.3f})")
for s, g in L.groupby("stratum"):
    m, lo, hi = boot_mean(g.gap)
    print(f"  {s:8s} n={len(g):2d} horizon med={g.horizon.median():5.1f} frac_trunc mean={g.frac_trunc.mean():.3f} "
          f"BF16 SR={1-g.fail_fp.mean():.3f} Q SR={1-g.fail_q.mean():.3f} gap={m:+.3f} [{lo:+.3f},{hi:+.3f}]")
# difference heavy - (none+light)
h = L[L.stratum == "2 heavy"].gap.values; nl = L[L.stratum != "2 heavy"].gap.values
bs = [rng.choice(h, len(h)).mean() - rng.choice(nl, len(nl)).mean() for _ in range(10000)]
print(f"  heavy - (none+light) gap diff = {h.mean()-nl.mean():+.3f} [{np.percentile(bs,2.5):+.3f},{np.percentile(bs,97.5):+.3f}]")
# permutation test on the heavy vs rest
obs = h.mean() - nl.mean(); allv = np.r_[h, nl]; cnt = 0
for _ in range(10000):
    p = rng.permutation(allv); cnt += abs(p[:len(h)].mean() - p[len(h):].mean()) >= abs(obs)
print(f"  permutation two-sided p = {cnt/10000:.3f}")

# All 85 tasks: 2x2-ish table horizon (long/short) x BF16 truncates (yes/no)
X["trunc_any"] = X.n_trunc > 0
print("\nAll 85 tasks: gap by long x BF16-truncates-at-all")
for (lg, ta), g in X.groupby(["long", "trunc_any"]):
    m, lo, hi = boot_mean(g.gap)
    print(f"  long={lg!s:5s} trunc_any={ta!s:5s} n={len(g):2d} horizon med={g.horizon.median():4.1f} gap={m:+.3f} [{lo:+.3f},{hi:+.3f}]")

# OLS with HC3 + task bootstrap
def ols(df, cols, y="gap"):
    A = np.column_stack([np.ones(len(df))] + [df[c].values.astype(float) for c in cols])
    yv = df[y].values.astype(float)
    b, *_ = np.linalg.lstsq(A, yv, rcond=None)
    e = yv - A @ b
    XtXi = np.linalg.inv(A.T @ A)
    hdiag = np.einsum("ij,jk,ik->i", A, XtXi, A)
    meat = (A * (e / (1 - hdiag))[:, None] ** 2).T @ A if False else A.T @ (A * ((e / (1 - hdiag)) ** 2)[:, None])
    V = XtXi @ meat @ XtXi
    r2 = 1 - (e ** 2).sum() / ((yv - yv.mean()) ** 2).sum()
    return b, np.sqrt(np.diag(V)), r2

def report(df, cols, label, y="gap", B=5000):
    b, se, r2 = ols(df, cols, y)
    bs = []
    for _ in range(B):
        idx = rng.integers(0, len(df), len(df))
        try:
            bs.append(ols(df.iloc[idx], cols, y)[0])
        except np.linalg.LinAlgError:
            pass
    bs = np.array(bs)
    print(f"\n{label}  (n={len(df)}, R2={r2:.3f}, y={y})")
    for j, c in enumerate(["const"] + cols):
        print(f"   {c:14s} b={b[j]:+.4f}  HC3 se={se[j]:.4f}  boot95=[{np.percentile(bs[:,j],2.5):+.4f},{np.percentile(bs[:,j],97.5):+.4f}]")

X["h10"] = X.horizon / 10.0
X["logh"] = np.log(X.horizon)
X["ft"] = X.frac_trunc
X["ftq"] = X.frac_trunc_q
X["pre_k"] = X.max_pre / 1000.0
print("\ncorr(horizon, BF16 frac_trunc) pearson %.3f; corr(logh, ft) %.3f; corr(h, max_pre) %.3f" % (
    X[["horizon", "ft"]].corr().iloc[0, 1], X[["logh", "ft"]].corr().iloc[0, 1], X[["horizon", "max_pre"]].corr().iloc[0, 1]))
for cols in (["h10", "ft"], ["h10"], ["ft"]):
    pass
# VIF
r = np.corrcoef(X.h10, X.ft)[0, 1]; print("VIF (h10, ft) = %.2f" % (1 / (1 - r ** 2)))
report(X, ["h10"], "gap ~ horizon/10")
report(X, ["ft"], "gap ~ BF16 trunc frac")
report(X, ["h10", "ft"], "gap ~ horizon/10 + BF16 trunc frac")
report(X, ["h10", "ft", "airline"], "gap ~ horizon/10 + BF16 trunc frac + airline")
report(X, ["logh", "ft", "airline"], "gap ~ log horizon + BF16 trunc frac + airline")
report(X[X.long], ["h10", "ft"], "LONG ONLY: gap ~ horizon/10 + BF16 trunc frac")
report(X, ["h10", "ftq"], "gap ~ horizon/10 + mean Q trunc frac (post-treatment! mediator, not a control)")
# Also BF16 failure and Q failure separately
report(X, ["h10", "ft", "airline"], "BF16 fail ~ horizon + ft + airline", y="fail_fp")
report(X, ["h10", "ft", "airline"], "Q fail ~ horizon + ft + airline", y="fail_q")

# Residual variation: how much of ft is not explained by horizon?
b = np.polyfit(X.horizon, X.ft, 1); res = X.ft - np.polyval(b, X.horizon)
print("\nft residual sd after linear horizon: %.3f (raw sd %.3f)" % (res.std(), X.ft.std()))
# Among tasks with horizon 12-20 (where both vary), show spread of ft
M = X[(X.horizon >= 12) & (X.horizon <= 20)]
print("horizon 12-20: n=%d, ft range %.2f-%.2f, n(ft==0)=%d" % (len(M), M.ft.min(), M.ft.max(), (M.ft == 0).sum()))

# checkpoint-level: per checkpoint amplification (to show draw spread)
qq = q.merge(X[["domain", "task_id", "fail_fp", "long", "ft"]])
qq["gap"] = qq.fail - qq.fail_fp
amp = qq.groupby(["run", "long"]).gap.mean().unstack()
amp["amp"] = amp[True] - amp[False]
print("\nper-checkpoint long gap / short gap / amplification:")
print(amp.round(3).to_string())
print("amplification mean %.3f sd across 18 ckpts %.3f" % (amp.amp.mean(), amp.amp.std()))
qq["heavy"] = qq.ft > med
a2 = qq[qq.long].groupby(["run", "heavy"]).gap.mean().unstack()
print("per-checkpoint long-task gap heavy vs not: mean diff %.3f, sd %.3f, n ckpts with heavy>not: %d/18" % (
    (a2[True] - a2[False]).mean(), (a2[True] - a2[False]).std(), ((a2[True] - a2[False]) > 0).sum()))
