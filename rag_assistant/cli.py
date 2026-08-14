"""Interactive terminal chat with the vehicle listings assistant.

Usage:
    uv run python -m rag_assistant.cli
"""

from __future__ import annotations

import sys

from . import config, data_store
from .agent import build_agent


def main() -> None:
    try:
        config.require_api_key()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"Loading listings from {config.DATA_DIR} ...")
    n = data_store.row_count()
    print(f"Loaded {n} listings. Ask me about vehicles (Ctrl-D or 'quit' to exit).\n")

    agent = build_agent()

    while True:
        try:
            message = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not message:
            continue
        if message.lower() in {"quit", "exit"}:
            break

        agent(message)
        print()


if __name__ == "__main__":
    main()
