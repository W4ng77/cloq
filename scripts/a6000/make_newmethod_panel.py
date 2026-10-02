"""New-method common panels (docs/insights/NEWMETHOD_PANEL_PROTOCOL.md, W99v). CPU only; never queues anything.

Subcommands
  build      write the frozen panel manifest (refuses to overwrite):
               panel A (tau2): one ordinary state per task x block on the BF16 trajectory a6k2_<model>_bfpair_<blk>
                 (Bank U sub-bank U2B rule, FORK_PROTOCOL §15 amendment 1), blocks f01-f06 (phase 1 = f01-f03,
                 phase 2 = f04-f06), retail/airline 85-task split pool (manifests/fork/splits_v1.json dev).
                 t = floor(u * n_decisions), u = int(sha256("bank-u-v1|" + run + "|" + domain + "|" + task)[:12], 16) / 16**12;
                 state_key = sha256("U2B|" + run + "|" + domain + "|" + task)[:16]. Rows are in the Bank U row schema, so
                 fork_driver mode bank_u (subs ["U2B"]) runs them unchanged. For q8 f01-f03 the rows are asserted
                 identical to the U2B rows of manifests/fork/bank_u_v1.json (same states as the Bank U reference cells).
               panel B (BFCL multi-turn): 50 ids per category (200), pool = bfcl_mt_v1 eval ids minus every id used by
                 an adapter-development, smoke or gate sample (bfcl_mt_v1 dev+smoke, bfcl_mt_l8gate_v1 smoke_l8g,
                 bfcl_mt_l8probe_v1 probe_l8, and every BFCL id appearing in analysis/fork/{ext/gate,ext_q14_gate,
                 ext_l8_gate}/), ordered by sha256("cloq-nmp-bfcl-v1:" + id). Stored as top-level "categories"
                 {cat: {"test_category", "nmp_v1": [...]}} so scripts/ext/bfcl_run.py reads it as a task_file with
                 subset "nmp_v1".
             Reads only message structure, decision counts and termination reasons of the BF16 source episodes (as
             make_bank_u.py); never a reward, a branch outcome or any fork output.
             --model q8 (default) -> manifests/fork/newmethod_panel_v1.json
             --model <m> --source-template 'a6k2_<m>_bfpair_{blk}' -> manifests/fork/newmethod_panel_v1_<m>.json
               (second-family use, e.g. Mistral: same rules, same BFCL ids; built only after its six BF16 blocks
               are admitted in a snapshot).
  expansion  the phase-2 decision (protocol §5). Reads ONLY queue status and the throughput fields of phase-1
             bank_summary.json files (seconds, n_rows, n_ok, n_errors, n_missing, gate flags) and the task's "gpus";
             it refuses to open bank_rows.jsonl or branches/. Writes analysis/fork/newmethod/expansion_<model>.json once.
  spec       print the fork specs (bank_u / gate_same / bank_u gate / score / BFCL eval + fork_ext dev) for one cell, for
             the method agents to wrap in their own queue tasks (Q role = theirs). Writes nothing.

usage:
  python scripts/a6000/make_newmethod_panel.py build [--model q8] [--snapshot S] [--source-template T]
  python scripts/a6000/make_newmethod_panel.py expansion --model q8 --cells quarot_w4 quarot_w16 ... [--now ISO] [--write]
  python scripts/a6000/make_newmethod_panel.py spec --model q8 --cell quarot_w4 [--phase 1]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
sys.path.insert(0, str(ROOT))

VERSION = "newmethod_panel_v1"
PROTOCOL = "docs/insights/NEWMETHOD_PANEL_PROTOCOL.md"
DEF_SNAPSHOT = "analysis/insights/iter_3/out/snapshot_auto_20261002T0631Z.json"
BLOCKS = ("f01", "f02", "f03", "f04", "f05", "f06")
PHASE = {"f01": 1, "f02": 1, "f03": 1, "f04": 2, "f05": 2, "f06": 2}
DOMS = ("retail", "airline")
BFCL_SRC = "manifests/bfcl/bfcl_mt_v1.json"
BFCL_L8GATE = "manifests/bfcl/bfcl_mt_l8gate_v1.json"
BFCL_L8PROBE = "manifests/bfcl/bfcl_mt_l8probe_v1.json"
BFCL_GATE_DIRS = ("analysis/fork/ext/gate", "analysis/fork/ext_q14_gate", "analysis/fork/ext_l8_gate")
BFCL_SALT = "cloq-nmp-bfcl-v1"
BFCL_PER_CAT = 50
BFCL_SUBSET = "nmp_v1"
ID_RE = re.compile(r"multi_turn_(?:base|miss_param|miss_func|long_context)_\d+")
OUTDIR = "analysis/fork/newmethod"
# Expansion rule constants (protocol §5): fixed before any panel task ran.
T_DECIDE = {"q8": "2026-10-03T20:00:00-07:00", "default": "2026-10-04T00:00:00-07:00"}
T_DEADLINE = "2026-10-04T12:00:00-07:00"
G_PANEL = 8          # GPUs assumed available to the panel's phase-2 tasks (4 concurrent 2-GPU q8 fork tasks)
SAFETY = 1.25        # multiplier on the measured phase-1 GPU-hours
REF_CELLS = {"q8": ("gptq_w4_d1", "awq_w4", "kvq_int8")}
QUEUE = Path("/data/ziyangs/cloq_work/queue")


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def u01(s: str) -> float:
    return int(hashlib.sha256(s.encode()).hexdigest()[:12], 16) / 16 ** 12


# ---------------------------------------------------------------------------- panel A (tau2)
def tau2_rows(model: str, template: str, snap: dict) -> tuple[list[dict], dict]:
    from cloq import fork as F

    split = json.load(open(ROOT / "manifests/fork/splits_v1.json"))
    tasks = {d: [str(t) for t in split["splits"]["dev"]["tasks"][d]] for d in DOMS}
    rows, sources = [], {}
    for blk in BLOCKS:
        run = template.format(blk=blk)
        for dom in DOMS:
            fr = (snap["frozen"].get(run) or {}).get(dom)
            b = None
            if fr is not None:
                b = F.Block(ROOT, run, dom)
                d = ROOT / "runs" / run / dom
                sources[f"{run}|{dom}"] = {"trajectory_sha256": sha_file(d / "trajectory.jsonl"),
                                           "decisions_sha256": sha_file(d / "decisions.jsonl"), "nonce": b.nonce,
                                           "snapshot_n_tasks": fr.get("n_tasks"), "snapshot_infra_missing": fr.get("infra_missing")}
            for tid in tasks[dom]:
                key = f"U2B|{run}|{dom}|{tid}"
                row = {"state_key": hashlib.sha256(key.encode()).hexdigest()[:16], "sub": "U2B", "model": model, "cell": None,
                       "source_run": run, "block": blk, "phase": PHASE[blk], "domain": dom, "task_id": tid, "t": None,
                       "n_decisions": None, "selection_probability": None, "q0": False, "missing_reason": None}
                if b is None:
                    row["missing_reason"] = "source run not admitted in snapshot"
                else:
                    tr = b.traj.get(tid)
                    if tr is None:
                        row["missing_reason"] = "task not in source trajectory"
                    elif tr["termination_reason"] not in ("user_stop", "agent_stop", "max_steps", "too_many_errors"):
                        row["missing_reason"] = f"source episode termination {tr['termination_reason']}"
                    else:
                        pos = F.agent_positions(tr["messages"], F.prefix_len(tr["task"]))
                        if len(pos) != len(b.dec.get(tid, [])) or not pos:
                            row["missing_reason"] = "decision/trajectory count mismatch"
                        else:
                            n = len(pos)
                            row.update(n_decisions=n, t=int(u01(f"bank-u-v1|{run}|{dom}|{tid}") * n), selection_probability=1.0 / n)
                rows.append(row)
    return rows, sources


def check_against_bank_u(rows: list[dict], model: str) -> dict:
    """q8 f01-f03: every panel row must equal the Bank U U2B row of the same state (state_key, t, n_decisions, source)."""
    bu = json.load(open(ROOT / "manifests/fork/bank_u_v1.json"))
    ref = {r["state_key"]: r for r in bu["rows"] if r["sub"] == "U2B" and r["model"] == model}
    n = 0
    for r in rows:
        if r["block"] in bu["blocks"]:
            x = ref[r["state_key"]]
            for k in ("source_run", "block", "domain", "task_id", "t", "n_decisions", "missing_reason"):
                assert x[k] == r[k], (r["state_key"], k, x[k], r[k])
            n += 1
    return {"bank_u_manifest": "manifests/fork/bank_u_v1.json", "bank_u_manifest_sha256": sha_file(ROOT / "manifests/fork/bank_u_v1.json"),
            "n_rows_checked_identical": n}


# ---------------------------------------------------------------------------- panel B (BFCL)
def bfcl_panel() -> dict:
    src = json.load(open(ROOT / BFCL_SRC))
    l8g = json.load(open(ROOT / BFCL_L8GATE))
    l8p = json.load(open(ROOT / BFCL_L8PROBE))
    excl: dict[str, set] = {"bfcl_mt_v1 dev": set(), "bfcl_mt_v1 smoke (q4 gate)": set(), "l8 smoke_l8g (l8 gate)": set(),
                            "l8 probe_l8": set(), "ids in gate directories": set()}
    for cat, c in src["categories"].items():
        excl["bfcl_mt_v1 dev"] |= set(c["dev"])
        excl["bfcl_mt_v1 smoke (q4 gate)"] |= set(c["smoke"])
        excl["l8 smoke_l8g (l8 gate)"] |= set(l8g["categories"][cat]["smoke_l8g"])
        excl["l8 probe_l8"] |= set(l8p["categories"][cat]["probe_l8"])
    for g in BFCL_GATE_DIRS:
        for dp, _, fn in os.walk(ROOT / g):
            for f in fn:
                excl["ids in gate directories"] |= set(ID_RE.findall(open(os.path.join(dp, f), errors="ignore").read()))
    allx = set().union(*excl.values())
    cats = {}
    for cat, c in src["categories"].items():
        pool = [i for i in c["eval"] if i not in allx]
        order = sorted(pool, key=lambda i: hashlib.sha256(f"{BFCL_SALT}:{i}".encode()).hexdigest())
        assert len(order) >= BFCL_PER_CAT, (cat, len(order))
        cats[cat] = {"test_category": c["test_category"], "n_total": c["n_total"], "n_eval": len(c["eval"]),
                     "n_excluded_from_eval": len(c["eval"]) - len(pool), "n_pool": len(pool), BFCL_SUBSET: order[:BFCL_PER_CAT]}
        assert not set(cats[cat][BFCL_SUBSET]) & allx
    meta = {k: v for k, v in src.items() if k not in ("manifest", "selection", "categories", "frozen_before_model_runs")}
    return {"bfcl_meta": meta, "categories": cats,
            "bfcl_selection": {"rule": f"per category: bfcl_mt_v1 eval ids minus the exclusion set, sorted by sha256('{BFCL_SALT}:' + id); "
                                       f"{BFCL_SUBSET} = first {BFCL_PER_CAT}. Ids only; no model outcome or divergence information.",
                               "salt": BFCL_SALT, "parent_manifest": BFCL_SRC, "parent_manifest_sha256": sha_file(ROOT / BFCL_SRC),
                               "exclusion_sources": {BFCL_L8GATE: sha_file(ROOT / BFCL_L8GATE), BFCL_L8PROBE: sha_file(ROOT / BFCL_L8PROBE),
                                                     "gate_dirs": list(BFCL_GATE_DIRS)},
                               "exclusion_counts": {k: len(v) for k, v in excl.items()}, "excluded_ids": sorted(allx)}}


def build(a) -> None:
    model = a.model
    out = ROOT / ("manifests/fork/newmethod_panel_v1.json" if model == "q8" else f"manifests/fork/newmethod_panel_v1_{model}.json")
    if out.exists():
        raise SystemExit(f"{out} exists (frozen); refusing to overwrite")
    template = a.source_template or f"a6k2_{model}_bfpair_{{blk}}"
    snap_p = ROOT / a.snapshot
    snap = json.load(open(snap_p))
    rows, sources = tau2_rows(model, template, snap)
    check = check_against_bank_u(rows, model) if model == "q8" else {"not_applicable": "no Bank U rows for this model"}
    man = {"version": VERSION, "model": model, "protocol": PROTOCOL, "created": time.strftime("%FT%TZ", time.gmtime()),
           "builder": "scripts/a6000/make_newmethod_panel.py", "builder_sha256": sha_file(Path(__file__)),
           "snapshot": {"path": a.snapshot, "id": snap.get("snapshot_id"), "sha256": sha_file(snap_p)},
           "tau2": {"sub_bank": "U2B (BF16-sourced ordinary states; FORK_PROTOCOL §15 amendment 1)", "source_template": template,
                    "blocks": list(BLOCKS), "phase": PHASE, "domains": list(DOMS), "task_pool": "manifests/fork/splits_v1.json dev (retail 58, airline 27)",
                    "sampling": "t = floor(u * n_decisions), u = int(sha256('bank-u-v1|' + run + '|' + domain + '|' + task)[:12], 16) / 16**12; "
                                "state_key = sha256('U2B|' + run + '|' + domain + '|' + task)[:16]; no stratification; failed rows kept missing",
                    "sources": sources, "bank_u_identity": check,
                    "n_rows": len(rows), "n_missing": sum(1 for r in rows if r["missing_reason"])},
           "rows": rows, "frozen_before_any_panel_run": True}
    man.update(bfcl_panel())
    out.write_text(json.dumps(man, indent=1) + "\n")
    per = {}
    for r in rows:
        per.setdefault(r["block"], [0, 0])
        per[r["block"]][0] += 1
        per[r["block"]][1] += bool(r["missing_reason"])
    print("wrote", out.relative_to(ROOT), "sha256", sha_file(out))
    print("tau2 rows per block [rows, missing]:", per, "bank_u identity:", check)
    print("bfcl:", {k: (v["n_pool"], len(v[BFCL_SUBSET])) for k, v in man["categories"].items()}, man["bfcl_selection"]["exclusion_counts"])


# ---------------------------------------------------------------------------- expansion decision (protocol §5)
def _task_status(tid: str) -> tuple[str | None, dict | None]:
    for d in ("done", "failed", "running", "todo"):
        p = QUEUE / d / f"{tid}.json"
        if p.exists():
            return d, json.loads(p.read_text())
    return None, None


def expansion(a) -> None:
    m = a.model
    now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
    t_dec = dt.datetime.fromisoformat(T_DECIDE.get(m, T_DECIDE["default"]))
    t_dead = dt.datetime.fromisoformat(T_DEADLINE)
    outp = ROOT / OUTDIR / f"expansion_{m}.json"
    if outp.exists() and a.write:
        raise SystemExit(f"{outp} exists: the expansion decision is made once")
    cfg = {}
    for c in a.cells:
        per = {}
        for blk in ("f01", "f02", "f03"):
            tid = f"nmp_tau2_{m}_{c}_{blk}"
            st, task = _task_status(tid)
            sp = ROOT / OUTDIR / "tau2" / f"{m}_{c}" / blk / "bank_summary.json"
            s = json.loads(sp.read_text()) if sp.exists() else None
            keep = {k: s.get(k) for k in ("seconds", "n_rows", "n_ok", "n_missing", "n_errors", "budget_ok")} if s else None
            if s:
                keep["noop_all_pass"] = s["noop"]["n_pass"] == s["noop"]["n"]
            per[blk] = {"task": tid, "queue": st, "gpus": (task or {}).get("gpus"), "summary": keep}
        gate = ROOT / OUTDIR / "gate" / f"{m}_{c}"
        gs = gate / "same" / "gate_same.json"
        gb = gate / "bank" / "bank_summary.json"
        gate_ok = gs.exists() and gb.exists() and json.loads(gs.read_text())["verdict"]["pass"] and json.loads(gb.read_text())["gate_pass"]
        complete = all(v["queue"] == "done" and v["summary"] and v["summary"]["n_errors"] == 0 and v["summary"]["noop_all_pass"] for v in per.values())
        gpu_h = sum((v["summary"]["seconds"] * (v["gpus"] or 2)) / 3600 for v in per.values() if v["summary"])
        cfg[c] = {"blocks": per, "gate_pass": bool(gate_ok), "phase1_complete": bool(complete), "phase1_gpu_h": round(gpu_h, 3)}
    eligible = [c for c, v in cfg.items() if v["gate_pass"] and v["phase1_complete"]]
    ref_cost = 0.0
    for c in REF_CELLS.get(m, ()):  # reference cells: U2B share (85/190 rows) of their Bank U f01-f03 task time
        for blk in ("f01", "f02", "f03"):
            p = ROOT / "analysis/fork/bank_u" / f"{m}_{c}" / blk / "bank_summary.json"
            if p.exists():
                s = json.loads(p.read_text())
                ref_cost += s["seconds"] * 2 / 3600 * 85 / max(1, s["n_rows"])
    proj_gpu_h = SAFETY * (sum(cfg[c]["phase1_gpu_h"] for c in eligible) + ref_cost)
    proj_wall_h = proj_gpu_h / G_PANEL
    all_finished = all(v["queue"] in ("done", "failed") for c in cfg.values() for v in c["blocks"].values())
    decide_now = all_finished or now >= t_dec
    finish = now + dt.timedelta(hours=proj_wall_h)
    expand = bool(decide_now and eligible and finish <= t_dead)
    res = {"rule": "protocol §5: decide at the earlier of (all phase-1 tasks finished, T_decide); expand f04-f06 for ALL eligible "
                   "configs and the reference cells iff now + SAFETY * (phase-1 GPU-h of eligible configs + reference U2B cost) / "
                   "G_PANEL <= T_deadline. Eligible = gate passed and phase 1 complete (no errors, every no-op passed). "
                   "No outcome field is read.",
           "model": m, "now": now.isoformat(), "T_decide": t_dec.isoformat(), "T_deadline": t_dead.isoformat(), "G_PANEL": G_PANEL,
           "SAFETY": SAFETY, "configs": cfg, "eligible": eligible, "reference_cells": list(REF_CELLS.get(m, ())),
           "reference_u2b_gpu_h": round(ref_cost, 3), "projected_phase2_gpu_h": round(proj_gpu_h, 3), "projected_wall_h": round(proj_wall_h, 3),
           "projected_finish": finish.isoformat(), "decision_due": decide_now, "expand": expand if decide_now else None,
           "builder_sha256": sha_file(Path(__file__))}
    print(json.dumps({k: v for k, v in res.items() if k != "configs"}, indent=1))
    if a.write:
        if not decide_now:
            raise SystemExit("decision not due yet (phase 1 unfinished and before T_decide); nothing written")
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(res, indent=1) + "\n")
        print("wrote", outp.relative_to(ROOT))


# ---------------------------------------------------------------------------- spec templates (protocol §6)
def spec(a) -> None:
    m, c = a.model, a.cell
    man = "manifests/fork/newmethod_panel_v1.json" if m == "q8" else f"manifests/fork/newmethod_panel_v1_{m}.json"
    msha = sha_file(ROOT / man) if (ROOT / man).exists() else "<sha256 of the frozen manifest>"
    blocks = ["f01", "f02", "f03"] if a.phase == 1 else ["f04", "f05", "f06"]
    src = f"a6k2_{m}_bfpair_f01"
    out = {
        "gate_same (Q determinism, foreign states)": {"mode": "gate_same", "foreign_states": True, "q_blocks": [[src, "retail"], [src, "airline"]],
                                                      "n_per_block": 3, "idcheck_n": 8, "concurrency": 8, "out": f"{OUTDIR}/gate/{m}_{c}/same",
                                                      "_roles": "B = Q = this cell's checkpoint and serving config (two servers)"},
        "bank gate (BB no-op on every state)": {"mode": "bank_u", "manifest": man, "manifest_sha256": msha, "model": m, "cell": c,
                                                "blocks": ["f01"], "subs": ["U2B"], "limit_per_sub": 10, "noop_frac": 1.0, "concurrency": 8,
                                                "out": f"{OUTDIR}/gate/{m}_{c}/bank", "_roles": "B = BF16, Q = this cell"},
        "panel tasks (one per block; task id nmp_tau2_<model>_<cell>_<blk>)": [
            {"mode": "bank_u", "manifest": man, "manifest_sha256": msha, "model": m, "cell": c, "blocks": [b], "subs": ["U2B"],
             "noop_frac": 0.1, "concurrency": 8, "out": f"{OUTDIR}/tau2/{m}_{c}/{b}"} for b in blocks],
        "token scores (KLu), driver score, after each panel task": [
            {"driver": "score", "mode": "score_states", "model": m, "cell": c, "blocks": [b], "bank_out": f"{OUTDIR}/tau2/{m}_{c}/{b}",
             "out": f"{OUTDIR}/token_scores/{m}_{c}/{b}", "concurrency": 4} for b in blocks],
        "BFCL closed-loop Q run (eval task, env bfcl)": {"run_id": f"ext_{m}_{c}_bfcl_nmp1", "task_file": man, "subset": BFCL_SUBSET,
                                                         "domains": ["bfcl_base", "bfcl_miss_param", "bfcl_miss_func", "bfcl_long_context"]},
        "BFCL fork tasks (fork_ext dev, one per category)": [
            {"mode": "dev", "q_blocks": [f"ext_{m}_{c}_bfcl_nmp1:bfcl_{k}"], "noop_frac": 0.1, "concurrency": 12,
             "out": f"{OUTDIR}/bfcl/bfcl_{m}_{c}_{k}"} for k in ("base", "miss_param", "miss_func", "long_context")],
    }
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--model", default="q8")
    b.add_argument("--snapshot", default=DEF_SNAPSHOT)
    b.add_argument("--source-template", default=None)
    e = sub.add_parser("expansion")
    e.add_argument("--model", default="q8")
    e.add_argument("--cells", nargs="+", required=True)
    e.add_argument("--now", default=None)
    e.add_argument("--write", action="store_true")
    s = sub.add_parser("spec")
    s.add_argument("--model", default="q8")
    s.add_argument("--cell", required=True)
    s.add_argument("--phase", type=int, default=1, choices=(1, 2))
    a = ap.parse_args()
    {"build": build, "expansion": expansion, "spec": spec}[a.cmd](a)


if __name__ == "__main__":
    main()
