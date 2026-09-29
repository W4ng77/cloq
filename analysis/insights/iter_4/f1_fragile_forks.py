"""f1: are a model's fragile tasks the ones whose BF16 trajectories pass near-tied decision forks?

Fork margin. For every null draw of the reference checkpoint (U nonce draws + K canonical bf16/bf16_eager), per task:
  n_dec      number of agent decisions
  tie_rate   fraction of decisions whose FIRST-token BF16 margin (top-1 minus runner-up logprob, token_margins[0]) < 1;
             the first token is where the act-vs-talk fork is decided (<tool_call> vs text)
  tie_act / tie_talk   the same restricted to tool-call / text decisions
  min_first  minimum first-token margin over the trajectory
  tok_tie    fraction of ALL completion tokens with margin < 1 (non-fork control)
averaged over the null draws (tasks are the unit).
Fragility. Perturbed draws = nonce-stratum checkpoints (quant + Gaussian fixed) outside the floor/small dose groups.
On null-robust tasks (every U draw succeeds) break = mean over perturbed draws of (1 - y); on null-fail tasks (every U
draw fails) fix = mean of y.
Declared F1 (common4.DECLARED): partial Spearman(tie_rate, break | n_dec) per model, pooled as the task-count-weighted
mean over models; null = permutation of break across tasks within each model (B = CLOQ_B, default 20000), one-sided.
Exploratory: selection check over ALL tasks (null-robust tasks are robust to their own ties by construction):
tie_rate vs nonce-null coin-ness pU (1 - pU) and vs perturbed turnover |mean_P y - pU|, partial on n_dec, pooled with
within-model permutation (B/4); raw Spearman; tie_act, tie_talk, min_first (sign flipped), tok_tie; fix on null-fail tasks; cross-model
transfer (does model A's tie_rate predict model B's break on the same task, partial on B's n_dec).
Usage: CLOQ_SNAPSHOT=<manifest> [CLOQ_TAG=live_<id>] python f1_fragile_forks.py -> out/f1_fragile_forks_<tag>.json
"""
import os
import sys

import numpy as np
from scipy.stats import rankdata, spearmanr

from common4 import MODELS, dose_group, dump, model_data, rnd, ymat

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "iter_2"))
from common import load_many  # noqa: E402

B = int(os.environ.get("CLOQ_B", 20000))
rng = np.random.default_rng(20261002)


def pspear(x, y, z):
    rx, ry, rz = (rankdata(v) for v in (x, y, z))
    Z = np.c_[np.ones_like(rz), rz]
    ex = rx - Z @ np.linalg.lstsq(Z, rx, rcond=None)[0]
    ey = ry - Z @ np.linalg.lstsq(Z, ry, rcond=None)[0]
    return float(np.corrcoef(ex, ey)[0, 1])


def task_forks(null_runs, tasks):
    dec = load_many(null_runs)
    keys = ("n_dec", "tie_rate", "tie_act", "tie_talk", "min_first", "tok_tie")
    acc = {k: np.full((len(null_runs), len(tasks)), np.nan) for k in keys}
    idx = {t: i for i, t in enumerate(tasks)}
    for ri, r in enumerate(null_runs):
        per = {}
        for (d, t, i), v in dec[r].items():
            if not v["m"]:
                continue
            per.setdefault((d, t), []).append((v["m"][0] if v["m"][0] is not None else np.nan, v["kind"],
                                               np.array([x for x in v["m"] if x is not None], float)))
        for key, lst in per.items():
            if key not in idx:
                continue
            j = idx[key]
            fm = np.array([x[0] for x in lst], float)
            act = np.array([x[1] == "tool" for x in lst])
            toks = np.concatenate([x[2] for x in lst])
            acc["n_dec"][ri, j] = len(lst)
            acc["tie_rate"][ri, j] = np.mean(fm < 1)
            acc["tie_act"][ri, j] = np.mean(fm[act] < 1) if act.any() else np.nan
            acc["tie_talk"][ri, j] = np.mean(fm[~act] < 1) if (~act).any() else np.nan
            acc["min_first"][ri, j] = np.nanmin(fm)
            acc["tok_tie"][ri, j] = np.mean(toks < 1) if len(toks) else np.nan
    return {k: np.nanmean(v, 0) for k, v in acc.items()}


def main():
    res = {"B": B, "models": {}}
    per_model = {}
    per_model_all = {}
    for m in MODELS:
        D = model_data(m)
        meta, Y, U, K = D["meta"], D["Y"], D["U"], D["K"]
        pert = sorted(r for u, rs in D["units"].items() for r in rs if dose_group(meta[rs[0]]) not in ("floor", "small"))
        tasks = [t for t in D["tasks"] if all(t in Y[r] for r in U)]
        yU = ymat(Y, U, tasks)
        yP = ymat(Y, pert, tasks)
        ok, fl = yU.min(0) == 1, yU.max(0) == 0
        brk = np.nanmean(1 - yP, 0)
        fix = np.nanmean(yP, 0)
        fk = task_forks(U + K, tasks)
        o = dict(n_tasks=len(tasks), n_ok=int(ok.sum()), n_fail=int(fl.sum()), n_pert_draws=len(pert),
                 bf16_fork_ties=dict(mean_tie_rate=rnd(np.nanmean(fk["tie_rate"]), 3), mean_tie_act=rnd(np.nanmean(fk["tie_act"]), 3),
                                     mean_tie_talk=rnd(np.nanmean(fk["tie_talk"]), 3),
                                     frac_tasks_with_any_tie=rnd(np.nanmean(fk["min_first"] < 1), 3),
                                     mean_n_dec=rnd(np.nanmean(fk["n_dec"]), 2)))
        sel = ok & np.isfinite(fk["tie_rate"])
        o["F1_partial"] = rnd(pspear(fk["tie_rate"][sel], brk[sel], fk["n_dec"][sel]), 3)
        ex = {}
        for k in ("tie_rate", "tie_act", "tie_talk", "tok_tie", "n_dec"):
            s2 = sel & np.isfinite(fk[k])
            ex[f"raw_{k}~break"] = rnd(spearmanr(fk[k][s2], brk[s2])[0], 3)
            if k != "n_dec":
                ex[f"partial_{k}~break|n_dec"] = rnd(pspear(fk[k][s2], brk[s2], fk["n_dec"][s2]), 3)
        ex["partial_-min_first~break|n_dec"] = rnd(pspear(-fk["min_first"][sel], brk[sel], fk["n_dec"][sel]), 3)
        sf = fl & np.isfinite(fk["tie_rate"])
        ex["partial_tie_rate~fix|n_dec (null-fail tasks)"] = rnd(pspear(fk["tie_rate"][sf], fix[sf], fk["n_dec"][sf]), 3) if sf.sum() > 5 else None
        # selection check: null-robust tasks are, by construction, robust to whatever ties they pass. Over ALL tasks,
        # does tie_rate predict nonce-null instability (pU (1 - pU)) and perturbed turnover |mean_P y - mean_U y|?
        pU = yU.mean(0)
        sa = np.isfinite(fk["tie_rate"])
        ex["partial_tie_rate~null_coin pU(1-pU)|n_dec (all tasks)"] = rnd(pspear(fk["tie_rate"][sa], (pU * (1 - pU))[sa], fk["n_dec"][sa]), 3)
        turn = np.abs(np.nanmean(yP, 0) - pU)
        ex["partial_tie_rate~turnover |pP-pU||n_dec (all tasks)"] = rnd(pspear(fk["tie_rate"][sa], turn[sa], fk["n_dec"][sa]), 3)
        ex["raw_n_dec~turnover (all tasks)"] = rnd(spearmanr(fk["n_dec"][sa], turn[sa])[0], 3)
        per_model_all[m] = dict(tie=fk["tie_rate"][sa], ndec=fk["n_dec"][sa], turn=turn[sa], coin=(pU * (1 - pU))[sa])
        o["exploratory"] = ex
        res["models"][m] = o
        per_model[m] = dict(tasks=tasks, sel=sel, tie=fk["tie_rate"], ndec=fk["n_dec"], brk=brk, ok=ok)
        print(m, o)
    # pooled permutation
    obs = sum(per_model[m]["sel"].sum() * res["models"][m]["F1_partial"] for m in per_model) / sum(per_model[m]["sel"].sum() for m in per_model)
    null = np.zeros(B)
    for b in range(B):
        num = den = 0.0
        for m, v in per_model.items():
            s = v["sel"]
            num += s.sum() * pspear(v["tie"][s], rng.permutation(v["brk"][s]), v["ndec"][s]); den += s.sum()
        null[b] = num / den
    res["pooled"] = dict(F1=rnd(obs, 3), p=float((1 + np.sum(null >= obs)) / (1 + B)), perm_q95=rnd(np.quantile(null, .95), 3))
    print("pooled", res["pooled"])
    # exploratory pooled permutation for the all-task turnover and null-coin versions
    for key in ("turn", "coin"):
        obs2 = sum(len(v["tie"]) * pspear(v["tie"], v[key], v["ndec"]) for v in per_model_all.values()) / sum(len(v["tie"]) for v in per_model_all.values())
        nl = np.array([sum(len(v["tie"]) * pspear(v["tie"], rng.permutation(v[key]), v["ndec"]) for v in per_model_all.values())
                       / sum(len(v["tie"]) for v in per_model_all.values()) for _ in range(B // 4)])
        res[f"pooled_all_tasks_tie_rate~{key}|n_dec"] = dict(rho=rnd(obs2, 3), p_one_sided=float((1 + np.sum(nl >= obs2)) / (1 + len(nl))))
        print("pooled all-task", key, res[f"pooled_all_tasks_tie_rate~{key}|n_dec"])
    # cross-model transfer (exploratory)
    cross = {}
    for a in per_model:
        for b in per_model:
            if a == b:
                continue
            A, Bm = per_model[a], per_model[b]
            common = [t for t in Bm["tasks"] if t in A["tasks"]]
            ia = np.array([A["tasks"].index(t) for t in common]); ib = np.array([Bm["tasks"].index(t) for t in common])
            s = Bm["sel"][ib] & np.isfinite(A["tie"][ia])
            cross[f"{a}->{b}"] = rnd(pspear(A["tie"][ia][s], Bm["brk"][ib][s], Bm["ndec"][ib][s]), 3)
    res["cross_model_partial"] = cross
    res["cross_model_mean"] = rnd(np.mean(list(cross.values())), 3)
    print("cross-model mean", res["cross_model_mean"])
    res["primary"] = dict(test="F1", p=res["pooled"]["p"], rho=res["pooled"]["F1"])
    dump("f1_fragile_forks", res)


if __name__ == "__main__":
    main()
