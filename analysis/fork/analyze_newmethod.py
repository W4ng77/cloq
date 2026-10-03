"""New-method common panels: frozen analysis (docs/insights/NEWMETHOD_PANEL_PROTOCOL.md, W99v; amendment A1 = W99v-a1).
SKELETON, frozen with the protocol; it refuses to run if the protocol or the manifest sha256 differs from the frozen values below.

Panel A (tau2, U2B ordinary states on the BF16 trajectory; fork_driver mode bank_u):
  inputs  analysis/fork/newmethod/tau2/<model>_<cell>/<blk>/{bank_summary.json, bank_rows.jsonl}
          reference cells (q8, f01-f03): analysis/fork/bank_u/q8_<cell>/<blk>/ U2B rows, admitted only if identical to the
          panel row (state_key, t, source_run, domain, task_id) and run under the Bank U manifest sha (protocol §2.5)
          token scores (local fidelity): analysis/fork/newmethod/token_scores/<model>_<cell>/<blk>/scores.jsonl.gz
          (reference cells: analysis/fork/token_scores/q8_<cell>/<blk>/)
  unit    state (one per task x block); four arms required (never imputed); a task output with a failed no-op is dropped
  rules   strict blocks: a (cell, block) enters only with all 85 states complete (complete-case sensitivity alongside);
          m24 (amendment A3): a frozen analysis mask (MASKS) fixes the population to 83 tasks (airline 13, 44 excluded
          uniformly, all cells and blocks); strict blocks then need all 83; the actual-available-rows analysis (all
          non-missing rows per block, unmasked) is reported alongside, labelled sensitivity
          phase-2 blocks (f04-f06) only if analysis/fork/newmethod/expansion_<model>.json says expand = true
          amendment A6 (primary, every model and cell): an arm error raised on the agent model's own generated message
          (A6_SIGNATURES, read from branches/<state_key>.json; >= 1 branch decision) is Y = 0 as end-to-end; every other
          arm error stays missing; 'strict as preregistered' (no A6) is reported alongside, labelled sensitivity
  stats   analyze_dev.effects + analyze_ghf.add_E (imported), plus D_cc = Y_QB - Y_BB, damage_cc, gain_cc, M_cc;
          all-state task-equal means (analyze_dev.Boot.task_mean: t over block means primary for k < 10, block bootstrap
          alongside, crossed task x block secondary); conditional on an action difference (Boot.ratio, non-exact states)
  contrasts per state, same blocks: D_cc(m1) - D_cc(m2) (= Y_QB(m1) - Y_QB(m2)) and G(m1) - G(m2); Holm over P1-P3 (D_cc)
Panel B (BFCL multi-turn, fork-ext-v1):
  inputs  analysis/fork/newmethod/bfcl/bfcl_<model>_<cell>_<cat>/ and reference analysis/fork/ext/dev/bfcl_q8_<cell>_<cat>/,
          loaded with analyze_ext.load_dir (quarantine) + analyze_ext.replay_guard (W99o), restricted to the 200 panel ids
  stats   ext_r2.r2_effects on divergent items (+ D_cc); all-item G/r/d/M/D_cc with no-divergence items = 0;
          analyze_ext.StratBoot (items within category, B = 2000, seed 20261001), draws shared across cells; item-paired
          contrasts; Holm over P1-P3 (D_cc_all)
Local fidelity (descriptive): exact agreement, agreement category, KLu_0 / KLu_mean over a_B tokens (teacher-forced on the
  common BF16 action), Q-argmax fraction and mean Q log-prob of a_B; M, M_cc, |D_cc| by agreement class and KL tertile
  (cut points from the KL values alone, pooled over admitted cells' phase-1 states); Spearman across cells (descriptive).
Never opens analysis/fork/holdout/.

usage: /data/ziyangs/cloq_work/envs/cloq/bin/python analysis/fork/analyze_newmethod.py [--model q8] [--B 2000] [--dry] [--selftest]  (needs scipy)
  --dry       load and admit everything, print counts only (no estimates), write nothing
  --selftest  synthetic units only (reads no fork output): mask, strict blocks, sensitivity, m24 contrasts, A6; writes nothing
-> analysis/fork/out/newmethod_<model>_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
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
PROTOCOL = ROOT / "docs/insights/NEWMETHOD_PANEL_PROTOCOL.md"
# Amendment A1 (W99v-a1, 2026-10-02): was 9cd5c979... (frozen nmp-v1); only the amended protocol is accepted.
# Amendment A2 (W100e, 2026-10-02): was 28b78509... (A1); m24 manifest registered.
# Amendment A3 (W100e-b, 2026-10-02): was c6603f90... (A2); m24 83-task analysis mask, M1 contrast.
# Amendment A4 (W99t-b, 2026-10-02): was da8b69ba... (A3); kivi_k16v16 kernel-path control, KIVI _fx gates, k4v4 secondary.
# Amendment A5 (W100g, 2026-10-02): was 0dc3143e... (A4); expansion decision: registered cells, KIVI _fx gates, fixed population, KIVI pairing, frozen snapshot.
# Amendment A6 (W100v, 2026-10-03): was f9f8b3a5... (A5); fork-branch arm errors on the agent's own output scored Y = 0.
PROTOCOL_SHA256 = "73bf5538e9316c5c695fc9441115e44e795095b88f1986c4379d8ad9f226d7b5"
# Amendment A6.2 (W100v): exception signatures raised only by validating an AGENT message (repr as cloq/fork.py::run_branch records
# it); S1 = mistral_common's check of an assistant tool call's function name (W99p), S3 = tau2's agent_msg.validate() on an
# empty agent message (W92). Either quote style (repr switches to " when the message contains ').
A6_SIGNATURES = (("invalid_function_name", re.compile(r"""^InvalidFunctionCallException\(['"]Function name was """)),
                 ("empty_agent_message", re.compile(r"""^ValueError\(['"]AssistantMessage must have either content or tool_calls""")))
ARMS4 = ("BB", "BQ", "QB", "QQ")
# Amendment A3 (W100e-b): per-model tau2 analysis mask (frozen file + sha); the population is the manifest tasks minus the mask's
# excluded tasks, uniformly for all cells and blocks.
MASKS = {"m24": ("manifests/fork/newmethod_panel_v1_m24_mask_v1.json", "b03a8a918959e3568315b1ae134f2902580e6af822d80beccb692729c2f82c81")}
MANIFESTS = {"q8": ("manifests/fork/newmethod_panel_v1.json", "7534c6907fa68bc8dab48061d7a2944a719e6e2fa123b639e7a0674c5a6ca201"),
             "m24": ("manifests/fork/newmethod_panel_v1_m24.json", "53295b64fbcc7c4501ea8883aa34ce922a5ca0e23c5636c8bb1c4efe38e3ff4c")}
BANK_U_SHA256 = "e236ee6483e723ffe8acd743ff2f5af8c1f92b49a39a7e721359c960ee12a907"
NM = ROOT / "analysis/fork/newmethod"
REF_TAU2 = {"q8": ("gptq_w4_d1", "awq_w4", "kvq_int8")}
REF_BFCL = {"q8": ("gptq_w4_d1", "awq_w4_d1", "kvq_int4", "gptq_w3")}
# Amendment A1.1: rotation cells (all KV16r). spinquant_w4 retired (rotation does not move under a rotation-invariant
# W16A16 loss); spinqoff_w4 not built (reported "not run").
NEW_CELLS = ("quarot_w4", "quarot_w4a4", "quarot_w16", "spinquant_w4a4", "spinquant_w16", "kivi_k2v2", "kivi_k4v4", "kivi_k16v16")  # A4.1: kivi_k16v16
NOT_RUN = {"spinquant_w4": "retired (amendment A1.1)", "spinqoff_w4": "not built (amendment A1.1)"}
# Primary contrast family (protocol §7 as amended by A1.2). P3's KIVI cell falls back to kivi_k4v4 only if kivi_k2v2 is not
# admitted (gate). P1 confound (named): calibration data differ (WikiText-2 vs calib_fp_traj_c1).
PRIMARY = [("P1", "quarot_w4", "gptq_w4_d1"), ("P2", "spinquant_w4a4", "quarot_w4a4"), ("P3", "kivi_k2v2", "kvq_int8")]
BFCL_PRIMARY = [("P1", "quarot_w4", "gptq_w4_d1"), ("P2", "spinquant_w4a4", "quarot_w4a4"), ("P3", "kivi_k2v2", "kvq_int4")]
SECONDARY = [("T1", "quarot_w4", "quarot_w16"), ("T2", "spinquant_w4a4", "spinquant_w16"), ("T3", "quarot_w4a4", "quarot_w16"),
             ("K2", "kivi_k4v4", "kvq_int8")]
# Amendment A3: m24 (second family) cells and contrast. One primary contrast per panel (Holm over one = unadjusted):
# M1 gptq_w4_d1 - rtn_w4 on tau2 D_cc (t over block-mean differences, blocks complete in both cells) and on BFCL D_cc_all.
M24_CELLS = ("rtn_w4", "gptq_w4_d1")
CONTRASTS = {"q8": {"primary": PRIMARY, "bfcl_primary": BFCL_PRIMARY, "secondary": SECONDARY},
             "m24": {"primary": [("M1", "gptq_w4_d1", "rtn_w4")], "bfcl_primary": [("M1", "gptq_w4_d1", "rtn_w4")], "secondary": []}}
CATS = ("base", "miss_param", "miss_func", "long_context")
ALL_KEYS = ["G", "H", "F", "D_cc", "I", "rescue", "damage", "M", "damage_cc", "gain_cc", "M_cc", "offdiag", "strict_reversal", "exact"]
BFCL_ALL = ["G", "rescue", "damage", "M", "D_cc", "damage_cc", "gain_cc", "M_cc"]
BFCL_COND = ["G", "H", "F", "D_cc", "I", "offdiag", "strict_reversal"]


def _load(name: str, rel: str):
    sp = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    return mod


AE = _load("analyze_ext", "analysis/fork/analyze_ext.py")
AD = AE.AD
ER = _load("ext_r2", "analysis/fork/ext_r2.py")
sys.path.insert(0, str(ROOT / "analysis/fork"))
import analyze_ghf as GHF  # noqa: E402

AE.ARMS = tuple(AE.ARMS) + tuple(c for c in NEW_CELLS + M24_CELLS if c not in AE.ARMS)  # parse_dir must know the new cell names


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def guard(model: str) -> dict:
    ps = sha(PROTOCOL)
    if ps != PROTOCOL_SHA256:
        raise SystemExit(f"analyze_newmethod: protocol sha256 {ps} != frozen {PROTOCOL_SHA256}; amend the protocol and this constant together")
    if model not in MANIFESTS:
        raise SystemExit(f"analyze_newmethod: no frozen manifest for model {model} (add it by a dated protocol amendment)")
    rel, want = MANIFESTS[model]
    ms = sha(ROOT / rel)
    if ms != want:
        raise SystemExit(f"analyze_newmethod: manifest sha256 {ms} != frozen {want}")
    g = {"protocol_sha256": ps, "manifest": rel, "manifest_sha256": ms}
    if model in MASKS:
        mrel, mwant = MASKS[model]
        mss = sha(ROOT / mrel)
        if mss != mwant:
            raise SystemExit(f"analyze_newmethod: mask sha256 {mss} != frozen {mwant}")
        mk = json.loads((ROOT / mrel).read_text())
        if mk["applies_to"]["manifest_sha256"] != ms:
            raise SystemExit("analyze_newmethod: mask was frozen for a different manifest")
        g.update(mask=mrel, mask_sha256=mss)
    return g


def population(model: str, man: dict) -> tuple[set, list]:
    """Analysis population (tasks) = manifest tasks minus the frozen mask's excluded tasks (amendment A3)."""
    tasks = {f"{r['domain']}|{r['task_id']}" for r in man["rows"]}
    if model not in MASKS:
        return tasks, []
    mk = json.loads((ROOT / MASKS[model][0]).read_text())
    exc = list(mk["excluded_tasks"])
    pop = tasks - set(exc)
    assert pop == set(mk["population"]) and len(pop) == mk["n_tasks_population"], "mask population != manifest minus excluded"
    return pop, exc


def no_holdout(p: Path) -> Path:
    assert "/holdout" not in str(p), p
    return p


# ---------------------------------------------------------------------------- amendment A6
def a6_class(br: dict | None) -> tuple[str, str]:
    """A6.2: ('agent_output', signature) iff the arm's branch error record matches A6_SIGNATURES and the branch logged >= 1
    agent decision before the error (so the offending message was produced in the branch); else ('missing', reason)."""
    if not isinstance(br, dict) or "error" not in br:
        return "missing", "no branch error record"
    if br.get("infra_cause"):
        return "missing", f"infra_cause {br['infra_cause']}"
    e = str(br["error"])
    for name, rx in A6_SIGNATURES:
        if rx.search(e):
            return ("agent_output", name) if int(br.get("n_decisions") or 0) >= 1 else ("missing", f"{name} before any branch decision")
    return "missing", (re.match(r"[\w.]+", e) or [e[:40]])[0]


def a6_resolve(x: dict, branches: dict) -> tuple[dict | None, dict]:
    """A6.2/A6.3 on one bank row with an undefined arm: run arms with an error -> a6_class on their branch record; a reused
    arm ('reuse=XX', §2.3 identity under protocol A) takes XX's value. (four defined arms or None, per-arm classes)."""
    Y, src, cls = dict(x.get("Y") or {}), x.get("arm_source") or {}, {}
    for a in ARMS4:
        if Y.get(a) is None and str(src.get(a, "")).startswith("error"):
            cls[a] = a6_class(branches.get(a))
            Y[a] = 0 if cls[a][0] == "agent_output" else None
    for a in ARMS4:
        s = str(src.get(a, ""))
        if Y.get(a) is None and s.startswith("reuse=") and Y.get(s[6:]) is not None:
            Y[a], cls[a] = Y[s[6:]], ("reuse", s)
    return (Y if all(Y.get(a) in (0, 1) for a in ARMS4) else None), cls


def strict_prereg(raw: dict) -> dict:
    """A6.3 sensitivity 'strict as preregistered': every unit that A6 completed is excluded again, exactly as without A6."""
    drop = ("Y", "E", "exact", "category", "a6")
    return {c: [{**{k: v for k, v in u.items() if k not in drop}, "excluded": "arm missing"} if "a6" in u else u for u in us]
            for c, us in raw.items()}


def a6_report(raw: dict, pop: set) -> dict:
    """A6.3 reporting: per cell and block, states / arms scored Y = 0 under A6 (by signature, with tasks) and the arm errors
    that stayed missing (by reason)."""
    rep: dict = {}
    for c, us in sorted(raw.items()):
        for u in us:
            k6 = "a6" if "a6" in u else "a6_missing" if "a6_missing" in u else None
            if not k6:
                continue
            r = rep.setdefault(c, {}).setdefault(u["block"], {"states_reclassified": 0, "arms_reclassified": 0, "arms_reused": 0,
                                                               "by_signature": {}, "states_still_missing": 0, "missing_reasons": {}, "states": []})
            r["states_reclassified" if k6 == "a6" else "states_still_missing"] += 1
            for a, (kind, s) in sorted(u[k6].items()):
                if kind == "agent_output":
                    r["arms_reclassified"] += 1
                    r["by_signature"][s] = r["by_signature"].get(s, 0) + 1
                elif kind == "reuse":
                    r["arms_reused"] += 1
                else:
                    r["missing_reasons"][s] = r["missing_reasons"].get(s, 0) + 1
            r["states"].append(f"{u['task'].replace('|', ':')} {'Y=0' if k6 == 'a6' else 'missing'} {','.join(sorted(u[k6]))}" + ("" if u["task"] in pop else " (outside population)"))
    return rep


# ---------------------------------------------------------------------------- effects
def unit_effects(Y: dict, exact: bool) -> dict:
    E = AD.effects(Y, True)
    GHF.add_E({"Y": Y, "E": E})
    E.update(D_cc=Y["QB"] - Y["BB"], damage_cc=int(Y["BB"] == 1 and Y["QB"] == 0), gain_cc=int(Y["BB"] == 0 and Y["QB"] == 1),
             exact=int(bool(exact)), nonexact=int(not exact))
    E["M_cc"] = E["damage_cc"] + E["gain_cc"]
    return E


# ---------------------------------------------------------------------------- panel A loaders
def expansion_ok(model: str) -> bool:
    p = NM / f"expansion_{model}.json"
    return p.exists() and json.loads(p.read_text()).get("expand") is True


def load_tau2(model: str, man: dict, blocks: set | None = None, only: set | None = None, a6: bool = False) -> tuple[dict, dict]:
    """blocks / only (--blocks / --cells): restrict what is loaded; a cell outside `only` is never opened. Default: all.
    a6 (amendment A6; main() passes True for the primary): a row whose only gap is arm errors is completed by a6_resolve
    from its branch records; default False = the loader exactly as before A6 (strict as preregistered)."""
    rows = {r["state_key"]: r for r in man["rows"]}
    allow2 = expansion_ok(model)
    cells: dict = defaultdict(list)
    log: dict = defaultdict(list)

    def take(cell, blk, d: Path, src: str, sha_want: str):
        sp = d / "bank_summary.json"
        if not sp.exists():
            log[cell].append(f"{blk}: not finished")
            return
        s = json.loads(sp.read_text())
        if s.get("manifest_sha256") != sha_want:
            log[cell].append(f"{blk}: manifest sha {s.get('manifest_sha256')} != {sha_want} (refused)")
            return
        if s["noop"]["n_pass"] != s["noop"]["n"]:
            log[cell].append(f"{blk}: QUARANTINED (no-op {s['noop']})")
            return
        for line in (d / "bank_rows.jsonl").read_text().splitlines():
            if not line.strip():
                continue
            x = json.loads(line)
            if x.get("sub") != "U2B" or x.get("model") != model:
                continue
            r = rows.get(x["state_key"])
            if r is None or any(x.get(k) != r[k] for k in ("t", "source_run", "domain", "task_id", "block")):
                log[cell].append(f"{blk}: row {x['state_key']} not identical to the panel row (refused)")
                continue
            u = {"cell": cell, "block": blk, "phase": r["phase"], "task": f"{r['domain']}|{r['task_id']}", "state_key": r["state_key"],
                 "domain": r["domain"], "div": True, "source": src}
            Y = x.get("Y") or {}
            if "missing_reason" in x or "error" in x or any(Y.get(a) is None for a in ("BB", "BQ", "QB", "QQ")):
                Y6, cls = (a6_resolve(x, _branches(d, x["state_key"])) if a6 and "missing_reason" not in x and "error" not in x
                           else (None, {}))
                if Y6 is not None:
                    u.update(Y=Y6, E=unit_effects(Y6, x["exact_agreement"]), exact=x["exact_agreement"], category=x.get("agreement_category"), a6=cls)
                else:
                    u["excluded"] = str(x.get("missing_reason") or x.get("error") or "arm missing")[:160]
                    if cls:
                        u["a6_missing"] = cls
            else:
                u.update(Y=Y, E=unit_effects(Y, x["exact_agreement"]), exact=x["exact_agreement"], category=x.get("agreement_category"))
            cells[cell].append(u)

    def _branches(d: Path, sk: str) -> dict:
        p = no_holdout(d) / "branches" / f"{sk}.json"
        return json.loads(p.read_text()) if p.exists() else {}

    base = NM / "tau2"
    for d in sorted(base.glob(f"{model}_*/*")) if base.exists() else []:
        cell, blk = d.parent.name[len(model) + 1:], d.name
        if blk not in man["tau2"]["phase"] or (only and cell not in only):
            continue
        if blocks and blk not in blocks:
            log[cell].append(f"{blk}: not requested (--blocks)")
            continue
        if man["tau2"]["phase"][blk] == 2 and not allow2:
            log[cell].append(f"{blk}: phase 2 without an expand=true decision record (refused)")
            continue
        take(cell, blk, no_holdout(d), "panel", MANIFESTS[model][1])
    for cell in REF_TAU2.get(model, ()):
        for blk in ("f01", "f02", "f03"):
            if (only and cell not in only) or (blocks and blk not in blocks):
                continue
            if any(u["block"] == blk for u in cells.get(cell, [])):
                continue  # a panel-run reference block takes precedence (not expected for f01-f03)
            take(cell, blk, no_holdout(ROOT / "analysis/fork/bank_u" / f"{model}_{cell}" / blk), "bank_u", BANK_U_SHA256)
    return dict(cells), dict(log)


def strict_blocks(units: list[dict], n_tasks: int, pop: set | None = None) -> tuple[list[dict], dict]:
    """A block enters only if it has a complete four-arm state for every task of the population (n_tasks; with a mask,
    exactly the set pop). Missing arms are never imputed; a newly missing branch fails the block."""
    by = defaultdict(list)
    for u in units:
        by[u["block"]].append(u)
    keep, info = [], {}
    for blk, us in sorted(by.items()):
        ok = [u for u in us if "excluded" not in u]
        full = len(ok) == n_tasks and len({u["task"] for u in ok}) == n_tasks and (pop is None or {u["task"] for u in ok} == pop)
        info[blk] = {"rows": len(us), "complete": len(ok), "population": n_tasks, "admitted": full}
        if any("a6" in u for u in ok):
            info[blk]["complete_via_a6"] = sum(1 for u in ok if "a6" in u)  # amendment A6: states completed by Y = 0 arms
        if not full:
            info[blk]["incomplete_tasks"] = sorted((pop or {u["task"] for u in us}) - {u["task"] for u in ok})[:20]
        if full:
            keep += ok
    return keep, info


def apply_population(raw: dict, pop: set, n_tasks: int) -> tuple[dict, dict, dict, dict]:
    """Primary (strict, on the frozen population), complete-case (population, any block) and the amendment-A3 sensitivity
    'actual available rows' (every non-missing four-arm row of every block, unmasked, no strictness)."""
    cells, info, cc, avail = {}, {}, {}, {}
    for c, us in raw.items():
        inpop = [u for u in us if u["task"] in pop]
        cells[c], info[c] = strict_blocks(inpop, n_tasks, pop)
        cc[c] = [u for u in inpop if "excluded" not in u]
        avail[c] = [u for u in us if "excluded" not in u]
    return cells, info, cc, avail


def load_scores(model: str, cell: str, blk: str, ref: bool) -> dict:
    d = (ROOT / "analysis/fork/token_scores" / f"{model}_{cell}" / blk) if ref else (NM / "token_scores" / f"{model}_{cell}" / blk)
    p = no_holdout(d) / "scores.jsonl.gz"
    out = {}
    if not p.exists():
        return out
    with gzip.open(p, "rt") as f:
        for line in f:
            r = json.loads(line)
            if r.get("sub") not in (None, "U2B"):
                continue
            tok = ((r.get("acts") or {}).get("a_B") or {}).get("tok") or []
            if not tok:
                continue
            kl = [t["KLu_BQ"] for t in tok]
            out[r["state_key"]] = {"KLu_0": kl[0], "KLu_mean": float(np.mean(kl)), "argmaxQ_frac": float(np.mean([t["rank_Q"] == 1 for t in tok])),
                                   "lpQ_aB_mean": float(np.mean([t["lp_Q"] for t in tok]))}
    return out


# ---------------------------------------------------------------------------- panel A statistics
def boot_for(units: list[dict], B: int):
    bo = defaultdict(set)
    for u in units:
        bo[u["task"]].add(u["block"])
    return AD.Boot(sorted(bo), {t: sorted(v) for t, v in bo.items()}, B=B)


def tau2_cell(units: list[dict], B: int) -> dict:
    boot = boot_for(units, B)
    res = {"n_states": len(units), "k_blocks": len(boot.blocks), "blocks": boot.blocks, "all_states_pp": {}, "nonexact_pp": {}}
    for s in ALL_KEYS:
        pt, dr = boot.task_mean(*boot.arrays(units, s))
        res["all_states_pp"][s] = AD.summarise(pt, dr, boot=boot)
    ne = [u for u in units if not u["exact"]]
    res["n_nonexact"] = len(ne)
    for s in ("G", "H", "F", "D_cc", "I", "M", "M_cc", "offdiag", "strict_reversal"):
        if ne:
            pt, dr = boot.ratio(*boot.arrays(ne, s))
            res["nonexact_pp"][s] = AD.summarise(pt, dr, boot=boot)
    res["table3"] = ER.table3(units)
    res["patterns16"] = ER.patterns16(units)
    return res


def t_pvalue(bm: np.ndarray) -> float | None:
    from scipy.stats import ttest_1samp
    bm = bm[np.isfinite(bm)]
    return float(ttest_1samp(bm, 0.0).pvalue) if len(bm) >= 2 and np.std(bm) > 0 else (1.0 if len(bm) >= 2 else None)


def tau2_contrast(a: list[dict], b: list[dict], B: int, match_tasks: bool = False) -> dict:
    """Primary: a, b are strict-admitted units, so common blocks are complete in both cells. match_tasks (sensitivity only):
    pair the states present in both cells within the common blocks."""
    ib = {(u["task"], u["block"]): u for u in b}
    common_blocks = sorted({u["block"] for u in a} & {u["block"] for u in b})
    pairs = []
    for u in a:
        v = ib.get((u["task"], u["block"]))
        if v is not None and u["block"] in common_blocks:
            assert u["state_key"] == v["state_key"]
            pairs.append({"task": u["task"], "block": u["block"], "E": {k: u["E"][k] - v["E"][k] for k in ("D_cc", "G", "M_cc", "M")}})
    if len(common_blocks) < 2:
        return {"not_estimable": f"{len(common_blocks)} common complete block(s)", "common_blocks": common_blocks}
    boot = boot_for(pairs, B)
    out = {"common_blocks": common_blocks, "n_states": len(pairs)}
    for k in ("D_cc", "G", "M_cc", "M"):
        pt, dr = boot.task_mean(*boot.arrays(pairs, k))
        out[k] = AD.summarise(pt, dr, boot=boot)
        out[k]["t_p_two_sided"] = t_pvalue(np.asarray(boot.last["block_means"], float))
    return out


def tau2_contrasts(cells: dict, CT: dict, B: int) -> tuple[dict, dict]:
    """Primary + secondary contrasts on admitted units and the Holm-adjusted primary family (t p on D_cc)."""
    con = {}
    for lab, x, y in CT["primary"] + CT["secondary"]:
        if lab == "P3" and not cells.get("kivi_k2v2") and cells.get("kivi_k4v4"):
            x = "kivi_k4v4"  # protocol §1: gate fallback
        con[lab] = tau2_contrast(cells[x], cells[y], B) if cells.get(x) and cells.get(y) else {"not_estimable": "cell not admitted", "cells": [x, y]}
        con[lab]["cells"] = [x, y]
    return con, holm({lab: con[lab].get("D_cc", {}).get("t_p_two_sided") for lab, _, _ in CT["primary"] if "D_cc" in con[lab]})


def holm(ps: dict) -> dict:
    items = sorted((p, k) for k, p in ps.items() if p is not None)
    m, out, run = len(items), {}, 0.0
    for i, (p, k) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = round(run, 6)
    return out


def fidelity(cells: dict, scores: dict) -> dict:
    allkl = [scores[c][u["state_key"]]["KLu_mean"] for c, us in cells.items() for u in us
             if u["phase"] == 1 and u["state_key"] in scores.get(c, {})]
    cuts = [float(x) for x in np.quantile(allkl, [1 / 3, 2 / 3])] if len(allkl) >= 3 else None
    res = {"KLu_mean_tertile_cuts": cuts, "n_scored_phase1": len(allkl), "cells": {}}
    for c, us in cells.items():
        sc = scores.get(c, {})
        r = {"n": len(us), "exact_rate": float(np.mean([u["exact"] for u in us])) if us else None,
             "categories": {str(k): sum(1 for u in us if u.get("category") == k) for k in sorted({u.get("category") for u in us}, key=str)},
             "n_scored": sum(1 for u in us if u["state_key"] in sc)}
        for f in ("KLu_0", "KLu_mean", "argmaxQ_frac", "lpQ_aB_mean"):
            v = [sc[u["state_key"]][f] for u in us if u["state_key"] in sc]
            r[f] = {"mean": float(np.mean(v)), "median": float(np.median(v))} if v else None
        strata = {"exact": [u for u in us if u["exact"]], "nonexact": [u for u in us if not u["exact"]]}
        if cuts:
            for i, (lo, hi) in enumerate([(-np.inf, cuts[0]), (cuts[0], cuts[1]), (cuts[1], np.inf)]):
                strata[f"KL_t{i + 1}"] = [u for u in us if u["state_key"] in sc and lo < sc[u["state_key"]]["KLu_mean"] <= hi]
        r["by_stratum"] = {k: {"n": len(v), "M": float(np.mean([u["E"]["M"] for u in v])) if v else None,
                               "M_cc": float(np.mean([u["E"]["M_cc"] for u in v])) if v else None,
                               "abs_D_cc": float(np.mean([abs(u["E"]["D_cc"]) for u in v])) if v else None} for k, v in strata.items()}
        res["cells"][c] = r
    xs = [(r["KLu_mean"]["mean"], np.mean([u["E"]["M_cc"] for u in cells[c]])) for c, r in res["cells"].items() if r["KLu_mean"]]
    if len(xs) >= 3:
        from scipy.stats import spearmanr
        rho = spearmanr([x[0] for x in xs], [x[1] for x in xs])
        res["across_cells_spearman_KLu_mean_vs_M_cc"] = {"rho": float(rho.correlation), "n_cells": len(xs), "label": "descriptive"}
    return res


# ---------------------------------------------------------------------------- panel B
def load_bfcl(model: str, man: dict, only: set | None = None) -> tuple[dict, dict]:
    panel = {f"bfcl_{c}|{i}" for c in CATS for i in man["categories"][c]["nmp_v1"]}
    dirs = []
    if (NM / "bfcl").exists():
        dirs += [d for d in sorted((NM / "bfcl").glob(f"bfcl_{model}_*")) if d.is_dir()]
    dirs += [d for d in sorted((ROOT / "analysis/fork/ext/dev").glob(f"bfcl_{model}_*"))
             if d.is_dir() and AE.parse_dir(d.name)[2] in REF_BFCL.get(model, ())]
    dirs = [d for d in dirs if not only or AE.parse_dir(d.name)[2] in only]  # --cells: other cells are never opened
    loaded = [AE.load_dir(no_holdout(d)) for d in dirs]
    done = [L for L in loaded if not L["incomplete"]]
    guard_counts = AE.replay_guard(done, "analyze_newmethod") if hasattr(AE, "replay_guard") else "replay_guard unavailable"
    cells: dict = defaultdict(list)
    log = {"quarantined": [L["dir"] for L in done if L["quarantined"]], "incomplete": [L["dir"] for L in loaded if L["incomplete"]],
           "replay_guard": guard_counts}
    for L in done:
        if L["quarantined"]:
            continue
        for u in L["units"]:
            if u["task"] not in panel:
                continue
            if "excluded" not in u:
                if u["div"]:
                    E = ER.r2_effects(u["Y"])
                    E.update({k: v for k, v in AD.effects(u["Y"], True).items() if k in ("rescue", "damage", "M")})
                    E.update(D_cc=u["Y"]["QB"] - u["Y"]["BB"], damage_cc=int(u["Y"]["BB"] == 1 and u["Y"]["QB"] == 0),
                             gain_cc=int(u["Y"]["BB"] == 0 and u["Y"]["QB"] == 1))
                else:
                    E = {k: 0 for k in ("G", "rescue", "damage", "M", "D_cc", "damage_cc", "gain_cc")}
                E["M_cc"] = E["damage_cc"] + E["gain_cc"]
                u["E"] = E
            cells[L["arm"]].append(u)
    for c, us in cells.items():
        log.setdefault("coverage", {})[c] = {"items": len({u["task"] for u in us}), "excluded": sum(1 for u in us if "excluded" in u),
                                             "divergent": sum(1 for u in us if u.get("div") and "excluded" not in u)}
    return dict(cells), log


def bfcl_stats(cells: dict, B: int, contrasts: dict | None = None) -> dict:
    contrasts = contrasts or CONTRASTS["q8"]
    strata = defaultdict(set)
    for us in cells.values():
        for u in us:
            strata[u["stratum"]].add(u["task"])
    boot = AE.StratBoot({s: sorted(v) for s, v in strata.items()}, B=B)
    res, draws = {}, {}
    for c, us in sorted(cells.items()):
        ok = [u for u in us if "excluded" not in u]
        div = [u for u in ok if u["div"]]
        r = {"n_items": len(ok), "n_div": len(div), "all_items_pp": {}, "cond_div_pp": {}}
        for k in BFCL_ALL:
            pt, dr = boot.mean(*boot.arrays(ok, k))
            draws[(c, k)] = (pt, dr)
            r["all_items_pp"][k] = AD.summarise(pt, dr)
        for k in BFCL_COND:
            if div:
                pt, dr = boot.mean(*boot.arrays(div, k))
                r["cond_div_pp"][k] = AD.summarise(pt, dr)
        r["table3"], r["patterns16"] = ER.table3(div), ER.patterns16(div)
        res[c] = r
    con = {}
    for lab, a, b in contrasts["bfcl_primary"] + contrasts["secondary"]:
        if a not in cells or b not in cells:
            con[lab] = {"not_estimable": "cell not admitted", "cells": [a, b]}
            continue
        ia = {u["task"]: u for u in cells[a] if "excluded" not in u}
        ib = {u["task"]: u for u in cells[b] if "excluded" not in u}
        common = sorted(set(ia) & set(ib))
        pr = [{"task": t, "E": {k: ia[t]["E"][k] - ib[t]["E"][k] for k in ("D_cc", "G", "M_cc", "M")}} for t in common]
        con[lab] = {"cells": [a, b], "n_items": len(common)}
        for k in ("D_cc", "G", "M_cc", "M"):
            pt, dr = boot.mean(*boot.arrays(pr, k))
            con[lab][k] = AD.summarise(pt, dr)
            d = np.asarray(dr)
            con[lab][k]["boot_p_two_sided"] = float(min(1.0, 2 * min((d <= 0).mean(), (d >= 0).mean())))
    fam = {lab: con[lab].get("D_cc", {}).get("boot_p_two_sided") for lab, _, _ in contrasts["bfcl_primary"] if "D_cc" in con[lab]}
    return {"cells": res, "contrasts": con, "holm_primary_D_cc_all": holm(fam)}


# ---------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", default="q8")
    ap.add_argument("--B", type=int, default=AD.B_BOOT)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--blocks", help="comma list of panel A blocks to load, e.g. f01,f02,f03 (phase 1 only: an interim run while phase 2 "
                                     "runs); default every block the rules admit. Rules are unchanged within the loaded blocks")
    ap.add_argument("--cells", help="comma list of cells to load (tau2 panel/reference and BFCL); other cells' outputs are never opened")
    ap.add_argument("--tag", help="output name prefix (default newmethod_<model>)")
    a = ap.parse_args()
    if a.selftest:
        selftest(a.B)
        return
    g = guard(a.model)
    CT = CONTRASTS.get(a.model, CONTRASTS["q8"])
    man = json.loads((ROOT / g["manifest"]).read_text())
    blocks = set(a.blocks.split(",")) if a.blocks else None
    only = set(a.cells.split(",")) if a.cells else None
    known = set(NEW_CELLS + M24_CELLS + REF_TAU2.get(a.model, ()) + REF_BFCL.get(a.model, ()))
    if (blocks and not blocks <= set(man["tau2"]["phase"])) or (only and not only <= known):
        raise SystemExit(f"analyze_newmethod: unknown --blocks {blocks} or --cells {only}")
    restrict = {"blocks": sorted(blocks) if blocks else "all", "cells": sorted(only) if only else "all"}
    pop, excluded = population(a.model, man)
    n_tasks = len(pop)
    t0 = time.time()
    raw, tlog = load_tau2(a.model, man, blocks, only, a6=True)  # amendment A6: primary
    pre = strict_prereg(raw)  # A6.3 sensitivity; must equal the loader without A6 unit by unit (A6 touches nothing else)
    raw0, _ = load_tau2(a.model, man, blocks, only)
    sig = lambda R_: {c: [(u["state_key"], "excluded" in u, u.get("Y")) for u in us] for c, us in R_.items()}  # noqa: E731
    assert sig(pre) == sig(raw0), "A6: strict-as-preregistered view differs from the loader without A6"
    a6rep = a6_report(raw, pop)
    cells, blocks_info, cc_cells, avail_cells = apply_population(raw, pop, n_tasks)
    pcells, pblocks, _, _ = apply_population(pre, pop, n_tasks)
    bcells, blog = load_bfcl(a.model, man, only)
    if a.dry:
        print(json.dumps({"guard": g, "restrict": restrict, "population": {"n_tasks": n_tasks, "excluded_by_mask": excluded}, "not_run": NOT_RUN, "tau2_blocks": blocks_info, "tau2_log": tlog, "bfcl_log": blog,
                          "expansion_ok": expansion_ok(a.model), "a6": a6rep, "tau2_blocks_strict_prereg": pblocks}, indent=1, default=str))
        return
    R = {"guard": g, "script_sha256": sha(Path(__file__)), "git": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "restrict": restrict, "B": a.B, "seed": AD.SEED, "not_run": NOT_RUN, "expansion_ok": expansion_ok(a.model), "tau2": {"population": {"n_tasks": n_tasks, "excluded_by_mask": excluded,
                                                                                                "label": "conditional population (amendment A3)" if excluded else "full panel"},
                                                                                 "blocks": blocks_info, "log": tlog, "cells": {}, "complete_case": {},
                                                                                 "sensitivity_available_rows": {}}}
    for c, us in sorted(cells.items()):
        if us:
            R["tau2"]["cells"][c] = tau2_cell(us, a.B)
        if cc_cells[c]:
            R["tau2"]["complete_case"][c] = {k: v for k, v in tau2_cell(cc_cells[c], a.B).items() if k in ("n_states", "k_blocks", "all_states_pp")}
        if excluded and avail_cells[c]:
            R["tau2"]["sensitivity_available_rows"][c] = {"label": "SENSITIVITY: actual available rows (non-missing four-arm rows per block, no mask, no strictness)",
                                                          **{k: v for k, v in tau2_cell(avail_cells[c], a.B).items() if k in ("n_states", "k_blocks", "all_states_pp")}}
    con, R["tau2"]["holm_primary_D_cc"] = tau2_contrasts(cells, CT, a.B)
    R["tau2"]["contrasts"] = con
    R["tau2"]["a6"] = {"rule": "amendment A6: arm errors on the agent's own message (A6_SIGNATURES, >= 1 branch decision) scored Y = 0",
                       "per_cell_block": a6rep}
    pcon, phl = tau2_contrasts(pcells, CT, a.B)
    R["tau2"]["sensitivity_strict_prereg"] = {"label": "SENSITIVITY: strict as preregistered (§7/A3.3 without A6: every arm error fails its block)",
                                              "blocks": pblocks, "contrasts": pcon, "holm_primary_D_cc": phl,
                                              "cells": {c: {k: v for k, v in tau2_cell(us, a.B).items() if k in ("n_states", "k_blocks", "all_states_pp")}
                                                        for c, us in sorted(pcells.items()) if us}}
    if excluded:
        sc = {}
        for lab, x, y in CT["primary"]:
            sc[lab] = (tau2_contrast(avail_cells[x], avail_cells[y], a.B, match_tasks=True) if avail_cells.get(x) and avail_cells.get(y)
                       else {"not_estimable": "cell has no rows"})
            sc[lab].update(cells=[x, y], label="SENSITIVITY: actual available rows")
        R["tau2"]["sensitivity_available_rows_contrasts"] = sc
    scores = {}
    for c, us in cells.items():
        ref = all(u["source"] == "bank_u" for u in us if u["phase"] == 1)
        scores[c] = {}
        for blk in sorted({u["block"] for u in us}):
            scores[c].update(load_scores(a.model, c, blk, ref and blk in ("f01", "f02", "f03")))
    R["fidelity"] = fidelity(cells, scores)
    R["bfcl"] = {"log": blog, **(bfcl_stats(bcells, a.B, CT) if bcells else {"cells": {}})}
    R["seconds"] = time.time() - t0
    OUT.mkdir(parents=True, exist_ok=True)
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    tag = a.tag or f"newmethod_{a.model}"
    jp = OUT / f"{tag}_{utc}.json"
    jp.write_text(json.dumps(R, indent=1, default=str))
    (OUT / f"{tag}_{utc}.md").write_text(markdown(R, jp))
    print("wrote", jp.relative_to(ROOT))


def markdown(R: dict, jp: Path) -> str:
    def f(x):
        if not x:
            return "–"
        return f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}]" + (f" (crossed {x['crossed_ci95'][0]:+.1f}, {x['crossed_ci95'][1]:+.1f})" if x.get("crossed_ci95") else "")
    L = [f"# New-method panels ({R['guard']['manifest']})", "",
         f"Protocol sha256 `{R['guard']['protocol_sha256']}`, manifest sha256 `{R['guard']['manifest_sha256']}`, script `{R['script_sha256'][:12]}`, "
         f"git `{R['git'][:10]}`. Phase-2 admitted: {R['expansion_ok']}. Loaded (--blocks/--cells): {R.get('restrict')}. "
         "pp; primary interval per analyze_dev.summarise.", "",
         "## τ² (U2B states), all states, task-equal", "", "| cell | k | n | D_cc | G | H | F | I | M | M_cc | exact |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c, r in R["tau2"]["cells"].items():
        s = r["all_states_pp"]
        L.append(f"| {c} | {r['k_blocks']} | {r['n_states']} | " + " | ".join(f(s[k]) for k in ("D_cc", "G", "H", "F", "I", "M", "M_cc", "exact")) + " |")
    L += ["", "## τ² contrasts (same states)", "", "| id | cells | blocks | ΔD_cc | ΔG | t p | Holm |", "|---|---|---|---|---|---|---|"]
    for lab, x in R["tau2"]["contrasts"].items():
        if "D_cc" in x:
            L.append(f"| {lab} | {' − '.join(x['cells'])} | {','.join(x['common_blocks'])} | {f(x['D_cc'])} | {f(x['G'])} | {x['D_cc'].get('t_p_two_sided')} | {R['tau2']['holm_primary_D_cc'].get(lab, '–')} |")
        else:
            L.append(f"| {lab} | {' − '.join(x['cells'])} | – | {x.get('not_estimable')} | | | |")
    a6 = R["tau2"].get("a6", {}).get("per_cell_block", {})
    L += ["", "## Amendment A6: arm errors on the agent's own message scored Y = 0", "",
          "| cell | block | states Y=0 | arms Y=0 (+ reused) | signatures | arm errors still missing | states |", "|---|---|---|---|---|---|---|"]
    L += [f"| {c} | {b} | {r['states_reclassified']} | {r['arms_reclassified']} (+{r['arms_reused']}) | {r['by_signature'] or '–'} | "
          f"{r['states_still_missing']} {r['missing_reasons'] or ''} | {'; '.join(r['states'])} |" for c, bs in a6.items() for b, r in bs.items()] or ["| – | | 0 | 0 | | 0 | |"]
    ps = R["tau2"].get("sensitivity_strict_prereg", {})
    L += ["", "SENSITIVITY, strict as preregistered (§7/A3.3 without A6): admitted blocks "
          + "; ".join(f"{c} {','.join(b for b, i in bi.items() if i['admitted']) or 'none'}" for c, bi in ps.get("blocks", {}).items()), "",
          "| id | cells | blocks | ΔD_cc | t p | Holm |", "|---|---|---|---|---|---|"]
    L += [f"| {lab} | {' − '.join(x['cells'])} | {','.join(x.get('common_blocks', [])) or '–'} | "
          + (f"{f(x['D_cc'])} | {x['D_cc'].get('t_p_two_sided')} | {ps['holm_primary_D_cc'].get(lab, '–')} |" if "D_cc" in x else f"{x.get('not_estimable')} | | |")
          for lab, x in ps.get("contrasts", {}).items()]
    L += ["", "## BFCL (200 panel items), all items", "", "| cell | items | div | D_cc | G | M | M_cc |", "|---|---|---|---|---|---|---|"]
    for c, r in R["bfcl"].get("cells", {}).items():
        s = r["all_items_pp"]
        L.append(f"| {c} | {r['n_items']} | {r['n_div']} | " + " | ".join(f(s[k]) for k in ("D_cc", "G", "M", "M_cc")) + " |")
    L += ["", "Local fidelity, BFCL contrasts and complete-case sensitivities: see the JSON. Descriptive fidelity only (protocol §9).",
          f"Source: `{jp.relative_to(ROOT)}`.", ""]
    return "\n".join(L)


# ---------------------------------------------------------------------------- selftest (synthetic only)
def selftest(B: int) -> None:
    """Synthetic m24-shaped units; reads only the frozen manifest + mask (no fork output). Checks: the population is 83 tasks;
    blocks complete on the 83 are admitted even though airline 13/44 rows are missing; a newly missing branch fails its
    block; masked tasks never enter the primary; the sensitivity keeps every available row; M1 uses blocks complete in
    both cells; no arm is imputed; A6: a state completed by an agent-output arm error enters the primary, not the
    strict-as-preregistered sensitivity."""
    rng = np.random.default_rng(0)
    g = guard("m24")
    man = json.loads((ROOT / g["manifest"]).read_text())
    pop, exc = population("m24", man)
    assert len(pop) == 83 and set(exc) == {"airline|13", "airline|44"}, (len(pop), exc)
    raw = {}
    for cell in M24_CELLS:
        us = []
        for r in man["rows"]:
            if r["phase"] != 1:
                continue
            task = f"{r['domain']}|{r['task_id']}"
            u = {"cell": cell, "block": r["block"], "phase": 1, "task": task, "state_key": r["state_key"], "domain": r["domain"], "div": True, "source": "panel"}
            if r["missing_reason"]:
                u["excluded"] = r["missing_reason"]
            else:
                Y = {k: int(rng.random() < 0.3) for k in ("BB", "BQ", "QB", "QQ")}
                ex = bool(rng.random() < 0.5)
                if ex:
                    Y["BQ"], Y["QB"] = Y["QQ"], Y["BB"]
                u.update(Y=Y, E=unit_effects(Y, ex), exact=ex, category=None)
            us.append(u)
        raw[cell] = us
    # newly missing branch: gptq f03 loses one in-population state -> that block must fail for gptq only
    victim = next(u for u in raw["gptq_w4_d1"] if u["block"] == "f03" and u["task"] in pop and "excluded" not in u)
    victim.pop("Y"); victim.pop("E"); victim["excluded"] = "arm missing"
    # amendment A6: rtn f02 has one state completed by an agent-output arm error (Y_QQ = 0): admitted in the primary only
    v6 = next(u for u in raw["rtn_w4"] if u["block"] == "f02" and u["task"] in pop and "excluded" not in u)
    v6["Y"]["QQ"] = 0
    v6.update(E=unit_effects(v6["Y"], v6["exact"]), a6={"QQ": ("agent_output", "invalid_function_name")})
    a6_selftest()
    pc, pinfo, _, _ = apply_population(strict_prereg(raw), pop, len(pop))
    assert pinfo["rtn_w4"]["f02"]["admitted"] is False and len(pc["rtn_w4"]) == 166 and len(pc["gptq_w4_d1"]) == 166, pinfo["rtn_w4"]
    assert "not_estimable" in tau2_contrasts(pc, CONTRASTS["m24"], B)[0]["M1"]  # prereg: common blocks {f01} only
    rep = a6_report(raw, pop)["rtn_w4"]["f02"]
    assert (rep["states_reclassified"], rep["arms_reclassified"], rep["by_signature"]) == (1, 1, {"invalid_function_name": 1}), rep
    cells, info, cc, avail = apply_population(raw, pop, len(pop))
    assert info["rtn_w4"]["f02"]["complete_via_a6"] == 1
    assert all(info["rtn_w4"][b]["admitted"] for b in ("f01", "f02", "f03")), info["rtn_w4"]
    assert info["gptq_w4_d1"]["f03"]["admitted"] is False and info["gptq_w4_d1"]["f01"]["admitted"], info["gptq_w4_d1"]
    assert len(cells["rtn_w4"]) == 249 and len(cells["gptq_w4_d1"]) == 166
    assert not any(u["task"] in exc for c in cells.values() for u in c)
    n_avail = sum(1 for u in raw["rtn_w4"] if "excluded" not in u)
    assert len(avail["rtn_w4"]) == n_avail == 255 - 4 and any(u["task"] == "airline|13" for u in avail["rtn_w4"])
    assert all("Y" in u and all(u["Y"][k] in (0, 1) for k in ("BB", "BQ", "QB", "QQ")) for c in cells.values() for u in c)
    r1 = tau2_cell(cells["rtn_w4"], B)
    con = tau2_contrast(cells["gptq_w4_d1"], cells["rtn_w4"], B)
    assert con["common_blocks"] == ["f01", "f02"] and con["n_states"] == 166, con.get("common_blocks")
    sens = tau2_contrast(avail["gptq_w4_d1"], avail["rtn_w4"], B, match_tasks=True)
    assert sens["common_blocks"] == ["f01", "f02", "f03"]
    print(json.dumps({"selftest": "PASS", "population": len(pop), "excluded": exc, "blocks": info,
                      "rtn_w4_states": r1["n_states"], "M1_common_blocks": con["common_blocks"], "M1_n_states": con["n_states"],
                      "sensitivity_n_states": sens["n_states"], "a6": "PASS", "strict_prereg_blocks": pinfo}, indent=1, default=str))


def a6_selftest() -> None:
    """A6.2 on synthetic branch error records (repr strings as cloq/fork.py::run_branch writes them) and row resolution."""
    s1 = {"error": "InvalidFunctionCallException('Function name was  but must be a-z, A-Z, 0-9, or contain underscores and dashes, "
                   "with a maximum length of 64.')", "n_decisions": 7}
    s1q = {"error": 'InvalidFunctionCallException("Function name was I\'m transferring you but must be a-z")', "n_decisions": 1}
    s3 = {"error": "ValueError(\"AssistantMessage must have either content or tool_calls. Got AssistantMessage(role='assistant')\")", "n_decisions": 2}
    assert a6_class(s1) == ("agent_output", "invalid_function_name") and a6_class(s1q)[0] == "agent_output"
    assert a6_class(s3) == ("agent_output", "empty_agent_message")
    for br in ({**s1, "n_decisions": 0}, {**s1, "infra_cause": "context_overflow"}, None, {"n_decisions": 3},
               {"error": "JSONDecodeError('Unterminated string starting at: line 1 column 7 (char 6)')", "n_decisions": 2},
               {"error": "litellm.APIConnectionError: Connection error.", "n_decisions": 3},
               {"error": "litellm.BadRequestError: Hosted_vllmException - This model only supports single tool-calls at once!", "n_decisions": 2},
               {"error": "InvalidToolException('Function name was x y but must be a-z')", "n_decisions": 3},
               {"error": "ValueError(\"UserMessage must have either content or tool_calls. Got UserMessage(role='user')\")", "n_decisions": 3},
               {"error": "KeyError('QQ')", "n_decisions": 4}):
        assert a6_class(br)[0] == "missing", br
    assert a6_class({"error": "JSONDecodeError('x')", "n_decisions": 2}) == ("missing", "JSONDecodeError")
    # exact state: BB orig, QB = BB, QQ run (S1), BQ = QQ -> both Q-controller arms 0; any other error keeps the row missing
    x = {"Y": {"BB": 1, "BQ": None, "QB": 1, "QQ": None},
         "arm_source": {"BB": "orig", "QB": "reuse=BB", "QQ": "error: InvalidFunctionCallException('Function name was", "BQ": "reuse=QQ"}}
    Y6, cls = a6_resolve(x, {"QQ": s1})
    assert Y6 == {"BB": 1, "BQ": 0, "QB": 1, "QQ": 0} and cls == {"QQ": ("agent_output", "invalid_function_name"), "BQ": ("reuse", "reuse=QQ")}
    assert x["Y"]["QQ"] is None  # the bank row itself is not modified
    assert a6_resolve(x, {"QQ": {"error": "JSONDecodeError('x')", "n_decisions": 2}})[0] is None and a6_resolve(x, {})[0] is None
    two = {"Y": {"BB": 0, "BQ": None, "QB": None, "QQ": 1}, "arm_source": {"BB": "run", "BQ": "error: a", "QB": "error: b", "QQ": "run"}}
    assert a6_resolve(two, {"BQ": s3, "QB": {"error": "litellm.Timeout: x", "n_decisions": 1}})[0] is None  # one arm still missing
    assert a6_resolve(two, {"BQ": s3, "QB": s1})[0] == {"BB": 0, "BQ": 0, "QB": 0, "QQ": 1}


if __name__ == "__main__":
    main()
