# 12 — Sources

The other pages condense research; this page holds the links so claims stay re-checkable.
Gathered 2026-08-23/24. **Anything time-sensitive — free-tier limits, pricing, API shapes —
should be re-verified before being relied on**, since all of it changed at least once during
this project's short life.

## Verified in-browser (highest confidence)

Read live in Chrome during this session, not fetched summaries:

- CopilotKit — Generative UI overview, the six primitives:
  https://docs.copilotkit.ai/concepts/generative-ui-overview
- CopilotKit — **Tool Rendering** (`useRenderTool`, `useDefaultRenderTool`); the code in
  [05](05-research-agent-stack.md) §1 is adapted from this page:
  https://docs.copilotkit.ai/generative-ui/tool-rendering
- CopilotKit — State Rendering: https://docs.copilotkit.ai/generative-ui/state-rendering
- CopilotKit — Headless Threads (source of the Enterprise-Intelligence constraint in
  [11](11-ui-plan.md) §3.1): https://docs.copilotkit.ai/headless-threads
- CopilotKit — LangChain/LangGraph integration tracks: https://docs.copilotkit.ai/langgraph-fastapi
  (also `/langgraph-python`, `/langgraph-typescript`)
- Hugging Face Spaces overview — the "Docker/Gradio Spaces require a paid plan" finding:
  https://huggingface.co/docs/hub/spaces-overview

## GitHub, via the API

Star counts, licences and push dates in [09](09-open-source-landscape.md) §1 were read from
`gh api repos/<owner>/<name>` on 2026-08-24.

- WrenAI https://github.com/Canner/WrenAI · docs https://docs.getwren.ai/oss/concepts/what_is_mdl
- Vanna https://github.com/vanna-ai/vanna
- DB-GPT https://github.com/eosphoros-ai/DB-GPT
- pandas-ai https://github.com/sinaptik-ai/pandas-ai
- Cube https://github.com/cube-js/cube · Malloy https://github.com/malloydata/malloy
- Spider 2.0 https://github.com/xlang-ai/Spider2 · TAG-Bench https://github.com/TAG-Research/TAG-Bench
- MindsDB https://github.com/mindsdb/mindsdb (redirects to `mindsdb/mindshub`)
- CopilotKit https://github.com/CopilotKit/CopilotKit
- build-kg https://github.com/agtm1199/build-kg — read via the GitHub API; see [06](06-memory-and-knowledge-graph.md) §1

Comparison teardown of the three live NL2SQL projects:
https://sudiptapathak.com/blog/dissecting-open-source-nl2sql/

## Infrastructure and quotas

Re-verify all of these before acting.

- Neon plans / free-tier limits: https://neon.com/docs/introduction/plans ·
  https://neon.com/faqs/free-plan-limits-and-quotas
- CockroachDB Serverless Request Units: https://www.cockroachlabs.com/docs/cockroachcloud/plan-your-cluster-serverless
- MotherDuck pricing & Duckling sizes (the Pulse per-query metering fact):
  https://motherduck.com/docs/about-motherduck/billing/pricing/ ·
  https://motherduck.com/docs/about-motherduck/billing/duckling-sizes/ ·
  Fees Addendum (free-account suspension terms) https://motherduck.com/fees-addendum/
- Render free tier: https://render.com/docs/free
- Vercel function duration (300 s Hobby cap): https://vercel.com/docs/functions/configuring-functions/duration ·
  Python runtime https://vercel.com/docs/functions/runtimes/python ·
  Services (beta) https://vercel.com/changelog/run-multiple-frameworks-in-one-project-with-vercel-services
- Turso pricing: https://turso.tech/pricing
- BigQuery Sandbox: https://docs.cloud.google.com/bigquery/docs/sandbox
- Hugging Face storage limits: https://huggingface.co/docs/hub/storage-limits
- Cloudflare R2 card requirement: https://community.cloudflare.com/t/why-using-r2-free-tier-involves-giving-card-info/945179
- Groq rate limits: https://console.groq.com/docs/rate-limits · deprecations https://console.groq.com/docs/deprecations

## DuckDB

- Hugging Face / `hf://` support in httpfs: https://duckdb.org/docs/current/core_extensions/httpfs/hugging_face
- Parquet metadata & row-group pruning: https://duckdb.org/docs/lts/data/parquet/metadata
- Information schema: https://duckdb.org/docs/current/sql/meta/information_schema ·
  listing tables https://duckdb.org/docs/lts/guides/meta/list_tables
- Date format functions (`strftime`/`strptime`): https://duckdb.org/docs/lts/sql/functions/dateformat
- Node Neo client: https://duckdb.org/docs/current/clients/node_neo/overview
- No statement timeout — open discussion: https://github.com/duckdb/duckdb/discussions/10550 ·
  `interrupt()` reliability https://github.com/duckdb/duckdb/issues/15925
- **MotherDuck's own LangChain SQL agent tutorial** — closest published analogue to Finbot's
  design, and the source of the "tell the model it's DuckDB" warning:
  https://motherduck.com/blog/langchain-sql-agent-duckdb-motherduck/
- DuckDB-NSQL (evidence that general LLMs are Postgres-biased):
  https://motherduck.com/blog/duckdb-text2sql-llm/

## LangGraph / LangChain

- Persistence, checkpointers, Store API: https://docs.langchain.com/oss/python/langgraph/persistence
- SQL agent example: https://docs.langchain.com/oss/python/langgraph/sql-agent
- Structured output: https://docs.langchain.com/oss/python/langchain/structured-output
- LangMem: https://www.langchain.com/blog/langmem-sdk-launch
- LangChain on multi-agent: https://www.langchain.com/blog/how-and-when-to-build-multi-agent-systems

## Competitive products

- Databricks Genie Agent Mode: https://docs.databricks.com/aws/en/genie/agent-mode ·
  https://www.databricks.com/blog/introducing-genie-agent-mode
- Genie Ontology: https://www.databricks.com/blog/introducing-genie-one-genie-ontology-and-genie-agents
- **Metric View YAML reference** (the format [04](04-competitive-research.md) §1 recommends
  copying): https://docs.databricks.com/aws/en/uc-semantics/metric-views/yaml-reference
- ThoughtSpot Spotter Semantics: https://www.thoughtspot.com/blog/spotter-semantics
- **Hex Magic architecture** — the ZenML case study, the most candid engineering account of the
  four: https://www.zenml.io/llmops-database/building-production-data-agents-with-long-running-context-and-iterative-workflows
- Julius AI teardown: https://medium.com/@trelvek/julius-ai-technical-teardown-2026-where-an-ai-data-analyst-fits-in-the-stack-4ec728d1fac9

## Semantic layer / metric drift

- Text-to-SQL metric drift in enterprise: https://atlan.com/know/ai-agent/data-for-ai/text-to-sql-for-enterprise/
- Why text-to-SQL fails (Omni): https://omni.co/blog/why-text-to-sql-fails
- Semantic layer for AI agents (Cube): https://cube.dev/articles/semantic-layer-for-ai-agents-2026
- Building trust in conversational BI (AtScale): https://www.atscale.com/blog/build-trust-conversational-bi-semantic-layer/
- WrenAI on the semantic layer: https://www.getwren.ai/post/why-the-semantic-layer-is-essential-for-reliable-text-to-sql-and-how-wren-ai-brings-it-to-life

## Agent design

- Anthropic — writing effective tools for agents: https://www.anthropic.com/engineering/writing-tools-for-agents
- Anthropic — multi-agent research system: https://www.anthropic.com/engineering/built-multi-agent-research-system
- Cognition — "Don't Build Multi-Agents" / what's working: https://cognition.com/blog/multi-agents-working
- Single vs multi-agent: https://www.philschmid.de/single-vs-multi-agents

## Frontend / design

- Vercel Web Interface Guidelines (raw): https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md
- Design systems corpus (73 companies): https://github.com/voltagent/awesome-design-md
- Motion: https://motion.dev/
- Further links and extracted tokens: [`website-instructions.md`](website-instructions.md)

## Data

- Global Findex 2025 (World Bank): https://www.worldbank.org/en/publication/globalfindex

## Claims deliberately left unverified

Listed so nobody mistakes them for established fact:

- LangGraph's support for CopilotKit **state rendering** — inferred, not confirmed on the
  framework grid ([05](05-research-agent-stack.md) §1).
- LangGraph.js ↔ Python **parity** — third-party trackers only, no official matrix.
- LangMem p95 memory-search latency (~60 s) — single secondary source.
- Graphiti's Kuzu backend status — one issue calls it deprecated.
- mem0's Groq provider support — not directly confirmed.
- Mistral and Together AI current free-tier numbers — not checked.
- Exact CopilotKit v1→v2 migration diff, and which version v2 shipped in.
- Whether `@copilotkit/react-ui/styles.css` exposes CSS variables ([11](11-ui-plan.md) §8).
- Whether a 329 MB DuckDB file performs acceptably in Render's 512 MB / 0.1 CPU free tier —
  **the single most important untested assumption in the plan**
  ([03](03-infrastructure-decision.md) §8).
