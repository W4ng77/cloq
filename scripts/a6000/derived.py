"""Derived checkpoint kinds for the worker (execution plan P2, engineering line 3; docs/insights/PERTURBATION_PROTOCOL.md).

  {"kind": "restore", "base": <Q spec>, "arm": "late", "manifest": "manifests/perturb/restore_v1/q4/late.json"}
  {"kind": "resid",   "base": <Q spec>, "alpha": 0.5}
  <Q spec> = an ordinary gptq / awq / rtn ckpt dict, e.g. {"kind": "gptq", "wbits": 4, "calib": "manifests/a6k2/q4/calib_fp_traj_c1.json"}

Q is built once per (model, Q spec) into a persistent content-addressed cache, /data/ziyangs/cloq_work/ckpt_cache/base/
<model>_<kind>_<spec tag>/ (cross-node lock file; every later task, on any node, reuses the same Q files, so all arms of
one base are derived from bit-identical Q weights). The derived checkpoint itself is rebuilt per task in node-local
scratch by cloq.perturb (CPU, ~1-3 min) and deleted once vLLM has loaded it, exactly like every other built kind.

Tags and checks
  spec tag      sha256(protocol, model, revision, ckpt spec [+ manifest module sha])[:12]
  content sha   cloq.perturb's sha256 over (name, dtype, shape, bytes) of every tensor; the first build of a tag
                writes ckpt_cache/registry/<model>_<tag>.json, every later build (any node) must reproduce it
  equals        "bf16" (alpha 0, arm all) / "q" (alpha 1, arm none) is verified tensor by tensor during the build;
                "q" is also checked at file level against the cached Q (identical safetensors files)
  canary        after serving: equals bf16 -> must reproduce the BF16 agent reference canary (same rule as bf16 tasks);
                equals q -> the per-base reference canary_agentq_<base key>; every tag -> canary_derived_<tag>
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
WORK = Path("/data/ziyangs/cloq_work")
CACHE = Path(os.environ.get("CLOQ_CKPT_CACHE", str(WORK / "ckpt_cache")))
MAX_GB = float(os.environ.get("CLOQ_CKPT_CACHE_MAX_GB", "100"))  # refuse to add a base beyond this (1 TB user quota)
KINDS = ("restore", "resid")
BASE_KINDS = ("gptq", "awq", "rtn")
PROTOCOL = "perturb-v1"
STALE_LOCK = 3 * 3600


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def manifest_sha(ck: dict) -> str | None:
    if ck["kind"] != "restore":
        return None
    return json.load(open(ROOT / ck["manifest"]))["modules_sha256"]


def spec_tag(model: str, revision: str, ck: dict) -> str:
    return hashlib.sha256(canon({"protocol": PROTOCOL, "model": model, "revision": revision, "ckpt": ck,
                                 "manifest_modules_sha256": manifest_sha(ck) if ck.get("kind") == "restore" else None}
                                ).encode()).hexdigest()[:12]


def base_key(model: str, revision: str, base: dict) -> str:
    return f"{model}_{base['kind']}_{spec_tag(model, revision, base)}"


def dir_gb(p: Path) -> float:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e9 if p.exists() else 0.0


def cached_base(model: str, revision: str, base: dict, env, gpus, log, build_fn, sha_fn) -> tuple[str, dict]:
    """Path and cache record of the Q checkpoint for (model, base spec), building it once under a cross-node lock."""
    assert base["kind"] in BASE_KINDS, f"derived kinds need a gptq/awq/rtn base, got {base['kind']}"
    key = base_key(model, revision, base)
    root = CACHE / "base"
    root.mkdir(parents=True, exist_ok=True)
    d, info_p, lock = root / key, root / key / "cache.json", root / f"{key}.lock"
    while True:
        if info_p.exists():
            os.utime(info_p)  # last use, for manual LRU cleanup
            return str(d), json.load(open(info_p))
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > STALE_LOCK:
                    lock.unlink()
                    continue
            except FileNotFoundError:
                continue
            log.write(f"[derived] waiting for {key} (lock {lock.read_text() if lock.exists() else ''})\n")
            log.flush()
            time.sleep(30)
            continue
        os.write(fd, f"{socket.gethostname()} job={os.environ.get('SLURM_JOB_ID')} pid={os.getpid()} {time.ctime()}".encode())
        os.close(fd)
        tmp = CACHE / "build" / key
        try:
            used = dir_gb(root)
            if used > MAX_GB:
                raise RuntimeError(f"ckpt cache {root} holds {used:.0f} GB > CLOQ_CKPT_CACHE_MAX_GB={MAX_GB:.0f}; "
                                   "delete unused bases (see docs/insights/PERTURBATION_PROTOCOL.md section 6)")
            shutil.rmtree(tmp, ignore_errors=True)
            tmp.mkdir(parents=True)
            t0 = time.time()
            path, meta = build_fn({"id": "base", "model": model, "ckpt": base}, env, gpus, tmp, log)
            info = {"key": key, "spec": base, "model": model, "source_revision": revision,
                    "files_sha256": sha_fn(path), "built_on": socket.gethostname(), "job": os.environ.get("SLURM_JOB_ID"),
                    "built_at": time.time(), "build_seconds": time.time() - t0,
                    "quantization": {k: v for k, v in (meta or {}).items() if k not in ("per_tensor", "stats")}}
            if d.exists():
                shutil.rmtree(d)
            os.rename(path, d)  # same filesystem: atomic; cache.json written last marks it ready
            (d / "cache.json.tmp").write_text(json.dumps(info, indent=1))
            (d / "cache.json.tmp").replace(info_p)
            log.write(f"[derived] built base {key} in {info['build_seconds']:.0f}s sha={info['files_sha256'][:16]}\n")
            return str(d), info
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            try:
                lock.unlink()
            except FileNotFoundError:
                pass


def build(task: dict, src: str, revision: str, env, gpus, scratch: Path, log, build_fn, sha_fn) -> tuple[str, dict]:
    ck, model = task["ckpt"], task["model"]
    assert ck["kind"] in KINDS
    if ck["kind"] == "restore":
        man = json.load(open(ROOT / ck["manifest"]))
        assert man["model"] == model and man["source_revision"] == revision, f"manifest {ck['manifest']} is for another model"
        assert ck.get("arm", man["arm"]) == man["arm"], f"ckpt arm {ck.get('arm')} != manifest arm {man['arm']}"
        mode_args = ["--manifest", str(ROOT / ck["manifest"])]
    else:
        mode_args = ["--alpha", repr(float(ck["alpha"]))]
    tag = spec_tag(model, revision, ck)
    bpath, binfo = cached_base(model, revision, ck["base"], env, gpus, log, build_fn, sha_fn)
    out = scratch / f"ckpt_{task['id']}"
    if out.exists():
        shutil.rmtree(out)
    extra = {"spec": ck, "tag": tag, "base_cache": {"key": binfo["key"], "files_sha256": binfo["files_sha256"],
                                                   "built_on": binfo["built_on"], "path": bpath}}
    cmd = [sys.executable, "-m", "cloq.perturb", ck["kind"], "--src", src, "--q", bpath, "--out", str(out),
           "--extra-meta", json.dumps(extra)] + mode_args
    r = subprocess.run(cmd, cwd=ROOT, env=dict(env, CUDA_VISIBLE_DEVICES=""), stdout=log, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        raise RuntimeError(f"derived checkpoint build failed ({ck}) rc={r.returncode}")
    meta = json.load(open(out / "quantization.json"))
    meta["files_sha256"] = sha_fn(str(out))
    if meta["equals"] == "q" and meta["files_sha256"] != binfo["files_sha256"]:
        raise RuntimeError(f"{tag}: tensors equal Q but files differ from the cached Q ({meta['files_sha256'][:16]} vs "
                           f"{binfo['files_sha256'][:16]})")
    reg = CACHE / "registry" / f"{model}_{tag}.json"
    reg.parent.mkdir(parents=True, exist_ok=True)
    rec = {"tag": tag, "spec": ck, "content_sha256": meta["content_sha256"], "files_sha256": meta["files_sha256"],
           "equals": meta["equals"], "base_key": binfo["key"], "base_files_sha256": binfo["files_sha256"],
           "host": socket.gethostname(), "time": time.time(), "task": task["id"]}
    if reg.exists():
        want = json.load(open(reg))
        if (want["content_sha256"], want["base_files_sha256"]) != (rec["content_sha256"], rec["base_files_sha256"]):
            raise RuntimeError(f"derived ckpt {tag} not reproduced: content {rec['content_sha256'][:16]} vs registry "
                               f"{want['content_sha256'][:16]}")
    else:
        reg.write_text(json.dumps(rec, indent=1))
    with open(CACHE / "registry.log", "a") as f:
        f.write(json.dumps(rec) + "\n")
    (out / "quantization.json").write_text(json.dumps(meta, indent=1))
    return str(out), meta


def canary_checks(port: int, model: str, meta: dict, check_canary) -> dict:
    """Numerics canary rules for a served derived checkpoint (see module docstring)."""
    out = {}
    if meta.get("equals") == "bf16":
        out["bf16_ref"] = check_canary(port, model, "agent")
    elif meta.get("equals") == "q":
        out["q_ref"] = check_canary(port, model, f"agentq_{meta['base_cache']['key']}")
    out["tag_ref"] = check_canary(port, model, f"derived_{meta['tag']}")
    return out
