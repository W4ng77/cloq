"""EXPLORATORY, POST HOC (review 2026-10-05, W3-W5 'Mistral evidence thin'): outcome classes on the second-family panel.
Panel: Mistral-Small-3.2-24B (m24), new-method panel A (analyze_newmethod loaders, 83-task frozen mask, strict blocks), cells GPTQ-W4 d1 and
RTN-W4. Views as in the paper: 'A6' = the primary (arm errors on the agent's own message scored Y = 0, then strict blocks; GPTQ 6 blocks, RTN 5)
and 'strict' = strict as preregistered (no A6; GPTQ 5, RTN 3). States are U2B ordinary states sampled on the BF16 trajectory, not Bank P first
divergences on the Q trajectory: BB is the recorded BF16 original (shared by both cells), a_B is the recorded BF16 action, a_Q is Q's proposal.
Arm naming: the panel already uses XY = (source of the action at the state, continuation controller), the same as outcome_classes.py and
analyze_dev.effects (A = Y_BB - Y_QB, G = Y_BQ - Y_QQ); its headline D_cc = Y_QB - Y_BB = -Delta_B. Bit order BB,BQ,QB,QQ is identical, so the
16 patterns and the named patterns carry over by arm label (checked per unit against the panel's own E: D_cc = -(y_BB - y_QB), offdiag).
Named patterns by arm label: joint rescue = 1000 (only BB succeeds); rescue undone = 0100, 0110. On this panel the reference is BB (BF16 all the
way), so 1000 reads 'only the all-BF16 arm succeeds' and the rescue reading of Bank P (Q baseline QQ) is not the natural one; shares are reported
by arm label only. Label reference (labels permuted uniformly given k): E[J] = P(k=1)/4, E[U] = P(k=1)/4 + P(k=2)/6; obs - ref per state.
Denominators: 'nonexact' (a_Q not token-identical to a_B; the analogue of divergent states; primary) and 'all' (exact states included: there
QB = BB and BQ = QQ are reused arms, so act_any = 0 by construction and only the continuation can change the outcome). The label reference
assumes the four arm labels are exchangeable, which fails on exact states (1000, 0100, 0110 are impossible there but get reference mass), so
E[J], E[U] and obs - ref are defined on 'nonexact' only; on 'all' rows they are biased downward by construction and printed n/a (JSON keeps them).
BB is the recorded original (no-op re-run on a 10% hash sample, protocol §2.3) and the other three arms are re-executions; under A6 only the
re-executed arms can be scored Y = 0 (counted per pattern in JSON a6_zeroed_nonexact). Patterns that single out BB (1000, 0111) carry this asymmetry.
Estimation exactly as outcome_classes.group: ratios of sums per cell, pool = equal-weight mean of the two cells on common blocks; fixed task pool:
t over per-block ratios (K < 10; block bootstrap kept in JSON); new tasks: crossed task x block bootstrap; B = 2000, seed 20261001.
Never opens analysis/fork/holdout/ (analyze_newmethod.no_holdout guards every path).
usage: python analysis/fork/mistral_patterns.py [--B 2000] [--selftest] -> analysis/fork/out/mistral_patterns_<UTC>.{md,json}
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, time  # noqa: E401
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import outcome_classes as OC  # noqa: E402
import analyze_newmethod as NMx  # noqa: E402

ON, AD, ROOT, OUT = OC.ON, OC.AD, OC.ROOT, OC.OUT
CITED, MODEL, CELLS = "analysis/fork/out/newmethod_m24_20261004T024453Z.json", "m24", ("gptq_w4_d1", "rtn_w4")
REFS = (("jr - E[J]", "djr", "one"), ("ru - E[U]", "dru", "one"), ("E[J] (label ref)", "jref", "one"), ("E[U] (label ref)", "uref", "one"), ("P(k=1)", "k1", "one"))

def setup() -> None:
    OC.STATS[:] = [s for s in OC.STATS if s[0] not in {r[0] for r in REFS}] + list(REFS)
    OC.setup()
    for p, f in ON.FE.items():
        k = p.count("1")
        f.update(jref=(k == 1) / 4, uref=(k == 1) / 4 + (k == 2) / 6)
        f.update(djr=f["jr"] - f["jref"], dru=f["ru"] - f["uref"])

def load():
    g = NMx.guard(MODEL)
    man = json.loads((ROOT / g["manifest"]).read_text())
    pop, exc = NMx.population(MODEL, man)
    views: dict = {}
    raw, log = NMx.load_tau2(MODEL, man, None, set(CELLS), a6=True, views=views, recovery=True)
    pre = NMx.strict_prereg(raw)
    assert {c: [(u["state_key"], "excluded" in u, u.get("Y")) for u in us] for c, us in pre.items()} == \
           {c: [(u["state_key"], "excluded" in u, u.get("Y")) for u in us] for c, us in views["strict"].items()}, "strict view != loader without A6"
    out = {"A6": NMx.apply_population(raw, pop, len(pop))[:2], "strict": NMx.apply_population(pre, pop, len(pop))[:2]}
    return g, pop, exc, out, log

def recs(units, denom):
    R = []
    for u in units:
        Y, E = u["Y"], u["E"]
        pat = "".join(str(int(Y[a])) for a in ON.ARMS)
        f = ON.FE[pat]
        assert E["D_cc"] == int(pat[2]) - int(pat[0]) and E["offdiag"] == f["off"] and E["A"] == int(pat[0]) - int(pat[2]), (u["state_key"], pat)
        assert not u["exact"] or (pat[0] == pat[2] and pat[1] == pat[3]), ("exact state with differing reused arms", u["state_key"], pat)
        R.append({"task": u["task"], "b": u["block"], "div": denom == "all" or not u["exact"], "pat": pat, "sk": u["state_key"]})
    return R

def md(o, jp):
    G = o["groups"]
    iv = lambda x, c, s="": "–" if not x else f"{x['est']:{s}.1f}" + (f" [{x[c][0]:{s}.1f}, {x[c][1]:{s}.1f}]" if x.get(c) else "")  # noqa: E731
    pr = lambda x, s="": iv(x, "t" if x and x.get("t") else "block", s)  # noqa: E731
    sg = lambda nm: "+" if nm in ("act - cont", "jr - E[J]", "ru - E[U]") else ""  # noqa: E731
    na = lambda n, c: ":all:" in n and c in [r[0] for r in REFS]  # noqa: E731  label reference undefined with exact states (see Method)
    def tab(names, cols, fn):
        L = [f"| group | states | K | {' | '.join(cols)} |", "|---" * (len(cols) + 3) + "|"]
        return "\n".join(L + [f"| {n} | {G[n]['n_states']} | {G[n]['K']} | {' | '.join('n/a' if na(n, c) else fn(G[n].get(c), c) for c in cols)} |" for n in names]) + "\n"
    top, cl, nd = ["act_any", "cont_any", "act - cont", "P(k=2)"], [n for n, _ in OC.CLS], ["joint rescue", "E[J] (label ref)", "jr - E[J]", "rescue undone", "E[U] (label ref)", "ru - E[U]"]
    p = G["A6:nonexact:pool"]
    T = lambda x, nm="": f"{pr(x, sg(nm))} (t), {iv(x, 'crossed', sg(nm))} (crossed)"  # noqa: E731
    order = [f"{v}:{d}:{c}" for v in ("A6", "strict") for d in ("nonexact", "all") for c in CELLS + ("pool",)]
    L = [f"**TL;DR** EXPLORATORY, POST HOC. Mistral-Small-3.2-24B, ordinary BF16-trajectory states (U2B), A6 primary view, pool of GPTQ-W4 and RTN-W4 "
         f"(equal-weight cells, {p['n_states']} non-exact states, K = {p['K']} common blocks): act_any {T(p['act_any'])}%, cont_any {T(p['cont_any'])}%, "
         f"gap {T(p['act - cont'], 'act - cont')} pp. Classes: unchanged {p['unchanged']['est']:.1f}, action only {p['action only']['est']:.1f}, continuation only "
         f"{p['continuation only']['est']:.1f}, one arm differs {p['one arm differs']['est']:.1f}, strict reversal {p['strict reversal']['est']:.1f}%. "
         f"Joint rescue (1000) {T(p['joint rescue'])}% vs label reference {p['E[J] (label ref)']['est']:.1f} (obs - ref {T(p['jr - E[J]'], 'jr - E[J]')} pp); "
         f"rescue undone (0100, 0110) {T(p['rescue undone'])}% vs {p['E[U] (label ref)']['est']:.1f} (obs - ref {T(p['ru - E[U]'], 'ru - E[U]')} pp). "
         f"Check vs `{CITED}`: {o['check_vs_cited']['ok']}. These are BF16-trajectory states (BB = recorded BF16 original), not Bank P upgrade states: "
         "the named patterns are defined by arm label and do not carry the Bank P rescue reading.", "",
         f"# Outcome classes on the m24 panel (EXPLORATORY, POST HOC; {o['utc']})", "",
         f"Script `analysis/fork/mistral_patterns.py` (sha256 {o['sources_sha256']['analysis/fork/mistral_patterns.py'][:16]}), git {o['git_head'][:10]}, B = {o['B']}, seed {o['seed']}. "
         f"Full numbers: `{jp.relative_to(ROOT)}` (block bootstrap and task-cluster intervals kept there). Shares in % of the stated denominator. Fixed pool: t over per-block ratios "
         "(K < 10), not clipped at 0; zero-count shares print [0.0, 0.0]: not valid intervals for a proportion. Rows `<view>:<denominator>:<cell>`; pool = GPTQ-W4 + RTN-W4 on common blocks.", "",
         "## 1. Action vs continuation (fixed task pool, t)", "", tab(order, top, lambda x, c: pr(x, sg(c))),
         "## 2. Same, new tasks (crossed task x block)", "", tab(order, top, lambda x, c: iv(x, "crossed", sg(c))),
         "## 3. Five classes (partition; fixed task pool, t)", "", tab(order, cl, lambda x, c: pr(x)),
         "## 4. Named patterns and label reference (fixed task pool, t)", "", tab(order, nd, lambda x, c: pr(x, sg(c))),
         "## 5. Named patterns, new tasks (crossed)", "", tab(order, nd, lambda x, c: iv(x, "crossed", sg(c))),
         "## 6. Admission and checks", "", "```", json.dumps({k: o[k] for k in ("admitted_blocks", "check_vs_cited", "population", "a6_zeroed_nonexact")}, indent=1), "```", "",
         "## Method", "", "```", __doc__.strip(), "```", "", "## Data sources (sha256)", ""]
    return "\n".join(L + [f"- `{k}` {v}" for k, v in o["sources_sha256"].items()] + [f"- units digest (cell, state_key, view, pattern) {o['units_digest']}"]) + "\n"

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--B", type=int, default=AD.B_BOOT), ap.add_argument("--selftest", action="store_true")
    a, t0 = ap.parse_args(), time.time()
    setup()
    g, pop, exc, views, log = load()
    cu, adm = {}, {}
    for v, (cells, info) in views.items():
        adm[v] = {c: sorted(b for b, x in info[c].items() if x["admitted"]) for c in CELLS}
        for d in ("nonexact", "all"):
            cu |= {f"{v}:{d}:{c}": recs(cells[c], d) for c in CELLS}
    gs = [(f"{v}:{d}:{c}", [f"{v}:{d}:{c}"]) for v in views for d in ("nonexact", "all") for c in CELLS]
    gs += [(f"{v}:{d}:pool", [f"{v}:{d}:{c}" for c in CELLS]) for v in views for d in ("nonexact", "all")]
    res = {n: OC.group(cu, labs, a.B) for n, labs in gs}
    ref, ck = json.load(open(ROOT / CITED))["tau2"], {}
    for c in CELLS:
        rc, rs = ref["cells"][c], ref["sensitivity_strict_prereg"]["cells"][c]
        ck[c] = {"A6 n_states [ours, cited]": [res[f"A6:all:{c}"]["n_states"], rc["n_states"]], "A6 n_nonexact": [res[f"A6:nonexact:{c}"]["n_states"], rc["n_nonexact"]],
                 "A6 blocks": [adm["A6"][c], rc["blocks"]], "A6 offdiag all-states %": [None, round(rc["all_states_pp"]["offdiag"]["est"], 2)],
                 "strict n_states": [res[f"strict:all:{c}"]["n_states"], rs["n_states"]], "strict K": [res[f"strict:all:{c}"]["K"], rs["k_blocks"]]}
    off = lambda c: round(100 * sum(ON.FE[r["pat"]]["off"] for r in cu[f"A6:all:{c}"]) / len(cu[f"A6:all:{c}"]), 2)  # noqa: E731
    for c in CELLS:
        ck[c]["A6 offdiag all-states %"][0] = off(c)
    ck["ok"] = all(x[0] == x[1] if not isinstance(x[0], float) else abs(x[0] - x[1]) < 0.01 for c in CELLS for x in ck[c].values())
    a6z = {f"{v}:{c}": dict(Counter(f"{''.join(str(int(u['Y'][x])) for x in ON.ARMS)} zeroed {','.join(sorted(u['a6']))}" for u in cells[c] if "a6" in u and not u["exact"]))
           for v, (cells, _) in views.items() for c in CELLS}
    dig = hashlib.sha256(json.dumps(sorted((k, r["sk"], r["pat"], r["div"]) for k, v in cu.items() for r in v)).encode()).hexdigest()
    bank = sorted(p for c in CELLS for p in (NMx.NM / "tau2").glob(f"{MODEL}_{c}/*/bank_rows.jsonl"))
    src = [g["manifest"], g["mask"], "docs/insights/NEWMETHOD_PANEL_PROTOCOL.md", CITED] + [f"analysis/fork/{f}.py" for f in ("analyze_newmethod", "analyze_dev", "offdiag_null", "outcome_classes", "mistral_patterns")]
    src += [str(p.relative_to(ROOT)) for p in bank]
    o = {"label": "EXPLORATORY, POST HOC (not pre-registered)", "utc": (utc := time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())),
         "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(), "B": a.B, "seed": AD.SEED,
         "population": {"n_tasks": len(pop), "excluded_by_mask": exc}, "admitted_blocks": adm, "load_log": log, "check_vs_cited": ck, "a6_zeroed_nonexact": a6z,
         "sources_sha256": {p: AD.sha256(ROOT / p) for p in src}, "units_digest": dig, "groups": res, "seconds": round(time.time() - t0)}
    (jp := OUT / f"mistral_patterns_{utc}.json").write_text(json.dumps(o, indent=1, default=float))
    (OUT / f"mistral_patterns_{utc}.md").write_text(md(o, jp))
    print(f"mistral_patterns: wrote {jp.relative_to(ROOT)} and .md ({o['seconds']} s); check vs cited ok = {ck['ok']}")

def selftest():
    setup()
    for p, f in ON.FE.items():
        assert abs(f["djr"] - f["jr"] + f["jref"]) < 1e-12 and abs(f["dru"] - f["ru"] + f["uref"]) < 1e-12
    for k in range(5):  # the label reference is the mean of the named indicator over the C(4,k) arrangements of k successes
        ps = [p for p in ON.FE if p.count("1") == k]
        assert abs(sum(ON.FE[p]["jr"] for p in ps) / len(ps) - ON.FE[ps[0]]["jref"]) < 1e-12 and abs(sum(ON.FE[p]["ru"] for p in ps) / len(ps) - ON.FE[ps[0]]["uref"]) < 1e-12, k
    u = {"Y": {"BB": 1, "BQ": 0, "QB": 0, "QQ": 0}, "exact": False, "state_key": "s", "task": "t", "block": "f01"}
    u["E"] = NMx.unit_effects(u["Y"], False)
    assert recs([u], "nonexact")[0]["pat"] == "1000" and u["E"]["D_cc"] == -1 and ON.FE["1000"]["jr"] == 1
    print("mistral_patterns selftest OK (label reference = arrangement mean, arm conversion; nothing written)")

if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv[1:] else main()
