"""Fork development, batch 2 (2026-09-30, W35): Q blocks that plain evals can run correctly now.
  KV8 : q4/q8, BF16 weights + KV INT8 hook, on the development blocks q4, q5, f01-f17 (q3 already exists)
  TEL : telecom development split (manifests/telecom/dev_v1.json, 80 tasks; the 34 holdout tasks are NOT in it),
        q4/q8 x {BF16, GPTQ-W4 d1, AWQ-W4 d1} on blocks f01-f06
Nonces from manifests/fork/dev_blocks_v1.json. Never overwrites an existing task id. usage: python make_tasks_fork_dev2.py [--dry]
"""
import json, sys
from pathlib import Path
Q = Path("/data/ziyangs/cloq_work/queue"); ROOT = Path("/data/ziyangs/cloq")
man = json.load(open(ROOT / "manifests/fork/dev_blocks_v1.json"))
blocks = {**{k: v for k, v in man["existing_blocks"].items() if k != "q3"}, **man["new_blocks"]}
exists = lambda tid: any((Q / d / f"{tid}.json").exists() for d in ("todo", "running", "done", "failed", "deferred"))
new = []
def chunks(items, n=3): return [items[i:i + n] for i in range(0, len(items), n)]
for m in ("q4", "q8"):
    for ci, ch in enumerate(chunks(list(blocks.items()))):
        new.append({"id": f"a6k2_{m}_kvq_int8_fdev{ci+1}", "kind": "eval", "model": m, "arm": "kvq", "ckpt": {"kind": "bf16"},
                    "serve_env": {"CLOQ_PYHOOKS": "1", "CLOQ_KVQ_BITS": "8"},
                    "runs": [{"run_id": f"a6k2_{m}_kvq_int8_{b}", "task_file": "manifests/eval_tasks_v0.json", "nonce": n} for b, n in ch],
                    "priority": -7, "deps": [], "note": "fork dev batch 2: KV8 Q blocks"})
    tel = [(b, man["new_blocks"][b]) for b in ("f01", "f02", "f03", "f04", "f05", "f06")]
    for cell in ("bfpair", "gptq_w4_d1", "awq_w4"):
        src = None if cell == "bfpair" else json.load(open(Q / "done" / f"a6k2_{m}_{cell}.json"))
        for ci, ch in enumerate(chunks(tel)):
            new.append({"id": f"a6k2_{m}_tel_{cell}_fdev{ci+1}", "kind": "eval", "model": m, "domains": ["telecom"],
                        "arm": src["arm"] if src else "bf16", "ckpt": src["ckpt"] if src else {"kind": "bf16"},
                        "runs": [{"run_id": f"a6k2_{m}_tel_{cell}_{b}", "task_file": "manifests/telecom/dev_v1.json", "nonce": n} for b, n in ch],
                        "priority": -6, "deps": [d for d in (src.get("deps", []) if src else []) if "calib" in d],
                        "note": "fork dev batch 2: telecom dev blocks (holdout untouched)"})
new = [t for t in new if not exists(t["id"])]
for t in new: print(t["id"], t["priority"], len(t["runs"]))
if "--dry" not in sys.argv:
    for t in new: json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)
print(len(new), "tasks", sum(len(t["runs"]) for t in new), "runs")
