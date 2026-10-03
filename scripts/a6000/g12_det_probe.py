"""W100n: which serving factor breaks g12 (Gemma 4 12B) replay determinism? (adapted from det_probe.py; g12 only)

The tau2 fork gate's identity probe failed on g12 (idcheck Q 9/16, B 12/16): every recorded tool-call decision
regenerated exactly, but most long text replies did not. This replays recorded BF16 g12 decisions (text replies and tool
calls from runs a6k2_g12_bf16_g1 / a6k2_g12_bf16_cal) on fresh text-only BF16 servers on this GPU, under
  seq_cold   one request at a time (shared prefixes get cached after the first)
  seq_warm   the same again (every prompt fully cached)
  conc       all prompts at once (batching, chunked-prefill interleaving)
for several server configurations (the gate's g12 flags plus one change each). Reports, per condition, how many
completions equal the record and equal seq_cold of the same configuration.

usage (inside a cmd task): python scripts/a6000/g12_det_probe.py --out analysis/fork/g12_gate/det_probe.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
sys.path.insert(0, str(ROOT / "scripts/a6000"))
from worker import MODELS, healthy, model_src, stop_server  # noqa: E402
from make_tasks_g12 import SERVE_EXTRA  # noqa: E402

FROZEN = json.load(open(ROOT / "configs/frozen_v0.json"))
RUNS = ("a6k2_g12_bf16_g1", "a6k2_g12_bf16_cal")


def items(n_text: int, n_tool: int):
    text, tool = [], []
    for run in RUNS:
        for d in ("retail", "airline"):
            for line in open(ROOT / "runs" / run / d / "decisions.jsonl"):
                x = json.loads(line)
                if not x.get("completion_token_ids") or not x.get("prompt_ids_from_server"):
                    continue
                key = (run, d, str(x["task_id"]), x["decision_idx"])
                h = hashlib.sha256(("g12det|" + "|".join(map(str, key))).encode()).hexdigest()
                (tool if x.get("tool_calls") else text).append((h, key, x))
    text.sort()
    tool.sort()
    return [(k, x) for _, k, x in text[:n_text] + tool[:n_tool]]


def complete(port: int, ids: list[int]) -> list[int]:
    g = FROZEN["generation_agent"]
    body = {"model": "agent", "prompt": ids, "max_tokens": int(g["max_tokens"]), "temperature": g["temperature"],
            "top_p": g["top_p"], "top_k": g["top_k"], "seed": g["seed"], "repetition_penalty": g["repetition_penalty"],
            "presence_penalty": g["presence_penalty"], "frequency_penalty": g["frequency_penalty"],
            "return_token_ids": True, "skip_special_tokens": False}
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        c = json.load(r)["choices"][0]
    return c.get("token_ids")


def serve(port: int, extra: list[str], env_extra: dict):
    m = MODELS["g12"]
    env = dict(os.environ, CLOQ_TOOL_PARSER=m["parser"], **env_extra)
    gpus = os.environ["CUDA_VISIBLE_DEVICES"]
    log = open(ROOT.parent / "cloq_work/logs/tasks" / f"g12_det_probe.{port}.vllm.log", "a")
    p = subprocess.Popen([str(ROOT / "scripts/a6000/serve.sh"), gpus, str(port), model_src(m), "agent", "33792", *extra],
                         env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    t0 = time.time()
    while not healthy(port):
        if p.poll() is not None or time.time() - t0 > 1800:
            raise RuntimeError(f"server failed {extra} {env_extra}")
        time.sleep(3)
    return p


def first_diff(a, b):
    if a == b:
        return None
    return next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-text", type=int, default=16)
    ap.add_argument("--n-tool", type=int, default=6)
    ap.add_argument("--configs", default="base,nopc,eager")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    port = int(os.environ.get("CLOQ_TASK_PORT", "8050"))
    gpus = os.environ["CUDA_VISIBLE_DEVICES"].split(",")
    its = items(a.n_text, a.n_tool)
    prompts = [x["prompt_token_ids"] for _, x in its]
    rec = [x["completion_token_ids"] for _, x in its]
    res = {"items": [{"key": list(k), "tool_call": bool(x.get("tool_calls")), "n_prompt": len(x["prompt_token_ids"]),
                      "n_completion": len(x["completion_token_ids"])} for k, x in its], "summary": {}, "first_diff": {}}
    cfgs = {"base": (SERVE_EXTRA, {}),
            "nopc": (SERVE_EXTRA + ["--no-enable-prefix-caching"], {}),
            "eager": (SERVE_EXTRA + ["--enforce-eager"], {}),
            "nopc_nochunk": (SERVE_EXTRA + ["--no-enable-prefix-caching", "--no-enable-chunked-prefill"], {})}
    for name in a.configs.split(","):
        extra, envx = cfgs[name]
        try:
            srv = serve(port, extra, envx)
        except Exception as e:  # noqa: BLE001
            res["summary"][name] = {"error": str(e)}
            print(name, "server error", e, flush=True)
            continue
        try:
            outs = {}
            for cond, conc in (("seq_cold", False), ("seq_warm", False), ("conc", True)):
                if conc:
                    with ThreadPoolExecutor(len(prompts)) as ex:
                        o = list(ex.map(lambda ids: complete(port, ids), prompts))
                else:
                    o = [complete(port, ids) for ids in prompts]
                outs[cond] = o
                s = {"eq_record": sum(x == r for x, r in zip(o, rec)), "eq_seq_cold": sum(x == y for x, y in zip(o, outs["seq_cold"])),
                     "eq_record_text": sum(x == r for x, r, (_, it) in zip(o, rec, its) if not it.get("tool_calls")),
                     "n": len(o), "n_text": sum(1 for _, it in its if not it.get("tool_calls"))}
                res["summary"][f"{name}/{cond}"] = s
                res["first_diff"][f"{name}/{cond}"] = [first_diff(x, r) for x, r in zip(o, rec)]
                print(f"{name}/{cond}: {s}", flush=True)
        finally:
            stop_server(srv, gpus)
        Path(a.out).write_text(json.dumps(res, indent=1))
    Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
