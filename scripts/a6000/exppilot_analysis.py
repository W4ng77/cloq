"""Analysis triggers for scripts/a6000/exppilot.py (W100r, responsibility B). Login node, CPU, timeout 30 min, each analysis
succeeds at most once (state file), outputs + one ledger line committed with explicit paths.

  newmethod_<m>  analysis/fork/analyze_newmethod.py --model <m>, only once analysis/fork/newmethod/expansion_<m>.json exists,
                 and when every panel + score task of the record's admitted cells is done: phase 1 (f01-f03 tau2 + score and
                 the queued BFCL forks) of the eligible cells, phase 2 (f04-f06, q8 reference cells with their gates) of
                 phase2_cells if expand = true. After T_deadline 2026-10-04 12:00 PDT it runs on whatever the protocol admits.
  sameprec       analysis/fork/analyze_sameprec.py and analyze_sameprec_w3.py once, after the 2026-10-04 00:00 PDT freeze
                 (SAMEPREC_PROTOCOL A1: longest complete prefix; W3 protocol: K = 3).
"""
from __future__ import annotations

import datetime as dt
import os
import subprocess

PDT = dt.timezone(dt.timedelta(hours=-7))
T_DEADLINE = dt.datetime(2026, 10, 4, 12, 0, tzinfo=PDT)  # NEWMETHOD_PANEL_PROTOCOL §5.4
T_FREEZE = dt.datetime(2026, 10, 4, 0, 0, tzinfo=PDT)     # SAMEPREC final analysis
CO = "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
ENV = "source scripts/a6000/env.sh >/dev/null 2>&1; export TMPDIR=/data/ziyangs/cloq_work/tmp; exec nice -n 10 python "


def required(P, m: str, rec: dict, idx: dict) -> list:
    p1 = [c for c in rec.get("eligible") or [] if not (m == "q8" and c in P.REF)]
    req = [f"nmp_{k}_{m}_{c}_{b}" for c in p1 for b in ("f01", "f02", "f03") for k in ("tau2", "score")]
    req += [t for t in idx if t.startswith(tuple(f"nmp_bfcl_{m}_{c}_" for c in p1))] if p1 else []
    if rec.get("expand") is True:
        req += [t for c in rec.get("phase2_cells") or [] for t in P.expected(m, c)]
    return req


def step(P, idx: dict) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    for m in ("m24", "q8"):
        key, rec = f"newmethod_{m}", P.record(m)
        if rec is None:  # never analyse a panel before its expansion decision record exists
            continue
        if P.st["analyses"].get(key, {}).get("ok"):
            run(P, key, "", "", "")  # done; only retries a pending commit
            continue
        req = required(P, m, rec, idx)
        left = [t for t in req if idx.get(t) != "done"]
        if left and now < T_DEADLINE:
            P.once_per(f"anwait_{m}", 3600, f"analysis {key}: waiting on {len(left)}/{len(req)} tasks, e.g. {left[:3]}")
            continue
        why = "all admitted panel+score tasks done" if not left else f"T_deadline passed, {len(left)}/{len(req)} not done"
        run(P, key, f"analysis/fork/analyze_newmethod.py --model {m}", f"newmethod_{m}_", why)
    if now >= T_FREEZE:
        run(P, "sameprec", "analysis/fork/analyze_sameprec.py", "sameprec_2", "SAMEPREC freeze 2026-10-04 00:00 PDT")
        run(P, "sameprec_w3", "analysis/fork/analyze_sameprec_w3.py", "sameprec_w3_", "SAMEPREC W3 freeze 2026-10-04 00:00 PDT")
    else:
        P.once_per("sp_wait", 3 * 3600, f"analysis sameprec / sameprec_w3: waiting for the freeze {T_FREEZE.isoformat()}")


def run(P, key: str, script: str, prefix: str, why: str) -> None:
    a = P.st["analyses"].setdefault(key, {})
    if a.get("ok"):
        return None if a.get("committed") or P.dry else commit(P, key, a)
    if a.get("attempts", 0) >= 3:
        return P.once_per(f"angive_{key}", 1e9, f"analysis {key}: 3 failed attempts, given up (see {a.get('log')})")
    if P.dry:
        return P.act(f"analysis {key} ({why}): timeout 1800 bash -c '{ENV}{script}'")
    out = P.ROOT / "analysis/fork/out"
    before, logf = set(os.listdir(out)), P.WORK / "logs" / f"exppilot_{key}_{P.utc()}.log"
    try:
        with open(logf, "w") as lf:
            rc = subprocess.run(["timeout", "1800", "bash", "-c", ENV + script], cwd=P.ROOT, stdout=lf, stderr=subprocess.STDOUT,
                                timeout=1900).returncode
    except subprocess.TimeoutExpired:
        rc = "timeout"
    new = sorted(f for f in set(os.listdir(out)) - before if f.startswith(prefix) and f.endswith((".json", ".md")))
    a.update(attempts=a.get("attempts", 0) + 1, log=str(logf))
    if rc != 0 or not new:
        return P.act(f"analysis {key} FAILED rc={rc} new={new} (attempt {a['attempts']}/3), log {logf}")
    a.update(ok=P.utc(), files=[f"analysis/fork/out/{f}" for f in new], why=why, committed=None)
    with open(out / "EXPPILOT_LEDGER.md", "a") as f:
        f.write(f"- {a['ok']} `{key}` ({why}): {', '.join(f'`{x}`' for x in a['files'])}\n")
    P.act(f"analysis {key} OK ({why}): {new}")
    P.save()
    return commit(P, key, a)


def commit(P, key: str, a: dict) -> None:
    """Only this analysis's outputs + the ledger (explicit paths), then pull --rebase --autostash and push."""
    paths = a["files"] + ["analysis/fork/out/EXPPILOT_LEDGER.md"]
    g = lambda *x: subprocess.run(["git", *x], cwd=P.ROOT, capture_output=True, text=True, timeout=300)  # noqa: E731
    r = g("add", "--", *paths)
    if r.returncode == 0 and g("diff", "--cached", "--quiet", "--", *paths).returncode:
        r = g("commit", "-q", "-m", f"exppilot: {key} analysis ({a['why']})\n\n" + "\n".join(a["files"]) + f"\n\n{CO}", "--", *paths)
    for args in (("pull", "-q", "--rebase", "--autostash", "origin", "master"), ("push", "-q", "origin", "master")):
        r = g(*args) if r.returncode == 0 else r
    if r.returncode == 0:
        a["committed"] = P.utc()
        P.act(f"committed + pushed {key}: {g('log', '--oneline', '-1').stdout.strip()}")
    else:
        P.once_per(f"git_{key}", 1800, f"git for {key} failed, retry next loop: {(r.stderr or r.stdout).strip()[-200:]}")
    P.save()
