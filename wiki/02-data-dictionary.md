# 02 — Data Dictionary (measured 2026-08-23)

Every number below was produced by running DuckDB 1.5.5 over the raw files in `Datasets/`.
None of it is estimated. Reproduce with the scripts described in §7.

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
| `merchant_state` | VARCHAR | 199 distinct (US states + country codes for online) |
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
2. Negative amounts silently distort every spend aggregate.
3. `zip` as DOUBLE renders as `58523.0`.

## 3. `fraud_labels` — and the rare-event problem

| Column | Type |
|---|---|
| `transaction_id` | BIGINT -> `transactions.id` |
| `is_fraud` | `"Yes"`/`"No"` (store as BOOLEAN) |

- 8,914,963 rows. **`Yes` = 13,332. `No` = 8,901,631.**
- **Overall fraud rate = 0.1495%** (about 1 in 669).
- **Coverage is partial**: only 8,914,963 of 13,305,915 transactions have a label.
  **4,390,952 transactions (33.0%) are unlabeled.**
  Labeled rows span the full 2010–2019 range, so this is a random-ish holdout, not a time cut.

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
  gives 6,650 or 10,915 depending on the denominator — a textbook case for the semantic layer.

## 5. Macro tables (no join key to the transaction data)

**`findex_2025`** (8,577 rows x 438 cols): World Bank Global Findex. 174 countries,
years 2011–2024. Key cols: `countrynewwb, codewb, year, pop_adult, regionwb24_hi,
incomegroupwb24, group, group2`, then ~430 `fin*` indicator columns.

**`databank`** (302,008 rows long-format): melted from 642 x 1,232 wide. 183 countries,
1,226 indicator codes, years 2011–2021. Columns: `countrynewwb, codewb, year,
regionwb21_hi, incomegroupwb21, pop_adult, indicator_code, value`.

> These two share no key with the transaction tables. They are a **second, parallel
> analytical thread** (national financial-inclusion trends), not a dimension to join.
> The agent must be told this explicitly or it will hallucinate a join. There is also no
> indicator-code dictionary — `fin11a` is opaque. Sourcing one is a small, high-value task.

## 6. Query performance — measured on the 329 MB DuckDB file

Local, laptop, single-threaded cold connection, full 22.5M rows:

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

Scripts used live in the job scratch dir and are not committed. To regenerate:
`duckdb` 1.5.5 + `read_csv_auto` for CSVs; for the fraud JSON you **must** pass
`maximum_object_size=200000000` to `read_json` (the file is one 159 MB JSON object and
DuckDB's 16 MB default rejects it), then
`unnest(map_keys(target))` / `unnest(map_values(target))` to explode the map.

## 8. Real findings already surfaced (use these in the demo)

Not invented — measured:

- **Online transactions are 28x more fraud-prone than swipe.**
  Online 0.8409% · Chip 0.0992% · Swipe 0.0295%. Large, clean, instantly legible.
- **Highest-fraud MCCs** (min 10k txns): Passenger Railways 2.004% · Gardening Supplies
  1.282% · Industrial Equipment 1.218% — all ~10x the 0.1495% baseline.
- **Credit score barely predicts fraud victimhood**: good 0.155% · fair 0.146% ·
  excellent 0.143%. A genuinely interesting negative result — good demo material because
  it contradicts the obvious hypothesis.

### Statistical-power warning
Of 109 MCC segments, **22 already have fewer than 10 fraud cases at full scale.** Fraud is
rare enough that segmentation runs out of power fast. Any downsampling makes this
dramatically worse and is the main technical argument against the sampling plan — see
[03](03-infrastructure-decision.md) §5.
