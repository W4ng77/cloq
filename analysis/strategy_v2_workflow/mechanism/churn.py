"""Churn: is a quantized checkpoint's closed-loop outcome a small degradation or a re-roll? Is BF16 exchangeable with the 18 quantized members?"""
import pickle, json, numpy as np, pandas as pd
from pathlib import Path
from scipy import stats
OUT = Path(__file__).resolve().parent
d = pickle.load(open(OUT / "tables.pkl", "rb")); C, CK = d["C"], d["CKPTS"]
rng = np.random.default_rng(3)
M = C.pivot_table(index=["domain", "task_id"], columns="ck", values="q_success").astype(float)[CK]
bf = C.groupby(["domain", "task_id"]).bf16_success.first().astype(float).loc[M.index]
H = C.groupby(["domain", "task_id"]).H_fp.first().loc[M.index]
res = {}
for lab, mask in [("all", np.ones(len(M), bool)), ("long(H>11)", (H > 11).values), ("short", (H <= 11).values)]:
    Mm, b = M.values[mask], bf.values[mask]
    lost = ((b[:, None] == 1) & (Mm == 0)).sum(); gained = ((b[:, None] == 0) & (Mm == 1)).sum()
    nS = (b == 1).sum() * 18; nF = (b == 0).sum() * 18
    print(f"{lab}: tasks={mask.sum()} BF16 success={b.mean():.3f} mean Q success={Mm.mean():.3f} (ckpt range {Mm.mean(0).min():.3f}-{Mm.mean(0).max():.3f}); "
          f"lost {lost}/{nS} ({lost/nS:.3f}) gained {gained}/{nF} ({gained/nF:.3f}); net loss per task-ckpt {(lost-gained)/(18*mask.sum()):.3f}; gross churn {(lost+gained)/(18*mask.sum()):.3f}")
    res[lab] = dict(tasks=int(mask.sum()), bf16=float(b.mean()), q=float(Mm.mean()), lost=int(lost), nS=int(nS), gained=int(gained), nF=int(nF))
    # exchangeability: rank of BF16 success count among 19 members; and each member's agreement with the rest
    counts = Mm.sum(0); print("   BF16 successes", int(b.sum()), "vs quantized counts", sorted(counts.astype(int).tolist()))
    # agreement of member with the mean of the other members
    allm = np.column_stack([Mm, b])
    def corr_with_rest(i):
        rest = np.delete(allm, i, axis=1).mean(1); return np.corrcoef(allm[:, i], rest)[0, 1] if allm[:, i].std() > 0 else np.nan
    cq = [corr_with_rest(i) for i in range(18)]; cb = corr_with_rest(18)
    print(f"   corr(member, mean of other 18 members): BF16 {cb:.3f}; quantized mean {np.nanmean(cq):.3f} range [{np.nanmin(cq):.3f},{np.nanmax(cq):.3f}]")
    res[lab].update(corr_bf16=float(cb), corr_q_mean=float(np.nanmean(cq)), corr_q_min=float(np.nanmin(cq)), corr_q_max=float(np.nanmax(cq)),
                    bf16_count=int(b.sum()), q_counts=sorted(counts.astype(int).tolist()))
# paired: per-task BF16 success minus mean Q success, task bootstrap
diff = bf.values - M.values.mean(1)
for lab, mask in [("all", np.ones(len(M), bool)), ("long", (H > 11).values)]:
    dd = diff[mask]; bs = [dd[rng.integers(0, len(dd), len(dd))].mean() for _ in range(10000)]
    print(f"BF16 - mean(18 Q) {lab}: {dd.mean():.3f} task-bootstrap 95% CI [{np.percentile(bs,2.5):.3f},{np.percentile(bs,97.5):.3f}] n={mask.sum()}")
    res[f"bf16_minus_q_{lab}"] = (float(dd.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)))
# how much of per-ckpt success variance is task-level vs checkpoint-level: 2-way decomposition on the 85x18 matrix
Y = M.values; gm = Y.mean(); task_eff = Y.mean(1) - gm; ck_eff = Y.mean(0) - gm
ss_task = 18 * (task_eff ** 2).sum(); ss_ck = 85 * (ck_eff ** 2).sum(); ss_tot = ((Y - gm) ** 2).sum()
print(f"variance decomposition of 85x18 success matrix: task {ss_task/ss_tot:.3f}, checkpoint {ss_ck/ss_tot:.3f}, residual (task x ckpt churn) {1-(ss_task+ss_ck)/ss_tot:.3f}")
# arm effect: arm means with the 3 draws, residual check
arm_eff = {a: Y[:, [CK.index(f'{a}_{x}') for x in ['c1','c2','c3']]].mean() for a in d["ARMS"]}
ss_arm = 85 * 3 * sum((v - gm) ** 2 for v in arm_eff.values())
print(f"   of which between-arm {ss_arm/ss_tot:.4f}, within-arm between-draw {(ss_ck-ss_arm)/ss_tot:.4f}")
res["var_decomp"] = dict(task=ss_task/ss_tot, ckpt=ss_ck/ss_tot, arm=ss_arm/ss_tot, resid=1-(ss_task+ss_ck)/ss_tot)
json.dump(res, open(OUT / "res_churn.json", "w"), indent=1, default=float)
