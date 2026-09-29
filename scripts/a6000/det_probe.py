"""Which serving factor breaks cross-node determinism? Replay recorded agent prompts under controlled conditions.

Takes decision records where two BF16 runs of the same config (det_<m>_a on one node, det_<m>_b on another) saw a
byte-identical prompt but produced different completions, plus some where they agreed, and replays each prompt on a
fresh server on this GPU under several conditions:
  seq_cold   one request at a time, fresh server (shared system/tool prefix gets cached after the first)
  seq_warm   the same again (every prefix now cached)
  conc       all prompts at once (batching + chunked-prefill interleaving)
  nopc_seq / nopc_conc   the same with --no-enable-prefix-caching
  eager_conc --enforce-eager (no CUDA graphs / torch.compile)
Reports, per condition, how many completions equal the node-A record, the node-B record, and seq_cold.

usage (inside a cmd task, CUDA_VISIBLE_DEVICES and CLOQ_TASK_PORT set):
  python scripts/a6000/det_probe.py --model q4 --run-a a6000_det_q4_a --run-b a6000_det_q4_b --out analysis/determinism/probe_q4.json
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
sys.path.insert(0, str(ROOT / "scripts/a6000"))
from worker import MODELS, healthy, snapshot, stop_server  # noqa: E402

FROZEN = json.load(open(ROOT / "configs/frozen_v0.json"))


def load(run: str) -> dict:
    out = {}
    for d in ("retail", "airline"):
        p = ROOT / "runs" / run / d / "decisions.jsonl"
        for line in open(p):
            x = json.loads(line)
            out[(d, x["task_id"], x["decision_idx"])] = x
    return out


def pick(A: dict, B: dict, n_div: int, n_same: int):
    div, same = [], []
    for k in sorted(set(A) & set(B)):
        a, b = A[k], B[k]
        if a["prompt_token_ids"] != b["prompt_token_ids"]:
            continue
        if a["completion_token_ids"] != b["completion_token_ids"]:
            if len(div) < n_div and not any(x[0][:2] == k[:2] for x in div):  # first divergence per task
                div.append((k, a, b))
        elif len(same) < n_same and k[2] > 0:
            same.append((k, a, b))
    return div + same


def complete(port: int, ids: list[int]) -> list[int]:
    g = FROZEN["generation_agent"]
    body = {"model": "agent", "prompt": ids, "max_tokens": int(g["max_tokens"]), "temperature": g["temperature"],
            "top_p": g["top_p"], "top_k": g["top_k"], "seed": g["seed"], "repetition_penalty": g["repetition_penalty"],
            "presence_penalty": g["presence_penalty"], "frequency_penalty": g["frequency_penalty"],
            "return_token_ids": True}
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        c = json.load(r)["choices"][0]
    return c.get("token_ids") or (c.get("provider_specific_fields") or {}).get("token_ids")


def serve(model: str, port: int, extra: list[str]):
    m = MODELS[model]
    env = dict(os.environ, CLOQ_TOOL_PARSER=m["parser"])
    gpus = os.environ["CUDA_VISIBLE_DEVICES"]
    p = subprocess.Popen([str(ROOT / "scripts/a6000/serve.sh"), gpus, str(port), snapshot(m["hf_id"], m["revision"]),
                          "agent", "33792", *extra], env=env, stdout=open(os.devnull, "w"), stderr=subprocess.STDOUT,
                         start_new_session=True)
    t0 = time.time()
    while not healthy(port):
        if p.poll() is not None or time.time() - t0 > 1200:
            raise RuntimeError("server failed")
        time.sleep(3)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="q4")
    ap.add_argument("--run-a", required=True)
    ap.add_argument("--run-b", required=True)
    ap.add_argument("--n-div", type=int, default=20)
    ap.add_argument("--n-same", type=int, default=10)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    port = int(os.environ.get("CLOQ_TASK_PORT", "8050"))
    gpus = os.environ["CUDA_VISIBLE_DEVICES"].split(",")
    items = pick(load(a.run_a), load(a.run_b), a.n_div, a.n_same)
    prompts = [x[1]["prompt_token_ids"] for x in items]
    res = {"items": [{"key": list(k), "diverged": ra["completion_token_ids"] != rb["completion_token_ids"],
                      "n_prompt": len(ra["prompt_token_ids"])} for k, ra, rb in items], "conditions": {}}

    def run_cond(name, conc):
        if conc:
            with ThreadPoolExecutor(len(prompts)) as ex:
                outs = list(ex.map(lambda ids: complete(port, ids), prompts))
        else:
            outs = [complete(port, ids) for ids in prompts]
        res["conditions"][name] = outs
        eqA = sum(o == x[1]["completion_token_ids"] for o, x in zip(outs, items))
        eqB = sum(o == x[2]["completion_token_ids"] for o, x in zip(outs, items))
        base = res["conditions"].get("seq_cold")
        eqC = sum(o == b for o, b in zip(outs, base)) if base else None
        print(f"{name:12s} = A {eqA}/{len(items)}  = B {eqB}/{len(items)}  = seq_cold {eqC}", flush=True)
        res.setdefault("summary", {})[name] = {"eq_a": eqA, "eq_b": eqB, "eq_seq_cold": eqC, "n": len(items)}

    for extra, conds in (([], [("seq_cold", False), ("seq_warm", False), ("conc", True)]),
                         (["--no-enable-prefix-caching"], [("nopc_seq", False), ("nopc_conc", True)]),
                         (["--enforce-eager"], [("eager_seq", False), ("eager_conc", True)])):
        srv = serve(a.model, port, extra)
        try:
            for name, conc in conds:
                run_cond(name, conc)
        finally:
            stop_server(srv, gpus)
    res.pop("conditions")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
