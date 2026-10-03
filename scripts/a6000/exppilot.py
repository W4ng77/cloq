"""Experiment pilot (W100r): an unattended loop (default 12 h, every 10 min) that keeps the A6000 queue working without a
session. Docs: scripts/a6000/EXPPILOT.md. Stop: touch /data/ziyangs/cloq_work/queue/EXPPILOT_STOP.

  A  phase-2 release (effect-blind): for q8 / m24, once analysis/fork/newmethod/expansion_<m>.json exists with expand = true,
     queue every missing f04-f06 panel + score task of the record's phase2_cells (q8 reference cells also get their §2.4
     gates) through the official generator of each cell family; nothing if expand is not true. Reads only the record's
     expand / phase2_cells / eligible fields and queue presence, never a panel outcome.
  B  analyses (login node, timeout 30 min, once each): analyze_newmethod.py --model <m> when its record exists and every
     panel + score task of the admitted cells is done (or T_deadline 2026-10-04 12:00 PDT passed); analyze_sameprec.py and
     analyze_sameprec_w3.py after the 2026-10-04 00:00 PDT freeze. Outputs + a ledger line are committed (explicit paths).
  C  GPU fill: if idle agent GPUs > runnable todo demand for 2 consecutive loops, release deferred tasks (exppilot_fill.py
     rules) into todo at priority -19, at most (idle - demand) GPUs per loop.
  D  health: 'starved' once per hour when nothing is runnable or releasable; a family with > 3 failures in 2 h is held.
  E  a status paragraph every 30 min.
Never: sbatch / scancel / kill, touch queue/running/, open analysis/fork/holdout/, edit frozen configs, manifests or protocols.

usage: python3 scripts/a6000/exppilot.py [--hours 12] [--dry-run] [--once]
"""
from __future__ import annotations

import argparse
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
TIER = {"m24": -30, "rot": -27, "kivi": -29, "ref": -27}  # tau2 tiers of the cell families


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
        ids = [f"nmp_{k}_{m}_{c}_{b}" for b in P2 for k in ("tau2", "score")]
        return ids + ([f"nmp_gate_same_{m}_{c}", f"nmp_gate_bank_{m}_{c}"] if m == "q8" and c in REF else [])

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
            for c in cells:
                miss = [t for t in self.expected(m, c) if t not in idx]
                if not miss:
                    continue
                cmd = self.gen_cmd(m, c, idx) + ([] if self.dry else ["--write"])
                r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600)
                if self.dry:
                    self.act(f"phase 2 {m}/{c}: {len(miss)} missing -> {' '.join(cmd[1:])} --write")
                    print("    " + (r.stdout + r.stderr).strip().replace("\n", "\n    "))
                    continue
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
        gs = F.gpu_state(live)
        cap = {n: len(v["agent"]) for n, v in gs.items()}
        idle = sum(len(v["idle"]) for v in gs.values())
        dem, _ = F.demand(idx, cap, M)
        blocked = F.failing_families()
        for fam, n in blocked.items():
            self.once_per(f"blk_{fam}", 7200, f"health: family {fam} has {n} failures within 2 h; not releasing it")
        cands, skip = F.candidates(idx, cap, M, set(blocked))
        self.st["fill_streak"] = self.st["fill_streak"] + 1 if idle > dem else 0
        self.snap = {"idle": idle, "demand": dem, "runner_nodes": len(live), "releasable": len(cands)}
        if self.dry:
            self.log(f"fill: idle agent GPUs {idle} {dict((n, v['idle']) for n, v in gs.items() if v['idle'])}, runnable demand {dem} "
                     f"GPUs; releasable deferred {[t for t, _ in cands]}; held {dict(Counter(skip.values()))}")
        if idle > dem and (self.st["fill_streak"] >= 2 or self.dry):
            budget, stamp = idle - dem, time.strftime("%F %T")
            if self.dry and self.st["fill_streak"] < 2:
                self.log(f"fill: idle {idle} > demand {dem}, streak {self.st['fill_streak']}/2; if it holds next loop:")
            for tid, t in cands:
                need = max(1, F.gpus_needed(t, M))
                if need > budget or not F.place(t, need, gs):  # only onto idle cards that can actually host it
                    continue
                desc = f"fill: release {tid} ({need} GPU, prio {t.get('priority')} -> {F.FILL_PRIORITY}); idle {idle} demand {dem}"
                if self.dry:
                    self.act(desc)
                else:
                    try:
                        F.release(tid, t, stamp)
                        self.act(desc)
                    except (OSError, FileExistsError) as e:
                        self.log(f"fill: {tid} not released: {e!r}")
                        continue
                budget -= need
        if dem == 0 and not any(v == "todo" for v in idx.values()) and not cands:
            self.once_per("starved", 3600, f"starved: nothing runnable in todo, deferred exhausted; idle GPUs {idle}")

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
    end = time.time() + a.hours * 3600
    P.log(f"exppilot start: {'dry run, ' if a.dry_run else ''}{a.hours} h, pid {os.getpid()}; stop: touch {STOP}")
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
    P.log("exppilot end")


if __name__ == "__main__":
    main()
