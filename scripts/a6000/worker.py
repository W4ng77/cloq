"""Run one queued task on the GPUs a node runner assigned to it.

eval task: build the checkpoint in node-local scratch (bf16: none; rtn/gauss/gshape/rtnsign/nf4/mxfp4/rtnsr:
cloq.compress; gptq/awq: cloq.quantize; rot_bf16/rot_rtn: cloq.rotate; rot_gptq: cloq.rotate then cloq.quantize --src;
restore/resid: cloq.perturb from a cached Q, scripts/a6000/derived.py), serve it on this worker's port, delete the weight files once vLLM has
loaded them, run every (run, domain) of the task against the node's shared user simulator, stop the
server and verify the GPUs are released. calib task: build a calibration manifest (CPU).
sim task: one extra user-simulator replica on an NVLink pair, registered in the instance registry (run_sim, simreg.py).

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derived  # noqa: E402  restore / resid checkpoint kinds (P2 line 3)

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


CANARY_TEXT = ("You are a careful assistant for an airline. Policy: verify identity before any change, never refund "
               "without a reservation id, and summarise the customer's request before acting. ") * 40


def canary(port: int, model: str, name: str = "agent") -> str:
    """Hash of a fixed greedy completion *including exact logprobs*: any change in numerics flavour changes it."""
    import hashlib
    m = MODELS[model]
    body = {"model": name, "temperature": 0.0, "max_tokens": 48, "seed": 0, "logprobs": True, "top_logprobs": 5,
            "messages": [{"role": "system", "content": CANARY_TEXT},
                         {"role": "user", "content": "My reservation is ABC123; I want to change my flight to Friday."}],
            "return_token_ids": True}
    if m.get("chat_template_kwargs"):
        body["chat_template_kwargs"] = m["chat_template_kwargs"]
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        c = json.load(r)["choices"][0]
    lp = [(t["token"], t["logprob"], [(a["token"], a["logprob"]) for a in t["top_logprobs"]]) for t in c["logprobs"]["content"]]
    return hashlib.sha256(json.dumps([c.get("token_ids"), lp]).encode()).hexdigest()[:16]


def check_canary(port: int, model: str, role: str, name: str = "agent") -> str:
    """First server of (role, model) writes the reference; every later one must reproduce it exactly."""
    h = canary(port, model, name)
    ref = ROOT / "analysis/determinism" / f"canary_{role}_{model}.json"
    ref.parent.mkdir(parents=True, exist_ok=True)
    rec = {"hash": h, "host": socket.gethostname(), "job": os.environ.get("SLURM_JOB_ID"), "time": time.time()}
    if not ref.exists():
        ref.write_text(json.dumps(rec, indent=1))
        return h
    want = json.load(open(ref))["hash"]
    with open(WORK / "logs/canary.log", "a") as f:
        f.write(json.dumps({**rec, "role": role, "model": model, "ok": h == want}) + "\n")
    if h != want:
        raise RuntimeError(f"numerics canary mismatch for {role} {model} on {socket.gethostname()}: {h} != {want}")
    return h



def user_base():
    """Simulator URL: queue/USER_BASE.<node> (read at every run start; moves a node's new runs to another simulator
    replica without restarting its runner), else $CLOQ_USER_BASE, else the node's own simulator. A route to a replica
    that the instance registry (scripts/a6000/simreg.py) lists as not live (draining/stopped/dead/stale) is ignored."""
    f = WORK / "queue" / f"USER_BASE.{socket.gethostname().split('.')[0]}"
    try:
        url = f.read_text().strip() if f.exists() else ""
    except OSError:
        url = ""
    if url:
        try:
            import simreg
            r = simreg.by_url(url)
            if r is None or simreg.is_live(r):
                return url
        except Exception:
            return url
    return os.environ.get("CLOQ_USER_BASE", "http://127.0.0.1:8000/v1")


def lease(url: str, run: str):
    """Mark `url` as in use by a long-lived simulator client (run_arm / fork_driver) of this worker (simreg.py leases):
    a draining replica stops only after every lease on it is gone, so running episodes keep their endpoint."""
    try:
        import simreg
        node = socket.gethostname().split('.')[0]
        url = url.replace("://127.0.0.1:", f"://{node}:").replace("://localhost:", f"://{node}:")  # registry URLs use the host name
        return simreg.lease_open(f"{node}_{os.getpid()}_{run.replace('/', '_')}", url, run)
    except Exception:
        return None


def lease_touch(p):
    if p is not None:
        try:
            os.utime(p)
        except OSError:
            pass


def lease_close(p):
    if p is not None:
        try:
            p.unlink()
        except OSError:
            pass

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
    if ck["kind"] == "hf":  # X1: serve an official pre-quantized repo (pinned revision) instead of building one
        path = snapshot(ck["hf_id"], ck["revision"])
        if not Path(path, "config.json").exists():
            raise RuntimeError(f"hf checkpoint {ck['hf_id']}@{ck['revision']} not in the HF cache")
        qc = json.load(open(Path(path, "config.json"))).get("quantization_config") or {}
        return path, {"method": "hf", "format": ck.get("format"), "hf_id": ck["hf_id"], "revision": ck["revision"],
                      "source_model": m["hf_id"], "source_revision": m["revision"], "quantization_config": qc,
                      "serve_extra": task.get("serve_extra", [])}
    if ck["kind"] in derived.KINDS:  # P2 line 3: restoration / residual dose from a cached Q (scripts/a6000/derived.py)
        return derived.build(task, src, m["revision"], env, gpus, scratch, log, build_ckpt, ckpt_sha)
    out = scratch / f"ckpt_{task['id']}"
    if out.exists():
        shutil.rmtree(out)
    e = dict(env, CUDA_VISIBLE_DEVICES=gpus[0])
    prov = ["--source-model", m["hf_id"], "--source-revision", m["revision"]]
    rot = None
    if ck["kind"] in ("rtn", "gauss", "gshape", "rtnsign", "nf4", "mxfp4", "rtnsr"):
        cmd = [sys.executable, "-m", "cloq.compress", ck["kind"], "--src", src, "--out", str(out), "--no-sha"] + prov
        if ck["kind"] == "rtn":
            cmd += ["--wbits", str(ck["wbits"])]
        elif ck["kind"] == "rtnsr":  # stochastic rounding on the RTN grid (k ignored)
            cmd += ["--wbits", str(ck["wbits"]), "--seed", str(ck["seed"])]
        elif ck["kind"] not in ("nf4", "mxfp4"):
            cmd += ["--k", str(ck["k"]), "--seed", str(ck["seed"])] + (["--wbits", str(ck["wbits"])] if "wbits" in ck else [])
    elif ck["kind"] in ("rot_bf16", "rot_rtn"):  # QuaRot-style rotation (cloq.rotate), optionally + RTN g128
        cmd = [sys.executable, "-m", "cloq.rotate", "--src", src, "--out", str(out), "--no-sha",
               "--seed", str(ck.get("seed", 0))] + prov + (["--wbits", str(ck["wbits"])] if ck["kind"] == "rot_rtn" else [])
    elif ck["kind"] == "smoothquant":  # SmoothQuant W8 + smoothing (cloq.smoothquant); A8 via serve_env (pyhooks/cloq_aq.py)
        cmd = [sys.executable, "-m", "cloq.smoothquant", "--src", src, "--out", str(out), "--no-sha",
               "--alpha", str(ck.get("alpha", "auto"))] + prov
    elif ck["kind"] == "quarot":  # QuaRot offline transforms (+ W4 RTN/GPTQ) (cloq.quarot); online half via serve_env
        cmd = [sys.executable, "-m", "cloq.quarot", "--src", src, "--out", str(out), "--no-sha", "--seed", str(ck.get("seed", 0)),
               "--wbits", str(ck.get("wbits", 16)), "--wmethod", ck.get("wmethod", "gptq")] + prov + (["--check"] if ck.get("check") else [])
    elif ck["kind"] == "rot_gptq":  # rotate to scratch, then GPTQ on the rotated BF16 model
        rot = scratch / f"ckpt_{task['id']}_rot"
        if rot.exists():
            shutil.rmtree(rot)
        r = subprocess.run([sys.executable, "-m", "cloq.rotate", "--src", src, "--out", str(rot), "--no-sha",
                            "--seed", str(ck.get("seed", 0))] + prov, cwd=ROOT, env=e, stdout=log, stderr=subprocess.STDOUT)
        if r.returncode != 0:
            raise RuntimeError(f"rotation failed ({ck}) rc={r.returncode}")
        cmd = [sys.executable, "-m", "cloq.quantize", "--method", "gptq", "--wbits", str(ck["wbits"]), "--src", str(rot),
               "--calib", str(ROOT / ck["calib"]), "--out", str(out), "--no-sha"]
    else:
        cmd = [sys.executable, "-m", "cloq.quantize", "--method", ck["kind"], "--wbits", str(ck["wbits"]),
               "--calib", str(ROOT / ck["calib"]), "--out", str(out), "--no-sha"]
    r = subprocess.run(cmd, cwd=ROOT, env=e, stdout=log, stderr=subprocess.STDOUT)
    if rot is not None:
        shutil.rmtree(rot, ignore_errors=True)
    if r.returncode != 0:
        raise RuntimeError(f"checkpoint build failed ({ck}) rc={r.returncode}")
    return str(out), json.load(open(out / "quantization.json"))


def toolcall_side(rid: str, dom: str, task_id: str) -> str:
    """W41: a tau2 pydantic 'validation error for ToolCall' (e.g. arguments=[] instead of {}) is not an outage. If the
    agent's last recorded decision for the task parsed cleanly, the malformed call came from the user simulator (telecom
    users have tools): 'user_sim_error', which stays missing, symmetric in every arm. Otherwise it is the agent's own
    output: 'agent_parse_error', which counts as a failure (W27)."""
    last = None
    try:
        with open(ROOT / "runs" / rid / dom / "decisions.jsonl") as fh:
            for ln in fh:
                if task_id in ln:
                    r = json.loads(ln)
                    if str(r.get("task_id")) == task_id:
                        last = r
    except OSError:
        pass
    return "user_sim_error" if last is not None and str(last.get("parser_error")) == "False" else "agent_parse_error"


def run_eval(task, args, st: Status):
    gpus = args.gpus.split(",")
    env = model_env(task["model"], args.port)
    scratch = Path(os.environ.get("TMPDIR", "/tmp"))
    logdir = WORK / "logs/tasks"
    logdir.mkdir(parents=True, exist_ok=True)
    log = open(logdir / f"{task['id']}.log", "a")
    log.write(f"\n=== {time.ctime()} {socket.gethostname()} gpus={args.gpus} port={args.port}\n")
    log.flush()
    st.set("quantize" if task["ckpt"]["kind"] in ("gptq", "awq", "rot_gptq") else "compress" if task["ckpt"]["kind"] not in ("bf16", "hf") else "setup",
           f"build {task['ckpt']['kind']}")
    path, qmeta = build_ckpt(task, env, gpus, scratch, log)
    senv = task.get("serve_env", {})
    kvq = bool(senv.get("CLOQ_KVQ_BITS")) and senv.get("CLOQ_PYHOOKS") == "1"
    if kvq:  # W13: fake KV-cache quantization hook (scripts/a6000/pyhooks/cloq_kvq.py) on top of the task's weights
        m = MODELS[task["model"]]
        qmeta = dict(qmeta or {"method": "bf16", "source_model": m["hf_id"], "source_revision": m["revision"]},
                     kv_cache={"method": "kvq_fake", "bits": int(senv["CLOQ_KVQ_BITS"]), "rot": senv.get("CLOQ_KVQ_ROT", "0") == "1",
                               "rot_mode": senv.get("CLOQ_KVQ_ROT", "0"), "fmt": senv.get("CLOQ_KVQ_FMT", "minmax"),
                               "kclip": float(senv.get("CLOQ_KVQ_KCLIP", 1.0)), "vclip": float(senv.get("CLOQ_KVQ_VCLIP", 1.0)),
                               "which": senv.get("CLOQ_KVQ_WHICH", "kv"), "granularity": "per-token per-head, group=head_dim, asymmetric",
                               "hook": "pyhooks/cloq_kvq.py"})
    aq = senv.get("CLOQ_PYHOOKS") == "1" and bool(senv.get("CLOQ_AQ_BITS") or senv.get("CLOQ_AQ_HAD", "0") != "0")
    for k, v in ((qmeta or {}).get("requires_serve_env") or {}).items():  # SmoothQuant / QuaRot ckpts need their online half
        if str(senv.get(k)) != str(v):
            raise RuntimeError(f"checkpoint {task['ckpt']['kind']} requires serve_env {k}={v}, task has {senv.get(k)}")
    for k, v in ((qmeta or {}).get("forbids_serve_env") or {}).items():
        if str(senv.get(k)) == str(v):
            raise RuntimeError(f"checkpoint {task['ckpt']['kind']} forbids serve_env {k}={v}")
    if aq:  # fake activation quantization / QuaRot online Hadamards (scripts/a6000/pyhooks/cloq_aq.py, METHOD_FIDELITY.md)
        m = MODELS[task["model"]]
        qmeta = dict(qmeta or {"method": "bf16", "source_model": m["hf_id"], "source_revision": m["revision"]},
                     activations={"method": "aq_fake", "bits": int(senv.get("CLOQ_AQ_BITS", 16)), "fmt": senv.get("CLOQ_AQ_FMT", "sym_quarot"),
                                  "clip": float(senv.get("CLOQ_AQ_CLIP", 1.0)), "group": int(senv.get("CLOQ_AQ_GROUP", -1)),
                                  "only": senv.get("CLOQ_AQ_ONLY", "qkv,o,gate_up,down"), "had": senv.get("CLOQ_AQ_HAD", "0"),
                                  "granularity": "per token, dynamic", "scale_dtype": "fp32", "hook": "pyhooks/cloq_aq.py"})
    st.set("setup", "starting vLLM")
    slog = open(logdir / f"{task['id']}.vllm.log", "a")
    server = subprocess.Popen([str(ROOT / "scripts/a6000/serve.sh"), args.gpus, str(args.port), path, "agent", str(AGENT_MAXLEN),
                               *task.get("serve_extra", [])], env=dict(env, **task.get("serve_env", {})), stdout=slog, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        t0 = time.time()
        while not healthy(args.port):
            if server.poll() is not None:
                raise RuntimeError("vLLM agent server exited during startup")
            if time.time() - t0 > 1800:
                raise RuntimeError("vLLM agent server did not come up in 30 min")
            time.sleep(5)
        # BF16 servers of a model must be bit-identical on every node (quantized ckpts differ by design)
        if task["ckpt"]["kind"] == "bf16" and not task.get("serve_extra") and not kvq and not aq:  # eager/KVQ/AQ = different flavour by design
            st.set("check", "numerics canary")
            check_canary(args.port, task["model"], "agent")
        if (qmeta or {}).get("protocol") == derived.PROTOCOL and not task.get("serve_extra") and not kvq and not aq:
            st.set("check", "numerics canary (derived ckpt)")
            qmeta["canary"] = derived.canary_checks(args.port, task["model"], qmeta, check_canary)
        if path.startswith(str(scratch)):  # weights are on the GPU now; free the RAM disk
            for f in Path(path).glob("*.safetensors"):
                f.unlink()
        ext = task.get("env")  # simulator-free external environment (scripts/ext/: "bfcl" | "alfworld"); no user simulator
        ubase = None if ext else user_base()
        t1 = time.time()
        while ubase:  # the simulator may live on another node and still be starting
            try:
                urllib.request.urlopen(ubase + "/models", timeout=5)
                break
            except Exception:
                if time.time() - t1 > 2400:
                    raise RuntimeError(f"user simulator {ubase} unreachable")
                st.set("setup", "waiting for user simulator")
                time.sleep(15)
        ol = task.get("openloop")
        if ol:  # E3: open-loop logit shift on the BF16 reference contexts (scripts/a6000/openloop_d.py)
            st.set("eval", "open-loop D")
            cmd = [sys.executable, str(ROOT / "scripts/a6000/openloop_d.py"), "--port", str(args.port), "--n", str(ol.get("n", 400)),
                   "--out", ol["out"]] + [x for r in ol["ref_runs"] for x in ("--ref-run", r)]
            if ol.get("topk"):  # E4-2: top-k alternatives at decision starts / tool names (scripts/a6000/openloop_topk.py)
                cmd[1] = str(ROOT / "scripts/a6000/openloop_topk.py")
                cmd += ["--topk", str(ol["topk"]), "--positions", ol.get("positions", "first,tool")]
                cmd += ["--first-all"] if ol.get("first_all", True) else []
                cmd += ["--ref", ol["ref"]] if ol.get("ref") else []
            if subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT).returncode != 0:
                raise RuntimeError("openloop_d failed")
        jobs = [(r, d) for r in task["runs"] for d in task.get("domains", ("retail", "airline"))]
        done, running = 0, []
        st.set("eval", f"{len(jobs)} run-domains", 0.0)
        leases: dict = {}
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
                e.update({k: str(v) for k, v in r.get("env", {}).items()})  # per-run overrides, e.g. agent sampling
                if r.get("nonce"):
                    e["CLOQ_PROMPT_NONCE"] = r["nonce"]
                else:
                    e.pop("CLOQ_PROMPT_NONCE", None)
                if ext:  # isolated venv per benchmark (cloq_work/envs/<env>); a manifest subset instead of a tau2 task file
                    cmd = [str(WORK / "envs" / ext / "bin/python"), str(ROOT / "scripts/ext" / f"{ext}_run.py"), "--run-id", r["run_id"],
                           "--arm", task["arm"], "--domain", d, "--manifest", r["task_file"], "--subset", r.get("subset", "smoke"),
                           "--agent-base", f"http://127.0.0.1:{args.port}/v1", "--checkpoint", json.dumps(task["ckpt"])]
                    cmd += ["--limit", str(r["limit"])] if r.get("limit") else []
                else:
                    ub = user_base()
                    cmd = [sys.executable, "-m", "cloq.run_arm", "--run-id", r["run_id"], "--arm", task["arm"], "--domain", d,
                           "--task-file", str(ROOT / r["task_file"]), "--agent-base", f"http://127.0.0.1:{args.port}/v1",
                           "--user-base", ub, "--checkpoint", json.dumps(task["ckpt"])]
                    leases[(r["run_id"], d)] = lease(ub, f"{r['run_id']}/{d}")
                running.append(((r["run_id"], d), subprocess.Popen(cmd, cwd=ROOT, env=e, stdout=log, stderr=subprocess.STDOUT)))
            time.sleep(10)
            for lp in leases.values():
                lease_touch(lp)
            for item in list(running):
                (rid, d), p = item
                if p.poll() is not None:
                    running.remove(item)
                    lease_close(leases.pop((rid, d), None))
                    ok = (ROOT / "runs" / rid / d / "status.json").exists() and \
                        json.load(open(ROOT / "runs" / rid / d / "status.json")).get("status") == "completed"
                    if p.returncode != 0 or not ok:
                        raise RuntimeError(f"run {rid}/{d} failed rc={p.returncode}")
                    # episodes cut by a dead simulator/server are not agent failures (W6): never accept them as data
                    tr = json.load(open(ROOT / "runs" / rid / d / "metrics.json")).get("termination_reasons") or {}
                    if isinstance(tr, dict) and tr.get("infrastructure_error", 0):
                        # W10: a conversation that outgrows the simulator/agent context window is the agent's doing
                        # (it loops or rambles), i.e. a task failure, not an outage. Record causes; fail only on real outages.
                        causes = {}
                        res = ROOT / "runs" / rid / d / "tau2_results.json"
                        if res.exists():
                            for sim in json.load(open(res)).get("simulations", []):
                                if str(sim.get("termination_reason")) == "infrastructure_error":
                                    err = str((sim.get("info") or {}).get("error", ""))
                                    causes[str(sim["task_id"])] = ("context_overflow" if "ContextWindowExceeded" in err else
                                                                   "agent_parse_error" if "only supports single tool-calls" in err else
                                                                   toolcall_side(rid, d, str(sim["task_id"])) if "validation error for ToolCall" in err else
                                                                   "outage")
                        (ROOT / "runs" / rid / d / "infra_causes.json").write_text(json.dumps(causes, indent=1))
                        n_out = sum(v == "outage" for v in causes.values()) if causes else tr["infrastructure_error"]
                        if n_out:
                            raise RuntimeError(f"run {rid}/{d}: {n_out} infrastructure_error episodes (outage)")
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
        for lp in locals().get("leases", {}).values():
            lease_close(lp)
        stop_server(server, gpus)
    summ = {}
    for r in task["runs"]:
        for d in task.get("domains", ("retail", "airline")):
            mp = ROOT / "runs" / r["run_id"] / d / "metrics.json"
            if mp.exists():
                m = json.load(open(mp))
                summ[f"{r['run_id']}/{d}"] = {k: m.get(k) for k in ("db_match_rate", "success_rate", "official_reward_mean", "reward_mean", "n_tasks", "mean_decisions", "premature_rate", "termination_reasons")
                                              if k in m}
    if (qmeta or {}).get("protocol") == derived.PROTOCOL:
        summ["_ckpt"] = {k: qmeta.get(k) for k in ("tag", "method", "arm", "alpha", "equals", "content_sha256", "files_sha256",
                                                   "eff_alpha", "n_restored", "canary", "base_cache")}
    return summ


def ckpt_sha(path: str) -> str | None:
    """sha256 over the checkpoint's safetensors files (name + content), for built (scratch) checkpoints only."""
    import hashlib
    files = sorted(Path(path).glob("*.safetensors"))
    if not files:
        return None
    h = hashlib.sha256()
    for f in files:
        h.update(f.name.encode())
        fh = hashlib.sha256()
        with open(f, "rb") as fp:
            for chunk in iter(lambda: fp.read(1 << 24), b""):
                fh.update(chunk)
        h.update(fh.digest())
    return h.hexdigest()


def run_fork(task, args, st: Status):
    """Fork task (protocol fork-v1, docs/insights/FORK_PROTOCOL.md): build Q (and B) checkpoints, serve each on its own
    vLLM server (2 GPUs: one per server; 1 GPU: both on it with GPU_UTIL=task['gpu_util'], started one after the
    other), check the numerics canary per server, run scripts/a6000/fork_driver.py against the node's simulator,
    then stop both servers. Prefix caches are per server process, so nothing is shared across weights."""
    gpus = args.gpus.split(",")
    env = model_env(task["model"], args.port)
    scratch = Path(os.environ.get("TMPDIR", "/tmp"))
    logdir = WORK / "logs/tasks"
    logdir.mkdir(parents=True, exist_ok=True)
    log = open(logdir / f"{task['id']}.log", "a")
    log.write(f"\n=== {time.ctime()} {socket.gethostname()} gpus={args.gpus} port={args.port} (fork)\n")
    log.flush()
    import fork_serve as FS  # per-role serving configs (scripts/a6000/fork_serve.py)
    # Fail fast on a wrong allocation (an old runner ignores task["gpus"]): only q4 fits B+Q on one card at max_len 33792.
    if len(gpus) != int(task.get("gpus", 1)) or (len(gpus) == 1 and task["model"] != "q4"):
        raise RuntimeError(f"fork {task['model']}: allocated GPUs {gpus} but the task needs {task.get('gpus')} "
                           f"(1-GPU B+Q only for q4; q8 at max_model_len {AGENT_MAXLEN} needs one GPU per server)")
    cfg = {r: FS.role_cfg(task, r) for r in ("B", "Q")}
    q_ck, b_ck = cfg["Q"]["ckpt"], cfg["B"]["ckpt"]
    same_w = q_ck == b_ck  # same weights spec: build once (the configurations may still differ, e.g. pure-KV Q)
    st.set("quantize" if q_ck["kind"] in ("gptq", "awq") else "setup", f"fork: build Q {q_ck['kind']}")
    q_path, q_meta = build_ckpt({"id": task["id"] + "_Q", "model": task["model"], "ckpt": q_ck}, env, gpus, scratch, log)
    b_path, b_meta = (q_path, q_meta) if same_w else build_ckpt({"id": task["id"] + "_B", "model": task["model"], "ckpt": b_ck}, env, gpus, scratch, log)
    one_gpu = len(gpus) == 1
    plan = {"B": (gpus[0], args.port + 100, b_path, b_ck), "Q": (gpus[-1], args.port + 200, q_path, q_ck)}
    servers, procs = {}, {}
    try:
        for role in ("B", "Q"):  # sequential start: on one GPU the second server profiles after the first holds its share
            g, port, path, ck = plan[role]
            st.set("setup", f"fork: starting {role} server on GPU {g}")
            senv = dict(env)
            if one_gpu:
                senv["GPU_UTIL"] = str(task.get("gpu_util", 0.44))
            senv.update(cfg[role]["serve_env"])  # same semantics as run_eval: the role's serve_env over the model env
            launch = [str(ROOT / "scripts/a6000/serve.sh"), g, str(port), path, "agent", str(AGENT_MAXLEN), *cfg[role]["serve_extra"]]
            lp = logdir / f"{task['id']}.{role}.vllm.log"
            off = lp.stat().st_size if lp.exists() else 0
            slog = open(lp, "a")
            procs[role] = subprocess.Popen(launch, env=senv, stdout=slog, stderr=subprocess.STDOUT, start_new_session=True)
            t0 = time.time()
            while not healthy(port):
                if procs[role].poll() is not None:
                    raise RuntimeError(f"fork {role} server exited during startup")
                if time.time() - t0 > 1800:
                    raise RuntimeError(f"fork {role} server did not come up in 30 min")
                time.sleep(5)
            with open(lp, errors="replace") as fh:
                fh.seek(off)
                cov = FS.hook_coverage(fh.read(), cfg[role], FS.num_layers(MODELS[task["model"]], path))
            servers[role] = {"gpu": g, "port": port, "pid": procs[role].pid, "ckpt": ck, "path": path,
                             "serve_env": cfg[role]["serve_env"], "serve_extra": cfg[role]["serve_extra"], "launch_args": launch[1:],
                             "gpu_util": senv.get("GPU_UTIL", "0.90"), "hook_coverage": cov, "canary": canary(port, task["model"])}
            if cov is not None and not cov["ok"]:
                raise RuntimeError(f"fork {role}: hook coverage failed {cov}")
        st.set("check", "fork: canaries")
        for role, path in (("Q", q_path),) + ((("B", b_path),) if not same_w else ()):
            if path.startswith(str(scratch)):
                servers[role]["ckpt_sha256"] = ckpt_sha(path)
        if same_w:
            servers["B"]["ckpt_sha256"] = servers["Q"].get("ckpt_sha256")
        for role in ("B", "Q"):
            eff = FS.effective_config(cfg[role], MODELS[task["model"]], servers[role].get("ckpt_sha256"), AGENT_MAXLEN, env)
            servers[role]["effective_config"] = eff
            servers[role]["effective_config_sha"] = FS.config_hash(eff)
        same_cfg = servers["B"]["effective_config_sha"] == servers["Q"]["effective_config_sha"]
        servers["same_effective_config"] = same_cfg
        for role in ("B", "Q"):  # BF16 reference canary only for the plain BF16 path (as run_eval: hooks/extra = other flavour)
            c = cfg[role]
            if c["ckpt"]["kind"] == "bf16" and not c["serve_extra"] and not FS.hooked(c):
                check_canary(plan[role][1], task["model"], "agent")
                servers[role]["canary_ref_ok"] = True
        for role, meta in (("B", b_meta), ("Q", q_meta)):  # derived restore/resid ckpts: same canary rules as run_eval
            c = cfg[role]
            if (meta or {}).get("protocol") == derived.PROTOCOL and not c["serve_extra"] and not FS.hooked(c):
                servers[role]["derived"] = {k: meta.get(k) for k in ("tag", "method", "arm", "alpha", "equals", "content_sha256",
                                                                     "files_sha256", "eff_alpha", "n_restored", "base_cache")}
                servers[role]["derived"]["canary"] = derived.canary_checks(plan[role][1], task["model"], meta, check_canary)
        if (same_cfg or task.get("expect_same_numerics")) and servers["B"]["canary"] != servers["Q"]["canary"]:
            raise RuntimeError(f"same effective config / expected same numerics, different canaries: "
                               f"{servers['B']['canary']} vs {servers['Q']['canary']}")
        if task.get("expect_distinct_numerics") and servers["B"]["canary"] == servers["Q"]["canary"]:
            raise RuntimeError("roles expected to differ numerically share a canary (quantization hook inactive?)")
        for path in {q_path, b_path}:
            if path.startswith(str(scratch)):
                for f in Path(path).glob("*.safetensors"):
                    f.unlink()
        servers["q_quantization"] = {k: v for k, v in (q_meta or {}).items() if k not in ("per_tensor", "stats")}
        ext = task.get("env")  # simulator-free external environment fork (scripts/ext/fork_ext.py, W39-extfork)
        ubase = None if ext else user_base()
        t1 = time.time()
        while ubase:
            try:
                urllib.request.urlopen(ubase + "/models", timeout=5)
                break
            except Exception:
                if time.time() - t1 > 2400:
                    raise RuntimeError(f"user simulator {ubase} unreachable")
                st.set("setup", "waiting for user simulator")
                time.sleep(15)
        servers["user_base"] = ubase
        servers["host"] = socket.gethostname()
        servers["job"] = os.environ.get("SLURM_JOB_ID")
        sfile = logdir / f"{task['id']}.servers.json"
        sfile.write_text(json.dumps(servers, indent=1))
        st.set("eval", f"fork {task['fork']['mode']}")
        if ext:
            cmd = [str(WORK / "envs" / ext / "bin/python"), str(ROOT / "scripts/ext/fork_ext.py"), "--task", args.task,
                   "--b-base", f"http://127.0.0.1:{plan['B'][1]}/v1", "--q-base", f"http://127.0.0.1:{plan['Q'][1]}/v1",
                   "--servers", str(sfile)]
        else:
            cmd = [sys.executable, str(ROOT / "scripts/a6000/fork_driver.py"), "--task", args.task,
                   "--b-base", f"http://127.0.0.1:{plan['B'][1]}/v1", "--q-base", f"http://127.0.0.1:{plan['Q'][1]}/v1",
                   "--user-base", ubase, "--servers", str(sfile)]
        drv = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        drv_lease = lease(ubase, f"fork/{task['id']}") if ubase else None
        while drv.poll() is None:
            time.sleep(10)
            lease_touch(drv_lease)
            for role, p in procs.items():
                if p.poll() is not None:
                    drv.kill()
                    raise RuntimeError(f"fork {role} server died during the driver")
        if drv.returncode != 0:
            raise RuntimeError(f"fork_driver failed rc={drv.returncode}")
    finally:
        lease_close(locals().get("drv_lease"))
        for role, p in procs.items():
            stop_server(p, [plan[role][0]])
    outp = ROOT / task["fork"]["out"]
    res = {"out": str(outp.relative_to(ROOT)), "servers": {k: {kk: vv for kk, vv in v.items() if kk != "path"} if isinstance(v, dict) else v
                                                           for k, v in servers.items() if k != "q_quantization"}}
    for name in ("gate.json", "gate_same.json"):
        if (outp / name).exists():
            res["verdict"] = json.load(open(outp / name)).get("verdict")
    return res


def run_sim(task, args, st: Status):
    """kind "sim" (W34-infra): one extra user-simulator replica on this worker's NVLink pair, served on the worker's
    port (8001 + first GPU, so it never collides with an agent port on the node). A runner holding the node claims it
    like any 2-GPU task, so a replica is added WITHOUT restarting the runner, and only once a whole pair has drained
    (while a 2-GPU task waits, the runner's upper pairs take only 2-GPU tasks, W5; the task's high priority wins).
    Steps: serve.sh on 0.0.0.0 -> numerics canary == fixed reference (check_canary, role sim) -> identical-request
    no-op check against a live reference replica -> concurrent throughput probe -> registry state up + heartbeat.
    Retire on queue/SIMSTOP.<instance>, queue/STOP, queue/STOP.<node> or < task["min_left"] s of Slurm time: state
    draining (the balancer and user_base() stop routing to it), then stop once no lease (running run_arm/fork_driver)
    refers to it. SIGTERM from the runner: stop now and leave the task in running/ so the runner requeues it."""
    import simreg
    node = socket.gethostname().split(".")[0]
    gpus = args.gpus.split(",")
    if len(gpus) != 2 or int(gpus[0]) % 2 or int(gpus[1]) != int(gpus[0]) + 1:
        raise RuntimeError(f"sim task needs one NVLink pair, got GPUs {gpus}")
    code = task.get("model", "q30a3")
    m = MODELS[code]
    port = args.port
    iid, url = simreg.instance_id(node, port), simreg.base_url(node, port)
    job = os.environ.get("SLURM_JOB_ID")
    rec = {"instance_id": iid, "url": url, "host": node, "port": port, "gpus": gpus, "model": code, "served_name": "user",
           "hf_id": m["hf_id"], "revision": m["revision"], "maxlen": int(task.get("maxlen", 65536)),
           "owner": {"kind": "sim_task", "task": task["id"], "job": job, "pid": os.getpid()},
           "started": time.time(), "state": "starting", "health": {"ok": False, "checked": time.time(), "detail": "starting"}}
    simreg.write(rec)
    slog = open(WORK / "logs" / f"sim_{iid}_{job or 'x'}.log", "a")
    senv = dict(os.environ, CLOQ_TOOL_PARSER=m["parser"], CLOQ_SERVE_HOST="0.0.0.0")
    server = subprocess.Popen([str(ROOT / "scripts/a6000/serve.sh"), args.gpus, str(port), snapshot(m["hf_id"], m["revision"]),
                               "user", str(rec["maxlen"])], env=senv, stdout=slog, stderr=subprocess.STDOUT, start_new_session=True)

    def on_term(*_):  # runner shutdown: never leave a replica behind, never touch anything but our own GPUs
        simreg.update(iid, state="stopped", stopped=time.time(), stop_reason="SIGTERM (runner stopping)",
                      interrupted_leases=simreg.active_leases(url))
        try:
            stop_server(server, gpus)
        finally:
            os._exit(143)
    signal.signal(signal.SIGTERM, on_term)
    try:
        st.set("setup", f"sim replica {iid}: starting vLLM")
        t0 = time.time()
        while not healthy(port):
            if server.poll() is not None:
                raise RuntimeError("simulator replica exited during startup")
            if time.time() - t0 > 1800:
                raise RuntimeError("simulator replica did not come up in 30 min")
            time.sleep(5)
        st.set("check", f"sim replica {iid}: numerics canary")
        h = check_canary(port, code, "sim", name="user")  # raises unless == analysis/determinism/canary_sim_<model>.json
        ref = task.get("ref_url")
        if not ref:
            live = [r for r in simreg.all_instances().values() if r.get("model") == code and r["instance_id"] != iid
                    and simreg.is_live(r)]
            live.sort(key=lambda r: (r.get("host") != node, r.get("port", 0)))
            ref = live[0]["url"] if live else None
        noop = simreg.noop_check(url, ref) if ref else {"ok": None, "detail": "no live reference replica"}
        if noop.get("ok") is False:
            raise RuntimeError(f"no-op check failed vs {ref}: {noop['identical']}/{noop['n']} identical")
        st.set("check", f"sim replica {iid}: throughput probe")
        tp = simreg.throughput(url, conc=int(task.get("probe_conc", 16)))
        simreg.update(iid, state="up", canary=h, canary_ok=True, noop=noop, throughput=tp, up_since=time.time(),
                      health={"ok": True, "checked": time.time(), "detail": "up"})
        with open(WORK / "logs/sim_instances.log", "a") as f:
            f.write(json.dumps({"event": "up", "instance": iid, "task": task["id"], "job": job, "gpus": gpus, "canary": h,
                                "noop_ok": noop.get("ok"), "gen_tok_s": tp["gen_tok_s"], "time": time.time()}) + "\n")
        st.set("user", f"user simulator replica {iid} (canary {h})")
        min_left = float(task.get("min_left", 1800))
        fails, draining, reason = 0, False, ""
        while True:
            time.sleep(30)
            if server.poll() is not None or not healthy(port):
                fails += 1
                if server.poll() is not None or fails >= 3:
                    raise RuntimeError(f"simulator replica {iid} died (rc={server.poll()})")
            else:
                fails = 0
            simreg.heartbeat(iid, fails == 0, "draining" if draining else "up")
            end = os.environ.get("CLOQ_JOB_END")
            left = float(end) - time.time() if end else 1e9
            q = WORK / "queue"
            if not draining:
                reason = ("SIMSTOP" if (q / f"SIMSTOP.{iid}").exists() else "STOP" if (q / "STOP").exists()
                          else f"STOP.{node}" if (q / f"STOP.{node}").exists() else "job time" if left < min_left else "")
                if reason:
                    draining = True
                    simreg.update(iid, state="draining", draining_since=time.time(), stop_reason=reason)
                    st.set("user", f"sim replica {iid} draining ({reason})")
                continue
            leases = simreg.active_leases(url)
            if leases and left > 300:
                continue
            simreg.update(iid, state="stopped", stopped=time.time(), interrupted_leases=leases)
            if leases:  # only when the Slurm job is about to end anyway: record who loses the endpoint
                with open(WORK / "logs/sim_interruptions.jsonl", "a") as f:
                    f.write(json.dumps({"instance": iid, "time": time.time(), "cause": "job end", "leases": leases}) + "\n")
            (q / f"SIMSTOP.{iid}").unlink(missing_ok=True)
            return {"instance": iid, "url": url, "canary": h, "noop": noop, "throughput": tp, "stop_reason": reason,
                    "served_s": time.time() - t0}
    except BaseException as e:
        r = simreg.read(iid) or {}
        if r.get("state") != "stopped":
            simreg.update(iid, state="dead", stopped=time.time(), stop_reason=repr(e)[:300],
                          interrupted_leases=simreg.active_leases(url))
            if simreg.active_leases(url):
                with open(WORK / "logs/sim_interruptions.jsonl", "a") as f:
                    f.write(json.dumps({"instance": iid, "time": time.time(), "cause": repr(e)[:300],
                                        "leases": simreg.active_leases(url)}) + "\n")
        raise
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        stop_server(server, gpus)


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
        elif task["kind"] == "sim":  # extra user-simulator replica (W34-infra, scripts/a6000/simreg.py)
            res = run_sim(task, args, st)
        elif task["kind"] == "fork":  # same-state 2x2 fork (cloq/fork.py, scripts/a6000/fork_driver.py)
            res = run_fork(task, args, st)
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
