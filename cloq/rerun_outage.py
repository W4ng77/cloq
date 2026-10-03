"""W100w (F3): re-run only the outage episodes of a run-domain. Opt-in: CLOQ_RERUN_OUTAGE=1 (worker.py sets it for a task
with a `rerun_outage` list); without it cloq/run_arm.py never imports this module.

Why: worker.py fails a task whose run-domain holds 'outage' infrastructure_error episodes (W6), run_arm skips a completed
run-domain, and tau2's own resume drops every infrastructure_error episode (also the context overflows that W10 counts as
agent failures). So a plain retry re-fails without re-running anything (W100q §1.1).

With the flag, for a run-domain whose tau2_results.json exists:
 1. plan(): classify each episode like worker.py's W6/W10 check (is_outage); keep every non-outage episode (incl.
    context_overflow / parse / empty-output ones); todo = outage + never-run task ids (missing ones are needed for a
    complete run-domain and are reported separately).
 2. archive into runs/<id>/<domain>/rerun_outage/<tag>/orig/: big files as read-only hard links (no extra disk; any later
    in-place write to the original fails loudly instead of altering it), small files as copies. Nothing is deleted.
 3. run_arm runs only `todo` as its own tau2 run in rerun_outage/<tag>/ (own results, decisions, config, environment,
    status; resumable: an unfinished <tag> is resumed from its archive, never from the run-domain files).
 4. merge(): each re-run episode takes the slot of the episode it replaces (same task id, trial and seed, checked),
    never-run ones are appended; decisions of re-run task ids are replaced by the re-run's records (run_arm's W8 pass then
    keeps each task's final attempt). run_arm then writes trajectory / metrics / status as usual and the worker re-runs
    its W6 check on the merged run-domain.
"""
from __future__ import annotations

import hashlib, json, os, shutil
from datetime import datetime, timezone
from pathlib import Path

LINK = ("tau2_results.json", "decisions.jsonl")
COPY = ("status.json", "metrics.json", "trajectory.jsonl", "infra_causes.json", "config.json", "environment.json",
        "model.json", "task_manifest.json", "loop_guard.jsonl")
MIN_FREE = 512 << 20  # bytes left free on /data after the merged copies (quota at ~1 GB free on 2026-10-03 08:15 PDT)


def is_outage(sim: dict) -> bool:
    """worker.py run_eval classify() == 'outage' (W6/W10/W41/W92/W99p); toolcall_side() never returns 'outage'."""
    if str(sim.get("termination_reason")) != "infrastructure_error":
        return False
    e = str((sim.get("info") or {}).get("error", ""))
    return not ("ContextWindowExceeded" in e or "only supports single tool-calls" in e
                or ("Function name was" in e and "must be a-z" in e)
                or "AssistantMessage must have either content or tool_calls" in e or "validation error for ToolCall" in e)


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def _plan(res: Path, run_dir: Path) -> dict | None:
    r = json.load(open(res))
    sims = r.get("simulations") or []
    outage = [str(s["task_id"]) for s in sims if is_outage(s)]
    kept = {str(s["task_id"]) for s in sims if not is_outage(s)}
    todo = [str(t["id"]) for t in r["tasks"] if str(t["id"]) not in kept]
    if not todo:
        return None
    cf = run_dir / "infra_causes.json"  # the worker's own classification must agree (fail loud otherwise)
    if res.parent == run_dir and cf.exists():
        w = sorted(t for t, c in json.load(open(cf)).items() if c == "outage")
        if w != sorted(outage):
            raise RuntimeError(f"rerun_outage {run_dir}: infra_causes.json outages {w} != classified {sorted(outage)}")
    tag = hashlib.sha256(",".join(todo).encode()).hexdigest()[:8]
    return {"dir": run_dir / "rerun_outage" / tag, "todo": todo, "outage": outage,
            "missing": [t for t in todo if t not in outage], "seeds": sorted({s.get("seed") for s in sims})}


def plan(run_dir: Path) -> dict | None:
    """Re-run plan for a run-domain, or None (no tau2_results.json, or nothing to re-run): run_arm's normal path."""
    base = run_dir / "rerun_outage"
    for o in sorted(base.glob("*/orig")) if base.exists() else []:
        if not (o.parent / "merged.json").exists():  # an interrupted re-run or merge: resume it from its archive
            return _plan(o / "tau2_results.json", run_dir)
    res = run_dir / "tau2_results.json"
    if not res.exists() or res.stat().st_size == 0:
        return None
    p = _plan(res, run_dir)
    if p is None:
        return None
    need = sum((run_dir / f).stat().st_blocks * 512 for f in LINK if (run_dir / f).exists())
    st = os.statvfs(run_dir)
    if st.f_bavail * st.f_frsize < need + MIN_FREE:
        raise RuntimeError(f"rerun_outage {run_dir}: {st.f_bavail * st.f_frsize >> 20} MB free < {(need + MIN_FREE) >> 20} MB")
    tmp, o = p["dir"] / "orig.tmp", p["dir"] / "orig"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    man = {"archived": datetime.now(timezone.utc).isoformat(), "plan": {k: v for k, v in p.items() if k != "dir"}, "files": {}}
    for f in LINK + COPY:
        src = run_dir / f
        if src.exists():
            if f in LINK:
                os.chmod(src, 0o444)
                os.link(src, tmp / f)
            else:
                shutil.copy2(src, tmp / f)
            man["files"][f] = {"sha256": _sha(tmp / f), "bytes": (tmp / f).stat().st_size, "how": "hardlink" if f in LINK else "copy"}
    (tmp / "MANIFEST.json").write_text(json.dumps(man, indent=1))
    os.rename(tmp, o)
    return p


def subset(tasks: list, p: dict) -> list:
    ids = {str(t.id) for t in tasks}
    if not set(p["todo"]) <= ids:
        raise RuntimeError(f"rerun_outage: todo ids {sorted(set(p['todo']) - ids)} not in this run's task set")
    return [t for t in tasks if str(t.id) in set(p["todo"])]


def _replace(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".rro.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)  # never writes into the archived (hard-linked, read-only) inode


def merge(run_dir: Path, p: dict, rstatus: dict, elapsed: float):
    """Merged Results (run_dir/tau2_results.json, decisions.jsonl) and the run-domain status dict to finish with."""
    from tau2.data_model.simulation import Results

    o, d = p["dir"] / "orig", p["dir"]
    orig, new = json.load(open(o / "tau2_results.json")), json.load(open(d / "tau2_results.json"))
    by_tid = {str(s["task_id"]): s for s in new["simulations"]}
    if set(by_tid) != set(p["todo"]):
        raise RuntimeError(f"rerun_outage {run_dir}: re-run returned {sorted(by_tid)} for todo {p['todo']}")
    sims = []
    for s in orig["simulations"]:
        n = by_tid.pop(str(s["task_id"]), None) if str(s["task_id"]) in set(p["outage"]) else None
        if n is not None and (n.get("seed"), n.get("trial")) != (s.get("seed"), s.get("trial")):
            raise RuntimeError(f"rerun_outage {run_dir}: task {s['task_id']} seed/trial {n.get('seed'), n.get('trial')} != {s.get('seed'), s.get('trial')}")
        sims.append(n if n is not None else s)
    for t in p["missing"]:
        n = by_tid.pop(t)
        if p["seeds"] and n.get("seed") not in p["seeds"]:
            raise RuntimeError(f"rerun_outage {run_dir}: task {t} seed {n.get('seed')} not in {p['seeds']}")
        sims.append(n)
    orig["simulations"] = sims
    redo = set(p["todo"])
    dec = [ln for ln in open(o / "decisions.jsonl") if ln.strip() and str(json.loads(ln)["task_id"]) not in redo] \
        if (o / "decisions.jsonl").exists() else []
    dec += [ln for ln in open(d / "decisions.jsonl") if ln.strip()] if (d / "decisions.jsonl").exists() else []
    _replace(run_dir / "decisions.jsonl", "".join(x if x.endswith("\n") else x + "\n" for x in dec))
    _replace(run_dir / "tau2_results.json", json.dumps(orig))
    st = json.load(open(o / "status.json")) if (o / "status.json").exists() else dict(rstatus)
    st["rerun_outage"] = {"dir": str(d.relative_to(run_dir)), "n_outage": len(p["outage"]), "n_missing": len(p["missing"]),
                          "rerun_ids": p["todo"], "rerun_elapsed_seconds": elapsed, "orig_status": st.get("status"),
                          "orig_elapsed_seconds": st.get("elapsed_seconds"), "rerun_started": rstatus.get("started")}
    return Results.load(run_dir / "tau2_results.json"), st


def done(p: dict, status: dict) -> None:
    (p["dir"] / "merged.json").write_text(json.dumps({"merged": datetime.now(timezone.utc).isoformat(), **status["rerun_outage"],
                                                       "final_status": status.get("status")}, indent=1))
