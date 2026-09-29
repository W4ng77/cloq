"""r05: does a cheap OPEN-LOOP probe predict WHICH tasks a quantizer breaks or fixes in closed loop (RQ4)?

E3 (scripts/a6000/openloop_d.py) teacher-forces 400 decisions sampled (random.Random(0).shuffle, first 400, sorted) from the
BF16 reference run through each perturbed server and stores per-token flips (analysis/openloop/a6k2/<m>/<cell>.npz;
field 'decision' indexes the 400 sampled decisions). The sample is reconstructed here exactly as openloop_d.load does
and verified token-by-token against the stored BF16 margins (assert). Per task we then compute
  ol_any   fraction of the task's sampled decisions with >= 1 flipped token (under a given cell)
  ol_tool  same, tool-call decisions only (first_tool marks tool-call decisions)
Predictors for a quantizer draw's closed-loop breaks (reference-always-ok tasks) and fixes (always-fail tasks):
  own      the quantizer's own open-loop cell
  gauss    mean over the Gaussian cells with k >= 0.3 (the 'cheap generic probe')
  margin   (control) min BF16 token margin over the task's sampled decisions (negated)
Also the per-cell identity: rho(open-loop decision_any_flip, closed-loop lam from r01) over all cells with both.
Usage: CLOQ_SNAPSHOT=<manifest> python r05_openloop_task.py  (needs out/r01_realloc_<tag>.json) -> out/r05_openloop_task_<tag>.json
"""
import json
import os
import random
import re
from collections import defaultdict

import numpy as np
from scipy.stats import spearmanr

from r_common import OPENLOOP, OUT, RUNS, TAG, dump, load, rnd

MODELS = ("q4", "q8")


def sample(ref_runs):
    out = []
    for r in ref_runs:
        for d in ("retail", "airline"):
            for line in open(RUNS / r / d / "decisions.jsonl"):
                x = json.loads(line)
                if x.get("token_logprobs") and x.get("completion_token_ids"):
                    out.append((x["run_id"], x["domain"], str(x["task_id"]), x["decision_idx"], x["token_margins"]))
    random.Random(0).shuffle(out)
    return sorted(out[:400], key=lambda x: x[:4])


def auc(score, y):
    ok = np.isfinite(score)
    score, y = score[ok], y[ok]
    pos, neg = score[y == 1], score[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def main():
    r01 = json.load(open(OUT / f"r01_realloc_{TAG}.json"))
    res = {"models": {}}
    for m in MODELS:
        cells = sorted(p.stem for p in (OPENLOOP / m).glob("*.json"))
        ref = json.load(open(OPENLOOP / m / f"{cells[0]}.json"))["ref_runs"]
        ds = sample(ref)
        tasks_of = [(d[1], d[2]) for d in ds]
        z0 = np.load(OPENLOOP / m / "bf16_eager.npz")
        marg = np.concatenate([[x if x is not None else np.nan for x in d[4]] for d in ds])
        assert np.allclose(marg, z0["margin"], equal_nan=True), "open-loop sample reconstruction failed"
        per_task = {}
        for c in cells:
            z = np.load(OPENLOOP / m / f"{c}.npz")
            dec, flip, ft = z["decision"], z["flip"], z["first_tool"]
            anyf = np.array([flip[dec == i].any() for i in range(len(ds))], float)
            istool = np.array([ft[dec == i].any() for i in range(len(ds))])
            agg = defaultdict(lambda: [0, 0, 0, 0])
            for i, k in enumerate(tasks_of):
                agg[k][0] += anyf[i]; agg[k][1] += 1
                if istool[i]:
                    agg[k][2] += anyf[i]; agg[k][3] += 1
            per_task[c] = {k: (v[0] / v[1], (v[2] / v[3]) if v[3] else np.nan) for k, v in agg.items()}
        minm = defaultdict(lambda: np.inf)
        for d in ds:
            mm = [x for x in d[4] if x is not None]
            if mm:
                minm[(d[1], d[2])] = min(minm[(d[1], d[2])], min(mm))
        gcells = [c for c in cells if (g := re.match(r"gauss([\d.]+)_s", c)) and float(g.group(1)) >= 0.3]
        Y, meta = load(m)
        U = sorted(r for r in Y if meta[r]["family"] == "null_U")
        Q = sorted(r for r in Y if meta[r]["kind"] == "quant" and "w8" not in r)
        tasks = sorted(set.intersection(*[set(Y[r]) for r in U + Q]) & set(per_task[cells[0]]))
        rows = {}
        for q in Q:
            own = meta[q]["ckpt"] if meta[q]["ckpt"] in per_task else None
            R = [u for u in U if meta[u]["nonce"] != meta[q]["nonce"]]
            pr = np.array([np.mean([Y[u][t] for u in R]) for t in tasks])
            y = np.array([Y[q][t] for t in tasks], float)
            ok, fl = pr == 1, pr == 0
            preds = {"gauss_any": np.array([np.mean([per_task[c][t][0] for c in gcells]) for t in tasks]),
                     "gauss_tool": np.array([np.nanmean([per_task[c][t][1] for c in gcells]) if any(np.isfinite(per_task[c][t][1]) for c in gcells) else np.nan for t in tasks]),
                     "margin": -np.array([minm[t] for t in tasks])}
            if own:
                preds["own_any"] = np.array([per_task[own][t][0] for t in tasks])
                preds["own_tool"] = np.array([per_task[own][t][1] for t in tasks])
            rows[q] = {"n_ok": int(ok.sum()), "n_break": int(((1 - y) * ok).sum()), "n_fail": int(fl.sum()), "n_fix": int((y * fl).sum())}
            for k, s in preds.items():
                rows[q]["break_" + k] = rnd(auc(s[ok], (1 - y)[ok]))
                rows[q]["fix_" + k] = rnd(auc(s[fl], y[fl]))
        keys = sorted({k for r in rows.values() for k in r if k.startswith(("break_", "fix_"))})
        summ = {k: dict(mean=rnd(np.mean([r[k] for r in rows.values() if r.get(k) is not None])),
                        n=sum(r.get(k) is not None for r in rows.values())) for k in keys}
        # cell-level identity: open-loop decision_any_flip vs closed-loop lam (r01)
        fams = r01["models"][m]["families"]
        pts = []
        for f, v in fams.items():
            if v.get("openloop") and v["kind"] in ("quant", "gauss_canon") and (f.startswith("ckpt:") or v["kind"] == "quant"):
                if v["kind"] == "quant" and f.startswith("ckpt:"):
                    continue
                pts.append((f, v["openloop"]["decision_any_flip"], v["openloop"]["flip_rate"], v["lam"],
                            v.get("lam_composed"), v["kind"], v["delta_obs"]))
        lam_use = [p[4] if p[4] is not None else p[3] for p in pts]
        rho = spearmanr([p[1] for p in pts], lam_use) if len(pts) > 3 else None
        rho_d = spearmanr([p[1] for p in pts], [p[6] for p in pts]) if len(pts) > 3 else None
        res["models"][m] = dict(ref_runs=ref, n_sampled_decisions=len(ds), n_tasks=len(tasks), gauss_probe_cells=gcells,
                                auc_summary=summ, per_draw=rows,
                                cell_identity=dict(points=[dict(family=p[0], ol_decision_any_flip=rnd(p[1]), ol_flip_rate=rnd(p[2]),
                                                                lam=p[3], lam_composed=p[4], kind=p[5], delta_obs=p[6]) for p in pts],
                                                   spearman_ol_any_vs_lam=rnd(rho.statistic) if rho else None,
                                                   p=rnd(rho.pvalue) if rho else None, n=len(pts),
                                                   spearman_ol_any_vs_delta_obs=rnd(rho_d.statistic) if rho_d else None,
                                                   p_delta=rnd(rho_d.pvalue) if rho_d else None))
        print(m, {k: v["mean"] for k, v in summ.items()}, "rho(ol, lam)", rnd(rho.statistic) if rho else None, rnd(rho.pvalue) if rho else None,
              "rho(ol, delta)", rnd(rho_d.statistic) if rho_d else None, rnd(rho_d.pvalue) if rho_d else None, len(pts))
    dump("r05_openloop_task", res)


if __name__ == "__main__":
    main()
