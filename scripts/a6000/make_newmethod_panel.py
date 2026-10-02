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
  expansion  the phase-2 decision (protocol §5 as amended by A5, W100g). Registered cells are fixed per model in REGISTERED
             (no command-line choice). Reads ONLY queue status (+ the task's gpus, finished time and fork spec), the
             allowed fields of phase-1 bank_summary.json files (seconds, n_rows, n_ok, n_missing, n_errors, budget_ok,
             no-op counts; provenance manifest_sha256 / spec blocks / cell), the gate verdicts (KIVI: the _fx gates; k4v4:
             strict T1), the manifest's row lists and the A3 mask (via analyze_newmethod.guard/population). Never opens
             bank_rows.jsonl, branches/, token scores or holdout/. Judged on a frozen snapshot as of min(now, T_decide);
             every input file's sha256 is recorded. Writes analysis/fork/newmethod/expansion_<model>.json exactly once.
  spec       print the fork specs (bank_u / gate_same / bank_u gate / score / BFCL eval + fork_ext dev) for one cell, for
             the method agents to wrap in their own queue tasks (Q role = theirs). Writes nothing.

usage:
  python scripts/a6000/make_newmethod_panel.py build [--model q8] [--snapshot S] [--source-template T]
  python scripts/a6000/make_newmethod_panel.py expansion --model q8|m24 [--now ISO (dry run only)] [--write] [--selftest]
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


# ---------------------------------------------------------------------------- expansion decision (protocol §5 + A5)
# Amendment A5 (W100g): the registered cells are fixed here per model, never chosen on the command line.
REGISTERED = {
    "q8": ("quarot_w4", "quarot_w4a4", "quarot_w16", "spinquant_w4a4", "spinquant_w16",  # A1.1
           "kivi_k2v2", "kivi_k4v4", "kivi_k16v16"),                                    # §1, A4.1, A4.3
    "m24": ("rtn_w4", "gptq_w4_d1"),                                                     # A2.2
}
# A4.2: KIVI gates count only from the re-runs on the fixed kernel (task id and output dir suffix _fx); the old gate
# outputs never admit a cell.
GATE_SUFFIX = {("q8", "kivi_k2v2"): "_fx", ("q8", "kivi_k4v4"): "_fx", ("q8", "kivi_k16v16"): "_fx"}
# A4.3: kivi_k4v4 additionally needs the strict T1 of the KIVI toy gate on the fixed kernel.
EXTRA_RELEASE = {("q8", "kivi_k4v4"): {"task": "kivi_gate_q8_toy4", "file": "analysis/fork/kivi_gate/gate_q8_toy4.json",
                                       "field": ("toy", "verdict_strict", "T1_strict_codes_scale_mn_deq_bitwise")}}
# A5: the KIVI kernel-path control expands together with the quantized KIVI cells, on the same blocks (f04-f06).
PAIRED_CONTROL = {"q8": {"kivi_k16v16": ("kivi_k2v2", "kivi_k4v4")}}
PHASE1 = ("f01", "f02", "f03")
_FORBIDDEN = ("bank_rows.jsonl", "/branches", "/holdout", "token_scores")


def _an():
    """analysis/fork/analyze_newmethod.py: protocol / manifest / mask guard and the A3 population (one source of truth)."""
    import importlib.util
    sp = importlib.util.spec_from_file_location("analyze_newmethod", ROOT / "analysis/fork/analyze_newmethod.py")
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    return mod


class Snap:
    """Frozen input snapshot: every file is read once, parsed from the same bytes whose sha256 is recorded."""

    def __init__(self, data_root: Path, queue: Path):
        self.data_root, self.queue, self.files, self.tasks = data_root, queue, {}, {}

    def read(self, rel: str):
        assert not any(f in "/" + rel for f in _FORBIDDEN), f"expansion never opens {rel}"
        try:
            b = (self.data_root / rel).read_bytes()
        except FileNotFoundError:
            self.files[rel] = None
            return None
        self.files[rel] = hashlib.sha256(b).hexdigest()
        return json.loads(b)

    def task(self, tid: str) -> dict:
        if tid in self.tasks:
            return self.tasks[tid]
        info = {"queue": None}
        for _ in range(3):  # a task file can move between directories while we look
            for d in ("done", "failed", "running", "todo", "deferred"):
                try:
                    b = (self.queue / d / f"{tid}.json").read_bytes()
                except FileNotFoundError:
                    continue
                t = json.loads(b)
                f = t.get("fork") or {}
                info = {"queue": d, "sha256": hashlib.sha256(b).hexdigest(), "gpus": t.get("gpus"), "finished": t.get("finished"),
                        "fork": {k: f.get(k) for k in ("mode", "model", "cell", "blocks", "subs", "manifest_sha256", "limit_per_sub", "out")}}
                break
            if info["queue"]:
                break
        self.tasks[tid] = info  # never the task's "result"
        return info


def _done_by(info: dict, as_of: float) -> bool:
    return info["queue"] == "done" and info.get("finished") is not None and info["finished"] <= as_of


def _get(d, path):
    for k in path:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def _population_plan(m: str, AN) -> dict:
    """Per phase-1 block: manifest U2B rows, manifest-missing rows (source failures), the A3 population tasks."""
    rel, want = AN.MANIFESTS[m]
    man = json.loads((ROOT / rel).read_text())
    pop, excluded = AN.population(m, man)
    plan = {}
    for blk in PHASE1:
        rows = [r for r in man["rows"] if r["model"] == m and r["block"] == blk and r["sub"] == "U2B"]
        miss = sorted(f"{r['domain']}|{r['task_id']}" for r in rows if r["missing_reason"])
        tasks = {f"{r['domain']}|{r['task_id']}" for r in rows}
        bad = set(miss) & pop
        if bad:  # a population task without a source state: the block could never be complete (A3 excludes these)
            raise SystemExit(f"expansion: manifest-missing rows inside the {m} population in {blk}: {sorted(bad)}")
        plan[blk] = {"n_rows": len(rows), "missing_source_rows": miss, "n_missing": len(miss),
                     "n_population_states": len(tasks & pop)}
    return {"manifest": rel, "manifest_sha256": want, "population_n_tasks": len(pop), "excluded_tasks": excluded, "blocks": plan}


def _block(m, c, blk, snap: Snap, as_of: float, plan: dict, msha: str) -> dict:
    """Phase-1 completeness of one (cell, block), from queue status + allowed summary fields + the manifest/mask counts.
    With n_missing equal to the number of manifest-missing rows of the block (all outside the population) and n_ok =
    n_rows - n_missing, n_errors = 0, every population state of the block has a completed record (A5.2)."""
    tid = f"nmp_tau2_{m}_{c}_{blk}"
    info = snap.task(tid)
    exp_out = f"{OUTDIR}/tau2/{m}_{c}/{blk}"
    why = []
    f = info.get("fork") or {}
    if not info["queue"]:
        why.append("task not queued")
    elif not _done_by(info, as_of):
        why.append(f"task not done at decision time (queue {info['queue']})")
    if info["queue"] and (f.get("out") != exp_out or f.get("mode") != "bank_u" or f.get("blocks") != [blk] or f.get("cell") != c
                          or f.get("model") != m or f.get("manifest_sha256") != msha or f.get("limit_per_sub") or f.get("subs") != ["U2B"]):
        why.append(f"task spec is not the panel spec ({f})")
    keep = None
    if _done_by(info, as_of):
        s = snap.read(f"{exp_out}/bank_summary.json")
        if s is None:
            why.append("bank_summary.json missing")
        else:
            keep = {k: s.get(k) for k in ("seconds", "n_rows", "n_ok", "n_missing", "n_errors", "budget_ok")}
            keep["noop_n"], keep["noop_n_pass"] = _get(s, ("noop", "n")), _get(s, ("noop", "n_pass"))
            sp = s.get("spec") or {}
            if s.get("manifest_sha256") != msha or sp.get("blocks") != [blk] or sp.get("cell") != c:
                why.append("summary provenance (manifest_sha256 / spec blocks / cell) mismatch")
            if keep["n_errors"] != 0:
                why.append(f"n_errors {keep['n_errors']}")
            if keep["n_rows"] != plan["n_rows"]:
                why.append(f"n_rows {keep['n_rows']} != manifest {plan['n_rows']}")
            if keep["n_missing"] != plan["n_missing"]:
                why.append(f"n_missing {keep['n_missing']} != {plan['n_missing']} manifest-missing source rows "
                           f"{plan['missing_source_rows']} (any other missing row fails the block)")
            if keep["n_ok"] != plan["n_rows"] - plan["n_missing"]:
                why.append(f"n_ok {keep['n_ok']} != {plan['n_rows'] - plan['n_missing']}")
            if keep["noop_n_pass"] is None or keep["noop_n_pass"] != keep["noop_n"]:
                why.append(f"no-op {keep['noop_n_pass']}/{keep['noop_n']} passed")
    complete = not why
    return {"task": tid, "queue": info["queue"], "finished": info.get("finished"), "task_sha256": info.get("sha256"),
            "gpus": info.get("gpus"), "summary": keep, "complete": complete,
            "population_states_covered": plan["n_population_states"] if complete else None, "reasons": why}


def _gates(m, c, snap: Snap, as_of: float, msha: str) -> tuple[bool, dict]:
    sfx = GATE_SUFFIX.get((m, c), "")
    out, ok_all = {}, True
    for kind, fname in (("same", "gate_same.json"), ("bank", "bank_summary.json")):
        tid = f"nmp_gate_{kind}_{m}_{c}{sfx}"
        info = snap.task(tid)
        exp_out = f"{OUTDIR}/gate/{m}_{c}{sfx}/{kind}"
        f = info.get("fork") or {}
        why = []
        if not info["queue"]:
            why.append("gate task not queued")
        elif not _done_by(info, as_of):
            why.append(f"gate task not done at decision time (queue {info['queue']})")
        if info["queue"] and f.get("out") != exp_out:
            why.append(f"gate task writes {f.get('out')}, expected {exp_out}")
        if kind == "bank" and info["queue"] and (f.get("cell") != c or f.get("manifest_sha256") != msha):
            why.append("bank gate spec cell / manifest mismatch")
        verdict = None
        if _done_by(info, as_of) and f.get("out") == exp_out:
            g = snap.read(f"{exp_out}/{fname}")
            verdict = None if g is None else bool(_get(g, ("verdict", "pass")) if kind == "same" else g.get("gate_pass"))
            if not verdict:
                why.append(f"gate verdict {verdict}")
        out[kind] = {"task": tid, "queue": info["queue"], "finished": info.get("finished"), "task_sha256": info.get("sha256"),
                     "out": exp_out, "pass": verdict, "reasons": why}
        ok_all &= not why
    x = EXTRA_RELEASE.get((m, c))
    if x:
        info = snap.task(x["task"])
        why = []
        val = None
        if not _done_by(info, as_of):
            why.append(f"{x['task']} not done at decision time (queue {info['queue']})")
        else:
            g = snap.read(x["file"])
            val = None if g is None else _get(g, x["field"])
            if val is not True:
                why.append(f"{'.'.join(x['field'])} = {val}")
        out["release"] = {"task": x["task"], "queue": info["queue"], "task_sha256": info.get("sha256"), "file": x["file"],
                          "field": ".".join(x["field"]), "value": val, "reasons": why}
        ok_all &= not why
    return ok_all, out


def _ts(x: float) -> str:
    return dt.datetime.fromtimestamp(x, dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=-7))).isoformat()


def decide(m: str, now: dt.datetime, data_root: Path = ROOT, queue: Path = None) -> dict:
    """The §5 decision on a frozen snapshot (A5). Pure: reads, never writes."""
    queue = queue or QUEUE
    if m not in REGISTERED:
        raise SystemExit(f"expansion: no registered cells for model {m} (register them by a dated amendment)")
    AN = _an()
    g = AN.guard(m)  # protocol, manifest and mask sha (refuses on mismatch)
    plan = _population_plan(m, AN)
    msha = plan["manifest_sha256"]
    t_dec = dt.datetime.fromisoformat(T_DECIDE.get(m, T_DECIDE["default"]))
    t_dead = dt.datetime.fromisoformat(T_DEADLINE)
    snap = Snap(data_root, queue)
    cells = REGISTERED[m]
    # (a) all phase-1 panel tasks of the registered cells finished (done or failed), judged now
    status_now = {c: [snap.task(f"nmp_tau2_{m}_{c}_{b}")["queue"] for b in PHASE1] for c in cells}
    all_finished = all(s in ("done", "failed") for v in status_now.values() for s in v)
    due = all_finished or now >= t_dec
    as_of = min(now, t_dec) if now >= t_dec else now  # past T_decide: the state as of T_decide (poll latency changes nothing)
    trigger = "T_decide" if now >= t_dec else ("all phase-1 tasks finished" if all_finished else None)
    a = as_of.timestamp()
    cfg = {}
    for c in cells:
        gate_ok, gates = _gates(m, c, snap, a, msha)
        blocks = {b: _block(m, c, b, snap, a, plan["blocks"][b], msha) for b in PHASE1}
        complete = all(v["complete"] for v in blocks.values())
        gpu_h = sum(v["summary"]["seconds"] * (v["gpus"] or 2) / 3600 for v in blocks.values()
                    if v["summary"] and isinstance(v["summary"].get("seconds"), (int, float)))
        why = [f"gate {k}: {r}" for k, v in gates.items() for r in v["reasons"]] + \
              [f"{b}: {r}" for b, v in blocks.items() for r in v["reasons"]]
        cfg[c] = {"gate_suffix": GATE_SUFFIX.get((m, c), ""), "gates": gates, "gate_pass": gate_ok, "blocks": blocks,
                  "phase1_complete": complete, "phase1_states_covered": sum(v["population_states_covered"] or 0 for v in blocks.values()),
                  "phase1_gpu_h": round(gpu_h, 3), "eligible_own": gate_ok and complete, "reasons": why}
    for ctl, quants in PAIRED_CONTROL.get(m, {}).items():  # A5.3 KIVI pairing (all-or-none within the KIVI group)
        own_q = [q for q in quants if q in cfg and cfg[q]["eligible_own"]]
        if ctl in cfg and cfg[ctl]["eligible_own"] and not own_q:
            cfg[ctl]["reasons"].append(f"A5.3: no eligible quantized KIVI cell among {list(quants)} to pair the kernel-path control with")
            cfg[ctl]["paired_out"] = True
        if ctl in cfg and not cfg[ctl]["eligible_own"]:
            for q in own_q:
                cfg[q]["reasons"].append(f"A5.3: kernel-path control {ctl} not eligible, so {q} does not expand without it")
                cfg[q]["paired_out"] = True
    for c in cells:
        cfg[c]["eligible"] = cfg[c]["eligible_own"] and not cfg[c].get("paired_out")
    eligible = [c for c in cells if cfg[c]["eligible"]]
    ref_cost, ref_in = 0.0, {}
    for c in REF_CELLS.get(m, ()):  # reference cells: U2B share (85 of n_rows) of their Bank U f01-f03 task time
        for blk in PHASE1:
            rel = f"analysis/fork/bank_u/{m}_{c}/{blk}/bank_summary.json"
            s = snap.read(rel)
            if s:
                ref_cost += s["seconds"] * 2 / 3600 * 85 / max(1, s["n_rows"])
                ref_in[f"{c}/{blk}"] = {"seconds": s["seconds"], "n_rows": s["n_rows"]}
    proj_gpu_h = SAFETY * (sum(cfg[c]["phase1_gpu_h"] for c in eligible) + ref_cost)
    proj_wall_h = proj_gpu_h / G_PANEL
    finish = now + dt.timedelta(hours=proj_wall_h)
    expand = bool(due and eligible and finish <= t_dead)
    return {"rule": "protocol §5 as amended by A5: decide once, at the earlier of (all phase-1 panel tasks of the registered cells "
                    "finished, T_decide), on a frozen snapshot (state as of min(now, T_decide)); eligible = both §2.4 gates passed "
                    "(KIVI: the _fx gates, A4.2; kivi_k4v4 also strict T1, A4.3) and phase 1 complete at decision time (f01-f03 done, "
                    "n_errors 0, every no-op passed, every population state covered: n_rows = manifest rows, n_missing = the "
                    "manifest-missing source rows outside the population, n_ok = n_rows - n_missing; m24 population = the A3 83-task "
                    "mask); KIVI pairing A5.3; expand ALL eligible cells and the reference cells iff now + SAFETY * (phase-1 GPU-h of "
                    "eligible + reference U2B cost) / G_PANEL <= T_deadline. No outcome field is read.",
            "model": m, "registered_cells": list(cells), "registry": "make_newmethod_panel.REGISTERED (amendment A5.1)",
            "now": now.isoformat(), "T_decide": t_dec.isoformat(), "T_deadline": t_dead.isoformat(), "decision_due": due,
            "trigger": trigger, "snapshot_as_of": as_of.isoformat(), "phase1_queue_now": status_now,
            "G_PANEL": G_PANEL, "SAFETY": SAFETY, "population": {k: plan[k] for k in ("population_n_tasks", "excluded_tasks", "blocks")},
            "guard": g, "configs": cfg, "eligible": eligible,
            "ineligible": {c: cfg[c]["reasons"] for c in cells if not cfg[c]["eligible"]},
            "reference_cells": list(REF_CELLS.get(m, ())), "reference_inputs": ref_in, "reference_u2b_gpu_h": round(ref_cost, 3),
            "projected_phase2_gpu_h": round(proj_gpu_h, 3), "projected_wall_h": round(proj_wall_h, 3),
            "projected_finish": finish.isoformat(), "expand": expand if due else None,
            "phase2_cells": (eligible + list(REF_CELLS.get(m, ()))) if expand else [],
            "inputs": {"files_sha256": snap.files, "queue_tasks": snap.tasks},
            "builder": "scripts/a6000/make_newmethod_panel.py", "builder_sha256": sha_file(Path(__file__))}


def write_once(res: dict, outp: Path) -> None:
    """Exactly one decision record per model: hard link of a complete temp file (fails if the record exists)."""
    outp.parent.mkdir(parents=True, exist_ok=True)
    tmp = outp.with_name(f".{outp.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(res, indent=1) + "\n")
    try:
        os.link(tmp, outp)
    except FileExistsError:
        raise SystemExit(f"{outp} exists: the expansion decision is made once")
    finally:
        tmp.unlink()


def _summary(res: dict) -> dict:
    return {"model": res["model"], "now": res["now"], "decision_due": res["decision_due"], "trigger": res["trigger"],
            "snapshot_as_of": res["snapshot_as_of"], "eligible": res["eligible"], "ineligible": res["ineligible"],
            "phase1_gpu_h": {c: v["phase1_gpu_h"] for c, v in res["configs"].items()},
            "reference_u2b_gpu_h": res["reference_u2b_gpu_h"], "projected_phase2_gpu_h": res["projected_phase2_gpu_h"],
            "projected_wall_h": res["projected_wall_h"], "projected_finish": res["projected_finish"], "expand": res["expand"],
            "builder_sha256": res["builder_sha256"]}


def expansion(a) -> None:
    m = a.model
    if a.cells is not None and tuple(a.cells) != REGISTERED.get(m):
        raise SystemExit(f"expansion: --cells {a.cells} != the registered cells {REGISTERED.get(m)} (amendment A5.1); omit --cells")
    if a.write and a.now:
        raise SystemExit("expansion: --now is for dry runs only; --write uses the clock")
    if a.selftest:
        return selftest()
    now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise SystemExit("expansion: --now needs a UTC offset, e.g. 2026-10-03T20:05:00-07:00")
    outp = ROOT / OUTDIR / f"expansion_{m}.json"
    if a.write and outp.exists():
        raise SystemExit(f"{outp} exists: the expansion decision is made once")
    res = decide(m, now)
    print(json.dumps(_summary(res), indent=1))
    if a.write:
        if not res["decision_due"]:
            raise SystemExit("decision not due yet (phase 1 unfinished and before T_decide); nothing written")
        write_once(res, outp)
        print("wrote", outp.relative_to(ROOT))


def selftest() -> None:
    """Synthetic queue + summaries in a temp dir (reads the real manifests, mask and protocol only; no fork output)."""
    import tempfile
    tz = dt.timezone(dt.timedelta(hours=-7))
    AN = _an()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)

        def setup(name):
            r = td / name
            for d in ("done", "failed", "running", "todo"):
                (r / "queue" / d).mkdir(parents=True)
            return r

        def put(r, d, tid, fork, fin, gpus=2):
            (r / "queue" / d / f"{tid}.json").write_text(json.dumps({"id": tid, "gpus": gpus, "fork": fork, "finished": fin,
                                                                    "result": {"must_not_be_used": True}}))

        def js(r, rel, obj):
            p = r / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(obj))

        def cell(r, m, c, fin, gates=True, sfx=None, blocks=None, gpus=2):
            msha = AN.MANIFESTS[m][1]
            sfx = GATE_SUFFIX.get((m, c), "") if sfx is None else sfx
            for kind, fn in (("same", "gate_same.json"), ("bank", "bank_summary.json")):
                out = f"{OUTDIR}/gate/{m}_{c}{sfx}/{kind}"
                put(r, "done", f"nmp_gate_{kind}_{m}_{c}{sfx}", {"out": out, "cell": c, "manifest_sha256": msha}, fin)
                js(r, f"{out}/{fn}", {"verdict": {"pass": gates}} if kind == "same" else {"gate_pass": gates})
            plan = _population_plan(m, AN)["blocks"]
            for b in PHASE1:
                p = plan[b]
                over = (blocks or {}).get(b, {})
                out = f"{OUTDIR}/tau2/{m}_{c}/{b}"
                put(r, over.get("queue", "done"), f"nmp_tau2_{m}_{c}_{b}",
                    {"mode": "bank_u", "model": m, "cell": c, "blocks": [b], "subs": ["U2B"], "manifest_sha256": msha, "out": out},
                    over.get("fin", fin), gpus)
                s = {"seconds": 3600.0, "n_rows": p["n_rows"], "n_ok": p["n_rows"] - p["n_missing"], "n_missing": p["n_missing"],
                     "n_errors": 0, "budget_ok": True, "noop": {"n": 8, "n_pass": 8}, "manifest_sha256": msha,
                     "spec": {"blocks": [b], "cell": c}}
                s.update(over.get("s", {}))
                js(r, f"{out}/bank_summary.json", s)

        def strict_t1(r, val):
            put(r, "done", "kivi_gate_q8_toy4", {}, 0.0)
            js(r, "analysis/fork/kivi_gate/gate_q8_toy4.json", {"toy": {"verdict_strict": {"T1_strict_codes_scale_mn_deq_bitwise": val}}})

        t_dec8 = dt.datetime.fromisoformat(T_DECIDE["q8"])
        before = (t_dec8 - dt.timedelta(hours=1)).timestamp()
        after = (t_dec8 + dt.timedelta(minutes=2)).timestamp()
        now = t_dec8 + dt.timedelta(minutes=5)
        # q8 scenario 1
        r = setup("q8a")
        cell(r, "q8", "quarot_w4", before)                                                    # eligible
        cell(r, "q8", "quarot_w4a4", before, blocks={"f03": {"s": {"n_missing": 1, "n_ok": 84}}})  # a newly missing row
        cell(r, "q8", "quarot_w16", before, blocks={"f02": {"fin": after}})                   # done after T_decide
        cell(r, "q8", "spinquant_w4a4", before, gates=False)                                   # gate failed
        cell(r, "q8", "kivi_k2v2", before, sfx="")                                             # only the old (pre-fix) gates
        cell(r, "q8", "kivi_k4v4", before)
        strict_t1(r, False)                                                                    # strict T1 not passed
        cell(r, "q8", "kivi_k16v16", before)                                                   # own-eligible, no partner
        res = decide("q8", now, r, r / "queue")
        assert res["decision_due"] and res["trigger"] == "T_decide" and res["snapshot_as_of"] == t_dec8.isoformat()
        assert res["eligible"] == ["quarot_w4"], res["eligible"]
        iz = res["ineligible"]
        assert any("n_missing 1 != 0" in x for x in iz["quarot_w4a4"])
        assert any("f02: task not done at decision time" in x for x in iz["quarot_w16"])
        assert any("gate verdict False" in x for x in iz["spinquant_w4a4"])
        assert any("task not queued" in x for x in iz["spinquant_w16"])
        assert any("nmp_gate_same_q8_kivi_k2v2_fx" in json.dumps(res["configs"]["kivi_k2v2"]["gates"]) and "not queued" in x for x in iz["kivi_k2v2"])
        assert any("T1_strict" in x for x in iz["kivi_k4v4"])
        assert any(x.startswith("A5.3: no eligible quantized") for x in iz["kivi_k16v16"])
        assert res["configs"]["quarot_w4"]["phase1_states_covered"] == 255 and abs(res["projected_phase2_gpu_h"] - 1.25 * 6) < 1e-9
        assert res["expand"] is True and "must_not_be_used" not in json.dumps(res["inputs"])
        assert all(not k.endswith("bank_rows.jsonl") for k in res["inputs"]["files_sha256"])
        print("selftest q8 scenario 1 OK:", res["eligible"], {c: v[0] for c, v in iz.items()})
        # q8 scenario 2: _fx gates pass -> k2v2 + k16v16 (+ k4v4 with strict T1) expand together; then k16v16 incomplete
        r = setup("q8b")
        cell(r, "q8", "kivi_k2v2", before)
        cell(r, "q8", "kivi_k4v4", before)
        strict_t1(r, True)
        cell(r, "q8", "kivi_k16v16", before)
        res = decide("q8", now, r, r / "queue")
        assert res["eligible"] == ["kivi_k2v2", "kivi_k4v4", "kivi_k16v16"], res["eligible"]
        r = setup("q8c")
        cell(r, "q8", "kivi_k2v2", before)
        cell(r, "q8", "kivi_k16v16", before, blocks={"f03": {"queue": "running", "fin": None}})
        res = decide("q8", now, r, r / "queue")
        assert res["eligible"] == [] and any("A5.3: kernel-path control kivi_k16v16 not eligible" in x for x in res["ineligible"]["kivi_k2v2"])
        assert res["expand"] is False
        print("selftest q8 KIVI pairing OK")
        # m24: the 7 manifest-missing source rows (tasks 13/44) do not block; any other missing row does
        t_dec24 = dt.datetime.fromisoformat(T_DECIDE["default"])
        r = setup("m24")
        early = (t_dec24 - dt.timedelta(hours=10)).timestamp()
        cell(r, "m24", "rtn_w4", early, gpus=4)
        cell(r, "m24", "gptq_w4_d1", early, gpus=4, blocks={"f02": {"s": {"n_missing": 2, "n_ok": 83}}})
        now24 = t_dec24 - dt.timedelta(hours=5)
        res = decide("m24", now24, r, r / "queue")
        assert res["decision_due"] and res["trigger"] == "all phase-1 tasks finished" and res["snapshot_as_of"] == now24.isoformat()
        assert res["eligible"] == ["rtn_w4"] and res["configs"]["rtn_w4"]["phase1_states_covered"] == 249
        assert any("n_missing 2 != 1" in x for x in res["ineligible"]["gptq_w4_d1"])
        assert abs(res["projected_phase2_gpu_h"] - 1.25 * 12) < 1e-9 and res["reference_u2b_gpu_h"] == 0
        print("selftest m24 OK:", res["eligible"], res["ineligible"])
        # not due: before T_decide with phase 1 unfinished
        r = setup("m24b")
        cell(r, "m24", "rtn_w4", early, gpus=4, blocks={"f03": {"queue": "running", "fin": None}})
        res = decide("m24", now24, r, r / "queue")
        assert res["decision_due"] is False and res["expand"] is None
        # write once
        outp = td / "out" / "expansion_m24.json"
        write_once(res, outp)
        try:
            write_once(res, outp)
            raise AssertionError("second write was not refused")
        except SystemExit:
            pass
        assert len(list(outp.parent.iterdir())) == 1
        # forbidden paths
        for bad in (f"{OUTDIR}/tau2/q8_x/f01/bank_rows.jsonl", f"{OUTDIR}/tau2/q8_x/f01/branches/a.json", "analysis/fork/holdout/x.json"):
            try:
                Snap(r, r / "queue").read(bad)
                raise AssertionError(bad)
            except AssertionError as e:
                assert "never opens" in str(e), e
        print("selftest decision_due / write-once / forbidden-path guard OK")
    print("SELFTEST PASS")


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
    e.add_argument("--cells", nargs="+", default=None, help="optional; must equal the registered cells (A5.1)")
    e.add_argument("--now", default=None, help="dry runs only")
    e.add_argument("--write", action="store_true")
    e.add_argument("--selftest", action="store_true", help="synthetic queue/summaries in a temp dir; writes nothing in the repo")
    s = sub.add_parser("spec")
    s.add_argument("--model", default="q8")
    s.add_argument("--cell", required=True)
    s.add_argument("--phase", type=int, default=1, choices=(1, 2))
    a = ap.parse_args()
    {"build": build, "expansion": expansion, "spec": spec}[a.cmd](a)


if __name__ == "__main__":
    main()
