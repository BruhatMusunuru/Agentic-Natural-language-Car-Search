"""Runtime configuration for the RAG assistant.

All settings are read from environment variables (optionally loaded from a
``.env`` file) so the same code runs unmodified on a laptop or inside the
Docker container.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load a local .env file if present (no-op if it doesn't exist).
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Directory containing the AutoTrader listing parquet files (data/data/*.parquet).
DATA_DIR = Path(os.environ.get("LISTINGS_DATA_DIR", PROJECT_ROOT / "data" / "data"))

# Anthropic credentials / model selection. ANTHROPIC_API_KEY is intentionally
# not snapshotted into a module-level constant: require_api_key() re-reads
# the environment on every call so tests (and callers that set the env var
# after this module is first imported) see the current value rather than
# whatever was present at import time.
ANTHROPIC_MODEL_ID = os.environ.get("ANTHROPIC_MODEL_ID", "claude-sonnet-5")
ANTHROPIC_MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "1536"))

# Default number of listings a search tool call returns.
DEFAULT_SEARCH_LIMIT = int(os.environ.get("DEFAULT_SEARCH_LIMIT", "8"))
MAX_SEARCH_LIMIT = int(os.environ.get("MAX_SEARCH_LIMIT", "25"))

# Web server.
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))


def require_api_key() -> str:
    """Return the configured Anthropic API key or raise a clear error."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it or add it to a .env file "
            "(see .env.example)."
        )
    return key
