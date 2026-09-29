"""Review items 3 and 6 (W2): is the per-decision "floor" an exact-tie property of bf16 logits? Text vs tool hazard.

Margins are logged as logprob(top1) - logprob(top2) rounded to 1e-4 (cloq/agent.py `_token_margins`); vLLM 0.29 computes
the lm_head in the model dtype (bf16) unless `--hf-overrides '{"head_dtype": "float32"}'` is set
(vllm/model_executor/layers/logits_processor.py `_apply_head`, vllm/config/model.py `head_dtype`), so a logged margin
of exactly 0 is an exact tie of two bf16 logits, broken by argmax index order.

A. Reference tie density (bf16 run, plus *_bf16_cal for q30a3/q32): per decision kind, fraction of decisions with
   at least one m == 0 token, with min margin in (0, 0.25), tokens with m == 0 per decision, smallest non-zero margins.
B. Closed loop, every clean cell vs its reference (pairing as iter_1 v01; tasks with infrastructure_error dropped):
   per-decision hazard overall / text / tool (events / decisions at risk, kind of the reference decision);
   the reference margin of the first flipped token (0 / (0,.125] / (.125,.25] / ... ); per-bin token hazard
   (flips / tokens at risk, tokens at risk = every token up to and including the first flip).
   Predictions of the per-decision hazard: full = mean over at-risk reference decisions of 1 - prod_j (1 - h_bin(m_j));
   tie-only = the same with h = 0 outside the m == 0 bin (share of the floor carried by exact ties).
   Cross-model: q4's floor-cell h_bin applied to q8/q14 reference margins vs their observed hazard.
C. Open loop (E3 npz, analysis/openloop/a6k2/<m>/<cell>.npz; teacher-forced on the bf16 reference contexts, no
   survivorship): P(flip | m == 0), P(flip | 0 < m <= 0.125), ..., decision-any-flip by decision kind (sample rebuilt
   as in scripts/a6000/openloop_d.py: seed 0 shuffle, first 400, sorted), and the share of flipped decisions whose
   flips include an exact-tie token.
Usage: python p02_ties.py  -> out/p02_ties.json
"""
import json
import random
import re
from collections import defaultdict

import numpy as np

from common import DOMS, ROOT, RUNS, dump, fam, first_div, infra_tasks, load_many, now, ref_for, runs_for

BINS = [("0", 0, 0), ("(0,0.125]", 1e-9, 0.125), ("(0.125,0.25]", 0.125 + 1e-9, 0.25), ("(0.25,0.5]", 0.25 + 1e-9, 0.5),
        ("(0.5,1]", 0.5 + 1e-9, 1), ("(1,2]", 1 + 1e-9, 2), (">2", 2 + 1e-9, 1e9)]
FLOOR = re.compile(r"_(bf16_eager|gauss0\.00[13]_s\d|gauss0\.01_s\d|gauss0\.03_s\d|rtn_w8_n\d|null_n\d)$")


def bin_of(m):
    if m is None:
        return None
    for name, lo, hi in BINS:
        if lo <= m <= hi:
            return name
    return None


def tie_density(dec):
    res = {}
    for kind in ("text", "tool"):
        ds = [r for r in dec.values() if r["kind"] == kind and r["m"]]
        if not ds:
            continue
        ms = [[m for m in r["m"] if m is not None] for r in ds]
        allm = np.array([m for x in ms for m in x])
        nz = allm[allm > 0]
        vals, cnt = np.unique(nz[nz < 0.3], return_counts=True) if len(nz) else ([], [])
        res[kind] = {"n_decisions": len(ds), "n_tokens": int(len(allm)),
                     "frac_dec_with_exact_tie": round(float(np.mean([any(m == 0 for m in x) for x in ms])), 4),
                     "frac_dec_min_in_(0,0.25)": round(float(np.mean([bool(x) and 0 < min(x) < 0.25 for x in ms])), 4),
                     "exact_ties_per_decision": round(float(np.mean([sum(m == 0 for m in x) for x in ms])), 3),
                     "frac_tokens_exact_tie": round(float(np.mean(allm == 0)), 5),
                     "frac_tokens_(0,0.25)": round(float(np.mean((allm > 0) & (allm < 0.25))), 5),
                     "smallest_nonzero_margins": {str(round(float(v), 4)): int(c) for v, c in list(zip(vals, cnt))[:8]}}
    return res


def pair(R, P, key, drop):
    rows = [r for r in first_div(R, P, key) if (r[0], r[1]) not in drop]
    risk = defaultdict(int); ev = defaultdict(int)
    tok_risk = defaultdict(int); tok_flip = defaultdict(int)
    first_bin = defaultdict(int)
    at_risk_decs = []  # (ref decision) for predictions
    for dom, t, i, e, kind, n, why in rows:
        for j in range(i):
            b = R[(dom, t, j)]
            risk[b["kind"]] += 1
            at_risk_decs.append(b)
            for m in b["m"]:
                tok_risk[bin_of(m)] += 1
        if why == "agent":
            b, p = R[(dom, t, i)], P[(dom, t, i)]
            risk[b["kind"]] += 1; ev[b["kind"]] += 1
            at_risk_decs.append(b)
            a, q = b["ids"], p["ids"]
            jj = next((x for x in range(min(len(a), len(q))) if a[x] != q[x]), min(len(a), len(q)))
            for x in range(min(jj + 1, len(b["m"]))):
                tok_risk[bin_of(b["m"][x])] += 1
            fb = bin_of(b["m"][jj]) if jj < len(b["m"]) else None
            tok_flip[fb] += 1
            first_bin[fb] += 1
    n_ev = sum(ev.values()); n_risk = sum(risk.values())
    # task-bootstrap 95% CI of the per-decision hazard (as iter_1 v01 `hazard_ci`)
    e_arr = np.array([1 if r[6] == "agent" else 0 for r in rows]); x_arr = np.array([r[2] + (1 if r[6] == "agent" else 0) for r in rows])
    J = np.random.default_rng(7).integers(0, len(rows), size=(2000, len(rows))) if rows else None
    hz_ci = None
    if rows and x_arr.sum():
        bs = e_arr[J].sum(1) / np.maximum(x_arr[J].sum(1), 1)
        hz_ci = [round(float(np.quantile(bs, .025)), 4), round(float(np.quantile(bs, .975)), 4)]
    h_bin = {k: tok_flip[k] / tok_risk[k] for k in tok_risk if tok_risk[k]}
    out = {"n_tasks": len(rows), "events": n_ev, "decisions_at_risk": n_risk,
           "hazard": round(n_ev / n_risk, 4) if n_risk else None, "hazard_ci95_task_boot": hz_ci,
           "hazard_text": round(ev["text"] / risk["text"], 4) if risk["text"] else None,
           "hazard_tool": round(ev["tool"] / risk["tool"], 4) if risk["tool"] else None,
           "risk_by_kind": dict(risk), "events_by_kind": dict(ev),
           "first_flip_ref_margin_bin": {k or "none": v for k, v in first_bin.items()},
           "share_first_flips_exact_tie": round(first_bin["0"] / n_ev, 4) if n_ev else None,
           "token_hazard_by_bin": {k or "none": {"risk": tok_risk[k], "flips": tok_flip[k], "h": round(h_bin.get(k, 0), 5)}
                                   for k in tok_risk},
           "n_censored_ctx_first": sum(1 for r in rows if r[6] == "ctx")}
    return out, h_bin, at_risk_decs


def predict(decs, h_bin, tie_only=False):
    if not decs:
        return None
    ps = []
    for b in decs:
        q = 1.0
        for m in b["m"]:
            k = bin_of(m)
            if tie_only and k != "0":
                continue
            q *= 1 - h_bin.get(k, 0.0)
        ps.append(1 - q)
    return round(float(np.mean(ps)), 4)


def openloop(model):
    base = ROOT / "analysis/openloop/a6k2" / model
    if not base.exists():
        return None
    ref = f"a6k2_{model}_bf16"
    ds = []
    for d in DOMS:
        for line in open(RUNS / ref / d / "decisions.jsonl"):
            x = json.loads(line)
            if x.get("token_logprobs") and x.get("completion_token_ids"):
                ds.append((x["run_id"], x["domain"], x["task_id"], x["decision_idx"], bool(x.get("tool_calls")),
                           len(x["completion_token_ids"])))
    random.Random(0).shuffle(ds)
    ds = sorted(ds[:400], key=lambda x: (x[0], x[1], x[2], x[3]))
    kinds = np.array(["tool" if x[4] else "text" for x in ds])
    ntok = np.array([x[5] for x in ds])
    res = {}
    for f in sorted(base.glob("*.npz")):
        z = np.load(f)
        dec, flip, marg = z["decision"], z["flip"], z["margin"]
        counts = np.bincount(dec, minlength=len(ds))
        ok = len(counts) == len(ds) and np.array_equal(counts, ntok)
        r = {"sample_rebuilt_ok": bool(ok), "n_tokens": int(len(flip))}
        for name, lo, hi in BINS:
            sel = (marg >= lo) & (marg <= hi)
            if sel.any():
                r[f"flip|m in {name}"] = {"n": int(sel.sum()), "p": round(float(flip[sel].mean()), 4)}
        anyflip = np.zeros(len(ds), bool); tieflip = np.zeros(len(ds), bool); hastie = np.zeros(len(ds), bool)
        np.logical_or.at(anyflip, dec, flip)
        np.logical_or.at(tieflip, dec, flip & (marg == 0))
        np.logical_or.at(hastie, dec, marg == 0)
        if ok:
            for k in ("text", "tool"):
                s = kinds == k
                r[f"decision_any_flip_{k}"] = round(float(anyflip[s].mean()), 4)
                r[f"frac_dec_with_tie_{k}"] = round(float(hastie[s].mean()), 4)
                r[f"decision_flip_given_tie_{k}"] = round(float(anyflip[s & hastie].mean()), 4) if (s & hastie).any() else None
                r[f"decision_flip_given_no_tie_{k}"] = round(float(anyflip[s & ~hastie].mean()), 4) if (s & ~hastie).any() else None
            r["n_text"] = int((kinds == "text").sum()); r["n_tool"] = int((kinds == "tool").sum())
        r["decision_any_flip"] = round(float(anyflip.mean()), 4)
        r["share_flipped_decisions_with_tie_flip"] = round(float(tieflip[anyflip].mean()), 4) if anyflip.any() else None
        res[f.stem] = r
    return res


def main():
    res = {"snapshot_utc": now(), "tie_density": {}, "closed_loop": {}, "open_loop": {}, "cross_model": {}}
    for m in ("q30a3", "q32"):
        cal = f"a6k2_{m}_bf16_cal"
        if (RUNS / cal).exists():
            res["tie_density"][m + " (cal run)"] = tie_density(load_many([cal])[cal])
    floor_h = {}
    for model in ("q4", "q8", "q14"):
        runs = runs_for(model)
        pairs = [(r, *ref_for(model, r, runs)) for r in runs if r != f"a6k2_{model}_bf16"]
        det = f"a6k2_det_{model}_a"
        if (RUNS / det).exists():
            pairs.append((det, f"a6k2_{model}_bf16", "sha"))
        need = sorted({x for p in pairs for x in p[:2]} | {f"a6k2_{model}_bf16"})
        D = load_many(need)
        ref = D[f"a6k2_{model}_bf16"]
        res["tie_density"][model] = tie_density(ref)
        cl = {}
        pooled_tok = defaultdict(lambda: [0, 0])
        for run, rr, key in pairs:
            if not D.get(run) or not D.get(rr):
                continue
            drop = infra_tasks(run) | infra_tasks(rr)
            o, h_bin, decs = pair(D[rr], D[run], key, drop)
            if o["n_tasks"] < 10 or o["decisions_at_risk"] == 0:
                continue
            o["family"] = fam(run, model); o["ref"] = rr
            o["pred_hazard_full"] = predict(decs, h_bin)
            o["pred_hazard_tie_only"] = predict(decs, h_bin, tie_only=True)
            cl[run] = o
            if FLOOR.search(run):
                for k, v in o["token_hazard_by_bin"].items():
                    pooled_tok[k][0] += v["flips"]; pooled_tok[k][1] += v["risk"]
            print(model, run, o["hazard"], o["hazard_text"], o["hazard_tool"], "tie share", o["share_first_flips_exact_tie"],
                  "pred", o["pred_hazard_full"], o["pred_hazard_tie_only"])
        res["closed_loop"][model] = cl
        floor_h[model] = {k: f / r for k, (f, r) in pooled_tok.items() if r}
        res.setdefault("floor_token_hazard_pooled", {})[model] = {k: {"flips": f, "risk": r, "h": round(f / r, 5)}
                                                                    for k, (f, r) in pooled_tok.items() if r}
        # all reference decisions (not only at-risk ones) for cross-model transfer
        res.setdefault("_refdecs", {})[model] = list(ref.values())
        res["open_loop"][model] = openloop(model)
    # cross-model: q4 floor token hazard applied to other models' reference decisions
    q4h = {("none" if k is None else k): v for k, v in floor_h.get("q4", {}).items()}
    q4h = {(None if k == "none" else k): v for k, v in q4h.items()}
    for model in ("q4", "q8", "q14"):
        decs = res["_refdecs"][model]
        obs = [v["hazard"] for r, v in res["closed_loop"][model].items() if FLOOR.search(r) and v["hazard"] is not None]
        obs_text = [v["hazard_text"] for r, v in res["closed_loop"][model].items() if FLOOR.search(r) and v["hazard_text"] is not None]
        res["cross_model"][model] = {
            "pred_all_decisions_q4_floor_h": predict(decs, q4h),
            "pred_text_decisions_q4_floor_h": predict([d for d in decs if d["kind"] == "text"], q4h),
            "pred_tie_only_q4_floor_h": predict(decs, q4h, tie_only=True),
            "own_floor_h_pred": predict(decs, {(None if k == "none" else k): v for k, v in floor_h[model].items()}),
            "observed_floor_hazard_range": [min(obs), max(obs)] if obs else None,
            "observed_floor_hazard_median": float(np.median(obs)) if obs else None,
            "observed_floor_text_hazard_median": float(np.median(obs_text)) if obs_text else None,
            "floor_cells": sorted(r for r in res["closed_loop"][model] if FLOOR.search(r))}
        print("cross", model, res["cross_model"][model])
    res.pop("_refdecs")
    dump("p02_ties.json", res)


if __name__ == "__main__":
    main()
