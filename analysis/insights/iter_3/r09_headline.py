"""r09: collect the iteration-3 headline numbers (I5-I8) from r01-r08 outputs of one tag into one table.
Also: pooled attractor gap at W4, c - p_bar (mean over models x W4 families, with the per-family bootstrap CIs listed).
Usage: CLOQ_SNAPSHOT=<manifest> python r09_headline.py -> out/r09_headline_<tag>.json
"""
import json

import numpy as np

from r_common import OUT, TAG, dump, rnd

W4 = ("rtn_w4", "gptq_w4", "awq_w4")


def J(name):
    p = OUT / f"{name}_{TAG}.json"
    return json.load(open(p)) if p.exists() else None


def main():
    r01, r03, r04, r05, r07, r08 = (J(n) for n in ("r01_realloc", "r03_fragility", "r04_margin_predict",
                                                    "r05_openloop_task", "r07_damage", "r08_size_generic"))
    out = {"I5_lambda": {}, "I5_attractor_W4": {}, "I6_fragility": {}, "I7_openloop": {}, "I8_damage": {}}
    gaps = []
    for m, M in r01["models"].items():
        fam = M["families"]
        out["I5_lambda"][m] = {f: dict(lam=fam[f]["lam"], ci=fam[f]["lam_ci"], n_draws=fam[f]["n_draws"],
                                       lam_composed=fam[f].get("lam_composed"))
                               for f in ("rtn_w8", "gauss0.03_fixed", "gauss0.3", "rtn_w4", "gptq_w4", "awq_w4",
                                         "gauss1", "gauss1_fixed", "gptq_w3", "rtn_w3") if f in fam}
        for f in W4:
            if f in fam and fam[f]["c"] is not None:
                out["I5_attractor_W4"].setdefault(m, {})[f] = dict(c=fam[f]["c"], c_ci=fam[f]["c_ci"], p_bar=fam[f]["p_bar_null"],
                                                                     lam=fam[f]["lam"], delta_obs=fam[f]["delta_obs"],
                                                                     delta_model=rnd(fam[f]["lam"] * (fam[f]["c"] - fam[f]["p_bar_null"])))
                if fam[f]["lam"] > 0.1:
                    gaps.append(fam[f]["c"] - fam[f]["p_bar_null"])
    out["I5_attractor_W4"]["pooled_c_minus_pbar_lam_gt_0.1"] = dict(mean=rnd(np.mean(gaps)), median=rnd(np.median(gaps)),
                                                                     n=len(gaps), values=rnd(gaps))
    if r08:
        out["I5_size_generic"] = dict(pooled=r08["pooled"], per_model={m: M["contrasts"] for m, M in r08["models"].items()},
                                      null_sd={m: (M["null_single_draw_lam_sd"], M["null_pair_lam_sd"]) for m, M in r08["models"].items()})
    for m, M in r03["models"].items():
        g = M["groups"]
        out["I6_fragility"][m] = dict(
            lift_break={k: g[k]["lift_break"] for k in g}, lift_fix={k: g[k]["lift_fix"] for k in g},
            p_fail_given_fail={k: g[k]["p_fail_given_fail"] for k in g}, p_fail={k: g[k]["p_fail"] for k in g},
            auc=M["auc_summary_excl_w8"],
            super_robust=({k: v for k, v in r04["models"][m]["super_robust"].items() if k != "per_draw"} if r04 and m in r04["models"] else None),
            ref_margin_auc=({k: v["mean"] for k, v in r04["models"][m]["auc_summary"].items()} if r04 and m in r04["models"] else None))
    cm = J("r06_crossmodel")
    if cm:
        out["I6_fragility"]["cross_model"] = cm
    if r05:
        for m, M in r05["models"].items():
            out["I7_openloop"][m] = dict(task_level_auc={k: v["mean"] for k, v in M["auc_summary"].items()},
                                         rho_ol_lam=M["cell_identity"]["spearman_ol_any_vs_lam"], p=M["cell_identity"]["p"],
                                         rho_ol_delta=M["cell_identity"].get("spearman_ol_any_vs_delta_obs"),
                                         p_delta=M["cell_identity"].get("p_delta"), n_cells=M["cell_identity"]["n"])
    if r07:
        out["I8_damage"] = dict(pooled=r07.get("pooled_lam_gt_0.15"),
                                per_model={m: dict(null=M["null"], families={f: {k: v[k] for k in ("lam", "c", "gap", "abn", "abn_excess", "brk_abn", "n_breaks", "dec", "rep")}
                                                                             for f, v in M["families"].items()})
                                           for m, M in r07["models"].items()})
    dump("r09_headline", out)
    print(json.dumps(out["I5_attractor_W4"]["pooled_c_minus_pbar_lam_gt_0.1"]))


if __name__ == "__main__":
    main()
