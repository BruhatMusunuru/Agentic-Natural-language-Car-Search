# Project layout

```
src/car_search/
  __init__.py          main() entry point; re-exports SearchResponse, run_search
  orchestrator.py       run_search: ties extraction, guardrails, search, and
                          explanation together (cross-cutting, stays at root)
  core/
    __init__.py          re-exports SearchFilters, Listing, BodyType, FuelType,
                          FilterResult, TOP_K, get_model_id, get_max_tokens,
                          require_api_key
    models.py              SearchFilters / Listing / FilterResult pydantic+dataclass models
    config.py               env-var config, .env loading, ANTHROPIC_API_KEY checks
  geo/
    __init__.py          re-exports resolve_location, zip_to_coords,
                          DEFAULT_RADIUS_MI, haversine_miles
    locations.py           zip/city -> (lat, lon) resolution via the zipcodes package
    distance.py              haversine distance in miles
  data/
    __init__.py          re-exports load_listings
    inventory.py           loads the small curated fixture (tests only, see docs/data.md)
    seed_listings.json       curated fixture (test-only, 26 listings)
    golden_set.json          eval golden set
  search/
    __init__.py          re-exports search_listings, filter_listings, FILTER_FIELDS,
                          search_full_dataset, dataset_row_count, relax_and_search,
                          RelaxationStep, SearchFn, build_explanation
    dataset.py              DuckDB-backed out-of-core query engine over data/*.parquet (production)
    search.py                filter_listings (in-memory reference impl) + @tool search_listings
    relaxation.py             zero-result auto-relax, backend-agnostic (search_fn)
    explanation.py             grounded, deterministic explanation template
  agents/
    __init__.py          re-exports extract_filters, ask_clarifying_question,
                          needs_clarification, build_extraction_agent,
                          build_clarify_agent, build_model, detect_contradiction,
                          apply_synonym_fallback, apply_price_shorthand_fallback,
                          safe_parse_search_filters
    agent.py                Strands Agent wiring (extraction + clarify sub-agent)
    guardrails.py             synonym mapping, price-shorthand normalization,
                                contradiction detection, defensive enum parsing
  api/
    __init__.py          re-exports app
    server.py               FastAPI POST /search
scripts/
  curate_seed_listings.py    regenerates seed_listings.json (test fixture)
  eval_golden_set.py           golden-set precision/recall eval
tests/                          pytest suite (no network calls required)
docs/
  layout.md                      this file
  data.md                          data-shape decisions (price, location, fixtures)
  diagrams/                         Mermaid/draw.io architecture diagram sources
```

See `archive/2026-08-16-natural-language-car-search/prd-natural-language-car-search.md`
for the full original feature PRD, and `tasks/prd-src-restructure-and-readme.md` for the
PRD behind this package layout.
