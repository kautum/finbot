# Finbot Wiki — start here

**Audience: an LLM agent picking up this project cold.** Read this page, then the page you need.
Written 2026-08-24. Everything factual here was measured or read from the source, not recalled.

## What Finbot is

A multi-table AI financial analyst: a chat agent that reasons jointly across transaction-level
data, fraud labels, user/card data and World Bank financial-inclusion indicators, and produces
real analytical work — EDA, KPIs, segmentation, cohort analysis, statistical group comparison —
with inline charts and a visible reasoning trace.

The bar is **Databricks Genie / ThoughtSpot Spotter / Hex Magic / Julius AI**, not a
weekend text-to-SQL demo. It must survive being demoed to a boss or client.

## Read in this order

| Page | Read it when |
|---|---|
| **[01 — Current State](01-current-state.md)** | Always. What actually exists, verified against the working tree, plus four errors in the older planning docs. |
| **[02 — Data Dictionary](02-data-dictionary.md)** | Before writing any SQL or metric. Measured schema, row counts, data-quality traps, query benchmarks. |
| **[03 — Infrastructure Decision](03-infrastructure-decision.md)** | **Before touching the ETL or `.env`. This is the live blocker.** |
| **[04 — Competitive Research](04-competitive-research.md)** | When deciding what to build and what to skip. |
| **[05 — Agent Stack Research](05-research-agent-stack.md)** | Before touching CopilotKit, LangGraph, Groq or the stats tools. Version-sensitive. |
| **[06 — Memory & Knowledge Graph](06-memory-and-knowledge-graph.md)** | When memory or `build-kg` comes up. |
| **[07 — Roadmap](07-roadmap.md)** | To know what to do next and in what order. |
| [website-instructions.md](website-instructions.md) | Any frontend/visual design work. Pre-existing, account-wide, not Finbot-specific. |

## The five things that matter most

1. **The dataset is 220 MB, not 1.3 GB.** As Parquet+zstd the whole thing is 219.9 MB; a single
   `.duckdb` file is 329 MB. Analyst queries over all 22.5M rows run in **3–130 ms**. Both
   previous hosting failures came from forcing a columnar dataset into a row-store, where it
   inflates to 2–4 GB. **The data was never too big — the storage engine was wrong.**

2. **Nothing currently connects to a database with data in it.** `agent/.env` points at the
   capacity-blocked Neon project. The CockroachDB cluster is quota-disabled. This is the blocker.

3. **Fraud is 0.1495%** — 13,332 cases in 8,914,963 labeled rows. And **33% of transactions have
   no fraud label at all**. Any fraud metric computed over all transactions is wrong by ~33%.
   This single fact drives the semantic layer, the sampling verdict, and the stats guardrails.

4. **The agent is under-built, not wrong.** 65 lines: one ReAct loop, no system prompt, no plan,
   no trace, no semantic layer, no read-only enforcement. Julius AI proves single-agent chat is
   a viable shape. Deepen it, don't replace it.

5. **The highest-leverage work is the YAML metric registry plus the reasoning-trace panel,
   shipped together** — roughly two days for the largest share of demo credibility. The trace
   becomes convincing exactly when it can say *"used the governed definition of `fraud_rate`."*

## Hard constraints — do not violate

- **Zero billing.** No credit card at any provider. Not "free tier with a card on file." Firm
  until the product is proven. Never propose "just enable billing" as a first-choice fix.
- **Confirm the database decision with the owner before touching `load_to_neon.py` or `.env`.**
  Two provider switches already caused significant rework.
- **Never expose `card_number` or `cvv`.** Synthetic, but they look exactly like real PANs/CVVs.
- **Read-only must be enforced at the database driver, not in the prompt.**

## Real findings already measured (use these in the demo)

- **Online transactions are 28× more fraud-prone than swipe**: 0.8409% vs 0.0295% (chip 0.0992%).
- **Highest-fraud MCCs**: Passenger Railways 2.004%, Gardening Supplies 1.282% — ~10× baseline.
- **Credit score barely predicts fraud victimhood**: 0.155% / 0.146% / 0.143% across bands. A
  genuinely interesting negative result, because it contradicts the obvious hypothesis.

## Conventions

- Numbered pages, `NN-topic.md`, cross-linked relatively.
- Every quantitative claim is measured or sourced. Unverified things are labelled unverified.
- When this wiki and an older planning doc disagree, **the wiki wins** —
  `PROGRESS.md`, `finbot-project-plan.md` and `finbot-project-plan-v2.md` are superseded and
  retained only as history.
