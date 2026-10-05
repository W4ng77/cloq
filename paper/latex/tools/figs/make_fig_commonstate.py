#!/usr/bin/env python3
"""F8 (W100f; pre-registered; k = 6 after the fixed extension since 10-03, A1 + D2): common-state action sources on q8, from analysis/fork/analyze_commonstate.py.

Separate from make_figs.py on purpose (another session edits that file); it imports make_figs only for the shared style,
palette, widths, load(), interval() and save(). PDF metadata carries the source JSON sha256 and THIS script's sha256; this
script also merges its entry into figures/provenance.json (other entries untouched).

    /data/ziyangs/cloq_work/envs/cloq/bin/python paper/latex/tools/figs/make_fig_commonstate.py [path/to/commonstate_<UTC>.json]

(a) V(source, continuation), success % on the same 510 states (B = BF16, Q = GPTQ-W4 d1, Q' = GPTQ-W4 d2).
(b) K(c) = V(B, c) - V(Q', c) under each continuation: thick = task-cluster bootstrap 95%, thin = t95 over block means
    (ordinary intervals after the fixed extension; the two-look sensitivity intervals are in the appendix text);
    shaded = the +-3 pp equivalence margin of the frozen rule.
(c) Exact action agreement among the three sources: the five patterns of the 510 states.
Panels are lettered (b)-(d) since 10-04 (post freeze): the figure sits next to the F6a re-plot, panel (a), in main-text Figure 3.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_figs as MF  # noqa: E402
from make_figs import AQUA, BAND, BLUE, COL_W, GRID, INK, INK2, MUTED, ORANGE, plt, style_axis  # noqa: E402,F401
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

DEFAULT = "analysis/fork/out/commonstate_q8ext_20261003T231159Z.json"
NAME = "f8_commonstate"
SHOWS = ("W100u common states (q8, k = 6, after the fixed extension): V(source, continuation) grid, K(c) = V(B,c) - V(Q',c) "
         "with t95 and boot95 under each continuation, and exact action-agreement patterns among B, Q, Q'")


def script_sha():
    return hashlib.sha256(open(os.path.abspath(__file__), "rb").read()).hexdigest()


def pp(x):
    return 100.0 * x


def f8(src: str = DEFAULT):
    MF.SRC["cs"] = src
    MF.script_sha = script_sha  # PDF metadata records THIS script
    r = MF.load("cs")
    E, A = r["estimates"], r["agreement"]
    S = E["stats"]
    n = E["n"]
    # numbers the paper text quotes (sections/results_r2.tex); fail loudly if the source changes
    assert (n, E["k"], E["n_tasks"]) == (510, 6, 85)
    V = {(s, c): pp(S[f"V[{s},{c}]"]["point"]) for s in ("bf16", "d1", "d2") for c in ("bf16", "d1")}
    want = {("bf16", "bf16"): 30.6, ("bf16", "d1"): 30.0, ("d1", "bf16"): 29.0, ("d1", "d1"): 28.8,
            ("d2", "bf16"): 29.8, ("d2", "d1"): 29.0}
    for k, v in want.items():
        MF.near(MF.r1(V[k]), v)
    K = {c: S[f"K[{c}]"] for c in ("bf16", "d1")}
    MF.near(MF.r1(pp(K["d1"]["point"])), 1.0)
    MF.near(MF.r1(pp(K["bf16"]["point"])), 0.8)
    R2 = r["readings_two_look"]
    assert R2["K[bf16]"]["reading"] == R2["K[d1]"]["reading"] == "not resolved"
    MF.near(MF.r1(pp(A["exact_bf16_d1"])), 55.7)
    MF.near(MF.r1(pp(A["exact_bf16_d2"])), 57.3)
    MF.near(MF.r1(pp(A["exact_d1_d2"])), 53.9)
    P = A["patterns"]
    assert sum(P.values()) == n

    fig = plt.figure(figsize=(COL_W, 1.7), layout="constrained")
    gs = fig.add_gridspec(2, 2, height_ratios=[2.35, 1.0], width_ratios=[1.0, 1.25])
    a, b, c = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, :])

    # (a) 3x2 grid, single-hue sequential fill, numbers in ink
    cmap = LinearSegmentedColormap.from_list("seq", ["#ffffff", BLUE])
    rows, cols = ("bf16", "d1", "d2"), ("bf16", "d1")
    lo, hi = 26.0, 33.0
    for i, s in enumerate(rows):
        for j, cc in enumerate(cols):
            v = V[(s, cc)]
            a.add_patch(plt.Rectangle((j, -i - 1), 0.96, 0.92, color=cmap(0.12 + 0.6 * (v - lo) / (hi - lo)), lw=0))
            a.text(j + 0.48, -i - 0.54, f"{v:.1f}", ha="center", va="center", fontsize=7, color=INK)
    a.set_xlim(-0.02, 2.0)
    a.set_ylim(-3.05, 0.0)
    a.set_xticks([0.48, 1.48])
    a.set_xticklabels(["B", "Q"])
    a.xaxis.set_ticks_position("top")
    a.set_yticks([-0.54, -1.54, -2.54])
    a.set_yticklabels(["B", "Q", "Q\u2032"])
    a.tick_params(length=0, pad=1.5)
    for s_ in a.spines.values():
        s_.set_visible(False)
    a.set_ylabel("action source", fontsize=6.8, labelpad=1)
    a.set_title("(b) success %, continuation:", pad=2, fontsize=6.8)

    # (b) K(c) with both intervals and the +-3 pp margin
    style_axis(b, grid_axis="x")
    m = r["margin_pp"]
    b.axvspan(-m, m, color=BAND, zorder=0, lw=0)
    b.axvline(0, color=INK2, lw=0.5, zorder=1)
    for y, cc, col, mk in ((1, "bf16", INK, "o"), (0, "d1", INK, "s")):
        k = K[cc]
        MF.interval(b, y, pp(k["point"]), [pp(x) for x in k["boot95"]], [pp(x) for x in k["t95"]], col, marker=mk,
                    ms=3.4, horizontal=True)
    b.set_yticks([1, 0])
    b.set_yticklabels(["cont. B", "cont. Q"])
    b.tick_params(axis="y", length=0)
    b.set_ylim(-0.6, 1.6)
    b.set_xlim(-10, 10)
    b.set_xlabel("K(c) = V(B, c) \u2212 V(Q\u2032, c), pp", fontsize=6.6, labelpad=1)
    b.set_title("(c) B's action minus Q\u2032's", pad=2, fontsize=6.8)

    # (c) agreement patterns, one stacked bar of the 255 states
    seg = [("all equal", P["all equal"], GRID), ("B=Q", P["BF16 = d1 != d2"], AQUA),
           ("B=Q\u2032", P["BF16 = d2 != d1"], BLUE), ("Q=Q\u2032", P["d1 = d2 != BF16"], ORANGE),
           ("all differ", P["all different"], "#cfcdc6")]
    x0 = 0
    from matplotlib.patches import Patch
    for lab, v, col in seg:
        c.barh(0, v, left=x0, height=0.7, color=col, lw=0.8, edgecolor="white")
        c.text(x0 + v / 2, 0, f"{v}", ha="center", va="center", fontsize=6.2, color=INK)
        x0 += v
    c.set_xlim(0, n)
    c.set_ylim(-0.4, 0.4)
    c.set_yticks([])
    c.set_xticks([])
    for s_ in ("top", "right", "left", "bottom"):
        c.spines[s_].set_visible(False)
    c.legend(handles=[Patch(color=col, label=lab) for lab, _, col in seg], loc="upper center",
             bbox_to_anchor=(0.5, -0.02), ncol=5, frameon=False, fontsize=6.2, handlelength=0.9, columnspacing=0.9,
             handletextpad=0.35, borderaxespad=0.0)
    c.set_title(f"(d) exact action agreement among the three sources ({n} states)", pad=2, fontsize=6.8)

    MF.save(fig, NAME, ["cs"], SHOWS)
    e = MF.PROV[NAME]
    e["script"] = "paper/latex/tools/figs/make_fig_commonstate.py"
    e["script_sha256"] = script_sha()
    pj = os.path.join(MF.OUT, "provenance.json")
    old = json.load(open(pj)) if os.path.exists(pj) else {}
    old[NAME] = e
    json.dump(old, open(pj, "w"), indent=1, sort_keys=True)
    print("asserts passed;", json.dumps(e))


if __name__ == "__main__":
    f8(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
