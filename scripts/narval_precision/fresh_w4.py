"""Generate and analyze fresh paired W4/BF16 action interventions on Narval."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import ExitStack

SCRIPT = Path(__file__).resolve().parent
REPO = SCRIPT.parents[1]
DOMAINS = ("retail", "airline")
TAU2_REV = "2174a603f6d014ef94473ffa95957f6ce27100db"
AGENT = "q8"
SIM = "q30a3"
CALIB = "manifests/a6k2/q8/calib_fp_traj_c1.json"
SEED = "cloq-narval-fresh-w4-v1"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def task_plan(index):
    tasks = load(REPO / "manifests/eval_tasks_v0.json")
    if [len(set(tasks[domain])) for domain in DOMAINS] != [58, 27]:
        raise ValueError("Unexpected development task panel")
    if index == 0:
        tasks = {
            domain: sorted(tasks[domain], key=lambda task: digest(f"{SEED}|smoke|{domain}|{task}"))[:3]
            for domain in DOMAINS
        }
    nonce = digest(f"{SEED}|block|{index:02d}")[:8]
    return tasks, nonce


def hf_home(work):
    return Path(os.environ.get("CLOQ_HF_HOME", work / "hf")).expanduser().resolve()


def setup_runtime(work):
    from huggingface_hub import snapshot_download

    manifest = load(REPO / CALIB)
    contexts = manifest["contexts"]
    if len(contexts) != 57 or sum(len(c["row_idx"]) for c in contexts) != 64000:
        raise ValueError("Unexpected paper calibration draw")
    models = load(REPO / "scripts/a6000/models.json")
    for key in (AGENT, SIM):
        spec = models[key]
        print(snapshot_download(repo_id=spec["hf_id"], revision=spec["revision"],
                                cache_dir=str(hf_home(work) / "hub")), flush=True)


def snapshots(work):
    models = load(REPO / "scripts/a6000/models.json")
    out = {}
    for key in (AGENT, SIM):
        m = models[key]
        folder = "models--" + m["hf_id"].replace("/", "--")
        path = hf_home(work) / "hub" / folder / "snapshots" / m["revision"]
        if not (path / "config.json").is_file() or not any(path.glob("*.safetensors")):
            raise RuntimeError(f"Pinned model is missing: {path}. Run the prepare command.")
        out[key] = path
    return models, out


def git_revision(path, env_key):
    return os.environ.get(env_key) or subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def workspace(root, work, models):
    root.mkdir(parents=True)
    for key in ("cloq", "configs", "scripts", "manifests"):
        (root / key).symlink_to(REPO / key, target_is_directory=True)
    tau2 = work / "tau2-bench"
    (root / "third_party").mkdir()
    (root / "third_party" / "tau2-bench").symlink_to(tau2, target_is_directory=True)
    current = git_revision(tau2, "CLOQ_TAU2_REV")
    if current != TAU2_REV:
        raise ValueError(f"Unexpected tau2 commit {current}")
    base = models[AGENT]
    sim = models[SIM]
    os.environ.update({
        "PYTHONPATH": str(root),
        "CLOQ_ROOT": str(root),
        "TAU2_DATA_DIR": str(tau2 / "data"),
        "HF_HOME": str(hf_home(work)),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "CLOQ_MODEL_ID": base["hf_id"],
        "CLOQ_MODEL_REVISION": base["revision"],
        "CLOQ_CHAT_TEMPLATE_KWARGS": json.dumps(base["chat_template_kwargs"]),
        "CLOQ_USER_MODEL_ID": sim["hf_id"],
        "CLOQ_USER_CHAT_TEMPLATE_KWARGS": json.dumps(sim["chat_template_kwargs"]),
        "CLOQ_MAX_PROMPT_TOKENS": "32768",
        "CLOQ_TOP_LOGPROBS": "5",
        "CLOQ_AGENT_TEMPERATURE": "0",
        "CLOQ_AGENT_SEED": "0",
        "VLLM_BATCH_INVARIANT": "1",
        "VLLM_USE_FLASHINFER_SAMPLER": "0",
        "TORCHINDUCTOR_DETERMINISTIC": "1",
    })
    sys.path.insert(0, str(root))


def build(work, attempt):
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("GPTQ checkpoint build requires a CUDA compute job")
    final = work / "gptq_w4"
    if (final / "quantization.json").is_file():
        validate_quant(final)
        return
    models, paths = snapshots(work)
    workspace(attempt / "workspace", work, models)
    tmp = attempt / "checkpoint"
    subprocess.run([sys.executable, "-m", "cloq.quantize", "--method", "gptq", "--wbits", "4",
                    "--src", str(paths[AGENT]), "--calib", str(REPO / CALIB), "--out", str(tmp)], check=True)
    validate_quant(tmp)
    tmp.rename(final)


def validate_quant(checkpoint):
    meta = load(checkpoint / "quantization.json")
    expected = {"wbits": 4, "method": "GPTQ", "group_size": 128, "sym": False, "percdamp": .01,
                "blocksize": 128, "act_order": True, "true_sequential": True, "storage": "fake-quant bf16"}
    if any(meta.get(key) != value for key, value in expected.items()):
        raise ValueError("Checkpoint metadata does not match the frozen GPTQ-W4 recipe")
    revision = load(REPO / "scripts/a6000/models.json")[AGENT]["revision"]
    calibration = hashlib.sha256((REPO / CALIB).read_bytes()).hexdigest()
    if meta["source_revision"] != revision or meta["calibration"]["manifest_sha256"] != calibration:
        raise ValueError("Checkpoint provenance does not match the pinned inputs")
    shards = meta["weight_files"]
    if not shards or any(not (checkpoint / name).is_file() for name in shards):
        raise ValueError("GPTQ-W4 checkpoint is missing shards")
    return hashlib.sha256((checkpoint / "quantization.json").read_bytes()).hexdigest()


def gpu_ids():
    value = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    ids = [part.strip() for part in value.split(",") if part.strip()]
    if len(ids) != 4 or len(set(ids)) != 4:
        raise RuntimeError("Evaluation expects four allocated CUDA devices on one node")
    return ids


def stop(proc):
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
    except ProcessLookupError:
        proc.wait()


def next_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def serve(stack, path, devices, name, label, maxlen, attempt):
    port = next_port()
    base = f"http://127.0.0.1:{port}/v1"
    log = stack.enter_context((attempt / f"{label}.vllm.log").open("w"))
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=",".join(devices),
               VLLM_CACHE_ROOT=str(Path(os.environ["TMPDIR"]) / f"vllm-{label}"))
    cmd = [sys.executable, "-m", "vllm.entrypoints.cli.main", "serve", str(path),
           "--host", "127.0.0.1", "--port", str(port), "--served-model-name", name,
           "--dtype", "bfloat16", "--max-model-len", str(maxlen), "--gpu-memory-utilization", "0.90",
           "--tensor-parallel-size", str(len(devices)), "--generation-config", "vllm", "--seed", "0",
           "--enable-auto-tool-choice", "--tool-call-parser", "hermes", "--max-logprobs", "20",
           "--compilation-config", '{"inductor_compile_config":{"combo_kernels":true,"benchmark_combo_kernel":false}}']
    proc = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    stack.callback(stop, proc)
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"{label} server exited with {proc.returncode}. See {log.name}")
        try:
            with urllib.request.urlopen(base + "/models", timeout=3) as response:
                names = {m["id"] for m in json.load(response)["data"]}
            if name in names and proc.poll() is None:
                return base, cmd
        except OSError:
            pass
        time.sleep(5)
    raise RuntimeError(f"{label} server timed out. See {log.name}")


def load_upstream(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def outcome(record, task, messages):
    term = record.get("termination_reason")
    if term not in ("user_stop", "agent_stop", "max_steps", "too_many_errors"):
        raise ValueError(f"Unadmitted termination: {term}")
    value = record.get("official_reward")
    if value not in (0, 1):
        raise ValueError(f"Missing or nonbinary official reward: {value}")
    basis = (task.get("evaluation_criteria") or {}).get("reward_basis") or []
    if set(basis) - {"DB", "ENV_ASSERTION", "ACTION", "COMMUNICATE", "NL_ASSERTION"}:
        raise ValueError(f"Unsupported reward criterion: {basis}")
    info = record.get("reward_info") or {}
    checks = info.get("communicate_checks") or []
    return {
        "db": int(bool(record.get("db_match")) and term in ("user_stop", "agent_stop")),
        "official": int(value), "official_without_nl": int(value), "termination": term,
        "communication_failure": "COMMUNICATE" in basis and any(not check["met"] for check in checks),
        "judge_input": {"task_id": task["id"], "task": task, "messages": messages}
        if value == 1 and "NL_ASSERTION" in basis else None,
    }


def apply_nl_judgments(rows, user, attempt):
    # Upstream _judge_one temporarily patches the evaluator module. Run it serially.
    from cloq.config import judge_llm_args
    from cloq.nl_judge import _judge_one

    args = judge_llm_args(user)
    for row in rows:
        for arm in ("QQ", "BQ"):
            score = row[arm]
            judge_input = score.pop("judge_input", None)
            if judge_input is None:
                continue
            result = _judge_one(judge_input, "hosted_vllm/user", args)
            save(attempt / "judgments" / f"{row['domain']}-{row['task']}-{arm}.json", result)
            if result["judge_error"] or not result["nl_in_basis"]:
                raise RuntimeError(f"Invalid NL judgment: {row['domain']}:{row['task']} {arm}")
            score["official"] = int(result["nl_all_met"])
            score["nl_failure"] = not result["nl_all_met"]


def evaluate(work, attempt, index, concurrency, quant_sha):
    import torch
    import vllm

    ids = gpu_ids()
    if not torch.cuda.is_available() or torch.cuda.device_count() != 4:
        raise RuntimeError("Four visible CUDA devices are required")
    if any(torch.cuda.get_device_properties(i).total_memory < 39 * 1024**3 for i in range(4)):
        raise RuntimeError("Each of the four GPUs needs at least 40 GB of memory")
    models, paths = snapshots(work)
    root = attempt / "workspace"
    workspace(root, work, models)
    from cloq import fork
    driver = load_upstream(REPO / "scripts/a6000/fork_driver.py", "cloq_fork_driver")
    fork.setup_tau2()
    tasks, nonce = task_plan(index)
    run_id = f"a6k2_q8_gptq_w4_d1_n261125{index:02d}"
    task_file = attempt / "tasks.json"
    save(task_file, tasks)
    os.environ["CLOQ_PROMPT_NONCE"] = nonce

    with ExitStack() as stack:
        user, user_cmd = serve(stack, paths[SIM], ids[2:], "user", "user", 65536, attempt)
        q, q_cmd = serve(stack, work / "gptq_w4", ids[:1], "agent", "w4", 33792, attempt)
        b, b_cmd = serve(stack, paths[AGENT], ids[1:2], "agent", "bf16", 33792, attempt)
        bases = {"Q": q, "B": b}
        provenance = {
            "cloq_commit": git_revision(REPO, "CLOQ_CHECKOUT_REV"),
            "tau2_commit": TAU2_REV, "checkpoint_sha": quant_sha, "models": {k: models[k] for k in (AGENT, SIM)},
            "host": socket.gethostname(), "torch": torch.__version__, "vllm": vllm.__version__,
            "visible_gpu_models": [torch.cuda.get_device_name(i) for i in range(4)],
            "launch": [user_cmd, q_cmd, b_cmd], "seed": SEED, "nonce": nonce, "concurrency": concurrency,
        }
        save(attempt / "provenance.json", provenance)
        blocks = {}
        for domain in DOMAINS:
            subprocess.run([sys.executable, "-m", "cloq.run_arm", "--run-id", run_id,
                            "--arm", "gptq_w4_d1", "--domain", domain, "--task-file", str(task_file),
                            "--agent-base", q, "--user-base", user, "--checkpoint", str(work / "gptq_w4"),
                            "--max-concurrency", str(concurrency)], check=True, cwd=root)
            block = fork.Block(root, run_id, domain)
            if set(block.traj) != set(tasks[domain]):
                raise RuntimeError(f"Incomplete {domain} W4 baseline")
            blocks[domain] = block
        keys = [(domain, task) for domain in DOMAINS for task in tasks[domain]]
        states = attempt / "states"
        states.mkdir()

        def search(key):
            domain, task = key
            return driver.search_task(blocks[domain], task, bases, user, states, q_check=True)

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            searches = list(pool.map(search, keys))
        save(attempt / "search.json", searches)
        divergences = {r["state_id"] for r in searches if r.get("t_star") is not None}
        audits = sorted(divergences, key=lambda sid: digest(f"{SEED}|audit|{sid}"))
        audit_ids = set(audits if index == 0 else audits[:(len(audits) + 9) // 10])
        if index == 0 and not divergences:
            raise RuntimeError("Smoke found no divergences and could not validate replay")

        def pair(row):
            domain, task = row["domain"], row["task_id"]
            if row.get("exclusion"):
                raise ValueError(f"{domain}:{task}: {row['exclusion']}")
            tr = blocks[domain].traj[task]
            qq = outcome(tr, tr["task"], tr["messages"])
            result = {"domain": domain, "task": task, "diverged": row["t_star"] is not None, "QQ": qq, "BQ": qq}
            if not result["diverged"]:
                return result
            sid = row["state_id"]
            state = load(states / f"{sid}.json")
            if not all(row["q_replay"].values()) or not all(
                row["io_check"][k] for k in ("history_sha_ok", "env_hash_ok", "task_sha_ok")
            ):
                raise RuntimeError(f"State restoration or Q decision replay failed: {domain}:{task}")
            branch = fork.run_branch(state, "B", "Q", bases, user, f"fresh-BQ-{sid}")
            save(attempt / "branches" / f"{sid}_BQ.json", branch)
            if "error" in branch or not branch.get("prefix_ok") or not branch.get("env_hash_init_ok"):
                raise RuntimeError(f"Invalid BQ branch: {domain}:{task}")
            if not branch["decisions"] or not branch["decisions"][0]["forced"]:
                raise RuntimeError(f"BQ did not execute the forced action: {domain}:{task}")
            if not driver.budget_check(state, branch)["ok"]:
                raise RuntimeError(f"BQ budget replay mismatch: {domain}:{task}")
            result["BQ"] = outcome(branch, tr["task"], state["history"] + branch["suffix"])
            result["state_id"] = sid
            if sid in audit_ids:
                replay = fork.run_branch(state, "Q", "Q", bases, user, f"fresh-QQ-{sid}")
                save(attempt / "branches" / f"{sid}_QQ.json", replay)
                check = driver.noop_check(state, replay, driver.orig_final_hash(state, blocks[domain]))
                save(attempt / "audits" / f"{sid}.json", check)
                if not check["ok"]:
                    raise RuntimeError(f"QQ no-op replay failed: {domain}:{task}")
                result["qq_audit_ok"] = True
            return result

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            rows = list(pool.map(pair, searches))
        apply_nl_judgments(rows, user, attempt)
    return {"block": index, "provenance": provenance, "attempt": str(attempt), "rows": rows}


def effects(row):
    result = {}
    for endpoint in ("db", "official"):
        net = row["BQ"][endpoint] - row["QQ"][endpoint]
        result.update({f"{endpoint}_rescue": int(net == 1), f"{endpoint}_damage": int(net == -1),
                       f"{endpoint}_net": net})
    for metric in ("rescue", "damage", "net"):
        result[f"delta_{metric}"] = result[f"official_{metric}"] - result[f"db_{metric}"]
    return result


def summarize(work, indexes):
    analysis = load_upstream(REPO / "analysis/fork/analyze_dev.py", "cloq_analyze_dev")
    blocks = [load(work / "blocks" / f"{i:02d}.json") for i in indexes]
    members = {(b["provenance"]["cloq_commit"], b["provenance"]["checkpoint_sha"],
                b["provenance"]["vllm"], b["provenance"]["torch"], tuple(b["provenance"]["visible_gpu_models"]),
                b["provenance"]["concurrency"]) for b in blocks}
    if len(members) != 1:
        raise ValueError("Blocks use different revisions, checkpoints, devices, versions or concurrency")
    units = []
    for index, b in zip(indexes, blocks):
        tasks, nonce = task_plan(index)
        expected = {(domain, task) for domain, names in tasks.items() for task in names}
        actual = [(r["domain"], r["task"]) for r in b["rows"]]
        if b["block"] != index or b["provenance"]["nonce"] != nonce or len(actual) != len(expected) or set(actual) != expected:
            raise ValueError(f"Wrong task/nonce coverage for block {index}")
        units.extend({**r, "task": f"{r['domain']}:{r['task']}", "block": str(index), "E": effects(r)}
                     for r in b["rows"])
    out = {}
    for label in ("pooled", *DOMAINS):
        group = units if label == "pooled" else [u for u in units if u["domain"] == label]
        tasks = sorted({u["task"] for u in group})
        boot = analysis.Boot(tasks, {t: [str(i) for i in indexes] for t in tasks})
        metrics = {}
        for metric in group[0]["E"]:
            pt, draws = boot.task_mean(*boot.arrays(group, metric))
            metrics[metric] = analysis.summarise(pt, draws, boot=boot)
        counts = Counter()
        for row in group:
            for arm in ("QQ", "BQ"):
                arm_row = row[arm]
                if arm_row["db"] > arm_row["official"]:
                    counts[f"{arm}_db_success_official_failure"] += 1
                    if arm_row["communication_failure"]:
                        counts[f"{arm}_downgrade_with_communication_failure"] += 1
                    if arm_row.get("nl_failure"):
                        counts[f"{arm}_downgrade_with_nl_failure"] += 1
        out[label] = {"units": len(group), "divergent": sum(r["diverged"] for r in group),
                      "qq_audited": sum(r.get("qq_audit_ok", False) for r in group),
                      "estimates_pp": metrics, "endpoint_disagreements": dict(counts)}
    name = "full" if len(indexes) == 20 else "pilot"
    save(work / f"report-{name}.json", {"blocks": indexes, "results": out})
    print(json.dumps(out["pooled"], indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "build", "eval", "pilot-report", "full-report"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--block", type=int, choices=range(21))
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    work = args.work.resolve()
    if args.command == "prepare":
        setup_runtime(work)
    elif args.command in ("pilot-report", "full-report"):
        summarize(work, list(range(1, 4 if args.command == "pilot-report" else 21)))
    elif args.attempt is None or "SLURM_JOB_ID" not in os.environ:
        parser.error("build and eval require a Slurm compute allocation and --attempt")
    elif args.command == "build":
        build(work, args.attempt)
    elif args.block is None:
        parser.error("eval requires --block")
    else:
        quant_sha = validate_quant(work / "gptq_w4")
        target = work / "blocks" / f"{args.block:02d}.json"
        if target.exists():
            raise SystemExit(f"Block output already exists: {target}")
        save(target, evaluate(work, args.attempt, args.block, args.concurrency, quant_sha))
        print(f"Completed block {args.block:02d}: {target}", flush=True)


if __name__ == "__main__":
    main()
