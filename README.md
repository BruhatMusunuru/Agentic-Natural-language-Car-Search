# Vehicle Listings Assistant

A Q&A assistant grounded in a real dataset of AutoTrader vehicle listings
(`data/`). It's built on the [AWS Strands Agents SDK](https://strandsagents.com)
using Anthropic's Claude as the model provider, with a small set of tools
that query the listings so every answer is backed by actual rows rather than
the model's imagination.

## How it's grounded (RAG design)

- **Retrieval**: `data/data/*.parquet` (≈23.8k deduplicated listings) is
  loaded into an in-memory DuckDB table at startup (`rag_assistant/data_store.py`).
  Listings are deduped by `listingId`, and fields that are placeholder-masked
  in this sample export (`"[PREMIUM]"` — VIN, asking price, dealer
  name/phone/website, photos, listing URL) are nulled out rather than shown
  to the model as if they were real values.
- **Tools**: the agent has three tools (`rag_assistant/tools.py`):
  `search_listings` (structured filters: make/model/year/price/body
  style/fuel/location/etc, plus free-text keyword matching over the
  title/description/options), `get_listing_details` (full record for one
  listing), and `market_stats` (aggregate counts/price/mileage/deal-mix over
  a slice of the data).
- **Generation**: the agent (`rag_assistant/agent.py`) is instructed to
  always call a tool before answering questions about specific vehicles,
  prices, or availability; to cite `listingId`s; to say when a search comes
  up empty rather than invent a vehicle; and to describe price as an
  *estimated* KBB-based range since the real asking price isn't present in
  this sample.

Because there's no real asking price in the sample data, prices are the KBB
Fair Purchase Price range (falling back to MSRP for new vehicles) — the
system prompt makes the assistant say this explicitly rather than present it
as a listed price.

## Project layout

```
rag_assistant/
  config.py       # env-driven settings (API key, model id, data dir, ...)
  data_store.py   # DuckDB load/clean + search / get / stats queries
  tools.py         # @tool wrappers the agent calls
  agent.py         # builds the Strands Agent + AnthropicModel
  cli.py           # terminal chat loop
  server.py        # FastAPI app: POST /chat, GET /health, static UI
static/index.html  # minimal single-page chat UI served by the FastAPI app
Dockerfile, docker-compose.yml, .dockerignore
```

## Run it locally

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env        # then fill in ANTHROPIC_API_KEY
uv sync

# Terminal chat:
uv run python -m rag_assistant.cli

# Or the web app:
uv run uvicorn rag_assistant.server:app --reload
# -> open http://localhost:8000
```

`data/data/*.parquet` is loaded with DuckDB directly, so `pandas`/`jupyter`/etc.
aren't needed to run the app or tests. They're only used by `test.ipynb`;
grab them with `uv sync --group notebook` if you want to poke at the data
that way. This also keeps the Docker image lean (~700MB vs. ~2.1GB with the
notebook stack included).

## Run it in Docker

```bash
cp .env.example .env        # then fill in ANTHROPIC_API_KEY

docker compose up --build
# -> open http://localhost:8000
```

Or without compose:

```bash
docker build -t vehicle-listings-assistant .
docker run --rm -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -v "$(pwd)/data:/app/data:ro" \
  vehicle-listings-assistant
```

The listings data is mounted as a volume rather than baked into the image
(see `.dockerignore`), so you can swap in a bigger export without rebuilding.

## API

- `GET /health` → `{"status": "ok", "listings_loaded": <n>}`
- `POST /chat` → body `{"message": "...", "session_id": "<optional>"}`,
  returns `{"reply": "...", "session_id": "..."}`. Omit `session_id` on the
  first call and reuse the one you get back to continue the same
  conversation (sessions are in-memory only — an MVP simplification, they
  don't survive a restart).
- `DELETE /session/{session_id}` → clears a conversation.

`/chat` error responses: `400` empty message, `422` malformed body, `500`
misconfiguration (e.g. missing API key), `409` if a second request for the
same `session_id` arrives while the first is still being answered (send
messages for one session one at a time), `502` on any other failure talking
to Claude.

## Tests

```bash
uv run pytest
```

`tests/` covers the DuckDB retrieval layer, the Strands tool wrappers, and
the FastAPI app's non-LLM behavior (health check, static UI, validation) —
none of it needs an API key.

## What's verified vs. not

Built and smoke-tested end-to-end in this environment: the automated test
suite above, the Docker image build, and a live container run (non-root
user, `/health` healthcheck passing, data volume mounted and readable) —
hitting it with a syntactically-valid-but-invalid Anthropic key reached
Anthropic's API and got back a clean `401 authentication_error`, confirming
the whole request path (FastAPI → Strands `Agent` → `AnthropicModel` →
Anthropic API) is wired correctly. A live conversation was **not** exercised
here since no real `ANTHROPIC_API_KEY` was available in this sandbox — set
one in `.env` and try the CLI or web UI to see it answer for real.

## Environment variables

See `.env.example`. Notably `ANTHROPIC_API_KEY` (required),
`ANTHROPIC_MODEL_ID` (defaults to a current Claude Sonnet), and
`LISTINGS_DATA_DIR` if you want to point at a different data export.
