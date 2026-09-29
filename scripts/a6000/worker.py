"""Run one queued task on the GPUs a node runner assigned to it.

eval task: build the checkpoint in node-local scratch (bf16: none; rtn/gauss: cloq.compress;
gptq/awq: cloq.quantize), serve it on this worker's port, delete the weight files once vLLM has
loaded them, run every (run, domain) of the task against the node's shared user simulator, stop the
server and verify the GPUs are released. calib task: build a calibration manifest (CPU).

usage: python scripts/a6000/worker.py <task.json> --gpus 2,3 --port 8003 --status-prefix <dir>/node003
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
WORK = Path("/data/ziyangs/cloq_work")
MODELS = json.load(open(ROOT / "scripts/a6000/models.json"))
NONCES = ["3f9a1c07", "b84e2d91", "5c0d7e3a", "e21f6b48", "9a7c4f15"]  # same as the 4080 null (scripts/null_rerolls.sh)
AGENT_MAXLEN = 33792
RUN_PAR = int(os.environ.get("CLOQ_RUN_PAR", "4"))


def snapshot(hf_id: str, rev: str) -> str:
    return str(WORK / "hf/hub" / ("models--" + hf_id.replace("/", "--")) / "snapshots" / rev)


class Status:
    def __init__(self, prefix: str, gpus: list[str], task: dict):
        self.paths = [Path(f"{prefix}-g{g}.json") for g in gpus]
        self.task = task
        self.t0 = time.time()

    def set(self, state: str, detail: str = "", progress: float | None = None):
        rec = {"state": state, "task": self.task["id"], "model": self.task.get("model"), "detail": detail,
               "progress": progress, "since": self.t0, "updated": time.time(), "host": socket.gethostname(),
               "job": os.environ.get("SLURM_JOB_ID")}
        for p in self.paths:
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(rec))
            tmp.replace(p)


def model_env(code: str, port: int) -> dict:
    m = MODELS[code]
    env = dict(os.environ)
    env.update({
        "CLOQ_MODEL_ID": m["hf_id"], "CLOQ_MODEL_REVISION": m["revision"],
        "CLOQ_CHAT_TEMPLATE_KWARGS": json.dumps(m.get("chat_template_kwargs") or {}),
        "CLOQ_TOOL_PARSER": m["parser"], "CLOQ_MAX_PROMPT_TOKENS": "32768", "CLOQ_TOP_LOGPROBS": "5",
        "CLOQ_AGENT_PORT": str(port), "CLOQ_USER_PORT": "8000",
    })
    return env


def healthy(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def gpu_pids(gpus: list[str]) -> list[int]:
    """PIDs holding memory on the given (job-local) GPU indices."""
    try:
        uu = subprocess.check_output(["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader"], text=True)
        uuids = {l.split(",")[1].strip() for l in uu.strip().splitlines() if l.split(",")[0].strip() in gpus}
        out = subprocess.check_output(["nvidia-smi", "--query-compute-apps=pid,gpu_uuid", "--format=csv,noheader"], text=True)
        return [int(l.split(",")[0]) for l in out.strip().splitlines() if l and l.split(",")[1].strip() in uuids]
    except Exception:
        return []


def stop_server(proc, gpus):
    if proc is None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    for _ in range(60):
        if proc.poll() is not None:
            break
        time.sleep(1)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    for _ in range(30):  # orphaned EngineCore processes (4080 lesson) hold the GPU after the API server exits
        pids = gpu_pids(gpus)
        if not pids:
            return
        for p in pids:
            try:
                os.kill(p, signal.SIGKILL)
            except ProcessLookupError:
                pass
        time.sleep(2)
    raise RuntimeError(f"GPUs {gpus} still busy after stopping the server: {gpu_pids(gpus)}")


def build_ckpt(task, env, gpus, scratch: Path, log) -> tuple[str, dict | None]:
    m = MODELS[task["model"]]
    src = snapshot(m["hf_id"], m["revision"])
    ck = task["ckpt"]
    if ck["kind"] == "bf16":
        return src, None
    out = scratch / f"ckpt_{task['id']}"
    if out.exists():
        shutil.rmtree(out)
    e = dict(env, CUDA_VISIBLE_DEVICES=gpus[0])
    if ck["kind"] in ("rtn", "gauss"):
        cmd = [sys.executable, "-m", "cloq.compress", ck["kind"], "--src", src, "--out", str(out), "--no-sha",
               "--source-model", m["hf_id"], "--source-revision", m["revision"]]
        cmd += ["--wbits", str(ck["wbits"])] if ck["kind"] == "rtn" else ["--k", str(ck["k"]), "--seed", str(ck["seed"])]
    else:
        cmd = [sys.executable, "-m", "cloq.quantize", "--method", ck["kind"], "--wbits", str(ck["wbits"]),
               "--calib", str(ROOT / ck["calib"]), "--out", str(out), "--no-sha"]
    r = subprocess.run(cmd, cwd=ROOT, env=e, stdout=log, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        raise RuntimeError(f"checkpoint build failed ({ck}) rc={r.returncode}")
    return str(out), json.load(open(out / "quantization.json"))


def run_eval(task, args, st: Status):
    gpus = args.gpus.split(",")
    env = model_env(task["model"], args.port)
    scratch = Path(os.environ.get("TMPDIR", "/tmp"))
    logdir = WORK / "logs/tasks"
    logdir.mkdir(parents=True, exist_ok=True)
    log = open(logdir / f"{task['id']}.log", "a")
    log.write(f"\n=== {time.ctime()} {socket.gethostname()} gpus={args.gpus} port={args.port}\n")
    log.flush()
    st.set("quantize" if task["ckpt"]["kind"] in ("gptq", "awq") else "compress" if task["ckpt"]["kind"] != "bf16" else "setup",
           f"build {task['ckpt']['kind']}")
    path, qmeta = build_ckpt(task, env, gpus, scratch, log)
    st.set("setup", "starting vLLM")
    slog = open(logdir / f"{task['id']}.vllm.log", "a")
    server = subprocess.Popen([str(ROOT / "scripts/a6000/serve.sh"), args.gpus, str(args.port), path, "agent", str(AGENT_MAXLEN)],
                              env=env, stdout=slog, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        t0 = time.time()
        while not healthy(args.port):
            if server.poll() is not None:
                raise RuntimeError("vLLM agent server exited during startup")
            if time.time() - t0 > 1800:
                raise RuntimeError("vLLM agent server did not come up in 30 min")
            time.sleep(5)
        if path.startswith(str(scratch)):  # weights are on the GPU now; free the RAM disk
            for f in Path(path).glob("*.safetensors"):
                f.unlink()
        ubase = os.environ.get("CLOQ_USER_BASE", "http://127.0.0.1:8000/v1")
        t1 = time.time()
        while True:  # the simulator may live on another node and still be starting
            try:
                urllib.request.urlopen(ubase + "/models", timeout=5)
                break
            except Exception:
                if time.time() - t1 > 2400:
                    raise RuntimeError(f"user simulator {ubase} unreachable")
                st.set("setup", "waiting for user simulator")
                time.sleep(15)
        jobs = [(r, d) for r in task["runs"] for d in ("retail", "airline")]
        done, running = 0, []
        st.set("eval", f"{len(jobs)} run-domains", 0.0)
        pending = list(jobs)
        while pending or running:
            while pending and len(running) < RUN_PAR:
                r, d = pending.pop(0)
                if qmeta is not None:
                    qdir = ROOT / "runs" / r["run_id"]
                    qdir.mkdir(parents=True, exist_ok=True)
                    q = {k: v for k, v in qmeta.items() if k not in ("per_tensor", "stats")}
                    (qdir / "quantization.json").write_text(json.dumps(q, indent=1))
                e = dict(env)
                if r.get("nonce"):
                    e["CLOQ_PROMPT_NONCE"] = r["nonce"]
                else:
                    e.pop("CLOQ_PROMPT_NONCE", None)
                cmd = [sys.executable, "-m", "cloq.run_arm", "--run-id", r["run_id"], "--arm", task["arm"], "--domain", d,
                       "--task-file", str(ROOT / r["task_file"]), "--agent-base", f"http://127.0.0.1:{args.port}/v1",
                       "--user-base", os.environ.get("CLOQ_USER_BASE", "http://127.0.0.1:8000/v1"), "--checkpoint", json.dumps(task["ckpt"])]
                running.append(((r["run_id"], d), subprocess.Popen(cmd, cwd=ROOT, env=e, stdout=log, stderr=subprocess.STDOUT)))
            time.sleep(10)
            for item in list(running):
                (rid, d), p = item
                if p.poll() is not None:
                    running.remove(item)
                    ok = (ROOT / "runs" / rid / d / "status.json").exists() and \
                        json.load(open(ROOT / "runs" / rid / d / "status.json")).get("status") == "completed"
                    if p.returncode != 0 or not ok:
                        raise RuntimeError(f"run {rid}/{d} failed rc={p.returncode}")
                    done += 1
                    # storage: tau2_results.json (~4 MB/task) duplicates trajectory.jsonl once the run is complete
                    tr = ROOT / "runs" / rid / d / "tau2_results.json"
                    if tr.exists() and (ROOT / "runs" / rid / d / "trajectory.jsonl").stat().st_size > 0:
                        tr.unlink()
                    st.set("eval", f"{done}/{len(jobs)} run-domains", done / len(jobs))
            if server.poll() is not None:
                raise RuntimeError("vLLM agent server died during evaluation")
    finally:
        for _, p in locals().get("running", []):
            p.kill()
        stop_server(server, gpus)
    summ = {}
    for r in task["runs"]:
        for d in ("retail", "airline"):
            mp = ROOT / "runs" / r["run_id"] / d / "metrics.json"
            if mp.exists():
                m = json.load(open(mp))
                summ[f"{r['run_id']}/{d}"] = {k: m.get(k) for k in ("db_match_rate", "reward_mean", "n_tasks", "mean_decisions", "premature_rate", "termination_reasons")
                                              if k in m}
    return summ


def run_calib(task, args, st: Status):
    st.set("setup", "build calibration manifest")
    env = model_env(task["model"], args.port)
    out = ROOT / task["out"]
    if out.exists():
        return {"exists": str(out)}
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, "-m", "cloq.calib_v1", "--arm", task["arm"], "--draw", task["draw"],
                        "--fp-run", task["fp_run"], "--out", str(out)], cwd=ROOT, env=env, capture_output=True, text=True)
    (WORK / "logs/tasks" / f"{task['id']}.log").write_text(r.stdout[-20000:] + r.stderr[-20000:])
    if r.returncode != 0:
        raise RuntimeError("calib_v1 failed: " + r.stderr[-2000:])
    return {"manifest": str(out)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task")
    ap.add_argument("--gpus", default="")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--status-prefix", required=True)
    args = ap.parse_args()
    task = json.load(open(args.task))
    st = Status(args.status_prefix, args.gpus.split(",") if args.gpus else [], task)
    t0 = time.time()
    try:
        if task["kind"] == "cmd":  # ad-hoc GPU experiment on this worker's cards
            st.set("check", task.get("title", "experiment"))
            e = dict(os.environ, CUDA_VISIBLE_DEVICES=args.gpus, CLOQ_TASK_PORT=str(args.port))
            logf = open(WORK / "logs/tasks" / f"{task['id']}.log", "a")
            r = subprocess.run(["bash", "-c", task["cmd"]], cwd=ROOT, env=e, stdout=logf, stderr=subprocess.STDOUT)
            if r.returncode != 0:
                raise RuntimeError(f"cmd failed rc={r.returncode}")
            res = {"cmd": "ok"}
        else:
            res = run_eval(task, args, st) if task["kind"] == "eval" else run_calib(task, args, st)
        task.update({"result": res, "finished": time.time(), "seconds": time.time() - t0, "host": socket.gethostname()})
        Path(args.task).write_text(json.dumps(task, indent=1))
        Path(args.task).replace(WORK / "queue/done" / Path(args.task).name)
        st.set("idle", f"finished {task['id']}")
    except Exception as e:
        task.update({"error": repr(e), "trace": traceback.format_exc()[-4000:], "failed_at": time.time(), "host": socket.gethostname()})
        Path(args.task).write_text(json.dumps(task, indent=1))
        Path(args.task).replace(WORK / "queue/failed" / Path(args.task).name)
        st.set("failed", repr(e)[:200])
        sys.exit(1)


if __name__ == "__main__":
    main()
