"""W100w dry check for the outage re-run path (no GPU, no server; scratch copies of real run-domains).

run_arm.main() of the OLD (git HEAD) and NEW file is run against copies of real run-domains with tau2's run_tasks replaced
by a fake that behaves like tau2 (resume from save_path, infra errors dropped, missing tasks 'run' by cloning a finished
episode, decisions written through cloq.agent's writer). Checks:
  A. no flag: every case gives identical run_tasks calls and identical files (old vs new);
  B. flag on a completed run-domain without outages: skipped, files unchanged;
  C. flag on an outage run-domain: only the outage (+ never-run) ids are run, in rerun_outage/<tag>/, originals archived
     (sha256 equal, read-only), kept episodes byte-identical, merged run-domain complete; interrupted re-run resumes.
usage: <cloq env python> scripts/a6000/rerun_outage_drycheck.py <old run_arm.py> <new run_arm.py> <scratch dir> > drycheck.txt
"""
from __future__ import annotations

import copy, hashlib, importlib.util, json, os, shutil, sys
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
sys.path.insert(0, str(ROOT))
from cloq import agent as AG, config as C  # noqa: E402
import tau2.runner.batch as B  # noqa: E402
from tau2.data_model.simulation import Results  # noqa: E402
from cloq.rerun_outage import is_outage  # noqa: E402

OLD, NEW, S = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
CASES = {"completed_clean": "a6k2_q32_gauss3_s2/airline", "completed_outage": "a6k2_q14_gauss3_s2/airline",
         "completed_outage_ctx_overflow": "a6k2_q14_gauss3_s1/airline",
         "running_outage_missing": "a6k2_pert_q4_rtn_w3_restore_rand_mlp_s3_q4/retail"}
CALLS: list = []
CRASH = {"after": None}


def fake_run_tasks(cfg, tasks, save_path=None, save_dir=None, **kw):
    prev = json.load(open(save_path)) if save_path.exists() else None
    kept = [s for s in (prev or {}).get("simulations", []) if s["termination_reason"] != "infrastructure_error"]
    tmpl = next(s for s in json.load(open(TEMPLATE))["simulations"] if s["termination_reason"] != "infrastructure_error")
    tdecs = [json.loads(x) for x in open(TEMPLATE.parent / "decisions.jsonl") if f'"task_id": "{tmpl["task_id"]}"' in x][:3]
    CALLS.append({"ids": [t.id for t in tasks], "save_path": str(save_path), "save_dir": str(save_dir),
                  "cfg": json.loads(cfg.model_dump_json())})
    sims = list(kept)
    for i, t in enumerate(x for x in tasks if x.id not in {s["task_id"] for s in kept}):
        if CRASH["after"] is not None and i >= CRASH["after"]:
            raise KeyboardInterrupt("simulated kill")
        s = copy.deepcopy(tmpl) | {"id": f"fake-{t.id}", "task_id": t.id}
        for d in tdecs:
            AG._WRITER.write(d | {"task_id": t.id, "trajectory_id": f"fake-traj-{t.id}", "run_id": d["run_id"]})
        sims.append(s)
        info = (prev or json.load(open(TEMPLATE)))["info"]
        save_path.write_text(json.dumps({"info": info, "tasks": [json.loads(x.model_dump_json()) for x in tasks], "simulations": sims}))
    if not save_path.exists():
        save_path.write_text(json.dumps({"info": (prev or json.load(open(TEMPLATE)))["info"],
                                         "tasks": [json.loads(x.model_dump_json()) for x in tasks], "simulations": sims}))
    return Results.load(save_path)


def load_main(path: Path):
    spec = importlib.util.spec_from_file_location(f"ra_{abs(hash(str(path)))}", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.main


def files(d: Path) -> dict:
    out = {}
    for p in sorted(d.rglob("*")):
        if p.is_file():
            txt = p.read_bytes()
            if p.name in ("status.json", "environment.json", "MANIFEST.json", "merged.json"):
                j = json.loads(txt)  # wall-clock fields differ between runs by construction
                for k in ("started", "finished", "timestamp", "elapsed_seconds", "archived", "merged", "rerun_elapsed_seconds"):
                    j.pop(k, None)
                txt = json.dumps(j, sort_keys=True).encode()
            out[str(p.relative_to(d))] = hashlib.sha256(txt).hexdigest()
    return out


def run(main, root: Path, rd: str, flag: bool) -> list:
    C.RUNS_DIR, CALLS[:] = root, []
    rid, dom = rd.split("/")
    os.environ.pop("CLOQ_RERUN_OUTAGE", None)
    if flag:
        os.environ["CLOQ_RERUN_OUTAGE"] = "1"
    tf = ROOT / "manifests/eval_tasks_v0.json"
    sys.argv = ["run_arm", "--run-id", rid, "--arm", "x", "--domain", dom, "--task-file", str(tf), "--max-concurrency", "4",
                "--agent-base", "http://127.0.0.1:9/v1", "--user-base", "http://127.0.0.1:9/v1"]
    main()
    return json.loads(json.dumps(CALLS).replace(str(root), "<root>"))  # scratch roots differ between old and new


def fresh(tag: str, rd: str) -> Path:
    root = S / tag
    shutil.rmtree(root, ignore_errors=True)
    (root / rd).parent.mkdir(parents=True)
    shutil.copytree(ROOT / "runs" / rd, root / rd, ignore=shutil.ignore_patterns("rerun_outage"))
    return root


B.run_tasks = fake_run_tasks
old, new = load_main(OLD), load_main(NEW)
ok = True
for name, rd in CASES.items():  # A: no flag, old vs new
    TEMPLATE = ROOT / "runs" / rd / "tau2_results.json"
    if not TEMPLATE.exists():
        TEMPLATE = ROOT / "runs/a6k2_q14_gauss3_s2/airline/tau2_results.json"
    ra, rb = fresh("A_old", rd), fresh("A_new", rd)
    ca, cb = run(old, ra, rd, False), run(new, rb, rd, False)
    same = ca == cb and files(ra / rd) == files(rb / rd)
    ok &= same
    print(f"A {name}: no flag, old == new: {same}; run_tasks calls {len(ca)} ids {[len(c['ids']) for c in ca]}")
TEMPLATE = ROOT / "runs/a6k2_q14_gauss3_s2/airline/tau2_results.json"
r = fresh("B", CASES["completed_clean"])
before = files(r / CASES["completed_clean"])
c = run(new, r, CASES["completed_clean"], True)
res = c == [] and files(r / CASES["completed_clean"]) == before
ok &= res
print(f"B completed_clean: flag, skipped and unchanged: {res}")
for name in ("completed_outage", "completed_outage_ctx_overflow", "running_outage_missing"):  # C: flag on outage run-domains (incl. an interrupted re-run)
    rd = CASES[name]
    TEMPLATE = ROOT / "runs" / rd / "tau2_results.json"
    r = fresh("C_" + name, rd)
    d = r / rd
    orig = json.load(open(d / "tau2_results.json"))
    sha0 = {f: hashlib.sha256((d / f).read_bytes()).hexdigest() for f in ("tau2_results.json", "decisions.jsonl")}
    CRASH["after"] = 1
    try:
        run(new, r, rd, True)
    except KeyboardInterrupt:
        pass
    CRASH["after"] = None
    untouched = {f: hashlib.sha256((d / f).read_bytes()).hexdigest() for f in sha0} == sha0
    c = run(new, r, rd, True)
    tag = next((d / "rerun_outage").iterdir())
    man = json.load(open(tag / "orig/MANIFEST.json"))
    merged = json.load(open(d / "tau2_results.json"))
    redo = set(man["plan"]["todo"])
    kept_same = all(m == o for m, o in zip(merged["simulations"], orig["simulations"]) if o["task_id"] not in redo)
    slots = [s["task_id"] for s in merged["simulations"]][:len(orig["simulations"])] == [s["task_id"] for s in orig["simulations"]]
    st = json.load(open(d / "status.json"))
    n_traj = sum(1 for _ in open(d / "trajectory.jsonl"))
    checks = {"run_dir untouched by the interrupted re-run": untouched,
              "re-run ids == outage + missing": sorted(c[0]["ids"]) == sorted(redo) and tag.name in c[0]["save_path"],
              "max_concurrency recorded": c[0]["cfg"]["max_concurrency"] == 4,
              "archive sha == original": all(man["files"][f]["sha256"] == sha0[f] for f in sha0),
              "archive read-only": all(not os.access(tag / "orig" / f, os.W_OK) for f in sha0),
              "kept episodes byte-identical, same slots": kept_same and slots,
              "merged complete": st["status"] == "completed" and n_traj == st["n_tasks"] == len(merged["simulations"]),
              "merged.json written": (tag / "merged.json").exists(),
              "non-outage infra episodes kept": not redo & {s["task_id"] for s in orig["simulations"]
                                                            if s["termination_reason"] == "infrastructure_error" and not is_outage(s)},
              "rerun decisions replace originals": all(json.loads(x)["trajectory_id"].startswith("fake-traj-")
                                                       for x in open(d / "decisions.jsonl") if json.loads(x)["task_id"] in redo)}
    ok &= all(checks.values())
    print(f"C {name}: outage {len(man['plan']['outage'])} missing {len(man['plan']['missing'])} -> {checks}")
    print(f"  status.rerun_outage = {st.get('rerun_outage')}")
print("ALL OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
