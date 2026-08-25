# 07 — Build Roadmap

Sequenced. Each phase states a **verifiable exit condition** — not "it works", but a check that
fails loudly if the phase is broken. Phases are ordered so that nothing built later has to be
torn up by a decision made later.

**Guiding principle from the research**: Julius AI proves a single-agent chat design is not
inherently limited ([04](04-competitive-research.md) §4). Finbot's architecture is not wrong,
it is *under-built*. Almost everything below deepens the existing graph rather than replacing it.

---

## Status snapshot (updated 2026-08-25, verified against the working tree)

**Phases 0–6 are done and running locally.** `git log` shows three feature commits
(`b0890c2`, `8e47475`, `8fed013`) that shipped the pre-joined DuckDB store, governed views,
driver-level read-only, the query budget, the semantic layer, charts, the SQL trace, and the
discovery UI. `agent/agent.py` has a real system prompt, two tools (`run_sql`, `chart`), and
the budget-rebind guard — none of that existed when this roadmap was first written. Phase 8
step 1 (checkpointer) is also done: `agent/server.py` builds an `AsyncSqliteSaver` correctly.
Everything below this line is what is **actually still open**, in order.

**Phases 0–6 bodies below are kept as historical record** — the safety patterns, view
definitions and gotchas they document are still exactly what shipped. Skip to
[Phase 7](#phase-7--statistics--ab-testing-built-not-wired) for the real remaining work.

---

## PHASE 0 — Unblock (BLOCKED ON OWNER) — ✅ DONE (resolved as Option A, local DuckDB)

**Nothing else can start.** The repo currently cannot reach a database with data in it.

| Step | Exit condition |
|---|---|
| 0.1 Owner picks Option A / B / C from [03](03-infrastructure-decision.md) §8 | A decision is written down |
| 0.2 ~~Memory probe~~ **DONE** — [13](13-experiments.md) E1–E4 | ✅ Answered: only the **pre-joined** layout fits (183 MB vs 731 MB). Now a hard requirement in Phase 1. |
| 0.3 Commit the uncommitted `run_sql` change on `main` | `git status` clean |
| 0.4 Mark `PROGRESS.md` and plan v1/v2 superseded (done) | No doc contradicts [01](01-current-state.md) |
| 0.5 *(optional, ~1 h)* Repeat the memory probe on a real Linux 512 MB cgroup | Confirms the macOS proxy before Phase 9 |

**Recommendation: Option A** — DuckDB/Parquet data layer, Python backend on Render, Next.js on
Vercel. No quota in the system can silently kill it.

---

## PHASE 1 — Data layer, rebuilt properly (~1 day) — ✅ DONE (`data/finbot.duckdb`, 279 MB)

Rewrite the ETL. The current `load_to_neon.py` carries four correctness bugs worth fixing while
it is being touched anyway.

> **0. Build a pre-joined `fact_transactions` table. This is now mandatory, not an optimisation.**
> [13](13-experiments.md) E1–E3 measured the normalised layout at **731 MB peak RSS** — it does
> not fit a 512 MB host. Pre-joined: **183 MB and 10× faster**. Working query in
> `tools/experiments/e3_prejoined_fact.py`; builds in 2.5 s. 8,914,963 rows = the labeled subset,
> with `is_fraud`, `mcc_description`, card and user attributes denormalised in.
> Keep the raw tables available for the 33% unlabeled rows and for macro data.

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

## PHASE 2 — Make `run_sql` safe and dialect-correct (~half a day) — ✅ DONE (`agent/db.py`)

This is security work, not polish. The tool as written would execute `DROP TABLE`.

All of this is **verified working** in `tools/experiments/e5_safety.py` — copy from there.

1. **Read-only at the driver.** Verified: it blocks `DROP`, `DELETE`, `UPDATE`, `CREATE` and
   `INSERT`, while `SELECT` still works.
   **Use the `:memory:` + ATTACH pattern, not `connect(read_only=True)`** — the latter also
   blocks `CREATE VIEW`, so you could not define the governed views:
   ```python
   con = duckdb.connect(":memory:")
   con.execute("ATTACH 'fact.duckdb' AS fact (READ_ONLY)")
   con.execute("CREATE VIEW v_spend AS SELECT * FROM fact.fact_transactions WHERE amount > 0")
   ```
2. **`SELECT`/`WITH`/`DESCRIBE`-only string check** as defence in depth — never the sole control.
   Verified to reject `DROP`, lowercase `delete`, `PRAGMA` and `ATTACH`.
3. **Server-side `LIMIT` injection** when the model omits one.
4. **Wall-clock timeout wrapper.** Confirmed: DuckDB has **no `statement_timeout`** — both
   `SET statement_timeout='1s'` and `=1000` raise *unrecognized configuration parameter*.
   `ThreadPoolExecutor` + `future.result(timeout=N)` + `con.interrupt()` was verified to cut off
   a runaway self-join at exactly 3.0 s, **with the connection still usable afterwards**.
   Set `memory_limit` and `threads` at connect.
5. **Rewrite the docstring to say DuckDB**, naming the high-risk gotchas
   ([03](03-infrastructure-decision.md) §6.3). MotherDuck's own blog is blunt about this:
   *"DuckDB has its own dialect and functions, and if you don't tell the model to use them,
   it won't."*

**Exit condition**: a test asserting `DROP TABLE transactions` is refused, an unbounded
`SELECT *` is capped, and a deliberately slow query is killed by the timeout.

---

## PHASE 3 — Semantic layer (~1–2 days) — ✅ DONE (`agent/metrics.yaml`, governed views in `db.py`)

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

## PHASE 4 — Multi-step reasoning (~2–3 days) — ⚠️ PARTIAL (budget guard done; no explicit plan/reflect nodes)

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

## PHASE 5 — Wire the frontend (~2–3 days) — ✅ DONE ([16](16-ui-build.md))

**Partly done already.** [13](13-experiments.md) E11 took the full path end-to-end:
Next.js → CopilotKit → AG-UI → FastAPI → LangGraph → Groq → DuckDB, rendering a correct
answer in the chat. `npm install` and `npm run build` both succeeded cleanly —
**the predicted peer-dependency fight did not materialise.**

> **⚠ Three integration bugs must be fixed first, all of which appear in the browser only as
> the word "terminated":**
> 1. **A checkpointer is mandatory** — AG-UI calls `graph.aget_state()`; `.compile()` without
>    one raises `ValueError: No checkpointer set`. **This makes Phase 8 a prerequisite of
>    Phase 5, not a later step.**
> 2. **Sync `SqliteSaver` fails** — AG-UI is async; it raises `NotImplementedError`.
> 3. **`AsyncSqliteSaver` can't be built at module scope** — needs a running event loop.
>
> The working pattern is in `tools/experiments/e11_server.py`: build everything inside an async
> `main()` with `AsyncSqliteSaver.from_conn_string()` as a context manager, and serve uvicorn
> from within it. Copy it.

Also: set `COPILOTKIT_TELEMETRY_DISABLED=true` — the runtime enables anonymous telemetry by default.

1. End-to-end plain chat first. Nothing else until a message round-trips. **(Done in E11.)**
2. **Decide v1 vs v2 API before writing any UI code** ([05](05-research-agent-stack.md) §1).
   Recommend **v2** — the docs already steer away from `useCopilotAction`.
3. Chart rendering via `useRenderTool` from `@copilotkit/react-core/v2`, `name` matching the
   Python tool **exactly**. Add a charting library — none is installed today.
4. `useDefaultRenderTool` during development to see every tool call.

**Exit condition**: a question returning grouped data renders an actual chart component in the
chat, not a markdown table.

---

## PHASE 6 — Reasoning-trace panel (~1–2 days) — ⚠️ PARTIAL (SqlCard shows queries; no dedicated trace panel — see [16](16-ui-build.md) §6)

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

## PHASE 7 — Statistics / A/B testing (BUILT, NOT WIRED) — the next thing to build

**The math is done.** `agent/statistics.py` (27 KB) implements `compare_two_rates`,
`rate_interval`, `compare_many_rates` — Wilson score intervals, pooled/unpooled z-tests,
Fisher's exact fallback, Benjamini–Hochberg correction, the Cohen's-h rare-event fix — and
passes its full oracle suite verified against `scipy`/`statsmodels`/hand arithmetic. Full
design rationale in [15](15-statistics.md). **None of it is reachable from the chat yet.**

Concrete steps, in order:

1. **Register the three functions as `@tool` in `agent/agent.py`.** They are plain functions
   today, not LangChain tools — wrap each with `@tool` and a docstring the model can act on
   (signatures: `compare_two_rates(label_a, successes_a, trials_a, label_b, successes_b,
   trials_b, confidence=0.95)`, `rate_interval(label, successes, trials, confidence=0.95)`,
   `compare_many_rates(labels, successes_list, trials_list, ...)`). Add them to the `tools`
   list at `agent.py:135` alongside `run_sql` and `chart`.
2. **Add them to the over-budget rebind at `agent.py:167`.** Today that line does
   `llm.bind_tools([chart])` once the 4-query budget is spent — change it to
   `llm.bind_tools([chart, compare_two_rates, rate_interval, compare_many_rates])`. Without
   this, a test becomes unreachable at exactly the point the model has the counts it needs to
   run one.
3. **Extend the system prompt** (`agent.py` `SYSTEM_PROMPT`): call a stats tool whenever the
   user asks whether a difference is real, significant, or meaningful — and never assert
   significance without having run one. Point at the same rare-event refusal rule already in
   the prompt (≥30 events) so the model doesn't test segments the stats layer will refuse anyway.
4. **Build a `StatCard.tsx`** in `frontend/app/components/`, and a matching `useRenderTool`
   registration in `page.tsx` (zod schema mirroring the three tool signatures, `name` matching
   exactly — same pattern as `SqlCard`/`ChartCard`). Render order, per [15](15-statistics.md)
   §6: the verdict sentence first, then rates with CI error bars, then p-value/effect size as
   secondary detail.
5. Update this roadmap's status line once shipped (do not leave a second stale "done" claim).

**Exit condition**: "is online fraud significantly higher than swipe fraud?" returns a p-value
and a confidence interval in a rendered card, not just two percentages. The real answer is
dramatic — 0.8378% vs 0.0158%, 353× — so this is the strongest demo moment available.

**Guardrail already built into `statistics.py`**: refuses to test segments with too few
events rather than returning a number it can't justify — see [15](15-statistics.md) §4.

---

## PHASE 8 — Memory (~half a day) — ⚠️ PARTIAL

1. `MemorySaver` → **`AsyncSqliteSaver`** — ✅ DONE. `agent/server.py` builds it correctly
   inside async `main()`, exactly per the E11 pattern. State survives a restart.
2. An `agent_memory(scope, key, value, updated_at)` table with one explicit "remember this"
   tool — **not built.** Low priority: nothing in the current demo script needs a correction
   to persist across a restart. Defer unless the owner hits this in practice.

**Exit condition** (for step 2, if ever picked up): correct a metric definition, restart the
server, and the correction survives.

---

## PHASE 9 — Deploy (~1 day estimated; currently BLOCKED, in progress)

Two separate deployments, and both are open right now.

### 9a. Frontend → Vercel — blocked on a platform permission wall
The connected Vercel token can create a brand-new project's first deployment, but 403s on
any second touch to that same project — including projects created earlier in this same
session (`finbot`, `finbot-analyst` both failed on redeploy). Every retry needs a **fresh,
never-before-touched project name**.

Steps:
1. Deploy under an unused project name (e.g. `finbot-demo`).
2. Verify by fetching the live URL directly — deployment status can't be queried through the
   API once the 403 wall is hit, so the URL fetch *is* the verification.
3. Understand what this ships even when it works: `frontend/app/api/overview/route.ts` falls
   back to the committed `overview-snapshot.json` when no backend is reachable, so the page
   shows real measured dataset stats — but the chat cannot answer anything, and the UI says so
   (`snapshot: true` banner in `page.tsx`). This is a legitimate intermediate milestone, not
   the finished product.

### 9b. Backend hosting — decision still owed by the owner ([03](03-infrastructure-decision.md) §8)
Nothing here has been built yet — no `Dockerfile`, no `render.yaml`. Once the owner picks:

- **Option A (recommended)**: Render free web service, the 279 MB `data/finbot.duckdb`
  bundled into the container image, `AGENT_URL` in Vercel pointed at the Render URL. Measured
  ~410 MB RSS / 153 ms worst query for the pre-joined layout — fits Render's 512 MB free tier.
  Mitigate the 15-min spin-down with a loading state or a GitHub Actions cron ping.
- **Option B**: rewrite the agent in LangGraph.js, run in-process in the same Vercel
  deployment as the frontend. No second host, but loses Python's `scipy`/`statsmodels` — would
  need to re-derive Phase 7's math in JS, which nothing has scoped yet.
- **Option C (rejected)**: MotherDuck — reintroduces exactly the "account can be suspended for
  any reason" quota risk that killed Neon and CockroachDB twice already.

**Groq quota is the real demo risk once this is public**, and must be handled at this step,
not after: TPD 200,000 ≈ **13–14 multi-step questions/day**, and TPM 8,000 can be blown
*inside a single turn* by a fast multi-tool loop. Mandatory before opening this to strangers:
exponential backoff, a visible "rate limited, retrying" state, and — cheapest and most
effective, already partly done in `run_sql` — never feed raw rows back into context, only
aggregates and a truncated preview. Keep a no-card fallback provider configured (Cerebras has
1M tokens/day, 5× Groq's budget).

**Exit condition**: a public URL a stranger can use for real chat (not the snapshot fallback),
and a rate-limit that degrades visibly rather than looking broken.

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

## What's left, in priority order (2026-08-25)

1. **Phase 7 — wire the statistics layer.** The math is done and verified; only the tool
   registration, prompt update, and `StatCard` UI remain. Highest leverage per hour of any
   remaining item — the 353× channel gap becomes a p-value-and-CI demo instead of two numbers.
2. **Phase 9a — land one working Vercel deploy** under a fresh project name, to have a real
   link to share (snapshot-backed, chat still offline).
3. **Phase 9b — owner decides backend hosting**, then build the one artifact that decision
   requires (Dockerfile for Option A, or the JS rewrite for Option B) and wire `AGENT_URL`.
4. Everything else — mobile layout, a dedicated reasoning-trace panel (CopilotKit's built-in
   "Thought for N seconds" already covers most of this for free), the `agent_memory` table —
   is polish, not a blocker to a working public demo.

## Realistic total (superseded — kept for history)

The original estimate below assumed a fully cold start; Phases 0–6 turned out to take about
that long and are now done. Remaining work (Phase 7 wiring + Phase 9 deploy) is realistically
**1–2 more days**, dominated by whichever backend-hosting option the owner picks in 9b.

<details><summary>Original estimate, written before Phase 0</summary>

Summing the per-phase estimates: **10–14 working days** for Phases 0–9, solo, assuming the
CopilotKit install fight in Phase 5 does not spiral. Phases 3 and 6 together — roughly two days —
deliver the largest share of the demo credibility, which is why they are not deferred.

Add ~1 day of slack for the Render memory probe in Phase 0 and its possible fallback
([03](03-infrastructure-decision.md) §8), giving a realistic **11–15 days**.

</details>
