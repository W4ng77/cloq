"""Open-loop NLL/token per checkpoint vs closed-loop db_match success (STRATEGY_v2 A4/A5).

NLL/token per checkpoint is recomputed directly from openloop.jsonl as
sum(nll) / sum(n_action_tokens) pooled over both domains (NOT the cached
openloop.summary.json field, which is a mean-of-ratios rather than a token-weighted mean;
both are reported for transparency). Closed-loop success is the pooled db_match rate from
01_checkpoint_success.py's independent recomputation.

Also: a permutation test of Static vs the other 5 trajectory arms on open-loop NLL/token
(STRATEGY_v2 A4: "Static 0.094, 5 trajectory arms 0.075-0.077, arm permutation p=0.0044").
"""
from __future__ import annotations

import json

import numpy as np
from scipy.stats import spearmanr

from common import ARMS, DRAWS, dev_run_dir, openloop_pool, openloop_state_ratios, RUNS, save_json

N_PERM = 100000
SEED = 0


def checkpoint_nll(arm: str, draw: str) -> dict:
    """Two pooled NLL/token conventions, over both domains combined:
    - nll_per_token_weighted: sum(nll)/sum(tokens) (token-weighted; sensitive to long states)
    - nll_per_token_mean: mean over all per-state nll_per_token ratios (unweighted; this is the
      convention behind the cached openloop.summary.json field and appears to match
      STRATEGY_v2's reported NLL numbers, e.g. Static ~0.094)."""
    total_nll = 0.0
    total_tok = 0.0
    n_states = 0
    per_domain = {}
    all_ratios = []
    for dom in ("retail", "airline"):
        rd = dev_run_dir(arm, draw, dom)
        nll, tok, n = openloop_pool(rd)
        ratios = openloop_state_ratios(rd)
        all_ratios.extend(ratios)
        per_domain[dom] = {"nll_per_token_weighted": nll / tok if tok else None, "n_states": n}
        total_nll += nll
        total_tok += tok
        n_states += n
    return {
        "nll_per_token": float(np.mean(all_ratios)) if all_ratios else None,  # primary: mean-of-ratios
        "nll_per_token_weighted": total_nll / total_tok if total_tok else None,
        "n_states": n_states, "per_domain": per_domain,
    }


def mean_diff_perm(a: np.ndarray, b: np.ndarray, n_perm: int, seed: int) -> dict:
    """Two-sample permutation test, statistic = mean(a) - mean(b) (a=static, b=rest)."""
    obs = float(a.mean() - b.mean())
    pool = np.concatenate([a, b])
    na = len(a)
    rng = np.random.default_rng(seed)
    stats = np.empty(n_perm)
    for i in range(n_perm):
        perm = rng.permutation(pool)
        stats[i] = perm[:na].mean() - perm[na:].mean()
    p_two = float((np.abs(stats) >= abs(obs)).mean())
    return {"observed_diff": obs, "p_two_sided": p_two, "n_perm": n_perm}


def main():
    checkpoint_json = json.loads((__import__("pathlib").Path(__file__).parent / "out" / "01_checkpoint_success.json").read_text())
    ckpts = checkpoint_json["checkpoints"]

    nll_by_ckpt = {}
    for arm in ARMS:
        for draw in DRAWS:
            key = f"{arm}_{draw}"
            nll_by_ckpt[key] = checkpoint_nll(arm, draw)

    # RTN has no calibration draw; use runs/rtn_eval directly.
    rtn_ratios = []
    for dom in ("retail", "airline"):
        rtn_ratios.extend(openloop_state_ratios(RUNS / "rtn_eval" / dom))
    rtn_nll_per_tok = float(np.mean(rtn_ratios)) if rtn_ratios else None

    # Static (v0 eval run, matches the "Static 0.094" reference point most directly) as a
    # cross-check against the v1 static_c1/c2/c3 dev checkpoints.
    static_eval_ratios = []
    for dom in ("retail", "airline"):
        static_eval_ratios.extend(openloop_state_ratios(RUNS / "static_eval" / dom))
    static_eval_nll = float(np.mean(static_eval_ratios)) if static_eval_ratios else None

    # Spearman: NLL/token per checkpoint (18 pts) vs pooled / long closed-loop db_match.
    # Reported under BOTH pooling conventions since they turn out to disagree in sign
    # (see RESULTS.md caveat) -- "nll_per_token" = mean-of-per-state-ratios (matches
    # STRATEGY_v2's headline Static/rest/RTN NLL numbers almost exactly), "nll_per_token_weighted"
    # = sum(nll)/sum(tokens) (matches STRATEGY_v2's r=0.05/0.04 correlation numbers almost exactly).
    order = [f"{a}_{d}" for a in ARMS for d in DRAWS]
    pooled_succ = np.array([ckpts[k]["pooled_db_match"] for k in order])
    long_succ = np.array([ckpts[k]["long_db_match"] for k in order])

    nll_vals_mean = np.array([nll_by_ckpt[k]["nll_per_token"] for k in order])
    rho_pooled_mean = spearmanr(nll_vals_mean, pooled_succ).correlation
    rho_long_mean = spearmanr(nll_vals_mean, long_succ).correlation

    nll_vals_weighted = np.array([nll_by_ckpt[k]["nll_per_token_weighted"] for k in order])
    rho_pooled_weighted = spearmanr(nll_vals_weighted, pooled_succ).correlation
    rho_long_weighted = spearmanr(nll_vals_weighted, long_succ).correlation

    # Static-vs-rest permutation test on NLL/token (18 checkpoints: 3 static, 15 rest),
    # under both conventions.
    static_nll = np.array([nll_by_ckpt[f"static_{d}"]["nll_per_token"] for d in DRAWS])
    rest_arms = [a for a in ARMS if a != "static"]
    rest_nll = np.array([nll_by_ckpt[f"{a}_{d}"]["nll_per_token"] for a in rest_arms for d in DRAWS])
    static_vs_rest = mean_diff_perm(static_nll, rest_nll, N_PERM, SEED)

    static_nll_w = np.array([nll_by_ckpt[f"static_{d}"]["nll_per_token_weighted"] for d in DRAWS])
    rest_nll_w = np.array([nll_by_ckpt[f"{a}_{d}"]["nll_per_token_weighted"] for a in rest_arms for d in DRAWS])
    static_vs_rest_weighted = mean_diff_perm(static_nll_w, rest_nll_w, N_PERM, SEED + 1)

    # RTN vs Static ratio
    rtn_vs_static_ratio = rtn_nll_per_tok / static_nll.mean() if static_nll.mean() else None

    result = {
        "nll_by_checkpoint": nll_by_ckpt,
        "rtn_nll_per_token": rtn_nll_per_tok,
        "static_eval_v0_nll_per_token": static_eval_nll,
        "static_c1c2c3_mean_nll_per_token": float(static_nll.mean()),
        "rest_arms_mean_nll_per_token": float(rest_nll.mean()),
        "rtn_vs_static_ratio": rtn_vs_static_ratio,
        "spearman_nll_vs_pooled_success_meanofratios": rho_pooled_mean,
        "spearman_nll_vs_long_success_meanofratios": rho_long_mean,
        "spearman_nll_vs_pooled_success_tokenweighted": rho_pooled_weighted,
        "spearman_nll_vs_long_success_tokenweighted": rho_long_weighted,
        "static_vs_rest_nll_permutation_meanofratios": static_vs_rest,
        "static_vs_rest_nll_permutation_tokenweighted": static_vs_rest_weighted,
    }
    save_json("03_openloop_vs_closedloop.json", result)
    print(f"Static (v1 c1-c3 mean) NLL/token = {static_nll.mean():.4f}; rest arms mean = {rest_nll.mean():.4f}")
    print(f"Static vs rest permutation (mean-of-ratios): diff={static_vs_rest['observed_diff']:.4f} p={static_vs_rest['p_two_sided']:.4f}")
    print(f"Static vs rest permutation (token-weighted): diff={static_vs_rest_weighted['observed_diff']:.4f} p={static_vs_rest_weighted['p_two_sided']:.4f}")
    print(f"RTN NLL/token = {rtn_nll_per_tok:.4f}; ratio to Static = {rtn_vs_static_ratio:.3f}x")
    print(f"Spearman(NLL, pooled success) mean-of-ratios = {rho_pooled_mean:.3f}; token-weighted = {rho_pooled_weighted:.3f}")
    print(f"Spearman(NLL, long success) mean-of-ratios = {rho_long_mean:.3f}; token-weighted = {rho_long_weighted:.3f}")


if __name__ == "__main__":
    main()
