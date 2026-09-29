"""E3: open-loop logit shift D of a served checkpoint on the model's own BF16 reference contexts.

For a deterministic sample of decisions from the BF16 reference run(s), teacher-force prompt + BF16 completion through
the served cell (prompt_logprobs=1) and compare each completion token's log-probability with the one BF16 logged in
closed loop (`token_logprobs` in decisions.jsonl, same serving numerics). Per token we keep:
  d      = logprob_cell(tok) - logprob_bf16(tok)
  flip   = the BF16 token is no longer the cell's argmax (rank > 1)
  margin = BF16's own top-1 minus runner-up at that position (`token_margins`)
Output: <out>.json (summary: |d| quantiles, flip rate overall / by BF16 margin bin / on the first token of tool calls)
and <out>.npz (per-token arrays) for the insight agents. Plan: docs/insights/EXPERIMENTS.md (E3).

usage (inside a worker, server already up):
  python scripts/a6000/openloop_d.py --port 8003 --ref-run a6k2_q4_bf16 --n 400 --out analysis/openloop/q4/rtn_w4
"""

from __future__ import annotations

import argparse
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests

ROOT = Path("/data/ziyangs/cloq")
MARGIN_BINS = [0, 0.25, 0.5, 1, 2, 4, 8, 1e9]


def load(ref_runs: list[str]) -> list[dict]:
    out = []
    for r in ref_runs:
        for d in ("retail", "airline"):
            for line in open(ROOT / "runs" / r / d / "decisions.jsonl"):
                x = json.loads(line)
                if x.get("token_logprobs") and x.get("completion_token_ids"):
                    out.append({k: x[k] for k in ("run_id", "domain", "task_id", "decision_idx", "prompt_token_ids",
                                                   "completion_token_ids", "token_logprobs", "token_margins", "tool_calls")})
    return out


def score(port: int, d: dict) -> dict:
    ids = d["prompt_token_ids"] + d["completion_token_ids"]
    body = {"model": "agent", "prompt": ids, "max_tokens": 1, "temperature": 0.0, "prompt_logprobs": 1,
            "return_token_ids": True}
    r = requests.post(f"http://127.0.0.1:{port}/v1/completions", json=body, timeout=1800)
    r.raise_for_status()
    pl = r.json()["choices"][0]["prompt_logprobs"]
    n = len(d["completion_token_ids"])
    lp, rank = [], []
    for tok, ent in zip(d["completion_token_ids"], pl[-n:]):
        e = ent.get(str(tok)) or ent.get(tok)
        lp.append(e["logprob"])
        rank.append(e.get("rank", 1))
    return {"lp": lp, "rank": rank}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--ref-run", action="append", required=True)
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ds = load(a.ref_run)
    random.Random(a.seed).shuffle(ds)
    ds = sorted(ds[:a.n], key=lambda x: (x["run_id"], x["domain"], x["task_id"], x["decision_idx"]))
    with ThreadPoolExecutor(a.concurrency) as ex:
        res = list(ex.map(lambda d: score(a.port, d), ds))
    dd, flip, marg, first_tool, dec = [], [], [], [], []
    for i, (d, r) in enumerate(zip(ds, res)):
        m = d["token_margins"] or [np.nan] * len(r["lp"])
        for j, (lp_c, rk, lp_b) in enumerate(zip(r["lp"], r["rank"], d["token_logprobs"])):
            dd.append(lp_c - lp_b)
            flip.append(rk > 1)
            marg.append(m[j] if j < len(m) and m[j] is not None else np.nan)
            first_tool.append(j == 0 and bool(d["tool_calls"]))
            dec.append(i)
    dd, flip, marg, first_tool, dec = map(np.asarray, (dd, flip, marg, first_tool, dec))
    ad = np.abs(dd)
    summ = {"ref_runs": a.ref_run, "n_decisions": len(ds), "n_tokens": int(len(dd)),
            "abs_d_quantiles": {str(q): float(np.quantile(ad, q)) for q in (0.5, 0.9, 0.99)},
            "abs_d_mean": float(ad.mean()), "frac_tokens_shifted": float((ad > 1e-3).mean()),
            "flip_rate": float(flip.mean()),
            "decision_any_flip": float(np.mean([flip[dec == i].any() for i in range(len(ds))])),
            "first_token_flip_rate": float(flip[np.r_[0, np.flatnonzero(np.diff(dec)) + 1]].mean()),
            "flip_by_bf16_margin": {}}
    for lo, hi in zip(MARGIN_BINS[:-1], MARGIN_BINS[1:]):
        sel = (marg >= lo) & (marg < hi)
        if sel.any():
            summ["flip_by_bf16_margin"][f"[{lo},{hi})"] = {"n": int(sel.sum()), "flip": float(flip[sel].mean()),
                                                         "abs_d_median": float(np.median(ad[sel]))}
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(str(out) + ".npz", d=dd.astype(np.float32), flip=flip, margin=marg.astype(np.float32),
                        first_tool=first_tool, decision=dec.astype(np.int32))
    Path(str(out) + ".json").write_text(json.dumps(summ, indent=1))
    print(json.dumps({k: summ[k] for k in ("n_tokens", "abs_d_quantiles", "flip_rate", "decision_any_flip")}))


if __name__ == "__main__":
    main()
