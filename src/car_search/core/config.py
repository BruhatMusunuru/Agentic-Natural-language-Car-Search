"""Runtime configuration, read from environment variables.

Only ANTHROPIC_API_KEY is required. It's read implicitly by the Anthropic
SDK from the environment -- this module makes sure a checked-in `.env` at
the repo root is loaded into the environment first (so `uv run car-search`
etc. work without the caller having to manually `export`/`source` it), and
fails fast with a clear message if the key is still missing when actually
needed, rather than surfacing the Anthropic SDK's low-level auth error deep
in a request stack trace.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# Loads .env (if present) into the environment without overriding any
# variable the caller already exported. Safe to call from a directory other
# than the repo root; python-dotenv walks up from the cwd to find it.
load_dotenv()

DEFAULT_MODEL_ID = "claude-sonnet-5"
DEFAULT_MAX_TOKENS = 1536
TOP_K = 5


def get_model_id() -> str:
    return os.environ.get("ANTHROPIC_MODEL_ID", DEFAULT_MODEL_ID)


def get_max_tokens() -> int:
    return int(os.environ.get("ANTHROPIC_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))


def require_api_key() -> str:
    """Return ANTHROPIC_API_KEY, or raise a clear error if it's not set."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Set it in your shell "
            "(export ANTHROPIC_API_KEY=sk-ant-...) or in a .env file at the "
            "repo root -- see README.md for details."
        )
    return api_key
