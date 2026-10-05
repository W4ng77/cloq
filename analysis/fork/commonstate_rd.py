"""EXPLORATORY, POST HOC (Analysis 3, 2026-10-05; protocol docs/insights/COMMONSTATE_RD_POSTHOC.md, not pre-registered).
Common-state BF16 vs same-precision substitute Q' (= W4-d2) decomposition: at the same states and the same continuation c,
extra rescues XR = r_B - r_Q', extra damages XD = d_B - d_Q', net XN = XR - XD = K(c) of the published common-state reading.
Loads through analyze_commonstate.load (same manifests, admission, quarantine, freeze) and reuses analyze_commonstate.estimate
(t over block means, task-cluster bootstrap, B = 2000, seed 20261002). Asserts n, K point estimates and published r/d exactly.
usage: python analysis/fork/commonstate_rd.py [--boot B] -> analysis/fork/out/commonstate_rd_<UTC>.{md,json}
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time  # noqa: E401
from datetime import datetime
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_commonstate as AC  # noqa: E402

ROOT, OUT, CONT = AC.ROOT, AC.OUT, AC.CONT
PUB = {"q8ext": "analysis/fork/out/commonstate_q8ext_20261003T231159Z.json", "q4": "analysis/fork/out/commonstate_q4_20261004T001159Z.json"}
NEXP = {"q8ext": (510, 6), "q4": (170, 2)}
PROTO = "docs/insights/COMMONSTATE_RD_POSTHOC.md"
LBL = ("more", "fewer")


def rd_columns(units: list[dict]) -> dict:
    """Per-state columns. Baseline = d1 action under the same continuation c."""
    C = {}
    for c in CONT:
        y1, yb, yq = ([u["Y"][(s, c)] for u in units] for s in ("d1", "bf16", "d2"))
        C[f"rB[{c}]"] = [int(b == 1 and a == 0) for a, b in zip(y1, yb)]
        C[f"dB[{c}]"] = [int(b == 0 and a == 1) for a, b in zip(y1, yb)]
        C[f"rQ[{c}]"] = [int(q == 1 and a == 0) for a, q in zip(y1, yq)]
        C[f"dQ[{c}]"] = [int(q == 0 and a == 1) for a, q in zip(y1, yq)]
        for x in ("B", "Q"):
            C[f"net{x}[{c}]"] = [r - d for r, d in zip(C[f"r{x}[{c}]"], C[f"d{x}[{c}]"])]
        C[f"XR[{c}]"] = [a - b for a, b in zip(C[f"rB[{c}]"], C[f"rQ[{c}]"])]
        C[f"XD[{c}]"] = [a - b for a, b in zip(C[f"dB[{c}]"], C[f"dQ[{c}]"])]
        C[f"XN[{c}]"] = [a - b for a, b in zip(C[f"XR[{c}]"], C[f"XD[{c}]"])]
        C[f"K[{c}]"] = [(b - a) - (q - a) for a, b, q in zip(y1, yb, yq)]  # published definition, recomputed
        assert C[f"XN[{c}]"] == C[f"K[{c}]"], "identity XN = K violated"
    for n in ("rB", "dB", "rQ", "dQ", "netB", "netQ", "XR", "XD", "XN", "K"):
        C[f"{n}[avg]"] = [(a + b) / 2 for a, b in zip(C[f"{n}[bf16]"], C[f"{n}[d1]"])]
    return C


def crosstab(units: list[dict]) -> dict:
    out = {}
    for c in CONT:
        t = {"Y1=0": dict.fromkeys(("both", "BF16 only", "Q' only", "neither"), 0), "Y1=1": dict.fromkeys(("both", "BF16 only", "Q' only", "neither"), 0)}
        for u in units:
            a, b, q = (u["Y"][(s, c)] for s in ("d1", "bf16", "d2"))
            hb, hq = (b != a), (q != a)  # flip relative to d1: rescue if a = 0, damage if a = 1
            t[f"Y1={a}"]["both" if hb and hq else "BF16 only" if hb else "Q' only" if hq else "neither"] += 1
        out[c] = t
    return out


def frame_counts(units: list[dict]) -> dict:
    b: dict = {}
    for u in units:
        b[u["block"]] = b.get(u["block"], 0) + 1
    return {"n": len(units), "k": len(b), "n_tasks": len({u["task"] for u in units}), "per_block": dict(sorted(b.items()))}


def overall(rd: dict) -> str:
    xr, xd = rd["XR"], rd["XD"]
    if xr == "more" and xd == "fewer":
        return "both: more rescues and fewer damages"
    if xr == "more" and xd == "more":
        return "rescues and damages both higher (offsetting)"
    if xr == "more":
        return "BF16's extra value comes from more rescues"
    if xd == "fewer" and xr != "fewer":  # protocol section 5: XR must not read "fewer"
        return "BF16's extra value comes from fewer damages"
    return "unresolved: neither component separated from zero"


def check_unique(units: list[dict]) -> None:
    """Row-equal weighting in a block (AC.estimate) equals the protocol's task-equal weighting only with 1 state per (task, block)."""
    pairs = [(u["task"], u["block"]) for u in units]
    assert len(pairs) == len(set(pairs)), "more than one state per (task, block): row weights != task weights"


def load_design(design: str, inputs: dict) -> tuple[list[dict], dict, dict]:
    man = json.loads(AC.MAN.read_text())
    proto = ROOT / man["protocol"]
    AC.guard(proto, man["protocol_sha256"])
    dm = json.loads(AC.DESIGNS[design].read_text())
    if AC.guard(proto, dm["protocol_sha256"]) != AC.PROTOCOL_SHA_D2:
        raise SystemExit("design manifest needs the D2 protocol")
    segs = ([man] if design == "q8ext" else []) + [dm]
    units, notes = AC.load(man, inputs, False, segs, datetime.fromisoformat(dm["freeze"]).timestamp())
    return units, notes, man


def analyse(design: str, nboot: int, inputs: dict) -> dict:
    units, notes, man = load_design(design, inputs)
    fc = frame_counts(units)
    check_unique(units)
    assert (fc["n"], fc["k"]) == NEXP[design], f"{design}: frame {fc} != expected {NEXP[design]}"
    seed, margin = man["boot"]["seed"], man["margin_pp"] / 100
    E = AC.estimate(units, rd_columns(units), nboot, seed, pocock=design == "q8ext")
    S, pub = E["stats"], json.loads((ROOT / PUB[design]).read_text())
    inputs[PUB[design]] = AC.sha_file(ROOT / PUB[design])
    P = pub["estimates"]["stats"]
    assert pub["estimates"]["n"] == fc["n"] and pub["estimates"]["blocks"] == E["blocks"]
    chk = {}
    for c in CONT:
        chk[f"K[{c}]"] = (S[f"XN[{c}]"]["point"], P[f"K[{c}]"]["point"])
        for mine, theirs in ((f"rB[{c}]", f"r[bf16-d1|{c}]"), (f"dB[{c}]", f"d[bf16-d1|{c}]"), (f"rQ[{c}]", f"r[d2-d1|{c}]"), (f"dQ[{c}]", f"d[d2-d1|{c}]")):
            chk[mine] = (S[mine]["point"], P[theirs]["point"])
        if nboot == pub["boot"]["B"]:
            chk[f"K[{c}] boot95/t95"] = (S[f"XN[{c}]"]["boot95"] + S[f"XN[{c}]"]["t95"], P[f"K[{c}]"]["boot95"] + P[f"K[{c}]"]["t95"])
    chk["Kbar"] = (S["XN[avg]"]["point"], P["Kbar"]["point"])
    bad = {k: v for k, v in chk.items() if v[0] != v[1]}
    assert not bad, f"{design}: does not reproduce the published numbers: {bad}"
    rd = {}
    for c in CONT + ("avg",):
        rd[c] = {n: AC.reading(S[f"{n}[{c}]"], margin, None, *LBL)["reading"] for n in ("XR", "XD", "XN")}
        rd[c]["overall"] = overall(rd[c])
    return {"frame": fc, "excluded": len(notes["excluded"]), "seed": seed, "margin": margin, "stats": S, "readings": rd,
            "crosstab": crosstab(units), "reproduced": {k: v[0] for k, v in chk.items()}}


def f(e: dict, k: str) -> str:
    return f"[{100 * e[k][0]:+.1f}, {100 * e[k][1]:+.1f}]" if k in e else "n/a"


def comp(r: dict) -> str:
    return "; ".join(f"c = {c}: XR {r['readings'][c]['XR']}, XD {r['readings'][c]['XD']}" for c in CONT + ("avg",))


def scale(r: dict, margin: float) -> str:
    S = r["stats"]
    rates = [100 * S[f"{n}[{c}]"]["point"] for n in ("rB", "rQ", "dB", "dQ") for c in CONT]
    mult = [(S[f"rQ[{c}]"]["point"] + margin) / S[f"rQ[{c}]"]["point"] for c in CONT if S[f"rQ[{c}]"]["point"] > 0]
    eq = any("equivalent" in r["readings"][c][n] for c in CONT + ("avg",) for n in ("XR", "XD"))
    return (f"the ±{100 * margin:.0f} pp margin is large relative to the component rates themselves ({min(rates):.1f} to {max(rates):.1f} pp)"
            + (f"; equivalence within it still allows BF16 up to {min(mult):.1f}x to {max(mult):.1f}x the rescues of Q' (r_Q' + margin over r_Q'), "
               "or no extra rescues" if eq and mult else "; no component reached equivalence here"))


def md(R: dict) -> str:
    L = [f"# Common-state BF16 vs Q' rescue/damage decomposition (EXPLORATORY, POST HOC; {R['utc']})", "",
         "**TL;DR** EXPLORATORY, POST HOC. " + " ".join(
        f"{m}: net K = {100 * r['stats']['XN[avg]']['point']:+.1f} pp (avg over c) = extra rescues {100 * r['stats']['XR[avg]']['point']:+.1f} "
        f"minus extra damages {100 * r['stats']['XD[avg]']['point']:+.1f} pp; {r['readings']['avg']['overall']} (c = d1: {r['readings']['d1']['overall']}). "
        f"Components: {comp(r)}. Note: {scale(r, r['margin'])}."
        for m, r in R["designs"].items()), "",
         f"Protocol `{PROTO}`. Script `analysis/fork/commonstate_rd.py` sha256 `{R['script_sha256']}`, git `{R['git_head']}`, B = {R['B']}, "
         f"seed {R['seed']}. Q' = W4-d2; baseline = d1 action under the same continuation c. Intervals: t over block means (df = k-1) and "
         "task-cluster bootstrap (no crossed bootstrap in this machinery). Point estimates of K, Kbar and published r/d reproduced exactly (asserted).",
         "Inference is to these 85 tasks (same-task; the bootstrap resamples tasks with blocks fixed); no new-task (crossed) interval is reported. "
         "These are hindsight outcome contrasts on fixed states, not a selection rule or router. Point splits of an unresolved K are descriptive only.", ""]
    for m, r in R["designs"].items():
        S = r["stats"]
        L += [f"## {m}: n = {r['frame']['n']}, k = {r['frame']['k']}, tasks = {r['frame']['n_tasks']}, per block {r['frame']['per_block']}", "",
              "| c | r_B | r_Q' | d_B | d_Q' | net_B | net_Q' | XR = r_B-r_Q' (t95; boot95) | XD = d_B-d_Q' (t95; boot95) | XN = K (t95; boot95) | reading XR / XD / overall |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        degen = [f"{n}[{c}]" for c in CONT + ("avg",) for n in ("XR", "XD", "XN") if "t95" in S[f"{n}[{c}]"] and S[f"{n}[{c}]"]["t95"][0] == S[f"{n}[{c}]"]["t95"][1]]
        for c in CONT + ("avg",):
            p = lambda n: f"{100 * S[f'{n}[{c}]']['point']:.1f}"  # noqa: E731
            x = lambda n: f"{100 * S[f'{n}[{c}]']['point']:+.1f} ({f(S[f'{n}[{c}]'], 't95')}; {f(S[f'{n}[{c}]'], 'boot95')})"  # noqa: E731
            rr = r["readings"][c]
            L.append(f"| {c if c != 'avg' else 'avg over c (Kbar-style)'} | {p('rB')} | {p('rQ')} | {p('dB')} | {p('dQ')} | {p('netB')} | {p('netQ')} | {x('XR')} | {x('XD')} | {x('XN')} | {rr['XR']} / {rr['XD']} / {rr['overall']} |")
        if r["frame"]["k"] < 4:
            L += ["", f"k = {r['frame']['k']} (df = {r['frame']['k'] - 1}): t intervals are uninformative; readings rest on the bootstrap. "
                  f"t degenerate (zero spread across blocks): {', '.join(degen) or 'none'}."]
        L += ["", "Counts (unweighted) of flips relative to d1, per continuation: " + json.dumps(r["crosstab"]), ""]
        if "boot97" in S["XR[d1]"]:
            L += ["Pocock 97% (reference only): " + "; ".join(f"{n}[{c}] t97 {f(S[f'{n}[{c}]'], 't97')} boot97 {f(S[f'{n}[{c}]'], 'boot97')}" for c in CONT for n in ("XR", "XD")), ""]
    L += ["## Inputs (sha256)", "", *[f"- `{k}` {v}" for k, v in R["inputs"].items()]]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--boot", type=int, default=2000)
    a, inputs = ap.parse_args(), {}
    R = {"label": "EXPLORATORY, POST HOC (not pre-registered; data already seen)", "utc": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
         "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "script_sha256": AC.sha_file(Path(__file__).resolve()), "protocol": PROTO, "protocol_sha256": AC.sha_file(ROOT / PROTO), "B": a.boot}
    R["designs"] = {m: analyse(d, a.boot, inputs) for m, d in (("q8", "q8ext"), ("q4", "q4"))}
    R["seed"], R["inputs"] = R["designs"]["q8"]["seed"], inputs
    jp = OUT / f"commonstate_rd_{R['utc']}.json"
    jp.write_text(json.dumps(R, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else float(o)))
    (OUT / f"commonstate_rd_{R['utc']}.md").write_text(md(R))
    print(jp.with_suffix(".md"))
    print(md(R).split("\n")[0])


if __name__ == "__main__":
    main()
