"""W99o: every number that changes between two analyze_ext outputs and two ext_r2 outputs (old -> new), at paper rounding.

Section 1 lists the paper's tab:extr2 columns per cell and pool (R1 from analyze_ext: items, r, d, M, G_all; R2 from ext_r2:
states, G, H, F, G-H, off-diagonal %, expected off-diagonal %, kappa, strict reversals n). Section 2 gives the ranges the
paper text quotes. Section 3 is exhaustive: every numeric leaf under cells/pooled of both outputs whose rounded value
changed (pp and % to 1 decimal, kappa/shares to 3 decimals, counts exact).

usage: python scripts/ext/w99o_diff.py OLD_EXT NEW_EXT OLD_R2 NEW_R2 --out analysis/fork/ext/w99o/diff
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
W4 = ("gptq_w4_d1", "awq_w4_d1")
NAMES = {"gptq_w4_d1": "GPTQ-W4", "awq_w4_d1": "AWQ-W4", "gptq_w3": "GPTQ-W3", "kvq_int4": "KV4"}


def f1(x):
    return None if x is None else f"{x:+.1f}"


def ci(x):
    return None if not x else f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}]"


def r1row(e, lab):
    c = e["cells"].get(lab)
    if not c:
        return {}
    a = c["all_pp"]
    return {"items": c["n_units"], "states (ext)": c["n_states"], "r": f"{a['rescue']['est']:.1f}", "d": f"{a['damage']['est']:.1f}",
            "M": f"{a['M']['est']:.1f}", "M CI": f"[{a['M']['ci95'][0]:.1f}, {a['M']['ci95'][1]:.1f}]", "G_all": ci(a["G"]),
            "rescue n": c["counts"]["rescue"], "damage n": c["counts"]["damage"]}


def r2row(r, lab):
    c = r["cells"].get(lab)
    if not c or "table3" not in c:
        return {}
    e, t = c["pp_on_divergent"], c["table3"]
    ct = t["marginal_preserving_pairing_agreement_control"]
    return {"states": c["coverage"]["divergent_states_four_arms"], "items analysed": c["coverage"]["items_analysed"],
            "G": ci(e["G"]), "H": ci(e["H"]), "F": ci(e["F"]), "G-H": ci(e["GmH"]), "I": ci(e["I"]),
            "off-diag %": f"{e['offdiag']['est']:.1f} [{e['offdiag']['ci95'][0]:.1f}, {e['offdiag']['ci95'][1]:.1f}]",
            "exp. %": f"{100 * ct['expected_offdiag_share_independent']:.1f}",
            "kappa": None if ct["kappa"] is None else f"{ct['kappa']:.3f}", "rev. (n)": t["strict_reversal_n"],
            "Y_BB/BQ/QB/QQ": "/".join(f"{e[k]['est']:.1f}" for k in ("Y_BB", "Y_BQ", "Y_QB", "Y_QQ"))}


def pool_row(e, r, name):
    pe, pr = e["pooled"].get(name), r["pooled"].get(name)
    out = {}
    if pe:
        out.update({"G_all": ci(pe.get("G")), "cells": len(pe["cells"])})
    if pr:
        d = pr["pp_on_divergent"]
        out.update({"G": ci(d["G"]), "H": ci(d["H"]), "F": ci(d["F"]), "G-H": ci(d["GmH"]),
                    "off-diag %": f"{d['offdiag']['est']:.1f} [{d['offdiag']['ci95'][0]:.1f}, {d['offdiag']['ci95'][1]:.1f}]",
                    "strict rev. %": f"{d['strict_reversal']['est']:.1f}"})
    return out


def ranges(e, r):
    def cells(env, fam=W4):
        return [l for l in r["cells"] if l.startswith(env + ":") and l.split(":")[2] in fam]
    out = {}
    bw, aw = cells("bfcl"), cells("alfworld")
    od = {l: r["cells"][l]["pp_on_divergent"]["offdiag"]["est"] for l in bw + aw}
    out["BFCL W4 off-diagonal range %"] = f"{min(od[l] for l in bw):.1f}–{max(od[l] for l in bw):.1f}"
    out["BFCL W4 off-diagonal pool %"] = f"{r['pooled']['W4:bfcl:pooled_equal_weight']['pp_on_divergent']['offdiag']['est']:.1f}"
    out["ALFWorld W4 off-diagonal range %"] = f"{min(od[l] for l in aw):.1f}–{max(od[l] for l in aw):.1f}"
    ex = {l: 100 * r["cells"][l]["table3"]["marginal_preserving_pairing_agreement_control"]["expected_offdiag_share_independent"] for l in bw + aw}
    kp = {l: r["cells"][l]["table3"]["marginal_preserving_pairing_agreement_control"]["kappa"] for l in bw + aw}
    out["BFCL W4 expected off-diagonal range %"] = f"{min(ex[l] for l in bw):.1f}–{max(ex[l] for l in bw):.1f}"
    out["BFCL W4 kappa range"] = f"{min(kp[l] for l in bw):.2f}–{max(kp[l] for l in bw):.2f}"
    m = {l: e["cells"][l]["all_pp"]["M"]["est"] for l in bw + aw}
    out["W4 turnover M range % (BFCL + ALFWorld cells)"] = f"{min(m.values()):.1f}–{max(m.values()):.1f}"
    out["W4 cells whose G_all 95% CI excludes 0"] = "; ".join(f"{l} {ci(e['cells'][l]['all_pp']['G'])}" for l in bw + aw
                                                           if e["cells"][l]["all_pp"]["G"]["ci95"][0] > 0 or e["cells"][l]["all_pp"]["G"]["ci95"][1] < 0) or "none"
    out["BFCL W4 pool G_all"] = ci(e["pooled"]["W4:bfcl:pooled_equal_weight"]["G"])
    out["W4 all-env pool G_all"] = ci(e["pooled"]["W4:all_envs:pooled_equal_weight"]["G"])
    out["stress BFCL pool G_all"] = ci(e["pooled"]["stress:bfcl:pooled_equal_weight"]["G"])
    out["tau2 comparison line"] = e["tau2_comparison"]["line"]
    return out


def leaves(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from leaves(v, f"{p}.{k}" if p else str(k))
    elif isinstance(o, list) and all(isinstance(x, (int, float)) for x in o) and len(o) <= 4:
        yield p, o
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        yield p, o


def rnd(path, v):
    if isinstance(v, list):
        return [rnd(path, x) for x in v]
    if isinstance(v, int):
        return v
    last = path.split(".")[-1]
    if "kappa" in path or "share" in path or "margins" in path or last in ("divergence_rate",):
        return round(v, 3)
    return round(v, 1)


def exhaustive(old, new, keys=("cells", "pooled")):
    rows = []
    for k in keys:
        lo, ln = dict(leaves(old.get(k, {}), k)), dict(leaves(new.get(k, {}), k))
        for p in sorted(set(lo) | set(ln)):
            a, b = lo.get(p), ln.get(p)
            ra, rb = (rnd(p, a) if a is not None else None), (rnd(p, b) if b is not None else None)
            if ra != rb and not any(s in p for s in ("block_boot", "lb95", "draws")):
                rows.append((p, ra, rb))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old_ext")
    ap.add_argument("new_ext")
    ap.add_argument("old_r2")
    ap.add_argument("new_r2")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    oe, ne, orr, nr = (json.load(open(ROOT / p)) for p in (a.old_ext, a.new_ext, a.old_r2, a.new_r2))
    labs = sorted(set(oe["cells"]) | set(ne["cells"]), key=lambda l: (l.split(":")[2] not in W4, l.split(":")[0], l))
    L = [f"# W99o: old → new numbers (ext and ext_r2)", "",
         f"- old: `{a.old_ext}`, `{a.old_r2}`", f"- new: `{a.new_ext}`, `{a.new_r2}`", "",
         "## 1. tab:extr2 columns per cell (only changed entries; `=` rows omitted)", ""]
    res = {"old": [a.old_ext, a.old_r2], "new": [a.new_ext, a.new_r2], "cells": {}, "pools": {}, "ranges": {}, "exhaustive": {}}
    for lab in labs:
        o = {**r1row(oe, lab), **r2row(orr, lab)}
        n = {**r1row(ne, lab), **r2row(nr, lab)}
        ch = {k: (o.get(k), n.get(k)) for k in dict.fromkeys(list(o) + list(n)) if o.get(k) != n.get(k)}
        res["cells"][lab] = {"old": o, "new": n, "changed": ch}
        env, m, arm = lab.split(":")
        name = f"{'BFCL' if env == 'bfcl' else 'ALFWorld'} {m} {NAMES.get(arm, arm)}"
        if ch:
            L.append(f"**{name}** (`{lab}`)")
            L += [f"- {k}: {v[0]} → {v[1]}" for k, v in ch.items()]
            L.append("")
        else:
            L.append(f"**{name}**: unchanged")
            L.append("")
    L += ["## 2. Pools (equal weight per cell)", ""]
    for p in sorted(set(oe["pooled"]) | set(ne["pooled"])):
        o, n = pool_row(oe, orr, p), pool_row(ne, nr, p)
        ch = {k: (o.get(k), n.get(k)) for k in dict.fromkeys(list(o) + list(n)) if o.get(k) != n.get(k)}
        res["pools"][p] = {"old": o, "new": n, "changed": ch}
        L.append(f"**{p}**: " + ("; ".join(f"{k} {v[0]} → {v[1]}" for k, v in ch.items()) if ch else "unchanged"))
    L += ["", "## 3. Ranges and statements quoted in the paper text", ""]
    ro, rn = ranges(oe, orr), ranges(ne, nr)
    for k in ro:
        res["ranges"][k] = {"old": ro[k], "new": rn[k]}
        L.append(f"- {k}: {ro[k]} → {rn[k]}" if ro[k] != rn[k] else f"- {k}: {ro[k]} (unchanged)")
    L += ["", "## 4. Exhaustive: every changed numeric leaf (rounded) under cells/pooled", ""]
    for nm, (o, n) in (("ext", (oe, ne)), ("ext_r2", (orr, nr))):
        rows = exhaustive(o, n)
        res["exhaustive"][nm] = rows
        L.append(f"### {nm}: {len(rows)} changed leaves")
        L.append("")
        L += [f"- `{p}`: {x} → {y}" for p, x, y in rows]
        L.append("")
    Path(a.out + ".json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    Path(a.out + ".md").write_text("\n".join(L) + "\n")
    print(f"wrote {a.out}.md")


if __name__ == "__main__":
    main()
