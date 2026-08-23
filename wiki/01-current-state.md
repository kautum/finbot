# 01 — Current State (verified 2026-08-23)

Everything here was read from the working tree or executed, not inferred from prior planning docs.
Where a planning doc disagrees with this file, **this file wins** — see §6.

## 1. Repository layout

```
finbot/
├── agent/                      Python 3.12 backend, uv-managed
│   ├── agent.py                LangGraph graph + tools          [MODIFIED, uncommitted]
│   ├── server.py               FastAPI + AG-UI endpoint, port 8123
│   ├── load_to_neon.py         ETL: 7 tables -> DATABASE_URL
│   ├── inspect_data.py         one-off dataset shape probe
│   ├── test_groq.py            Groq connectivity smoke test
│   ├── test_neon.py            DB connectivity smoke test (SELECT version())
│   ├── main.py                 uv scaffold stub, unused
│   ├── pyproject.toml          dependency manifest
│   ├── .env                    4 secrets, gitignored          [NOT committed - verified]
│   └── .agents/skills/         neon + neon-postgres skills    [gitignored]
├── frontend/                   Next.js 16.3.2 + React 19.2.8 + CopilotKit 1.69
│   ├── app/layout.tsx          <CopilotKit runtimeUrl="/api/copilotkit" agent="finbot_agent">
│   ├── app/page.tsx            <CopilotChat> only
│   ├── app/api/copilotkit/route.ts   CopilotRuntime -> LangGraphHttpAgent(AGENT_URL)
│   └── AGENTS.md               auto-generated Next.js agent rules (do not delete)
├── Datasets/                   1.3 GB raw                     [gitignored]
├── wiki/                       this wiki
├── PROGRESS.md                 STALE - describes a pandas/CSV design that was abandoned
├── finbot-project-plan.md      v1 plan, superseded
└── finbot-project-plan-v2.md   v2 plan, partially stale       [untracked]
```

## 2. The agent (`agent/agent.py`, 65 lines)

A textbook single-loop ReAct graph. Nothing more.

```
START -> agent -> (tools_condition) -> tools -> agent -> ... -> END
```

- **LLM**: `ChatGroq`, model from `GROQ_MODEL` env, default `openai/gpt-oss-120b`.
- **State**: `MessagesState` — message list only. No plan, no trace, no scratchpad.
- **Checkpointer**: `MemorySaver` — **in-process only, wiped on every restart.**
- **Tools** (2):
  - `run_sql(query: str)` — opens a SQLAlchemy connection, `fetchmany(200)`, returns
    `str({"columns": [...], "rows": [...]})`. Catches all exceptions and returns the error
    text so the model can self-correct. Table list is hardcoded in the docstring.
  - `TavilySearch(max_results=3)`.

### What the graph does NOT have
No system prompt at all. No planning step. No reflection or verification node. No semantic
layer. No schema introspection tool. No row/time limits beyond `fetchmany(200)`. No read-only
enforcement — `run_sql` will happily execute `DROP TABLE` if the model emits it and the DB
credential permits it. No structured output. No reasoning trace. No retry bound.

## 3. The server (`agent/server.py`, 20 lines)

`FastAPI` + `LangGraphAGUIAgent(name="finbot_agent", graph=graph)` mounted at `/` via
`add_langgraph_fastapi_endpoint`, uvicorn on `0.0.0.0:8123`. Agent name `finbot_agent`
matches the frontend's `agent="finbot_agent"` — that wiring is correct.

## 4. The frontend

Scaffold only, and **never once run against the backend**. `page.tsx` renders a bare
`<CopilotChat>`. There are no chart components, no `useRenderTool` / `useCopilotAction`
registrations, no Recharts (not even installed — `package.json` has no charting dependency).
`route.ts` proxies to `AGENT_URL || http://localhost:8123`.

## 5. Credentials in `agent/.env`

| Var | Provider | State |
|---|---|---|
| `GROQ_API_KEY` | Groq | live |
| `GROQ_MODEL` | — | `openai/gpt-oss-120b` |
| `DATABASE_URL` | **Neon** (`postgresql://…ep-sparkling-glade-zaj1q59s-pooler.c-2.eu-west-2.aws.neon.tech`) | points at the capacity-blocked Neon project |
| `TAVILY_API_KEY` | Tavily | live |

`.gitignore` covers `.env` — confirmed never committed.

## 6. Where the planning docs are WRONG

Four corrections, all verified by execution:

1. **`.env` points at Neon, not CockroachDB.** `finbot-project-plan-v2.md` §2 and §7 state the
   project migrated to CockroachDB and that `DATABASE_URL` uses the `cockroachdb://` scheme.
   The actual value is a `postgresql://` Neon pooler URL. The CockroachDB connection string is
   not present anywhere in the working tree. Either the migration was reverted or the URL was
   overwritten. **Nothing in the repo can currently reach a database with data in it.**

2. **`databank_wide` is 302,008 rows, not 787,092.** The source sheet is 642 rows x 1,232
   columns. Melting it yields 642 x 1,226 = 787,092 cells, but **485,084 of those are empty** —
   the 787K figure counted nulls as rows. Real non-null long-format rows: **302,008**.
   `load_to_neon.py:74` also casts every value to `str`, destroying numeric types.

3. **`PROGRESS.md` is entirely stale.** It describes a pandas-over-local-CSV design with a
   Kaggle credit-card dataset, a `data/` directory, and a 6-stage plan. None of that is the
   current architecture. It should be deleted or clearly marked superseded.

4. **Row counts in plan-v2 §3 are otherwise accurate** — transactions 13,305,915 and
   fraud_labels 8,914,963 both confirmed exactly. Credit where due.

## 7. Git state

- Branch `main` @ `b76c909`, clean except:
  - `agent/agent.py` — **modified, uncommitted**: the `ping_tool` -> `run_sql` swap. This is
    real working code and should be committed.
  - `finbot-project-plan-v2.md` — untracked.
  - `wiki/` — untracked.
- 12 commits total. Remote `origin/main` exists and is in sync.

## 8. Version drift found in the manifest

| Pin | Reality |
|---|---|
| `ag-ui-langgraph<0.0.43` | latest **is** 0.0.43 — the pin excludes the newest release |
| `llama-3.3-70b-versatile` (default in `test_groq.py`) | **deprecated on Groq ~2026-06-17** |
| `copilotkit>=0.1.95` | current, but a `0.2.0a0` prerelease exists — breaking bump inbound |
| `pandas>=3.0.5` | pandas 3.x changed default string dtype + copy-on-write semantics |
| `langgraph>=1.2.11` | current |
| `@copilotkit/*@^1.69.0` | current; but a **v2 React API** now exists — see [05](05-research-agent-stack.md) |
