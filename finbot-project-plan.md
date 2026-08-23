# Finbot — Project Plan & Roadmap

_Compiled from our full planning conversation, plus additional research on ways to strengthen the build. Last updated: 23 Aug 2026._

## 1. What Finbot Is

Finbot is a general-purpose, conversational **fintech data-analyst agent**. Point it at structured data (Postgres tables) and, increasingly, unstructured documents (via a knowledge graph), and it can autonomously explore schemas, run SQL, look up real-world context on the web, generate visualizations, and produce analyst-grade write-ups — all inside a chat interface, without a human pre-modeling the data first.

**Positioning against traditional BI (Tableau/Power BI/Looker):** BI tools are a "system of record" — governed, pixel-perfect dashboards that answer predefined questions an analyst modeled in advance. Finbot is a "system of action" — it investigates open-ended questions ("why did fraud spike?") and reasons live, at a fraction of the setup time and cost. It doesn't replace BI; it fills the gap BI leaves for exploratory, conversational analysis. For AML/fraud specifically, it can also answer relationship questions ("who is connected to whom") that row-and-column BI tools handle poorly.

**Target use case:** pitching a fintech AI agent/product to a client in the Middle East.

---

## 2. Current Data Sources

| Dataset | File(s) | What it is | Scale |
|---|---|---|---|
| Transactions | `transactions_data.csv` | Synthetic US credit-card transactions (IBM/Kaggle-style dataset): id, date, client_id, card_id, amount, merchant, MCC, errors | 13,305,916 rows |
| Cards | `cards_data.csv` | One row per card: brand, type, credit limit, expiry, dark-web flag | Small |
| Users | `users_data.csv` | One row per person: age, income, debt, credit score, location | Small |
| MCC codes | `mcc_codes.json` | Lookup: numeric merchant category code → readable category | Small |
| Fraud labels | `train_fraud_labels.json` | Fraud flag per transaction ID | 159 MB |
| Global Findex 2025 | `GlobalFindexDatabase2025.csv` | Real World Bank survey — financial inclusion indicators across 141 countries, ~145,000 interviews in 2024 | 8,577 rows |
| Databank (wide) | `Databank-wide.xlsx` | Historical/wide-format companion to Findex, one row per country-year, 1,232 columns of `fin*` indicators across editions (2011–2021) | ~8,500 rows sample |

**How they relate:** the five transaction files join into one micro-level picture (person → card(s) → transactions → fraud flag → merchant category). The two Findex files are macro-level (national survey stats) and don't share a join key with the transaction data — they sit alongside it as a second analytical thread (individual spending/fraud behavior vs. global financial-inclusion trends).

**Neon Postgres table plan (7 tables):** `transactions`, `cards`, `users`, `mcc_codes`, `fraud_labels`, `findex_2025`, `databank_wide`.

---

## 3. Infrastructure Decisions Made

### Moved off Google Cloud / BigQuery
Abandoned due to CLI auth complexity (`gcloud` setup, application-default credentials). Fully uninstalled:
```bash
brew uninstall --cask gcloud-cli
rm -rf ~/.config/gcloud
uv remove google-cloud-bigquery pandas-gbq
```

### Switched to Neon (Postgres)
- Sign up: [neon.com](https://neon.com) — GitHub/Google login, no card required.
- Free tier: 3GB storage, plain Postgres, connection string only (no CLI needed).
- Python packages: `sqlalchemy`, `psycopg2-binary`.
- Credential stored in `.env` as `DATABASE_URL`.
- Connection verified working (`PostgreSQL 18.6` confirmed via test script).

### Data loading
`load_to_neon.py` written to load all 7 tables — chunked loading (`chunksize=50,000`) for the 13.3M-row transactions file, straightforward `to_sql()` for small tables, custom JSON parsing for `mcc_codes.json` and `train_fraud_labels.json`.

**Status: not yet run.** Next step is to verify `train_fraud_labels.json`'s structure and test the small tables before committing to the full transactions load.

---

## 4. Agent Architecture

### Core stack
- **LLM:** Groq (`openai/gpt-oss-120b` via `ChatGroq`), key in `.env` as `GROQ_API_KEY`.
- **Orchestration:** LangGraph (`StateGraph`, `MessagesState`, `ToolNode`, `tools_condition`, `MemorySaver` checkpointer).
- **Tools wired so far:**
  - `ping_tool` — placeholder, confirmed tool-calling works, to be retired.
  - `TavilySearch` (`langchain-tavily`) — web search, confirmed working (tested with an MCC-code lookup, returned grounded, sourced answer).
- **Tools planned:**
  - `run_sql` — executes queries against Neon Postgres so the agent can query the loaded tables directly.
  - `dashboard_agent` — a second LangGraph node that profiles a table, decides on metrics/chart types, and generates Plotly/Matplotlib visualizations, assembled into a report ("the wiki").

### Web search
- Provider: **Tavily** ([tavily.com](https://tavily.com)) — chosen because it's the native LangChain/LangGraph integration, has a genuine free tier (1,000 searches/month, no card), and returns clean LLM-ready snippets instead of raw HTML.
- Key stored in `.env` as `TAVILY_API_KEY`.
- Package: `langchain-tavily`.

### Multi-agent BI / dashboard layer
Research-backed pattern for the dashboard agent (Planner → Coder → Critic):
1. **Data-to-Insight stage** — profile dataset, detect domain, extract structured insights.
2. **Insight-to-Dashboard stage** — decide chart types/layout, generate and assemble visualizations.
- Reference: [Data-to-Dashboard multi-agent LLM framework paper](https://arxiv.org/abs/2505.23695) — benchmarked against a human Kaggle analyst on a finance dataset; scored +113% on insight depth and +77% on novelty.
- Reference: [Lightweight controllable framework, Planner/Coder/Critic pattern](https://arxiv.org/html/2601.06126v1).
- Decision: build this ourselves (Plotly + a second LangGraph node) rather than integrating an external BI tool's API (e.g. Metabase), to keep the system self-contained and demonstrably original IP. Roadmap item: "can also push to Metabase/Power BI" as a future integration, not built now.

### Frontend: CopilotKit
- [copilotkit.ai](https://www.copilotkit.ai/) — turns a LangGraph agent into a full in-app copilot via the **AG-UI protocol**, rather than a bare chat window.
- Python SDK (`LangGraphAGUIAgent`) wraps the existing compiled `graph` object — no rewrite of `agent.py` needed, just a FastAPI endpoint wrapper.
- **Generative UI** is the key feature: the agent can render live, structured components (tables, cards, charts) directly in the conversation instead of returning plain text — this is what will actually display the dashboard agent's charts.
- `useCoAgent` hook syncs agent state to the frontend live, so a client can watch reasoning/partial results appear in real time.
- Starter template: `npx copilotkit@latest create` (pairs Next.js frontend + Python LangGraph backend).
- Docs: [LangGraph integration](https://docs.copilotkit.ai/langgraph-python), [Generative UI](https://docs.copilotkit.ai/agent-spec/generative-ui), [Quickstart](https://docs.copilotkit.ai/langgraph-python/quickstart).
- **Sequencing note:** build this after the SQL/web-search reasoning loop is solid — polishing a UI on top of unreliable reasoning risks a demo that looks good but answers badly.

### Knowledge graph layer: `build-kg`
- Repo: [github.com/agtm1199/build-kg](https://github.com/agtm1199/build-kg)
- Pipeline: `crawl.py` → `chunk.py` → `parse.py`/`parse_batch.py` (LLM entity/relationship extraction per domain schema) → `id_extractors.py` (entity resolution) → `setup_graph.py` (loads into a graph store) → `verify.py` (validates extraction quality).
- **Confirmed relevant:** ships a pre-built `financial-aml.yaml` domain schema (alongside `default`, `data-privacy`, `food-safety`) — purpose-built for anti-money-laundering entity/relationship extraction.
- **What it would add:** the ability to answer relationship questions BI tools and SQL handle poorly — "show every account connected to this flagged merchant within two hops (shared addresses, shared cards, shared devices)."
- **Blocker:** it extracts entities from unstructured text/documents. Current datasets are already structured (CSVs) — there's nothing for it to crawl/parse yet. Needs either synthetic AML case narratives/KYC documents, or treat as a "roadmap slide" feature rather than build now.

---

## 5. Credentials / APIs Currently Held

All stored in `agent/.env` (never share raw values in chat):

| Variable | Service | Purpose |
|---|---|---|
| `GROQ_API_KEY` | Groq | LLM inference (`openai/gpt-oss-120b`) |
| `DATABASE_URL` | Neon | Postgres connection string |
| `TAVILY_API_KEY` | Tavily | Web search tool |

Not yet obtained (needed for later phases):
- CopilotKit — no separate API key needed for open-source self-hosted use; check their docs if using their hosted Cloud tier.
- LangSmith — needed for observability/evals (see Section 6).
- Any graph database (e.g. Neo4j) if pursuing `build-kg`.

---

## 6. Additional Research: Ways to Strengthen Finbot

These weren't part of the original conversation — added after further research on what separates a demo agent from a genuinely production-credible one, which matters for a client pitch.

### Observability & evaluation — LangSmith
Since the stack is already LangChain/LangGraph, [LangSmith](https://www.langchain.com/langsmith-platform) is the natural fit and requires minimal instrumentation to add.
- **Tracing:** records every LLM call, tool invocation, and reasoning step as a nested trace tree — critical for debugging why the agent chose a bad SQL query or missed a tool call.
- **Evaluation:** run LLM-as-judge, code-based, or multi-turn evaluators against real traces; useful for regression-testing the agent before a client demo ("did this prompt change break anything?").
- **Cost/latency monitoring:** track token cost and latency per run — directly relevant if the client asks "what would this cost to run at scale?"
- Free tier: Developer plan is $0/seat/month.
- Docs: [LangSmith Observability](https://docs.langchain.com/oss/python/langchain/observability), [Agent Observability guide](https://www.langchain.com/resources/agent-observability).
- **Why it matters for the pitch:** being able to show a client a trace of the agent's reasoning (which tools it called, why) is a strong trust-building demo moment — it makes the "black box" transparent.

### Guardrails & security for fintech AI agents
Given the eventual AML/fraud use case, security guardrails aren't optional polish — they're often literally what a regulated client will ask about first.
- **Three-layer framework** (from [Salvador Cloud](https://salvador.cloud/insights/ai-security-guardrails-for-fintech/)):
  1. Data layer — provenance, classification, retention, DLP.
  2. Model layer — risk register, red-team cadence, bias/eval pipelines.
  3. Prompt layer — injection defense, output filtering, audit logging.
- **Practical minimum for a demo-stage build:** an input filter (allow-list of permitted intents), a "behavior cage" (agent can't call privileged/write tools without secondary confirmation — you're already doing this pattern with `confirm_action`-style flows), an output guard (PII/regulatory-content filtering), and an audit log of every agent decision.
- **Risk tiering** (from [tkxel's guardrail framework](https://tkxel.com/blog/agentic-ai-guardrails-framework/)): classify each capability by "blast radius" — e.g., "read transaction data" is low-risk, "flag an account for investigation" or "export data" would need stricter guardrails.
- Prompt injection is officially OWASP LLM Top 10 category LLM01 — worth explicitly testing for if this ever touches real client data.

### Other improvements worth considering (not yet scoped in detail)
- **Semantic layer / metric definitions:** define canonical business metrics (e.g., "fraud rate," "average transaction value") once, so the SQL agent doesn't recompute inconsistent definitions across different questions.
- **Caching layer:** for repeated or similar queries (e.g., common aggregate stats), cache results to reduce Groq API calls and Neon query load — relevant once the transactions table is loaded.
- **Vector search / RAG:** if `build-kg`'s document layer gets built out, pairing it with a vector store (e.g., pgvector directly inside Neon — no new infra needed) would let the agent do semantic search over case notes alongside graph traversal.
- **Rate limiting / cost caps:** important before a live client demo — an open-ended agent with SQL + web search + LLM calls can rack up unexpected cost or hang on a bad query against 13M rows without safeguards.

---

## 7. Suggested Build Order (Small Steps)

1. Verify `train_fraud_labels.json` structure, run `load_to_neon.py` on small tables first, then the full transactions load.
2. Retire `ping_tool`; add `run_sql` tool for querying Neon directly.
3. Test a combined query exercising both `run_sql` and `TavilySearch` in one turn.
4. Add LangSmith tracing (low effort, high payoff for debugging and demo credibility).
5. Build the `dashboard_agent` node (Plotly charts + report assembly).
6. Wrap the graph with CopilotKit for a real frontend.
7. Decide on `build-kg`: either source/generate unstructured AML documents to feed it, or keep as a roadmap slide.
8. Layer in guardrails (input filtering, audit logging) before any client-facing demo with real or realistic data.

---

## 8. All Reference Links

- Neon: [neon.com](https://neon.com)
- Tavily: [tavily.com](https://tavily.com)
- CopilotKit docs: [docs.copilotkit.ai/langgraph-python](https://docs.copilotkit.ai/langgraph-python) | [Generative UI](https://docs.copilotkit.ai/agent-spec/generative-ui) | [Quickstart](https://docs.copilotkit.ai/langgraph-python/quickstart) | [Agents concept](https://docs.copilotkit.ai/concepts/agents)
- build-kg repo: [github.com/agtm1199/build-kg](https://github.com/agtm1199/build-kg)
- LangSmith: [langchain.com/langsmith-platform](https://www.langchain.com/langsmith-platform) | [Observability docs](https://docs.langchain.com/oss/python/langchain/observability) | [Agent Observability guide](https://www.langchain.com/resources/agent-observability)
- Data-to-Dashboard multi-agent paper: [arxiv.org/abs/2505.23695](https://arxiv.org/abs/2505.23695)
- Planner/Coder/Critic dashboard framework paper: [arxiv.org/html/2601.06126v1](https://arxiv.org/html/2601.06126v1)
- AI security guardrails for fintech: [salvador.cloud/insights/ai-security-guardrails-for-fintech](https://salvador.cloud/insights/ai-security-guardrails-for-fintech/)
- Agentic AI guardrails framework: [tkxel.com/blog/agentic-ai-guardrails-framework](https://tkxel.com/blog/agentic-ai-guardrails-framework/)
- Global Findex Database 2025 (World Bank): [worldbank.org/en/publication/globalfindex](https://www.worldbank.org/en/publication/globalfindex)
- Agentic BI vs traditional BI comparison: [gooddata.ai/blog/ai-agents-vs-traditional-bi-comparison](https://www.gooddata.ai/blog/ai-agents-vs-traditional-bi-comparison/)
