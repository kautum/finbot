# 17 — The rate-limit failure

**Read this before touching `agent/agent.py`, the model config, or anything that adds to the
prompt.** Written 2026-08-27. Every number here was measured against Groq's own token counter
or read out of Render's logs — none of it is estimated.

**One-line summary: the deploy works, the product does not.** Finbot is live at both ends and
answers correctly when it answers at all, but a single question costs more tokens than the
free Groq tier allows in a minute, so real use crashes. This is an arithmetic problem, not a
bug, and no amount of retrying fixes it.

---

## 1. Symptom

The site loads, the data panel is correct, the chat accepts a question — and then hangs or dies
mid-answer. Intermittent enough to look like flakiness. It is not flaky; it is deterministic,
and the reason it *sometimes* works is explained in §5.

## 2. The crash, from the logs

`agent/server.py` runs uvicorn at `log_level="warning"`, so there are no access logs — the only
thing that reaches Render's log stream is an unhandled stack trace. Two of them exist:

```
2026-08-25T21:18:03  Traceback (most recent call last):
2026-08-25T21:18:04  Traceback (most recent call last):
...
groq.APIStatusError: Error code: 413 - {'error': {'message': 'Request too large for model
`openai/gpt-oss-120b` in organization `org_...` service tier `on_demand` on tokens per
minute (TPM): Limit 8000, Requested 8217, please reduce your message size and try again.
...', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
During task with name 'agent' and id '7cfce635-...'
```

The traceback runs `starlette.responses.stream_response` → `ag_ui_langgraph` →
`langgraph.pregel` → `agent/agent.py:234 call_model` → `langchain_groq` → `groq._base_client`.
It is raised **inside the SSE generator**, so the event stream simply stops. The browser gets a
half-finished response with no `RUN_ERROR` and no `RUN_FINISHED` — which is why it presents as
a hang rather than an error message.

A keyword sweep of the whole retained log history:

| pattern | hits |
|---|---|
| `Error code: 413` / `rate_limit_exceeded` | 2 |
| `Traceback` | 6 |
| `Error code: 429` | 0 |
| `Out of memory` / `MemoryError` / `Killed` | 0 |
| `TimeoutError` / `APIConnectionError` / `RUN_ERROR` | 0 |

Four of the six tracebacks are the 20:25–20:42 build failures already fixed in
[03 §9](03-infrastructure-decision.md). **The 413 is the only runtime failure that has ever
happened.** Memory is not the problem, DuckDB is not the problem, the 292 MB attach is not the
problem.

## 3. Why — the token arithmetic

The free tier's ceiling, read from the response headers (`x-ratelimit-limit-tokens`), is
**8,000 tokens per minute** and 1,000 requests per day.

That budget is **per minute, shared across every call**, and one user question makes several.
I rebuilt the exact message history from a successful live run and priced each round trip
against Groq. This is the *cheapest possible* question — one SQL query, a 3-row result, no
chart, a one-sentence answer:

| call | prompt tokens |
|---|---|
| `agent/run` — first pass | 2,685 |
| `agent/run` — after the SQL result | 2,855 |
| `agent/suggest` — follow-up suggestions | 2,951 |
| **total inside one minute** | **8,491** |
| **free-tier ceiling** | **8,000** |

The best case is already 6% over. A question that returns 60 rows and draws a chart adds a
fourth and fifth call and a much larger history — 15,000–25,000 tokens is the realistic range.

## 4. Where the tokens actually go

**94% of that total is the same static prefix, resent on every call.** The conversation is
almost irrelevant. Measured with the real bound tools:

| payload | prompt tokens |
|---|---|
| system prompt + 5 tool schemas + `"hi"` (**the floor**) | **2,675** |
| system prompt alone, no tools | 1,782 |
| tool schemas alone, no system prompt | 965 |
| floor minus `tavily_search` | 2,460 |
| floor minus `tavily_search` **and** minus `metrics.yaml` | 1,659 |

Raw sizes behind those numbers: `SYSTEM_PROMPT` is 6,957 chars, of which `metrics.yaml`
contributes 3,139. The five tool schemas serialise to 10,251 chars, and **`tavily_search` alone
is 6,493 of them — 63% of all tool schema text** for a tool the analyst path rarely needs.

## 5. Four contributing causes, in order of size

1. **`metrics.yaml` is injected whole into every system prompt** (`agent.py:43`). ~800 tokens
   on every call, ~2,400 per question. It is governed-metric grounding that the model mostly
   does not consult on any given turn.
2. **Suggestions run through the full agent.** `frontend/app/page.tsx:71-80` sets
   `providerAgentId: AGENT_ID`, so `useConfigureSuggestions` resends the entire system prompt,
   all five tool schemas and the whole finished conversation — 2,951 tokens — purely to write
   three follow-up questions under nine words each. This is visible in the Vercel logs as
   **paired simultaneous `POST /api/copilotkit`** entries.
3. **`tavily_search` is bound on every call** at ~215 tokens of schema, though it is only
   relevant to questions the database cannot answer.
4. **Tool results re-enter the history in full.** `run_sql` caps its preview at 60 rows
   (`agent.py:116`), which was already a deliberate TPM defence — but 60 rows of JSON is still
   large, and it is paid again on every subsequent call in the turn.

**Why it sometimes works.** A single short question, asked into a fresh token window, with a
tiny result and no chart, lands just under the ceiling — that is exactly the shape of the
verification run recorded in [03 §9](03-infrastructure-decision.md), which passed honestly and
proved the plumbing while missing the ceiling entirely. Add the suggestions call, a second
question in the same minute, or a real result set, and it fails. **A green end-to-end test is
not evidence that the token budget holds.**

## 6. The retry wrapper does not cover this

`agent/agent.py:93` sets `max_retries=4` on `ChatGroq`, and [07](07-roadmap.md) listed
retry/backoff as mandatory before opening the demo. It does not help here:

- LangChain retries `groq.RateLimitError`, which is **HTTP 429**.
- Groq returns this as **HTTP 413**, surfacing as a bare `groq.APIStatusError`.
- Evidence it never retried: the two tracebacks are **one second apart**. Four exponential
  backoff attempts cannot fit in one second.

The `code` field does say `rate_limit_exceeded`, so it *is* a rate limit — it just arrives with
a status code the retry layer does not recognise. Any fix must catch `APIStatusError` and
branch on the status, not on the exception class.

## 7. Switching models does not fix it

Every active chat model on the free tier carries the same 8,000 TPM ceiling. Measured:

| model | TPM | requests/day |
|---|---|---|
| `openai/gpt-oss-120b` (current) | 8,000 | 1,000 |
| `openai/gpt-oss-20b` | 8,000 | 1,000 |
| `openai/gpt-oss-safeguard-20b` | 8,000 | 1,000 |
| `qwen/qwen3.6-27b` | 8,000 | 1,000 |
| `groq/compound` | **70,000** | **250** |
| `groq/compound-mini` | **70,000** | **250** |

Note also that `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `moonshotai/kimi-k2-instruct`
and `qwen/qwen3-32b` **no longer exist on Groq** — they return no rate-limit headers and are
absent from `/v1/models`. Any wiki page or doc that names them as an option is out of date.

The `compound` models are the only ones with real headroom, but they are agentic systems with
built-in tools rather than plain chat models, and whether they accept Finbot's five custom
tools is **untested**. Worth one experiment; not worth assuming.

**Changing provider might.** [05 §3](05-research-agent-stack.md) already researched no-card
fallbacks, and **Cerebras allows 30,000 TPM and 1M tokens/day with no credit card** — roughly
4× Groq's per-minute ceiling, which would clear the current 8,491-token question outright and
without touching the prompt. It supports function calling. This is the single highest-leverage
option on the table and it respects the zero-billing constraint. It is also **untested against
Finbot's actual tool schemas**, and [05](05-research-agent-stack.md) is explicit that fallback
providers must be verified empirically against the real `run_sql` schema before being depended
on. Do that experiment before the prompt surgery in §10 item 2 — if Cerebras handles the tools,
item 2's trade-off disappears entirely.

## 7b. This was predicted

[05 §3](05-research-agent-stack.md) called it, in writing, before the build:

> *"**TPM 8,000** → still the sharpest edge: the hardest question consumed 12,559 tokens, and
> if its 6 calls land inside one minute it exceeds the per-minute cap mid-answer. This remains
> the most likely demo-day failure."*

It also declared mitigations "mandatory": backoff, a visible "rate limited, retrying" state,
and control of how much result text re-enters context. Two of the three were built —
`max_retries=4` and the 60-row cap in `run_sql`. The demo shipped anyway, because the
end-to-end verification passed. **The research was right and the verification was not wrong —
it just never tested the thing the research warned about.** That gap is the lesson: when a page
names a specific failure as most likely, the exit check for that phase has to be a test that
would *catch* it, not a happy path that avoids it.

One detail 05 got wrong mattered enormously: it predicted a **429**. Groq sends **413**, which
LangChain's retry layer ignores — see §6. Corrected in place on that page.

## 8. The second, separate failure: cold start

Measured today: `GET /health` on a sleeping service took **51.3 seconds**. Warm, the same
backend answers a full chat question in **4.3 seconds**.

`frontend/app/api/copilotkit/route.ts` sets no `maxDuration`, and there is no `vercel.json`, so
the function runs on Vercel's default ceiling of 60s. **A cold start of 51s against a 60s
ceiling is a race the demo will sometimes lose**, and when it loses, the user sees exactly what
the 413 looks like: a hang. Two distinct root causes, one indistinguishable symptom — which is
why this needs fixing even though it is not what crashed on the 25th.

## 9. Blind spot found while diagnosing this

`server.py` runs uvicorn with `log_level="warning"`. There are **no request logs at all** — the
entire log stream since 2026-08-26 is four lines, all service-start notices. Diagnosis worked
only because the exception happened to be unhandled and printed a stack trace. A handled error,
a slow query, or a 4xx from the frontend would leave no trace whatsoever. Fixing the rate limit
without fixing this means the next failure is invisible.

## 10. The plan

Ranked by measured tokens saved per question. Items 1, 3, 5 and 6 do not change answer quality;
item 2 does, and needs an owner decision.

**0. First, spend an hour testing Cerebras** (§7). 30,000 TPM with no card would clear the whole
problem without touching a line of the prompt, and the only question is whether it drives the
five tool schemas as reliably as Groq. If it does, items 2 and 6 become unnecessary and item 1
becomes optional. If it does not, nothing is lost and the list below stands. **Do this before
committing to any of the token-shaving work** — otherwise you may trade away metric grounding
to solve a problem a provider swap would have removed.

**1. Take suggestions off the agent path.** Point `useConfigureSuggestions` at a bare model with
no tools and no system prompt, or disable it. **Saves 2,951 tokens/question**, taking one
question from 8,491 to 5,540 — under the ceiling on its own. Smallest possible diff, biggest
single win.

**2. Cut the static prefix from 2,675 to 1,659.** Move `metrics.yaml` behind a lookup tool
instead of injecting it wholesale, and bind `tavily_search` only when a question actually needs
the web. **Saves ~1,000 tokens on every call**, ~2,000 more per question, taking a question to
~3,500 and allowing two per minute. *Trade-off:* the model loses always-on sight of the governed
metric definitions, which is the thing [08](08-positioning.md) argues is the product. Do not do
this silently — if the registry moves behind a tool, the system prompt must still list the
metric *names* so the model knows to ask.

**3. Make the 413 survivable.** Catch `groq.APIStatusError`, branch on `status_code == 413`,
read `x-ratelimit-reset-tokens` from the response headers, wait, retry once. Emit a proper
`RUN_ERROR` so the stream closes cleanly instead of truncating. Surface "rate limited, retrying"
in the UI. This converts a silent hang into an honest delay — the trust-boundary rule in its
clearest form: a path that can fail without saying so must fail loudly instead.

**4. Pace requests against the real budget.** Even with 1 and 2 done, two questions in the same
minute still exceed 8,000. Track `x-ratelimit-remaining-tokens` server-side and *wait* when the
next call will not fit, rather than firing it and failing. At ~3,500 tokens/question that yields
roughly two questions per minute — slow, but honest and never broken. This is what makes the
demo robust rather than merely less fragile.

**5. Fix the cold-start race.** Set `maxDuration = 60` explicitly on the copilotkit route, add a
"waking the backend, up to a minute" UI state distinct from the offline banner, and warm the URL
before any demo.

**6. Turn request logging on.** `log_level="info"` at minimum; ideally log each agent turn's
prompt-token count so the budget is observable instead of inferred.

## 11. What this does not justify

**Upgrading to Groq's Dev Tier is billing**, and [00 §Hard constraints](00-INDEX.md) rules it
out until the product is proven. It is the obvious fix and it is off the table; do not propose
it first. Items 1–4 bring a question to ~3,500 tokens, which fits the free tier with room to
spare. Solve it with arithmetic before solving it with money.

## 12. How to re-measure

Everything above is reproducible. The rate-limit ceiling for any model:

```bash
curl -s -D - -o /dev/null https://api.groq.com/openai/v1/chat/completions \
  -H "Authorization: Bearer $GROQ_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-oss-120b","messages":[{"role":"user","content":"hi"}],"max_tokens":1}' \
  | grep -i x-ratelimit
```

The prompt-token cost of any payload: POST it with `"max_tokens":1` and read
`usage.prompt_tokens` — that is Groq's own count, not an estimate. To price the static floor,
build the body from `agent.SYSTEM_PROMPT` plus `convert_to_openai_tool` over `agent.tools`.

Render logs (there is no MCP path for this — use the REST API, per
[03 §9](03-infrastructure-decision.md)):

```bash
curl -s -H "Authorization: Bearer $RENDER_API_KEY" --get \
  "https://api.render.com/v1/logs" \
  --data-urlencode "ownerId=tea-da6vdvajnfac73a8jfpg" \
  --data-urlencode "resource=srv-da6vjf26iojc73fvdu1g" \
  --data-urlencode "text=413" --data-urlencode "limit=100"
```
