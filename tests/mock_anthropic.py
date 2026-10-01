"""Minimal local mock of the Anthropic Messages API (POST /v1/messages) for key-free dry runs of the user_llm override,
plus a trivial OpenAI-shaped /v1/chat/completions agent (always a short talk reply) so a fork branch runs on CPU.

It records every request body (and whether an x-api-key header was present, never its value) to --log as JSONL and
answers with a scripted user reply: a short reply, then ###STOP### on the branch's --stop-after-th user turn (turns are
counted by the mock's own earlier replies in the request, so the old simulator's history does not count). The response
carries a request-id header and Anthropic-shaped usage so the recorder's fields are exercised.

usage: python tests/mock_anthropic.py --port 18765 --log /tmp/mock.jsonl [--stop-after 3]
"""
from __future__ import annotations

import argparse
import json
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18765)
    ap.add_argument("--log", required=True)
    ap.add_argument("--stop-after", type=int, default=3, help="reply ###STOP### on this user turn of a branch (1-based)")
    a = ap.parse_args()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *x):
            pass

        def do_POST(self):
            n = int(self.headers.get("content-length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            if self.path.endswith("/chat/completions"):  # mock agent (OpenAI shape) for the CPU dry run
                k = 1 + sum(1 for m in body.get("messages", []) if m.get("role") == "assistant")
                out = {"id": "chatcmpl-mock", "object": "chat.completion", "created": 0, "model": body.get("model"),
                       "choices": [{"index": 0, "finish_reason": "stop",
                                    "message": {"role": "assistant", "content": f"[mock agent {k}] Is there anything else I can help you with?"}}],
                       "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
                b = json.dumps(out).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
                return
            with open(a.log, "a") as f:
                f.write(json.dumps({"path": self.path, "has_api_key_header": bool(self.headers.get("x-api-key")),
                                    "anthropic_version": self.headers.get("anthropic-version"),
                                    "anthropic_beta": self.headers.get("anthropic-beta"), "body": body}) + "\n")
            # k = this branch's user turn: 1 + the mock's own earlier replies in the (role-flipped) request
            k = 1 + sum(1 for m in body.get("messages", []) if m.get("role") == "assistant" and "[mock user turn" in json.dumps(m))
            text = "###STOP###" if k >= a.stop_after else f"[mock user turn {k}] Yes, please go ahead."
            out = {"id": "msg_mock_" + uuid.uuid4().hex[:16], "type": "message", "role": "assistant", "model": body.get("model"),
                   "content": [{"type": "text", "text": text}], "stop_reason": "end_turn", "stop_sequence": None,
                   "usage": {"input_tokens": 1000 + 10 * len(body.get("messages", [])), "output_tokens": 12,
                             "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}
            b = json.dumps(out).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("request-id", "req_mock_" + uuid.uuid4().hex[:12])
            self.send_header("content-length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
