"""Experiment pilot (W100r): an unattended loop (default 12 h, every 10 min) that keeps the A6000 queue working without a
session. Docs: scripts/a6000/EXPPILOT.md. Stop: touch /data/ziyangs/cloq_work/queue/EXPPILOT_STOP.

  A  phase-2 release (effect-blind): for q8 / m24, once analysis/fork/newmethod/expansion_<m>.json exists with expand = true,
     queue every missing f04-f06 panel + score task of the record's phase2_cells (q8 reference cells without new gates,
     §5.5) through the official generator of each cell family, all or none: every generator is first run without --write
     and must list every expected id. One tau2 tier for all q8 cells (§5.5: never ranked). Nothing if expand is not true.
     Reads only the record's expand / phase2_cells / eligible fields and queue presence, never a panel outcome.
  B  analyses (login node, timeout 30 min, once each): analyze_newmethod.py --model <m> when its record exists and every
     panel + score task of the admitted cells is done (or T_deadline 2026-10-04 12:00 PDT passed); analyze_sameprec.py and
     analyze_sameprec_w3.py after the 2026-10-04 00:00 PDT freeze. Outputs + a ledger line are committed (explicit paths).
  C  GPU fill: idle cards that no runnable todo task can use on their node (per-node demand, pre-W99p runners never take
     > 2-GPU tasks) for 2 consecutive loops -> release deferred tasks listed in queue/EXPPILOT_FILL_ALLOW (user OK) into todo
     at priority -19 with autopilot_retry set; unlisted ones that pass every check are only logged for approval.
  D  health: 'starved' once per hour when nothing in todo is runnable and nothing is releasable; > 3 failures in 2 h of a
     family hold it.
  E  a status paragraph every 30 min.
Never: sbatch / scancel / kill, touch queue/running/, open analysis/fork/holdout/, edit frozen configs, manifests or protocols.

The run ends after --hours (default 12, the user's request) or at --until. Scheduled duties after the end (q8 record at
T_decide 2026-10-03 20:00 PDT, SAMEPREC freeze 2026-10-04 00:00, T_deadline 2026-10-04 12:00) are logged as NOT covered
at start and at exit; they need a relaunch (e.g. --until 2026-10-04T13:00-07:00) or a human.

usage: python3 scripts/a6000/exppilot.py [--hours 12 | --until ISO] [--dry-run] [--once]
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exppilot_analysis as A  # noqa: E402
import exppilot_fill as F  # noqa: E402

ROOT, WORK, Q = F.ROOT, F.WORK, F.Q
LOG, STATE, STOP = WORK / "logs/exppilot.log", WORK / "exppilot_state.json", Q / "EXPPILOT_STOP"
NM = ROOT / "analysis/fork/newmethod"
P1, P2 = ("f01", "f02", "f03"), ("f04", "f05", "f06")
REF = ("gptq_w4_d1", "awq_w4", "kvq_int8")               # q8 reference cells (protocol §2.5)
TIER = {"m24": -30, "rot": -29, "kivi": -29, "ref": -29}  # tau2 tiers; one tier for every q8 cell (§5.5: never ranked)


def utc() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


class Pilot:
    ROOT, WORK, REF = ROOT, WORK, REF
    utc = staticmethod(utc)

    def __init__(self, dry: bool):
        self.dry, self.snap = dry, {}
        try:
            self.st = json.loads(STATE.read_text())
        except (OSError, ValueError):
            self.st = {}
        for k, v in (("phase2", {}), ("analyses", {}), ("last_log", {}), ("acts", []), ("fill_streak", 0)):
            self.st.setdefault(k, v)

    def save(self):
        if not self.dry:
            tmp = STATE.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.st, indent=1))
            os.replace(tmp, STATE)

    def log(self, msg: str):
        line = f"[{time.strftime('%F %T')}] {msg}"
        if self.dry:
            print(line)
        else:
            with open(LOG, "a") as f:
                f.write(line + "\n")

    def once_per(self, key: str, sec: float, msg: str):
        if time.time() - self.st["last_log"].get(key, 0) >= sec:
            self.st["last_log"][key] = time.time()
            self.log(msg)

    def act(self, desc: str):
        self.st["acts"].append(f"{time.strftime('%H:%M')} {desc}"[:200])
        self.log(("WOULD " if self.dry else "") + desc)

    # ------------------------------------------------------------------ A: phase-2 release
    @staticmethod
    def record(m: str) -> dict | None:
        p = NM / f"expansion_{m}.json"
        return json.loads(p.read_text()) if p.exists() else None

    @staticmethod
    def expected(m: str, c: str) -> list:
        return [f"nmp_{k}_{m}_{c}_{b}" for b in P2 for k in ("tau2", "score")]  # reference cells: no gates (§5.5)

    def gen_cmd(self, m: str, c: str, idx: dict) -> list:
        fam = "m24" if m == "m24" else "ref" if c in REF else "kivi" if c.startswith("kivi") else "rot"
        tier = TIER[fam]
        pr = [(F.load(idx[t], t) or {}).get("priority") for t in (f"nmp_score_{m}_{c}_{b}" for b in P1) if t in idx]
        st = str(int(min([p for p in pr if isinstance(p, (int, float))], default=tier)))  # the cell's score tier
        g = [sys.executable, "scripts/a6000/" + {"m24": "make_tasks_m24.py", "rot": "make_tasks_rotpanel.py",
                                                  "kivi": "make_tasks_kivi.py", "ref": "make_tasks_bank_u.py"}[fam]]
        return g + {"m24": ["panel", "--cell", c, "--phase", "2", "--priority", str(tier), "--score-priority", st],
                    "rot": ["--panel", "--phase", "2", "--cells", c, "--priority", str(tier)],
                    "kivi": ["--cells", c, "--phase", "2", "--gate-suffix", "_fx", "--priority", str(tier), "--score-priority", st],
                    "ref": ["--nmp-phase2", c, "--priority", str(tier)]}[fam]

    def phase2(self, idx: dict):
        for m in ("q8", "m24"):
            rec = self.record(m)
            if rec is None:
                self.once_per(f"p2wait_{m}", 3600, f"phase 2 {m}: no expansion record yet (expansion_sched.sh writes it)")
                continue
            cells = list(rec.get("phase2_cells") or [])
            if rec.get("expand") is not True:
                self.once_per(f"p2_{m}", 1e9, f"phase 2 {m}: record says expand={rec.get('expand')}; nothing queued (§5.5)")
                continue
            kivi_q = {"kivi_k2v2", "kivi_k4v4"} & set(cells)
            if m == "q8" and (bool(kivi_q) != ("kivi_k16v16" in cells) or not set(REF) <= set(cells)):
                self.once_per(f"p2bad_{m}", 3600, f"phase 2 {m}: REFUSED, record violates A5.3 pairing or §5.5 reference cells: {cells}")
                continue
            todo = [(c, miss) for c in cells if (miss := [t for t in self.expected(m, c) if t not in idx])]
            run = lambda c, w: subprocess.run(self.gen_cmd(m, c, idx) + w, cwd=ROOT, capture_output=True, text=True,  # noqa: E731
                                              timeout=600)
            pre = {c: run(c, []) for c, _ in todo}  # preflight without --write: all or none (§5.5, A5.3)
            bad = {}
            for c, miss in todo:
                lacks = sorted(set(miss) - set(pre[c].stdout.split()))  # the generator must list every expected id
                if pre[c].returncode or lacks:
                    bad[c] = (pre[c].stderr or pre[c].stdout).strip()[-160:] if pre[c].returncode else f"does not list {lacks}"
            if bad:
                self.once_per(f"p2pre_{m}", 3600, f"phase 2 {m}: preflight failed for {sorted(bad)}, nothing written (all or none): {bad}")
                continue
            for c, miss in todo:
                cmd = self.gen_cmd(m, c, idx) + ["--write"]
                if self.dry:
                    self.act(f"phase 2 {m}/{c}: {len(miss)} missing -> {' '.join(cmd[1:])}")
                    print("    " + (pre[c].stdout + pre[c].stderr).strip().replace("\n", "\n    "))
                    continue
                r = run(c, ["--write"])
                left = [t for t in miss if t not in F.index()]
                msg = f"phase 2 {m}/{c}: queued {len(miss) - len(left)}/{len(miss)} via {' '.join(cmd[1:4])} rc={r.returncode}"
                if len(left) == len(miss):  # generator refused or failed: retried every loop, logged once per hour
                    self.once_per(f"p2fail_{m}_{c}", 3600, f"{msg}; {(r.stderr or r.stdout).strip()[-200:]}")
                    continue
                self.act(msg + (f"; still missing {left[:3]}" if left else ""))
                self.st["phase2"][f"{m}/{c}"] = {"at": utc(), "queued": len(miss) - len(left), "missing": left}

    # ------------------------------------------------------------------ C + D: GPU fill, health
    def fill(self, idx: dict):
        M, live = F.models(), F.live_runners()
        gs, big = F.gpu_state(live), F.big_ok(live)
        cap = {n: len(v["agent"]) for n, v in gs.items()}
        per, run_ids, dep_blocked = F.demand(idx, cap, big, M)
        idle = sum(len(v["idle"]) for v in gs.values())
        # fillable = idle cards on a node that no runnable todo task can use (its runner keeps the others for that work)
        fg = {n: {"idle": list(v["idle"])} for n, v in gs.items() if v["idle"] and not per.get(n)}
        nfill = sum(len(v["idle"]) for v in fg.values())
        blocked = F.failing_families()
        for fam, n in blocked.items():
            self.once_per(f"blk_{fam}", 7200, f"health: family {fam} has {n} failures within 2 h; not releasing it")
        cands, skip = F.candidates(idx, cap, big, M, set(blocked))
        ask = sorted(t for t, why in skip.items() if why == "needs user OK")
        self.st["fill_streak"] = self.st["fill_streak"] + 1 if nfill else 0
        self.snap = {"idle": idle, "fillable": nfill, "demand_by_node": {n: d for n, d in per.items() if d},
                     "runner_nodes": len(live), "releasable": len(cands), "needs_ok": len(ask)}
        if self.dry:
            self.log(f"fill: idle agent GPUs {idle} {dict((n, v['idle']) for n, v in gs.items() if v['idle'])}; fillable "
                     f"{dict((n, v['idle']) for n, v in fg.items())}; demand by node {self.snap['demand_by_node']}; pre-W99p "
                     f"runners (no >2-GPU claims) {sorted(set(live) - big)}; releasable {[t for t, _ in cands]}; "
                     f"held {dict(Counter(skip.values()))}")
        if nfill and ask:
            self.once_per("fill_ask", 3600, f"fill: {nfill} fillable idle GPUs; deferred tasks passing every check but not "
                                             f"approved (add ids to {F.ALLOW} after the user's OK): {ask}")
        if nfill and (self.st["fill_streak"] >= 2 or self.dry):
            budget, stamp = nfill, time.strftime("%F %T")
            for tid, t in cands:
                need = max(1, F.gpus_needed(t, M))
                if need > budget or not F.place(t, need, fg, big):  # only onto fillable cards that can host it
                    continue
                desc = f"fill: release {tid} ({need} GPU, prio {t.get('priority')} -> {F.FILL_PRIORITY}); fillable {nfill}"
                if self.dry:
                    self.act(desc)
                else:
                    try:
                        F.release(tid, t, stamp)
                        self.act(desc)
                    except OSError as e:
                        self.once_per(f"rel_{tid}", 3600, f"fill: {tid} not released: {e!r}")
                        continue
                budget -= need
        if idle and not run_ids and not cands:
            outside = Counter(idx.get(d, "missing") for k in dep_blocked for d in (F.load("todo", k) or {}).get("deps") or []
                              if idx.get(d) != "done")
            self.once_per("starved", 3600, f"starved: no runnable todo task, nothing releasable; idle GPUs {idle}; "
                                           f"{len(dep_blocked)} todo tasks blocked on deps not done (dep dirs {dict(outside)})")

    # ------------------------------------------------------------------ E: status paragraph
    def summary(self, idx: dict):
        if not self.dry and time.time() - self.st.get("last_summary", 0) < 1800:
            return
        n = Counter(idx.values())
        fam = {d: Counter(F.family(t) for t, v in idx.items() if v == d).most_common(6) for d in ("running", "todo", "failed")}
        txt = lambda c: ", ".join(f"{k} {v}" for k, v in c) or "-"  # noqa: E731
        acts = self.st["acts"]
        self.log(f"STATUS todo {n['todo']} running {n['running']} done {n['done']} failed {n['failed']} deferred {n['deferred']}; "
                 f"running by family: {txt(fam['running'])}; todo: {txt(fam['todo'])}; failed: {txt(fam['failed'])}; "
                 f"GPUs {self.snap}; fill streak {self.st['fill_streak']}; phase-2 released {sorted(self.st['phase2'])}; "
                 f"analyses {({k: bool(v.get('ok')) for k, v in self.st['analyses'].items()})}; "
                 f"{len(acts)} actions since last status{': ' + ' | '.join(acts[-4:]) if acts else ''}")
        if not self.dry:
            self.st["last_summary"], self.st["acts"] = time.time(), []

    def uncovered(self, end: float) -> list:
        """Scheduled duties that fall after this run's end."""
        out = []
        if self.record("q8") is None and end < A.T_DECIDE.timestamp() + 1800:
            out.append("q8 phase-2 release if expansion_q8.json is written at T_decide 2026-10-03 20:00 PDT (15-min poll)")
        if end < A.T_FREEZE.timestamp():
            out.append("sameprec + sameprec_w3 final analyses (freeze 2026-10-04 00:00 PDT; main session owns F0)")
        pend = [m for m in ("m24", "q8") if not self.st["analyses"].get(f"newmethod_{m}", {}).get("ok")]
        if pend and end < A.T_DEADLINE.timestamp():
            out.append(f"newmethod analyses {pend} that are not due before the end, incl. the T_deadline 2026-10-04 12:00 PDT fallback")
        return out

    def cycle(self):
        for name, fn in (("phase2", self.phase2), ("fill", self.fill), ("analyses", lambda i: A.step(self, i)),
                         ("summary", self.summary)):
            try:
                fn(F.index())
            except Exception as e:  # one failing step never stops the loop
                self.once_per(f"err_{name}", 1800, f"step {name} error: {e!r} {traceback.format_exc()[-400:]}")
        self.save()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hours", type=float, default=12)
    ap.add_argument("--until", help="absolute end, ISO 8601, e.g. 2026-10-04T13:00-07:00 (overrides --hours)")
    ap.add_argument("--dry-run", action="store_true", help="print every action it would take; write nothing")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    P = Pilot(a.dry_run)
    if not a.dry_run:
        lock = open(WORK / "exppilot.lock", "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            sys.exit("another exppilot holds /data/ziyangs/cloq_work/exppilot.lock")
    end = dt.datetime.fromisoformat(a.until).timestamp() if a.until else time.time() + a.hours * 3600
    gap = P.uncovered(end)
    P.log(f"exppilot start: {'dry run, ' if a.dry_run else ''}until {time.strftime('%F %T', time.localtime(end))}, pid {os.getpid()}; "
          f"stop: touch {STOP}" + (f"; NOT covered after the end (relaunch with --until or do by hand): {gap}" if gap else ""))
    while True:
        if STOP.exists():
            P.log(f"exppilot stop: {STOP} present (remove it before restarting)")
            break
        P.cycle()
        if a.once or time.time() >= end:
            break
        for _ in range(20):  # 10 min, checking the stop file every 30 s
            if STOP.exists():
                break
            time.sleep(30)
    gap = P.uncovered(time.time())
    P.log("exppilot end" + (f"; still NOT covered (relaunch with --until or do by hand): {gap}" if gap else ""))
    P.save()


if __name__ == "__main__":
    main()
