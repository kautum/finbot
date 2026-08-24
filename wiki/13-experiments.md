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

## Not yet tested

- Real deployment on Linux with a hard 512 MB cgroup — the proxy is conservative but not the thing.
- Any LLM call. No prompt, dialect handling, or tool-calling behaviour has been exercised;
  that needs the Groq key and is the natural next experiment.
- Frontend against backend ([07](07-roadmap.md) Phase 5).
- Remote Parquet over HTTPS range requests (moot if the pre-joined file is bundled).
