"""NEWMETHOD_PANEL_PROTOCOL A7.4 / A7.E2 (W100ai): per-arm report of the A7 re-runs, effect-blind (no outcome value printed).

Per named arm: cell, block, state_key, arm, A7.2 class, status (recovered / failed again / persistent timeout / pending),
longest re-run request (s), state identity, shadow identity. Per task: server identity vs a7_expect, spec arms == recovery
arms, one recovery directory. A7.E2: on a no-op-sampled bank_u row (same hash rule as bank_u) whose BB arm was re-run,
the re-run BB must reproduce the original source suffix (fork_driver.noop_check, equality only).
Exit 0 only if every check passes and nothing is pending.

usage: python scripts/a6000/a7_report.py [--write]
"""
from __future__ import annotations

import argparse, glob, hashlib, json, sys
from pathlib import Path

ROOT, WORK = Path("/data/ziyangs/cloq"), Path("/data/ziyangs/cloq_work")
sys.path.insert(0, str(ROOT / "scripts/a6000"))


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--write", action="store_true"); a = ap.parse_args()
    cls = {(x["cell"], x["block"], x["state_key"], x["arm"]): x["class"] for x in json.loads((ROOT / "analysis/fork/kivi_recovery/failed_arms.json").read_text())}
    rows, tasks, bad = [], {}, []
    for f in sorted(glob.glob(str(WORK / "queue/*/a7_rr1_q8_*.json"))):
        t = json.loads(Path(f).read_text()); st = Path(f).parent.name; fk = t["fork"]; out = ROOT / fk["out"]
        info = {"queue": st, "arms": len(fk["arms"])}
        if st != "done":
            info["pending"] = True; bad.append(f"{t['id']}: {st}")
        else:
            srv = json.loads((WORK / "logs/tasks" / f"{t['id']}.servers.json").read_text())
            got = {r: {k: srv[r].get(k) for k in ("canary", "ckpt_sha256", "effective_config_sha")} | {"hook_version": (srv[r].get("effective_config") or {}).get("hook_version")} for r in ("B", "Q")}
            info["servers_identical"] = got == t["a7_expect"]
            info["one_recovery_dir"] = sorted(p.name for p in out.parent.iterdir()) == ["rr1"]
            rec = {x["state_key"]: x for x in map(json.loads, filter(str.strip, (out / "recovery_rows.jsonl").read_text().splitlines()))}
            info["arms_match_spec"] = sorted([sk, arm] for sk, x in rec.items() for arm in x.get("arms", [])) == sorted(fk["arms"])
            for k in ("servers_identical", "one_recovery_dir", "arms_match_spec"):
                if not info[k]: bad.append(f"{t['id']}: {k}")
            src = ROOT / fk["src_out"]
            for sk, x in sorted(rec.items()):
                br = json.loads((out / "branches" / f"{sk}.json").read_text()) if (out / "branches" / f"{sk}.json").exists() else {}
                noop = int(hashlib.sha256(f"bank-u-noop-v1|{sk}|{fk['cell']}".encode()).hexdigest()[:8], 16) / 16 ** 8 < 0.1
                for arm in x.get("arms", []):
                    wall = max([d.get("wall_seconds") or 0 for d in (br.get(arm) or {}).get("decisions") or []] or [0])
                    how = x.get("arm_source", {}).get(arm, x.get("missing_reason", "refused"))
                    status = "recovered" if how == "rerun" and wall < 600 else "persistent timeout" if how == "rerun" or "Timeout" in str(how) else "failed again"
                    r = {"cell": fk["cell"], "block": fk["block"], "state_key": sk, "arm": arm, "class": cls.get((fk["cell"], fk["block"], sk, arm)),
                         "status": status, "max_request_s": round(wall, 1), "state_identical": all((x.get("state_identical") or {}).values()),
                         "shadow_identical": x.get("shadow_identical")}
                    if not r["state_identical"]: bad.append(f"{sk} {arm}: state not identical")
                    if noop and arm == "BB" and status == "recovered":  # A7.E2 no-op equality on the re-run BB
                        saved, sys.argv = sys.argv, sys.argv[:1]
                        import fork_driver as FD  # noqa: E402 (CPU only: state rebuild + noop_check)
                        sys.argv = saved
                        m = {q["state_key"]: q for q in json.loads((ROOT / fk["manifest"]).read_text())["rows"] if q["state_key"] == sk}[sk]
                        blk = FD.F.Block(ROOT, m["source_run"], m["domain"]); s = FD.F.make_state(blk, m["task_id"], m["t"])
                        chk = FD.noop_check(s, br["BB"], FD.orig_final_hash(s, blk))
                        r["noop_check_ok"] = bool(chk.get("ok"))
                        if not r["noop_check_ok"]: bad.append(f"{sk} BB: no-op check failed {[k for k, v in chk.items() if v is False]}")
                    rows.append(r)
        tasks[t["id"]] = info
    rep = {"tasks": tasks, "arms": rows, "problems": bad, "ok": not bad}
    md = ["# A7 re-runs: per-arm report (effect-blind; NEWMETHOD A7.4, A7.E2)", "", f"**TL;DR** ok = {rep['ok']}; problems: {bad or 'none'}", "",
          "| cell | block | state | arm | A7.2 class | status | longest request (s) | state id. | shadow id. | no-op (BB) |", "|---|---|---|---|---|---|---|---|---|---|"]
    md += [f"| {r['cell']} | {r['block']} | {r['state_key']} | {r['arm']} | {r['class']} | {r['status']} | {r['max_request_s']} | {r['state_identical']} | {r['shadow_identical']} | {r.get('noop_check_ok', '–')} |" for r in rows]
    md += ["", "| task | queue | arms | servers = a7_expect | arms = spec | one rr dir |", "|---|---|---|---|---|---|"]
    md += [f"| {k} | {v['queue']} | {v['arms']} | {v.get('servers_identical', '–')} | {v.get('arms_match_spec', '–')} | {v.get('one_recovery_dir', '–')} |" for k, v in tasks.items()]
    print("\n".join(md[:4]))
    if a.write:
        (ROOT / "analysis/fork/kivi_recovery/A7_REPORT.json").write_text(json.dumps(rep, indent=1))
        (ROOT / "analysis/fork/kivi_recovery/A7_REPORT.md").write_text("\n".join(md) + "\n")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
