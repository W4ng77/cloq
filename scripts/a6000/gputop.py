"""nvitop-like cluster view from the per-node samplers (scripts/a6000/gpumon.sh).
usage: python scripts/a6000/gputop.py [--hist MIN]   # latest sample per node (+ averages over the last MIN minutes)
Shows per GPU: util %, power W, memory GB, the task on it (from status/), and per vLLM server: running/waiting
requests, KV-cache %, prompt/generation tokens per second over the window. Port 8000 is the user simulator.
"""
import argparse
import glob
import json
import os
import time

W = "/data/ziyangs/cloq_work"


def load(node, since):
    rows = []
    with open(f"{W}/gpumon/{node}.jsonl") as f:
        for ln in f:
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r["ts"] >= since:
                rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hist", type=float, default=10)
    a = ap.parse_args()
    now = time.time()
    status = {}
    for f in glob.glob(f"{W}/status/node*-g*.json"):
        s = json.load(open(f))
        status[os.path.basename(f)[:-5]] = s
    tot = {"gpus": 0, "pw": 0.0, "gen": 0.0, "simwait": 0}
    for p in sorted(glob.glob(f"{W}/gpumon/node*.jsonl")):
        node = os.path.basename(p)[:-6]
        rows = load(node, now - a.hist * 60)
        if not rows:
            print(f"{node}: no samples in the last {a.hist:.0f} min")
            continue
        last, first = rows[-1], rows[0]
        dt = max(1, last["ts"] - first["ts"])
        print(f"== {node}  ({len(rows)} samples, {time.strftime('%H:%M:%S', time.localtime(last['ts']))})")
        for g in last["gpus"]:
            avg_pw = sum(x["pw"] for r in rows for x in r["gpus"] if x["i"] == g["i"]) / len(rows)
            avg_ut = sum(x["util"] for r in rows for x in r["gpus"] if x["i"] == g["i"]) / len(rows)
            st = status.get(f"{node}-g{g['i']}", {})
            task = (st.get("task") or "")[:34]
            print(f"  g{g['i']} util {g['util']:3.0f}% (avg {avg_ut:3.0f})  {g['pw']:5.0f} W (avg {avg_pw:5.0f})  "
                  f"{g['mem']/1024:4.1f} GB  {st.get('state','?'):8s} {task}")
            tot["gpus"] += 1
            tot["pw"] += avg_pw
        f0 = {s["port"]: s for s in first["srv"]}
        for s in last["srv"]:
            s0 = f0.get(s["port"], s)
            gen = (s["gtok"] - s0["gtok"]) / dt
            pre = (s["ptok"] - s0["ptok"]) / dt
            role = "SIM " if s["port"] == 8000 else "agent"
            print(f"  :{s['port']} {role} run {s['run']:3.0f} wait {s['wait']:3.0f}  kv {100*s['kv']:3.0f}%  "
                  f"gen {gen:6.0f} tok/s  prefill {pre:7.0f} tok/s")
            tot["gen"] += gen
            if s["port"] == 8000:
                tot["simwait"] += s["wait"]
    print(f"== cluster: {tot['gpus']} GPUs, mean power {tot['pw']/max(1,tot['gpus']):.0f} W, "
          f"generation {tot['gen']:.0f} tok/s, simulator requests waiting {tot['simwait']:.0f}")


if __name__ == "__main__":
    main()
