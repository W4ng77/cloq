"""Telecom HOLDOUT task generator (W86; docs/insights/PREREG_FORK_CONFIRM.md §3, §4, §15). DRY RUN by default: prints the
tasks and the GPU-h estimate and writes nothing. `--write` queues them and is refused unless the prereg is frozen
(analyze_dev.split_guard: its sha256 equals manifests/fork/splits_v1.json splits.holdout.prereg_sha256).

Modelled on the telecom dev tasks (scripts/a6000/make_tasks_fork_dev2.py -> a6k2_{q4,q8}_tel_{bfpair,gptq_w4_d1,awq_w4}_fdevN,
scripts/a6000/make_tasks_fork_tel.py -> fork_tel_q8_<cell>_gN); only the task file, the nonces, the block ids and the
fork output root change:
  closed loop (kind eval, domain telecom, 3 blocks per task, as dev):
      a6k2_q4_tel_bfpair_hNN, a6k2_q4_tel_gptq_w4_d1_hNN, a6k2_q8_tel_bfpair_hNN, a6k2_q8_tel_gptq_w4_d1_hNN, a6k2_q8_tel_awq_w4_hNN
      for hNN in h01-h12; checkpoints copied from the done a6k2_<m>_<cell>.json (calibration c1), as dev2 did.
      GPUs: the models.json default (1), exactly as the dev closed-loop runs: the fork's Q server (1 GPU per server)
      must regenerate the closed-loop Q actions (q_check), so the closed loop is NOT run tensor-parallel.
  forks (kind fork, mode dev: search + BB/BQ/QB + 10% QQ no-op; 2 blocks per task, as fork_tel): cells q4 GPTQ-W4 d1
      (1 GPU, gpu_util 0.44, as fork_dev_q4), q8 GPTQ-W4 d1 and q8 AWQ-W4 (2 GPUs: one per B/Q server); deps = the
      closed-loop Q tasks holding their blocks; output analysis/fork/holdout/<model>_<cell>/gNN. No node pins.
Nonces (§3): nonce(block k) = sha256("cloq-fork-holdout-v1|" + str(k))[:8], k = 0..13 for h01..h14; must equal the
frozen table below and must not be used by any non-holdout run or queued task (checked; abort on collision).
Reserve blocks h13/h14 are generated only with --reserve (§4.4: infrastructure repair under the frozen completeness rule).
Task file: manifests/telecom/holdout_v1.json = {"telecom": splits_v1 splits.holdout.tasks.telecom (same order)}; written by
--write only if absent (dry run never writes it, and no task id is ever printed).

usage: python scripts/a6000/make_tasks_holdout.py [--reserve h13 [h14]] [--write]
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
Q = Path("/data/ziyangs/cloq_work/queue")
sys.path.insert(0, str(ROOT / "analysis/fork"))
import analyze_dev as AD  # noqa: E402

TASK_FILE = "manifests/telecom/holdout_v1.json"
PLANNING = ROOT / "analysis/fork/out/holdout_k_planning_20261001T134838Z.json"
NONCE_SALT = "cloq-fork-holdout-v1|"
FROZEN_NONCES = {  # PREREG_FORK_CONFIRM.md §3 table
    "h01": "18bf2ee3", "h02": "66d4bb88", "h03": "2e4fb169", "h04": "fadf7cf5", "h05": "2a5b0348", "h06": "5b3494c6",
    "h07": "04b40ec0", "h08": "76ea129b", "h09": "9537c607", "h10": "fb34253c", "h11": "a8daaa2a", "h12": "103c78cc",
    "h13": "0354e294", "h14": "555fd7b8"}
PRIMARY = [f"h{k:02d}" for k in range(1, 13)]
CLOSED = {"q4": ("bfpair", "gptq_w4_d1"), "q8": ("bfpair", "gptq_w4_d1", "awq_w4")}
FORK_CELLS = (("q4", "gptq_w4_d1"), ("q8", "gptq_w4_d1"), ("q8", "awq_w4"))
QDIRS = ("todo", "running", "done", "failed", "deferred")
# planning cost components (GPU-h per 80-task block, measured on telecom dev; holdout_k_planning cost)
COST_KEYS = {("closed", "q8", "bfpair"): "closed_q8_bfpair", ("closed", "q8", "gptq_w4_d1"): "closed_q8_gptq",
             ("closed", "q8", "awq_w4"): "closed_q8_awq", ("closed", "q4", "bfpair"): "closed_q4_bfpair",
             ("closed", "q4", "gptq_w4_d1"): "closed_q4_gptq", ("fork", "q8", "gptq_w4_d1"): "fork_q8_gptq",
             ("fork", "q8", "awq_w4"): "fork_q8_awq", ("fork", "q4", "gptq_w4_d1"): "fork_q4_gptq_scaled"}


def nonce(k: int) -> str:
    return hashlib.sha256(f"{NONCE_SALT}{k}".encode()).hexdigest()[:8]


def used_nonces(exclude_run_prefix_blocks: set[str]) -> dict:
    """nonce -> first user (run id or queue task id), excluding the holdout runs themselves (re-generation)."""
    def is_holdout(rid: str) -> bool:
        return any(rid.endswith(f"_{b}") for b in exclude_run_prefix_blocks) and "_tel_" in rid
    used = {}
    for p in glob.glob(str(ROOT / "runs/*/*/environment.json")):
        try:
            d = json.load(open(p))
        except Exception:
            continue
        rid = Path(p).parent.parent.name
        n = d.get("prompt_nonce")
        if n and not is_holdout(rid):
            used.setdefault(str(n), rid)
    for sub in QDIRS + ("legacy_v1",):
        for p in glob.glob(str(Q / sub / "*.json")):
            try:
                t = json.load(open(p))
            except Exception:
                continue
            for r in t.get("runs") or []:
                if isinstance(r, dict) and r.get("nonce") and not is_holdout(r.get("run_id", "")):
                    used.setdefault(str(r["nonce"]), t.get("id"))
    return used


def chunks(xs, n):
    return [xs[i:i + n] for i in range(0, len(xs), n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reserve", nargs="*", default=None, choices=["h13", "h14"],
                    help="generate ONLY these reserve blocks (§4.4: an unrepairable block is replaced in all cells)")
    ap.add_argument("--eval-priority", type=int, default=-6)
    ap.add_argument("--fork-priority", type=int, default=-12)
    ap.add_argument("--write", action="store_true", help="queue the tasks (refused unless the prereg is frozen)")
    a = ap.parse_args()
    frozen_ok = True
    try:
        AD.split_guard([], "holdout", "make_tasks_holdout")
    except SystemExit as e:
        frozen_ok = False
        print(f"NOTE: {e}")
        if a.write:
            raise SystemExit("make_tasks_holdout: --write refused: the prereg is not frozen")
    # ---- nonces
    for k, b in enumerate(sorted(FROZEN_NONCES)):
        assert nonce(k) == FROZEN_NONCES[b], (b, nonce(k), FROZEN_NONCES[b])
    blocks = list(a.reserve) if a.reserve else PRIMARY
    used = used_nonces(set(FROZEN_NONCES))
    clash = {b: used[FROZEN_NONCES[b]] for b in blocks if FROZEN_NONCES[b] in used}
    if clash:
        raise SystemExit(f"make_tasks_holdout: holdout nonce(s) already used by other runs/tasks: {clash} (prereg §3)")
    # ---- task file (never printed)
    man = json.load(open(AD.SPLITS))
    hold = [str(t) for t in man["splits"]["holdout"]["tasks"]["telecom"]]
    dev_hold = {str(t) for t in json.load(open(ROOT / "manifests/telecom/dev_v1.json"))["holdout"]}
    assert len(hold) == 34 == len(set(hold)) and set(hold) == dev_hold, "holdout list mismatch between splits_v1 and dev_v1"
    tf_payload = {"_note": ("Telecom HOLDOUT task file (W86) for cloq.run_arm --task-file; = manifests/fork/splits_v1.json "
                            "splits.holdout.tasks.telecom in the same order; written by scripts/a6000/make_tasks_holdout.py --write "
                            "after the PREREG_FORK_CONFIRM.md freeze"),
                  "splits_v1_sha256": AD.sha256(AD.SPLITS), "telecom": hold}
    tfp = ROOT / TASK_FILE
    if tfp.exists():
        assert json.load(open(tfp))["telecom"] == hold, f"{TASK_FILE} differs from splits_v1"
    # ---- tasks
    T = []
    eval_of = {}
    for m, cells in CLOSED.items():
        for cell in cells:
            src = None if cell == "bfpair" else json.load(open(Q / "done" / f"a6k2_{m}_{cell}.json"))
            for ci, ch in enumerate(chunks(blocks, 3), 1):
                tid = f"a6k2_{m}_tel_{cell}_hold{'R' if a.reserve else ''}{ci}"
                for b in ch:
                    eval_of[(m, cell, b)] = tid
                T.append({"id": tid, "kind": "eval", "model": m, "domains": ["telecom"],
                          "arm": src["arm"] if src else "bf16", "ckpt": src["ckpt"] if src else {"kind": "bf16"},
                          "runs": [{"run_id": f"a6k2_{m}_tel_{cell}_{b}", "task_file": TASK_FILE, "nonce": FROZEN_NONCES[b]} for b in ch],
                          "priority": a.eval_priority,
                          "deps": [d for d in (src.get("deps", []) if src else []) if "calib" in d],
                          "note": "W86 telecom HOLDOUT closed loop (make_tasks_holdout.py; PREREG_FORK_CONFIRM.md frozen)",
                          "_cost": ("closed", m, cell, len(ch))})
    for m, cell in FORK_CELLS:
        ck = json.load(open(Q / "done" / f"a6k2_{m}_{cell}.json"))["ckpt"]
        for gi, ch in enumerate(chunks(blocks, 2), 1):
            g = f"g{'R' if a.reserve else ''}{gi:02d}"
            T.append({"id": f"fork_hold_{m}_{cell}_{g}", "kind": "fork", "model": m, "gpus": 1 if m == "q4" else 2,
                      **({"gpu_util": 0.44} if m == "q4" else {}), "priority": a.fork_priority,
                      "deps": sorted({eval_of[(m, cell, b)] for b in ch}),
                      "B": {"ckpt": {"kind": "bf16"}}, "Q": {"ckpt": ck},
                      "fork": {"mode": "dev", "q_blocks": [[f"a6k2_{m}_tel_{cell}_{b}", "telecom"] for b in ch],
                               "branches": ["BB", "BQ", "QB"], "noop_frac": 0.1, "q_check": True, "concurrency": 8,
                               "out": f"analysis/fork/holdout/{m}_{cell}/{g}"},
                      "note": "W86 telecom HOLDOUT forks (make_tasks_holdout.py; fork-v1 protocol A as telecom dev)",
                      "_cost": ("fork", m, cell, len(ch))})
    # ---- cost
    comp = json.load(open(PLANNING))["cost"]["holdout_K12_3cells"]["per_80task_block_components_gpu_h"]
    tot = 0.0
    exists = lambda tid: any((Q / d / f"{tid}.json").exists() for d in QDIRS)
    print(f"{'task':40s} {'kind':5s} {'model':5s} gpus  blocks  deps  est_GPU-h")
    for t in T:
        kind, m, cell, nb = t.pop("_cost")
        gh = comp[COST_KEYS[(kind, m, cell)]] * 34 / 80 * nb
        tot += gh
        blk = [r["run_id"].rsplit("_", 1)[1] for r in t["runs"]] if kind == "closed" else [q[0].rsplit("_", 1)[1] for q in t["fork"]["q_blocks"]]
        print(f"{t['id']:40s} {t['kind']:5s} {t['model']:5s} {t.get('gpus', 'def'):>4} {','.join(blk):15s} {','.join(t['deps']) or '-'}  {gh:5.1f}"
              f"{'  (EXISTS: skipped)' if exists(t['id']) else ''}")
    n_runs = sum(len(t.get("runs", [])) for t in T)
    print(f"\n{len(T)} tasks ({sum(t['kind'] == 'eval' for t in T)} eval with {n_runs} closed-loop runs, "
          f"{sum(t['kind'] == 'fork' for t in T)} fork); blocks {blocks}; estimated {tot:.1f} GPU-h "
          f"(planning central figure, x0.7-x1.5: {0.7 * tot:.0f}-{1.5 * tot:.0f}); task file {TASK_FILE} "
          f"({'present' if tfp.exists() else 'to be written by --write'}); prereg frozen: {frozen_ok}")
    if not a.write:
        print("DRY RUN: nothing written (use --write only after the freeze)")
        return
    if not tfp.exists():
        tfp.write_text(json.dumps(tf_payload, indent=1) + "\n")
        print(f"wrote {TASK_FILE} sha256 {AD.sha256(tfp)}")
    n = 0
    for t in T:
        if not exists(t["id"]):
            json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)
            n += 1
    print("queued", n)


if __name__ == "__main__":
    main()
