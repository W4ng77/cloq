"""Per-role serving configuration for fork tasks (protocol fork-v1; docs/insights/FORK_PROTOCOL.md §5).

A fork task serves two roles, B and Q, each on its own vLLM server. A role is fully described by
  {"ckpt": <checkpoint spec as in eval tasks>, "serve_env": {...}, "serve_extra": [...]}
given as task["B"] / task["Q"]. The legacy form (task["q_ckpt"], task["b_ckpt"]) maps to empty serve_env/serve_extra.
serve_env and serve_extra are applied to that role's server exactly as run_eval applies a task's (env overrides on
top of the model env; extra vLLM args after the fixed ones). Two roles are "the same configuration" only if their
effective-config hashes are equal; weights alone never decide it (a pure-KV Q shares B's weights but is a different
configuration and gets its own server).

Effective config (hashed): model id/revision, weights identity (built checkpoint: sha256 of its safetensors; BF16/HF:
repo@revision), ckpt spec, serve_env, serve_extra, max_model_len, frozen numerics env (batch invariance, Inductor
determinism), W/A/K/V bits, hook version (sha256 of scripts/a6000/pyhooks/*.py) when hooked, compile-cache namespace.
Not hashed (recorded): GPU, port, pid, gpu_memory_utilization (memory only; the BF16 canary reproduces its reference at
0.44, analysis/fork/gate/q4_gptq_w4_d1/gate.json servers.B).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
HOOKS = ROOT / "scripts/a6000/pyhooks"
NUMERICS_ENV = ("VLLM_BATCH_INVARIANT", "VLLM_USE_FLASHINFER_SAMPLER", "TORCHINDUCTOR_DETERMINISTIC", "CLOQ_BATCH_INVARIANT")


def role_cfg(task: dict, role: str) -> dict:
    if role in task:
        c = dict(task[role])
    else:
        ck = task["q_ckpt"] if role == "Q" else task.get("b_ckpt", {"kind": "bf16"})
        c = {"ckpt": ck}
    c.setdefault("serve_env", {})
    c.setdefault("serve_extra", [])
    c["serve_env"] = {k: str(v) for k, v in c["serve_env"].items()}
    return c


def hooked(cfg: dict) -> bool:
    return cfg["serve_env"].get("CLOQ_PYHOOKS") == "1"


def kvq(cfg: dict) -> dict | None:
    e = cfg["serve_env"]
    if not (hooked(cfg) and e.get("CLOQ_KVQ_BITS")):
        return None
    bits = int(e["CLOQ_KVQ_BITS"])
    rot = e.get("CLOQ_KVQ_ROT", "0") == "1"
    which = e.get("CLOQ_KVQ_WHICH", "kv")
    return {"bits": bits, "rot": rot, "which": which, "active": bits < 16 or rot, "namespace": f"kvq_b{bits}_r{int(rot)}_{which}"}


def aq(cfg: dict) -> dict | None:
    e = cfg["serve_env"]
    if not (hooked(cfg) and (e.get("CLOQ_AQ_BITS") or e.get("CLOQ_AQ_HAD", "0") != "0")):
        return None
    b = int(e.get("CLOQ_AQ_BITS", 16))
    only = sorted(x for x in e.get("CLOQ_AQ_ONLY", "qkv,o,gate_up,down").split(",") if x)
    return {"bits": b, "fmt": e.get("CLOQ_AQ_FMT", "sym_quarot"), "clip": e.get("CLOQ_AQ_CLIP", "1.0"),
            "group": e.get("CLOQ_AQ_GROUP", "-1"), "only": only, "had": e.get("CLOQ_AQ_HAD", "0"), "quant": b < 16}


def bits(cfg: dict) -> dict:
    ck = cfg["ckpt"]
    w = 16 if ck["kind"] in ("bf16", "rot_bf16") else int(ck.get("wbits", 16)) if "wbits" in ck else None
    if ck["kind"] == "hf":
        w = {"fp8": 8, "awq": 4}.get(ck.get("format"), None)
    k = v = 16
    q = kvq(cfg)
    if q:
        k = q["bits"] if "k" in q["which"] else 16
        v = q["bits"] if "v" in q["which"] else 16
    a = aq(cfg)["bits"] if aq(cfg) else 16
    return {"W": w, "A": a, "K": k, "V": v}


def hook_version() -> str:
    h = hashlib.sha256()
    for p in sorted(HOOKS.glob("*.py")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def weights_id(cfg: dict, model: dict, ckpt_sha: str | None) -> str:
    ck = cfg["ckpt"]
    if ck["kind"] == "bf16":
        return f"{model['hf_id']}@{model['revision']}"
    if ck["kind"] == "hf":
        return f"{ck['hf_id']}@{ck['revision']}"
    return f"sha256:{ckpt_sha}"


def effective_config(cfg: dict, model: dict, ckpt_sha: str | None, maxlen: int, base_env: dict) -> dict:
    q = kvq(cfg)
    eff = {"model": {"hf_id": model["hf_id"], "revision": model["revision"], "chat_template_kwargs": model.get("chat_template_kwargs") or {}},
           "weights": weights_id(cfg, model, ckpt_sha), "ckpt": cfg["ckpt"], "serve_env": cfg["serve_env"],
           "serve_extra": list(cfg["serve_extra"]), "max_model_len": maxlen,
           "numerics_env": {k: base_env.get(k) for k in NUMERICS_ENV}, "bits": bits(cfg),
           "hook_version": hook_version() if hooked(cfg) else None,
           "cache_namespace": "/".join(x for x in ((q or {}).get("namespace"), ("aq:" + hashlib.sha256(json.dumps(aq(cfg), sort_keys=True).encode()).hexdigest()[:8]) if aq(cfg) else None) if x) or "default"}
    return eff


def config_hash(eff: dict) -> str:
    return hashlib.sha256(json.dumps(eff, sort_keys=True).encode()).hexdigest()[:16]


def num_layers(model: dict, path: str) -> int | None:
    try:
        c = json.load(open(Path(path) / "config.json"))
        return int(c.get("num_hidden_layers") or (c.get("text_config") or {}).get("num_hidden_layers"))
    except Exception:
        return None


def hook_coverage(log_text: str, cfg: dict, n_layers: int | None) -> dict | None:
    """Coverage from the server log of this launch. KV hook: `wrapped` lines (patch installed, per process) and one
    `hooked attention` line per Attention instance in the engine process; every decoder layer must be hooked. Activation
    hook: its per-module lines (action quant / had_only / pass) in the engine process; with bits < 16 the number of
    quantized linear modules must equal len(only) x layers, with a Hadamard setting at least one Hadamard module.
    The compile-cache roots the hooks report are recorded (cache namespace actually used)."""
    if not hooked(cfg):
        return None
    lines = log_text.splitlines()
    q, a = kvq(cfg), aq(cfg)
    out = {"kvq": q, "aq": a, "cache_roots": sorted({ln.split("cache_root=")[1].split()[0] for ln in lines if "cache_root=" in ln and "[cloq_" in ln})}
    ok = True
    if q is not None:
        wrapped = [ln for ln in lines if "[cloq_kvq]" in ln and "wrapped" in ln]
        by_pid: dict = {}
        for ln in lines:
            if "[cloq_kvq]" in ln and "hooked attention" in ln and "type=decoder" in ln.lower():
                pid = ln.split("pid=")[1].split()[0]
                by_pid[pid] = by_pid.get(pid, 0) + 1
        n_dec = max(by_pid.values()) if by_pid else 0
        out.update({"n_wrapped_processes": len(wrapped), "decoder_attention_hooked": n_dec, "expected_layers": n_layers})
        ok &= len(wrapped) > 0 and n_layers is not None and n_dec == n_layers
    if a is not None:
        cnt: dict = {}
        for ln in lines:
            if "[cloq_aq]" in ln and " module " in ln and "action=" in ln:
                pid = ln.split("pid=")[1].split()[0]
                act = ln.split("action=")[1].split()[0]
                cnt.setdefault(pid, {"quant": 0, "had_only": 0, "pass": 0})
                cnt[pid][act] = cnt[pid].get(act, 0) + 1
        best = max(cnt.values(), key=lambda c: sum(c.values())) if cnt else {"quant": 0, "had_only": 0, "pass": 0}
        exp_q = len(a["only"]) * n_layers if (a["quant"] and n_layers) else 0
        out.update({"aq_modules": best, "aq_expected_quant": exp_q})
        ok &= (not a["quant"] or best["quant"] == exp_q) and (a["had"] == "0" or best["quant"] + best["had_only"] > 0) and bool(cnt)
    out["ok"] = bool(ok)
    return out
