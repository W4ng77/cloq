"""End-to-end test of the simrelay-v2 relay (W97) in a TEMPORARY relay root (never the real pending/ directory).

Phase A (real Claude Code calls, ~3 x $0.02): three v2 requests built exactly as a fork branch builds them (tau2's own
UserSimulator system prompt and role-flipped history of three frozen dev retail states, history cut after an agent
message; the third with an agent message containing a $ amount) go through cloq.user_llm.relay_call; the real
scripts/a6000/simrelay_cli.py daemon answers them. Checks: answer content non-empty, req_id / protocol / msg_sha256 echoed
and verified, msg_sha256 = canonical sha of the litellm list, frozen template sha, request file holds only the v2 keys,
the bookkeeping only in the meta/ sidecar, $ preserved in the rendered prompt.
Phase B (no Claude call): tampering. (1) an answer whose msg_sha256 is altered -> RelayIntegrityError; (2) an answer whose
req_id echo is altered -> RelayIntegrityError; (3) a request whose messages are altered after hashing -> the daemon
(--mock) rejects it without content -> RelayIntegrityError at the branch; (4) a correct mock answer is accepted.

usage: /data/ziyangs/cloq_work/envs/cloq/bin/python tests/test_simrelay_v2.py [--skip-real] [--out <json>]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/a6000"))
MODEL = "relay/claude-sonnet-5-5 (headless claude -p, one clean call per user turn)"
STATES = ["analysis/fork/dev/q4_gptq_w4_d1/g1/states/{}.json"]


def retail_requests(n: int = 3) -> list[list[dict]]:
    """Realistic litellm message lists (system + flipped history) from frozen dev retail states (no outcomes read)."""
    from cloq import fork as F
    from tau2.data_model.tasks import Task
    from tau2.runner.build import build_environment, build_user
    from tau2.user.user_simulator_base import is_valid_user_history_message
    from tau2.utils.llm_utils import to_litellm_messages

    man = json.loads((ROOT / "manifests/fork/simctrl_p_v1.json").read_text()) if (ROOT / "manifests/fork/simctrl_p_v1.json").exists() else None
    if man:
        files = [u["state_file"] for u in man["units"] if u["domain"] == "retail"][:n]
    else:
        files = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "analysis/fork/dev/q4_gptq_w4_d1/g1/states").glob("*.json"))
        files = [f for f in files if json.loads((ROOT / f).read_text())["domain"] == "retail"][:n]
    env = build_environment("retail")
    out = []
    for f in files:
        st = json.loads((ROOT / f).read_text())
        task = Task.model_validate(st["task"])
        u = build_user(st["run_config"].get("user", "user_simulator"), env, task, llm="expected", llm_args={})
        hist = [F.msg_from_dict(m) for m in st["history"]]
        us = u.get_init_state(message_history=[m for m in hist if is_valid_user_history_message(m)])
        msgs = to_litellm_messages(us.system_messages + us.flip_roles())
        while len(msgs) > 2 and msgs[-1]["role"] != "user":  # end on an agent message (role 'user' in the flipped view)
            msgs.pop()
        out.append(msgs)
    out[-1] = out[-1] + [{"role": "assistant", "content": "Yes, please go ahead."},
                         {"role": "user", "content": "Done. A refund of $302.67 will go back to your original payment method "
                                                     "within 5-7 business days. Is there anything else I can help with?"}]
    return out


def call_in_thread(UL, msgs, tag, i, results):
    def run():
        UL.set_context({"protocol": UL.RELAY_V2, "state_id": f"teststate{i}", "unit_id": f"testunit{i}", "arm": "BQ", "replicate": i})
        try:
            results[i] = ("ok",) + UL.relay_call(MODEL, msgs, 512, tag, i)
        except Exception as e:  # noqa: BLE001
            results[i] = ("exc", type(e).__name__, str(e)[:300])
        finally:
            UL.set_context(None)

    t = threading.Thread(target=run)
    t.start()
    return t


def wait_pending(root: Path, n: int, timeout: float = 30) -> list[Path]:
    t0 = time.time()
    while time.time() - t0 < timeout:
        ps = sorted((root / "pending").glob("v2-*.json"))
        if len(ps) >= n:
            return ps
        time.sleep(0.2)
    raise RuntimeError("requests did not appear")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-real", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="simrelay_v2_test_", dir=os.environ.get("TMPDIR") or None))
    os.environ["CLOQ_SIMRELAY_DIR"] = str(tmp / "A")
    os.environ["CLOQ_SIMRELAY_TIMEOUT_S"] = "240"
    from cloq import user_llm as UL
    import simrelay_cli as SC

    report = {"tmp_root": str(tmp), "template_sha256": SC.TEMPLATE_SHA256, "phaseA": None, "phaseB": {}}
    # ---------------------------------------------------------------- phase A: real CLI
    if not a.skip_real:
        rootA = tmp / "A" / "v2"
        reqs = retail_requests(3)
        results: dict = {}
        threads = [call_in_thread(UL, m, f"test-A-{i}", i, results) for i, m in enumerate(reqs)]
        wait_pending(rootA, 3)
        # requests as the responder sees them, before the daemon claims them
        seen = [json.loads(p.read_text()) for p in sorted((rootA / "pending").glob("v2-*.json"))]
        cli = subprocess.Popen([sys.executable, str(ROOT / "scripts/a6000/simrelay_cli.py"), "--root", str(rootA), "--concurrency", "3",
                                "--exit-when-idle", "15", "--log", str(tmp / "cli_A.log"), "--quiet"])
        for t in threads:
            t.join(300)
        cli.wait(120)
        rows = []
        for i, m in enumerate(reqs):
            r = results.get(i)
            row = {"i": i, "result": r[0] if r else None}
            if r and r[0] == "ok":
                text, meta = r[1], r[2]
                done = json.loads(Path(meta["done_path"]).read_text())
                row.update({"content": text, "responder": meta["responder"], "model": meta["model"], "cost_usd": meta["cost_usd"],
                            "duration_s": meta["duration_s"], "integrity_ok": meta["integrity_ok"],
                            "msg_sha256_is_canonical": meta["msg_sha256"] == UL.canon_sha(m),
                            "answer_echo_ok": done["req_id"] == meta["req_id"] and done["msg_sha256"] == meta["msg_sha256"]
                            and done["protocol"] == UL.RELAY_V2,
                            "template_ok": done["template_sha256"] == SC.TEMPLATE_SHA256, "cleaning": done["cleaning"],
                            "models_used": done["models_used"], "meta_sidecar": Path(meta["meta_path"]).exists()})
            else:
                row["error"] = r
            rows.append(row)
        keysets = [sorted(s) for s in seen]
        rend = SC.render(seen[-1]["messages"]) if seen else ""
        report["phaseA"] = {
            "rows": rows,
            "request_keys_only_v2": all(set(s) == set(UL.RELAY_V2_KEYS) for s in seen), "request_keys": keysets[0] if keysets else None,
            "no_identifiers_in_request": all(not any(x in json.dumps(s) for x in ("teststate", "testunit", '"arm"', "replicate")) for s in seen),
            "dollar_preserved_in_render": any("$302.67" in SC.render(s["messages"]) for s in seen),
            "rendered_tail": rend[-400:], "cli_log_tail": (tmp / "cli_A.log").read_text()[-1500:]}
        report["phaseA"]["pass"] = (all(r.get("result") == "ok" and r["integrity_ok"] and r["msg_sha256_is_canonical"] and r["answer_echo_ok"]
                                        and r["template_ok"] and r["meta_sidecar"] and r["content"].strip() for r in rows)
                                    and report["phaseA"]["request_keys_only_v2"] and report["phaseA"]["no_identifiers_in_request"]
                                    and report["phaseA"]["dollar_preserved_in_render"])
    # ---------------------------------------------------------------- phase B: tampering (no Claude call)
    os.environ["CLOQ_SIMRELAY_DIR"] = str(tmp / "B")
    os.environ["CLOQ_SIMRELAY_TIMEOUT_S"] = "60"
    rootB = tmp / "B" / "v2"
    msgs = [{"role": "system", "content": "You are a customer. Your order is #W123."},
            {"role": "user", "content": "Hi! How can I help you today? Your refund would be $302.67."}]
    UL.relay_v2_dirs(rootB)

    def tamper_answer(field):
        res: dict = {}
        t = call_in_thread(UL, msgs, f"test-B-{field}", 0, res)
        p = wait_pending(rootB, 1)[0]
        req = json.loads(p.read_text())
        os.rename(p, rootB / "claimed" / p.name) if (rootB / "claimed").exists() else None
        ans = {"req_id": req["req_id"], "protocol": req["protocol"], "msg_sha256": req["msg_sha256"], "content": "Hello.",
               "responder": "tamper-test"}
        if field == "msg_sha256":
            ans["msg_sha256"] = "0" * 64
        elif field == "req_id":
            ans["req_id"] = "v2-" + "f" * 32
        UL.atomic_write_json(rootB / "done" / p.name, ans)
        t.join(90)
        return res.get(0)

    report["phaseB"]["tampered_msg_sha256"] = tamper_answer("msg_sha256")
    report["phaseB"]["tampered_req_id"] = tamper_answer("req_id")
    report["phaseB"]["untampered_manual_answer"] = (lambda r: (r[0], r[1]) if r and r[0] == "ok" else r)(tamper_answer("none"))
    # (3) request altered after hashing -> the daemon rejects without content
    res3: dict = {}
    t = call_in_thread(UL, msgs, "test-B-reqtamper", 0, res3)
    p = wait_pending(rootB, 1)[0]
    req = json.loads(p.read_text())
    req["messages"][-1]["content"] = req["messages"][-1]["content"].replace("$302.67", "$3.02")
    UL.atomic_write_json(p, req)
    cli = subprocess.Popen([sys.executable, str(ROOT / "scripts/a6000/simrelay_cli.py"), "--root", str(rootB), "--concurrency", "2",
                            "--exit-when-idle", "6", "--log", str(tmp / "cli_B.log"), "--quiet", "--mock"])
    t.join(90)
    # (4) a correct request through the mock daemon is accepted
    res4: dict = {}
    t4 = call_in_thread(UL, msgs, "test-B-mockok", 0, res4)
    t4.join(90)
    cli.wait(60)
    report["phaseB"]["tampered_request_rejected_by_daemon"] = res3.get(0)
    report["phaseB"]["mock_daemon_ok"] = (lambda r: (r[0], r[1], r[2]["responder"], r[2]["integrity_ok"]) if r and r[0] == "ok" else r)(res4.get(0))
    report["phaseB"]["cli_log"] = (tmp / "cli_B.log").read_text()[-1200:]
    pb = report["phaseB"]
    pb["pass"] = (pb["tampered_msg_sha256"][:2] == ("exc", "RelayIntegrityError") and pb["tampered_req_id"][:2] == ("exc", "RelayIntegrityError")
                  and pb["untampered_manual_answer"][0] == "ok" and pb["tampered_request_rejected_by_daemon"][:2] == ("exc", "RelayIntegrityError")
                  and pb["mock_daemon_ok"][0] == "ok")
    report["pass"] = pb["pass"] and (a.skip_real or report["phaseA"]["pass"])
    s = json.dumps(report, indent=1, ensure_ascii=False, default=str)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(s + "\n")
    print(s)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
