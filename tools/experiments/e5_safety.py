"""E5: Do the safety mechanisms in roadmap Phase 2 actually work?

Validates three claims made in the wiki:
  1. duckdb read_only=True genuinely blocks DDL/DML at the driver, not by convention
  2. DuckDB has no statement_timeout, so a thread-based wall-clock wrapper is needed
  3. A SELECT/WITH-only guard catches what read_only would let through anyway
"""
import duckdb, time, os, sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FTimeout

DB = os.environ.get("FINBOT_FACT", "/Users/kpkautum/.claude/jobs/b441694d/tmp/fact.duckdb")

print("=" * 62)
print("1. READ-ONLY ENFORCEMENT AT THE DRIVER")
print("=" * 62)
con = duckdb.connect(DB, read_only=True)
ATTACKS = [
    "DROP TABLE fact_transactions",
    "DELETE FROM fact_transactions WHERE 1=1",
    "UPDATE fact_transactions SET is_fraud = true",
    "CREATE TABLE evil AS SELECT 1",
    "INSERT INTO fact_transactions VALUES (1)",
]
for sql in ATTACKS:
    try:
        con.execute(sql)
        print(f"  !! NOT BLOCKED: {sql}")
    except Exception as e:
        print(f"  blocked: {sql[:42]:45s} -> {type(e).__name__}")

print("\n  control - a SELECT still works:",
      con.execute("SELECT count(*) FROM fact_transactions").fetchone())

print("\n" + "=" * 62)
print("2. IS THERE A STATEMENT TIMEOUT?")
print("=" * 62)
for stmt in ["SET statement_timeout='1s'", "SET statement_timeout=1000"]:
    try:
        con.execute(stmt)
        print(f"  {stmt} -> ACCEPTED")
    except Exception as e:
        print(f"  {stmt} -> rejected: {str(e)[:70]}")

print("\n" + "=" * 62)
print("3. THREAD-BASED WALL-CLOCK TIMEOUT WRAPPER")
print("=" * 62)

SLOW = """SELECT count(*) FROM fact_transactions a
          JOIN fact_transactions b ON a.client_id = b.client_id
          WHERE a.amount > 0 AND b.amount > 0"""


def run_with_timeout(conn, sql, seconds):
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(lambda: conn.execute(sql).fetchall())
        try:
            return fut.result(timeout=seconds), None
        except FTimeout:
            conn.interrupt()
            try:
                fut.result(timeout=5)
            except Exception:
                pass
            return None, "timeout"
        except Exception as e:
            return None, f"error: {type(e).__name__}"


t = time.time()
res, err = run_with_timeout(con, SLOW, 3)
print(f"  deliberately expensive self-join, 3s budget -> {err or 'completed'} "
      f"after {time.time()-t:.1f}s")

t = time.time()
res, err = run_with_timeout(con, "SELECT count(*) FROM fact_transactions", 3)
print(f"  cheap query, 3s budget -> {err or 'completed'} in {(time.time()-t)*1000:.0f} ms, {res}")

print("\n  connection still usable after interrupt:",
      con.execute("SELECT 1").fetchone())

print("\n" + "=" * 62)
print("4. SELECT/WITH-ONLY GUARD (defence in depth)")
print("=" * 62)


def is_read_only_sql(q: str) -> bool:
    s = q.strip().lstrip("(").upper()
    return s.startswith("SELECT") or s.startswith("WITH") or s.startswith("DESCRIBE")


for q in ["SELECT 1", "WITH x AS (SELECT 1) SELECT * FROM x", "DESCRIBE fact_transactions",
          "DROP TABLE x", "  delete from x", "PRAGMA database_list", "ATTACH 'x.db'"]:
    print(f"  {'ALLOW' if is_read_only_sql(q) else 'REJECT'}  {q[:45]}")
