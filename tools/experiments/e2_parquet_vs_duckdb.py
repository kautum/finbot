"""E2: Parquet-backed views vs a materialised .duckdb file, under tight memory.

Hypothesis: querying Parquet streams column chunks and keeps RSS far below the
mmap-everything profile of a native .duckdb file, at some cost in latency.
This decides the storage format for a memory-constrained host.
"""
import duckdb, time, resource, os, sys

PQ = os.environ.get("FINBOT_PQ", "/Users/kpkautum/.claude/jobs/b441694d/tmp/pq")
MEM = sys.argv[1] if len(sys.argv) > 1 else "300MB"
THREADS = sys.argv[2] if len(sys.argv) > 2 else "1"


def rss_mb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 1e6 if sys.platform == "darwin" else r / 1e3


total_pq = sum(os.path.getsize(os.path.join(PQ, f)) for f in os.listdir(PQ))
print(f"parquet set: {total_pq/1e6:.1f} MB | memory_limit={MEM} threads={THREADS}")
print(f"RSS start: {rss_mb():.0f} MB")

con = duckdb.connect(":memory:")
con.execute(f"SET memory_limit='{MEM}'")
con.execute(f"SET threads={THREADS}")
for t in ["transactions", "fraud_labels", "users", "cards", "mcc_codes", "findex", "databank"]:
    con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{PQ}/{t}.parquet')")
print(f"RSS after views created: {rss_mb():.0f} MB")

Q = {
    "Q1 fraud rate (8.9M)": "SELECT count(*), sum(is_fraud::INT) FROM fraud_labels",
    "Q2 fraud by MCC (3-join)": """SELECT m.description, count(*) n, sum(f.is_fraud::INT) fr
   FROM transactions t JOIN fraud_labels f ON t.id=f.transaction_id
   JOIN mcc_codes m ON t.mcc=m.mcc_code GROUP BY 1 HAVING count(*)>10000
   ORDER BY sum(f.is_fraud::INT)*1.0/count(*) DESC LIMIT 5""",
    "Q3 credit bands (4-join)": """SELECT CASE WHEN u.credit_score<600 THEN 'poor'
     WHEN u.credit_score<700 THEN 'fair' WHEN u.credit_score<800 THEN 'good' ELSE 'excellent' END b,
   count(*), round(100.0*sum(f.is_fraud::INT)/count(*),3)
   FROM transactions t JOIN fraud_labels f ON t.id=f.transaction_id JOIN cards c ON t.card_id=c.id
   JOIN users u ON c.client_id=u.id GROUP BY 1""",
    "Q4 monthly series": """SELECT date_trunc('month',t.date) m, count(*), sum(f.is_fraud::INT)
   FROM transactions t JOIN fraud_labels f ON t.id=f.transaction_id GROUP BY 1 ORDER BY 1""",
    "Q5 window rank": """SELECT client_id, sum(amount) tot, rank() OVER (ORDER BY sum(amount) DESC) r
   FROM transactions GROUP BY 1 ORDER BY r LIMIT 5""",
    "Q6 use_chip fraud": """SELECT t.use_chip, count(*) n, sum(f.is_fraud::INT) fr
   FROM transactions t JOIN fraud_labels f ON t.id=f.transaction_id GROUP BY 1""",
    "Q7 WORST CASE full scan": "SELECT count(*), avg(amount), count(DISTINCT merchant_id) FROM transactions",
}

worst = 0.0
for name, sql in Q.items():
    t = time.time()
    try:
        con.execute(sql).fetchall()
        ms = (time.time() - t) * 1000
        worst = max(worst, ms)
        print(f"  {name:28s} {ms:8.0f} ms   RSS {rss_mb():.0f} MB")
    except Exception as e:
        print(f"  {name:28s} FAILED: {str(e)[:90]}")

print(f"\nPEAK RSS: {rss_mb():.0f} MB   SLOWEST QUERY: {worst:.0f} ms")
