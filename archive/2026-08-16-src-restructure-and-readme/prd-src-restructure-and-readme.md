# PRD: Restructure src/car_search into Subpackages + Crisp README

## 1. Introduction/Overview

`src/car_search/` has grown to 13 flat modules covering everything from Pydantic models to the FastAPI app to the LLM agent wiring. This PRD groups those modules into cohesive subpackages (`core/`, `geo/`, `data/`, `search/`, `agents/`, `api/`) following standard Python package-organization practice, with `orchestrator.py` remaining at the top level as the cross-cutting use-case layer that ties every subpackage together.

Separately (but delivered together, since both were requested as one cleanup pass), the README gets rewritten to be crisp: setup/run/test essentials only, a new Architecture section with the already-committed `arch_diagram.png` inlined, and the deep-dive content (full project-layout tree, the data-shape decisions writeup) moved into new `docs/layout.md` and `docs/data.md` files linked from the README.

This PRD is internal restructuring + docs. It changes **where code lives and how the README reads**, not what the service does — every existing test must still pass and the API's runtime behavior must be identical before and after.

## 2. Goals

- Replace the flat `src/car_search/` module list with 6 cohesive subpackages, each with an `__init__.py` that re-exports its public names.
- Keep `orchestrator.py` and the top-level `car_search/__init__.py` at the package root, since orchestration is cross-cutting rather than owned by any one subpackage.
- Never leave the tree in a broken state: every story ends with the full test suite, mypy, and ruff green.
- Rewrite `README.md` to be short and scannable, with the architecture diagram inlined and detailed content linked out to `docs/`.

## 3. Target Package Layout

```
src/car_search/
  __init__.py          # main() entry point, re-exports the primary public API
  orchestrator.py       # SearchResponse, run_search -- cross-cutting, stays at root
  core/
    __init__.py          # re-exports SearchFilters, Listing, BodyType, FuelType,
                          # FilterResult, TOP_K, get_model_id, get_max_tokens, require_api_key
    models.py
    config.py
  geo/
    __init__.py          # re-exports resolve_location, zip_to_coords, haversine_miles,
                          # DEFAULT_RADIUS_MI
    locations.py
    distance.py
  data/
    __init__.py          # re-exports load_listings
    inventory.py
    seed_listings.json
    golden_set.json
  search/
    __init__.py          # re-exports search_listings, filter_listings, FILTER_FIELDS,
                          # search_full_dataset, relax_and_search, RelaxationStep,
                          # SearchFn, build_explanation
    dataset.py
    search.py
    relaxation.py
    explanation.py
  agents/
    __init__.py          # re-exports extract_filters, ask_clarifying_question,
                          # needs_clarification, build_extraction_agent, build_clarify_agent,
                          # detect_contradiction, apply_synonym_fallback,
                          # apply_price_shorthand_fallback, safe_parse_search_filters
    agent.py
    guardrails.py
  api/
    __init__.py          # re-exports app
    server.py
```

## 4. User Stories

### US-001: `core` subpackage (models, config)
**Description:** As a developer, I want `models.py` and `config.py` in a `core` subpackage so the two modules everything else depends on are clearly identified as the foundation layer.

**Acceptance Criteria:**
- [ ] `models.py` and `config.py` moved to `src/car_search/core/models.py` and `src/car_search/core/config.py`
- [ ] `src/car_search/core/__init__.py` re-exports `SearchFilters`, `Listing`, `BodyType`, `FuelType`, `FilterResult` (from models) and `TOP_K`, `get_model_id`, `get_max_tokens`, `require_api_key` (from config)
- [ ] Every import of `car_search.models` / `car_search.config` across `src/`, `tests/`, and `scripts/` updated to the new path (`car_search.core` or `car_search.core.models`/`car_search.core.config`) -- `grep -rn "from car_search.models\|from car_search.config\|car_search\.models\|car_search\.config" src tests scripts` returns no hits outside `core/` itself
- [ ] `uv run pytest`, `uv run mypy`, `uv run ruff check .` all pass

### US-002: `geo` subpackage (locations, distance)
**Description:** As a developer, I want the zip-resolution and haversine-distance code in a `geo` subpackage since they're a self-contained concern with no dependency on anything else in the codebase.

**Acceptance Criteria:**
- [ ] `locations.py` and `distance.py` moved to `src/car_search/geo/locations.py` and `src/car_search/geo/distance.py`
- [ ] `src/car_search/geo/__init__.py` re-exports `resolve_location`, `zip_to_coords`, `DEFAULT_RADIUS_MI` (from locations) and `haversine_miles` (from distance)
- [ ] Every import of `car_search.locations` / `car_search.distance` across `src/`, `tests/`, and `scripts/` updated -- grep for the old paths returns no hits outside `geo/`
- [ ] `uv run pytest`, `uv run mypy`, `uv run ruff check .` all pass

### US-003: `data` subpackage (inventory + fixtures)
**Description:** As a developer, I want the curated-fixture loader colocated with the fixture files it loads, in a `data` subpackage.

**Acceptance Criteria:**
- [ ] `inventory.py` moved to `src/car_search/data/inventory.py`; `seed_listings.json` and `golden_set.json` (already at `src/car_search/data/`) stay in place
- [ ] `SEED_LISTINGS_PATH` in the moved `inventory.py` updated to `Path(__file__).resolve().parent / "seed_listings.json"` (no longer `.parent / "data" / "seed_listings.json"` -- `__file__`'s parent is now the data directory itself, not its parent)
- [ ] `src/car_search/data/__init__.py` re-exports `load_listings`
- [ ] Every import of `car_search.inventory` across `src/`, `tests/`, and `scripts/` updated -- grep for the old path returns no hits outside `data/`
- [ ] `uv run pytest` confirms `load_listings()` still finds and loads `seed_listings.json` correctly (i.e. the path fix in the second bullet actually works, not just typechecks) -- add or reuse a test that calls `load_listings()` and asserts a nonzero result
- [ ] `uv run mypy`, `uv run ruff check .` pass

### US-004: `search` subpackage (dataset, search, relaxation, explanation)
**Description:** As a developer, I want every deterministic-search-related module (the DuckDB engine, the in-memory reference filter, zero-result relaxation, and explanation generation) grouped under `search/`.

**Acceptance Criteria:**
- [ ] `dataset.py`, `search.py`, `relaxation.py`, `explanation.py` moved to `src/car_search/search/`
- [ ] `DATA_GLOB` in the moved `dataset.py` (built from `Path(__file__).resolve().parent.parent.parent`) re-verified/updated to still resolve to the repo-root `data/` directory correctly from its new location (one extra level of nesting)
- [ ] `src/car_search/search/__init__.py` re-exports `search_listings`, `filter_listings`, `FILTER_FIELDS`, `search_full_dataset`, `dataset_row_count`, `relax_and_search`, `RelaxationStep`, `SearchFn`, `build_explanation`
- [ ] Every import of `car_search.dataset` / `car_search.search` / `car_search.relaxation` / `car_search.explanation` across `src/`, `tests/`, and `scripts/` updated -- grep for the old paths returns no hits outside `search/`
- [ ] `uv run pytest`, `uv run mypy`, `uv run ruff check .` all pass

### US-005: `agents` subpackage (agent, guardrails)
**Description:** As a developer, I want the Strands agent wiring and the extraction guardrails grouped under `agents/`, since guardrails exist specifically to make agent output trustworthy.

**Acceptance Criteria:**
- [ ] `agent.py` and `guardrails.py` moved to `src/car_search/agents/`
- [ ] `src/car_search/agents/__init__.py` re-exports `extract_filters`, `ask_clarifying_question`, `needs_clarification`, `build_extraction_agent`, `build_clarify_agent`, `build_model` (from agent) and `detect_contradiction`, `apply_synonym_fallback`, `apply_price_shorthand_fallback`, `safe_parse_search_filters` (from guardrails)
- [ ] Every import of `car_search.agent` / `car_search.guardrails` across `src/`, `tests/`, and `scripts/` updated -- grep for the old paths returns no hits outside `agents/`
- [ ] `uv run pytest`, `uv run mypy`, `uv run ruff check .` all pass

### US-006: `api` subpackage (server) + entry point
**Description:** As a developer, I want the FastAPI app in its own `api/` subpackage, with the console-script entry point updated to match.

**Acceptance Criteria:**
- [ ] `server.py` moved to `src/car_search/api/server.py`
- [ ] `src/car_search/api/__init__.py` re-exports `app`
- [ ] Top-level `src/car_search/__init__.py`'s `main()` updated to run `"car_search.api.server:app"` (was `"car_search.server:app"`)
- [ ] `uv run car-search` still starts the server successfully (manual verification: start it, confirm it's listening, stop it)
- [ ] `uv run pytest`, `uv run mypy`, `uv run ruff check .` all pass

### US-007: `orchestrator.py` import fixes + top-level `__init__.py` public API
**Description:** As a developer, I want `orchestrator.py`'s imports updated to the new subpackage paths, and the top-level `__init__.py` to re-export the handful of names most callers actually need, so `orchestrator.py` and the package root are the last pieces wired up correctly.

**Acceptance Criteria:**
- [ ] `orchestrator.py` stays at `src/car_search/orchestrator.py` (not moved into any subpackage -- it's cross-cutting, importing from `agents`, `search`, and `core`)
- [ ] `orchestrator.py`'s imports updated to the new paths (`car_search.agents`, `car_search.search`, `car_search.core`)
- [ ] Top-level `src/car_search/__init__.py` re-exports `SearchResponse`, `run_search` (from orchestrator) in addition to `main`
- [ ] `uv run pytest`, `uv run mypy`, `uv run ruff check .` all pass

### US-008: End-to-end smoke verification
**Description:** As a developer, I want to confirm the restructured package actually works at runtime, not just at the type/unit-test level, since import-path mistakes can pass mypy/pytest yet still break real startup.

**Acceptance Criteria:**
- [ ] Fresh `uv sync` succeeds with no errors
- [ ] `uv run car-search` starts successfully; `curl -X POST http://127.0.0.1:8000/search -d '{"query": "reliable family SUV under $30k, low mileage, near Chicago"}'` returns a 200 with real results (manual verification, live Anthropic API call)
- [ ] `curl -X POST .../search -d '{}'` returns a 4xx
- [ ] `uv run python scripts/eval_golden_set.py` runs without import errors (manual verification; live API call, don't need to check the score)
- [ ] Full test suite (`uv run pytest`), `uv run mypy`, `uv run ruff check .` all pass one final time with the complete restructured tree

### US-009: Crisp README with inlined architecture diagram
**Description:** As a new developer, I want a short, scannable README that shows me the architecture at a glance and gets me running quickly, with deeper detail one click away instead of inline.

**Acceptance Criteria:**
- [ ] New `docs/layout.md` contains the full project-layout tree (the content currently in README's "Project layout" section), updated to reflect the US-001 through US-007 restructuring
- [ ] New `docs/data.md` contains the data-shape decisions writeup (the content currently in README's "About the data" section: price/`kbbFairPriceHigh` reasoning, zip-lookup-via-`zipcodes`-package reasoning, the curated-fixture-is-test-only note)
- [ ] `README.md` rewritten to: one short pitch paragraph, setup (`uv sync` + `ANTHROPIC_API_KEY`), run + one curl example, test/lint/eval commands, and a new "Architecture" section
- [ ] The "Architecture" section inlines `arch_diagram.png` (`![Architecture](arch_diagram.png)`) and links to `docs/diagrams/` (for the Mermaid/draw.io sources and per-diagram legends), `docs/layout.md`, and `docs/data.md`
- [ ] README stays under roughly 100 lines (down from the current ~184)
- [ ] Every command shown in the trimmed README (`uv sync`, `uv run car-search`, the curl example, `uv run pytest`, `uv run mypy`, `uv run ruff check .`, `uv run python scripts/eval_golden_set.py`) still works exactly as written, verified by actually running each one

## 5. Functional Requirements

- FR-1: `src/car_search/` must be reorganized into the subpackages listed in Section 3, each with an `__init__.py` re-exporting its public names.
- FR-2: `orchestrator.py` and the top-level `__init__.py` remain at `src/car_search/` root.
- FR-3: No behavior change: the FastAPI JSON contract, CLI entry point name (`car-search`), and all existing test assertions must be unaffected by the move -- this is a pure internal reorganization.
- FR-4: Every `Path(__file__)`-relative path calculation (in `dataset.py` and the moved `inventory.py`) must be re-verified against its new file location, not just left as-is.
- FR-5: After every story, `uv run pytest`, `uv run mypy`, and `uv run ruff check .` must all pass before moving to the next story -- the tree is never left broken between stories.
- FR-6: `README.md` must inline `arch_diagram.png` and link to `docs/diagrams/`, `docs/layout.md`, and `docs/data.md`.
- FR-7: `docs/layout.md` and `docs/data.md` must be created to hold content moved out of the README, not deleted.

## 6. Non-Goals (Out of Scope)

- No behavior/logic changes to any module -- this is file moves + import fixes only.
- No renaming of individual files beyond what's needed to resolve the `search/search.py` naming (see Open Questions) -- keep module names as listed in Section 3.
- No changes to `data/*.parquet`/`data/*.csv` (the real dataset) or `docs/diagrams/*` (already done in a prior PRD).
- No CI/CD, Docker, or deployment config changes (none currently exist in this repo).
- No new dependencies.

## 7. Design Considerations

- N/A (backend-only restructuring, no UI).

## 8. Technical Considerations

- **Path-relative-to-`__file__` gotcha:** any module that computes a sibling/nearby file path via `Path(__file__).resolve().parent...` needs that arithmetic re-verified after moving, since the number of `.parent` hops needed changes when the file gains or loses a directory level. This affects `inventory.py` (US-003) and `dataset.py` (US-004) specifically.
- **Order matters:** the story order in Section 4 is a dependency order -- `core` first (nothing depends on anything, everything depends on it), then the other leaf-ish subpackages, then `search`/`agents` (which depend on `core`/`geo`/`data`), then `api` and `orchestrator.py` last (which depend on everything else). Do not reorder.
- **`__init__.py` re-exports** are what let the rest of the codebase (and any external caller) write `from car_search.core import SearchFilters` instead of needing to know it's specifically in `core/models.py`. Keep them accurate and complete per the lists in Section 3 -- an incomplete re-export list will cause import errors elsewhere that only show up when that specific name is used, so grep every call site rather than trusting the list is exhaustive.
- **pyproject.toml**: `[project.scripts]` still points at `car_search:main`, which is unaffected by the internal restructuring (US-006 only changes what `main()` does internally). `[tool.mypy] files` and `[tool.pytest.ini_options] testpaths` are directory-based and need no changes.

## 9. Success Metrics

- `uv run pytest && uv run mypy && uv run ruff check .` all pass after every story, and again at the end.
- A developer can `grep -rn "^from car_search\.[a-z_]* import\|^import car_search\."` across `src/`/`tests/`/`scripts/` and see only the new subpackage-qualified paths -- no stale flat-module imports remain.
- README is under ~100 lines and a new developer can go from clean checkout to a working `/search` call using only what's in it.
- The architecture diagram is visible on GitHub/GitLab's README preview without clicking through.

## 10. Open Questions

- `search/search.py` (the file, inside the `search/` subpackage) is a slightly redundant name (`car_search.search.search`). The approved grouping keeps this name as-is; renaming it (e.g. to `filtering.py`) is an easy follow-up but explicitly out of scope here to avoid scope creep beyond what was requested.
- Whether `docs/layout.md` should be regenerated by a script (so it can't drift from the real tree) versus hand-maintained -- left hand-maintained for now given the small size of the codebase.
