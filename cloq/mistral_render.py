"""Local prompt rendering for models served with vLLM `--tokenizer-mode mistral` (m24, W99p).

Mistral-Small-3.2 ships no HF tokenizer or chat template, only the official `tekken.json`; vLLM 0.29 then renders
chat requests with mistral_common (vllm.renderers.mistral). The harness renders every decision locally too (context
policy token counts, logged prompt ids, fork prompt checks), so the local path must follow the server's exactly. This
module does the same steps as the server's chat preprocessing for a Mistral tokenizer
(vllm.renderers.online_renderer + vllm.tokenizers.mistral): validate the body as a ChatCompletionRequest,
`maybe_serialize_tool_calls` (tool_calls None -> []), `truncate_tool_call_ids` (ids > 9 chars -> last 9), tools as
`tool.model_dump()`, then `MistralTokenizer.apply_chat_template` on the raw (not template_view) messages.
The equality with the server's ids is checked per decision (`prompt_ids_match_local`) in every run.

Selected by CLOQ_TOKENIZER_MODE=mistral (scripts/a6000/worker.py::model_env sets it from models.json
"tokenizer_mode"); the tokenizer directory is CLOQ_MODEL_PATH. Unused by every Qwen / Llama model.
"""

from __future__ import annotations

import copy
from typing import Any, Optional


class MistralChatRender:
    """apply_chat_template-compatible wrapper (the subset cloq.context_policy uses)."""

    is_mistral = True

    def __init__(self, path: str):
        from vllm.tokenizers.mistral import MistralTokenizer
        self.path = path
        self.tok = MistralTokenizer.from_pretrained(path)

    @staticmethod
    def server_view(messages: list[dict], tools: Optional[list[dict]]) -> tuple[list[dict], Optional[list[dict]]]:
        from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionRequest
        from vllm.tokenizers import mistral as _mt
        body: dict[str, Any] = {"model": "agent", "messages": copy.deepcopy(messages)}
        if tools:
            body["tools"] = copy.deepcopy(tools)
        req = ChatCompletionRequest(**body)
        _mt.maybe_serialize_tool_calls(req)
        _mt.truncate_tool_call_ids(req)
        tool_dicts = [t.model_dump() for t in req.tools] if req.tools else None
        return req.messages, tool_dicts

    def apply_chat_template(self, messages: list[dict], tools: Optional[list[dict]] = None, add_generation_prompt: bool = True,
                            tokenize: bool = True, **_ignored):
        msgs, tool_dicts = self.server_view(messages, tools)
        out = self.tok.apply_chat_template(msgs, tools=tool_dicts, add_generation_prompt=add_generation_prompt, tokenize=tokenize)
        if tokenize and (isinstance(out, dict) or hasattr(out, "input_ids")):
            out = out["input_ids"]
        return out

    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
        return self.tok.encode(text, add_special_tokens=add_special_tokens)

    def decode(self, ids, skip_special_tokens: bool = False) -> str:
        return self.tok.decode(ids, skip_special_tokens=skip_special_tokens)

    def render_turn(self, messages: list[dict], tools: Optional[list[dict]] = None) -> tuple[str, list[int]]:
        """W100o (score_driver, m24): a conversation that ENDS with a completed assistant turn, rendered by mistral_common
        in finetuning validation mode (serving mode refuses a final assistant message): the assistant tokens are followed
        by EOS, as the model emits them. Same server_view as apply_chat_template; returns (text, ids)."""
        if getattr(self, "_ft", None) is None:
            from transformers.tokenization_mistral_common import MistralCommonBackend
            self._ft = MistralCommonBackend.from_pretrained(self.path, mode="finetuning")
        msgs, tool_dicts = self.server_view(messages, tools)
        ids = self._ft.apply_chat_template(msgs, tools=tool_dicts, tokenize=True)
        if isinstance(ids, dict) or hasattr(ids, "input_ids"):
            ids = ids["input_ids"]
        text = self._ft.apply_chat_template(msgs, tools=tool_dicts, tokenize=False)
        return text, list(ids)
