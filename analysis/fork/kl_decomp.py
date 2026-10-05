"""EXPLORATORY, POST HOC (reviewer ruling 2026-10-04 evening): what local fidelity (mean token KL) predicts on the q8 new-method Panel A.
States: the common q8 U2B Panel A states (BF16 trajectory, protocol nmp-v1), admitted exactly as the primary of analyze_newmethod
(its loaders are imported: A6 + A7, strict 85-task blocks; reference cells = Bank U U2B rows f01-f03). KL = KLu_mean of
analyze_newmethod.load_scores (Q vs B next-token KL, teacher-forced on a_B's tokens, mean over a_B's tokens), reported x 1e-3.
Decomposition of the action swap under the common BF16 continuation (D_cc = Y_QB - Y_BB, protocol §4), per cell:
  P(diff) = P(a_Q != a_B) = share of non-exact states;  P(flip | diff) = M_cc / P(diff) (ratio of sums over non-exact states);
  upgrade orientation, as native r/d: r_cc = damage_cc = P(Y_BB=1, Y_QB=0) (B's action rescues), d_cc = gain_cc = P(Y_BB=0, Y_QB=1)
  (B's action damages);  M_cc = r_cc + d_cc = P(diff) x P(flip | diff) (exact states have QB = BB by construction; violations are
  counted);  D_cc = Y_QB - Y_BB = d_cc - r_cc (protocol sign: negative = B's action better);  rescue share = r_cc / M_cc.
  Native (Q continuation): r = P(Y_BQ=1, Y_QQ=0), d = P(Y_BQ=0, Y_QQ=1), M = r + d, G = r - d, P(flipQ | diff) = M / P(diff).
KL vs components: (a) across cells, Spearman over the 11 q8 cells (and over the 8 cells without W16/K16 path controls), descriptive;
(b) within cell, state level: AUC of KL for diff (all states), for flip given diff, and for rescue (r_cc) given flip; mean of cell AUCs.
Paired contrast spinquant_w4a4 - quarot_w4a4 on the same states (common complete blocks): KL and every component, point = mean of
block means (ratios: ratio of sums per cell, then difference); intervals: t over the K block differences (primary, K < 10) and the
crossed task x block bootstrap (both cells share one analyze_dev.Boot, so the draws are paired). B = 2000, seed 20261001.
analysis/fork/holdout/ is never opened (analyze_newmethod.no_holdout guards every path).
usage: python analysis/fork/kl_decomp.py [--B 2000] [--selftest] -> analysis/fork/out/kl_decomp_<UTC>.{md,json}
"""
from __future__ import annotations
import argparse, importlib.util, json, subprocess, sys, time  # noqa: E401
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr, mannwhitneyu

ROOT = Path(__file__).resolve().parents[2]
_sp = importlib.util.spec_from_file_location("analyze_newmethod", ROOT / "analysis/fork/analyze_newmethod.py")
AN = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(AN)
AD, OUT = AN.AD, AN.OUT
SRC = "analysis/fork/out/newmethod_q8_20261004T051538Z.json"
CONTROLS = ("quarot_w16", "spinquant_w16", "kivi_k16v16")
PAIR = ("spinquant_w4a4", "quarot_w4a4")
# (name, numerator key, denominator mask key or None = all states, scale 100 or 1)
COMP = [("KL", "KL", None, 1), ("P(diff)", "nonexact", None, 100), ("P(flip|diff)", "M_cc", "nonexact", 100), ("P(r_cc|diff)", "damage_cc", "nonexact", 100),
        ("P(d_cc|diff)", "gain_cc", "nonexact", 100), ("r_cc", "damage_cc", None, 100), ("d_cc", "gain_cc", None, 100), ("M_cc", "M_cc", None, 100),
        ("D_cc", "D_cc", None, 100), ("rescue share", "damage_cc", "M_cc", 100), ("P(flipQ|diff)", "M", "nonexact", 100), ("r", "rescue", None, 100),
        ("d", "damage", None, 100), ("M", "M", None, 100), ("G", "G", None, 100)]

def est(bt: AD.Boot, us: list, num: str, den: str | None):
    """Point, block values, block-bootstrap and crossed draws (ratio of sums over den-masked states when den is set)."""
    X, M = bt.arrays([u for u in us if u["E"][den]] if den else us, num)
    return bt.ratio(X, M) if den else bt.task_mean(X, M)

def cell_row(us: list, B: int) -> dict:
    bt = AN.boot_for(us, B)
    out = {"n_states": len(us), "K": len(bt.blocks), "n_diff": sum(u["E"]["nonexact"] for u in us), "n_flip_cc": sum(u["E"]["M_cc"] for u in us),
           "exact_with_flip": sum(1 for u in us if u["exact"] and (u["E"]["M_cc"] or u["E"]["M"]))}
    raw = {}
    for nm, num, den, f in COMP:
        raw[nm], dr = est(bt, us, num, den)
        out[nm] = AD.summarise(raw[nm], dr, pct=f == 100)
    out["identity_M_cc_minus_Pdiff_x_Pflip"] = float(raw["M_cc"] - raw["P(diff)"] * raw["P(flip|diff)"])
    out["identity_M_minus_Pdiff_x_PflipQ"] = float(raw["M"] - raw["P(diff)"] * raw["P(flipQ|diff)"])
    return out

def auc(x: list, y: list) -> float | None:
    x, y = np.asarray(x, float), np.asarray(y, int)
    return None if y.min(initial=1) == y.max(initial=0) else float(mannwhitneyu(x[y == 1], x[y == 0]).statistic / (y.sum() * (1 - y).sum()))

def within(us: list) -> dict:
    kl = lambda v: [u["E"]["KL"] for u in v]  # noqa: E731
    dv, fl = [u for u in us if u["E"]["nonexact"]], [u for u in us if u["E"]["M_cc"]]
    return {"AUC_KL_diff": auc(kl(us), [u["E"]["nonexact"] for u in us]), "AUC_KL_flip_given_diff": auc(kl(dv), [u["E"]["M_cc"] for u in dv]),
            "AUC_KL_rescue_given_flip": auc(kl(fl), [u["E"]["damage_cc"] for u in fl]), "n_diff": len(dv), "n_flip": len(fl)}

def paired(a: list, b: list, B: int) -> dict:
    ib = {(u["task"], u["block"]): u for u in b}
    blocks = sorted({u["block"] for u in a} & {u["block"] for u in b})
    A = [u for u in a if (u["task"], u["block"]) in ib and u["block"] in blocks]
    Bm = [ib[(u["task"], u["block"])] for u in A]
    assert all(u["state_key"] == v["state_key"] for u, v in zip(A, Bm)), "paired states differ"
    bt, out = AN.boot_for(A + Bm, B), {"n_pairs": len(A), "blocks": blocks}
    for nm, num, den, f in COMP:
        (pa, da), (pb, db) = est(bt, A, num, den), est(bt, Bm, num, den)
        t = AD.t_interval(np.asarray(da.block_means) - np.asarray(db.block_means))
        out[nm] = AD.summarise(pa - pb, np.asarray(da) - np.asarray(db), pct=f == 100, t=t, crossed=(da.crossed_pt - db.crossed_pt, da.crossed - db.crossed))
        out[nm]["cells"] = [round(f * pa, 4), round(f * pb, 4)]
    return out

def load() -> tuple[dict, dict]:
    g = AN.guard("q8")
    man = json.loads((ROOT / g["manifest"]).read_text())
    pop, _ = AN.population("q8", man)
    raw, _ = AN.load_tau2("q8", man, a6=True, recovery=True)
    cells = {c: us for c, us in AN.apply_population(raw, pop, len(pop))[0].items() if us}
    for c, us in cells.items():
        ref = all(u["source"] == "bank_u" for u in us if u["phase"] == 1)
        sc = {}
        for blk in sorted({u["block"] for u in us}):
            sc.update(AN.load_scores("q8", c, blk, ref and blk in ("f01", "f02", "f03")))
        miss = [u["state_key"] for u in us if u["state_key"] not in sc]
        assert not miss, f"{c}: {len(miss)} admitted states without token scores"
        for u in us:
            u["E"] = {**u["E"], "KL": 1e3 * sc[u["state_key"]]["KLu_mean"]}  # x 1e-3 (summarise rounds to 3 decimals)
    return cells, g

def across(R: dict, cells: list) -> dict:
    kl = [R[c]["KL"]["est"] for c in cells]
    return {nm: {"rho": round(float((s := spearmanr(kl, [R[c][nm]["est"] for c in cells])).correlation), 3), "p_descriptive": round(float(s.pvalue), 4)}
            for nm, *_ in COMP[1:]} | {"n_cells": len(cells)}

def md(o: dict, jp: Path) -> str:
    R, P, S, S8 = o["cells"], o["paired"], o["across_cells_spearman"]["all"], o["across_cells_spearman"]["no_path_controls"]
    v = lambda x, d=1: f"{x['est']:+.{d}f}"  # noqa: E731
    iv = lambda x, k, d=1: f"[{x[k][0]:+.{d}f}, {x[k][1]:+.{d}f}]" if x.get(k) else ""  # noqa: E731
    cols = [nm for nm, *_ in COMP]
    L = [f"**TL;DR** EXPLORATORY, POST HOC. q8 Panel A common states, 11 cells. Across cells mean KL orders P(diff) (rho {S['P(diff)']['rho']}) and turnover M_cc "
         f"(rho {S['M_cc']['rho']}); it orders P(flip|diff) at rho {S['P(flip|diff)']['rho']}, B-rescue r_cc at {S['r_cc']['rho']}, B-damage d_cc at {S['d_cc']['rho']}, "
         f"D_cc (= Y_QB - Y_BB) at {S['D_cc']['rho']}, rescue share at {S['rescue share']['rho']} (8 cells without path controls: P(diff) {S8['P(diff)']['rho']}, P(flip|diff) {S8['P(flip|diff)']['rho']}, D_cc {S8['D_cc']['rho']}). "
         f"Within cells (state level, mean AUC): diff {o['within_mean']['AUC_KL_diff']}, flip given diff {o['within_mean']['AUC_KL_flip_given_diff']}, rescue given flip "
         f"{o['within_mean']['AUC_KL_rescue_given_flip']}. SpinQuant-W4A4 minus QuaRot-W4A4 on {P['n_pairs']} paired states: KL (x 1e-3) {v(P['KL'], 2)} {iv(P['KL'], 't_ci95', 2)} (t, K = 3), "
         f"crossed {iv(P['KL'], 'crossed_ci95', 2)}; P(diff) {v(P['P(diff)'])} {iv(P['P(diff)'], 't_ci95')}; P(flip|diff) {v(P['P(flip|diff)'])} {iv(P['P(flip|diff)'], 't_ci95')}; "
         f"r_cc {v(P['r_cc'])}, d_cc {v(P['d_cc'])}, D_cc (Y_QB - Y_BB) {v(P['D_cc'])} {iv(P['D_cc'], 't_ci95')} pp.", "",
         f"# KL decomposition on the q8 new-method panel (EXPLORATORY, POST HOC; {o['utc']})", "",
         f"Script `analysis/fork/kl_decomp.py` (sha256 {o['script_sha256'][:16]}), git {o['git'][:10]}, B = {o['B']}. Inputs: analyze_newmethod loaders (protocol sha "
         f"{o['guard']['protocol_sha256'][:16]}); cross-check against `{SRC}`: {o['check_vs_newmethod']}. Full numbers incl. intervals: `{jp.relative_to(ROOT)}`.", "",
         "## 1. Per cell (point estimates; % except KL, which is x 1e-3; conditional rates are ratios over non-exact states; r_cc/r = B rescues, d_cc/d = B damages, D_cc = Y_QB - Y_BB, G = Y_BQ - Y_QQ)", "",
         "| cell | n | " + " | ".join(cols) + " |", "|---" * (len(cols) + 2) + "|"]
    L += [f"| {c} | {r['n_states']} | " + " | ".join(f"{r[nm]['est']:.2f}" if nm == "KL" else f"{r[nm]['est']:.1f}" for nm in cols) + " |" for c, r in R.items()]
    L += ["", "## 2. KL vs components", "", "| component | Spearman (11 cells) | p | Spearman (8, no path controls) |", "|---|---|---|---|"]
    L += [f"| {nm} | {S[nm]['rho']} | {S[nm]['p_descriptive']} | {S8[nm]['rho']} |" for nm in cols[1:]]
    L += ["", "Within cell, state level (AUC of KL; 0.5 = no discrimination):", "", "| cell | diff | flip given diff (n diff) | rescue given flip (n flip) |", "|---|---|---|---|"]
    fa = lambda x: "–" if x is None else f"{x:.2f}"  # noqa: E731
    L += [f"| {c} | {fa(w['AUC_KL_diff'])} | {fa(w['AUC_KL_flip_given_diff'])} ({w['n_diff']}) | {fa(w['AUC_KL_rescue_given_flip'])} ({w['n_flip']}) |" for c, w in o["within"].items()]
    L += ["", f"## 3. Paired {PAIR[0]} minus {PAIR[1]} ({P['n_pairs']} states, blocks {', '.join(P['blocks'])})", "",
          "| quantity | SpinQuant | QuaRot | difference | t over block differences (K = 3) | crossed task x block |", "|---|---|---|---|---|---|"]
    L += [f"| {nm} | {P[nm]['cells'][0]} | {P[nm]['cells'][1]} | {v(P[nm], 2 if nm == 'KL' else 1)} | {iv(P[nm], 't_ci95', 2 if nm == 'KL' else 1)} | {iv(P[nm], 'crossed_ci95', 2 if nm == 'KL' else 1)} |" for nm in cols]
    L += ["", "## What KL predicts", "", o["reading"], "", "## Method", "", "```", __doc__.strip(), "```"]
    return "\n".join(L) + "\n"

def main(B: int):
    t0, (cells, g) = time.time(), load()
    R = {c: cell_row(us, B) for c, us in sorted(cells.items())}
    W = {c: within(us) for c, us in sorted(cells.items())}
    ref = json.load(open(ROOT / SRC))
    chk = all(abs(R[c]["M_cc"]["est"] - ref["tau2"]["cells"][c]["all_states_pp"]["M_cc"]["est"]) < 1e-6 and R[c]["n_states"] == ref["tau2"]["cells"][c]["n_states"]
              and abs(R[c]["KL"]["est"] - 1e3 * ref["fidelity"]["cells"][c]["KLu_mean"]["mean"]) < 1e-3 for c in R)
    o = {"label": "EXPLORATORY, POST HOC (not pre-registered)", "utc": (utc := time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())), "guard": g, "B": B, "seed": AD.SEED,
         "script_sha256": AN.sha(Path(__file__)), "git": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "check_vs_newmethod": {"M_cc, n, KL identical": chk}, "cells": R, "within": W,
         "within_mean": {k: round(float(np.mean([w[k] for w in W.values() if w[k] is not None])), 3) for k in ("AUC_KL_diff", "AUC_KL_flip_given_diff", "AUC_KL_rescue_given_flip")},
         "across_cells_spearman": {"all": across(R, list(R)), "no_path_controls": across(R, [c for c in R if c not in CONTROLS])},
         "paired": paired(cells[PAIR[0]], cells[PAIR[1]], B), "reading": ""}
    S, Wm = o["across_cells_spearman"]["all"], o["within_mean"]
    o["reading"] = (f"Across cells KL orders how often the action differs (rho {S['P(diff)']['rho']}) and hence turnover (M_cc {S['M_cc']['rho']}, r_cc {S['r_cc']['rho']}, "
                    f"d_cc {S['d_cc']['rho']}; r_cc = B-action rescues, d_cc = B-action damages); it orders the flip rate given a difference at rho {S['P(flip|diff)']['rho']}, "
                    f"D_cc (Y_QB - Y_BB, negative = B better) at {S['D_cc']['rho']} and the rescue share at {S['rescue share']['rho']}, all unresolved. Within cells the "
                    f"state-level AUCs are {Wm['AUC_KL_diff']} (diff), {Wm['AUC_KL_flip_given_diff']} (flip | diff), {Wm['AUC_KL_rescue_given_flip']} (rescue | flip). Cell-level rho over 11 configurations is descriptive (no interval; cells are not exchangeable draws).")
    o["seconds"] = round(time.time() - t0)
    (jp := OUT / f"kl_decomp_{utc}.json").write_text(json.dumps(o, indent=1, default=float))
    (OUT / f"kl_decomp_{utc}.md").write_text(md(o, jp))
    print(f"kl_decomp: wrote {jp.relative_to(ROOT)} and .md ({o['seconds']} s); check {chk}")

def selftest():
    rng, us = np.random.default_rng(5), []
    for t in range(40):
        for b in ("f01", "f02", "f03"):
            kl = float(rng.gamma(1.0, 0.1)); ne = int(rng.random() < min(1, 3 * kl)); y = {"BB": int(rng.random() < .5)}  # noqa: E702
            y["QB"] = y["BB"] if not ne else int(rng.random() < .5); y["QQ"] = int(rng.random() < .4); y["BQ"] = y["QQ"] if not ne else int(rng.random() < .5)  # noqa: E702
            us.append({"task": f"r|{t}", "block": b, "state_key": f"{t}{b}", "exact": not ne, "E": {**AN.unit_effects(y, not ne), "KL": kl}})
    r = cell_row(us, 200)
    assert r["exact_with_flip"] == 0 and abs(r["identity_M_cc_minus_Pdiff_x_Pflip"]) < 1e-9, r["identity_M_cc_minus_Pdiff_x_Pflip"]
    assert abs(r["D_cc"]["est"] - (r["d_cc"]["est"] - r["r_cc"]["est"])) < 2e-3 and abs(r["identity_M_minus_Pdiff_x_PflipQ"]) < 1e-12
    p0 = paired(us, us, 200)
    assert all(abs(p0[nm]["est"]) < 1e-12 and p0[nm]["crossed_ci95"] == [0, 0] for nm, *_ in COMP)
    v = [{**u, "E": {**u["E"], "KL": u["E"]["KL"] + 0.01}} for u in us]
    p1 = paired(v, us, 200)
    assert abs(p1["KL"]["est"] - 0.01) < 1e-9 and abs(p1["P(diff)"]["est"]) < 1e-12
    assert auc([1, 2, 3, 4], [0, 0, 1, 1]) == 1.0 and auc([1, 2], [1, 1]) is None and within(us)["AUC_KL_diff"] > 0.6
    print("kl_decomp selftest OK (M_cc = P(diff) x P(flip|diff), D_cc = d_cc - r_cc, M = P(diff) x P(flipQ|diff), paired self = 0, shift, AUC; nothing written)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--B", type=int, default=AD.B_BOOT), ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    selftest() if a.selftest else main(a.B)
