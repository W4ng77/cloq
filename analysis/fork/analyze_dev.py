"""Fork development analysis (protocol fork-v1, deterministic protocol A): coverage, rescue/damage table, G, A/C/I.

Estimands (docs/insights/EXTERNAL_REVIEW_GPT61_20260930.md §E; FORK_PROTOCOL.md §6c). Unit = task x block (one Q
closed-loop episode of a cell on one nonce). Y = success: retail/airline DB success (db_match and a normal
user_stop/agent_stop ending), telecom official task-basis success (official_reward == 1). L = 1 - Y. At the unit's
primary state (first semantic action divergence along Q's history, frozen before branches ran):
  G  = E[Y_BQ - Y_QQ] = h - b     h = P(Y_BQ=1, Y_QQ=0) rescue,  b = P(Y_BQ=0, Y_QQ=1) new damage
  A  = L_QB - L_BB     C = L_BQ - L_BB     I = L_QQ - L_QB - L_BQ + L_BB      L_QQ - L_BB = A + C + I
Y_QQ is the original episode (no-op replay verified on a 10% sample per fork task). Units without a primary divergence
enter with all four branches equal to the original outcome (zero effect). Excluded units (search / branch
infrastructure failures, Q block not admitted in the snapshot, quarantined fork task) leave the denominator and are
counted per reason; they are never coded as "no divergence".
  Sign dictionary (W68, CONSEQUENCE_ANALYSIS_PLAN §2): A = Y_BB-Y_QB, C = Y_BB-Y_BQ, I = Y_BQ+Y_QB-Y_BB-Y_QQ, G = A+I,
H = Y_QB-Y_QQ = C+I, F = Y_BB-Y_QQ = A+C+I. No-divergence units: primary-policy quantities G/r/d/M (and the explicit
pivot policies H_policy/F_policy) are zero; raw A/C/I/H/F are null, so those are reported on divergent states only.
  G_all (primary)       mean over the full task pool: mean over blocks of the block's mean over tasks.
  G_div (secondary)     ratio form over divergent units only (sum of effects / number of states).
Headline (review of 7528f2e): the two-sided consequence decomposition on one denominator (all units of the fixed task
pool, non-divergent units = 0): r = P(Y_BQ=1, Y_QQ=0), d = P(Y_BQ=0, Y_QQ=1), M = r + d (outcome changed in either
direction), G = r - d; and r, d, M conditional on divergence.
Intervals (W63, class Boot): a block (nonce) is a common effect over all tasks, so it is resampled whole.
  primary   fixed task pool: statistic per complete shared block, then (i) block bootstrap (block_boot_ci95) and (ii) t
            over block means (t_ci95, df = K - 1), flagged when they disagree. `ci95`/`lb95_one_sided` = the block
            bootstrap when K >= 10 complete blocks (W4: 20, KV8: 22), else the t interval (stress/telecom/restore cells
            have 3-6 blocks; a percentile bootstrap over so few clusters is anti-conservative). B = 2000, seed 20261001.
  secondary generalisation to new tasks: crossed two-way bootstrap, tasks and blocks resampled jointly (crossed_ci95).
Draws are shared by all cells (same task ids and nonces), so the equal-weight pools carry valid intervals.
Complete blocks (W63): only complete shared blocks enter (every split task of the domain present in the block, no
pending branches); incomplete blocks are listed per cell and their units excluded with that reason.
Split (W63): --split dev (default) uses manifests/fork/splits_v1.json; units outside the split are excluded and any
telecom-holdout unit aborts the run unless --split holdout with a frozen PREREG_FORK_CONFIRM.md (sha recorded).
Thresholds (§F): g_min = eps = 3 pp. The lower one-sided 95% bound (5th percentile) is reported with flags
LB > 0 and LB > 3 pp. 5 pp is a sensitivity analysis only.
Quarantine (protocol A): a fork task (output directory) with any QQ no-op sample differing from its original
(suffix messages, prompt ids, termination, outcome, counters) is dropped whole and listed.
Divergence types: act->talk, talk->act, tool name, tool args, user-side device call (telecom: Q or B calls a tool that
belongs to the user's device toolset), other (tool count / order, stop, parse failure, invalid tool / args).

Pools: equal weight per cell within pre-declared families (W4 = gptq_w4_d1 + awq_w4; KV8 = kvq_int8; stress =
gptq_w3 + kvq_int4_rot + rtn_w3; every cell is also reported on its own), per model and across models; families are never pooled together.
Inputs: every directory under analysis/fork/{dev,kv,stress,restore,holdout}/ that holds search.json + states/ + branches/
(--include-gate also reads analysis/fork/gate/, whose states were selected, not searched over the full pool, for
testing only). Cell/model/block come from the Q run id a6k2_<model>_<cell>_<block>. The Q block (run, domain) must be
admitted (frozen) in the integrity-gated snapshot, and its trajectory.jsonl must still have the snapshot's sha256.
Idempotent: an output with the same input fingerprint (script, snapshot, every input file sha) is not rewritten.

usage: python analysis/fork/analyze_dev.py --snapshot <snapshot.json> [--cells gptq_w4_d1 awq_w4 ...] [--include-gate]
-> analysis/fork/out/dev_[gatetest_]<cells|all>_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis/fork/out"
ROOTS = ["analysis/fork/dev", "analysis/fork/kv", "analysis/fork/stress", "analysis/fork/telecom", "analysis/fork/repair", "analysis/fork/restore", "analysis/fork/holdout"]
# Pre-declared pooling families (equal weight per cell within a family; families are never pooled together).
FAMILIES = {"W4": ("gptq_w4_d1", "awq_w4"), "KV8": ("kvq_int8",), "stress": ("gptq_w3", "kvq_int4_rot", "kvq_int4", "rtn_w3")}


def family(cell: str) -> str:
    return next((f for f, cs in FAMILIES.items() if cell in cs), "other")
B_BOOT, SEED, G_MIN = 2000, 20261001, 0.03
MIN_BLOCKS_BOOT = 10  # below this many complete blocks the percentile block bootstrap is anti-conservative: t is primary
RUN_RE = re.compile(r"^a6k2_(q\d+|l8|m24)_(.+)_(q\d+|f\d\d|n\d+|h\d+)$")
TYPES = ["act->talk", "talk->act", "tool_name", "tool_args", "user_device_call", "other"]


def sha256(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


SPLITS = ROOT / "manifests/fork/splits_v1.json"


def unit_key(u: dict) -> tuple[str, str]:
    return u["domain"], u["task"].split(":", 1)[1]


PENDING = "state without branches"


def dedupe_units(units: list[dict]) -> tuple[list[dict], int]:
    """One record per (Q run, domain, task). A unit found in several directories (an original fork task and a W70 repair)
    keeps its non-excluded record; among equals the first (sorted directory order) wins."""
    best: dict = {}
    for u in units:
        k = (u["run_id"], u["domain"], u["task"])
        if k not in best or ("excluded" in best[k] and "excluded" not in u):
            best[k] = u
    return list(best.values()), len(units) - len(best)


def mark_incomplete_blocks(units: list[dict], split: str, strict: bool = True) -> dict:
    """Primary inference uses complete shared blocks only (W63, W70). A (model, cell, domain, block) is complete when every
    split task of that domain has a unit in it and, with strict=True (primary), none of its units is missing for any
    reason (pending branches, search or branch infrastructure failures, quarantine). strict=False reproduces the earlier
    rule (only missing tasks and pending branches make a block incomplete) and is a labelled complete-case sensitivity.
    Call after dedupe_units. Units of incomplete blocks are excluded with that reason. Returns {key: reason}."""
    need = {d: {str(t) for t in ts} for d, ts in json.load(open(SPLITS))["splits"][split]["tasks"].items()}
    groups = defaultdict(list)
    for u in units:
        groups[(u["model"], u["cell"], u["domain"], u["block"])].append(u)
    out = {}
    for (m, c, d, b), us in groups.items():
        have = {unit_key(u)[1] for u in us if not u.get("excluded", "").startswith("not in split")}
        missing = len(need.get(d, set()) - have)
        pending = sum(1 for u in us if u.get("excluded") == PENDING)
        other = sum(1 for u in us if "excluded" in u and u["excluded"] != PENDING and not u["excluded"].startswith("not in split"))
        if missing or pending or (strict and other):
            out[f"{m}:{c}|{d}|{b}"] = f"{missing} tasks missing, {pending} pending, {other} other missing units"
            for u in us:
                if "excluded" not in u:
                    u["excluded"] = "incomplete block (tasks missing, branches pending or missing units)"
    return out


def split_guard(units: list[dict], split: str, who: str = "analysis") -> dict:
    """Holdout boundary (W63). Units outside `split` are excluded ("not in split"); a unit whose task belongs to the
    telecom holdout aborts the analysis unless split == "holdout", which itself requires a frozen PREREG_FORK_CONFIRM.md
    whose sha256 equals the manifest's holdout.prereg_sha256. Returns provenance for the output."""
    man = json.load(open(SPLITS))
    sp = man["splits"]
    if split not in sp:
        raise SystemExit(f"{who}: unknown split {split!r} (manifest {SPLITS.relative_to(ROOT)}: {sorted(sp)})")
    if split == "holdout":
        h = sp["holdout"]
        pre = ROOT / h["prereg"]
        if not h.get("prereg_sha256") or not pre.exists() or sha256(pre) != h["prereg_sha256"]:
            raise SystemExit(f"{who}: refusing --split holdout: {h['prereg']} is not frozen with the sha256 recorded in "
                             f"{SPLITS.relative_to(ROOT)} (recorded {h.get('prereg_sha256')})")
    own = {(d, str(t)) for d, ts in sp[split]["tasks"].items() for t in ts}
    hold = {(d, str(t)) for d, ts in sp.get("holdout", {}).get("tasks", {}).items() for t in ts}
    leak = [u for u in units if unit_key(u) in hold and split != "holdout"]
    if leak:
        raise SystemExit(f"{who}: refusing: {len(leak)} unit(s) belong to the telecom holdout "
                         f"(e.g. {leak[0]['run_id']} {leak[0]['task']}); holdout analyses need --split holdout after the prereg freeze")
    n = 0
    for u in units:
        if unit_key(u) not in own and "excluded" not in u:
            u["excluded"] = f"not in split {split}"
            n += 1
    return {"split": split, "manifest": str(SPLITS.relative_to(ROOT)), "manifest_sha256": sha256(SPLITS), "n_units_not_in_split": n}


def success(domain: str, rec: dict) -> int:
    if domain == "telecom":
        return int(rec.get("official_reward") == 1.0)
    return int(bool(rec.get("db_match")) and rec.get("termination_reason", rec.get("termination")) in ("user_stop", "agent_stop"))


_UT: dict = {}


def user_tools(domain: str) -> set:
    if domain not in _UT:
        names = set()
        if domain == "telecom":
            try:
                sys.path.insert(0, str(ROOT))
                from tau2.runner.build import build_environment
                env = build_environment("telecom")
                names = {t.name for t in (env.get_user_tools() or [])}
            except Exception:
                names = set()
        _UT[domain] = names
    return _UT[domain]


def dtype(st: dict) -> str:
    d = st.get("divergence") or {}
    cat = d.get("category") or ""
    names = {c.split('"name":"')[1].split('"')[0] for c in (d.get("q_calls") or []) + (d.get("b_calls") or []) if '"name":"' in c}
    if st["domain"] == "telecom" and names & user_tools("telecom"):
        return "user_device_call"
    if cat == "class:act->talk":
        return "act->talk"
    if cat == "class:talk->act":
        return "talk->act"
    if cat in ("tool_name", "tool_args"):
        return cat
    return "other"


def noop_ok(st: dict, r: dict) -> tuple[bool, dict]:
    if "error" in r:
        return False, {"error": r["error"]}
    o = st["orig"]
    prompts = [d["prompt_ids_sha"] for d in r.get("decisions", [])]
    c = {"suffix": r.get("suffix_sha") == o["suffix_sha"], "prompts": prompts == o["suffix_prompt_ids_sha"],
         "termination": r.get("termination_reason") == o["termination_reason"],
         "outcome": success(st["domain"], r) == success(st["domain"], {**o, "termination_reason": o["termination_reason"]}),
         "counters": [r.get("step_count_final"), r.get("num_errors_final")] == list(o["budget_final"])}
    return all(c.values()), c


# ----------------------------------------------------------------------------
# loading
# ----------------------------------------------------------------------------


def discover(include_gate: bool) -> list[Path]:
    roots = ROOTS + (["analysis/fork/gate"] if include_gate else [])
    out = []
    for r in roots:
        for p in sorted(glob.glob(str(ROOT / r / "**" / "search.json"), recursive=True)):
            d = Path(p).parent
            if (d / "states").is_dir() and (d / "branches").is_dir():
                out.append(d)
    return out


def load_dir(d: Path, snap: dict, traj_sha_cache: dict) -> dict:
    """Units of one fork output directory, with its quarantine status and input file hashes."""
    s = json.load(open(d / "search.json"))
    rows = s["rows"] if isinstance(s, dict) else s
    files = {str((d / "search.json").relative_to(ROOT)): sha256(d / "search.json")}
    bfiles = {}
    for p in sorted((d / "branches").glob("*.json")):
        stem = p.stem
        sid = stem.split("_")[0]
        kind = stem[len(sid) + 1:] if "_" in stem else ""
        if kind in ("", "fwd"):  # dev: <sid>.json; gate: <sid>_fwd.json (rev/conc/bbnoop are gate-only checks)
            bfiles[sid] = p
    units, noop = [], []
    for row in rows:
        if not isinstance(row, dict) or "run_id" not in row:
            continue
        m = RUN_RE.match(row["run_id"])
        if not m:
            continue
        model, cell, block = m.groups()
        cell = cell[4:] if cell.startswith("tel_") else cell  # telecom runs a6k2_<m>_tel_<cell>_<blk>: same cell, domain telecom
        dom = row["domain"]
        u = {"dir": str(d.relative_to(ROOT)), "model": model, "cell": cell, "block": block, "domain": dom,
             "task": f"{dom}:{row['task_id']}", "run_id": row["run_id"], "n_decisions": row.get("n_decisions")}
        fr = (snap["frozen"].get(row["run_id"]) or {}).get(dom)
        if fr is None:
            units.append({**u, "excluded": f"Q block {row['run_id']}/{dom} not admitted in snapshot"})
            continue
        key = (row["run_id"], dom)
        if key not in traj_sha_cache:
            tp = ROOT / "runs" / row["run_id"] / dom / "trajectory.jsonl"
            traj_sha_cache[key] = sha256(tp) if tp.exists() else None
        if traj_sha_cache[key] != fr["files"]["trajectory.jsonl"]["sha256"]:
            units.append({**u, "excluded": "trajectory.jsonl differs from the snapshot"})
            continue
        if row.get("exclusion") or "error" in row:
            units.append({**u, "excluded": f"search: {row.get('exclusion') or row.get('error')}"[:200]})
            continue
        y0 = success(dom, {"db_match": row.get("orig_db_match"), "official_reward": row.get("orig_official_reward"),
                           "termination_reason": row.get("orig_termination")})
        if row.get("t_star") is None:
            units.append({**u, "div": False, "Y": {"QQ": y0, "BB": y0, "BQ": y0, "QB": y0}})
            continue
        sid = row["state_id"]
        sp = d / "states" / f"{sid}.json"
        if sid not in bfiles or not sp.exists():
            units.append({**u, "excluded": "state without branches"})
            continue
        st = json.load(open(sp))
        r4 = json.load(open(bfiles[sid]))
        files[str(sp.relative_to(ROOT))] = sha256(sp)
        files[str(bfiles[sid].relative_to(ROOT))] = sha256(bfiles[sid])
        yq = success(dom, {**st["orig"], "termination_reason": st["orig"]["termination_reason"]})
        if yq != y0:
            units.append({**u, "excluded": "state orig outcome != search row outcome"})
            continue
        bad = [b for b in ("BB", "BQ", "QB") if b not in r4 or "error" in r4[b]]
        if bad:
            units.append({**u, "excluded": f"branch error {bad}"})
            continue
        if "QQ" in r4:
            ok, chk = noop_ok(st, r4["QQ"])
            noop.append({"state_id": sid, "ok": ok, "checks": chk})
        Y = {"QQ": yq, **{b: success(dom, r4[b]) for b in ("BB", "BQ", "QB")}}
        units.append({**u, "div": True, "state_id": sid, "t": st["decision_idx"], "type": dtype(st),
                      "category": st["divergence"]["category"], "steps_left": st["budget"]["steps_left"],
                      "errors_left": st["budget"]["errors_left"], "Y": Y})
    quarantined = any(not x["ok"] for x in noop)
    return {"dir": str(d.relative_to(ROOT)), "units": units, "noop": noop, "quarantined": quarantined, "files": files}


# ----------------------------------------------------------------------------
# estimation
# ----------------------------------------------------------------------------


# Sign dictionary (docs/insights/CONSEQUENCE_ANALYSIS_PLAN.md §2, W68). Success scale; A and C keep the loss-oriented
# reading (positive = loss from replacing that BF16 component with Q). Numerically identical to the earlier
# L-scale definitions (A = L_QB - L_BB, C = L_BQ - L_BB, I = L_QQ - L_QB - L_BQ + L_BB).
SIGN_DICTIONARY = {
    "source": "docs/insights/CONSEQUENCE_ANALYSIS_PLAN.md §2 (W68)",
    "A": "Y_BB - Y_QB", "C": "Y_BB - Y_BQ", "I": "Y_BQ + Y_QB - Y_BB - Y_QQ",
    "G": "Y_BQ - Y_QQ = A + I (replace the current action only)",
    "H": "Y_QB - Y_QQ = C + I (keep Q's action, BF16 suffix)",
    "F": "Y_BB - Y_QQ = A + C + I (BF16 action and suffix)",
    "r": "P(Y_BQ=1, Y_QQ=0)", "d": "P(Y_BQ=0, Y_QQ=1)", "M": "r + d",
    "strict_reversal": "(Y_BB - Y_QB)(Y_BQ - Y_QQ) < 0, i.e. A*G < 0 (patterns 0110, 1001); reported apart from I != 0",
    "no_divergence": ("no eligible divergence = the primary pivot policy does nothing: G, r, d, M, H_policy, F_policy = 0 "
                      "(effect_source no_intervention); raw Y_BB/Y_BQ/Y_QB, A, C, I, H, F and the 16-pattern are null, "
                      "so A/C/I/H/F are reported only on observed divergent states"),
    "change_vs_W63": ("names G/H/F per the plan (H was QB_minus_QQ, F was BB_minus_QQ); full-pool A/C/I and full-pool H/F as "
                      "if no-divergence units had four equal outcomes are withdrawn; H/F on the full pool are now the "
                      "explicit pivot policies H_policy/F_policy (switch at the pivot, do nothing without one)"),
}


def effects(Y: dict, div: bool = True) -> dict:
    """Unit contrasts. For a no-divergence unit (div=False) only the primary-policy quantities are defined (zero)."""
    if not div:
        return {"G": 0, "rescue": 0, "damage": 0, "M": 0, "H_policy": 0, "F_policy": 0, "Y_QQ": Y["QQ"],
                "both_succeed": None, "both_fail": None, "A": None, "C": None, "I": None, "H": None, "F": None,
                "Y_BB": None, "Y_BQ": None, "Y_QB": None, "strict_reversal": None, "pattern": None, "effect_source": "no_intervention"}
    A, C = Y["BB"] - Y["QB"], Y["BB"] - Y["BQ"]
    I = Y["BQ"] + Y["QB"] - Y["BB"] - Y["QQ"]
    G, H, F = Y["BQ"] - Y["QQ"], Y["QB"] - Y["QQ"], Y["BB"] - Y["QQ"]
    assert G == A + I and H == C + I and F == A + C + I
    r = int(Y["BQ"] == 1 and Y["QQ"] == 0)
    d = int(Y["BQ"] == 0 and Y["QQ"] == 1)
    return {"G": G, "rescue": r, "damage": d, "M": r + d, "H_policy": H, "F_policy": F, "Y_QQ": Y["QQ"],
            "both_succeed": int(Y["BQ"] == 1 and Y["QQ"] == 1), "both_fail": int(Y["BQ"] == 0 and Y["QQ"] == 0),
            "A": A, "C": C, "I": I, "H": H, "F": F, "Y_BB": Y["BB"], "Y_BQ": Y["BQ"], "Y_QB": Y["QB"],
            "strict_reversal": int(A * G < 0), "pattern": f"{Y['BB']}{Y['BQ']}{Y['QB']}{Y['QQ']}",
            "effect_source": "observed-deterministic-forks"}


# Full pool (every admitted unit; the primary pivot policy: zero when there is no divergence)
STATS = ["G", "rescue", "damage", "M", "H_policy", "F_policy", "Y_QQ"]
# Observed divergent states only (pivot_four_branch_conditional)
COND_STATS = ("G", "rescue", "damage", "M", "both_succeed", "both_fail", "A", "C", "I", "H", "F", "strict_reversal",
              "Y_BB", "Y_BQ", "Y_QB", "Y_QQ")


class Draws(np.ndarray):
    """Block-bootstrap draws that also carry the t-over-blocks interval and the crossed draws of the same estimate, so
    `summarise(*boot.task_mean(...))` reports all three wherever the pair is stored. Derived arrays (means across cells,
    arithmetic) do not inherit this metadata."""

    def __new__(cls, a, t=None, crossed=None, crossed_pt=None, block_means=None):
        obj = np.asarray(a, float).view(cls)
        obj.t_info, obj.crossed, obj.crossed_pt, obj.block_means = t, crossed, crossed_pt, block_means
        return obj

    def __array_finalize__(self, obj):
        self.t_info = self.crossed = self.crossed_pt = self.block_means = None


class Boot:
    """Inference over the fixed task pool with complete shared blocks (W63; review of 7528f2e).

    A block (nonce) is one closed-loop run of every task, so it is a common random effect over all tasks. It must be
    resampled as a whole, never independently inside each task.
      primary (fixed task pool): the statistic of each complete block (mean over that block's tasks), then inference over
               blocks. (i) Block bootstrap (blocks with replacement, B draws, shared by all cells, so pools are valid);
               (ii) t over block means (df = K - 1). Both are reported (`ci95` = block bootstrap, `t_ci95`) and flagged
               when they disagree.
      secondary (generalisation to new tasks): crossed two-way bootstrap that keeps the global task x block pairing,
               tasks and blocks resampled jointly (unit weight = task multiplicity x block multiplicity), as in
               success_ni's generalisation_task_clustered_crossed (`crossed_ci95`).
    Point estimate: mean of block means (equal block weight). Ratio (conditional) forms use block sums.
    `task_mean` / `ratio` keep their old signatures and return the primary (block bootstrap) draws.
    """

    def __init__(self, tasks: list[str], blocks_of: dict[str, list[str]], B: int = B_BOOT, seed: int = SEED):
        self.tasks = tasks
        self.tix = {t: i for i, t in enumerate(tasks)}
        self.blocks = sorted({b for v in blocks_of.values() for b in v})
        self.bix = {b: i for i, b in enumerate(self.blocks)}
        T, K = len(tasks), len(self.blocks)
        rng = np.random.default_rng(seed)
        self.Vb = np.stack([np.bincount(rng.integers(0, K, K), minlength=K) for _ in range(B)]).astype(float)  # (B, K)
        self.Wc = np.stack([np.bincount(rng.integers(0, T, T), minlength=T) for _ in range(B)]).astype(float)  # (B, T)
        self.Vc = np.stack([np.bincount(rng.integers(0, K, K), minlength=K) for _ in range(B)]).astype(float)  # (B, K)
        self.last: dict = {}

    def arrays(self, units: list[dict], key: str, mask_key=None):
        T, K = len(self.tasks), len(self.blocks)
        X, M = np.zeros((T, K)), np.zeros((T, K))
        for u in units:
            if mask_key and not u.get(mask_key):
                continue
            v = u["E"][key]
            if v is None:  # undefined for this unit (e.g. raw four-branch contrasts of a no-divergence unit)
                continue
            t, k = self.tix[u["task"]], self.bix[u["block"]]
            X[t, k] = v
            M[t, k] = 1
        return X, M

    def block_means(self, X, M):
        n = M.sum(0)
        return np.where(n > 0, (X * M).sum(0) / np.maximum(n, 1e-12), np.nan)

    def task_mean(self, X, M):
        """Primary estimator (mean of block means) and its block-bootstrap draws; also sets self.last (t, crossed)."""
        bm = self.block_means(X, M)
        has = np.isfinite(bm)
        bmz = np.where(has, bm, 0.0)
        pt = float(bmz[has].mean()) if has.any() else float("nan")
        w = self.Vb * has
        ws = w.sum(-1)
        draws = np.where(ws > 0, (w * bmz).sum(-1) / np.maximum(ws, 1e-12), np.nan)  # a draw without data is missing, not 0
        cw = self.Wc[:, :, None] * self.Vc[:, None, :]
        cden = (cw * M).sum((-1, -2))
        crossed = np.where(cden > 0, (cw * X * M).sum((-1, -2)) / np.maximum(cden, 1e-12), np.nan)
        self.last = {"block_means": bm, "crossed": crossed, "crossed_pt": float((X * M).sum() / max(M.sum(), 1e-12)),
                     "t": t_interval(bm[has])}
        return pt, Draws(draws, self.last["t"], crossed, self.last["crossed_pt"], bm)

    def ratio(self, X, M):
        """Ratio form over the masked units (conditional on divergence) with block sums; crossed draws in self.last."""
        S, N = (X * M).sum(0), M.sum(0)
        pt = float(S.sum() / max(N.sum(), 1e-12))
        dn = (self.Vb * N).sum(-1)
        draws = np.where(dn > 0, (self.Vb * S).sum(-1) / np.maximum(dn, 1e-12), np.nan)
        cw = self.Wc[:, :, None] * self.Vc[:, None, :]
        cden = (cw * M).sum((-1, -2))
        crossed = np.where(cden > 0, (cw * X * M).sum((-1, -2)) / np.maximum(cden, 1e-12), np.nan)
        br = np.where(N > 0, S / np.maximum(N, 1e-12), np.nan)
        self.last = {"block_means": br, "crossed": crossed, "crossed_pt": pt, "t": t_interval(br), "t_note": "t over per-block ratios"}
        return pt, Draws(draws, self.last["t"], crossed, pt, br)

    def unit_weights(self, ti, ki, scheme: str = "block"):
        """(B, n) weights of units at (task index, block index) under the block or crossed scheme."""
        return self.Vb[:, ki] if scheme == "block" else self.Wc[:, ti] * self.Vc[:, ki]


def t_interval(x) -> dict | None:
    x = np.asarray([v for v in x if np.isfinite(v)], float)
    if len(x) < 2:
        return None
    from scipy.stats import t as tdist
    m, se = x.mean(), x.std(ddof=1) / np.sqrt(len(x))
    q = tdist.ppf(0.975, len(x) - 1)
    return {"lo": float(m - q * se), "hi": float(m + q * se), "lb_one_sided": float(m - tdist.ppf(0.95, len(x) - 1) * se),
            "k": int(len(x)), "df": int(len(x) - 1)}


def summarise(pt: float, draws: np.ndarray, pct: bool = True, boot: "Boot | None" = None, t: dict | None = None,
              crossed: tuple | None = None) -> dict:
    """Interval report. `draws` = block-bootstrap draws; t = t over block means (from boot.last or given); crossed =
    (point, draws) of the crossed task x block bootstrap. Primary interval (`ci95`, `lb95_one_sided`, `primary`):
    block bootstrap when there are >= MIN_BLOCKS_BOOT complete blocks, else t over block means (few clusters). Both are
    always reported (`block_boot_ci95`, `t_ci95`), flagged when they disagree, plus `crossed_ci95` (generalisation)."""
    f = 100 if pct else 1
    if isinstance(draws, Draws):  # metadata travels with the draws (siblings store (pt, draws) pairs)
        t = t if t is not None else draws.t_info
        crossed = crossed if crossed is not None else ((draws.crossed_pt, draws.crossed) if draws.crossed is not None else None)
    elif boot is not None and boot.last:
        t = t if t is not None else boot.last.get("t")
        crossed = crossed if crossed is not None else (boot.last.get("crossed_pt"), boot.last.get("crossed"))
    draws = np.asarray(draws, float)
    draws = draws[np.isfinite(draws)]
    lo, hi = np.percentile(draws, [2.5, 97.5]) if len(draws) else (np.nan, np.nan)
    lb = np.percentile(draws, 5) if len(draws) else np.nan
    out = {"est": round(float(f * pt), 3), "block_boot_ci95": [round(float(f * lo), 3), round(float(f * hi), 3)],
           "block_boot_lb95": round(float(f * lb), 3)}
    primary = "block bootstrap"
    ci, lb1 = out["block_boot_ci95"], out["block_boot_lb95"]
    if t:
        out["t_ci95"] = [round(f * t["lo"], 3), round(f * t["hi"], 3)]
        out["t_lb95_one_sided"] = round(f * t["lb_one_sided"], 3)
        out["n_blocks"] = t["k"]
        wb, wt = hi - lo, t["hi"] - t["lo"]
        out["block_vs_t_differ"] = bool(abs(wb - wt) > 0.2 * max(wb, wt, 1e-12) or (lo > 0) != (t["lo"] > 0))
        if t["k"] < MIN_BLOCKS_BOOT:
            primary = f"t over {t['k']} block means (fewer than {MIN_BLOCKS_BOOT} blocks)"
            ci, lb1 = out["t_ci95"], out["t_lb95_one_sided"]
    elif len(draws) and boot is not None and len(boot.blocks) < MIN_BLOCKS_BOOT:
        primary = "block bootstrap (t unavailable; few blocks: interpret with caution)"
    out["ci95"], out["lb95_one_sided"], out["primary"] = ci, lb1, primary
    if crossed is not None and crossed[1] is not None:
        c = np.asarray(crossed[1], float)
        c = c[np.isfinite(c)]
        if len(c):
            out["crossed_est"] = round(f * float(crossed[0]), 3)
            out["crossed_ci95"] = [round(float(f * x), 3) for x in np.percentile(c, [2.5, 97.5])]
    return out


def analyse(units: list[dict], boot: Boot, draws_out: dict | None = None, label: str = "") -> dict:
    div = [u for u in units if u["div"]]
    res = {"n_units": len(units), "n_tasks": len({u["task"] for u in units}), "n_blocks": len({u["block"] for u in units}),
           "n_states": len(div), "divergence_rate": round(len(div) / len(units), 4) if units else None}
    if not units:
        return res
    all_ = {}
    for s in STATS:
        X, M = boot.arrays(units, s)
        pt, dr = boot.task_mean(X, M)
        all_[s] = summarise(pt, dr, boot=boot)
        if draws_out is not None:
            draws_out.setdefault(label, {})[s] = (pt, dr, boot.last["block_means"], boot.last["crossed"], boot.last["crossed_pt"])
    res["all_pp"] = all_
    g = all_["G"]
    res["G_all_decision"] = {"lb_gt_0": bool(g["lb95_one_sided"] > 0), "lb_gt_gmin": bool(g["lb95_one_sided"] > 100 * G_MIN),
                             "ub_lt_minus_gmin": bool(g["ci95"][1] < -100 * G_MIN), "g_min_pp": 100 * G_MIN,
                             "t_lb_gt_0": bool(g.get("t_lb95_one_sided", -1e9) > 0), "basis": "block bootstrap (primary); t over blocks alongside"}
    if div:
        cond = {}
        for s in COND_STATS:
            X, M = boot.arrays(div, s)
            pt, dr = boot.ratio(X, M)
            cond[s] = summarise(pt, dr, boot=boot)
        res["conditional_on_divergence_pp"] = cond
        res["counts"] = {k: int(sum(u["E"][k] for u in div)) for k in ("rescue", "damage", "M", "both_succeed", "both_fail", "strict_reversal")}
        ts = np.array([u["t"] for u in div])
        rel = np.array([u["t"] / max(1, u["n_decisions"] or 1) for u in div])
        res["t_star"] = {"quantiles": {str(q): float(np.quantile(ts, q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)},
                         "hist": {str(k): int(v) for k, v in zip(*np.unique(ts, return_counts=True))},
                         "rel_median": round(float(np.median(rel)), 3)}
        res["steps_left_median"] = float(np.median([u["steps_left"] for u in div]))
        res["errors_left_median"] = float(np.median([u["errors_left"] for u in div]))
    return res


def breakdown(units: list[dict], boot: Boot, field: str, levels: list[str]) -> dict:
    """Per divergence type / domain: counts, conditional effects, and the share of G_all it contributes."""
    out = {}
    div = [u for u in units if u["div"]]
    for lv in levels:
        sub = [u for u in div if u.get(field) == lv]
        if not sub:
            continue
        r = {"n_states": len(sub), "counts": {k: int(sum(u["E"][k] for u in sub)) for k in ("rescue", "damage", "M", "both_succeed", "both_fail")}}
        for s in ("G", "rescue", "damage", "M", "A", "C", "I"):
            X, M = boot.arrays(sub, s)
            pt, dr = boot.ratio(X, M)
            r[f"{s}_cond_pp"] = summarise(pt, dr, boot=boot)
        # contribution to G_all: effect of this type's units, all other units counted as zero
        zu = [{**u, "E": {**u["E"], "G": u["E"]["G"] if (u["div"] and u.get(field) == lv) else 0}} for u in units]
        X, M = boot.arrays(zu, "G")
        pt, dr = boot.task_mean(X, M)
        r["G_all_contribution_pp"] = summarise(pt, dr, boot=boot)
        out[lv] = r
    return out


def pooled(draws: dict, labels: list[str]) -> dict:
    """Equal-weight pool over cells (pre-declared) on the shared draws: block bootstrap, t over the per-block pooled means
    (blocks present in every pooled cell), crossed; primary per summarise(). Accepts (pt, draws) pairs from siblings."""
    out = {}
    for s in ("G", "rescue", "damage", "M", "H_policy", "F_policy"):
        vals = [draws[l][s] for l in labels if l in draws and s in draws[l]]
        if not vals:
            continue
        pt = float(np.mean([v[0] for v in vals]))
        t = crossed = None
        if all(len(v) >= 5 for v in vals):
            t = t_interval(np.mean(np.vstack([v[2] for v in vals]), axis=0))
            crossed = (float(np.mean([v[4] for v in vals])), np.mean([v[3] for v in vals], axis=0))
        out[s] = summarise(pt, np.mean([v[1] for v in vals], axis=0), t=t, crossed=crossed)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--cells", nargs="*", default=None)
    ap.add_argument("--include-gate", action="store_true", help="also read analysis/fork/gate (selected states; testing only)")
    ap.add_argument("--B", type=int, default=B_BOOT)
    ap.add_argument("--split", default="dev", help="dev (default) | holdout (only after the prereg freeze); manifests/fork/splits_v1.json")
    ap.add_argument("--complete-case", action="store_true", help="sensitivity: blocks with infrastructure-missing units stay complete (pre-W70 rule)")
    a = ap.parse_args()
    t0 = time.time()
    try:  # tau2 (imported for the telecom user-tool list) logs at INFO on import
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    snap = json.load(open(a.snapshot))
    dirs = discover(a.include_gate)
    cache: dict = {}
    loaded = [load_dir(d, snap, cache) for d in dirs]
    units_all = [u for L in loaded for u in L["units"]]
    known = sorted({u["cell"] for u in units_all})
    if a.cells:
        miss = [c for c in a.cells if c not in known]
        if miss:
            print(f"analyze_dev: no fork outputs for cell(s) {miss} yet (cells with outputs: {known or 'none'}); nothing to do.")
        loaded_f = [{**L, "units": [u for u in L["units"] if u["cell"] in a.cells]} for L in loaded]
        loaded = [L for L in loaded_f if L["units"]]
        if not loaded:
            return
    if not loaded:
        print(f"analyze_dev: no fork output directories under {ROOTS}{' + gate' if a.include_gate else ''}; nothing to do.")
        return
    tag = ("gatetest_" if a.include_gate else "") + ("cc_" if a.complete_case else "") + ("" if a.split == "dev" else f"{a.split}_") + ("_".join(sorted(a.cells)) if a.cells else "all")
    script_sha = sha256(__file__)
    files = {k: v for L in loaded for k, v in L["files"].items()}
    fp = hashlib.sha256(json.dumps({"script": script_sha, "snapshot": sha256(a.snapshot), "files": files, "cells": a.cells,
                                    "gate": a.include_gate, "B": a.B, "split": a.split, "splits": sha256(SPLITS), "complete_case": a.complete_case},
                                   sort_keys=True).encode()).hexdigest()[:16]
    OUT.mkdir(parents=True, exist_ok=True)
    for p in sorted(OUT.glob(f"dev_{tag}_*.json")):
        try:
            if json.load(open(p)).get("input_fingerprint") == fp:
                print(f"analyze_dev: unchanged inputs (fingerprint {fp}); existing output {p.relative_to(ROOT)}")
                return
        except Exception:
            continue
    split_info = split_guard([u for L in loaded for u in L["units"]], a.split, "analyze_dev")
    quarantine = [L["dir"] for L in loaded if L["quarantined"]]
    for L in loaded:
        if L["quarantined"]:
            for u in L["units"]:
                u.setdefault("excluded", "quarantined fork task (QQ no-op mismatch)")
    units, dups = dedupe_units([u for L in loaded for u in L["units"]])
    incomplete = mark_incomplete_blocks(units, a.split, strict=not a.complete_case)
    excluded = [u for u in units if "excluded" in u]
    ok = [u for u in units if "excluded" not in u]
    for u in ok:
        u["E"] = effects(u["Y"], u["div"])
    PRIMARY_DOMAINS = ("retail", "airline")  # W70: common 85-task retail/airline panel is primary; telecom reported separately

    def boot_for(us):  # resampling frame = exactly the tasks and blocks these units have (no empty draws, W70)
        bo = defaultdict(set)
        for u in us:
            bo[u["task"]].add(u["block"])
        return Boot(sorted(bo), {t: sorted(v) for t, v in bo.items()}, B=a.B)

    def cell_result(cu, allc, m, c):
        boot = boot_for(cu)
        r = analyse(cu, boot)
        r["by_type"] = breakdown(cu, boot, "type", TYPES)
        r["by_domain"] = {d: analyse([u for u in cu if u["domain"] == d], boot_for([u for u in cu if u["domain"] == d]))
                          for d in sorted({u["domain"] for u in cu})} if len({u["domain"] for u in cu}) > 1 else {}
        ex = defaultdict(int)
        for u in allc:
            if "excluded" in u:
                ex[u["excluded"].split(":")[0] if u["excluded"].startswith(("search", "branch error")) else u["excluded"]] += 1
        r["incomplete_blocks"] = sorted(k.split("|", 1)[1] for k in incomplete if k.startswith(f"{m}:{c}|")
                                        and k.split("|")[1] in {u["domain"] for u in allc})
        r["excluded"] = dict(ex)
        r["coverage"] = {"units_found": len(allc), "units_analysed": len(cu), "states": r["n_states"],
                         "excluded_by_reason": dict(ex), "tasks": r["n_tasks"], "blocks": sorted({u["block"] for u in cu}),
                         "blocks_found": sorted({u["block"] for u in allc}),
                         "domains": {d: {"units": sum(1 for u in cu if u["domain"] == d),
                                         "task_ids": sorted({u["task"].split(":", 1)[1] for u in cu if u["domain"] == d})}
                                     for d in sorted({u["domain"] for u in allc})},
                         "source_dirs": sorted({u["dir"] for u in allc})}
        return r

    cells = sorted({(u["model"], u["cell"]) for u in units})
    res_cells, res_tel = {}, {}
    for m, c in cells:
        cu = [u for u in ok if u["model"] == m and u["cell"] == c and u["domain"] in PRIMARY_DOMAINS]
        allc = [u for u in units if u["model"] == m and u["cell"] == c and u["domain"] in PRIMARY_DOMAINS]
        if allc:
            res_cells[f"{m}:{c}"] = cell_result(cu, allc, m, c) if cu else {"n_units": 0, "note": "no complete block"}
        tu = [u for u in ok if u["model"] == m and u["cell"] == c and u["domain"] == "telecom"]
        tall = [u for u in units if u["model"] == m and u["cell"] == c and u["domain"] == "telecom"]
        if tall:
            res_tel[f"{m}:{c}"] = cell_result(tu, tall, m, c) if tu else {"n_units": 0, "note": "no complete telecom block"}
    # pools: only over the complete blocks shared by every pooled cell (W70); otherwise not poolable
    models = sorted({m for m, _ in cells})
    pools = {}
    for fam in sorted({family(c) for _, c in cells}):
        fc = [(m, c) for m, c in cells if family(c) == fam]
        groups = {f"{fam}:{m}:pooled_equal_weight": [(mm, c) for mm, c in fc if mm == m] for m in models}
        groups[f"{fam}:all:pooled_equal_weight"] = fc
        for name, gcells in groups.items():
            gcells = [mc for mc in gcells if any(u["model"] == mc[0] and u["cell"] == mc[1] and u["domain"] in PRIMARY_DOMAINS for u in ok)]
            if not gcells:
                continue
            per = {mc: {(u["domain"], u["block"]) for u in ok if (u["model"], u["cell"]) == mc and u["domain"] in PRIMARY_DOMAINS} for mc in gcells}
            common = set.intersection(*per.values())
            nblk = len({b for _, b in common})
            if nblk < 2:
                pools[name] = {"not_poolable": f"{nblk} common complete block(s) across {[f'{x}:{y}' for x, y in gcells]}"}
                continue
            pu = [u for u in ok if (u["model"], u["cell"]) in per and (u["domain"], u["block"]) in common]
            boot = boot_for(pu)
            draws: dict = {}
            for mc in gcells:
                analyse([u for u in pu if (u["model"], u["cell"]) == mc], boot, draws, f"{mc[0]}:{mc[1]}")
            pools[name] = {**pooled(draws, [f"{x}:{y}" for x, y in gcells]), "cells": [f"{x}:{y}" for x, y in gcells],
                           "common_blocks": sorted({b for _, b in common}), "k_blocks": nblk}
    noop = [x for L in loaded for x in L["noop"]]
    res = {
        "protocol": "fork-v1 / protocol A", "analysis": "analysis/fork/analyze_dev.py", "input_fingerprint": fp,
        "snapshot": {"id": snap.get("snapshot_id"), "path": str(Path(a.snapshot).resolve()), "sha256": sha256(a.snapshot)},
        "script": {"path": str(Path(__file__).resolve()), "sha256": script_sha,
                   "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()},
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cells_filter": a.cells, "include_gate": a.include_gate,
        "bootstrap": {"B": a.B, "seed": SEED,
                      "primary": "fixed task pool: statistic per complete shared block; ci95 = block bootstrap if >= 10 blocks else t over block means; both reported (block_boot_ci95, t_ci95)",
                      "secondary": "generalisation to new tasks: crossed two-way bootstrap, tasks and blocks resampled jointly (crossed_ci95)",
                      "draws": "shared by all cells (same task ids and nonces), so equal-weight pools are valid"},
        "split": split_info, "incomplete_blocks": incomplete, "sign_dictionary": SIGN_DICTIONARY,
        "block_rule": ("COMPLETE-CASE SENSITIVITY: blocks with infrastructure-missing units kept (pre-W70 rule)" if a.complete_case else
                       "primary (W70): a block with any missing unit is incomplete and leaves the analysis"),
        "estimand_ids": {"all_pp": "primary_pivot_G_all (+ r/d/M and pivot-policy H_policy/F_policy on the same full-pool denominator)",
                         "conditional_on_divergence_pp": "pivot_G_conditional and pivot_four_branch_conditional (A/C/I/H/F, strict reversal)"},
        "thresholds": {"g_min_pp": 100 * G_MIN, "eps_pp": 100 * G_MIN, "sensitivity_pp": 5.0},
        "success_definition": {"retail/airline": "DB success (db_match and user_stop/agent_stop)", "telecom": "official task-basis success (official_reward == 1)"},
        "input_dirs": [L["dir"] for L in loaded], "quarantined_dirs": quarantine, "duplicate_units_dropped": dups,
        "noop_sample": {"n": len(noop), "n_pass": sum(x["ok"] for x in noop), "fails": [x for x in noop if not x["ok"]]},
        "cells": res_cells, "telecom_cells": res_tel, "pooled": pools,
        "population": "cells/pooled = common retail/airline panel (85 split tasks, complete blocks); telecom_cells reported separately (W70)", "n_input_files": len(files), "input_files": files,
        "seconds": round(time.time() - t0, 1),
    }
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    jp = OUT / f"dev_{tag}_{utc}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    (OUT / f"dev_{tag}_{utc}.md").write_text(markdown(res, jp))
    print(f"analyze_dev: wrote {jp.relative_to(ROOT)} ({res['seconds']} s)")


def markdown(res: dict, jp: Path) -> str:
    def f(x):
        return f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}]"

    def fr(x):  # non-negative rates
        return f"{x['est']:.1f} [{x['ci95'][0]:.1f}, {x['ci95'][1]:.1f}]"

    def tci(x):
        return f"[{x['t_ci95'][0]:+.1f}, {x['t_ci95'][1]:+.1f}]" if "t_ci95" in x else "n/a"

    def cc(x):
        return f"[{x['crossed_ci95'][0]:+.1f}, {x['crossed_ci95'][1]:+.1f}]" if "crossed_ci95" in x else "n/a"
    cells = res["cells"]
    tl = "; ".join(f"{k}: r {v['all_pp']['rescue']['est']:.1f}, d {v['all_pp']['damage']['est']:.1f}, M {v['all_pp']['M']['est']:.1f}, "
                   f"G {f(v['all_pp']['G'])} pp" for k, v in cells.items() if "all_pp" in v)
    L = [f"**TL;DR** Fork development analysis{' (INCLUDES GATE STATES: testing only)' if res['include_gate'] else ''}, split "
         f"{res['split']['split']}. Two-sided consequences on the full pool (r rescue, d new damage, M = r + d, G = r - d): {tl}. "
         f"No-op sample {res['noop_sample']['n_pass']}/{res['noop_sample']['n']}; quarantined dirs {len(res['quarantined_dirs'])}.",
         "", f"# Fork development analysis ({res['utc']})", "",
         f"Snapshot `{res['snapshot']['id']}` (sha {res['snapshot']['sha256'][:12]}), script sha {res['script']['sha256'][:12]}, "
         f"git {res['script']['git_head'][:10]}, fingerprint {res['input_fingerprint']}, splits {res['split']['manifest_sha256'][:12]}. "
         f"Full numbers: `{jp.relative_to(ROOT)}`.",
         "Units = task x block; pp. Primary intervals over complete shared blocks: block bootstrap with >= 10 blocks, else t over block means (both in the JSON); "
         "secondary: crossed task x block bootstrap (generalisation to new tasks). G_all is the primary endpoint (g_min = eps = 3 pp).", "",
         f"Block rule: {res['block_rule']}. Population: {res['population']}.", "",
         "## Two-sided consequences (full pool = every admitted unit of the retail/airline panel, equal task weight within block, equal block weight)", "",
         "| cell | units | states | r | d | M | G (primary) | G t-over-blocks | G crossed |", "|---|---|---|---|---|---|---|---|---|"]
    for k, v in cells.items():
        if "all_pp" not in v:
            continue
        a = v["all_pp"]
        L.append(f"| {k} | {v['n_units']} | {v['n_states']} | {fr(a['rescue'])} | {fr(a['damage'])} | {fr(a['M'])} | {f(a['G'])} | {tci(a['G'])} | {cc(a['G'])} |")
    L += ["", "Conditional on divergence (ratio of sums over divergent states; a different estimand from the full-pool figures above):", ""]
    for k, v in cells.items():
        c = v.get("conditional_on_divergence_pp")
        if c:
            L.append(f"- {k}: r {fr(c['rescue'])}, d {fr(c['damage'])}, M {fr(c['M'])}, G {f(c['G'])}")
    L += ["", "## Four-branch decomposition on observed divergent states (pivot_four_branch_conditional)", "",
          "Sign dictionary (CONSEQUENCE_ANALYSIS_PLAN §2, W68): A = Y_BB-Y_QB, C = Y_BB-Y_BQ, I = Y_BQ+Y_QB-Y_BB-Y_QQ; "
          "G = A+I, H = Y_QB-Y_QQ = C+I, F = Y_BB-Y_QQ = A+C+I. Numerically identical to W63's A/C/I; the W63 full-pool "
          "A/C/I and Y_QB-Y_QQ / Y_BB-Y_QQ columns are withdrawn (no-divergence units are not four equal outcomes).", "",
          "| cell | A | C | I | G | H | F | strict reversal | full-pool H_policy | full-pool F_policy |", "|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in cells.items():
        c = v.get("conditional_on_divergence_pp")
        if c:
            a = v["all_pp"]
            L.append(f"| {k} | {f(c['A'])} | {f(c['C'])} | {f(c['I'])} | {f(c['G'])} | {f(c['H'])} | {f(c['F'])} | "
                     f"{fr(c['strict_reversal'])} | {f(a['H_policy'])} | {f(a['F_policy'])} |")
    L += ["", "| pool (equal weight per cell, full pool, common complete blocks only) | k blocks | r | d | M | G | G t-over-blocks | H_policy | F_policy |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k, v in res["pooled"].items():
        if "not_poolable" in v:
            L.append(f"| {k} | not poolable: {v['not_poolable']} | | | | | | | |")
        elif v.get("G"):
            L.append(f"| {k} | {v['k_blocks']} | {fr(v['rescue'])} | {fr(v['damage'])} | {fr(v['M'])} | {f(v['G'])} | {tci(v['G'])} | {f(v['H_policy'])} | {f(v['F_policy'])} |")
    if res.get("telecom_cells"):
        L += ["", "## Telecom development (separate population, official task-basis success)", "",
              "| cell | units | states | k blocks | r | d | M | G (full pool) |", "|---|---|---|---|---|---|---|---|"]
        for k, v in res["telecom_cells"].items():
            if "all_pp" in v:
                a = v["all_pp"]
                L.append(f"| {k} | {v['n_units']} | {v['n_states']} | {v['n_blocks']} | {fr(a['rescue'])} | {fr(a['damage'])} | {fr(a['M'])} | {f(a['G'])} |")
            else:
                L.append(f"| {k} | 0 | | | | | | {v.get('note')} |")
    L += ["", "## Coverage and sources", "", "| cell | units found | analysed | states | blocks | tasks per domain | excluded by reason | source dirs |",
          "|---|---|---|---|---|---|---|---|"]
    for k, v in cells.items():
        cv = v.get("coverage", {})
        doms = ", ".join(f"{d} {x['units']} units / {len(x['task_ids'])} tasks" for d, x in cv.get("domains", {}).items())
        L.append(f"| {k} | {cv.get('units_found')} | {cv.get('units_analysed')} | {cv.get('states')} | {len(cv.get('blocks', []))} "
                 f"({','.join(cv.get('blocks', [])[:3])}{'...' if len(cv.get('blocks', [])) > 3 else ''}) | {doms} | "
                 f"{cv.get('excluded_by_reason') or 'none'} | {len(cv.get('source_dirs', []))} |")
    L += ["", "Consequence composition and type breakdown (divergent units):"]
    for k, v in cells.items():
        if v.get("counts"):
            L.append(f"- {k}: {v['counts']}; t* median {v['t_star']['quantiles']['0.5']}")
            for t, b in v["by_type"].items():
                L.append(f"  - {t}: n {b['n_states']}, {b['counts']}, G|type {f(b['G_cond_pp'])}, contribution to G_all {f(b['G_all_contribution_pp'])}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
