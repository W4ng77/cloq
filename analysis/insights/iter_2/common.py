"""Shared loaders for iteration-2 prep analyses (review items 1-9). Read-only over runs/ and analysis/openloop/.

Conventions follow analysis/insights/iter_1/verify/v01_legacy_recompute.py and v03/v04 so numbers are comparable:
  * outcome y(t) = db_match AND normal termination (metrics.json per_task, else tau2_results.json for live runs);
  * pairing: null_n* vs bf16 on conversation context excluding the system prompt ("ctx"); quantised cells with a
    nonce vs their same-nonce null on prompt_sha; everything else vs bf16 on prompt_sha;
  * first divergence = first decision whose completion token ids differ on an identical context (event), or whose
    context already differs (censored: the environment/simulator diverged first).
A compact per-(run, domain) decision cache is kept in iter_2/.cache (keyed on file size + mtime) so repeated scripts
do not re-parse the 30-40 MB decisions.jsonl files.
"""
import hashlib
import json
import os
import pickle
import re
from collections import defaultdict
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path("/data/ziyangs/cloq")
RUNS = ROOT / "runs"
HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
CACHE = HERE / ".cache"
OUT.mkdir(exist_ok=True)
CACHE.mkdir(exist_ok=True)
DOMS = ("retail", "airline")
WRITE_RE = re.compile(r"^(cancel|modify|return|exchange|book|update|send|transfer)")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _strip(x):
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if k not in ("id", "tool_call_id")}
    if isinstance(x, list):
        return [_strip(v) for v in x]
    return x


def _calls(r):
    out = []
    for tc in r.get("tool_calls") or []:
        # decisions.jsonl stores tau2-style calls {"name", "arguments"} at top level (checked on a6k2 and a6000 runs);
        # OpenAI-style {"function": {...}} is accepted too. iter_1/common.py action_key reads only the latter, so
        # its tool actions all normalise to (None, None).
        fn = tc.get("function") or tc
        a = fn.get("arguments")
        try:
            a = json.dumps(json.loads(a) if isinstance(a, str) else a, sort_keys=True)
        except Exception:
            a = str(a)
        out.append((fn.get("name"), a))
    return tuple(out)


def _parse(args):
    run, dom = args
    p = RUNS / run / dom / "decisions.jsonl"
    if not p.exists():
        return (run, dom), {}
    st = p.stat()
    c = CACHE / f"{run}__{dom}.pkl"
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
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        ctx = hashlib.sha1(json.dumps([_strip(m) for m in r.get("messages") or [] if m.get("role") != "system"],
                                      sort_keys=True, default=str).encode()).hexdigest()
        data[(str(r["task_id"]), int(r["decision_idx"]))] = dict(
            sha=r.get("prompt_sha256"), ctx=ctx, ids=r.get("completion_token_ids") or [],
            m=r.get("token_margins") or [], kind="tool" if r.get("tool_calls") else "text", calls=_calls(r),
            content=(r.get("content") or "").strip())
    pickle.dump(((st.st_size, st.st_mtime), data), open(c, "wb"))
    return (run, dom), data


_MEM = {}


def load_many(runs, procs=24):
    todo = [(r, d) for r in runs for d in DOMS if (r, d) not in _MEM]
    if todo:
        with Pool(min(procs, len(todo))) as pool:
            for k, v in pool.imap_unordered(_parse, todo):
                _MEM[k] = v
    return {r: {(d, t, i): v for d in DOMS for (t, i), v in _MEM[(r, d)].items()} for r in runs}


INFRA = "infrastructure_error"
# iter-2 rule (differs from iter_1/verify): an episode ended by infrastructure_error (agent or simulator server
# unreachable, e.g. a6k2_q4_null_n3..n5 and a6k2_q8_{gauss1_s1,rtn_w3_n*} after node003's simulator died at 19:43:43,
# /data/ziyangs/cloq_work/logs/tasks/a6k2_q4_bf16.log) is MISSING, not a failure. Set CLOQ_INFRA_AS_FAIL=1 for the
# iter-1 convention.
INFRA_AS_FAIL = os.environ.get("CLOQ_INFRA_AS_FAIL") == "1"


def outcomes(run, dom, with_reason=False):
    mp = RUNS / run / dom / "metrics.json"
    rows = []
    if mp.exists():
        for t in json.load(open(mp))["per_task"]:
            rows.append((str(t["task_id"]), int(bool(t["db_match"]) and not t.get("premature")), t.get("termination_reason")))
    else:
        p = RUNS / run / dom / "tau2_results.json"
        if not p.exists():
            return {}
        try:
            sims = json.load(open(p)).get("simulations", [])
        except json.JSONDecodeError:
            return {}
        for s in sims:
            db = ((s.get("reward_info") or {}).get("db_check") or {}).get("db_match")
            tr = s.get("termination_reason")
            rows.append((str(s["task_id"]), int(bool(db) and tr in ("user_stop", "agent_stop")), tr))
    if with_reason:
        return {t: (y, tr) for t, y, tr in rows}
    return {t: y for t, y, tr in rows if INFRA_AS_FAIL or tr != INFRA}


def infra_tasks(run):
    return {(d, t) for d in DOMS for t, (y, tr) in outcomes(run, d, True).items() if tr == INFRA}


def outcomes_both(run):
    return {(d, t): v for d in DOMS for t, v in outcomes(run, d).items()}


def runs_for(model, pfx="a6k2"):
    return sorted(p.name for p in RUNS.iterdir()
                  if p.is_dir() and p.name.startswith(f"{pfx}_{model}_") and not p.name.endswith("_cal"))


def fam(run, model):
    """Family label, as in verify/v04_pooled_draws.py."""
    s = re.sub(rf"^(a6000|a6k2)_{model}_", "", run)
    if s in ("bf16", "bf16_eager") or s.startswith("null_n"):
        return "null:" + ("bf16" if s == "bf16" else "eager" if s == "bf16_eager" else "nonce")
    s = re.sub(r"_(s\d|n\d|d\d_n\d)$", "", s)
    return re.sub(r"_d\d$", "", s)


def ref_for(model, run, runs, pfx="a6k2"):
    """Reference run + pairing key, as in verify/v01_legacy_recompute.py."""
    m = re.search(r"_n(\d+)$", run)
    if "_null_" in run:
        return f"{pfx}_{model}_bf16", "ctx"
    if m and f"{pfx}_{model}_null_n{m.group(1)}" in runs:
        return f"{pfx}_{model}_null_n{m.group(1)}", "sha"
    return f"{pfx}_{model}_bf16", ("ctx" if m else "sha")


def first_div(R, P, key):
    """rows: (dom, task, i, event, kind_of_ref_decision_at_i, n_ref_decisions)."""
    nref = defaultdict(int)
    for (d, t, i) in R:
        nref[(d, t)] = max(nref[(d, t)], i + 1)
    rows = []
    for dom, t in sorted({k[:2] for k in R} & {k[:2] for k in P}):
        i = 0
        while True:
            b, p = R.get((dom, t, i)), P.get((dom, t, i))
            if b is None or p is None:
                rows.append((dom, t, i, 0, None, nref[(dom, t)], "end")); break
            if b[key] != p[key]:
                rows.append((dom, t, i, 0, b["kind"], nref[(dom, t)], "ctx")); break
            if b["ids"] != p["ids"]:
                rows.append((dom, t, i, 1, b["kind"], nref[(dom, t)], "agent")); break
            i += 1
    return rows


def boot_mean_clusters(clusters, rng, B=4000):
    """clusters: dict key -> list of row values. Returns point, bootstrap array (ratio of sums)."""
    keys = list(clusters)
    sums = np.array([sum(clusters[k]) for k in keys], float)
    cnts = np.array([len(clusters[k]) for k in keys], float)
    J = rng.integers(0, len(keys), size=(B, len(keys)))
    bs = sums[J].sum(1) / cnts[J].sum(1)
    return float(sums.sum() / cnts.sum()), bs


def dump(name, obj):
    p = OUT / name
    with open(p, "w") as f:
        json.dump(obj, f, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print("wrote", p)
