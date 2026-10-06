#!/usr/bin/env python3
"""F10 (visual-first main text, 2026-10-05): Result 1 as one full-width row of four panels (main-text Figure 2).

(a) development W4: rescues | damages | net per configuration + pool (re-plot of make_figs.f3 panel a);
(b) pre-registered telecom holdout, crossed 90% (re-plot of make_figs.f3 panel b);
(c) upgrade modes G / H / F on W4 divergent states (re-plot of make_fig_modes.f9 panel a, G/H/F only);
(d) joint rescue / rescue undone, observed minus the conditional label-permutation reference (exploratory, post hoc).

No new numbers: every plotted value is loaded from a committed analysis output and asserted against the value the paper
already prints (Table tab:r1, tab:holdout, tab:ghf, tab:ghf-crossed, tab:patternref, results_r1.tex). Imports make_figs
only for style, palette, widths, load(), interval() and save(); merges its entry into figures/provenance.json.

    source scripts/a6000/env.sh; cd paper/latex && python3 tools/figs/make_fig_r1quad.py
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_figs as MF  # noqa: E402
from make_figs import (B, CELL4, DAMAGE, FULL_W, INK, INK2, LW_ZERO, REF, RESCUE, Line2D,  # noqa: E402
                       near, plt, r1, style_axis)

NAME = "f10_r1_quad"
FT, FL, FSUB = 8.0, 7.5, 7.0  # panel title (bold), ticks/labels, grey subtitle
H = 2.70                      # figure height, in (interval key in the caption; enlarged again, R3 review)
SHORT = {"q4 GPTQ-W4": "q4 GPTQ", "q4 AWQ-style W4": "q4 AWQ", "q8 GPTQ-W4": "q8 GPTQ", "q8 AWQ-style W4": "q8 AWQ"}


def script_sha():
    return hashlib.sha256(open(os.path.abspath(__file__), "rb").read()).hexdigest()


def r2(x):
    return round(x + 0.0, 2)


def header(fig, x_in, title, sub):
    """Bold '(x) title' on line 1, grey population/denominator subtitle lines below (inches from the left edge)."""
    fig.text(x_in / FULL_W, 1 - 0.05 / H, title, fontsize=FT, fontweight="bold", va="top", ha="left", color=INK)
    for i, s in enumerate(sub):
        fig.text(x_in / FULL_W, 1 - (0.21 + 0.115 * i) / H, s, fontsize=FSUB, va="top", ha="left", color=INK2)


def iv(ax, pos, est, thick, thin, color, marker="o", ms=3.0, alpha=1.0, mfc=None, z=3):
    """Horizontal thick/thin interval as MF.interval, with an alpha for de-emphasised (descriptive) rows."""
    ax.plot(thin, [pos, pos], color=color, lw=0.6, solid_capstyle="butt", zorder=z, alpha=alpha)
    ax.plot(thick, [pos, pos], color=color, lw=1.8, solid_capstyle="butt", zorder=z, alpha=alpha)
    ax.plot([est], [pos], marker=marker, ms=ms, color=color, mfc=color if mfc is None else mfc, mec=color, mew=0.8,
            zorder=z + 1, ls="none", alpha=alpha)


def axes(fig, x_in, w_in, top_in=0.56, bot_in=0.33):
    return fig.add_axes([x_in / FULL_W, bot_in / H, w_in / FULL_W, (H - top_in - bot_in) / H])


def rows_y(groups, gap=0.35):
    """y positions top-down; a gap before each row flagged True."""
    ys, y = [], 0.0
    for g in groups:
        if g:
            y -= gap
        ys.append(y)
        y -= 1.0
    return ys


def data():
    dev, hc, ghf = MF.load("dev"), MF.load("hconf"), MF.load("ghf")
    pr, oc = MF.load("pref"), MF.load("oc")

    # (a) development W4 (asserts identical to make_figs.f3)
    A = []
    for k, lab in CELL4:
        a = dev["cells"][k]["all_pp"]
        A.append((SHORT[lab], a["rescue"]["est"], a["damage"]["est"], a["G"]["est"], a["G"]["ci95"],
                  a["G"]["crossed_ci95"], a["M"]["est"], False))
    p = dev["pooled"]["W4:all:pooled_equal_weight"]
    A.append(("W4 pool", p["rescue"]["est"], p["damage"]["est"], p["G"]["est"], p["G"]["ci95"], p["G"]["crossed_ci95"],
              p["M"]["est"], True))
    assert [r1(r[1]) for r in A[:4]] == [6.8, 9.8, 10.4, 11.4] and [r1(r[2]) for r in A[:4]] == [8.7, 10.1, 7.5, 9.5]
    assert [r1(r[6]) for r in A[:4]] == [15.5, 19.9, 17.9, 20.9] and r1(A[4][6]) == 18.6
    assert [r1(r[3]) for r in A[:4]] == [-1.9, -0.3, 2.9, 1.9]
    assert [[r1(v) for v in r[4]] for r in A[:4]] == [[-3.7, -0.1], [-2.2, 1.6], [1.4, 4.4], [-0.6, 4.3]]
    assert [[r1(v) for v in r[5]] for r in A[:4]] == [[-6.8, 2.7], [-5.4, 5.2], [-2.9, 9.2], [-3.9, 8.1]]
    assert (r1(A[4][1]), r1(A[4][2]), r1(A[4][3])) == (9.6, 9.0, 0.7)
    assert [r1(v) for v in A[4][4]] == [-0.3, 1.6] and [r1(v) for v in A[4][5]] == [-2.1, 3.4]
    assert [(r[4][0] > 0) - (r[4][1] < 0) for r in A[:4]] == [-1, 0, 1, 0]  # two fixed-pool intervals exclude 0
    assert all(r[5][0] < 0 < r[5][1] for r in A)                          # no new-task interval does
    for k in ("q4:kvq_int8", "q8:kvq_int8"):  # KV8 rows: asserted as in f3, not drawn
        a = dev["cells"][k]["all_pp"]
        assert (r1(a["rescue"]["est"]), r1(a["damage"]["est"])) in ((3.1, 3.4), (4.3, 3.7))

    # (b) telecom holdout, crossed 90% (asserts identical to make_figs.f3)
    Bh = []
    for k, lab in [("q4:gptq_w4_d1", "q4 GPTQ"), ("q8:gptq_w4_d1", "q8 GPTQ"), ("q8:awq_w4", "q8 AWQ")]:
        c = hc["per_cell_descriptive"][k]
        Bh.append((lab, c["rescue"]["crossed"]["est"], c["damage"]["crossed"]["est"], c["G"]["crossed"]["est"],
                   c["G"]["crossed"]["ci90"], False))
    pg, s1 = hc["primary_G_all"], hc["S1_two_sided_consequences"]
    Bh.append(("Weighted", s1["rescue"]["crossed_decisional"]["est"], s1["damage"]["crossed_decisional"]["est"],
               pg["crossed_decisional"]["est"], pg["crossed_decisional"]["ci90"], True))
    assert r2(pg["crossed_decisional"]["est"]) == -4.57
    assert [r2(v) for v in pg["crossed_decisional"]["ci90"]] == [-7.17, -1.96]
    assert [r2(v) for v in pg["block_t_alongside"]["ci90"]] == [-6.08, -3.05]  # asserted, not drawn
    assert (r2(Bh[3][1]), r2(Bh[3][2])) == (5.21, 9.77)
    assert [r2(r[3]) for r in Bh[:3]] == [-3.03, -5.64, -6.57]
    assert [r2(r[1]) for r in Bh[:3]] == [5.05, 4.41, 6.31] and [r2(r[2]) for r in Bh[:3]] == [8.08, 10.05, 12.88]

    # (c) G / H / F on divergent states (asserts: tab:ghf, tab:ghf-crossed, results_r1.tex)
    C = [(SHORT[lab], {m: ghf["cells"][k]["stats"][m] for m in "GHF"}, False) for k, lab in CELL4]
    C.append(("W4 pool", {m: ghf["pools"]["W4:all"]["stats"][m] for m in "GHF"}, True))
    S = {r[0]: r[1] for r in C}

    def chk(lab, m, est, fx=None, cr=None):
        s = S[lab][m]
        assert r1(s["est"]) == est, (lab, m, s["est"])
        if fx is not None:
            assert [r1(v) for v in s["ci95"]] == fx, (lab, m, s["ci95"])
        if cr is not None:
            assert [r1(v) for v in s["crossed_ci95"]] == cr, (lab, m, s["crossed_ci95"])
    chk("W4 pool", "G", 0.5, [-0.7, 1.7], [-2.9, 3.8]); chk("W4 pool", "H", 0.2, [-1.3, 1.6], [-2.7, 2.8])
    chk("W4 pool", "F", 0.7, [-0.6, 2.1], [-3.1, 4.4])
    chk("q4 GPTQ", "G", -2.9, [-5.7, -0.2], [-10.3, 4.2]); chk("q4 GPTQ", "H", 0.7, [-1.6, 3.0], [-4.0, 6.0])
    chk("q4 GPTQ", "F", -2.5, [-5.3, 0.2], [-9.9, 4.7])
    chk("q4 AWQ", "G", -0.3); chk("q4 AWQ", "H", 0.9); chk("q4 AWQ", "F", -0.8)
    chk("q8 GPTQ", "G", 3.3, [1.6, 5.0]); chk("q8 GPTQ", "H", 0.4); chk("q8 GPTQ", "F", 5.4, [3.5, 7.2])
    chk("q8 AWQ", "G", 2.1); chk("q8 AWQ", "H", -1.3); chk("q8 AWQ", "F", 0.6)
    for m in "GHF":  # W4 pool: every fixed-pool and new-task interval covers zero (results_r1.tex)
        s = S["W4 pool"][m]
        assert s["ci95"][0] < 0 < s["ci95"][1] and s["crossed_ci95"][0] < 0 < s["crossed_ci95"][1]
    assert oc["groups"]["pool W4:all"]["n_states"] == 5576

    # (d) joint rescue (J) / rescue undone (U): observed minus label-permutation reference (tab:patternref)
    G = pr["groups"]
    D = []
    want = {("J", "pool W4:all"): (3.96, 3.48, 0.47, [0.06, 0.87], [-0.33, 1.37]),
            ("J", "pool W4:q4"): (3.22, 3.56, -0.34, [-0.83, 0.13], [-1.46, 0.88]),
            ("J", "pool W4:q8"): (4.69, 3.40, 1.29, [0.79, 1.78], [-0.07, 2.74]),
            ("U", "pool W4:all"): (4.80, 5.78, -0.99, [-1.58, -0.42], [-2.19, 0.27]),
            ("U", "pool W4:q4"): (4.77, 6.01, -1.24, [-2.09, -0.45], [-2.97, 0.69]),
            ("U", "pool W4:q8"): (4.82, 5.56, -0.74, [-1.35, -0.07], [-2.34, 0.98])}
    for (c, g), (o, rf, d, blk, cr) in want.items():
        x = G[g]
        assert x["K"] == 20
        assert (r2(x[f"{c} obs"]["est"]), r2(x[f"{c} ref"]["est"])) == (o, rf), (c, g)
        dd = x[f"{c} obs-ref"]
        assert r2(dd["est"]) == d and [r2(v) for v in dd["block"]] == blk and [r2(v) for v in dd["crossed"]] == cr
        assert dd["crossed"][0] < 0 < dd["crossed"][1]  # every new-task interval covers zero (the paper's reading)
        D.append((c, {"pool W4:all": "W4 pool", "pool W4:q4": "q4", "pool W4:q8": "q8"}[g],
                  x[f"{c} obs"]["est"], x[f"{c} ref"]["est"], dd["est"], dd["block"], dd["crossed"]))
    # cross-check against the outcome-class shares printed in Appendix app:offdiag (paragraph before
    # Table tab:patternref: 4.0 / 4.8 with both intervals)
    o4 = oc["groups"]["pool W4:all"]
    jr, ru = o4["joint rescue"], o4["rescue undone"]
    near(jr["est"], G["pool W4:all"]["J obs"]["est"], 0.006); near(ru["est"], G["pool W4:all"]["U obs"]["est"], 0.006)
    assert (r1(jr["est"]), [r1(v) for v in jr["block"]], [r1(v) for v in jr["crossed"]]) == (4.0, [3.5, 4.5], [2.7, 5.3])
    assert (r1(ru["est"]), [r1(v) for v in ru["block"]], [r1(v) for v in ru["crossed"]]) == (4.8, [4.1, 5.4], [3.2, 6.5])
    return A, Bh, C, D


def f10():
    MF.SRC["pref"] = "analysis/fork/out/pattern_ref_20261005T134721Z.json"
    MF.SRC["oc"] = "analysis/fork/out/outcome_classes_20261004T143614Z.json"
    MF.script_sha = script_sha
    A, Bh, C, D = data()

    fig = plt.figure(figsize=(FULL_W, H))
    # inch layout per panel: label column | axis (| side column); gaps between panels
    GAP = 0.15
    La, wa, wm = 0.50, 0.98, 0.26            # (a) + turnover column
    Lb, wb = 0.47, 0.83                      # (b)
    Lc, wc = 0.44, 0.88                      # (c)
    Ld, wd, wr = 0.40, 0.58, 0.48            # (d) + obs/ref column
    xa = 0.0
    xb = xa + La + wa + wm + GAP
    xc = xb + Lb + wb + GAP
    xd = xc + Lc + wc + GAP
    assert xd + Ld + wd + wr <= FULL_W + 1e-6, xd + Ld + wd + wr

    # ---------- (a) development W4 ----------
    ax = axes(fig, xa + La, wa)
    header(fig, xa, "(a) Development, W4", ["85 tasks × 20 blocks", "% of task×block units"])
    style_axis(ax, grid_axis="x")
    ys = rows_y([r[7] for r in A])
    for r, y in zip(A, ys):
        lab, res, dam, net, thick, thin, M, pool = r
        ax.barh(y, res, height=.58, color=RESCUE, alpha=.82, lw=0, zorder=2)
        ax.barh(y, -dam, height=.58, color=DAMAGE, alpha=.82, lw=0, zorder=2)
        MF.interval(ax, y, net, thick, thin, INK, marker="D", ms=3.4, horizontal=True, z=4)
        ax.text(1.0 + 0.07 / wa, y, f"{M:.1f}", transform=ax.get_yaxis_transform(), fontsize=FL, color=INK2,
                ha="left", va="center", fontweight="bold" if pool else "normal")
    ax.text(1.0 + 0.07 / wa, ys[0] + 0.62, "turn-\nover", transform=ax.get_yaxis_transform(), fontsize=FSUB,
            color=INK2, ha="left", va="bottom", linespacing=0.95)
    ax.axvline(0, color=INK2, lw=LW_ZERO, zorder=3)
    ax.set_xlim(-13, 13)
    ax.set_xticks([-10, 0, 10])
    ax.set_xticklabels(["10", "0", "10"])
    ax.set_xlabel("← damages   rescues →", fontsize=FL, labelpad=1.5)
    ax.legend(handles=[Line2D([], [], color=INK, marker="D", lw=0, ms=3.4, label="net, pp")], loc="upper left",
              bbox_to_anchor=(0.01, 1.04), frameon=False, fontsize=FSUB, handletextpad=0.1, borderaxespad=0.0,
              handlelength=0.8)
    _ylabels(ax, ys, [r[0] for r in A], [r[7] for r in A], hi=ys[0] + 1.0)

    # ---------- (b) telecom holdout ----------
    ax = axes(fig, xb + Lb, wb)
    header(fig, xb, "(b) Telecom holdout", ["pre-registered · 34 tasks × 12 bl.", "% of units · crossed 90%"])
    style_axis(ax, grid_axis="x")
    ys = rows_y([r[5] for r in Bh])
    for r, y in zip(Bh, ys):
        lab, res, dam, net, ci90, prim = r
        al = .82 if prim else .45
        ax.barh(y, res, height=.58, color=RESCUE, alpha=al, lw=0, zorder=2)
        ax.barh(y, -dam, height=.58, color=DAMAGE, alpha=al, lw=0, zorder=2)
        # one interval type (crossed 90%) at one weight; the primary row is marked by its filled diamond + bold label
        ax.plot(ci90, [y, y], color=INK if prim else INK2, lw=1.0, solid_capstyle="butt", zorder=4)
        ax.plot([net], [y], marker="D", ms=3.8 if prim else 3.0, color=INK if prim else INK2,
                mfc=INK if prim else "white", mec="white" if prim else INK2, mew=0.6 if prim else 0.8, ls="none",
                zorder=5)
    p = Bh[3]
    m = lambda v: f"{v:.2f}".replace("-", "\u2212")  # noqa: E731
    # the frozen reading sits below the rows, outside the zero line / shading extent and clear of the left spine
    lo_b = ys[3] - 2.15
    note_top = ys[3] - 0.5
    fr = (note_top - lo_b) / (ys[0] + 0.85 - lo_b)
    ax.axvspan(-3, 3, ymin=fr, color=INK, alpha=.07, lw=0, zorder=0)
    ax.axvline(0, ymin=fr, color=INK2, lw=LW_ZERO, zorder=3)
    ax.spines["left"].set_bounds(note_top, ys[0] + 0.85)
    ax.text(1.0, ys[3] - 0.62, f"net {m(p[3])} [{m(p[4][0])}, {m(p[4][1])}]", fontsize=FSUB, color=INK,
            ha="right", va="top", transform=ax.get_yaxis_transform(), zorder=6)
    ax.text(1.0, ys[3] - 1.36, "frozen reading: inconclusive", fontsize=FSUB, color=INK, ha="right", va="top",
            style="italic", transform=ax.get_yaxis_transform(), zorder=6)
    ax.grid(False)
    ax.set_xlim(-14, 14)
    ax.set_xticks([-10, 0, 10])
    ax.set_xticklabels(["10", "0", "10"])
    ax.set_xlabel("← damages   rescues →", fontsize=FL, labelpad=1.5)
    _ylabels(ax, ys, [r[0] for r in Bh], [r[5] for r in Bh], lo=lo_b, grey=[not r[5] for r in Bh])

    # ---------- (c) G / H / F ----------
    ax = axes(fig, xc + Lc, wc)
    header(fig, xc, "(c) Upgrade modes", ["W4 divergent states (5576)", "G this step · H rest · F both"])
    style_axis(ax, grid_axis="x")
    ax.axvspan(-3, 3, color=INK, alpha=.07, lw=0, zorder=0)
    ax.axvline(0, color=INK2, lw=LW_ZERO, zorder=1)
    ys = rows_y([r[2] for r in C])
    # H drawn grey with an open square so that blue keeps meaning B's action (G) across figures
    # R3 review: H in a darker grey (REF is too light on the +-3 pp band); grey keeps one meaning (the band)
    MODES = [("G", B, "o", 0.24, None), ("H", "#6E6E6E", "s", 0.0, "white"), ("F", INK, "D", -0.24, None)]
    for (lab, st, pool), y in zip(C, ys):
        if pool:  # the W4-pool row is the reading row: a thin rule above it (no grey box); configuration rows recede
            ax.axhline(y + 0.5 + 0.35 / 2, color=INK2, lw=0.4, zorder=1)
        for mo, col, mk, off, mfc in MODES:
            s = st[mo]
            iv(ax, y + off, s["est"], s["ci95"], s["crossed_ci95"], col, marker=mk, ms=2.8,
               alpha=1.0 if pool else 0.65, mfc=mfc)
    ax.text(-0.04, ys[-1] - 0.5, "W4 pool:\nall cover 0", transform=ax.get_yaxis_transform(), fontsize=FSUB,
            color=INK2, ha="right", va="top", style="italic", linespacing=1.0)
    ax.set_xlim(-11, 14)
    ax.set_xticks([-8, 0, 8])
    ax.set_xlabel("gain over QQ, pp", fontsize=FL, labelpad=1.5)
    ax.legend(handles=[Line2D([], [], color=col, marker=mk, mfc=col if mfc is None else mfc, lw=0, ms=3.2, label=mo)
                       for mo, col, mk, _, mfc in MODES],
              loc="upper center", bbox_to_anchor=(0.5, 1.04), ncol=3, frameon=False, fontsize=FSUB,
              handletextpad=0.05, columnspacing=0.8, borderaxespad=0.0, handlelength=1.0)
    _ylabels(ax, ys, [r[0] for r in C], [r[2] for r in C], lo=ys[-1] - 0.75, hi=ys[0] + 1.05)
    ax.spines["left"].set_bounds(ys[-1] - 0.75, ys[0] + 1.05)

    # ---------- (d) joint rescue / rescue undone vs reference ----------
    ax = axes(fig, xd + Ld, wd)
    header(fig, xd, "(d) Patterns vs reference", ["W4 divergent states, pp", "exploratory, post hoc",
                                                     "reading: new-task 95%"])
    style_axis(ax, grid_axis="x")
    ax.axvline(0, color=INK2, lw=LW_ZERO, zorder=1)
    ys, lab, heads, y = [], [], [], 0.0
    for c, title in (("J", "joint rescue"), ("U", "rescue undone")):
        heads.append((y, title))
        y -= 0.8
        for row in [d for d in D if d[0] == c]:
            ys.append(y)
            lab.append(row)
            y -= 0.85
        y -= 0.2
    for row, yy in zip(lab, ys):
        c, g, o, rf, d, blk, cr = row
        # obs - ref is a difference: black diamond as for net, B - Q' and keys - B; small so the thick bar shows
        MF.interval(ax, yy, d, blk, cr, INK if g == "W4 pool" else INK2, marker="D", ms=2.2, horizontal=True)
        ax.text(1.0 + 0.05 / wd, yy, f"{o:.2f} / {rf:.2f}", transform=ax.get_yaxis_transform(), fontsize=FSUB,
                color=INK2, ha="left", va="center")
    for yy, t in heads:  # group headings inside the axes (clear of the spine), opaque over the zero line
        ax.text(0.03, yy, t, transform=ax.get_yaxis_transform(), fontsize=FSUB, color=INK, ha="left",
                va="center", style="italic", zorder=6,
                bbox=dict(boxstyle="square,pad=0.05", fc="white", ec="none"))
    ax.text(1.0 + 0.05 / wd, heads[0][0] - 0.1, "obs / ref, %", transform=ax.get_yaxis_transform(), fontsize=FSUB,
            color=INK2, ha="left", va="bottom")
    ax.set_xlim(-3.3, 3.0)
    ax.set_xticks([-2, 0, 2])
    ax.set_xlabel("obs \u2212 ref, pp", fontsize=FL, labelpad=1.5)
    ax.text(-0.04, ys[-1] - 0.45, "new tasks:\nall cover 0", transform=ax.get_yaxis_transform(), fontsize=FSUB,
            color=INK2, ha="right", va="top", style="italic", linespacing=1.0)
    _ylabels(ax, ys, [r[1] for r in lab], [r[1] == "W4 pool" for r in lab], lo=ys[-1] - 1.15,
             hi=heads[0][0] + 0.5)
    ax.spines["left"].set_bounds(ys[-1] - 1.15, heads[0][0] + 0.5)

    # interval key: stated once, in the caption (R2 review: not both caption and footer)
    MF.save(fig, NAME, ["dev", "hconf", "ghf", "pref", "oc"],
            "(a) dev W4 rescue/damage/net (+turnover) per config + pool, fixed-pool and new-task 95%; (b) telecom "
            "holdout rescue/damage/net, crossed 90%, primary weighted row; (c) G/H/F on W4 divergent states, "
            "fixed-pool and new-task 95%; (d) joint rescue / rescue undone observed minus label-permutation reference "
            "(block and crossed 95%), obs/ref printed")
    pj = os.path.join(MF.OUT, "provenance.json")
    old = json.load(open(pj))
    for kk, v in MF.PROV.items():
        v["script"] = "paper/latex/tools/figs/make_fig_r1quad.py"
        v["script_sha256"] = script_sha()
        old[kk] = v
    json.dump(old, open(pj, "w"), indent=1, sort_keys=True)
    print("asserts passed")


def _ylabels(ax, ys, labels, bold, lo=None, hi=None, grey=None):
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=FL)
    for i, t in enumerate(ax.get_yticklabels()):
        if bold[i]:
            t.set_fontweight("bold")
        if grey is not None and grey[i]:
            t.set_color(INK2)
    ax.tick_params(axis="y", length=0, pad=2)
    ax.tick_params(axis="x", labelsize=FL, pad=1.5)
    ax.set_ylim(ys[-1] - 0.7 if lo is None else lo, ys[0] + 0.85 if hi is None else hi)


if __name__ == "__main__":
    f10()
