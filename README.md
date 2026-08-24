# Finbot

A conversational AI financial analyst over 22.5 million rows of transaction, fraud, cardholder
and macroeconomic data. It writes its own SQL, chains multiple queries to answer open-ended
questions, checks whether the differences it finds are statistically significant, and shows
every query and metric definition it used to get there.

**Status: in development.** The agent and data layer work; the frontend is scaffolded but not
yet wired. See [`wiki/07-roadmap.md`](wiki/07-roadmap.md) for what is built and what is next.

## Why it exists

Traditional BI answers questions someone modelled in advance. Finbot is aimed at the gap that
leaves — the exploratory *"why"* questions nobody built a dashboard for — with three properties
most conversational-BI tools don't have:

- **A governed semantic layer**, so the same question returns the same number every time.
  The industry name for the failure this prevents is *metric drift*.
- **Statistical honesty.** It reports p-values and confidence intervals, and refuses to answer
  when a segment has too little data to support a conclusion.
- **A visible reasoning trace.** Every answer shows the queries run and the definitions used.

Full argument, including where it deliberately does *not* compete:
[`wiki/08-positioning.md`](wiki/08-positioning.md).

## The data

| Table | Rows |
|---|---:|
| `transactions` | 13,305,915 |
| `fraud_labels` | 8,914,963 |
| `databank` (World Bank indicators, long format) | 302,008 |
| `findex_2025` (Global Findex) | 8,577 |
| `cards` | 6,146 |
| `users` | 2,000 |
| `mcc_codes` | 109 |

10 years of US credit-card activity (2010–2019) plus World Bank financial-inclusion indicators
for 174 countries. 1.3 GB raw; 220 MB as Parquet. Full schema, data-quality traps and query
benchmarks: [`wiki/02-data-dictionary.md`](wiki/02-data-dictionary.md).

Some findings already measured from it:

- **Online transactions are 28× more fraud-prone than swipe** — 0.8409% vs 0.0295%.
- **Credit score barely predicts fraud victimhood** — 0.155% / 0.146% / 0.143% across bands.
- Fraud is rare: **0.1495%**, which is exactly why naive segment analysis misleads.

## Stack

| Layer | Choice |
|---|---|
| Agent | LangGraph (Python 3.12, `uv`) |
| LLM | Groq |
| Query engine | DuckDB *(pending — see below)* |
| Web search | Tavily |
| Frontend | Next.js 16 + React 19 + CopilotKit |

## Repository

```
agent/      LangGraph agent, tools, FastAPI AG-UI server
frontend/   Next.js + CopilotKit chat UI
wiki/       Project documentation - START HERE
Datasets/   raw data (gitignored)
```

## Documentation

**[`wiki/00-INDEX.md`](wiki/00-INDEX.md) is the entry point** and is written to be read by both
humans and coding agents. It covers verified current state, the data dictionary, infrastructure
decisions and their history, competitive research, and the build roadmap.

> One open decision blocks the next phase: where the database is hosted. The analysis and
> recommendation are in [`wiki/03-infrastructure-decision.md`](wiki/03-infrastructure-decision.md).

`PROGRESS.md` and the two `finbot-project-plan*.md` files are superseded and kept only as history.
