"""W96 (GPT-6.1 review 7, decision 1): multiplicity for the four core W4 G-H contrasts (q4/q8 x GPTQ-W4 d1/AWQ-W4) of
the W93 G/H/F analysis. Exploratory family of 4; Holm step-down on two-sided p-values from the t-over-blocks interval
(se = width / (2 t_{.975, n-1}); same estimate). Also Bonferroni 98.75% fixed-pool t intervals and the crossed intervals
(new tasks), copied from the source JSON. Fixed task pool throughout except the crossed column.
usage: python analysis/fork/ghf_multiplicity.py [analysis/fork/out/ghf_<UTC>.json] -> analysis/fork/out/ghf_multiplicity_<UTC>.md
"""
import json
import sys
import time
from pathlib import Path

from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "analysis/fork/out/ghf_20261001T211519Z.json"
d = json.load(open(src))
CELLS = ["q4:gptq_w4_d1", "q4:awq_w4", "q8:gptq_w4_d1", "q8:awq_w4"]
rows = []
for c in CELLS:
    s = d["cells"][c]["stats"]["GmH"]
    n = s["n_blocks"]
    lo, hi = s["t_ci95"]
    tq = stats.t.ppf(0.975, n - 1)
    se = (hi - lo) / (2 * tq)
    p = 2 * stats.t.sf(abs(s["est"]) / se, n - 1)
    tb = stats.t.ppf(1 - 0.05 / (2 * len(CELLS)), n - 1)
    rows.append({"cell": c, "est": s["est"], "boot_ci95": s["block_boot_ci95"], "t_ci95": s["t_ci95"], "n_blocks": n, "p": p,
                 "bonf_ci": [s["est"] - tb * se, s["est"] + tb * se], "crossed_ci95": s["crossed_ci95"]})
m = len(rows)
order = sorted(range(m), key=lambda i: rows[i]["p"])
run = 0.0
for k, i in enumerate(order):
    run = max(run, min(1.0, (m - k) * rows[i]["p"]))
    rows[i]["p_holm"] = run
utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
f = lambda v: f"{v:+.1f}"  # noqa: E731
L = [f"**TL;DR** Four core W4 G-H contrasts (fixed task pool, t over blocks), Holm-adjusted over the family of 4: "
     + "; ".join(f"{r['cell']} {f(r['est'])} pp, p_holm {r['p_holm']:.3f}" for r in rows)
     + ". Crossed (new-task) intervals cover 0 in all four. Exploratory label stays.", "",
     f"# G-H multiplicity (W96)", "", f"Source: `{src.relative_to(ROOT)}`; script `analysis/fork/ghf_multiplicity.py`.", "",
     "| cell | G-H (pp) | fixed-pool boot 95% | t 95% | p (t, 2-sided) | p Holm (m=4) | Bonferroni 98.75% (t) | crossed 95% |", "|---|---|---|---|---|---|---|---|"]
for r in rows:
    L.append(f"| {r['cell']} | {f(r['est'])} | [{f(r['boot_ci95'][0])}, {f(r['boot_ci95'][1])}] | [{f(r['t_ci95'][0])}, {f(r['t_ci95'][1])}] | "
             f"{r['p']:.4f} | {r['p_holm']:.4f} | [{f(r['bonf_ci'][0])}, {f(r['bonf_ci'][1])}] | [{f(r['crossed_ci95'][0])}, {f(r['crossed_ci95'][1])}] |")
out = ROOT / f"analysis/fork/out/ghf_multiplicity_{utc}.md"
out.write_text("\n".join(L) + "\n")
json.dump({"source": str(src.relative_to(ROOT)), "rows": rows}, open(out.with_suffix(".json"), "w"), indent=1)
print("\n".join(L)); print(out)
