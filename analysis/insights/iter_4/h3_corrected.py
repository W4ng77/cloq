"""h3_corrected: CORRECTED (POST-HOC) RE-ANALYSIS of PREREG_iter4 H3 (split-task behavioural fingerprint).

Not the pre-registered analysis. The pre-registered result (prereg_h1_h4.py, out/prereg_h1_h4_CONF_20260930T0044Z.json,
F_split 0.2602, p 0.0008, p_holm 0.0024) is kept unchanged as history. The 28 confirmatory runs were unblinded on
2026-09-30; everything here is computed after their outcomes were seen (docs/insights/METHODOLOGY_REVISION.md §H3).

Why (docs/insights/EXTERNAL_REVIEW_GPT61_20260930.md §B). prereg_h1_h4.split_cos standardises every feature by
sd_w = sqrt(mean_j (sA_j - sB_j)^2 / 2), i.e. by the differences of the TRUE (q1-draw, q2-draw) pairs of each
checkpoint, and fsplit_test then permutes the checkpoint labels of a cosine matrix that was computed with that fixed
scale. The scale is a function of the observed pairing, so the observed labelling is not exchangeable with the
permuted ones: features on which the true pairs happen to agree get up-weighted for the observed statistic only.

Data (unchanged from prereg_h1_h4, reused through its ModelData): the 28 confirmatory runs (14 checkpoints x draws
q1, q2) on q4/q8, the 12 P2 disposition features (common4.DISP, fixed list and order), per-task shift = x - mean over
the NR1-3 nonce reference, tasks = complete case over the nonce null and the 28 runs (q4 airline 45 removed),
integrity-gated snapshot (CLOQ_SNAPSHOT semantics).

Fixed preprocessing (identical for the observed statistic and every permutation):
  splits      100 random task halves per model from the prereg stream rng_for("split:primary:<m>") (the same halves
              as the pre-registered run); all variants and all permutations use these same halves.
  shift       per split: s_A[j] = nanmean over half H of draw q1's per-task shift, s_B[j] = over the complement, draw q2.
  missing     a shift entry with no defined task in its half (NaN) is set to 0 after scaling (= no shift); counted.
  zero-var    a feature whose scale is 0 or non-finite in a split is dropped (zero-filled) for that split; counted.
  scale       variant-specific (below); always computed per model over all 7 units (4 RECAL + 3 RAND) of that model.
  cosine      cos(z_A[i], z_B[k]) per split, averaged over the 100 splits; F = J-weighted mean over blocks of
              (mean same-checkpoint cos - mean different-checkpoint cos) (p2_dispositions.fingerprint statistic).
Variants
  original    true-pair sd_w, fixed under permutation (reproduces the pre-registered numbers; INVALID null, history).
  main        pairing-invariant unpaired pooled scale: per split and feature,
                sd_pool = sqrt( (sum_j (s_A[j]-mean_A)^2 + sum_j (s_B[j]-mean_B)^2) / (2 (J_m - 1)) ),
              a function of the unordered sets {s_A} and {s_B} only, hence identical under every within-block
              relabelling; the permutation of the cosine matrix is then a valid permutation test.
  sensitivity the original statistic (true-pair sd_w) with the full preprocessing recomputed inside every permutation
              (sd_w from the permuted pairs, then cosines, then F); observed F equals the original F.
Permutation: B-side (q2 draw) checkpoint labels within block; exact enumeration when prod_b J_b! <= 5000, else 5000
Monte Carlo relabellings (seeded, identical across variants), p = (1 + #{F* >= F})/(B + 1) (MC) or #{F* >= F}/n (exact,
identity included).
Reported families (point, p): pooled (4 model x set blocks, = pre-registered H3), RECAL-only, RAND-only, per model,
within model x method (blocks q4/q8 x {GPTQ d3,d4 | AWQ d3,d4 | Gaussian k=1 s2,s4,s5}; J = 2 blocks allow only 2
relabellings, p in {0.5, 1}; J = 3 allows 6, p_min 1/6; pooled over the 6 blocks 576 relabellings, p_min 1/576;
pooled over the 4 GPTQ/AWQ blocks only 16 relabellings, p_min 1/16).
Split-seed stability: main F for 3 extra split streams.
Simulation (--sim): false-rejection rate at alpha 0.05 under exchangeable synthetic data and power under a planted
checkpoint signal, for original / main / sensitivity, with Monte Carlo SE sqrt(p(1-p)/n_sim). Synthetic data are
resampled from the real per-task shift rows: for unit j of block b, each task row of its q1 and q2 draw is drawn from
that task's rows over all draws of block b (so draws are exchangeable within block, feature scales, missingness and
task structure are realistic). Planted signal: every task row of both draws of unit j gets + delta * g_j * s_f
(g_j ~ N(0, I_12), s_f = per-feature SD of the real per-task rows of the model). Sim settings: 20 splits, B = 199.

Usage:
  source scripts/a6000/env.sh; cd analysis/insights/iter_4
  python h3_corrected.py --snapshot /data/ziyangs/cloq/analysis/insights/iter_3/out/snapshot_live_20260930T0044Z.json
  python h3_corrected.py --snapshot <same> --sim [--n-sim 1000]
-> out/h3_corrected_<snapshot id>.json  (--sim: out/h3_corrected_sim_<snapshot id>.json)
"""
import argparse
import hashlib
import itertools
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = Path("/data/ziyangs/cloq")
B_PERM = 5000
N_SPLIT = 100
ALPHA = 0.05
LABEL = "corrected (post-hoc) re-analysis; NOT the pre-registered test"
ORIG = HERE / "out/prereg_h1_h4_CONF_20260930T0044Z.json"
PR = None


def setup(snapshot):
    """Import prereg_h1_h4 with the snapshot gate and wire its globals exactly as its main() does."""
    global PR
    os.environ["CLOQ_SNAPSHOT"] = str(Path(snapshot).resolve())
    sys.path.insert(0, str(HERE))
    import common4 as C4  # noqa: E402
    import p1_overdispersion as P1  # noqa: E402
    import prereg_h1_h4 as PR_  # noqa: E402
    PR_.C4, PR_.P1, PR_.C2 = C4, P1, sys.modules["common"]
    PR_.SNAP = PR_.C2.SNAP
    PR = PR_
    return PR_


def sha256(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def rnd(x, k=4):
    if x is None:
        return None
    if isinstance(x, (list, tuple, np.ndarray)):
        return [rnd(v, k) for v in list(x)]
    x = float(x)
    return None if not np.isfinite(x) else round(x, k)


# ------------------------------------------------------------------------------------------------ core statistic
def split_arrays(dl, units, tasks_idx, n_split, rng):
    """-> SA, SB (n_split, J, F): split shifts of the q1 draw on H and the q2 draw on the complement, per unit."""
    tasks_idx = np.asarray(tasks_idx)
    J, Fn = len(units), next(iter(dl.values())).shape[1]
    SA, SB = np.zeros((n_split, J, Fn)), np.zeros((n_split, J, Fn))
    with np.errstate(invalid="ignore"), _quiet():
        for s in range(n_split):
            perm = rng.permutation(tasks_idx)
            H, Hc = perm[: len(perm) // 2], perm[len(perm) // 2:]
            for j, (a, b) in enumerate(units):
                SA[s, j] = np.nanmean(dl[a][H], 0)
                SB[s, j] = np.nanmean(dl[b][Hc], 0)
    return SA, SB


class _quiet:
    def __enter__(self):
        import warnings
        self._w = warnings.catch_warnings(); self._w.__enter__(); warnings.simplefilter("ignore", RuntimeWarning)

    def __exit__(self, *a):
        self._w.__exit__(*a)


def scale_truepair(SA, SB):
    with _quiet():
        return np.sqrt(np.nanmean((SA - SB) ** 2, 1) / 2)  # (S, F)


def scale_pooled(SA, SB):
    """Unpaired pooled SD over the A-side and B-side shift vectors (each centred on its own side mean)."""
    with _quiet():
        ca = SA - np.nanmean(SA, 1, keepdims=True)
        cb = SB - np.nanmean(SB, 1, keepdims=True)
        ss = np.nansum(ca ** 2, 1) + np.nansum(cb ** 2, 1)
        n = np.sum(np.isfinite(SA), 1) + np.sum(np.isfinite(SB), 1)
        return np.sqrt(ss / np.maximum(n - 2, 1))


def cos_full(SA, SB, sd):
    """Mean over splits of the (J, J) cosine matrix of z_A rows vs z_B cols; returns (C, n_dropped, n_nan)."""
    keep = np.isfinite(sd) & (sd > 1e-9)  # (S, F)
    with _quiet():
        ZA = np.where(keep[:, None, :], SA / np.where(keep, sd, 1)[:, None, :], 0.0)
        ZB = np.where(keep[:, None, :], SB / np.where(keep, sd, 1)[:, None, :], 0.0)
    n_nan = int(np.sum(~np.isfinite(ZA)) + np.sum(~np.isfinite(ZB)))
    ZA, ZB = np.nan_to_num(ZA), np.nan_to_num(ZB)
    na, nb = np.linalg.norm(ZA, axis=2), np.linalg.norm(ZB, axis=2)
    with np.errstate(invalid="ignore", divide="ignore"):
        C = np.einsum("sif,skf->sik", ZA, ZB) / (na[:, :, None] * nb[:, None, :])
    C[~np.isfinite(C)] = np.nan
    with _quiet():
        return np.nanmean(C, 0), int((~keep).sum()), n_nan


def F_blocks(Cm, blocks, perms=None):
    """Cm: {model: (J, J) cos matrix}; blocks: list of (model, idx array); perms: list of idx permutations (per block)
    applied to the B side. J-weighted mean over blocks of mean diag - mean off-diag."""
    num = den = 0.0
    for bi, (m, idx) in enumerate(blocks):
        J = len(idx)
        cols = idx if perms is None else idx[perms[bi]]
        C = Cm[m][np.ix_(idx, cols)]
        off = ~np.eye(J, dtype=bool)
        with _quiet():
            num += J * (np.nanmean(np.diag(C)) - np.nanmean(C[off]))
        den += J
    return num / den if den else np.nan


def perm_space(Js, B, rng):
    n = math.prod(math.factorial(j) for j in Js)
    if n <= B:
        return [tuple(np.array(p) for p in combo) for combo in
                itertools.product(*[list(itertools.permutations(range(j))) for j in Js])], True
    return [tuple(rng.permutation(j) for j in Js) for _ in range(B)], False


def pval(T, Ts, exact):
    Ts = np.asarray(Ts)
    if exact:
        return float(np.mean(Ts >= T - 1e-12))
    return float((1 + np.sum(Ts >= T - 1e-12)) / (1 + len(Ts)))


def test_family(SAB, blocks, variant, B, rng):
    """SAB: {model: (SA, SB)}; blocks: list of (model, idx). variant in original | main | sensitivity."""
    Js = [len(i) for _, i in blocks]
    space, exact = perm_space(Js, B, rng)
    models = sorted({m for m, _ in blocks})
    if variant in ("original", "main"):
        f = scale_truepair if variant == "original" else scale_pooled
        Cm = {m: cos_full(*SAB[m], f(*SAB[m]))[0] for m in models}
        F = F_blocks(Cm, blocks)
        Fs = np.array([F_blocks(Cm, blocks, ps) for ps in space])
    else:  # sensitivity: recompute sd_w from the permuted pairs, per model
        Cm = {m: cos_full(*SAB[m], scale_truepair(*SAB[m]))[0] for m in models}
        F = F_blocks(Cm, blocks)
        Fs = np.zeros(len(space))
        for k, ps in enumerate(space):
            Cp = {}
            for m in models:
                SA, SB = SAB[m]
                col = np.arange(SA.shape[1])
                for (mm, idx), p in zip(blocks, ps):
                    if mm == m:
                        col[idx] = idx[p]
                SBp = SB[:, col]
                Cp[m] = cos_full(SA, SBp, scale_truepair(SA, SBp))[0]
            # permutation already applied to the B side: evaluate with identity column order
            Fs[k] = F_blocks(Cp, blocks)
    return dict(F=F, p=pval(F, Fs, exact), exact=exact, n_relabellings=len(space), perm_mean=float(np.mean(Fs)),
                perm_q95=float(np.quantile(Fs, 0.95)), p_min=(1 / len(space)) if exact else 1 / (1 + len(space)))


def block_detail(SAB, blocks, variant):
    f = scale_truepair if variant in ("original", "sensitivity") else scale_pooled
    out = {}
    for m, idx, name in blocks:
        SA, SB = SAB[m]
        C, nd, nn = cos_full(SA, SB, f(SA, SB))
        Cb = C[np.ix_(idx, idx)]
        off = ~np.eye(len(idx), dtype=bool)
        out[name] = dict(J=len(idx), same=rnd(np.nanmean(np.diag(Cb)), 3), diff=rnd(np.nanmean(Cb[off]), 3),
                         same_minus_diff=rnd(np.nanmean(np.diag(Cb)) - np.nanmean(Cb[off]), 3))
    return out


# ------------------------------------------------------------------------------------------------ families
def families(unit_meta):
    """unit_meta: {model: [dict(set, method, unit)]} -> {family name: [(model, idx, block name)]}."""
    fam = {"pooled": [], "RECAL_only": [], "RAND_only": [], "per_model:q4": [], "per_model:q8": [],
           "within_model_method": [], "within_model_method:RECAL": []}
    for m, us in unit_meta.items():
        for s in ("RECAL", "RAND"):
            idx = np.array([i for i, u in enumerate(us) if u["set"] == s])
            b = (m, idx, f"{m}:{s}")
            fam["pooled"].append(b)
            fam[f"{s}_only"].append(b)
            fam[f"per_model:{m}"].append(b)
        for meth in ("gptq_w4", "awq_w4", "gauss1"):
            idx = np.array([i for i, u in enumerate(us) if u["method"] == meth])
            b = (m, idx, f"{m}:{meth}")
            fam["within_model_method"].append(b)
            if meth != "gauss1":
                fam["within_model_method:RECAL"].append(b)
            fam[f"within:{m}:{meth}"] = [b]
    return fam


def run_family(SAB, fam_blocks, variant, B, name):
    rng = PR.rng_for(f"h3c:perm:{name}")  # same relabellings for every variant of a family
    r = test_family(SAB, [(m, i) for m, i, _ in fam_blocks], variant, B, rng)
    r["blocks"] = block_detail(SAB, fam_blocks, variant)
    tot = sum(b["J"] * b["same_minus_diff"] for b in r["blocks"].values() if b["same_minus_diff"] is not None)
    for b in r["blocks"].values():  # J-weighted contribution of each block to F
        b["share_of_F"] = rnd(b["J"] * b["same_minus_diff"] / tot, 3) if tot and b["same_minus_diff"] is not None else None
    return {k: (rnd(v, 5) if isinstance(v, float) else v) for k, v in r.items()}


# ------------------------------------------------------------------------------------------------ data
def load(snapshot, procs):
    setup(snapshot)
    units = PR.confirmatory_units()
    MD, dls, meta, tix = {}, {}, {}, {}
    for m in PR.MODELS:
        us = [u for u in units if u["model"] == m]
        us = [u for u in us if u["set"] == "RECAL"] + [u for u in us if u["set"] == "RAND"]
        runs = sorted({r for u in us for r in u["draws"]})
        D = PR.ModelData(m, runs, lambda r: None, procs)
        MD[m] = D
        dls[m] = {r: D.dl(r) for r in runs}
        meta[m] = us
        tix[m] = [D.tix[t] for t in D.tasks]
    return MD, dls, meta, tix


def build_SAB(dls, meta, tix, n_split, stream):
    return {m: split_arrays(dls[m], [tuple(u["draws"]) for u in meta[m]], tix[m], n_split, PR.rng_for(stream.format(m=m)))
            for m in meta}


# ------------------------------------------------------------------------------------------------ simulation
def _sim_one(args):
    seed, pools, s_f, delta, n_split, B = args
    rng = np.random.default_rng(seed)
    SAB = {}
    for m, (blocks_rows, J_sets) in pools.items():
        dl, units = {}, []
        for bset, rows in blocks_rows.items():  # rows: (n_draws_in_block, T, F)
            nd, T, Fn = rows.shape
            for j in range(J_sets[bset]):
                g = rng.standard_normal(Fn) * s_f[m] * delta
                for side in ("a", "b"):
                    pick = rng.integers(0, nd, T)
                    x = rows[pick, np.arange(T)] + g
                    dl[f"{bset}{j}{side}"] = x
                units.append((f"{bset}{j}a", f"{bset}{j}b"))
        T = next(iter(dl.values())).shape[0]
        SAB[m] = split_arrays(dl, units, np.arange(T), n_split, rng)
    blocks, off = [], {}
    for m, (blocks_rows, J_sets) in pools.items():
        k = 0
        for bset in blocks_rows:
            blocks.append((m, np.arange(k, k + J_sets[bset])))
            k += J_sets[bset]
    out = {}
    for v in ("original", "main", "sensitivity"):
        r = test_family(SAB, blocks, v, B, np.random.default_rng(seed + 1))
        out[v] = r["p"]
    return out


def simulate(dls, meta, n_sim, deltas, n_split, B, procs, seed0=20261005):
    pools, s_f = {}, {}
    for m in meta:
        br, Js = {}, {}
        for s in ("RECAL", "RAND"):
            us = [u for u in meta[m] if u["set"] == s]
            br[s] = np.array([dls[m][r] for u in us for r in u["draws"]])
            Js[s] = len(us)
        pools[m] = (br, Js)
        allr = np.concatenate([x.reshape(-1, x.shape[-1]) for x in br.values()])
        with _quiet():
            sd = np.nanstd(allr, 0)
        s_f[m] = np.nan_to_num(sd)
    res = {}
    for delta in deltas:
        jobs = [(seed0 + 7919 * i + int(1000 * delta), pools, s_f, delta, n_split, B) for i in range(n_sim)]
        with Pool(procs) as pool:
            ps = pool.map(_sim_one, jobs, chunksize=4)
        r = {}
        for v in ("original", "main", "sensitivity"):
            p = np.array([x[v] for x in ps])
            rate = float(np.mean(p < ALPHA))
            r[v] = dict(reject_rate=rnd(rate, 4), mc_se=rnd(math.sqrt(rate * (1 - rate) / n_sim), 4),
                        mean_p=rnd(p.mean(), 4))
        res[f"delta={delta}"] = dict(n_sim=n_sim, role="false-rejection rate (H0 exchangeable)" if delta == 0 else "power (planted checkpoint signal)", **r)
        print("sim delta", delta, r, flush=True)
    return res


# ------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--procs", type=int, default=8)
    ap.add_argument("--B", type=int, default=B_PERM)
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--n-sim", type=int, default=1000)
    ap.add_argument("--deltas", default="0,0.1,0.2,0.4")
    ap.add_argument("--sim-split", type=int, default=20)
    ap.add_argument("--sim-B", type=int, default=199)
    ap.add_argument("--sim-seed", type=int, default=20261005)
    a = ap.parse_args()
    MD, dls, meta, tix = load(a.snapshot, a.procs)
    sid = PR.SNAP["snapshot_id"]
    head = dict(label=LABEL, snapshot=dict(id=sid, path=str(Path(a.snapshot).resolve()), sha256=sha256(a.snapshot)),
                script=dict(path=str(Path(__file__).resolve()), sha256=sha256(__file__),
                            git_head=subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()),
                run_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                n_tasks={m: len(tix[m]) for m in meta}, features=list(PR.C4.DISP),
                units={m: [dict(set=u["set"], method=u["method"], unit=u["unit"], draws=list(u["draws"])) for u in meta[m]] for m in meta})
    if a.sim:
        deltas = [float(x) for x in a.deltas.split(",")]
        res = dict(head, sim=dict(settings=dict(n_split=a.sim_split, B=a.sim_B, alpha=ALPHA, generator="within-block resampling of real per-task shift rows; planted delta*g_j*s_f"),
                                  results=simulate(dls, meta, a.n_sim, deltas, a.sim_split, a.sim_B, a.procs, a.sim_seed)))
        res["sim"]["settings"]["seed0"] = a.sim_seed
        suf = ("" if (a.sim_split, a.sim_B) == (20, 199) else f"_s{a.sim_split}_B{a.sim_B}") + ("" if a.sim_seed == 20261005 else f"_seed{a.sim_seed}")
        p = HERE / "out" / f"h3_corrected_sim{suf}_{sid}.json"
        json.dump(res, open(p, "w"), indent=1)
        print("wrote", p)
        return
    SAB = build_SAB(dls, meta, tix, N_SPLIT, "split:primary:{m}")
    diag = {}
    for m, (SA, SB) in SAB.items():
        for v, f in (("truepair", scale_truepair), ("pooled", scale_pooled)):
            _, nd, nn = cos_full(SA, SB, f(SA, SB))
            diag[f"{m}:{v}"] = dict(n_feature_split_dropped=nd, n_nan_shift_entries=nn, of=int(SA.shape[0] * SA.shape[2]))
    fam = families(meta)
    out = {}
    for v in ("original", "main", "sensitivity"):
        out[v] = {}
        for name, blocks in fam.items():
            out[v][name] = run_family(SAB, blocks, v, a.B, name)
            print(v, name, {k: out[v][name][k] for k in ("F", "p", "exact", "n_relabellings")}, flush=True)
    # original reproduction check against the pre-registered output (H3 used its own relabelling stream)
    orig_conf = json.load(open(ORIG))["primary"]["H3"]
    rng = PR.rng_for("F:H3:primary")
    blocks = [(m, i) for m, i, _ in fam["pooled"]]
    space, exact = PR.perms_space([len(i) for _, i in blocks], PR.B_PERM, rng)
    Cm = {m: cos_full(*SAB[m], scale_truepair(*SAB[m]))[0] for m in SAB}
    F0 = F_blocks(Cm, blocks)
    p0 = pval(F0, [F_blocks(Cm, blocks, ps) for ps in space], exact)
    repro = dict(F_prereg=orig_conf["F_split"], p_prereg=orig_conf["p"], F_here=rnd(F0, 4), p_here=rnd(p0, 5),
                 match=bool(abs(F0 - orig_conf["F_split"]) < 1e-4 and abs(p0 - orig_conf["p"]) < 1e-9))
    print("reproduction", repro)
    # split-seed stability of the main statistic
    stab = {}
    for k in range(1, 4):
        S2 = build_SAB(dls, meta, tix, N_SPLIT, f"h3c:splitseed{k}:{{m}}")
        stab[f"seed{k}"] = {name: rnd(F_blocks({m: cos_full(*S2[m], scale_pooled(*S2[m]))[0] for m in S2},
                                               [(m, i) for m, i, _ in fam[name]]), 4)
                            for name in ("pooled", "RECAL_only", "RAND_only", "per_model:q4", "per_model:q8")}
    res = dict(head, reproduction_of_prereg=repro, preprocessing_diagnostics=diag, split_seed_stability_main_F=stab,
               settings=dict(B=a.B, n_split=N_SPLIT, alpha=ALPHA, split_stream="prereg rng_for('split:primary:<m>')",
                             perm_stream="rng_for('h3c:perm:<family>')"),
               results=out)
    p = HERE / "out" / f"h3_corrected_{sid}.json"
    json.dump(res, open(p, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print("wrote", p)


if __name__ == "__main__":
    main()
