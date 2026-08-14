"""FastAPI app exposing the vehicle listings assistant as a small chat API
plus a static single-page chat UI, for the MVP / Docker deployment.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from strands.types.exceptions import ConcurrencyException

from . import config, data_store
from .agent import build_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag_assistant.server")

STATIC_DIR = config.PROJECT_ROOT / "static"


@asynccontextmanager
async def _lifespan(_: FastAPI):
    # Build the DuckDB table eagerly so the first request isn't slow and so
    # startup fails fast if the data directory is misconfigured. Also verify
    # the API key is present so misconfiguration surfaces immediately in the
    # container logs rather than on the first chat request.
    n = data_store.row_count()
    logger.info("Loaded %d listings from %s", n, config.DATA_DIR)
    config.require_api_key()
    yield


app = FastAPI(title="Vehicle Listings Assistant", version="0.1.0", lifespan=_lifespan)

# In-memory session store: session_id -> (Agent, last_used_epoch_seconds).
# A Strands Agent holds its own running conversation history, so reusing the
# same instance across turns is what gives the API multi-turn memory. This is
# an MVP: sessions are lost on restart and never persisted to disk.
_sessions: dict[str, tuple] = {}
_sessions_lock = threading.Lock()
_SESSION_TTL_SECONDS = 60 * 60


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


def _get_or_create_agent(session_id: str | None) -> tuple[str, object]:
    now = time.time()
    with _sessions_lock:
        # Opportunistically drop stale sessions.
        stale = [sid for sid, (_, last) in _sessions.items() if now - last > _SESSION_TTL_SECONDS]
        for sid in stale:
            del _sessions[sid]

        if session_id and session_id in _sessions:
            agent, _ = _sessions[session_id]
            _sessions[session_id] = (agent, now)
            return session_id, agent

        new_id = session_id or str(uuid.uuid4())
        agent = build_agent(callback_handler=None)
        _sessions[new_id] = (agent, now)
        return new_id, agent


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "listings_loaded": data_store.row_count()}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message must not be empty")

    try:
        session_id, agent = _get_or_create_agent(req.session_id)
        result = agent(message)
    except RuntimeError as exc:
        # e.g. missing ANTHROPIC_API_KEY.
        raise HTTPException(status_code=500, detail=str(exc))
    except ConcurrencyException:
        # A Strands Agent instance refuses concurrent invocation rather than
        # corrupting its conversation history - this happens if two requests
        # for the same session_id land at the same time (e.g. a double
        # click/retry). Not a server failure, so give it its own status
        # instead of the generic 502 below.
        raise HTTPException(
            status_code=409,
            detail="A request for this session is already in progress. Wait for it to finish before sending another.",
        )
    except Exception:
        logger.exception("agent invocation failed")
        raise HTTPException(status_code=502, detail="assistant failed to generate a response")

    return ChatResponse(reply=str(result), session_id=session_id)


@app.delete("/session/{session_id}")
def clear_session(session_id: str) -> dict:
    with _sessions_lock:
        existed = _sessions.pop(session_id, None) is not None
    return {"cleared": existed}


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(str(STATIC_DIR / "index.html"))
