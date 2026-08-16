# PRD: Sample Output in README

## 1. Introduction/Overview

The README's "Running the API locally" section currently shows how to *call*
the `/search` endpoint (a `curl` one-liner) but never shows what comes back.
A reader has to actually run the server and fire the request themselves to
see the shape of a real response. This PRD adds a genuine, live-captured
sample request/response pair to the README so the response shape (filters,
results, explanation, relaxed_fields, clarifying_question) is visible at a
glance, without requiring setup.

The example query doubles as an update to the existing curl example: it
switches the location from Chicago to Detroit (`"reliable family SUV under
$30k, low mileage, near Detroit"`), and the sample response shown is the
actual JSON returned by a live local run of that exact query — not
hand-written or fabricated.

## 2. Goals

- Show a real `curl` request/response pair in the README for the query
  `"reliable family SUV under $30k, low mileage, near Detroit"`.
- Capture the response from an actual live run against the full local
  dataset (not fabricated), so field names/shapes/values are trustworthy.
- Replace the existing Chicago-location example in "Running the API
  locally" with this Detroit one, keeping one example in that section
  (no duplication).
- Keep the README's existing structure and tone intact everywhere else.

## 3. User Stories

### US-001: Capture a real sample response
**Description:** As a developer maintaining the README, I want a genuine
JSON response captured from a live run of the target query, so the
documented example reflects real system behavior.

**Acceptance Criteria:**
- [ ] Local API server started successfully (`uv run car-search`)
- [ ] `curl -s -X POST http://127.0.0.1:8000/search -H "Content-Type:
      application/json" -d '{"query": "reliable family SUV under $30k, low
      mileage, near Detroit"}'` executed against it
- [ ] Raw JSON response captured and pretty-printed
- [ ] Response contains actual matching listings (not an empty
      `clarifying_question` fallback) — confirms the query is specific
      enough to search meaningfully

### US-002: Update README with the request + sample response
**Description:** As a new reader of the README, I want to see a full
example request and its response together, so I understand what the API
returns without running it myself.

**Acceptance Criteria:**
- [ ] "Running the API locally" section's existing Chicago curl example
      query text is replaced with the Detroit query
- [ ] The captured, pretty-printed JSON response is added directly below
      the curl command, in a fenced ```json code block
- [ ] Response block is the full, untruncated output (all fields, all
      returned results) as captured in US-001
- [ ] README renders correctly as Markdown (fenced code blocks properly
      closed, no broken formatting)
- [ ] No other README sections changed

## 4. Functional Requirements

- FR-1: The README's "Running the API locally" section's curl example must
  use the query `"reliable family SUV under $30k, low mileage, near
  Detroit"`.
- FR-2: Directly beneath that curl command, the README must include a
  fenced `json` code block containing the real response returned by a live
  local run of that exact request.
- FR-3: The sample response must be shown in full — every top-level field
  (`filters`, `results`, `explanation`, `relaxed_fields`,
  `clarifying_question`) and every result listing, with no truncation.
- FR-4: No other part of the README (Setup, tests/typecheck/lint, golden-set
  eval, Architecture) is modified.

## 5. Non-Goals (Out of Scope)

- No changes to application code, API behavior, or data.
- No additional example queries beyond the one Detroit query.
- No changes to `docs/layout.md` or `docs/data.md`.
- No CI step to keep the sample output in sync automatically — it's a
  point-in-time capture and may drift from live data over time (acceptable
  since it's illustrative, not a contract test).

## 6. Technical Considerations

- Requires `ANTHROPIC_API_KEY` to be set (already present in the repo's
  `.env`) since `/search` calls the live extraction agent.
- Server must be run locally (`uv run car-search`) against the full
  `data/*.parquet` inventory already present in the repo.

## 7. Success Metrics

- A reader can see the full request/response shape by reading the README
  alone, with zero setup.

## 8. Open Questions

- None.
