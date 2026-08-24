"""E3: Does pre-joining into one denormalised fact table fix the memory problem?

E1/E2 showed peak RSS ~690-730 MB regardless of storage format. The cost is the
repeated 13.3M x 8.9M hash join, not the file. Here we materialise the join once
(the "governed view", made physical) and re-run the same questions with zero joins.
"""
import duckdb, time, resource, os, sys

PQ = os.environ.get("FINBOT_PQ", "/Users/kpkautum/.claude/jobs/b441694d/tmp/pq")
OUT = os.environ.get("FINBOT_OUT", "/Users/kpkautum/.claude/jobs/b441694d/tmp/fact.duckdb")
MEM = sys.argv[1] if len(sys.argv) > 1 else "300MB"
THREADS = sys.argv[2] if len(sys.argv) > 2 else "1"


def rss_mb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 1e6 if sys.platform == "darwin" else r / 1e3


# ---- BUILD (one-off, done at ETL time on a real machine, not on the host) ----
if not os.path.exists(OUT):
    print("building denormalised fact table (one-off)...")
    b = duckdb.connect(OUT)
    t = time.time()
    b.execute(f"""
      CREATE TABLE fact_transactions AS
      SELECT t.id, t.date, t.client_id, t.card_id, t.amount,
             t.use_chip, t.merchant_id, t.merchant_city, t.merchant_state, t.mcc, t.errors,
             f.is_fraud,
             m.description               AS mcc_description,
             c.card_brand, c.card_type, c.credit_limit,
             u.current_age, u.gender, u.credit_score, u.yearly_income
      FROM read_parquet('{PQ}/transactions.parquet') t
      JOIN read_parquet('{PQ}/fraud_labels.parquet') f ON t.id = f.transaction_id
      LEFT JOIN read_parquet('{PQ}/mcc_codes.parquet') m ON t.mcc = m.mcc_code
      LEFT JOIN read_parquet('{PQ}/cards.parquet') c ON t.card_id = c.id
      LEFT JOIN read_parquet('{PQ}/users.parquet') u ON c.client_id = u.id
    """)
    print(f"  built in {time.time()-t:.1f}s, rows={b.execute('SELECT count(*) FROM fact_transactions').fetchone()[0]:,}")
    b.close()

print(f"fact file: {os.path.getsize(OUT)/1e6:.1f} MB | memory_limit={MEM} threads={THREADS}")
print(f"RSS start: {rss_mb():.0f} MB")

con = duckdb.connect(OUT, read_only=True)
con.execute(f"SET memory_limit='{MEM}'")
con.execute(f"SET threads={THREADS}")
print(f"RSS after connect: {rss_mb():.0f} MB")

Q = {
    "Q1 fraud rate": "SELECT count(*), sum(is_fraud::INT) FROM fact_transactions",
    "Q2 fraud by MCC": """SELECT mcc_description, count(*) n, sum(is_fraud::INT) fr
   FROM fact_transactions GROUP BY 1 HAVING count(*)>10000
   ORDER BY sum(is_fraud::INT)*1.0/count(*) DESC LIMIT 5""",
    "Q3 credit bands": """SELECT CASE WHEN credit_score<600 THEN 'poor' WHEN credit_score<700 THEN 'fair'
     WHEN credit_score<800 THEN 'good' ELSE 'excellent' END b,
   count(*), round(100.0*sum(is_fraud::INT)/count(*),3)
   FROM fact_transactions GROUP BY 1""",
    "Q4 monthly series": """SELECT date_trunc('month',date) m, count(*), sum(is_fraud::INT)
   FROM fact_transactions GROUP BY 1 ORDER BY 1""",
    "Q5 window rank": """SELECT client_id, sum(amount) tot, rank() OVER (ORDER BY sum(amount) DESC) r
   FROM fact_transactions GROUP BY 1 ORDER BY r LIMIT 5""",
    "Q6 use_chip fraud": """SELECT use_chip, count(*) n, sum(is_fraud::INT) fr,
   round(100.0*sum(is_fraud::INT)/count(*),4) pct FROM fact_transactions GROUP BY 1 ORDER BY pct DESC""",
    "Q7 WORST CASE full scan": "SELECT count(*), avg(amount), count(DISTINCT merchant_id) FROM fact_transactions",
}

worst = 0.0
for name, sql in Q.items():
    t = time.time()
    try:
        r = con.execute(sql).fetchall()
        ms = (time.time() - t) * 1000
        worst = max(worst, ms)
        print(f"  {name:24s} {ms:8.0f} ms   RSS {rss_mb():.0f} MB")
    except Exception as e:
        print(f"  {name:24s} FAILED: {str(e)[:90]}")

print(f"\nPEAK RSS: {rss_mb():.0f} MB   SLOWEST QUERY: {worst:.0f} ms")
print("Q6 (the demo query):", con.execute(Q["Q6 use_chip fraud"]).fetchall())
