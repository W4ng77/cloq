"""Mock responder for the simctrl file relay (W91 dry runs only; never used for results).

Loops over scripts/a6000/simrelay_claim.py exactly as a Claude Code responder would: `next --responder <id>`, read the
request JSON, check its fields, write a scripted reply to a file, `answer <req_id> <file>`. The reply is a short user
message, and ###STOP### on the branch's --stop-after-th relay turn (counted from the mock's own earlier replies in the
role-flipped message list, so the old simulator's history does not count). Stops after --idle-exit seconds without work.

usage: CLOQ_SIMRELAY_DIR=<dir> python tests/mock_simrelay_responder.py --responder mock-a [--stop-after 3] [--idle-exit 60]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = [sys.executable, str(ROOT / "scripts/a6000/simrelay_claim.py")]
REQUIRED = ("req_id", "state_id", "arm", "replicate", "system_prompt", "messages", "litellm_messages", "max_tokens", "stop_token_convention")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--responder", required=True)
    ap.add_argument("--stop-after", type=int, default=3)
    ap.add_argument("--idle-exit", type=float, default=60)
    ap.add_argument("--delay", type=float, default=0.5, help="seconds per answer (pretend thinking)")
    a = ap.parse_args()
    last, n = time.time(), 0
    while time.time() - last < a.idle_exit:
        r = subprocess.run(HELPER + ["next", "--responder", a.responder], capture_output=True, text=True)
        path = r.stdout.strip()
        if r.returncode == 3 or path == "NONE":
            time.sleep(1)
            continue
        if r.returncode != 0:
            raise SystemExit(f"next failed: {r.stderr}")
        req = json.loads(Path(path).read_text())
        miss = [k for k in REQUIRED if k not in req]
        if miss:
            raise SystemExit(f"request {path} lacks {miss}")
        assert req["litellm_messages"][0]["role"] == "system" and req["litellm_messages"][0]["content"] == req["system_prompt"]
        assert req["litellm_messages"][1:] == req["messages"]
        k = 1 + sum(1 for m in req["messages"] if m.get("role") == "assistant" and "[mock relay user turn" in (m.get("content") or ""))
        text = "###STOP###" if k >= a.stop_after else f"[mock relay user turn {k}] Yes, please go ahead."
        time.sleep(a.delay)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write(text + "\n")
        r2 = subprocess.run(HELPER + ["answer", req["req_id"], f.name], capture_output=True, text=True)
        if r2.returncode != 0:
            raise SystemExit(f"answer failed: {r2.stderr}")
        n += 1
        last = time.time()
        print(f"{a.responder}: answered {req['req_id']} ({req['arm']} r{req['replicate']}, turn {k})", flush=True)
    print(f"{a.responder}: idle {a.idle_exit:.0f} s, exiting after {n} answers", flush=True)


if __name__ == "__main__":
    main()
