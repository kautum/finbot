"""Build the Finbot data store: raw CSV/JSON -> Parquet -> one pre-joined fact table.

Why pre-joined: experiment E3 (wiki/13) measured the normalised layout at 731 MB peak RSS,
which does not fit a 512 MB free host. Pre-joined it is 183 MB and 10x faster.

Run:  uv run python tools/etl/build_fact.py
Idempotent: skips stages whose output already exists. Pass --force to rebuild.
"""
import duckdb, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.environ.get("FINBOT_RAW", os.path.join(ROOT, "Datasets"))
TXN = os.path.join(RAW, "financial_transactions")
PQ = os.environ.get("FINBOT_PQ", os.path.join(ROOT, "data", "pq"))
OUT = os.environ.get("FINBOT_DB", os.path.join(ROOT, "data", "finbot.duckdb"))
FORCE = "--force" in sys.argv

# Measured in wiki/02. The load is wrong if any of these drift.
EXPECTED = {"transactions": 13_305_915, "labeled": 8_914_963, "fraud": 13_332}


def stage_parquet(con):
    """Typed, cleaned Parquet. Fixes the string-money and string-boolean bugs at the source."""
    os.makedirs(PQ, exist_ok=True)
    t = time.time()

    def copy(name, select, opts=""):
        path = f"{PQ}/{name}.parquet"
        if os.path.exists(path) and not FORCE:
            return
        con.execute(f"COPY ({select}) TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD{opts})")
        print(f"  wrote {name}.parquet {os.path.getsize(path)/1e6:.1f} MB")

    # Sorted by date: row-group min/max pruning is useless on unsorted data, and date
    # filters are the dominant analyst query shape.
    copy("transactions", f"""
      SELECT id, date, client_id, card_id,
             TRY_CAST(replace(replace(amount,'$',''),',','') AS DECIMAL(10,2)) AS amount,
             use_chip, merchant_id, merchant_city, merchant_state,
             TRY_CAST(zip AS INTEGER) AS zip, mcc, errors
      FROM read_csv_auto('{TXN}/transactions_data.csv', sample_size=200000)
      ORDER BY date""", ", ROW_GROUP_SIZE 1000000")

    copy("fraud_labels", f"""
      SELECT unnest(map_keys(target))::BIGINT AS transaction_id,
             unnest(map_values(target))='Yes'  AS is_fraud
      FROM read_json('{TXN}/train_fraud_labels.json',
                     columns={{'target':'MAP(VARCHAR,VARCHAR)'}},
                     maximum_object_size=200000000)""")

    # cards_data.csv contains card_number and cvv. Synthetic, but they look exactly like
    # real PANs/CVVs -- they must never reach a screenshot, so they are dropped here.
    copy("cards", f"""
      SELECT id, client_id, card_brand, card_type,
             TRY_CAST(replace(credit_limit,'$','') AS INTEGER) AS credit_limit,
             has_chip, num_cards_issued, year_pin_last_changed
      FROM read_csv_auto('{TXN}/cards_data.csv', sample_size=-1)""")

    copy("users", f"""
      SELECT id, current_age, gender, credit_score, num_credit_cards,
             TRY_CAST(replace(yearly_income,'$','') AS INTEGER)  AS yearly_income,
             TRY_CAST(replace(total_debt,'$','')    AS INTEGER)  AS total_debt,
             address, latitude, longitude
      FROM read_csv_auto('{TXN}/users_data.csv', sample_size=-1)""")

    # mcc_codes.json is one flat object, which DuckDB reads as a single 109-column row.
    # UNPIVOT turns those columns back into rows.
    copy("mcc_codes", f"""
      SELECT mcc_code::INTEGER AS mcc_code, description
      FROM (UNPIVOT (SELECT * FROM read_json('{TXN}/mcc_codes.json'))
            ON COLUMNS(*) INTO NAME mcc_code VALUE description)""")

    copy("findex", f"SELECT * FROM read_csv_auto('{RAW}/GlobalFindexDatabase2025.csv', sample_size=-1)")

    total = sum(os.path.getsize(f"{PQ}/{f}") for f in os.listdir(PQ))
    print(f"parquet: {total/1e6:.1f} MB in {time.time()-t:.0f}s")


def stage_fact():
    """One denormalised table. No joins at query time = no memory blowup."""
    if os.path.exists(OUT) and not FORCE:
        print("fact table: already built, skipping")
        return
    if os.path.exists(OUT):
        os.remove(OUT)
    t = time.time()
    b = duckdb.connect(OUT)
    b.execute(f"""
      CREATE TABLE fact_transactions AS
      SELECT t.id, t.date, t.client_id, t.card_id, t.amount,
             t.use_chip, t.merchant_id, t.merchant_city, t.merchant_state, t.mcc, t.errors,
             f.is_fraud,
             m.description AS mcc_description,
             -- merchant_state mixes US 2-letter codes, full country names, and NULL for
             -- online. Treating it as one thing is the most dangerous trap in this dataset,
             -- so the ambiguity is resolved once, here, into two honest columns.
             CASE WHEN t.merchant_state IS NULL           THEN 'Online'
                  WHEN length(t.merchant_state) = 2       THEN 'In-person (domestic)'
                  ELSE 'In-person (foreign)' END          AS channel,
             CASE WHEN t.merchant_state IS NULL           THEN NULL
                  WHEN length(t.merchant_state) = 2       THEN 'United States'
                  ELSE t.merchant_state END               AS merchant_country,
             c.card_brand, c.card_type, c.credit_limit,
             u.current_age, u.gender, u.credit_score, u.yearly_income
      FROM      read_parquet('{PQ}/transactions.parquet') t
      JOIN      read_parquet('{PQ}/fraud_labels.parquet') f ON t.id  = f.transaction_id
      LEFT JOIN read_parquet('{PQ}/mcc_codes.parquet')    m ON t.mcc = m.mcc_code
      LEFT JOIN read_parquet('{PQ}/cards.parquet')        c ON t.card_id = c.id
      LEFT JOIN read_parquet('{PQ}/users.parquet')        u ON c.client_id = u.id
    """)
    # The unlabeled 33% are deliberately NOT stored as rows -- keeping them would double the
    # file for no analytical gain, and any fraud query touching them is wrong by ~33% anyway.
    # Only the coverage counts survive, so the agent can state the caveat honestly.
    b.execute(f"""CREATE TABLE data_coverage AS
      SELECT (SELECT count(*) FROM read_parquet('{PQ}/transactions.parquet')) AS total_transactions,
             (SELECT count(*) FROM fact_transactions)                         AS labeled_transactions,
             (SELECT count(*) FROM read_parquet('{PQ}/transactions.parquet'))
             - (SELECT count(*) FROM fact_transactions)                       AS unlabeled_transactions""")
    b.execute(f"""CREATE TABLE findex AS SELECT * FROM read_parquet('{PQ}/findex.parquet')""")
    b.close()
    print(f"fact table: {os.path.getsize(OUT)/1e6:.1f} MB in {time.time()-t:.0f}s")


def verify():
    con = duckdb.connect(OUT, read_only=True)
    got = {
        "transactions": con.execute("SELECT total_transactions FROM data_coverage").fetchone()[0],
        "labeled":      con.execute("SELECT count(*) FROM fact_transactions").fetchone()[0],
        "fraud":        con.execute("SELECT sum(is_fraud::INT) FROM fact_transactions").fetchone()[0],
    }
    bad = {k: (v, EXPECTED[k]) for k, v in got.items() if v != EXPECTED[k]}
    for k, v in got.items():
        print(f"  {k:14s} {v:>12,}  {'OK' if k not in bad else f'EXPECTED {EXPECTED[k]:,}'}")

    # Row counts alone do not prove the LEFT JOINs landed -- a failed join leaves the count
    # intact and every joined column NULL. Check the columns, not just the rows.
    for col in ("mcc_description", "card_brand", "credit_score", "channel"):
        filled = con.execute(
            f"SELECT count({col}) FROM fact_transactions").fetchone()[0]
        pct = 100.0 * filled / got["labeled"]
        print(f"  {col:16s} {pct:6.2f}% populated  {'OK' if pct > 95 else 'JOIN FAILED'}")
        if pct <= 95:
            bad[col] = (pct, ">95%")
    print("  channel:", con.execute(
        "SELECT channel, count(*), round(100.0*sum(is_fraud::INT)/count(*),4) "
        "FROM fact_transactions GROUP BY 1 ORDER BY 3 DESC").fetchall())
    con.close()
    if bad:
        raise SystemExit(f"LOAD IS WRONG: {bad}")
    print("verified.")


if __name__ == "__main__":
    stage_parquet(duckdb.connect())
    stage_fact()
    verify()
