# 10 — Agent Instruction Design

**The agent currently has no system prompt at all** ([01](01-current-state.md) §2). This page
specifies what to write and, more importantly, *where each kind of instruction belongs*.

## 1. The governing principle: four layers, not one big prompt

Hex's engineers said the context-harvesting pipeline was *"more valuable than the basic agent
loop architecture"*, and split context into **static** (always present) and **dynamic**
(retrieved per query) ([04](04-competitive-research.md) §3). Finbot needs the same discipline,
because its binding constraint is Groq's **8,000 tokens/minute** — a prompt that is 2,000 tokens
of boilerplate costs 25% of the per-minute budget on every single call.

| Layer | Contains | Loaded | Budget |
|---|---|---|---|
| **1. System prompt** | Identity, hard rules, dialect, refusal policy | Always | ≤600 tokens |
| **2. Tool docstrings** | Per-tool contract, arguments, gotchas | Always (with tool defs) | ≤200 tokens each |
| **3. Semantic layer** | Governed metric definitions + caveats | Retrieved by relevance | ≤800 tokens |
| **4. Few-shot examples** | Verified question→SQL pairs | Retrieved by SQL-structure similarity | ≤600 tokens |

> **The single most important instruction-design decision**: put *correctness* in the database
> (SQL views, [09](09-open-source-landscape.md) §3) and read-only enforcement in the driver
> ([03](03-infrastructure-decision.md) §6.4). **Prompts are for judgement, not for enforcement.**
> Anything a prompt merely asks for, the model will eventually not do.

## 2. Layer 1 — the system prompt

Anthropic's guidance on tools applies equally here: descriptions *are* prompts — clarity is
paramount, and vague descriptions produce incorrect tool use. Prompt agents to emit reasoning
alongside structured output, because that triggers chain-of-thought behaviour.

Draft, annotated. Each rule exists because of a specific documented failure.

```text
You are Finbot, a financial data analyst. You answer questions about a credit-card
transaction dataset by writing and running SQL, then interpreting the results.

## The database
DuckDB. NOT PostgreSQL. Specifically:
- Use strftime()/strptime(). to_char() and to_timestamp() DO NOT EXIST.
- QUALIFY, SELECT * EXCLUDE(...), and DISTINCT ON are available and useful.
- Do NOT use COUNT(DISTINCT x) OVER (...) — unreliable in DuckDB.
- Inspect schema with DESCRIBE or duckdb_tables(), not pg_catalog.
- There are no stored procedures.

## Prefer governed views over raw tables
Query v_labeled_transactions, not transactions JOIN fraud_labels. Query v_spend, not
transactions, for anything about spending. These views encode decisions you would
otherwise get wrong. If no view fits, use raw tables — and say so in your answer.

## How to work
1. Plan before querying. State what you need to find out and in what order.
2. Prefer several small, checkable queries over one large one.
3. If a query errors, read the error and fix it. Maximum 3 attempts.
4. If a query runs and returns rows, ACCEPT IT. Do not re-check working queries.
5. If a result is empty, say so. Do not invent a plausible answer.

## Honesty rules (these override helpfulness)
- Fraud is rare here: about 0.15%. Segments run out of data fast.
- Never report a rate from fewer than 30 positive cases without flagging it as
  unreliable. If asked to compare such segments, refuse and explain why.
- Never state a difference is meaningful without a significance test.
- If a question is ambiguous, ask. Offer 2-3 interpretations. Do not guess silently.
- If you did not verify something with a query, do not assert it.
```

**Why each block is there:**

| Rule | Failure it prevents |
|---|---|
| The DuckDB block | MotherDuck's own blog: *"DuckDB has its own dialect and functions, and if you don't tell the model to use them, it won't."* LLMs are Postgres-biased. |
| Prefer governed views | Metric drift ([08](08-positioning.md) §3) — same question, different number |
| Rule 4 (early-accept) | Documented failure where asking a model to double-check turns a correct query into a wrong one ([04](04-competitive-research.md) §5) |
| Max 3 attempts | Hex saw agents run **50** verification queries "just to be certain" |
| The 30-positive-cases rule | 22 of 109 MCC segments have <10 fraud cases ([02](02-data-dictionary.md) §8). This is Julius AI's documented failure — hallucinated statistics on sparse data |
| Ask, don't guess | The Hex Threads pattern ([04](04-competitive-research.md) §3) |

**Deliberately NOT in the system prompt**: "you are a world-class expert", "be helpful and
friendly", "think step by step" (redundant with an explicit plan node), and the full schema
(that belongs in layer 3, retrieved).

## 3. Layer 2 — tool docstrings

The docstring **is** the contract. Anthropic's guidance: name, input schema with types and
required/optional, and a description of the output shape so the agent knows how to consume it.

The current `run_sql` docstring says *"Use standard SQL"* — which the research identifies as a
named, real failure mode, not a theoretical one. Rewrite:

```python
@tool
def run_sql(query: str) -> str:
    """Run a read-only DuckDB SQL query and return the rows.

    Dialect is DuckDB, not PostgreSQL. Only SELECT and WITH are permitted;
    anything else is rejected. A LIMIT is added automatically if you omit one.
    Queries are cancelled after 30 seconds.

    Prefer the governed views (v_labeled_transactions, v_spend) over raw tables.
    Call describe_schema first if you are unsure of a column name.

    Returns: {"columns": [...], "rows": [[...]], "row_count": N, "truncated": bool}
    On failure returns {"error": "...", "hint": "..."} - read the hint and retry.
    """
```

Two more tools worth adding, both cheap:

- `describe_schema(table: str | None)` — so the agent stops guessing column names. Without it,
  the schema must live in the system prompt permanently, which costs tokens on every call.
- `lookup_metric(name: str)` — returns the governed definition and its caveat. Makes the
  semantic layer *pull-based* rather than always-resident, and — critically — **produces a
  visible trace event proving the definition was consulted**, which is the sentence the
  reasoning panel exists to show ([07](07-roadmap.md) Phase 6).

## 4. Layer 3 — the semantic layer, retrieved not resident

15–30 metrics is well past the token budget if always present. Retrieve by matching the question
against `name` + `synonyms`, inject only the matches.

```yaml
- name: fraud_rate
  display_name: "Fraud Rate"
  synonyms: ["fraud %", "fraud percentage", "how much fraud", "fraud level"]
  view: v_labeled_transactions
  expr: "SUM(is_fraud::INT) * 1.0 / COUNT(*)"
  caveat: >
    Labeled transactions only. 4,390,952 of 13,305,915 transactions carry no
    fraud label; computing this over all transactions understates it by ~33%.
  min_denominator: 30
  format: {unit: percent, decimals: 4}
```

`caveat` is the field that earns its place — it is what the trace panel displays and what makes
the answer defensible. `min_denominator` is machine-readable, so the refusal rule becomes
enforceable code rather than a hope.

**Hex's warning applies here**: contradictory definitions send agents into "collapse mode" —
30 minutes of self-second-guessing. **A small consistent registry beats a large inconsistent
one.** Start with 10 metrics that are definitely right.

## 5. Layer 4 — few-shot examples, selected by SQL structure

The literature is specific: select examples by **SQL structural similarity**, not question-text
similarity. Masked-question similarity (mask table/column names, then kNN) also works.

Practical minimum — no vector store needed at this scale:

```json
{"question": "fraud rate by card type",
 "sql": "SELECT c.card_type, COUNT(*) n, SUM(v.is_fraud::INT) fraud, ... FROM v_labeled_transactions v JOIN cards c ON v.card_id = c.id GROUP BY 1",
 "shape": "group_by + join + rate",
 "verified": "2026-08-24"}
```

Tag each with a `shape`; match the question's inferred shape; inject 2–3. Every query the owner
confirms correct gets appended. This is Vanna's flywheel **with a human gate** — Vanna's
auto-training adds any query that merely *executes*, which at a 0.1495% base rate cannot
distinguish a right fraud query from a wrong one ([09](09-open-source-landscape.md) §4).

## 6. Instructions for the ANSWER, not just the query

Mostly overlooked, and it is where a demo is won or lost. The agent must be told how to write:

```text
When presenting results:
- Lead with the answer, then the evidence. Not a narration of your process.
- Always give the denominator. "0.84%" alone is not an answer; "0.84% (8,779 of
  1,043,975 online transactions)" is.
- Round sensibly. Do not report 0.8409183% - report 0.84%.
- State the comparison. A number without a baseline is not a finding.
- If you ran a significance test, give the p-value and the interval, in plain words.
- Never describe a pattern as a cause. You measured an association.
```

That last rule matters more than it looks: `fraud_by_year`
([02](02-data-dictionary.md) §3) contains a drop to 0.004% in 2011 and 0.018% in 2017 that are
almost certainly synthetic-generation artifacts. Without this rule the agent will confidently
narrate a fraud-prevention success story about a data glitch — in front of the person you are
trying to impress.

## 7. What to measure

Anthropic's guidance is to instrument tool use: runtime per call, number of calls per task,
token consumption, and error counts — the data reveals which tools to consolidate. For Finbot
the four worth logging from day one:

1. **Tokens per question** — validates or breaks the ~14-questions/day estimate
2. **Tool calls per question** — if it climbs past ~6, the loop is thrashing
3. **SQL error rate and first-attempt success** — the headline accuracy number
4. **How often the model used a governed view vs a raw table** — measures whether the semantic
   layer is actually being adopted, rather than assumed

A 20-question golden set with hand-checked answers, re-run after every prompt change, is the
cheapest possible eval harness and prevents the classic failure of tuning a prompt until the one
demo question works.

## 8. Sequencing

1. System prompt (§2) + rewritten `run_sql` docstring (§3) — **do this first, it is an hour**
2. `describe_schema` tool
3. Governed views + minimal 10-metric registry + `lookup_metric`
4. Answer-formatting rules (§6)
5. Few-shot store, once ~20 verified pairs exist
6. Retrieval for layers 3 and 4, once they exceed the token budget

Steps 1–2 alone will visibly improve output before any of the larger phases land.
