# PRD: Search Code Quality & Performance Cleanup

## Introduction/Overview

A code review of the `car_search` package (see `code-improver` findings, 2026-08-16) identified four issues concentrated in the search subsystem: a performance problem in the dataset query layer, a minor race condition in a shared cache file, a stale/misleading comment in the search module, and a missing error-handling boundary in the API layer. This PRD scopes the fix for all four.

The primary driver is **search latency**: `search_full_dataset` currently issues up to 9 separate full-table scans per call (one `SELECT count(*)` per filter field plus one for the radius predicate, then a final matching query), and `relax_and_search` can call it up to 5 times when a query returns zero results — meaning a single user query can trigger up to ~45 scans of the parquet dataset. Consolidating the per-field counts into one aggregate query cuts this to 2 scans per call regardless of relaxation depth.

The other three items are lower-effort cleanups bundled into the same unit of work because they touch adjacent files and were flagged in the same review pass.

## Goals

- Reduce DB round-trips in `search_full_dataset` from up to 9 to exactly 2 per call, with a test asserting the new call count.
- Eliminate the check-then-write race in the zip-coords CSV cache path.
- Remove the misleading relaxation-order comment on `FILTER_FIELDS` (or the field itself, if genuinely unused).
- Bring `_relax_field` in line with the dict-of-callables convention used elsewhere in `search/`.
- Ensure `/search` returns a clean, non-5xx-traceback error response when `run_search` raises due to config or upstream LLM failure.
- No behavioral regression: existing test suite (`tests/test_dataset.py`, `tests/test_search.py`, `tests/test_relaxation.py`, `tests/test_server.py`) passes unchanged in its existing assertions.

## User Stories

### US-001: Consolidate per-field exclusion counts into a single aggregate query
**Description:** As a user issuing a search, I want the backend to compute filter-exclusion counts without repeatedly scanning the full dataset, so that searches (especially ones that trigger relaxation) return faster.

**Acceptance Criteria:**
- [ ] `search_full_dataset` in `src/car_search/search/dataset.py` computes all per-field exclusion counts (`make`, `model`, `body_type`, `price_max`, `mileage_max`, `year_min`, `fuel_type`, `radius_mi`) via a single `SELECT` using conditional aggregation (`sum(CASE WHEN NOT (...) THEN 1 ELSE 0 END) AS field`), rather than one `SELECT count(*)` per field.
- [ ] The function issues exactly 2 queries against `base_from` per call: one aggregate-count query and one query for matching rows (down from up to 9).
- [ ] A new test (in `tests/test_dataset.py`) mocks or instruments the DuckDB connection/query execution and asserts the query count per `search_full_dataset` call is 2, regardless of how many filters are set.
- [ ] `excluded_by` output is unchanged in shape and values compared to the old per-field-query approach (verified by existing tests in `tests/test_dataset.py` continuing to pass without modification to their assertions).
- [ ] Field names used as SQL column aliases remain restricted to the fixed, hardcoded set of Python identifiers already in `field_predicates`/`radius_predicate` (no user input is ever used as a column alias) — add a code comment noting this trust boundary, matching the existing precedent in `_connection()`.
- [ ] Typecheck/lint passes.

### US-002: Fix check-then-write race in zip-coords cache
**Description:** As an operator running multiple worker processes, I want the zip-coords CSV cache to be written atomically, so that concurrent workers can't corrupt or read a partially-written cache file.

**Acceptance Criteria:**
- [ ] `_zip_coords_csv_path` in `src/car_search/search/dataset.py` writes to a temporary file suffixed with the process ID (e.g. `cache_path.with_suffix(f".{os.getpid()}.tmp")`) and then atomically renames it into place via `Path.replace()`.
- [ ] `import os` added to `dataset.py`.
- [ ] Existing behavior for the already-cached case (`cache_path.exists()` returns the existing path without rewriting) is unchanged.
- [ ] Existing tests in `tests/test_dataset.py` covering this function continue to pass.
- [ ] Typecheck/lint passes.

### US-003: Fix or remove the misleading `FILTER_FIELDS` comment
**Description:** As a developer reading `search.py`, I want the comment on `FILTER_FIELDS` to accurately describe the tuple, so I don't waste time reconciling it against `relaxation.py`'s actual relaxation order.

**Acceptance Criteria:**
- [ ] Confirm whether `FILTER_FIELDS` (in `src/car_search/search/search.py`) is consumed anywhere besides its re-export from `src/car_search/search/__init__.py`.
- [ ] If unused beyond the re-export: remove `FILTER_FIELDS` and its re-export.
- [ ] If it turns out to be used (directly or by an external consumer of the package): keep it, but rewrite the comment to describe what the order actually represents (declaration order used by `filter_listings`'s predicate dict) instead of claiming it matches `relaxation.py`'s `_RELAXATION_ORDER`.
- [ ] No change to `_RELAXATION_ORDER` in `relaxation.py` — that ordering is out of scope here (see US-004 for its dispatch logic).
- [ ] Existing tests in `tests/test_search.py` pass; if `FILTER_FIELDS` is removed, no test references it (confirm via search before removing).
- [ ] Typecheck/lint passes.

### US-004: Refactor `_relax_field` into a dispatch table
**Description:** As a developer extending relaxation logic, I want per-field relaxation logic organized as small named functions in a dispatch dict, consistent with the style used in `search.py`, so the code is easier to scan and extend.

**Acceptance Criteria:**
- [ ] `_relax_field` in `src/car_search/search/relaxation.py` is replaced with individual functions per field (`_relax_radius`, `_relax_mileage_max`, `_relax_price_max`, `_relax_year_min`), each with the same signature and return behavior as the corresponding branch in the current if/elif chain.
- [ ] A `_RELAXERS: dict[str, Callable[[SearchFilters], tuple[SearchFilters, RelaxationStep] | None]]` maps field name to its handler function.
- [ ] `_relax_field(field, filters)` becomes a thin lookup: `_RELAXERS[field](filters)`, preserving the existing `ValueError` behavior for unknown fields (either via `.get()` with an explicit raise, or by letting `KeyError` propagate — decide and keep the resulting error type/message equivalent to today's `ValueError(f"Unknown relaxable field: {field}")` so callers aren't surprised).
- [ ] All existing tests in `tests/test_relaxation.py` pass unchanged, including any test that exercises the unknown-field error path.
- [ ] Typecheck/lint passes.

### US-005: Return a clean error response from `/search` on internal failures
**Description:** As an API consumer, I want `/search` to return a structured error response instead of a raw 500 traceback when the backend fails due to configuration or upstream LLM issues, so I can distinguish "bad request" from "service problem" and avoid leaking internals.

**Acceptance Criteria:**
- [ ] The `/search` endpoint in `src/car_search/api/server.py` wraps the call to `run_search(query)` in a `try/except RuntimeError` block.
- [ ] On `RuntimeError` (e.g. missing/invalid `ANTHROPIC_API_KEY`, upstream LLM failure surfaced as `RuntimeError`), the endpoint raises `HTTPException(status_code=502, detail=str(exc))` chained with `from exc`.
- [ ] The existing 422 behavior for empty query strings is unchanged.
- [ ] A new test in `tests/test_server.py` simulates `run_search` raising `RuntimeError` (e.g. via monkeypatching/dependency override) and asserts the response is a 502 with the error detail in the body, not an unhandled 500.
- [ ] Existing tests in `tests/test_server.py` continue to pass.
- [ ] Typecheck/lint passes.

## Functional Requirements

- FR-1: `search_full_dataset` must compute exclusion counts for all filter fields and the radius filter using one aggregate SQL query instead of one query per field.
- FR-2: `search_full_dataset` must issue exactly 2 queries against the dataset per call (1 aggregate-count query + 1 match query), independent of how many filters are active.
- FR-3: `_zip_coords_csv_path` must write the cache file to a unique temporary path and atomically rename it into place, never leaving a partially-written file at the final `cache_path`.
- FR-4: `FILTER_FIELDS` in `search.py` must either be removed (if unused outside its own re-export) or have its comment corrected to no longer claim alignment with `relaxation.py`'s relaxation order.
- FR-5: `_relax_field` in `relaxation.py` must be implemented as a lookup into a dict of per-field handler functions (`_RELAXERS`), not an if/elif chain.
- FR-6: The `/search` endpoint must catch `RuntimeError` raised by `run_search` and respond with HTTP 502 and the error message in the response detail, rather than allowing an unhandled exception to produce a raw 500.
- FR-7: None of the above changes may alter the public return shape/types of `search_full_dataset`, `relax_and_search`, `filter_listings`, or the `/search` endpoint's success-path response schema.

## Non-Goals (Out of Scope)

- Changing the relaxation order itself (`_RELAXATION_ORDER` in `relaxation.py`) — only the *implementation style* of `_relax_field` is in scope, not the field ordering or relaxation strategy.
- Adding caching, connection pooling, or other DB-layer performance work beyond the query consolidation in US-001.
- Catching or handling exception types other than `RuntimeError` in the `/search` endpoint (e.g. network-level exceptions from the Anthropic/Strands client) — noted as a follow-up, not required here.
- Any change to `core/config.py`, `core/models.py`, `geo/distance.py`, `geo/locations.py`, `data/inventory.py`, `agents/agent.py`, `agents/guardrails.py`, `orchestrator.py`, `search/explanation.py`, or `scripts/` — the review found no issues in these files.
- Introducing a formal benchmarking/perf-testing framework; verification is via query-count assertions in the existing test suite, not wall-clock timing.
- Multi-worker deployment configuration changes (e.g. adding `uvicorn --workers`) — US-002 only fixes the race condition so the code is safe *if* that configuration is used, it doesn't change current deployment.

## Design Considerations

Not applicable — this is a backend-only change with no UI surface.

## Technical Considerations

- **US-001** relies on DuckDB supporting conditional aggregation (`SUM(CASE WHEN ... THEN 1 ELSE 0 END)`) within a single `SELECT`, which is standard SQL and already compatible with the existing query-building pattern in `dataset.py`.
- **US-001**'s query-count test will need a way to observe/count calls to the DuckDB connection's `execute()` — likely via a wrapper/spy around `con.execute` in the test, matching however `tests/test_dataset.py` currently sets up its test connection/fixtures. Check existing fixtures before adding a new one.
- **US-001**: field names are inlined directly into SQL as column aliases; this is safe only because they come from the fixed, hardcoded set of predicate dict keys, never from user input. Preserve this invariant explicitly (comment) since it's a security-relevant assumption, not just a style choice.
- **US-002** requires `import os` in `dataset.py`; confirm no naming collision with existing imports.
- **US-003**: before removing `FILTER_FIELDS`, grep the full repo (including `tests/`, `scripts/`, and `search/__init__.py`) to confirm it has zero consumers besides the re-export.
- **US-004**: the refactor must preserve the exact exception type and message raised for an unknown field, since `tests/test_relaxation.py` may assert on it directly.
- **US-005**: confirm what exception type(s) `run_search` / `require_api_key()` actually raise today (per the review, `RuntimeError` is the documented case) before writing the except clause — don't widen the catch beyond what's confirmed without discussion.
- All five stories touch files with existing dedicated test files (`test_dataset.py`, `test_search.py`, `test_relaxation.py`, `test_server.py`), so each acceptance criteria set requires running that file's existing suite plus any new test added, not the full suite in isolation (though a full `pytest` run before considering the work done is expected).

## Success Metrics

- `search_full_dataset` query count per call drops from up to 9 to exactly 2, verified by an automated test (not manual timing).
- Zero regressions: full existing test suite (`tests/test_dataset.py`, `tests/test_search.py`, `tests/test_relaxation.py`, `tests/test_server.py`, and any others) passes after all five stories are implemented.
- `/search` no longer returns an unhandled 500/traceback for the `RuntimeError` failure case, verified by a new test.
- Typecheck and lint pass with zero new warnings introduced by these changes.

## Open Questions

- Does `run_search` (or anything it calls, e.g. the Strands/Anthropic client) raise exception types other than `RuntimeError` on failure today? If so, should US-005 widen its except clause, or is that explicitly deferred to a follow-up?
- Is `FILTER_FIELDS` referenced by anything outside this repo (e.g. is `car_search` published/imported elsewhere), which would affect whether US-003 can safely remove it versus just fixing the comment?
- Is multi-worker deployment (the scenario motivating US-002) actually in use or planned, or is this purely a defensive fix for a currently-unexercised risk?
