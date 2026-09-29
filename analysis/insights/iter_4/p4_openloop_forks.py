"""p4: does the open-loop (teacher-forced, no simulator) logprob shift at policy-fork tokens predict the direction of a
checkpoint's closed-loop behaviour shift and net effect?

Data. E3 (scripts/a6000/openloop_d.py): for 400 decisions sampled from the model's BF16 reference run, every completion
token of the BF16 output is teacher-forced through the perturbed checkpoint. Stored per token: d = logprob_cell(BF16
token) - logprob_bf16(BF16 token), flip, BF16 margin, first_tool, decision index. Only the BF16 token's logprob is stored
(not the alternatives'), so a fork direction is measured as a CONTRAST between decisions where BF16 took one branch and
decisions where it took the other:
  s_act      = mean d(first token | BF16 decision starts with <tool_call>) - mean d(first token | BF16 decision is text)
               > 0: the checkpoint moved probability toward acting (tool call) and away from talking at BF16 contexts
  s_write    = mean d(tool-name token | BF16 called a state-changing tool) - mean d(name token | read-only tool)
  s_transfer = mean d(name token | transfer_to_human_agents) - mean d(name token | other tools) (few events; reported n)
  mean_d, flip_rate: generic degradation (dose proxy).
The E3 decision sample is reconstructed exactly as openloop_d.py draws it (load ref runs in order, random.Random(seed 0)
shuffle, first n, sorted) and verified token by token against the stored BF16 margins.
Closed loop. For the same checkpoint, the per-task disposition shift (common4 features) is averaged over all its draws:
nonce-stratum draws vs U minus nonce-mates (NR1-3); canonical Gaussian cells vs the canonical null K (bf16, bf16_eager).
Net Delta likewise (success rate minus the matching reference).
Declared P4 (common4.DECLARED): q4, across checkpoints with both E3 and closed-loop data, partial Spearman
(s_act, closed-loop tool_share shift | flip_rate) > 0; null = permutation of the closed-loop shift (B = CLOQ_B, default
20000), one-sided. Exploratory: raw Spearman; s_write vs write shifts; s_transfer vs transfer shift; s_act, s_write vs
net Delta; per-cell bootstrap CI of s_act over decisions; leave-one-cell-out range and flip_rate >= 0.02 cells only;
q8 and q30a3 (awq + Gaussian cells only); pooled over the three models (n-weighted mean partial rho, permutation within
model, B/4 replicates).
E3 outputs are not covered by the integrity gate and another session may still be adding cells (q30a3 was being
written during this analysis); every input .npz is pinned by the first 16 hex digits of its sha256 (ol_npz_sha256_16).
Usage: CLOQ_SNAPSHOT=<manifest> [CLOQ_TAG=live_<id>] python p4_openloop_forks.py -> out/p4_openloop_forks_<tag>.json
"""
import hashlib
import json
import os
import random
import re
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, spearmanr

from common4 import DISP, RUNS, WRITE_RE, dump, fmat, model_data, ref_for, rnd, ymat

OPEN = Path("/data/ziyangs/cloq/analysis/openloop/a6k2")
B = int(os.environ.get("CLOQ_B", 20000))
rng = np.random.default_rng(20261001)
POOL = []
TOOL_TOK = "<tool_call>"


def tokenizer(model):
    from transformers import AutoTokenizer
    root = json.load(open(RUNS / f"a6k2_{model}_bf16" / "retail" / "model.json"))["agent_server_models"]["data"][0]["root"]
    return AutoTokenizer.from_pretrained(root)


def e3_sample(ref_runs, n, seed=0):
    out = []
    for r in ref_runs:
        for d in ("retail", "airline"):
            for line in open(RUNS / r / d / "decisions.jsonl"):
                x = json.loads(line)
                if x.get("token_logprobs") and x.get("completion_token_ids"):
                    out.append({k: x[k] for k in ("run_id", "domain", "task_id", "decision_idx", "completion_token_ids",
                                                   "token_margins", "tool_calls")})
    random.Random(seed).shuffle(out)
    return sorted(out[:n], key=lambda x: (x["run_id"], x["domain"], x["task_id"], x["decision_idx"]))


def fork_index(ds, tok):
    """per decision: kind (act/talk), first-token position 0, name-token position (or -1) and tool class."""
    tool_id = tok.convert_tokens_to_ids(TOOL_TOK)
    info = []
    for x in ds:
        ids = x["completion_token_ids"]
        act = ids[0] == tool_id
        pos, cls = -1, None
        if x["tool_calls"]:
            name = (x["tool_calls"][0].get("function") or x["tool_calls"][0]).get("name") or ""
            cls = "transfer" if name.startswith("transfer_to_human") else ("write" if WRITE_RE.match(name) else "read")
            pieces = [tok.decode([i]) for i in ids[:40]]
            for j in range(len(pieces) - 3):
                if pieces[j].strip() == "name" and pieces[j + 1].strip().startswith('":') and pieces[j + 2].strip() == '"':
                    pos = j + 3
                    break
        info.append(dict(act=act, has_tool=bool(x["tool_calls"]), name_pos=pos, cls=cls, n=len(ids)))
    return info


def cell_scores(npz, info, boot=1000):
    z = np.load(npz)
    d, dec = z["d"], z["decision"]
    starts = np.r_[0, np.flatnonzero(np.diff(dec)) + 1]
    d0 = d[starts]
    act = np.array([i["act"] for i in info])
    namepos = np.array([starts[k] + i["name_pos"] if i["name_pos"] >= 0 else -1 for k, i in enumerate(info)])
    cls = np.array([i["cls"] or "" for i in info])
    dn = np.where(namepos >= 0, d[np.maximum(namepos, 0)], np.nan)

    def contrast(v, a, b):
        return np.nanmean(v[a]) - np.nanmean(v[b]) if a.any() and b.any() else np.nan

    has = namepos >= 0
    s_act = contrast(d0, act, ~act)
    bs = []
    for _ in range(boot):
        i = rng.integers(0, len(d0), len(d0))
        bs.append(contrast(d0[i], act[i], ~act[i]))
    return dict(s_act=s_act, s_act_ci=np.nanpercentile(bs, [2.5, 97.5]),
                s_write=contrast(dn, has & (cls == "write"), has & (cls == "read")),
                s_transfer=contrast(dn, has & (cls == "transfer"), has & (cls != "transfer")),
                d_first_act=np.mean(d0[act]), d_first_talk=np.mean(d0[~act]),
                mean_d=float(d.mean()), flip_rate=float(z["flip"].mean()),
                n_act=int(act.sum()), n_talk=int((~act).sum()), n_write=int((has & (cls == "write")).sum()),
                n_read=int((has & (cls == "read")).sum()), n_transfer=int((has & (cls == "transfer")).sum()))


def closed_loop(D, e3_names):
    """per E3 cell name -> closed-loop shift (DISP) and Delta averaged over the checkpoint's draws."""
    meta, Y, U, K, tasks = D["meta"], D["Y"], D["U"], D["K"], D["tasks"]
    m = next(iter(meta)).split("_")[1]
    out = {}
    for nm in e3_names:
        draws = []
        for r, k in meta.items():
            s = r[len(f"a6k2_{m}_"):]
            if k["kind"] == "quant" and k["ckpt"] == nm:
                draws.append((r, ref_for(r, meta, U)))
            elif k["kind"] == "gauss_canon" and s == nm:
                draws.append((r, K))
            elif k["kind"] == "gauss_fixed" and k["ckpt"] == nm:
                draws.append((r, ref_for(r, meta, U)))
        if not draws:
            continue
        sh, dl = [], []
        for r, R in draws:
            tk = [t for t in tasks if t in Y[r] and all(t in Y[u] for u in R)]
            X = fmat(D["F"], [r], tk, DISP)[0]
            X0 = np.nanmean(fmat(D["F"], R, tk, DISP), 0)
            with np.errstate(invalid="ignore"):
                sh.append(np.nanmean(X - X0, 0))
            dl.append(ymat(Y, [r], tk).mean() - ymat(Y, R, tk).mean())
        out[nm] = dict(shift=dict(zip(DISP, np.nanmean(sh, 0))), delta=float(np.mean(dl)), n_draws=len(draws),
                       draws=[r for r, _ in draws])
    return out


def partial_spearman(x, y, z):
    rx, ry, rz = (rankdata(v) for v in (x, y, z))
    Z = np.c_[np.ones_like(rz), rz]
    ex = rx - Z @ np.linalg.lstsq(Z, rx, rcond=None)[0]
    ey = ry - Z @ np.linalg.lstsq(Z, ry, rcond=None)[0]
    return float(np.corrcoef(ex, ey)[0, 1])


def perm_p(x, y, z=None):
    obs = partial_spearman(x, y, z) if z is not None else spearmanr(x, y)[0]
    null = np.array([partial_spearman(x, rng.permutation(y), z) if z is not None else spearmanr(x, rng.permutation(y))[0]
                     for _ in range(B)])
    return dict(rho=rnd(obs, 3), p_one_sided=float((1 + np.sum(null >= obs)) / (1 + B)),
                p_two_sided=float((1 + np.sum(np.abs(null) >= abs(obs))) / (1 + B)), n=len(x))


def main():
    res = {"B": B, "models": {}}
    for m in ("q4", "q8", "q30a3"):
        cells = sorted(p.stem for p in (OPEN / m).glob("*.json") if p.stem not in ("bf16", "bf16_eager"))
        js = json.load(open(OPEN / m / f"{cells[0]}.json"))
        ds = e3_sample(js["ref_runs"], js["n_decisions"])
        # verify reconstruction against the stored BF16 margins
        z = np.load(OPEN / m / f"{cells[0]}.npz")
        mg = np.concatenate([[np.nan if v is None else v for v in (x["token_margins"] or [None] * len(x["completion_token_ids"]))]
                             for x in ds]).astype(np.float32)
        ok = len(mg) == len(z["margin"]) and np.allclose(np.nan_to_num(mg, nan=-9), np.nan_to_num(z["margin"], nan=-9))
        if not ok:
            raise RuntimeError(f"{m}: E3 sample reconstruction does not match stored margins")
        tok = tokenizer(m)
        info = fork_index(ds, tok)
        D = model_data(m)
        cl = closed_loop(D, cells)
        rows = {}
        for c in cells:
            if c not in cl:
                continue
            sc = cell_scores(OPEN / m / f"{c}.npz", info)
            sha = hashlib.sha256(open(OPEN / m / f"{c}.npz", "rb").read()).hexdigest()[:16]
            rows[c] = dict({k: rnd(v, 4) for k, v in sc.items()}, ol_npz_sha256_16=sha, closed={k: rnd(v, 4) for k, v in cl[c]["shift"].items()},
                           delta=rnd(cl[c]["delta"], 4), n_draws=cl[c]["n_draws"], draws=cl[c]["draws"])
        names = sorted(rows)
        g = lambda k: np.array([rows[c][k] for c in names], float)
        gc = lambda k: np.array([rows[c]["closed"][k] for c in names], float)
        s_act, s_wr, s_tr, flip = g("s_act"), g("s_write"), g("s_transfer"), g("flip_rate")
        tests = {}
        tests["s_act~tool_share|flip"] = perm_p(s_act, gc("tool_share"), flip)
        tests["s_act~tool_share raw"] = perm_p(s_act, gc("tool_share"))
        tests["flip~tool_share raw"] = perm_p(flip, gc("tool_share"))
        tests["s_act~delta|flip"] = perm_p(s_act, g("delta"), flip)
        tests["s_act~delta raw"] = perm_p(s_act, g("delta"))
        tests["flip~delta raw"] = perm_p(flip, g("delta"))
        okw = np.isfinite(s_wr)
        tests["s_write~n_write|flip"] = perm_p(s_wr[okw], gc("n_write")[okw], flip[okw])
        tests["s_write~any_write|flip"] = perm_p(s_wr[okw], gc("any_write")[okw], flip[okw])
        tests["s_write~delta|flip"] = perm_p(s_wr[okw], g("delta")[okw], flip[okw])
        okt = np.isfinite(s_tr)
        if okt.sum() >= 5:
            tests["s_transfer~transfer|flip"] = perm_p(s_tr[okt], gc("transfer")[okt], flip[okt])
        # exploratory robustness of the primary contrast: leave-one-cell-out, and cells with flip_rate >= 0.02 only
        y_ts = gc("tool_share")
        loo = {c: rnd(partial_spearman(np.delete(s_act, i), np.delete(y_ts, i), np.delete(flip, i)), 3)
               for i, c in enumerate(names)}
        big = flip >= 0.02
        tests["s_act~tool_share|flip LOO"] = dict(min=min(loo.values()), max=max(loo.values()), per_cell=loo)
        if big.sum() >= 5:
            tests["s_act~tool_share|flip flip>=0.02"] = perm_p(s_act[big], y_ts[big], flip[big])
        POOL.append((s_act, y_ts, flip))
        res["models"][m] = dict(ref_runs=js["ref_runs"], n_decisions=len(ds), reconstruction_verified=bool(ok),
                                n_act=int(sum(i["act"] for i in info)), n_name_found=int(sum(i["name_pos"] >= 0 for i in info)),
                                n_tool_decisions=int(sum(i["has_tool"] for i in info)),
                                n_cls={c: int(sum(i["cls"] == c for i in info)) for c in ("read", "write", "transfer")},
                                cells=rows, tests=tests)
        print(m, len(names), "cells", {k: (v.get("rho"), v.get("p_one_sided"), v.get("min"), v.get("max")) for k, v in tests.items()})
        for c in names:
            r = rows[c]
            print(f"   {c:22s} s_act {r['s_act']:+.3f} {r['s_act_ci']} flip {r['flip_rate']:.3f} tool_share_shift "
                  f"{r['closed']['tool_share']:+.4f} delta {r['delta']:+.3f} s_write {r['s_write']}")
    # exploratory: pooled over models, n-weighted mean of per-model partial rho, permutation within model
    def pooled(perm):
        num = den = 0.0
        for x, y, z in POOL:
            yy = rng.permutation(y) if perm else y
            num += len(x) * partial_spearman(x, yy, z); den += len(x)
        return num / den
    obs = pooled(False)
    null = np.array([pooled(True) for _ in range(B // 4)])
    res["pooled_models_s_act~tool_share|flip"] = dict(rho=rnd(obs, 3), p_one_sided=float((1 + np.sum(null >= obs)) / (1 + len(null))),
                                                     models=["q4", "q8", "q30a3"])
    print("pooled", res["pooled_models_s_act~tool_share|flip"])
    res["primary"] = dict(test="P4", p=res["models"]["q4"]["tests"]["s_act~tool_share|flip"]["p_one_sided"],
                          rho=res["models"]["q4"]["tests"]["s_act~tool_share|flip"]["rho"])
    dump("p4_openloop_forks", res)


if __name__ == "__main__":
    main()
