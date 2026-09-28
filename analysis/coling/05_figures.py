"""Figure-ready plots for the COLING analysis. Reads the JSON produced by 01-03 (run those
first) plus runs/ctx32k_* directly. All figures written as PDFs to analysis/coling/figs/.

(a) per-checkpoint success (pooled & long) for 18 GPTQ ckpts + RTN + BF16, with a placeholder
    hook to overlay a null distribution from runs/null_bf16_n*/ once those dirs exist and are
    completed (none exist yet at the time of writing -- the hook is a no-op then).
(b) NLL/token vs closed-loop success scatter (both pooling conventions).
(c) 8k vs 32k comparison, reading runs/ctx32k_* where completed, skipping incomplete ones.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from common import ARMS, DRAWS, FIGS, OUT, RUNS, task_db_match

FIGS.mkdir(parents=True, exist_ok=True)

ARM_COLORS = {
    "static": "#4c72b0", "fp_traj": "#dd8452", "cloq_all": "#55a868",
    "cloq_novel": "#c44e52", "cloq_matched_random": "#8172b3", "cloq_matched_alt": "#937860",
}


def load_null_bf16() -> list[float] | None:
    """Placeholder hook: overlay a null distribution of BF16 re-roll pooled db_match rates
    from runs/null_bf16_n*/ once that perturbation-null experiment (STRATEGY_v2 E1 /
    COLING_PLAN's '扰动 null') has been run and completed. Returns None (no-op) if no such
    directory exists yet, or if it is not marked completed in all domains."""
    dirs = sorted(glob.glob(str(RUNS / "null_bf16_n*")))
    if not dirs:
        return None
    rates = []
    for d in dirs:
        dp = Path(d)
        ok = all((dp / dom / "status.json").exists() and
                 json.loads((dp / dom / "status.json").read_text()).get("status") == "completed"
                 for dom in ("retail", "airline"))
        if not ok:
            continue
        tasks = {}
        for dom in ("retail", "airline"):
            for tid, v in task_db_match(dp / dom).items():
                tasks[f"{dom}:{tid}"] = v
        if tasks:
            rates.append(float(np.mean(list(tasks.values()))))
    return rates or None


def fig_a():
    d = json.loads((OUT / "01_checkpoint_success.json").read_text())
    ckpts = d["checkpoints"]
    order = [f"{a}_{c}" for a in ARMS for c in DRAWS]
    pooled = [ckpts[k]["pooled_db_match"] for k in order]
    long = [ckpts[k]["long_db_match"] for k in order]
    colors = [ARM_COLORS[ckpts[k]["arm"]] for k in order]
    labels = [f"{ckpts[k]['arm']}\n{ckpts[k]['draw']}" for k in order]

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    x = np.arange(len(order))
    for ax, vals, title in zip(axes, [pooled, long], ["Pooled db_match", "Long-task (BF16 horizon > 11) db_match"]):
        ax.bar(x, vals, color=colors)
        ax.axhline(d["bf16_v1"]["pooled_db_match"] if title.startswith("Pooled") else d["bf16_v1"]["long_db_match"],
                   color="black", ls="--", lw=1.5, label="BF16 (v1)")
        ax.axhline(d["rtn_eval"]["pooled_db_match"] if title.startswith("Pooled") else d["rtn_eval"]["long_db_match"],
                   color="gray", ls=":", lw=1.5, label="RTN")
        null_rates = load_null_bf16()
        if null_rates:
            lo, hi = np.percentile(null_rates, [2.5, 97.5])
            ax.axhspan(lo, hi, color="black", alpha=0.1, label="BF16 perturbation null (95%)")
        ax.set_title(title)
        ax.set_ylabel("db_match rate")
        ax.legend(loc="upper right", fontsize=8)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=90, fontsize=7)
    fig.suptitle("Per-checkpoint closed-loop success: 18 GPTQ arm x draw checkpoints, RTN, BF16")
    fig.tight_layout()
    fig.savefig(FIGS / "fig_a_checkpoint_success.pdf")
    plt.close(fig)
    print("wrote", FIGS / "fig_a_checkpoint_success.pdf", "(null overlay:", "yes" if load_null_bf16() else "no data yet)")


def fig_b():
    d = json.loads((OUT / "03_openloop_vs_closedloop.json").read_text())
    nll_by_ckpt = d["nll_by_checkpoint"]
    ck = json.loads((OUT / "01_checkpoint_success.json").read_text())["checkpoints"]
    order = [f"{a}_{c}" for a in ARMS for c in DRAWS]

    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for ax, conv_key, title in zip(
        axes, ["nll_per_token", "nll_per_token_weighted"],
        ["NLL/token (mean-of-state-ratios)", "NLL/token (token-weighted)"],
    ):
        xs = [nll_by_ckpt[k][conv_key] for k in order]
        ys = [ck[k]["pooled_db_match"] for k in order]
        colors = [ARM_COLORS[ck[k]["arm"]] for k in order]
        ax.scatter(xs, ys, c=colors, s=60, edgecolor="k", linewidth=0.5)
        for arm, color in ARM_COLORS.items():
            ax.scatter([], [], c=color, label=arm)
        ax.set_xlabel(title)
        ax.set_ylabel("Pooled closed-loop db_match")
    axes[0].legend(fontsize=7, loc="upper right")
    rho_mean = d["spearman_nll_vs_pooled_success_meanofratios"]
    rho_w = d["spearman_nll_vs_pooled_success_tokenweighted"]
    axes[0].set_title(f"Spearman rho = {rho_mean:.3f}")
    axes[1].set_title(f"Spearman rho = {rho_w:.3f}")
    fig.suptitle("Open-loop NLL vs closed-loop success (18 GPTQ checkpoints)")
    fig.tight_layout()
    fig.savefig(FIGS / "fig_b_nll_vs_success.pdf")
    plt.close(fig)
    print("wrote", FIGS / "fig_b_nll_vs_success.pdf")


def fig_c():
    # bf16_v1 (not the v0 "bf16" run, which covers the full 114/50-task pool including
    # calibration tasks) is the 8k-harness run over the SAME 58/27 dev task set as ctx32k_bf16.
    pairs = [("bf16_v1", "ctx32k_bf16", "BF16")]
    for cand_arm, run8k in [("static", "static_c1_dev")]:
        run32k = f"ctx32k_{cand_arm}_c1"
        p = RUNS / run32k
        complete = all(
            (p / dom / "status.json").exists() and json.loads((p / dom / "status.json").read_text()).get("status") == "completed"
            for dom in ("retail", "airline")
        )
        if complete:
            pairs.append((run8k, run32k, f"{cand_arm} c1"))
        else:
            print(f"skipping {run32k}: not completed in both domains (8k-vs-32k comparison needs both)")

    rows = []
    for run8k, run32k, label in pairs:
        tasks8 = {}
        tasks32 = {}
        for dom in ("retail", "airline"):
            p8 = RUNS / run8k / dom if not Path(run8k).is_absolute() else Path(run8k) / dom
            p8 = RUNS / run8k / dom
            p32 = RUNS / run32k / dom
            if not (p8 / "trajectory.jsonl").exists() or not (p32 / "trajectory.jsonl").exists():
                continue
            for tid, v in task_db_match(p8).items():
                tasks8[f"{dom}:{tid}"] = v
            for tid, v in task_db_match(p32).items():
                tasks32[f"{dom}:{tid}"] = v
        if not tasks8 or not tasks32:
            continue
        rows.append({
            "label": label, "db_match_8k": float(np.mean(list(tasks8.values()))),
            "db_match_32k": float(np.mean(list(tasks32.values()))),
        })

    if not rows:
        print("fig_c: no complete 8k/32k pairs available yet; writing placeholder-only figure")

    fig, ax = plt.subplots(figsize=(6, 5))
    x = np.arange(len(rows)) if rows else np.arange(1)
    width = 0.35
    labels = [r["label"] for r in rows] or ["(no completed pairs yet)"]
    v8 = [r["db_match_8k"] for r in rows] or [0]
    v32 = [r["db_match_32k"] for r in rows] or [0]
    ax.bar(x - width / 2, v8, width, label="8k harness", color="#4c72b0")
    ax.bar(x + width / 2, v32, width, label="32k harness", color="#dd8452")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Pooled db_match")
    ax.set_title("8k vs 32k context harness (pooled over retail+airline)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGS / "fig_c_8k_vs_32k.pdf")
    plt.close(fig)
    print("wrote", FIGS / "fig_c_8k_vs_32k.pdf", "rows=", rows)
    (OUT / "05c_ctx32k_pairs.json").write_text(json.dumps(rows, indent=2))


if __name__ == "__main__":
    fig_a()
    fig_b()
    fig_c()
