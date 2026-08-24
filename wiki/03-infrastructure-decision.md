# 03 — Infrastructure Decision (research complete, AWAITING OWNER SIGN-OFF)

> **STATUS: DECISION NOT MADE. Do not touch `load_to_neon.py` or `agent/.env` until the owner
> picks a path.** Two provider switches have already caused significant rework. A third blind
> switch is the specific thing this document exists to prevent.

## 1. The constraint set

| Constraint | Detail |
|---|---|
| **Zero billing** | No credit card at any provider. Not "free tier with a card on file." Firm. |
| **Minimum service count** | *"Too many cooks spoil the broth."* Every new SaaS signup is a new account, quota, dashboard and failure mode. **Adding a provider must be justified, not defaulted to.** |
| **Publicly reachable** | A future Vercel deployment must reach it. Not localhost, not a laptop, not a tunnel. |
| **Analytical workload** | An LLM issuing repeated exploratory GROUP BY / JOIN / window queries. |
| **Real scale** | 22.5M rows. But see §2 — the "scale" framing was the mistake. |

### Service-count budget

Accounts already held: **Groq, Tavily, GitHub, Neon** (dead), CockroachDB (dead).
Vercel is required for the frontend regardless.

| Verdict | Service |
|---|---|
| **Already have — prefer these** | GitHub, Groq, Tavily |
| **Required, unavoidable** | Vercel (frontend) |
| **At most ONE new signup** | a backend host (see §4B) |
| **Rejected on service-count grounds** | MotherDuck, Hugging Face, Langfuse, LangSmith, CopilotKit Enterprise Intelligence, Zep — each solves a problem that a file or a table already solves |

This constraint changes one earlier recommendation: **do not host the Parquet on Hugging Face.**
GitHub Releases accepts files up to 2 GB, serves them over HTTPS with Range-request support, and
**requires no new account.** For a 220 MB Parquet set or a 329 MB DuckDB file that is strictly
better under this budget.

## 2. The reframe that solves this

Both previous failures came from putting a **columnar analytical dataset into a row-store**.

| Format | Size |
|---|---:|
| Raw CSV/JSON/XLSX | 1.3 GB |
| **Estimated in Postgres** (row overhead + indexes) | **2–4 GB** |
| **Parquet + zstd** | **219.9 MB** |
| Single consolidated `.duckdb` file | 329 MB |

Measured, not estimated ([02](02-data-dictionary.md) §1). Two distinct numbers, not to be
conflated:

- **Compression ratio**: 1.3 GB raw → 219.9 MB Parquet = **5.9× smaller**.
- **Headroom against a 512 MB tier**: 219.9 MB is **2.3× under** it.

(Neon stores Postgres pages, not Parquet files, so the comparison is illustrative of *scale*,
not a claim you could load Parquet into Neon.) Every query in the benchmark suite ran in
**3–130 ms** — under best-case local conditions; see [02](02-data-dictionary.md) §6.

**The dataset was never too big. The storage engine was wrong.** This also retires the sampling
question — see §5.

## 3. Post-mortem: why each previous attempt died

| Attempt | Cause of death | Still true in 2026? |
|---|---|---|
| Google Cloud | CLI/auth friction; card required | Yes |
| **Neon** | **0.5 GB project cap.** Blew it partway through `fraud_labels`. | Yes — confirmed 0.5 GB/project, 100 CU-hrs/mo. No card. |
| **CockroachDB Serverless** | **50M Request Units/month covering reads AND writes.** The one-time load of 22.5M rows consumed the entire monthly quota in one session. Cluster hard-disabled. | **Yes — the RU model is unchanged.** Do not return here. |
| Oracle Always Free | Documented silent account suspension/deletion; plus self-hosting ops burden | Yes |
| Local Docker Postgres | No network path from Vercel serverless | Yes |
| Supabase | 500 MB cap, **and auto-pauses after 7 days idle** | Yes |

**The pattern**: the killer was never storage size. It was an **opaque usage quota** (RUs) that
a one-time bulk load could exhaust. Any candidate must be judged primarily on *"can a single
mistake silently disable it?"*

Also eliminated on the card constraint or on runtime incompatibility: Render Postgres
(hard-deletes after 30 days), Fly.io, Railway, Xata (free tier retired), Tembo (dead — exited
hosted Postgres in 2025), Northflank (card required for all users), Scaleway (card required),
Cloudflare R2 (card required), ClickHouse Cloud / Snowflake (trials only), Koyeb (conditional
card; free tier reportedly closed to new signups).

## 4. The two decisions

There are **two** hosting questions, and the brief only named one. The second was missed and is
equally blocking:

- **4A — Where does the data live?**
- **4B — Where does the Python backend run?** Vercel only solves the *frontend*. The FastAPI +
  LangGraph server on port 8123 needs its own publicly reachable home.

### 4A — Data hosting

| Option | Storage | Quota | Card | Silent-death risk |
|---|---|---|---|---|
| **DuckDB file bundled with the backend** | 329 MB on the backend's own disk | **none** | No | **None. There is no quota and no account.** |
| **Parquet on Hugging Face + DuckDB `httpfs`** | 220 MB | **none** | No | Near-zero. Only a soft anti-abuse policy aimed at multi-TB hoarding. |
| **MotherDuck Lite** | 10 GB | 10 CU-hrs/mo | No | Low-but-real — see below |
| Turso (libSQL) | 5 GB | 500M rows read/mo | No | Low. SQLite dialect is a bigger LLM-generation departure. |
| BigQuery Sandbox | 10 GB | 1 TB queries/mo | **No** (Sandbox specifically) | Medium — **tables auto-expire after 60 days**; no DML in sandbox |

**On MotherDuck specifically** — the research corrected an important assumption. A "Pulse
compute hour" is **not** wall-clock awake time. Per MotherDuck's docs, Pulse Ducklings are
*"metered on a per-query basis, with a minimum of 1 Compute Unit (CU) second... instead of
wall-clock time."* So 10 CU-hrs = **36,000 CU-seconds ≈ 36,000 queries/month** even at the
1-second-per-query floor — and measured query times are 3–130 ms. That is generous, not tight,
and it is *not* the CockroachDB failure mode: the metering is transparent and tied to real
compute rather than opaque RUs.

The residual risk is **contractual, not quota-based**. MotherDuck's Fees Addendum states free
accounts must upgrade (add a card) for more volume, and that *"MotherDuck may suspend a Free
Account at any time and for any reason."* The exact behaviour at the 10-hour line is
undocumented. There is no confirmed real-time quota meter on Lite.

> **Recommendation for 4A: make the DuckDB file / Parquet the load-bearing path, distributed
> via GitHub Releases, and skip MotherDuck entirely** (service-count budget, §1). Keep
> `run_sql` behind an interface so MotherDuck can be swapped in later without touching the agent.
>
> **This is the first data layer in this project's history with no quota that can kill it** —
> there is no account and no meter. Note the scope: the *data layer* becomes quota-free. The
> system as a whole still has one live quota, Groq's 200,000 tokens/day
> ([05](05-research-agent-stack.md) §3), which is handled separately in
> [07](07-roadmap.md) Phase 9.

### 4B — Backend hosting

| Option | Card | Notes |
|---|---|---|
| **LangGraph.js in-process in Next.js** | No | **Collapses to ONE Vercel deployment.** No second host at all. |
| **Render free web service** | No | 512 MB / 0.1 CPU / 750 hrs. Sleeps after 15 min idle, ~1 min cold start. Python unchanged. |
| Modal / Beam.cloud | No (until $30/mo credit exhausted) | Real Python containers, native ASGI streaming |
| Vercel Services (beta) | No | Python + Next.js in one project, but 300 s Hobby cap + **ephemeral disk** |
| Hugging Face Spaces | — | **ELIMINATED.** Docker/Gradio Spaces now require a paid PRO plan; only Static Spaces are free. |
| PythonAnywhere | — | ELIMINATED — free accounts restricted to a whitelist; `api.groq.com` not on it |
| Cloudflare Workers Python | — | ELIMINATED — Pyodide/WASM, ~10 MB limit, no DuckDB |

**The LangGraph.js option is the significant finding.** CopilotKit ships `LangGraphAgent` from
`@copilotkit/runtime/langgraph`, which wraps a compiled TypeScript `CompiledStateGraph`
**running in the same Node process as the Next.js API route** — no network hop, no second
deployment. `@langchain/groq` and `@langchain/tavily` both exist with matching interfaces.

> **Caveat**: LangGraph.js checkpointer and streaming *parity* with Python is reported by
> third-party trackers, not by an official LangChain parity matrix. Treat as
> **corroborated but not primary-sourced** — verify before betting the architecture on it.

Cost of that path: the ~65-line Python agent gets rewritten in TS (roughly a day), and DuckDB
access from Node uses `@duckdb/node-api` (the old `duckdb` npm package is deprecated).

> **Recommendation for 4B: stay in Python on Render for now; revisit LangGraph.js only if the
> spin-down proves unacceptable.** Rationale: the Python agent already works, the analytical
> tooling (`scipy`/`statsmodels`, see [05](05-research-agent-stack.md) §5) is Python-native and
> has no clean JS equivalent, and Render's cold start is a UX problem solvable with a loading
> state or a GitHub Actions cron ping — not a capacity problem.

## 5. The sampling question — RESOLVED: do not sample

The open question was whether to cut transactions to ~13% to fit Neon. **The answer is no**,
on two independent grounds.

**It is unnecessary.** 220 MB of Parquet fits every candidate with room to spare.

**It would be genuinely destructive.** Fraud here is a rare event: **13,332 fraud cases out of
8,914,963 labeled rows = 0.1495%**. Already at *full* scale, **22 of 109 MCC segments have
fewer than 10 fraud cases**. Cutting to 13% leaves ~1,733 fraud cases total and pushes the
large majority of segments below any usable threshold — segment fraud comparison, cohort
analysis and the A/B-testing feature all stop working, and "zero fraud in category X" becomes a
sampling artifact reported as a finding. That is precisely the "hallucinated statistics on
sparse data" failure documented for Julius AI ([04](04-competitive-research.md) §4).

*If* sampling were ever forced: stratify on `is_fraud` (keep ~100% of fraud rows, downsample
the majority class) **and** sample at `client_id` level rather than row level, taking all of a
selected user's transactions, or the users ⋈ cards ⋈ transactions ⋈ fraud_labels joins break.

## 6. What must change in code once a path is chosen

Do not start these yet. Listed so the blast radius of the decision is visible.

1. **`load_to_neon.py`** — rename, and rewrite for a set-based load. DuckDB is not tuned for
   row-by-row inserts; use `COPY`/`CREATE TABLE AS SELECT` from Parquet. Also fix at this
   point: parse `amount` to `DECIMAL(10,2)`, cast `is_fraud` to BOOLEAN, keep `databank.value`
   numeric instead of `str`, drop `card_number`/`cvv`.
2. **`agent/.env`** — `DATABASE_URL` currently points at the dead Neon project.
3. **`run_sql` docstring** — must say **DuckDB**, not "standard SQL". MotherDuck's own
   engineering blog is explicit: *"DuckDB has its own dialect and functions, and if you don't
   tell the model to use them, it won't."* Highest-risk gotchas to name in the prompt:
   - `strftime`/`strptime`, **not** Postgres's `to_char`/`to_timestamp` (these do not exist)
   - no stored procedures / PL-pgSQL; `CREATE MACRO` is the nearest thing
   - `information_schema` works, but `duckdb_tables()` / `duckdb_columns()` are richer
   - `QUALIFY`, `SELECT * EXCLUDE(...)`, `DISTINCT ON` all work and are useful
   - avoid `COUNT(DISTINCT x) OVER (...)` — unreliable in DuckDB
4. **Read-only enforcement (security, non-negotiable).** `run_sql` currently would execute
   `DROP TABLE`. Enforce at the driver, not the prompt:
   `duckdb.connect(path, read_only=True)`, or `ATTACH '...' AS db (READ_ONLY)`; on MotherDuck,
   a role-scoped read-only service token or a read-only share. Add a `SELECT`/`WITH`-only
   string check as defence in depth, never as the sole control.
5. **Query timeouts.** DuckDB has **no `statement_timeout`**. `con.interrupt()` exists but is
   documented as unreliable. Wrap each query in a `ThreadPoolExecutor` with
   `future.result(timeout=N)` and recycle the connection if it doesn't land. Also inject a
   server-side `LIMIT` when the model omits one, and set `memory_limit`/`threads` at connect.

## 7. Validation that this is a real architecture

MotherDuck published *"Build a LangChain SQL Agent with DuckDB and MotherDuck"* (April 2026) —
essentially this exact design, from the vendor. Their documented lessons match the plan here:
an iterative `list_tables → get_schema → draft → check → execute → self-correct` loop; feeding
execution errors back to the model; enforcing read-only at the connection *"not just in the
prompt"*; injecting `LIMIT`; and adding a semantic layer to bridge business vocabulary to
column names.

## 8. THE DECISION REQUIRED FROM THE OWNER

**Option A — Recommended. Zero-quota data layer, one new signup.**
DuckDB file distributed via GitHub Releases, Python backend on Render free, Next.js on Vercel.
*Pros:* no data-layer quota can kill it; keeps the working Python agent; scipy/statsmodels
available; exactly one new account (Render).
*Cons:* two deployments; ~1 min cold start after 15 min idle; **and one untested assumption —
see the risk below.**

> ### ⚠ The one thing Option A has NOT been validated on
> Render's free web service gives **512 MB RAM and 0.1 CPU**. Option A puts a **329 MB DuckDB
> file** behind a Python process running langgraph + langchain + duckdb on that box. Nobody has
> tested whether it fits or performs.
>
> Reasons for cautious optimism: DuckDB memory-maps its file rather than loading it into RAM,
> streams results, and honours a `memory_limit` setting with spill-to-disk. Reasons for caution:
> the 3–130 ms benchmarks were on a warm multi-core laptop, **not** on 0.1 CPU, and the
> `08-positioning.md` demo script promises sub-second responses.
>
> **This is the first thing to test in Phase 0** — before building anything on top of it.
> Cheapest probe: deploy a bare FastAPI + DuckDB service that runs the six benchmark queries and
> reports timings and peak RSS. An hour of work that de-risks the whole plan.
> Fallbacks if it fails, in order: (1) set `memory_limit='300MB'` and reduce `threads`;
> (2) drop `transactions` to the labeled subset only, halving the file; (3) move to Modal or
> Beam (real containers, $30/mo credit, no card) — one different signup, not an extra one.

**Option B — Single deployment.**
Rewrite the agent in LangGraph.js, run in-process in Next.js on Vercel, DuckDB via
`@duckdb/node-api` or MotherDuck.
*Pros:* one deployment, no cold start, no second host.
*Cons:* ~1 day rewrite; loses easy access to Python's statistical libraries — the A/B-testing
feature would need rethinking.

**Option C — MotherDuck-first.**
As Option A, but MotherDuck as the primary store rather than a bundled file.
*Pros:* a real cloud DB to point at in a demo; 10 GB headroom.
*Cons:* reintroduces an account that can be suspended "for any reason" — the one risk class
this project has been burned by twice.

**My recommendation: Option A**, with the `run_sql` tool written against an interface that lets
MotherDuck be swapped in later without touching the agent.
