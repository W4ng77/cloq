#!/usr/bin/env python3
"""F7 (W100d; INTERIM, descriptive): which units the two substitutions rescue / harm, from analysis/fork/sameprec_split.py.

Separate from make_figs.py on purpose (another session edits that file); it imports make_figs only for the shared style,
palette, widths, load() and save() (PDF metadata carries the source JSON sha256 and this script's sha256). It does not write
figures/provenance.json; the provenance is in the PDF metadata and printed here.

    /data/ziyangs/cloq_work/envs/cloq/bin/python paper/latex/tools/figs/make_fig_sameprec_split.py [path/to/sameprec_split_<UTC>.json]

(a) Per contrast (G action side, H continuation side, F full substitution) and design (BF16 vs GPTQ-W4 d2 as the B role):
    rescues above zero, harms below, split into units shared by both designs and design-specific units; net marked.
(b) Cohen's kappa of each set between the designs, block-bootstrap 95%, against the within-task(x Y_QQ) shuffle null.
"""
import glob
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_figs as MF  # noqa: E402
from make_figs import AQUA, BLUE, FULL_W, GRID, INK, INK2, MUTED, ORANGE, BAND, plt, style_axis  # noqa: E402,F401
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

DEFAULT = "analysis/fork/out/sameprec_split_20261002T145148Z.json"


def script_sha():
    return hashlib.sha256(open(os.path.abspath(__file__), "rb").read()).hexdigest()


def f7(src: str = DEFAULT):
    MF.SRC["split"] = src
    MF.script_sha = script_sha  # PDF metadata records THIS script
    r = MF.load("split")
    R = r["main"]
    S, N, C = R["sets"]["by_contrast"], R["net"], R["controller"]["both_divergent"]
    assert R["sets"]["yqq_mismatch_units"] == 0
    for c in ("G", "H", "F"):
        cn = N[c]["counts"]
        assert cn["net_BF16"] == cn["shared_rescue"] + cn["BF16_only_rescue"] - cn["shared_harm"] - cn["BF16_only_harm"]
        assert cn["net_d2"] == cn["shared_rescue"] + cn["d2_only_rescue"] - cn["shared_harm"] - cn["d2_only_harm"]
        assert S[c]["rescue"]["both"] == cn["shared_rescue"] and S[c]["harm"]["both"] == cn["shared_harm"]
    if R["K"] == 6:  # interim numbers quoted in docs/RESEARCH_LOG.md W100d
        g = N["G"]["counts"]
        assert (g["shared_rescue"], g["BF16_only_rescue"], g["d2_only_rescue"]) == (56, 26, 39)
        assert (g["shared_harm"], g["BF16_only_harm"], g["d2_only_harm"]) == (51, 38, 35)
        assert round(C["kappa"], 2) == 0.29 and R["n_units"] == 1020

    fig, (a, b) = plt.subplots(1, 2, figsize=(FULL_W, 1.75), layout="constrained", gridspec_kw={"width_ratios": [1.9, 1.0]})
    # (a) diverging stacked counts
    style_axis(a)
    w = 0.34
    xt, xl = [], []
    for i, c in enumerate(("G", "H", "F")):
        cn = N[c]["counts"]
        for j, (d, col) in enumerate((("BF16", BLUE), ("d2", ORANGE))):
            x = i + (j - 0.5) * (w + 0.06)
            for sign, kind in ((1, "rescue"), (-1, "harm")):
                sh, sp = cn[f"shared_{kind}"], cn[f"{d}_only_{kind}"]
                a.bar(x, sign * sh, w, color=AQUA, lw=0, zorder=2, alpha=1.0 if sign > 0 else 0.6)
                a.bar(x, sign * sp, w, bottom=sign * sh, color=col, lw=0.6, zorder=2, alpha=1.0 if sign > 0 else 0.6,
                      edgecolor="white")
            net = cn[f"net_{d}"]
            a.plot([x], [net], marker="D", ms=3.2, color=INK, mfc="white", mew=0.8, zorder=4, ls="none")
            a.text(x, cn["shared_rescue"] + cn[f"{d}_only_rescue"] + 3, f"{cn[f'flips_{d}']}", ha="center", va="bottom",
                   fontsize=6, color=INK2)
        xt.append(i)
        xl.append({"G": "$G$ action ($BQ$ vs $QQ$)", "H": "$H$ continuation ($QB$)", "F": "$F$ full ($BB$)"}[c])
    a.axhline(0, color=INK2, lw=0.5, zorder=3)
    a.set_xticks(xt)
    a.set_xticklabels(xl)
    a.tick_params(axis="x", length=0)
    a.set_ylabel(f"harm ←  units of {R['n_units']}  → rescue", fontsize=6.8)
    lim = max(N[c]["counts"][f"flips_{d}"] for c in "GHF" for d in ("BF16", "d2"))
    a.set_ylim(-0.95 * lim, 0.85 * lim)
    a.legend(handles=[Patch(color=AQUA, label="shared by both"), Patch(color=BLUE, label="BF16 only"),
                      Patch(color=ORANGE, label="W4 ckpt 2 only"),
                      Line2D([], [], marker="D", ms=3.2, color=INK, mfc="white", lw=0, label="net")],
             loc="lower center", frameon=False, fontsize=6.2, ncol=4, handlelength=1.0, columnspacing=0.8, borderaxespad=0.1)
    a.set_title(f"(a) rescued / harmed units by substitution (bar top: flips; K = {R['K']}, interim)", pad=2)
    # (b) kappa vs shuffle null
    style_axis(b, grid_axis="x")
    rows = [(f"{c} {s[0]}", S[c][s], S[c][s]["null_within_task_yqq"]) for c in ("G", "H", "F") for s in ("rescue", "harm")]
    rows.append(("off-diag.", C, C["null_within_task"]))
    for k, (lab, x, nl) in enumerate(rows):
        y = -k
        b.plot(nl["kappa_null_95"], [y, y], color=GRID, lw=3.2, solid_capstyle="butt", zorder=1)
        b.plot([nl["kappa_null_mean"]], [y], marker="|", ms=5, color=MUTED, zorder=2, ls="none")
        MF.interval(b, y, x["kappa"], x["kappa_boot_ci95"], None, INK, marker="o", ms=3.2, horizontal=True)
    b.set_yticks([-k for k in range(len(rows))])
    b.set_yticklabels([r_[0] for r_ in rows])
    b.tick_params(axis="y", length=0)
    b.set_xlim(-0.05, 0.8)
    b.axvline(0, color=INK2, lw=0.5)
    b.set_xlabel("κ (block-boot 95%); grey: shuffle null")
    b.set_title("(b) same units under both?", pad=2)
    MF.save(fig, "f7_sameprec_split", ["split"],
            "W100d interim: rescue/harm sets shared vs design-specific for G/H/F (BF16 vs W4 d2) and kappa vs within-task shuffle null")
    print({k: v for k, v in MF.PROV.items()})


if __name__ == "__main__":
    f7(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
