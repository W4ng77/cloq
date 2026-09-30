"""nvitop-like cluster view from the per-node samplers (scripts/a6000/gpumon.sh).
usage: python scripts/a6000/gputop.py [--hist MIN]   # latest sample per node (+ averages over the last MIN minutes)
Shows per GPU: util %, power W, memory GB, the task on it (from status/), and per vLLM server: running/waiting
requests, KV-cache %, prompt/generation tokens per second over the window. User-simulator replicas are the ports in the
instance registry (cloq_work/sims/<node>-<port>.json, scripts/a6000/simreg.py; port 8000 if unregistered), shown with
their registry state. A summary line per replica closes the view.
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
    reg = {}
    for f in glob.glob(f"{W}/sims/node*.json"):
        try:
            r = json.load(open(f))
            reg[(r["host"], int(r["port"]))] = r
        except Exception:
            pass
    simrows = []
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
        # token counters restart from 0 when a server restarts: sum the non-negative increments per port
        inc = {}
        for r0, r1 in zip(rows, rows[1:]):
            prev = {x["port"]: x for x in r0["srv"]}
            for x in r1["srv"]:
                if x["port"] in prev:
                    g, q = inc.get(x["port"], (0.0, 0.0))
                    inc[x["port"]] = (g + max(0, x["gtok"] - prev[x["port"]]["gtok"]),
                                      q + max(0, x["ptok"] - prev[x["port"]]["ptok"]))
        for s in last["srv"]:
            gen, pre = (v / dt for v in inc.get(s["port"], (0.0, 0.0)))
            r = reg.get((node, s["port"]))
            is_sim = r is not None or s.get("sim") or (s["port"] == 8000 and not any(k[0] == node for k in reg))
            role = f"SIM[{r.get('state', '?')}]" if r else ("SIM " if is_sim else "agent")
            print(f"  :{s['port']} {role} run {s['run']:3.0f} wait {s['wait']:3.0f}  kv {100*s['kv']:3.0f}%  "
                  f"gen {gen:6.0f} tok/s  prefill {pre:7.0f} tok/s")
            tot["gen"] += gen
            if is_sim:
                tot["simwait"] += s["wait"]
                simrows.append((f"{node}-{s['port']}", r.get("state", "unregistered") if r else "unregistered", s, gen))
    for iid, state, s, gen in simrows:
        print(f"   sim {iid:14s} {state:12s} run {s['run']:3.0f} wait {s['wait']:3.0f} kv {100*s['kv']:3.0f}% gen {gen:5.0f} tok/s")
    print(f"== cluster: {len(simrows)} simulator replicas, {tot['gpus']} GPUs, mean power {tot['pw']/max(1,tot['gpus']):.0f} W, "
          f"generation {tot['gen']:.0f} tok/s, simulator requests waiting {tot['simwait']:.0f}")


if __name__ == "__main__":
    main()
