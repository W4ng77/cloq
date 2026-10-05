"""End-to-end selftest of the ko-v1 KQ path without a GPU (KEYORDER_PERTURB_PROTOCOL.md §Build checks).

A local fake OpenAI-compatible server stands in for vLLM: for the agent it renders the received request with the frozen
chat template (cloq.context_policy.render_prompt_ids, i.e. vLLM's json.loads of the arguments string then the HF template)
and returns those prompt ids, then a fixed text reply; for the user simulator it returns ###STOP###. keyorder_arm.run then
forces a_K through the real tau2 orchestrator, and every outcome-blind check must pass: the reversed key order is in the
trajectory and the forced record, the tool messages equal the scanner's, and the next prompt ids that crossed the litellm
transport equal the scanner's prediction. The QQ no-op on the same states must FAIL (the fake continuation differs from
the recorded episode), which shows the no-op check is discriminating. Fake outcomes are never real outcomes.
usage: python scripts/a6000/keyorder_selftest.py --manifest <keyorder manifest json> [--n 3]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import keyorder_scan as KS

SCRATCH = Path("/data/ziyangs/cloq_work/tmp/keyorder_selftest")


class Fake(BaseHTTPRequestHandler):
    OVERFLOW = False  # agent requests get vLLM's context-length 400 (the first continuation overflows)

    def log_message(self, *a):
        pass

    def do_POST(self):
        from cloq.context_policy import render_prompt_ids

        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        agent = body.get("model") == "agent"
        if agent and Fake.OVERFLOW:
            raw = json.dumps({"error": {"message": "This model's maximum context length is 40960 tokens. However, you requested 41000 tokens "
                                                   "in the messages. Please reduce the length of the messages.", "type": "BadRequestError", "param": None, "code": 400}}).encode()
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            return self.wfile.write(raw)
        ids = render_prompt_ids(body["messages"], body.get("tools")) if agent else [0]
        text = "Thank you, is there anything else I can help with?" if agent else "###STOP###"
        out = {"id": f"fake-{time.time_ns()}", "object": "chat.completion", "created": int(time.time()), "model": body.get("model"),
               "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop", "token_ids": [1, 2, 3]}],
               "usage": {"prompt_tokens": len(ids), "completion_tokens": 3, "total_tokens": len(ids) + 3}, "prompt_token_ids": ids}
        raw = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--n", type=int, default=3)
    a = ap.parse_args()
    F = KS.setup()
    import fork_driver as FD

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/v1"
    mp = Path(a.manifest)
    man = json.loads(mp.read_text())
    el = [r for r in man["rows"] if r["eligible"] and r["group"].endswith("/g1")]
    pick = [next(r for r in el if r["domain"] == d) for d in ("airline", "retail")]
    pick += [r for r in el if max(r["n_keys"]) >= 7 and r not in pick][:1]  # a long call (book_reservation-like)
    pick = pick[: max(a.n, 1)]
    spec = {"mode": "keyorder", "manifest": str(mp), "manifest_sha256": hashlib.sha256(mp.read_bytes()).hexdigest(),
            "group": el[0]["group"], "state_ids": [r["state_id"] for r in pick], "noop_frac": 1.0, "shadow_check": False,
            "concurrency": 3, "out": str(SCRATCH)}
    s = __import__("keyorder_arm").run(FD, spec, {"B": base, "Q": base}, base, {}, SCRATCH)
    rows = [json.loads(x) for x in (SCRATCH / "keyorder_rows.jsonl").read_text().splitlines()]
    for r in rows:
        print(r["state_id"], r["domain"], "KQ", {k: v for k, v in r["KQ"].items() if k not in ("duration",)},
              "QQ noop ok", (r.get("QQ_noop") or {}).get("ok"))
    assert s["n_run"] == len(pick) and s["n_kq_ok"] == len(pick), s["kq_check_fail"]
    assert all(r["QQ_noop"]["ok"] is False for r in rows), "fake continuation must not pass the no-op check"
    for r in rows:  # the forced action in the saved trajectory carries the reversed order; values are unchanged
        br = json.loads((SCRATCH / "branches" / f"{r['state_id']}.json").read_text())
        kq, qq = br["KQ"]["suffix"][0]["tool_calls"], br["QQ"]["suffix"][0]["tool_calls"]
        assert [list(t["arguments"]) for t in kq] == [list(reversed(list(t["arguments"]))) for t in qq]
        assert [t["arguments"] for t in kq] == [t["arguments"] for t in qq] and [t["name"] for t in kq] == [t["name"] for t in qq]
    print("keyorder arm selftest ok:", len(pick), "states; server-side prompt ids equal the scanner prediction")
    # review fixes: a context overflow before the first continuation is a valid failure (Y = 0) only where the transformed next
    # prompt is longer than the Q episode's (n_next_k > n_next_q, amendment 2026-10-05c); otherwise it fails acceptance
    Fake.OVERFLOW, KA = True, __import__("keyorder_arm")
    longer = next(r for r in man["rows"] if r["eligible"] and r["n_next_k"] > r["n_next_q"])
    for sid, grp, want in ((spec["state_ids"][0], spec["group"], False), (longer["state_id"], longer["group"], True)):
        od = SCRATCH / f"overflow_{want}"
        so = KA.run(FD, {**spec, "group": grp, "state_ids": [sid], "noop_frac": 0.0, "out": str(od)}, {"B": base, "Q": base}, base, {}, od)
        ro = json.loads((od / "keyorder_rows.jsonl").read_text().splitlines()[0])
        bo = json.loads((od / "branches" / f"{ro['state_id']}.json").read_text())["KQ"]
        print("overflow", ro["state_id"], "KQ", {k: v for k, v in ro["KQ"].items() if k != "duration"}, "Y_KQ", FD._y(ro["domain"], bo),
              "summary pass", so["pass"], so["kq_context_overflow"])
        assert bo["infra_cause"] == "context_overflow" and ro["KQ"]["overflow_at"] == "before_first_continuation" and FD._y(ro["domain"], bo) == 0
        assert ro["KQ"]["ok"] is want and ro["KQ"]["overflow_consistent"] is want and so["pass"] is want, (want, ro["KQ"], so["pass"])
        # the overflow record keeps the audit trail: forced action, its tool results and prefix are verified, not skipped
        assert all(ro["KQ"][k] is True for k in ("record_key_order", "trajectory_key_order", "tool_messages", "prefix_ok")), ro["KQ"]
        assert bo["decisions"][0]["tool_calls"] and bo["partial_suffix"][0]["tool_calls"], "overflow record lost the forced action"
        # regression: a record without the audit fields must fail acceptance, never pass by omission (overflow path ignores st)
        mrow = next(r for r in man["rows"] if r["state_id"] == ro["state_id"])
        assert KA.kq_checks(FD, {}, mrow, bo)["ok"] is want
        assert KA.kq_checks(FD, {}, mrow, {k: v for k, v in bo.items() if k != "partial_suffix"})["ok"] is False
    print("keyorder overflow selftest ok: before-first-continuation overflow passes only with n_next_k > n_next_q (Y = 0), else fails acceptance")
    srv.shutdown()


if __name__ == "__main__":
    sys.exit(main())
