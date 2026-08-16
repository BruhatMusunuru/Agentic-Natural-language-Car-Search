# Agentic Flow

Diagrams: [`agentic-flow.mmd`](./agentic-flow.mmd) (Mermaid) and [`agentic-flow.drawio`](./agentic-flow.drawio) (diagrams.net XML) — same flow, two formats. Matches `src/car_search/orchestrator.py::run_search` exactly.

**Amber nodes** call the LLM (the Anthropic/Bedrock model, via a Strands Agent). There are exactly two: filter extraction (`extract_filters`) and the clarify sub-agent (`ask_clarifying_question`).

**Blue nodes** are deterministic — plain Python or SQL, no model call, same output every time for the same input. This is everything else: the guardrail fallbacks, contradiction detection, the clarify-trigger check, `search_full_dataset` (DuckDB), the zero-result relaxation loop, ranking, and explanation generation.

The clarify path is a short-circuit: when triggered, the flow returns a `clarifying_question` directly and never reaches `search_full_dataset` — no search happens on a query too vague to act on.

`contradiction_note` (from `detect_contradiction`) is computed early but only consumed later, by `build_explanation` — shown as a dashed edge rather than a step in the main path.
