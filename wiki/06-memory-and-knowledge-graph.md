# 06 — Memory and Knowledge Graph

Researched 2026-08-23. Two questions get conflated in the brief; they are separate and have
different answers.

## 1. `agtm1199/build-kg` — verdict: not applicable

Read directly from the repo (Apache-2.0, 2 stars, 0 forks, 1 contributor, 16 commits, last
push **2026-02-26**).

**What it mechanically is**: a document-to-graph pipeline shipped as an agent *skill*
(a `SKILL.md` the coding agent reads), not an importable library. Flow:

```
topic -> crawl4ai (web fetch)
      -> unstructured (chunk_by_title)
      -> Postgres staging tables (source_document / source_fragment)
      -> LLM extraction (Claude Haiku default) against an ontology json_schema
      -> Apache AGE (graph extension for Postgres), queryable via Cypher
```

Dependencies: Apache AGE via the bundled `docker-compose.yml`; an Anthropic or OpenAI key
(no local option); `crawl4ai`, `unstructured`, `psycopg2-binary`, `pydantic`, `pyyaml`.

**What `financial-aml.yaml` actually defines** — and this is the crux. It is a
**regulatory-text extraction ontology**, not a fraud/transaction schema:

- `Provision` — a clause from AML/KYC **legislation** (`provision_id`, `text`, `jurisdiction`, `authority`)
- `Requirement` — derived from a Provision, with `requirement_type` (identification /
  verification / monitoring / reporting / record_keeping / …) and `deontic_modality`
  (must / must_not / may / should)
- `Constraint` — a testable rule (`logic_type`, `operator`, `threshold`, `unit`, `pattern`)
- Edges: `DERIVED_FROM`, `HAS_CONSTRAINT`
- `id_patterns`: regexes for **statute citations** (31 CFR §, FATF Recommendation N, EU directives)
- `discovery.search_templates`: queries like `"<country> anti-money laundering AML regulations"`
  — it drives a crawler at **government and regulator web pages**

**Why it does not fit Finbot.** The pipeline exists to turn **prose** into graph entities via an
LLM. Finbot's data is already structured rows. Running it against SQL tables would mean
serialising rows to text so an LLM can re-parse them back into structure you already had — at
LLM cost, with LLM error risk, for zero gain over `INSERT INTO`.

**The one honest use**: if Finbot ever wanted a *compliance* knowledge base — "which AML rule
requires flagging cash transactions over $10k", as a citable fact — `build-kg` could ingest
FinCEN/FATF text into a queryable rule graph. That is a **different product surface** (a
regulatory Q&A bot), not a knowledge graph of the transaction data.

> **Verdict: skip it.** Not because it is badly built, but because it targets unstructured
> regulatory text and Finbot's problem is 100% structured data. It shares the words "financial"
> and "AML" with the use case and nothing else. Keep it as a roadmap slide at most.

## 2. Agent memory — what Finbot actually needs

Three distinct things, routinely confused:

| Layer | What it is | Needed? |
|---|---|---|
| **Checkpointing** | Graph state per thread; resume after restart | **Yes — unconditionally. This is a bug fix.** |
| **Long-term / semantic memory** | Facts retained across sessions | **Yes, selectively.** |
| **Knowledge graph** | Entity-relationship structure over the domain data | **No — see §4.** |

### 2.1 Checkpointing — fix this immediately, one line

Current `MemorySaver` (renamed `InMemorySaver`, old alias kept) is in-process and dies on every
restart. Options:

- `pip install langgraph-checkpoint-sqlite` → `SqliteSaver.from_conn_string("checkpoints.db")`
- `pip install langgraph-checkpoint-postgres` → `PostgresSaver` (for concurrent processes)

Drop-in: same `.compile(checkpointer=...)` call. **Zero infra, zero billing, one line.**

### 2.2 Long-term memory — what a fintech analyst agent should actually remember

Concrete and worth persisting:
- **Corrected metric definitions** — "active user means a transaction in the last 30 days, not 90"
- **Query patterns that previously failed** — wrong column name, ambiguous join. (Julius AI does
  exactly this and it is one of its better ideas — see [04](04-competitive-research.md) §4.)
- **Standing preferences** — "always exclude negative amounts from spend", "amounts in USD"
- **Prior conclusions worth citing back** — "last session we found fraud concentrates in online txns"

### 2.3 Options surveyed

| Option | Effort | Verdict |
|---|---|---|
| **Plain SQL table** `agent_memory(scope, key, value, updated_at)` | ~50 lines | **Recommended.** Written by an explicit tool call when the agent learns something; read into the system prompt at session start. |
| LangGraph `Store` API (`PostgresStore`) | Low | Native, but needs Postgres. Use if the plain table outgrows itself. Note: no confirmed `SqliteStore`. |
| LangMem | Medium | Official, but pre-1.0 (~0.0.30, slow cadence) and every extraction is an LLM call — background/batch only, never on the interactive path. |
| mem0 | Medium | Mature (~47k stars), in-process mode needs no Docker, but not LangGraph-native. |
| Zep / Graphiti | Medium-high | Needs a persistent graph server. See §3. |
| Letta (MemGPT) | High | Wants to own the agent loop — fights LangGraph rather than extending it. |

## 3. Graphiti / Zep specifically

- Does **not** require Neo4j. Backends: Neo4j, FalkorDB, Kuzu, Amazon Neptune. FalkorDB Lite is
  genuinely embedded/file-based; Kuzu support is marked deprecated in at least one issue —
  verify before relying on it.
- Zep Cloud free tier: no card, 10k credits/month, then a steep cliff to $125/mo. Self-hosting
  Graphiti is the actual zero-billing path.
- **Serverless fit: no.** Graphiti wants a persistent server process or a persistent volume.
  Neither is native to Vercel functions. If the backend lands on Render (per
  [03](03-infrastructure-decision.md) §4B), it becomes *possible* — but still unjustified at
  this stage.

## 4. Would a knowledge graph over the *transactional* data add value?

This is the real, separate question. Honest answer: **narrowly yes, and it does not require a
graph database.**

**What the schema has**: users (address, lat/long), cards (brand, limit), transactions
(merchant_id, city, mcc), fraud labels.
**What it critically lacks**: device ID, IP address, email — precisely the fields that make
graph fraud detection powerful in the canonical Neo4j IEEE-CIS demos, where "device shared
across N cards" is the strongest ring signal. Without them the graph is shallow:
`user —owns→ card —charges→ transaction —at→ merchant`, plus `user —shares_address→ user`.

Genuinely graph-shaped analyses that *are* possible here:
- **Shared-address clustering** — multiple distinct users at one address (blunt, could be a household)
- **Merchant-centric community detection** — users whose fraud clusters on a small merchant set,
  suggesting a compromised or collusive merchant
- **Geographic velocity** — impossible-travel sequences (lat/long + timestamp)
- **Connected components / Louvain** over shared-address and shared-merchant edges

All of it is 2–3 hops on a small schema — inside what a recursive CTE or self-join can do. Where
it genuinely exceeds SQL (Louvain, PageRank, connected components), the fix is **not** standing
up Neo4j. It is: pull the edges into `networkx`/`igraph` in a batch script, run the algorithm
once, write `cluster_id` / `ring_risk_score` back into a SQL table. That delivers ~90% of the
value with zero new infrastructure, and the output lands in a column the existing `run_sql`
tool already queries.

> **Verdict: a persistent graph database here is a solution looking for a problem.** A batch
> `networkx` job materialising graph-derived features into SQL columns is not. Sequence if it
> ever becomes a real feature: batch graph analysis → materialised SQL column → agent queries
> SQL as before. Revisit a real graph DB only if the agent must construct arbitrary-depth
> traversals on the fly — nothing in the stated use case asks for that.

## 5. Recommendation, ranked

1. **Swap `MemorySaver` → `SqliteSaver`.** One line, free, fixes a real bug.
2. **Add an `agent_memory` SQL table** with one explicit "remember this" tool. Not a framework.
3. Only if that outgrows itself: LangGraph `PostgresStore`, optionally with LangMem doing
   extraction in a *background* step.
4. **Do not adopt Graphiti / Zep / Letta / mem0 now.** They solve problems (temporal fact
   contradiction, autonomous self-managing memory) a single-user analyst agent does not have,
   and each demands a persistent server or another signup.
5. **Do not build a graph database over the transaction data.** If ring detection becomes a real
   request, do it as a `networkx` batch job writing back to SQL.
6. **`build-kg` is not applicable anywhere in this plan.**

### Flagged as unverified
LangMem's reported p95 memory-search latency (~60 s) could not be confirmed from a primary
source. Graphiti's Kuzu backend status is ambiguous. mem0's Groq provider support was not
directly confirmed.
