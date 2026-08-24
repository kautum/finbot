# 11 — UI Plan: CopilotKit × the design system

How the chat UI gets built, reconciling CopilotKit's actual API
([05](05-research-agent-stack.md) §1, verified live in-browser) with the design rules in
[`website-instructions.md`](website-instructions.md).

## 1. What the repo actually has

| | State |
|---|---|
| Next.js 16.3.2 / React 19.2.8 | installed |
| `@copilotkit/react-core`, `react-ui`, `runtime` @ ^1.69.0 | installed, current |
| **Tailwind v4** (`@tailwindcss/postcss`, `tailwindcss: ^4`) | **installed** |
| Chart library | **none** |
| Motion / animation library | **none** |
| UI written | `<CopilotChat>` and nothing else |

> **This changes one standing recommendation.** `website-instructions.md` §1 says not to install
> Bklit UI or KokonutUI *"unless the project already uses Tailwind/shadcn."* **This project does
> use Tailwind v4.** So Tailwind/shadcn-based component libraries are legitimately on the table
> here, unlike in the portfolio project that guidance was written for.

## 2. The design direction

`website-instructions.md` §4 identifies one cross-cutting rule from all 73 design systems
surveyed, and it happens to be *written for exactly this kind of product*:

> *"The accent colour is never decorative. It is reserved for the brand mark, focus rings,
> primary CTAs, or — in data contexts — the data itself. Data/CTAs glow; the page around them
> does not."*

For an analyst tool this is the whole brief. **The chart is the only thing allowed to be
colourful.** Chrome, chat bubbles, sidebars and panels stay in one grey family.

**Recommended: Linear's dark surface ladder**, which is the closest fit of the four sets of
tokens already extracted:

```
bg          #010102
surfaces    #0f1011 → #141516 → #18191a → #191a1b   (hierarchy by stepped lightness)
depth       NO drop shadows on dark; subtle white top-edge highlight on a lifted panel
accent      #5e6ad2 — brand mark, focus ring, primary CTA ONLY
spacing     4 / 8 / 12 / 16 / 24 / 32 / 48 / 96
radius      4 / 6 / 8 / 12 / 16 / 24 / 9999
focus ring  2px @ 50% opacity
```

Rationale over the alternatives: Warp's zero-accent palette leaves nothing to colour data with;
Cursor's warm cream reads consumer rather than analytical; Raycast confines chromatic colour to
illustrations, which is the opposite of what a chart needs.

### Anti-patterns that are disqualifying here
From `website-instructions.md` §2 — these are the tells that make a product look AI-generated:
AI-purple gradients, centred hero over dark mesh, three equal feature cards, glassmorphism
everywhere, infinite-loop micro-animations, **Inter + slate-900**, serif-as-default
(`Fraunces`/`Instrument_Serif` named explicitly), and **fake-precise invented numbers**.

That last one is worth restating for this project specifically: **every number on screen must
come from a real query.** No placeholder "94% accuracy" badge, no mock sparkline in an empty
state. [02](02-data-dictionary.md) has plenty of real figures if a number is needed.

Also relevant: the **brutalist skill recommends** decorative telemetry strings ("REV 2.6",
"UNIT/D-01") for atmosphere, while the taste-skill **bans exactly that** as fake operator
jargon. `website-instructions.md` §2 already resolves the conflict — **only label real data**.

## 3. Component plan

### 3.1 Keep `<CopilotChat>` initially; go headless only if it fights you
CopilotKit ships `@copilotkit/react-ui/styles.css`, already imported in `layout.tsx`. Restyle via
CSS variables and overrides first. Rewriting the chat shell before the agent is trustworthy
inverts the sequencing warning in [07](07-roadmap.md).

> **Constraint found**: CopilotKit's **Rich Threads** — persistent, resumable, multi-device
> conversation history with a thread sidebar — **runs on their Enterprise Intelligence Platform**,
> not on the OSS runtime alone. There is a free Developer tier, but it is another hosted-service
> signup, and the docs note it *"does not list or mutate native LangGraph stores unless your
> backend explicitly bridges those systems."*
>
> Given the zero-billing/no-new-accounts posture and that Finbot already plans its own
> `SqliteSaver` checkpointing ([06](06-memory-and-knowledge-graph.md) §2.1), **skip Rich Threads.
> Single-thread chat is fine for the demo.** Revisit only if multi-conversation history becomes
> a requirement.

### 3.2 The chart — `useRenderTool`
The verified v2 API ([05](05-research-agent-stack.md) §1):

```tsx
import { useRenderTool } from "@copilotkit/react-core/v2";

useRenderTool({
  name: "run_sql",              // MUST match the Python @tool name exactly
  parameters: runSqlParams,     // zod schema mirroring the Python signature
  render: ({ status, parameters, result }) =>
    status !== "complete"
      ? <QuerySkeleton sql={parameters.query} />
      : <ResultView data={result} />,
});
```

`ResultView` picks its own form from the result shape — that decision belongs in one place:

| Result shape | Render |
|---|---|
| 1 row × 1 col | Big number + label + denominator |
| 1 categorical + 1 numeric, ≤12 rows | Horizontal bar |
| date + numeric | Line |
| 2 categorical + 1 numeric | Grouped bar or small-multiples |
| anything else | Table |

**Before writing any chart code, load the `dataviz` skill.** It exists precisely for this — the
palette formula, mark specs, stat-tile and legend/axis rules — and it keeps light and dark
consistent. Do not hand-pick chart colours.

### 3.3 The reasoning-trace panel — state rendering
Stream the `reasoning_trace` state field ([07](07-roadmap.md) Phase 6). A collapsed strip under
each answer — *"3 queries · 2 governed definitions"* — expanding to the steps.

Docs caveat, already noted: mid-node emitted state is a *prediction*; the node's returned state
overwrites it. Include the trace in the return.

### 3.4 `useDefaultRenderTool` during development
Catch-all renderer showing every tool call, name, args and result. Turn it off for the demo.

## 4. Non-negotiable interface rules

From `website-instructions.md` §3 (Vercel Web Interface Guidelines), the ones that actually bite
in a streaming chat with numeric tables:

- **`font-variant-numeric: tabular-nums`** on every numeric column. In a fraud-rate table with
  proportional figures, columns visibly fail to line up.
- **`aria-live="polite"`** on the streaming answer region — otherwise a screen reader never
  announces the answer.
- **`prefers-reduced-motion`** honoured; animate **`transform`/`opacity` only**; **never
  `transition: all`**.
- Real `…` not `...`; `text-wrap: balance` on headings.
- Visible `:focus-visible`; never `outline: none` without a replacement.
- `<button>` for actions, `<a>` for navigation. Icon-only buttons need `aria-label`.
- **Compute contrast ratios, do not eyeball them.** 4.5:1 body, 3:1 large/non-text. Chart series
  colours on `#010102` are exactly where this fails silently.
- Wide tables scroll inside their own `overflow-x: auto`; the page body never scrolls sideways.

Accessibility-tree trap worth repeating: **`role="img"` on an `<svg>` silently removes all
focusable descendants from the a11y tree.** If a chart has interactive points, label a wrapping
element with `role="group"` instead.

## 5. Motion

Motion must be motivated — *"what does this communicate? Valid: hierarchy, storytelling,
feedback, state transition. Invalid: it looked cool."* Exact values already extracted:

| Use | Value |
|---|---|
| Spring | `stiffness: 100, damping: 20` |
| Reveal stagger | `i * 0.06` |
| Easing | `[0.16, 1, 0.3, 1]`, 0.6 s |
| Standard transitions | 200–300 ms |
| Press feedback | `translateY(-1px)` or `scale(0.98)` |

Three motivated animations, and no more:
1. **Chart entrance** — bars/lines draw in on arrival. Communicates "this is new".
2. **Trace-step arrival** — each reasoning step fades up as it streams. Communicates progress,
   which is the whole point of the panel.
3. **Number count-up** on a headline stat. Draws the eye to the answer.

Installing `motion` is justified for these; do not install it before there is something to animate.

## 6. The three screens

1. **Empty state.** The hardest screen and the one usually skipped. It must teach what to ask. A
   one-line description plus **3–4 real starter questions drawn from
   [02](02-data-dictionary.md) §8** — the ones with known, genuinely interesting answers. No
   fake preview chart.
2. **Conversation.** Question → reasoning strip → answer → chart/table. The answer leads; the
   trace is collapsed by default; the chart sits inline.
3. **Error / refusal.** The differentiating screen ([08](08-positioning.md) §2). When the agent
   declines on insufficient data, that must look *deliberate and authoritative* — not like a
   crash. A distinct treatment, explanatory copy, and a suggested broader question. Design this
   properly; it is a feature, not an error path.

## 7. Sequencing

1. `npm install`, get `<CopilotChat>` talking to the backend. **Nothing else until a message
   round-trips.** Budget time for a `--legacy-peer-deps` dependency fight.
2. Apply tokens and typography to the prebuilt chat. Cheapest visible win, per the
   `redesign-skill` priority order (font → palette → states → layout).
3. `useDefaultRenderTool` to see raw tool calls.
4. `ResultView` + the first real chart (load `dataviz` first).
5. Trace panel.
6. Empty state and refusal state.
7. Motion, last.

## 8. Open questions to resolve before building

- **v1 or v2 CopilotKit API?** Recommendation: **v2** — the docs already steer away from
  `useCopilotAction`. Decide before writing UI code; it changes every render line.
- **Chart implementation**: bespoke SVG, Recharts, or a Tailwind/shadcn data-viz library (now
  viable given Tailwind v4 is present). Bespoke gives full control of the palette but costs the
  most time. Unresolved — decide with `dataviz` loaded.
- **Does `@copilotkit/react-ui/styles.css` expose CSS variables**, or does restyling require
  overriding class names? Not verified. If overrides prove brittle, the headless path is the
  fallback.
