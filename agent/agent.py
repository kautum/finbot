"""Finbot: an AI financial analyst over 8.9M labeled card transactions."""
import os
import json
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition

import db
import statistics as stats

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")

METRICS = (HERE / "metrics.yaml").read_text()

SYSTEM_PROMPT = f"""You are Finbot, a financial data analyst. You answer questions about a
credit-card transaction dataset by querying it, not by guessing.

## The data

One DuckDB database, queried through governed views. Query these, never the physical tables:

- `v_transactions` -- 8,914,963 labeled transactions, 2010-2019. One row per transaction,
  already joined to fraud labels, merchant category, card and cardholder attributes.
  Columns: id, date, client_id, card_id, amount, use_chip, merchant_id, merchant_city,
  merchant_state, mcc, errors, is_fraud, mcc_description, channel, merchant_country,
  card_brand, card_type, credit_limit, current_age, gender, credit_score, yearly_income.
- `v_spend` -- the same rows with refunds (negative amounts) excluded. Use for money questions.
- `v_coverage` -- one row: total_transactions, labeled_transactions, unlabeled_transactions.
- `v_findex` -- World Bank financial-inclusion indicators by country.

## Governed definitions

Prefer these definitions. If a question needs a metric that is not defined here, compute it
from raw columns but say explicitly that you used an ad-hoc definition.

{METRICS}

## How to work

1. Understand what is actually being asked. If it is genuinely ambiguous, ask one short
   clarifying question instead of guessing.
2. Run SQL. Start with the query that answers the question directly; only break it into
   steps if the question really has multiple parts.
3. Look at the numbers before writing the answer. If a result looks absurd, investigate
   rather than reporting it.
4. **Budget: at most 4 `run_sql` calls per question.** If a query runs and returns rows,
   accept the result and move on -- do not re-run it a different way to double-check.
   Re-verifying a working query is how correct answers get turned into wrong ones.
5. **Chart comparisons and trends.** A grouped result with 2-40 categories, or any time
   series, gets a `chart` call before your final answer. A single number needs no chart,
   and a list longer than 40 rows needs none either -- summarise that in prose. Never
   contort a result to fit a chart, and never re-query just to make one.
   A compact table alongside the chart is fine when the exact values matter, but keep it
   to 10 rows at most; past that the chart alone is the answer.
6. Answer in plain language, and keep it short: 2-5 sentences. Lead with the finding, then
   the number, then the caveat if one matters. Do not paste SQL or tables into your answer;
   the user can already see the chart and the query.

## Rules

- DuckDB SQL dialect. `strftime(date, '%Y-%m')` not `to_char`. `date_trunc('month', date)`
  works. `SELECT * EXCLUDE (col)` and `QUALIFY` are available.
- Never claim a number you did not query.
- Rare-event honesty: fraud is 0.1495% of rows. Do not rank or compare segments with fewer
  than 30 fraud cases -- say the sample is too small. This matters more than being helpful.
  Refuse in one short paragraph: state the counts you found, say why they are too few, and
  offer a coarser cut that would work. Do not keep querying to find a way around it.
- Correlation is not cause. Say "associated with", not "causes", unless you tested it.
- Round percentages sensibly. Fraud rates need 3-4 decimal places to be meaningful.
- `tavily_search` is for context the database cannot supply -- what an MCC code means in
  general, background on a company or event, macro news. Never use it for a transaction,
  spend, or fraud number; the database is always authoritative for those, even if a web
  result disagrees with it.
- When asked whether a difference is real, significant, or meaningful, call a statistics
  tool (`compare_two_rates`, `rate_interval`, `compare_many_rates`) and report both the
  p-value and the effect size. Never assert significance from eyeballing two percentages.
"""

llm = ChatGroq(
    model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0,
)

_con = db.connect()
web_search = TavilySearch(max_results=3)


@tool
def run_sql(query: str) -> str:
    """Run a read-only DuckDB SQL query against the transaction data and return the rows.

    Query the governed views (v_transactions, v_spend, v_coverage, v_findex), not physical
    tables. Only SELECT / WITH / DESCRIBE are permitted. Results are capped at 200 rows and
    20 seconds. Use DuckDB dialect: strftime() and date_trunc(), not to_char().
    """
    cols, rows, err = db.run(_con, query)
    if err:
        return f"ERROR: {err}"
    if not rows:
        return "Query returned no rows."
    # Aggregates, not raw rows: feeding 200 rows of context back into a free-tier model
    # is the fastest way to hit the token-per-minute ceiling mid-conversation.
    preview = rows[:60]
    out = {"columns": cols, "rows": [list(map(_jsonable, r)) for r in preview],
           "row_count": len(rows)}
    if len(rows) > len(preview):
        out["note"] = f"showing first {len(preview)} of {len(rows)} rows"
    return json.dumps(out, default=str)


@tool
def chart(kind: str, title: str, x_key: str, y_keys: list[str], data: list[dict]) -> str:
    """Render a chart in the chat. Call this whenever a result is worth seeing visually.

    kind: "bar", "line", or "area".
    title: a short descriptive title.
    x_key: the field name in `data` used for the x axis / category labels.
    y_keys: one or more numeric field names to plot.
    data: the rows, as a list of flat objects, e.g.
          [{"channel": "Online", "fraud_rate": 0.8378}, ...]
    Up to 40 points. Long category names are fine -- charts with more than 12 categories
    are laid out as horizontal bars automatically. Round values before passing them in.
    """
    return f"Chart rendered: {title} ({kind}, {len(data)} points)."


@tool
def compare_two_rates(
    label_a: str, successes_a: int, trials_a: int,
    label_b: str, successes_b: int, trials_b: int,
    confidence: float = 0.95,
) -> str:
    """Test whether two rates differ, and by how much. Use this whenever asked if a
    difference is real, significant, or meaningful -- never claim significance without it.

    Pass raw counts (successes and trials), not percentages. Returns whether the gap is
    statistically real (p-value) AND whether it is large enough to matter (risk ratio with
    confidence interval, Cohen's h) -- these are separate questions, and at millions of rows
    almost anything is "significant" without being important.
    """
    try:
        return json.dumps(stats.compare_two_rates(
            label_a, successes_a, trials_a, label_b, successes_b, trials_b, confidence
        ))
    except stats.StatsError as e:
        return f"ERROR: {e}"


@tool
def rate_interval(label: str, successes: int, trials: int, confidence: float = 0.95) -> str:
    """Confidence interval for a single rate -- how precisely it is known from this many
    events. Use this for "how confident are we in X%" questions, and for segments too small
    to compare against another group.
    """
    try:
        return json.dumps(stats.rate_interval(label, successes, trials, confidence))
    except stats.StatsError as e:
        return f"ERROR: {e}"


@tool
def compare_many_rates(
    labels: list[str], successes: list[int], trials: list[int], confidence: float = 0.95
) -> str:
    """Test whether a rate differs across three or more groups (e.g. across merchant
    categories or years). Corrects for multiple comparisons -- testing many groups without
    this correction manufactures false "findings" by chance. Needs at least 3 groups; use
    compare_two_rates for 2.
    """
    try:
        return json.dumps(stats.compare_many_rates(labels, successes, trials, confidence))
    except stats.StatsError as e:
        return f"ERROR: {e}"


def _jsonable(v):
    from decimal import Decimal
    from datetime import date, datetime
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


stats_tools = [compare_two_rates, rate_interval, compare_many_rates]
tools = [run_sql, chart, web_search] + stats_tools
llm_with_tools = llm.bind_tools(tools)


QUERY_BUDGET = 4


def _queries_this_turn(messages) -> int:
    """Count run_sql calls since the user's last message."""
    n = 0
    for m in reversed(messages):
        if m.type == "human":
            break
        for call in getattr(m, "tool_calls", None) or []:
            if call["name"] == "run_sql":
                n += 1
    return n


def call_model(state: MessagesState):
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    # The prompt asks for at most QUERY_BUDGET queries and the model ignores it -- measured
    # at 15+ on an ambiguous question, which is the documented "collapse mode" failure.
    # So the budget is enforced here instead: past the cap, the tools are taken away and
    # the model has to answer with what it already has.
    if _queries_this_turn(state["messages"]) >= QUERY_BUDGET:
        messages.append(SystemMessage(content=(
            f"You have used your {QUERY_BUDGET}-query budget. Do not call run_sql again. "
            "Answer now from the results you already have. If they are not sufficient to "
            "answer safely, say so plainly and explain what you would need. You may still "
            "call `chart`, `tavily_search`, or a statistics tool if you already have the "
            "counts it needs."
        )))
        return {"messages": [llm.bind_tools([chart, web_search] + stats_tools).invoke(messages)]}
    return {"messages": [llm_with_tools.invoke(messages)]}


graph_builder = StateGraph(MessagesState)
graph_builder.add_node("agent", call_model)
graph_builder.add_node("tools", ToolNode(tools))
graph_builder.add_edge(START, "agent")
graph_builder.add_conditional_edges("agent", tools_condition)
graph_builder.add_edge("tools", "agent")


if __name__ == "__main__":
    from langgraph.checkpoint.memory import MemorySaver
    g = graph_builder.compile(checkpointer=MemorySaver())
    q = os.sys.argv[1] if len(os.sys.argv) > 1 else "Which channel has the worst fraud rate?"
    for chunk in g.stream({"messages": [("user", q)]},
                          config={"configurable": {"thread_id": "cli"}},
                          stream_mode="values"):
        chunk["messages"][-1].pretty_print()
