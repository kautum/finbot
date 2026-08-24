> **SUPERSEDED (2026-08-24) — retained as history only.**
> Contains four verified factual errors (the CockroachDB migration state, the `databank_wide`
> row count, and others) catalogued in [`wiki/01-current-state.md`](wiki/01-current-state.md) §6.
> Current source of truth: [`wiki/00-INDEX.md`](wiki/00-INDEX.md).

# Finbot — Project Plan & Roadmap (v2)

_Updated 23 Aug 2026 to reflect the database migration from Neon to CockroachDB and the completed data load. Supersedes `finbot-project-plan.md`._

## 1. What Finbot Is

Finbot is a general-purpose, conversational fintech data-analyst agent. Point it at structured data (via SQL) and, eventually, unstructured documents (via a knowledge graph), and it autonomously explores schemas, runs queries, looks up real-world context on the web, generates visualizations, and produces analyst-grade write-ups — all inside a chat interface. Positioned as a complement to traditional BI tools (Tableau/Power BI/Looker), not a replacement: BI answers predefined questions from governed dashboards; finbot investigates open-ended questions live, at a fraction of setup time and cost. Target use case: pitching a fintech AI agent to a client in the Middle East.

## 2. Database: CockroachDB Serverless (Corrected From Neon)

**Why we moved off Neon:** Neon's free tier is 512MB (not 3GB as originally, incorrectly, stated) — nowhere near enough for the ~1.3GB raw / ~2-4GB-in-Postgres dataset. The `fraud_labels` table alone (8.9M narrow rows, ~24-28 bytes of fixed row overhead each) exceeded the limit before the big transactions table was even attempted.

**Why CockroachDB:** 10GB free tier, Postgres wire-compatible (same `psycopg2`/SQLAlchemy code), no credit card required, cloud-hosted and Vercel-reachable from day one (no local-dev/production mismatch). Confirmed working after two setup fixes:
- SSL: connection string needs `&sslrootcert=system` appended (uses the OS's trusted CA store instead of a missing local cert file).
- SQLAlchemy dialect: needed the `sqlalchemy-cockroachdb` package installed and the connection string scheme changed from `postgresql://` to `cockroachdb://`, because CockroachDB's version string (`CockroachDB CCL v26.2.5...`) doesn't match SQLAlchemy's default Postgres version parser.

**Rejected alternatives and why:**
- Local Postgres (Docker) — rejected because Vercel serverless functions cannot reach a laptop's `localhost`; would only work for local dev, not production, and the user wanted to skip local dev entirely.
- Oracle Cloud "Always Free" self-hosted VM — technically has 200GB free storage, but rejected due to a well-documented pattern of surprise account suspension/deletion with no recovery path (multiple independent Reddit reports spanning 2022-2026), plus the operational burden of self-managing security, patching, and backups — reintroducing the complexity that motivated leaving GCP in the first place.
- Supabase — same 500MB free-tier problem as Neon.

**Data footprint (confirmed via `du -sh`):** 1.3GB raw across all files (`transactions_data.csv` at 1.2GB dominates). Estimated 2-4GB once loaded into Postgres/CockroachDB with standard row/index overhead — comfortably inside CockroachDB's 10GB free tier.

## 3. Data Loaded — Status: Complete

All 7 tables successfully loaded into CockroachDB:

| Table | Rows | Source |
|---|---|---|
| `users` | 2,000 | `users_data.csv` |
| `cards` | 6,146 | `cards_data.csv` |
| `mcc_codes` | 109 | `mcc_codes.json` |
| `fraud_labels` | 8,914,963 | `train_fraud_labels.json` |
| `findex_2025` | 8,577 | `GlobalFindexDatabase2025.csv` |
| `databank_wide` | 787,092 | `Databank-wide.xlsx` (reshaped wide→long to fit Postgres's 8KB row-size limit) |
| `transactions` | 13,305,915 | `transactions_data.csv` |

**Key technical lesson learned:** `Databank-wide.xlsx` originally had 1,232 columns and could not be loaded as-is — Postgres/CockroachDB caps a single row at ~8KB regardless of column count or nullability. Fixed by reshaping to tidy/long format (`pd.melt()`), turning ~8,500 wide rows into ~787K narrow rows. This is both a technical fix and the more correct way to model many time-series indicators.

Load script: `agent/load_to_neon.py` (name is now slightly misleading post-migration, but left as-is to avoid churn — functionally loads into whatever `DATABASE_URL` points to).

## 4. Agent Architecture — Status: In Progress

### Core stack (built)
- LLM: Groq (`openai/gpt-oss-120b`) via `ChatGroq`.
- Orchestration: LangGraph (`StateGraph`, `MessagesState`, `ToolNode`, `tools_condition`, `MemorySaver`).
- Tools confirmed working: `ping_tool` (placeholder, ready to retire), `TavilySearch` (confirmed with a real grounded MCC-code lookup).

### Tools not yet added (next task)
- `run_sql` — executes queries against CockroachDB, returns results with a row-limit safety cap. Code drafted, not yet added to `agent.py`.

### Planned but not started
- `dashboard_agent` — second LangGraph node for Plotly chart generation, following the Planner→Coder→Critic pattern from research (see v1 plan for full citations).
- LangSmith tracing for observability and demo credibility.
- Guardrails (input filtering, audit logging, risk-tiered tool permissions) before any client-facing demo.

## 5. Frontend — Status: Scaffolded, Not Wired Up

A CopilotKit/Next.js scaffold already exists in `frontend/` (confirmed via git — `next.config.ts`, `eslint.config.mjs`, `AGENTS.md`, etc. are committed). Not yet connected to the LangGraph backend. Next step when we get here: wrap the compiled `graph` object with `LangGraphAGUIAgent` behind a FastAPI endpoint, per CopilotKit's LangGraph integration docs.

## 6. Knowledge Graph (`build-kg`) — Status: Roadmap Item, Not Started

Confirmed the repo ([github.com/agtm1199/build-kg](https://github.com/agtm1199/build-kg)) ships a `financial-aml.yaml` domain schema, genuinely relevant to fintech AML use cases. Blocked because it extracts entities from unstructured documents, and current datasets are all structured. Needs either synthetic AML case narratives/KYC documents to test against, or should stay a "coming next" pitch slide rather than a built feature for now.

## 7. Credentials Currently Held

Stored in `agent/.env` (gitignored, confirmed never committed):

| Variable | Service | Purpose |
|---|---|---|
| `GROQ_API_KEY` | Groq | LLM inference |
| `DATABASE_URL` | CockroachDB Serverless | Database connection (scheme: `cockroachdb://`, requires `sslrootcert=system`) |
| `TAVILY_API_KEY` | Tavily | Web search tool |

Needed later: LangSmith API key (observability), possibly a graph database if `build-kg` gets built out.

## 8. Immediate Next Steps, In Order

1. Add the `run_sql` tool to `agent.py`; update the tools list to `[run_sql, web_search_tool]`, retiring `ping_tool`.
2. Test a combined query exercising both tools in one turn (e.g., MCC lookup + aggregate spend by category).
3. Add LangSmith tracing.
4. Build the `dashboard_agent` node (Plotly-based).
5. Wire the existing `frontend/` CopilotKit scaffold to the LangGraph backend.
6. Revisit `build-kg` — decide whether to source synthetic AML documents or keep as roadmap-only.
7. Add guardrails (input filtering, audit logging) before any client-facing demo.
8. Before an actual client demo: migrate `DATABASE_URL` from CockroachDB free tier to a paid production instance (CockroachDB paid tier or reconsider Neon paid tier) for guaranteed uptime/performance under demo conditions.

## 9. All Reference Links

- CockroachDB Serverless: [cockroachlabs.com/get-started-cockroachdb](https://www.cockroachlabs.com/get-started-cockroachdb/)
- Tavily: [tavily.com](https://tavily.com)
- CopilotKit docs: [docs.copilotkit.ai/langgraph-python](https://docs.copilotkit.ai/langgraph-python)
- build-kg repo: [github.com/agtm1199/build-kg](https://github.com/agtm1199/build-kg)
- LangSmith: [langchain.com/langsmith-platform](https://www.langchain.com/langsmith-platform)
- Global Findex Database 2025: [worldbank.org/en/publication/globalfindex](https://www.worldbank.org/en/publication/globalfindex)
