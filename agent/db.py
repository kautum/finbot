"""Read-only DuckDB access for the agent.

Two layers of protection, because a prompt is advice and this needs to be structural:
  1. the database is ATTACHed READ_ONLY, so DDL/DML fails at the driver
  2. a SELECT/WITH/DESCRIBE-only guard rejects anything else before it is sent

Plus governed views, which are the point of the whole design: the agent is pointed at
views where the known traps in this dataset are already excluded, so the wrong answer
is not reachable rather than merely discouraged.
"""
import os
import re

import duckdb
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("FINBOT_DB", os.path.join(ROOT, "data", "finbot.duckdb"))

QUERY_TIMEOUT_S = 20
MAX_ROWS = 200
MEMORY_LIMIT = os.environ.get("FINBOT_MEMORY_LIMIT", "350MB")

# Note: connect(read_only=True) also blocks CREATE VIEW, so the governed views could not
# be defined. Attaching read-only to an in-memory database gives both.
_GOVERNED_VIEWS = """
CREATE VIEW v_transactions AS
  SELECT * FROM fact.fact_transactions;

-- 660k transactions are refunds carried as negative amounts. Summing spend without
-- excluding them understates it, so "spend" gets its own view.
CREATE VIEW v_spend AS
  SELECT * FROM fact.fact_transactions WHERE amount > 0;

CREATE VIEW v_coverage AS
  SELECT * FROM fact.data_coverage;

CREATE VIEW v_findex AS
  SELECT * FROM fact.findex;
"""


def connect():
    con = duckdb.connect(":memory:")
    con.execute(f"SET memory_limit='{MEMORY_LIMIT}'")
    con.execute(f"ATTACH '{DB_PATH}' AS fact (READ_ONLY)")
    con.execute(_GOVERNED_VIEWS)
    return con


def is_read_only_sql(q: str) -> bool:
    s = q.strip().lstrip("(").upper()
    return s.startswith(("SELECT", "WITH", "DESCRIBE", "SUMMARIZE"))


_TRAILING_LIMIT = re.compile(r"\bLIMIT\s+\d+\s*(OFFSET\s+\d+\s*)?$", re.IGNORECASE)


def _add_limit(sql: str) -> str:
    """Cap unbounded results. An aggregate the model forgot to limit can still be huge."""
    stripped = sql.rstrip().rstrip(";").rstrip()
    # Matching on whitespace, not a literal " LIMIT ": the model formats SQL across lines,
    # so an existing limit usually arrives as "\nLIMIT 10" and a substring check misses it,
    # producing the syntax error "LIMIT 10 LIMIT 200".
    if _TRAILING_LIMIT.search(stripped):
        return stripped
    return f"{stripped} LIMIT {MAX_ROWS}"


def run(con, sql: str):
    """Execute one read-only statement. Returns (columns, rows, error)."""
    if not is_read_only_sql(sql):
        return None, None, "Only SELECT / WITH / DESCRIBE queries are allowed."
    sql = _add_limit(sql)
    # DuckDB has no statement_timeout, so the wall clock has to be enforced from outside.
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(lambda: con.execute(sql))
        try:
            cur = fut.result(timeout=QUERY_TIMEOUT_S)
            return [d[0] for d in cur.description], cur.fetchall(), None
        except FutureTimeout:
            con.interrupt()
            return None, None, f"Query exceeded the {QUERY_TIMEOUT_S}s limit. Narrow it down."
        except Exception as e:
            return None, None, f"{type(e).__name__}: {e}"


if __name__ == "__main__":
    c = connect()
    for bad in ["DROP TABLE fact.fact_transactions", "delete from v_spend", "ATTACH 'x.db'"]:
        assert run(c, bad)[2], f"guard let through: {bad}"
    cols, rows, err = run(c, "SELECT channel, count(*) FROM v_transactions GROUP BY 1")
    assert err is None and len(rows) == 3, (err, rows)
    assert "LIMIT 200" in _add_limit("SELECT 1")
    assert _add_limit("SELECT 1 LIMIT 5").endswith("LIMIT 5")
    # The multi-line form is what the model actually emits, and it used to double-limit.
    assert _add_limit("SELECT 1\nORDER BY x\nLIMIT 10;").endswith("LIMIT 10")
    assert _add_limit("SELECT 1 limit 10 offset 5").endswith("offset 5")
    assert _add_limit("SELECT 'LIMIT 3' AS s").endswith(f"LIMIT {MAX_ROWS}")
    print("db guards OK:", cols, rows)
