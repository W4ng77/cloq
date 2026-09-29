"""Which numerical "flavour" did each A6000 agent server run in? (read-only over logs, queue and runs)

Mechanism under test (docs/insights/iter_1_discussion.md, Experiment round 1): with VLLM_BATCH_INVARIANT=1 the
matmul/attention kernels are fixed, but torch.compile/Inductor still *benchmarks* several reduction configs
(R0_BLOCK) for the fused residual+RMSNorm kernels at compile time and keeps the fastest. A different R0_BLOCK for a
reduction longer than the block changes the summation order, hence the bits of every forward pass. The pick is
made once per fresh compile (timing-dependent, so contention matters) and written to the node-local cache
/tmp/cloq_<job>/torchinductor_ziyangs; later servers of the same architecture on that node load it (compile ~1.5 s).

For each task this prints: node, GPUs, claim time, compile seconds (fresh > 5 s, cached otherwise), how many
fresh compiles of the same architecture started on that node within 90 s (>1 means the server's own pick is
unknown: only the last writer's pick is on disk), and the node's on-disk R0_BLOCK for that model's
hidden-size reductions (from e_bestconfig.sh output).
usage: python e_server_flavour.py   -> out/server_flavour.json
"""
import glob
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
LOGS = Path("/data/ziyangs/cloq_work/logs")
Q = Path("/data/ziyangs/cloq_work/queue")
HIDDEN = {"q30a3": 2048, "q4": 2560, "q8": 4096, "q14": 5120, "q32": 5120}

claims = {}
for f in sorted(LOGS.glob("node_node*_*.out")):
    for line in open(f, errors="ignore"):
        m = re.match(r"\[(\S+ \S+)\] (node\d+) claimed (\S+) on GPUs \[(.*?)\]", line)
        if m:
            claims[m.group(3)] = {"claimed": m.group(1), "node": m.group(2), "job": f.stem.split("_")[-1],
                                  "gpus": m.group(4).replace("'", "").replace(" ", "")}

tasks = {}
for d in ("done", "running", "todo", "failed"):
    for p in (Q / d).glob("*.json"):
        t = json.load(open(p))
        tasks[t["id"]] = {"state": d, "model": t.get("model"), "kind": t.get("kind"), "seconds": t.get("seconds"),
                          "host": t.get("host"), "runs": [r["run_id"] for r in t.get("runs", [])]}

best = defaultdict(dict)  # (node, job) -> {r0_numel: {kernel: R0_BLOCK}}
for f in glob.glob(str(HERE / "out/bestconfig_*_job*.tsv")):
    node, job = re.search(r"bestconfig_(node\d+)_job(\d+)", f).groups()
    for line in open(f):
        r0, kern, mtime, xb, rb, nw = line.rstrip("\n").split("\t")
        best[(node, job)].setdefault(int(r0), {})[kern[:9]] = int(rb)

rows = []
for tid, c in claims.items():
    t = tasks.get(tid, {})
    if t.get("kind") != "eval":
        continue
    vl = LOGS / "tasks" / f"{tid}.vllm.log"
    txt = open(vl, errors="ignore").read() if vl.exists() else ""
    m = re.search(r"Compiling a graph for compile range \(1, 2048\) takes ([0-9.]+) s", txt)
    comp = float(m.group(1)) if m else None
    rows.append({"task": tid, "model": t["model"], "state": t["state"], "node": c["node"], "job": c["job"],
                 "gpus": c["gpus"], "claimed": c["claimed"], "compile_s": comp,
                 "fresh": (comp is not None and comp > 5), "runs": t["runs"], "seconds": t.get("seconds")})

ts = lambda r: datetime.strptime(r["claimed"], "%Y-%m-%d %H:%M:%S")
for r in rows:
    same = [o for o in rows if o["node"] == r["node"] and o["job"] == r["job"] and o["model"] == r["model"]
            and o["fresh"] and abs((ts(o) - ts(r)).total_seconds()) <= 90]
    r["concurrent_fresh_same_arch"] = len(same) if r["fresh"] else 0
    r["node_disk_R0_BLOCK"] = best.get((r["node"], r["job"]), {}).get(HIDDEN[r["model"]])
    if r["compile_s"] is None:
        r["flavour_status"] = "not started / no log"
    elif not r["fresh"]:
        r["flavour_status"] = "inherited node cache"
    elif r["concurrent_fresh_same_arch"] == 1:
        r["flavour_status"] = "own pick = node cache"
    else:
        r["flavour_status"] = "own pick, unknown (concurrent fresh compiles)"

rows.sort(key=lambda r: (r["model"], r["task"]))
(HERE / "out").mkdir(exist_ok=True)
(HERE / "out/server_flavour.json").write_text(json.dumps(rows, indent=1))
for r in rows:
    print(f"{r['task']:18s} {r['state']:8s} {r['node']} g{r['gpus']:5s} {r['claimed'][11:]} "
          f"compile={r['compile_s']} conc_fresh={r['concurrent_fresh_same_arch']} "
          f"disk={r['node_disk_R0_BLOCK']} -> {r['flavour_status']}")
