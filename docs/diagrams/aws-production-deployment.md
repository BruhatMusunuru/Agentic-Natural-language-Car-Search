# AWS Production Deployment

Diagram: [`aws-production-deployment.drawio`](./aws-production-deployment.drawio) — diagrams.net XML using the official AWS icon shape library. Import into Miro via **Import → Files → select the `.drawio` file**.

High-level only: no VPC/subnet/security-group/IAM-role detail, no CI/CD pipeline. This is the request/data flow, not a build-ready infra spec (see the PRD's Open Questions for what's still undecided).

| Component | Role |
|---|---|
| Client | Whatever calls the API (browser, CLI, another service) |
| Amazon API Gateway | Public HTTPS entry point for `POST /search` |
| Amazon Bedrock AgentCore — Runtime | Hosts the Strands agent (extraction + clarify sub-agent) |
| Amazon Bedrock AgentCore — Gateway | Exposes `search_listings` as a managed tool, backed by Lambda |
| AWS Lambda | Runs the `search_listings` tool (the same DuckDB query engine as local dev) |
| Amazon S3 | Stores the daily parquet exports (`data/*.parquet`), replacing local disk |
| Amazon Bedrock | Foundation model (Claude) invoked by AgentCore Runtime for extraction/clarify |
| Amazon CloudWatch | Logs and metrics for every service in the account |

**Request path:** Client → API Gateway → AgentCore Runtime → (Bedrock, for model calls) and → AgentCore Gateway → Lambda → S3 (for the tool call). Responses flow back along the same arrows. Every service in the account emits logs/metrics to CloudWatch (drawn as one grouped dashed edge from the account boundary, not one line per service, to keep the diagram readable).

**Note on AgentCore icons:** draw.io's bundled AWS icon library currently ships a single "Bedrock AgentCore" icon (no separate Runtime/Gateway icons yet), so both nodes reuse that icon and are distinguished by label text and a dashed "AWS Production Account" boundary grouping them with the rest of the account's services.

**Note on secrets:** unlike local development (which reads `ANTHROPIC_API_KEY` from the environment/`.env`), this design has no Secrets Manager node — moving model calls to Bedrock via AgentCore uses IAM role-based auth instead of a manually managed API key. See the PRD's Open Questions; this should be confirmed before implementation.
