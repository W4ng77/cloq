#!/usr/bin/env python3
"""F9 (W100j; panel (b) added post-freeze 10-04): paired upgrade modes G (this step), H (from the next step), F (both),
and (b) the joint-rescue / rescue-undone outcome classes, per core W4 cell and pool, main text.
The q8 RTN-W3 and q14 BFCL rows are still asserted (their numbers stay in the text and tables) but no longer drawn.

A slim companion of F2 (appendix forest). Separate from make_figs.py (edited by other sessions); imports it only for
style, palette, widths, load(), save() and interval(). Reads committed outputs only and asserts every quoted number.
Writes figures/f9_upgrade_modes.pdf and merges its entry into figures/provenance.json.

    /data/ziyangs/cloq_work/envs/cloq/bin/python paper/latex/tools/figs/make_fig_modes.py
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_figs as MF  # noqa: E402
from make_figs import ALT, B, COL_W, FS, FS_S, INK, INK2, LW_ZERO, QP, plt, style_axis, r1  # noqa: E402


def script_sha():
    return hashlib.sha256(open(os.path.abspath(__file__), "rb").read()).hexdigest()


KEYS = ("G", "H", "F", "GmH")


def f9():
    MF.SRC["q14"] = "analysis/fork/out/ext_q14_20261002T085647Z.json"
    MF.SRC["mult"] = "analysis/fork/out/ghf_multiplicity_20261001T225727Z.json"
    MF.script_sha = script_sha
    ghf, q14 = MF.load("ghf"), MF.load("q14")
    q = q14["cells"]["q14"]["r2"]["pp_on_divergent"]
    rows = [  # (label, {G,H,F: (est, thick, thin)}, colour, marker)
        ("q4 GPTQ-W4", {k: ghf["cells"]["q4:gptq_w4_d1"]["stats"][k] for k in KEYS}, B, "o"),
        ("q4 AWQ-W4", {k: ghf["cells"]["q4:awq_w4"]["stats"][k] for k in KEYS}, B, "o"),
        ("q8 GPTQ-W4", {k: ghf["cells"]["q8:gptq_w4_d1"]["stats"][k] for k in KEYS}, B, "o"),
        ("q8 AWQ-W4", {k: ghf["cells"]["q8:awq_w4"]["stats"][k] for k in KEYS}, B, "o"),
        ("W4 pool", {k: ghf["pools"]["W4:all"]["stats"][k] for k in KEYS}, INK, "s"),
        ("q8 RTN-W3$^s$", {k: ghf["cells"]["q8:rtn_w3"]["stats"][k] for k in KEYS}, QP, "^"),
        ("q14 GPTQ-W4$^b$", {k: q[k] for k in KEYS}, ALT, "D"),
    ]
    S = {lab: st for lab, st, _, _ in rows}

    def chk(lab, k, est, ci=None):
        assert r1(S[lab][k]["est"]) == est, (lab, k, S[lab][k]["est"])
        if ci is not None:
            assert [r1(v) for v in S[lab][k]["ci95"]] == ci, (lab, k, S[lab][k]["ci95"])

    chk("W4 pool", "G", 0.5, [-0.7, 1.7]); chk("W4 pool", "H", 0.2, [-1.3, 1.6]); chk("W4 pool", "F", 0.7, [-0.6, 2.1])
    chk("q8 GPTQ-W4", "G", 3.3, [1.6, 5.0]); chk("q8 GPTQ-W4", "H", 0.4); chk("q8 GPTQ-W4", "F", 5.4, [3.5, 7.2])
    chk("q4 GPTQ-W4", "G", -2.9, [-5.7, -0.2]); chk("q4 GPTQ-W4", "H", 0.7); chk("q4 GPTQ-W4", "F", -2.5)
    chk("q8 RTN-W3$^s$", "G", -0.4, [-3.8, 3.0]); chk("q8 RTN-W3$^s$", "H", 15.3, [0.7, 29.9])
    chk("q8 RTN-W3$^s$", "F", 18.4, [16.7, 20.1])
    chk("q14 GPTQ-W4$^b$", "G", 5.7, [2.9, 8.7]); chk("q14 GPTQ-W4$^b$", "H", 0.4, [-1.1, 1.9])
    chk("q14 GPTQ-W4$^b$", "F", 9.1, [5.8, 12.5])
    assert ghf["cells"]["q8:rtn_w3"]["stats"]["H"]["n_blocks"] == 3
    # preregistered multiplicity family: four core W4 G-H (fixed pool), Holm m = 4 (ghf_multiplicity)
    chk("q4 GPTQ-W4", "GmH", -3.6, [-6.6, -0.6]); chk("q4 AWQ-W4", "GmH", -1.3, [-3.0, 0.6])
    chk("q8 GPTQ-W4", "GmH", 2.9, [1.3, 4.7]); chk("q8 AWQ-W4", "GmH", 3.4, [1.5, 5.2])
    for lab in ("q4 GPTQ-W4", "q4 AWQ-W4", "q8 GPTQ-W4", "q8 AWQ-W4"):
        lo, hi = S[lab]["GmH"]["crossed_ci95"]
        assert lo < 0 < hi, lab
    chk("q8 RTN-W3$^s$", "GmH", -15.7, [-27.5, -3.9]); chk("q14 GPTQ-W4$^b$", "GmH", 5.3, [2.3, 8.4])

    # Holm family (m = 4) for G-H: plain 95% t interval and Bonferroni simultaneous 98.75% interval (same source)
    mult = {r_["cell"]: r_ for r_ in MF.load("mult")["rows"]}
    cellkey = {"q4 GPTQ-W4": "q4:gptq_w4_d1", "q4 AWQ-W4": "q4:awq_w4", "q8 GPTQ-W4": "q8:gptq_w4_d1",
               "q8 AWQ-W4": "q8:awq_w4"}
    assert [round(mult[cellkey[l]]["p_holm"], 3) for l in cellkey] == [0.069, 0.199, 0.013, 0.012]
    assert mult["q4:gptq_w4_d1"]["t_ci95"][1] < 0 < mult["q4:gptq_w4_d1"]["bonf_ci"][1]  # plain excludes 0, Holm fails
    for l, ck in cellkey.items():
        assert abs(mult[ck]["est"] - S[l]["GmH"]["est"]) < 0.06, l

    # (b) joint rescue (only BB succeeds) and rescue undone (BQ = 1, QQ = 0, BB = 0), % of divergent states
    # exploratory, post hoc; fixed pool = block bootstrap (K = 20), new tasks = crossed task x block bootstrap
    MF.SRC["oc"] = "analysis/fork/out/outcome_classes_20261004T143614Z.json"
    oc = MF.load("oc")["groups"]
    ockey = dict(cellkey, **{"W4 pool": "pool W4:all"})
    CLS = [("joint rescue", "joint rescue (only BB)"), ("rescue undone", "rescue undone")]
    for lab, ck in ockey.items():
        assert oc[ck]["K"] == 20, lab
    jr, ru = oc["pool W4:all"]["joint rescue"], oc["pool W4:all"]["rescue undone"]
    assert (r1(jr["est"]), [r1(v) for v in jr["block"]], [r1(v) for v in jr["crossed"]]) == (4.0, [3.5, 4.5], [2.7, 5.3])
    assert (r1(ru["est"]), [r1(v) for v in ru["block"]], [r1(v) for v in ru["crossed"]]) == (4.8, [4.1, 5.4], [3.2, 6.5])
    assert oc["pool W4:all"]["n_states"] == 5576

    main = rows[:5]
    fig = plt.figure(figsize=(COL_W, 2.85), layout="constrained")
    sfa, sfb = fig.subfigures(2, 1, height_ratios=[5.0, 4.0], hspace=0.02)
    panels = [("G", "$G$: this step"), ("H", "$H$: rest"), ("F", "$F$: both"), ("GmH", "$G-H$")]
    allv = [v for _, st, _, _ in main for k, _ in panels[:3] for v in st[k]["crossed_ci95"]]
    allv += [v for l in cellkey for v in mult[cellkey[l]]["bonf_ci"]]
    lim = (min(allv) - 0.8, max(allv) + 0.8)
    ypos, y = [], 0.0
    for lab, *_ in main:
        ypos.append(y)
        y -= 1.0
        if lab == "q8 AWQ-W4":
            y -= 0.35
    axs = sfa.subplots(1, 4, sharey=False)
    for j, (ax, (k, title)) in enumerate(zip(axs, panels)):
        style_axis(ax, grid_axis="x")
        ax.axvline(0, color=INK2, lw=LW_ZERO, zorder=1)
        for (lab, st, col, mk), yy in zip(main, ypos):
            s_ = st[k]
            if k == "GmH" and lab in cellkey:
                m = mult[cellkey[lab]]
                sig = m["p_holm"] < 0.05
                MF.interval(ax, yy, m["est"], m["t_ci95"], m["bonf_ci"], col, marker=mk, horizontal=True,
                            ms=3.2, mfc=col if sig else "white")
            else:
                MF.interval(ax, yy, s_["est"], s_["ci95"], s_.get("crossed_ci95"), col, marker=mk,
                            horizontal=True, ms=3.2)
        ax.set_title(title, pad=2, fontsize=FS)
        ax.set_xlim(*lim)
        ax.set_xticks([t_ for t_ in [-8, 0, 8] if lim[0] <= t_ <= lim[1]])
        ax.tick_params(axis="y", length=0, labelsize=FS)
        ax.tick_params(axis="x", labelsize=FS)
        ax.set_yticks(ypos)
        ax.set_yticklabels([r_[0] for r_ in main] if j == 0 else [])
        ax.set_ylim(ypos[-1] - 0.6, ypos[0] + 0.6)
        if j:
            ax.spines["left"].set_visible(False)
    sfa.supxlabel("gain over QQ, or paired difference (pp)", fontsize=FS)
    sfa.text(0.0, 1.0, "(a)", fontsize=FS, va="top", ha="left")
    axb = sfb.subplots(1, 2)
    hi = max(oc[ck][c]["crossed"][1] for ck in ockey.values() for c, _ in CLS)
    for j, (ax, (c, title)) in enumerate(zip(axb, CLS)):
        style_axis(ax, grid_axis="x")
        for (lab, _, col, mk), yy in zip(main, ypos):
            g = oc[ockey[lab]][c]
            MF.interval(ax, yy, g["est"], g["block"], g["crossed"], col, marker=mk, horizontal=True, ms=3.2)
        ax.set_title(title, pad=2, fontsize=FS)
        ax.set_xlim(0, hi + 0.6)
        ax.set_xticks([0, 2, 4, 6, 8])
        ax.tick_params(axis="y", length=0, labelsize=FS)
        ax.tick_params(axis="x", labelsize=FS)
        ax.set_yticks(ypos)
        ax.set_yticklabels([r_[0] for r_ in main] if j == 0 else [])
        ax.set_ylim(ypos[-1] - 0.6, ypos[0] + 0.6)
        if j:
            ax.spines["left"].set_visible(False)
    sfb.supxlabel("% of divergent states", fontsize=FS)
    sfb.text(0.0, 1.0, "(b)", fontsize=FS, va="top", ha="left")
    MF.save(fig, "f9_upgrade_modes", ["ghf", "mult", "oc"],
            "(a) G/H/F and G-H (t 95% + Bonferroni simultaneous 98.75%) for four core W4 cells + pool; "
            "(b) joint rescue and rescue undone, % of divergent states (block and crossed 95%), same cells + pool")
    pj = os.path.join(MF.OUT, "provenance.json")
    old = json.load(open(pj))
    for kk, v in MF.PROV.items():
        v["script"] = "paper/latex/tools/figs/make_fig_modes.py"
        v["script_sha256"] = script_sha()
        old[kk] = v
    json.dump(old, open(pj, "w"), indent=1, sort_keys=True)
    print("asserts passed")


if __name__ == "__main__":
    f9()
