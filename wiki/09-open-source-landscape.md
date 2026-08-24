# 09 — Open-Source Landscape & the Multi-Agent Question

Researched 2026-08-24. **Every repo below was fetched from the GitHub API** — stars, licence and
last-push dates are read values, not recalled. Anything not fetched is not listed.

## 1. The landscape, verified

| Repo | Stars | Licence | Last push | What it is |
|---|---:|---|---|---|
| **[Canner/WrenAI](https://github.com/Canner/WrenAI)** | 17,372 | NOASSERTION (AGPL per docs) | **2026-08-21** | **GenBI — governed text-to-SQL through an open context layer. The most relevant project in existence to Finbot.** |
| [mindsdb](https://github.com/mindsdb/mindsdb) | 39,638 | MIT | 2026-08-21 | Unified workspace for open models over data (repo now redirects to `mindsdb/mindshub`) |
| [CopilotKit](https://github.com/CopilotKit/CopilotKit) | 36,996 | MIT | **2026-08-24** | The frontend stack already in use here. Very actively developed. |
| [vanna-ai/vanna](https://github.com/vanna-ai/vanna) | 23,821 | MIT | 2026-02-02 *(6 mo stale)* | RAG text-to-SQL with a self-learning example flywheel |
| [sinaptik-ai/pandas-ai](https://github.com/sinaptik-ai/pandas-ai) | 23,764 | NOASSERTION | 2025-10-28 *(10 mo stale)* | Conversational dataframe/SQL analysis |
| [cube-js/cube](https://github.com/cube-js/cube) | 20,678 | NOASSERTION | 2026-08-24 | Open-source semantic layer for AI/BI |
| [eosphoros-ai/DB-GPT](https://github.com/eosphoros-ai/DB-GPT) | 19,785 | MIT | 2026-08-21 | Multi-agent AI data assistant, custom DAG engine (AWEL) |
| [malloydata/malloy](https://github.com/malloydata/malloy) | 2,556 | NOASSERTION | 2026-08-20 | Semantic data language |
| [xlang-ai/Spider2](https://github.com/xlang-ai/Spider2) | 857 | MIT | 2026-08-12 | ICLR 2025 enterprise text-to-SQL benchmark |
| [TAG-Research/TAG-Bench](https://github.com/TAG-Research/TAG-Bench) | 765 | MIT | 2026-07-25 | Table-augmented generation benchmark |
| [defog-ai/sqlcoder](https://github.com/defog-ai/sqlcoder) | 4,044 | Apache-2.0 | 2024-05-23 | **Effectively dead** |
| [Dataherald](https://github.com/Dataherald/dataherald) | 3,646 | Apache-2.0 | 2024-07-24 | **Effectively dead** |

> **Licence warning**: WrenAI is **AGPL**. Reading it for architecture is fine. Copying code into
> Finbot would impose AGPL obligations. **Study the design, write your own code.**

## 2. The three live approaches, compared

An independent teardown of Vanna / WrenAI / DB-GPT maps the whole design space:

| | **Vanna** | **WrenAI** | **DB-GPT** |
|---|---|---|---|
| Philosophy | Retrieval — good examples beat modelling | Explicit semantic modelling | Multi-agent workflows (AWEL DAG engine) |
| Context retrieval | Vector search over 3 collections: DDL, docs, question-SQL pairs | **MDL** semantic layer + Qdrant vector retrieval; **column pruning cuts context 60–80%** | Metadata schema linking + adaptive few-shot |
| Generation | LLM call, optional two-pass (exploratory query reveals real values first) | Generates **"WrenSQL" against semantic model names**, not physical tables | Specialist agents: analyst / architect / engineer |
| Validation | Basic regex via `sqlparse` | **Dry-run through DataFusion `LogicalPlan`**, then transpile to target dialect | Error-retry loop feeding failures back |
| Learning | **Auto-training** — any successfully executing query joins the training set | Accumulates verified pairs, no auto-learning | None built in; offers fine-tuning (`DB-GPT-Hub`) |
| Weakness | No semantic governance; inconsistent results from retrieval randomness; weak validation | Setup complexity; AGPL; iteration needed on hard queries | "Massive architectural complexity"; **accuracy on 'Extra Hard' queries drops to ~40%** |

## 3. The single best idea to steal — from WrenAI

**WrenAI does not let the LLM write SQL against physical tables.** The LLM writes against
*semantic model objects*; a deterministic engine (`wren-core`, Rust on Apache DataFusion) then
expands those into physical SQL, injecting model definitions as CTEs, resolving relationships
and calculated fields, and transpiling to the target dialect. It dry-run validates before
execution and returns **structured errors with hints**.

This sits precisely between ThoughtSpot's fully-deterministic compiler (unreproducible, patented)
and raw text-to-SQL (unreliable). And there is a cheap version of it.

> ### The Finbot adaptation: materialise the semantic layer as SQL views
>
> [07](07-roadmap.md) Phase 3 proposes a YAML registry injected into the prompt. That is
> *advisory* — it relies on the model choosing to comply. WrenAI's insight suggests going one
> step further and making the correct definition **structural**:
>
> ```sql
> CREATE VIEW v_labeled_transactions AS
>   SELECT t.*, f.is_fraud
>   FROM transactions t
>   JOIN fraud_labels f ON t.id = f.transaction_id;   -- inner join, by construction
>
> CREATE VIEW v_spend AS
>   SELECT * FROM transactions WHERE amount > 0;      -- excludes the 660,054 refunds
> ```
>
> Point the agent at the views and describe them in the tool docstring. The 33% fraud-labelling
> error ([02](02-data-dictionary.md) §3) then becomes **impossible to make**, not merely
> discouraged. Same for the negative-amount trap.
>
> **YAML for vocabulary and caveats; views for correctness.** The registry still earns its keep
> for synonyms, display names and the `caveat` text the trace panel shows — but the arithmetic
> is enforced by the database, not by the model's good behaviour. This is a strict upgrade on
> Phase 3 as currently written and costs perhaps two extra hours.

## 4. Other adoptable ideas, ranked

1. **Column pruning before prompting** (WrenAI: 60–80% context reduction). Directly attacks
   Finbot's binding constraint — Groq's 8,000 TPM ceiling ([05](05-research-agent-stack.md) §3).
   Send the columns the question plausibly needs, not all 438 `findex` columns.
2. **Dry-run validation before execution** (WrenAI). DuckDB supports `EXPLAIN` — validate the
   plan, catch errors without touching data, feed structured hints back.
3. **Verified question→SQL pair store** (Vanna's flywheel, WrenAI's `queries.yml`). Every query
   the owner confirms is correct becomes a few-shot example. The literature says select these by
   **SQL structure similarity, not question-text similarity** ([04](04-competitive-research.md) §5).
   Start as a JSON file; it is the cheapest accuracy gain available after the semantic layer.
4. **Two-pass generation** (Vanna). Run a cheap exploratory query to see actual values before
   writing the real one — e.g. discover that `use_chip` values are `'Swipe Transaction'` not
   `'swipe'`. Prevents a whole class of silent empty-result bugs.
5. **`instructions.md` as a first-class file** (WrenAI). Business context in prose, versioned in
   git, separate from the schema.

**Do not adopt**: Vanna's auto-training (adds *any* executing query, including confidently wrong
ones — with a 0.1495% base rate a wrong-but-executing fraud query is indistinguishable from a
right one). DB-GPT's AWEL DAG engine (see §5). Cube/Malloy (settled in
[04](04-competitive-research.md) §6).

## 5. Multi-agent: the answer is NO, and the reason is quantitative

The 2026 debate is genuinely split — Cognition published *"Don't Build Multi-Agents"* (fragile,
poor context sharing, conflicting decisions); Anthropic published a multi-agent research system
claiming **>90% improvement** on its tasks. They are not contradicting each other; they are
describing different task shapes.

The consensus that emerges:

| | Multi-agent wins | Single-agent wins |
|---|---|---|
| Task shape | **Wide and shallow** — market research, parallel data gathering, brainstorming | **Deep and narrow** — programming, long-form writing, coherent chains of reasoning |
| Why | Subtasks proceed independently, results merge | Memory consistency and logical coherence are paramount |

**Data analysis is deep and narrow.** "Why did fraud spike in 2015?" is one reasoning chain
where each step depends on the last — exactly the shape that multi-agent coordination fragments.
Reported costs of getting this wrong: **2–6× efficiency loss from context fragmentation** in
systems with more than ~10 tools, plus branching/backtracking/consensus overhead.

### The decisive number for Finbot
Multi-agent systems reportedly use **~15× more tokens** than single-agent chat.

Finbot's ceiling is Groq's **200,000 tokens/day**, which already limits it to roughly
**13–14 multi-step questions per day** ([05](05-research-agent-stack.md) §3). At 15× that
becomes **fewer than one question per day.** A multi-agent Finbot on the zero-billing constraint
is not merely unwise — it is arithmetically non-viable.

> **Verdict: single agent, deep reasoning.** This also matches the strongest competitive
> evidence: Julius AI is a single agentic loop and it works
> ([04](04-competitive-research.md) §4). Hex runs four agents but split them by *user persona*
> (notebook vs conversational), not by reasoning step — and needed Temporal to do it.
>
> **What Finbot should build instead of multiple agents: multiple *nodes* in one LangGraph
> graph, sharing one state object and one context.** Plan → execute → reflect are phases of a
> single coherent reasoning chain, not separate agents. That is Phase 4 exactly as written, and
> this research confirms rather than changes it.

If multi-agent is ever revisited, the one defensible split is the **wide-and-shallow** part:
parallel independent web-search lookups for macro context, merged back. That is genuinely
parallelisable. Nothing in the SQL reasoning path is.

## 6. Benchmarks worth knowing

- **Spider 2.0** (857★, MIT, ICLR 2025 Oral) — enterprise-realistic, ~800 columns/schema.
  Agentic systems reach ~21.3%; GPT-4 alone scores 6.0% on Spider 2.0-Lite vs 86.6% on Spider 1.0.
  **Use this to calibrate claims, not as a target.**
- **TAG-Bench** (765★, MIT) — table-augmented generation: questions needing reasoning *beyond*
  what SQL alone can express. Conceptually closest to what Finbot claims to do.
- A fine-tuned CodeLlama-13B reportedly hit **82.5%** on Spider (vs GPT-4 zero-shot 76.2%) via
  DB-GPT-Hub. Noted only to show fine-tuning is unnecessary — prompting a strong model plus a
  semantic layer is the cheaper path to the same place.
