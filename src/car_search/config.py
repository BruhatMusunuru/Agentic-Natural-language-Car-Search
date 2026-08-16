"""Runtime configuration, read from environment variables.

Only ANTHROPIC_API_KEY is required (read implicitly by the Anthropic SDK).
Everything else has a sensible default (see .env / README).
"""

from __future__ import annotations

import os

DEFAULT_MODEL_ID = "claude-sonnet-5"
DEFAULT_MAX_TOKENS = 1536
TOP_K = 5


def get_model_id() -> str:
    return os.environ.get("ANTHROPIC_MODEL_ID", DEFAULT_MODEL_ID)


def get_max_tokens() -> int:
    return int(os.environ.get("ANTHROPIC_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
