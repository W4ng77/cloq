"""Holdout FULL QQ no-op audit (W100av; docs/insights/HOLDOUT_QQFULL_PROTOCOL.md; read-only, counts only).
Reuses holdout_noop_audit.py unchanged (categories, noop_ok + noop_check + budget_check, evaluation-rule booleans, leak guard) with two
substitutions: every divergent state is eligible (noop_frac 1.0), and a state's QQ arm is read from
analysis/fork/holdout_qqfull/<cell>/gNN/branches/<state_id>.json (BB/BQ/QB stay the original files; the original QQ, where sampled, is
ignored). A state without a QQ-full file counts as 'eligible: QQ result missing' (coverage). Preconditions (protocol §3): each done
qqfull_hold_* task's Q server ckpt_sha256 and effective_config_sha equal its fork_hold_* original's.
--mirror reads QQ from the ORIGINAL branches instead (end-to-end self-check: must reproduce holdout_noop_audit's 135 pass / 1067 missing).
usage: python analysis/fork/holdout_qqfull_audit.py --split holdout [--mirror] -> out/holdout_qqfull_audit_*.{json,md}"""
from __future__ import annotations
import argparse, contextlib, glob, hashlib, io, json, sys, time, warnings  # noqa: E401
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import holdout_noop_audit as HA  # noqa: E402

AD, R, WHO, QDIR = HA.AD, HA.R, "holdout_qqfull_audit", Path("/data/ziyangs/cloq_work/queue")
HROOT, QROOT, CELLS = R / HA.ROOTS["holdout"], R / "analysis/fork/holdout_qqfull", ("q4_gptq_w4_d1", "q8_gptq_w4_d1", "q8_awq_w4")


def patch(mirror: bool) -> None:
    rd0 = HA.rd

    def rd(p: Path, raw: bool = False):
        q = Path(p)
        if raw or q.parent.name != "branches" or not q.is_relative_to(HROOT) or mirror:
            return rd0(p, raw)
        b, alt = rd0(p), QROOT / q.relative_to(HROOT)
        b.pop("QQ", None)
        return {**b, **({"QQ": rd0(alt)["QQ"]} if alt.exists() and "QQ" in json.loads(alt.read_text()) else {})}
    HA.rd, HA.eligible = rd, (lambda sid, frac: True)


def preconditions() -> dict:
    out = {}
    for cell in CELLS:
        for g in (f"g{k:02d}" for k in range(1, 7)):
            o, n = (json.load(open(p)) if (p := QDIR / "done" / f"{x}_hold_{cell}_{g}.json").exists() else None for x in ("fork", "qqfull"))
            if n is None:
                out[f"{cell}/{g}"] = "not done"
                continue
            so, sn = o["result"]["servers"]["Q"], n["result"]["servers"]["Q"]
            out[f"{cell}/{g}"] = {k: so.get(k) == sn.get(k) for k in ("ckpt_sha256", "effective_config_sha")}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", required=True, choices=["holdout"])
    ap.add_argument("--mirror", action="store_true")
    a = ap.parse_args()
    t0, g = time.time(), lambda *c: HA.subprocess.run(["git", "--no-optional-locks", "-C", *c], capture_output=True, text=True).stdout.strip()  # noqa: E731
    AD.split_guard([], "holdout", WHO)  # refuses unless the prereg is frozen; before any holdout file is opened
    HA.SPLIT, HA.TAU2 = "holdout", g(str(R / "third_party/tau2-bench"), "rev-parse", "HEAD") + ("+dirty" if g(str(R / "third_party/tau2-bench"), "status", "--porcelain") else "")
    patch(a.mirror)
    ref = HA.rd(R / HA.REF["holdout"])
    snap, tasks = HA.rd(R / ref["snapshot"]["path"]), sorted(f"telecom:{t}" for t in HA.rd(AD.SPLITS)["splits"]["holdout"]["tasks"]["telecom"])
    dirs = [Path(p).parent for p in sorted(glob.glob(str(HROOT / "**" / "search.json"), recursive=True)) if (Path(p).parent / "states").is_dir() and (Path(p).parent / "branches").is_dir()]
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), warnings.catch_warnings(action="ignore"):
        res = HA.audit(dirs, snap, tasks, "holdout", {(c, b) for c in ref["cells"] for b in ref["blocks"]["primary"]})
    T, C, pre = res["totals"], HA.CATS, preconditions()
    n_div = sum(T.get(c, 0) for c in C[2:8])  # divergent analysed + excluded-before-check states, all eligible here
    B = {"preconditions_all_done_and_equal": all(isinstance(v, dict) and all(v.values()) for v in pre.values()), "complete_coverage": sum(T.get(c, 0) for c in C[3:6]) == 0,
         "all_checked_pass": T.get(C[7], 0) == 0 and res["B"]["all_checks_pass"], "eval_rule_consistent": res["B"]["eval_rule_consistent"],
         "env_hash_computed_for_all_checked": res["B"]["env_hash_computed_for_all_checked"], "state_ids_consistent": res["B"]["state_ids_consistent"],
         "classification_matches_loader": res["B"]["classification_matches_loader"], "input_dirs_eq_ref": sorted(str(d.relative_to(R)) for d in dirs) == sorted(ref["provenance"]["input_dirs"])}
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    o = {"label": "telecom HOLDOUT full QQ no-op audit" + (" (MIRROR self-check: QQ from original branches)" if a.mirror else ""), "utc": utc, "mirror": a.mirror,
         "script": {"path": "analysis/fork/holdout_qqfull_audit.py", "sha256": AD.sha256(__file__), "base_sha256": AD.sha256(HA.__file__), "git_head": g(str(R), "rev-parse", "HEAD")},
         "protocol_sha256": AD.sha256(R / "docs/insights/HOLDOUT_QQFULL_PROTOCOL.md"), "tau2_head": HA.TAU2, "preconditions": pre, "n_states_eligible": n_div,
         "n_checked_pass": T.get(C[6], 0), "n_checked_fail": T.get(C[7], 0), "n_missing": T.get(C[3], 0), "n_qq_error": T.get(C[4], 0), "n_excluded_before_check": T.get(C[5], 0),
         "fail_or_uncomputable_by_check": {k: {v: n for v, n in cnt.items() if v != "True"} for k, cnt in res["noop_checks"].items() if set(cnt) - {"True"}},
         "by_cell_block": res["by_cell_block"], "totals": T, "noop_checks": res["noop_checks"], "eval_rule": res["eval_rule"], "sub_reasons": res["sub_reasons"], "booleans": B,
         "state_ids_digest": hashlib.sha256(json.dumps(sorted(p.stem for d in dirs for p in (d / "states").glob("*.json"))).encode()).hexdigest(),
         "seconds": round(time.time() - t0), "n_inputs": len(HA.INP), "inputs_digest": hashlib.sha256(json.dumps(HA.INP, sort_keys=True).encode()).hexdigest(), "inputs_sha256": HA.INP}
    HA.leak(o)
    jp = AD.OUT / f"holdout_qqfull_audit_{'MIRROR_' if a.mirror else ''}{utc}.json"
    jp.write_text(json.dumps(o, indent=1))
    jp.with_suffix(".md").write_text("\n".join([
        f"**TL;DR** {o['label']}: {o['n_checked_pass']} of {n_div} eligible states pass every no-op check, {o['n_checked_fail']} fail; QQ missing {o['n_missing']}, QQ error {o['n_qq_error']}, "
        f"excluded before the check {o['n_excluded_before_check']}. " + "; ".join(f"{k} **{v}**" for k, v in B.items()) + ".", "",
        f"# Holdout full QQ no-op audit ({utc})", "", f"Script sha256 `{o['script']['sha256'][:16]}` (base holdout_noop_audit.py `{o['script']['base_sha256'][:16]}`), git `{o['script']['git_head'][:10]}`, "
        f"protocol sha256 `{o['protocol_sha256'][:16]}`, tau2 `{o['tau2_head']}`; state_id list digest `{o['state_ids_digest'][:16]}`; {o['n_inputs']} inputs, digest `{o['inputs_digest'][:16]}`.", "",
        "## Preconditions (Q ckpt_sha256, effective_config_sha equal to the original fork)", "", *[f"- {k}: {v}" for k, v in pre.items()], "",
        "## Failing or uncomputable checks (check: value: count)", "", json.dumps(o["fail_or_uncomputable_by_check"]) or "{}", "", "## Totals by category", "",
        *[f"- {k}: {v}" for k, v in T.items()], "", f"Sub-reasons: {json.dumps(o['sub_reasons'])}", "", "## Method", "", "```", __doc__.strip(), "```", ""]))
    print(f"{WHO}: wrote {jp.relative_to(R)} and .md ({o['seconds']} s); pass {o['n_checked_pass']}/{n_div}, fail {o['n_checked_fail']}, missing {o['n_missing']}; booleans {json.dumps(B)}")


if __name__ == "__main__":
    main()
