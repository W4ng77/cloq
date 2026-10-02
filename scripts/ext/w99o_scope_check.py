"""W99o: scope of the process-shared BFCL long-context backend state (W99g) in the historical eval runs and fork outputs.

CPU only, no server. Uses the fixed code (bfcl_run W99g unaliasing on), under which a replayed episode's backend state
does not depend on process history (W99g c3), so its per-decision state hashes are the *pristine* ones.

Part A (eval runs). Every recorded episode of every BFCL eval run's bfcl_long_context block (the only category whose
backends load module-level constants: `_load_scenario(long_context=True)`; each eval domain runs in its own
bfcl_run.py process, so other categories never share a process with a long-context backend) is replayed with every
decision forced to the recorded response. An eval run is unaffected iff, for every episode, every replayed observation
is byte-equal to the recorded one, the decision count, termination and the official success equal the recorded ones
(the official evaluator runs inside the replay, on unaliased instances).

Part B (fork outputs). For every state of every BFCL long_context fork directory, the backend-state hash at t frozen by
the divergence search (states/<sid>.json state_sha) and every branch's hash before each replayed step (branches/<sid>.json
state_shas) are compared with the pristine hashes from Part A for the same Q-block episode. A fork directory is clean
iff every state's search hash and every branch hash equals the pristine one. (Any mutation of a shared constant changes
the hash of every TravelAPI long-context instance built after it, so a clean directory also shows that no mutation
happened before its last branch started.)

usage (bfcl venv): python scripts/ext/w99o_scope_check.py --out analysis/fork/ext/w99o/scope_check.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ext"))
DOMAIN = "bfcl_long_context"


def H(x) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()


_BLK: dict = {}


def job(a):
    run_id, item = a
    import contextlib
    import io
    import bfcl_run as BR
    import fork_ext as F
    assert BR._UNALIAS and BR.CANON_BRANCH_NAMES
    if run_id not in _BLK:
        _BLK.clear()
        _BLK[run_id] = F.load_block(run_id, DOMAIN)
    blk = _BLK[run_id]
    recs = blk["decs"].get(item, [])

    class Pol:
        state_sha = None

        def __call__(self, idx, messages, tools):
            if idx >= len(recs):
                term = blk["traj"][item]["termination_reason"]
                if term in ("context_overflow", "agent_parse_error"):
                    raise BR.ChatError(term, "recorded termination")
                raise F.ReplayError("beyond recorded")
            return F.raw_from_rec(recs[idx]), 0.0
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            traj, decs = F.run_env("bfcl", DOMAIN, item, Pol(), f"w99o|{run_id}|{item}")
        except Exception as e:
            return {"run_id": run_id, "item": item, "error": repr(e)[:300]}
    n = min(len(recs), len(decs))
    tr = blk["traj"][item]
    return {"run_id": run_id, "item": item, "n_rec": len(recs), "n_rep": len(decs),
            "obs_eq": all(json.dumps(decs[i]["observations"]) == json.dumps(recs[i]["observations"]) for i in range(n)),
            "msgs_eq": all(H(decs[i]["messages"]) == H(recs[i]["messages"]) for i in range(n)),
            "success_rec": bool(tr["success"]), "success_rep": bool(traj["success"]),
            "term_eq": traj["termination_reason"] == tr["termination_reason"],
            "state": [d.get("state_sha_before") for d in decs]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--procs", type=int, default=12)
    a = ap.parse_args()
    t0 = time.time()
    runs = sorted(p.name for p in (ROOT / "runs").glob("ext_*_bfcl_eval") if (p / DOMAIN / "trajectory.jsonl").exists())
    jobs = [(r, json.loads(x)["task_id"]) for r in runs
            for x in (ROOT / "runs" / r / DOMAIN / "trajectory.jsonl").read_text().splitlines() if x.strip()]
    with mp.get_context("spawn").Pool(a.procs, maxtasksperchild=200) as pool:
        rows = pool.map(job, jobs, chunksize=8)
    pristine = {(x["run_id"], x["item"]): x["state"] for x in rows if "error" not in x}
    evals = {}
    for x in rows:
        s = evals.setdefault(x["run_id"], {"episodes": 0, "errors": 0, "obs_mismatch": [], "n_dec_mismatch": [], "success_mismatch": [],
                                           "term_mismatch": [], "n_success_rec": 0, "n_success_rep": 0})
        s["episodes"] += 1
        if "error" in x:
            s["errors"] += 1
            continue
        s["n_success_rec"] += x["success_rec"]
        s["n_success_rep"] += x["success_rep"]
        for k, ok in (("obs_mismatch", x["obs_eq"] and x["msgs_eq"]), ("n_dec_mismatch", x["n_rec"] == x["n_rep"]),
                      ("success_mismatch", x["success_rec"] == x["success_rep"]), ("term_mismatch", x["term_eq"])):
            if not ok:
                s[k].append(x["item"])
    for s in evals.values():
        s["unaffected"] = s["errors"] == 0 and not any(s[k] for k in ("obs_mismatch", "n_dec_mismatch", "success_mismatch", "term_mismatch"))

    forks = {}
    for d in sorted((ROOT / "analysis/fork/ext/dev").glob("bfcl_*_long_context")):
        if not (d / "branches.json").exists():
            forks[d.name] = {"incomplete": True}
            continue
        eff = {json.loads(l)["state_id"]: json.loads(l) for l in (d / "effects.jsonl").read_text().splitlines() if l.strip()}
        f = {"states": 0, "search_hash_contaminated": 0, "any_branch_contaminated": 0, "by_branch_contaminated": {},
             "replay_flag_false": 0, "flag_true_but_contaminated": 0, "contaminated_state_ids": [], "no_pristine": 0}
        for sp in sorted((d / "states").glob("*.json")):
            st = json.loads(sp.read_text())
            pr = pristine.get((st["run_id"], st["task_id"]))
            f["states"] += 1
            if pr is None:
                f["no_pristine"] += 1
                continue
            t = st["decision_idx"]
            br = json.loads((d / "branches" / sp.name).read_text())
            s_bad = st.get("state_sha") != pr[t]
            b_bad = {b: r.get("state_shas") != pr[:t + 1] for b, r in br.items() if not r.get("error")}
            bad = s_bad or any(b_bad.values())
            f["search_hash_contaminated"] += s_bad
            for b, v in b_bad.items():
                f["by_branch_contaminated"][b] = f["by_branch_contaminated"].get(b, 0) + v
            f["any_branch_contaminated"] += any(b_bad.values())
            flag = eff.get(st["state_id"], {}).get("replay")
            f["replay_flag_false"] += flag is False
            f["flag_true_but_contaminated"] += bool(flag) and bad
            if bad:
                f["contaminated_state_ids"].append(st["state_id"])
        f["n_contaminated"] = len(f["contaminated_state_ids"])
        f["clean"] = f["n_contaminated"] == 0 and f["no_pristine"] == 0
        forks[d.name] = f
    res = {"check": "W99o scope of the process-shared BFCL long-context backend state (scripts/ext/w99o_scope_check.py)",
           "code": {"bfcl_run_sha256": hashlib.sha256((ROOT / "scripts/ext/bfcl_run.py").read_bytes()).hexdigest(),
                    "fork_ext_sha256": hashlib.sha256((ROOT / "scripts/ext/fork_ext.py").read_bytes()).hexdigest()},
           "seconds": round(time.time() - t0, 1), "eval_runs": evals, "fork_dirs": forks,
           "affected_eval_runs": [r for r, s in evals.items() if not s["unaffected"]],
           "contaminated_fork_dirs": [k for k, v in forks.items() if not v.get("clean", False) and not v.get("incomplete")]}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps({"affected_eval_runs": res["affected_eval_runs"], "contaminated_fork_dirs": res["contaminated_fork_dirs"],
                      "forks": {k: {kk: v.get(kk) for kk in ("states", "n_contaminated", "replay_flag_false", "search_hash_contaminated",
                                                              "by_branch_contaminated", "flag_true_but_contaminated")} for k, v in forks.items()},
                      "seconds": res["seconds"]}, indent=1))


if __name__ == "__main__":
    main()
