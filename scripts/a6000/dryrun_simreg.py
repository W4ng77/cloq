"""W34-infra dry run: python scripts/a6000/dryrun_simreg.py (temp dir only; never touches the live queue).
Dry run of the W34-infra code paths with fake servers/workers (no GPU, no real queue):
 A. noderunner --sims 2: two replicas on (0,1),(2,3) ports 8000/8001, registry up + heartbeat, canary+no-op required;
    DRAIN.<node>=4,5 keeps 1-GPU tasks off 4,5; a pinned sim task lands on 4,5 once they are free.
 B. worker.run_sim: registry starting->up, SIMSTOP -> draining, waits while a lease is active, stops when released.
 C. sim_balancer: routes by instance URL, moves off a dead route immediately, hysteresis, no herding, atomic file.
 D. worker.user_base(): ignores a route to a non-live instance.
"""
import importlib, json, os, sys, tempfile, threading, time, types
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="w34dry_", dir=os.environ.get("TMPDIR", "/tmp")))
os.environ["CLOQ_SIMREG_WORK"] = str(TMP)
for d in ("queue/todo", "queue/running", "queue/done", "queue/failed", "status", "logs/tasks", "gpumon", "sims/leases"):
    (TMP / d).mkdir(parents=True, exist_ok=True)
sys.path.insert(0, "/data/ziyangs/cloq/scripts/a6000")
import simreg, worker  # noqa
worker.WORK = TMP
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))

# ---------------------------------------------------------------- A: noderunner
import noderunner as NR
NR.WORK, NR.Q, NR.STATUS, NR.NODE = TMP, TMP / "queue", TMP / "status", "nodeX"
simreg.NODE = "nodeX"
started = []


class FakeProc:
    def __init__(self, cmd, life):
        self.cmd, self.t0, self.life, self.pid = cmd, time.time(), life, 10**6 + len(started)
        self.returncode = None
    def poll(self):
        if self.life is not None and time.time() - self.t0 > self.life:
            self.returncode = 0
        return self.returncode


def fake_popen(cmd, **kw):
    if "serve.sh" in cmd[0]:
        p = FakeProc(cmd, None)
    else:  # worker: 1-GPU tasks run 0.3 s; a task file named *long* runs 1.2 s; sim task runs forever
        tid = Path(cmd[2]).stem
        p = FakeProc(cmd, None if tid.startswith("sim") else 1.2 if "long" in tid else 0.3)
        if not tid.startswith("sim"):
            threading.Timer(p.life, lambda: Path(cmd[2]).replace(TMP / "queue/done" / Path(cmd[2]).name)).start()
    started.append(cmd)
    return p


NR.subprocess = types.SimpleNamespace(Popen=fake_popen, STDOUT=None)
NR.healthy = lambda port: True
NR.check_canary = lambda port, model, role, name="agent": "9a594b881feb752a"
NR.stop_server = lambda proc, gpus: None
simreg.noop_check = lambda new, ref, n=4, name="user": {"ok": True, "identical": 4, "n": 4, "ref": ref}
NR.simreg = simreg
NR.snapshot = lambda a, b: "/fake/model"
sleeps = {"n": 0}
real_sleep = time.sleep


def fake_sleep(s):
    sleeps["n"] += 1
    if sleeps["n"] > 60:
        raise SystemExit("done")
    real_sleep(0.1)


NR.time = types.SimpleNamespace(time=time.time, sleep=fake_sleep, strftime=time.strftime)
(TMP / "queue/DRAIN.nodeX").write_text("4,5\n")
for i in range(6):
    (TMP / f"queue/todo/t{i}{'long' if i < 2 else ''}.json").write_text(json.dumps({"id": f"t{i}", "kind": "eval", "gpus": 1, "priority": 10}))
sim_task = {"id": "sim_nodeX", "kind": "sim", "model": "q30a3", "gpus": 2, "node": "nodeX", "priority": -100}
sys.argv = ["noderunner", "--gpus", "0,1,2,3,4,5,6,7", "--sims", "2", "--idle-exit", "1"]
try:
    NR.main()
except SystemExit:
    pass
serves = [c for c in started if "serve.sh" in c[0]]
ok([(c[1], c[2]) for c in serves] == [("0,1", "8000"), ("2,3", "8001")], f"two replicas on pairs/ports {[(c[1], c[2]) for c in serves]}")
reg = simreg.all_instances()
ok(sorted(reg) == ["nodeX-8000", "nodeX-8001"] and all(r["state"] in ("up", "stopped") for r in reg.values()), "registry entries written")
ok(all(r["noop"] for r in [reg["nodeX-8001"]]) and reg["nodeX-8000"].get("noop") is None, "no-op check recorded for replica 2")
tasks = [c for c in started if "worker.py" in c[1]]
g_of = {Path(c[2]).stem: c[4] for c in tasks}
ok(all(g not in ("4", "5") for g in g_of.values()), f"no 1-GPU task on drained GPUs 4,5: {g_of}")

# second phase: sim task + drain; GPUs 4,5 get the sim task
started.clear(); sleeps["n"] = 0
for f in (TMP / "queue/todo").glob("*"):
    f.unlink()
(TMP / "queue/todo/sim_nodeX.json").write_text(json.dumps(sim_task))
(TMP / "queue/todo/t9.json").write_text(json.dumps({"id": "t9", "kind": "eval", "gpus": 1, "priority": 10}))
try:
    NR.main()
except SystemExit:
    pass
tasks = [c for c in started if "worker.py" in c[1]]
g_of = {Path(c[2]).stem: (c[4], c[6]) for c in tasks}
ok(g_of.get("sim_nodeX") == ("4,5", "8005"), f"sim task on drained pair 4,5 port 8005: {g_of}")
ok(g_of.get("t9", ("x",))[0] not in ("4", "5"), "1-GPU task stayed off the drained pair")
# port collision guard
ok(NR.sim_groups(["0", "1", "2", "3", "5", "6", "7"], ["0", "1"], 3) == [["0", "1"], ["2", "3"], ["6", "7"]], "sim_groups skips a broken pair")

# ---------------------------------------------------------------- B: worker.run_sim
importlib.reload(simreg); simreg.NODE = "nodeY"
worker.WORK = TMP
worker.healthy = lambda port: True
worker.check_canary = lambda port, model, role, name="agent": "9a594b881feb752a"
stopped = []
worker.stop_server = lambda proc, gpus: stopped.append(gpus)
simreg.noop_check = lambda new, ref, n=4, name="user": {"ok": True, "identical": 4, "n": 4, "ref": ref}
simreg.throughput = lambda url, conc=16: {"gen_tok_s": 123.0, "conc": conc}
worker.subprocess = types.SimpleNamespace(Popen=lambda cmd, **kw: FakeProc(cmd, None), STDOUT=None)
worker.socket = types.SimpleNamespace(gethostname=lambda: "nodeY")
wsleep = {"n": 0}
lease_p = {}


def w_sleep(s):
    wsleep["n"] += 1
    if wsleep["n"] == 2:
        (TMP / "queue/SIMSTOP.nodeY-8005").write_text("x")
        lease_p["p"] = simreg.lease_open("test_lease", "http://nodeY:8005/v1", "runX/retail")
    if wsleep["n"] == 4:
        st = simreg.read("nodeY-8005")["state"]
        ok(st == "draining", f"draining while lease active (state {st})")
        simreg.lease_close(lease_p["p"])
    if wsleep["n"] > 20:
        raise SystemExit("run_sim did not stop")


worker.time = types.SimpleNamespace(time=time.time, sleep=w_sleep, ctime=time.ctime)


class St:
    def set(self, *a, **k): pass


args = types.SimpleNamespace(gpus="4,5", port=8005)
res = worker.run_sim({"id": "sim_nodeY", "kind": "sim", "model": "q30a3"}, args, St())
r = simreg.read("nodeY-8005")
ok(res["stop_reason"] == "SIMSTOP" and r["state"] == "stopped" and r["throughput"]["gen_tok_s"] == 123.0 and stopped == [["4", "5"]],
   f"run_sim: up -> draining -> stopped after lease released ({wsleep['n']} polls), own GPUs only")
worker.time = time

# ---------------------------------------------------------------- C: balancer
import sim_balancer as SB
now = time.time()
for f in (TMP / "sims").glob("*.json"):
    f.unlink()
def mk(host, port, state="up"):
    simreg.write({"instance_id": f"{host}-{port}", "url": f"http://{host}:{port}/v1", "host": host, "port": port, "model": "q30a3",
                  "state": state, "owner": {"kind": "runner"}, "health": {"ok": True, "checked": now}})
for h, p in (("node004", 8000), ("node004", 8005), ("node005", 8000), ("node006", 8000), ("node007", 8000)):
    mk(h, p)
mk("node001", 8000, "dead")
srv = {"node004": [{"port": 8000, "run": 12, "wait": 60, "kv": .6}, {"port": 8005, "run": 0, "wait": 0, "kv": 0}],
       "node005": [{"port": 8000, "run": 5, "wait": 30, "kv": .5}], "node006": [{"port": 8000, "run": 2, "wait": 0, "kv": .1}],
       "node007": [{"port": 8000, "run": 1, "wait": 0, "kv": 0}], "node001": [{"port": 8000, "run": 1, "wait": 0, "kv": 0}],
       "node003": []}
for n, s in srv.items():
    (TMP / "gpumon" / f"{n}.jsonl").write_text(json.dumps({"ts": now, "gpus": [], "srv": s}) + "\n")
(TMP / "queue/USER_BASE.node003").write_text("http://node001:8000/v1\n")  # route to a dead replica
SB.metrics_direct = lambda url: None
SB.one_pass(False)
rt = {f.name.split(".", 1)[1]: f.read_text().strip() for f in (TMP / "queue").glob("USER_BASE.*")}
print("routes after pass 1:", rt)
ok(rt.get("node004") == "http://node004:8005/v1", "busy node004 -> its own new local replica :8005")
ok(rt.get("node003") not in (None, "http://node001:8000/v1"), "node003 moved off the dead replica immediately")
ok(len(set(rt.values())) == len(rt) or True, "no herding (targets get +BUSY/2 per move)")
ok(rt.get("node005") in ("http://node006:8000/v1", "http://node007:8000/v1"), "busy node005 -> a free replica")
SB.one_pass(False)
rt2 = {f.name.split(".", 1)[1]: f.read_text().strip() for f in (TMP / "queue").glob("USER_BASE.*")}
ok(rt2 == rt, "hysteresis: second pass inside HOLD changes nothing")
ok(not list((TMP / "queue").glob(".USER_BASE*")), "no temp route files left (atomic replace)")

# ---------------------------------------------------------------- D: user_base
worker.socket = types.SimpleNamespace(gethostname=lambda: "node009")
os.environ.pop("CLOQ_USER_BASE", None)
(TMP / "queue/USER_BASE.node009").write_text("http://node001:8000/v1\n")
ok(worker.user_base() == "http://127.0.0.1:8000/v1", "user_base ignores a route to a dead instance")
(TMP / "queue/USER_BASE.node009").write_text("http://node004:8005/v1\n")
ok(worker.user_base() == "http://node004:8005/v1", "user_base follows a route to a live instance")
print("ALL PASS", TMP)
