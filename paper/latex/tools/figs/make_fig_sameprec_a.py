#!/usr/bin/env python3
"""F6a (post-freeze editing, 2026-10-04): column-width re-plot of panel (a) of F6 for the main-text Figure 3.

Same data and asserts as make_figs.f6 panel (a); re-plot only, no new numbers. Separate from make_figs.py (another
session edits it); imports it only for style, palette, widths, load(), interval() and save(). Reads the frozen
same-precision output (analysis set K = 6). Writes figures/f6a_sameprec_rates.pdf and merges its entry into
figures/provenance.json (other entries untouched). The full two-panel F6 (incl. the overlap panel) stays in the appendix.

    /data/ziyangs/cloq_work/envs/cloq/bin/python paper/latex/tools/figs/make_fig_sameprec_a.py
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_figs as MF  # noqa: E402
from make_figs import B, COL_W, FS, INK2, LW_ZERO, QP, Line2D, plt, r1, style_axis  # noqa: E402

NAME = "f6a_sameprec_rates"
SRC_SAME = "analysis/fork/out/sameprec_20261004T070601Z.json"  # frozen analysis set (K = 6), cited by the caption


def script_sha():
    return hashlib.sha256(open(os.path.abspath(__file__), "rb").read()).hexdigest()


def f6a():
    MF.SRC["same"] = SRC_SAME
    MF.script_sha = script_sha
    sp = MF.load("same")
    assert sp["analysis_set"]["K"] == 6 and sp["analysis_set"]["blocks"] == ["f01", "f02", "f03", "f04", "f05", "f06"]
    pr, sa = sp["pooled"]["prec"], sp["pooled"]["same"]
    mets = [("rescue", "$r$"), ("damage", "$d$"), ("M", "$M$"), ("G", r"$G_{\mathrm{all}}$"),
            ("cond_offdiag", "off-diag.")]
    # values quoted in the text (pooled q4+q8, K = 6); identical to the asserts of make_figs.f6
    assert [r1(pr[k]["est"]) for k, _ in mets] == [8.0, 8.7, 16.8, -0.7, 25.0]
    assert [r1(sa[k]["est"]) for k, _ in mets] == [9.3, 8.4, 17.7, 0.9, 26.2]
    assert [r1(v) for v in sa["rescue"]["ci95"]] == [7.0, 11.7] and [r1(v) for v in sa["damage"]["ci95"]] == [6.4, 10.5]
    for k in ("rescue", "damage", "cond_offdiag"):  # A1.3: every same-precision 95% lower bound > 0
        assert sa[k]["ci95"][0] > 0 and sa[k]["crossed_ci95"][0] > 0

    fig, a = plt.subplots(1, 1, figsize=(COL_W, 1.70), layout="constrained")
    style_axis(a)
    for i, (k, _) in enumerate(mets):
        for d, (src, col, mk) in enumerate([(pr, B, "o"), (sa, QP, "s")]):
            MF.interval(a, i + (d - 0.5) * 0.32, src[k]["est"], src[k]["ci95"], src[k]["crossed_ci95"], col, marker=mk)
    a.axhline(0, color=INK2, lw=LW_ZERO, zorder=1)
    a.set_xticks(range(len(mets)))
    a.set_xticklabels([m[1] for m in mets])
    a.tick_params(axis="x", length=0)
    a.set_ylabel("pp of units (off-diag.: %)")
    a.legend(handles=[Line2D([], [], color=B, marker="o", lw=0, ms=3.6, label="B's action"),
                      Line2D([], [], color=QP, marker="s", lw=0, ms=3.6, label="second W4 checkpoint's action")],
             loc="upper left", frameon=False, fontsize=FS, handletextpad=0.2, borderaxespad=0.1)
    a.set_ylim(-7, 36)
    a.set_title("(a) divergent states, W4: replacement source", pad=2, fontsize=FS)
    MF.save(fig, NAME, ["same"],
            "re-plot of F6 panel (a) at column width: r/d/M/G_all/off-diag, B vs second W4 checkpoint as replacement (W4, K = 6)")
    pj = os.path.join(MF.OUT, "provenance.json")
    old = json.load(open(pj))
    for kk, v in MF.PROV.items():
        v["script"] = "paper/latex/tools/figs/make_fig_sameprec_a.py"
        v["script_sha256"] = script_sha()
        old[kk] = v
    json.dump(old, open(pj, "w"), indent=1, sort_keys=True)
    print("asserts passed")


if __name__ == "__main__":
    f6a()
