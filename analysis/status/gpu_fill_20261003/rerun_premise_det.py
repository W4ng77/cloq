"""W100w: does load change tokens? Read-only check of the existing determinism pairs for the arms in the F3 outage re-run.

A re-run of a timed-out episode at low load reproduces the episode load prevented only if serving is batch-invariant
(load changes latency, not tokens). For every closed-loop det pair (same config, two runs on two nodes at different
times, so different batch compositions) this compares each decision present in both runs: prompt token ids, completion
token ids and token logprobs. Reports identical counts, the longest identical prompt (chunked-prefill coverage) and the
agent server queue (vLLM engine lines) of each run.

usage: python analysis/status/gpu_fill_20261003/rerun_premise_det.py > analysis/status/gpu_fill_20261003/rerun_premise_det.json
"""
from __future__ import annotations

import json, os, re, statistics, sys

RUNS, LOGS = "/data/ziyangs/cloq/runs", "/data/ziyangs/cloq_work/logs/tasks"
LINE = re.compile(r"Running: (\d+) reqs, Waiting: (\d+) reqs")
PAIRS = {  # pair -> what it covers for the re-run arms
    "a6k2_det_q4": "dense Qwen3 BF16 path, TP=1 (pert_q4 derived ckpts, q14 gauss3 kernel class)",
    "a6k2_det_q4_fp32h": "dense Qwen3 TP=1, fp32 head",
    "a6k2_det_q30a3": "user simulator model (MoE, TP=2)",
    "a6k2_det_q30a3_x1_fp8": "MoE TP=2, FP8 GEMM",
    "a6k2_det_q4_x1_fp8": "q4 FP8 GEMM, TP=1",
    "a6k2_det_q8_x1_fp8": "q8 FP8 GEMM, TP=1",
    "a6k2_det_q14_x1_fp8": "q14 TP=1 (FP8 GEMM; same attention/norm kernels as q14 BF16)",
    "a6k2_det_q32_x1_fp8": "q32 TP=2 all-reduce (FP8 GEMM; same attention/norm/all-reduce as q32 BF16)",
    "a6k2_det_q8_x1_awq": "AWQ fp16 dequant path, TP=1",
    "a6k2_det_q14_x1_awq": "AWQ fp16 dequant path, TP=1",
    "a6k2_det_q32_x1_awq": "AWQ fp16 dequant path, TP=2",
    "a6k2_tel_det_q8": "q8 BF16 telecom (long contexts)",
    "a6k2_det_q4_kvq_int4_rot": "KV-quant pyhook (CLOQ_PYHOOKS) closed loop",
}


def load(run: str) -> dict:
    out = {}
    for d in ("retail", "airline", "telecom"):
        p = f"{RUNS}/{run}/{d}/decisions.jsonl"
        if os.path.exists(p):
            for ln in open(p):
                x = json.loads(ln)
                out[(d, x["task_id"], x["decision_idx"])] = (x["prompt_token_ids"], x["completion_token_ids"],
                                                             x.get("token_logprobs"), x.get("n_prompt_tokens") or 0)
    return out


def queue(task: str) -> dict | None:
    p = f"{LOGS}/{task}.vllm.log"
    if not os.path.exists(p):
        return None
    r, w = [], []
    for ln in open(p, errors="ignore"):
        m = LINE.search(ln)
        if m:
            r.append(int(m[1])); w.append(int(m[2]))
    return {"running_median": statistics.median(r), "running_max": max(r), "waiting_max": max(w)} if r else None


def main() -> None:
    out = {}
    for base, covers in PAIRS.items():
        a, b = f"{base}_a", f"{base}_b"
        rec = {"covers": covers, "queue_a": queue(a), "queue_b": queue(b)}
        if not os.path.isdir(f"{RUNS}/{b}"):
            rec["verdict"] = "pair incomplete (no _b run)"
            out[base] = rec
            continue
        A, B = load(a), load(b)
        common = sorted(set(A) & set(B))
        same_prompt = [k for k in common if A[k][0] == B[k][0]]
        same_tok = [k for k in same_prompt if A[k][1] == B[k][1]]
        same_lp = [k for k in same_tok if A[k][2] == B[k][2]]
        tasks = {(k[0], k[1]) for k in common}
        diverged = {(k[0], k[1]) for k in common if A[k][:3] != B[k][:3]}
        rec.update({"n_decisions_a": len(A), "n_decisions_b": len(B), "n_common": len(common),
                    "same_prompt": len(same_prompt), "same_completion": len(same_tok), "same_logprobs": len(same_lp),
                    "n_tasks": len(tasks), "tasks_diverged": len(diverged),
                    "max_prompt_tokens_identical": max((A[k][3] for k in same_lp), default=0),
                    "verdict": "bit-exact" if common and len(same_lp) == len(common) == len(A) == len(B) else "NOT bit-exact"})
        out[base] = rec
    json.dump(out, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
