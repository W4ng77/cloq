#!/usr/bin/env python3
"""Publication figures for the CLOQ paper (W99j). One function per figure.

Reads ONLY committed analysis outputs under analysis/fork/out/ (the JSON next to each .md), asserts every number
the paper text quotes for that figure, and writes vector PDFs to paper/latex/figures/.

    /data/ziyangs/cloq_work/envs/cloq/bin/python paper/latex/tools/figs/make_figs.py [f1 f2 ...]

Provenance: each PDF carries its source JSON paths, their sha256 and this script's sha256 in the PDF metadata
(Subject / Keywords), and figures/provenance.json lists the same. No number in a figure is typed by hand;
derived quantities (e.g. pp = count / 1020 * 100) are computed here from JSON fields and named in the caption.

Palette (dataviz reference instance, validated with validate_palette.js --mode light, 3 slots, all checks pass):
blue #2a78d6, orange #eb6834, aqua #1baf7a; marks also differ by shape/fill so the figures read in greyscale.
"""
import hashlib
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "figures"))
SRC = {
    "ghf": "analysis/fork/out/ghf_20261001T211519Z.json",
    "agree": "analysis/fork/out/agreement_control_20261002T024240Z.json",
    "ext": "analysis/fork/out/ext_r2_20261002T024433Z.json",
    "hr2": "analysis/fork/out/holdout_r2_posthoc_20261002T024414Z.json",
    "hconf": "analysis/fork/out/holdout_confirm_20261002T012353Z.json",
    "simp": "analysis/fork/out/simctrl_p_20261002T015200Z.json",
    "oracle": "analysis/fork/out/oracle_trigger_20261002T024423Z.json",
    "tok": "analysis/fork/out/token_mech_20261002T003130Z.json",
    "dev": "analysis/fork/out/dev_all_20261001T070326Z.json",
}
_cache = {}

# ACL review format, measured with tectonic: \textwidth 455.24pt = 6.30in, \columnwidth 219.09pt = 3.03in.
# Figures are drawn at exactly these widths and included at scale 1, so the font sizes below are print sizes.
FULL_W, COL_W = 455.24 / 72.27, 219.09 / 72.27
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED, GRID, BAND = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#f1f0ec"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Liberation Serif", "Nimbus Roman", "Times New Roman", "Times", "STIXGeneral"],
    "mathtext.fontset": "stix",
    "font.size": 7.5,
    "axes.labelsize": 7.5,
    "axes.titlesize": 7.5,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "figure.constrained_layout.h_pad": 0.01,
    "figure.constrained_layout.w_pad": 0.01,
    "axes.linewidth": 0.5,
    "axes.edgecolor": INK2,
    "axes.labelcolor": INK,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
    "xtick.major.size": 2,
    "ytick.major.size": 2,
    "pdf.fonttype": 42,
    "savefig.dpi": 300,
})

CELL4 = [("q4:gptq_w4_d1", "q4 GPTQ-W4"), ("q4:awq_w4", "q4 AWQ-W4"),
         ("q8:gptq_w4_d1", "q8 GPTQ-W4"), ("q8:awq_w4", "q8 AWQ-W4")]
KV8 = [("q4:kvq_int8", "q4 KV8"), ("q8:kvq_int8", "q8 KV8")]


def load(key):
    if key not in _cache:
        p = os.path.join(ROOT, SRC[key])
        raw = open(p, "rb").read()
        _cache[key] = (json.loads(raw), hashlib.sha256(raw).hexdigest())
    return _cache[key][0]


def r1(x):
    return round(x + 0.0, 1)


def near(a, b, tol=0.051):
    assert abs(a - b) <= tol, (a, b)


def script_sha():
    return hashlib.sha256(open(os.path.abspath(__file__), "rb").read()).hexdigest()


PROV = {}


def save(fig, name, keys, what):
    os.makedirs(OUT, exist_ok=True)
    srcs = [SRC[k] for k in keys]
    shas = {SRC[k]: _cache[k][1] for k in keys}
    meta = {
        "Title": name,
        "Author": "CLOQ paper figures (paper/latex/tools/figs/make_figs.py)",
        "Subject": "Source: " + "; ".join(srcs),
        "Keywords": "script_sha256=" + script_sha() + "; " + "; ".join(f"{s}={h}" for s, h in shas.items()),
        "Creator": "paper/latex/tools/figs/make_figs.py",
    }
    path = os.path.join(OUT, name + ".pdf")
    w = fig.get_size_inches()[0]
    fig.savefig(path, metadata=meta)
    assert abs(w - FULL_W) < 1e-6 or abs(w - COL_W) < 1e-6, w
    plt.close(fig)
    PROV[name] = {"pdf": os.path.relpath(path, ROOT), "shows": what, "sources": shas,
                  "script": "paper/latex/tools/figs/make_figs.py"}
    print("wrote", os.path.relpath(path, ROOT))


def style_axis(ax, grid_axis="y"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis=grid_axis, color=GRID, lw=0.4, ls="-", zorder=0)
    ax.set_axisbelow(True)


def interval(ax, pos, est, thick, thin, color, marker="o", ms=3.6, horizontal=False, mfc=None, z=3):
    """Point estimate with a thick (fixed-pool) and a thin (new-task) interval."""
    mfc = color if mfc is None else mfc
    if horizontal:
        if thin is not None:
            ax.plot(thin, [pos, pos], color=color, lw=0.6, solid_capstyle="butt", zorder=z)
        if thick is not None:
            ax.plot(thick, [pos, pos], color=color, lw=1.8, solid_capstyle="butt", zorder=z)
        ax.plot([est], [pos], marker=marker, ms=ms, color=color, mfc=mfc, mec=color if mfc != "white" else color,
                mew=0.8, zorder=z + 1, ls="none")
    else:
        if thin is not None:
            ax.plot([pos, pos], thin, color=color, lw=0.6, solid_capstyle="butt", zorder=z)
        if thick is not None:
            ax.plot([pos, pos], thick, color=color, lw=1.8, solid_capstyle="butt", zorder=z)
        ax.plot([pos], [est], marker=marker, ms=ms, color=color, mfc=mfc, mew=0.8, zorder=z + 1, ls="none")


# ---------------------------------------------------------------------------------------------------------------
# F1: per-cell controller dependence (observed off-diagonal share vs pairing agreement control) across environments
# ---------------------------------------------------------------------------------------------------------------
def f1():
    ghf, ag, ext, hr2 = load("ghf"), load("agree"), load("ext"), load("hr2")
    groups = []  # (title, posthoc, rows); row = (label, est, thick, thin, control, is_pool)

    def dev_rows(cells, pool_key):
        rows = []
        for k, lab in cells:
            st = ghf["cells"][k]["stats"]["offdiag"]
            a = ag["cells"][k]["stats"]
            near(a["observed_offdiag"]["est"], st["est"], 0.001)
            rows.append((lab, st["est"], st["ci95"], st["crossed_ci95"], a["expected_offdiag"]["est"], False))
        p = ag["pools"][pool_key]["equal_weight"]
        po = ghf["pools"][pool_key]["stats"]["offdiag"]
        near(p["observed_offdiag"]["est"], po["est"], 0.001)
        rows.append(("pool", po["est"], po["ci95"], po["crossed_ci95"], p["expected_offdiag"]["est"], True))
        return rows

    w4 = dev_rows(CELL4, "W4:all")
    kv = dev_rows(KV8, "KV8:all")
    # Asserts: numbers the text quotes (intro, R2, Fig. 3x3 caption, app. agreement table)
    assert r1(w4[-1][1]) == 26.9 and [r1(v) for v in w4[-1][2]] == [25.7, 28.1]
    assert r1(w4[-1][4]) == 38.0
    near(ag["pools"]["W4:all"]["equal_weight"]["kappa"]["est"], 0.29, 0.0051)
    assert [r1(v) for v in ag["pools"]["W4:all"]["equal_weight"]["expected_offdiag"]["ci95"]] == [36.7, 39.0]
    assert sorted(r1(r[1]) for r in w4[:4]) == [22.9, 25.0, 29.3, 30.5]
    assert r1(kv[-1][1]) == 15.3 and r1(kv[-1][4]) == 33.6
    near(ag["pools"]["KV8:all"]["equal_weight"]["kappa"]["est"], 0.55, 0.0051)
    groups.append((r"$\tau^2$-bench W4", "development", w4))
    groups.append((r"$\tau^2$-bench KV8", "development", kv))

    def ext_rows(env, cells):
        rows = []
        for k, lab in cells:
            c = ext["cells"][f"{env}:{k}"]
            assert c["family"] == "W4"
            st = c["pp_on_divergent"]["offdiag"]
            ctl = c["table3"]["marginal_preserving_pairing_agreement_control"]
            near(ctl["observed_offdiag_share"] * 100, st["est"], 0.001)
            rows.append((lab, st["est"], None, st["ci95"], ctl["expected_offdiag_share_independent"] * 100, False))
        po = ext["pooled"][f"W4:{env}:pooled_equal_weight"]["pp_on_divergent"]["offdiag"]
        rows.append(("pool", po["est"], None, po["ci95"], None, True))  # no pooled control in the source
        return rows

    bf = ext_rows("bfcl", [("q4:gptq_w4_d1", "q4 GPTQ-W4"), ("q4:awq_w4_d1", "q4 AWQ-W4"),
                           ("q8:gptq_w4_d1", "q8 GPTQ-W4"), ("q8:awq_w4_d1", "q8 AWQ-W4")])
    af = ext_rows("alfworld", [("q8:gptq_w4_d1", "q8 GPTQ-W4"), ("q8:awq_w4_d1", "q8 AWQ-W4")])
    assert sorted(r1(r[1]) for r in bf[:4]) == [4.7, 7.8, 11.7, 17.1] and r1(bf[-1][1]) == 10.3
    assert sorted(r1(r[4]) for r in bf[:4]) == [16.2, 19.9, 27.4, 32.4]
    assert sorted(r1(r[1]) for r in af[:2]) == [32.8, 40.0] and r1(af[-1][1]) == 36.4
    assert sorted(r1(r[4]) for r in af[:2]) == [42.9, 46.4]
    groups.append(("BFCL W4", "post hoc", bf))
    groups.append(("ALFWorld W4", "post hoc", af))

    ho = []
    for k, lab in [("q4:gptq_w4_d1", "q4 GPTQ-W4"), ("q8:gptq_w4_d1", "q8 GPTQ-W4"), ("q8:awq_w4", "q8 AWQ-W4")]:
        c = hr2["cells"][k]
        st = c["stats"]["offdiag"]
        ctl = c["table3"]["marginal_preserving_pairing_agreement_control"]
        ho.append((lab, st["est_pp"], st["block_t"]["ci95_pp"], st["crossed"]["ci95_pp"],
                   ctl["expected_offdiag_share_independent"] * 100, False))
    p = hr2["pool_prereg_weighted"]
    ho.append(("pool", p["stats"]["offdiag"]["est_pp"], p["stats"]["offdiag"]["block_t"]["ci95_pp"],
               p["stats"]["offdiag"]["crossed"]["ci95_pp"],
               p["marginal_preserving_pairing_agreement_control"]["expected_offdiag_share_independent"] * 100, True))
    assert r1(ho[-1][1]) == 20.7 and r1(ho[-1][4]) == 25.7
    assert [r1(r[1]) for r in ho[:3]] == [19.7, 19.5, 23.7] and [r1(r[4]) for r in ho[:3]] == [27.0, 23.1, 26.0]
    groups.append(("Telecom holdout W4", "post hoc", ho))

    fig, ax = plt.subplots(figsize=(COL_W, 2.5), layout="constrained")
    style_axis(ax, grid_axis="x")
    y, ticks, labels, spans, gap = 0.0, [], [], [], 0.35
    for title, kind, rows in groups:
        y -= 0.95  # header row
        y0 = y
        for lab, est, thick, thin, ctl, is_pool in rows:
            col = INK if is_pool else BLUE
            if ctl is not None:
                ax.plot([ctl], [y], marker="D", ms=3.4, mfc="white", mec=ORANGE, mew=1.0, ls="none", zorder=5)
            interval(ax, y, est, thick, thin, col, marker="s" if is_pool else "o", ms=3.6 if is_pool else 3.4,
                     horizontal=True)
            ticks.append(y)
            labels.append(lab)
            y -= 1
        spans.append((y0 + 0.5, y + 0.5, title, kind))
        y -= gap
    xmax = 50
    for top, bot, title, kind in spans:
        if kind == "post hoc":
            ax.axhspan(bot - 0.15, top + 1.05, color=BAND, zorder=0, lw=0)
        t = ax.text(0.6, top + 0.5, title, ha="left", va="center", fontsize=7, color=INK, fontweight="bold")
        ax.annotate(" development" if kind == "development" else " post hoc", xycoords=t, xy=(1, 0.5),
                    va="center", ha="left", fontsize=7, color=INK2, style="italic")
    ax.set_yticks(ticks)
    ax.set_yticklabels(labels)
    for t, lab in zip(ax.get_yticklabels(), labels):
        if lab == "pool":
            t.set_fontweight("bold")
    ax.tick_params(axis="y", length=0, pad=2)
    ax.set_ylim(y + gap + 0.35, spans[0][0] + 1.1)
    ax.set_xlim(0, xmax)
    ax.set_xticks(range(0, 51, 10))
    ax.set_xlabel(r"off-diagonal share ($\Delta_{\mathrm{Q}}\neq\Delta_{\mathrm{B}}$), % of divergent states", labelpad=1)
    handles = [
        Line2D([], [], color=BLUE, marker="o", ms=3.4, lw=1.8, label="cell"),
        Line2D([], [], color=INK, marker="s", ms=3.6, lw=1.8, label="pool"),
        Line2D([], [], color=ORANGE, marker="D", ms=3.4, mfc="white", mew=1.0, lw=0,
               label="pairing control"),
    ]
    # legend in the empty right part of the BFCL group (x > 34%, no marks there)
    bf_top, bf_bot = spans[2][0], spans[2][1]
    leg = ax.legend(handles=handles, loc="upper right", bbox_to_anchor=(xmax - 0.3, bf_top - 1.9), borderaxespad=0,
                    bbox_transform=ax.transData, frameon=True, framealpha=1.0, edgecolor=BAND, facecolor="white",
                    handletextpad=0.4, fontsize=7, handlelength=1.4, borderpad=0.3, labelspacing=0.25)
    leg.get_frame().set_linewidth(0.4)
    save(fig, "f1_controller_dependence", ["ghf", "agree", "ext", "hr2"],
         "per-cell off-diagonal share with intervals vs marginal-preserving pairing agreement control, by environment")


# ---------------------------------------------------------------------------------------------------------------
# F2: G, H, F, G-H forest plot per core cell (fixed-pool 95% thick, crossed new-task 95% thin)
# ---------------------------------------------------------------------------------------------------------------
def f2():
    ghf = load("ghf")
    rows = []
    for k, lab in CELL4:
        rows.append((lab, ghf["cells"][k]["stats"], BLUE, "o"))
    rows.append(("W4 pool", ghf["pools"]["W4:all"]["stats"], INK, "s"))
    for k, lab in KV8:
        rows.append((lab, ghf["cells"][k]["stats"], ORANGE, "^"))
    rows.append(("KV8 pool", ghf["pools"]["KV8:all"]["stats"], INK, "s"))
    S = {lab: st for lab, st, _, _ in rows}

    def chk(lab, key, est, ci):
        s = S[lab][key]
        assert r1(s["est"]) == est, (lab, key, s["est"])
        if ci is not None:
            assert [r1(v) for v in s["ci95"]] == ci, (lab, key, s["ci95"])

    # Asserts: numbers quoted in R2 text / Table tab:ghf
    chk("W4 pool", "G", 0.5, [-0.7, 1.7]); chk("W4 pool", "H", 0.2, [-1.3, 1.6]); chk("W4 pool", "F", 0.7, [-0.6, 2.1])
    chk("W4 pool", "GmH", 0.4, [-0.8, 1.7])
    chk("q8 GPTQ-W4", "G", 3.3, [1.6, 5.0]); chk("q8 GPTQ-W4", "H", 0.4, None); chk("q8 GPTQ-W4", "F", 5.4, None)
    chk("q8 GPTQ-W4", "GmH", 2.9, [1.3, 4.7]); chk("q8 AWQ-W4", "GmH", 3.4, [1.5, 5.2])
    chk("q4 GPTQ-W4", "G", -2.9, [-5.7, -0.2]); chk("q4 GPTQ-W4", "GmH", -3.6, [-6.6, -0.6])
    chk("q4 KV8", "H", -2.5, [-4.5, -0.5])
    # new-task intervals of all four W4 cells cover zero for G-H (text, R2)
    for lab, _ in [(c[1], 0) for c in CELL4]:
        lo, hi = S[lab]["GmH"]["crossed_ci95"]
        assert lo < 0 < hi, lab

    panels = [("G", r"$G$ (this step only), pp"), ("H", r"$H$ (from the next step), pp"),
              ("F", r"$F$ (from here on), pp"), ("GmH", r"$G-H$, pp")]
    allv = [v for _, st, _, _ in rows for k, _ in panels for v in st[k]["crossed_ci95"]]
    lo, hi = min(allv), max(allv)
    lim = (min(-8.0, lo - 0.5), max(8.0, hi + 0.5))
    fig, axs = plt.subplots(1, 4, figsize=(FULL_W, 1.3), sharey=True, layout="constrained")
    ypos = []
    y = 0.0
    for i, (lab, _, _, _) in enumerate(rows):
        ypos.append(y)
        y -= 1.0
        if lab == "W4 pool":
            y -= 0.5
    for ax, (key, title) in zip(axs, panels):
        style_axis(ax, grid_axis="x")
        ax.axvline(0, color=INK2, lw=0.6, zorder=1)
        for (lab, st, col, mk), yy in zip(rows, ypos):
            s = st[key]
            interval(ax, yy, s["est"], s["ci95"], s["crossed_ci95"], col, marker=mk, horizontal=True,
                     ms=3.6 if mk == "s" else 3.4)
        ax.set_title(title, pad=3)
        ax.set_xlim(*lim)
        ax.set_xticks([t for t in (-10, -5, 0, 5, 10) if lim[0] <= t <= lim[1]])
        ax.tick_params(axis="y", length=0)
        if ax is not axs[0]:
            ax.spines["left"].set_visible(False)
    axs[0].set_yticks(ypos)
    axs[0].set_yticklabels([r[0] for r in rows])
    axs[0].set_ylim(ypos[-1] - 0.6, ypos[0] + 0.6)
    for t, (lab, _, _, _) in zip(axs[0].get_yticklabels(), rows):
        if "pool" in lab:
            t.set_fontweight("bold")
    # no legend: row labels name W4/KV8/pool; thick = fixed-pool 95%, thin = new-task 95% (stated in caption)
    save(fig, "f2_ghf_forest", ["ghf"], "G, H, F, G-H per core cell and pool, fixed-pool and crossed intervals")


# ---------------------------------------------------------------------------------------------------------------
# F3: redistribution - rescue vs damage per cell (dev W4/KV8 + holdout) and the small net G_all
# ---------------------------------------------------------------------------------------------------------------
def f3():
    dev, hc = load("dev"), load("hconf")
    rows = []  # (label, r, d, net, thick, thin, group)
    for k, lab in CELL4 + KV8:
        a = dev["cells"][k]["all_pp"]
        rows.append((lab, a["rescue"]["est"], a["damage"]["est"], a["G"]["est"], a["G"]["ci95"],
                     a["G"]["crossed_ci95"], "dev"))
        if k == "q8:awq_w4":
            p = dev["pooled"]["W4:all:pooled_equal_weight"]
            rows.append(("W4 pool", p["rescue"]["est"], p["damage"]["est"], p["G"]["est"], p["G"]["ci95"],
                         p["G"]["crossed_ci95"], "devpool"))
    # Asserts: Table r1 / R1 text
    w4 = [r for r in rows if r[6] == "dev"][:4]
    assert [r1(r[1]) for r in w4] == [6.8, 9.8, 10.4, 11.4] and [r1(r[2]) for r in w4] == [8.7, 10.1, 7.5, 9.5]
    assert [r1(dev["cells"][k]["all_pp"]["M"]["est"]) for k, _ in CELL4] == [15.5, 19.9, 17.9, 20.9]
    assert [r1(r[3]) for r in w4] == [-1.9, -0.3, 2.9, 1.9]
    pool = [r for r in rows if r[6] == "devpool"][0]
    assert (r1(pool[1]), r1(pool[2]), r1(pool[3])) == (9.6, 9.0, 0.7) and [r1(v) for v in pool[4]] == [-0.3, 1.6]
    assert r1(dev["pooled"]["W4:all:pooled_equal_weight"]["M"]["est"]) == 18.6
    kv = [r for r in rows if r[6] == "dev"][4:]
    assert [(r1(r[1]), r1(r[2]), r1(r[3])) for r in kv] == [(3.1, 3.4, -0.3), (4.3, 3.7, 0.6)]

    for k, lab in [("q4:gptq_w4_d1", "q4 GPTQ-W4"), ("q8:gptq_w4_d1", "q8 GPTQ-W4"), ("q8:awq_w4", "q8 AWQ-W4")]:
        c = hc["per_cell_descriptive"][k]
        rows.append((lab, c["rescue"]["crossed"]["est"], c["damage"]["crossed"]["est"], c["G"]["crossed"]["est"],
                     c["G"]["block_t"]["ci90"], c["G"]["crossed"]["ci90"], "ho"))
    pg, s1 = hc["primary_G_all"], hc["S1_two_sided_consequences"]
    rows.append(("weighted", s1["rescue"]["crossed_decisional"]["est"], s1["damage"]["crossed_decisional"]["est"],
                 pg["crossed_decisional"]["est"], pg["block_t_alongside"]["ci90"], pg["crossed_decisional"]["ci90"],
                 "hopool"))
    assert round(pg["crossed_decisional"]["est"], 2) == -4.57
    assert [round(v, 2) for v in pg["crossed_decisional"]["ci90"]] == [-7.17, -1.96]
    assert [round(v, 2) for v in pg["block_t_alongside"]["ci90"]] == [-6.08, -3.05]
    assert round(s1["rescue"]["crossed_decisional"]["est"], 2) == 5.21
    assert round(s1["damage"]["crossed_decisional"]["est"], 2) == 9.77
    assert [round(r[3], 2) for r in rows if r[6] == "ho"] == [-3.03, -5.64, -6.57]
    assert [round(r[1], 2) for r in rows if r[6] == "ho"] == [5.05, 4.41, 6.31]
    assert [round(r[2], 2) for r in rows if r[6] == "ho"] == [8.08, 10.05, 12.88]

    fig, ax = plt.subplots(figsize=(COL_W, 1.72), layout="constrained")
    style_axis(ax, grid_axis="x")
    ypos, y, prev = [], 0.0, None
    for r in rows:
        if prev is not None and r[6] == "ho" and prev != "ho":
            y -= 0.9
        if prev == "devpool":
            y -= 0.35
        ypos.append(y)
        y -= 1.0
        prev = r[6]
    h = 0.62
    for r, yy in zip(rows, ypos):
        lab, rr, dd, net, thick, thin, g = r
        ax.barh(yy, rr, height=h, color=BLUE, alpha=0.85, lw=0, zorder=2)
        ax.barh(yy, -dd, height=h, color=ORANGE, alpha=0.85, lw=0, zorder=2)
        interval(ax, yy, net, thick, thin, INK, marker="D", ms=3.2, horizontal=True, z=4)
    ax.axvline(0, color=INK2, lw=0.6, zorder=3)
    ax.set_yticks(ypos)
    ax.set_yticklabels([r[0] for r in rows])
    for t, r in zip(ax.get_yticklabels(), rows):
        if r[6] in ("devpool", "hopool"):
            t.set_fontweight("bold")
    ax.tick_params(axis="y", length=0)
    ax.set_ylim(ypos[-1] - 0.6, ypos[0] + 0.6)
    ax.set_xlim(-14, 14)
    ax.set_xticks([-12, -8, -4, 0, 4, 8, 12])
    ax.set_xticklabels(["12", "8", "4", "0", "4", "8", "12"])
    ax.set_xlabel("% of units (net: pp)")
    ax.text(-13.6, ypos[0] + 0.9, r"$\leftarrow$ damage $d$", ha="left", va="bottom", fontsize=7, color=INK)
    ax.text(13.6, ypos[0] + 0.9, r"rescue $r$ $\rightarrow$", ha="right", va="bottom", fontsize=7, color=INK)
    iho = [i for i, r in enumerate(rows) if r[6] == "ho"][0]
    ax.text(13.6, ypos[iho] + 0.62, "telecom holdout (pre-reg., 90%)", ha="right", va="bottom", fontsize=7,
            color=INK2, style="italic")
    ax.text(13.6, ypos[0] + 0.0, r"$\tau^2$ dev", ha="right", va="center", fontsize=7, color=INK2, style="italic")
    # no legend: bars are labelled at the top (damage d / rescue r); the diamond is net G_all (caption)
    save(fig, "f3_rescue_damage", ["dev", "hconf"], "rescue and damage rates per cell with net G_all and intervals")


# ---------------------------------------------------------------------------------------------------------------
# F4: frozen trigger vs matched oracle vs random by budget, KL reference faint
# ---------------------------------------------------------------------------------------------------------------
def f4():
    o, tok = load("oracle"), load("tok")
    budgets = ["0.05", "0.1", "0.2"]
    xs = [5, 10, 20]
    fr = [o["frozen"][b]["pooled"] for b in budgets]
    orc = [o["action_oracle"][b]["pooled"] for b in budgets]
    # KL reference: KLu_max ranked within the frozen rule's exact per-cell counts (count-matched; post hoc)
    kl = [o["kl"]["val_count_matched_to_frozen"][b]["pooled"] for b in budgets]
    N = fr[0]["N"]
    assert N == 1020 and fr[0]["turnover_total"] == 69 and fr[0]["R"] == 38 and fr[0]["D"] == 31
    assert o["checks"]["w98_primary_reproduced"] is True
    # cross-check the frozen rule against token_mech validation (primary S_mm U1)
    vk = [k for k in tok["validation"] if k.startswith("U1") and "S_mm" in k and "PRIMARY" in k.upper()]
    for b, x in zip(budgets, xs):
        m = [k for k in vk if k.rstrip().endswith(f"{x}%")]
        assert len(m) == 1, (x, vk)
        tv = tok["validation"][m[0]]["pooled"]
        fb = o["frozen"][b]["pooled"]
        assert (tv["n_escalated"], tv["net_gain"], tv["turnover_captured"]) == \
               (fb["n_escalated"], fb["net_gain"], fb["turnover_captured"])
    assert [f["n_escalated"] for f in fr] == [50, 114, 222]
    assert [f["net_gain"] for f in fr] == [4, 2, 5]
    assert [round(f["random_expected_net"], 2) for f in fr] == [0.21, 0.98, 2.38]
    assert [f["turnover_captured"] for f in fr] == [8, 12, 27]
    assert [round(f["random_expected_turnover"], 2) for f in fr] == [3.48, 7.52, 14.3]
    assert [p["oracle_net_pp"] for p in orc] == [3.33, 3.73, 3.73]
    assert [k["n_escalated"] for k in kl] == [50, 114, 222]
    assert [k["net_gain"] for k in kl] == [1, 1, 6] and [k["turnover_captured"] for k in kl] == [7, 15, 32]
    vv = o["kl"]["val_f02f03"]["KLu_max"]  # own-count row of Table tab:oracle (not plotted; asserted)
    assert [vv[b]["pooled"]["turnover_captured"] for b in budgets] == [11, 15, 33]

    pp = lambda v: 100.0 * v / N  # noqa: E731  derived: pp = count / 1020 * 100
    net_fr = [pp(f["net_gain"]) for f in fr]
    net_rd = [pp(f["random_expected_net"]) for f in fr]
    net_or = [pp(p["net"]) for p in orc]
    net_kl = [pp(k["net_gain"]) for k in kl]
    assert [round(v, 2) for v in net_fr] == [0.39, 0.2, 0.49] and [round(v, 2) for v in net_or] == [3.33, 3.73, 3.73]
    # turnover ceiling at the frozen rule's per-cell counts: sum_c min(m_c, R_c + D_c) (derived from JSON fields)
    ceil_t = [sum(min(c["n_escalated"], c["R"] + c["D"]) for c in o["frozen"][b]["per_cell"].values())
              for b in budgets]
    tv = lambda v: 100.0 * v / 69  # noqa: E731  derived: % of the 69 turnover states
    fig, axs = plt.subplots(1, 2, figsize=(COL_W, 1.95), layout="constrained")
    a, b2 = axs
    for ax in axs:
        style_axis(ax)
        ax.set_xticks(xs)
        ax.set_xticklabels(["5", "10", "20"])
        ax.set_xlim(3, 22)
        ax.set_xlabel("escalation budget (%)")
    kw = dict(lw=1.2, ms=3.4)
    a.plot(xs, net_or, color=INK, marker="^", label="matched oracle", **kw)
    a.plot(xs, net_fr, color=BLUE, marker="o", label="frozen Q-only trigger", **kw)
    a.plot(xs, net_rd, color=MUTED, marker="s", mfc="white", label="random (expected)", **kw)
    a.plot(xs, net_kl, color=AQUA, marker="x", lw=0.8, ms=3.4, alpha=0.6, label="KL ref. (post hoc)")
    a.axhline(0, color=INK2, lw=0.5, zorder=1)
    a.set_ylim(-0.3, 4.2)
    a.set_ylabel("net gain (pp)")
    a.set_title("(a) net gain", pad=2)
    b2.plot(xs, [tv(v) for v in ceil_t], color=INK, marker="^", **kw)
    b2.plot(xs, [tv(f["turnover_captured"]) for f in fr], color=BLUE, marker="o", **kw)
    b2.plot(xs, [tv(f["random_expected_turnover"]) for f in fr], color=MUTED, marker="s", mfc="white", **kw)
    b2.plot(xs, [tv(k["turnover_captured"]) for k in kl], color=AQUA, marker="x", lw=0.8, ms=3.4, alpha=0.6)
    b2.set_ylim(0, 105)
    b2.set_ylabel("turnover captured (% of 69)")
    b2.set_title("(b) turnover captured", pad=2)
    fig.legend(loc="outside lower center", ncol=2, frameon=False, fontsize=7,
               handletextpad=0.4, columnspacing=1.0)
    PROV_EXTRA["f4_turnover_ceiling"] = ceil_t
    save(fig, "f4_trigger_oracle", ["oracle", "tok"],
         "net gain and turnover captured by budget: frozen trigger, matched oracle/ceiling, random, KL reference")


# ---------------------------------------------------------------------------------------------------------------
# F5 (appendix): SIMCTRL-P original vs Sonnet simulator, G/H/F/G-H, per cell and pool
# ---------------------------------------------------------------------------------------------------------------
def f5():
    s = load("simp")
    sc = s["scopes"][s["primary_scope"]]
    assert sc["n_states"] == 80
    E = sc["estimands"]
    p = lambda k, arm: E[k][arm]["pool"]  # noqa: E731
    assert (p("G", "sonnet")["est"], [round(v, 1) for v in p("G", "sonnet")["ci95_states"]]) == (-3.0, [-10.2, 4.8])
    assert (p("H", "sonnet")["est"], [round(v, 1) for v in p("H", "sonnet")["ci95_states"]]) == (5.5, [-0.0, 11.2])
    assert (p("GmH", "sonnet")["est"], [round(v, 1) for v in p("GmH", "sonnet")["ci95_states"]]) == \
           (-8.5, [-14.8, -2.8])
    assert (p("GmH", "original")["est"], [round(v, 1) for v in p("GmH", "original")["ci95_states"]]) == \
           (-2.5, [-11.2, 6.2])
    assert E["GmH"]["original"]["q8:gptq_w4_d1"]["est"] == 0.0 and E["GmH"]["original"]["q8:awq_w4"]["est"] == 0.0
    cells = [k for k, _ in CELL4] + ["pool"]
    labs = [l for _, l in CELL4] + ["pool"]
    panels = [("G", r"$G$"), ("H", r"$H$"), ("F", r"$F$"), ("GmH", r"$G-H$")]
    fig, axs = plt.subplots(1, 4, figsize=(FULL_W, 1.75), sharey=True, layout="constrained")
    ypos = [0, -1, -2, -3, -4.4]
    for ax, (k, title) in zip(axs, panels):
        style_axis(ax, grid_axis="x")
        ax.axvline(0, color=INK2, lw=0.6, zorder=1)
        for c, yy in zip(cells, ypos):
            o, so = E[k]["original"][c], E[k]["sonnet"][c]
            interval(ax, yy + 0.17, o["est"], None, o["ci95_states"], MUTED, marker="o", mfc="white", horizontal=True)
            interval(ax, yy - 0.17, so["est"], so["ci95_states"], None, BLUE, marker="s" if c == "pool" else "o",
                     horizontal=True)
        ax.set_title(title, pad=3)
        ax.set_xlim(-50, 50)
        ax.set_xticks([-40, -20, 0, 20, 40])
        ax.tick_params(axis="y", length=0)
        ax.set_xlabel("pp", labelpad=1)
        if ax is not axs[0]:
            ax.spines["left"].set_visible(False)
    axs[0].set_yticks(ypos)
    axs[0].set_yticklabels(labs)
    axs[0].get_yticklabels()[-1].set_fontweight("bold")
    axs[0].set_ylim(-5.0, 0.6)
    handles = [Line2D([], [], color=MUTED, marker="o", mfc="white", ms=3.4, lw=0.6,
                      label="original simulator (single run)"),
               Line2D([], [], color=BLUE, marker="o", ms=3.4, lw=1.8, label="Sonnet 5.5 user (5 replicates)")]
    fig.legend(handles=handles, loc="outside lower center", ncol=2, frameon=False,
               fontsize=7)
    save(fig, "f5_simctrl_p", ["simp"], "SIMCTRL-P G/H/F/G-H, original vs Sonnet user simulator, 95% over states")


PROV_EXTRA = {}
FIGS = {"f1": f1, "f2": f2, "f3": f3, "f4": f4, "f5": f5}

if __name__ == "__main__":
    want = sys.argv[1:] or list(FIGS)
    for w in want:
        FIGS[w]()
    pj = os.path.join(OUT, "provenance.json")
    old = json.load(open(pj)) if os.path.exists(pj) else {}
    old.update(PROV)
    old["_script_sha256"] = script_sha()
    if PROV_EXTRA:
        old.setdefault("_derived", {}).update(PROV_EXTRA)
    json.dump(old, open(pj, "w"), indent=1, sort_keys=True)
    print("asserts passed; provenance ->", os.path.relpath(pj, ROOT))
