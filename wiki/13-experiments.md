# 13 — Experiments (run 2026-08-24)

Seven experiments run to validate the research before committing to an architecture. Scripts at
[`tools/experiments/`](../tools/experiments/); all reproducible, none needed an API key or a signup.

**Three of them changed a decision. Two contradicted earlier pages of this wiki.**

---

## E1/E2/E3 — Can this run on a 512 MB free-tier box?

The single untested assumption behind Option A. Simulated Render free
(512 MB RAM, 0.1 CPU) with DuckDB `memory_limit` and `threads=1`.

| Storage approach | Peak RSS | Slowest query | Verdict |
|---|---:|---:|---|
| Normalised `.duckdb` (329 MB) | **731 MB** | 1,490 ms | ❌ blows the limit |
| Parquet views (219.9 MB) | **687 MB** | 1,551 ms | ❌ blows the limit |
| **Pre-joined fact table (264 MB)** | **183 MB** | **153 ms** | ✅ **fits** |

**The finding: the storage format was never the problem — the joins were.** Repeatedly hash-joining
13.3M transactions against 8.9M fraud labels is what consumed the memory. Setting `memory_limit`
did not help, because the growth is mmap'd file pages, not DuckDB's buffer pool.

Materialising the join once at ETL time — `fact_transactions`, 8,914,963 rows with fraud label,
MCC description, card and user attributes already attached — gives **4× less memory and 10×
lower latency**. Build cost: 2.5 s, one-off, offline.

> **This reframes the semantic layer.** [07](07-roadmap.md) Phase 3 justified governed views on
> *correctness* grounds. They turn out to also be **what makes free-tier hosting viable at all**.
> The correctness win and the performance win are the same change.

### E4 — the Python stack's share of the budget

| Import | Cost |
|---|---:|
| baseline interpreter | 18 MB |
| fastapi + uvicorn + pydantic | +33 MB |
| langgraph + langchain-core + groq + tavily | +42 MB |
| pandas | **+43 MB** |
| **total measured** | **135 MB** |

`duckdb`, `scipy` and `statsmodels` were not installed in the agent venv; budget ~90 MB more.

**Budget: ~225 MB stack + 183 MB data ≈ 410 MB, inside 512 MB — but only just.**
**`pandas` is 43 MB and is only needed at ETL time. Keep it out of the runtime image.** That
alone buys back a fifth of the remaining headroom.

> Caveat: measured on macOS, where `ru_maxrss` counts mmap'd pages that Linux can reclaim under
> pressure. Real Linux behaviour may be more forgiving. **This shifts Option A from "unvalidated"
> to "validated under a conservative proxy" — it is not a deployment test.**

---

## E5 — Do the safety mechanisms actually work?

All three Phase-2 claims verified.

**Read-only at the driver** — `duckdb.connect(path, read_only=True)` blocked every attack:
`DROP TABLE`, `DELETE`, `UPDATE`, `CREATE TABLE`, `INSERT` all raised. `SELECT` still worked.
It is genuine enforcement, not convention.

> Side effect worth knowing: `read_only=True` also blocks `CREATE VIEW`, so you cannot define
> governed views on that connection. **The production pattern is an in-memory connection with
> the data attached read-only:**
> ```python
> con = duckdb.connect(":memory:")
> con.execute("ATTACH 'fact.duckdb' AS fact (READ_ONLY)")
> con.execute("CREATE VIEW v_spend AS SELECT * FROM fact.fact_transactions WHERE amount > 0")
> ```
> Views live in the ephemeral in-memory catalog; the data stays immutable.

**No statement timeout** — confirmed. Both `SET statement_timeout='1s'` and `=1000` fail with
*Catalog Error: unrecognized configuration parameter*.

**Thread-based wall-clock wrapper works.** A deliberately expensive self-join was cut off at
exactly 3.0 s via `ThreadPoolExecutor` + `future.result(timeout=...)` + `con.interrupt()`, and
**the connection remained usable afterwards** (`SELECT 1` succeeded). Cheap queries pass through
untouched. This is the pattern to ship.

**A `SELECT`/`WITH`/`DESCRIBE`-only guard** correctly rejected `DROP`, lowercase `delete`,
`PRAGMA` and `ATTACH`. Keep as defence in depth, never as the sole control.

---

## E6/E7 — Analytical claims

### The cross-domain join is real but analytically weak — [08](08-positioning.md) overstated it

Confirmed: `merchant_state` matches `findex.countrynewwb` on **104 countries**. But:

- The naive join fans out **55.9×** (not ~49× as [02](02-data-dictionary.md) first estimated):
  3,102,332 joined rows from **55,485 actual transactions**.
- Those 55,485 transactions are **0.4% of the labeled dataset**.
- Most matching countries have **zero fraud**, so the fraud-vs-inclusion correlation is
  degenerate rather than interesting.
- **`findex` indicator columns are `VARCHAR`, not numeric** — `avg(account_t_d)` fails outright.
  A new data-quality trap; `TRY_CAST(... AS DOUBLE)` is required.

**Verdict: keep the join as a capability demonstration, drop it as the flagship demo.** E7 found
something far stronger.

### E7 — the finding the demo should lead with

Segmenting by what `merchant_state` actually encodes:

| Segment | Transactions | Fraud | Rate |
|---|---:|---:|---:|
| US state code (domestic, in-person) | 7,807,586 | 1,234 | **0.0158%** |
| NULL (= online) | 1,047,865 | 8,779 | **0.8378%** |
| **Foreign country** | **59,512** | **3,319** | **5.577%** |

**Foreign merchants carry a 353× higher fraud rate than domestic in-person.**

And `merchant_state IS NULL` is **not missing data** — it is *exactly* the online channel.
1,043,975 of 1,047,865 NULLs are `Online Transaction`. This **corrects
[02](02-data-dictionary.md)**, which called the 11.75% NULL rate a data-quality trap. It is a
meaningful category, and should be labelled `Online` in the ETL, not treated as missing.

### The Italy anomaly — a textbook breach signature

Of all foreign countries with ≥500 transactions, **only Italy has any fraud at all**:

| Year | Transactions | Fraud | Rate |
|---|---:|---:|---:|
| 2010–2016 | ~1,120 | **0** | 0% |
| 2017 | 288 | 172 | **59.72%** |
| 2018 | 1,700 | 1,529 | **89.94%** |
| 2019 | 1,598 | 1,360 | **85.11%** |

Zero for seven years, then sudden onset in 2017 sustained through 2019. Concentrated in
**65 merchants across 424 clients**. Canada, Mexico, Japan, Spain, Netherlands and every other
foreign country: **0 fraud**.

This is the shape of a compromised merchant cluster. It is a *synthetic* dataset, so this is a
generated pattern rather than a real breach — **say so** — but it is exactly the anomaly an
analyst is supposed to surface, and no dashboard would have been built to show it.

> **This should be the demo's "why" question**: *"Is fraud evenly distributed across
> geographies?"* → 353× foreign multiplier → drill in → Italy → drill in → a 2017 onset in 65
> merchants. Three chained queries, a real narrative, an unambiguous finding.

### Statistical tools validated on real numbers

`statsmodels`, online vs swipe:
- **z = 177.9, p ≈ 0**
- Online 95% CI **[0.8236%, 0.8586%]**, Swipe **[0.0280%, 0.0311%]** — non-overlapping.

### The refusal guardrail must use counts, not interval width

The experiment falsified a plausible design. Segments with **zero** fraud have a *very narrow*
confidence interval:

| Segment | Fraud / n | CI width |
|---|---|---:|
| Tolls and Bridge Fees | 0 / 451,814 | 0.001 pp |
| Utilities | 0 / 162,371 | 0.002 pp |
| Department Stores | 2,251 / 318,511 | 0.058 pp |

**A width-based rule would confidently accept "Tolls have 0% fraud" and reject the segment that
actually has signal — exactly backwards.** The guardrail must key on the **absolute positive
count** (refuse below ~30 fraud cases), as [10](10-agent-instruction-design.md) §2 specifies.
Recording this because the wrong version is the intuitive one.

---

---

## E8 — Does the LLM write correct DuckDB SQL? (the central unvalidated claim)

Same six questions, two system prompts, `openai/gpt-oss-120b` at temperature 0.

| Prompt | Executed successfully | Tokens |
|---|---|---:|
| **Naive** — "use standard SQL" (what the repo has today) | **5/6** | 3,306 |
| **DuckDB-aware** — names the dialect and its traps | **6/6** | 3,791 |

**The single failure was exactly the predicted one.** The naive prompt emitted
`TO_CHAR(date, 'YYYY-MM')` → *Catalog Error: Scalar Function with name to_char does not exist!*
The DuckDB-aware prompt used `strftime` and succeeded.

MotherDuck's claim — *"DuckDB has its own dialect and functions, and if you don't tell the model
to use them, it won't"* — is **confirmed empirically**. The fix costs ~80 extra tokens per call.

Both prompts handled the harder semantic traps correctly (refund exclusion, the three-way
`merchant_state` channel split), so the dialect is the dominant failure mode, not reasoning.

## E9 — Real agentic loop: token cost was over-estimated by 2.3×

Full LangGraph tool-calling loop with the hardened `run_sql`, three questions of rising difficulty:

| Question | LLM calls | SQL queries | Tokens | Time |
|---|---:|---:|---:|---:|
| Overall fraud rate | 2 | 1 | ~1,400 | 3 s |
| "Is fraud evenly distributed across geographies?" | 3 | 2 | 4,765 | 5.4 s |
| "Which categories are riskiest, and is it trustworthy?" | 6 | 5 | 12,559 | 70 s |
| **Average** | | | **6,242** | |

**The wiki estimated ~14,400 tokens/question → ~14 questions/day. The measured average is
6,242 → ~32 questions/day.** The hardest question did cost 12,559, so a session of only hard
questions gets ~16/day. Either way the constraint is real but looser than feared.

**Quality was genuinely good.** Unprompted, the agent computed Wilson confidence intervals and
**applied the ≥30-fraud-cases reliability rule from the system prompt**, writing *"Only
categories with ≥ 30 fraud cases are shown."* The guardrail works as an instruction.

## E10 — Verifying the agent's numbers, and a trap it caught that I missed

Never trust an LLM's arithmetic. Every figure it reported was checked against the database.

**All of them were exactly right** — 8,914,963 / 13,332 / 0.1495%, and the full top-risk table.

But its MCC results disagreed with an earlier benchmark, and **the agent was more correct**:

> **`mcc_description` is not unique.** "Passenger Railways" maps to **two different MCC codes**
> with very different risk: **3722** (10,414 txns, 1.45%) and **4112** (1,463 txns, 5.95%).
> Grouping by description merges them into a misleading blended **2.004%** — which is exactly
> what [02](02-data-dictionary.md) originally reported as a headline finding.
> **Group by `mcc`, not by `mcc_description`.**

The corrected top-risk list (≥30 fraud cases, grouped by code):

| MCC | Description | n | Fraud | Rate |
|---|---|---:|---:|---:|
| 4411 | Cruise Lines | 276 | 165 | **59.78%** |
| 5733 | Music Stores – Musical Instruments | 204 | 76 | **37.25%** |
| 5045 | Computers & Peripherals | 1,883 | 204 | 10.83% |
| 5732 | Electronics Stores | 4,689 | 402 | 8.57% |
| 5094 | Precious Stones and Metals | 3,525 | 242 | 6.87% |

Far more striking than the 2.004% the wiki previously led with.

## E11 — Full stack end-to-end: three integration bugs, all real

`npm install` succeeded cleanly in 11 s and `npm run build` compiled with no errors —
**the predicted peer-dependency fight did not happen.** Next.js 16.3.2 + React 19.2.8 +
CopilotKit 1.69 build fine together.

Then, wiring the Next.js UI to a DuckDB-backed LangGraph agent over AG-UI, three failures in
sequence — each surfacing in the browser only as an unhelpful **"terminated"**:

1. **A checkpointer is mandatory, not optional.** The adapter calls `graph.aget_state(config)`;
   a plain `.compile()` raises `ValueError: No checkpointer set`.
   *This reclassifies [07](07-roadmap.md) Phase 8 — checkpointing is a Phase 5 prerequisite.*
2. **Sync `SqliteSaver` does not work.** AG-UI is async and calls `aget_tuple()` →
   `NotImplementedError: The SqliteSaver does not support async methods.`
3. **`AsyncSqliteSaver` cannot be built at module scope** — its `__init__` calls
   `asyncio.get_running_loop()` → `RuntimeError: no running event loop`.

**The working pattern** (in `tools/experiments/e11_server.py`): construct everything inside an
async `main()`, using the saver as an async context manager, and serve uvicorn from within it.

```python
async def main():
    async with AsyncSqliteSaver.from_conn_string(DB) as checkpointer:
        graph = graph_builder.compile(checkpointer=checkpointer)
        app = FastAPI()
        add_langgraph_fastapi_endpoint(app=app,
            agent=LangGraphAGUIAgent(name="finbot_agent", graph=graph), path="/")
        await uvicorn.Server(uvicorn.Config(app, port=8123)).serve()

asyncio.run(main())
```

**Result: the full path works** — Next.js → CopilotKit runtime → AG-UI → FastAPI → LangGraph →
Groq → DuckDB → back. The chat rendered a correct markdown table (Chip 3,202,776 / 0.0992%,
Online 1,043,975 / 0.8409%, Swipe 4,668,212 / 0.0295%) and added, unprompted:
*"All three categories have well-above 30 fraud cases, so the rates are reliable."*

Two incidental findings: CopilotKit Runtime enables **anonymous telemetry by default**
(`COPILOTKIT_TELEMETRY_DISABLED=true` to opt out), and the dev UI ships a **Web Inspector**
panel with an AG-UI event stream — useful for debugging Phase 6.

## Correction accepted: CopilotKit state rendering IS supported on LangGraph

[05](05-research-agent-stack.md) flagged this as unverified and Phase 6 carried a fallback plan.
**That hedge was wrong** — the docs exist at
`docs.copilotkit.ai/langgraph-python/generative-ui/state-rendering`, verified in-browser, with a
complete Python + React example using `CopilotKitMiddleware`, `StateStreamingMiddleware`, and a
frontend `useAgent({ agentId, updates: [UseAgentUpdate.OnStateChanged, ...] })` subscription.

Note the current hook is **`useAgent`**, not the v1-era `useCoAgentStateRender`.
**Phase 6 is unblocked and needs no fallback.**

---

## What these experiments changed

| Decision | Before | After |
|---|---|---|
| Storage layout | normalised tables or Parquet | **pre-joined `fact_transactions`** — the only option that fits |
| Semantic layer rationale | correctness | **correctness + the thing that makes free hosting work** |
| Option A viability | unvalidated, flagged as top risk | **validated under a conservative proxy** |
| Runtime dependencies | unexamined | **drop `pandas` from the runtime** (43 MB) |
| Read-only pattern | `connect(read_only=True)` | **`:memory:` + `ATTACH … (READ_ONLY)`**, or views can't be created |
| Flagship demo | credit-score / findex join | **geographic fraud → Italy breach signature** |
| `merchant_state` NULL | "a data-quality trap" | **the online channel; label it** |
| Refusal guardrail | CI width was a candidate | **absolute positive count only** |
| Token budget | ~14,400/question → 14 questions/day | **6,242/question → ~32 questions/day** |
| Dialect prompt | recommended on vendor advice | **empirically required** — naive prompt fails on `to_char` |
| Checkpointer | Phase 8 "nice to have" | **Phase 5 prerequisite** — AG-UI won't run without one |
| CopilotKit state rendering | unverified, fallback planned | **confirmed supported; hedge removed** |
| Frontend install | "expect a peer-dep fight" | **installs and builds clean** |
| Grouping key | `mcc_description` | **`mcc`** — descriptions are not unique |

## Not yet tested

- Real deployment on Linux with a hard 512 MB cgroup — the proxy is conservative but not the thing.
- Charts. Everything so far renders as markdown tables; `useRenderTool` is unexercised.
- The reasoning-trace panel (Phase 6) — documented and unblocked, but not built.
- Remote Parquet over HTTPS range requests (moot if the pre-joined file is bundled).
- Behaviour under a Groq 429; the rate-limit path has never been triggered.
