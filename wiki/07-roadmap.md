# 07 — Build Roadmap

Sequenced. Each phase states a **verifiable exit condition** — not "it works", but a check that
fails loudly if the phase is broken. Phases are ordered so that nothing built later has to be
torn up by a decision made later.

**Guiding principle from the research**: Julius AI proves a single-agent chat design is not
inherently limited ([04](04-competitive-research.md) §4). Finbot's architecture is not wrong,
it is *under-built*. Almost everything below deepens the existing graph rather than replacing it.

---

## PHASE 0 — Unblock (BLOCKED ON OWNER)

**Nothing else can start.** The repo currently cannot reach a database with data in it.

| Step | Exit condition |
|---|---|
| 0.1 Owner picks Option A / B / C from [03](03-infrastructure-decision.md) §8 | A decision is written down |
| 0.2 **Memory probe**: deploy a bare FastAPI + DuckDB service on the chosen host, run the six benchmark queries, report timings and peak RSS | 329 MB file demonstrably works in 512 MB RAM — **or** a fallback is chosen before anything is built on it |
| 0.3 Commit the uncommitted `run_sql` change on `main` | `git status` clean |
| 0.4 Mark `PROGRESS.md` and plan v1/v2 superseded (done) | No doc contradicts [01](01-current-state.md) |

**0.2 is the highest-value hour in the plan.** It is the only untested assumption underneath
everything else ([03](03-infrastructure-decision.md) §8). Do it before Phase 1.

**Recommendation: Option A** — DuckDB/Parquet data layer, Python backend on Render, Next.js on
Vercel. No quota in the system can silently kill it.

---

## PHASE 1 — Data layer, rebuilt properly (~1 day)

Rewrite the ETL. The current `load_to_neon.py` carries four correctness bugs worth fixing while
it is being touched anyway.

1. **Set-based load, not row-by-row.** `COPY` / `CREATE TABLE AS SELECT` from Parquet. DuckDB is
   not tuned for `to_sql()` inserts.
2. **Fix the type bugs** ([02](02-data-dictionary.md) §2–4):
   - `amount` `"$-77.00"` → `DECIMAL(10,2)`
   - `is_fraud` `"Yes"/"No"` → `BOOLEAN`
   - `databank.value` → numeric (currently force-cast to `str`)
   - `zip` DOUBLE → INTEGER
   - **drop `card_number` and `cvv`** — synthetic, but they look exactly like real PANs/CVVs and
     must never reach a screenshot
3. **Sort `transactions` by `date`** before writing Parquet. Row-group min/max pruning degrades
   badly on unsorted data (every group's min/max spans the whole domain, so nothing is skipped),
   and date filters are the dominant analyst query shape. Row groups ~100K–1M rows; keep zstd.
   *Note: this mainly pays off on the Parquet-over-HTTP path. With a local `.duckdb` file
   (Option A) it is a minor win — do it anyway, it is free at write time.*
4. **Normalise `merchant_state`** or add a derived `merchant_country` column. It currently mixes
   US 2-letter codes with full country names and is 11.75% NULL
   ([02](02-data-dictionary.md) §2) — the most dangerous trap in the dataset, because it yields
   plausible wrong answers rather than errors.
5. **Source a findex/databank indicator dictionary** so `fin11a` is not opaque. Small, and
   nothing else in the plan owns it. Without it the macro tables are close to unusable by an
   agent.

**Exit condition**: a script that rebuilds the store from `Datasets/` reproducibly, plus an
assertion check that reproduces the [02](02-data-dictionary.md) numbers exactly —
13,305,915 / 8,914,963 / 13,332 fraud / 0 orphan joins. If any number drifts, the load is wrong.

---

## PHASE 2 — Make `run_sql` safe and dialect-correct (~half a day)

This is security work, not polish. The tool as written would execute `DROP TABLE`.

1. **Read-only at the driver**: `duckdb.connect(path, read_only=True)` or
   `ATTACH '...' (READ_ONLY)`. On MotherDuck, a role-scoped read-only token or a read-only share.
2. **`SELECT`/`WITH`-only string check** as defence in depth — never as the sole control.
3. **Server-side `LIMIT` injection** when the model omits one.
4. **Wall-clock timeout wrapper.** DuckDB has **no `statement_timeout`** and `con.interrupt()` is
   documented as unreliable. Use `ThreadPoolExecutor` + `future.result(timeout=N)`, recycle the
   connection if the interrupt doesn't land. Set `memory_limit` and `threads` at connect.
5. **Rewrite the docstring to say DuckDB**, naming the high-risk gotchas
   ([03](03-infrastructure-decision.md) §6.3). MotherDuck's own blog is blunt about this:
   *"DuckDB has its own dialect and functions, and if you don't tell the model to use them,
   it won't."*

**Exit condition**: a test asserting `DROP TABLE transactions` is refused, an unbounded
`SELECT *` is capped, and a deliberately slow query is killed by the timeout.

---

## PHASE 3 — Semantic layer (~1–2 days) ← **highest leverage in the whole plan**

**Two halves: SQL views for correctness, YAML for vocabulary.**

### 3a. Governed views — make the wrong answer impossible (~2 hours)
Adapted from WrenAI, which does not let the LLM write SQL against physical tables at all
([09](09-open-source-landscape.md) §3). A YAML file injected into a prompt is *advisory* — the
model may ignore it. A view is *structural*.

```sql
CREATE VIEW v_labeled_transactions AS      -- inner join: the 33% gap can't be hit
  SELECT t.*, f.is_fraud
  FROM transactions t JOIN fraud_labels f ON t.id = f.transaction_id;

CREATE VIEW v_spend AS                     -- excludes the 660,054 refunds
  SELECT * FROM transactions WHERE amount > 0;
```

Point the agent at these and name them in the tool docstring. Cheapest correctness win in the
entire plan.

### 3b. YAML metric registry — vocabulary, synonyms, caveats
All four reference products reduce to this once the enterprise serving layer is stripped away
([04](04-competitive-research.md) §6). Steal Databricks' Metric View shape.

```yaml
measures:
  - name: fraud_rate
    display_name: "Fraud Rate"
    synonyms: ["fraud %", "fraud percentage", "how much fraud"]
    expr: "SUM(f.is_fraud::INT) * 1.0 / COUNT(*)"
    requires_join: fraud_labels
    caveat: >
      Computed ONLY over labeled transactions. 4,390,952 of 13,305,915
      transactions have no fraud label; including them understates the rate by ~33%.
    format: { unit: percent }
```

15–30 metrics is enough. Encode the traps [02](02-data-dictionary.md) already surfaced:
- fraud rate over the **labeled subset only**
- spend metrics **excluding the 660,054 negative amounts**
- "per user" — denominator is 1,219 active users, not 2,000 registered

Inject into the system prompt with the Hex Threads policy: **prefer a governed definition;
fall back to raw column math only when none exists, and say so.**

**Exit condition**: ask the same metric three different ways in three separate threads; all
three produce identical SQL. That is the entire point — and it is the demo moment.

> **Warning from Hex's own post-mortem**: contradictory semantic definitions send an agent into
> "collapse mode" — 30 minutes of self-second-guessing. An *inconsistent* registry is worse
> than no registry. Keep it small and internally consistent.

---

## PHASE 4 — Multi-step reasoning (~2–3 days)

Replace the trivial ReAct loop with PLAN → EXECUTE → REFLECT.

- Plan node: `llm.with_structured_output(PlanSchema)` with a **Pydantic** model.
- Execute node: existing tool loop, now appending to a `reasoning_trace` state field.
- Reflect node: check results are non-absurd; route back with `Command`.
- **Bounded retries with early-accept**: on error, feed the error back (max 2–3 attempts).
  On a query that runs and returns ≥1 row, **accept immediately** — asking the model to
  double-check a working query is a documented way to turn a correct query into a wrong one.
- **Clarify, don't guess** on ambiguity — use `interrupt()`, present 2–3 interpretations
  (the Hex Threads pattern).

Guard against Hex's other documented failure: agents running *50* verification queries "just to
be certain". Cap the loop.

**Exit condition**: a "why did fraud spike in 2015?" style question demonstrably chains ≥3
queries and produces a narrative citing each. And a deliberately ambiguous question produces a
clarifying question, not a guess.

---

## PHASE 5 — Wire the frontend (~2–3 days)

The scaffold has **never been run against the backend**. Expect an install fight first —
CopilotKit has known ESM/CJS and peer-dependency issues on React 19; budget for
`--legacy-peer-deps`.

1. End-to-end plain chat first. Nothing else until a message round-trips.
2. **Decide v1 vs v2 API before writing any UI code** ([05](05-research-agent-stack.md) §1).
   Recommend **v2** — the docs already steer away from `useCopilotAction`.
3. Chart rendering via `useRenderTool` from `@copilotkit/react-core/v2`, `name` matching the
   Python tool **exactly**. Add a charting library — none is installed today.
4. `useDefaultRenderTool` during development to see every tool call.

**Exit condition**: a question returning grouped data renders an actual chart component in the
chat, not a markdown table.

---

## PHASE 6 — Reasoning-trace panel (~1–2 days)

Genie's "Thinking steps", which both Databricks and Hex ship as a headline feature.

Stream the Phase-4 `reasoning_trace` over AG-UI state rendering. **Not LangSmith** — that is
developer observability, its traces live in their dashboard, and its free tier hard-stops at
5,000 traces/month. If dev-side tracing is wanted later, use **Langfuse** (no card, self-hostable).

Caveat: mid-node emitted state is only a *prediction*; the node's returned state overwrites it.
Include the trace in the return.

**Exit condition**: the panel shows each query run **and which governed metric definition was
used**. That last clause is what makes it credible rather than decorative — it is the sentence
Phase 3 exists to enable.

---

## PHASE 7 — Statistics / A/B testing (~1 day)

**Do not add a Python sandbox.** `langchain-experimental` is archived (2026-05-26); E2B is
disproportionate infrastructure for closed-form tests.

Three parameterised tools taking only aggregate counts `run_sql` already returned:
`two_proportion_ztest`, `chi_square_independence`, `proportion_confidence_interval`
(implementations in [05](05-research-agent-stack.md) §5). No raw rows cross the tool boundary.

**Exit condition**: "is online fraud significantly higher than swipe fraud?" returns a p-value
and a confidence interval, not just two percentages. The real answer is dramatic — 0.8409% vs
0.0295% — so this is a strong demo.

**Guardrail**: the agent must refuse to test segments with too few fraud cases.
22 of 109 MCC segments already have <10 fraud cases at full scale.

---

## PHASE 8 — Memory (~half a day)

1. `MemorySaver` → `SqliteSaver`. One line. Fixes state loss on restart.
2. An `agent_memory(scope, key, value, updated_at)` table with one explicit "remember this" tool.
   Not a memory framework — see [06](06-memory-and-knowledge-graph.md) §5.

**Exit condition**: correct a metric definition, restart the server, and the correction survives.

---

## PHASE 9 — Deploy (~1 day)

Backend to Render (or per the Phase-0 decision), frontend to Vercel, `AGENT_URL` wired.
Mitigate the 15-min spin-down with a loading state or a GitHub Actions cron ping.

**Groq quota is the real demo risk** and needs handling here, not later: TPD 200,000 ≈ **13–14
multi-step questions/day**, and TPM 8,000 can be blown *inside a single turn* by a fast
multi-tool loop. Mandatory: exponential backoff, a visible "rate limited, retrying" state, and —
cheapest and most effective — **do not feed 200 raw rows back into context**; feed aggregates
and a truncated preview. Keep a no-card fallback provider configured (Cerebras has 1M tokens/day,
5× Groq's budget).

**Exit condition**: a public URL a stranger can use, and a rate-limit that degrades visibly
rather than looking broken.

---

## Explicitly NOT building (aspirational only)

Say these on a roadmap slide; do not build them.

| Item | Why not |
|---|---|
| Genie-style self-learning ontology | Cross-product graph infrastructure. Fake the outcome with a curated glossary. |
| ThoughtSpot's deterministic token compiler | It is their patent and a multi-year systems bet. |
| Hex's Temporal 4-agent orchestration | 30-person-team problem. One good graph is right-sized. |
| `build-kg` / knowledge graph | Targets unstructured regulatory text; Finbot's data is 100% structured. See [06](06-memory-and-knowledge-graph.md) §1. |
| Graph DB over transaction data | Schema lacks device/IP/email — the fields that make graph fraud detection work. If ring detection is ever needed: a `networkx` batch job writing `cluster_id` back into SQL. |
| dbt Semantic Layer / Cube | The YAML file is 90% of the value at 5% of the setup. |
| Sampling the dataset | Unnecessary (220 MB) and destructive (fraud is 0.1495%). See [03](03-infrastructure-decision.md) §5. |
| Paid production DB | Not until the product is proven. |

## Sequencing rationale

- **1–2 before 3**: no point defining `fraud_rate` against a store whose `amount` is a string.
- **3 before 4**: multi-step reasoning that re-derives inconsistent metrics per hop compounds error.
- **4 before 5**: the research is explicit — polishing a UI over unreliable reasoning yields a
  demo that looks good and answers badly.
- **6 after 3 and 4**: the trace panel is only impressive if there is real reasoning *and* a
  governed definition to cite.
- **9 last**: deploying before the answers are trustworthy just publishes the problem.

## Realistic total

Summing the per-phase estimates: **10–14 working days** for Phases 0–9, solo, assuming the
CopilotKit install fight in Phase 5 does not spiral. Phases 3 and 6 together — roughly two days —
deliver the largest share of the demo credibility, which is why they are not deferred.

Add ~1 day of slack for the Render memory probe in Phase 0 and its possible fallback
([03](03-infrastructure-decision.md) §8), giving a realistic **11–15 days**.
