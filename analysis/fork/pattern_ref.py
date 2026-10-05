"""EXPLORATORY, POST HOC (review W2a, 2026-10-05): joint rescue and rescue undone against the label-permutation reference given k.
Arms in order BB, BQ, QB, QQ; k = number of successful arms. Joint rescue J = 1[pattern 1000]; rescue undone U = 1[0100 or 0110]
(Y_BQ = 1, Y_QQ = 0, Y_BB = 0). If the four outcome labels of a state are permuted uniformly given k, 1000 has probability 1/4 at k = 1,
0100 has 1/4 at k = 1 and 0110 has 1/6 at k = 2, so per state E[J | k] = 1[k=1]/4 and E[U | k] = 1[k=1]/4 + 1[k=2]/6, and the
pool references are E[J] = P(k=1)/4, E[U] = P(k=1)/4 + P(k=2)/6. Per state obs - ref = 1[pattern] - E[pattern | k]; its share is
the observed share minus the reference share computed on the same states and the same bootstrap draws (paired by construction).
The reference keeps k; it says nothing about why k is what it is. A share above it means the named arrangement is more frequent than
a random arrangement of the same number of successes, not a distinct interaction mechanism (outcome_classes: additive scores with a
success threshold already give 1000). Q' rows (sameW4/sameW3): Q' is a second same-bit-width GPTQ checkpoint in the B role; prec rows:
the BF16 fork restricted to the same blocks. Each protocol picks its own first divergent state, so sameW4 vs precW4 compares how often
two selection and replacement protocols find the arrangement, not a precision-specific effect at a common state.
Estimation exactly as outcome_classes.group (via offdiag_null.group): ratios of sums per cell, pools = equal-weight mean of cell ratios
on common blocks; fixed task pool: t over per-block ratios if K < 10, else block bootstrap; new tasks: crossed task x block bootstrap
(analyze_dev.Boot Wc x Vc); B = 2000, seed 20261001. Same loaders as outcome_classes; analysis/fork/holdout/ is never opened (holdout
rows: point estimates from stored 16-pattern counts). BFCL/ALFWorld are not loaded here (one run per item; see outcome_classes).
usage: python analysis/fork/pattern_ref.py [--B 2000] [--selftest] -> analysis/fork/out/pattern_ref_<UTC>.{md,json}
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time  # noqa: E401
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import offdiag_null as ON, outcome_classes as OC  # noqa: E401,E402

AD, ROOT, OUT = ON.AD, ON.AD.ROOT, ON.AD.OUT
REF = "analysis/fork/out/outcome_classes_20261004T143614Z.json"
STATS = [("J obs", "jr", "one"), ("J ref", "ejr", "one"), ("J obs-ref", "djr", "one"), ("U obs", "ru", "one"), ("U ref", "eru", "one"), ("U obs-ref", "dru", "one"),
         ("P(k=1)", "k1", "one"), ("P(k=2)", "k2", "one"), ("U 0100", "u1", "one"), ("U 0110", "u2", "one")]
W4 = ["q4:awq_w4", "q4:gptq_w4_d1", "q8:awq_w4", "q8:gptq_w4_d1"]
REVIEW = {"pool W4:all": (3.96, 3.48, 4.80, 5.79), "pool sameW4": (2.27, 3.50, 5.78, 5.75), "pool precW4": (4.96, 3.53, 3.82, 6.14)}

def extend(fe: dict) -> None:
    for p, f in fe.items():
        k = p.count("1")
        f.update(jr=int(p == "1000"), ru=int(p in ("0100", "0110")), u1=int(p == "0100"), u2=int(p == "0110"), ejr=(k == 1) / 4, eru=(k == 1) / 4 + (k == 2) / 6)
        f.update(djr=f["jr"] - f["ejr"], dru=f["ru"] - f["eru"])

def setup() -> None:
    extend(ON.FE)
    ON.STATS[:] = STATS  # ON.group / ON.pts read ON.STATS at call time
    OC.STATS[:] = STATS  # OC.group's crossed loop reads OC.STATS
    ON.icc = lambda *a, **k: None

def md(o: dict, jp: Path) -> str:
    g, h = o["groups"], o["holdout_counts_only"]
    iv = lambda x, c, s="": "–" if not x else f"{x['est']:{s}.2f}" + (f" [{x[c][0]:{s}.2f}, {x[c][1]:{s}.2f}]" if x.get(c) else "")  # noqa: E731
    fx = lambda x, s="": iv(x, "t" if x and x.get("t") else "block", s)  # noqa: E731
    cols = [("J obs", ""), ("J ref", ""), ("J obs-ref", "+"), ("U obs", ""), ("U ref", ""), ("U obs-ref", "+")]
    def tab(items, fn):
        L = [f"| group | states | K | {' | '.join(c for c, _ in cols)} | P(k=1) | P(k=2) |", "|---" * (len(cols) + 5) + "|"]
        return "\n".join(L + [f"| {n} | {v['n_states']} | {v.get('K', '–')} | {' | '.join(fn(v.get(c), s) for c, s in cols)} | {v['P(k=1)']['est']:.2f} | {v['P(k=2)']['est']:.2f} |" for n, v in items]) + "\n"
    P = [n for n in g if n.startswith("pool")]
    hl = lambda n: f"{n} ({g[n]['n_states']} states, K = {g[n]['K']}): J {g[n]['J obs']['est']:.2f} vs ref {g[n]['J ref']['est']:.2f}, obs-ref {fx(g[n]['J obs-ref'], '+')} fixed pool, {iv(g[n]['J obs-ref'], 'crossed', '+')} new tasks; U {g[n]['U obs']['est']:.2f} vs ref {g[n]['U ref']['est']:.2f}, obs-ref {fx(g[n]['U obs-ref'], '+')} fixed, {iv(g[n]['U obs-ref'], 'crossed', '+')} new tasks"  # noqa: E731
    L = [f"**TL;DR** EXPLORATORY, POST HOC. Observed minus label-permutation reference (pp of divergent states, 95%): " + "; ".join(hl(n) for n in ("pool W4:all", "pool sameW4", "pool precW4", "pool KV8:all", "pool tel:q8")) + ". "
         f"Review point estimates reproduced: {o['review_check']}. sameW4 and precW4 rows use different first divergent states (each protocol picks its own), so their difference is a protocol detection-rate contrast, not a precision effect at a common state.", "",
         f"# Joint rescue and rescue undone vs the label-permutation reference (EXPLORATORY, POST HOC; {o['utc']})", "",
         f"Script `analysis/fork/pattern_ref.py` (sha256 {o['sources_sha256']['analysis/fork/pattern_ref.py'][:16]}), git {o['git_head'][:10]}, B = {o['B']}, seed {o['seed']}. Full numbers: `{jp.relative_to(ROOT)}`. "
         f"Shares in % of divergent states. Fixed pool = t over per-block ratios when K < 10, else block bootstrap; new tasks = crossed task x block bootstrap. Point estimates of J obs and U obs equal `{REF}`: {o['check_vs_outcome_classes']}.", "", OC.LABELS, "",
         "## 1. Fixed task pool (block or t)", "", tab([(n, g[n]) for n in P] + [(n, v) for n, v in g.items() if n not in P], fx),
         "## 2. New tasks (crossed task x block)", "", tab([(n, g[n]) for n in P] + [(n, v) for n, v in g.items() if n not in P], lambda x, s: iv(x, "crossed", s)),
         "## 3. Rescue undone split (fixed pool): 0100 (ref P(k=1)/4) and 0110 (ref P(k=2)/6)", "", "| group | 0100 | P(k=1)/4 | 0110 | P(k=2)/6 |", "|---|---|---|---|---|"]
    L += [f"| {n} | {v['U 0100']['est']:.2f} | {v['P(k=1)']['est'] / 4:.2f} | {v['U 0110']['est']:.2f} | {v['P(k=2)']['est'] / 6:.2f} |" for n, v in g.items() if n.startswith("pool")]
    L += ["", "## 4. Telecom holdout (point estimates from stored counts, no intervals, pending the no-op acceptance audit)", "", "| group | states | J obs | J ref | U obs | U ref |", "|---|---|---|---|---|---|"]
    L += [f"| {n} | {v['n_states']} | {v['J obs']['est']:.2f} | {v['J ref']['est']:.2f} | {v['U obs']['est']:.2f} | {v['U ref']['est']:.2f} |" for n, v in h.items()]
    L += ["", "## Method", "", "```", __doc__.strip(), "```", "", "## Data sources (sha256)", ""] + [f"- `{p}` {s}" for p, s in o["sources_sha256"].items()]
    return "\n".join(L) + "\n"

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--B", type=int, default=AD.B_BOOT), ap.add_argument("--selftest", action="store_true")
    a, t0 = ap.parse_args(), time.time()
    setup()
    cu = ON.load_tau2()
    Rd = {l: ON.recs(v) for l, v in cu.items()}
    for tag in ON.SP:
        U, blocks, _, _ = ON.load_sp(tag)
        Rd |= {f"{d}{tag}:{m}": ON.recs(us) if d == "same" else [r for r in Rd[f"{m}:{ON.SP[tag][2]}"] if r["b"] in blocks] for m, us in U.items() for d in ("same", "prec")}
    gs = [(f"pool {p}", c) for p, c in (("W4:all", W4), ("W4:q4", W4[:2]), ("W4:q8", W4[2:]), ("KV8:all", ["q4:kvq_int8", "q8:kvq_int8"]))] + [(l, [l]) for l in W4 + ["q4:kvq_int8", "q8:kvq_int8"]]
    for x, c in [("tel:q8", ["awq_w4", "gptq_w4_d1"])] + [(d + t, ["q4", "q8"]) for t in ON.SP for d in ("same", "prec")]:
        gs += [(f"pool {x}", [f"{x}:{y}" for y in c])] + [(f"{x}:{y}", [f"{x}:{y}"]) for y in c]
    res = {n: OC.group(Rd, c, a.B) for n, c in gs}
    hold = {f"holdout {l}": {"weight": c["prereg_weight"], "n_states": sum(c["patterns16"]["counts"].values()), **ON.pts(c["patterns16"]["counts"])} for l, c in json.load(open(ROOT / ON.HOLD))["cells"].items()}
    hold["holdout pool (prereg weights)"] = {"n_states": sum(v["n_states"] for v in hold.values()), **{nm: {"est": round(sum(v["weight"] * v[nm]["est"] for v in hold.values()), 2)} for nm, _, _ in STATS}}
    ref = json.load(open(ROOT / REF))["groups"]
    chk = all(abs(res[n]["J obs"]["est"] - ref[n]["joint rescue"]["est"]) < 0.01 and abs(res[n]["U obs"]["est"] - ref[n]["rescue undone"]["est"]) < 0.01 and res[n]["counts16"] == ref[n]["counts16"] for n in res if n in ref)
    rv = {n: {"ours": [res[n][k]["est"] for k in ("J obs", "J ref", "U obs", "U ref")], "review": list(v), "match_0.02": bool(np.allclose([res[n][k]["est"] for k in ("J obs", "J ref", "U obs", "U ref")], v, atol=0.02))} for n, v in REVIEW.items()}
    src = [ON.G.DEF_SNAPSHOT, "manifests/fork/splits_v1.json", ON.HOLD, REF] + [p for v in ON.SP.values() for p in v[:2]]
    src += [f"analysis/fork/{f}.py" for f in ("analyze_dev", "analyze_ghf", "analyze_sameprec", "offdiag_null", "outcome_classes", "pattern_ref")]
    o = {"label": "EXPLORATORY, POST HOC (not pre-registered)", "utc": (utc := time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())), "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "B": a.B, "seed": AD.SEED, "sources_sha256": {p: AD.sha256(ROOT / p) for p in src}, "groups": res, "holdout_counts_only": hold, "review_check": rv,
         "check_vs_outcome_classes": {"groups_compared": sum(n in ref for n in res), "J_U_counts16_identical": chk}, "seconds": round(time.time() - t0)}
    (jp := OUT / f"pattern_ref_{utc}.json").write_text(json.dumps(o, indent=1, default=float))
    (OUT / f"pattern_ref_{utc}.md").write_text(md(o, jp))
    print(f"pattern_ref: wrote {jp.relative_to(ROOT)} and .md ({o['seconds']} s); vs outcome_classes {o['check_vs_outcome_classes']}; review {rv}")

def selftest():
    setup()
    for k in range(5):  # reference = mean over the C(4,k) arrangements of each indicator
        ps = [p for p in ON.FE if p.count("1") == k]
        for ind, e in (("jr", "ejr"), ("ru", "eru")):
            assert abs(np.mean([ON.FE[p][ind] for p in ps]) - ON.FE[ps[0]][e]) < 1e-12, (k, ind)
    rng = np.random.default_rng(5)  # exchangeable labels given k: obs-ref interval covers 0
    cu = {"c": [{"task": f"x:{t}", "b": f"b{b:02d}", "div": True, "pat": "".join(map(str, rng.permutation([1] * (k := int(rng.choice(5, p=[.4, .3, .15, .1, .05]))) + [0] * (4 - k))))} for t in range(40) for b in range(12)]}
    r = OC.group(cu, ["c"], 400)
    assert r["J obs-ref"]["block"][0] < 0 < r["J obs-ref"]["block"][1] and r["U obs-ref"]["crossed"][0] < 0 < r["U obs-ref"]["crossed"][1], r
    assert abs(r["J obs-ref"]["est"] - (r["J obs"]["est"] - r["J ref"]["est"])) < 0.02
    print("pattern_ref selftest OK (reference = arrangement mean given k; exchangeable null covers 0; obs-ref = obs - ref; nothing written)")

if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv[1:] else main()
