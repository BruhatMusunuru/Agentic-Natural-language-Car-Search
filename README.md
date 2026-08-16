# car-search

Natural-language car search: turn a free-text query (e.g. *"reliable family
SUV under $30k, low mileage, near Chicago"*) into structured search filters
via an LLM agent, deterministically filter the **entire real car
inventory** (~22k listings across `data/*.parquet`) against them via SQL,
and return the top matches with a grounded explanation. Runs entirely
locally — no database server, no deployment, no auth.

## Setup

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
```

Set your Anthropic API key (the only required piece of configuration) —
either export it, or put it in a `.env` file at the repo root (loaded
automatically):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

If the key is missing entirely, you get a clear `ANTHROPIC_API_KEY is not
set` error rather than a raw SDK stack trace. See `.env` for the full list
of optional overrides (model ID, max tokens, host/port).

## Running the API locally

```bash
uv run car-search
# or: uv run uvicorn car_search.api.server:app --reload
```

Then, from another terminal:

```bash
curl -s -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "reliable family SUV under $30k, low mileage, near Chicago"}' | python3 -m json.tool
```

A malformed request (missing/empty `query`) returns a `4xx`. If a query is
too vague to search meaningfully (e.g. `"find me a car"`), the response
instead sets `clarifying_question` and returns no results.

## Running tests / typecheck / lint

```bash
uv run pytest      # unit tests only, no network calls required
uv run mypy         # strict typecheck (src, scripts, tests)
uv run ruff check .
```

## Running the golden-set eval

```bash
uv run python scripts/eval_golden_set.py [--strict]
```

Runs a 12-query hand-written golden set (`src/car_search/data/golden_set.json`)
through the real extraction step (this hits the live Anthropic API) and
prints a per-field precision/recall/F1 table plus contradiction- and
clarify-triggering behavior checks. `--strict` exits non-zero if the score
or a behavior check falls short — useful for CI.

## Architecture

![Architecture](arch_diagram.png)

Built with [AWS Strands Agents](https://strandsagents.com/) for
orchestration, the Anthropic API as the model provider, and
[DuckDB](https://duckdb.org/) for out-of-core querying of the full dataset
(no need to hold it all in memory).

- Diagram sources (Mermaid + draw.io) and per-diagram legends: `docs/diagrams/`
- Full package layout: `docs/layout.md`
- Data-shape decisions (price, location, fixtures): `docs/data.md`
