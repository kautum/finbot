"""E9: Real multi-step agentic loop - token cost and reasoning quality.

E8 measured single-shot SQL (~630 tok/question). The wiki estimated ~14,400 tokens
for a multi-step question, giving ~14 questions/day on Groq's 200k free budget.
This measures the real number with a full LangGraph tool-calling loop, and checks
whether the agent can actually chain queries to reach the Italy finding.

Run from agent/ with:  uv run python ../tools/experiments/e9_agent_loop.py
"""
import os, time, re
import duckdb
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FTimeout

_AGENT_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "agent", ".env")
load_dotenv(_AGENT_ENV)
FACT = os.environ.get("FINBOT_FACT", "/Users/kpkautum/.claude/jobs/b441694d/tmp/fact.duckdb")

# ---- data layer, using the verified-safe pattern from E5 -------------------
con = duckdb.connect(":memory:")
con.execute(f"ATTACH '{FACT}' AS fact (READ_ONLY)")
con.execute("CREATE VIEW fact_transactions AS SELECT * FROM fact.fact_transactions")
con.execute("SET memory_limit='300MB'")

CALLS = {"sql": 0, "rejected": 0}


def _guard(q: str) -> bool:
    s = q.strip().lstrip("(").upper()
    return s.startswith(("SELECT", "WITH", "DESCRIBE"))


@tool
def run_sql(query: str) -> str:
    """Run a read-only DuckDB SQL query against fact_transactions and return rows.

    Dialect is DuckDB, not PostgreSQL: use strftime(), NOT to_char().
    Only SELECT/WITH/DESCRIBE are permitted. A LIMIT is applied automatically.
    Returns {"columns": [...], "rows": [...]} or {"error": ..., "hint": ...}.
    """
    CALLS["sql"] += 1
    if not _guard(query):
        CALLS["rejected"] += 1
        return '{"error": "Only SELECT/WITH/DESCRIBE permitted"}'
    q = query.rstrip().rstrip(";")
    if not re.search(r"\blimit\s+\d+\s*$", q, re.I):
        q += " LIMIT 200"
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(lambda: con.execute(q).fetchall())
            try:
                rows = fut.result(timeout=30)
            except FTimeout:
                con.interrupt()
                return '{"error": "query exceeded 30s and was cancelled", "hint": "aggregate more"}'
        cols = [d[0] for d in con.description]
        return str({"columns": cols, "rows": [list(r) for r in rows[:60]],
                    "row_count": len(rows)})
    except Exception as e:
        return f'{{"error": "{str(e).splitlines()[0][:160]}", "hint": "DuckDB dialect. Check column names with DESCRIBE fact_transactions."}}'


SYSTEM = """You are Finbot, a financial data analyst. Answer by writing and running SQL.

TABLE fact_transactions (8,914,963 labeled transactions, 2010-2019):
  id, date TIMESTAMP, client_id, card_id, amount DECIMAL (negative = refund),
  use_chip ('Swipe Transaction'|'Chip Transaction'|'Online Transaction'),
  merchant_id, merchant_city,
  merchant_state -- US 2-letter code, OR full country name, OR NULL meaning online
  mcc, errors, is_fraud BOOLEAN, mcc_description,
  card_brand, card_type, credit_limit, current_age, gender, credit_score, yearly_income

Database is DuckDB, NOT PostgreSQL. Use strftime(), not to_char(). Cast is_fraud::INT to sum.

How to work:
1. Plan first, then query. Prefer several small checkable queries to one large one.
2. If a query errors, read the error and fix it. Max 3 attempts.
3. If a query runs and returns rows, ACCEPT IT. Do not re-check working queries.
4. Fraud is rare (~0.15%). Never report a rate from fewer than 30 fraud cases without
   flagging it unreliable.
5. Always give the denominator. State the comparison. Never claim causation.
Be concise."""

llm = ChatGroq(model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
               api_key=os.getenv("GROQ_API_KEY"), temperature=0)
tools = [run_sql]
llm_t = llm.bind_tools(tools)

USAGE = {"in": 0, "out": 0, "calls": 0}


def call_model(state: MessagesState):
    msgs = state["messages"]
    if not any(getattr(m, "type", "") == "system" for m in msgs):
        msgs = [("system", SYSTEM)] + list(msgs)
    r = llm_t.invoke(msgs)
    u = getattr(r, "usage_metadata", None) or {}
    USAGE["in"] += u.get("input_tokens", 0)
    USAGE["out"] += u.get("output_tokens", 0)
    USAGE["calls"] += 1
    return {"messages": [r]}


b = StateGraph(MessagesState)
b.add_node("agent", call_model)
b.add_node("tools", ToolNode(tools))
b.add_edge(START, "agent")
b.add_conditional_edges("agent", tools_condition)
b.add_edge("tools", "agent")
graph = b.compile()

QUESTIONS = [
    "What is the overall fraud rate?",
    "Is fraud evenly distributed across geographies? Investigate and explain what you find.",
    "Which merchant categories are riskiest, and is the difference trustworthy?",
]

if __name__ == "__main__":
    grand = 0
    for q in QUESTIONS:
        for k in USAGE:
            USAGE[k] = 0
        CALLS["sql"] = 0
        print("\n" + "=" * 72)
        print("Q:", q)
        print("=" * 72)
        t0 = time.time()
        try:
            out = graph.invoke({"messages": [("user", q)]}, {"recursion_limit": 25})
            ans = out["messages"][-1].content
            tot = USAGE["in"] + USAGE["out"]
            grand += tot
            print(ans[:1100])
            print(f"\n  --- {time.time()-t0:.1f}s | {USAGE['calls']} LLM calls | "
                  f"{CALLS['sql']} SQL queries | {tot:,} tokens "
                  f"(in {USAGE['in']:,} / out {USAGE['out']:,})")
        except Exception as e:
            print("  ERROR:", str(e)[:250])

    print("\n" + "=" * 72)
    print(f"GRAND TOTAL: {grand:,} tokens for {len(QUESTIONS)} questions "
          f"(avg {grand//len(QUESTIONS):,}/question)")
    if grand:
        print(f"=> Groq free tier 200,000 tok/day supports ~{200000//(grand//len(QUESTIONS))} "
              f"questions/day at this cost")
