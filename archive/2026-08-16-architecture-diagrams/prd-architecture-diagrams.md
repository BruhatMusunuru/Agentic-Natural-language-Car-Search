# PRD: Architecture Diagrams (Agentic Flow & AWS Production Deployment)

## 1. Introduction/Overview

The car-search service (see `tasks/prd-natural-language-car-search.md`) currently runs entirely locally: a FastAPI app, a Strands agent calling the Anthropic API directly, and DuckDB querying parquet files on local disk. Two things are missing before this can be discussed with stakeholders or handed to an infra team: (1) a clear picture of how a request actually flows through the agent/tool/data layers today, and (2) a concrete target architecture for running this in AWS production, built around Amazon Bedrock AgentCore (which is designed to host Strands agents) and fronted by API Gateway.

This PRD scopes the creation of exactly two diagrams:

1. **Agentic flow diagram** — how a `/search` request moves through extraction, guardrails, deterministic search/relaxation, ranking, and explanation in the *current* system. Delivered in both Mermaid and draw.io/diagrams.net XML.
2. **AWS production deployment diagram** — the target AWS architecture (API Gateway → Bedrock AgentCore Runtime + Gateway → Lambda → S3, with Bedrock as the model provider). Delivered in draw.io/diagrams.net XML using the official AWS icon shape library, built to be imported into Miro.

This is a **documentation-only** deliverable. No infrastructure is provisioned and no application code changes as part of this PRD.

## 2. Goals

- Produce an accurate, reviewable diagram of the current agentic request flow, distinguishing LLM-backed steps from deterministic (non-LLM) steps.
- Produce a high-level target AWS production architecture diagram centered on Bedrock AgentCore (Runtime + Gateway), API Gateway, Lambda, and S3.
- Make the AWS diagram directly importable into Miro with recognizable, official AWS service icons (not generic boxes).
- Keep both diagrams small enough to review in one sitting and update as the system evolves.

## 3. User Stories

### US-001: Agentic flow diagram (Mermaid)
**Description:** As an engineer, I want a Mermaid diagram of the current agentic request flow so I can read/review it directly in the repo's markdown docs without opening another tool.

**Acceptance Criteria:**
- [ ] File saved at `docs/diagrams/agentic-flow.mmd`, valid Mermaid syntax (flowchart or sequence diagram — implementer's choice, whichever reads more clearly for this flow)
- [ ] Diagram includes every step in the real flow: client request → `POST /search` → filter extraction (Strands agent, structured output) → guardrail fallbacks (synonym/price-shorthand normalization, contradiction detection) → clarify-trigger check → clarify sub-agent (when triggered, short-circuits before search) → `search_listings`/`search_full_dataset` (DuckDB over `data/*.parquet`) → zero-result auto-relaxation loop → deterministic ranking/cap → explanation generation → response
- [ ] The two LLM-calling steps (filter extraction, clarify sub-agent) are visually distinguished (e.g. color/style) from the deterministic Python/SQL steps (guardrails, relaxation, ranking, explanation, `search_listings`)
- [ ] The clarify short-circuit path (skips search entirely) is visually distinct from the main search path
- [ ] Renders correctly when previewed (e.g. via an Artifact or any standard Mermaid renderer) — no syntax errors
- [ ] A short caption/legend (2-4 sentences, inline as a markdown file alongside the diagram or a comment block) explains what the color/style distinction means

### US-002: Agentic flow diagram (draw.io/diagrams.net XML)
**Description:** As an engineer, I want the same agentic flow available as an editable draw.io diagram so it can be dropped into other tools (Confluence, Miro, slides) without redrawing it.

**Acceptance Criteria:**
- [ ] File saved at `docs/diagrams/agentic-flow.drawio`, valid diagrams.net XML that opens without errors in the draw.io desktop app, VS Code draw.io extension, or app.diagrams.net
- [ ] Same set of steps, same LLM-vs-deterministic visual distinction, and same clarify short-circuit path as US-001 — this is the same diagram in a second format, not a different diagram
- [ ] Manually verified: file opens cleanly in app.diagrams.net (or equivalent) with no broken/overlapping shapes

### US-003: AWS production deployment diagram (draw.io XML, AWS icons, Miro-ready)
**Description:** As an engineer, I want a high-level AWS production architecture diagram using official AWS icons so I can import it into Miro and discuss the deployment plan with the team.

**Acceptance Criteria:**
- [ ] File saved at `docs/diagrams/aws-production-deployment.drawio`, valid diagrams.net XML using shapes from the built-in AWS icon library (AWS19/AWS21-style shapes shipped with draw.io — e.g. the "AWS / AWS19" or newer shape set), not generic rectangles
- [ ] Diagram includes, at minimum, these components as distinct AWS-icon nodes: Client, Amazon API Gateway, Amazon Bedrock AgentCore Runtime, Amazon Bedrock AgentCore Gateway, AWS Lambda (hosting the `search_listings` tool), Amazon S3 (holding `data/*.parquet`), Amazon Bedrock (foundation model), Amazon CloudWatch (logs/metrics)
- [ ] Arrows show the real request path: Client → API Gateway → AgentCore Runtime → Bedrock (model calls for extraction/clarify) and AgentCore Runtime → AgentCore Gateway → Lambda → S3 (tool call path), with the response flowing back the same way; all components shown emitting logs/metrics to CloudWatch
- [ ] High-level only: no VPC/subnet/security-group/IAM-role-level detail, no CI/CD pipeline — just the services and the data flow between them (see Non-Goals)
- [ ] A short legend/caption block (on-canvas text or an accompanying `docs/diagrams/aws-production-deployment.md`) briefly explains each component's role in one line
- [ ] Manually verified: (a) file opens cleanly in app.diagrams.net with correct AWS icons rendered (not placeholder/missing-icon boxes), and (b) exported/imported into Miro at least once to confirm shapes and labels survive the import intact

## 4. Functional Requirements

- FR-1: The agentic flow diagram (both formats) must depict every step listed in US-001's acceptance criteria, in the correct order, matching the real implementation in `src/car_search/orchestrator.py`, `agent.py`, `guardrails.py`, `relaxation.py`, `search.py`/`dataset.py`, and `explanation.py`.
- FR-2: The agentic flow diagram must visually distinguish LLM-backed steps (calls to the Anthropic/Bedrock model) from deterministic steps (plain Python/SQL, no model call).
- FR-3: The agentic flow diagram must show the clarify short-circuit: when triggered, the flow returns a `clarifying_question` and never reaches `search_listings`.
- FR-4: The AWS production diagram must use official AWS service icons (draw.io's built-in AWS shape library), not generic shapes, for every AWS service node.
- FR-5: The AWS production diagram must show Amazon Bedrock AgentCore split into its two relevant primitives — Runtime (hosts the agent) and Gateway (exposes the `search_listings` tool, backed by Lambda) — as separate nodes, not a single merged "AgentCore" box.
- FR-6: The AWS production diagram must show Amazon S3 as the storage location for the parquet dataset (replacing the local `data/` folder used in local development).
- FR-7: The AWS production diagram must show Amazon Bedrock as the model provider invoked by AgentCore Runtime (replacing the direct Anthropic API key call used in local development).
- FR-8: The AWS production diagram must be saved as diagrams.net XML so it can be imported into Miro via Miro's native draw.io import, preserving AWS icons and labels.
- FR-9: Every diagram file must be accompanied by a one-line-per-component legend explaining what each node does (inline on-canvas or in a companion markdown file).

## 5. Non-Goals (Out of Scope)

- No actual AWS resources are provisioned; no Terraform/CDK/CloudFormation is written.
- No VPC, subnet, security group, or IAM policy detail in the AWS diagram (high-level only, per the chosen detail level).
- No CI/CD pipeline diagram.
- No multi-region, disaster-recovery, or auto-scaling design.
- No architecture decision record (ADR) explaining *why* AgentCore was chosen over alternatives (Lambda-only, ECS Fargate, etc.) — that was explicitly descoped in favor of diagrams-only.
- No changes to the running application code, `prd.json`, or the existing local-dev architecture.
- The exact mechanism by which API Gateway invokes AgentCore Runtime (direct HTTP integration vs. a thin Lambda adapter) is left as a single labeled arrow/note in the diagram, not fully specified — see Open Questions.

## 6. Design Considerations

- Keep both diagrams to roughly 8-12 nodes each. If the agentic flow needs more than that to stay accurate, prefer a Mermaid **sequence diagram** (participants + messages) over a flowchart — it tends to stay readable at higher step counts for this kind of request/response flow.
- Use consistent left-to-right or top-to-bottom flow direction within each diagram; don't mix.
- For the AWS diagram, group icons loosely by concern (entry point, agent layer, tool/data layer, model, observability) using visual proximity or a light background color per group — draw.io's AWS shape library includes "group" container shapes for this.
- Reuse the same component names/labels across both the flow diagram and the AWS diagram wherever they refer to the same logical piece (e.g. "search_listings tool") so a reader can mentally connect the two.

## 7. Technical Considerations

- **Tooling**: draw.io / diagrams.net (desktop app, VS Code extension, or app.diagrams.net) ships an official AWS icon shape library out of the box — use that rather than sourcing icons separately. Mermaid diagrams can be authored directly as text and previewed via any standard Mermaid renderer (e.g. an Artifact, GitHub's native Mermaid rendering, or the Mermaid Live Editor).
- **Miro import**: Miro's board import supports `.drawio`/diagrams.net XML files directly (Import → Files → select `.drawio`); verify AWS icons and text labels survive the import before considering US-003 done.
- **File location**: new `docs/diagrams/` directory at the repo root (does not exist yet — create it as part of this work). Keep source files (`.mmd`, `.drawio`) checked into git so diagrams are versioned like code.
- **AgentCore pairing with Strands**: the current app already uses the Strands Agents SDK (`src/car_search/agent.py`); Bedrock AgentCore Runtime is designed to host Strands agents directly, which is why it's the natural production target — call this out briefly in the AWS diagram's legend so the connection to the existing codebase is obvious to a reader.

## 8. Success Metrics

- Both diagram formats for the agentic flow render without errors in their respective tools (Mermaid renderer / draw.io).
- The AWS diagram imports into Miro with all AWS icons and labels intact, verified manually at least once.
- A team member unfamiliar with the codebase can look at the agentic flow diagram and correctly state which two steps call an LLM.
- A team member unfamiliar with the codebase can look at the AWS diagram and correctly describe the request path from client to response in one sentence.

## 9. Open Questions

- Exact API Gateway → AgentCore Runtime integration mechanism (direct HTTP integration vs. a thin Lambda adapter for request shaping/auth) — left as a single labeled arrow for now; needs a real decision before any implementation PRD is written.
- Whether Secrets Manager is needed at all in production: moving model calls to Bedrock (via AgentCore, using IAM role-based auth) likely eliminates the need for a manually managed `ANTHROPIC_API_KEY` secret entirely — worth confirming and reflected in the diagram's legend rather than adding a Secrets Manager node speculatively.
- Whether the daily parquet export process (how files land in S3) is in scope for a future diagram — explicitly not covered here.
- Whether authentication/authorization at API Gateway (API keys, Cognito, IAM) matters enough to note even at high level — currently omitted per the "high-level" detail choice.
