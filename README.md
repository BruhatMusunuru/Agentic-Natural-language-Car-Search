# car-search

Natural-language car search: turn a free-text query (e.g. *"reliable family
SUV under $30k, low mileage, near Chicago"*) into structured search filters
via an LLM agent, deterministically filter the **entire real car
inventory** (~22k listings across `data/*.parquet`) against them via SQL,
and return the top matches with a grounded explanation.

Built with [AWS Strands Agents](https://strandsagents.com/) for
orchestration, the Anthropic API as the model provider, and
[DuckDB](https://duckdb.org/) for out-of-core querying of the full dataset
(no need to hold it all in memory). Runs entirely locally — no database
server, no deployment, no auth — with nothing but a Strands install and an
`ANTHROPIC_API_KEY`.

## Setup

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
```

This installs all runtime dependencies, including `strands-agents[anthropic]`
(AWS Strands Agents with the Anthropic model provider), FastAPI, and the dev
tools (`pytest`, `mypy`, `ruff`).

Set your Anthropic API key (the only required piece of configuration).
Either export it in your shell:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

or put it in a `.env` file at the repo root -- it's loaded automatically
(via `python-dotenv`) whenever the service starts, so `uv run car-search`
and friends work without a manual `export`/`source` step. A shell-exported
value always takes precedence over `.env`. If the key is missing entirely,
you get a clear `ANTHROPIC_API_KEY is not set` error rather than a raw SDK
stack trace.

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

Search runs against the **entire** real dataset in `data/*.parquet` — every
daily MarketCheck-style export snapshot (30 files, ~22k listings after
data-quality filtering), not a hand-picked subset. `dataset.py` queries the
parquet files directly through [DuckDB](https://duckdb.org/), an embedded
OLAP engine: every filter (make/model/body/price/mileage/year/fuel, and
location+radius via a SQL haversine expression) is pushed down into a
vectorized SQL scan, so the service never loads the ~22k-row dataset into
Python objects/memory — only the handful of rows that actually match a
search get materialized. A search across the whole dataset takes well
under 200ms once DuckDB's connection is warm.

Two data-shape decisions worth knowing about:

- **Price**: `salePrice` and `kbbFairPurchasePrice` are gated (`"[PREMIUM]"`)
  in every row of the source export, so there's no usable per-listing sale
  price anywhere in the data. `kbbFairPriceHigh` (a real KBB fair-price
  band) is used as each listing's effective `price` throughout. Rows with
  `kbbFairPriceHigh <= 0` (a "missing price" sentinel — ~5.8% of otherwise-
  qualifying rows, with a clean gap before the next-lowest real price of
  ~$1,680) are excluded as data-quality noise, the same way `[PREMIUM]`/
  empty values are.
- **Location**: the source data has no `lat`/`lon` columns, only
  `sellerCity`/`sellerState`/`sellerZip` (~4k distinct zips across the full
  dataset — too many to hand-maintain). `locations.py` resolves zips and
  city names via the [`zipcodes`](https://pypi.org/project/zipcodes/)
  package, which bundles a complete offline US zip-code dataset (~43k
  zips, ~1.9MB) — no network geocoding call, ever. Ambiguous city names
  (e.g. "Beverly Hills" exists in both CA and FL) resolve to whichever
  state has more zips under that name, rather than averaging across
  unrelated regions.

The small curated fixture (`src/car_search/data/seed_listings.json`, 26
hand-picked real rows, built by `scripts/curate_seed_listings.py`) is no
longer the production data source — it's kept checked in purely so the
unit test suite has a small, fast, dependency-light dataset to test
`search.py`'s reference filtering logic against without needing DuckDB/
parquet I/O for every test.

## Project layout

```
src/car_search/
  models.py         SearchFilters / Listing / FilterResult pydantic+dataclass models
  dataset.py          DuckDB-backed out-of-core query engine over data/*.parquet (production)
  inventory.py         loads the small curated fixture (tests only, see "About the data")
  locations.py           zip/city -> (lat, lon) resolution via the zipcodes package
  distance.py               haversine distance in miles
  search.py                   filter_listings (in-memory reference impl) + @tool search_listings
  guardrails.py                synonym mapping, price-shorthand normalization,
                                contradiction detection, defensive enum parsing
  relaxation.py                 zero-result auto-relax (US-006), backend-agnostic (search_fn)
  explanation.py                 grounded, deterministic explanation template
  agent.py                        Strands Agent wiring (extraction + clarify sub-agent)
  orchestrator.py                  run_search: ties it all together
  server.py                          FastAPI POST /search
  data/
    seed_listings.json                 curated fixture (test-only, 26 listings)
    golden_set.json                      eval golden set
scripts/
  curate_seed_listings.py                regenerates seed_listings.json (test fixture)
  eval_golden_set.py                       golden-set precision/recall eval
tests/                                      pytest suite (no network calls required)
```

See `tasks/prd-natural-language-car-search.md` for the full PRD.
