"""EXPLORATORY, POST HOC (review 2026-10-05, W3): do fragile tasks dominate the tau2 core W4 consequences? Low base success?
Cells: tau2 retail/airline core W4 (q4/q8 x awq_w4/gptq_w4_d1), Bank P, 20 complete blocks x 85 tasks = 1,700 units per cell, loaded exactly
as offdiag_null.load_tau2 (analyze_ghf roots: analysis/fork/holdout/ is never opened). Per unit (analyze_dev.effects): r = 1[Y_BQ=1, Y_QQ=0],
d = 1[Y_BQ=0, Y_QQ=1], M = r + d, G = r - d; non-divergent units = 0 (full-pool denominator). Pool = equal-weight mean of the four cells.
Split (fixed before any outcome is read; `--write-split` writes it alone): half(b) = int(sha256('frag-v1|' + b), 16) mod 2 (A = 0, B = 1).
(1) Fragility of a task in the defining half = its mean M over the four cells and that half's blocks; top 20% = the 17 of 85 tasks with the
largest fragility (ties broken by sha256('frag-v1|' + task)). In the OTHER half: r, d, M, G for top-20% vs rest, their difference, and the
top-20% share of the held-out turnover (sum of M over top tasks / sum over all; 20% if fragility does not persist). Both directions (A->B, B->A).
(2) Conditional rates, all 20 blocks: rescue rate among QQ failures P(Y_BQ=1 | Y_QQ=0) = sum r / sum (1 - Y_QQ), damage rate among QQ
successes P(Y_BQ=0 | Y_QQ=1) = sum d / sum Y_QQ (ratios of sums per cell; non-divergent units are in the denominators).
(3) BF16 difficulty: task BF16 success rate from the nonce-matched BF16 closed-loop runs (a6k2_<model>_bfpair_<block>, retail/airline only,
infra-missing tasks dropped as analyze_difficulty.bf16_task_stats) in the defining half, per model; tertiles (analyze_difficulty.tertile_labels,
ties go low, so strata sizes are reported); r, d, M, G in the other half, both directions.
Intervals 95%: held-out halves (9-11 blocks): t over per-block pool values (primary: only 9 or 11 blocks)
and crossed task x block bootstrap (tasks resampled over all 85, blocks over the held-out half; group membership fixed by the defining half);
full pool: block bootstrap (primary, K = 20), t, crossed. B = 2000, seed 20261001 (analyze_dev.SEED). Strata are defined on one half and
estimated on the other, so selection on the outcome (regression to the mean) does not enter the held-out estimates.
usage: python analysis/fork/task_fragility.py [--write-split] [--B 2000] -> analysis/fork/out/task_fragility_<UTC>.{md,json}
"""
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, sys, time  # noqa: E401
from pathlib import Path
import numpy as np
from scipy.stats import t as tdist
sys.path.insert(0, str(Path(__file__).resolve().parent))
import offdiag_null as ON, analyze_difficulty as DF  # noqa: E401,E402

AD, ROOT, OUT = ON.AD, ON.AD.ROOT, ON.AD.OUT
CELLS, KEYS, TOP = ["q4:awq_w4", "q4:gptq_w4_d1", "q8:awq_w4", "q8:gptq_w4_d1"], ("r", "d", "M", "G"), 17
BF_RE = re.compile(r"^a6k2_(q\d+)_bfpair_(q\d+|f\d\d)$")
half = lambda b: int(hashlib.sha256(f"frag-v1|{b}".encode()).hexdigest(), 16) % 2  # noqa: E731
SPLIT_GLOB = "task_fragility_split_*.json"

def write_split(blocks) -> Path:
    sp = {"label": "EXPLORATORY, POST HOC split, written before outcomes", "rule": "half = int(sha256('frag-v1|'+block),16) % 2", "half": {b: half(b) for b in blocks}}
    (p := OUT / f"task_fragility_split_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json").write_text(json.dumps(sp, indent=1))
    return p

def mats(cu):
    """Per cell: (T x K) arrays of r, d, M, G, QQ over the common 85 tasks x 20 blocks (complete; asserted)."""
    tasks, blocks = sorted({u["task"] for u in cu[CELLS[0]]}), sorted({u["block"] for u in cu[CELLS[0]]})
    ti, bi, X = {t: i for i, t in enumerate(tasks)}, {b: i for i, b in enumerate(blocks)}, {}
    for c in CELLS:
        A, F = np.zeros((5, len(tasks), len(blocks))), np.zeros((len(tasks), len(blocks)))
        for u in cu[c]:
            Y, i, k = u["Y"], ti[u["task"]], bi[u["block"]]
            r, d = (int(Y["BQ"] == 1 and Y["QQ"] == 0), int(Y["BQ"] == 0 and Y["QQ"] == 1)) if u["div"] else (0, 0)
            A[:, i, k], F[i, k] = (r, d, r + d, r - d, Y["QQ"]), F[i, k] + 1
        assert (F == 1).all(), f"{c}: incomplete task x block grid"
        X[c] = dict(zip(KEYS + ("QQ",), A))
    return tasks, blocks, X

def bf16_rates(snap, tasks, blocks):
    """(model, half) -> task BF16 success rate over that half's bfpair blocks (retail/airline only)."""
    acc = {}
    for rid, doms in snap["frozen"].items():
        if not (m := BF_RE.match(rid)) or m.group(2) not in blocks:
            continue
        for dom, fr in doms.items():
            if dom not in ("retail", "airline") or not (p := ROOT / "runs" / rid / dom / "trajectory.jsonl").exists():
                continue
            infra = set(map(str, fr.get("infra_missing") or []))
            for ln in open(p):
                if str((t := json.loads(ln))["task_id"]) not in infra and t.get("termination_reason") != "infrastructure_error":
                    acc.setdefault((m.group(1), half(m.group(2)), f"{dom}:{t['task_id']}"), []).append(AD.success(dom, t))
    return {(mo, h): np.array([np.mean(acc.get((mo, h, t), [np.nan])) for t in tasks]) for mo in ("q4", "q8") for h in (0, 1)}, {f"{k[0]}:{k[1]}:{k[2]}": len(v) for k, v in acc.items()}

class Est:
    """Shared draws: crossed (tasks over all T, blocks over the evaluation blocks), block bootstrap; t over per-block pool values."""
    def __init__(self, T, kix, B, seed=AD.SEED):
        rng, K = np.random.default_rng(seed), len(kix)
        self.kix, self.Wt = kix, np.stack([np.bincount(rng.integers(0, T, T), minlength=T) for _ in range(B)]).astype(float)
        self.Vk, self.Vb = (np.stack([np.bincount(rng.integers(0, K, K), minlength=K) for _ in range(B)]).astype(float) for _ in range(2))

    def cell(self, num, den, m):
        """num, den (T x Kall); m (T,) bool. Returns point, per-block ratios, crossed draws, block-boot draws."""
        n, dd = (num[:, self.kix] * m[:, None]), (den[:, self.kix] * m[:, None])
        rat = lambda a, b: np.where(b > 0, a / np.maximum(b, 1e-12), np.nan)  # noqa: E731
        return (n.sum() / max(dd.sum(), 1e-12), rat(n.sum(0), dd.sum(0)), rat(np.einsum("rt,tk,rk->r", self.Wt, n, self.Vk), np.einsum("rt,tk,rk->r", self.Wt, dd, self.Vk)),
                rat(self.Vb @ n.sum(0), self.Vb @ dd.sum(0)))

    def pool(self, parts, f=100):
        pt, pb, cr, bb = (np.mean([p[i] for p in parts], 0) for i in range(4))
        q = lambda d: [round(f * float(x), 2) for x in np.nanpercentile(d, [2.5, 97.5])]  # noqa: E731
        pb = pb[np.isfinite(pb)]
        h = tdist.ppf(.975, len(pb) - 1) * pb.std(ddof=1) / np.sqrt(len(pb))
        return {"est": round(f * float(pt), 2), "t": [round(f * (pb.mean() - h), 2), round(f * (pb.mean() + h), 2)], "crossed": q(cr), "block": q(bb), "K": int(len(pb))}

def diff(a, b):
    return tuple(x - y for x, y in zip(a, b))

def strata_eval(E, X, groups, keys=KEYS):
    """groups: name -> {cell: mask}. Per group: pooled r, d, M, G; plus per-group cells (G only kept compact)."""
    one = np.ones_like(X[CELLS[0]]["r"])
    return {g: {k: E.pool([E.cell(X[c][k], one, ms[c]) for c in CELLS]) for k in keys} | {"n_tasks": {c: int(ms[c].sum()) for c in CELLS}} for g, ms in groups.items()}

def run(cu, snap, B):
    tasks, blocks, X = mats(cu)
    H = np.array([half(b) for b in blocks])
    one, T, res = np.ones((len(tasks), len(blocks))), len(tasks), {"blocks_by_half": {h: [b for b, x in zip(blocks, H) if x == h] for h in (0, 1)}}
    Ef = Est(T, np.arange(len(blocks)), B)
    res["full_pool"] = {"pool": {k: Ef.pool([Ef.cell(X[c][k], one, np.ones(T, bool)) for c in CELLS]) for k in KEYS},
                        "cells": {c: {k: Ef.pool([Ef.cell(X[c][k], one, np.ones(T, bool))]) for k in KEYS} for c in CELLS}}
    cond = {"rescue|QQ fail": ("r", lambda c: 1 - X[c]["QQ"]), "damage|QQ success": ("d", lambda c: X[c]["QQ"]), "P(QQ success)": ("QQ", lambda c: one)}
    res["conditional"] = {nm: {"pool": Ef.pool([Ef.cell(X[c][k], den(c), np.ones(T, bool)) for c in CELLS]), **{c: Ef.pool([Ef.cell(X[c][k], den(c), np.ones(T, bool))]) for c in CELLS}} for nm, (k, den) in cond.items()}
    bf, bf_n = bf16_rates(snap, tasks, blocks)
    tie = np.array([int(hashlib.sha256(f"frag-v1|{t}".encode()).hexdigest(), 16) for t in tasks], float)
    for dh in (0, 1):
        E, ev = Est(T, np.where(H != dh)[0], B), H == dh
        frag = np.mean([X[c]["M"][:, ev].mean(1) for c in CELLS], 0)
        top = np.zeros(T, bool)
        top[np.lexsort((-tie, -frag))[:TOP]] = True
        allm = np.ones(T, bool)
        tp, rs = ({c: m for c in CELLS} for m in (top, ~top))
        out = strata_eval(E, X, {"top20": tp, "rest": rs})
        out["top20 - rest"] = {k: E.pool([diff(E.cell(X[c][k], one, top), E.cell(X[c][k], one, ~top)) for c in CELLS]) for k in KEYS}
        out["top20 share of held-out turnover"] = E.pool([E.cell(X[c]["M"] * top[:, None], X[c]["M"], allm) for c in CELLS])
        out["defining half"] = {"top20 mean fragility M %": round(100 * frag[top].mean(), 2), "rest mean fragility M %": round(100 * frag[~top].mean(), 2),
                                "threshold M %": round(100 * frag[top].min(), 2), "tied at threshold (outside top)": int(((frag == frag[top].min()) & ~top).sum()), "top20 tasks": [t for t, x in zip(tasks, top) if x]}
        res[f"fragility define {'AB'[dh]} -> estimate {'AB'[1 - dh]}"] = out
        lab, cuts = {}, {}
        for mo in ("q4", "q8"):
            v = bf[(mo, dh)]
            assert np.isfinite(v).all(), f"BF16 rate missing for {mo} half {dh}"
            L, cuts[mo] = DF.tertile_labels(list(v))
            lab[mo] = np.array(L)
        so = strata_eval(E, X, {s: {c: lab[c[:2]] == s for c in CELLS} for s in ("T1", "T2", "T3")})
        so["T1 - T3"] = {k: E.pool([diff(E.cell(X[c][k], one, lab[c[:2]] == "T1"), E.cell(X[c][k], one, lab[c[:2]] == "T3")) for c in CELLS]) for k in KEYS}
        so["tertile cuts (BF16 success rate)"] = cuts
        so["conditional in held-out half"] = {s: {nm: E.pool([E.cell(X[c][k], den(c), lab[c[:2]] == s) for c in CELLS]) for nm, (k, den) in list(cond.items())[:2]} for s in ("T1", "T2", "T3")}
        res[f"BF16 difficulty define {'AB'[dh]} -> estimate {'AB'[1 - dh]}"] = so
    return res, {"bf16_task_blocks_counted": len(bf_n), "bf16_episodes": int(sum(bf_n.values()))}

def md(o, jp):
    f = lambda x: f"{x['est']:+.2f} [t {x['t'][0]:+.2f}, {x['t'][1]:+.2f}; crossed {x['crossed'][0]:+.2f}, {x['crossed'][1]:+.2f}]"  # noqa: E731
    fb = lambda x: f"{x['est']:.2f} [block {x['block'][0]:.2f}, {x['block'][1]:.2f}; t {x['t'][0]:.2f}, {x['t'][1]:.2f}; crossed {x['crossed'][0]:.2f}, {x['crossed'][1]:.2f}]"  # noqa: E731
    R, L = o["results"], [f"# Task fragility and difficulty strata, tau2 core W4 (EXPLORATORY, POST HOC; {o['utc']})", "",
                          f"Script `analysis/fork/task_fragility.py` (sha256 {o['sources_sha256']['analysis/fork/task_fragility.py'][:16]}), git {o['git_head'][:10]}, B = {o['B']}, seed {o['seed']}. Full numbers: `{jp.relative_to(ROOT)}`. Split file: `{o['split_file']}`. All values in % (pp for G and differences).", "",
                          "## Full pool (primary; 4 cells equal weight, 20 blocks x 85 tasks per cell)", ""]
    L += [f"- pool {k}: {fb(v)}" for k, v in R["full_pool"]["pool"].items()] + [f"- {c} M: {fb(v['M'])}; G: {fb(v['G'])}" for c, v in R["full_pool"]["cells"].items()]
    L += ["", "## Conditional rates (all 20 blocks)", ""] + [f"- {nm} {c}: {fb(v)}" for nm, d in R["conditional"].items() for c, v in d.items()]
    for nm in [k for k in R if k.startswith("fragility")]:
        x = R[nm]
        L += ["", f"## Split-half fragility: {nm}", "", f"- defining half: {json.dumps({k: v for k, v in x['defining half'].items() if k != 'top20 tasks'})}", "| group | r | d | M | G |", "|---|---|---|---|---|"]
        L += [f"| {g} | {' | '.join(f(x[g][k]) for k in ('r', 'd', 'M', 'G'))} |" for g in ("top20", "rest", "top20 - rest")]
        L += ["", f"- top-20% share of held-out turnover (20.0 if fragility does not persist): {f(x['top20 share of held-out turnover'])}"]
    for nm in [k for k in R if k.startswith("BF16")]:
        x = R[nm]
        L += ["", f"## BF16 difficulty tertiles: {nm} (cuts {x['tertile cuts (BF16 success rate)']}; T1 = hardest)", "", "| stratum | tasks per cell | r | d | M | G |", "|---|---|---|---|---|---|"]
        L += [f"| {g} | {list(x[g]['n_tasks'].values()) if 'n_tasks' in x[g] else '–'} | {' | '.join(f(x[g][k]) for k in ('r', 'd', 'M', 'G'))} |" for g in ("T1", "T2", "T3", "T1 - T3")]
        L += [f"- {s}: " + "; ".join(f"{nm2} {f(v)}" for nm2, v in d.items()) for s, d in x["conditional in held-out half"].items()]
    L += ["", "## Method", "", "```", __doc__.strip(), "```", "", "## Data sources (sha256)", ""] + [f"- `{p}` {s}" for p, s in o["sources_sha256"].items()]
    return "\n".join(L + [f"- units digest per cell: {o['units_digest']}", f"- BF16 inputs: {o['bf16']}"]) + "\n"

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--B", type=int, default=AD.B_BOOT), ap.add_argument("--write-split", action="store_true")
    a, t0 = ap.parse_args(), time.time()
    cu = ON.load_tau2()
    if a.write_split:  # reads block ids only
        return print(f"task_fragility: wrote {write_split(sorted({u['block'] for u in cu[CELLS[0]]})).relative_to(ROOT)}")
    sp = sorted(OUT.glob(SPLIT_GLOB))[0]
    assert all(half(b) == h for b, h in json.load(open(sp))["half"].items()), "split file disagrees with the rule"
    snap = json.load(open(ROOT / ON.G.DEF_SNAPSHOT))
    res, bfi = run(cu, snap, a.B)
    src = [ON.G.DEF_SNAPSHOT, "manifests/fork/splits_v1.json", str(sp.relative_to(ROOT))] + [f"analysis/fork/{x}.py" for x in ("analyze_dev", "analyze_ghf", "analyze_difficulty", "offdiag_null", "task_fragility")]
    o = {"label": "EXPLORATORY, POST HOC (not pre-registered)", "utc": (utc := time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())), "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "B": a.B, "seed": AD.SEED, "split_file": str(sp.relative_to(ROOT)), "sources_sha256": {p: AD.sha256(ROOT / p) for p in src}, "units_digest": {c: AD.units_digest(cu[c])[:16] for c in CELLS}, "bf16": bfi, "results": res, "seconds": round(time.time() - t0)}
    (jp := OUT / f"task_fragility_{utc}.json").write_text(json.dumps(o, indent=1, default=float))
    (OUT / f"task_fragility_{utc}.md").write_text(md(o, jp))
    print(f"task_fragility: wrote {jp.relative_to(ROOT)} and .md ({o['seconds']} s)")

if __name__ == "__main__":
    main()
