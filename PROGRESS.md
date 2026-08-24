> **SUPERSEDED (2026-08-24) — retained as history only.**
> This file describes an abandoned pandas-over-local-CSV design. The current source of truth is
> [`wiki/00-INDEX.md`](wiki/00-INDEX.md); the specific errors here are catalogued in
> [`wiki/01-current-state.md`](wiki/01-current-state.md) §6.3.

# FinBot — Project Wiki & Progress Log

A local-first data-science chatbot for the fintech domain, built with CopilotKit (generative UI in chat), a LangGraph agent, and Groq for LLM inference.

## Final Decisions (locked in)

| Decision | Choice | Why |
|---|---|---|
| LLM provider | **Groq API** (`llama-3.3-70b-versatile`) | Cloud inference, 300-1500+ tok/s, free tier (30 RPM / 14,400 req/day) — much faster than local Mac inference for multi-step tool-calling |
| Local LLM (Ollama) | **Rejected** | Considered `qwen3.5:4b` via a local Ollama binary, but local inference speed + tool-calling reliability of small models was a bigger risk/slowdown than Groq's free cloud tier. Not pursuing. |
| "Hermes" | **N/A** | Turned out to not be a downloaded local model — just a cached cloud-model catalog list from another tool. No action needed. |
| Agent framework | LangGraph + LangChain (`langchain-groq`) | Orchestrates tool calls: pandas queries, chart-data formatting |
| UI framework | CopilotKit (`@copilotkit/react-core`, `@copilotkit/react-ui`) + Next.js | Generative UI: `useCopilotAction` renders real React/Recharts components inline in the chat, not just text |
| Backend↔Frontend bridge | FastAPI + `copilotkit` + `ag-ui-langgraph` packages (AG-UI protocol) | Confirmed via CopilotKit's official LangGraph-Python quickstart and reference example |
| Charts | Recharts | Rendered via `useCopilotAction` |
| Dataset | Kaggle **Credit Card Fraud Detection** (start) → optionally swap to **PaySim** synthetic mobile-money dataset later | Fraud dataset is clean/numeric, ready to load immediately; PaySim has richer categorical/time-series data for later expansion |
| Data access | pandas, loaded from local CSV in `data/` | No external DB for this local test build |
| Python env/package manager | `uv` (not conda, not plain pip/venv) | CopilotKit's own docs standardize on `uv` for the agent project |
| Version control | Git, single monorepo (`agent/` + `frontend/` + `data/`) | Simpler for a small local test project than two repos |

## Environment Audit (Mac) — findings from investigation

- Tools confirmed installed and working: `uv 0.6.13`, `node v22.23.1`, `npm 10.9.8`, `git 2.50.1`, `python 3.13.5`.
- Conda envs on this machine (unrelated to FinBot, noted for reference): `base`, `DM`, `events`, `guardai`.
- An old Ollama binary was found at `~/Documents/Events/bin/ollama` (v0.32.14, not running, non-standard model path) — **not used for FinBot**. If we ever revisit local models, do a clean `brew install ollama` instead of reusing that path.
- `~/Projects/finbot` did not exist before this session — created fresh in Stage 0.

## Progress So Far

- [x] Decided architecture: Next.js + CopilotKit frontend ↔ FastAPI + LangGraph (Groq) backend via AG-UI
- [x] Verified real CopilotKit package names and integration pattern against official docs (corrected earlier wrong hook name: it's `useCopilotAction`, not `useComponent`)
- [x] Investigated and ruled out local Ollama path
- [x] **Stage 0 complete**: `~/Projects/finbot` created, git initialized, `agent/`, `frontend/`, `data/` folders created, `.gitignore` committed on `main` (commit `0878ed0`)
- [ ] Groq API key obtained and saved to `agent/.env`
- [ ] Stage 1: Python agent skeleton (`uv` project init, LangGraph + `langchain-groq`, basic chat working)
- [ ] Stage 2: AG-UI wiring (FastAPI + `add_langgraph_fastapi_endpoint`, confirm `localhost:8123`)
- [ ] Stage 3: Next.js frontend skeleton (CopilotKit provider + `/api/copilotkit` route + `CopilotChat`, end-to-end plain chat test)
- [ ] Stage 4: Dataset tool (pandas tool bound to fintech CSV)
- [ ] Stage 5: Generative UI charts (`useCopilotAction` + Recharts)
- [ ] Stage 6: Fintech-specific tools & polish, tag v1

## Next Immediate Step

1. Get a free Groq API key from console.groq.com (if not already done).
2. Start Stage 1: initialize the `agent/` folder as a `uv` Python project and install `langgraph`, `langchain-groq`, `copilotkit`, `ag-ui-langgraph`, `fastapi`, `uvicorn`, `pandas`, `python-dotenv`.

## Repo Structure (current)

```
finbot/
├── .gitignore
├── agent/       (empty — Stage 1 target)
├── frontend/    (empty — Stage 3 target)
└── data/        (empty — Stage 4 target: fraud dataset CSV goes here)
```
