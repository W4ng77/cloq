"""W99g gate check (c3): the instance-name fix leaves every existing Qwen BFCL observation byte-identical.

CPU only, no server. Every recorded episode of the listed BFCL eval runs is replayed through the fork engine
(scripts/ext/fork_ext.py run_env -> bfcl_run.run_item, the code path of every fork branch), each decision forced to the
recorded response, under a fork-branch model name ("cf_" + 12 hex, as run_env names branches). Two passes:
  old  CANON_BRANCH_NAMES = False, _UNALIAS = False  (the code that produced the q4/q8 fork results)
  new  CANON_BRANCH_NAMES = True,  _UNALIAS = True   (the W99g fixes: instance-name canonicalisation, backend unaliasing)
Episodes whose recorded run ended on a context_overflow request end the same way in the replay (the recorded error).
The two passes run in separate process pools; inside a pass each worker process replays many episodes in sequence, so
process-shared backend state is exercised as in a fork task (many episodes per process).
For every decision the replayed observations (json bytes), the prompt messages sent to the agent (sha256) and the
backend-state hash before the decision are compared with the recorded run and between the two passes.

usage (bfcl venv): python analysis/fork/ext_q14_gate/replay_obs_check.py --out analysis/fork/ext_q14_gate/replay_obs_check.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/ext"))

RUNS = ["ext_q4_gptq_w4_d1_bfcl_eval", "ext_q4_bf16_bfcl_eval", "ext_q8_gptq_w4_d1_bfcl_eval", "ext_q8_bf16_bfcl_eval",
        "ext_q14_gptq_w4_d1_bfcl_eval", "ext_q14_bf16_bfcl_eval"]
DOMAINS = ["bfcl_base", "bfcl_miss_param", "bfcl_miss_func", "bfcl_long_context"]


def H(x) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()


_BLK: dict = {}


def job(a):
    run_id, domain, item, fix, label = a
    import io
    import contextlib
    import bfcl_run as BR
    import fork_ext as F
    BR.CANON_BRANCH_NAMES = fix
    BR._UNALIAS = fix
    if (run_id, domain) not in _BLK:
        _BLK.clear()
        _BLK[(run_id, domain)] = F.load_block(run_id, domain)
    blk = _BLK[(run_id, domain)]
    recs = blk["decs"].get(item, [])

    class Pol:
        state_sha = None

        def __call__(self, idx, messages, tools):
            if idx >= len(recs):
                term = blk["traj"][item]["termination_reason"]
                if term in ("context_overflow", "agent_parse_error"):  # the recorded episode ended on this request
                    raise BR.ChatError(term, "recorded termination")
                raise F.ReplayError("beyond recorded")
            return F.raw_from_rec(recs[idx]), 0.0
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            traj, decs = F.run_env("bfcl", domain, item, Pol(), f"w99g|{run_id}|{domain}|{item}|{fix}")
        except Exception as e:
            return {"run_id": run_id, "domain": domain, "item": item, "fix": label, "error": repr(e)[:300]}
    n = min(len(recs), len(decs))
    return {"run_id": run_id, "domain": domain, "item": item, "fix": label, "n_rec": len(recs), "n_rep": len(decs),
            "obs_bytes_eq_rec": [json.dumps(decs[i]["observations"]) == json.dumps(recs[i]["observations"]) for i in range(n)],
            "msgs_eq_rec": [H(decs[i]["messages"]) == H(recs[i]["messages"]) for i in range(n)],
            "obs_sha": [H(d["observations"]) for d in decs], "state": [d.get("state_sha_before") for d in decs],
            "success_eq_rec": traj["success"] == blk["traj"][item]["success"], "term_eq_rec": traj["termination_reason"] == blk["traj"][item]["termination_reason"],
            "n_obs_with_instance_name": sum("_instance" in json.dumps(d["observations"]) for d in decs)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--procs", type=int, default=12)
    a = ap.parse_args()
    import fork_ext as F
    jobs = []
    for r in RUNS:
        for d in DOMAINS:
            items = sorted(json.loads(x)["task_id"] for x in (ROOT / "runs" / r / d / "trajectory.jsonl").read_text().splitlines() if x.strip())
            jobs += [(r, d, i) for i in items]
    t0 = time.time()
    rows = []
    # separate process pools per pass (old code must not pre-contaminate the processes of a new pass); the *_rev passes
    # replay the same episodes in reverse order, so a different process history precedes every episode
    for label, fix, order in ((False, False, 1), ("old_rev", False, -1), (True, True, 1), ("new_rev", True, -1)):
        with mp.get_context("spawn").Pool(a.procs, maxtasksperchild=400) as pool:
            rows += pool.map(job, [(*j, fix, label) for j in jobs[::order]], chunksize=10)
    by = {}
    for x in rows:
        by.setdefault((x["run_id"], x["domain"], x["item"]), {})[x["fix"]] = x
    summ = {}
    bad, old_state_diff = [], []
    for (r, d, i), p in by.items():
        s = summ.setdefault(r, {"items": 0, "decisions": 0, "errors": 0, "obs_eq_rec_new": 0, "obs_eq_rec_old": 0,
                                "msgs_eq_rec_new": 0, "old_new_obs_identical_items": 0, "old_new_state_identical_items": 0,
                                "n_dec_eq_rec_items": 0, "success_eq_rec_items": 0, "obs_with_instance_name": 0,
                                "new_state_history_independent_items": 0, "old_state_history_independent_items": 0,
                                "new_rev_obs_eq_rec_items": 0, "old_rev_obs_eq_rec_items": 0})
        s["items"] += 1
        o, n, orv, nrv = p.get(False), p.get(True), p.get("old_rev"), p.get("new_rev")
        if not all(p.get(k) and not p[k].get("error") for k in (False, True, "old_rev", "new_rev")):
            s["errors"] += 1
            bad.append({"run_id": r, "domain": d, "item": i, "old": (o or {}).get("error"), "new": (n or {}).get("error")})
            continue
        s["decisions"] += n["n_rec"]
        s["obs_eq_rec_new"] += sum(n["obs_bytes_eq_rec"])
        s["obs_eq_rec_old"] += sum(o["obs_bytes_eq_rec"])
        s["msgs_eq_rec_new"] += sum(n["msgs_eq_rec"])
        s["old_new_obs_identical_items"] += o["obs_sha"] == n["obs_sha"]
        s["old_new_state_identical_items"] += o["state"] == n["state"]
        s["n_dec_eq_rec_items"] += n["n_rep"] == n["n_rec"]
        s["success_eq_rec_items"] += n["success_eq_rec"]
        s["obs_with_instance_name"] += n["n_obs_with_instance_name"]
        s["new_state_history_independent_items"] += n["state"] == nrv["state"]
        s["old_state_history_independent_items"] += o["state"] == orv["state"]
        s["new_rev_obs_eq_rec_items"] += all(nrv["obs_bytes_eq_rec"])
        s["old_rev_obs_eq_rec_items"] += all(orv["obs_bytes_eq_rec"])
        if not (all(n["obs_bytes_eq_rec"]) and all(nrv["obs_bytes_eq_rec"]) and o["obs_sha"] == n["obs_sha"] and n["state"] == nrv["state"]
                and n["n_rep"] == n["n_rec"] and all(n["msgs_eq_rec"])):
            bad.append({"run_id": r, "domain": d, "item": i, "new_obs_eq": all(n["obs_bytes_eq_rec"]), "old_eq_new": o["obs_sha"] == n["obs_sha"],
                        "n_rec": n["n_rec"], "n_rep": n["n_rep"], "new_state_history_independent": n["state"] == nrv["state"]})
        if o["state"] != n["state"] or o["state"] != orv["state"]:
            old_state_diff.append({"run_id": r, "domain": d, "item": i, "old_eq_old_rev": o["state"] == orv["state"],
                                   "old_eq_new": o["state"] == n["state"], "obs_identical": o["obs_sha"] == n["obs_sha"] == orv["obs_sha"]})
    tot = {k: sum(v[k] for v in summ.values()) for k in next(iter(summ.values()))}
    res = {"check": "W99g c3: instance-name fix vs old code on recorded Qwen BFCL episodes (replay under a fork-branch name)",
           "runs": RUNS, "domains": DOMAINS, "seconds": time.time() - t0, "per_run": summ, "total": tot, "mismatches": bad,
           "old_code_state_hash_differences": old_state_diff,
           "pass_rule": "new code: every replayed observation byte-equal to the recorded one in both orders, every prompt equal, "
                        "old and new observations identical, new backend-state hashes identical across process histories, no errors",
           "pass": not bad and tot["obs_eq_rec_new"] == tot["decisions"] and tot["msgs_eq_rec_new"] == tot["decisions"] and tot["errors"] == 0}
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("total", "pass", "seconds")}, indent=1))
    print("mismatches", len(bad), bad[:5])
    print("old-code state-hash differences", len(old_state_diff), old_state_diff[:3])


if __name__ == "__main__":
    main()
