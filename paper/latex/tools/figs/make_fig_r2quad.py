#!/usr/bin/env python3
"""F11 (visual-first main text, 2026-10-05): Result 2 reference interventions as one full-width row of four panels
(main-text Figure 3; replaces main-text Table tab:refs, whose full version stays in Appendix Table tab:refsfull).

(a) second W4 checkpoint Q' vs B on the same six blocks: rescues, damages, turnover, paired turnover difference,
    and the W3 stress pair's turnover (adapts make_fig_sameprec_a.py);
(b) continuation dependence (off-diagonal share), B vs Q', W4 and W3 stress (descriptive);
(c) common states: K = B's action value beyond Q' under Q's and under B's continuation; thick = two-look 97% (the
    protocol-designated reading), thin = unadjusted 95%; t and task-cluster bootstrap rows (adapts make_fig_commonstate);
(d) key order (exploratory): reversed keys vs B's action on the same 300 states; one bar = wider of block and crossed 95%.

Populations differ between panels; nothing is subtracted across panels. No new numbers: every plotted value is loaded
from a committed analysis output and asserted against the value the paper or its cited report prints. Imports
make_figs only for style, palette, widths, load(), interval() and save(); merges its entry into figures/provenance.json.

    source scripts/a6000/env.sh; cd paper/latex && python3 tools/figs/make_fig_r2quad.py
"""
import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_figs as MF  # noqa: E402
from make_figs import B, FULL_W, INK, INK2, LW_ZERO, Q, QP, Line2D, plt, r1, style_axis  # noqa: E402

NAME = "f11_refs_quad"
FT, FL, FSUB = 8.0, 7.5, 7.0
H = 2.70
TOP = 0.60   # one bold title line + at most three grey subtitle lines per panel (R3 review)
MINUS = "−"


def script_sha():
    return hashlib.sha256(open(os.path.abspath(__file__), "rb").read()).hexdigest()


def header(fig, x_in, titles, sub, sub0=0.21):
    for i, t in enumerate(titles):
        fig.text(x_in / FULL_W, 1 - (0.05 + 0.125 * i) / H, t, fontsize=FT, fontweight="bold", va="top", ha="left",
                 color=INK)
    for i, s in enumerate(sub):
        fig.text(x_in / FULL_W, 1 - (sub0 + 0.108 * i) / H, s, fontsize=FSUB, va="top", ha="left", color=INK2)


def axes(fig, x_in, w_in, top_in=TOP, bot_in=0.55):
    return fig.add_axes([x_in / FULL_W, bot_in / H, w_in / FULL_W, (H - top_in - bot_in) / H])


def pp(x):
    return 100.0 * x


def r1l(v):
    return [r1(x) for x in v]


def data():
    sp, w3, cs, ko = MF.load("same"), MF.load("w3"), MF.load("cs"), MF.load("ko")
    # (a)/(b) same-precision W4 (K = 6) and W3 stress (K = 3)
    assert sp["analysis_set"]["K"] == 6 and w3["analysis_set"]["K"] == 3
    pr, sa, pw, sw = sp["pooled"]["prec"], sp["pooled"]["same"], w3["pooled"]["prec"], w3["pooled"]["same"]
    assert [r1(pr[k]["est"]) for k in ("rescue", "damage", "M", "cond_offdiag")] == [8.0, 8.7, 16.8, 25.0]
    assert [r1(sa[k]["est"]) for k in ("rescue", "damage", "M", "cond_offdiag")] == [9.3, 8.4, 17.7, 26.2]
    assert r1l(pr["M"]["ci95"]) == [13.9, 19.6] and r1l(sa["M"]["ci95"]) == [15.7, 19.8]
    assert r1l(sa["rescue"]["ci95"]) == [7.0, 11.7] and r1l(sa["damage"]["ci95"]) == [6.4, 10.5]
    assert r1l(pr["rescue"]["ci95"]) == [6.0, 10.1] and r1l(pr["damage"]["ci95"]) == [6.5, 11.0]
    for k in ("rescue", "damage", "cond_offdiag"):  # A1.3: every same-precision fixed-pool 95% lower bound > 0
        assert sa[k]["ci95"][0] > 0
    assert r1l(pr["cond_offdiag"]["ci95"]) == [20.6, 29.0] and r1l(sa["cond_offdiag"]["ci95"]) == [20.7, 31.3]
    dM = sp["pooled"]["paired"]["dM"]
    assert r1(dM["est"]) == -1.0 and r1l(dM["ci95"]) == [-3.9, 1.9] and r1l(dM["crossed_ci95"]) == [-4.5, 2.7]
    assert dM["ci95"][0] < 0 < dM["ci95"][1] and dM["crossed_ci95"][0] < 0 < dM["crossed_ci95"][1]
    assert (r1(pw["M"]["est"]), r1(sw["M"]["est"])) == (18.8, 17.3)
    assert r1l(pw["M"]["ci95"]) == [9.9, 27.7] and r1l(sw["M"]["ci95"]) == [8.7, 25.8]
    assert (r1(pw["cond_offdiag"]["est"]), r1(sw["cond_offdiag"]["est"])) == (27.3, 27.6)
    assert r1l(pw["cond_offdiag"]["ci95"]) == [11.3, 43.3] and r1l(sw["cond_offdiag"]["ci95"]) == [27.1, 28.1]
    # R2 review: every drawn crossed (new-task) interval is asserted; the same values are printed in Appendix
    # app:qprime (paragraph "Figure 3a,b intervals"), so each drawn value has a printed source
    CR = {("W4", "prec"): {"rescue": [5.0, 11.9], "damage": [5.7, 12.4], "M": [12.5, 21.6], "cond_offdiag": [18.4, 31.9]},
          ("W4", "same"): {"rescue": [5.9, 13.2], "damage": [5.5, 12.0], "M": [13.4, 22.5], "cond_offdiag": [19.7, 33.5]},
          ("W3", "prec"): {"M": [13.1, 25.9], "cond_offdiag": [19.0, 36.6]},
          ("W3", "same"): {"M": [11.8, 23.7], "cond_offdiag": [21.3, 33.9]}}
    for (pa, des), kv in CR.items():
        P = (sp if pa == "W4" else w3)["pooled"][des]
        for k, v in kv.items():
            assert r1l(P[k]["crossed_ci95"]) == v, (pa, des, k, P[k]["crossed_ci95"])
    # W3 stress: the 3-block t interval (fixed pool) is wider than the crossed one for B's turnover and both
    # off-diagonal shares except Q' (nested; drawn offset, see ivv)
    # divergent-state denominators of (b): 784 / 784 (tab:patternref), W3 474 / 468 (sameprec_w3 .md, Full pool)
    assert (pr["n_states"], sa["n_states"], pw["n_states"], sw["n_states"]) == (784, 784, 474, 468)
    assert sum(w3["cells"][m]["prec"]["n_units"] for m in ("q4", "q8")) == 510  # W3: 85 tasks x 3 blocks x 2 models
    assert sum(sp["cells"][m]["prec"]["n_units"] for m in ("q4", "q8")) == 1020
    # Step 2 (results_r2.tex; tab:refsfull row 10): action-side net difference B - Q'
    dG = sp["pooled"]["paired"]["dG"]
    assert r1(dG["est"]) == -1.6 and r1l(dG["ci95"]) == [-6.2, 3.0] and r1l(dG["crossed_ci95"]) == [-6.5, 3.6]
    assert dG["ci95"][0] < 0 < dG["ci95"][1] and dG["crossed_ci95"][0] < 0 < dG["crossed_ci95"][1]
    # Step 1 equivalence statement: neither pair's turnover difference lies within +-3 pp (both intervals)
    dW = w3["pooled"]["paired"]["dM"]
    assert r1(dW["est"]) == 1.6 and r1l(dW["crossed_ci95"]) == [-2.0, 5.5]
    assert dM["crossed_ci95"][0] < -3 and dW["crossed_ci95"][1] > 3

    # (c) common states, K(c) = V(B, c) - V(Q', c); d1 = Q, bf16 = B continuation
    E = cs["estimates"]
    assert (E["n"], E["k"], E["n_tasks"]) == (510, 6, 85) and cs["margin_pp"] == 3
    K = {c: E["stats"][f"K[{c}]"] for c in ("d1", "bf16")}
    R2 = cs["readings_two_look"]
    assert R2["K[d1]"]["reading"] == R2["K[bf16]"]["reading"] == "not resolved"
    want = {"d1": (1.0, [-4.2, 6.2], [-1.4, 3.5], [-3.5, 5.4], [-1.2, 3.1]),
            "bf16": (0.8, [-2.2, 3.8], [-2.0, 3.7], [-1.8, 3.3], [-1.8, 3.3])}
    for c, (pt, t97, b97, t95, b95) in want.items():
        k = K[c]
        assert r1(pp(k["point"])) == pt
        assert [r1l([pp(x) for x in k[n]]) for n in ("t97", "boot97", "t95", "boot95")] == [t97, b97, t95, b95], c

    # (d) key order (exploratory): conditional %, wider of block and crossed bootstrap 95%
    e = ko["estimate"]
    assert (e["n_eligible_units"], e["n_eligible_tasks"]) == (300, 41)
    cp = e["conditional_pct"]
    kw = {"rescue_K": (3.3, [0.0, 9.3]), "damage_K": (3.3, [0.4, 8.0]), "M_K": (6.7, [0.8, 14.4]),
          "rescue_B": (3.3, [0.0, 9.2]), "damage_B": (5.7, [1.5, 11.5]), "M_B": (9.0, [2.9, 18.2]),
          "M_KmB": (-2.3, [-8.4, 2.9])}
    for k, (est, w) in kw.items():
        assert r1(cp[k]["est"]) == est and r1l(cp[k]["widest"]) == w, k
    rules = e["rules"]
    assert rules["M_K_minus_M_B_upper_below_0"] is False and rules["M_K_minus_M_B_lower_above_0"] is False
    return pr, sa, pw, sw, dM, dG, dW, K, cs["margin_pp"], cp


def ivv(ax, pos, est, thick, thin, color, marker="o", ms=3.4, dx=0.11, z=3):
    """Vertical thick/thin interval. When the thin interval lies inside the thick one it would be hidden, so it is
    drawn as its own 0.6-lw line beside the thick one (offset dx), with short end caps."""
    nested = thin[0] >= thick[0] and thin[1] <= thick[1]
    xt = pos + dx if nested else pos
    ax.plot([xt, xt], thin, color=color, lw=0.6, solid_capstyle="butt", zorder=z)
    if nested:
        for v in thin:
            ax.plot([xt - 0.04, xt + 0.04], [v, v], color=color, lw=0.6, zorder=z)
    ax.plot([pos, pos], thick, color=color, lw=1.8, solid_capstyle="butt", zorder=z)
    ax.plot([pos], [est], marker=marker, ms=ms, color=color, mew=0.8, zorder=z + 1, ls="none")


def f11():
    MF.SRC["same"] = "analysis/fork/out/sameprec_20261004T070601Z.json"
    MF.SRC["w3"] = "analysis/fork/out/sameprec_w3_20261004T070607Z.json"
    MF.SRC["cs"] = "analysis/fork/out/commonstate_q8ext_20261003T231159Z.json"
    MF.SRC["ko"] = "analysis/fork/out/keyorder_20261005T204349Z.json"
    MF.script_sha = script_sha
    pr, sa, pw, sw, dM, dG, dW, K, margin, cp = data()

    fig = plt.figure(figsize=(FULL_W, H))
    # R3 review: (c) gets a right-margin value column; widths rebalanced so (b)'s one-line title and subtitles fit
    GAP = 0.12
    La, wa = 0.33, 1.32
    Lb, wb = 0.29, 0.80
    Lc, wc, wrc = 0.58, 0.74, 0.50
    Ld, wd = 0.41, 0.95
    xa = 0.0
    xb = xa + La + wa + GAP
    xc = xb + Lb + wb + GAP
    xd = xc + Lc + wc + wrc + GAP
    assert xd + Ld + wd <= FULL_W + 1e-6, xd + Ld + wd
    OFF = 0.17
    LIGHT = 0.55  # alpha of thin (new-task / unadjusted) intervals drawn beside or below a thick one

    def tag(ax, x, y, s="not\nresolved", va="bottom"):
        ax.text(x, y, s, fontsize=6.5, color=INK2, ha="center", va=va, style="italic", linespacing=0.95)

    def xcat(ax, labels):
        ax.set_xticklabels(labels, fontsize=FSUB, rotation=28, ha="right", rotation_mode="anchor")
        ax.tick_params(axis="x", length=0, pad=2)

    # ---------- (a) Steps 1-2: Q' vs B. x order follows the argument: Step 1 block | Step 2 block ----------
    ax = axes(fig, xa + La, wa)
    header(fig, xa, ["(a) Steps 1–2: Q′ vs B"],
           ["own first divergent states · % of units", "W4: q4+q8 GPTQ-W4, 85 × 6 bl. (1020)",
            "W3: q4+q8 GPTQ-W3, 85 × 3 bl. (510)"])
    style_axis(ax, grid_axis="y")
    XG = [0, 1, 2]
    for i, k in zip(XG, ("rescue", "damage", "M")):
        ivv(ax, i - OFF, pr[k]["est"], pr[k]["ci95"], pr[k]["crossed_ci95"], B, marker="o")
        ivv(ax, i + OFF, sa[k]["est"], sa[k]["ci95"], sa[k]["crossed_ci95"], QP, marker="s")
    xw = 3.0  # W3 stress turnover (Step 1 content, a separate 3-block panel)
    ivv(ax, xw - OFF, pw["M"]["est"], pw["M"]["ci95"], pw["M"]["crossed_ci95"], B, marker="o")
    ivv(ax, xw + OFF, sw["M"]["est"], sw["M"]["ci95"], sw["M"]["crossed_ci95"], QP, marker="s")
    tag(ax, 2.55, 6.6, "W3: 3 blocks,\nfixed-pool $t$ wider", va="top")
    xsep = 3.62
    ax.axvline(xsep, color=INK2, lw=0.5, ls=(0, (1.5, 1.5)), zorder=1)
    xD = [4.15, 4.95]  # paired differences B - Q': turnover (primary) and net; +-3 pp behind these only
    ax.add_patch(plt.Rectangle((xD[0] - 0.38, -margin), xD[1] - xD[0] + 0.76, 2 * margin, color=INK, alpha=.07,
                               lw=0, zorder=0))
    for x, dd in zip(xD, (dM, dG)):
        ivv(ax, x, dd["est"], dd["ci95"], dd["crossed_ci95"], INK, marker="D")
    tag(ax, np.mean(xD), max(dM["crossed_ci95"][1], dG["crossed_ci95"][1]) + 0.8, "both not\nresolved")
    for x0, t in ((-0.4, "Step 1"), (xsep + 0.1, "Step 2")):
        ax.text(x0, 37.5, t, fontsize=FSUB, color=INK, ha="left", va="top", fontweight="bold")
    ax.axhline(0, color=INK2, lw=LW_ZERO, zorder=1)
    ax.set_xlim(-0.45, 5.4)
    ax.set_xticks(XG + [xw] + xD)
    xcat(ax, ["rescues", "damages", "turnover", "W3 turnover", "Δ turnover", "Δ net"])
    ax.tick_params(axis="y", labelsize=FL, pad=1.5)
    ax.set_ylim(-8, 38)
    ax.set_yticks([0, 10, 20, 30])
    ax.set_ylabel("% of units (Δ: pp)", fontsize=FL, labelpad=1)
    ax.legend(handles=[Line2D([], [], color=B, marker="o", lw=0, ms=3.4, label="B"),
                       Line2D([], [], color=QP, marker="s", lw=0, ms=3.4, label="Q′"),
                       Line2D([], [], color=INK, marker="D", lw=0, ms=3.4, label=f"B {MINUS} Q′")],
              loc="upper left", bbox_to_anchor=(0.0, 0.88), ncol=1, frameon=False, fontsize=FSUB,
              handletextpad=0.05, borderaxespad=0.0, handlelength=1.0, labelspacing=0.15)

    # ---------- (b) Step 1: continuation dependence ----------
    ax = axes(fig, xb + Lb, wb)
    header(fig, xb, ["(b) Step 1: continuation"],
           ["descriptive · % of own", "divergent states",
            f"n: {pr['n_states']}/{sa['n_states']} W4; {pw['n_states']}/{sw['n_states']} W3"])
    style_axis(ax, grid_axis="y")
    for i, (P, S) in enumerate(((pr, sa), (pw, sw))):
        ivv(ax, i - OFF, P["cond_offdiag"]["est"], P["cond_offdiag"]["ci95"], P["cond_offdiag"]["crossed_ci95"], B,
            marker="o")
        ivv(ax, i + OFF, S["cond_offdiag"]["est"], S["cond_offdiag"]["ci95"], S["cond_offdiag"]["crossed_ci95"], QP,
            marker="s")
    tag(ax, 0.72, 9.8, "W3: 3 blocks,\nfixed-pool $t$\nwider", va="top")
    ax.set_xlim(-0.5, 1.5)
    ax.set_xticks([0, 1])
    xcat(ax, ["W4", "W3 stress"])
    ax.tick_params(axis="y", labelsize=FL, pad=1.5)
    ax.set_ylim(0, 46)
    ax.set_yticks([0, 20, 40])

    # ---------- (c) Step 3: common states, K under each continuation ----------
    ax = axes(fig, xc + Lc, wc)
    header(fig, xc, ["(c) Step 3: common states"],
           ["510 q8 states (85 × 6), all arms · pp", "K = B's action value beyond Q′'s",
            "thick: two-look 97% (reading) · thin: 95%"])
    style_axis(ax, grid_axis="x")
    sg = lambda v: (f"+{v:.1f}" if v >= 0 else f"{MINUS}{-v:.1f}")  # noqa: E731
    ys, labs, heads, y = [], [], [], 0.0
    SUB = 0.26  # the unadjusted 95% sits on its own sub-row (it nests inside the 97% interval), lighter
    XR = 1.0 + 0.06 / wc  # right-margin value column (t, two-look 97%)
    for c, title in (("d1", "Q continues"), ("bf16", "B continues")):
        k = K[c]
        heads.append(y)
        ax.text(-Lc / wc, y, title, transform=ax.get_yaxis_transform(), fontsize=FSUB, color=INK, ha="left",
                va="center", style="italic")
        t97 = [pp(v) for v in k["t97"]]
        ax.text(XR, y - 0.8, f"{sg(pp(k['point']))}\n[{sg(t97[0])}, {sg(t97[1])}]",
                transform=ax.get_yaxis_transform(), fontsize=FSUB, color=INK, ha="left", va="center",
                linespacing=1.0)
        y -= 0.8
        for nm, thick, thin, mk in (("t (blocks)", "t97", "t95", "o"), ("task bootstrap", "boot97", "boot95", "s")):
            th = [pp(v) for v in k[thick]]
            tn = [pp(v) for v in k[thin]]
            ax.plot(th, [y, y], color=INK, lw=1.8, solid_capstyle="butt", zorder=3)
            ax.plot([pp(k["point"])], [y], marker=mk, ms=3.0, color=INK, ls="none", zorder=4)
            ax.plot(tn, [y - SUB, y - SUB], color=INK, lw=0.7, solid_capstyle="butt", zorder=3, alpha=LIGHT)
            for v in tn:
                ax.plot([v, v], [y - SUB - 0.1, y - SUB + 0.1], color=INK, lw=0.7, zorder=3, alpha=LIGHT)
            ys.append(y)
            labs.append(nm)
            y -= 0.85
        y -= 0.15
    ax.text(XR, heads[0], "t, 97%", transform=ax.get_yaxis_transform(), fontsize=FSUB, color=INK2,
            ha="left", va="center")
    tag(ax, 6.6, ys[-1] - 0.45, "not\nresolved", va="center")
    ax.set_xlim(-6, 8)
    ax.set_xticks([-3, 0, 3, 6])
    ax.set_xticklabels([f"{MINUS}3", "0", "3", "6"])
    ax.set_xlabel("pp", fontsize=FL, labelpad=1.0)
    ax.set_yticks(ys)
    ax.set_yticklabels(labs, fontsize=FSUB)
    ax.tick_params(axis="y", length=0, pad=2)
    ax.tick_params(axis="x", labelsize=FL, pad=1.5)
    lo, hi = y + 0.3, heads[0] + 0.5
    ax.set_ylim(lo, hi)
    ax.axvspan(-margin, margin, color=INK, alpha=.07, lw=0, zorder=0)
    ax.axvline(0, color=INK2, lw=LW_ZERO, zorder=1)
    ax.grid(False)
    ax.text(-Lc / wc, -0.30 / (H - TOP - 0.55), "pre-registered; 3-block first look unresolved;\n6-block extension and two-look rule "
            "fixed after it", transform=ax.transAxes, fontsize=6.5, color=INK2, ha="left", va="top",
            linespacing=1.0, clip_on=False)

    # ---------- (d) Step 4: key order ----------
    ax = axes(fig, xd + Ld, wd)
    header(fig, xd, ["(d) Step 4: key order"], ["exploratory · 300 q8 GPTQ-W4", "states, 41 tasks · % of states",
                                                "bar: wider of block/crossed 95%"])
    style_axis(ax, grid_axis="y")

    def bar(x, s, col, mk):
        ax.plot([x, x], s["widest"], color=col, lw=1.0, solid_capstyle="butt", zorder=3)
        ax.plot([x], [s["est"]], marker=mk, ms=3.4, color=col, ls="none", zorder=4)
    XG = [0, 1, 2]
    for i, k in zip(XG, ("rescue", "damage", "M")):
        bar(i - OFF, cp[f"{k}_B"], B, "o")
        bar(i + OFF, cp[f"{k}_K"], Q, "^")
    bar(3.0, cp["M_KmB"], INK, "D")
    tag(ax, 3.05, cp["M_KmB"]["widest"][1] + 0.8)
    ax.axhline(0, color=INK2, lw=LW_ZERO, zorder=1)
    ax.set_xlim(-0.45, 3.6)
    ax.set_xticks(XG + [3.0])
    xcat(ax, ["rescues", "damages", "turnover", "Δ turnover"])
    ax.tick_params(axis="y", labelsize=FL, pad=1.5)
    ax.set_ylim(-10, 30)
    ax.set_yticks([-5, 0, 5, 10, 15, 20])
    ax.set_yticklabels([f"{MINUS}5", "0", "5", "10", "15", "20"])
    ax.set_ylabel("% of states (Δ: pp)", fontsize=FL, labelpad=1)
    ax.legend(handles=[Line2D([], [], color=B, marker="o", lw=0, ms=3.4, label="B's action"),
                       Line2D([], [], color=Q, marker="^", lw=0, ms=3.4, label="Q, keys reversed"),
                       Line2D([], [], color=INK, marker="D", lw=0, ms=3.4, label=f"keys {MINUS} B")],
              loc="upper left", bbox_to_anchor=(0.0, 1.0), ncol=1, frameon=False, fontsize=FSUB,
              handletextpad=0.05, borderaxespad=0.0, handlelength=1.0, labelspacing=0.15)

    MF.save(fig, NAME, ["same", "w3", "cs", "ko"],
            "(a) B vs Q' r/d/turnover (W4, K = 6) + paired dM and dG (Step 2 net) with +-3 pp band + W3 stress "
            "turnover, fixed-pool and new-task 95% (thin drawn offset when nested); (b) off-diagonal share B vs Q', "
            "W4 and W3, with divergent-state counts; (c) common-state K under Q and B continuation, two-look 97% and "
            "unadjusted 95% (own sub-row), t and bootstrap, t97 labels; (d) key-order r/d/turnover for reversed keys "
            "and B + difference, wider of block and crossed 95%")
    pj = os.path.join(MF.OUT, "provenance.json")
    old = json.load(open(pj))
    for kk, v in MF.PROV.items():
        v["script"] = "paper/latex/tools/figs/make_fig_r2quad.py"
        v["script_sha256"] = script_sha()
        old[kk] = v
    json.dump(old, open(pj, "w"), indent=1, sort_keys=True)
    print("asserts passed")


if __name__ == "__main__":
    f11()
