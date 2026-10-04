"""EXPLORATORY, POST HOC (not pre-registered): the off-diagonal share P(Delta_Q != Delta_B) against chance nulls.
State arms (Y_BB, Y_BQ, Y_QB, Y_QQ) in {0,1}, k = #successes; Delta_Q = Y_BQ - Y_QQ, Delta_B = Y_BB - Y_QB, I = Delta_Q - Delta_B (method.tex).
Off-diagonal <=> k odd, or k = 2 with a strict reversal (1001, 0110). Per state, exchangeable-branch null (labels permuted given k):
E0 = 1[k odd] + 1[k=2]/3, so obs - E0 = 1[rev] - 1[k=2]/3; independent re-roll null (4 iid Bernoulli(p = k/4)): E_ind = 1 - [(1-p)^4 +
4p^2(1-p)^2 + p^4]. Ratios of sums over a cell's states; pools = equal-weight mean of cell ratios on common blocks (analyze_ghf.pool).
CIs: block bootstrap (analyze_dev.Boot, B = 2000, seed 20261001; t over per-block ratios primary if K < 10) and task-cluster bootstrap
(Boot.Wc); BFCL/ALFWorld: stratified item bootstrap (analyze_ext.StratBoot) in both. Count tests (states independent: clustering
ignored): exact binomial P(rev|k=2) = 1/3; MC exact multinomial (chi-square statistic, R = 20000) of the k = 2 pair type (action
1100/0011, continuation 1010/0101, reversal) vs 1/3 and of the odd arm at k = 1 (only success) / k = 3 (only failure) vs 1/4.
Task share of var(I), var(off): one-way random-effects moments over tasks, s2 = (MSB - MSW)/n0, n0 = (N - sum n_j^2/N)/(J - 1),
share = s2/(s2 + MSW) (untruncated); task bootstrap CI; permutation p (values permuted among the states of each block).
Inputs only via existing loaders; analysis/fork/holdout/ is never opened (holdout: 16-pattern counts stored in HOLD).
usage: python analysis/fork/offdiag_null.py [--B 2000] [--R 2000] [--selftest] -> analysis/fork/out/offdiag_null_<UTC>.{md,json}
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, time, warnings  # noqa: E401
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import binomtest, chisquare, t as tdist
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD, analyze_ext as AE, analyze_ghf as G, analyze_sameprec as S  # noqa: E401,E402

np.seterr(invalid="ignore", divide="ignore"), warnings.simplefilter("ignore", RuntimeWarning)
ROOT, OUT, ARMS, R_MC = AD.ROOT, AD.OUT, ("BB", "BQ", "QB", "QQ"), 20000
GHF, HOLD, EXTR2 = (f"analysis/fork/out/{x}.json" for x in ("ghf_20261001T211519Z", "holdout_r2_posthoc_20261002T024414Z", "ext_r2_20261002T024433Z"))
SP = {"W4": ("manifests/fork/sameprec_v1.json", "analysis/fork/out/sameprec_20261003T023857Z.json", "gptq_w4_d1"),
      "W3": ("manifests/fork/sameprec_w3_v1.json", "analysis/fork/out/sameprec_w3_20261003T023933Z.json", "gptq_w3")}
STATS = [("off", "off", "one"), ("E0", "e0", "one"), ("obs-E0", "d0", "one"), ("E_ind", "eind", "one"), ("obs-E_ind", "dind", "one"), ("P(k odd)", "kodd", "one"),
         ("P(k=2)", "k2", "one"), ("P(rev)", "rev", "one"), ("P(rev|k=2)", "rev", "k2"), ("P(act|k=2)", "k2act", "k2"), ("P(cont|k=2)", "k2cont", "k2"), ("mean I", "I", "one")]
STATS += [(f"k{k}:{a}", f"k{k}{a}", f"k{k}") for k in (1, 3) for a in ARMS]
TESTS = (("k2 type act/cont/rev", [("1100", "0011"), ("1010", "0101"), ("1001", "0110")]), ("k1 odd BB/BQ/QB/QQ", [("1000",), ("0100",), ("0010",), ("0001",)]),
         ("k3 odd BB/BQ/QB/QQ", [("0111",), ("1011",), ("1101",), ("1110",)]))
PLAIN = ("On the success scale Δ_Q ≠ Δ_B holds exactly when k is odd (one arm differs from the other three) or when k = 2 with the two successes on a diagonal (BB+QQ or BQ+QB: the strict reversals). Every odd-k state is off-diagonal however its four outcomes are assigned to the arms, so most of the share counts states whose four arms do not split 0/4, 2/2 or 4/4, and against the exchangeable-branch null it can only rise through reversals above 1/3 of the k = 2 states. "
         "Odd-k patterns are also what a success threshold on additive action and continuation effects produces (a removable, scale-dependent interaction): under any deterministic additive latent score per state (arm score = action term + continuation term), BB + QQ and BQ + QB have equal sums, so only the strict reversals are impossible (checked in --selftest). "
         "The share is therefore a correct count of states whose action effect differs between continuations on the success scale (exact replay rules out replay noise), but not evidence of crossover coupling beyond chance: crossover states are the reversals, and they are rarer than chance. Structure shows in the arrangement (k = 2 successes sharing the action, i.e. action main effects; which arm is the odd one) and in task reproducibility (task share of variance). The independent re-roll null is weaker: it does not keep k and puts no off-diagonal mass on k = 0 or 4 states.")

def feats(pat: str) -> dict:
    k, dq, db, p = sum(y := [int(c) for c in pat]), y[1] - y[3], y[0] - y[2], sum(y) / 4
    f = {"one": 1, "off": int(dq != db), "e0": k % 2 + (k == 2) / 3, "eind": 1 - ((1 - p) ** 4 + 4 * p * p * (1 - p) ** 2 + p ** 4), "kodd": k % 2,
         "k1": int(k == 1), "k2": int(k == 2), "k3": int(k == 3), "rev": int(dq * db < 0), "I": dq - db, "k2act": int(pat in ("1100", "0011")),
         "k2cont": int(pat in ("1010", "0101")), **{f"k{j}{a}": int(k == j and y[i] == (j == 1)) for j in (1, 3) for i, a in enumerate(ARMS)}}
    return {**f, "d0": f["off"] - f["e0"], "dind": f["off"] - f["eind"]}

FE = {f"{i:04b}": feats(f"{i:04b}") for i in range(16)}
pts = lambda cnt: {nm: {"est": round(100 * sum(c * FE[p][u] for p, c in cnt.items()) / max(1e-12, sum(c * FE[p][d] for p, c in cnt.items())), 2)} for nm, u, d in STATS}  # noqa: E731
recs = lambda us, ext=False: [{"task": u["task"], "b": u["task"] if ext else u["block"], "div": bool(u.get("div")), "pat": "".join(str(int(u["Y"][a])) for a in ARMS)} for u in us]  # noqa: E731

def ratio(bt, st, num, den):
    ix = {by: np.array([(bt.bix if by == "b" else bt.tix)[s[by]] for s in st], int) for by in ("b", "task")}
    Sb, Nb, St, Nt = (np.bincount(ix[by], [FE[s["pat"]][k] for s in st], minlength=len(bt.bix if by == "b" else bt.tix)) for by in ("b", "task") for k in (num, den))
    return Sb.sum() / Nb.sum(), (bt.Vb @ Sb) / (bt.Vb @ Nb), (bt.Wc @ St) / (bt.Wc @ Nt), np.where(Nb > 0, Sb / np.maximum(Nb, 1e-12), np.nan)

def summ(pt, bb, tb, pb, f=100) -> dict:
    q = lambda d: [round(f * float(x), 2) for x in np.nanpercentile(d, [2.5, 97.5])] if np.isfinite(d).any() else None  # noqa: E731
    pb = pb[np.isfinite(pb)]
    h = tdist.ppf(.975, len(pb) - 1) * pb.std(ddof=1) / np.sqrt(len(pb)) if 1 < len(pb) < 10 else None
    return {"est": round(f * float(pt), 2), "block": q(bb), "task": q(tb), "t": None if h is None else [round(f * (pb.mean() - h), 2), round(f * (pb.mean() + h), 2)]}

def mom(n, Sj, Qj, w):
    N, J, A = (w * n).sum(-1), (w * (n > 0)).sum(-1), np.where(n > 0, Sj * Sj / np.maximum(n, 1), 0)
    msb, msw = ((w * A).sum(-1) - (w * Sj).sum(-1) ** 2 / N) / (J - 1), (w * (Qj - A)).sum(-1) / (N - J)
    s2 = (msb - msw) / ((N - (w * n * n).sum(-1) / N) / (J - 1))
    return s2 / (s2 + msw)

def icc(bt, st, key, R, seed=AD.SEED):
    st, rng = sorted(st, key=lambda s: s["b"]), np.random.default_rng(seed)  # block-sorted, so lexsort((rand, block)) permutes within blocks
    tj, bj, y = np.array([bt.tix[s["task"]] for s in st], int), np.array([s["b"] for s in st]), np.array([FE[s["pat"]][key] for s in st], float)
    Tm, Yp = np.eye(len(bt.tix))[tj], np.array([y[np.lexsort((rng.random(len(y)), bj))] for _ in range(R)])
    return None if ((n := Tm.sum(0)) > 1).sum() < 2 else (mom(n, y @ Tm, y * y @ Tm, 1.0), mom(n, y @ Tm, y * y @ Tm, bt.Wc), mom(n, Yp @ Tm, (Yp * Yp) @ Tm, 1.0))

def tests(cnt: dict, seed=AD.SEED) -> dict:
    rng, out = np.random.default_rng(seed), {}
    for nm, cats in TESTS:
        o = np.array([sum(cnt.get(x, 0) for x in c) for c in cats])
        chi = lambda x, e=o.sum() / len(o): (((x - e) ** 2) / e).sum(-1)  # noqa: E731
        out[nm] = {"counts": o.tolist(), "n": int(o.sum())} | ({"chi2": round(float(chi(o)), 2), "p_chi2": float(chisquare(o).pvalue),
                   "p_mc": float((1 + (chi(rng.multinomial(o.sum(), [1 / len(o)] * len(o), size=R_MC)) >= chi(o) - 1e-9).sum()) / (R_MC + 1))} if o.sum() else {})
    return out | {"rev|k2 binom 1/3": {"rev": (rv := out[TESTS[0][0]]["counts"][2]), "n_k2": n2, "p_two": binomtest(rv, n2, 1 / 3).pvalue, "p_greater": binomtest(rv, n2, 1 / 3, "greater").pvalue} if (n2 := out[TESTS[0][0]]["n"]) else None}

def group(cu, labs, B, R, bt=None) -> dict:
    """Cells labs -> equal-weight summaries with shared draws, task variance shares (tau2 only), count-summed tests."""
    if bt is None:
        com, bo = set.intersection(*[{r["b"] for r in cu[l]} for l in labs]), defaultdict(set)
        [bo[r["task"]].add(r["b"]) for l in labs for r in cu[l] if r["b"] in com]
        bt = AD.Boot(sorted(bo), {t: sorted(v) for t, v in bo.items()}, B=B)
    st = {l: [r for r in cu[l] if r["div"] and r["b"] in bt.bix] for l in labs}
    res = {"cells": labs, "n_states": sum(map(len, st.values())), "K": len(bt.bix)}
    for nm, num, den in STATS:
        Rs = [ratio(bt, st[l], num, den) for l in labs]
        res[nm] = summ(*(np.mean([x[i] for x in Rs], 0) for i in range(3)), np.nanmean([x[3] for x in Rs], 0))
    for key in ("I", "off") if bt.Vb is not bt.Wc else ():
        if None not in (Ic := [icc(bt, st[l], key, R) for l in labs]):
            pt, bd, pm = (np.mean([x[i] for x in Ic], 0) for i in range(3))
            res[f"task_share_{key}"] = {"est": round(float(pt), 3), "task": [round(float(x), 3) for x in np.nanpercentile(bd, [2.5, 97.5])], "perm_p": float((1 + (pm >= pt - 1e-12).sum()) / (R + 1))}
    cnt = Counter(r["pat"] for l in labs for r in st[l])
    return {**res, "counts16": dict(sorted(cnt.items())), "tests": tests(cnt)}

def load_tau2() -> dict:
    loaded = [AD.load_dir(d, snap, {}) for snap in [json.load(open(ROOT / G.DEF_SNAPSHOT))] for d in G.discover()]  # analyze_ghf roots exclude analysis/fork/holdout
    AD.split_guard(allu := [u for L in loaded for u in L["units"]], "dev", "offdiag_null")
    [u.setdefault("excluded", "quarantined fork task (QQ no-op mismatch)") for L in loaded if L["quarantined"] for u in L["units"]]
    units, _ = AD.dedupe_units(allu)
    AD.mark_incomplete_blocks(units, "dev", strict=True)
    AD.mark_partial_panel_blocks(units, "dev")
    cu = defaultdict(list)
    [cu[("tel:" if u["domain"] == "telecom" else "") + f"{u['model']}:{u['cell']}"].append(u) for u in units if "excluded" not in u]
    return cu

def load_sp(tag: str):
    man, ref = json.load(open(ROOT / SP[tag][0])), json.load(open(ROOT / SP[tag][1]))
    S.guard(man) if tag == "W4" else (AD.sha256(ROOT / man["protocol"]) == man["protocol_sha256"] or sys.exit("offdiag_null: W3 protocol sha256 mismatch"))
    S.CELL, blocks = SP[tag][2], ref["analysis_set"]["blocks"]
    U, _, meta = S.admit([d for m in man["cells"] for d in S.dirs_under(man["sameprec_dirs"][m])], json.load(open(ROOT / man.get("snapshot", G.DEF_SNAPSHOT))))
    return {m: [u for u in U if "excluded" not in u and u["block"] in blocks and u["model"] == m] for m in man["cells"]}, blocks, meta["files_digest"], ref

def load_ext(B: int):
    AE.superseded_pending(["q4", "q8", "q14"]) and sys.exit("offdiag_null: W99o ext reruns pending")
    L = [x for x in (AE.load_dir(d) for d in AE.select_dirs(AE.DEV, None, ["q4", "q8", "q14"])) if not x["incomplete"]]
    AE.replay_guard(L, "offdiag_null")
    strata, cu = defaultdict(set), defaultdict(list)
    [(strata[u["stratum"]].add(u["task"]), cu[f"{u['env']}:{u['cell']}"].append(u)) for x in L if not x["quarantined"] for u in x["units"] if "excluded" not in u]
    sb = AE.StratBoot({s: sorted(v) for s, v in strata.items()}, B=B)
    dg = hashlib.sha256(json.dumps({k: v for x in L for k, v in x["files"].items()}, sort_keys=True).encode()).hexdigest()
    return {k: recs(v, True) for k, v in cu.items()}, type("ItemBoot", (), {"Vb": sb.W, "Wc": sb.W, "tix": sb.tix, "bix": sb.tix})(), dg, [x["dir"] for x in L if x["quarantined"]]

def md(o: dict, jp: Path) -> str:
    g, h, ck, w, kv = o["groups"], o["holdout_counts_only"], o["checks"], o["groups"]["pool W4:all"], o["groups"]["pool KV8:all"]
    f = lambda x, c="block": "–" if not x else f"{x['est']:+.1f}" + (f" [{x[c][0]:+.1f}, {x[c][1]:+.1f}]" if x.get(c) else "")  # noqa: E731
    pr, e, ft = (lambda x: f(x, "t" if x.get("t") else "block")), (lambda x: "–" if not x else f"{x['est']:.1f}"), (lambda x: f(x, "task"))  # noqa: E731
    s4 = lambda x: "–" if not x else f"{x['est']:+.3f} [{x['task'][0]:+.3f}, {x['task'][1]:+.3f}], perm p {x['perm_p']:.3g}"  # noqa: E731
    tp = lambda nm: lambda t: f"{'/'.join(map(str, t[nm]['counts']))} (p {t[nm]['p_mc']:.2g})" if t and "p_mc" in t.get(nm, {}) else "–"  # noqa: E731
    bp = lambda t: f"{t['rev|k2 binom 1/3']['p_two']:.2g}" if t and t.get("rev|k2 binom 1/3") else "–"  # noqa: E731
    C = {1: [("states", "n_states", str), ("K", "K", str), ("off %", "off", e), ("E0 %", "E0", e), ("obs − E0 pp [block or t]", "obs-E0", pr), ("obs − E0 [task boot]", "obs-E0", ft), ("E_ind %", "E_ind", e), ("obs − E_ind pp [block or t]", "obs-E_ind", pr)],
         2: [("P(k odd) %", "P(k odd)", e), ("P(rev) %", "P(rev)", e), ("P(k=2) %", "P(k=2)", e), ("P(rev given k=2) % [task boot]", "P(rev|k=2)", ft), ("binom p vs 1/3", "tests", bp)] + [(f"{t} (MC p)", "tests", tp(t)) for t, _ in TESTS],
         4: [("mean I pp [block or t]", "mean I", pr), ("task share of var(I) [task boot]", "task_share_I", s4), ("task share of var(off) [task boot]", "task_share_off", s4)]}
    T = lambda c, it: "\n".join([f"| group | {' | '.join(n for n, _, _ in C[c])} |", "|---" * (len(C[c]) + 1) + "|"] + [f"| {n} | {' | '.join(fn(v[k]) if k in v else '–' for _, k, fn in C[c])} |" for n, v in it]) + "\n"  # noqa: E731
    sec = lambda *s: [(n, v) for n, v in g.items() if v["section"] in s]  # noqa: E731
    lo = {n: (v["obs-E0"]["t"] or v["obs-E0"]["block"]) for n, v in g.items()}
    st = [n for n, v in list(g.items()) + list(h.items()) if not n.startswith("pool") and "tests" in v and any(v["tests"][t].get("p_mc", 1) < 1e-3 for t, _ in TESTS)]
    L = [f"**TL;DR** EXPLORATORY, POST HOC. The off-diagonal share {'exceeds' if lo['pool W4:all'][0] > 0 else 'is below' if lo['pool W4:all'][1] < 0 else 'does not differ from'} exchangeable-branch chance: W4 pool {e(w['off'])}% vs E0 {e(w['E0'])}% "
         f"(obs − E0 {f(w['obs-E0'])} pp), KV8 pool {e(kv['off'])}% vs {e(kv['E0'])}% ({f(kv['obs-E0'])}); lower bound > 0 in {sum(v[0] > 0 for v in lo.values())} of {len(lo)} groups, upper bound < 0 in {sum(v[1] < 0 for v in lo.values())}. Odd-k states (W4 pool {e(w['P(k odd)'])} of the {e(w['off'])} points) are off-diagonal under any labelling, so obs − E0 = P(k=2)(P(rev|k=2) − 1/3); P(rev|k=2) = {e(w['P(rev|k=2)'])}% (W4 pool).",
         f"Structure is in the arrangement: at k = 2 the two successes share the action in {e(w['P(act|k=2)'])}% of W4 states (chance 33.3%); count tests with MC p < 0.001 (k=2 type or odd arm): {', '.join(st) or 'none'}. Task share of var(I): W4 pool {s4(w.get('task_share_I'))}; mean I {f(w['mean I'])} pp (paper +0.0 [−1.9, +2.0]).", "",
         f"# Off-diagonal share vs chance nulls (EXPLORATORY, POST HOC; {o['utc']})", "", f"Script `analysis/fork/offdiag_null.py` (sha256 {o['sources_sha256']['analysis/fork/offdiag_null.py'][:16]}), git {o['git_head'][:10]}, B = {o['B']}, permutations {o['R_perm']}, "
         f"MC draws {o['R_mc']}, seed {o['seed']}. Full numbers: `{jp.relative_to(ROOT)}`. Sign: I = Δ_Q − Δ_B as in method.tex and analyze_ghf (with I = Δ_B − Δ_Q the mean flips sign; shares are unchanged). Primary interval: t over per-block ratios when K < 10, else block bootstrap.", "",
         "## 0. Reproduction of the paper's table (`analysis/fork/out/ghf_20261001T211519Z.json`)", "", "| cell | off % ours | off % ghf | units digest = ghf |", "|---|---|---|---|"] + [f"| {l} | {a:.2f} | {b:.2f} | {d} |" for l, (a, b, d) in ck["tau2_cells"].items()] + [""]
    L += [f"- {p}: ours {f(a)}, ghf {b['est']:+.3f} {b['ci95']}" for p, (a, b) in ck["pools"].items()] + [f"- ext_r2 {l}: ours {f(a)}, ext_r2 {b['est']:+.2f} {b['ci95']}" for l, (a, b) in ck["ext_r2"].items()]
    L += [f"- same-precision states [ours, cited output]: {o['sameprec']}", "", "## 1 and 3. Observed share vs E0 (exchangeable branches) and E_ind (independent re-roll): τ² development cells and pools", "", T(1, sec("main")),
          "## 2. Decomposition and structure (pool count tests are count-summed over the pool's cells; p values ignore task clustering)", "", T(2, sec("main")), "## 4. Mean I and task share of variance", "", T(4, sec("main")),
          "## 5. Other four-arm designs", "", "Reached: telecom dev (tel:, q8 W4, 6 blocks); same-precision W4 (Q' = second GPTQ-W4 draw in the B role; cited K = 6 analysis set) and W3 (q3-q5), and the BF16 design on the same blocks (prec*); "
          "BFCL multi-turn and ALFWorld (q4/q8, q14 BFCL; stratified item bootstrap in both interval columns, K = number of items; one run per item, so no task-variance split); telecom holdout: point estimates and count tests from the 16-pattern counts stored in "
          f"`{HOLD}` (no unit data, since analysis/fork/holdout/ is not opened: no intervals). Not computed: Bank U / common-state panels (ordinary states, no Bank P off-diagonal in the paper; common-state is a 3-source x 2-continuation "
          "confirmatory design), SIMCTRL-P (stochastic replicates: off-diagonal undefined; its script forbids the comparison), new-method panels (frozen confirmatory analysis in progress: not read).", "",
          T(1, sec("other", "ext") + list(h.items())), T(2, sec("other", "ext") + list(h.items())), T(4, sec("other")), "## Method", "", "```", __doc__.strip(), "```", "", "## Data sources (sha256)", ""]
    return "\n".join(L + [f"- `{p}` {s}" for p, s in o["sources_sha256"].items()] + [f"- ext input files digest {o['ext_files_digest']} (quarantined: {o['ext_quarantined_dirs']})", "", "## What the off-diagonal share measures", "", PLAIN]) + "\n"

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    [ap.add_argument(f"--{n}", type=int, default=v) for n, v in (("B", AD.B_BOOT), ("R", 2000))], ap.add_argument("--selftest", action="store_true")
    t0, a, ghf, cu, sp, W4 = time.time(), ap.parse_args(), json.load(open(ROOT / GHF)), load_tau2(), {}, ["q4:awq_w4", "q4:gptq_w4_d1", "q8:awq_w4", "q8:gptq_w4_d1"]
    Rd = {l: recs(v) for l, v in cu.items()}
    for tag in SP:
        U, blocks, dg, ref = load_sp(tag)
        Rd |= {f"{d}{tag}:{m}": recs(us) if d == "same" else [r for r in Rd[f"{m}:{SP[tag][2]}"] if r["b"] in blocks] for m, us in U.items() for d in ("same", "prec")}
        sp[tag] = {"blocks": blocks, "files_digest": dg, "n_states [ours, cited]": {f"{d}:{m}": [sum(r["div"] for r in Rd[f"{d}{tag}:{m}"]), ref["cells"][m][d]["n_states"]] for m in U for d in ("same", "prec")}}
    Rd |= (E := (ext := load_ext(a.B))[0])
    gs = [("main", l, [l], None) for l in ghf["cells"]] + [("main", f"pool {p}", c, None) for p, c in (("W4:q4", W4[:2]), ("W4:q8", W4[2:]), ("W4:all", W4), ("KV8:all", ["q4:kvq_int8", "q8:kvq_int8"]))]
    for x, c in [("tel:q8", ["awq_w4", "gptq_w4_d1"])] + [(d + t, ["q4", "q8"]) for t in SP for d in ("same", "prec")]:
        gs += [("other", f"{x}:{y}", [f"{x}:{y}"], None) for y in c] + [("other", f"pool {x}", [f"{x}:{y}" for y in c], None)]
    gs += [("ext", l, [l], ext[1]) for l in sorted(E)] + [("ext", f"pool W4:{v}", [l for l in sorted(E) if l.split(":")[0] == v and "q14" not in l and "w4" in l], ext[1]) for v in ("bfcl", "alfworld")]
    res = {n: {"section": s, **group(Rd, c, a.B, a.R, bt)} for s, n, c, bt in gs}
    hold = {f"holdout {l}": {"weight": c["prereg_weight"], "n_states": sum(c["patterns16"]["counts"].values()), "tests": tests(c["patterns16"]["counts"]), **pts(c["patterns16"]["counts"])} for l, c in json.load(open(ROOT / HOLD))["cells"].items()}
    hold["holdout pool (prereg weights)"] = {"n_states": sum(v["n_states"] for v in hold.values()), **{nm: {"est": round(sum(v["weight"] * v[nm]["est"] for v in hold.values()), 2)} for nm, _, _ in STATS}}
    ck = {"tau2_cells": {l: [res[l]["off"]["est"], round(c["stats"]["offdiag"]["est"], 2), AD.units_digest(cu[l])[:16] == ghf["units_digest_check"][l]["digest"]] for l, c in ghf["cells"].items()},
          "pools": {f"{p} {k}": [res[f"pool {p}"][k], ghf["pools"][p]["stats"][q]] for p in ("W4:all", "KV8:all") for k, q in (("off", "offdiag"), ("mean I", "I"))},
          "ext_r2": {l: [res[l]["off"], c["pp_on_divergent"]["offdiag"]] for l, c in json.load(open(ROOT / EXTR2))["cells"].items()}}
    src = [G.DEF_SNAPSHOT, "manifests/fork/splits_v1.json", GHF, HOLD, EXTR2] + [p for v in SP.values() for p in v[:2]] + [f"analysis/fork/{f}.py" for f in ("analyze_dev", "analyze_ghf", "analyze_sameprec", "analyze_ext", "offdiag_null")]
    o = {"label": "EXPLORATORY, POST HOC (not pre-registered)", "utc": (utc := time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())), "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "B": a.B, "R_perm": a.R, "R_mc": R_MC, "seed": AD.SEED, "sources_sha256": {p: AD.sha256(ROOT / p) for p in src}, "ext_files_digest": ext[2], "ext_quarantined_dirs": ext[3], "sameprec": sp, "checks": ck, "groups": res, "holdout_counts_only": hold, "seconds": round(time.time() - t0)}
    (jp := OUT / f"offdiag_null_{utc}.json").write_text(json.dumps(o, indent=1, default=float))
    (OUT / f"offdiag_null_{utc}.md").write_text(md(o, jp))
    print(f"offdiag_null: wrote {jp.relative_to(ROOT)} and .md ({o['seconds']} s)")

def selftest():
    for k in range(5):  # identities; E0 = mean over the C(4,k) arrangements; E_ind = off-rate of 4 iid Bernoulli(k/4)
        ps, sim = [p for p in FE if p.count("1") == k], (np.random.default_rng(k).random((200000, 4)) < k / 4).astype(int)
        assert all(FE[p]["off"] == FE[p]["kodd"] + FE[p]["rev"] and abs(FE[p]["d0"] - FE[p]["rev"] + FE[p]["k2"] / 3) < 1e-12 for p in ps) and abs(np.mean([FE[p]["off"] for p in ps]) - FE[ps[0]]["e0"]) < 1e-12 and abs(np.mean((sim[:, 1] - sim[:, 3]) != (sim[:, 0] - sim[:, 2])) - FE[ps[0]]["eind"]) < 5e-3
    assert not any((((B := x[0] + x[2] > 0) & (Q := x[1] + x[3] > 0) & ~(x[0] + x[3] > 0) & ~(x[1] + x[2] > 0)) | ((x[0] + x[3] > 0) & (x[1] + x[2] > 0) & ~B & ~Q)).any() for x in [np.random.default_rng(9).normal(size=(4, 10 ** 5))])  # additive latent: no reversal
    def draw(t, rev_ok, task_eff, rng=np.random.default_rng(7)):  # exchangeable labels given k; or no reversals; or a planted task effect on I (pattern 0100 in even tasks)
        y = list(rng.permutation([1] * (k := int(rng.choice(5, p=[.4, .2, .15, .1, .15]))) + [0] * (4 - k)))
        return "".join(map(str, [0, 1, 0, 0] if task_eff and t % 2 == 0 and rng.random() < .8 else [1, 1, 0, 0] if k == 2 and not rev_ok else y))
    g = {n: group({"c": [{"task": f"x:{t}", "b": f"b{b:02d}", "div": True, "pat": draw(t, *a)} for t in range(40) for b in range(12)]}, ["c"], 500, 200)
         for n, a in (("exchangeable", (True, False)), ("no reversals", (False, False)), ("task effect", (True, True)))}
    print("offdiag_null selftest:", {n: (v["obs-E0"]["block"], v["task_share_I"], v["tests"]["rev|k2 binom 1/3"]["p_two"]) for n, v in g.items()})
    assert g["exchangeable"]["obs-E0"]["block"][0] < 0 < g["exchangeable"]["obs-E0"]["block"][1] and g["exchangeable"]["task_share_I"]["perm_p"] > .01, "exchangeable"
    assert g["no reversals"]["obs-E0"]["block"][1] < 0 and g["no reversals"]["tests"]["rev|k2 binom 1/3"]["p_two"] < 1e-6 and g["task effect"]["task_share_I"]["task"][0] > .1 and g["task effect"]["task_share_I"]["perm_p"] < .01
    print("offdiag_null selftest OK (nothing written)")

if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv[1:] else main()
