"""prereg_h1_h4: the confirmatory analysis of docs/insights/PREREG_iter4.md (binding; sha256[:16] 0d5e8385c911824f).

Implements PREREG §2-§4 exactly as written, with the resolutions listed in docs/insights/PREREG_iter4_analysis.md (A1-A14):
  H1  phi_RECAL > 1       P1 estimator (p1_overdispersion.stats / perm_T, unchanged), pooled over q4, q8 as
                          sum_m (J-1) sig_ck / sum_m (J-1) indep; P1 null (within-task permutation of the checkpoint
                          labels of each (y_q1, y_q2) pair, within (model, set)), B = 5000, one-sided.
  H2  r > 0               Pearson r of Delta(q1) vs Delta(q2) across RECAL checkpoints, pooled over models after
                          centring each draw's Delta per model; null = permutation of the q2 labels within model (exact
                          enumeration when the number of relabellings is <= B, else Monte Carlo B), one-sided.
  H3  F_split > 0         RECAL u RAND. 12 P2 features (common4.DISP). For each of 100 random task halves H (per model):
                          shift of draw q1 on H and of draw q2 on the complement, P2 shift definition (mean over tasks of
                          x - mean over the NR1-3 reference), standardised per model by the P2 sd_w computed from these
                          split shifts over all units of the model; cosine matrix per (model, set) block; F = J-weighted
                          mean over blocks of (mean same-checkpoint cos - mean different-checkpoint cos), averaged over
                          the 100 splits. Null = permutation of checkpoint labels (q2 side) within block, one-sided.
  Holm over H1-H3 at alpha 0.05 (common4.holm).
  H4  phi_RECAL - phi_RAND != 0  (secondary, outside Holm): exact enumeration of the RECAL/RAND labels within model
                          (C(7,4)^2 = 1225 relabellings), two-sided p = min(1, 2 min(P(D* >= D), P(D* <= D))); 95% CI by
                          task bootstrap within model (B_BOOT = 2000, percentile).
Secondary (§4, descriptive): per-model and per-domain H1-H3; sensitivity excluding tasks where any confirmatory draw of
the model ended in max_steps / in a context overflow; variance components of checkpoint net effect (method / checkpoint /
nonce) over GPTQ/AWQ-W4 d1-d4 draws (d1, d2 are non-confirmatory; used only here). The open-loop predictor bullet of §4
is NOT implemented here (see A14).

Data (§1, §5): integrity-gated snapshot (CLOQ_SNAPSHOT semantics of iter_2/common.py; files changed after the freeze
raise). y = official db_match success (iter_2/common.outcomes: infrastructure_error = missing, context overflow = failure,
W10). Null = BF16 nonce draws null_n1..n8 of the same model with >= 77 tasks, minus the nonce-mate of the draw (NR1-3).
Tasks = complete case over the null and every draw used for that model, q4 airline 45 removed explicitly (W17).

Modes
  default (confirmatory): refuses unless (a) the PREREG sha matches, (b) every one of the 28 confirmatory runs (A1) is
      admitted in the snapshot with its registered nonce, (c) this script is committed and unmodified and its last commit
      predates the snapshot, (d) no earlier snapshot already admitted all 28 runs (override: --allow-later-snapshot, which
      is recorded), (e) the output file does not exist yet (analysis runs once). Prints nothing about outcomes until the
      final table. --deadline-mode (only on/after 2026-10-05 UTC, §5): uses the admitted checkpoints (both draws needed).
  --dev: swaps in non-confirmatory stand-ins (RECAL: gptq_w4_d1, gptq_w4_d2, awq_w4, awq_w4_d2; RAND: gauss1_s1 fixed,
      gshape_w4, rtnsign_w4; q4 and q8) and refuses to touch any confirmatory run.
Usage:
  python prereg_h1_h4.py --snapshot <manifest.json>                 # confirmatory, once
  python prereg_h1_h4.py --dev --snapshot analysis/insights/iter_3/out/snapshot_live_20260929T1937Z.json
-> analysis/insights/iter_4/out/prereg_h1_h4_<tag>.json (tag CONF_<snapshot id> | DEV)
"""
import argparse
import hashlib
import itertools
import json
import math
import os
import subprocess
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path("/data/ziyangs/cloq")
HERE = Path(__file__).resolve().parent
PREREG = ROOT / "docs/insights/PREREG_iter4.md"
PREREG_SHA16 = "0d5e8385c911824f"
Q1, Q2 = "6d1f0b3e", "f07a5c21"
SEED = 20261005
B_PERM = 5000
N_SPLIT = 100
B_BOOT = 2000
ALPHA = 0.05
MODELS = ("q4", "q8")
DOMS = ("retail", "airline")
DROP_TASKS = {"q4": {("airline", "45")}}
MIN_NULL_TASKS = 77  # NR1-2
DEADLINE = "2026-10-05"


# ----------------------------------------------------------------------------------------------------- units
def confirmatory_units():
    U = []
    for m in MODELS:
        for meth in ("gptq_w4", "awq_w4"):
            for d in ("d3", "d4"):
                ck = f"{meth}_{d}"
                U.append(dict(model=m, set="RECAL", unit=ck, method=meth, cal=d,
                              draws=(f"a6k2_{m}_{ck}_q1", f"a6k2_{m}_{ck}_q2")))
        for s in ("s2", "s4", "s5"):
            ck = f"gauss1_{s}"
            U.append(dict(model=m, set="RAND", unit=ck, method="gauss1", cal=s,
                          draws=(f"a6k2_{m}_{ck}_q1", f"a6k2_{m}_{ck}_q2")))
    return U


CONF_RUNS = frozenset(r for u in confirmatory_units() for r in u["draws"])
assert len(CONF_RUNS) == 28


def dev_units():
    U = []
    for m in MODELS:
        for ck, meth, cal, (a, b) in (("gptq_w4_d1", "gptq_w4", "d1", ("n1", "n2")), ("gptq_w4_d2", "gptq_w4", "d2", ("n1", "n2")),
                                      ("awq_w4", "awq_w4", "d1", ("n1", "n2")), ("awq_w4_d2", "awq_w4", "d2", ("q1", "q2"))):
            U.append(dict(model=m, set="RECAL", unit=ck, method=meth, cal=cal, draws=(f"a6k2_{m}_{ck}_{a}", f"a6k2_{m}_{ck}_{b}")))
        for ck, meth in (("gauss1_s1", "gauss1"), ("gshape_w4", "gshape"), ("rtnsign_w4", "rtnsign")):
            U.append(dict(model=m, set="RAND", unit=ck, method=meth, cal="-", draws=(f"a6k2_{m}_{ck}_q1", f"a6k2_{m}_{ck}_q2")))
    return U


def varcomp_units(dev):
    """GPTQ/AWQ-W4 checkpoints d1-d4 with all their nonce draws (d3/d4 only in confirmatory mode). Plus Gaussian k=1
    fixed seeds as a third 'method' for the with_gauss variant (s1 non-confirmatory; s2/s4/s5 confirmatory only)."""
    out = []
    for m in MODELS:
        spec = [("gptq_w4", "d1", "gptq_w4_d1", ["n1", "n2", "q3", "q4", "q5"]), ("gptq_w4", "d2", "gptq_w4_d2", ["n1", "n2"]),
                ("awq_w4", "d1", "awq_w4", ["n1", "n2", "q3", "q4", "q5"]), ("awq_w4", "d2", "awq_w4_d2", ["q1", "q2", "q3"]),
                ("gauss1", "s1", "gauss1_s1", ["q1", "q2"])]
        if not dev:
            spec += [(meth, d, f"{meth}_{d}", ["q1", "q2"]) for meth in ("gptq_w4", "awq_w4") for d in ("d3", "d4")]
            spec += [("gauss1", s, f"gauss1_{s}", ["q1", "q2"]) for s in ("s2", "s4", "s5")]
        for meth, cal, ck, dr in spec:
            out.append(dict(model=m, method=meth, cal=cal, unit=ck, draws=[f"a6k2_{m}_{ck}_{x}" for x in dr]))
    return out


# ----------------------------------------------------------------------------------------------------- guards
def sha256(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def refuse(msg):
    sys.stderr.write(f"REFUSED: {msg}\n")
    sys.exit(2)


def git(*a):
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True).stdout.strip()


def rng_for(name):
    return np.random.default_rng([SEED, zlib.crc32(name.encode())])


# ----------------------------------------------------------------------------------------------------- statistics
def phi_test(blocks, name, B=B_PERM):
    """blocks: list of (yA, yB) (J, N). P1 estimator and P1 null, unchanged (p1_overdispersion.perm_T / summarize)."""
    blocks = [(a, b) for a, b in blocks if a.shape[0] >= 2]
    if not blocks:
        return None
    P1.rng = rng_for("phi:" + name)
    T, E, Ts = P1.perm_T(blocks, B)
    return P1.summarize(T, E, Ts, len(blocks), sum(a.shape[0] - 1 for a, _ in blocks))


def phi_point(blocks):
    T = E = 0.0
    for a, b in blocks:
        if a.shape[0] < 2:
            continue
        s, e = P1.stats(a, b)[:2]
        T += (a.shape[0] - 1) * s
        E += (a.shape[0] - 1) * e
    return T / E if E > 0 else np.nan


def perms_space(Js, B, rng):
    """Relabellings of within-block permutations: exact product if prod(J!) <= B, else B Monte Carlo draws.
    Yields tuples of index arrays (one per block). Returns (list, exact flag)."""
    n = math.prod(math.factorial(j) for j in Js)
    if n <= B:
        return [tuple(np.array(p) for p in combo) for combo in
                itertools.product(*[list(itertools.permutations(range(j))) for j in Js])], True
    return [tuple(rng.permutation(j) for j in Js) for _ in range(B)], False


def pvalue(T, Ts, exact):
    Ts = np.asarray(Ts)
    if exact:  # identity included in the enumeration
        return float(np.mean(Ts >= T - 1e-12))
    return float((1 + np.sum(Ts >= T - 1e-12)) / (1 + len(Ts)))


def rep_r(dA, dB):
    """dA, dB: list per model of arrays (J,) of Delta(q1), Delta(q2). Per-model centring, pooled Pearson."""
    a = np.concatenate([x - x.mean() for x in dA])
    b = np.concatenate([x - x.mean() for x in dB])
    if a.std() == 0 or b.std() == 0:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def rep_test(dA, dB, name, B=B_PERM):
    keep = [i for i, x in enumerate(dA) if len(x) >= 2]
    dA, dB = [dA[i] for i in keep], [dB[i] for i in keep]
    if not dA:
        return None
    r = rep_r(dA, dB)
    space, exact = perms_space([len(x) for x in dB], B, rng_for("r:" + name))
    Rs = np.array([rep_r(dA, [x[p] for x, p in zip(dB, ps)]) for ps in space])
    return dict(r=rnd(r, 4), p=pvalue(r, Rs, exact), exact=exact, n_relabellings=len(Rs), perm_mean=rnd(np.nanmean(Rs), 4),
                perm_q95=rnd(np.nanquantile(Rs, .95), 4), n_ckpt=int(sum(len(x) for x in dA)), n_models=len(dA),
                p_min=rnd(1 / len(Rs) if exact else 1 / (1 + len(Rs)), 5))


def cosm(ZA, ZB):
    na, nb = np.linalg.norm(ZA, axis=1), np.linalg.norm(ZB, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        C = (ZA @ ZB.T) / np.outer(na, nb)
    C[~np.isfinite(C)] = np.nan
    return C


def F_from_C(Cs, perms=None):
    """Cs: list of (J, J) mean cosine matrices (rows q1 of checkpoint i, cols q2 of checkpoint k). J-weighted mean over
    blocks of (mean diag - mean off-diag), the p2_dispositions.fingerprint statistic."""
    num = den = 0.0
    for bi, C in enumerate(Cs):
        J = len(C)
        if J < 2:
            continue
        if perms is not None:
            C = C[:, perms[bi]]
        off = ~np.eye(J, dtype=bool)
        num += J * (np.nanmean(np.diag(C)) - np.nanmean(C[off]))
        den += J
    return num / den if den else np.nan


def split_cos(dl, units_by_block, tasks_idx, n_split, rng):
    """dl: {run: (T, F) per-task shift}; units_by_block: list of (block name, [(runA, runB)]) of ONE model;
    tasks_idx: indices into the model's task list available for splitting. Returns {block: mean cos matrix},
    per-split F values, and sd_w diagnostics."""
    allu = [u for _, us in units_by_block for u in us]
    acc = {b: [] for b, _ in units_by_block}
    tasks_idx = np.asarray(tasks_idx)
    for _ in range(n_split):
        perm = rng.permutation(tasks_idx)
        H, Hc = perm[: len(perm) // 2], perm[len(perm) // 2:]
        with np.errstate(invalid="ignore"), _quiet():
            S = {a: np.nanmean(dl[a][H], 0) for a, _ in allu}
            S.update({b: np.nanmean(dl[b][Hc], 0) for _, b in allu})
        sA = np.array([S[a] for a, _ in allu]); sB = np.array([S[b] for _, b in allu])
        with _quiet():
            sd_w = np.sqrt(np.nanmean((sA - sB) ** 2, 0) / 2)
        keep = np.isfinite(sd_w) & (sd_w > 1e-9)
        for b, us in units_by_block:
            ZA = np.zeros((len(us), len(sd_w))); ZB = np.zeros_like(ZA)
            ZA[:, keep] = np.nan_to_num(np.array([S[a] for a, _ in us])[:, keep] / sd_w[keep])
            ZB[:, keep] = np.nan_to_num(np.array([S[bb] for _, bb in us])[:, keep] / sd_w[keep])
            acc[b].append(cosm(ZA, ZB))
    with _quiet():
        return {b: np.nanmean(np.array(v), 0) for b, v in acc.items()}


class _quiet:
    def __enter__(self):
        import warnings
        self._w = warnings.catch_warnings(); self._w.__enter__(); warnings.simplefilter("ignore", RuntimeWarning)

    def __exit__(self, *a):
        self._w.__exit__(*a)


def fsplit_test(Cblocks, name, B=B_PERM):
    """Cblocks: list of (block name, J x J mean cos matrix)."""
    Cblocks = [(n, C) for n, C in Cblocks if len(C) >= 2]
    if not Cblocks:
        return None
    Cs = [C for _, C in Cblocks]
    F = F_from_C(Cs)
    space, exact = perms_space([len(C) for C in Cs], B, rng_for("F:" + name))
    Fs = np.array([F_from_C(Cs, ps) for ps in space])
    per = {}
    for n, C in Cblocks:
        off = ~np.eye(len(C), dtype=bool)
        per[n] = dict(J=len(C), same=rnd(np.nanmean(np.diag(C)), 3), diff=rnd(np.nanmean(C[off]), 3))
    return dict(F_split=rnd(F, 4), p=pvalue(F, Fs, exact), exact=exact, n_relabellings=len(Fs), perm_mean=rnd(Fs.mean(), 4),
                perm_q95=rnd(np.quantile(Fs, .95), 4), blocks=per)


# ----------------------------------------------------------------------------------------------------- data
class ModelData:
    """Outcomes, termination reasons, features and per-task disposition shifts for one model, restricted to the listed
    draws plus the eligible nonce null. Never touches a run outside `runs` + null."""

    def __init__(self, m, runs, guard, procs):
        self.m = m
        for r in runs:
            guard(r)
        nulls = sorted(r for r in SNAP["frozen"] if r.startswith(f"a6k2_{m}_null_n"))
        self.Y, self.TR, self.nonce = {}, {}, {}
        for r in list(runs) + nulls:
            y, tr = {}, {}
            for d in DOMS:
                for t, (v, why) in C2.outcomes(r, d, True).items():
                    tr[(d, t)] = why
                    if why != C2.INFRA:
                        y[(d, t)] = v
            self.Y[r], self.TR[r] = y, tr
            self.nonce[r] = SNAP["frozen"][r]["retail"]["prompt_nonce"]
        self.U = [u for u in nulls if len(self.Y[u]) >= MIN_NULL_TASKS]
        self.runs = list(runs)
        tasks = set.intersection(*[set(self.Y[r]) for r in self.U + self.runs])
        self.tasks = sorted(tasks - DROP_TASKS.get(m, set()))
        self.tix = {t: i for i, t in enumerate(self.tasks)}
        self.F = C4.features(self.runs + self.U, procs=procs)
        self._dl = {}

    def ref(self, r):
        return [u for u in self.U if self.nonce[u] != self.nonce[r]]  # NR1-3

    def y(self, r, tasks=None):
        tasks = self.tasks if tasks is None else tasks
        return np.array([self.Y[r][t] for t in tasks], float)

    def delta(self, r, tasks=None, drop_null=None):
        """Delta = mean_t y_r - mean_t mean_{u in ref} y_u (null episodes whose termination is in drop_null excluded)."""
        tasks = self.tasks if tasks is None else tasks
        R = self.ref(r)
        yn = np.array([[np.nan if (drop_null and self.TR[u].get(t) in drop_null) else self.Y[u][t] for t in tasks] for u in R])
        with _quiet():
            return float(self.y(r, tasks).mean() - np.nanmean(np.nanmean(yn, 0)))

    def dl(self, r):
        """(T, 12) per-task disposition shift vs the NR1-3 reference (p2_dispositions.shift)."""
        if r not in self._dl:
            X = C4.fmat(self.F, [r], self.tasks, C4.DISP)[0]
            with _quiet():
                X0 = np.nanmean(C4.fmat(self.F, self.ref(r), self.tasks, C4.DISP), 0)
                self._dl[r] = X - X0
        return self._dl[r]


# ----------------------------------------------------------------------------------------------------- analysis
def analyse(units, MD, task_filter=None, label="primary", n_split=N_SPLIT, B=B_PERM, drop_null=None, with_h4=True, boot=True):
    """units: confirmatory-unit dicts (both draws present). task_filter(m) -> list of task keys (subset of MD[m].tasks)."""
    res = {"label": label, "models": {}}
    rec_blocks, rand_blocks, dA, dB, Cblocks = [], [], [], [], []
    per_model = {}
    for m in MODELS:
        D = MD[m]
        tasks = D.tasks if task_filter is None else task_filter(m)
        ti = [D.tix[t] for t in tasks]
        us = {s: [u for u in units if u["model"] == m and u["set"] == s] for s in ("RECAL", "RAND")}
        mats = {s: (np.array([D.y(u["draws"][0], tasks) for u in v]).reshape(len(v), len(tasks)),
                    np.array([D.y(u["draws"][1], tasks) for u in v]).reshape(len(v), len(tasks))) for s, v in us.items()}
        deltas = {s: [(D.delta(u["draws"][0], tasks, drop_null), D.delta(u["draws"][1], tasks, drop_null)) for u in v]
                  for s, v in us.items()}
        Cm = split_cos({r: D.dl(r) for s in us for u in us[s] for r in u["draws"]},
                       [(s, [tuple(u["draws"]) for u in us[s]]) for s in ("RECAL", "RAND") if us[s]],
                       ti, n_split, rng_for(f"split:{label}:{m}"))
        rec_blocks.append(mats["RECAL"]); rand_blocks.append(mats["RAND"])
        dA.append(np.array([d[0] for d in deltas["RECAL"]])); dB.append(np.array([d[1] for d in deltas["RECAL"]]))
        Cblocks += [(f"{m}:{s}", C) for s, C in Cm.items()]
        per_model[m] = dict(rec=mats["RECAL"], rand=mats["RAND"], dA=dA[-1], dB=dB[-1], C=[(f"{m}:{s}", C) for s, C in Cm.items()])
        res["models"][m] = dict(
            n_tasks=len(tasks), n_null=len(D.U),
            units={s: [dict(unit=u["unit"], q1=u["draws"][0], q2=u["draws"][1], delta_q1=rnd(d[0]), delta_q2=rnd(d[1]),
                            net=rnd((d[0] + d[1]) / 2)) for u, d in zip(v, deltas[s])] for s, v in us.items()},
            phi_point={s: rnd(phi_point([mats[s]]), 4) for s in mats})
    res["H1"] = phi_test(rec_blocks, f"H1:{label}", B)
    res["H2"] = rep_test(dA, dB, f"H2:{label}", B)
    res["H3"] = fsplit_test(Cblocks, f"H3:{label}", B)
    if with_h4:
        res["H4"] = h4_test(rec_blocks, rand_blocks, f"H4:{label}", boot=boot)
        res["phi_RAND"] = phi_test(rand_blocks, f"RAND:{label}", B)
    res["_per_model_inputs"] = per_model
    return res


def h4_test(rec_blocks, rand_blocks, name, boot=True):
    """Exact relabelling of RECAL/RAND within model; two-sided; task-bootstrap CI."""
    pairs = [(np.vstack([ra[0], rn[0]]), np.vstack([ra[1], rn[1]]), len(ra[0])) for ra, rn in zip(rec_blocks, rand_blocks)]
    if any(k < 2 or len(a) - k < 2 for a, _, k in pairs):
        return None

    def D(sel):
        rb = [(a[s], b[s]) for (a, b, _), s in zip(pairs, sel)]
        nb = [(a[~s], b[~s]) for (a, b, _), s in zip(pairs, sel)]
        return phi_point(rb) - phi_point(nb), phi_point(rb), phi_point(nb)

    obs_sel = [np.arange(len(a)) < k for a, _, k in pairs]
    d0, pr, pn = D(obs_sel)
    combos = []
    for a, _, k in pairs:
        cs = []
        for c in itertools.combinations(range(len(a)), k):
            s = np.zeros(len(a), bool); s[list(c)] = True; cs.append(s)
        combos.append(cs)
    Ds = np.array([D(list(sel))[0] for sel in itertools.product(*combos)])
    n_all = len(Ds)
    Ds = Ds[np.isfinite(Ds)]  # A11: phi undefined when the indep denominator E <= 0; conditional test on defined relabellings
    if not np.isfinite(d0) or len(Ds) == 0:
        return dict(phi_RECAL=rnd(pr, 4), phi_RAND=rnd(pn, 4), diff=None, p_two_sided=None, n_relabellings=n_all,
                    note="phi undefined (indep denominator <= 0) for the observed labelling")
    p_hi = float(np.mean(Ds >= d0 - 1e-12)); p_lo = float(np.mean(Ds <= d0 + 1e-12))
    out = dict(phi_RECAL=rnd(pr, 4), phi_RAND=rnd(pn, 4), diff=rnd(d0, 4), p_two_sided=min(1.0, 2 * min(p_hi, p_lo)),
               p_upper=p_hi, p_lower=p_lo, n_relabellings=n_all, n_defined=len(Ds), exact=True,
               direction_prediction_phi_RECAL_gt_RAND=bool(d0 > 0))
    if boot:
        rng = rng_for("boot:" + name)
        bs = np.zeros((B_BOOT, 3))
        for i in range(B_BOOT):
            rb, nb = [], []
            for ra, rn in zip(rec_blocks, rand_blocks):
                idx = rng.integers(0, ra[0].shape[1], ra[0].shape[1])
                rb.append((ra[0][:, idx], ra[1][:, idx])); nb.append((rn[0][:, idx], rn[1][:, idx]))
            a_, b_ = phi_point(rb), phi_point(nb)
            bs[i] = (a_ - b_, a_, b_)
        q = lambda k: rnd(np.nanquantile(bs[:, k], [.025, .975]), 4)
        out.update(ci95_diff=q(0), ci95_phi_RECAL=q(1), ci95_phi_RAND=q(2), B_boot=B_BOOT, ci_method="task bootstrap within model, percentile")
    return out


def varcomp(vunits, MD, method_set):
    """Nested method-of-moments variance components of checkpoint net effect Delta (per model, then averaged)."""
    out = {}
    comps = []
    for m in MODELS:
        D = MD[m]
        cks = [u for u in vunits if u["model"] == m and u["method"] in method_set]
        cks = [dict(u, draws=[r for r in u["draws"] if r in D.Y]) for u in cks]
        cks = [u for u in cks if len(u["draws"]) >= 2]
        tasks = D.vtasks
        dl = {u["unit"]: np.array([D.delta(r, tasks) for r in u["draws"]]) for u in cks}
        ss = sum(((v - v.mean()) ** 2).sum() for v in dl.values()); dfw = sum(len(v) - 1 for v in dl.values())
        s2n = ss / dfw
        meth = {}
        for u in cks:
            meth.setdefault(u["method"], []).append(u["unit"])
        raw, s2c_l, Mm = {}, [], []
        for me, lst in meth.items():
            cm = np.array([dl[k].mean() for k in lst])
            if len(cm) < 2:
                continue
            raw[me] = (cm.var(ddof=1), len(cm))
            s2c_l.append(cm.var(ddof=1) - s2n * np.mean([1 / len(dl[k]) for k in lst]))
            Mm.append(cm.mean())
        s2c = float(np.mean(s2c_l)) if s2c_l else np.nan
        s2m = float(np.var(Mm, ddof=1) - np.mean([v / k for v, k in raw.values()])) if len(Mm) >= 2 else np.nan
        comps.append((s2m, s2c, s2n))
        out[m] = dict(n_tasks=len(tasks), checkpoints={k: dict(n_draws=len(v), deltas=rnd(v), mean=rnd(v.mean()))
                                                       for k, v in dl.items()},
                      var_method=rnd(s2m, 6), var_checkpoint=rnd(s2c, 6), var_nonce=rnd(s2n, 6),
                      sd_pp=dict(method=rnd(100 * np.sqrt(max(s2m, 0)), 2) if np.isfinite(s2m) else None,
                                 checkpoint=rnd(100 * np.sqrt(max(s2c, 0)), 2), nonce=rnd(100 * np.sqrt(s2n), 2)))
    c = np.nanmean(np.array(comps), 0)
    tot = np.nansum(np.clip(c, 0, None))
    out["pooled_mean_over_models"] = dict(var_method=rnd(c[0], 6), var_checkpoint=rnd(c[1], 6), var_nonce=rnd(c[2], 6),
                                          share_truncated=dict(zip(("method", "checkpoint", "nonce"), rnd(np.clip(c, 0, None) / tot, 3))))
    return out


# ----------------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True, help="integrity.py manifest (CLOQ_SNAPSHOT)")
    ap.add_argument("--dev", action="store_true", help="non-confirmatory stand-in units (development only)")
    ap.add_argument("--deadline-mode", action="store_true", help="PREREG §5: on/after 2026-10-05 use available checkpoints")
    ap.add_argument("--allow-later-snapshot", action="store_true", help="an earlier snapshot already admitted all 28 runs")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--procs", type=int, default=8)
    ap.add_argument("--n-split", type=int, default=N_SPLIT, help=argparse.SUPPRESS)  # dev smoke only
    ap.add_argument("--B", type=int, default=B_PERM, help=argparse.SUPPRESS)  # dev smoke only
    a = ap.parse_args()
    confirm = not a.dev
    if confirm and (a.n_split != N_SPLIT or a.B != B_PERM):
        refuse("B / n-split are fixed by the pre-registration in confirmatory mode")

    # (a) pre-registration identity
    psha = sha256(PREREG)
    if psha[:16] != PREREG_SHA16:
        refuse(f"{PREREG} sha256 {psha[:16]} != registered {PREREG_SHA16}; the pre-registration was edited")

    global SNAP, C2, C4, P1
    os.environ["CLOQ_SNAPSHOT"] = str(Path(a.snapshot).resolve())
    sys.path.insert(0, str(HERE))
    import common4 as C4  # noqa: E402  (imports iter_2/common with the snapshot gate)
    import p1_overdispersion as P1  # noqa: E402
    C2 = sys.modules["common"]
    SNAP = C2.SNAP
    sid = SNAP["snapshot_id"]
    tag = a.tag or ("DEV" if a.dev else f"CONF_{sid}" + ("_deadline" if a.deadline_mode else ""))
    out_path = HERE / "out" / f"prereg_h1_h4_{tag}.json"
    say = print if a.dev else (lambda *x, **k: None)  # confirmatory: silent until the final table
    notes = []

    def guard(run):
        if a.dev and run in CONF_RUNS:
            raise RuntimeError(f"dev mode must not touch confirmatory run {run}")

    if a.dev:
        units = dev_units()
        assert not (CONF_RUNS & {r for u in units for r in u["draws"]})
        miss = [r for u in units for r in u["draws"] if r not in SNAP["frozen"]]
        if miss:
            refuse(f"dev stand-ins not admitted: {miss}")
    else:
        # (e) runs once
        if out_path.exists():
            refuse(f"{out_path} exists; the confirmatory analysis runs once (§5)")
        # (b) admission + registered nonces (admission metadata only; no outcome is read here)
        units_all = confirmatory_units()
        bad = {}
        for r in sorted(CONF_RUNS):
            f = SNAP["frozen"].get(r)
            want = Q1 if r.endswith("_q1") else Q2
            if f is None or set(f) != set(DOMS):
                bad[r] = "not admitted"
            elif any(f[d]["prompt_nonce"] != want for d in DOMS):
                bad[r] = "nonce mismatch"
        if bad:
            if not a.deadline_mode:
                refuse(f"{len(bad)} of 28 confirmatory runs not admitted/valid: {bad}. Wait for the next snapshot, or on/after "
                       f"{DEADLINE} pass --deadline-mode (§5).")
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if today < DEADLINE or SNAP["utc"][:10] < DEADLINE:
                refuse(f"--deadline-mode is only allowed on/after {DEADLINE} (today {today}, snapshot {SNAP['utc']})")
            notes.append(f"deadline mode: excluded runs {bad}")
        elif a.deadline_mode:
            notes.append("--deadline-mode passed but all 28 runs admitted; ignored")
        units = [u for u in units_all if all(r not in bad for r in u["draws"])]
        # (d) first snapshot admitting all runs
        earlier = []
        for p in sorted(ROOT.glob("analysis/insights/*/out/snapshot*.json")):
            if p.resolve() == Path(a.snapshot).resolve():
                continue
            try:
                s = json.load(open(p))
            except Exception:
                continue
            if s.get("utc", "9") < SNAP["utc"] and CONF_RUNS <= set(s.get("frozen", {})):
                earlier.append(str(p))
        if earlier and not a.allow_later_snapshot:
            refuse(f"earlier snapshot(s) already admitted all 28 runs: {earlier} (§5 'first snapshot'); "
                   "pass --allow-later-snapshot to override (recorded)")
        if earlier:
            notes.append(f"--allow-later-snapshot: earlier snapshots admitting all runs {earlier}")
        # (c) script committed before the snapshot, unmodified
        rel = str(Path(__file__).resolve().relative_to(ROOT))
        if git("status", "--porcelain", "--", rel):
            refuse(f"{rel} has uncommitted changes")
        ct = git("log", "-1", "--format=%cI", "--", rel)
        if not ct:
            refuse(f"{rel} is not committed")
        snap_utc = datetime.fromisoformat(SNAP["utc"].replace("Z", "+00:00"))
        if datetime.fromisoformat(ct) >= snap_utc:
            refuse(f"{rel} last committed {ct}, not before snapshot {SNAP['utc']} (§5)")

    # ------------------------------------------------------------------ load
    MD, vunits = {}, varcomp_units(a.dev)
    for m in MODELS:
        runs = sorted({r for u in units if u["model"] == m for r in u["draws"]})
        vruns = sorted({r for u in vunits if u["model"] == m for r in u["draws"] if r in SNAP["frozen"]})
        vruns = [r for r in vruns if r not in runs and not (a.dev and r in CONF_RUNS)]
        MD[m] = ModelData(m, runs + vruns, guard, a.procs)
        # primary task set: complete case over the null and the confirmatory draws only (A5)
        vset = set(vruns)
        MD[m].vtasks = MD[m].tasks
        prim = set.intersection(*[set(MD[m].Y[r]) for r in MD[m].U + runs]) - DROP_TASKS.get(m, set())
        MD[m].tasks = sorted(prim)
        MD[m].tix = {t: i for i, t in enumerate(MD[m].tasks)}
        MD[m]._dl = {}
        say(m, "tasks primary", len(MD[m].tasks), "varcomp", len(MD[m].vtasks), "null", len(MD[m].U), "vruns", len(vset))

    # ------------------------------------------------------------------ confirmatory family
    prim = analyse(units, MD, label="primary", n_split=a.n_split, B=a.B)
    say("H1", prim["H1"]); say("H2", prim["H2"]); say("H3", {k: v for k, v in prim["H3"].items() if k != "blocks"})
    fam = [("H1", prim["H1"]["phi"] if prim["H1"] else None, prim["H1"]["p"] if prim["H1"] else np.nan, "phi_RECAL (pooled q4,q8)"),
           ("H2", prim["H2"]["r"] if prim["H2"] else None, prim["H2"]["p"] if prim["H2"] else np.nan, "r Delta(q1) vs Delta(q2), RECAL"),
           ("H3", prim["H3"]["F_split"] if prim["H3"] else None, prim["H3"]["p"] if prim["H3"] else np.nan, "F_split, RECAL u RAND")]
    adj = C4.holm([f[2] for f in fam])
    table = []
    for (h, est, p, what), pa in zip(fam, adj):
        table.append(dict(id=h, statistic=what, estimate=est, p=rnd(p, 5), p_holm=rnd(pa, 5), role="primary (Holm H1-H3)",
                          verdict="not computable" if not np.isfinite(p) else
                          ("supported (reject H0 after Holm)" if pa < ALPHA else "not supported after Holm")))
    h4 = prim["H4"]
    table.append(dict(id="H4", statistic="phi_RECAL - phi_RAND (two-sided)", estimate=h4 and h4["diff"],
                      p=h4 and rnd(h4["p_two_sided"], 5), p_holm=None, ci95=h4 and h4.get("ci95_diff"),
                      role="secondary (outside Holm)",
                      verdict="not computable" if not h4 or h4["p_two_sided"] is None else
                      ("difference detected" if h4["p_two_sided"] < ALPHA else "not detected (underpowered; not 'no difference')")))

    # ------------------------------------------------------------------ secondary (§4)
    sec = {}
    say("secondary: per model")
    sec["per_model"] = {}
    for m in MODELS:
        pm = prim["_per_model_inputs"][m]
        sec["per_model"][m] = dict(H1=phi_test([pm["rec"]], f"H1:model:{m}", a.B), H2=rep_test([pm["dA"]], [pm["dB"]], f"H2:model:{m}", a.B),
                                   H3=fsplit_test(pm["C"], f"H3:model:{m}", a.B), phi_RAND=rnd(phi_point([pm["rand"]]), 4))
    say("secondary: per domain")
    sec["per_domain"] = {}
    for d in DOMS:
        r = analyse(units, MD, task_filter=lambda m, d=d: [t for t in MD[m].tasks if t[0] == d], label=f"dom:{d}",
                    n_split=a.n_split, B=a.B, boot=False)
        sec["per_domain"][d] = strip(r)
    say("secondary: sensitivity")
    sec["sensitivity"] = {}
    for key, reasons in (("excl_max_steps", {"max_steps"}), ("excl_context_overflow", {"context_overflow"})):
        dropped = {}

        def filt(m, reasons=reasons):
            D = MD[m]
            runs = [r for u in units if u["model"] == m for r in u["draws"]]
            bad = {t for t in D.tasks if any(D.TR[r].get(t) in reasons for r in runs)}
            dropped[m] = len(bad)
            return [t for t in D.tasks if t not in bad]
        r = analyse(units, MD, task_filter=filt, label=key, n_split=a.n_split, B=a.B, drop_null=reasons, boot=False)
        sec["sensitivity"][key] = dict(n_tasks_dropped=dict(dropped), **strip(r))
    say("secondary: variance components")
    sec["variance_components"] = dict(
        gptq_awq=varcomp(vunits, MD, {"gptq_w4", "awq_w4"}),
        gptq_awq_gauss1=varcomp(vunits, MD, {"gptq_w4", "awq_w4", "gauss1"}),
        note="d1/d2 (and gauss1_s1) are non-confirmatory; this is descriptive only" + ("; DEV: d3/d4, gauss s2/s4/s5 excluded" if a.dev else ""))
    sec["open_loop_predictors"] = "not implemented in this script (A14); to be run separately"

    res = dict(
        _prereg=dict(path=str(PREREG), sha256=psha, sha16_expected=PREREG_SHA16, ok=psha[:16] == PREREG_SHA16),
        _snapshot=dict(id=sid, utc=SNAP["utc"], path=str(Path(a.snapshot).resolve()), null_rule_sha256=SNAP.get("null_rule", {}).get("sha256")),
        _script=dict(path=str(Path(__file__).resolve()), sha256=sha256(Path(__file__).resolve()), git_head=git("rev-parse", "HEAD"),
                     dirty=bool(git("status", "--porcelain", "--", str(Path(__file__).resolve().relative_to(ROOT)))),
                     deps_sha256={str(Path(mod.__file__).resolve().relative_to(ROOT)): sha256(mod.__file__) for mod in
                                  (C4, P1, C2, sys.modules["r_common"])}),
        _run_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        mode="DEV (stand-in units, NOT confirmatory)" if a.dev else ("CONFIRMATORY" + (" deadline-mode" if a.deadline_mode else "")),
        settings=dict(seed=SEED, B_perm=a.B, n_split=a.n_split, B_boot=B_BOOT, alpha=ALPHA, features=C4.DISP, models=MODELS,
                      drop_tasks={k: sorted(map(list, v)) for k, v in DROP_TASKS.items()}, q1=Q1, q2=Q2),
        notes=notes,
        units=[dict(u, draws=list(u["draws"])) for u in units],
        confirmatory_table=table,
        primary=strip(prim),
        secondary=sec)
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(res, f, indent=1, default=lambda x: x.item() if hasattr(x, "item") else (x.tolist() if hasattr(x, "tolist") else str(x)))
    # ------------------------------------------------------------------ final table (the only outcome print)
    print(f"\n{res['mode']}  snapshot {sid}  prereg sha16 {psha[:16]}  units {len(units)}")
    print(f"{'id':3} {'statistic':38} {'estimate':>9} {'p':>8} {'p_holm':>8}  verdict")
    for r in table:
        e = r["estimate"]
        print(f"{r['id']:3} {r['statistic']:38} {e if e is not None else float('nan'):9.4f} {r['p'] if r['p'] is not None else float('nan'):8.4f} "
              f"{r['p_holm'] if r['p_holm'] is not None else float('nan'):8.4f}  {r['verdict']}" + (f"  CI95 {r['ci95']}" if r.get("ci95") else ""))
    print("wrote", out_path)


def strip(r):
    return {k: v for k, v in r.items() if not k.startswith("_")}


def rnd(x, k=4):
    if x is None:
        return None
    if isinstance(x, (list, tuple, np.ndarray)):
        return [rnd(v, k) for v in list(x)]
    x = float(x)
    return None if not np.isfinite(x) else round(x, k)


SNAP = C2 = C4 = P1 = None

if __name__ == "__main__":
    main()
