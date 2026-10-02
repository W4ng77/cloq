"""Fork development analysis on the simulator-free environments (protocol fork-ext-v1; W39-extfork, W51).

Same estimands and conventions as analysis/fork/analyze_dev.py (imported, not copied): Y = official success
(ALFWorld: TextWorld won; BFCL: official multi-turn checker valid), L = 1 - Y, at the item's primary state
  G = Y_BQ - Y_QQ (h rescue, b new damage), A = L_QB - L_BB, C = L_BQ - L_BB, I = L_QQ - L_QB - L_BQ + L_BB.
Y_QQ is the original episode (QQ no-op verified on a 10% sample per fork task). Items without a primary divergence enter
with all four branches equal to the original outcome (zero effect). Excluded items (search exclusion, branch error,
quarantined task) leave the denominator and are counted per reason; never coded as "no divergence".
Unit = item (ALFWorld game, BFCL entry); one run (block) per item and cell. G_all (primary) = mean over the full item
pool; conditional-on-divergence effects are secondary (ratio form).
Sign dictionary (W68): analyze_dev.SIGN_DICTIONARY (CONSEQUENCE_ANALYSIS_PLAN §2); A/C/I are reported on divergent items only.
Headline (W63): r = P(Y_BQ=1, Y_QQ=0), d = P(Y_BQ=0, Y_QQ=1), M = r + d, G = r - d on one denominator (all items,
non-divergent = 0), plus r/d/M conditional on divergence; same definitions as analyze_dev.
ITEM-LEVEL INFERENCE: the external environments have one run (block) per item and cell, so there is no shared-block
effect to resample; intervals describe item sampling only (unlike the tau2 forks' block-level inference, W63).
Intervals: percentile bootstrap, B = 2000, seed 20261001, items resampled with replacement within stratum
(environment x category: alfworld; bfcl_base / miss_param / miss_func / long_context). The draws are shared by all cells
(the same items are crossed across cells), so equal-weight pools carry valid intervals. g_min = 3 pp.
Pools (pre-declared, equal weight per cell, families never mixed): W4 = gptq_w4_d1 + awq_w4_d1; stress = gptq_w3 +
kvq_int4; per environment (cells = model x arm) and across environments (cells = env x model x arm).
Quarantine: a fork task directory whose QQ no-op sample mismatched (QUARANTINE file or dev_summary.qq_noop_ok) is
dropped whole and listed. Incomplete directories (no branches.json yet) are skipped and listed.
Replay-consistency guard (W99o): every divergent state of an admitted directory must carry effects.jsonl "replay": true
(fork_ext.replay_consistency: backend-state hash before every replayed step identical across branches and equal to the
search replay, prefix observations/messages equal to the recorded episode). A state with "replay" false or missing, or
an admitted directory without effects.jsonl, makes the analysis FAIL (exit 3, nothing written) unless its directory is
quarantined. W99g found the process-shared BFCL long-context backend state through this flag; the affected q4
long-context forks were moved to analysis/fork/ext/quarantine/w99o/ and rerun with the fixed code (W99o).
Models: --models (default q4,q8, the pre-declared ext panel). q14 (W99h scale check) is analysed by ext_q14.py and is never
pooled here.
Idempotent: the input fingerprint (script sha + every input file sha) is compared with existing outputs.

usage: python analysis/fork/analyze_ext.py [--B 2000] -> analysis/fork/out/ext_<UTC>.{json,md}
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis/fork/out"
DEV = ROOT / "analysis/fork/ext/dev"
_spec = importlib.util.spec_from_file_location("analyze_dev", ROOT / "analysis/fork/analyze_dev.py")
AD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(AD)
effects, summarise, pooled, STATS = AD.effects, AD.summarise, AD.pooled, AD.STATS
B_BOOT, SEED, G_MIN = AD.B_BOOT, AD.SEED, AD.G_MIN
FAMILIES = {"W4": ("gptq_w4_d1", "awq_w4_d1"), "stress": ("gptq_w3", "kvq_int4")}
ARMS = ("gptq_w4_d1", "awq_w4_d1", "gptq_w3", "kvq_int4")
TYPES = ["act->talk", "talk->act", "tool_name", "tool_args", "command", "other"]


def family(arm: str) -> str:
    return next((f for f, cs in FAMILIES.items() if arm in cs), "other")


def sha256(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dtype(cat: str) -> str:
    return {"class:act->talk": "act->talk", "class:talk->act": "talk->act", "tool_name": "tool_name",
            "tool_args": "tool_args", "command": "command"}.get(cat, "other")


def parse_dir(name: str) -> tuple[str, str, str, str]:
    """<env>_<model>_<arm>_<tag> -> env, model, arm, stratum."""
    env, rest = name.split("_", 1)
    model, rest = rest.split("_", 1)
    arm = next(a for a in ARMS if rest.startswith(a + "_"))
    tag = rest[len(arm) + 1:]
    return env, model, arm, ("alfworld" if env == "alfworld" else f"bfcl_{tag}")


def load_dir(d: Path) -> dict:
    env, model, arm, stratum = parse_dir(d.name)
    res = {"dir": str(d.relative_to(ROOT)), "env": env, "model": model, "arm": arm, "stratum": stratum, "units": [], "files": {},
           "quarantined": False, "incomplete": False}
    if not (d / "search.json").exists() or not (d / "branches.json").exists():
        res["incomplete"] = True
        return res
    for f in [d / "search.json", d / "branches.json"] + [d / n for n in ("effects.jsonl", "dev_summary.json") if (d / n).exists()]:
        res["files"][str(f.relative_to(ROOT))] = sha256(f)
    summ = json.loads((d / "dev_summary.json").read_text()) if (d / "dev_summary.json").exists() else {}
    ef = d / "effects.jsonl"
    replay = {json.loads(x)["state_id"]: json.loads(x).get("replay") for x in ef.read_text().splitlines() if x.strip()} if ef.exists() else None
    res["has_effects"] = replay is not None
    qq = summ.get("qq_noop_ok") or [0, 0]
    res["noop"] = {"n": qq[1], "n_pass": qq[0]}
    if (d / "QUARANTINE").exists() or qq[0] != qq[1]:
        res["quarantined"] = True
    search = json.loads((d / "search.json").read_text())
    blk_traj: dict = {}
    for row in search["rows"]:
        key = (row["run_id"], row["domain"])
        if key not in blk_traj:
            p = ROOT / "runs" / row["run_id"] / row["domain"] / "trajectory.jsonl"
            blk_traj[key] = {json.loads(l)["task_id"]: json.loads(l) for l in p.read_text().splitlines() if l.strip()}
            res["files"][str(p.relative_to(ROOT))] = sha256(p)
        u = {"env": env, "model": model, "arm": arm, "cell": f"{model}:{arm}", "stratum": stratum, "task": f"{stratum}|{row['task_id']}",
             "block": row["run_id"], "run_id": row["run_id"], "domain": row["domain"], "item": row["task_id"], "div": False}
        y0 = 1 if blk_traj[key][row["task_id"]]["success"] else 0
        if row["status"] == "excluded":
            u["excluded"] = f"search: {row.get('reason')}"
        elif row["status"] == "no_divergence":
            u["Y"] = {b: y0 for b in ("BB", "BQ", "QB", "QQ")}
        else:
            st = json.loads((d / "states" / f"{row['state_id']}.json").read_text())
            bp = d / "branches" / f"{row['state_id']}.json"
            br = json.loads(bp.read_text()) if bp.exists() else {}
            res["files"][str(bp.relative_to(ROOT))] = sha256(bp) if bp.exists() else None
            y = {b: br[b].get("reward") for b in ("BB", "BQ", "QB") if b in br and not br[b].get("error")}
            if len(y) < 3:
                u["excluded"] = "branch error" if br else "branch missing"
            else:
                u["Y"] = {**{b: int(v) for b, v in y.items()}, "QQ": int(st["orig"]["reward"])}
                u.update(div=True, t=st["decision_idx"], state_id=row["state_id"], type=dtype(st["divergence"]["category"]),
                         category=st["divergence"]["category"], n_decisions=st["n_decisions_orig"],
                         replay_ok=(replay or {}).get(row["state_id"]) is True)
                if int(st["orig"]["reward"]) != y0:
                    u["excluded"] = "state/original outcome mismatch"
        res["units"].append(u)
    return res


def replay_guard(done: list[dict], who: str = "analyze_ext") -> dict:
    """W99o: FAIL if any admitted (non-quarantined) directory has a divergent state whose backend state was not
    replay-consistent, or has no effects.jsonl to verify it. Returns the per-directory counts when it passes."""
    bad, counts = {}, {}
    for L in done:
        if L["quarantined"]:
            continue
        div = [u for u in L["units"] if u.get("div")]
        nbad = sum(1 for u in div if not u.get("replay_ok"))
        counts[L["dir"]] = {"states": len(div), "replay_inconsistent": nbad, "has_effects": L.get("has_effects", False)}
        if nbad or not L.get("has_effects", False):
            bad[L["dir"]] = counts[L["dir"]]
    if bad:
        msg = "; ".join(f"{k}: {v['replay_inconsistent']}/{v['states']} states replay-inconsistent"
                        + ("" if v["has_effects"] else " (no effects.jsonl)") for k, v in bad.items())
        raise SystemExit(f"{who}: FAIL replay-consistency guard (W99o): {msg}. Quarantine or rerun these directories.")
    return counts


def select_dirs(dev: Path, dirs_arg, models: list[str]) -> list[Path]:
    return sorted(p for p in dev.glob("*") if p.is_dir() and (not dirs_arg or p.name in dirs_arg)
                  and parse_dir(p.name)[1] in models)


class StratBoot:
    """Items resampled with replacement within stratum; one block per item; draws shared across cells."""

    def __init__(self, strata: dict[str, list[str]], B: int = B_BOOT, seed: int = SEED):
        self.tasks = [t for s in sorted(strata) for t in sorted(strata[s])]
        self.tix = {t: i for i, t in enumerate(self.tasks)}
        rng = np.random.default_rng(seed)
        self.W = np.zeros((B, len(self.tasks)))
        for s in sorted(strata):
            idx = np.array([self.tix[t] for t in sorted(strata[s])])
            for r in range(B):
                self.W[r, idx] += np.bincount(rng.integers(0, len(idx), len(idx)), minlength=len(idx))
        self.W1 = np.ones(len(self.tasks))

    def arrays(self, units, key):
        X, M = np.zeros(len(self.tasks)), np.zeros(len(self.tasks))
        for u in units:
            X[self.tix[u["task"]]] = u["E"][key]
            M[self.tix[u["task"]]] = 1
        return X, M

    def mean(self, X, M):
        def est(W):
            return (W * M * X).sum(-1) / np.maximum((W * M).sum(-1), 1e-12)
        return float(est(self.W1)), est(self.W)


def analyse(units, boot, draws=None, label=""):
    div = [u for u in units if u["div"]]
    r = {"n_units": len(units), "n_states": len(div), "divergence_rate": round(len(div) / len(units), 4) if units else None}
    if not units:
        return r
    r["all_pp"] = {}
    for s in STATS:
        pt, dr = boot.mean(*boot.arrays(units, s))
        r["all_pp"][s] = summarise(pt, dr)
        if draws is not None:
            draws.setdefault(label, {})[s] = (pt, dr)
    g = r["all_pp"]["G"]
    r["G_all_decision"] = {"lb_gt_0": bool(g["lb95_one_sided"] > 0), "lb_gt_gmin": bool(g["lb95_one_sided"] > 100 * G_MIN),
                           "ub_lt_minus_gmin": bool(g["ci95"][1] < -100 * G_MIN), "g_min_pp": 100 * G_MIN}
    r["counts"] = {k: int(sum(u["E"][k] for u in div)) for k in ("rescue", "damage", "M", "both_succeed", "both_fail")}
    if div:
        r["conditional_on_divergence_pp"] = {s: summarise(*boot.mean(*boot.arrays(div, s))) for s in ("G", "rescue", "damage", "M", "A", "C", "I")}
        r["t_star_median"] = float(np.median([u["t"] for u in div]))
        r["by_type"] = {}
        for tp in TYPES:
            sub = [u for u in div if u["type"] == tp]
            if sub:
                zu = [{**u, "E": {**u["E"], "G": u["E"]["G"] if (u["div"] and u["type"] == tp) else 0}} for u in units]
                r["by_type"][tp] = {"n_states": len(sub), "counts": {k: int(sum(u["E"][k] for u in sub)) for k in ("rescue", "damage", "both_succeed", "both_fail")},
                                    "G_cond_pp": summarise(*boot.mean(*boot.arrays(sub, "G"))),
                                    "G_all_contribution_pp": summarise(*boot.mean(*boot.arrays(zu, "G")))}
    return r


def tau2_line(ext_pools: dict, ext_div: dict) -> tuple[str, dict]:
    fs = sorted((ROOT / "analysis/fork/out").glob("dev_all_*.json"))
    if not fs:
        return "τ² comparison: no analysis/fork/out/dev_all_*.json yet.", {}
    t = json.loads(fs[-1].read_text())
    g = t["pooled"].get("W4:all:pooled_equal_weight", {}).get("G")
    w4 = [v for k, v in t["cells"].items() if k.split(":")[1] in ("gptq_w4_d1", "awq_w4")]
    dr = float(np.mean([v["n_states"] / v["n_units"] for v in w4])) if w4 else None

    def fmt(x):
        return f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}] pp" if x else "n/a"
    parts = [f"τ² W4 pooled G_all {fmt(g)}, divergence {100 * dr:.0f}%" if dr is not None else f"τ² W4 pooled G_all {fmt(g)}"]
    for env in ("alfworld", "bfcl"):
        p = ext_pools.get(f"W4:{env}:pooled_equal_weight", {}).get("G")
        d = ext_div.get(env)
        parts.append(f"{'ALFWorld' if env == 'alfworld' else 'BFCL'} {fmt(p)}" + (f", divergence {100 * d:.0f}%" if d is not None else ""))
    return "; ".join(parts) + f" (τ² source {fs[-1].relative_to(ROOT)}).", {"source": str(fs[-1].relative_to(ROOT)), "sha256": sha256(fs[-1]),
                                                                            "tau2_W4_G_all_pp": g, "tau2_W4_divergence_rate": dr}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--B", type=int, default=B_BOOT)
    ap.add_argument("--dirs", nargs="*", default=None, help="only these task dirs under analysis/fork/ext/dev (testing)")
    ap.add_argument("--models", default="q4,q8", help="model panel (default q4,q8; q14 is analysed by ext_q14.py)")
    a = ap.parse_args()
    t0 = time.time()
    models = a.models.split(",")
    dirs = select_dirs(DEV, a.dirs, models)
    loaded = [load_dir(d) for d in dirs]
    done = [L for L in loaded if not L["incomplete"]]
    if not done:
        print("analyze_ext: no complete fork_ext dev directories yet; nothing to do.")
        return
    replay_counts = replay_guard(done)
    script_sha = sha256(__file__)
    files = {k: v for L in done for k, v in L["files"].items()}
    tau_src = sorted((ROOT / "analysis/fork/out").glob("dev_all_*.json"))
    fp = hashlib.sha256(json.dumps({"script": script_sha, "analyze_dev": sha256(ROOT / "analysis/fork/analyze_dev.py"), "files": files,
                                    "B": a.B, "dirs": a.dirs, "models": models, "tau2": sha256(tau_src[-1]) if tau_src else None},
                                   sort_keys=True).encode()).hexdigest()[:16]
    OUT.mkdir(parents=True, exist_ok=True)
    for p in sorted(OUT.glob("ext_*.json")):
        try:
            if json.load(open(p)).get("input_fingerprint") == fp:
                print(f"analyze_ext: unchanged inputs (fingerprint {fp}); existing output {p.relative_to(ROOT)}")
                return
        except Exception:
            continue
    quarantined = [L["dir"] for L in done if L["quarantined"]]
    units = [u for L in done if not L["quarantined"] for u in L["units"]]
    excluded = [u for u in units if "excluded" in u]
    ok = [u for u in units if "excluded" not in u]
    for u in ok:
        u["E"] = effects(u["Y"], u.get("div", True))
    strata: dict = defaultdict(set)
    for u in ok:
        strata[u["stratum"]].add(u["task"])
    boot = StratBoot({s: sorted(v) for s, v in strata.items()}, B=a.B)
    draws: dict = {}
    res_cells, ext_div = {}, {}
    for env in sorted({u["env"] for u in ok}):
        for cell in sorted({u["cell"] for u in ok if u["env"] == env}):
            cu = [u for u in ok if u["env"] == env and u["cell"] == cell]
            lab = f"{env}:{cell}"
            r = analyse(cu, boot, draws, lab)
            r["by_category"] = {s: analyse([u for u in cu if u["stratum"] == s], boot) for s in sorted({u["stratum"] for u in cu})}
            ex = defaultdict(int)
            for u in excluded:
                if u["env"] == env and u["cell"] == cell:
                    ex[u["excluded"].split(":")[0] if u["excluded"].startswith("search") else u["excluded"]] += 1
            r["excluded"] = dict(ex)
            r["coverage"] = {"items_searched": len(cu) + sum(ex.values()), "items_analysed": len(cu), "states": r["n_states"],
                             "divergence_rate": r["divergence_rate"], "categories": {s: sum(1 for u in cu if u["stratum"] == s) for s in sorted({u["stratum"] for u in cu})},
                             "family": family(cell.split(":")[1])}
            res_cells[lab] = r
    pools = {}
    for fam in FAMILIES:
        labs_all = [l for l in res_cells if family(l.split(":")[2]) == fam]
        for env in ("alfworld", "bfcl"):
            labs = [l for l in labs_all if l.startswith(env + ":")]
            if labs:
                pools[f"{fam}:{env}:pooled_equal_weight"] = {**pooled(draws, labs), "cells": labs}
                if fam == "W4":
                    ext_div[env] = float(np.mean([res_cells[l]["divergence_rate"] for l in labs]))
        if labs_all:
            pools[f"{fam}:all_envs:pooled_equal_weight"] = {**pooled(draws, labs_all), "cells": labs_all}
    line, tau = tau2_line(pools, ext_div)
    res = {
        "protocol": "fork-ext-v1 / protocol A", "analysis": "analysis/fork/analyze_ext.py", "input_fingerprint": fp,
        "script": {"path": str(Path(__file__).resolve().relative_to(ROOT)), "sha256": script_sha,
                   "analyze_dev_sha256": sha256(ROOT / "analysis/fork/analyze_dev.py"),
                   "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()},
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bootstrap": {"B": a.B, "seed": SEED, "scheme": "items with replacement within stratum (env x category); one run per item; draws shared by all cells"},
        "thresholds": {"g_min_pp": 100 * G_MIN},
        "success_definition": {"alfworld": "TextWorld infos['won']", "bfcl": "official multi_turn_checker valid"},
        "input_dirs": [L["dir"] for L in done], "incomplete_dirs": [L["dir"] for L in loaded if L["incomplete"]],
        "quarantined_dirs": quarantined, "models": models,
        "replay_guard": {"rule": "every divergent state of an admitted directory has effects.jsonl replay=true (W99o)", "pass": True,
                         "per_dir": replay_counts},
        "excluded_by_reason": {k: sum(1 for u in excluded if (u["excluded"].split(":")[0] if u["excluded"].startswith("search") else u["excluded"]) == k)
                               for k in sorted({(u["excluded"].split(":")[0] if u["excluded"].startswith("search") else u["excluded"]) for u in excluded})},
        "noop_sample": {L["dir"]: L.get("noop") for L in done},
        "cells": res_cells, "pooled": pools, "tau2_comparison": {"line": line, **tau},
        "n_input_files": len(files), "input_files": files, "seconds": round(time.time() - t0, 1),
    }
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    jp = OUT / f"ext_{utc}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    (OUT / f"ext_{utc}.md").write_text(markdown(res, jp))
    print(f"analyze_ext: wrote {jp.relative_to(ROOT)} ({res['seconds']} s)")


def markdown(res: dict, jp: Path) -> str:
    def f(x):
        return f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}]" if x else "n/a"
    cells = res["cells"]
    tl = "; ".join(f"{k}: r {v['all_pp']['rescue']['est']:.1f}, d {v['all_pp']['damage']['est']:.1f}, M {v['all_pp']['M']['est']:.1f}, "
                   f"G {f(v['all_pp']['G'])} pp ({v['n_states']}/{v['n_units']} divergent)" for k, v in cells.items() if "all_pp" in v)
    L = [f"**TL;DR** External-environment fork analysis (fork-ext-v1), ITEM-LEVEL inference (one run per item): two-sided "
         f"consequences on the full pool (r rescue, d new damage, M = r + d, G = r - d): {tl}. {res['tau2_comparison']['line']}", "",
         f"Source: `{jp.relative_to(ROOT)}` (fingerprint {res['input_fingerprint']}, script {res['script']['sha256'][:12]}, "
         f"git {res['script']['git_head'][:10]}). Units = items; pp; 95% bootstrap (items within env x category), B = "
         f"{res['bootstrap']['B']}, seed {res['bootstrap']['seed']}. G = Y_BQ - Y_QQ; A/C/I on L = 1 - Y. g_min = 3 pp.", "",
         f"Quarantined: {res['quarantined_dirs'] or 'none'}. Incomplete (skipped): {len(res['incomplete_dirs'])}. "
         f"Excluded by reason: {res['excluded_by_reason'] or 'none'}.", "",
         "| env:model:arm | items | divergent | r (pp) | d (pp) | M (pp) | both succeed | both fail | G_all | A (div.) | C (div.) | I (div.) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in cells.items():
        c, a = v["counts"], v["all_pp"]
        cd = v.get("conditional_on_divergence_pp") or {}
        L.append(f"| {k} | {v['n_units']} | {v['n_states']} ({100 * v['divergence_rate']:.0f}%) | {f(a['rescue'])} | {f(a['damage'])} | "
                 f"{f(a['M'])} | {c['both_succeed']} | {c['both_fail']} | {f(a['G'])} | {f(cd.get('A'))} | {f(cd.get('C'))} | {f(cd.get('I'))} |")
    L += ["", "Per category (G_all, pp):", ""]
    for k, v in cells.items():
        if len(v["by_category"]) > 1:
            L.append(f"- {k}: " + "; ".join(f"{s} {f(x['all_pp']['G'])} ({x['n_states']}/{x['n_units']})" for s, x in v["by_category"].items()))
    L += ["", "Divergence types (states; G_all contribution, pp):", ""]
    for k, v in cells.items():
        L.append(f"- {k}: " + "; ".join(f"{t} {x['n_states']} ({f(x['G_all_contribution_pp'])})" for t, x in v.get("by_type", {}).items()))
    L += ["", "Pools (equal weight per cell; W4 and stress never mixed):", ""]
    for k, v in res["pooled"].items():
        L.append(f"- {k} ({len(v['cells'])} cells): G {f(v.get('G'))}; A {f(v.get('A'))}; C {f(v.get('C'))}; I {f(v.get('I'))}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
