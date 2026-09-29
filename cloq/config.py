"""Frozen protocol constants and project paths for CLOQ v0."""

from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("CLOQ_ROOT", Path(__file__).resolve().parent.parent))
CONFIG_PATH = PROJECT_ROOT / "configs" / "frozen_v0.json"
RUNS_DIR = PROJECT_ROOT / "runs"
CKPT_DIR = PROJECT_ROOT / "ckpts"
TAU2_DIR = PROJECT_ROOT / "third_party" / "tau2-bench"
MANIFEST_DIR = PROJECT_ROOT / "manifests"


def load_frozen() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


FROZEN = load_frozen()

# A6000 multi-model matrix: CLOQ_MODEL_ID / CLOQ_MODEL_REVISION select the agent model (default: the frozen 4B).
# The tokenizer, context policy, quantizers and run records all follow them.
MODEL_ID = os.environ.get("CLOQ_MODEL_ID", FROZEN["model"]["hf_id"])
MODEL_REVISION = os.environ.get("CLOQ_MODEL_REVISION", FROZEN["model"]["revision"] if "CLOQ_MODEL_ID" not in os.environ else "main")
# Extra chat-template kwargs for the agent, identical for local rendering and the server request,
# e.g. '{"enable_thinking": false}' for the Qwen3 hybrid-thinking models.
CHAT_TEMPLATE_KWARGS = json.loads(os.environ.get("CLOQ_CHAT_TEMPLATE_KWARGS") or "{}")
USER_CHAT_TEMPLATE_KWARGS = json.loads(os.environ.get("CLOQ_USER_CHAT_TEMPLATE_KWARGS") or "{}")
# The user simulator / NL judge model actually served on the user port (recorded, never used to load weights).
USER_MODEL_ID = os.environ.get("CLOQ_USER_MODEL_ID", FROZEN["model"]["hf_id"])
# Top-k alternatives requested per generated token for decision-margin logging (0 disables).
TOP_LOGPROBS = int(os.environ.get("CLOQ_TOP_LOGPROBS", "0"))
# CLOQ_MAX_PROMPT_TOKENS overrides the frozen limit for the context-length control runs only.
MAX_PROMPT_TOKENS = int(os.environ.get("CLOQ_MAX_PROMPT_TOKENS", FROZEN["context_policy"]["max_prompt_tokens"]))
AGENT_MAX_TOKENS = int(FROZEN["generation_agent"]["max_tokens"])
USER_MAX_TOKENS = int(FROZEN["generation_user"]["max_tokens"])

AGENT_PORT = int(os.environ.get("CLOQ_AGENT_PORT", FROZEN["serving"]["agent_port"]))
USER_PORT = int(os.environ.get("CLOQ_USER_PORT", FROZEN["serving"]["user_port"]))
AGENT_API_BASE = f"http://127.0.0.1:{AGENT_PORT}/v1"
USER_API_BASE = f"http://127.0.0.1:{USER_PORT}/v1"
AGENT_SERVED_NAME = "agent"
USER_SERVED_NAME = "user"


def agent_llm_args(api_base: str = AGENT_API_BASE) -> dict:
    g = FROZEN["generation_agent"]
    return {
        "temperature": g["temperature"],
        "top_p": g["top_p"],
        "max_tokens": g["max_tokens"],
        "seed": g["seed"],
        "presence_penalty": g["presence_penalty"],
        "frequency_penalty": g["frequency_penalty"],
        "extra_body": {
            "top_k": g["top_k"],
            "repetition_penalty": g["repetition_penalty"],
            "return_token_ids": True,
            **({"chat_template_kwargs": CHAT_TEMPLATE_KWARGS} if CHAT_TEMPLATE_KWARGS else {}),
        },
        **({"logprobs": True, "top_logprobs": TOP_LOGPROBS} if TOP_LOGPROBS else {}),
        "api_base": api_base,
        "api_key": "EMPTY",
        "timeout": 600,
    }


def user_llm_args(api_base: str = USER_API_BASE) -> dict:
    g = FROZEN["generation_user"]
    return {
        "temperature": g["temperature"],
        "top_p": g["top_p"],
        "max_tokens": g["max_tokens"],
        "seed": g["seed"],
        "extra_body": {"top_k": g["top_k"], **({"chat_template_kwargs": USER_CHAT_TEMPLATE_KWARGS} if USER_CHAT_TEMPLATE_KWARGS else {})},
        "api_base": api_base,
        "api_key": "EMPTY",
        "timeout": 600,
    }


def judge_llm_args(api_base: str = USER_API_BASE) -> dict:
    """NL-assertion judge: the frozen local BF16 server, greedy."""
    return {
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 2048,
        "seed": 0,
        "extra_body": {"top_k": -1, **({"chat_template_kwargs": USER_CHAT_TEMPLATE_KWARGS} if USER_CHAT_TEMPLATE_KWARGS else {})},
        "api_base": api_base,
        "api_key": "EMPTY",
        "timeout": 600,
    }
