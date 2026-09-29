"""Iteration-3 shared helpers (quantization-centred insights). Read-only over runs/ and analysis/openloop/.

Re-uses the iteration-2 snapshot machinery (analysis/insights/iter_2/common.py): set CLOQ_SNAPSHOT to a manifest
written by analysis/insights/iter_2/integrity.py. Two manifests are used in iteration 3:
  * frozen  analysis/insights/iter_2/out/snapshot_20260929T0732Z.json  (the iteration-2 frozen set; primary where it suffices)
  * live    analysis/insights/iter_3/out/snapshot_live_<utc>.json      (same gate, run later; adds the churn controls,
            the fresh-nonce quantizer draws *_q3..q5, q4 nulls n3..n5 redo; PROVISIONAL)
Outputs go to analysis/insights/iter_3/out/<name>_<tag>.json where tag = frozen | live (from the manifest name).

Run taxonomy (per model m, run a6k2_<m>_<s>):
  null U   : null_n<k>                (nonce prompt, reference weights)
  null K   : bf16, bf16_eager         (canonical prompt, reference weights)
  gauss canonical cell : gauss<k>_s<seed>           (one checkpoint per seed, canonical prompt)
  gauss fixed control  : gauss<k>_s<seed>_q<j>      (one checkpoint, fresh nonces 6d1f0b3e / f07a5c21)
  quantizer draw       : <q>_n<j> | <q>_q<j>        (q in rtn_w8/w4/w3, awq_w4, gptq_w4_d1/d2, gptq_w3; one deterministic
                                                     checkpoint per q, drawn under nonces; n1/n2 reuse null n1/n2 nonces)
"""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iter_2"))
from common import RUNS, SNAP, SNAP_PATH, outcomes_both, runs_for  # noqa: E402

OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
OPENLOOP = Path("/data/ziyangs/cloq/analysis/openloop/a6k2")
MIN_TASKS = 77
TAG = ("live" if SNAP_PATH and "live" in os.path.basename(SNAP_PATH) else "frozen") if SNAP_PATH else "unfrozen"
QUANT_RE = re.compile(r"^(rtn_w\d|awq_w\d|gptq_w\d(?:_d\d)?)_(?:n|q)\d+$")
GCTL_RE = re.compile(r"^(gauss[\d.]+_s\d+)_q\d+$")
GCAN_RE = re.compile(r"^(gauss([\d.]+))_s\d+$")


def nonce_of(run):
    for d in ("retail", "airline"):
        p = RUNS / run / d / "environment.json"
        if p.exists():
            return json.load(open(p)).get("prompt_nonce")
    return None


def classify(run, model):
    """-> dict(kind, ckpt, family, stratum) or None (skipped)."""
    s = re.sub(rf"^a6k2_{model}_", "", run)
    if s.startswith("null_n"):
        return dict(kind="null", ckpt="ref", family="null_U", stratum="nonce")
    if s in ("bf16", "bf16_eager"):
        return dict(kind="null", ckpt="ref", family="null_K", stratum="canonical")
    m = QUANT_RE.match(s)
    if m:
        ck = m.group(1)
        return dict(kind="quant", ckpt=ck, family=re.sub(r"_d\d$", "", ck), stratum="nonce")
    m = GCTL_RE.match(s)
    if m:
        ck = m.group(1)
        return dict(kind="gauss_fixed", ckpt=ck, family=re.sub(r"_s\d+$", "", ck) + "_fixed", stratum="nonce")
    m = GCAN_RE.match(s)
    if m:
        return dict(kind="gauss_canon", ckpt=s, family=m.group(1), stratum="canonical")
    return None


def load(model):
    """Y[run] = {(dom, task): 0/1}; meta[run] = classify() + nonce. Runs with < MIN_TASKS scored tasks dropped."""
    Y, meta = {}, {}
    for r in runs_for(model, ctl=True):
        c = classify(r, model)
        if c is None:
            continue
        y = outcomes_both(r)
        if len(y) < MIN_TASKS:
            continue
        Y[r] = y
        meta[r] = dict(c, nonce=nonce_of(r))
    return Y, meta


def openloop(model, cell):
    p = OPENLOOP / model / f"{cell}.json"
    if not p.exists():
        return None
    d = json.load(open(p))
    return {k: d.get(k) for k in ("abs_d_mean", "flip_rate", "decision_any_flip", "first_token_flip_rate", "n_decisions")}


def weight_err(run):
    p = RUNS / run / "quantization.json"
    if not p.exists():
        return None
    return json.load(open(p)).get("mean_rel_weight_err")


def dump(name, obj):
    p = OUT / f"{name}_{TAG}.json"
    obj = {"_snapshot": {"id": SNAP["snapshot_id"] if SNAP else None, "path": SNAP_PATH, "tag": TAG}, **obj}
    with open(p, "w") as f:
        json.dump(obj, f, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print("wrote", p)
    return p


def rnd(x, k=4):
    if x is None:
        return None
    if isinstance(x, (list, tuple, np.ndarray)):
        return [rnd(v, k) for v in list(x)]
    return round(float(x), k)
