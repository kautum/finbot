"""E8: Does the LLM generate correct DuckDB SQL? And does naming the dialect help?

Tests the central unvalidated claim: MotherDuck says "DuckDB has its own dialect and
functions, and if you don't tell the model to use them, it won't."

Runs the same questions under two system prompts - the naive one currently in the
repo ("standard SQL") and a DuckDB-specific one - and compares execution success,
error types, and token cost.

Run from agent/ with:  uv run python ../tools/experiments/e8_llm_sql.py
"""
import os, sys, time, json, re
import duckdb
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# load_dotenv() with no args walks up from THIS file's directory, which misses
# agent/.env when the script lives in tools/. Point at it explicitly.
_AGENT_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "agent", ".env")
load_dotenv(_AGENT_ENV)
FACT = os.environ.get("FINBOT_FACT", "/Users/kpkautum/.claude/jobs/b441694d/tmp/fact.duckdb")

con = duckdb.connect(":memory:")
con.execute(f"ATTACH '{FACT}' AS fact (READ_ONLY)")
con.execute("CREATE VIEW fact_transactions AS SELECT * FROM fact.fact_transactions")

SCHEMA = """TABLE fact_transactions (8,914,963 rows) - one row per labeled transaction
  id BIGINT, date TIMESTAMP (2010-01-01 to 2019-10-31),
  client_id BIGINT, card_id BIGINT,
  amount DECIMAL(10,2)   -- negative values are refunds
  use_chip VARCHAR       -- 'Swipe Transaction' | 'Chip Transaction' | 'Online Transaction'
  merchant_id BIGINT, merchant_city VARCHAR,
  merchant_state VARCHAR -- US 2-letter code, OR a full country name, OR NULL meaning online
  mcc BIGINT, errors VARCHAR,
  is_fraud BOOLEAN,
  mcc_description VARCHAR, card_brand VARCHAR, card_type VARCHAR, credit_limit VARCHAR,
  current_age BIGINT, gender VARCHAR, credit_score BIGINT, yearly_income VARCHAR
"""

NAIVE = f"""You are a data analyst. Write SQL to answer the question.
Available table:
{SCHEMA}
Use standard SQL. Return ONLY the SQL query, no explanation, no markdown fences."""

DUCKDB_AWARE = f"""You are a data analyst. Write SQL to answer the question.
Available table:
{SCHEMA}

The database is DuckDB, NOT PostgreSQL. Specifically:
- Use strftime(ts, fmt) / strptime(). to_char() and to_timestamp() DO NOT EXIST.
- date_trunc('month', ts), year(ts), month(ts) all work.
- QUALIFY and SELECT * EXCLUDE(col) are available.
- Do NOT use COUNT(DISTINCT x) OVER (...) - unreliable in DuckDB.
- Cast booleans to int with is_fraud::INT to sum them.
Return ONLY the SQL query, no explanation, no markdown fences."""

QUESTIONS = [
    ("simple aggregate", "How many transactions are there and what is the average amount?"),
    ("rate by group", "What is the fraud rate for each value of use_chip? Show counts too."),
    ("date formatting", "Show total transaction volume by month for 2018, formatted as a YYYY-MM string label."),
    ("channel trap", "Compare fraud rates between domestic US transactions, foreign-country transactions, and online transactions."),
    ("window / top-N", "Which 5 merchant categories have the highest fraud rate, among those with at least 10000 transactions?"),
    ("refund trap", "What is the total amount spent in 2019, excluding refunds?"),
]


def strip_sql(t: str) -> str:
    t = re.sub(r"^```(?:sql)?", "", t.strip(), flags=re.I | re.M)
    t = t.replace("```", "").strip()
    return t


def run_suite(label, system_prompt, llm):
    print("\n" + "=" * 70)
    print(f"  {label}")
    print("=" * 70)
    ok = 0
    toks = 0
    for name, q in QUESTIONS:
        try:
            t0 = time.time()
            resp = llm.invoke([("system", system_prompt), ("user", q)])
            latency = time.time() - t0
            usage = getattr(resp, "usage_metadata", None) or {}
            toks += usage.get("total_tokens", 0)
            sql = strip_sql(resp.content)
            try:
                rows = con.execute(sql).fetchmany(3)
                ok += 1
                preview = str(rows[:2])[:90]
                print(f"  [OK]   {name:18s} {latency:4.1f}s {usage.get('total_tokens',0):>5}tok  {preview}")
            except Exception as e:
                msg = str(e).split("\n")[0][:95]
                print(f"  [FAIL] {name:18s} {latency:4.1f}s {usage.get('total_tokens',0):>5}tok")
                print(f"         SQL: {sql[:110]}")
                print(f"         ERR: {msg}")
        except Exception as e:
            print(f"  [LLM ERROR] {name}: {str(e)[:110]}")
    print(f"\n  RESULT: {ok}/{len(QUESTIONS)} executed   total tokens: {toks:,}")
    return ok, toks


if __name__ == "__main__":
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    print(f"model: {model}")
    llm = ChatGroq(model=model, api_key=os.getenv("GROQ_API_KEY"), temperature=0)

    a_ok, a_tok = run_suite("A. NAIVE PROMPT ('use standard SQL') - what the repo has today", NAIVE, llm)
    b_ok, b_tok = run_suite("B. DUCKDB-AWARE PROMPT - what the wiki recommends", DUCKDB_AWARE, llm)

    print("\n" + "=" * 70)
    print(f"  naive:       {a_ok}/{len(QUESTIONS)}   {a_tok:,} tokens")
    print(f"  duckdb-aware:{b_ok}/{len(QUESTIONS)}   {b_tok:,} tokens")
    print(f"  total spent this run: {a_tok+b_tok:,} tokens of the 200,000/day free budget")
