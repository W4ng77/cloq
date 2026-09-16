"""Aggregate all arms into tables, contrasts, horizon analysis and figures.

usage: python -m cloq.report --bf16-run bf16 --arm-runs static=static_eval fp_traj=fp_traj_eval cloq=cloq_eval [rtn=rtn_eval]
Writes analysis/results.json, analysis/REPORT.md and analysis/fig_*.png
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from cloq import config as C
from cloq.metrics import paired_bootstrap, read_jsonl, spearman

ANALYSIS = C.PROJECT_ROOT / "analysis"


def load_task_metrics(run_id: str, domain: str, eval_ids: list[str]) -> dict[str, dict]:
    rd = C.RUNS_DIR / run_id / domain
    m = json.load(open(rd / "metrics.json"))
    rows = {r["task_id"]: r for r in m["per_task"]}
    succ = {}
    if (rd / "task_success.json").exists():
        succ = {r["task_id"]: r["task_success"] for r in json.load(open(rd / "task_success.json"))["per_task"]}
    out = {}
    for tid in eval_ids:
        if tid not in rows:
            continue
        r = dict(rows[tid])
        r["task_success"] = succ.get(tid)
        out[tid] = r
    return out


def horizon_table(split: dict, domain: str, bf16: dict, arms: dict[str, dict], metric: str) -> dict:
    qmap = split["domains"][domain]["quartile_by_task"]
    hmap = split["domains"][domain]["horizon_by_task"]
    res = {}
    for q in range(4):
        ids = [t for t in bf16 if qmap.get(t) == q]
        if not ids:
            continue
        row = {"n": len(ids), "bf16": float(np.mean([bool(bf16[t][metric]) for t in ids]))}
        for a, d in arms.items():
            v = [bool(d[t][metric]) for t in ids if t in d]
            row[a] = float(np.mean(v)) if v else None
            row[f"delta_{a}"] = (row["bf16"] - row[a]) if row[a] is not None else None
        res[f"Q{q + 1}"] = row
    # continuous rank correlation between horizon and per-task failure of each arm
    corr = {}
    for a, d in arms.items():
        ids = [t for t in bf16 if t in d]
        fail = [float(not d[t][metric]) for t in ids]
        corr[a] = spearman([hmap[t] for t in ids], fail)
    return {"buckets": res, "spearman_horizon_vs_failure": corr}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bf16-run", default="bf16")
    ap.add_argument("--arm-runs", nargs="+", required=True)
    ap.add_argument("--split", default=str(C.MANIFEST_DIR / "task_split_v0.json"))
    ap.add_argument("--out", default=str(ANALYSIS))
    ap.add_argument("--domains", nargs="+", default=None)
    a = ap.parse_args()
    arm_runs = dict(kv.split("=", 1) for kv in a.arm_runs)
    split = json.load(open(a.split))
    domains = a.domains or list(split["domains"].keys())
    out_dir = Path(a.out); out_dir.mkdir(parents=True, exist_ok=True)
    nboot = int(C.FROZEN["analysis"]["bootstrap_replicates"])

    results = {"arms": list(arm_runs), "domains": {}, "pooled": {}}
    pooled: dict[str, dict[str, dict]] = defaultdict(dict)  # arm -> metric -> {dom/tid: val}
    for domain in domains:
        eval_ids = split["domains"][domain]["evaluation"]
        bf16 = load_task_metrics(a.bf16_run, domain, eval_ids)
        arms = {arm: load_task_metrics(run, domain, eval_ids) for arm, run in arm_runs.items()}
        dres = {"n_eval": len(eval_ids), "summary": {}, "contrasts": {}, "horizon": {}, "openloop": {}, "divergence": {}}
        for metric in ["db_match", "task_success", "reward"]:
            summ = {"bf16": float(np.mean([float(bool(v[metric])) for v in bf16.values()])) if all(v.get(metric) is not None for v in bf16.values()) else None}
            for arm, d in arms.items():
                vals = [float(bool(v[metric])) for v in d.values() if v.get(metric) is not None]
                summ[arm] = float(np.mean(vals)) if vals else None
            dres["summary"][metric] = summ
            # contrasts (paired bootstrap over task ids)
            series = {"bf16": {t: float(bool(v[metric])) for t, v in bf16.items() if v.get(metric) is not None}}
            for arm, d in arms.items():
                series[arm] = {t: float(bool(v[metric])) for t, v in d.items() if v.get(metric) is not None}
                for t, val in series[arm].items():
                    pooled[arm].setdefault(metric, {})[f"{domain}/{t}"] = val
            for t, val in series["bf16"].items():
                pooled["bf16"].setdefault(metric, {})[f"{domain}/{t}"] = val
            cs = {}
            for name in C.FROZEN["analysis"]["primary_contrasts"]:
                x, y = [s.strip() for s in name.split("-")]
                if x in series and y in series:
                    cs[name] = paired_bootstrap(series[x], series[y], n_boot=nboot)
            for arm in arms:
                cs[f"bf16 - {arm}"] = paired_bootstrap(series["bf16"], series[arm], n_boot=nboot)
            dres["contrasts"][metric] = cs
            dres["horizon"][metric] = horizon_table(split, domain, bf16, arms, metric)
        # secondary closed-loop stats
        sec = {}
        for arm, run in {"bf16": a.bf16_run, **arm_runs}.items():
            m = json.load(open(C.RUNS_DIR / run / domain / "metrics.json"))
            sec[arm] = {k: m.get(k) for k in ["mean_decisions", "mean_tool_calls", "tool_error_rate", "parser_error_rate", "premature_rate", "repeated_tool_call_rate", "truncated_context_rate", "termination_reasons"]}
        dres["secondary"] = sec
        for arm, run in arm_runs.items():
            p = C.RUNS_DIR / run / domain / "openloop.summary.json"
            if p.exists():
                dres["openloop"][arm] = json.load(open(p))
            p = C.RUNS_DIR / run / domain / "divergence.json"
            if p.exists():
                d = json.load(open(p)); d.pop("per_task", None); dres["divergence"][arm] = d
        results["domains"][domain] = dres

    # pooled (db_match is definitionally identical across domains; task_success is not -> report but flag)
    for metric in ["db_match", "task_success"]:
        cs = {}
        for name in C.FROZEN["analysis"]["primary_contrasts"]:
            x, y = [s.strip() for s in name.split("-")]
            if metric in pooled.get(x, {}) and metric in pooled.get(y, {}):
                cs[name] = paired_bootstrap(pooled[x][metric], pooled[y][metric], n_boot=nboot)
        for arm in arm_runs:
            if metric in pooled.get(arm, {}):
                cs[f"bf16 - {arm}"] = paired_bootstrap(pooled["bf16"][metric], pooled[arm][metric], n_boot=nboot)
        results["pooled"][metric] = {"means": {arm: float(np.mean(list(pooled[arm][metric].values()))) for arm in pooled if metric in pooled[arm]}, "contrasts": cs}
    for p in [out_dir / "occupancy_last.json", out_dir / "occupancy_obs.json"]:
        if p.exists():
            results[p.stem] = json.load(open(p))
    (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    write_markdown(results, split, out_dir)
    try:
        make_figures(results, out_dir)
    except Exception as e:  # pragma: no cover
        print("figure generation failed:", repr(e))
    print("wrote", out_dir / "results.json", out_dir / "REPORT.md")


def _fmt(x):
    return "n/a" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))


def write_markdown(results: dict, split: dict, out_dir: Path) -> None:
    L = ["# CLOQ v0 results (auto-generated)", ""]
    arms = ["bf16"] + results["arms"]
    for domain, d in results["domains"].items():
        L += [f"## {domain} (n_eval = {d['n_eval']})", ""]
        L += ["| metric | " + " | ".join(arms) + " |", "|---|" + "---|" * len(arms)]
        for metric, s in d["summary"].items():
            L.append(f"| {metric} | " + " | ".join(_fmt(s.get(a)) for a in arms) + " |")
        L += ["", "### Paired bootstrap contrasts (db_match)", "", "| contrast | diff | 95% CI | n |", "|---|---|---|---|"]
        for name, c in d["contrasts"]["db_match"].items():
            L.append(f"| {name} | {_fmt(c.get('diff'))} | [{_fmt(c.get('ci_lo'))}, {_fmt(c.get('ci_hi'))}] | {c.get('n')} |")
        if "task_success" in d["contrasts"]:
            L += ["", "### Paired bootstrap contrasts (task_success, local judge)", "", "| contrast | diff | 95% CI | n |", "|---|---|---|---|"]
            for name, c in d["contrasts"]["task_success"].items():
                L.append(f"| {name} | {_fmt(c.get('diff'))} | [{_fmt(c.get('ci_lo'))}, {_fmt(c.get('ci_hi'))}] | {c.get('n')} |")
        h = d["horizon"]["db_match"]
        L += ["", "### Horizon amplification (db_match; BF16 horizon quartile)", "", "| quartile | n | bf16 | " + " | ".join(f"{a} (Δ)" for a in results["arms"]) + " |", "|---|---|---|" + "---|" * len(results["arms"])]
        for q, row in h["buckets"].items():
            L.append(f"| {q} | {row['n']} | {_fmt(row['bf16'])} | " + " | ".join(f"{_fmt(row.get(a))} ({_fmt(row.get('delta_' + a))})" for a in results["arms"]) + " |")
        L.append("")
        L.append("Spearman(horizon, failure): " + ", ".join(f"{a}={_fmt(v)}" for a, v in h["spearman_horizon_vs_failure"].items()))
        if d["openloop"]:
            L += ["", "### Open-loop fidelity on BF16 held-out states", "",
              "Replay of each stored BF16 context without executing the result. Full-action agreement includes free-text",
              "rewording and is therefore bounded by the launch-noise floor; the tool-call columns are the primary readout.", "",
              "| arm | states | tool-name agr. | full tool-call agr. | full action agr. | field F1 | NLL/token |", "|---|---|---|---|---|---|---|"]
            for a, o in d["openloop"].items():
                L.append(f"| {a} | {o['n_states']} | {_fmt(o['tool_name_agreement'])} | {_fmt(o['full_tool_call_agreement'])} | {_fmt(o['full_action_agreement'])} | {_fmt(o['field_f1_given_name'])} | {_fmt(o['nll_per_token_mean'])} |")
        if d["divergence"]:
            L += ["", "### First divergence (t* = first decision whose tool-call behaviour differs from BF16)", "",
                  "Free-text rewording is excluded: it also differs between two launches of the same BF16 weights.",
                  "The last column is the fraction of tasks whose action string differs at all, wording included.", "",
                  "| arm | tool-div frac | median t* | median t*/H | SR early div | SR late div | SR no div | any-action div |",
                  "|---|---|---|---|---|---|---|---|"]
            for a, v in d["divergence"].items():
                L.append(f"| {a} | {_fmt(v['frac_any_divergence'])} | {_fmt(v['median_t_star'])} | {_fmt(v['median_t_star_norm'])} | "
                         f"{_fmt(v['success_given_early_div'])} (n={v['n_early']}) | {_fmt(v['success_given_late_div'])} (n={v['n_late']}) | "
                         f"{_fmt(v['success_given_no_div'])} (n={v['n_nodiv']}) | {_fmt(v.get('frac_any_action_divergence'))} |")
        L += ["", "### Secondary closed-loop statistics", "", "| arm | decisions | tool calls | tool err | parser err | premature | repeated | truncated ctx |", "|---|---|---|---|---|---|---|---|"]
        for a, s in d["secondary"].items():
            L.append(f"| {a} | {_fmt(s['mean_decisions'])} | {_fmt(s['mean_tool_calls'])} | {_fmt(s['tool_error_rate'])} | {_fmt(s['parser_error_rate'])} | {_fmt(s['premature_rate'])} | {_fmt(s['repeated_tool_call_rate'])} | {_fmt(s['truncated_context_rate'])} |")
        L.append("")
    L += ["## Pooled (db_match is definitionally identical across domains)", ""]
    for metric, p in results["pooled"].items():
        L += [f"### {metric}", "", "means: " + ", ".join(f"{a}={_fmt(v)}" for a, v in p["means"].items()), "", "| contrast | diff | 95% CI | n |", "|---|---|---|---|"]
        for name, c in p["contrasts"].items():
            L.append(f"| {name} | {_fmt(c.get('diff'))} | [{_fmt(c.get('ci_lo'))}, {_fmt(c.get('ci_hi'))}] | {c.get('n')} |")
        L.append("")
    for key in ["occupancy_last", "occupancy_obs"]:
        if key in results:
            L += [f"## Occupancy ({key})", ""]
            for domain, d in results[key]["domains"].items():
                L += [f"### {domain}", "", "FP states -> support: " + ", ".join(f"{k}={_fmt(v)}" for k, v in d["fp_to_support"].items()), ""]
                L += ["| arm | Q->static | Q->fp_traj | Q->cloq | pre-div (fp_traj supp) | post-div (fp_traj supp) | MMD(FP,Q) | MMD null |", "|---|---|---|---|---|---|---|---|"]
                for a, v in d["arms"].items():
                    pp = v["pre_post_divergence"].get("fp_traj", {})
                    L.append(f"| {a} | {_fmt(v['q_to_support'].get('static'))} | {_fmt(v['q_to_support'].get('fp_traj'))} | {_fmt(v['q_to_support'].get('cloq'))} | {_fmt(pp.get('pre_mean'))} (n={pp.get('n_pre')}) | {_fmt(pp.get('post_mean'))} (n={pp.get('n_post')}) | {_fmt(v['mmd_fp_vs_q'])} | {_fmt(v['mmd_fp_half_vs_half'])} |")
                L.append("")
    (out_dir / "REPORT.md").write_text("\n".join(L))


def make_figures(results: dict, out_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    arms = results["arms"]
    # Fig 2: horizon amplification
    fig, axes = plt.subplots(1, len(results["domains"]), figsize=(5 * len(results["domains"]), 3.6), squeeze=False)
    for ax, (domain, d) in zip(axes[0], results["domains"].items()):
        h = d["horizon"]["db_match"]["buckets"]
        qs = list(h.keys())
        for a in arms:
            ax.plot(qs, [h[q].get(f"delta_{a}") for q in qs], marker="o", label=a)
        ax.set_title(f"{domain}: BF16 - arm success by BF16 horizon quartile"); ax.set_ylabel("Δ success (BF16 − arm)"); ax.axhline(0, color="k", lw=0.5); ax.legend()
    fig.tight_layout(); fig.savefig(out_dir / "fig2_horizon.png", dpi=150); plt.close(fig)
    # Fig 5: method result
    fig, ax = plt.subplots(figsize=(5, 3.6))
    labels = ["bf16"] + arms
    for i, (domain, d) in enumerate(results["domains"].items()):
        vals = [d["summary"]["db_match"].get(a) for a in labels]
        ax.bar(np.arange(len(labels)) + i * 0.35, [v if v is not None else 0 for v in vals], width=0.35, label=domain)
    ax.set_xticks(np.arange(len(labels)) + 0.17); ax.set_xticklabels(labels); ax.set_ylabel("DB end-state match rate"); ax.legend(); ax.set_title("Closed-loop success at equal calibration budget")
    fig.tight_layout(); fig.savefig(out_dir / "fig5_method.png", dpi=150); plt.close(fig)
    # Fig 3: first divergence distribution
    fig, axes = plt.subplots(1, len(results["domains"]), figsize=(5 * len(results["domains"]), 3.6), squeeze=False)
    for ax, (domain, d) in zip(axes[0], results["domains"].items()):
        for a, v in d["divergence"].items():
            ax.bar(a, v["median_t_star_norm"] if v["median_t_star_norm"] is not None else 0)
        ax.set_title(f"{domain}: median t*/H"); ax.set_ylim(0, 1)
    fig.tight_layout(); fig.savefig(out_dir / "fig3_divergence.png", dpi=150); plt.close(fig)
    # Fig 4: occupancy aligned at divergence
    if "occupancy_last" in results:
        occ = results["occupancy_last"]["domains"]
        fig, axes = plt.subplots(1, len(occ), figsize=(5 * len(occ), 3.6), squeeze=False)
        for ax, (domain, d) in zip(axes[0], occ.items()):
            for a, v in d["arms"].items():
                curve = v["aligned_curve"].get("fp_traj", {})
                xs = sorted(int(k) for k in curve)
                ax.plot(xs, [curve[str(x)][0] for x in xs], marker=".", label=a)
            ax.axvline(0, color="k", lw=0.5); ax.set_xlabel("decision index − t*"); ax.set_ylabel("D_supp to FP-Traj support"); ax.set_title(domain); ax.legend()
        fig.tight_layout(); fig.savefig(out_dir / "fig4_occupancy.png", dpi=150); plt.close(fig)
    # Fig 6: open-loop vs closed-loop
    fig, ax = plt.subplots(figsize=(5, 3.6))
    for domain, d in results["domains"].items():
        for a in arms:
            o = d["openloop"].get(a)
            if o:
                ax.scatter(o["full_action_agreement"], d["summary"]["db_match"].get(a), label=f"{domain}/{a}")
    ax.set_xlabel("open-loop full action agreement on BF16 states"); ax.set_ylabel("closed-loop DB match"); ax.legend(fontsize=7); ax.set_title("Open-loop fidelity vs closed-loop success")
    fig.tight_layout(); fig.savefig(out_dir / "fig6_openloop_vs_closedloop.png", dpi=150); plt.close(fig)


if __name__ == "__main__":
    main()
