# car-search

Natural-language car search: turn a free-text query (e.g. *"reliable family
SUV under $30k, low mileage, near Chicago"*) into structured search filters
via an LLM agent, deterministically filter a curated, real car inventory
against them in plain Python, and return the top matches with a grounded
explanation.

Built with [AWS Strands Agents](https://strandsagents.com/) for
orchestration and the Anthropic API as the model provider. Runs entirely
locally — no database, no deployment, no auth — with nothing but a Strands
install and an `ANTHROPIC_API_KEY`.

## Setup

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
```

This installs all runtime dependencies, including `strands-agents[anthropic]`
(AWS Strands Agents with the Anthropic model provider), FastAPI, and the dev
tools (`pytest`, `mypy`, `ruff`).

Set your Anthropic API key (the only required piece of configuration):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Optional overrides (see `.env` for the full list):

| Variable              | Default            | Meaning                                   |
|-----------------------|--------------------|--------------------------------------------|
| `ANTHROPIC_MODEL_ID`  | `claude-sonnet-5`  | Anthropic model used for extraction/clarify |
| `ANTHROPIC_MAX_TOKENS`| `1536`             | Max tokens per model call                  |
| `HOST`                | `127.0.0.1`        | API bind host                              |
| `PORT`                | `8000`             | API bind port                              |

## Running the API locally

```bash
uv run car-search
# or: uv run uvicorn car_search.server:app --reload
```

Then, from another terminal:

```bash
curl -s -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "reliable family SUV under $30k, low mileage, near Chicago"}' | python3 -m json.tool
```

Example response (abridged):

```json
{
  "filters": {
    "make": null, "model": null, "body_type": "SUV",
    "price_max": 30000.0, "mileage_max": 50000, "year_min": null,
    "fuel_type": null, "location": "Chicago", "radius_mi": null
  },
  "results": [
    {"id": "784318216", "make": "Audi", "model": "Q5", "body_type": "SUV",
     "price": 23150.0, "mileage": 23117, "year": 2018, "fuel_type": "Gasoline",
     "city": "Schaumburg", "state": "IL", "zip": "60173"},
    "... up to 5 results, ranked by ascending price ..."
  ],
  "explanation": "Found 5 listings matching SUV, under 50,000 mi, under $30,000, near Chicago.",
  "relaxed_fields": null,
  "clarifying_question": null
}
```

A malformed request (missing/empty `query`) returns a `4xx`:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" -d '{}'
# 422
```

If a query is too vague to search meaningfully (e.g. `"find me a car"`),
the response instead sets `clarifying_question` and returns no results.

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

## About the data

The seed inventory (`src/car_search/data/seed_listings.json`, 26 listings)
is **curated from real rows** in `data/2026-07-01.csv` — a MarketCheck-style
US car-listing export — not synthetic/fabricated data. See
`scripts/curate_seed_listings.py` for the exact, reproducible selection
(hardcoded real `listingId`s with a comment on why each was picked). The
service loads this checked-in fixture once at startup; it never re-reads the
raw CSV/parquet files at runtime.

Two data-shape decisions worth knowing about:

- **Price**: `salePrice` and `kbbFairPurchasePrice` are gated (`"[PREMIUM]"`)
  in every row of the source export, so there's no usable per-listing sale
  price anywhere in the data. `kbbFairPriceHigh` (a real KBB fair-price
  band) is used as each listing's effective `price` throughout.
- **Location**: the source data has no `lat`/`lon` columns, only
  `sellerCity`/`sellerState`/`sellerZip`. Radius search uses a small,
  hardcoded `zip -> (lat, lon)` lookup (city-level approximation, sourced
  from public city coordinates) covering exactly the zips present in the
  curated fixture — there is no live/network geocoding.

## Project layout

```
src/car_search/
  models.py         SearchFilters / Listing pydantic models (+ enums)
  inventory.py       loads the curated seed fixture
  locations.py       static zip -> (lat, lon) lookup + free-text resolution
  distance.py         haversine distance in miles
  search.py           deterministic filter_listings + @tool search_listings
  guardrails.py       synonym mapping, price-shorthand normalization,
                       contradiction detection, defensive enum parsing
  relaxation.py        zero-result auto-relax (US-006)
  explanation.py        grounded, deterministic explanation template
  agent.py               Strands Agent wiring (extraction + clarify sub-agent)
  orchestrator.py         run_search: ties it all together
  server.py                 FastAPI POST /search
  data/
    seed_listings.json       curated real inventory (26 listings)
    golden_set.json            eval golden set
scripts/
  curate_seed_listings.py     regenerates seed_listings.json from data/2026-07-01.csv
  eval_golden_set.py           golden-set precision/recall eval
tests/                          pytest suite (no network calls required)
```

See `tasks/prd-natural-language-car-search.md` for the full PRD.
