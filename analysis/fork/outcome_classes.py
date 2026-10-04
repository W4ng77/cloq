"""EXPLORATORY, POST HOC (review 2026-10-04): which intervention changes the outcome at a divergent state.
Arms XY: X = source of the action at the divergent state, Y = continuation controller (method.tex: Delta_Q = Y_BQ - Y_QQ, Delta_B = Y_BB - Y_QB).
Per state: act_any = 1[Y_BQ != Y_QQ or Y_BB != Y_QB] (changing the action changes the outcome under at least one continuation controller);
cont_any = 1[Y_BB != Y_BQ or Y_QB != Y_QQ] (changing the continuation controller changes it under at least one action).
Five classes partition the 16 patterns (order BB,BQ,QB,QQ): unchanged (k = 0 or 4), action only (1100, 0011), continuation only (1010, 0101),
one arm differs from the other three (k odd), strict reversal (1001, 0110). Identities: act_any = odd + action only + reversal and
cont_any = odd + continuation only + reversal, so act_any - cont_any = action only - continuation only state by state: the gap comes from k = 2
states alone (it restates the k = 2 arrangement on the full denominator), and the two shares overlap on odd + reversal (they are not a split).
Named patterns: joint rescue = 1000 (only the joint upgrade succeeds: a complementary upgrade); rescue undone = Y_BQ = 1, Y_QQ = 0, Y_BB = 0
(0100, 0110: B's action rescues under Q's continuation and B's takeover of the continuation undoes the rescue).
A success threshold on additive action and continuation scores already yields odd-k patterns such as 1000 (selftest), so none of these shares by
itself shows a distinct interaction mechanism.
Estimation as offdiag_null.group: ratios of sums per cell, pools = equal-weight mean of cell ratios on common blocks. Fixed task pool: block
bootstrap (t over per-block ratios if K < 10); new tasks: crossed task x block bootstrap (analyze_dev.Boot Wc x Vc, as analyze_ghf); B = 2000,
seed 20261001. BFCL/ALFWorld: stratified item bootstrap only (one run per item). Same inputs and loaders as offdiag_null; analysis/fork/holdout/
is never opened (holdout rows: point estimates from stored 16-pattern counts, pending the no-op acceptance audit).
usage: python analysis/fork/outcome_classes.py [--B 2000] [--selftest] -> analysis/fork/out/outcome_classes_<UTC>.{md,json}
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time  # noqa: E401
from collections import defaultdict
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import offdiag_null as ON  # noqa: E402

AD, ROOT, OUT = ON.AD, ON.AD.ROOT, ON.AD.OUT
REF = "analysis/fork/out/offdiag_null_20261004T030949Z.json"
CLS = (("unchanged", "c_un"), ("action only", "c_act"), ("continuation only", "c_cont"), ("one arm differs", "c_odd"), ("strict reversal", "c_rev"))
NAMED = (("joint rescue", "jr"), ("rescue undone", "ru"))
STATS = [("act_any", "act", "one"), ("cont_any", "cont", "one"), ("act - cont", "dac", "one"), ("P(k=2)", "k2", "one")] + [(n, f, "one") for n, f in CLS + NAMED]
LABELS = ("Rows: `<model>:<cell>` = τ² retail/airline development cells (Bank P states); `tel:` = telecom development; `sameW4`/`sameW3` = the "
          "same-precision fork (Q' = a second GPTQ checkpoint of the same bit width in the B role, so its 'action' and 'continuation' are Q', not BF16); "
          "`precW4`/`precW3` = the BF16 fork on the same blocks; `bfcl:`/`alfworld:` = one run per item (K column: item bootstrap, no blocks).")

def extend(fe: dict) -> None:
    for p, f in fe.items():
        y, k = [int(c) for c in p], p.count("1")
        f.update(act=int(y[1] != y[3] or y[0] != y[2]), cont=int(y[0] != y[1] or y[2] != y[3]), c_un=int(k in (0, 4)), c_act=int(p in ("1100", "0011")),
                 c_cont=int(p in ("1010", "0101")), c_odd=k % 2, c_rev=int(p in ("1001", "0110")), jr=int(p == "1000"), ru=int(y[1] == 1 and y[3] == 0 and y[0] == 0))
        f["dac"] = f["act"] - f["cont"]

def setup() -> None:
    extend(ON.FE)
    ON.STATS[:] = STATS  # group(), pts() read ON.STATS at call time; the task variance shares (ICC) are not recomputed here
    ON.icc = lambda *a, **k: None

def boot_for(cu, labs, B):
    """The Boot that offdiag_null.group builds for these cells (same seed, so identical draws), kept for the crossed interval."""
    com, bo = set.intersection(*[{r["b"] for r in cu[l]} for l in labs]), defaultdict(set)
    [bo[r["task"]].add(r["b"]) for l in labs for r in cu[l] if r["b"] in com]
    return AD.Boot(sorted(bo), {t: sorted(v) for t, v in bo.items()}, B=B)

def crossed(bt, st, num, den):
    S, N = np.zeros((2, len(bt.tix), len(bt.bix)))
    for s in st:
        t, k = bt.tix[s["task"]], bt.bix[s["b"]]
        S[t, k] += ON.FE[s["pat"]][num]
        N[t, k] += ON.FE[s["pat"]][den]
    a, b = np.einsum("rt,tk,rk->r", bt.Wc, S, bt.Vc), np.einsum("rt,tk,rk->r", bt.Wc, N, bt.Vc)
    return np.where(b > 0, a / np.maximum(b, 1e-12), np.nan)

def group(cu, labs, B, bt=None) -> dict:
    new = bt is None
    res = ON.group(cu, labs, B, 2, bt := boot_for(cu, labs, B) if new else bt)
    res.pop("tests", None)
    if new:  # tau2 designs: add the crossed (new-task) interval; pools = equal-weight mean of the cells' crossed draws
        st = {l: [r for r in cu[l] if r["div"] and r["b"] in bt.bix] for l in labs}
        for nm, num, den in STATS:
            d = np.mean([crossed(bt, st[l], num, den) for l in labs], 0)
            res[nm]["crossed"] = [round(100 * float(x), 2) for x in np.nanpercentile(d, [2.5, 97.5])]
    return res

def rows_pooled(cnt: dict) -> dict:
    n = sum(cnt.values())
    return {nm: round(100 * sum(c * ON.FE[p][f] for p, c in cnt.items()) / n, 2) for nm, f, _ in STATS} | {"n_states": n}

def md(o: dict, jp: Path) -> str:
    g, h, w, kv, rp = o["groups"], o["holdout_counts_only"], o["groups"]["pool W4:all"], o["groups"]["pool KV8:all"], o["pooled_rows_W4_core"]
    iv = lambda x, c, s="": "–" if not x else f"{x['est']:{s}.1f}" + (f" [{x[c][0]:{s}.1f}, {x[c][1]:{s}.1f}]" if x.get(c) else "")  # noqa: E731
    pr = lambda x, s="": iv(x, "t" if x and x.get("t") else "block", s)  # noqa: E731
    sgn = lambda nm: "+" if nm == "act - cont" else ""  # noqa: E731
    def tab(items, cols, fn):
        L = [f"| group | states | K | {' | '.join(cols)} |", "|---" * (len(cols) + 3) + "|"]
        return "\n".join(L + [f"| {n} | {v['n_states']} | {v.get('K', '–') if v.get('section') != 'ext' else 'items'} | {' | '.join(fn(v.get(c), c) for c in cols)} |" for n, v in items]) + "\n"
    sec = lambda *s: [(n, v) for n, v in g.items() if v["section"] in s]  # noqa: E731
    top, cl, nd = ["act_any", "cont_any", "act - cont", "P(k=2)"], [n for n, _ in CLS], [n for n, _ in NAMED]
    T = lambda x, nm: f"{pr(x, sgn(nm))} (block or t), {iv(x, 'crossed', sgn(nm))} (new tasks)"  # noqa: E731
    L = [f"**TL;DR** EXPLORATORY, POST HOC. τ² retail/airline core W4 pool (equal-weight cells, {w['n_states']} divergent states, K = {w['K']}): changing the action changes the outcome "
         f"under at least one continuation controller in {T(w['act_any'], 'act_any')}% of states; changing the continuation controller changes it under at least one action in "
         f"{T(w['cont_any'], 'cont_any')}%. The two sets overlap (one arm differs + strict reversal = {w['one arm differs']['est'] + w['strict reversal']['est']:.1f}%), and their gap "
         f"{T(w['act - cont'], 'act - cont')} pp equals action only {w['action only']['est']:.1f} minus continuation only {w['continuation only']['est']:.1f}, i.e. it comes from k = 2 states alone. "
         f"Classes: unchanged {w['unchanged']['est']:.1f}, action only {w['action only']['est']:.1f}, continuation only {w['continuation only']['est']:.1f}, one arm differs "
         f"{w['one arm differs']['est']:.1f}, strict reversal {w['strict reversal']['est']:.1f}%. Joint rescue (only BB succeeds) {T(w['joint rescue'], '')}%; rescue undone by B's takeover "
         f"(BQ = 1, QQ = 0, BB = 0) {T(w['rescue undone'], '')}%. KV8 pool: act_any {T(kv['act_any'], '')}, cont_any {T(kv['cont_any'], '')}. The gap is not general: see telecom, "
         f"stress and ALFWorld rows. Count-weighted row totals (all {rp['n_states']} core W4 states pooled, not the paper's weighting): act_any {rp['act_any']}, cont_any {rp['cont_any']}, "
         f"P(k=2) {rp['P(k=2)']} (equal-weight P(k=2) {w['P(k=2)']['est']:.1f}). counts16 identical to `{REF}`: {o['check_vs_offdiag_null']['counts16_identical']} "
         f"({o['check_vs_offdiag_null']['groups_compared']} groups).", "",
         f"# Outcome classes at divergent states (EXPLORATORY, POST HOC; {o['utc']})", "", f"Script `analysis/fork/outcome_classes.py` (sha256 {o['sources_sha256']['analysis/fork/outcome_classes.py'][:16]}), "
         f"git {o['git_head'][:10]}, B = {o['B']}, seed {o['seed']}. Full numbers: `{jp.relative_to(ROOT)}` (it also keeps the task-cluster interval, blocks fixed, as `task`). "
         "Shares in % of divergent states (not the full-pool denominator of the turnover M). Intervals 95%: fixed pool = t over per-block ratios when K < 10, else block bootstrap; "
         "new tasks = crossed task x block bootstrap. t intervals are not clipped at 0 and zero-count shares print [0.0, 0.0]: neither is a valid interval for a proportion; do not quote them. "
         "BFCL/ALFWorld: stratified item bootstrap; in ALFWorld KV4 and BFCL KV4, QQ and BQ almost never succeed (floor), so 'continuation only' dominates there mechanically.", "", LABELS, "",
         "## 1. Action vs continuation, fixed task pool (block or t)", "", tab(sec("main", "other", "ext"), top + nd, lambda x, c: pr(x, sgn(c))),
         "## 2. Same, new tasks (crossed task x block; τ² designs only)", "", tab(sec("main", "other"), top + nd, lambda x, c: iv(x, "crossed", sgn(c))),
         "## 3. Five classes (a partition; fixed task pool)", "", tab(sec("main", "other", "ext"), cl, lambda x, c: pr(x)),
         "## 4. Telecom holdout (point estimates from stored 16-pattern counts; no intervals; pending the no-op acceptance audit)", "",
         tab(list(h.items()), top + cl + nd, lambda x, c: "–" if not x else f"{x['est']:{sgn(c)}.1f}"), "## Method", "", "```", __doc__.strip(), "```", "", "## Data sources (sha256)", ""]
    return "\n".join(L + [f"- `{p}` {s}" for p, s in o["sources_sha256"].items()] + [f"- ext input files digest {o['ext_files_digest']}"]) + "\n"

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--B", type=int, default=AD.B_BOOT), ap.add_argument("--selftest", action="store_true")
    a, t0 = ap.parse_args(), time.time()
    setup()
    cu, W4 = ON.load_tau2(), ["q4:awq_w4", "q4:gptq_w4_d1", "q8:awq_w4", "q8:gptq_w4_d1"]
    Rd = {l: ON.recs(v) for l, v in cu.items()}
    for tag in ON.SP:
        U, blocks, _, _ = ON.load_sp(tag)
        Rd |= {f"{d}{tag}:{m}": ON.recs(us) if d == "same" else [r for r in Rd[f"{m}:{ON.SP[tag][2]}"] if r["b"] in blocks] for m, us in U.items() for d in ("same", "prec")}
    Rd |= (E := (ext := ON.load_ext(a.B))[0])
    ghf = json.load(open(ROOT / ON.GHF))
    gs = [("main", l, [l], None) for l in ghf["cells"]] + [("main", f"pool {p}", c, None) for p, c in (("W4:q4", W4[:2]), ("W4:q8", W4[2:]), ("W4:all", W4), ("KV8:all", ["q4:kvq_int8", "q8:kvq_int8"]))]
    for x, c in [("tel:q8", ["awq_w4", "gptq_w4_d1"])] + [(d + t, ["q4", "q8"]) for t in ON.SP for d in ("same", "prec")]:
        gs += [("other", f"{x}:{y}", [f"{x}:{y}"], None) for y in c] + [("other", f"pool {x}", [f"{x}:{y}" for y in c], None)]
    gs += [("ext", l, [l], ext[1]) for l in sorted(E)] + [("ext", f"pool W4:{v}", [l for l in sorted(E) if l.split(":")[0] == v and "q14" not in l and "w4" in l], ext[1]) for v in ("bfcl", "alfworld")]
    res = {n: {"section": s, **group(Rd, c, a.B, bt)} for s, n, c, bt in gs}
    hold = {f"holdout {l}": {"weight": c["prereg_weight"], "n_states": sum(c["patterns16"]["counts"].values()), **ON.pts(c["patterns16"]["counts"])} for l, c in json.load(open(ROOT / ON.HOLD))["cells"].items()}
    hold["holdout pool (prereg weights)"] = {"n_states": sum(v["n_states"] for v in hold.values()), **{nm: {"est": round(sum(v["weight"] * v[nm]["est"] for v in hold.values()), 2)} for nm, _, _ in STATS}}
    ref = json.load(open(ROOT / REF))["groups"]
    src = [ON.G.DEF_SNAPSHOT, "manifests/fork/splits_v1.json", ON.GHF, ON.HOLD, REF] + [p for v in ON.SP.values() for p in v[:2]]
    src += [f"analysis/fork/{f}.py" for f in ("analyze_dev", "analyze_ghf", "analyze_sameprec", "analyze_ext", "offdiag_null", "outcome_classes")]
    o = {"label": "EXPLORATORY, POST HOC (not pre-registered)", "utc": (utc := time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())), "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "B": a.B, "seed": AD.SEED, "sources_sha256": {p: AD.sha256(ROOT / p) for p in src}, "ext_files_digest": ext[2], "groups": res, "holdout_counts_only": hold,
         "pooled_rows_W4_core": rows_pooled(res["pool W4:all"]["counts16"]), "seconds": round(time.time() - t0),
         "check_vs_offdiag_null": {"groups_compared": len(res), "counts16_identical": all(res[n]["counts16"] == ref[n]["counts16"] and res[n]["n_states"] == ref[n]["n_states"] for n in res)}}
    (jp := OUT / f"outcome_classes_{utc}.json").write_text(json.dumps(o, indent=1, default=float))
    (OUT / f"outcome_classes_{utc}.md").write_text(md(o, jp))
    print(f"outcome_classes: wrote {jp.relative_to(ROOT)} and .md ({o['seconds']} s); counts16 = offdiag_null: {o['check_vs_offdiag_null']}")

def selftest():
    setup()
    for p, f in ON.FE.items():
        assert sum(f[c] for _, c in CLS) == 1 and f["act"] == f["c_odd"] + f["c_act"] + f["c_rev"] and f["cont"] == f["c_odd"] + f["c_cont"] + f["c_rev"], p
        assert f["off"] == f["c_odd"] + f["c_rev"] and f["dac"] == f["c_act"] - f["c_cont"], p  # offdiag_null identity; the gap is k = 2 only
    assert {p for p, f in ON.FE.items() if f["ru"]} == {"0100", "0110"} and {p for p, f in ON.FE.items() if f["jr"]} == {"1000"}
    # a success threshold on additive scores (no reversal possible) still makes the continuation controller matter:
    a, c, thr = {"B": 1.0, "Q": 0.0}, {"B": 1.0, "Q": 0.0}, 1.5  # arm XY succeeds iff a[X] + c[Y] >= thr -> only BB succeeds
    pat = "".join(str(int(a[x] + c[y] >= thr)) for x, y in ("BB", "BQ", "QB", "QQ"))
    assert pat == "1000" and ON.FE[pat]["cont"] == ON.FE[pat]["act"] == ON.FE[pat]["off"] == ON.FE[pat]["jr"] == 1 and ON.FE[pat]["c_rev"] == 0
    assert ON.pts({"1000": 1})["joint rescue"]["est"] == 100 and ON.pts({"0110": 1, "1111": 1})["rescue undone"]["est"] == 50  # the patch reaches pts()
    rng = np.random.default_rng(3)
    cu = {"c": [{"task": f"x:{t}", "b": f"b{b:02d}", "div": True, "pat": f"{int(rng.integers(16)):04b}"} for t in range(30) for b in range(6)]}
    r = group(cu, ["c"], 300)
    direct = 100 * np.mean([ON.FE[s["pat"]]["act"] for s in cu["c"]])
    assert abs(r["act_any"]["est"] - direct) < 0.01 and r["act_any"]["crossed"][0] < r["act_any"]["est"] < r["act_any"]["crossed"][1] and "tests" not in r
    print("outcome_classes selftest OK (partition, identities, named patterns, additive-threshold 1000, patch reaches pts/group, crossed interval; nothing written)")

if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv[1:] else main()
