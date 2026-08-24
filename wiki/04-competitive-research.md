# 04 — Competitive Research: Genie, Spotter, Hex Magic, Julius

Researched 2026-08-23. Purpose: extract **specific adoptable mechanisms**, and separate them
from enterprise theatre a solo builder should not attempt.

## 1. Databricks Genie

**Architecture.** A compound multi-agent system, not one LLM call: intent parsing (metric,
filter, time range, aggregation) -> planner that decomposes multi-part questions into an
ordered plan -> retriever that grounds against tables/columns/dashboards/prior queries ->
SQL generation. **Agent Mode** wraps this in an outer loop that "creates research plans, runs
multiple queries, learns and iterates, delivers a report with citations", and scales reasoning
depth to question complexity.

**Semantic layer — the copyable part.** Databricks' answer is the **Metric View**: a YAML file
registered in Unity Catalog. Real shape:

```yaml
version: "1.1"
source: catalog.schema.table
joins:
  - name: customer
    source: catalog.schema.customer_table
    on: "source.key = customer.key"
    cardinality: "many_to_one"
fields:
  - name: order_date
    expr: "date_col"
    display_name: "Order Date"
    synonyms: ["order dt", "purchase date"]
measures:
  - name: total_revenue
    expr: "SUM(amount)"
    display_name: "Total Revenue"
    synonyms: ["revenue", "sales"]
    format: { unit: "currency" }
```

Up to 10 synonyms per field. **There is no compiler magic here — it is a hand-written YAML
registry.** That is the whole trick, and it is directly reproducible.

**Genie Ontology** (DAIS 2026) sits above it: an auto-built knowledge graph over tables,
queries, dashboards and pipelines, weighted by a PageRank-like authority score. How the LLM
consumes it is *not publicly documented*.

**Reasoning traces — the standout feature.** Genie renders **"Thinking steps"**: plain-language
explanations of the SQL logic behind the query, explicitly to build non-technical trust.
Answers can be marked "Trusted". Also exposed via API (`GenieQueryAttachments`). This is a
UI/UX pattern, not research — fully copyable.

No public BIRD/Spider accuracy numbers for Genie.

## 2. ThoughtSpot Spotter

**The interesting architectural bet: it does NOT let the LLM write SQL.** Stated thesis — LLMs
are good at *translation*, bad at *generation*. Pipeline: NL question -> **search tokens** from a
taxonomy derived from the data -> a **patented deterministic engine** compiles tokens to SQL.
This eliminates a whole class of text-to-SQL error by never asking for raw SQL. Spotter 3 also
decomposes multi-part questions and reviews results before answering.

Semantic layer is **TML** (ThoughtSpot Modeling Language), YAML-based, version-controllable
("Analytics-as-Code"). Full measure syntax was not retrievable publicly.

Whether Spotter shows reasoning traces: **not publicly documented.** No independent benchmarks.
Their "deterministic, not probabilistic" claim is architectural, not benchmarked.

**Verdict: do not attempt to reproduce.** The compiler is the patent and a multi-year systems
bet. Text-to-SQL with validation is the correct alternative, not an inferior stand-in.

## 3. Hex Magic — best-documented of the four

Four agents split by **user persona**, not technical function:
- **Notebook Agent** — technical users, 20+ min sessions, writes persistent cells.
- **Threads Agent** — non-technical, conversational, hides code. **Explicitly prioritises
  governed/semantically-modelled data, falling back to raw tables only when none exists.**
  That is a concrete, adoptable policy: *prefer the metric registry; fall back to raw scan.*
- **Semantic Model Agent** — generates/edits the YAML semantic model itself.
- **Context Agent** — background synthesis of "what does this org mean by X".

Orchestrated on **Temporal** for multi-hour resumable workflows. Hex calls this migration
"tremendously difficult" — explicitly enterprise infrastructure.

**Most reusable insight — context management.** Static context (tool defs, system prompt,
progressive-disclosure guides) vs dynamic (retrieved per query). They built *tool search*
because tool definitions alone hit ~100K tokens. Their own words: the context-harvesting
pipeline was **"more valuable than the basic agent loop architecture."**

**Ephemeral SQL tool** — agents run scratch queries that never appear in the final output,
validating before committing to an answer. Documented failure: with frontier models, agents
sometimes run **50 ephemeral queries "just to be certain"** — over-verification becomes a
latency/cost problem.

**Candid documented failure modes** (unusually honest for a vendor):
- Contradictory semantic definitions send the agent into "collapse mode" — 30 minutes of
  second-guessing. *Implication: an inconsistent metric registry is worse than none.*
- User-level memory contradicting team context broke the precedence hierarchy; they now keep
  the two separate rather than merged.
- A "reference registry" built to stop hallucination under weaker models is now "unnecessary
  baggage". **Lesson: scaffolding built to compensate for today's model limits becomes
  tomorrow's constraint.** A direct argument against over-engineering guardrails now.

**Ambiguity**: Threads does not silently guess — "shows different possible approaches, and
might even ask you for your feedback on which direction to take."

## 4. Julius AI — closest in shape to Finbot

Single agentic loop, no multi-agent split. Interpret intent -> pull learned context (prior
queries, discovered table relationships, **and specifically remembered failed queries and why
they failed**) -> generate Python/R -> execute in an isolated sandbox container -> observe ->
regenerate on error -> repeat. A "Learning Sub-Agent" persists schema knowledge per workspace.
Most requests under 5 seconds.

**No formal semantic layer** — it bets on *learned* metadata instead of authored definitions.
A meaningfully different wager from the other three.

Documented failure modes: **hallucinated summary statistics on sparse data** (under ~30–50 rows,
heavy missing values, or when the question doesn't map cleanly to columns); inconsistent
results across repeated runs; unreliable on regression/time-series/ML. Its "31% better than
GPT-4 on math" claim is vendor-stated and unverified.

**Why this matters for Finbot: Julius proves a single-agent chat design is not inherently
limited.** It just needs strong reasoning underneath. Finbot's current architecture is not
wrong — it is under-built.

## 5. Text-to-SQL accuracy — what the 2025–26 literature says actually works

**Benchmark reality check.** BIRD execution accuracy for strong systems ≈ 73%. Spider 2.0
(enterprise-realistic, ~800 cols/schema) is brutal: agentic systems ≈ **21.3%**; GPT-4 alone
scores **6.0%** on Spider 2.0-Lite vs 86.6% on Spider 1.0. Finbot's schema is small and
single-database — a BIRD-like target is realistic, Spider-2.0-style claims are not.

Techniques that measurably help:
1. **Schema linking by retrieval** — retrieve relevant tables/columns by embedding similarity
   instead of dumping the whole schema. (Marginal for Finbot's 7 tables, but cheap.)
2. **Few-shot selection by SQL *structure* similarity**, not question-text similarity.
   Masked-question kNN also effective.
3. **Execution-guided self-correction with a hard retry cap.** Critical nuance: **early-accept**
   — if a query runs and returns ≥1 row, accept it immediately. Asking the model to
   "double-check" a working query reintroduces a documented failure where a correct query gets
   "fixed" into a wrong one. On retry exhaustion, return the best partial result, don't hard-fail.
4. **Server-side LIMIT injection and DDL/DML rejection** — engineering hygiene, not research.

## 6. Semantic layer: build vs adopt

| Option | Verdict |
|---|---|
| dbt Semantic Layer / MetricFlow | Overkill — requires modelling the warehouse in dbt first |
| Cube (cube.dev) | Overkill — a caching/serving layer for problems Finbot doesn't have |
| Malloy | Risky — a real language, and **LLMs generate it poorly** (thin training data) |
| Boring Semantic Layer (Ibis-based) | Genuinely fits if a dependency is wanted |
| **Hand-written YAML registry** | **Correct answer.** ~150–300 lines. No dependency. Directly injectable into the prompt. This is what all four vendors reduce to once the enterprise serving layer is stripped away. |

## 7. Synthesis — ranked by (demo credibility) / (effort)

**Build these:**
1. **Visible "thinking steps" trace panel** — highest ratio. Cheap, visually distinctive,
   what both Databricks and Hex ship as a headline feature.
2. **YAML metric registry** — lets you say the exact sentence all four vendors say:
   *"one definition of fraud rate, not five."*
3. **Bounded self-correct + early-accept** — improves real accuracy, ~50–100 lines.
4. **Ambiguity -> clarify, don't guess** (Hex Threads pattern) — a day.
5. **Schema linking by retrieval** — cheap, real, but invisible in a demo.
6. **SQL safety guardrails** — mandatory, not a differentiator.

**Skip these (enterprise theatre):**
- Genie Ontology's self-learning knowledge graph. Fake the *outcome* with a curated glossary.
- ThoughtSpot's deterministic token compiler. Multi-year patent work.
- Hex's Temporal 4-agent orchestration. 30-person-team problem.
- Materialised-view acceleration / adaptive routing. Irrelevant at 130 ms query times.
- Cube / dbt infrastructure.

**The single highest-leverage first move: the YAML metric registry and the reasoning-trace
panel, shipped together.** They compound — the trace becomes far more convincing when it can
say *"Step 2: used the governed definition of `fraud_rate` from the metric registry, not raw
column math."* That one on-screen sentence is the exact trust move Databricks sells as
"Trusted" answers and ThoughtSpot builds its whole deck around. Roughly two days of work.
