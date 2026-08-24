# 16 — The built UI: discovery, theming, charts

What actually exists in `frontend/` as of 2026-08-24, why it is shaped this way, and the
CopilotKit v2 details that cost time to discover.

Supersedes the speculative parts of [11 — UI Plan](11-ui-plan.md). Where they disagree,
this page is what is on screen.

---

## 1. The problem this solves

A chat box over a database is a blank page. The user does not know what data exists, what
questions are answerable, or what vocabulary the agent understands. Every product in this
space ships an answer to that, and they converge:

- **Databricks Genie** — "sample questions… to present to people who are talking to a Genie
  if they're not sure what to ask", plus a Catalog Explorer showing table and column
  documentation.
- **ThoughtSpot Spotter** — "automatic quickstart suggestions" on the homepage; a data
  source picker.
- **shapeof.ai's Follow Up pattern** — conversation extenders after each answer, grounded
  in the previous exchange. Explicit anti-pattern: generic suggestions unconnected to what
  was just said.

Finbot ships all three.

## 2. What is on screen

**Header** — dataset counts pulled live, a `Data` toggle, a theme toggle.

**Onboarding hero** (before the first message) — headline naming the real row count, plus
categorised sample questions in four tabs: *Fraud · Spending · Customers · Deep dives*.
Grouped by kind of analysis, not by table: the user is picking a question, not planning a
join. Clicking one sends it via `agent.addMessage()` + `agent.runAgent()`.

**Data panel** (right, collapsible) — five measured stat cards, a fraud-rate-by-channel bar
group, four expandable field groups in plain English ("Transaction / Merchant / Card /
Cardholder"), and the labelled-subset caveat in a tinted box.

**Per-answer** — a collapsible SQL card per query showing the exact statement and row count;
inline Recharts charts; dynamic follow-up suggestions after the first message.

Everything in the panel is **measured at server startup**, not hardcoded — `agent/catalog.py`
runs the counts against DuckDB and `/overview` serves them. A hand-maintained data dictionary
drifts; this one cannot.

## 3. Design system

Follows `wiki/website-instructions.md` §4. Light by default — the previous dark-first build
read as a terminal, and Genie/Spotter/Hex are all light by default.

- Surface ladder rather than shadows on dark; real shadows on light.
- **The brand colour is never decorative.** Brand mark, focus rings, primary actions, and
  the data itself. No ambient glow, no gradient furniture.
- Token named `--brand`, *not* `--accent` — CopilotKit's stylesheet already owns `--accent`
  as a surface token. Two meanings on one name is how a theme silently falls apart.
- Red means fraud everywhere it appears. Semantic, not ornamental.
- `tabular-nums` on every figure; `text-wrap: balance` on headings; `prefers-reduced-motion`
  and `(hover: hover) and (pointer: fine)` both gated.

**Charts** switch to horizontal bars above 12 categories. Upright labels collide into an
unreadable smear at that point regardless of rotation — observed at 36 and 47 categories.
Recharts' default category tick also *wraps* to fit the axis width, which makes adjacent
labels overlap; a custom single-line `<text>` tick fixes it.

## 4. CopilotKit v2 findings

Version pinned: `@copilotkit/*` 1.69.0, `@copilotkit/react-core/v2` subpath.

1. **`useRenderTool` requires a `parameters` schema.** The no-schema overload only accepts
   `name: "*"`. Any Standard Schema library works; zod is installed for this.
2. **Props are `props.parameters`, not `props.args`.** And `render` must return an element —
   `null` fails the type check. Return `<></>`.
3. **The render callback receives `result` only in the `complete` state.** Narrow with
   `"result" in props`.
4. **`agentId` must be passed explicitly** to `CopilotChat`, `useRenderTool`, and
   `useConfigureSuggestions` (`providerAgentId`). Otherwise it looks for an agent literally
   named `default` and throws *"Agent 'default' not found… Known agents: [finbot_agent]"*.
5. **v2 themes off a `.dark` class, not a data attribute.** Our tokens key off
   `[data-theme="dark"]`; with only the attribute set, CopilotKit's `dark:` variants never
   fire and the chat renders near-black text on a dark background. **Set both.**
6. **`CopilotChat` has no `suggestions` prop** — use the `useConfigureSuggestions` hook.
   Static config takes `{title, message}[]`; dynamic takes an `instructions` prompt and
   generates them from the conversation.
7. **The chat paints opaque white** at `.copilotKitChat`, `.copilotKitMessages`,
   `.copilotKitMessage`, `.copilotKitAssistantMessage`, and `.copilotKitInput`. All must be
   made transparent or token-driven, or dark mode shows white slabs.
8. **`GET /api/copilotkit/info` 404s** — the v2 client probes it on load. Agent discovery
   still succeeds over POST, so it is console noise only; a `[[...rest]]` route would fix it.
   A `GET` export on the base route does **not** — that path is a child segment.

## 5. Bugs this build surfaced

Each was caught by running the thing, not by reading the code.

| Bug | How it showed | Root cause |
|---|---|---|
| `mcc_description` NULL on all 8.9M rows | The agent honestly refused a question about Italian merchants | `read_json` reads a flat JSON object as one 109-column row; needs `UNPIVOT`. Row-count assertions passed — a failed LEFT JOIN keeps the count and nulls the columns. **Now asserted per column.** |
| `LIMIT 10 LIMIT 200` syntax error | Query failed in the UI | The auto-LIMIT guard checked for `" LIMIT "` with spaces; the model formats SQL across lines, so it arrives as `"\nLIMIT 10"`. Now a regex on the tail. |
| Agent ran 15+ queries on a vague question | 3-minute hang | The 4-query budget was prompt-only. **Now enforced in `call_model`** — past the cap the tools are unbound and the model must answer. |
| Agent stalled deliberating whether to chart | Long reasoning trace, no chart | Two prompt rules contradicted: "always chart multi-row results" vs "keep charts under 40 points". At 47 rows it had no legal move. Hex documented exactly this collapse mode. |
| Registry said 109 categories | Model repeated it, panel said 108 | 109 distinct `mcc` codes, 108 distinct descriptions — two codes share a name. |

The pattern: **a prompt instruction is advice; only structure is a rule.** Governed views,
the driver-level read-only attach, and the query budget all work because they are
unavailable to ignore. Every rule left in prose was, at some point, ignored.

## 6. Not built yet

- Stats result rendering — see [15](15-statistics.md) §6.
- Reasoning-trace panel as a distinct surface. CopilotKit's built-in "Thought for N seconds"
  disclosure covers much of it for free.
- Starter-question chips do not yet show the dynamic follow-ups verifiably; the hook is
  configured but was not confirmed on screen.
- No mobile layout pass. The data panel is desktop-only in practice.
- Deployment. Still local-only: backend `:8123`, frontend `:3001`.
