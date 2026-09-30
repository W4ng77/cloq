"""Closed-loop restoration / residual-dose arms (W40, pert_*_fdev): paired Q vs arm vs BF16 success and turnover.

Runs (all must be admitted in the integrity-gated snapshot, with the same prompt nonce per block):
  arm   a6k2_pert_<model>_<cell>_<arm>_<block>     (restore_<module set> / resid_a<alpha>; scripts/a6000/derived.py)
  Q     a6k2_<model>_<cell>_<block>                (the dev-block Q run of the same checkpoint)
  BF16  a6k2_<model>_bfpair_<block>                (BF16 on the same nonce)
Unit = task x block, used only where all three episodes exist and none is an infrastructure episode (the snapshot's
infra_missing list). Y = DB success for retail/airline (db_match with a user_stop/agent_stop ending), official task-basis
success for telecom (official_reward == 1).
Per model x cell x arm:
  - success of Q, arm and BF16;
  - paired differences arm - Q, BF16 - Q and arm - BF16;
  - gap closed = (arm - Q) / (BF16 - Q), a ratio of the bootstrap means; undefined when the Q-BF16 gap is 0 in a draw;
  - turnover vs Q (P(Y_arm != Y_Q), fix = P(arm 1, Q 0), break = P(arm 0, Q 1)) and vs BF16.
Behavioural endpoint (W50; primary in the W4 equivalence regime, co-primary with success in the W3 damage regime):
  - turnover to BF16 T(X) = P(Y_X != Y_BF16) for X = Q and X = arm; turnover closed = 1 - T(arm) / T(Q), per bootstrap
    draw (defined where T(Q) > 0 in the draw). Unlike gap closed it does not depend on the sign of BF16 - Q: an arm that
    reverts Q's lucky successes towards BF16 closes turnover, and one that only moves success without matching BF16 does not.
  - decision level (token), from decisions.jsonl on the shared prefix (same nonce, greedy, deterministic serving): the first
    decision index k at which X's (prompt sha, completion token ids) differs from BF16's (None = identical episode);
    divergence rate D(X) = P(k exists), divergence closed = 1 - D(arm) / D(Q); prefix agreement = k / n_decisions(BF16)
    (1 when identical); later / earlier than Q = P(k_arm > k_Q) / P(k_arm < k_Q) with "identical" = +inf. A unit whose
    first difference is in the prompt rather than the completion is an environment (simulator/tool) divergence, counted
    separately (env_first); units with several trajectories per task in a decisions file are left out of this block.
  - action level: the same statistics on action signatures (cloq.fork.action_view kind + normalised tool calls; talk
    wording ignored) compared along the episode. The token level saturates at W4 (any weight change alters some token in
    the first decisions), so the action level is the informative decision-level measure; it is not a same-state
    comparison after the first wording difference.
Intervals come from the hierarchical bootstrap of analysis/fork/analyze_dev.py (tasks, then blocks within task; B = 2000;
seed 20261001; draws shared by every arm of a population, so arm contrasts are paired). Telecom cells (W53,
a6k2_pert_<m>_tel_<cell>_<arm>_<blk>, paired with a6k2_<m>_tel_<cell>_<blk> and a6k2_<m>_tel_bfpair_<blk>) get their own
bootstrap population and a persona breakdown (Hard / Easy / None from the task id).
W54: arms restore_recal_<X> (kept modules BF16, the rest re-calibrated sequentially) are paired like any arm and, where
the plain restore_<X> of the same cell exists, compared with it on joint units (compensation effect = recal - plain).
Idempotent: an output with the same input fingerprint (script, snapshot, every run file sha) is not rewritten.

usage: python analysis/fork/analyze_restore_eval.py --snapshot <snapshot.json> [--models q4 q8]
-> analysis/fork/out/restore_eval_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_dev import Boot, SEED, B_BOOT, sha256, success, summarise  # noqa: E402

OUT = ROOT / "analysis/fork/out"
ARM_RE = re.compile(r"^a6k2_pert_(q\d+)_((?:tel_)?(?:gptq_w4_d1|awq_w4|gptq_w3))_(.+)_(f\d\d|q\d+)$")
PERSONAS = ("Hard", "Easy", "None")  # telecom task ids end in [PERSONA:<level>]
REGIME = {"gptq_w4_d1": "W4 equivalence (behavioural endpoint primary)", "awq_w4": "W4 equivalence (behavioural endpoint primary)",
          "gptq_w3": "W3 damage (success and behavioural endpoints co-primary)",
          "tel_awq_w4": "W4 telecom damage (success and behavioural endpoints co-primary; Hard-persona breakdown)"}


def pair_ids(model: str, cell: str, arm_rid: str, blk: str) -> dict:
    """Arm, Q and BF16 run ids of one block. Telecom cells (tel_<cell>) pair with a6k2_<m>_tel_<cell>_<blk> and
    a6k2_<m>_tel_bfpair_<blk> (single-domain {telecom} runs, integrity W44)."""
    bf = f"a6k2_{model}_tel_bfpair_{blk}" if cell.startswith("tel_") else f"a6k2_{model}_bfpair_{blk}"
    return {"arm": arm_rid, "Q": f"a6k2_{model}_{cell}_{blk}", "B": bf}
_DEC_CACHE: dict = {}


def decisions(run_id: str, dom: str, fr: dict):
    """{unit task key: [(prompt sha, completion hash), ...] by decision_idx}, the file sha; None if missing/mismatched."""
    key = (run_id, dom)
    if key in _DEC_CACHE:
        return _DEC_CACHE[key]
    p = ROOT / "runs" / run_id / dom / "decisions.jsonl"
    want = ((fr.get("files") or {}).get("decisions.jsonl") or {}).get("sha256")
    out = None
    if p.exists():
        h = sha256(p)
        if want is None or h == want:
            seq, trajs = defaultdict(dict), defaultdict(set)
            for ln in open(p):
                d = json.loads(ln)
                k = f"{dom}:{d['task_id']}"
                trajs[k].add(d.get("trajectory_id"))
                seq[k][int(d["decision_idx"])] = (d.get("prompt_sha256"),
                                                  hashlib.sha256(json.dumps(d.get("completion_token_ids")).encode()).hexdigest()[:16],
                                                  act_sig(d))
            out = ({k: [v[i] for i in sorted(v)] for k, v in seq.items() if len(trajs[k]) == 1}, h)
    _DEC_CACHE[key] = out
    return out


def act_sig(d: dict) -> str:
    """Action signature of one decision (cloq.fork.action_view): kind + normalised tool calls; talk text ignored."""
    from cloq.fork import action_view
    v = action_view(d, {})
    return json.dumps([v["kind"], [c["norm"] for c in v["calls"]]], sort_keys=True, default=str)


def first_div(x: list, b: list):
    """Token level: (index of the first decision whose prompt or completion tokens differ, or None if the episode is
    identical; kind 'agent' | 'env' | 'length' | None)."""
    for i, (dx, db) in enumerate(zip(x, b)):
        if dx[:2] != db[:2]:
            return i, ("env" if dx[0] != db[0] else "agent")
    if len(x) != len(b):
        return min(len(x), len(b)), "length"
    return None, None


def first_act_div(x: list, b: list):
    """Action level: index of the first decision whose action signature differs (talk wording ignored), or None if the
    action sequences are identical. After a wording difference the states are no longer identical, so this is the first
    change in the action sequence, not a same-state comparison (that is the fork protocol's job)."""
    for i, (dx, db) in enumerate(zip(x, b)):
        if dx[2] != db[2]:
            return i, "action"
    if len(x) != len(b):
        return min(len(x), len(b)), "length"
    return None, None



def parse_arm(rid: str):
    """-> (model, cell, arm, block) for an arm run id, else None."""
    m = ARM_RE.match(rid)
    return m.groups() if m else None


def episodes(run_id: str, dom: str, fr: dict, det: dict) -> dict[str, int] | None:
    p = ROOT / "runs" / run_id / dom / "trajectory.jsonl"
    if not p.exists() or sha256(p) != fr["files"]["trajectory.jsonl"]["sha256"]:
        return None
    infra = set(map(str, (det or {}).get("infra_missing") or fr.get("infra_missing") or []))
    out = {}
    for ln in open(p):
        t = json.loads(ln)
        if str(t["task_id"]) in infra or t.get("termination_reason") == "infrastructure_error":
            continue
        out[f"{dom}:{t['task_id']}"] = success(dom, t)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--B", type=int, default=B_BOOT)
    a = ap.parse_args()
    t0 = time.time()
    snap = json.load(open(a.snapshot))
    fz, det = snap["frozen"], snap.get("detail", {})
    arms = defaultdict(list)  # (model, cell, arm) -> [(block, arm run id)]
    for rid in fz:
        g = parse_arm(rid)
        if g and (not a.models or g[0] in a.models):
            arms[g[:3]].append((g[3], rid))
    if not arms:
        print("analyze_restore_eval: no admitted restoration arm runs (a6k2_pert_<model>_<cell>_<arm>_<block>) in the snapshot yet; nothing to do.")
        return
    files, units, skipped = {}, defaultdict(list), []
    for (model, cell, arm), blocks in sorted(arms.items()):
        for blk, arm_rid in sorted(blocks):
            ids = pair_ids(model, cell, arm_rid, blk)
            for dom in sorted(fz[ids["arm"]]):
                if not all(dom in (fz.get(r) or {}) for r in ids.values()):
                    skipped.append({"arm": ids["arm"], "domain": dom, "reason": "Q or BF16 run not admitted"})
                    continue
                nonces = {k: fz[r][dom].get("prompt_nonce") for k, r in ids.items()}
                if len(set(nonces.values())) != 1:
                    skipped.append({"arm": ids["arm"], "domain": dom, "reason": f"nonce mismatch {nonces}"})
                    continue
                ep = {k: episodes(r, dom, fz[r][dom], (det.get(r) or {}).get(dom)) for k, r in ids.items()}
                if any(v is None for v in ep.values()):
                    skipped.append({"arm": ids["arm"], "domain": dom, "reason": "trajectory differs from the snapshot"})
                    continue
                for k, r in ids.items():
                    files[f"runs/{r}/{dom}/trajectory.jsonl"] = fz[r][dom]["files"]["trajectory.jsonl"]["sha256"]
                dec = {k: decisions(r, dom, fz[r][dom]) for k, r in ids.items()}
                if all(v is not None for v in dec.values()):
                    for k, r in ids.items():
                        files[f"runs/{r}/{dom}/decisions.jsonl"] = dec[k][1]
                else:
                    skipped.append({"arm": ids["arm"], "domain": dom, "reason": "decisions.jsonl missing or differs (decision block only)"})
                for task in sorted(set(ep["arm"]) & set(ep["Q"]) & set(ep["B"])):
                    u = {"task": task, "block": blk, "domain": dom,
                         "Y": {"arm": ep["arm"][task], "Q": ep["Q"][task], "B": ep["B"][task]}}
                    if all(v is not None and task in v[0] for v in dec.values()):
                        sb = dec["B"][0][task]
                        u["D"] = {"n_B": len(sb), "arm": first_div(dec["arm"][0][task], sb), "Q": first_div(dec["Q"][0][task], sb)}
                        u["A"] = {"n_B": len(sb), "arm": first_act_div(dec["arm"][0][task], sb), "Q": first_act_div(dec["Q"][0][task], sb)}
                    units[(model, cell, arm)].append(u)
    script_sha = sha256(__file__)
    fp = hashlib.sha256(json.dumps({"script": script_sha, "dev": sha256(ROOT / "analysis/fork/analyze_dev.py"),
                                    "snapshot": sha256(a.snapshot), "files": files, "models": a.models, "B": a.B},
                                   sort_keys=True).encode()).hexdigest()[:16]
    OUT.mkdir(parents=True, exist_ok=True)
    for p in sorted(OUT.glob("restore_eval_*.json")):
        try:
            if json.load(open(p)).get("input_fingerprint") == fp:
                print(f"analyze_restore_eval: unchanged inputs (fingerprint {fp}); existing output {p.relative_to(ROOT)}")
                return
        except Exception:
            continue
    allu = [u for v in units.values() for u in v]
    if not allu:
        print(f"analyze_restore_eval: arm runs found but no complete Q/arm/BF16 triples yet ({len(skipped)} skipped); nothing to do.")
        return
    def group(cell):  # separate bootstrap for telecom cells (own task population), shared draws within a group
        return "telecom" if cell.startswith("tel_") else "main"
    boots = {}
    for g_ in sorted({group(k[1]) for k in units}):
        bo = defaultdict(set)
        for k, us_ in units.items():
            if group(k[1]) == g_:
                for u in us_:
                    bo[u["task"]].add(u["block"])
        boots[g_] = Boot(sorted(bo), {k: sorted(v) for k, v in bo.items()}, B=a.B)
    boot = None

    def stat(us, fn, field="Y"):
        us = [u for u in us if field in u]
        for u in us:
            u["E"] = {"x": fn(u[field])}
        X, M = boot.arrays(us, "x")
        return boot.task_mean(X, M)

    def closed(num, den):
        """1 - num/den per draw (draws with den > 0), point estimate from the point estimates."""
        ok = den[1] > 1e-12
        d = 1 - num[1][ok] / den[1][ok]
        return {"est": round(1 - num[0] / den[0], 3) if den[0] > 1e-12 else None,
                "ci95": [round(float(x), 3) for x in np.percentile(d, [2.5, 97.5])] if ok.sum() > 10 else None,
                "draws_defined": int(ok.sum())}

    INF = float("inf")

    def k_of(fd):
        return INF if fd[0] is None else fd[0]

    res_arms = {}
    for key, us in sorted(units.items()):
        m, c, arm = key
        boot = boots[group(c)]
        r = {"n_units": len(us), "n_tasks": len({u["task"] for u in us}), "blocks": sorted({u["block"] for u in us}),
             "domains": sorted({u["domain"] for u in us})}
        fns = {"success_Q": lambda y: y["Q"], "success_arm": lambda y: y["arm"], "success_B": lambda y: y["B"],
               "arm_minus_Q": lambda y: y["arm"] - y["Q"], "B_minus_Q": lambda y: y["B"] - y["Q"], "arm_minus_B": lambda y: y["arm"] - y["B"],
               "turnover_vs_Q": lambda y: int(y["arm"] != y["Q"]), "fix_vs_Q": lambda y: int(y["arm"] == 1 and y["Q"] == 0),
               "break_vs_Q": lambda y: int(y["arm"] == 0 and y["Q"] == 1), "turnover_vs_B": lambda y: int(y["arm"] != y["B"]),
               "turnover_Q_vs_B": lambda y: int(y["Q"] != y["B"])}
        raw = {k: stat(us, f) for k, f in fns.items()}
        r["pp"] = {k: summarise(*v) for k, v in raw.items()}
        num, den = raw["arm_minus_Q"], raw["B_minus_Q"]
        ok = np.abs(den[1]) > 1e-12
        gc = num[1][ok] / den[1][ok]
        r["gap_closed"] = {"est": round(num[0] / den[0], 3) if abs(den[0]) > 1e-12 else None,
                           "ci95": [round(float(x), 3) for x in np.percentile(gc, [2.5, 97.5])] if ok.sum() > 10 else None,
                           "draws_defined": int(ok.sum()), "note": "ratio of bootstrap means; unstable when BF16 - Q is near 0"}
        # behavioural endpoint: outcome turnover to BF16
        r["regime"] = REGIME.get(c)
        r["turnover_closed"] = closed(raw["turnover_vs_B"], raw["turnover_Q_vs_B"])
        if c.startswith("tel_"):  # persona breakdown (Hard is where the W4 damage sits, W53)
            r["persona"] = {}
            for pl in PERSONAS:
                sub = [u for u in us if f"[PERSONA:{pl}]" in u["task"]]
                if not sub:
                    continue
                pr = {k: stat(sub, fns[k]) for k in ("success_Q", "success_arm", "success_B", "arm_minus_Q", "B_minus_Q",
                                                     "turnover_vs_B", "turnover_Q_vs_B")}
                n_, d_ = pr["arm_minus_Q"], pr["B_minus_Q"]
                r["persona"][pl] = {"n_units": len(sub), "pp": {k: summarise(*v) for k, v in pr.items()},
                                    "gap_closed": round(n_[0] / d_[0], 3) if abs(d_[0]) > 1e-12 else None,
                                    "turnover_closed": closed(pr["turnover_vs_B"], pr["turnover_Q_vs_B"])}
        # decision level: token-level shared prefix ("decision") and action-sequence level ("action")
        for name, fld in (("decision", "D"), ("action", "A")):
            ud = [u for u in us if fld in u]
            r[name] = {"n_units": len(ud)}
            if not ud:
                continue
            dfn = {"div_arm_vs_B": lambda d: int(d["arm"][0] is not None), "div_Q_vs_B": lambda d: int(d["Q"][0] is not None),
                   "prefix_agree_arm": lambda d: (d["arm"][0] / max(d["n_B"], 1)) if d["arm"][0] is not None else 1.0,
                   "prefix_agree_Q": lambda d: (d["Q"][0] / max(d["n_B"], 1)) if d["Q"][0] is not None else 1.0,
                   "later_than_Q": lambda d: int(k_of(d["arm"]) > k_of(d["Q"])),
                   "earlier_than_Q": lambda d: int(k_of(d["arm"]) < k_of(d["Q"]))}
            if fld == "D":
                dfn.update({"env_first_arm": lambda d: int(d["arm"][1] == "env"), "env_first_Q": lambda d: int(d["Q"][1] == "env")})
            draw = {k: stat(ud, f, fld) for k, f in dfn.items()}
            draw["prefix_agree_arm_minus_Q"] = stat(ud, lambda d: dfn["prefix_agree_arm"](d) - dfn["prefix_agree_Q"](d), fld)
            r[name]["pp"] = {k: summarise(*v) for k, v in draw.items()}
            r[name]["divergence_closed"] = closed(draw["div_arm_vs_B"], draw["div_Q_vs_B"])
            both = [u for u in ud if u[fld]["arm"][0] is not None and u[fld]["Q"][0] is not None]
            r[name]["first_div_index_both_diverge"] = {
                "n": len(both), "mean_arm": round(float(np.mean([u[fld]["arm"][0] for u in both])), 2) if both else None,
                "mean_Q": round(float(np.mean([u[fld]["Q"][0] for u in both])), 2) if both else None,
                "note": "conditional on both diverging from BF16 (selection); descriptive only"}
            # sanity: identical to BF16 but a different outcome would mean non-reproducible scoring/simulation
            r[name]["identical_but_outcome_differs"] = sum(1 for u in ud if u[fld]["arm"][0] is None and u["Y"]["arm"] != u["Y"]["B"])
        res_arms[f"{m}:{c}:{arm}"] = r
    # W54 compensation effect: restore_recal_<X> (rebuilt mixed precision) vs restore_<X> (post-hoc swap), paired units
    compensation = {}
    for (m, c, arm), us in sorted(units.items()):
        if not arm.startswith("restore_recal_"):
            continue
        plain = arm.replace("restore_recal_", "restore_", 1)
        if (m, c, plain) not in units:
            continue
        boot = boots[group(c)]
        pl = {(u["task"], u["block"]): u for u in units[(m, c, plain)]}
        joint = [{"task": u["task"], "block": u["block"],
                  "Y": {"recal": u["Y"]["arm"], "plain": pl[(u["task"], u["block"])]["Y"]["arm"], "Q": u["Y"]["Q"], "B": u["Y"]["B"]}}
                 for u in us if (u["task"], u["block"]) in pl]
        if not joint:
            continue
        cf = {"recal_minus_plain": lambda y: y["recal"] - y["plain"],
              "turnover_B_recal_minus_plain": lambda y: int(y["recal"] != y["B"]) - int(y["plain"] != y["B"]),
              "recal_vs_plain_turnover": lambda y: int(y["recal"] != y["plain"])}
        compensation[f"{m}:{c}:{plain[len('restore_'):]}"] = {
            "n_units": len(joint), "pp": {k: summarise(*stat(joint, f)) for k, f in cf.items()},
            "recal": {"success": res_arms[f"{m}:{c}:{arm}"]["pp"]["success_arm"], "gap_closed": res_arms[f"{m}:{c}:{arm}"]["gap_closed"]["est"],
                      "turnover_closed": res_arms[f"{m}:{c}:{arm}"]["turnover_closed"]},
            "plain": {"success": res_arms[f"{m}:{c}:{plain}"]["pp"]["success_arm"], "gap_closed": res_arms[f"{m}:{c}:{plain}"]["gap_closed"]["est"],
                      "turnover_closed": res_arms[f"{m}:{c}:{plain}"]["turnover_closed"]}}
    res = {"analysis": "analysis/fork/analyze_restore_eval.py", "input_fingerprint": fp,
           "snapshot": {"id": snap.get("snapshot_id"), "path": str(Path(a.snapshot).resolve()), "sha256": sha256(a.snapshot)},
           "script": {"path": str(Path(__file__).resolve()), "sha256": script_sha,
                      "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()},
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "bootstrap": {"B": a.B, "seed": SEED, "scheme": "tasks, then blocks within task; draws shared by all arms"},
           "success_definition": {"retail/airline": "DB success", "telecom": "official task-basis success"},
           "arms": res_arms, "compensation": compensation, "skipped": skipped, "input_files": files, "seconds": round(time.time() - t0, 1)}
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    jp = OUT / f"restore_eval_{utc}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))

    def f(x):
        return f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}]"
    L = [f"**TL;DR** Restoration arms vs Q vs BF16 on shared nonces, {len(res_arms)} arms, "
         f"{sum(v['n_units'] for v in res_arms.values())} paired units; {len(skipped)} run-domains skipped. Snapshot {res['snapshot']['id']}.",
         "", f"# Restoration closed-loop arms ({res['utc']})", "", f"Full numbers: `{jp.relative_to(ROOT) if jp.is_relative_to(ROOT) else jp}`. pp; 95% hierarchical bootstrap.", "",
         "| arm | units | Q | arm | BF16 | arm-Q | BF16-Q | gap closed | turnover vs Q (fix/break) |", "|---|---|---|---|---|---|---|---|---|"]
    for k, v in res_arms.items():
        p = v["pp"]
        L.append(f"| {k} | {v['n_units']} | {p['success_Q']['est']:.1f} | {p['success_arm']['est']:.1f} | {p['success_B']['est']:.1f} | "
                 f"{f(p['arm_minus_Q'])} | {f(p['B_minus_Q'])} | {v['gap_closed']['est']} | {p['turnover_vs_Q']['est']:.1f} "
                 f"({p['fix_vs_Q']['est']:.1f}/{p['break_vs_Q']['est']:.1f}) |")
    def g(x):
        return "n/a" if not x or x.get("est") is None else (f"{x['est']:.2f} [{x['ci95'][0]:.2f}, {x['ci95'][1]:.2f}]" if x.get("ci95") else f"{x['est']:.2f}")
    L += ["", "## Behavioural endpoint: turnover to BF16 and decision agreement",
          "", "Primary in the W4 equivalence regime (success can move either way there); co-primary with success for W3.",
          "turnover = P(outcome differs from BF16); closed = 1 - T(arm)/T(Q). div = P(any decision differs from BF16 on the "
          "shared prefix); prefix = mean first-divergence index / BF16 decisions (1 = identical). later/earlier = arm's first "
          "divergence after/before Q's.", "",
          "Token level (exact prompt + completion tokens) saturates in the W4 regime: almost every episode differs from BF16 "
          "within the first decisions. The action level compares action signatures (kind + normalised tool calls, talk "
          "wording ignored) along the episode.", "",
          "| arm | regime | T(Q) | T(arm) | turnover closed | action div Q / arm | action divergence closed | action prefix Q / arm | "
          "action later/earlier than Q | token div Q / arm | token prefix Q / arm |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in res_arms.items():
        p = v["pp"]
        reg = "W3" if "gptq_w3" in k else "W4"
        row = f"| {k} | {reg} | {p['turnover_Q_vs_B']['est']:.1f} | {p['turnover_vs_B']['est']:.1f} | {g(v['turnover_closed'])} | "
        a, d = v.get("action", {}), v.get("decision", {})
        if a.get("pp") and d.get("pp"):
            ap, dp = a["pp"], d["pp"]
            row += (f"{ap['div_Q_vs_B']['est']:.1f} / {ap['div_arm_vs_B']['est']:.1f} | {g(a['divergence_closed'])} | "
                    f"{ap['prefix_agree_Q']['est'] / 100:.3f} / {ap['prefix_agree_arm']['est'] / 100:.3f} | "
                    f"{ap['later_than_Q']['est']:.1f}/{ap['earlier_than_Q']['est']:.1f} | "
                    f"{dp['div_Q_vs_B']['est']:.1f} / {dp['div_arm_vs_B']['est']:.1f} | "
                    f"{dp['prefix_agree_Q']['est'] / 100:.3f} / {dp['prefix_agree_arm']['est'] / 100:.3f} |")
        else:
            row += "n/a | n/a | n/a | n/a | n/a | n/a |"
        L.append(row)
    if compensation:
        L += ["", "## restore (post-hoc swap) vs restore_recal (rebuilt mixed precision), W54", "",
              "Plain restore swaps BF16 modules into the finished Q, so downstream quantized layers see inputs they were not "
              "calibrated for. restore_recal re-runs the sequential GPTQ/AWQ around the kept modules. Compensation effect = "
              "recal - plain on paired units (pp).", "",
              "| cell:arm | units | success plain | success recal | recal - plain | gap closed plain / recal | "
              "turnover closed plain / recal | T(BF16) recal - plain |", "|---|---|---|---|---|---|---|---|"]
        for k, v in compensation.items():
            p = v["pp"]
            L.append(f"| {k} | {v['n_units']} | {v['plain']['success']['est']:.1f} | {v['recal']['success']['est']:.1f} | "
                     f"{f(p['recal_minus_plain'])} | {v['plain']['gap_closed']} / {v['recal']['gap_closed']} | "
                     f"{g(v['plain']['turnover_closed'])} / {g(v['recal']['turnover_closed'])} | {f(p['turnover_B_recal_minus_plain'])} |")
    tel = {k: v for k, v in res_arms.items() if v.get("persona")}
    if tel:
        L += ["", "## Telecom cell(s), by persona (W53)", "",
              "Separate bootstrap population (telecom dev tasks). pp; gap closed = (arm-Q)/(BF16-Q); turnover closed = 1 - T(arm)/T(Q).", "",
              "| arm | persona | units | Q | arm | BF16 | arm-Q | BF16-Q | gap closed | turnover closed |", "|---|---|---|---|---|---|---|---|---|---|"]
        for k, v in tel.items():
            p = v["pp"]
            L.append(f"| {k} | all | {v['n_units']} | {p['success_Q']['est']:.1f} | {p['success_arm']['est']:.1f} | {p['success_B']['est']:.1f} | "
                     f"{f(p['arm_minus_Q'])} | {f(p['B_minus_Q'])} | {v['gap_closed']['est']} | {g(v['turnover_closed'])} |")
            for pl, pv in v["persona"].items():
                pp = pv["pp"]
                L.append(f"| {k} | {pl} | {pv['n_units']} | {pp['success_Q']['est']:.1f} | {pp['success_arm']['est']:.1f} | "
                         f"{pp['success_B']['est']:.1f} | {f(pp['arm_minus_Q'])} | {f(pp['B_minus_Q'])} | {pv['gap_closed']} | "
                         f"{g(pv['turnover_closed'])} |")
    (OUT / f"restore_eval_{utc}.md").write_text("\n".join(L) + "\n")
    print(f"analyze_restore_eval: wrote {jp.relative_to(ROOT) if jp.is_relative_to(ROOT) else jp} ({res['seconds']} s)")


if __name__ == "__main__":
    main()
