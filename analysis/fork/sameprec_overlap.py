"""Unit and task overlap of the precision and same-precision 2x2 forks (W99l-c; DESCRIPTIVE / exploratory, protocol
docs/insights/SAMEPREC_PROTOCOL.md amendment A1.4; does not enter the reading).

Question: do similar average turnover values (M_prec ~ M') correspond to the SAME sensitive task x block units / tasks,
or to different ones?

Units: exactly the primary analysis set of analyze_sameprec.py (imported: protocol guard, admission = analyze_dev rules,
longest prefix of the manifest's blocks complete in both cells and both designs), paired task x block units admitted in
both designs, cells q4 and q8 (GPTQ-W4 d1 = Q; BF16 = B in the precision design; GPTQ-W4 d2 = Q' in the same-precision one).

Per unit: M = 1 iff Y_BQ != Y_QQ in the precision design (rescue r: Y_BQ = 1, Y_QQ = 0; damage d: Y_BQ = 0, Y_QQ = 1;
no divergence -> 0); M' the same with Q' in place of B. Secondary flag M_any: any of the B-involving arms (BB, BQ, QB) != QQ.
Overlap 2x2 (both / only BF16 / only d2 / neither) with directions; direction agreement among "both"; Cohen's kappa on
(M, M') with its marginal-preserving null (permutation of M' within cell x block strata; also within cell x block x Y_QQ),
kappa_max given the marginals, and a block-bootstrap interval. Task level: per-task flip rate over the K blocks in each
design, Pearson / Spearman between designs, compared with the within-design split-half (disjoint block halves) replication
correlation at the same noise level (cross-design vs within-design over all balanced block splits), and a task-permutation
null. Concentration: share of flips in the top 10% / 20% of tasks, Jaccard of the "ever flips" task sets.

Reported for K = 6 (f01-f06, the interim Report 6 set) and for the current complete prefix K if larger (labelled INTERIM
before the 2026-10-03 freeze).

usage: python analysis/fork/sameprec_overlap.py [--perm 10000]  ->  analysis/fork/out/sameprec_overlap_<UTC>.{md,json}
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import pearsonr, spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD  # noqa: E402
import analyze_sameprec as SP  # noqa: E402

ROOT, OUT = AD.ROOT, AD.OUT
SEED = 20261002
CELLS = ("both", "only_bf16", "only_d2", "neither")


def load(man: dict, snap: dict):
    U = {}
    for des, key in (("prec", "precision_dirs"), ("same", "sameprec_dirs")):
        dirs = [d for m in man["cells"] for d in SP.dirs_under(man[key][m])]
        U[des], _, _ = SP.admit(dirs, snap)
    blocks_all = {des: {m: SP.complete_blocks(U[des], m) for m in man["cells"]} for des in SP.DESIGNS}
    prefix = []
    for b in man["blocks_ordered"]:
        if all(b in blocks_all[des][m] for des in SP.DESIGNS for m in man["cells"]):
            prefix.append(b)
        else:
            break
    return U, prefix


def unit_rows(U: dict, blocks: list[str], models: list[str]) -> list[dict]:
    key = lambda u: (u["model"], u["domain"], u["task"], u["block"])  # noqa: E731
    S = {key(u): u for u in U["same"] if "excluded" not in u and u["block"] in blocks}
    rows = []
    for p in U["prec"]:
        if "excluded" in p or p["block"] not in blocks or p["model"] not in models:
            continue
        s = S.get(key(p))
        if s is None:
            continue

        def anyarm(u):
            if not u["div"]:
                return 0
            Y = u["Y"]
            return int(any(Y[a] != Y["QQ"] for a in ("BB", "BQ", "QB")))
        rows.append({"model": p["model"], "domain": p["domain"], "task": p["task"], "block": p["block"],
                     "yqq_p": p["Y"]["QQ"], "yqq_s": s["Y"]["QQ"], "div_p": int(p["div"]), "div_s": int(s["div"]),
                     "M": p["E"]["M"], "r": p["E"]["rescue"], "d": p["E"]["damage"],
                     "Ms": s["E"]["M"], "rs": s["E"]["rescue"], "ds": s["E"]["damage"],
                     "Many": anyarm(p), "Manys": anyarm(s)})
    return rows


def kappa(a: np.ndarray, b: np.ndarray) -> dict:
    a, b = np.asarray(a, float), np.asarray(b, float)
    n = len(a)
    pa, pb = a.mean(), b.mean()
    po = float(np.mean(a == b))
    pe = float(pa * pb + (1 - pa) * (1 - pb))
    k = (po - pe) / (1 - pe) if pe < 1 else float("nan")
    pomax = 1 - abs(pa - pb)
    kmax = (pomax - pe) / (1 - pe) if pe < 1 else float("nan")
    return {"n": n, "p_M": round(float(pa), 4), "p_Mprime": round(float(pb), 4), "p_obs_agree": round(po, 4),
            "p_exp_agree": round(pe, 4), "kappa": round(float(k), 4), "kappa_max": round(float(kmax), 4),
            "both_obs": int(np.sum((a == 1) & (b == 1))), "both_exp_indep": round(float(n * pa * pb), 2)}


def perm_null(a: np.ndarray, b: np.ndarray, strata: list, n_perm: int, rng) -> dict:
    """Permute b within strata (preserves every stratum's marginals of a and b); kappa and the 'both' count."""
    a, b = np.asarray(a), np.asarray(b)
    groups = defaultdict(list)
    for i, s in enumerate(strata):
        groups[s].append(i)
    idx = [np.asarray(v) for v in groups.values()]
    kobs = kappa(a, b)
    ks, bs = np.empty(n_perm), np.empty(n_perm)
    bp = b.copy()
    for i in range(n_perm):
        for g in idx:
            bp[g] = b[g][rng.permutation(len(g))]
        ks[i] = kappa(a, bp)["kappa"]
        bs[i] = int(np.sum((a == 1) & (bp == 1)))
    return {"kappa_null_mean": round(float(ks.mean()), 4), "kappa_null_95": [round(float(x), 4) for x in np.percentile(ks, [2.5, 97.5])],
            "p_one_sided_kappa_ge_obs": round(float((1 + np.sum(ks >= kobs["kappa"] - 1e-12)) / (1 + n_perm)), 5),
            "both_null_mean": round(float(bs.mean()), 2), "both_null_95": [float(x) for x in np.percentile(bs, [2.5, 97.5])],
            "n_perm": n_perm, "n_strata": len(idx)}


def block_boot_kappa(rows: list[dict], blocks: list[str], B: int, rng) -> list:
    by = defaultdict(list)
    for r in rows:
        by[r["block"]].append(r)
    ks = []
    for _ in range(B):
        pick = rng.integers(0, len(blocks), len(blocks))
        rr = [r for i in pick for r in by[blocks[i]]]
        ks.append(kappa([r["M"] for r in rr], [r["Ms"] for r in rr])["kappa"])
    ks = np.asarray(ks)
    ks = ks[np.isfinite(ks)]
    return [round(float(x), 4) for x in np.percentile(ks, [2.5, 97.5])]


def overlap_table(rows: list[dict], fa: str = "M", fb: str = "Ms") -> dict:
    n = len(rows)
    c = {k: 0 for k in CELLS}
    dirs = {"both": defaultdict(int), "only_bf16": defaultdict(int), "only_d2": defaultdict(int)}
    for r in rows:
        a, b = r[fa], r[fb]
        k = "both" if a and b else "only_bf16" if a else "only_d2" if b else "neither"
        c[k] += 1
        if fa == "M":
            dp = "rescue" if r["r"] else "damage" if r["d"] else None
            ds = "rescue" if r["rs"] else "damage" if r["ds"] else None
            if k == "both":
                dirs[k][f"{dp}/{ds}"] += 1
            elif k == "only_bf16":
                dirs[k][dp] += 1
            elif k == "only_d2":
                dirs[k][ds] += 1
    out = {"n": n, "counts": c, "share_pct": {k: round(100 * v / max(n, 1), 2) for k, v in c.items()}}
    if fa == "M":
        out["directions"] = {k: dict(v) for k, v in dirs.items()}
        nb = c["both"]
        same_dir = dirs["both"].get("rescue/rescue", 0) + dirs["both"].get("damage/damage", 0)
        out["both_same_direction"] = {"n": same_dir, "of": nb, "pct": round(100 * same_dir / nb, 1) if nb else None}
        # given a precision flip, share also flipped under d2 (and the reverse)
        nM, nMs = c["both"] + c["only_bf16"], c["both"] + c["only_d2"]
        out["p_Mprime_given_M_pct"] = round(100 * c["both"] / nM, 1) if nM else None
        out["p_M_given_Mprime_pct"] = round(100 * c["both"] / nMs, 1) if nMs else None
        out["jaccard_units"] = round(c["both"] / max(1, c["both"] + c["only_bf16"] + c["only_d2"]), 4)
        # divergence context of the one-design-only flips
        out["only_bf16_with_d2_divergent"] = sum(1 for r in rows if r["M"] and not r["Ms"] and r["div_s"])
        out["only_d2_with_bf16_divergent"] = sum(1 for r in rows if r["Ms"] and not r["M"] and r["div_p"])
    return out


def task_level(rows: list[dict], blocks: list[str], n_perm: int, rng) -> dict:
    """Per task (model, domain, task): flip rate over the K blocks in each design; between-design correlation vs the
    within-design replication correlation over disjoint block halves."""
    tasks = sorted({(r["model"], r["domain"], r["task"]) for r in rows})
    ti = {t: i for i, t in enumerate(tasks)}
    bi = {b: i for i, b in enumerate(blocks)}
    P, S = np.full((len(tasks), len(blocks)), np.nan), np.full((len(tasks), len(blocks)), np.nan)
    for r in rows:
        P[ti[r["task_key"]], bi[r["block"]]] = r["M"]
        S[ti[r["task_key"]], bi[r["block"]]] = r["Ms"]
    fp, fs = np.nanmean(P, 1), np.nanmean(S, 1)
    out = {"n_tasks": len(tasks), "K": len(blocks)}
    out["pearson"] = round(float(pearsonr(fp, fs)[0]), 4)
    out["spearman"] = round(float(spearmanr(fp, fs)[0]), 4)
    # task-permutation null (within model x domain): is the cross-design task correlation above chance?
    strata = defaultdict(list)
    for i, t in enumerate(tasks):
        strata[(t[0], t[1])].append(i)
    nulls = np.empty(n_perm)
    for k in range(n_perm):
        perm = np.arange(len(tasks))
        for g in strata.values():
            perm[g] = np.asarray(g)[rng.permutation(len(g))]
        nulls[k] = pearsonr(fp, fs[perm])[0]
    out["pearson_perm_null_95"] = [round(float(x), 4) for x in np.percentile(nulls, [2.5, 97.5])]
    out["pearson_perm_p_one_sided"] = round(float((1 + np.sum(nulls >= out["pearson"] - 1e-12)) / (1 + n_perm)), 5)
    # split-half: all balanced splits of the K blocks into two disjoint halves (h = K // 2 each; the odd block is dropped)
    K = len(blocks)
    h = K // 2
    within_p, within_s, cross = [], [], []
    seen = set()
    for A in itertools.combinations(range(K), h):
        rest = [i for i in range(K) if i not in A]
        for Bh in itertools.combinations(rest, h):
            key = frozenset([frozenset(A), frozenset(Bh)])
            if key in seen:
                continue
            seen.add(key)
            a, b = list(A), list(Bh)
            pa, pb = np.nanmean(P[:, a], 1), np.nanmean(P[:, b], 1)
            sa, sb = np.nanmean(S[:, a], 1), np.nanmean(S[:, b], 1)
            within_p.append(pearsonr(pa, pb)[0])
            within_s.append(pearsonr(sa, sb)[0])
            cross.append(0.5 * (pearsonr(pa, sb)[0] + pearsonr(sa, pb)[0]))
    wp, ws, cr = (float(np.nanmean(x)) for x in (within_p, within_s, cross))
    out["split_half"] = {"n_splits": len(seen), "half_blocks": h, "within_prec_r": round(wp, 4), "within_same_r": round(ws, 4),
                         "cross_design_r": round(cr, 4),
                         "cross_over_within_ratio": round(cr / np.sqrt(max(wp, 1e-9) * max(ws, 1e-9)), 3) if wp > 0 and ws > 0 else None,
                         "note": "same noise level (half the blocks each side): cross ~ within means the designs flag the same tasks as much as each design replicates itself"}
    # concentration
    def conc(f):
        tot = f.sum()
        o = np.sort(f)[::-1]
        return {f"top{q}pct_share_of_flips_pct": round(100 * float(o[: max(1, int(round(len(o) * q / 100)))].sum() / tot), 1) if tot else None
                for q in (10, 20)} | {"tasks_ever_flip": int(np.sum(f > 0)), "tasks_flip_ge_half_blocks": int(np.sum(f >= 0.5))}
    out["concentration_prec"], out["concentration_same"] = conc(fp), conc(fs)
    ep, es = fp > 0, fs > 0
    out["jaccard_ever_flip_tasks"] = round(float(np.sum(ep & es) / max(1, np.sum(ep | es))), 4)
    n = len(tasks)
    a_, b_ = ep.sum(), es.sum()
    exp_inter = a_ * b_ / n
    out["jaccard_expected_indep"] = round(float(exp_inter / max(1, a_ + b_ - exp_inter)), 4)
    out["ever_flip_counts"] = {"prec": int(a_), "same": int(b_), "both": int(np.sum(ep & es)), "expected_both_indep": round(float(exp_inter), 1)}
    # top tasks listing (by combined flip rate)
    order = np.argsort(-(fp + fs))[:15]
    out["top_tasks"] = [{"task": "|".join(tasks[i]), "flip_rate_prec": round(float(fp[i]), 3), "flip_rate_same": round(float(fs[i]), 3)} for i in order]
    return out


def analyse(rows_all: list[dict], blocks: list[str], models: list[str], n_perm: int, B: int) -> dict:
    rng = np.random.default_rng(SEED)
    res = {"blocks": blocks, "K": len(blocks), "per_cell": {}, "pooled": {}}
    for r in rows_all:
        r["task_key"] = (r["model"], r["domain"], r["task"])
    yqq_mismatch = sum(1 for r in rows_all if r["yqq_p"] != r["yqq_s"])
    res["yqq_shared"] = {"mismatch_units": yqq_mismatch, "n": len(rows_all),
                         "note": "Y_QQ is the same Q episode in both designs, so a unit flipping in both designs flips in the same direction by construction (rescue iff Y_QQ = 0)"}
    scopes = [(m, [r for r in rows_all if r["model"] == m]) for m in models] + [("pooled", rows_all)]
    for name, rows in scopes:
        a = np.array([r["M"] for r in rows])
        b = np.array([r["Ms"] for r in rows])
        x = {"overlap": overlap_table(rows), "overlap_any_arm": overlap_table(rows, "Many", "Manys"), "kappa": kappa(a, b)}
        x["kappa"]["null_within_cell_block"] = perm_null(a, b, [(r["model"], r["block"]) for r in rows], n_perm, rng)
        x["kappa"]["null_within_cell_block_yqq"] = perm_null(a, b, [(r["model"], r["block"], r["yqq_p"]) for r in rows], n_perm, rng)
        # same task vs same episode: permute M' across blocks WITHIN each task (keeps every task's flip propensity in both designs)
        x["kappa"]["null_within_task"] = perm_null(a, b, [r["task_key"] for r in rows], n_perm, rng)
        x["kappa"]["block_boot_ci95"] = block_boot_kappa(rows, blocks, B, rng)
        ka, kb = np.array([r["Many"] for r in rows]), np.array([r["Manys"] for r in rows])
        x["kappa_any_arm"] = kappa(ka, kb)
        # kappa within Y_QQ strata (rescue-only and damage-only possible flips)
        x["kappa_by_yqq"] = {f"Y_QQ={v}": kappa(np.array([r["M"] for r in rows if r["yqq_p"] == v]), np.array([r["Ms"] for r in rows if r["yqq_p"] == v]))
                             for v in (0, 1)}
        x["task_level"] = task_level(rows, blocks, n_perm, rng)
        (res["per_cell"].__setitem__(name, x) if name != "pooled" else res.__setitem__("pooled", x))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--perm", type=int, default=10000)
    ap.add_argument("--B", type=int, default=AD.B_BOOT)
    a = ap.parse_args()
    t0 = time.time()
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    man = json.load(open(SP.MANIFEST))
    psha = SP.guard(man)
    snap = json.load(open(ROOT / man["snapshot"]))
    models = man["cells"]
    U, prefix = load(man, snap)
    Ks = sorted({k for k in (6, len(prefix)) if 1 <= k <= len(prefix)})
    interim = time.gmtime() < time.strptime("2026-10-04T07", "%Y-%m-%dT%H")
    res = {"script": str(Path(__file__).relative_to(ROOT)), "script_sha256": AD.sha256(__file__), "protocol_sha256": psha,
           "analyze_sameprec_sha256": AD.sha256(SP.__file__), "analyze_dev_sha256": AD.sha256(AD.__file__),
           "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
           "utc": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), "seed": SEED, "n_perm": a.perm, "B": a.B,
           "status": "INTERIM (before the 2026-10-03 evidence freeze); DESCRIPTIVE / exploratory (amendment A1.4)" if interim else "DESCRIPTIVE / exploratory",
           "complete_prefix": prefix, "by_K": {}}
    for K in Ks:
        rows = unit_rows(U, prefix[:K], models)
        res["by_K"][str(K)] = analyse(rows, prefix[:K], models, a.perm, a.B)
        res["by_K"][str(K)]["units_digest"] = hashlib.sha256(json.dumps(sorted((r["model"], r["domain"], r["task"], r["block"], r["M"], r["Ms"]) for r in rows)).encode()).hexdigest()
    res["seconds"] = round(time.time() - t0, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    jp = OUT / f"sameprec_overlap_{res['utc']}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    (OUT / f"sameprec_overlap_{res['utc']}.md").write_text(markdown(res, jp))
    print(f"sameprec_overlap: wrote {jp.relative_to(ROOT)} (K = {Ks}, {res['seconds']} s)")


def markdown(r: dict, jp: Path) -> str:
    Kmax = max(r["by_K"], key=int)
    R = r["by_K"][Kmax]
    P = R["pooled"]
    o, k, tl = P["overlap"], P["kappa"], P["task_level"]
    c = o["counts"]
    n0 = k["null_within_cell_block"]
    L = [f"**TL;DR** ({r['status']}; K = {R['K']} blocks {R['blocks'][0]}–{R['blocks'][-1]}, q4+q8, {o['n']} task×block units.) "
         f"Of the units whose outcome flips under the precision replacement (M = 1: {c['both'] + c['only_bf16']}) and under the same-precision "
         f"replacement (M′ = 1: {c['both'] + c['only_d2']}), **{c['both']} flip under both** ({o['share_pct']['both']:.1f}% of units; "
         f"{o['p_Mprime_given_M_pct']:.0f}% of the BF16 flips, {o['p_M_given_Mprime_pct']:.0f}% of the d2 flips; unit Jaccard {o['jaccard_units']:.2f}), "
         f"vs {n0['both_null_mean']:.0f} expected if the two flip sets were independent within cell×block. "
         f"Only BF16 {c['only_bf16']}, only d2 {c['only_d2']}, neither {c['neither']}. "
         f"Cohen's κ(M, M′) = {k['kappa']:.2f} (block-bootstrap 95% [{k['block_boot_ci95'][0]:.2f}, {k['block_boot_ci95'][1]:.2f}]; "
         f"marginal-preserving null mean {n0['kappa_null_mean']:+.3f}, 95% [{n0['kappa_null_95'][0]:+.2f}, {n0['kappa_null_95'][1]:+.2f}], "
         f"p = {n0['p_one_sided_kappa_ge_obs']:.4f}; κ_max given the marginals {k['kappa_max']:.2f}). "
         f"All {o['both_same_direction']['of']} both-flip units flip in the same direction ({o['both_same_direction']['pct']:.0f}%), "
         f"which is forced by the shared Q episode (Y_QQ), not evidence. "
         f"Task level: per-task flip rates correlate r = {tl['pearson']:.2f} (Spearman {tl['spearman']:.2f}) between designs; at matched noise "
         f"(disjoint block halves) cross-design r = {tl['split_half']['cross_design_r']:.2f} vs within-design replication "
         f"{tl['split_half']['within_prec_r']:.2f} (precision) / {tl['split_half']['within_same_r']:.2f} (same-precision), "
         f"ratio {tl['split_half']['cross_over_within_ratio']}. "]
    ratio = tl["split_half"]["cross_over_within_ratio"] or 0
    nt = k["null_within_task"]
    unit_above = n0["p_one_sided_kappa_ge_obs"] < 0.05
    ep_above = nt["p_one_sided_kappa_ge_obs"] < 0.05
    L[0] += (f"Within-task null (M′ permuted across blocks inside each task, task propensities kept): both {nt['both_null_mean']:.0f} "
             f"[{nt['both_null_95'][0]:.0f}, {nt['both_null_95'][1]:.0f}] vs {c['both']} observed (κ null {nt['kappa_null_mean']:.2f}, p = {nt['p_one_sided_kappa_ge_obs']:.4f}). ")
    L[0] += ("**Answer:** " + ("similar average M corresponds to substantially overlapping sensitive units and tasks (far above chance), not to disjoint ones: " if unit_above else
                               "the overlap is at chance level: similar average M comes from different units. ")
             + (f"about {100 * ratio:.0f}% of the replicable task-level flip propensity is shared between the two replacements" if ratio else "")
             + ("; beyond task propensity, the same Q episodes (task×block) flip under both" if ep_above else
                "; beyond task propensity, the unit overlap is not larger than shared task propensity predicts") + ". "
             + f"Still, {c['only_bf16'] + c['only_d2']} of {c['both'] + c['only_bf16'] + c['only_d2']} flipping units flip under only one replacement.")
    if len(r["by_K"]) > 1:
        R6 = r["by_K"]["6"]["pooled"]
        L[0] += f" (K = 6: both {R6['overlap']['counts']['both']}, κ {R6['kappa']['kappa']:.2f}, task r {R6['task_level']['pearson']:.2f}.)"
    L += ["", f"# Same-precision vs precision 2×2: unit and task overlap ({r['utc']})", "",
          f"{r['status']}. Script `{r['script']}` sha {r['script_sha256'][:12]}; protocol sha {r['protocol_sha256'][:12]} (amended, A1); "
          f"analyze_sameprec {r['analyze_sameprec_sha256'][:12]}; git {r['git_head'][:10]}; seed {r['seed']}, {r['n_perm']} permutations, B = {r['B']}. "
          f"Full numbers: `{jp.relative_to(ROOT)}`. Complete prefix now: {', '.join(r['complete_prefix'])}.", "",
          "Definitions: unit = task×block, admitted in both designs (the primary analysis set). M = 1 iff Y_BQ ≠ Y_QQ (BF16 action, Q continues; "
          "rescue = Y_BQ 1/Y_QQ 0, damage = 0/1; no divergence = 0). M′ the same with Q′ = GPTQ-W4 d2 in place of BF16. "
          "M_any (secondary): any B-involving arm (BB, BQ, QB) ≠ QQ.", ""]
    for Kk, RK in sorted(r["by_K"].items(), key=lambda x: int(x[0])):
        L += [f"## K = {Kk} ({RK['blocks'][0]}–{RK['blocks'][-1]}){' — interim' if 'INTERIM' in r['status'] else ''}", "",
              f"Y_QQ identical across designs on {RK['yqq_shared']['n'] - RK['yqq_shared']['mismatch_units']}/{RK['yqq_shared']['n']} units. "
              + RK["yqq_shared"]["note"] + ".", "",
              "### Overlap table (M vs M′; counts, share of units)", "",
              "| scope | units | both | only BF16 | only d2 | neither | P(M′=1∣M=1) | P(M=1∣M′=1) | unit Jaccard |", "|---|---|---|---|---|---|---|---|---|"]
        for nm, x in list(RK["per_cell"].items()) + [("pooled", RK["pooled"])]:
            ov = x["overlap"]
            cc, sh = ov["counts"], ov["share_pct"]
            L.append(f"| {nm} | {ov['n']} | {cc['both']} ({sh['both']:.1f}%) | {cc['only_bf16']} ({sh['only_bf16']:.1f}%) | {cc['only_d2']} ({sh['only_d2']:.1f}%) | "
                     f"{cc['neither']} ({sh['neither']:.1f}%) | {ov['p_Mprime_given_M_pct']}% | {ov['p_M_given_Mprime_pct']}% | {ov['jaccard_units']:.3f} |")
        L += ["", "Directions (rescue / damage):", "", "| scope | both (BF16/d2) | both same direction | only BF16 | only d2 | only-BF16 units where d2 diverged | only-d2 units where BF16 diverged |", "|---|---|---|---|---|---|---|"]
        for nm, x in list(RK["per_cell"].items()) + [("pooled", RK["pooled"])]:
            ov = x["overlap"]
            dd = ov["directions"]
            fmt = lambda d: ", ".join(f"{k} {v}" for k, v in sorted(d.items())) or "-"  # noqa: E731
            L.append(f"| {nm} | {fmt(dd['both'])} | {ov['both_same_direction']['n']}/{ov['both_same_direction']['of']} | {fmt(dd['only_bf16'])} | {fmt(dd['only_d2'])} | "
                     f"{ov['only_bf16_with_d2_divergent']} | {ov['only_d2_with_bf16_divergent']} |")
        L += ["", "### Agreement (Cohen's κ on M vs M′)", "",
              "| scope | κ | block-boot 95% | κ_max | p_o | p_e (marginals) | both obs | both exp (indep.) | null κ cell×block: mean [95%], p | null κ cell×block×Y_QQ: mean [95%], p | null within task: κ mean [95%], both mean, p | κ M_any |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for nm, x in list(RK["per_cell"].items()) + [("pooled", RK["pooled"])]:
            kk = x["kappa"]
            a1, a2, a3 = kk["null_within_cell_block"], kk["null_within_cell_block_yqq"], kk["null_within_task"]
            L.append(f"| {nm} | {kk['kappa']:.3f} | [{kk['block_boot_ci95'][0]:.2f}, {kk['block_boot_ci95'][1]:.2f}] | {kk['kappa_max']:.3f} | {kk['p_obs_agree']:.3f} | "
                     f"{kk['p_exp_agree']:.3f} | {kk['both_obs']} | {kk['both_exp_indep']:.1f} | {a1['kappa_null_mean']:+.3f} [{a1['kappa_null_95'][0]:+.2f}, {a1['kappa_null_95'][1]:+.2f}], "
                     f"{a1['p_one_sided_kappa_ge_obs']:.4f} | {a2['kappa_null_mean']:+.3f} [{a2['kappa_null_95'][0]:+.2f}, {a2['kappa_null_95'][1]:+.2f}], "
                     f"{a2['p_one_sided_kappa_ge_obs']:.4f} | {a3['kappa_null_mean']:+.3f} [{a3['kappa_null_95'][0]:+.2f}, {a3['kappa_null_95'][1]:+.2f}], "
                     f"{a3['both_null_mean']:.1f}, {a3['p_one_sided_kappa_ge_obs']:.4f} | {x['kappa_any_arm']['kappa']:.3f} |")
        L += ["", "κ within Y_QQ strata (Y_QQ = 0: only rescues possible; Y_QQ = 1: only damages): "
              + "; ".join(f"{nm}: " + ", ".join(f"{s} κ {v['kappa']:.2f} (n {v['n']}, both {v['both_obs']} vs {v['both_exp_indep']:.1f} exp.)" for s, v in x["kappa_by_yqq"].items())
                          for nm, x in list(RK["per_cell"].items()) + [("pooled", RK["pooled"])]), "",
              "Overlap with M_any (any B-involving arm ≠ QQ), counts both / only BF16 / only d2 / neither: "
              + "; ".join(f"{nm} " + " / ".join(str(x['overlap_any_arm']['counts'][c]) for c in CELLS) for nm, x in list(RK["per_cell"].items()) + [("pooled", RK["pooled"])]), "",
              "### Task-level concentration", "",
              "| scope | tasks | r (Pearson) | perm null 95% (p) | Spearman | split-half within prec | within same | cross-design | cross/within | top-10% tasks' share of flips prec / same | tasks ever flip prec / same / both (exp.) | Jaccard ever-flip (exp.) |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for nm, x in list(RK["per_cell"].items()) + [("pooled", RK["pooled"])]:
            t = x["task_level"]
            sh = t["split_half"]
            ef = t["ever_flip_counts"]
            L.append(f"| {nm} | {t['n_tasks']} | {t['pearson']:.3f} | [{t['pearson_perm_null_95'][0]:+.2f}, {t['pearson_perm_null_95'][1]:+.2f}] ({t['pearson_perm_p_one_sided']:.4f}) | "
                     f"{t['spearman']:.3f} | {sh['within_prec_r']:.3f} | {sh['within_same_r']:.3f} | {sh['cross_design_r']:.3f} | {sh['cross_over_within_ratio']} | "
                     f"{t['concentration_prec']['top10pct_share_of_flips_pct']}% / {t['concentration_same']['top10pct_share_of_flips_pct']}% | "
                     f"{ef['prec']} / {ef['same']} / {ef['both']} ({ef['expected_both_indep']}) | {t['jaccard_ever_flip_tasks']:.3f} ({t['jaccard_expected_indep']:.3f}) |")
        L += ["", f"Split-half: all {RK['pooled']['task_level']['split_half']['n_splits']} balanced splits of the K blocks into two disjoint halves of "
              f"{RK['pooled']['task_level']['split_half']['half_blocks']} blocks; within = same design on the two halves, cross = precision on one half vs "
              "same-precision on the other (mean of both orientations). cross/within = cross / sqrt(within_prec × within_same).", "",
              "Top tasks by combined flip rate (pooled): " + "; ".join(f"{x['task']} {x['flip_rate_prec']:.2f}/{x['flip_rate_same']:.2f}" for x in RK["pooled"]["task_level"]["top_tasks"][:10]), ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
