"""W100w dry check for worker.py's rerun_outage gate (no GPU: build, server, simulator and run_arm are faked).

run_eval() of the OLD (git HEAD) and NEW worker.py is driven with the same queue records; every subprocess.Popen call
(command + environment) and every quantization.json written is recorded. Checks:
  A. existing tasks (no rerun fields): identical calls and files, old vs new;
  B. a rerun_outage task: only its listed run-domains run, at most run_par at a time, each with CLOQ_RERUN_OUTAGE=1 and
     --max-concurrency; the original quantization.json is kept and a different rebuilt checkpoint is refused.
usage: python scripts/a6000/rerun_outage_drycheck_worker.py <old worker.py> <new worker.py> <scratch dir> <rro task.json>
"""
from __future__ import annotations

import argparse, importlib.util, json, shutil, sys
from pathlib import Path

ROOT, Q = Path("/data/ziyangs/cloq"), Path("/data/ziyangs/cloq_work/queue")
sys.path.insert(0, str(ROOT / "scripts/a6000"))
OLD, NEW, S, RRO = (Path(x) for x in sys.argv[1:5])
TASKS = [Q / "failed/a6k2_q14_kvq_int3.json", Q / "failed/a6k2_q32_rtn_w3.json", Q / "failed/pert_q4_gptq_w3_resid_a2_q345.json",
         Q / "done/a6k2_q4_samp_T0.5.json"]


def drive(path: Path, task: dict, root: Path, qmeta_edit=None) -> dict:
    spec = importlib.util.spec_from_file_location(f"w_{abs(hash((str(path), str(root))))}", path)
    W = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(W)
    rec = {"popen": [], "max_active": 0}
    active: list = []

    class P:
        def __init__(self, cmd, cwd=None, env=None, **kw):
            self.cmd, self.n, self.returncode = cmd, 0, 0
            keys = sorted(k for k in (env or {}) if k.startswith(("CLOQ_", "VLLM_", "CUDA")))
            rec["popen"].append({"cmd": [str(c).replace(str(root), "<root>") for c in cmd], "env": {k: env[k] for k in keys}})
            if "cloq.run_arm" in cmd:
                active.append(self)
                rec["max_active"] = max(rec["max_active"], len([p for p in active if p.n < 2]))
                rid, d = cmd[cmd.index("--run-id") + 1], cmd[cmd.index("--domain") + 1]
                (root / "runs" / rid / d).mkdir(parents=True, exist_ok=True)
                (root / "runs" / rid / d / "status.json").write_text('{"status": "completed"}')
                (root / "runs" / rid / d / "metrics.json").write_text('{"termination_reasons": {}}')

        def poll(self):
            if "cloq.run_arm" not in self.cmd:
                return None
            self.n += 1
            return 0 if self.n >= 2 else None

    def build(task, env, gpus, scratch, log):
        qp = ROOT / "runs" / task["runs"][0]["run_id"] / "quantization.json"
        if task["ckpt"]["kind"] == "bf16" or not qp.exists():
            return "/fake/ckpt", None
        q = json.load(open(qp))
        q.pop("kv_cache", None)
        return "/fake/ckpt", (qmeta_edit(q) if qmeta_edit else q)

    W.ROOT, W.WORK = root, root / "work"
    (root / "work/logs/tasks").mkdir(parents=True, exist_ok=True)
    W.subprocess.Popen, W.build_ckpt, W.healthy, W.check_canary = P, build, (lambda port: True), (lambda *a, **k: "c")
    W.user_base, W.lease, W.lease_touch, W.lease_close = (lambda: "http://u:8000/v1"), (lambda *a: None), (lambda p: None), (lambda p: None)
    W.stop_server, W.time.sleep = (lambda *a: None), (lambda s: None)
    W.urllib.request.urlopen = lambda *a, **k: None
    W.derived.canary_checks = lambda port, model, meta, cc: meta.get("canary")  # a rebuilt identical ckpt reproduces it
    args = argparse.Namespace(gpus="2,3", port=8003)
    try:
        W.run_eval(task, args, W.Status(str(root / "st"), ["2"], task))
        rec["error"] = None
    except Exception as e:  # noqa: BLE001
        rec["error"] = repr(e)[:300]
    rec["files"] = {str(p.relative_to(root)): p.read_text() for p in sorted((root / "runs").rglob("quantization*.json"))}
    return rec


def fresh(tag: str, task: dict) -> Path:
    root = S / tag
    shutil.rmtree(root, ignore_errors=True)
    for r in task["runs"]:
        (root / "runs" / r["run_id"]).mkdir(parents=True)
        q = ROOT / "runs" / r["run_id"] / "quantization.json"
        if q.exists():
            shutil.copy2(q, root / "runs" / r["run_id"] / "quantization.json")
    return root


ok = True
for tp in TASKS:
    t = json.load(open(tp))
    a, b = drive(OLD, t, fresh("W_old", t)), drive(NEW, t, fresh("W_new", t))
    same = a == b
    ok &= same and a["error"] is None
    print(f"A {t['id']}: old == new {same}; run_arm calls {sum('cloq.run_arm' in c['cmd'] for c in a['popen'])}, "
          f"max parallel {a['max_active']}, error {a['error']}")
t = json.load(open(RRO))
r = drive(NEW, t, fresh("W_rro", t))
ra = [c for c in r["popen"] if "cloq.run_arm" in c["cmd"]]
got = sorted(f"{c['cmd'][c['cmd'].index('--run-id') + 1]}/{c['cmd'][c['cmd'].index('--domain') + 1]}" for c in ra)
checks = {"only listed run-domains": got == sorted(t["rerun_outage"]), "max parallel <= run_par": r["max_active"] <= t["run_par"],
          "CLOQ_RERUN_OUTAGE=1": all(c["env"].get("CLOQ_RERUN_OUTAGE") == "1" for c in ra),
          "--max-concurrency": all(c["cmd"][c["cmd"].index("--max-concurrency") + 1] == str(t["max_concurrency"]) for c in ra),
          "original quantization kept": any("pre_rerun" in f for f in r["files"]) or t["ckpt"]["kind"] == "bf16", "no error": r["error"] is None}
bad = drive(NEW, t, fresh("W_rro_bad", t), qmeta_edit=lambda q: q | {"mean_rel_weight_err": 0.5, "content_sha256": "x"})
checks["different ckpt refused"] = t["ckpt"]["kind"] == "bf16" or "rebuilt checkpoint differs" in str(bad["error"])
ok &= all(checks.values())
print(f"B {t['id']}: {checks}; run-domains {got}; refused with: {str(bad['error'])[:160]}")
print("ALL OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
