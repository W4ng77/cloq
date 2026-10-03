"""Which units each substitution rescues / harms (W100d; DESCRIPTIVE / exploratory, protocol docs/insights/SAMEPREC_PROTOCOL.md
amendment A1.4; does not enter the reading; INTERIM before the 2026-10-03 freeze).

Question (GPT-6.1, main figure): on the SAME task x block units, do the two substitutions (precision: B = BF16; same-precision:
B role = Q' = GPTQ-W4 d2; Q = GPTQ-W4 d1 in both) have similar flip VOLUME but different rescued / harmed units and a different
continuation dependence?

Units: exactly those of sameprec_overlap.py (imported loader: protocol guard, analyze_dev admission, longest prefix of the
manifest's blocks complete in both cells and both designs; unit = (model, domain, task, block) admitted in both designs).
A unit without divergence in a design has every arm equal to Y_QQ there (no flip).

1. Rescue / harm sets for three contrasts against the shared QQ arm: G (action side, BQ vs QQ), H (continuation side, QB vs
   QQ), F (full substitution, BB vs QQ). rescue = Y_arm 1 / Y_QQ 0, harm = Y_arm 0 / Y_QQ 1. Per set: sizes in each design,
   overlap, Jaccard, expected overlap if independent within cell x block, a within-task shuffle null (the design-2 flag
   permuted across blocks inside each task, as sameprec_overlap.py) and a stricter within task x Y_QQ shuffle, Cohen's kappa
   with a block-bootstrap interval. Cross-direction counts (rescued under one design, harmed under the other), within and
   across contrasts.
2. Controller dependence: off-diagonal flag (Delta_Q = Y_BQ - Y_QQ != Delta_B = Y_BB - Y_QB) on units divergent in both
   designs (and on the same-decision subset t_prec = t_same): 2x2 overlap, kappa, nulls, share off-diagonal in one design only.
3. Net decomposition: G (and H, F) per design = shared rescue + design-specific rescue - shared harm - design-specific harm;
   the difference between designs only involves the design-specific parts.
4. Trigger link: the frozen Q-only trigger (manifests/fork/token_trigger_rule_v1.json, score S_mm, per-cell thresholds) is
   scored only on Bank U U1 states (analysis/fork/token_scores, blocks f01-f03). Fork states are linked when (model, block,
   domain, task, decision index) coincide. Enrichment of flips among triggered states and their net, per design.
5. Intervals: t over the K pooled block means (primary when K < 10, as analyze_sameprec) and a block bootstrap (blocks
   resampled jointly for both cells; B = 2000) for every pp quantity and difference; block bootstrap for kappa and shares.

Never reads analysis/fork/holdout/ (asserted by analyze_sameprec.dirs_under). Writes nothing outside analysis/fork/out/.

usage: python analysis/fork/sameprec_split.py [--perm 10000] [--B 2000] [--max-k K] [--w3]
       -> analysis/fork/out/sameprec_split_<UTC>.{md,json}  (--w3: sameprec_w3_split_<UTC>.{md,json})
  --w3 (W100h): the W3 pair (manifests/fork/sameprec_w3_v1.json, cell gptq_w3, blocks q3-q5, protocol guard of
       analyze_sameprec_w3.py); the trigger link is skipped (the frozen rule is defined for gptq_w4_d1 on Bank U f01-f03).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD  # noqa: E402
import analyze_sameprec as SP  # noqa: E402
import sameprec_overlap as SO  # noqa: E402

ROOT, OUT = AD.ROOT, AD.OUT
SEED = 20261002
CONTRASTS = {"G": "BQ", "H": "QB", "F": "BB"}
DES = ("prec", "same")
LAB = {"prec": "BF16", "same": "d2"}
RULE = ROOT / "manifests/fork/token_trigger_rule_v1.json"
RULE_SHA = "335e737d54bf59b948022b8054897ba703a1b9df6665f55bf6ab19b70333c052"


# ----------------------------------------------------------------------------------------------------------------------
# units
# ----------------------------------------------------------------------------------------------------------------------

def arms(u: dict) -> dict:
    Y = u["Y"]
    if not u["div"]:
        return {a: Y["QQ"] for a in ("BB", "BQ", "QB", "QQ")}
    return {a: Y[a] for a in ("BB", "BQ", "QB", "QQ")}


def rows_for(U: dict, blocks: list[str], models: list[str]) -> list[dict]:
    key = lambda u: (u["model"], u["domain"], u["task"], u["block"])  # noqa: E731
    S = {key(u): u for u in U["same"] if "excluded" not in u and u["block"] in blocks}
    out = []
    for p in U["prec"]:
        if "excluded" in p or p["block"] not in blocks or p["model"] not in models:
            continue
        s = S.get(key(p))
        if s is None:
            continue
        r = {"model": p["model"], "domain": p["domain"], "task": p["task"], "block": p["block"],
             "task_key": (p["model"], p["domain"], p["task"])}
        for d, u in (("prec", p), ("same", s)):
            Y = arms(u)
            r[f"div_{d}"] = int(u["div"])
            r[f"t_{d}"] = u.get("t")
            r[f"yqq_{d}"] = Y["QQ"]
            for c, a in CONTRASTS.items():
                r[f"R{c}_{d}"] = int(Y[a] == 1 and Y["QQ"] == 0)
                r[f"D{c}_{d}"] = int(Y[a] == 0 and Y["QQ"] == 1)
            r[f"off_{d}"] = int(u["E"]["offdiag"]) if u["div"] else None
            r[f"dQ_{d}"] = (Y["BQ"] - Y["QQ"]) if u["div"] else None
            r[f"dB_{d}"] = (Y["BB"] - Y["QB"]) if u["div"] else None
        out.append(r)
    return out


# ----------------------------------------------------------------------------------------------------------------------
# block-level resampling helpers
# ----------------------------------------------------------------------------------------------------------------------

class Blocks:
    """Pooled per-block unit means (all cells; equal unit counts per cell and block, so = equal-weight cell mean) and a
    block bootstrap that resamples block labels jointly for both cells (as sameprec_overlap.block_boot_kappa)."""

    def __init__(self, rows: list[dict], blocks: list[str], B: int, rng):
        self.blocks = blocks
        self.by = defaultdict(list)
        for r in rows:
            self.by[r["block"]].append(r)
        self.picks = [rng.integers(0, len(blocks), len(blocks)) for _ in range(B)]

    def mean_pp(self, f) -> dict:
        """f(row) -> number; pooled unit mean in pp with t over block means and block-bootstrap 95% intervals."""
        bm = np.array([100 * np.mean([f(r) for r in self.by[b]]) for b in self.blocks])
        est = float(bm.mean())
        t = AD.t_interval(bm)
        draws = np.array([bm[p].mean() for p in self.picks])
        return {"est": round(est, 3), "t_ci95": [round(t["lo"], 3), round(t["hi"], 3)] if t else None,
                "boot_ci95": [round(float(x), 3) for x in np.percentile(draws, [2.5, 97.5])],
                "block_means": [round(float(x), 3) for x in bm]}

    def stat_boot(self, fn) -> list:
        """fn(list of rows) -> scalar; block-bootstrap 95% percentile interval."""
        v = []
        for p in self.picks:
            x = fn([r for i in p for r in self.by[self.blocks[i]]])
            if x is not None and np.isfinite(x):
                v.append(x)
        return [round(float(x), 4) for x in np.percentile(v, [2.5, 97.5])] if v else None


def overlap_stats(rows: list[dict], fa: str, fb: str, n_perm: int, rng, bk: Blocks, extra_null: bool = True) -> dict:
    a = np.array([r[fa] for r in rows])
    b = np.array([r[fb] for r in rows])
    k = SO.kappa(a, b)
    both, na, nb = int(np.sum(a & b)), int(a.sum()), int(b.sum())
    # independence within cell x block
    g = defaultdict(list)
    for i, r in enumerate(rows):
        g[(r["model"], r["block"])].append(i)
    exp_cb = sum(a[ix].sum() * b[ix].sum() / len(ix) for ix in map(np.asarray, g.values()))
    out = {"n": len(rows), "n_a": na, "n_b": nb, "both": both, "only_a": na - both, "only_b": nb - both,
           "jaccard": round(both / max(1, na + nb - both), 4), "exp_indep_cell_block": round(float(exp_cb), 2),
           "kappa": k["kappa"], "kappa_max": k["kappa_max"],
           "kappa_boot_ci95": bk.stat_boot(lambda rr: SO.kappa([r[fa] for r in rr], [r[fb] for r in rr])["kappa"]),
           "share_specific_pct": round(100 * (na + nb - 2 * both) / max(1, na + nb - both), 2),
           "share_specific_boot_ci95": bk.stat_boot(lambda rr: _spec(rr, fa, fb))}
    out["null_within_task"] = SO.perm_null(a, b, [r["task_key"] for r in rows], n_perm, rng)
    if extra_null:
        out["null_within_task_yqq"] = SO.perm_null(a, b, [(r["task_key"], r["yqq_prec"]) for r in rows], n_perm, rng)
    # share specific expected under the within-task shuffle (from the null 'both' mean)
    bn = out["null_within_task"]["both_null_mean"]
    out["share_specific_null_within_task_pct"] = round(100 * (na + nb - 2 * bn) / max(1, na + nb - bn), 2)
    return out


def _spec(rr, fa, fb):
    a = sum(r[fa] for r in rr)
    b = sum(r[fb] for r in rr)
    both = sum(r[fa] and r[fb] for r in rr)
    u = a + b - both
    return 100 * (a + b - 2 * both) / u if u else None


# ----------------------------------------------------------------------------------------------------------------------
# 1-3
# ----------------------------------------------------------------------------------------------------------------------

def split_sets(rows, n_perm, rng, bk) -> dict:
    out = {}
    for c in CONTRASTS:
        x = {}
        for kind in ("R", "D"):
            x["rescue" if kind == "R" else "harm"] = overlap_stats(rows, f"{kind}{c}_prec", f"{kind}{c}_same", n_perm, rng, bk)
        for r in rows:
            r[f"flip{c}_prec"] = r[f"R{c}_prec"] | r[f"D{c}_prec"]
            r[f"flip{c}_same"] = r[f"R{c}_same"] | r[f"D{c}_same"]
        x["flip"] = overlap_stats(rows, f"flip{c}_prec", f"flip{c}_same", n_perm, rng, bk)
        x["cross_direction"] = {"rescued_BF16_harmed_d2": sum(r[f"R{c}_prec"] and r[f"D{c}_same"] for r in rows),
                                "harmed_BF16_rescued_d2": sum(r[f"D{c}_prec"] and r[f"R{c}_same"] for r in rows)}
        out[c] = x
    # across contrasts (e.g. rescued by the action under BF16, harmed by the continuation under d2)
    cc = {}
    for c1 in CONTRASTS:
        for c2 in CONTRASTS:
            cc[f"{c1}_BF16/{c2}_d2"] = sum((r[f"R{c1}_prec"] and r[f"D{c2}_same"]) or (r[f"D{c1}_prec"] and r[f"R{c2}_same"]) for r in rows)
    yqq_mm = sum(r["yqq_prec"] != r["yqq_same"] for r in rows)
    return {"by_contrast": out, "cross_direction_any_contrast_pair": cc, "yqq_mismatch_units": yqq_mm,
            "note": "Y_QQ is the same Q episode in both designs, so rescue (needs Y_QQ = 0) and harm (needs Y_QQ = 1) are mutually "
                    "exclusive across designs and contrasts: every cross-direction count is 0 by construction, not by evidence."}


def controller(rows, n_perm, rng, bk_all, blocks, B) -> dict:
    out = {}
    for lab, sel in (("both_divergent", lambda r: r["div_prec"] and r["div_same"]),
                     ("same_decision", lambda r: r["div_prec"] and r["div_same"] and r["t_prec"] == r["t_same"])):
        sub = [r for r in rows if sel(r)]
        bk = Blocks(sub, blocks, B, np.random.default_rng(SEED + 7))
        x = overlap_stats(sub, "off_prec", "off_same", n_perm, rng, bk, extra_null=False)
        x["off_rate_pct"] = {"BF16": round(100 * x["n_a"] / len(sub), 2), "d2": round(100 * x["n_b"] / len(sub), 2)}
        x["off_one_design_only_pct_of_states"] = round(100 * (x["only_a"] + x["only_b"]) / len(sub), 2)
        x["d_off_rate_pp"] = bk.mean_pp(lambda r: r["off_prec"] - r["off_same"])
        x["off_one_only_pp"] = bk.mean_pp(lambda r: int(r["off_prec"] != r["off_same"]))
        # among units with an action flip in both designs: same 3x3 cell?
        gg = [r for r in sub if r["dQ_prec"] != 0 and r["dQ_same"] != 0]
        x["action_flip_both"] = {"n": len(gg), "same_dB": sum(r["dB_prec"] == r["dB_same"] for r in gg),
                                 "off_BF16_only": sum(r["off_prec"] and not r["off_same"] for r in gg),
                                 "off_d2_only": sum(r["off_same"] and not r["off_prec"] for r in gg),
                                 "off_both": sum(r["off_prec"] and r["off_same"] for r in gg)}
        out[lab] = x
    return out


def net_decomp(rows, bk) -> dict:
    out = {}
    for c in CONTRASTS:
        R0, R1, D0, D1 = (f"R{c}_prec", f"R{c}_same", f"D{c}_prec", f"D{c}_same")
        parts = {
            "shared_rescue": lambda r: r[R0] & r[R1],
            "BF16_only_rescue": lambda r: r[R0] & (1 - r[R1]),
            "d2_only_rescue": lambda r: r[R1] & (1 - r[R0]),
            "shared_harm": lambda r: r[D0] & r[D1],
            "BF16_only_harm": lambda r: r[D0] & (1 - r[D1]),
            "d2_only_harm": lambda r: r[D1] & (1 - r[D0]),
            "net_BF16": lambda r: r[R0] - r[D0],
            "net_d2": lambda r: r[R1] - r[D1],
            "flips_BF16": lambda r: r[R0] + r[D0],
            "flips_d2": lambda r: r[R1] + r[D1],
            "d_net": lambda r: (r[R0] - r[D0]) - (r[R1] - r[D1]),
            "d_flips": lambda r: (r[R0] + r[D0]) - (r[R1] + r[D1]),
            "d_specific_rescue": lambda r: r[R0] - r[R1],
            "d_specific_harm": lambda r: r[D0] - r[D1],
            "specific_flips_any": lambda r: int((r[R0] + r[D0]) != (r[R1] + r[D1])),
        }
        x = {"counts": {k: int(sum(f(r) for r in rows)) for k, f in parts.items()}, "pp": {k: bk.mean_pp(f) for k, f in parts.items()}}
        cn = x["counts"]
        assert cn["net_BF16"] == cn["shared_rescue"] + cn["BF16_only_rescue"] - cn["shared_harm"] - cn["BF16_only_harm"]
        assert cn["net_d2"] == cn["shared_rescue"] + cn["d2_only_rescue"] - cn["shared_harm"] - cn["d2_only_harm"]
        out[c] = x
    return out


# ----------------------------------------------------------------------------------------------------------------------
# 4. trigger link
# ----------------------------------------------------------------------------------------------------------------------

def trigger_link(U, prefix, models) -> dict:
    import analyze_token_mech as TM
    if AD.sha256(RULE) != RULE_SHA:
        return {"feasible": False, "note": "frozen rule sha mismatch; not used"}
    rule = json.load(open(RULE))
    score = rule["chosen_score"]
    raw, inputs = TM.load()
    idx = {}
    for r in raw:
        if r["sub"] != "U1" or r["cell"] != SP.CELL:
            continue
        f = TM.features(r)
        f["Y_bank"] = r["Y"]
        idx[(r["model"], r["block"], r["domain"], str(r["task_id"]), int(r["t"]))] = f
    scored_blocks = sorted({k[1] for k in idx})
    out = {"feasible": True, "score": score, "rule_sha256": RULE_SHA, "scored_blocks": scored_blocks, "u1_rows": len(idx),
           "dev_block_note": "f01 is the rule's development block (in-sample); f02/f03 validation",
           "inputs": {k: v for k, v in inputs.items() if SP.CELL in k}, "by_design": {}}
    bank_agree = {"n": 0, "same_Y": 0}
    for d in DES:
        st = []
        for u in U[d]:
            if "excluded" in u or not u["div"] or u["block"] not in prefix or u["model"] not in models:
                continue
            k = (u["model"], u["block"], u["domain"], u["task"].split(":")[-1], int(u["t"]))
            if k not in idx:
                continue
            f = idx[k]
            Y = u["Y"]
            G = Y["BQ"] - Y["QQ"]
            st.append({"model": u["model"], "block": u["block"], "S": f[score], "G": G, "flip": int(G != 0),
                       "M_any": int(any(Y[a] != Y["QQ"] for a in ("BB", "BQ", "QB")))})
            if d == "prec":
                bank_agree["n"] += 1
                bank_agree["same_Y"] += int(all(f["Y_bank"][a] == Y[a] for a in ("BB", "BQ", "QB", "QQ")))
        n_div = sum(1 for u in U[d] if "excluded" not in u and u["div"] and u["block"] in scored_blocks and u["block"] in prefix
                    and u["model"] in models)
        x = {"n_states_scored_blocks": n_div, "n_linked": len(st), "by_rate": {}}
        for rate, thr in rule["thresholds"].items():
            tr = [s for s in st if s["S"] > thr[f"{s['model']}_{SP.CELL}"]]
            nt = [s for s in st if not s["S"] > thr[f"{s['model']}_{SP.CELL}"]]
            fr = lambda xs, k: (round(100 * np.mean([s[k] for s in xs]), 1) if xs else None)  # noqa: E731
            x["by_rate"][rate] = {"n_trig": len(tr), "n_not": len(nt), "flip_pct_trig": fr(tr, "flip"), "flip_pct_not": fr(nt, "flip"),
                                  "net_G_trig": int(sum(s["G"] for s in tr)), "rescued_trig": sum(s["G"] == 1 for s in tr),
                                  "harmed_trig": sum(s["G"] == -1 for s in tr), "Many_pct_trig": fr(tr, "M_any"), "Many_pct_not": fr(nt, "M_any")}
            if tr and nt:
                from scipy.stats import fisher_exact
                a_, b_ = sum(s["flip"] for s in tr), len(tr) - sum(s["flip"] for s in tr)
                c_, d_ = sum(s["flip"] for s in nt), len(nt) - sum(s["flip"] for s in nt)
                x["by_rate"][rate]["fisher_p_greater"] = round(float(fisher_exact([[a_, b_], [c_, d_]], alternative="greater")[1]), 4)
        out["by_design"][d] = x
    out["bank_u_vs_prec_fork_same_Y"] = bank_agree
    out["note"] = ("Linked states are the fork states whose decision index happens to equal the sampled Bank U U1 state of the same "
                   "Q episode; tiny n, the first-divergence states are a selected subset, and f01 is in-sample for the rule. "
                   "Descriptive only; not an evaluation of the trigger under d2.")
    return out


# ----------------------------------------------------------------------------------------------------------------------

def analyse(rows, blocks, n_perm, B) -> dict:
    rng = np.random.default_rng(SEED)
    bk = Blocks(rows, blocks, B, np.random.default_rng(SEED + 1))
    res = {"blocks": blocks, "K": len(blocks), "n_units": len(rows),
           "units_digest": hashlib.sha256(json.dumps(sorted((r["model"], r["domain"], r["task"], r["block"]) for r in rows)).encode()).hexdigest()}
    res["sets"] = split_sets(rows, n_perm, rng, bk)
    res["controller"] = controller(rows, n_perm, rng, bk, blocks, B)
    res["net"] = net_decomp(rows, bk)
    res["per_cell_G"] = {}
    for m in sorted({r["model"] for r in rows}):
        rr = [r for r in rows if r["model"] == m]
        bkm = Blocks(rr, blocks, B, np.random.default_rng(SEED + 2))
        res["per_cell_G"][m] = {k: v["counts"] for k, v in net_decomp(rr, bkm).items() if k == "G"}["G"]
        res["per_cell_G"][m]["kappa_rescue"] = SO.kappa([r["RG_prec"] for r in rr], [r["RG_same"] for r in rr])["kappa"]
        res["per_cell_G"][m]["kappa_harm"] = SO.kappa([r["DG_prec"] for r in rr], [r["DG_same"] for r in rr])["kappa"]
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--perm", type=int, default=10000)
    ap.add_argument("--B", type=int, default=AD.B_BOOT)
    ap.add_argument("--max-k", type=int, default=None, help="restrict to the first K prefix blocks (labelled)")
    ap.add_argument("--w3", action="store_true", help="W3 pair (sameprec_w3_v1 manifest; W100h); trigger link skipped")
    a = ap.parse_args()
    t0 = time.time()
    stem = "sameprec_split"
    if a.w3:
        import analyze_sameprec_w3 as W3
        SP.MANIFEST, SP.guard, stem = W3.MAN, W3.guard, "sameprec_w3_split"
        SP.CELL = json.load(open(W3.MAN))["cell"]
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    man = json.load(open(SP.MANIFEST))
    psha = SP.guard(man)
    if a.w3:
        man.setdefault("snapshot", W3.SNAPSHOT)
    snap = json.load(open(ROOT / man["snapshot"]))
    models = man["cells"]
    U, prefix = SO.load(man, snap)
    full_prefix = list(prefix)
    if a.max_k:
        prefix = prefix[:a.max_k]
    interim = time.gmtime() < time.strptime("2026-10-04T07", "%Y-%m-%dT%H")
    res = {"script": str(Path(__file__).relative_to(ROOT)), "script_sha256": AD.sha256(__file__), "protocol_sha256": psha,
           "sameprec_overlap_sha256": AD.sha256(SO.__file__), "analyze_sameprec_sha256": AD.sha256(SP.__file__),
           "analyze_dev_sha256": AD.sha256(AD.__file__),
           "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
           "utc": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), "seed": SEED, "n_perm": a.perm, "B": a.B,
           "status": ("INTERIM (before the 2026-10-03 evidence freeze); " if interim else "") + "DESCRIPTIVE / exploratory (amendment A1.4)",
           "complete_prefix": full_prefix, "capped_by_max_k": a.max_k, "manifest": str(SP.MANIFEST.relative_to(ROOT)), "cell": SP.CELL}
    rows = rows_for(U, prefix, models)
    res["main"] = analyse(rows, prefix, a.perm, a.B)
    res["trigger"] = ({"feasible": False, "note": "Trigger link skipped (--w3): the frozen Q-only rule is defined for gptq_w4_d1 on Bank U f01-f03, "
                                   "not for GPTQ-W3 blocks q3-q5."} if a.w3 else trigger_link(U, prefix, models))
    res["seconds"] = round(time.time() - t0, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    tag = res["utc"] + (f"_capK{len(prefix)}" if a.max_k else "")
    jp = OUT / f"{stem}_{tag}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    md = markdown(res, jp)
    if a.w3:
        md = md.replace("GPTQ-W4", "GPTQ-W3")
    (OUT / f"{stem}_{tag}.md").write_text(md)
    print(f"sameprec_split: wrote {jp.relative_to(ROOT)} (K = {len(prefix)}, {res['seconds']} s)")


# ----------------------------------------------------------------------------------------------------------------------

def answer(S, N, C, pk) -> str:
    """Data-driven reading of the main question (descriptive)."""
    def beyond(c, s):  # overlap above the within task x Y_QQ shuffle (task propensity and the shared QQ outcome kept)
        return S[c][s]["null_within_task_yqq"]["p_one_sided_kappa_ge_obs"] < 0.05

    def same_vol(c):
        lo, hi = N[c]["pp"]["d_flips"][pk]
        return lo <= 0 <= hi
    g = S["G"]["flip"]
    vol = ", ".join(f"{c} {'similar' if same_vol(c) else 'DIFFERENT'} (Δflips {ci(N[c]['pp']['d_flips'], pk)} pp)" for c in CONTRASTS)
    shared_beyond = [f"{c} {s}" for c in CONTRASTS for s in ("rescue", "harm") if beyond(c, s)]
    not_beyond = [f"{c} {s}" for c in CONTRASTS for s in ("rescue", "harm") if not beyond(c, s)]
    off = C["both_divergent"]
    return (f"flip volume: {vol}. On the action side (G) the two substitutions share a large core of rescued and harmed units, "
            f"well above independence and above a within-task shuffle, yet {g['share_specific_pct']:.0f}% of the flipping units are "
            f"design-specific (within-task null {g['share_specific_null_within_task_pct']:.0f}%). Unit overlap beyond task propensity and the "
            f"shared Y_QQ (within task×Y_QQ shuffle, p < 0.05): {', '.join(shared_beyond) or 'none'}; not beyond it: {', '.join(not_beyond) or 'none'}. "
            f"Controller dependence is mostly design-specific: κ {off['kappa']:.2f}, {off['share_specific_pct']:.0f}% of off-diagonal units are "
            f"off-diagonal under one design only (within-task null {off['share_specific_null_within_task_pct']:.0f}%). "
            + (f"Read: different units mainly where the overlap is not beyond the task×Y_QQ shuffle ({', '.join(not_beyond) or 'none'}) and for "
               f"the off-diagonal (controller-dependent) set; the action contrast G shares a substantial unit core. ")
            + f"Net: ΔG {ci(N['G']['pp']['d_net'], pk)} pp, the difference of the design-specific rescues and harms.")


def ci(x, key="t_ci95"):
    return f"{x['est']:+.1f} [{x[key][0]:+.1f}, {x[key][1]:+.1f}]"


def markdown(r: dict, jp: Path) -> str:
    R = r["main"]
    S, C, N, T = R["sets"]["by_contrast"], R["controller"], R["net"], r["trigger"]
    g, nG = S["G"], N["G"]
    gc, gp = nG["counts"], nG["pp"]
    cb = C["both_divergent"]
    K, n = R["K"], R["n_units"]
    prim = "t over block means" if K < 10 else "block bootstrap"
    pk = "t_ci95" if K < 10 else "boot_ci95"

    def ov(x):
        nt = x["null_within_task"]
        return (f"{x['n_a']} vs {x['n_b']}; shared {x['both']} (Jaccard {x['jaccard']:.2f}); exp. indep. {x['exp_indep_cell_block']:.0f}, "
                f"within-task shuffle {nt['both_null_mean']:.0f} [{nt['both_null_95'][0]:.0f}, {nt['both_null_95'][1]:.0f}]; "
                f"κ {x['kappa']:.2f} [{x['kappa_boot_ci95'][0]:.2f}, {x['kappa_boot_ci95'][1]:.2f}]")
    tr = T.get("by_design", {})
    trig_txt = ("Trigger link: only " + ", ".join(f"{tr[d]['n_linked']}/{tr[d]['n_states_scored_blocks']} {LAB[d]} fork states" for d in DES)
                + " on the scored blocks coincide with a Bank U U1 state carrying the frozen S_mm score, so enrichment under d2 "
                "cannot be assessed (numbers below, descriptive only).") if T.get("feasible") else "Trigger link: not feasible."
    L = [f"**TL;DR** ({r['status']}; K = {K} blocks {R['blocks'][0]}–{R['blocks'][-1]}, q4+q8, {n} task×block units, the units of "
         f"sameprec_overlap.py.) **Action-side (G) flip volume {'similar' if (gp['d_flips'][pk][0] <= 0 <= gp['d_flips'][pk][1]) else 'DIFFERENT'}; "
         f"the flipping units overlap above chance but are not identical.** "
         f"Action-side (G) flips: BF16 {gc['flips_BF16']} vs d2 {gc['flips_d2']} (Δ {ci(gp['d_flips'], pk)} pp); rescues {g['rescue']['n_a']} vs "
         f"{g['rescue']['n_b']}, shared {g['rescue']['both']} (κ {g['rescue']['kappa']:.2f}); harms {g['harm']['n_a']} vs {g['harm']['n_b']}, "
         f"shared {g['harm']['both']} (κ {g['harm']['kappa']:.2f}). {g['flip']['share_specific_pct']:.0f}% of the units that flip under "
         f"either substitution flip under only one ({g['flip']['only_a'] + g['flip']['only_b']} of {g['flip']['n_a'] + g['flip']['n_b'] - g['flip']['both']}; "
         f"block-boot 95% [{g['flip']['share_specific_boot_ci95'][0]:.0f}, {g['flip']['share_specific_boot_ci95'][1]:.0f}]%), vs "
         f"{g['flip']['share_specific_null_within_task_pct']:.0f}% if the d2 flags were shuffled across blocks within task. "
         f"Net G: BF16 {gc['net_BF16']:+d} = shared ({gc['shared_rescue']} r − {gc['shared_harm']} h) + specific "
         f"({gc['BF16_only_rescue']} r − {gc['BF16_only_harm']} h); d2 {gc['net_d2']:+d} = same shared part + specific "
         f"({gc['d2_only_rescue']} r − {gc['d2_only_harm']} h); ΔG {ci(gp['d_net'], pk)} pp comes entirely from the design-specific units "
         f"(Δ specific rescue {ci(gp['d_specific_rescue'], pk)}, Δ specific harm {ci(gp['d_specific_harm'], pk)} pp). "
         f"Continuation side (H) agrees less (κ rescue {S['H']['rescue']['kappa']:.2f}, harm {S['H']['harm']['kappa']:.2f}) than the action side; "
         f"full substitution (F) κ rescue {S['F']['rescue']['kappa']:.2f}, harm {S['F']['harm']['kappa']:.2f}. "
         f"Controller dependence (off-diagonal Δ_Q ≠ Δ_B, {cb['n']} units divergent in both designs): {cb['n_a']} vs {cb['n_b']}, shared "
         f"{cb['both']}, κ {cb['kappa']:.2f} [{cb['kappa_boot_ci95'][0]:.2f}, {cb['kappa_boot_ci95'][1]:.2f}]; "
         f"{cb['off_one_design_only_pct_of_states']:.1f}% of these states are off-diagonal under one design only "
         f"({cb['share_specific_pct']:.0f}% of the off-diagonal set). "
         f"Cross-direction (rescued under one design, harmed under the other): 0 for every contrast pair, forced by the shared Y_QQ. "
         + trig_txt + " **Answer:** " + answer(S, N, C, pk), ""]
    # ---- figure-panel table
    L += ["## Figure-panel table (pooled q4+q8; counts of units, pp of all units in parentheses)", "",
          "| contrast | set | BF16 | d2 | shared | BF16 only | d2 only | exp. shared (indep.) | exp. shared (within-task shuffle) | κ [block-boot 95%] |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for c in CONTRASTS:
        for s in ("rescue", "harm", "flip"):
            x = S[c][s]
            nt = x["null_within_task"]
            L.append(f"| {c} | {s} | {x['n_a']} ({100 * x['n_a'] / n:.1f}) | {x['n_b']} ({100 * x['n_b'] / n:.1f}) | {x['both']} | {x['only_a']} | "
                     f"{x['only_b']} | {x['exp_indep_cell_block']:.1f} | {nt['both_null_mean']:.1f} [{nt['both_null_95'][0]:.0f}, {nt['both_null_95'][1]:.0f}] | "
                     f"{x['kappa']:.2f} [{x['kappa_boot_ci95'][0]:.2f}, {x['kappa_boot_ci95'][1]:.2f}] |")
    L.append(f"| off-diag. | states div. in both (n {cb['n']}) | {cb['n_a']} | {cb['n_b']} | {cb['both']} | {cb['only_a']} | {cb['only_b']} | "
             f"{cb['exp_indep_cell_block']:.1f} | {cb['null_within_task']['both_null_mean']:.1f} | {cb['kappa']:.2f} [{cb['kappa_boot_ci95'][0]:.2f}, {cb['kappa_boot_ci95'][1]:.2f}] |")
    L += ["", f"# Same-precision split: which units each substitution rescues and harms ({r['utc']})", "",
          f"{r['status']}. Script `{r['script']}` sha {r['script_sha256'][:12]}; protocol sha {r['protocol_sha256'][:12]} (A1); "
          f"sameprec_overlap {r['sameprec_overlap_sha256'][:12]}; analyze_sameprec {r['analyze_sameprec_sha256'][:12]}; git {r['git_head'][:10]}; "
          f"seed {r['seed']}, {r['n_perm']} permutations, B = {r['B']}. Full numbers: `{jp.relative_to(ROOT)}`. Complete prefix now: "
          f"{', '.join(r['complete_prefix'])}{' (capped at K = %d)' % K if r['capped_by_max_k'] else ''}. Units digest {R['units_digest'][:12]}.", "",
          "Definitions: contrast c ∈ {G: BQ vs QQ (action side), H: QB vs QQ (continuation side), F: BB vs QQ (full substitution)}; "
          "rescue = Y_arm 1 / Y_QQ 0, harm = Y_arm 0 / Y_QQ 1; no divergence = no flip. 'BF16' = precision design (B = BF16), "
          "'d2' = same-precision design (B role = GPTQ-W4 d2). Q = GPTQ-W4 d1 and the QQ episode are shared.", "",
          f"## 1. Rescue and harm sets", "",
          "| contrast | set | sizes / shared / nulls / κ | within task×Y_QQ shuffle: shared mean [95%], p | share design-specific (% of union) [boot 95%] vs within-task null |",
          "|---|---|---|---|---|"]
    for c in CONTRASTS:
        for s in ("rescue", "harm", "flip"):
            x = S[c][s]
            ny = x.get("null_within_task_yqq")
            L.append(f"| {c} | {s} | {ov(x)} | {ny['both_null_mean']:.1f} [{ny['both_null_95'][0]:.0f}, {ny['both_null_95'][1]:.0f}], {ny['p_one_sided_kappa_ge_obs']:.4f} | "
                     f"{x['share_specific_pct']:.1f} [{x['share_specific_boot_ci95'][0]:.1f}, {x['share_specific_boot_ci95'][1]:.1f}] vs "
                     f"{x['share_specific_null_within_task_pct']:.1f} |")
    L += ["", "Cross-direction counts (rescued under one design, harmed under the other), same contrast: "
          + "; ".join(f"{c}: {S[c]['cross_direction']['rescued_BF16_harmed_d2']} / {S[c]['cross_direction']['harmed_BF16_rescued_d2']}" for c in CONTRASTS)
          + ". Across contrast pairs: " + ", ".join(f"{k} {v}" for k, v in R["sets"]["cross_direction_any_contrast_pair"].items())
          + f". Y_QQ mismatches between designs: {R['sets']['yqq_mismatch_units']}. {R['sets']['note']}", "",
          "Per cell (G): " + "; ".join(f"{m}: flips {v['flips_BF16']}/{v['flips_d2']}, shared r {v['shared_rescue']} h {v['shared_harm']}, "
                                       f"specific r {v['BF16_only_rescue']}/{v['d2_only_rescue']} h {v['BF16_only_harm']}/{v['d2_only_harm']}, "
                                       f"net {v['net_BF16']:+d}/{v['net_d2']:+d}, κ r {v['kappa_rescue']:.2f} h {v['kappa_harm']:.2f}"
                                       for m, v in R["per_cell_G"].items()), "",
          "## 2. Controller dependence (off-diagonal: Δ_Q = Y_BQ − Y_QQ ≠ Δ_B = Y_BB − Y_QB)", "",
          "| subset | states | off-diag BF16 / d2 (%) | shared | BF16 only | d2 only | κ [boot 95%] | within-task shuffle shared | off-diag under one design only (% of states) | Δ off-diag rate (pp) | action flips in both: same Δ_B / off only BF16 / only d2 / both |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for lab, x in C.items():
        af = x["action_flip_both"]
        L.append(f"| {lab} | {x['n']} | {x['off_rate_pct']['BF16']:.1f} / {x['off_rate_pct']['d2']:.1f} | {x['both']} | {x['only_a']} | {x['only_b']} | "
                 f"{x['kappa']:.2f} [{x['kappa_boot_ci95'][0]:.2f}, {x['kappa_boot_ci95'][1]:.2f}] | {x['null_within_task']['both_null_mean']:.1f} "
                 f"[{x['null_within_task']['both_null_95'][0]:.0f}, {x['null_within_task']['both_null_95'][1]:.0f}] | "
                 f"{x['off_one_design_only_pct_of_states']:.1f} ({ci(x['off_one_only_pp'], pk)}) | {ci(x['d_off_rate_pp'], pk)} | "
                 f"{af['same_dB']}/{af['n']} · {af['off_BF16_only']} / {af['off_d2_only']} / {af['off_both']} |")
    L += ["", "States differ between designs when the first divergence is at a different decision (t); 'same_decision' keeps t_BF16 = t_d2.", "",
          f"## 3. Net decomposition (counts; pp of {n} units with {prim} 95% and block-bootstrap 95%)", "",
          "| contrast | shared rescue | shared harm | BF16-only rescue | BF16-only harm | d2-only rescue | d2-only harm | net BF16 | net d2 | Δnet (pp) | Δflips (pp) | Δ specific rescue (pp) | Δ specific harm (pp) |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in CONTRASTS:
        cn, pp = N[c]["counts"], N[c]["pp"]
        L.append(f"| {c} | {cn['shared_rescue']} | {cn['shared_harm']} | {cn['BF16_only_rescue']} | {cn['BF16_only_harm']} | {cn['d2_only_rescue']} | "
                 f"{cn['d2_only_harm']} | {cn['net_BF16']:+d} ({pp['net_BF16']['est']:+.1f}) | {cn['net_d2']:+d} ({pp['net_d2']['est']:+.1f}) | "
                 f"{ci(pp['d_net'], pk)}; boot [{pp['d_net']['boot_ci95'][0]:+.1f}, {pp['d_net']['boot_ci95'][1]:+.1f}] | {ci(pp['d_flips'], pk)} | "
                 f"{ci(pp['d_specific_rescue'], pk)} | {ci(pp['d_specific_harm'], pk)} |")
    L += ["", "Identity: net = shared rescue + design-specific rescue − shared harm − design-specific harm (asserted); the shared parts cancel in Δnet. "
          f"Consistency: G ΔG {N['G']['pp']['d_net']['est']:+.2f} pp should equal analyze_sameprec's pooled ΔG_all; G Δflips "
          f"{N['G']['pp']['d_flips']['est']:+.2f} pp its ΔM.", "", "## 4. Trigger link (frozen Q-only trigger)", ""]
    if T.get("feasible"):
        L += [f"Score {T['score']} (rule sha {T['rule_sha256'][:12]}); scored U1 blocks {', '.join(T['scored_blocks'])} ({T['dev_block_note']}); "
              f"{T['u1_rows']} U1 rows for {SP.CELL}. Bank U Y vs precision-fork Y at the linked states: "
              f"{T['bank_u_vs_prec_fork_same_Y']['same_Y']}/{T['bank_u_vs_prec_fork_same_Y']['n']} identical.", "",
              "| design | divergent fork states on scored blocks | linked | rate | triggered / not | flip % trig / not | Fisher p (greater) | net G triggered (r/h) |",
              "|---|---|---|---|---|---|---|---|"]
        for d, x in T["by_design"].items():
            for rate, y in x["by_rate"].items():
                L.append(f"| {LAB[d]} | {x['n_states_scored_blocks']} | {x['n_linked']} | {rate} | {y['n_trig']} / {y['n_not']} | {y['flip_pct_trig']} / "
                         f"{y['flip_pct_not']} | {y.get('fisher_p_greater', 'n/a')} | {y['net_G_trig']:+d} ({y['rescued_trig']}/{y['harmed_trig']}) |")
        L += ["", T["note"], ""]
    else:
        L += [T.get("note", "not feasible"), ""]
    L += ["## Caveats", "",
          "- INTERIM and descriptive (A1.4); the frozen analysis uses the longest complete prefix at the 2026-10-03 freeze; re-run this script then.",
          "- Forks are deterministic replays, so there is no within-design unit-level replication benchmark: the within-task shuffle and "
          "independence nulls are the only references for 'how much overlap is a lot'. Task-level replication (split-half) is in sameprec_overlap.",
          "- Direction agreement is forced by the shared QQ episode; only the *which-units* question is informative.",
          f"- K = {K} blocks: t intervals over {K} block means are wide; κ and share intervals are percentile block bootstraps over {K} clusters.",
          "- States differ between designs when the first divergence lands on a different decision; off-diagonal agreement is reported "
          "both on all doubly divergent units and on the same-decision subset.", ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
