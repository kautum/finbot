# 05 — Agent Stack Research (verified 2026-08-23)

Version-sensitive. Re-verify anything here before relying on it more than ~3 months out.

## 1. CopilotKit has a v2 React API — decide v1 vs v2 before writing UI code

Verified directly in the browser against `docs.copilotkit.ai`. There are now **two parallel
APIs**. v1 hooks (`useCopilotAction`) still work, but the docs say: *"we recommend migrating to
`useFrontendTool` from the v2 API."*

The v2 generative-UI surface is **six primitives**:

| Primitive | What it does |
|---|---|
| Components as Tools | Register a React component as a frontend tool the agent calls |
| **Tool Call Rendering** | **Map backend tool calls to custom UI cards — this is Finbot's chart path** |
| **State Rendering** | Subscribe to streamed agent state, re-render as values arrive — **the reasoning-trace path** |
| Reasoning | Render model reasoning tokens inline as a first-class message type |
| A2UI | Agent emits a declarative schema, composed against a catalog you register |
| MCP Apps | Sandboxed iframe UI shipped by an MCP server |

### The exact API Finbot needs (adapted from the live docs example)

`run_sql` is a **backend** tool, so the primitive is `useRenderTool`:

```tsx
import { useRenderTool } from "@copilotkit/react-core/v2";
import { z } from "zod";

const weatherParams = z.object({
  location: z.string().describe("The location to get weather for"),
});

useRenderTool({
  name: "get_weather",              // MUST match the Python @tool name exactly
  parameters: weatherParams,
  render: ({ status, parameters }) => (
    <p>{status !== "complete" ? "Calling weather API..." : `Called for ${parameters.location}.`}</p>
  ),
});
```

`useDefaultRenderTool` is the catch-all fallback for tools without a dedicated renderer —
useful during development to see every tool call:

```tsx
useDefaultRenderTool({
  render: ({ name, args, status, result }) => (/* generic card */),
});
```

**The hard contract**: the `name` string and the argument schema must match the Python tool
exactly. Drift, and CopilotKit silently falls back to no custom render, or the React component
throws destructuring args that aren't there.

### State rendering (the reasoning trace)
Frontend subscribes to agent state; each backend-forwarded value re-renders the component.
Backend emits `STATE_SNAPSHOT` events from the streaming loop (or via framework middleware).
**Caveat from the docs**: whatever is emitted mid-node is only a *prediction* — the node's
actual returned state at the end is the source of truth and overwrites anything not included
in the return. The docs state this is **not supported on CopilotKit's Built-in Agent**, only on real framework
integrations, and defer to a per-framework "framework grid".

> **⚠ UNVERIFIED — verify before building Phase 6 on it.** The docs page redirected before the
> framework grid could be read, so *"LangGraph supports state rendering"* is an inference from
> CopilotKit shipping three LangGraph integration tracks, **not** a confirmed entry in that grid.
> [07](07-roadmap.md) Phase 6 depends on this. Confirm at
> `docs.copilotkit.ai/generative-ui/state-rendering` (choose the LangChain backend) before
> committing to the design. If it turns out unsupported, the fallback is to return the
> `reasoning_trace` as part of the final tool result and render it with `useRenderTool`, which
> is confirmed to work.

Practical pattern: keep `reasoning_trace: list[dict]` in state, append in each node, emit after
each tool call, render in a collapsible panel.

### Integration paths
CopilotKit ships three LangGraph docs tracks: `/langgraph-python`, `/langgraph-fastapi`,
`/langgraph-typescript`. The repo's `add_langgraph_fastapi_endpoint` shape matches
**langgraph-fastapi** — a supported, current path.

### Install-time warning
CopilotKit has recurring ESM/CJS interop issues and a reported peer-dependency conflict on
newer React. Budget time for a `--legacy-peer-deps` fight on the first `npm install`.
`@copilotkit/react-core` and `@copilotkit/runtime` latest = **1.69.0** (pin is current).

## 2. Reasoning traces: LangSmith is the wrong tool for this

- Package is `langsmith`. Env var `LANGSMITH_TRACING=true` (old `LANGCHAIN_TRACING_V2` still works).
- **No credit card** to sign up for the free Developer tier. But there is a hard gate:
  **5,000 traces/month**, after which ingestion stops until a card is added. A hard cutoff,
  not a soft throttle.
- **LangSmith is developer observability, not a user-facing feature.** Traces live in their
  dashboard. For showing an end user "here are the 3 queries I ran", the right mechanism is
  the CopilotKit state-rendering path in §1 — no third-party dependency at all.
- Free alternative for dev-side tracing: **Langfuse** — Hobby cloud free, **no card**,
  50k units/month, 30-day retention, MIT-licensed and self-hostable via Docker in ~5 min.
  Strictly better fit for the zero-billing constraint than LangSmith.

**Recommendation: use CopilotKit state rendering for the user-facing trace. Add Langfuse
(not LangSmith) later if developer-side tracing is wanted.**

## 3. Groq free tier — the real numbers, and the real risk

From `console.groq.com/docs/rate-limits`, Free plan:

| Model | RPM | RPD | TPM | TPD |
|---|---:|---:|---:|---:|
| `openai/gpt-oss-120b` | 30 | 1,000 | **8,000** | **200,000** |
| `openai/gpt-oss-20b` | 30 | 1,000 | 8,000 | 200,000 |
| `llama-3.3-70b-versatile` | — | — | — | **DEPRECATED ~2026-06-17** |

### The arithmetic
Budget ~1,800 tokens per LLM call once SQL results are in context (a 20-row result table alone
is several hundred tokens), 8 calls per multi-step question → **~14,400 tokens/question**.

- **TPD 200,000** → ~**13–14 full questions/day**. Genuinely exhaustible in one demo session.
- **RPD 1,000** → ~125 questions/day. Not the binding constraint.
- **TPM 8,000** → **a single question doing 8 rapid round-trips can blow the per-minute cap
  within one user turn.** This is the most likely demo-day failure: a 429 mid-answer.

**Behaviour on breach is a 429 rate-limit, not account disablement** — unlike the CockroachDB
incident, Groq degrades rather than bans. But a silent 429 mid-answer looks broken to a
watching boss. **Mitigations are mandatory**: exponential backoff, a user-visible "rate
limited, retrying" state, and aggressive control of how much SQL result text re-enters context.

> The single cheapest TPM mitigation: don't feed 200 raw rows back into the model. Feed
> aggregates and a truncated preview. This is a prompt/tool-design decision, not infrastructure.

### No-card fallback providers
| Provider | Free limits | Card? | Notes |
|---|---|---|---|
| **Cerebras** | **1M tokens/day**, 15 RPM, 30K TPM, 128K ctx | No | 5x Groq's daily token budget. Best headroom. Supports function calling. |
| Google AI Studio (Gemini Flash) | ~10 RPM / 250 RPD (Flash), ~15 RPM / 1000 RPD (Flash-Lite) | No | Strongest tool-calling reliability of the group |
| OpenRouter `:free` models | 50 req/day (1,000 if ever topped up $10), 20 RPM | No | DeepSeek R1, Qwen3 Coder available |

No rigorous head-to-head benchmark for tool-calling/SQL on this specific schema was found —
**verify empirically against the real `run_sql` schema before depending on any fallback.**

## 4. LangGraph patterns for multi-step reasoning

- `create_react_agent` (`langgraph.prebuilt`) is the recommended baseline. **Finbot's
  hand-rolled `StateGraph` currently buys nothing over it** — it is the same ReAct loop with
  more code.
- Escalate to a hand-rolled graph precisely when you need what Finbot wants: parallel nodes,
  supervisor/worker, mid-execution interception, conditional retry — i.e. PLAN → EXECUTE → REFLECT.
- `Command` — a node return type combining a state update with an explicit routing decision.
  Replaces manual conditional-edge wiring.
- `interrupt()` — current human-in-the-loop primitive, resumed with `Command(resume=...)`.
  This is the mechanism for "ask a clarifying question" (§04 Hex pattern).
- `langgraph-supervisor` — prebuilt hierarchical multi-agent, if plan/execute/reflect become
  separate agents rather than nodes.
- Structured plan objects: `llm.with_structured_output(PlanSchema)` with a **Pydantic** model
  (docs prefer Pydantic over TypedDict for node-to-node handoffs — validated field access).
- Canonical example to copy: `docs.langchain.com/oss/python/langgraph/sql-agent`. Its stated
  security principle is directly applicable: **scope DB connection permissions as narrowly as
  the agent actually needs.**

`langgraph` latest = 1.2.11, matching the pin.

## 5. Statistical analysis: do NOT add a Python sandbox

Three patterns exist: (1) sandboxed arbitrary Python (E2B, Riza), (2) pure-SQL stats,
(3) a fixed set of parameterised statistical tools.

**Option 3 is correct here.** Arbitrary Python execution reopens exactly the risk class that
got `PythonREPLTool` pulled from core LangChain — and `langchain-experimental` is
**archived as of 2026-05-26**, unmaintained. Standing up E2B to run a two-proportion z-test is
disproportionate: an external service, another free-tier quota to babysit, network egress.

The needed tests are closed-form and take only scalars that `run_sql` already returned:

```python
from langchain_core.tools import tool
from statsmodels.stats.proportion import proportions_ztest, proportion_confint

@tool
def two_proportion_ztest(count_a: int, n_a: int, count_b: int, n_b: int) -> dict:
    """Two-proportion z-test, e.g. fraud rate in segment A vs segment B."""
    stat, pval = proportions_ztest([count_a, count_b], [n_a, n_b])
    return {"z_stat": float(stat), "p_value": float(pval),
            "rate_a": count_a / n_a, "rate_b": count_b / n_b}

@tool
def chi_square_independence(table: list[list[int]]) -> dict:
    """Chi-square test of independence over a contingency table of counts."""
    from scipy.stats import chi2_contingency
    chi2, p, dof, _ = chi2_contingency(table)
    return {"chi2": float(chi2), "p_value": float(p), "dof": dof}

@tool
def proportion_confidence_interval(count: int, n: int, confidence: float = 0.95) -> dict:
    """Wilson-score CI for a single proportion (e.g. fraud rate with uncertainty)."""
    lo, hi = proportion_confint(count, n, alpha=1 - confidence, method="wilson")
    return {"proportion": count / n, "ci_low": lo, "ci_high": hi}
```

`scipy` and `statsmodels` are pure computation — no execution surface, no sandbox, no new
infra. Only the aggregate counts cross the tool boundary, never raw rows or PII.

Add a sandbox only if a future requirement genuinely needs open-ended computation a fixed tool
cannot express.

## 6. Unresolved / could not verify
- Exact v1→v2 CopilotKit migration diff, and which package version v2 first shipped in.
- Whether `useCoAgentStateRender` (v1-era) has a direct v2 equivalent or was folded into the
  state-rendering primitive.
- Mistral and Together AI current free-tier numbers.
- Any rigorous benchmark comparing Gemini Flash vs Cerebras vs DeepSeek R1 on tool-calling
  for this specific schema.
