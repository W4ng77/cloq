"""Iteration-4 shared helpers: disposition features per trajectory, checkpoint units, dose groups, declared Holm family.

Read-only over runs/ and analysis/openloop/. Re-uses iter_3/r_common.py (run taxonomy, NULL_RULE-stratified null) and
iter_2/common.py (snapshot gate: CLOQ_SNAPSHOT=<manifest>; every trajectory.jsonl is checked against the manifest's
size/mtime so a file changed after the freeze raises instead of being read).

Disposition features (per trajectory = run x domain x task; from trajectory.jsonl messages):
  tool_share     fraction of assistant messages that carry a tool call (act vs talk)
  n_asst         number of assistant messages (turns)
  any_write      1 if any state-changing call (iter_2 WRITE_RE minus transfer_*)
  n_write        number of state-changing calls
  transfer       1 if transfer_to_human_agents was called
  err_rate       tool messages flagged error / tool calls
  notfound_rate  tool errors whose text contains 'not found' / tool calls (hallucinated or mistyped ID proxy)
  confirm_bw     fraction of write calls preceded (since the previous write) by an assistant text that asks for
                 confirmation (contains '?' and one of confirm|proceed|yes|would you like|shall i); NaN if no write
  ask_rate       fraction of assistant text messages containing '?'
  first_write    position of the first write among assistant messages / n_asst; NaN if no write
  max_steps      termination_reason == max_steps
  too_many_err   termination_reason == too_many_errors
  text_len       mean characters of assistant text messages (/100)
The first 12 form the declared disposition vector DISP (text_len is exploratory only).

Dose groups (checkpoints are compared only within model x dose group, so shared dose effects are not counted as
checkpoint-specific): floor {rot_bf16}; small {gauss0.03_s1 fixed}; mid {rtn_w8, rtn_w5, gptq_w5, gauss0.3_s1 fixed};
w4 {rtn/gptq/awq/rot_*/mxfp4/nf4/gshape/rtnsign/rtnsr W4, gauss1_s1 fixed}; w3 {rtn_w3, gptq_w3}.
"""
import json
import os
import pickle
import re
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iter_3"))
sys.path.insert(0, str(HERE.parent / "iter_2"))
from common import RUNS, SNAP, SNAP_PATH, check_frozen, in_snapshot, outcomes_both  # noqa: E402,F401
from r_common import classify, load, rnd  # noqa: E402,F401

OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
CACHE = HERE / ".cache"
CACHE.mkdir(exist_ok=True)
DOMS = ("retail", "airline")
WRITE_RE = re.compile(r"^(cancel|modify|return|exchange|book|update|send)")
CONFIRM_RE = re.compile(r"confirm|proceed|\byes\b|would you like|shall i|do you want", re.I)
DISP = ["tool_share", "n_asst", "any_write", "n_write", "transfer", "err_rate", "notfound_rate", "confirm_bw",
        "ask_rate", "first_write", "max_steps", "too_many_err"]
FEATS = DISP + ["text_len"]
MODELS = os.environ.get("CLOQ_MODELS", "q4,q8,q14,q30a3,q32").split(",")
TAG = os.environ.get("CLOQ_TAG") or (("live_" + SNAP["snapshot_id"]) if SNAP else "unfrozen")

# Declared confirmatory family (Holm, alpha 0.05), fixed before any iter-4 statistic was computed on the snapshot.
DECLARED = {
    "P1": "pooled over models: checkpoint net-success variance within model x dose group (nonce variance removed) "
          "exceeds the independent-landing expectation (within-task permutation of checkpoint labels), one-sided",
    "P2": "pooled over models: disposition-shift fingerprint (cosine same-checkpoint draw pair minus different-checkpoint "
          "same-dose-group pairs) > 0 (permutation of draw-B labels within model x dose group), one-sided",
    "P3": "pooled over models: cross-fitted (draw A dispositions -> draw B net success) LOCO ridge prediction of "
          "dose-group-centred checkpoint net success, Spearman > 0 (permutation within model x dose group), one-sided",
    "P4": "q4: open-loop act-vs-talk logprob contrast at the first decision token predicts the closed-loop tool_share "
          "shift across checkpoints beyond dose: partial Spearman given the open-loop flip rate > 0 (permutation of the "
          "closed-loop shift), one-sided. (Amended 2026-09-29 from raw Spearman to partial-given-flip-rate before any "
          "P4 statistic was computed; P1-P3 had been computed.)",
    "F1": "pooled over models: tasks with a higher rate of near-tied first decision tokens (BF16 first-token margin < 1) "
          "are more fragile (break rate over perturbed draws on null-robust tasks), partial Spearman given n decisions "
          "> 0 (task permutation), one-sided",
}


def dose_group(meta):
    ck, kind = meta["ckpt"], meta["kind"]
    if kind == "gauss_fixed":
        k = float(re.match(r"gauss([\d.]+)_s", ck).group(1))
        return "small" if k < 0.1 else ("mid" if k < 1 else "w4")
    if ck == "rot_bf16":
        return "floor"
    if re.search(r"_w3", ck):
        return "w3"
    if re.search(r"_w(5|8)", ck):
        return "mid"
    return "w4"


def _feat_traj(t):
    msgs = t.get("messages") or []
    asst = [m for m in msgs if m.get("role") == "assistant"]
    tools = [m for m in msgs if m.get("role") == "tool"]
    n_asst = len(asst)
    n_toolmsg = sum(1 for m in asst if m.get("tool_calls"))
    calls, texts = [], []
    writes, confirmed, first_w = 0, 0, None
    asked_since = False
    for i, m in enumerate(asst):
        c = (m.get("content") or "").strip()
        if c:
            texts.append(c)
            if "?" in c and CONFIRM_RE.search(c):
                asked_since = True
        for tc in m.get("tool_calls") or []:
            name = (tc.get("function") or tc).get("name") or ""
            calls.append(name)
            if WRITE_RE.match(name):
                writes += 1
                confirmed += int(asked_since)
                asked_since = False
                if first_w is None:
                    first_w = i
    n_calls = len(calls)
    errs = [m for m in tools if str(m.get("error")) in ("True", "true", "1")]
    nf = sum(1 for m in errs if "not found" in (m.get("content") or "").lower())
    term = t.get("termination_reason")
    return dict(
        tool_share=n_toolmsg / n_asst if n_asst else np.nan, n_asst=n_asst, any_write=float(writes > 0),
        n_write=writes, transfer=float(any(c.startswith("transfer_to_human") for c in calls)),
        err_rate=len(errs) / n_calls if n_calls else 0.0, notfound_rate=nf / n_calls if n_calls else 0.0,
        confirm_bw=confirmed / writes if writes else np.nan,
        ask_rate=np.mean(["?" in c for c in texts]) if texts else np.nan,
        first_write=first_w / n_asst if first_w is not None else np.nan,
        max_steps=float(term == "max_steps"), too_many_err=float(term == "too_many_errors"),
        text_len=np.mean([len(c) for c in texts]) / 100 if texts else np.nan, term=term)


def _parse(args):
    run, dom = args
    p = RUNS / run / dom / "trajectory.jsonl"
    if not p.exists() or not in_snapshot(run):
        return (run, dom), {}
    check_frozen(run, dom, "trajectory.jsonl")
    st = p.stat()
    c = CACHE / f"{run}__{dom}.traj.pkl"
    if c.exists():
        try:
            key, data = pickle.load(open(c, "rb"))
            if key == (st.st_size, st.st_mtime):
                return (run, dom), data
        except Exception:
            pass
    data = {}
    for line in open(p):
        try:
            t = json.loads(line)
        except json.JSONDecodeError:
            continue
        if t.get("termination_reason") == "infrastructure_error":
            continue
        data[str(t["task_id"])] = _feat_traj(t)
    pickle.dump(((st.st_size, st.st_mtime), data), open(c, "wb"))
    return (run, dom), data


def features(runs, procs=24):
    """-> {run: {(dom, task): feature dict}}"""
    todo = [(r, d) for r in runs for d in DOMS]
    out = {r: {} for r in runs}
    with Pool(min(procs, len(todo))) as pool:
        for (r, d), v in pool.imap_unordered(_parse, todo):
            for t, f in v.items():
                out[r][(d, t)] = f
    return out


def model_data(m):
    """Outcomes + features + taxonomy for one model.
    Returns dict(Y, meta, F, U, tasks, units) where units = {ckpt_key: [runs sorted]} for nonce-stratum checkpoints
    (quant + gauss_fixed) and tasks = complete-case over U."""
    Y, meta = load(m)
    U = sorted(r for r in Y if meta[r]["family"] == "null_U")
    K = sorted(r for r in Y if meta[r]["family"] == "null_K")
    tasks = sorted(set.intersection(*[set(Y[u]) for u in U]))
    units = {}
    for r, k in meta.items():
        if k["kind"] in ("quant", "gauss_fixed"):
            key = k["ckpt"] + ("_fixed" if k["kind"] == "gauss_fixed" else "")
            units.setdefault(key, []).append(r)
    units = {k: sorted(v) for k, v in units.items()}
    F = features(list(Y))
    return dict(Y=Y, meta=meta, F=F, U=U, K=K, tasks=tasks, units=units)


def ref_for(run, meta, U):
    """NULL_RULE NR1-3: stratum-matched nonce null minus the nonce-mate of this draw."""
    n = meta[run].get("nonce")
    return [u for u in U if meta[u]["nonce"] != n]


def ymat(Y, runs, tasks):
    return np.array([[Y[r].get(t, np.nan) for t in tasks] for r in runs], float)


def fmat(F, runs, tasks, feats=FEATS):
    """(runs, tasks, feats) array, NaN where missing."""
    return np.array([[[F[r].get(t, {}).get(f, np.nan) for f in feats] for t in tasks] for r in runs], float)


def holm(ps):
    ps = np.asarray(ps, float)
    order = np.argsort(ps)
    adj = np.zeros(len(ps)); run = 0
    for r, i in enumerate(order):
        run = max(run, min(1, (len(ps) - r) * ps[i]))
        adj[i] = run
    return adj


def dump(name, obj):
    p = OUT / f"{name}_{TAG}.json"
    obj = {"_snapshot": {"id": SNAP["snapshot_id"] if SNAP else None, "path": SNAP_PATH, "tag": TAG},
           "_declared": DECLARED, **obj}
    with open(p, "w") as f:
        json.dump(obj, f, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print("wrote", p)
    return p
