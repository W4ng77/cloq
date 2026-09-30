"""Integrity gate + frozen snapshot manifest (review v2 must-do 2, W-A). Read-only over runs/ and the queue.

For every run-domain an iter-2 analysis can touch (runs/a6k2_* and runs/a6000_*, smoke runs excluded) check:
  G1 status      status.json status == "completed" and metrics.json present;
  G2 infra       infrastructure_error episodes are counted and LISTED as missing (not a failure of the gate; the
                 analyses drop them, common.INFRA);
  G3 dedup       decisions.jsonl carries exactly one trajectory_id per task (post-W8 dedup);
  G4 counts      per task, #decision records == #assistant turns in trajectory.jsonl (or that minus the greeting),
                 decision_idx is 0..n-1 without gaps, trajectory.jsonl has one record per task, and the task sets of
                 metrics.json / trajectory.jsonl / task_manifest.json agree; every decisions record carries this run id;
  G5 nonce       environment.json prompt_nonce == the nonce the queue task intended for this run id
                 (queue/{done,running,todo,failed,legacy_v1}/*.json runs[].nonce; canonical = None), and the
                 system-prompt hash is one value per run-domain and consistent across runs: same (model, domain,
                 nonce) -> same system_sha256, different nonce -> different hash;
  G6 pending     the run id is not written by a *_redo task in queue/todo or queue/running (fail); a completed run whose
                 id is also written by another pending task (requeued after a runner crash, null_extra still running)
                 is admitted at its current hash with a warning (an unfinished one already fails G1);
  G7 canary      (informational) canonical BF16 compiled runs: a numerics-canary record ok=true for the same
                 host + slurm job + model before the run started (logs/canary.log). The first server of a model writes
                 the reference without a log line, so a missing record is reported, not failed.
A run is FROZEN (admitted) iff all its domains pass G1, G3, G4, G5, G6. Frozen runs are hashed (sha256 of
decisions.jsonl, trajectory.jsonl, metrics.json; size + mtime too, so common.py can refuse files changed after the
freeze). Also recorded: sha256 of docs/insights/NULL_RULE.md (the pre-declared null-admission rule) so its precedence
over the snapshot can be checked.

Usage: python integrity.py [--out out/snapshot_<utc>.json]   (prints the path; exit 0 even if runs are excluded)
"""
import argparse
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
RUNS = ROOT / "runs"
Q = Path("/data/ziyangs/cloq_work/queue")
CANARY = Path("/data/ziyangs/cloq_work/logs/canary.log")
HERE = Path(__file__).resolve().parent
DOMS = ("retail", "airline", "telecom")  # telecom: *_tel_* runs only (W44); consumers keep their own DOMS
INFRA = "infrastructure_error"
R_HEAD = re.compile(r'\{"run_id": "([^"]*)".*?"task_id": "([^"]*)", "trajectory_id": "([^"]*)", "decision_idx": (\d+)')
R_SYS = re.compile(r'"system_sha256": "([0-9a-f]+)"')


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def queue_map():
    """run_id -> list of (queue dir, task id, nonce); pending run ids (todo/running)."""
    m = defaultdict(list); pending = defaultdict(list)
    for d in ("done", "running", "todo", "failed", "legacy_v1"):
        for f in sorted((Q / d).glob("*.json")):
            try:
                t = json.load(open(f))
            except Exception:
                continue
            for r in t.get("runs") or []:
                rid = r.get("run_id")
                if not rid:
                    continue
                m[rid].append((d, t["id"], r.get("nonce")))
                if d in ("todo", "running"):
                    pending[rid].append(f"{d}/{f.name}")
    return m, pending


def check_domain(args):
    run, dom, want_hash = args
    p = RUNS / run / dom
    r = {"fail": [], "warn": []}
    st = p / "status.json"
    status = json.load(open(st)).get("status") if st.exists() else None
    r["status"] = status
    if status != "completed":
        r["fail"].append(f"G1 status={status}")
    mp = p / "metrics.json"
    per = {}
    if mp.exists():
        try:
            per = {str(t["task_id"]): t for t in json.load(open(mp))["per_task"]}
        except Exception as e:
            r["fail"].append(f"G1 metrics unreadable: {e}")
    else:
        r["fail"].append("G1 no metrics.json")
    r["n_tasks"] = len(per)
    r["infra_missing"] = sorted(t for t, x in per.items() if x.get("termination_reason") == INFRA)
    tm = p / "task_manifest.json"
    man = set(json.load(open(tm))["task_ids"]) if tm.exists() else None
    if man is not None and set(per) != man and per:
        r["fail"].append(f"G4 metrics tasks {len(per)} != manifest {len(man)}")
    # trajectory
    tp = p / "trajectory.jsonl"; na = {}; ntraj = Counter()
    if tp.exists():
        for ln in open(tp):
            try:
                x = json.loads(ln)
            except json.JSONDecodeError:
                r["fail"].append("G4 trajectory.jsonl has an unparsable line"); continue
            t = str(x["task_id"]); ntraj[t] += 1
            na[t] = sum(1 for m in x.get("messages") or [] if m.get("role") == "assistant")
    else:
        r["fail"].append("G4 no trajectory.jsonl")
    dup = sorted(t for t, c in ntraj.items() if c > 1)
    if dup:
        r["fail"].append(f"G4 trajectory.jsonl: {len(dup)} tasks with >1 record")
    if per and na and set(na) != set(per):
        r["fail"].append(f"G4 trajectory tasks {len(na)} != metrics tasks {len(per)}")
    # decisions
    dp = p / "decisions.jsonl"; tids = defaultdict(set); idx = defaultdict(list); runids = Counter(); syss = Counter()
    nbad = 0
    if dp.exists():
        for ln in open(dp):
            m = R_HEAD.match(ln)
            if not m:
                nbad += 1; continue
            rid, t, tj, i = m.groups(); runids[rid] += 1
            tids[t].add(tj); idx[t].append(int(i))
            s = R_SYS.search(ln)
            syss[s.group(1) if s else None] += 1
    else:
        r["fail"].append("G3 no decisions.jsonl")
    if nbad:
        r["fail"].append(f"G4 {nbad} decisions lines without the expected header")
    multi = sorted(t for t, s in tids.items() if len(s) > 1)
    r["tasks_multi_trajectory"] = multi
    if multi:
        r["fail"].append(f"G3 {len(multi)} tasks with >1 trajectory_id (dedup not applied)")
    if set(runids) - {run}:
        r["fail"].append(f"G4 decisions carry run ids {sorted(set(runids) - {run})}")
    mism = []; gaps = []
    for t in set(na) | set(idx):
        n = len(idx.get(t, []))
        if sorted(idx.get(t, [])) != list(range(n)):
            gaps.append(t)
        a = na.get(t)
        if a is None or n not in (a, a - 1):
            mism.append((t, n, a))
    miss_ok = set(r["infra_missing"])
    hard = [x for x in mism if x[0] not in miss_ok]
    r["count_mismatch"] = [list(x) for x in mism]
    if hard:
        r["fail"].append(f"G4 {len(hard)} tasks with decision count != assistant turns (non-infra)")
    if [t for t in gaps if t not in miss_ok]:
        r["fail"].append(f"G4 {len(gaps)} tasks with decision_idx gaps/duplicates")
    r["n_decisions"] = sum(len(v) for v in idx.values())
    r["system_sha256"] = sorted(k for k in syss if k)
    if len(r["system_sha256"]) != 1:
        r["fail"].append(f"G5 {len(r['system_sha256'])} distinct system prompts in one run-domain")
    env = json.load(open(p / "environment.json")) if (p / "environment.json").exists() else {}
    r["prompt_nonce"] = env.get("prompt_nonce")
    r["host"] = env.get("hostname"); r["job"] = env.get("slurm_job_id"); r["started"] = env.get("timestamp")
    r["model_id"] = env.get("model_id")
    # file identity
    r["files"] = {}
    for f in ("decisions.jsonl", "trajectory.jsonl", "metrics.json"):
        fp = p / f
        if fp.exists():
            s = fp.stat()
            r["files"][f] = {"size": s.st_size, "mtime": s.st_mtime, "sha256": sha256(fp) if want_hash else None}
    return run, dom, r


def canary_records():
    out = []
    if CANARY.exists():
        for ln in open(CANARY):
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                pass
    return out


def model_of(run):
    m = re.match(r"^(a6k2|a6000)_(?:det_)?([a-z0-9]+)_", run)
    return m.group(2) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--procs", type=int, default=32)
    a = ap.parse_args()
    utc = datetime.now(timezone.utc)
    sid = utc.strftime("%Y%m%dT%H%MZ")
    out = Path(a.out) if a.out else HERE / "out" / f"snapshot_{sid}.json"
    qmap, pending = queue_map()
    runs = sorted(p.name for p in RUNS.iterdir() if p.is_dir() and p.name.startswith(("a6k2_", "a6000_"))
                  and "_smoke" not in p.name)
    jobs = [(r, d, True) for r in runs for d in DOMS if (RUNS / r / d).is_dir()]
    with Pool(a.procs) as pool:
        res = pool.map(check_domain, jobs, chunksize=1)
    per = defaultdict(dict)
    for run, dom, r in res:
        per[run][dom] = r
    can = canary_records()
    # G5 intended nonce + G6 pending + G7 canary
    for run, doms in per.items():
        intents = {n for (_, _, n) in qmap.get(run, [])}
        src = sorted({f"{d}/{t}" for (d, t, _) in qmap.get(run, [])})
        for dom, r in doms.items():
            r["queue_tasks"] = src
            if not intents:
                r["warn"].append("G5 run id not found in any queue task (intended nonce unknown)")
                r["intended_nonce"] = "unknown"
            elif len(intents) > 1:
                r["fail"].append(f"G5 queue tasks disagree on the nonce: {sorted(map(str, intents))}")
                r["intended_nonce"] = sorted(map(str, intents))
            else:
                want = next(iter(intents)); r["intended_nonce"] = want
                if (want or None) != (r["prompt_nonce"] or None):
                    r["fail"].append(f"G5 prompt_nonce {r['prompt_nonce']} != intended {want}")
            if run in pending:
                redo = [x for x in pending[run] if x.endswith("_redo.json")]
                if redo:
                    r["fail"].append(f"G6 pending *_redo re-run: {redo}")
                else:  # a completed run of a task that is queued/running again (e.g. requeued after a runner crash):
                    # admitted at its current hash; common.py refuses it if the file changes after the freeze
                    r["warn"].append(f"G6 run id also written by pending task(s) {pending[run]}; frozen at current hash")
            if re.search(r"_(bf16|null_n\d+)$", run) or re.search(r"_det_[a-z0-9]+_[ab]$", run):
                m = model_of(run)
                t0 = datetime.fromisoformat(r["started"]).timestamp() if r.get("started") else None
                ok = [c for c in can if c.get("role") == "agent" and c.get("model") == m and c.get("host") == r["host"]
                      and str(c.get("job")) == str(r["job"]) and (t0 is None or c["time"] <= t0 + 60)]
                r["canary"] = ("ok" if ok and all(c["ok"] for c in ok[-1:]) else "no record")
    # G5 cross-run system-prompt consistency
    groups = defaultdict(set); byhash = defaultdict(set)
    for run, doms in per.items():
        m = model_of(run)
        for dom, r in doms.items():
            if len(r["system_sha256"]) == 1 and run.startswith("a6k2_"):
                groups[(m, dom, r["prompt_nonce"])].add(r["system_sha256"][0])
                byhash[(dom, r["system_sha256"][0])].add(r["prompt_nonce"])
    incons = {f"{k[0]}/{k[1]}/{k[2]}": sorted(v) for k, v in groups.items() if len(v) > 1}
    collide = {f"{k[0]}/{k[1][:12]}": sorted(map(str, v)) for k, v in byhash.items() if len(v) > 1}
    for run, doms in per.items():
        m = model_of(run)
        for dom, r in doms.items():
            k = f"{m}/{dom}/{r['prompt_nonce']}"
            # canonical prompts of different model families may legitimately differ (X1 AWQ tokenizer identical, so no)
            if run.startswith("a6k2_") and k in incons:
                r["warn"].append(f"G5 system prompt differs from other runs with the same (model, domain, nonce)")
    frozen, excluded = {}, {}
    for run, doms in sorted(per.items()):
        fails = [f"{d}: {x}" for d, r in doms.items() for x in r["fail"]]
        need = {"telecom"} if "_tel_" in run else {"retail", "airline"}  # W44: telecom runs are single-domain by design
        if set(doms) != need and not run.endswith("_cal") and "_det_" not in run:
            fails.append(f"domain set {sorted(doms)} != expected {sorted(need)}")
        if fails:
            excluded[run] = fails
        else:
            frozen[run] = {d: {"files": r["files"], "n_tasks": r["n_tasks"], "infra_missing": r["infra_missing"],
                               "n_decisions": r["n_decisions"], "prompt_nonce": r["prompt_nonce"],
                               "canary": r.get("canary")} for d, r in doms.items()}
    nr = ROOT / "docs/insights/NULL_RULE.md"
    snap = {"snapshot_id": sid, "utc": utc.strftime("%Y-%m-%dT%H:%M:%SZ"), "script": str(Path(__file__).resolve()),
            "gate": "G1 status, G3 dedup, G4 counts, G5 nonce, G6 pending must pass; G2 infra listed as missing; G7 info",
            "null_rule": {"path": str(nr), "sha256": sha256(nr) if nr.exists() else None,
                          "mtime_utc": datetime.fromtimestamp(nr.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if nr.exists() else None},
            "queue_pending_run_ids": {k: v for k, v in sorted(pending.items())},
            "n_runs_scanned": len(per), "n_frozen": len(frozen), "n_excluded": len(excluded),
            "system_prompt_inconsistent_groups": incons, "system_prompt_shared_across_nonces": collide,
            "frozen": frozen, "excluded": excluded,
            "detail": {run: {d: {k: v for k, v in r.items() if k != "files"} for d, r in doms.items()}
                       for run, doms in sorted(per.items())}}
    out.parent.mkdir(exist_ok=True)
    json.dump(snap, open(out, "w"), indent=1)
    n_infra = sum(len(r["infra_missing"]) for doms in per.values() for r in doms.values())
    print(f"snapshot {sid}: scanned {len(per)} runs, frozen {len(frozen)}, excluded {len(excluded)}, "
          f"infra-missing episodes in scanned runs {n_infra}")
    for run, f in excluded.items():
        print("  EXCL", run, "|", "; ".join(f)[:300])
    if incons:
        print("  system-prompt inconsistent groups:", incons)
    if collide:
        print("  system prompts shared across nonces:", collide)
    print(out)


if __name__ == "__main__":
    main()
