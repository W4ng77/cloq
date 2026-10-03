#!/usr/bin/env python3
"""F9 (W100j): paired upgrade modes G (this step), H (from the next step), F (both) per configuration, main text.

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
from make_figs import BLUE, COL_W, INK, INK2, ORANGE, AQUA, plt, style_axis, r1  # noqa: E402


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
        ("q4 GPTQ-W4", {k: ghf["cells"]["q4:gptq_w4_d1"]["stats"][k] for k in KEYS}, BLUE, "o"),
        ("q4 AWQ-W4", {k: ghf["cells"]["q4:awq_w4"]["stats"][k] for k in KEYS}, BLUE, "o"),
        ("q8 GPTQ-W4", {k: ghf["cells"]["q8:gptq_w4_d1"]["stats"][k] for k in KEYS}, BLUE, "o"),
        ("q8 AWQ-W4", {k: ghf["cells"]["q8:awq_w4"]["stats"][k] for k in KEYS}, BLUE, "o"),
        ("W4 pool", {k: ghf["pools"]["W4:all"]["stats"][k] for k in KEYS}, INK, "s"),
        ("q8 RTN-W3$^s$", {k: ghf["cells"]["q8:rtn_w3"]["stats"][k] for k in KEYS}, ORANGE, "^"),
        ("q14 GPTQ-W4$^b$", {k: q[k] for k in KEYS}, AQUA, "D"),
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

    main = rows[:5]
    supp = rows[5:]
    fig = plt.figure(figsize=(COL_W, 2.45), layout="constrained")
    gs = fig.add_gridspec(2, 4, height_ratios=[5.0, 2.3])
    panels = [("G", "$G$: this step"), ("H", "$H$: rest"), ("F", "$F$: both"), ("GmH", "$G-H$")]
    allv = [v for _, st, _, _ in main for k, _ in panels[:3] for v in st[k]["crossed_ci95"]]
    allv += [v for l in cellkey for v in mult[cellkey[l]]["bonf_ci"]]
    lim = (min(allv) - 0.8, max(allv) + 0.8)
    for row_i, (rws, xl, xt) in enumerate([(main, lim, [-8, 0, 8]), (supp, (-30, 32), [-20, 0, 20])]):
        ypos, y = [], 0.0
        for lab, *_ in rws:
            ypos.append(y)
            y -= 1.0
            if lab == "q8 AWQ-W4":
                y -= 0.35
        axs = [fig.add_subplot(gs[row_i, j]) for j in range(4)]
        for j, (ax, (k, title)) in enumerate(zip(axs, panels)):
            style_axis(ax, grid_axis="x")
            ax.axvline(0, color=INK2, lw=0.6, zorder=1)
            for (lab, st, col, mk), yy in zip(rws, ypos):
                s_ = st[k]
                if k == "GmH" and lab in cellkey:
                    m = mult[cellkey[lab]]
                    sig = m["p_holm"] < 0.05
                    MF.interval(ax, yy, m["est"], m["t_ci95"], m["bonf_ci"], col, marker=mk, horizontal=True,
                                ms=3.2, mfc=col if sig else "white")
                else:
                    MF.interval(ax, yy, s_["est"], s_["ci95"], s_.get("crossed_ci95"), col, marker=mk,
                                horizontal=True, ms=3.2)
            if row_i == 0:
                ax.set_title(title, pad=2, fontsize=7)
            ax.set_xlim(*xl)
            ax.set_xticks([t_ for t_ in xt if xl[0] <= t_ <= xl[1]])
            ax.tick_params(axis="y", length=0, labelsize=6.5)
            ax.tick_params(axis="x", labelsize=6.3)
            ax.set_yticks(ypos)
            ax.set_yticklabels([r_[0] for r_ in rws] if j == 0 else [])
            ax.set_ylim(ypos[-1] - 0.6, ypos[0] + 0.6)
            if j:
                ax.spines["left"].set_visible(False)
        if row_i == 1:
            for ax in axs:
                ax.set_title("supplementary, own scale" if ax is axs[1] else " ", pad=2, fontsize=6.3,
                             color=INK2, style="italic", loc="center")
    fig.supxlabel("gain over QQ, or paired difference (pp)", fontsize=7)
    MF.save(fig, "f9_upgrade_modes", ["ghf", "q14", "mult"],
            "main: G/H/F and G-H (t 95% + Bonferroni simultaneous 98.75%) for four core W4 cells + pool; supplementary: q8 RTN-W3, q14 BFCL (own scale)")
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
