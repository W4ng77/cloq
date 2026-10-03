"""Same-precision 2x2 fork analysis (W99k/W99l; docs/insights/SAMEPREC_PROTOCOL.md, frozen; manifests/fork/sameprec_v1.json).

Precision 2x2: B = BF16, Q = GPTQ-W4 d1 (analysis/fork/dev/<m>_gptq_w4_d1). Same-precision 2x2: the driver's B role is
Q' = GPTQ-W4 d2 (analysis/fork/sameprec/<m>_gptq_w4_d1_vs_d2). Both share the Q episodes (QQ arm), so the task x block
units pair one to one. Driver branch names map BB = Q'Q', BQ = Q'Q, QB = QQ', QQ = QQ.

Admission, effects, intervals: analyze_dev (imported): snapshot gate, quarantine, dedupe, strict complete-block rule
(W70), complete 85-task retail/airline panel blocks (W78), split guard dev; Boot / summarise (block bootstrap with >= 10
blocks else t over block means; crossed task x block alongside); B = 2000, seed 20261001. The 2x2 contrasts (offdiag,
3x3, 16 patterns): analyze_ghf (imported). Each design is admitted separately (the unit keys coincide).
Analysis set: longest prefix of the manifest's ordered blocks complete in the same-precision fork of BOTH cells (and in
the precision fork). Primary: paired Delta M = M_prec - M' on the same units, pooled q4+q8 equal weight. Secondary
(descriptive): Delta offdiag. Frozen reading (protocol §6). Per-block numbers for every completed block.
Refuses to run unless sha256(protocol) equals PROTOCOL_SHA256 here (amended protocol) and the manifest records the
original frozen sha (PROTOCOL_SHA256_V1), which must be a byte-identical prefix of the amended file.

Amendment A1 (W99l-c, 2026-10-02; protocol §"Amendment A1"): the §6 "similar" case was an incorrect equivalence
reading. Added, without changing the primary estimates: TOST at +-3 pp (t over the K pooled block means, df = K - 1;
90% interval, both one-sided p) on Delta M, Delta G_all and Delta offdiag (descriptive), pooled and per cell, and the A1.3
reading (`reading_a1`). The frozen §6 reading stays in the JSON under `reading` (labelled superseded).

usage: python analysis/fork/analyze_sameprec.py [--B 2000] [--max-k K]  ->  analysis/fork/out/sameprec_<UTC>[_capK<K>].{md,json}
  --max-k K: restrict the analysis set to the first K prefix blocks (interim look at an earlier K; labelled).
"""
from __future__ import annotations

import argparse
import glob
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
import analyze_ghf as GH  # noqa: E402

ROOT, OUT = AD.ROOT, AD.OUT
MANIFEST = ROOT / "manifests/fork/sameprec_v1.json"
# Amendment A1 (W99l-c, 2026-10-02): the frozen sameprec-v1 text (sha below, recorded in the manifest) is a byte-identical
# prefix of the amended protocol; only the amended file is accepted.
PROTOCOL_SHA256_V1 = "5c58d1e7d07ef10bd39f841236fccfd1436107c57ad264c62eaf14df94735823"
PROTOCOL_SHA256 = "89484d35c77cfc9ba69fbf4fa5de3b90ae0c35cdd8f988d0509ba29c0580131c"
EPS_PP = 3.0  # A1.2 equivalence margin (= few_pp = g_min)
PANEL = ("retail", "airline")
CELL = "gptq_w4_d1"
DESIGNS = ("prec", "same")
FULL = ["G", "rescue", "damage", "M"]
CONDK = ["G", "H", "F", "I", "offdiag", "strict_reversal", "M", "rescue", "damage"]


def guard(man: dict) -> str:
    p = ROOT / man["protocol"]
    s = AD.sha256(p)
    if s != PROTOCOL_SHA256 or man["protocol_sha256"] != PROTOCOL_SHA256_V1:
        raise SystemExit(f"analyze_sameprec: refusing: sha256({man['protocol']}) = {s} (expected amended {PROTOCOL_SHA256}); "
                         f"manifest records {man['protocol_sha256']} (expected frozen v1 {PROTOCOL_SHA256_V1})")
    raw = p.read_bytes()
    cut = raw.find(b"\n\n---\n\n## Amendment A1")
    if cut < 0 or hashlib.sha256(raw[:cut + 1]).hexdigest() != PROTOCOL_SHA256_V1:
        raise SystemExit("analyze_sameprec: refusing: the frozen v1 text is not a byte-identical prefix of the amended protocol")
    return s


def tost(vals: list[tuple], eps_pp: float = EPS_PP) -> dict:
    """A1.2: TOST at +-eps on the pooled per-block differences (equal-weight mean over cells of each cell's block means),
    t over the K blocks (df = K - 1), as the primary fixed-pool analysis; plus the block-bootstrap 90% percentile interval."""
    from scipy.stats import t as tdist
    bm = np.nanmean(np.vstack([np.asarray(v[1].block_means, float) for v in vals]), axis=0)
    x = 100 * bm[np.isfinite(bm)]
    k = len(x)
    if k < 2:
        return {"k": k, "note": "fewer than 2 blocks"}
    m, se = float(x.mean()), float(x.std(ddof=1) / np.sqrt(k))
    q90 = tdist.ppf(0.95, k - 1)
    p_lo = float(tdist.sf((m + eps_pp) / se, k - 1))   # H0: diff <= -eps
    p_hi = float(tdist.cdf((m - eps_pp) / se, k - 1))  # H0: diff >= +eps
    dr = 100 * np.mean([np.asarray(v[1], float) for v in vals], axis=0)
    dr = dr[np.isfinite(dr)]
    return {"est": round(m, 3), "se": round(se, 4), "k": k, "df": k - 1, "eps_pp": eps_pp,
            "t_ci90": [round(m - q90 * se, 3), round(m + q90 * se, 3)],
            "block_boot_ci90": [round(float(np.percentile(dr, 5)), 3), round(float(np.percentile(dr, 95)), 3)] if len(dr) else None,
            "p_lower": round(p_lo, 4), "p_upper": round(p_hi, 4), "p_tost": round(max(p_lo, p_hi), 4),
            "equivalent": bool(max(p_lo, p_hi) < 0.05), "block_diffs_pp": [round(float(v), 3) for v in x]}


def reading_a1(x95: dict, t: dict, what: str) -> dict:
    """A1.3: replaces the §6 'similar' case by TOST; the excess / at-least-as-large cases are unchanged."""
    lo, hi = x95["ci95"]
    est = x95["est"]
    if lo > 0:
        case, text = "precision_excess", f"{what}: precision-specific excess {est:+.1f} pp [{lo:+.1f}, {hi:+.1f}]"
    elif hi < 0:
        case, text = "same_larger", f"{what}: same-precision at least as large (95% interval excludes 0, diff < 0)"
    elif t.get("equivalent"):
        case, text = "equivalent", (f"{what}: equivalent within ±{t['eps_pp']:.0f} pp (TOST p = {t['p_tost']:.3f}; "
                                    f"90% CI [{t['t_ci90'][0]:+.2f}, {t['t_ci90'][1]:+.2f}])")
    else:
        case, text = "not_shown_equivalent", (f"{what}: no precision-specific excess detected, but equivalence at ±{t['eps_pp']:.0f} pp "
                                              f"is NOT shown (TOST p = {t['p_tost']:.3f}; 90% CI [{t['t_ci90'][0]:+.2f}, {t['t_ci90'][1]:+.2f}])")
    return {"case": case, "text": text, "est": est, "ci95": x95["ci95"], "tost": {k: t[k] for k in ("t_ci90", "p_lower", "p_upper", "p_tost", "equivalent")}}


def dirs_under(rel: str) -> list[Path]:
    out = []
    for p in sorted(glob.glob(str(ROOT / rel / "**" / "search.json"), recursive=True)):
        d = Path(p).parent
        if (d / "states").is_dir() and (d / "branches").is_dir():
            assert "/holdout/" not in str(d)
            out.append(d)
    return out


def admit(dirs: list[Path], snap: dict) -> tuple[list[dict], list[dict], dict]:
    loaded = [AD.load_dir(d, snap, {}) for d in dirs]
    allu = [u for L in loaded for u in L["units"]]
    AD.split_guard(allu, "dev", "analyze_sameprec")
    for L in loaded:
        if L["quarantined"]:
            for u in L["units"]:
                u.setdefault("excluded", "quarantined fork task (QQ no-op mismatch)")
    units, _ = AD.dedupe_units(allu)
    AD.mark_incomplete_blocks(units, "dev", strict=True)
    AD.mark_partial_panel_blocks(units, "dev")
    units = [u for u in units if u["cell"] == CELL and u["domain"] in PANEL]
    for u in units:
        if "Y" in u:
            u["E"] = AD.effects(u["Y"], u["div"])
            if u["div"]:
                GH.add_E(u)
    noop = [x for L in loaded for x in L["noop"]]
    meta = {"dirs": [L["dir"] for L in loaded], "quarantined": [L["dir"] for L in loaded if L["quarantined"]],
            "noop_sample": {"n": len(noop), "n_pass": sum(x["ok"] for x in noop)},
            "files_digest": hashlib.sha256(json.dumps({k: v for L in loaded for k, v in L["files"].items()}, sort_keys=True).encode()).hexdigest()}
    return units, loaded, meta


def acceptance(units: list[dict]) -> dict:
    """Q replay at the state; prefix_ok and env_hash_init_ok of every branch (counts only; exclusion is via quarantine)."""
    n = qr = br = brok = 0
    for u in units:
        if not u.get("div") or "excluded" in u:
            continue
        d = ROOT / u["dir"]
        st = json.load(open(d / "states" / f"{u['state_id']}.json"))
        r4 = json.load(open(d / "branches" / f"{u['state_id']}.json"))
        n += 1
        qr += int(all((st.get("q_replay") or {}).values()) and bool(st.get("q_replay")))
        for b, r in r4.items():
            br += 1
            brok += int(bool(r.get("prefix_ok")) and bool(r.get("env_hash_init_ok")))
    return {"states": n, "q_replay_ok": qr, "branches": br, "prefix_and_env_ok": brok}


def complete_blocks(units: list[dict], m: str) -> set:
    """Blocks of model m with both panel domains admitted (strict + W78 rules already applied)."""
    have = defaultdict(set)
    for u in units:
        if u["model"] == m and "excluded" not in u:
            have[u["block"]].add(u["domain"])
    return {b for b, ds in have.items() if set(PANEL) <= ds}


def per_block(units: list[dict]) -> dict:
    """Every block with units: found / admitted, complete flag, states, divergence rate, r, d, M, G (block means)."""
    out = {}
    g = defaultdict(list)
    for u in units:
        g[(u["model"], u["block"])].append(u)
    for (m, b), us in sorted(g.items()):
        y = [u for u in us if "Y" in u and (("excluded" not in u) or u["excluded"].startswith(("incomplete block", "partial-panel")))]
        row = {"units_found": len(us), "units_with_outcomes": len(y), "admitted": sum(1 for u in us if "excluded" not in u),
               "complete": all("excluded" not in u for u in us) and {u["domain"] for u in us} >= set(PANEL)
               and len(us) == sum(AD.panel_task_counts().values()),
               "excluded_by_reason": dict(sorted(defaultdict(int, {r: sum(1 for u in us if u.get("excluded") == r)
                                                                   for r in {u.get("excluded") for u in us if u.get("excluded")}}).items()))}
        if y:
            # retail/airline weights 58/85, 27/85 only when complete; otherwise plain unit mean (labelled)
            row["states"] = sum(1 for u in y if u["div"])
            row["divergence_rate_pct"] = round(100 * row["states"] / len(y), 2)
            for k in ("rescue", "damage", "M", "G"):
                row[f"{k}_pct"] = round(100 * float(np.mean([u["E"][k] for u in y])), 2)
            dv = [u for u in y if u["div"]]
            row["offdiag_pct"] = round(100 * float(np.mean([u["E"]["offdiag"] for u in dv])), 2) if dv else None
        out[f"{m}|{b}"] = row
    return out


def pair_units(prec: list[dict], same: list[dict]) -> list[dict]:
    key = lambda u: (u["model"], u["domain"], u["task"], u["block"])  # noqa: E731
    sp = {key(u): u for u in same}
    out = []
    for p in prec:
        s = sp.get(key(p))
        if s is None:
            continue
        E = {f"d{k}": p["E"][k] - s["E"][k] for k in ("M", "rescue", "damage", "G")}
        E["both_div"] = int(p["div"] and s["div"])
        E["same_t"] = int(p["div"] and s["div"] and p["t"] == s["t"])
        E["div_prec"], E["div_same"] = int(p["div"]), int(s["div"])
        E["d_div"] = E["div_prec"] - E["div_same"]
        if p["div"] and s["div"]:
            E["off_prec"], E["off_same"] = p["E"]["offdiag"], s["E"]["offdiag"]
            E["d_off"] = E["off_prec"] - E["off_same"]
        else:
            E["off_prec"] = E["off_same"] = E["d_off"] = None
        out.append({"model": p["model"], "domain": p["domain"], "task": p["task"], "block": p["block"], "div": True, "E": E,
                    "t_prec": p.get("t"), "t_same": s.get("t")})
    return out


def full_stat(boot, us, key):
    pt, dr = boot.task_mean(*boot.arrays(us, key))
    return pt, dr


def ratio_stat(boot, us, key, mask=None):
    sub = [u for u in us if (mask is None or u["E"].get(mask))]
    pt, dr = boot.ratio(*boot.arrays(sub, key))
    return pt, dr


def pool_pairs(vals: list[tuple]) -> dict:
    """Equal-weight pool of (pt, Draws) pairs on shared draws: block bootstrap mean, t over pooled block means, crossed."""
    pt = float(np.mean([v[0] for v in vals]))
    dr = np.mean([np.asarray(v[1]) for v in vals], axis=0)
    bms = [v[1].block_means for v in vals]
    t = AD.t_interval(np.nanmean(np.vstack(bms), axis=0)) if all(b is not None for b in bms) else None
    cr = (float(np.mean([v[1].crossed_pt for v in vals])), np.mean([v[1].crossed for v in vals], axis=0))
    return AD.summarise(pt, dr, t=t, crossed=cr)


def diff_pair(a: tuple, b: tuple) -> tuple:
    """(pt, Draws) of a - b on the shared draws (ratio statistics of two designs)."""
    pa, da = a
    pb, db = b
    bm = np.asarray(da.block_means) - np.asarray(db.block_means)
    return pa - pb, AD.Draws(np.asarray(da) - np.asarray(db), AD.t_interval(bm), np.asarray(da.crossed) - np.asarray(db.crossed),
                             da.crossed_pt - db.crossed_pt, bm)


def reading(x: dict, few: float, what: str) -> dict:
    lo, hi = x["ci95"]
    est = x["est"]
    inc0 = lo <= 0 <= hi
    if inc0 and abs(est) <= few:
        case, text = "similar", f"{what}: similar under same precision (interval includes 0, |diff| <= {few} pp) -> generic trajectory sensitivity"
    elif lo > 0:
        case, text = "precision_excess", f"{what}: precision-specific excess {est:+.1f} pp [{lo:+.1f}, {hi:+.1f}]"
    elif hi < 0:
        case, text = "same_larger", f"{what}: same-precision at least as large (interval excludes 0, diff < 0)"
    else:
        case, text = "unresolved", f"{what}: not resolved by this control (interval includes 0, |diff| > {few} pp)"
    return {"case": case, "text": text, "est": est, "ci95": x["ci95"], "primary": x.get("primary")}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--B", type=int, default=AD.B_BOOT)
    ap.add_argument("--max-k", type=int, default=None, help="interim look: first K prefix blocks only (labelled)")
    a = ap.parse_args()
    t0 = time.time()
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    man = json.load(open(MANIFEST))
    psha = guard(man)
    snap = json.load(open(ROOT / man["snapshot"]))
    models = man["cells"]
    U, M = {}, {}
    for des, key in (("prec", "precision_dirs"), ("same", "sameprec_dirs")):
        dirs = [d for m in models for d in dirs_under(man[key][m])]
        U[des], _, M[des] = admit(dirs, snap)
    blocks_all = {des: {m: complete_blocks(U[des], m) for m in models} for des in DESIGNS}
    prefix = []
    for b in man["blocks_ordered"]:
        if all(b in blocks_all[des][m] for des in DESIGNS for m in models):
            prefix.append(b)
        else:
            break
    full_prefix = list(prefix)
    if a.max_k is not None:
        prefix = prefix[:a.max_k]
    K = len(prefix)
    res = {"protocol": man["protocol"], "protocol_sha256": psha, "manifest": str(MANIFEST.relative_to(ROOT)),
           "script_sha256": AD.sha256(__file__), "analyze_dev_sha256": AD.sha256(AD.__file__), "analyze_ghf_sha256": AD.sha256(GH.__file__),
           "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
           "utc": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), "snapshot": man["snapshot"], "B": a.B, "seed": AD.SEED,
           "mapping": {"BB": "Q'Q'", "BQ": "Q'Q", "QB": "QQ'", "QQ": "QQ"},
           "admission_meta": M, "complete_blocks": {d: {m: sorted(v) for m, v in x.items()} for d, x in blocks_all.items()},
           "analysis_set": {"blocks": prefix, "K": K, "rule": "longest prefix of blocks_ordered complete in both cells and both designs",
                            "complete_prefix_K": len(full_prefix), "capped_by_max_k": a.max_k,
                            "status": "INTERIM (before the 2026-10-03 evidence freeze)" if time.gmtime() < time.strptime("2026-10-04T07", "%Y-%m-%dT%H") else "freeze"},
           "per_block": {d: per_block(U[d]) for d in DESIGNS}}
    if K >= 1:
        sel = {d: [u for u in U[d] if "excluded" not in u and u["block"] in prefix] for d in DESIGNS}
        bo = defaultdict(set)
        for d in DESIGNS:
            for u in sel[d]:
                bo[u["task"]].add(u["block"])
        boot = AD.Boot(sorted(bo), {t: sorted(v) for t, v in bo.items()}, B=a.B)
        cells, pairs_by = {}, {}
        for m in models:
            c = {}
            for d in DESIGNS:
                us = [u for u in sel[d] if u["model"] == m]
                div = [u for u in us if u["div"]]
                r = {"n_units": len(us), "n_states": len(div), "divergence_rate_pct": round(100 * len(div) / max(1, len(us)), 2),
                     "full_pp": {k: AD.summarise(*full_stat(boot, us, k)) for k in FULL}}
                r["cond_pp"] = {k: AD.summarise(*ratio_stat(boot, div, k)) for k in CONDK} if div else {}
                r["table3"] = GH.table3(div)
                r["patterns16"] = GH.patterns16(div)
                r["acceptance"] = acceptance(us)
                c[d] = r
            pu = pair_units([u for u in sel["prec"] if u["model"] == m], [u for u in sel["same"] if u["model"] == m])
            pairs_by[m] = pu
            c["paired"] = {"n_pairs": len(pu), "n_both_div": sum(u["E"]["both_div"] for u in pu), "n_same_t": sum(u["E"]["same_t"] for u in pu)}
            c["paired"]["full_pp"] = {k: AD.summarise(*full_stat(boot, pu, k)) for k in ("dM", "drescue", "ddamage", "dG", "d_div")}
            divp = [u for u in sel["prec"] if u["model"] == m and u["div"]]
            divs = [u for u in sel["same"] if u["model"] == m and u["div"]]
            c["paired"]["d_offdiag_pp"] = AD.summarise(*diff_pair(ratio_stat(boot, divp, "offdiag"), ratio_stat(boot, divs, "offdiag"))) if divp and divs else None
            c["paired"]["d_strict_reversal_pp"] = AD.summarise(*diff_pair(ratio_stat(boot, divp, "strict_reversal"), ratio_stat(boot, divs, "strict_reversal"))) if divp and divs else None
            for lab, mask in (("a_both_div", "both_div"), ("b_same_t", "same_t")):
                sub = [u for u in pu if u["E"][mask]]
                c["paired"][lab] = ({"n": len(sub), "off_prec_pp": AD.summarise(*ratio_stat(boot, sub, "off_prec")),
                                     "off_same_pp": AD.summarise(*ratio_stat(boot, sub, "off_same")),
                                     "d_off_pp": AD.summarise(*ratio_stat(boot, sub, "d_off"))} if sub else {"n": 0})
            cells[m] = c
        res["cells"] = cells
        # pooled q4 + q8, equal weight on the shared draws
        pool = {"prec": {}, "same": {}, "paired": {}}
        for d in DESIGNS:
            for k in FULL:
                pool[d][k] = pool_pairs([full_stat(boot, [u for u in sel[d] if u["model"] == m], k) for m in models])
            for k in ("offdiag", "strict_reversal", "G", "H", "F", "I"):
                pool[d][f"cond_{k}"] = pool_pairs([ratio_stat(boot, [u for u in sel[d] if u["model"] == m and u["div"]], k) for m in models])
            pool[d]["divergence_rate_pct"] = round(float(np.mean([cells[m][d]["divergence_rate_pct"] for m in models])), 2)
            pool[d]["table3_counts_summed"] = {k: sum(cells[m][d]["table3"]["counts"][k] for m in models) for k in cells[models[0]][d]["table3"]["counts"]}
            pool[d]["n_states"] = sum(cells[m][d]["n_states"] for m in models)
        for k in ("dM", "drescue", "ddamage", "dG", "d_div"):
            pool["paired"][k] = pool_pairs([full_stat(boot, pairs_by[m], k) for m in models])
        pool["paired"]["d_offdiag"] = pool_pairs([diff_pair(ratio_stat(boot, [u for u in sel["prec"] if u["model"] == m and u["div"]], "offdiag"),
                                                            ratio_stat(boot, [u for u in sel["same"] if u["model"] == m and u["div"]], "offdiag")) for m in models])
        for lab, mask in (("a_both_div", "both_div"), ("b_same_t", "same_t")):
            subs = [[u for u in pairs_by[m] if u["E"][mask]] for m in models]
            if all(subs):
                pool["paired"][lab] = {"n": sum(len(s) for s in subs), **{k: pool_pairs([ratio_stat(boot, s, kk) for s in subs])
                                                                          for k, kk in (("off_prec_pp", "off_prec"), ("off_same_pp", "off_same"), ("d_off_pp", "d_off"))}}
        res["pooled"] = pool
        few = float(man["few_pp"])
        if K >= int(man["min_blocks_reading"]):
            rm = reading(pool["paired"]["dM"], few, "Turnover M (paired, primary)")
            ro = reading(pool["paired"]["d_offdiag"], few, "Off-diagonal share (DESCRIPTIVE: different state sets)")
            both = rm["case"] == "similar" and ro["case"] == "similar"
            res["reading"] = {"K": K, "few_pp": few, "M": rm, "offdiag": ro,
                              "per_cell": {m: {"M": reading(cells[m]["paired"]["full_pp"]["dM"], few, f"{m} M"),
                                               "offdiag": reading(cells[m]["paired"]["d_offdiag_pp"], few, f"{m} off-diagonal (descriptive)")}
                                           for m in models if cells[m]["paired"]["d_offdiag_pp"]},
                              "frozen_statement": ("The paper must say that turnover and controller dependence largely reflect generic trajectory "
                                                   "sensitivity of the closed loop rather than precision-specific effects." if both else
                                                   "The paper must say that the turnover largely reflects generic trajectory sensitivity of the closed loop "
                                                   "rather than a precision-specific effect." if rm["case"] == "similar" else
                                                   f"The paper reports the precision-specific excess in turnover: ΔM {rm['est']:+.1f} pp "
                                                   f"[{rm['ci95'][0]:+.1f}, {rm['ci95'][1]:+.1f}], {100 * rm['est'] / max(1e-9, pool['prec']['M']['est']):.0f}% of M_prec."
                                                   if rm["case"] == "precision_excess" else rm["text"])}
        else:
            res["reading"] = {"K": K, "note": f"fewer than {man['min_blocks_reading']} complete prefix blocks: no reading (protocol §2); per-block numbers only"}
        if "frozen_statement" in res["reading"]:
            res["reading"]["status"] = "SUPERSEDED by amendment A1 (the 'similar' case was an incorrect equivalence reading); see reading_a1"
        # ---- Amendment A1 (W99l-c): TOST at +-3 pp; the estimates above are unchanged ----
        divs_of = lambda d, m: [u for u in sel[d] if u["model"] == m and u["div"]]  # noqa: E731
        vals = {"dM": {m: full_stat(boot, pairs_by[m], "dM") for m in models},
                "dG": {m: full_stat(boot, pairs_by[m], "dG") for m in models},
                "d_offdiag": {m: diff_pair(ratio_stat(boot, divs_of("prec", m), "offdiag"), ratio_stat(boot, divs_of("same", m), "offdiag"))
                              for m in models if divs_of("prec", m) and divs_of("same", m)}}
        ta = {"eps_pp": EPS_PP, "method": "TOST, t over the K pooled per-block differences (df = K - 1); 90% CI; p_lower: H0 diff <= -eps; p_upper: H0 diff >= +eps",
              "pooled": {k: tost(list(v.values())) for k, v in vals.items() if len(v) == len(models)},
              "per_cell": {m: {k: tost([v[m]]) for k, v in vals.items() if m in v} for m in models}}
        # Consistency with the frozen primary pipeline (W100h fix). dM / dG are unit means (Boot.task_mean): the point estimate
        # IS the mean of block means, so it must equal the TOST centre. d_offdiag is a ratio over divergent states
        # (Boot.ratio): its point estimate is the ratio of block SUMS (pooled over blocks), while its frozen primary interval
        # at K < 10 (t over per-block ratios) and the A1 TOST are centred on the MEAN of per-block ratios. The two agree only
        # when every block has the same number of states (W4 K = 6 passed by coincidence, 0.006 pp); so d_offdiag is checked
        # against the centre of the frozen pooled t interval, and both centres are recorded.
        ta["consistency"] = {}
        for k, x in ta["pooled"].items():
            pe = pool["paired"][k]
            if k == "d_offdiag":
                ref = (pe["t_ci95"][0] + pe["t_ci95"][1]) / 2 if pe.get("t_ci95") else x["est"]
                ta["consistency"][k] = {"tost_centre_mean_of_block_ratios": x["est"], "primary_t_centre": round(ref, 3),
                                        "point_est_ratio_of_block_sums": pe["est"],
                                        "note": "different estimators of the same share; equal only with equal state counts per block"}
            else:
                ref = pe["est"]
                ta["consistency"][k] = {"tost_centre": x["est"], "point_est": ref}
            assert abs(x["est"] - ref) < 0.01, (k, x["est"], ref)
        res["tost_a1"] = ta
        if K >= int(man["min_blocks_reading"]):
            P = pool
            ra = {k: reading_a1(P["paired"][kk], ta["pooled"][kk], lab) for k, kk, lab in
                  (("M", "dM", "Turnover M (paired, primary)"), ("G_all", "dG", "Net G_all (paired)"),
                   ("offdiag", "d_offdiag", "Off-diagonal share (DESCRIPTIVE: different state sets)")) if kk in ta["pooled"]}
            ra["per_cell"] = {m: {k: reading_a1(cells[m]["paired"]["full_pp"]["dM"] if k == "dM" else cells[m]["paired"]["full_pp"]["dG"] if k == "dG"
                                                else cells[m]["paired"]["d_offdiag_pp"], ta["per_cell"][m][k], f"{m} {k}")
                                  for k in ta["per_cell"][m]} for m in models}
            two_sided = all(P["same"][k]["ci95"][0] > 0 for k in ("rescue", "damage", "cond_offdiag"))
            defensible = ("A higher bit width is not necessary for two-sided flips and controller dependence; they also appear when only the "
                          f"W4 calibration checkpoint is swapped (d1 → d2): r′ {P['same']['rescue']['est']:.1f}, d′ {P['same']['damage']['est']:.1f}, "
                          f"M′ {P['same']['M']['est']:.1f} pp of units, off-diagonal′ {P['same']['cond_offdiag']['est']:.1f}% of divergent states.")
            cm = ra["M"]["case"]
            st = (defensible + " " if two_sided else "") + (
                f"Turnover is equivalent between the designs within ±3 pp (TOST p = {ta['pooled']['dM']['p_tost']:.3f})." if cm == "equivalent" else
                f"No precision-specific excess in turnover was detected (ΔM {ra['M']['est']:+.1f} pp), but equivalence at ±3 pp is not shown "
                f"(90% CI [{ta['pooled']['dM']['t_ci90'][0]:+.2f}, {ta['pooled']['dM']['t_ci90'][1]:+.2f}], TOST p = {ta['pooled']['dM']['p_tost']:.3f}); "
                "the paper must not call the designs similar or the turnover not precision-specific." if cm == "not_shown_equivalent" else ra["M"]["text"])
            ra.update({"K": K, "two_sided_same_precision": two_sided, "defensible_statement": defensible if two_sided else None, "statement": st})
            res["reading_a1"] = ra
    # context: precision M on all its complete blocks
    res["precision_all_blocks"] = {}
    for m in models:
        us = [u for u in U["prec"] if u["model"] == m and "excluded" not in u]
        if us:
            bo = defaultdict(set)
            for u in us:
                bo[u["task"]].add(u["block"])
            bt = AD.Boot(sorted(bo), {t: sorted(v) for t, v in bo.items()}, B=a.B)
            res["precision_all_blocks"][m] = {"K": len({u["block"] for u in us}), "M_pp": AD.summarise(*full_stat(bt, us, "M"))}
    res["seconds"] = round(time.time() - t0, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    tag = res["utc"] + (f"_capK{K}" if a.max_k is not None else "")
    jp = OUT / f"sameprec_{tag}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else sorted(o) if isinstance(o, set) else str(o)))
    (OUT / f"sameprec_{tag}.md").write_text(markdown(res, jp))
    print(f"analyze_sameprec: wrote {jp.relative_to(ROOT)} (K = {K}, {res['seconds']} s)")


def markdown(r: dict, jp: Path) -> str:
    def f(x):
        return "n/a" if not x else f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}]"

    def fr(x):
        return "n/a" if not x else f"{x['est']:.1f} [{x['ci95'][0]:.1f}, {x['ci95'][1]:.1f}]"

    def cx(x):
        return f"[{x['crossed_ci95'][0]:+.1f}, {x['crossed_ci95'][1]:+.1f}]" if x and "crossed_ci95" in x else "n/a"
    K = r["analysis_set"]["K"]
    L = []
    if K and r.get("pooled"):
        P = r["pooled"]
        rd = r["reading"]
        tl = (f"**TL;DR** Same-precision control (Q′ = GPTQ-W4 d2 in place of BF16; Q = GPTQ-W4 d1), q4+q8 pooled on K = {K} blocks "
              f"({r['analysis_set']['blocks'][0]}–{r['analysis_set']['blocks'][-1]}), 85 tasks each. Turnover M: precision {fr(P['prec']['M'])} vs "
              f"same-precision {fr(P['same']['M'])} pp; paired ΔM {f(P['paired']['dM'])} pp ({P['paired']['dM']['primary']}; crossed {cx(P['paired']['dM'])}). "
              f"Off-diagonal share (descriptive): {fr(P['prec']['cond_offdiag'])} vs {fr(P['same']['cond_offdiag'])}%, Δ {f(P['paired']['d_offdiag'])} pp. "
              f"Divergence rate {P['prec']['divergence_rate_pct']:.1f}% vs {P['same']['divergence_rate_pct']:.1f}%. ")
        ra = r.get("reading_a1")
        if ra:
            tm = r["tost_a1"]["pooled"]["dM"]
            tl += (f"**Amendment A1 (TOST ±3 pp):** ΔM 90% CI [{tm['t_ci90'][0]:+.2f}, {tm['t_ci90'][1]:+.2f}], p_lower {tm['p_lower']:.3f}, "
                   f"p_upper {tm['p_upper']:.3f} → {'equivalent' if tm['equivalent'] else 'equivalence NOT shown'}. Reading: " + ra["statement"])
            tl += f" ({r['analysis_set']['status']}; the frozen §6 'similar' reading is superseded.)"
        else:
            tl += ("Frozen reading: " + rd["frozen_statement"]) if "frozen_statement" in rd else rd.get("note", "")
        L += [tl, ""]
    else:
        L += [f"**TL;DR** Same-precision control: no complete prefix block yet (K = {K}); per-block numbers below.", ""]
    L += [f"# Same-precision 2×2 fork (Q vs Q′) ({r['utc']})", "",
          f"Protocol `{r['protocol']}` sha256 {r['protocol_sha256'][:16]} (verified); manifest `{r['manifest']}`; script sha {r['script_sha256'][:12]}, "
          f"analyze_dev {r['analyze_dev_sha256'][:12]}, analyze_ghf {r['analyze_ghf_sha256'][:12]}, git {r['git_head'][:10]}. Full numbers: `{jp.relative_to(ROOT)}`.",
          "Arm mapping (driver → same-precision): BB = Q′Q′, BQ = Q′Q, QB = QQ′, QQ = QQ. Admission = analyze_dev (strict complete blocks, 85-task panel). "
          "Intervals: fixed pool = t over block means when K < 10, block bootstrap when K ≥ 10 (both in JSON); crossed task × block = generalisation.", "",
          f"Analysis set: {r['analysis_set']['blocks'] or 'none'} (rule: {r['analysis_set']['rule']}). Complete blocks: "
          + "; ".join(f"{d} {m}: {','.join(v) or '-'}" for d, x in r["complete_blocks"].items() for m, v in x.items()), ""]
    if K and r.get("cells"):
        rd = r["reading"]
        if r.get("tost_a1"):
            L += ["## Amendment A1: equivalence by TOST at ±3 pp (W99l-c; added, primary estimates unchanged)", "",
                  f"Method: {r['tost_a1']['method']}.", "",
                  "| scope | contrast | est (pp) | 90% CI (t) | 90% CI (block boot) | p_lower (H0 ≤ −3) | p_upper (H0 ≥ +3) | p_TOST | equivalent |",
                  "|---|---|---|---|---|---|---|---|---|"]
            for sc, d in [("pool", r["tost_a1"]["pooled"])] + list(r["tost_a1"]["per_cell"].items()):
                for k, x in d.items():
                    if "est" in x:
                        bb = x["block_boot_ci90"]
                        L.append(f"| {sc} | {k}{' (descriptive)' if k == 'd_offdiag' else ''} | {x['est']:+.2f} | [{x['t_ci90'][0]:+.2f}, {x['t_ci90'][1]:+.2f}] | "
                                 f"{'[%+.2f, %+.2f]' % tuple(bb) if bb else 'n/a'} | {x['p_lower']:.3f} | {x['p_upper']:.3f} | {x['p_tost']:.3f} | {'yes' if x['equivalent'] else 'no'} |")
            co = r["tost_a1"].get("consistency", {}).get("d_offdiag")
            if co:
                L += ["", f"d_offdiag centres: TOST / t interval = mean of per-block ratio differences {co['tost_centre_mean_of_block_ratios']:+.2f}; "
                          f"point estimate = ratio of block sums {co['point_est_ratio_of_block_sums']:+.2f} (equal only with equal state counts per block)."]
            ra = r.get("reading_a1")
            if ra:
                L += ["", "A1.3 reading (pooled):", ""] + [f"- {ra[k]['text']}" for k in ("M", "G_all", "offdiag") if k in ra]
                L += [f"- per cell (secondary) {m}: " + "; ".join(f"{k} {x['case']}" for k, x in v.items()) for m, v in ra["per_cell"].items()]
                L += [f"- **Statement (A1):** {ra['statement']}", ""]
        if "M" in rd:
            L += ["## Frozen reading (protocol §6, pooled q4+q8) — SUPERSEDED by amendment A1 (incorrect equivalence reading; kept for the record)", "", f"- {rd['M']['text']} — ΔM {f(rd['M'])} ({rd['M']['primary']})",
                  f"- {rd['offdiag']['text']} — Δoff {f(rd['offdiag'])}", f"- **Statement:** {rd['frozen_statement']}"]
            for m, x in rd["per_cell"].items():
                L.append(f"- per cell {m} (secondary): {x['M']['case']} (ΔM {f(x['M'])}); off-diagonal {x['offdiag']['case']} ({f(x['offdiag'])})")
            L.append("")
        L += ["## Full pool (task × block units; pp)", "", "| cell | design | units | states (div. rate) | r | d | M | G_all |", "|---|---|---|---|---|---|---|---|"]
        for m, c in r["cells"].items():
            for d, lab in (("prec", "precision (B = BF16)"), ("same", "same-precision (Q′ = d2)")):
                x = c[d]
                L.append(f"| {m} | {lab} | {x['n_units']} | {x['n_states']} ({x['divergence_rate_pct']:.1f}%) | {fr(x['full_pp']['rescue'])} | "
                         f"{fr(x['full_pp']['damage'])} | {fr(x['full_pp']['M'])} | {f(x['full_pp']['G'])} |")
        P = r["pooled"]
        for d, lab in (("prec", "precision"), ("same", "same-precision")):
            L.append(f"| pool q4+q8 | {lab} | | {P[d]['n_states']} ({P[d]['divergence_rate_pct']:.1f}%) | {fr(P[d]['rescue'])} | {fr(P[d]['damage'])} | {fr(P[d]['M'])} | {f(P[d]['G'])} |")
        L += ["", "## Paired differences (precision − same-precision, same units)", "",
              "| cell | pairs | ΔM (primary) | ΔM crossed | Δr | Δd | ΔG_all | Δ divergence rate | Δ off-diagonal (descriptive) |", "|---|---|---|---|---|---|---|---|---|"]
        for m, c in r["cells"].items():
            p = c["paired"]
            L.append(f"| {m} | {p['n_pairs']} | {f(p['full_pp']['dM'])} | {cx(p['full_pp']['dM'])} | {f(p['full_pp']['drescue'])} | {f(p['full_pp']['ddamage'])} | "
                     f"{f(p['full_pp']['dG'])} | {f(p['full_pp']['d_div'])} | {f(p['d_offdiag_pp'])} |")
        pp = P["paired"]
        L.append(f"| pool | | {f(pp['dM'])} | {cx(pp['dM'])} | {f(pp['drescue'])} | {f(pp['ddamage'])} | {f(pp['dG'])} | {f(pp['d_div'])} | {f(pp['d_offdiag'])} |")
        L += ["", "## On divergent states (ratio of block sums; pp)", "",
              "| cell | design | states | G | H | F | I | off-diagonal | strict reversal |", "|---|---|---|---|---|---|---|---|---|"]
        for m, c in r["cells"].items():
            for d in DESIGNS:
                x = c[d]["cond_pp"]
                if x:
                    L.append(f"| {m} | {d} | {c[d]['n_states']} | {f(x['G'])} | {f(x['H'])} | {f(x['F'])} | {f(x['I'])} | {fr(x['offdiag'])} | {fr(x['strict_reversal'])} |")
        for d in DESIGNS:
            L.append(f"| pool | {d} | {P[d]['n_states']} | {f(P[d]['cond_G'])} | {f(P[d]['cond_H'])} | {f(P[d]['cond_F'])} | {f(P[d]['cond_I'])} | "
                     f"{fr(P[d]['cond_offdiag'])} | {fr(P[d]['cond_strict_reversal'])} |")
        L += ["", "Same-precision notation: G′ = Y_Q′Q − Y_QQ, H′ = Y_QQ′ − Y_QQ, F′ = Y_Q′Q′ − Y_QQ, Δ_Q = Y_Q′Q − Y_QQ, Δ_Q′ = Y_Q′Q′ − Y_QQ′.", "",
              "3×3 (Δ_Q, Δ_partner) counts, summed over q4+q8 (rows Δ_Q −1/0/+1, columns Δ_partner −1/0/+1):", ""]
        for d in DESIGNS:
            t3 = P[d]["table3_counts_summed"]
            L.append(f"- {d}: " + " | ".join(" ".join(str(t3[f'{a},{b}']) for b in (-1, 0, 1)) for a in (-1, 0, 1)))
        L += ["", "Off-diagonal per state, conditional on divergence in both designs (descriptive):", ""]
        for m, c in list(r["cells"].items()) + [("pool", {"paired": P["paired"]})]:
            for lab in ("a_both_div", "b_same_t"):
                x = c["paired"].get(lab) or {}
                if x.get("n"):
                    L.append(f"- {m} {lab}: n {x['n']}; precision {fr(x['off_prec_pp'])}, same-precision {fr(x['off_same_pp'])}, Δ {f(x['d_off_pp'])}")
        L += ["", "Acceptance (counts; exclusion only via quarantine, as in the precision analysis):", ""]
        for m, c in r["cells"].items():
            for d in DESIGNS:
                L.append(f"- {m} {d}: {c[d]['acceptance']}")
        L.append(f"- QQ no-op samples: prec {r['admission_meta']['prec']['noop_sample']}, same {r['admission_meta']['same']['noop_sample']}; "
                 f"quarantined dirs: {r['admission_meta']['prec']['quarantined'] + r['admission_meta']['same']['quarantined'] or 'none'}")
    L += ["", "Precision 2×2 on all its complete blocks (context): " + "; ".join(f"{m}: M {fr(x['M_pp'])} on {x['K']} blocks" for m, x in r["precision_all_blocks"].items()),
          "", "## Per block (every block with units; partial completion)", "",
          "| design | model\\|block | found | admitted | complete | states | div. rate | r | d | M | G | off-diag |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for d in DESIGNS:
        for k, x in r["per_block"][d].items():
            if d == "prec" and k.split("|")[1] not in (r["analysis_set"]["blocks"] or []) and not any(k in r["per_block"]["same"] for _ in [0]):
                continue
            L.append(f"| {d} | {k} | {x['units_found']} | {x['admitted']} | {x['complete']} | {x.get('states', '')} | {x.get('divergence_rate_pct', '')} | "
                     f"{x.get('rescue_pct', '')} | {x.get('damage_pct', '')} | {x.get('M_pct', '')} | {x.get('G_pct', '')} | {x.get('offdiag_pct', '')} |")
    L.append("\nPer-block r/d/M/G are plain unit means over units with outcomes (incomplete blocks included and flagged).")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
