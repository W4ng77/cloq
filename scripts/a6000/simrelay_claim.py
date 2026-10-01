"""Claim / answer helper for the simctrl user-simulator file relay (W91; protocol simrelay-v1, cloq/user_llm.py).

A fork branch running with user_llm provider "relay" writes one request per user turn to
  <relay>/pending/<req_id>.json            (relay = $CLOQ_SIMRELAY_DIR, default /data/ziyangs/cloq_work/simrelay)
and polls
  <relay>/done/<req_id>.json               {"content": "<the user's next message>", ...}
Responders (Claude Code Sonnet subagents; docs/insights/SIMRELAY_RESPONDER.md) use only this helper:

  python scripts/a6000/simrelay_claim.py next --responder <id>
      atomically moves ONE pending request (oldest first) to claimed/<id>/<req_id>.json and prints that path
      (prints NONE and exits 3 when nothing is pending).
  python scripts/a6000/simrelay_claim.py answer <req_id> <reply_file>
      reads the reply text from <reply_file> (only the user's message; surrounding whitespace is stripped) and writes
      done/<req_id>.json atomically (tmp + rename in done/). Refuses an empty reply, an unclaimed or expired request,
      and a second answer.
  python scripts/a6000/simrelay_claim.py status
      counts per directory (pending / claimed per responder / done / expired).

Every file write is tmp-in-the-same-directory + rename, so readers on other NFS clients never see a partial file;
claiming is a rename out of pending/, so exactly one responder wins a request (the loser gets ENOENT and tries the next).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from cloq.user_llm import atomic_write_json, relay_dirs  # noqa: E402


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def cmd_next(responder: str) -> int:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", responder):
        raise SystemExit("responder id: 1-64 chars of [A-Za-z0-9_.-]")
    d = relay_dirs()
    mine = d["claimed"] / responder
    mine.mkdir(parents=True, exist_ok=True)
    cands = []
    for p in d["pending"].glob("*.json"):
        if p.name.startswith("."):
            continue
        try:
            cands.append((p.stat().st_mtime, p.name, p))
        except FileNotFoundError:  # claimed by someone else meanwhile
            pass
    for _, _, p in sorted(cands):
        dst = mine / p.name
        try:
            os.rename(p, dst)
        except FileNotFoundError:
            continue
        if not dst.exists():  # defensive: NFS rename retried after a lost reply
            continue
        (mine / (p.stem + ".claim")).write_text(json.dumps({"responder": responder, "claimed_utc": _now(), "host": socket.gethostname()}))
        print(dst)
        return 0
    print("NONE")
    return 3


def cmd_answer(req_id: str, reply_file: str) -> int:
    d = relay_dirs()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", req_id):
        raise SystemExit(f"bad req_id {req_id!r}")
    done = d["done"] / f"{req_id}.json"
    if done.exists():
        raise SystemExit(f"{req_id} already answered ({done})")
    if (d["expired"] / f"{req_id}.json").exists():
        raise SystemExit(f"{req_id} expired (the branch timed out); do not answer")
    claimed = list(d["claimed"].glob(f"*/{req_id}.json"))
    if len(claimed) != 1:
        raise SystemExit(f"{req_id}: not claimed (found {len(claimed)}); run `next` first")
    responder = claimed[0].parent.name
    text = Path(reply_file).read_text().strip()
    if not text:
        raise SystemExit("empty reply: write the user's next message (or a stop token) to the file")
    req = json.loads(claimed[0].read_text())
    cl = claimed[0].with_suffix(".claim")
    claim = json.loads(cl.read_text()) if cl.exists() else {}
    atomic_write_json(done, {"req_id": req_id, "content": text, "responder": responder, "claimed_utc": claim.get("claimed_utc"),
                             "answered_utc": _now(), "request_sha256_messages": req.get("litellm_messages_sha256"),
                             "n_chars": len(text)})
    print(done)
    return 0


def cmd_status() -> int:
    d = relay_dirs()
    n = lambda p: sum(1 for x in p.glob("*.json") if not x.name.startswith("."))  # noqa: E731
    out = {"pending": n(d["pending"]), "done": n(d["done"]), "expired": sum(1 for x in d["expired"].glob("*.json") if not x.name.endswith(".reason.json")),
           "claimed": {p.name: n(p) for p in sorted(d["claimed"].iterdir()) if p.is_dir()}}
    out["claimed_unanswered"] = sum(1 for p in d["claimed"].glob("*/*.json") if not (d["done"] / p.name).exists())
    print(json.dumps(out))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a1 = sp.add_parser("next")
    a1.add_argument("--responder", required=True)
    a2 = sp.add_parser("answer")
    a2.add_argument("req_id")
    a2.add_argument("reply_file")
    sp.add_parser("status")
    a = ap.parse_args()
    if a.cmd == "next":
        return cmd_next(a.responder)
    if a.cmd == "answer":
        return cmd_answer(a.req_id, a.reply_file)
    return cmd_status()


if __name__ == "__main__":
    sys.exit(main())
