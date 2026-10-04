"""Holdout QQ no-op acceptance audit (GPT review 2026-10-04; read-only): does the no-op sample analyze_holdout_confirm counted (provenance.noop_sample; holdout n 135, n_fail 0) cover every state the driver's
fixed rule made eligible (incl. noncomputable ones), and are all checks consistent? Rule = scripts/a6000/fork_driver.py:1538 (QQ queued at L1552/L1558): sampled iff int(sha256('noop|' + state_id)[:8], 16) / 16**8 <
noop_frac as recorded (branches*.json spec, else search.json spec of mode dev, else driver default 0.1). Each search row (task x cell x block; a split task, or an expected cell x block of the reference, without a row:
'no search row'; state file without a row: orphan) gets one of CATS in analyze_dev.load_dir's order (L270-338): Q block not admitted / trajectory changed = S unless the state is eligible (then N); search exclusions map
to a closed vocabulary (driver exclusion prefix or exception class). Per counted QQ: analyze_dev.noop_ok (L242) + fork_driver.noop_check (L272; final env hash vs orig_final_hash L264, a strict tau2 replay of the
original episode) + budget_check (L296); the same checks run, reported apart from the 135, on eligible states excluded before the no-op check whose QQ exists. Per analysed divergent state: Y_QQ (original) and the
BB/BQ/QB/QQ-rerun official_reward come from cloq.run_arm.basis_reward (source 'trajectory'; row = state = trajectory record; the basis formula over stored reward_info reproduces every side; run config all_ignore_basis,
loop guard off; run tau2 commit = current clean HEAD; the fork's own is not stored). Input identity: discovered dirs and load_dir's file digest equal the reference's. Outputs only counts, categories, booleans, input
sha256, git head, script sha256 (leak guard; no outcome, no outcome-derived count). --split holdout: split_guard first. usage: python analysis/fork/holdout_noop_audit.py (--split holdout | --dry-run-dev |
--selftest) [--snapshot S] [--ref R] -> out/holdout_noop_audit_*.{json,md}"""
from __future__ import annotations
import argparse, contextlib, glob, hashlib, io, json, os, re, shutil, subprocess, sys, tempfile, time, warnings  # noqa: E401
from collections import Counter, defaultdict
from pathlib import Path
sys.dont_write_bytecode, sys.path[:0] = True, [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[2] / "scripts/a6000")]  # no .pyc writes
import analyze_dev as AD, fork_driver as FD  # noqa: E401,E402  (FD: the driver's own hsel, noop_check, budget_check; CPU only)

R, OUT, WHO, TAU2, INP, SPLIT = AD.ROOT, AD.OUT, "holdout_noop_audit", None, {}, None
ROOTS, REF = {"holdout": "analysis/fork/holdout", "dev": "analysis/fork/telecom"}, {"holdout": "analysis/fork/out/holdout_confirm_20261002T012353Z.json", "dev": "analysis/fork/out/holdout_confirm_DRYRUN_DEV_20261001T144457Z.json"}
CATS = ("no divergence", "search-excluded", "divergent, not eligible (not sampled)", "eligible: QQ result missing", "eligible: QQ error (noncomputable)", "eligible: state excluded before the no-op check (noncomputable)",
        "eligible: checked pass", "eligible: checked fail", "loader-excluded (Q block not admitted / trajectory changed; not eligible or no divergence)")
CODE, QNE, SIDK = dict(zip(CATS, "0X.MENPFS")), "QQ on a non-eligible state", "state_id != sha([run, domain, task, t*])[:16]"
EXV = ("decision/trajectory count mismatch", "termination", "shadow failed", "B prompt ids differ from Q's recorded prompt", "repair: re-run not accepted")  # fork_driver.py L173-199, L1522
EXTRA, BAD = ("reward", "db_match", "official_reward", "env_hash_replay_vs_live", "env_hash_init", "history_prefix"), {"Y", "Y_BB", "Y_BQ", "Y_QB", "Y_QQ", "pattern", "patterns16", "k", "G", "H", "F", "I", "A", "C", "r", "d", "M", "outcomes", "success"}  # EXTRA: fork_driver.noop_check keys beyond noop_ok's
norm = lambda s: re.split(r" at t=| \d| \(|: ", re.sub(r"Q block \S+ ", "Q block ", str(s)))[0].strip()[:80]  # noqa: E731  load_dir's own (closed) reasons
exr = lambda row: f"exclusion: {next((p for p in EXV if str(row['exclusion']).startswith(p)), 'other')}" if row.get("exclusion") else "error: " + ((m := re.match(r"\s*([A-Za-z_]\w{0,60})\(", str(row.get("error")))) and m[1] or "other")  # noqa: E731
eligible = lambda sid, frac: int(FD.hsel("noop|" + sid)[:8], 16) / 16 ** 8 < frac  # noqa: E731  fork_driver.py:1538 verbatim
formula = lambda rec, task: FD.F.official_from_traj({**{k: v for k, v in rec.items() if k != "official_reward"}, "task": task})  # noqa: E731  basis_reward on the stored reward_info
ukey = lambda rid, dom, tid: (m := AD.RUN_RE.match(rid or "")) and (f"{m[1]}:{m[2][4:] if m[2].startswith('tel_') else m[2]}", m[3], f"{dom}:{tid}")  # noqa: E731  load_dir's parse
with contextlib.suppress(ImportError): __import__("loguru").logger.remove()  # noqa: E701  tau2 logs via loguru (incl. message content on a failed replay): silenced

def rd(p: Path, raw: bool = False):  # read-only; every file read is hashed into the audit record; outside --split holdout a holdout path is refused (lexical check, no stat)
    SPLIT != "holdout" and Path(os.path.normpath(p)).is_relative_to(R / ROOTS["holdout"]) and sys.exit(f"{WHO}: refusing to read a holdout path without --split holdout")
    INP[str(p.relative_to(R))] = hashlib.sha256(b := p.read_bytes()).hexdigest()
    return b if raw else json.loads(b)

def traj(rid: str, dom: str, tc: dict) -> tuple:  # (sha256, {task_id: record}, run config.json); the last record per task wins, as in cloq.fork.Block
    if (rid, dom) not in tc:
        b, c = (rd(p, True) if (p := R / "runs" / rid / dom / f).exists() else None for f in ("trajectory.jsonl", "config.json"))
        tc[rid, dom] = (None if b is None else hashlib.sha256(b).hexdigest(), {t["task_id"]: t for t in (json.loads(x) for x in (b or b"").decode().splitlines() if x.strip())}, json.loads(c) if c else {})
    return tc[rid, dom]

def orig_hash(st: dict, tr: dict):  # fork_driver.orig_final_hash (L264) from the trajectory record (no decisions.jsonl load); None if not computable
    with contextlib.suppress(Exception):
        from tau2.data_model.tasks import Task
        return FD.F.env_hashes(FD.F.restore_env(st["domain"], Task.model_validate(st["task"]), [FD.F.msg_from_dict(m) for m in tr["messages"]]))

def checks(st: dict, q: dict, tr) -> tuple:  # (analyze_dev.noop_ok, check booleans, fork_driver.noop_check ok); noop_check and budget_check fail independently
    (ok, c), f, b, oh = AD.noop_ok(st, q), {}, False, (orig_hash(st, tr) if tr and "error" not in q else None)
    with contextlib.suppress(Exception): f = FD.noop_check(st, q, {} if oh is None else oh)  # noqa: E701
    with contextlib.suppress(Exception): b = FD.budget_check(st, q)["ok"]  # noqa: E701
    c |= {**{k: bool(f.get(k)) for k in EXTRA}, "budget_check": bool(b), "env_hash_final_vs_orig_replay": None if oh is None or q.get("env_hash_final") is None else bool(f.get("env_hash_final_vs_orig_replay"))}
    return (ok, {}, None) if "error" in q else (ok, {**c, "env_hash_replay_vs_live": c["env_hash_replay_vs_live"] if "env_hash_replay" in q else None}, (None if oh is None else f.get("ok")))

def evalrule(row: dict, st: dict, r4: dict, tr, cf: dict) -> dict:  # evaluation-rule booleans: original (Y_QQ) vs BB/BQ/QB and the QQ re-run
    o, arms, tr = st["orig"], [r4[a] for a in ("BB", "BQ", "QB")] + ([r4["QQ"]] if "QQ" in r4 and "error" not in r4["QQ"] else []), tr if tr and tr.get("task") else None
    return {"orig_source_trajectory": o.get("official_reward_source") == "trajectory", "orig_row_eq_state": [row.get(f"orig_{k}") for k in ("official_reward", "termination", "db_match")] == [o.get(k) for k in ("official_reward", "termination_reason", "db_match")],
            "orig_trajectory_record_eq_state": bool(tr) and FD.F.sha(tr["task"]) == st.get("task_sha") and tr.get("official_reward") == o.get("official_reward"), "orig_basis_formula_reproduces": bool(tr) and formula(tr, tr["task"]) == tr.get("official_reward"),
            "orig_run_eval_all_ignore_basis": str(cf.get("evaluation_type_at_run")).startswith("all_ignore_basis"), "orig_loop_guard_off": cf.get("loop_guard") is None and o.get("termination_reason") != "loop_early_stop",
            "arms_carry_basis_fields": all({"official_reward", "env_assert_all", "reward", "db_match"} <= set(x) for x in arms), "arms_basis_formula_reproduces": all(formula(x, st["task"]) == x.get("official_reward") for x in arms),
            "run_tau2_commit_eq_current_clean_head": (st.get("versions") or {}).get("tau2_commit") == TAU2}

def audit_dir(d: Path, snap: dict, tc: dict, recs: dict, anm: dict, fracs: dict, X: Counter) -> None:
    rel, s, bj, seen = str(d.relative_to(R)), (lambda x: x if isinstance(x, dict) else {"rows": x})(rd(d / "search.json")), [rd(p) for p in sorted(d.glob("branches*.json"))], set()
    fr = [x["spec"].get("noop_frac", 0.1) for x in bj if isinstance(x.get("spec"), dict)] or ([s["spec"].get("noop_frac", 0.1)] if (s.get("spec") or {}).get("mode") == "dev" else [])
    frac = fracs.setdefault(rel, {"noop_frac": fr[0] if fr else 0.1, "n_specs_recording_it": len(fr), "consistent": len(set(fr)) <= 1})["noop_frac"]
    drec = {r["state_id"]: r for x in bj for r in x.get("rows") or [] if isinstance(r, dict) and "state_id" in r}
    bf = {p.stem.split("_")[0]: p for p in sorted((d / "branches").glob("*.json")) if (p.stem.split("_", 1)[1] if "_" in p.stem else "") in ("", "fwd")}  # load_dir's rule
    for row in s["rows"]:
        if not (key := isinstance(row, dict) and ukey(row.get("run_id"), row.get("domain"), row.get("task_id"))):
            X["search rows without a parsable run_id (unattributable)"] += 1
            continue
        rid, dom, sid, ex, st, r4 = row["run_id"], row["domain"], (row.get("state_id") if row.get("t_star") is not None else None), bool(row.get("exclusion") or "error" in row), None, None
        (tsha, trs, cf), fz, el = traj(rid, dom, tc), (snap["frozen"].get(rid) or {}).get(dom), sid and eligible(sid, frac)
        an0 = f"Q block {rid}/{dom} not admitted in snapshot" if fz is None else "trajectory.jsonl differs from the snapshot" if tsha != fz["files"]["trajectory.jsonl"]["sha256"] else None
        an = an0 or (f"search: {row.get('exclusion') or row.get('error')}"[:200] if ex else None)  # load_dir's exclusion string (compared, never written)
        if sid:
            seen.add(sid)
            X[SIDK] += FD.F.sha([rid, dom, row["task_id"], row["t_star"]])[:16] != sid
            st, r4 = (rd(p) if (p := d / "states" / f"{sid}.json").exists() else None), (rd(bf[sid]) if sid in bf else None)
            bad, y0 = [b for b in ("BB", "BQ", "QB") if r4 is not None and (b not in r4 or "error" in r4[b])], AD.success(dom, {"db_match": row.get("orig_db_match"), "official_reward": row.get("orig_official_reward"), "termination_reason": row.get("orig_termination")})
            an = an or ("state without branches" if st is None or r4 is None else "state orig outcome != search row outcome" if AD.success(dom, st["orig"]) != y0 else f"branch error {bad}" if bad else None)
        anm[(rel, rid, key[2])], rec = an, {"dir": rel, "eligible": el, "qq": (qq := bool(r4) and "QQ" in r4)}
        cat, sub = (CATS[1], exr(row)) if ex else (CATS[8] if an0 and not el else CATS[0] if not sid else CATS[2] if not el else CATS[5] if an else CATS[3] if not qq else CATS[4] if "error" in r4["QQ"] else None, norm(an) if an else "")
        if cat == CATS[5] and qq and st and "error" not in r4["QQ"]:  # eligible, excluded before the no-op check, QQ present: checked apart from the 135
            ok, c, _ = checks(st, r4["QQ"], trs.get(row["task_id"]))
            rec.update(xchecks=c, xok=ok and all(v is not False for v in c.values()))
        if sid and an is None:
            if qq:  # load_dir appends a no-op record here, eligible or not
                (ok, c, fd), rv = checks(st, r4["QQ"], trs.get(row["task_id"])), (x := drec.get(sid) or {}).get("a_noop_QQ") or x.get("noop_check") or (x.get("checks") or {}).get("noop_QQ")
                X.update({"driver-recorded no-op verdicts": rv is not None, "driver-recorded verdicts = fork_driver.noop_check now": rv is not None and rv.get("ok") == fd})
                rec.update(ad_record=True, ad_ok=ok, checks=c)
                cat = cat or (CATS[6] if ok and all(v is not False for v in c.values()) else CATS[7])
            rec["eval"] = evalrule(row, st, r4, trs.get(row["task_id"]), cf)
        recs[key].append({**rec, "cat": cat, "sub": sub})
    for p in [p for p in sorted((d / "states").glob("*.json")) if p.stem not in seen]:  # orphan: the driver branches every state file; no row names it
        st, el, r4 = rd(p), eligible(p.stem, frac), (rd(bf[p.stem]) if p.stem in bf else None)
        recs[ukey(st.get("run_id"), st.get("domain"), st.get("task_id")) or ("?", "?", p.stem)].append({"dir": rel, "eligible": el, "qq": bool(r4) and "QQ" in r4, "cat": CATS[5 if el else 2], "sub": "orphan state (no search row)"})

def audit(dirs: list, snap: dict, tasks: list, split: str | None, expect=frozenset()) -> dict:
    tc, cache, recs, anm, fracs, X, by, pt = {}, {}, defaultdict(list), {}, {}, Counter(), defaultdict(Counter), defaultdict(lambda: defaultdict(dict))
    loaded, units = (lo := [AD.load_dir(d, snap, cache) for d in dirs]), [u for L in lo for u in L["units"]]  # = analyze_holdout_confirm.load: the no-op records it counted
    guard, _ = AD.split_guard(units, split, WHO) if split else None, [audit_dir(d, snap, tc, recs, anm, fracs, X) for d in dirs]  # guard first (dev: aborts on any holdout unit)
    have, ecb = {k[:2] for k in recs}, sorted({k[:2] for k in recs} | set(expect))  # expected (cell, block) without any row: every task 'no search row'
    [recs.setdefault((*cb, t), [{"dir": None, "eligible": None, "qq": None, "cat": CATS[1], "sub": "no search row"}]) for cb in ecb for t in tasks]
    for (c, b, t), rs in sorted(recs.items()):
        by[f"{c}|{b}"].update([r["cat"] for r in rs] + [QNE] * sum(bool(r["qq"] and r["eligible"] is False) for r in rs))
        pt[c][b][t] = [["q" if r["cat"] == CATS[2] and r["qq"] else CODE[r["cat"]], r["sub"], r["dir"]] + ([{x: v for x, v in r["checks"].items() if v is not True}] if r.get("ad_record") else []) for r in rs]
    flat = [r for rs in recs.values() for r in rs]
    chk, xc, ev, tot, lu = [r for r in flat if r.get("ad_record")], [r for r in flat if "xok" in r], [r["eval"] for r in flat if "eval" in r], sum(by.values(), Counter()), [u for u in units if not u.get("excluded", "").startswith("not in split")]
    cnt = lambda ds: {k: dict(Counter("not computable" if x.get(k) is None else str(x[k]) for x in ds)) for k in sorted({k for x in ds for k in x})}  # noqa: E731
    n_ad, ad_fail, mis = sum(len(L["noop"]) for L in loaded), len({(L["dir"], x["state_id"]) for L in loaded for x in L["noop"] if not x["ok"]}), sum(anm.get((u["dir"], u["run_id"], u["task"]), "missing") != u.get("excluded") for u in lu)
    B = {"all_eligible_checked": sum(tot[c] for c in CATS[3:6]) == 0, "all_checks_pass": all(r["ad_ok"] and all(v is not False for v in r["checks"].values()) for r in chk), "eval_rule_consistent": all(all(e.values()) for e in ev),
         "env_hash_computed_for_all_checked": all(r["checks"].get("env_hash_final_vs_orig_replay") is not None for r in chk if r["checks"]), "no_qq_on_non_eligible": tot[QNE] == 0, "noop_frac_consistent": all(f["consistent"] for f in fracs.values()),
         "state_ids_consistent": X[SIDK] == 0, "classification_matches_loader": mis == 0 and len(lu) == len(anm), "audit_records_eq_analyze_dev": len(chk) == n_ad, "excluded_eligible_qq_checks_pass": all(r["xok"] for r in xc), "expected_cell_blocks_present": set(expect) <= have}
    return {"guard": guard, "noop_frac_by_dir": fracs, "by_cell_block": {k: dict(v) for k, v in by.items()}, "totals": dict(tot), "B": B, "sub_reasons": dict(Counter(f"{CODE[r['cat']]} {r['sub']}" for r in flat if r["sub"])),
            "noop_checks": cnt([r["checks"] for r in chk if r["checks"]]), "noop_checks_excluded_eligible": cnt([r["xchecks"] for r in xc]), "eval_rule": {"n_states": len(ev), **cnt(ev)}, "misc_counts": dict(X), "per_task": {c: dict(v) for c, v in pt.items()},
            "loader_files_digest": hashlib.sha256(json.dumps({k: v for L in loaded for k, v in L["files"].items()}, sort_keys=True).encode()).hexdigest(),  # = analyze_holdout_confirm provenance.input_files_digest_sha256
            "reconcile": {"n_records_analyze_dev": n_ad, "n_fail_analyze_dev": ad_fail, "n_records_this_audit": len(chk), "n_units_analyze_dev": len(lu), "n_units_this_audit": len(anm), "n_unit_status_mismatches": mis,
                          "n_excluded_eligible_qq_checked": len(xc), "n_pass_with_uncomputable_check": sum(r["cat"] == CATS[6] and None in r["checks"].values() for r in chk)}}

def leak(o, path: str = "") -> None:  # structural guard (explicit raise, survives python -O): no outcome-named key, no float except noop_frac
    ((isinstance(o, dict) and BAD & set(o)) or (isinstance(o, float) and not path.endswith("noop_frac"))) and sys.exit(f"{WHO}: forbidden key or float at {path}")
    [leak(v, f"{path}/{k}") for k, v in (o.items() if isinstance(o, dict) else enumerate(o) if isinstance(o, list) else ())]

def md(o: dict, jp: Path) -> str:
    B, rc, T, pt, cols, L = o["booleans"], o["reconcile"], o["totals"], o["per_task"], list(CATS) + [QNE], ["> **DRY RUN ON DEV**: telecom dev blocks f01-f06 as a pseudo-holdout; proves the audit runs end to end; says nothing about the holdout.", ""] if o["split"] == "dev" else []
    L += [f"**TL;DR** {o['label']}: of {sum(T.get(c, 0) for c in CATS[3:8])} eligible states (fixed hash rule, noop_frac {sorted({v['noop_frac'] for v in o['noop_frac_by_dir'].values()})}), {T.get(CATS[6], 0)} pass "
          f"({rc['n_pass_with_uncomputable_check']} with an uncomputable check) and {T.get(CATS[7], 0)} fail the no-op checks; unchecked: QQ missing {T.get(CATS[3], 0)}, QQ error {T.get(CATS[4], 0)}, excluded before the check "
          f"{T.get(CATS[5], 0)} (of which {rc['n_excluded_eligible_qq_checked']} have a QQ, checked apart). analyze_dev counted {rc['n_records_analyze_dev']} no-op records (fail {rc['n_fail_analyze_dev']}) vs reference "
          f"{o['ref']['noop_sample']}; this audit {rc['n_records_this_audit']} ({T.get(QNE, 0)} on non-eligible states). " + "; ".join(f"{k} **{v}**" for k, v in B.items()) + ".", "", f"# QQ no-op acceptance audit, {o['split']} ({o['utc']})", "",
          f"Script `{o['script']['path']}` sha256 `{o['script']['sha256'][:16]}`, git `{o['script']['git_head'][:10]}`; snapshot `{o['snapshot']['path']}` (= reference's: {o['snapshot']['equals_ref']}); reference `{o['ref']['path']}`; "
          f"tau2 HEAD `{o['tau2_head']}`; rule {o['rule']}; repair log {o['repair_log']}; dirs with search.json, states/ or branches/ outside the discovered set: {o['undiscovered_dirs']}. {o['n_inputs']} input files read, digest "
          f"`{o['inputs_digest'][:16]}`; load_dir file digest `{o['loader_files_digest'][:16]}` (per-file sha256 in `{jp.relative_to(R)}`).", "", "## Categories per (cell, block)", "", "| cell, block | " + " | ".join(f"{CODE.get(c, 'q')}: {c}" for c in cols) + " |",
          "|---" * (len(cols) + 1) + "|"] + [f"| {k.replace('|', ' ')} | " + " | ".join(str(v.get(c, 0)) for c in cols) + " |" for k, v in sorted(o["by_cell_block"].items()) + [("total", T)]]
    L += [x for h, k in (("No-op checks on every QQ record load_dir reaches", "noop_checks"), ("No-op checks on eligible states excluded before the check, QQ present (not in the 135)", "noop_checks_excluded_eligible"),
                         ("Evaluation rule on analysed divergent states", "eval_rule")) for x in ["", f"## {h} (value: count)", "", "| check | counts |", "|---|---|"] + [f"| {c} | {v} |" for c, v in o[k].items()]]
    L += ["", f"Other counts: {json.dumps(o['misc_counts'])}. Sub-reasons: {json.dumps(o['sub_reasons'])}. Reconcile: {json.dumps(rc)}.", "", "## Per-task codes", "", "One code per block, blocks in header order: "
          + ", ".join(f"{v} {k}" for k, v in CODE.items()) + f", q {QNE}, - no record; '+' several rows.", "", "| task | " + " | ".join(f"{c} ({' '.join(sorted(pt[c]))})" for c in sorted(pt)) + " |", "|---" * (len(pt) + 1) + "|"] + [
          f"| {t.replace('|', '/')} | " + " | ".join("".join((lambda e: e[0][0] + "+" * (len(e) > 1))(pt[c][b].get(t, [["-"]])) for b in sorted(pt[c])) for c in sorted(pt)) + " |" for t in sorted({t for c in pt for b in pt[c] for t in pt[c][b]})]
    return "\n".join(L + ["", "## Method", "", "```", __doc__.strip(), "```"]) + "\n"

def main():
    global TAU2, SPLIT
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    [ap.add_argument(f"--{n}") for n in ("split", "snapshot", "ref")], [ap.add_argument(f"--{n}", action="store_true") for n in ("dry-run-dev", "selftest")]
    (a := ap.parse_args()).selftest and sys.exit(selftest())
    a.dry_run_dev == (a.split == "holdout") and sys.exit(f"{WHO}: use exactly one of --split holdout, --dry-run-dev, --selftest")
    split, t0, g = "dev" if a.dry_run_dev else "holdout", time.time(), lambda *c: subprocess.run(["git", "--no-optional-locks", "-C", *c], capture_output=True, text=True).stdout.strip()  # noqa: E731
    AD.split_guard([], "holdout", WHO) if split == "holdout" else None  # refuses unless the prereg sha256 = splits_v1 holdout.prereg_sha256; before any holdout file is opened
    SPLIT, TAU2 = split, g(str(R / "third_party/tau2-bench"), "rev-parse", "HEAD") + ("+dirty" if g(str(R / "third_party/tau2-bench"), "status", "--porcelain") else "")  # dev: rd refuses holdout paths (--ref, --snapshot)
    ref, root, INP["docs/insights/PREREG_FORK_CONFIRM.md"] = rd(ref_p := R / (a.ref or REF[split])), ROOTS[split], AD.sha256(R / "docs/insights/PREREG_FORK_CONFIRM.md")
    snap, ns, tasks = rd(snap_p := R / (a.snapshot or ref["snapshot"]["path"])), ref["provenance"]["noop_sample"], sorted(f"telecom:{t}" for t in rd(AD.SPLITS)["splits"][split]["tasks"]["telecom"])
    dirs = [Path(p).parent for p in sorted(glob.glob(str(R / root / "**" / "search.json"), recursive=True)) if (Path(p).parent / "states").is_dir() and (Path(p).parent / "branches").is_dir()]
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), warnings.catch_warnings(action="ignore"):  # tau2/pydantic prints (task or env state) never reach the terminal
        res = audit(dirs, snap, tasks, split, {(c, b) for c in ref["cells"] for b in ref["blocks"]["primary"]})
    rl, utc, rel, und = R / root / "REPAIR_LOG.jsonl", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), [str(d.relative_to(R)) for d in dirs], len({str(Path(p).parent) for n in ("search.json", "states", "branches") for p in glob.glob(str(R / root / "**" / n), recursive=True)} - {str(d) for d in dirs})
    B = {**res.pop("B"), "n135_reconciles": res["reconcile"]["n_records_analyze_dev"] == res["reconcile"]["n_records_this_audit"] == ns["n"] and res["reconcile"]["n_fail_analyze_dev"] == ns["n_fail"],
         "input_dirs_eq_ref": sorted(rel) == sorted(ref["provenance"]["input_dirs"]), "input_files_digest_eq_ref": res["loader_files_digest"] == ref["provenance"]["input_files_digest_sha256"], "all_fork_dirs_discovered": und == 0}
    o = {"label": "DRY RUN ON DEV (telecom dev f01-f06; proves execution only)" if split == "dev" else "telecom HOLDOUT QQ no-op acceptance audit", "split": split, "utc": utc, "script": {"path": "analysis/fork/holdout_noop_audit.py", "sha256": AD.sha256(__file__), "git_head": g(str(R), "rev-parse", "HEAD")}, "ref": {"path": str(ref_p.relative_to(R)), "noop_sample": ns},
         "snapshot": {"path": str(snap_p.relative_to(R)), "id": snap.get("snapshot_id"), "equals_ref": INP[str(snap_p.relative_to(R))] == ref["snapshot"]["sha256"]}, "tau2_head": TAU2, "categories": CODE,
         "rule": "fork_driver.py:1538 int(sha256('noop|' + state_id)[:8], 16) / 16**8 < noop_frac (recorded spec)", "input_dirs": rel, "undiscovered_dirs": und, "repair_log": {"present": rl.exists(), "n_entries": len(rd(rl, True).splitlines()) if rl.exists() else 0},
         **res, "booleans": B, "seconds": round(time.time() - t0), "n_inputs": len(INP), "inputs_digest": hashlib.sha256(json.dumps(INP, sort_keys=True).encode()).hexdigest(), "inputs_sha256": INP}
    leak(o)
    (jp := OUT / f"holdout_noop_audit_{'DRYRUN_DEV_' if split == 'dev' else ''}{utc}.json").write_text(json.dumps(o, indent=1)), jp.with_suffix(".md").write_text(md(o, jp))
    print(f"{WHO}: wrote {jp.relative_to(R)} and .md ({o['seconds']} s); booleans {json.dumps(B)}")

def selftest():  # synthetic fork dir under a temp root: every category, the QQ flag, loader reconciliation, leak guard; nothing written under the repo
    global R, TAU2, orig_hash
    R = AD.ROOT = T = Path(tempfile.mkdtemp(prefix="noop_audit_selftest_"))
    dom, r1, r2, TAU2, orig_hash = "telecom", "a6k2_q8_tel_awq_w4_f01", "a6k2_q8_tel_awq_w4_f02", "t2", lambda st, tr: tr.get("_h")  # synthetic final env hash (the real one replays the original episode in tau2)
    sid, put = lambda r, t: FD.F.sha([r, dom, t, 1])[:16], lambda p, x: (p.parent.mkdir(parents=True, exist_ok=True), p.write_text(x if isinstance(x, str) else json.dumps(x)))  # noqa: E731
    pick = lambda r, e, n, pre: [t for t in (f"{pre}{i}" for i in range(999)) if eligible(sid(r, t), .5) == e][:n]  # noqa: E731
    E, N, E2, RI, TK = pick(r1, True, 8, "x"), pick(r1, False, 5, "x"), pick(r2, True, 1, "y"), {"db_check": {"db_match": True}}, {"id": "x", "evaluation_criteria": {"reward_basis": ["DB"]}}
    A = {"termination_reason": "user_stop", "reward": 1.0, "db_match": True, "official_reward": 1.0, "env_assert_all": None, "reward_info": RI, "suffix_sha": "s", "decisions": [{"prompt_ids_sha": "p"}], "step_count_final": 5,
         "num_errors_final": 0, "budget_recount": [5, 0], "counters_tau2_default": [0, 0], "env_hash_final": {"db": "h"}, "env_hash_replay": {"db": "h"}, "env_hash_init_ok": True, "prefix_ok": True}
    O, d, rows = {**{k: A[k] for k in ("termination_reason", "reward", "db_match", "official_reward", "suffix_sha")}, "official_reward_source": "trajectory", "suffix_prompt_ids_sha": ["p"], "budget_final": [5, 0]}, T / "analysis/fork/telecom/q8_awq_w4/g1", []
    spec = {E[0]: (r1, {}, 1, {"QQ": A}), E[1]: (r1, {}, 1, {"QQ": {**A, "suffix_sha": "z"}}), E[2]: (r1, {}, 1, {}), E[3]: (r1, {}, 1, {"QQ": {"error": "x"}}), E[4]: (r1, {}, 1, {"BB": {"error": "x"}, "QQ": A}),
            E[5]: (r1, {}, 0, None), E[6]: (r1, {"orig_official_reward": 0.0}, 1, {"QQ": A}), E[7]: (None, {}, 1, {"QQ": A}), N[0]: (r1, {}, 1, {}), N[1]: (r1, {}, 1, {"QQ": A}), N[2]: (r1, {"t_star": None}, 0, None), N[3]: (r1, {"t_star": None, "exclusion": "decision/trajectory count mismatch 3 vs 4"}, 0, None),
            N[4]: (r1, {}, 1, {"BB": {**A, "db_match": False, "reward_info": {"db_check": {"db_match": False}}}}), E2[0]: (r2, {}, 1, {"QQ": A}), "zS": (r2, {"t_star": None}, 0, None)}
    [put(T / "runs" / r / dom / f, x) for r, ts in ((r1, E + N), (r2, E2)) for f, x in (("trajectory.jsonl", "".join(json.dumps({**O, "reward_info": RI, "task_id": t, "task": TK, "messages": [], "_h": {"db": "h"}}) + "\n" for t in ts)), ("config.json", {"evaluation_type_at_run": "all_ignore_basis (x)", "loop_guard": None}))]
    for t, (r, up, w, arms) in spec.items():
        rows += [{"run_id": r, "domain": dom, "task_id": t, "t_star": 1, "state_id": sid(r, t), "orig_official_reward": 1.0, "orig_termination": "user_stop", "orig_db_match": True, **up}] if r else []
        w and put(d / "states" / f"{sid(r or r1, t)}.json", {"state_id": sid(r or r1, t), "run_id": r or r1, "domain": dom, "task_id": t, "decision_idx": 1, "task": TK, "task_sha": FD.F.sha(TK), "orig": O, "divergence": {"category": "tool_args"}, "versions": {"tau2_commit": "t2"}, "budget": dict(zip(("steps_left", "errors_left", "max_steps", "max_errors", "steps_used", "errors_used"), (9, 9, 99, 9, 1, 0)))})
        arms is None or put(d / "branches" / f"{sid(r or r1, t)}.json", {"BB": A, "BQ": A, "QB": A, **arms})
    put(d / "search.json", {"spec": {"mode": "dev", "noop_frac": 0.5}, "rows": rows}), put(d / "branches.json", {"spec": {"mode": "dev", "noop_frac": 0.5}, "rows": []})
    try:
        res = audit([d], {"frozen": {r1: {dom: {"files": {"trajectory.jsonl": {"sha256": AD.sha256(T / "runs" / r1 / dom / "trajectory.jsonl")}}}}}}, [f"telecom:{t}" for t in E + N + ["nosrow"]], None, {("q8:awq_w4", f"f0{i}") for i in (1, 2, 3)})
        want = {("f01", t): c for t, c in zip(E + N + ["nosrow"], "PFMENNNN.q0X.X")} | {("f02", E2[0]): "N", ("f02", "zS"): "S", ("f03", "nosrow"): "X"}
        got, B, rc, ev = {(b, t): res["per_task"]["q8:awq_w4"][b][f"telecom:{t}"][0][0] for b, t in want}, res["B"], res["reconcile"], res["eval_rule"]
        assert got == want and rc["n_records_analyze_dev"] == rc["n_records_this_audit"] == 4 and rc["n_fail_analyze_dev"] == 2 and rc["n_unit_status_mismatches"] == 0 and B["classification_matches_loader"] and B["audit_records_eq_analyze_dev"] and B["state_ids_consistent"] and B["env_hash_computed_for_all_checked"] and not (B["all_eligible_checked"] or B["all_checks_pass"] or B["eval_rule_consistent"] or B["no_qq_on_non_eligible"] or B["expected_cell_blocks_present"]), B
        assert rc["n_excluded_eligible_qq_checked"] == 3 and B["excluded_eligible_qq_checks_pass"] and res["sub_reasons"]["N orphan state (no search row)"] == res["sub_reasons"]["X exclusion: decision/trajectory count mismatch"] == 1 and ev["arms_basis_formula_reproduces"] == {"True": 6, "False": 1} and ev["orig_run_eval_all_ignore_basis"] == {"True": 7} and [exr({"error": "ValueError('x=1.0')"}), exr({"exclusion": "termination infrastructure_error (infrastructure)"}), exr({"exclusion": "x 1.0"})] == ["error: ValueError", "exclusion: termination", "exclusion: other"], res
        leak(res)
    finally:
        shutil.rmtree(T, ignore_errors=True)
    print(f"{WHO} selftest OK: codes {sorted(set(got.values()))} reproduced, analyze_dev.load_dir count reconciles, leak guard passes (nothing written)")

if __name__ == "__main__":
    main()
