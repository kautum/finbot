# 02 — Data Dictionary (measured 2026-08-23)

Every number below was measured, not estimated. Almost all come from DuckDB 1.5.5 run over the
raw files in `Datasets/`; the exceptions are the `databank` reshape (pandas, because the source
is `.xlsx`) and the file sizes (the filesystem). **The scripts that produced every figure on
this page are committed at [`tools/profiling/`](../tools/profiling/)** — see §7.

## 1. Tables at a glance

| Table | Rows | Source file | Raw size | Parquet+zstd |
|---|---:|---|---:|---:|
| `transactions` | **13,305,915** | `financial_transactions/transactions_data.csv` | 1,258 MB | **179.80 MB** |
| `fraud_labels` | **8,914,963** | `financial_transactions/train_fraud_labels.json` | 159 MB | **34.54 MB** |
| `databank` | **302,008** | `Databank-wide.xlsx` (melted, nulls dropped) | 4.5 MB | **1.40 MB** |
| `findex_2025` | **8,577** | `GlobalFindexDatabase2025.csv` | 17.6 MB | **3.96 MB** |
| `cards` | **6,146** | `financial_transactions/cards_data.csv` | 0.5 MB | **0.12 MB** |
| `users` | **2,000** | `financial_transactions/users_data.csv` | 0.16 MB | **0.06 MB** |
| `mcc_codes` | **109** | `financial_transactions/mcc_codes.json` | 4.7 KB | **0.00 MB** |
| **TOTAL** | **22,539,718** | | **1.3 GB** | **219.9 MB** |

A single consolidated `.duckdb` file containing all seven tables is **329 MB**.

> **This is the single most consequential fact in the project.** The entire dataset is
> 220 MB in a columnar format. Every hosting failure so far came from trying to put it in a
> row-store, where per-row overhead inflates it to an estimated 2–4 GB. See [03](03-infrastructure-decision.md).

## 2. `transactions` — the core fact table

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT | PK. Joins to `fraud_labels.transaction_id`. |
| `date` | TIMESTAMP | minute resolution |
| `client_id` | BIGINT | -> `users.id` |
| `card_id` | BIGINT | -> `cards.id` |
| `amount` | **VARCHAR** | **`"$-77.00"` — dollar-sign string, MUST be parsed** |
| `use_chip` | VARCHAR | 3 values |
| `merchant_id` | BIGINT | 74,831 distinct; no merchant dimension table exists |
| `merchant_city` | VARCHAR | |
| `merchant_state` | VARCHAR | 199 distinct. US 2-letter codes **plus full country names** (`Mexico` 27,401 · `Canada` 10,647 · `Italy` 7,081 · `United Kingdom` 4,482 · …). **11.75% NULL (1,563,700 rows).** |
| `zip` | DOUBLE | should be INTEGER/VARCHAR |
| `mcc` | BIGINT | -> `mcc_codes.mcc_code` |
| `errors` | VARCHAR | NULL for 13,094,522 of 13,305,915 rows (98.4%) |

- **Date range**: 2010-01-01 00:01 → 2019-10-31 23:59. Just under 10 years, evenly spread
  (1.24M–1.40M rows/year, 2019 partial at 1.16M).
- **Distinct**: 1,219 clients · 4,071 cards · 74,831 merchants · 109 MCCs · 199 states.
- **Amount** (after parsing): min −500.00, max 6,820.20, mean 42.98, median 28.99.
  **660,054 rows are negative** (refunds/payments) — these must be excluded or handled
  explicitly in any "spend" metric, or totals will be understated.
- **`use_chip`**: Swipe 6,967,185 · Chip 4,780,818 · Online 1,557,912.
- **`errors`** top values: `Insufficient Balance` 130,902 · `Bad PIN` 32,119 ·
  `Technical Glitch` 26,271 · `Bad Card Number` 7,767 · `Bad Expiration` 6,161.

### Data-quality traps for the agent
1. `amount` is a **string with a `$`**. Unparsed, `AVG(amount)` errors or returns garbage.
   Fix at ETL time: `TRY_CAST(replace(amount,'$','') AS DECIMAL(10,2))`.
   Verified: **0 rows fail to parse** with this expression.
2. Negative amounts silently distort every spend aggregate.
3. **`merchant_state` encodes three different things in one column** — and this is the most
   valuable field in the dataset once you see it ([13](13-experiments.md) E7):
   - a **US 2-letter state code** → domestic, in-person
   - a **full country name** (`Mexico`, `Canada`, `Italy`, …) → foreign merchant
   - **NULL** → **not missing data: this is the online channel.** 1,043,975 of the 1,047,865
     NULLs in the labeled set are `Online Transaction`.

   Fraud rates differ by **353×** across the three (0.0158% / 0.8378% / 5.577%). A naive
   `GROUP BY merchant_state` drops the online segment entirely and puts `CA` beside `Canada`.
   **Derive a `channel` column at ETL time** (`domestic` / `foreign` / `online`) — it is the
   single highest-value transformation available.
4. **`findex` indicator columns are `VARCHAR`, not numeric.** `avg(account_t_d)` fails with a
   binder error; `TRY_CAST(... AS DOUBLE)` is required throughout.
5. `zip` as DOUBLE renders as `58523.0`.

## 3. `fraud_labels` — and the rare-event problem

| Column | Type |
|---|---|
| `transaction_id` | BIGINT -> `transactions.id` |
| `is_fraud` | `"Yes"`/`"No"` (store as BOOLEAN) |

- 8,914,963 rows. **`Yes` = 13,332. `No` = 8,901,631.**
- **Overall fraud rate = 0.1495%** (about 1 in 669).
- **Coverage is partial**: only 8,914,963 of 13,305,915 transactions have a label.
  **4,390,952 transactions (33.0%) are unlabeled.**
- The labeled fraction is **67.0% in every single year**, 2010 through 2019 (66.9–67.1%).
  That uniformity is strong evidence the holdout is a **random sample, not a time cut** —
  so aggregate rates computed on the labeled subset generalise, and there is no need to
  restrict analysis to a particular period.

> **Critical for correctness.** Any fraud-rate metric MUST be computed over the labeled
> subset only (`JOIN fraud_labels`), never over all transactions. A `LEFT JOIN` with
> `COALESCE(is_fraud,false)` understates the true rate by ~33%. The semantic layer must
> encode this — it is exactly the class of error a semantic layer exists to prevent.

### Fraud by year (labeled subset)
| Year | Labeled txns | Fraud | Rate |
|---|---:|---:|---:|
| 2010 | 831,529 | 2,573 | 0.309% |
| 2011 | 863,428 | 37 | 0.004% |
| 2012 | 885,421 | 923 | 0.104% |
| 2013 | 907,304 | 1,337 | 0.147% |
| 2014 | 915,073 | 664 | 0.073% |
| 2015 | 930,224 | 2,189 | 0.235% |
| 2016 | 932,762 | 2,448 | 0.262% |
| 2017 | 937,284 | 172 | 0.018% |
| 2018 | 934,599 | 1,629 | 0.174% |
| 2019 | 777,339 | 1,360 | 0.175% |

The 2011 and 2017 troughs (0.004%, 0.018%) are almost certainly synthetic-generation
artifacts, not signal. Worth knowing before the agent confidently narrates a story about them.

## 4. Reference tables

**`users`** (2,000): `id, current_age, retirement_age, birth_year, birth_month, gender,
address, latitude, longitude, per_capita_income, yearly_income, total_debt, credit_score,
num_credit_cards`. Money columns are `$`-prefixed strings, same trap as `amount`.

**`cards`** (6,146): `id, client_id, card_brand, card_type, card_number, expires, cvv,
has_chip, num_cards_issued, credit_limit, acct_open_date, year_pin_last_changed,
card_on_dark_web`.

> `card_number` and `cvv` are synthetic but **look exactly like real PANs and CVVs**.
> Never render them in the UI, never let the agent `SELECT` them. Drop or mask at ETL.
> This is a demo-safety issue: a screenshot showing a 16-digit card number reads badly.

**`mcc_codes`** (109): `mcc_code, description`.

### Referential integrity — verified clean
- Orphan `card_id` in transactions: **0**
- Orphan `client_id` in transactions: **0**
- But: only **1,219 of 2,000 users** and **4,071 of 6,146 cards** appear in transactions.
  781 users and 2,075 cards have zero activity. An "average transactions per user" metric
  gives **6,653** (all registered users) or **10,915** (active users only) depending on the
  denominator — a textbook case for the semantic layer.

## 5. Macro tables (no join key to the transaction data)

**`findex_2025`** (8,577 rows x 438 cols): World Bank Global Findex. 174 countries,
years 2011–2024. Key cols: `countrynewwb, codewb, year, pop_adult, regionwb24_hi,
incomegroupwb24, group, group2`, then ~430 `fin*` indicator columns.

**`databank`** (302,008 rows long-format): melted from 642 x 1,232 wide. 183 countries,
1,226 indicator codes, years 2011–2021. Columns: `countrynewwb, codewb, year,
regionwb21_hi, incomegroupwb21, pop_adult, indicator_code, value`.

### There IS a usable join — and it is the most interesting thing in the dataset

`transactions.merchant_state` contains **full country names** for non-US merchants, and those
match `findex.countrynewwb` exactly. **104 distinct countries join.** Verified:

```sql
SELECT count(DISTINCT t.merchant_state)
FROM transactions t JOIN findex fx ON t.merchant_state = fx.countrynewwb;  -- 104
```

This links micro-level card behaviour to national financial-inclusion indicators — a genuinely
cross-domain analysis, and the single most distinctive thing this dataset supports.

> **Three cautions, all measured ([13](13-experiments.md) E6).**
> 1. The naive join fans out **55.9×** — 3,102,332 joined rows from **55,485 real transactions**,
>    because `findex` holds ~49–56 rows per country (years × demographic groups). Aggregate
>    transactions **first**, then join, or filter findex to one `year` and `group`.
> 2. It reaches only **55,485 transactions — 0.4% of the labeled set** (the non-US slice), and
>    most matched countries have **zero** fraud. Real, but analytically thin: treat it as a
>    capability demonstration, not a headline finding.
> 3. `findex` indicator columns are `VARCHAR`; cast before aggregating.
>
> The agent must be told all three, or it will produce a confidently inflated number.

There is no indicator-code dictionary — `fin11a` is opaque. Sourcing one is a small,
high-value task; see [07](07-roadmap.md) Phase 1.

## 6. Query performance — measured on the 329 MB DuckDB file

Conditions, stated precisely: **local laptop (multi-core, DuckDB's default thread count), one
read-only connection reused across all six queries, against a file written seconds earlier —
so the OS page cache was warm.** These are best-case numbers. Treat them as an upper bound on
what the engine can do, not as a prediction of production latency on a 0.1 CPU container.
Full 22.5M rows:

| Query | Time |
|---|---:|
| Overall fraud rate (8.9M rows) | **3 ms** |
| Fraud rate by MCC, 3-table join, HAVING | **106 ms** |
| Fraud by credit-score band, 4-table join | **125 ms** |
| Monthly volume+fraud time series | **129 ms** |
| Per-client totals + RANK() window | **9 ms** |
| Fraud by `use_chip` (A/B shape) | **103 ms** |

Nothing exceeded 130 ms. Scanning the raw 1.2 GB CSV to count and profile took 5.8 s.

## 7. Reproducing this

Scripts are committed at [`tools/profiling/`](../tools/profiling/). Run in order with
`python3`; they need `duckdb>=1.5` and `pandas`, and expect `Datasets/` at the repo root.

| Script | Produces |
|---|---|
| `01_profile_transactions.py` | §2 — row count, date range, cardinality, amount stats |
| `02_profile_fraud.py` | §3 — fraud counts, label coverage, fraud by year |
| `03_to_parquet.py` | §1 — Parquet conversion and sizes |
| `04_to_parquet_macro.py` | §1, §5 — databank reshape, total size |
| `05_benchmark.py` | §6 — builds the `.duckdb` file, times the six queries |
| `06_integrity.py` | §4 — join integrity, orphan checks, segment power |
| `07_verify_claims.py` | §8 — credit bands, `merchant_state` nulls, the findex join, label uniformity |

**Two gotchas that will bite anyone regenerating this:**
1. `train_fraud_labels.json` is a single 159 MB JSON object. DuckDB's `read_json` defaults to a
   16 MB `maximum_object_size` and rejects it. Pass `maximum_object_size=200000000`, then
   `unnest(map_keys(target))` / `unnest(map_values(target))` to explode the map.
2. `05_benchmark.py` originally printed only `r[:3]` per query, which silently truncated the
   four-band credit-score result to three. **Print full result sets when the output is a
   finding.**

## 8. Real findings already surfaced (use these in the demo)

Not invented — measured:

- **Channel is the strongest signal in the data — a 353× spread**
  ([13](13-experiments.md) E7): foreign merchant **5.577%** (59,512 txns) · online **0.8378%**
  (1,047,865) · domestic in-person **0.0158%** (7,807,586).
- **The Italy anomaly — the single best finding.** Of every foreign country with ≥500
  transactions, **only Italy has any fraud at all**. Zero from 2010–2016, then **59.7% (2017),
  89.9% (2018), 85.1% (2019)**, across **65 merchants and 424 clients**. A textbook compromised-
  merchant-cluster signature with a datable onset. (Synthetic data — say so when presenting.)
- **Online transactions are 28× more fraud-prone than swipe.**
  Online 0.8409% · Chip 0.0992% · Swipe 0.0295%. Statistically confirmed: **z = 177.9, p ≈ 0**,
  Online 95% CI [0.8236%, 0.8586%] vs Swipe [0.0280%, 0.0311%] — non-overlapping.
- **Highest-fraud merchant categories** (≥30 fraud cases, **grouped by `mcc` code**):
  Cruise Lines **59.78%** (165/276) · Music Stores **37.25%** (76/204) ·
  Computers & Peripherals **10.83%** · Electronics Stores **8.57%** ·
  Precious Stones and Metals **6.87%**. Up to **400× baseline**.

  > **Trap: `mcc_description` is not unique.** "Passenger Railways" covers two codes — 3722
  > (10,414 txns, 1.45%) and 4112 (1,463 txns, 5.95%) — which grouping by description blends
  > into a misleading 2.004%. An earlier version of this page reported that blended figure as a
  > headline finding. **Always group by `mcc`.** ([13](13-experiments.md) E10)
- **Credit score does not predict fraud victimhood** — all four bands, full result:

  | Band | Transactions | Fraud rate |
  |---|---:|---:|
  | good (700–799) | 4,778,858 | 0.155% |
  | fair (600–699) | 2,843,966 | 0.146% |
  | excellent (800+) | 762,930 | 0.143% |
  | **poor (<600)** | **529,209** | **0.124%** |

  The whole range is 0.124–0.155% — no meaningful spread. And the *lowest* fraud rate belongs
  to the **poor** band, the opposite of the intuitive expectation. Strong demo material
  precisely because it contradicts the obvious hypothesis.
  **Report all four bands.** An earlier draft of this wiki listed only three because the
  benchmark script truncated its output, which would have left the demo unable to answer
  "what about sub-600?".

### Statistical-power warning
Of 109 MCC segments, **22 already have fewer than 10 fraud cases at full scale.** Fraud is
rare enough that segmentation runs out of power fast. Any downsampling makes this dramatically
worse and is the main technical argument against the sampling plan — see
[03](03-infrastructure-decision.md) §5.

> **Gate on the absolute count of fraud cases, never on confidence-interval width.**
> [13](13-experiments.md) E6 falsified the intuitive design: *Tolls and Bridge Fees* has
> **0 fraud in 451,814 transactions** and therefore a CI only **0.001 pp** wide, while
> *Department Stores* (2,251 fraud, real signal) has a **0.058 pp** interval. A width-based
> rule would confidently report "Tolls have 0% fraud" and reject the segment that actually has
> signal — exactly backwards. Refuse below ~30 positive cases.
