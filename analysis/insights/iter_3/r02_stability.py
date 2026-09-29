"""r02: is reallocation a deterministic re-dealing by the checkpoint, or a loss of stability (more nonce sensitivity)?

For every fixed checkpoint drawn under >= 2 prompt nonces (quantizer checkpoints n1/n2/q3..q5; fixed Gaussian
controls gauss*_s1_q1/q2) and for the reference model's nonce null U:
  V(m)  = mean over tasks of the unbiased within-checkpoint Bernoulli variance  p_hat(1-p_hat) m/(m-1), m draws;
          for U it is averaged over all m-subsets of U, so both sides use the same m.
          (A) re-dealing: re-drawn tasks become new near-deterministic tasks  -> V_ckpt ~ V_U;
          (B) destabilisation: re-drawn tasks become coins                   -> V_ckpt > V_U.
  concordance of breaks: for tasks always-ok on the reference (all U draws outside the pair), over ordered pairs of
          draws (a, b) of the same checkpoint: P(b fails | a fails) vs the marginal P(fail). 1 = the checkpoint
          decides the break; = marginal = breaks are independent re-rolls. Same for fixes (always-fail tasks).
          The null analogue uses pairs of U draws with the reference = the remaining U draws.
  fate table: for null-always-ok / always-fail tasks (all U draws), the distribution of #successes over the
          checkpoint's m draws (0..m).
Usage: CLOQ_SNAPSHOT=<manifest> python r02_stability.py -> out/r02_stability_<tag>.json
"""
import os
from collections import defaultdict
from itertools import combinations, permutations

import numpy as np

from r_common import dump, load, rnd

MODELS = os.environ.get("CLOQ_MODELS", "q4,q8,q14,q30a3").split(",")
B = 1000
rng = np.random.default_rng(7)


def V(M):
    m = M.shape[0]
    p = M.mean(0)
    return float((p * (1 - p) * m / (m - 1)).mean())


def concord(Ypair_rows, P):
    """Ypair_rows: list of (ya, yb, p_ref) arrays; returns P(b fail|a fail), P(fail), P(b fix|a fix), P(fix)."""
    nf = nff = n_ok = fails = 0
    nx = nxx = n_fl = fixes = 0
    for ya, yb, pr in Ypair_rows:
        ok, fl = pr == 1, pr == 0
        n_ok += ok.sum() * 2; fails += ((1 - ya) * ok).sum() + ((1 - yb) * ok).sum()
        nf += ((1 - ya) * ok).sum(); nff += ((1 - ya) * (1 - yb) * ok).sum()
        n_fl += fl.sum() * 2; fixes += (ya * fl).sum() + (yb * fl).sum()
        nx += (ya * fl).sum(); nxx += (ya * yb * fl).sum()
    return dict(p_fail_given_fail=nff / nf if nf else None, p_fail=fails / n_ok if n_ok else None,
                p_fix_given_fix=nxx / nx if nx else None, p_fix=fixes / n_fl if n_fl else None,
                n_break_events=int(nf), n_fix_events=int(nx))


def main():
    res = {"models": {}}
    for mdl in MODELS:
        Y, meta = load(mdl)
        U = sorted(r for r in Y if meta[r]["family"] == "null_U")
        if len(U) < 4:
            continue
        ck = defaultdict(list)
        for r, k in meta.items():
            if k["kind"] in ("quant", "gauss_fixed"):
                ck[k["ckpt"] + ("_fixed" if k["kind"] == "gauss_fixed" else "")].append(r)
        out = {"U": U, "checkpoints": {}}
        for c, runs in sorted(ck.items()):
            runs = sorted(runs)
            m = len(runs)
            if m < 2:
                continue
            tasks = sorted(set.intersection(*[set(Y[r]) for r in runs + U]))
            MU = np.array([[Y[u][t] for t in tasks] for u in U], float)
            MC = np.array([[Y[r][t] for t in tasks] for r in runs], float)
            pU = MU.mean(0)
            me = min(m, len(U))  # same number of draws on both sides
            csubs = list(combinations(range(m), me))
            v_c = float(np.mean([V(MC[list(s)]) for s in csubs]))
            v_u = [V(MU[list(s)]) for s in combinations(range(len(U)), me)]
            # task bootstrap of V_ckpt - mean V_U(m)
            T = len(tasks); diffs = []
            subs = list(combinations(range(len(U)), me))
            for _ in range(B):
                idx = rng.integers(0, T, T)
                diffs.append(np.mean([V(MC[list(s)][:, idx]) for s in csubs]) - np.mean([V(MU[list(s)][:, idx]) for s in subs[:20]]))
            # V restricted to null classes (all U)
            cls = {"ok": pU == 1, "fail": pU == 0, "coin": (pU > 0) & (pU < 1)}
            vcls = {k: dict(ckpt=rnd(np.mean([V(MC[list(s)][:, msk]) for s in csubs])) if msk.sum() else None,
                            null=rnd(np.mean([V(MU[list(s)][:, msk]) for s in subs])) if msk.sum() else None,
                            n=int(msk.sum())) for k, msk in cls.items()}
            # concordance: checkpoint pairs, reference = all U draws not nonce-mates of either draw
            rows = []
            for a, b in permutations(range(m), 2):
                na, nb = meta[runs[a]]["nonce"], meta[runs[b]]["nonce"]
                R = [i for i, u in enumerate(U) if meta[u]["nonce"] not in (na, nb)]
                rows.append((MC[a], MC[b], MU[R].mean(0)))
            nrows = []
            for a, b in permutations(range(len(U)), 2):
                R = [i for i in range(len(U)) if i not in (a, b)]
                nrows.append((MU[a], MU[b], MU[R].mean(0)))
            # fate of null-robust tasks across the checkpoint's m draws
            fate = {k: np.bincount(MC[:, cls[k]].sum(0).astype(int), minlength=m + 1).tolist() for k in ("ok", "fail")}
            out["checkpoints"][c] = dict(runs=runs, m=m, m_eff_for_V=me, n_tasks=T, V_ckpt=rnd(v_c), V_null_same_m=rnd(np.mean(v_u)),
                                         V_null_range=rnd([min(v_u), max(v_u)]),
                                         V_diff_ci95=rnd(np.percentile(diffs, [2.5, 97.5])),
                                         V_by_null_class=vcls, concordance=concord(rows, None),
                                         concordance_null=concord(nrows, None), fate_counts=fate)
            print(mdl, c, m, "V ckpt/null", rnd(v_c), rnd(np.mean(v_u)), "fate ok", fate["ok"], "fail", fate["fail"],
                  "conc", {k: rnd(v, 3) for k, v in concord(rows, None).items()})
        res["models"][mdl] = out
    dump("r02_stability", res)


if __name__ == "__main__":
    main()
