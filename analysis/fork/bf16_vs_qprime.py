"""EXPLORATORY, POST HOC (review W2b, 2026-10-05; not pre-registered): how often the BF16 design and the same-precision Q' design
detect joint rescue and rescue undone on the same task x block units.
Units: the frozen same-precision analysis set (manifests/fork/sameprec_v1.json; K = 6 blocks f01-f06 from SPREF; q4 and q8 GPTQ-W4 d1,
retail + airline, 85 tasks x 6 blocks = 510 units per cell). Both designs share the Q episode (QQ arm), so the units pair one to one
(analyze_sameprec.pair_units keys). Arms in order BB, BQ, QB, QQ; in the Q' design BB = Q'Q', BQ = Q'Q, QB = QQ' (analyze_sameprec mapping).
Per unit and design: D_jr = 1 if that design's first-divergence state has pattern 1000 (joint rescue), D_ru = 1 if it has BQ = 1, QQ = 0,
BB = 0 (0100, 0110: rescue undone); 0 if the design found no divergence or another pattern (outcome_classes definitions). Paired
difference per unit: D(BF16) - D(Q'). Estimates: mean of block means per cell (analyze_dev.Boot.task_mean), pool = equal-weight q4 + q8
on shared draws (analyze_sameprec.pool_pairs); primary = t over the 6 pooled block means (K < 10), block bootstrap and crossed
task x block bootstrap alongside; B = 2000, seed 20261001 (same Boot construction as analyze_sameprec, so identical draws).
Secondary: conditional shares among each design's divergent states (Boot.ratio), and the paired difference on units where both designs
diverged (still two different states in general; same_t = same turn index is reported only as a count).
CAVEAT (load-bearing): each design selects its own first divergence state (the first turn where its B-role action differs from Q's),
so D_jr and D_ru measure how often each selection-and-replacement protocol finds these consequences on a unit. A difference is not a
precision-specific effect at the same state; the common-state comparison (analyze_commonstate) is the direct test of extra action value.
Checks: 16-pattern counts per cell and design equal SPREF; conditional pooled shares equal outcome_classes (OCREF) samew4 / precw4 rows.
analysis/fork/holdout/ is never opened (analyze_sameprec.dirs_under asserts it).
usage: python analysis/fork/bf16_vs_qprime.py [--B 2000] [--selftest] -> analysis/fork/out/bf16_vs_qprime_<UTC>.{md,json}
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time  # noqa: E401
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD, analyze_sameprec as S  # noqa: E401,E402

ROOT, OUT, ARMS = AD.ROOT, AD.OUT, ("BB", "BQ", "QB", "QQ")
SPREF, OCREF = "analysis/fork/out/sameprec_20261004T070601Z.json", "analysis/fork/out/outcome_classes_20261004T143614Z.json"
PATS = {"jr": lambda p: p == "1000", "ru": lambda p: p[1] == "1" and p[3] == "0" and p[0] == "0"}
NAME = {"jr": "joint rescue", "ru": "rescue undone"}
pat = lambda u: "".join(str(int(u["Y"][a])) for a in ARMS) if u.get("div") and u.get("Y") else None  # noqa: E731

def unit_E(p: dict, s: dict) -> dict:
    E = {"div_p": int(bool(p.get("div"))), "div_s": int(bool(s.get("div")))}
    for k, f in PATS.items():
        a, b = (int(x is not None and f(x)) for x in (pat(p), pat(s)))
        E |= {f"{k}_p": a, f"{k}_s": b, f"d_{k}": a - b, f"{k}_pc": a if p.get("div") else None, f"{k}_sc": b if s.get("div") else None}
        E[f"d_{k}_both"] = a - b if p.get("div") and s.get("div") else None
    E["both"] = int(p.get("div") and s.get("div"))
    return E

def pair(prec: list, same: list) -> list:
    key, sp = (lambda u: (u["model"], u["domain"], u["task"], u["block"])), {}  # noqa: E731
    sp = {key(u): u for u in same}
    assert len(sp) == len(same) and {key(u) for u in prec} == set(sp), "units do not pair one to one"
    return [{"model": p["model"], "task": p["task"], "block": p["block"], "E": unit_E(p, sp[key(p)]), "same_t": int(bool(p.get("div") and sp[key(p)].get("div") and p.get("t") == sp[key(p)].get("t")))} for p in prec]

def stats(boot, pu: dict, models) -> dict:
    full = lambda m, k: S.full_stat(boot, pu[m], k)  # noqa: E731
    rat = lambda m, k: S.ratio_stat(boot, [u for u in pu[m] if u["E"][k] is not None], k)  # noqa: E731
    out = {}
    for k in PATS:
        r = {"rate_bf16": [full(m, f"{k}_p") for m in models], "rate_qprime": [full(m, f"{k}_s") for m in models], "diff_bf16_minus_qprime": [full(m, f"d_{k}") for m in models],
             "cond_share_bf16": [rat(m, f"{k}_pc") for m in models], "cond_share_qprime": [rat(m, f"{k}_sc") for m in models], "diff_on_both_div_units": [rat(m, f"d_{k}_both") for m in models]}
        out[NAME[k]] = {n: {"pool": S.pool_pairs(v), **{m: AD.summarise(*x) for m, x in zip(models, v)}} for n, v in r.items()}
    out["divergence"] = {n: {"pool": S.pool_pairs(v), **{m: AD.summarise(*x) for m, x in zip(models, v)}} for n, v in
                         (("rate_bf16", [full(m, "div_p") for m in models]), ("rate_qprime", [full(m, "div_s") for m in models]))}
    return out

def fmt(x: dict, sgn="") -> str:
    q = lambda c: f"[{x[c][0]:{sgn}.2f}, {x[c][1]:{sgn}.2f}]" if x.get(c) else "–"  # noqa: E731
    return f"{x['est']:{sgn}.2f} t {q('t_ci95')}, block {q('block_boot_ci95')}, crossed {q('crossed_ci95')}"

def md(o: dict, jp: Path) -> str:
    r, ck, L = o["results"], o["checks"], []
    for nm in NAME.values():
        x = r[nm]
        L.append(f"{nm}: detected on {x['rate_bf16']['pool']['est']:.2f}% of units by the BF16 design vs {x['rate_qprime']['pool']['est']:.2f}% by Q', paired difference {fmt(x['diff_bf16_minus_qprime']['pool'], '+')} pp")
    T = ["| statistic | design | pool q4+q8 | q4 | q8 |", "|---|---|---|---|---|"]
    for nm in list(NAME.values()) + ["divergence"]:
        for n, v in r[nm].items():
            T.append(f"| {nm} | {n} | {fmt(v['pool'], '+' if 'diff' in n else '')} | {fmt(v['q4'], '+' if 'diff' in n else '')} | {fmt(v['q8'], '+' if 'diff' in n else '')} |")
    H = [f"**TL;DR** EXPLORATORY, POST HOC. On the {o['n_units']} frozen same-precision task x block units (q4 + q8 GPTQ-W4, K = {o['K']}, equal-weight pool, % of units, 95% intervals: t over 6 block means primary): "
         + "; ".join(L) + ". Each design picks its own first divergence state, so this compares how often the two selection-and-replacement protocols find these consequences, not a precision-specific effect at the same state. "
         f"Checks: 16-pattern counts = sameprec freeze: {ck['patterns16_equal_spref']}; conditional pooled shares = outcome_classes: {ck['cond_equal_ocref']}.", "",
         f"# BF16 vs Q' pattern detection on paired units (EXPLORATORY, POST HOC; {o['utc']})", "", f"Script `analysis/fork/bf16_vs_qprime.py` (sha256 {o['sources_sha256']['analysis/fork/bf16_vs_qprime.py'][:16]}), git {o['git_head'][:10]}, B = {o['B']}, seed {o['seed']}. Full numbers: `{jp.relative_to(ROOT)}`.", "",
         "Rows: rate_* = % of all paired units on which that design's first-divergence state shows the pattern (no divergence counts 0); diff = paired BF16 minus Q' per unit; cond_share_* = % of that design's divergent states "
         "(different state sets: descriptive); diff_on_both_div_units = paired difference restricted to units where both designs diverged "
         f"({ck['n_both_div']} units, of which {ck['n_same_t']} at the same turn index). t intervals are not clipped at 0; zero counts give degenerate intervals.", "", *T, "",
         f"Per-block pooled differences (pp, blocks {', '.join(o['blocks'])}): " + "; ".join(f"{nm} {[round(100 * v, 2) for v in o['block_diffs'][nm]]}" for nm in NAME.values()), "",
         f"Counts (summed over q4 + q8): {json.dumps(ck['counts'])}", "", "## Method", "", "```", __doc__.strip(), "```", "", "## Data sources (sha256)", ""]
    return "\n".join(H + [f"- `{p}` {s}" for p, s in o["sources_sha256"].items()] + [f"- fork input files digest {o['files_digest']}"]) + "\n"

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--B", type=int, default=AD.B_BOOT), ap.add_argument("--selftest", action="store_true")
    a, t0 = ap.parse_args(), time.time()
    man, ref = json.load(open(S.MANIFEST)), json.load(open(ROOT / SPREF))
    S.guard(man)
    snap, models, blocks = json.load(open(ROOT / man["snapshot"])), man["cells"], ref["analysis_set"]["blocks"]
    U, M = {}, {}
    for d, key in (("prec", "precision_dirs"), ("same", "sameprec_dirs")):
        U[d], _, M[d] = S.admit([x for m in models for x in S.dirs_under(man[key][m])], snap)
    sel = {d: [u for u in U[d] if "excluded" not in u and u["block"] in blocks] for d in S.DESIGNS}
    bo = defaultdict(set)
    [bo[u["task"]].add(u["block"]) for d in S.DESIGNS for u in sel[d]]
    boot = AD.Boot(sorted(bo), {t: sorted(v) for t, v in bo.items()}, B=a.B)
    pu = {m: pair(*[[u for u in sel[d] if u["model"] == m] for d in S.DESIGNS]) for m in models}
    res = stats(boot, pu, models)
    p16 = {m: {d: dict(sorted(Counter(pat(u) for u in sel[d] if u["model"] == m and u["div"]).items())) for d in S.DESIGNS} for m in models}
    oc = json.load(open(ROOT / OCREF))["groups"]
    cond_ok = {f"{nm} {d}": [res[nm][f"cond_share_{dd}"]["pool"]["est"], oc[f"pool {d}W4"][nm]["est"]] for nm in NAME.values() for d, dd in (("prec", "bf16"), ("same", "qprime"))}
    cnt = {f"{NAME[k]} {d}": sum(u["E"][f"{k}_{d[0]}"] for m in models for u in pu[m]) for k in PATS for d in ("prec", "same")}
    cnt |= {f"{NAME[k]} both designs": sum(u["E"][f"{k}_p"] * u["E"][f"{k}_s"] for m in models for u in pu[m]) for k in PATS}
    ck = {"patterns16_equal_spref": all(p16[m][d] == {k: v for k, v in ref["cells"][m][d]["patterns16"]["counts"].items() if v} for m in models for d in S.DESIGNS),
          "cond_equal_ocref": all(abs(x - y) < 0.01 for x, y in cond_ok.values()), "cond_vs_ocref": cond_ok, "counts": cnt,
          "n_both_div": sum(u["E"]["both"] for m in models for u in pu[m]), "n_same_t": sum(u["same_t"] for m in models for u in pu[m]),
          "n_units_vs_spref": {m: [len(pu[m]), ref["cells"][m]["paired"]["n_pairs"]] for m in models}}
    bd = {nm: np.nanmean(np.vstack([S.full_stat(boot, pu[m], f"d_{k}")[1].block_means for m in models]), 0).tolist() for k, nm in NAME.items()}
    src = [str(S.MANIFEST.relative_to(ROOT)), man["snapshot"], man["protocol"], SPREF, OCREF] + [f"analysis/fork/{f}.py" for f in ("analyze_dev", "analyze_ghf", "analyze_sameprec", "outcome_classes", "bf16_vs_qprime")]
    o = {"label": "EXPLORATORY, POST HOC (not pre-registered)", "utc": (utc := time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())), "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "B": a.B, "seed": AD.SEED, "blocks": blocks, "K": len(blocks), "n_units": sum(map(len, pu.values())), "sources_sha256": {p: AD.sha256(ROOT / p) for p in src},
         "files_digest": {d: M[d]["files_digest"] for d in M}, "caveat": "Each design selects its own first divergence state: this compares how often each selection-and-replacement protocol finds these consequences, not a precision-specific effect at the same state.",
         "checks": ck, "patterns16": p16, "block_diffs": bd, "results": res, "seconds": round(time.time() - t0)}
    (jp := OUT / f"bf16_vs_qprime_{utc}.json").write_text(json.dumps(o, indent=1, default=float))
    (OUT / f"bf16_vs_qprime_{utc}.md").write_text(md(o, jp))
    print(f"bf16_vs_qprime: wrote {jp.relative_to(ROOT)} and .md ({o['seconds']} s); checks {ck['patterns16_equal_spref']} {ck['cond_equal_ocref']}")

def selftest():
    mk = lambda Y, div=True: {"model": "q4", "domain": "retail", "task": "t", "block": "f01", "div": div, "Y": dict(zip(ARMS, Y)) if div else None}  # noqa: E731
    E = unit_E(mk([1, 0, 0, 0]), mk([0, 1, 1, 0]))
    assert (E["jr_p"], E["jr_s"], E["d_jr"], E["ru_p"], E["ru_s"], E["d_ru"]) == (1, 0, 1, 0, 1, -1)
    E = unit_E(mk(None, False), mk([0, 1, 0, 0]))
    assert (E["jr_p"], E["ru_s"], E["d_ru"], E["jr_pc"], E["d_ru_both"]) == (0, 1, -1, None, None)
    assert {f"{i:04b}" for i in range(16) if PATS["ru"](f"{i:04b}")} == {"0100", "0110"} and {f"{i:04b}" for i in range(16) if PATS["jr"](f"{i:04b}")} == {"1000"}
    print("bf16_vs_qprime selftest OK (nothing written)")

if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv[1:] else main()
