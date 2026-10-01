"""simrelay-v2 responder daemon (W97): one clean, headless Claude Code call per user turn.

Runs on the LOGIN node (the compute nodes have no Claude Code login). It claims v2 requests written by fork branches
(cloq/user_llm.py, protocol "simrelay-v2", root $CLOQ_SIMRELAY_DIR/v2 = /data/ziyangs/cloq_work/simrelay/v2 by default)
and answers each with ONE fresh call

    claude -p --model claude-sonnet-5-5 --tools "" --strict-mcp-config --setting-sources "" --max-turns 1
           --no-session-persistence --system-prompt <request system_prompt> --output-format json

with cwd = an empty directory and the rendered conversation on stdin. No context is shared across requests (no session,
no tools, no MCP, no settings, no CLAUDE.md in the empty cwd); CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 removes the
side model call. Residual, identical for every request: Claude Code adds its own short environment block (cwd, platform,
date, model name) and an account-context reminder to the user message; neither carries any experiment identifier.

Rendering (frozen; its sha256 is TEMPLATE_SHA256 and is written into every answer): `-p` takes one user message, so the
role-flipped history (role "user" = the agent speaking to the customer, role "assistant" = the customer's own earlier
messages) is rendered deterministically as
    <HEADER>\n\n Agent: ...\n\n Customer (you): ...\n\n ... Customer (you):
The reply is cleaned only of an accidental role prefix, surrounding quotes or a code fence around the whole message;
nothing else ($ amounts, stop tokens, punctuation) is altered (no shell is involved: argv + stdin).

Integrity: the daemon recomputes msg_sha256 from system_prompt + messages before answering; a request that fails gets an
answer WITHOUT content (the branch raises RelayIntegrityError at once instead of waiting for a timeout). The answer
echoes req_id, protocol and msg_sha256; the branch verifies all three.

Claiming: rename pending/<req>.json -> claimed/cli-<n>/<req>.json (atomic; exactly one claimer wins). A slot claims only
when it is free, oldest request first. CLI failures are retried up to 3 times with backoff; then the request is moved
back to pending/ (cool-down 60 s) and retried later; garbage is never answered.

usage: python scripts/a6000/simrelay_cli.py [--concurrency 12] [--root DIR] [--log FILE] [--exit-when-idle S] [--mock]
       python scripts/a6000/simrelay_cli.py --render <request.json>      (print the rendered user message; no call)
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import queue
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from cloq.user_llm import RELAY_V2, RELAY_V2_KEYS, atomic_write_json, canon_sha, relay_dir, v2_messages  # noqa: E402

MODEL = "claude-sonnet-5-5"
EMPTY_CWD = "/data/ziyangs/cloq_work/simrelay/cli_empty"
LOG_DEFAULT = "/data/ziyangs/cloq_work/logs/simrelay_cli.log"
BIN_GLOB = "~/.vscode-server/extensions/anthropic.claude-code-*/resources/native-binary/claude"
MAX_ATTEMPTS = 3
BACKOFF_S = (5, 15)
COOLDOWN_S = 60
CALL_TIMEOUT_S = 300

# ---------------------------------------------------------------------------- frozen template (simrelay-cli-template-v1)
TEMPLATE = {
    "version": "simrelay-cli-template-v1",
    "header": ("You are the customer described in the system prompt. Below is the conversation so far. "
               "Write ONLY the customer's next message."),
    "agent_label": "Agent:",
    "customer_label": "Customer (you):",
    "empty_note": "(The conversation has not started yet.)",
    "joiner": "\n\n",
    "rule": ("header, then one block per message in order: role 'user' -> '<agent_label> <content>', role 'assistant' -> "
             "'<customer_label> <content>' (content stripped of surrounding whitespace), then a final '<customer_label>'; "
             "blocks joined by joiner; empty history -> empty_note in place of the blocks"),
}
TEMPLATE_SHA256 = hashlib.sha256(json.dumps(TEMPLATE, sort_keys=True).encode()).hexdigest()


def render(messages: list) -> str:
    blocks = [TEMPLATE["header"]]
    if not messages:
        blocks.append(TEMPLATE["empty_note"])
    for m in messages:
        role = m.get("role")
        if role == "user":
            lab = TEMPLATE["agent_label"]
        elif role == "assistant":
            lab = TEMPLATE["customer_label"]
        else:
            raise ValueError(f"unexpected role {role!r} in a v2 request")
        blocks.append(f"{lab} {(m.get('content') or '').strip()}")
    blocks.append(TEMPLATE["customer_label"])
    return TEMPLATE["joiner"].join(blocks)


_PREFIX = re.compile(r"^\s*(?:\*\*)?(?:Customer \(you\)|Customer|User)(?:\*\*)?\s*:\s*(?:\*\*)?\s*", re.I)
_FENCE = re.compile(r"^```[A-Za-z0-9_-]*[ \t]*\n(.*?)\n?```$", re.S)
_QUOTES = (('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’"))


def clean(text: str) -> tuple[str, list[str]]:
    """Strip an accidental code fence, role prefix or surrounding quotes around the WHOLE reply. Nothing else changes."""
    ops, t = [], (text or "").strip()
    m = _FENCE.match(t)
    if m:
        t, _ = m.group(1).strip(), ops.append("code_fence")
    m = _PREFIX.match(t)
    if m and len(t) > m.end():
        t, _ = t[m.end():].strip(), ops.append("role_prefix")
    for a, b in _QUOTES:
        if len(t) >= 2 and t.startswith(a) and t.endswith(b) and a not in t[1:-1] and b not in t[1:-1]:
            t, _ = t[1:-1].strip(), ops.append("surrounding_quotes")
            break
    return t, ops


def claude_bin() -> str:
    cands = glob.glob(os.path.expanduser(BIN_GLOB))
    if not cands:
        raise SystemExit(f"no Claude Code binary matches {BIN_GLOB}")

    def ver(p):
        m = re.search(r"anthropic\.claude-code-([0-9.]+)", p)
        return tuple(int(x) for x in m.group(1).split(".")) if m else ()

    return max(cands, key=ver)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Daemon:
    def __init__(self, a):
        self.a = a
        self.root = Path(a.root) if a.root else relay_dir() / "v2"
        self.d = {k: self.root / k for k in ("pending", "claimed", "done", "expired")}
        for p in self.d.values():
            p.mkdir(parents=True, exist_ok=True)
        self.bin = None if a.mock else claude_bin()
        self.empty = Path(a.empty_cwd)
        self.empty.mkdir(parents=True, exist_ok=True)
        if any(self.empty.iterdir()):
            raise SystemExit(f"{self.empty} is not empty; the CLI must run in an empty directory")
        self.env = {**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
        self.env.pop("ANTHROPIC_API_KEY", None)  # login (OAuth) only; never an inherited key
        self.slots: queue.Queue = queue.Queue()
        for i in range(a.concurrency):
            self.slots.put(f"{'mockcli' if a.mock else 'cli'}-{a.slot_offset + i}")
        self.cool: dict[str, float] = {}
        self.fails: dict[str, int] = {}
        self.lock = threading.Lock()
        self.logf = open(a.log, "a")
        self.n_ok = self.n_fail = self.n_bad = 0
        self.cost = 0.0
        self.stop = False

    def log(self, msg: str) -> None:
        line = f"[{time.strftime('%F %T')}] {msg}"
        with self.lock:
            self.logf.write(line + "\n")
            self.logf.flush()
            if not self.a.quiet:
                print(line, flush=True)

    # ------------------------------------------------------------------ claiming
    def recover_own_claims(self) -> None:
        """Requests left in this daemon's own claimed/<slot>/ by a crash go back to pending/ (unless answered/expired)."""
        names = {f"{'mockcli' if self.a.mock else 'cli'}-{self.a.slot_offset + i}" for i in range(self.a.concurrency)}
        for sd in self.d["claimed"].iterdir():
            if not sd.is_dir() or sd.name not in names:
                continue
            for p in sd.glob("v2-*.json"):
                if (self.d["done"] / p.name).exists() or (self.d["expired"] / p.name).exists():
                    continue
                try:
                    os.rename(p, self.d["pending"] / p.name)
                    self.log(f"recovered stale claim {p.name} from {sd.name}")
                except OSError:
                    pass

    def candidates(self) -> list[Path]:
        now = time.time()
        out = []
        for p in self.d["pending"].glob("v2-*.json"):
            if self.cool.get(p.stem, 0) > now:
                continue
            try:
                out.append((p.stat().st_mtime, p.name, p))
            except FileNotFoundError:
                pass
        return [p for _, _, p in sorted(out)]

    def claim(self, p: Path, slot: str) -> Path | None:
        mine = self.d["claimed"] / slot
        mine.mkdir(parents=True, exist_ok=True)
        dst = mine / p.name
        try:
            os.rename(p, dst)
        except FileNotFoundError:
            return None
        return dst if dst.exists() else None

    # ------------------------------------------------------------------ one request
    def call(self, sp: str, user_msg: str) -> dict:
        if self.a.mock:  # dry runs only: deterministic fake customer (never used for results)
            k = 1 + user_msg.count("[mock cli user turn")
            res = "###STOP###" if k >= self.a.mock_stop_after else f"[mock cli user turn {k}] Yes, please go ahead with that."
            time.sleep(self.a.mock_delay)
            return {"type": "result", "subtype": "success", "is_error": False, "result": res, "total_cost_usd": 0.0,
                    "modelUsage": {"mock": {}}, "duration_ms": int(self.a.mock_delay * 1000), "session_id": None}
        cmd = [self.bin, "-p", "--model", self.a.model, "--tools", "", "--strict-mcp-config", "--setting-sources", "",
               "--max-turns", "1", "--no-session-persistence", "--output-format", "json"]
        if len(sp.encode()) < 100_000:
            cmd += ["--system-prompt", sp]
        else:  # argv single-string limit (128 KiB): same content via a file
            spf = Path(self.a.root or relay_dir() / "v2") / ".sp" / f"{threading.get_ident()}.txt"
            spf.parent.mkdir(parents=True, exist_ok=True)
            spf.write_text(sp)
            cmd += ["--system-prompt-file", str(spf)]
        r = subprocess.run(cmd, input=user_msg, capture_output=True, text=True, cwd=str(self.empty), env=self.env,
                           timeout=CALL_TIMEOUT_S)
        if r.returncode != 0:
            raise RuntimeError(f"claude rc={r.returncode}: {(r.stderr or r.stdout)[-300:]}")
        out = json.loads(r.stdout)
        if out.get("is_error") or out.get("subtype") != "success" or not isinstance(out.get("result"), str):
            raise RuntimeError(f"claude result error: subtype={out.get('subtype')} is_error={out.get('is_error')} "
                               f"api_error_status={out.get('api_error_status')} result={str(out.get('result'))[:200]}")
        models = list((out.get("modelUsage") or {}).keys())
        if self.a.model not in models:
            raise RuntimeError(f"claude answered with {models}, not {self.a.model}")
        return out

    def handle(self, path: Path, slot: str) -> None:
        name = path.name
        req_id = path.stem
        claimed_utc = _now()
        try:
            req = json.loads(path.read_text())
            problems = []
            if req.get("protocol") != RELAY_V2:
                problems.append(f"protocol {req.get('protocol')!r}")
            if req.get("req_id") != req_id:
                problems.append("req_id differs from file name")
            extra = sorted(set(req) - set(RELAY_V2_KEYS))
            if extra:
                problems.append(f"unexpected request fields {extra} (v2 requests carry no bookkeeping)")
            if not problems and canon_sha(v2_messages(req["system_prompt"], req["messages"])) != req.get("msg_sha256"):
                problems.append("msg_sha256 does not match system_prompt + messages")
            if problems:  # answer without content: the branch fails at once as infra (never a garbage user turn)
                atomic_write_json(self.d["done"] / name, {"req_id": req.get("req_id"), "protocol": req.get("protocol"),
                                                         "error": "request integrity: " + "; ".join(problems), "responder": slot,
                                                         "answered_utc": _now()})
                self.n_bad += 1
                self.log(f"{slot} REJECTED {req_id}: {problems}")
                return
            user_msg = render(req["messages"])
            out, err, t0, attempts = None, None, time.time(), 0
            for attempt in range(MAX_ATTEMPTS):
                attempts = attempt + 1
                try:
                    out = self.call(req["system_prompt"], user_msg)
                    text, ops = clean(out["result"])
                    if not text:
                        raise RuntimeError("empty reply after cleaning")
                    break
                except Exception as e:  # noqa: BLE001
                    out, err = None, repr(e)[:400]
                    self.log(f"{slot} attempt {attempts} failed for {req_id}: {err}")
                    if attempt < MAX_ATTEMPTS - 1:
                        time.sleep(BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)])
            dur = time.time() - t0
            if out is None:
                with self.lock:
                    self.fails[req_id] = self.fails.get(req_id, 0) + 1
                    self.cool[req_id] = time.time() + COOLDOWN_S * self.fails[req_id]
                self.n_fail += 1
                try:
                    os.rename(path, self.d["pending"] / name)  # back for a later retry; never answer garbage
                    self.log(f"{slot} gave up on {req_id} after {attempts} attempts ({err}); returned to pending, cool-down "
                             f"{COOLDOWN_S * self.fails[req_id]} s")
                except OSError as e:
                    self.log(f"{slot} could not return {req_id} to pending: {e!r}")
                return
            if (self.d["done"] / name).exists() or (self.d["expired"] / name).exists():
                self.log(f"{slot} {req_id} already answered or expired; dropping reply")
                return
            cost = out.get("total_cost_usd")
            ans = {"req_id": req_id, "protocol": RELAY_V2, "msg_sha256": req["msg_sha256"], "content": text,
                   "responder": slot, "model": self.a.model if not self.a.mock else "mock",
                   "models_used": list((out.get("modelUsage") or {}).keys()), "cost_usd": cost, "duration_s": round(dur, 3),
                   "duration_api_ms": out.get("duration_api_ms"), "n_attempts": attempts, "template_sha256": TEMPLATE_SHA256,
                   "template_version": TEMPLATE["version"], "cleaning": ops, "raw_result": out.get("result"),
                   "stop_reason": out.get("stop_reason"), "usage": out.get("usage"), "model_usage": out.get("modelUsage"),
                   "cli_binary": self.bin, "host": socket.gethostname(), "claimed_utc": claimed_utc, "answered_utc": _now()}
            atomic_write_json(self.d["done"] / name, ans)
            with self.lock:
                self.n_ok += 1
                self.cost += cost or 0.0
            self.log(f"{slot} answered {req_id} in {dur:.1f} s (attempts {attempts}, cost ${cost}, clean {ops}, {len(text)} chars)")
        except Exception as e:  # noqa: BLE001
            self.log(f"{slot} internal error on {req_id}: {e!r}; returning to pending")
            try:
                os.rename(path, self.d["pending"] / name)
            except OSError:
                pass
        finally:
            self.slots.put(slot)

    # ------------------------------------------------------------------ loop
    def run(self) -> int:
        self.log(f"start: root {self.root}, concurrency {self.a.concurrency}, model {self.a.model}, bin {self.bin}, "
                 f"cwd {self.empty}, template {TEMPLATE_SHA256[:16]}, mock {self.a.mock}")
        self.recover_own_claims()
        threads: list[threading.Thread] = []
        last_work = time.time()
        while not self.stop:
            busy = self.a.concurrency - self.slots.qsize()
            cands = self.candidates() if self.slots.qsize() else []
            for p in cands:
                try:
                    slot = self.slots.get_nowait()
                except queue.Empty:
                    break
                dst = self.claim(p, slot)
                if dst is None:
                    self.slots.put(slot)
                    continue
                last_work = time.time()
                t = threading.Thread(target=self.handle, args=(dst, slot), daemon=True)
                t.start()
                threads.append(t)
            threads = [t for t in threads if t.is_alive()]
            if threads or busy:
                last_work = time.time()
            if self.a.exit_when_idle and time.time() - last_work > self.a.exit_when_idle:
                break
            time.sleep(self.a.poll)
        for t in threads:
            t.join()
        self.log(f"stop: answered {self.n_ok}, gave up {self.n_fail}, rejected {self.n_bad}, cost ${self.cost:.4f}")
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--concurrency", type=int, default=12)
    ap.add_argument("--root", default=None, help="v2 relay root (default $CLOQ_SIMRELAY_DIR/v2)")
    ap.add_argument("--log", default=LOG_DEFAULT)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--empty-cwd", default=EMPTY_CWD)
    ap.add_argument("--slot-offset", type=int, default=0, help="responder ids cli-<offset>..; use distinct offsets per daemon")
    ap.add_argument("--poll", type=float, default=0.3)
    ap.add_argument("--exit-when-idle", type=float, default=0, help="exit after this many idle seconds (0 = run forever)")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--mock", action="store_true", help="dry runs only: scripted replies, no Claude call")
    ap.add_argument("--mock-stop-after", type=int, default=3)
    ap.add_argument("--mock-delay", type=float, default=0.2)
    ap.add_argument("--render", default=None, help="print the rendered user message of a request file and exit")
    a = ap.parse_args()
    if a.render:
        req = json.loads(Path(a.render).read_text())
        print(render(req["messages"]))
        print(f"\n[template {TEMPLATE['version']} sha256 {TEMPLATE_SHA256}]", file=sys.stderr)
        return 0
    Path(a.log).parent.mkdir(parents=True, exist_ok=True)
    dm = Daemon(a)

    def _stop(*_):
        dm.stop = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    return dm.run()


if __name__ == "__main__":
    sys.exit(main())
