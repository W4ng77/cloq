"""template_view (cloq/context_policy.py) must leave the Qwen prompt path byte-identical and fix Llama-3.1.

Replays logged decision records: re-renders each record's `messages` with the raw list (pre-fix path) and with
template_view (post-fix path) and checks (a) the rendered text is identical for Qwen, (b) the ids equal the ids
the vLLM server logged, (c) Llama-3.1 raw rendering of a text turn with `tool_calls: None` raises the smoke-run
error while template_view renders it and matches the server ids.

usage: python tests/test_template_view.py            (runs every case in a subprocess per model)
       pytest tests/test_template_view.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = json.load(open(ROOT / "scripts/a6000/models.json"))
# (model code, run dir, max decisions per domain)
CASES = [("q4", "a6k2_det_q4_a", 400), ("q8", "a6k2_q8_bf16", 200), ("q30a3", "a6k2_det_q30a3_a", 200),
         ("l8", "a6k2_smoke_l8_v2", 400)]


def _check(code: str, run: str, limit: int) -> dict:
    from tau2.registry import registry

    from cloq.context_policy import get_tokenizer, render_prompt, template_view
    from cloq.config import CHAT_TEMPLATE_KWARGS

    tok = get_tokenizer()
    stats = {"n": 0, "text_same": 0, "server_match": 0, "server_n": 0, "raw_error": 0, "tool_call_turns": 0}
    for dom_dir in sorted((ROOT / "runs" / run).iterdir()):
        dec = dom_dir / "decisions.jsonl"
        if not dec.exists():
            continue
        tools = [t.openai_schema for t in registry.get_env_constructor(dom_dir.name)().get_tools()]
        for i, line in enumerate(open(dec)):
            if i >= limit:
                break
            d = json.loads(line)
            msgs = d["messages"]
            view = template_view(msgs)
            assert msgs == json.loads(line)["messages"], "template_view mutated its input"
            new = render_prompt(msgs, tools)
            stats["tool_call_turns"] += sum(1 for m in msgs if m.get("tool_calls"))
            try:
                old = tok.apply_chat_template(msgs, tools=tools, add_generation_prompt=True, tokenize=False,
                                              **CHAT_TEMPLATE_KWARGS)
                stats["text_same"] += old == new
            except TypeError as e:  # Llama-3.1: `tool_calls|length` on None
                assert "NoneType" in str(e), e
                stats["raw_error"] += 1
            if d.get("prompt_ids_from_server"):
                ids = tok.apply_chat_template(view, tools=tools, add_generation_prompt=True, tokenize=True,
                                              **CHAT_TEMPLATE_KWARGS)
                ids = list(ids["input_ids"] if isinstance(ids, dict) or hasattr(ids, "input_ids") else ids)
                stats["server_n"] += 1
                stats["server_match"] += ids == d["prompt_token_ids"]
            stats["n"] += 1
    return stats


def _run_case(code: str, run: str, limit: int) -> dict:
    m = MODELS[code]
    env = dict(os.environ, CLOQ_MODEL_ID=m["hf_id"], CLOQ_MODEL_REVISION=m["revision"],
               CLOQ_CHAT_TEMPLATE_KWARGS=json.dumps(m.get("chat_template_kwargs") or {}), HF_HUB_OFFLINE="1")
    out = subprocess.run([sys.executable, __file__, "--case", code, run, str(limit)], env=env, cwd=ROOT,
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_qwen_byte_identical():
    for code, run, limit in CASES:
        if not code.startswith("q") or not (ROOT / "runs" / run).exists():
            continue
        s = _run_case(code, run, limit)
        assert s["n"] > 0 and s["tool_call_turns"] > 0, (code, s)
        assert s["text_same"] == s["n"] and s["raw_error"] == 0, (code, s)
        assert s["server_match"] == s["server_n"], (code, s)


_SYNTH = [
    {"role": "system", "content": "policy"},
    {"role": "assistant", "content": "Hi! How can I help you today?", "tool_calls": None},
    {"role": "user", "content": "I want to return an item."},
    {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "name": "find_user_id_by_email", "type": "function",
                                                           "function": {"name": "find_user_id_by_email", "arguments": json.dumps({"email": "a@b.c"})}}]},
    {"role": "tool", "content": "user_1", "tool_call_id": "c1"},
    {"role": "assistant", "content": "Which order?", "tool_calls": None},
    {"role": "user", "content": "#W1"},
]


def _synth_llama() -> dict:
    from cloq.context_policy import get_tokenizer, render_prompt
    from cloq.config import CHAT_TEMPLATE_KWARGS

    tools = [{"type": "function", "function": {"name": "find_user_id_by_email", "description": "d",
                                               "parameters": {"type": "object", "properties": {"email": {"type": "string"}}}}}]
    try:
        get_tokenizer().apply_chat_template(_SYNTH, tools=tools, add_generation_prompt=True, tokenize=False,
                                            **CHAT_TEMPLATE_KWARGS)
        raw_error = None
    except TypeError as e:
        raw_error = str(e)
    text = render_prompt(_SYNTH, tools)
    return {"raw_error": raw_error, "args_as_object": '"parameters": {"email": "a@b.c"}' in text,
            "greeting_is_assistant": "<|start_header_id|>assistant<|end_header_id|>\n\nHi! How can I help" in text}


def test_llama_fixed():
    m = MODELS["l8"]
    env = dict(os.environ, CLOQ_MODEL_ID=m["hf_id"], CLOQ_MODEL_REVISION=m["revision"],
               CLOQ_CHAT_TEMPLATE_KWARGS=json.dumps(m.get("chat_template_kwargs") or {}), HF_HUB_OFFLINE="1")
    out = subprocess.run([sys.executable, __file__, "--synth"], env=env, cwd=ROOT, capture_output=True, text=True,
                         check=True)
    s = json.loads(out.stdout.strip().splitlines()[-1])
    assert s["raw_error"] and "NoneType" in s["raw_error"], s  # the smoke-run crash, on the pre-fix path
    assert s["args_as_object"] and s["greeting_is_assistant"], s
    code, run, limit = CASES[-1]
    if (ROOT / "runs" / run).exists():  # replay a run made with the fix: local ids must equal the server's
        r = _run_case(code, run, limit)
        assert r["server_match"] == r["server_n"] > 0, r


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--synth":
        sys.path.insert(0, str(ROOT))
        print(json.dumps(_synth_llama()))
    elif len(sys.argv) > 1 and sys.argv[1] == "--case":
        sys.path.insert(0, str(ROOT))
        print(json.dumps(_check(sys.argv[2], sys.argv[3], int(sys.argv[4]))))
    else:
        for code, run, limit in CASES:
            if (ROOT / "runs" / run).exists():
                print(code, run, _run_case(code, run, limit), flush=True)
        test_llama_fixed()
        print("l8 synthetic: ok")
