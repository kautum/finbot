# 08 — Positioning: how Finbot competes with BI tools and wins

Researched 2026-08-24. This page is the product argument. [04](04-competitive-research.md) is
*what the competition built*; this is *where Finbot beats them and where it must not pretend to*.

## 1. The rule that makes the rest credible

**Do not claim Finbot beats Power BI at being Power BI.** A solo project claiming to out-govern
a platform with a thousand engineers is instantly, obviously false — and the moment a technical
listener catches one inflated claim, every true claim goes with it.

Finbot wins by **changing the axis of comparison**, not by scoring higher on theirs.

| Concede outright | Win decisively |
|---|---|
| Enterprise governance, RBAC, row-level security, audit certification | Time-to-first-answer |
| Scale to thousands of concurrent users | Open-ended *"why"* questions |
| Connector breadth (SAP, Salesforce, Workday, …) | Statistical rigour |
| Pixel-perfect executive dashboards, print/export | Transparency of reasoning |
| Mobile apps, embedded distribution, alerting at scale | Cross-domain synthesis |

## 2. Where traditional BI structurally loses — four wedges

These are not weaknesses vendors forgot to fix. They are consequences of the architecture.

### Wedge 1 — BI answers questions you already knew to ask
A dashboard is a **pre-modelled answer to a pre-decided question**. Someone had to model the
data, choose the metric, and build the chart *before* anyone could ask. The moment a question
falls outside that model, the answer is "file a ticket with the data team."

Finbot inverts it: point it at the schema and ask anything, immediately. This is the
**system-of-record vs system-of-action** distinction, and it is the honest core of the pitch.

> **The demo move**: ask something no one would have built a dashboard for.
> *"Does a customer's credit score predict whether they get defrauded?"* Finbot answers in
> seconds — **and the answer is no**: 0.155% (good) / 0.146% (fair) / 0.143% (excellent) /
> **0.124% (poor)**, i.e. the *lowest* fraud rate sits with the weakest credit
> ([02](02-data-dictionary.md) §8). In a BI tool that question costs a modelling cycle. And a
> *negative* result is far more persuasive than a confirmation, because it proves the system
> is measuring rather than agreeing.

### Wedge 2 — BI shows differences; it does not tell you if they are real
This is the sharpest genuine gap, and it is under-exploited. Power BI, Tableau and Looker will
happily render two bars at 0.84% and 0.03% with no statement of whether the gap is real.

**Be precise about the claim.** These tools are not statistics-free: Tableau reports p-values
and R² on trend lines, and Power BI's analytics pane offers error bars and forecast confidence
intervals. What none of them does is **hypothesis-test two arbitrary user-named segments,
conversationally, at question time** — "is fraud significantly higher for online than swipe?"
is not a trend line, and there is no pane for it. The statistics that exist are attached to
specific chart features, not available on demand for whatever comparison a user just asked for.

Overstating this to "no BI tool does statistics" is the kind of claim a BI-literate listener
catches instantly — and by §1's own logic, one caught claim takes every true claim with it.

Finbot's Phase-7 tools ([07](07-roadmap.md)) return a p-value and a Wilson-score interval, and
**refuse to test segments with too few fraud cases** — 22 of 109 MCC segments have fewer than 10
fraud cases even at full scale ([02](02-data-dictionary.md) §8).

> An analyst tool that says *"I can't answer that reliably, here's why"* is doing something no
> dashboard on the market does. **Refusal is a feature.** It is also the single strongest
> counter to the "isn't this just a hallucinating chatbot?" objection.

### Wedge 3 — the join nobody modelled
Finbot's data has two threads that look unrelated: transaction-level micro data (13.3M rows) and
national financial-inclusion indicators (174 countries, 2011–2024).

They *do* join — `transactions.merchant_state` carries full country names for non-US merchants
and matches `findex.countrynewwb` on **104 countries** ([02](02-data-dictionary.md) §5). But it
is a join **nobody would have modelled in advance**, because it depends on noticing that a
column named "state" contains countries. It is not in any schema diagram. No BI semantic model
contains it, because a human would have had to spot it and build it first.

That is the real wedge — not "BI cannot join this", but **BI can only join what someone already
modelled**. An agent that inspects the data can find the relationship at question time.

> **The demo move**: *"Do merchants in countries with lower digital-account penetration see
> different fraud rates?"* A question that requires discovering the join, spanning two datasets
> nobody linked, answered live.
>
> **Two caveats the agent must state** or the number is wrong: `findex` has ~49 rows per country
> (years × demographic groups), so aggregate before joining or the count fans out ~49×; and it
> covers only the non-US slice, since US rows use 2-letter state codes.
>
> *(This wedge originally claimed no join key existed. A verification pass found one. Kept as a
> reminder that the dataset rewards inspection over assumption — which is the argument.)*

### Wedge 4 — the dashboard is opaque; Finbot shows its work
A dashboard number arrives with no provenance. Ask "where did that come from?" and the answer
is a Confluence page, if you are lucky.

Finbot's reasoning-trace panel shows every query it ran and which governed metric definition it
used ([07](07-roadmap.md) Phase 6). Databricks ships this as "Thinking steps" and treats it as a
headline trust feature; Hex ships step-by-step reasoning too. **It is the cheapest credibility
feature in the entire plan and it makes the black box auditable.**

## 3. Where the AI-native competitors are — and the one axis that matters

Everyone converged on the same conclusion in 2025–26, and it is not "get a better model."

> *"The critical enabler for agentic BI isn't the language model or the interface.
> It's the semantic layer."*

The industry has a name for the failure: **metric drift** — the same question returns different
numbers depending on who asks or which agent answers. The documented root cause is uniform: the
LLM is operating against a **raw schema instead of governed definitions**. The canonical example
in the literature is an LLM asked for MRR that joins orders straight to products, skipping the
subscription model, and returns total order value — syntactically perfect, semantically wrong,
and impossible to catch by reading the SQL.

**Finbot has exactly this problem in its dataset, and it is worse than average.** Ask "what's the
fraud rate?" against the raw schema and the obvious query — count fraud over all transactions —
is **wrong by 33%**, because 4,390,952 of 13,305,915 transactions carry no fraud label at all
([02](02-data-dictionary.md) §3). The query runs. It returns a plausible number. It is wrong.

That is why the YAML metric registry is Phase 3 and not Phase 8. It is not a nice-to-have; it is
the difference between a demo that survives scrutiny and one that quietly lies.

> **The demo move**: ask for fraud rate three different ways in three separate threads and show
> the identical SQL each time, then open the registry and show the `caveat` field spelling out
> the 33% labelling gap. That is the exact trust move Databricks sells as "Trusted" answers and
> ThoughtSpot builds its entire deck around — and here it is auditable in a text file.

### Honest read on each competitor

| Product | Their real edge | Finbot's honest counter |
|---|---|---|
| **Databricks Genie** | Agent Mode multi-query planning; ontology across a whole org's assets | Only works inside Databricks. Finbot runs against any SQL store, no lakehouse required. |
| **ThoughtSpot Spotter** | Deterministic non-LLM query compiler — genuinely avoids a class of error | Patented, per-seat (~$25/user/mo entry, five-to-six figures at enterprise), heavyweight deployment. Finbot: zero seats, zero deployment. |
| **Hex Magic** | 4 specialist agents on Temporal; best-in-class context harvesting | Enterprise-team infrastructure. Their own post-mortem says scaffolding built for weaker models became "unnecessary baggage" — a caution, not a target. |
| **Julius AI** | Proves single-agent chat works; fast; learns from failed queries | Documented to hallucinate statistics on sparse data. Finbot's refusal guardrail directly addresses the failure Julius is criticised for. |

**The most useful competitor insight**: Julius is architecturally closest to Finbot and it
succeeds. Single-agent chat is not the limitation. Reasoning depth is — and that is buildable.

## 4. The one-sentence positioning

> **Finbot is a system of action for data that BI leaves unmodelled — it answers the questions
> nobody built a dashboard for, tells you when the answer isn't statistically trustworthy, and
> shows every query and definition it used to get there.**

Three clauses, three defensible claims, no adjectives.

## 5. The demo script

Order matters. Build credibility, then spend it.

1. **Open with scale, casually.** "22.5 million rows, ten years, no pre-modelling." Ask a simple
   aggregate. It returns in well under a second. Sets the floor.
2. **Ask the question no dashboard exists for.** Credit score vs fraud. The answer is *no
   relationship* — a negative result. Establishes measurement over agreement.
3. **Ask a "why" question** that forces multi-step chaining. Show the trace panel: three queries,
   each labelled, each citing its governed definition.
4. **The significance moment.** "Is online fraud *significantly* higher than swipe?" p-value and
   confidence interval. 0.8409% vs 0.0295% — a 28× gap, and now a *defensible* one.
5. **The refusal.** Ask for fraud rate in a thin segment. Finbot declines and explains the power
   problem. This is the moment the audience stops treating it as a chatbot.
6. **Open the semantic layer.** Show `fraud_rate`'s `caveat` field. Explain the 33% labelling gap
   and that the naive query would have been wrong. Close on: *"this is why the same question
   gives the same answer every time."*

Close on the transparency, not the speed. Speed is impressive; **auditability is what gets it
approved.**

## 6. Claims to never make

| Don't say | Because |
|---|---|
| "Replaces Power BI / Tableau" | False, and instantly identifies you as someone who has not deployed BI |
| "Enterprise-ready" / "production-grade" | No RBAC, no audit certification, no SLA, free-tier hosting |
| "More accurate than [vendor]" | No benchmark run. Spider 2.0 agentic accuracy is ~21% — nobody has solved this |
| Any invented percentage | Every number in [02](02-data-dictionary.md) is measured. Keep it that way. Fabricated precision is the classic tell |
| "Understands your business" | It reads a YAML file you wrote. Say that — it is more impressive because it is checkable |

**Instead**: *"a complement to BI, not a replacement — it fills the gap BI leaves for
exploratory, conversational analysis."* That framing was already right in the v1 plan and it
survives scrutiny.

## 7. What would genuinely make Finbot a product

Beyond the portfolio bar, in order of leverage:

1. **Bring-your-own-database.** The moment Finbot points at *someone else's* Postgres and works,
   it stops being a demo. This is a connection-string change plus schema introspection — the
   single highest-value step past Phase 9.
2. **A semantic-layer authoring assistant.** Hex ships a Semantic Model Agent for exactly this,
   because writing the YAML is the real adoption cost. An agent that drafts the registry from a
   schema, for a human to approve, is the wedge against "the semantic layer is too much setup."
3. **Scheduled monitoring.** "Tell me when fraud rate moves significantly in any segment" —
   statistical process control on top of the existing tests. Reuses Phase 7 entirely, and it is
   the natural bridge from *answering* questions to *raising* them.
4. **Regulatory grounding.** The one legitimate use for `build-kg` — an AML rule graph the agent
   can cite ([06](06-memory-and-knowledge-graph.md) §1). Genuinely differentiating in fintech,
   and a different product surface from everything above. Roadmap slide, not a build.
