# Website / Frontend Design Instructions

A standing reference on web design resources and how to use them. Built while working on a
personal portfolio project, but written to be reusable by any agent on any project in this
account that touches frontend/web design. Not specific to that portfolio, no need to read that
project to use this file.

---

## 1. Reference links (design inspiration and tooling)

| Link | What it actually is | How to use it |
|---|---|---|
| https://motion.dev/ | **Motion**, the successor to Framer Motion. Animation library for React/JS/Vue: scroll animation, spring physics, layout animation, stagger, gestures, `pathLength` path drawing, `useScroll`/`useTransform`/`useSpring`. | Install `motion` (React: `motion/react`). Use for scroll-linked reveals, staggered entrances, number count-ups, SVG path draw-in. Prefer real spring physics (`type: "spring", stiffness: 100, damping: 20`) over linear/ease-only transitions for anything meant to feel physical. |
| https://bklit.com/ | **Bklit UI** — a data-visualisation component library (17+ chart types: area, bar, candlestick, heatmap, sankey, scatter, etc.), built on Tailwind/shadcn, partnered with Motion. | Don't install unless the project already uses Tailwind/shadcn. Otherwise steal the *ideas*: dot-texture grid with edge fade instead of solid gridlines, ring-style markers at data points, dashed reference bands/thresholds, dashed projection for incomplete/in-progress periods. All reimplementable in plain SVG + CSS. |
| https://kokonutui.com/ | **KokonutUI** — 100+ React components on Tailwind + shadcn + Motion (particle buttons, liquid-glass cards, shimmer text, AI-prompt inputs). | Same caveat as Bklit: hard-requires Tailwind/shadcn. Reimplement the visual ideas in bespoke CSS if the project isn't already on that stack: `backdrop-filter: blur()` for glass, `background-position` animation for shimmer, Motion for particle/entrance timing. |
| https://manus.im/ | An AI agent product's site. Referenced for its restraint: generous whitespace, few competing elements, calm pacing. | Use as a gut-check for "am I overcrowding this layout", not for concrete code. |
| https://github.com/gireeshkumarreddy/Project1 (live: https://portofilo22.netlify.app/) | A designer's personal portfolio, Next.js 15 + React 19 + Tailwind v4 + Framer Motion + **Lenis**. Full-bleed sections, one geometric sans-serif for all type (hierarchy from scale/weight only, no typeface mixing), scroll-scrubbed reveals ("tied to scroll position, not triggered on threshold"), procedural torn-paper edges between sections (SVG fractal displacement, not flat CSS borders). | Install **Lenis** (`npm install lenis`) for smooth scroll on any project that wants it — pair with a `prefers-reduced-motion` check to disable it. The single-typeface/hierarchy-by-scale discipline and "every visual element is structural, not decorative" principle are worth applying broadly. |
| https://mcpmarket.com/tools/skills/image-to-code-pro | A listing page for an image-to-code Claude Skill (same family as the `image-to-code-skill` inside the `taste-skill` plugin below, since it wasn't separately fetchable, rate-limited on lookup). | If doing image-to-code conversion work, check whether `leonxlnx/taste-skill`'s bundled `image-to-code-skill` covers it first before hunting for a separate tool. |
| https://github.com/leonxlnx/taste-skill | **Not a single file — a Claude Code plugin bundling 13 design skills.** Tree: `skills/brandkit`, `skills/brutalist-skill`, `skills/gpt-tasteskill`, `skills/image-to-code-skill`, `skills/imagegen-frontend-mobile`, `skills/imagegen-frontend-web`, `skills/minimalist-skill`, `skills/output-skill`, `skills/redesign-skill`, `skills/soft-skill`, `skills/stitch-skill`, `skills/taste-skill-v1`, `skills/taste-skill`. See §2 for what's actually in the important ones. | Fetch the specific `SKILL.md` you need with `gh api "repos/leonxlnx/taste-skill/contents/skills/<name>/SKILL.md" --jq '.content' \| base64 -d`. Don't assume the repo root is the skill; it's a marketplace plugin manifest. |
| https://github.com/vercel-labs/agent-skills/blob/main/skills/web-design-guidelines/SKILL.md | **A wrapper, not the content.** It's a thin CLI-tool descriptor that fetches guidelines from a second URL at runtime. | The actual rules live at `https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md`. Fetch that URL directly. See §3 for the extracted rule set. |
| https://github.com/voltagent/awesome-design-md | **The single most useful resource of the ten.** Not a link list — a repo containing `design-md/<company>/DESIGN.md` for 73 real companies' actual design systems (Linear, Vercel, Apple, Stripe, Framer, Figma, Notion, Nike, Raycast, Cursor, Warp, and more), each with real hex values, type scales, spacing, radius, and stated design principles. | List all 73: `gh api repos/voltagent/awesome-design-md/contents/design-md --jq '.[].name'`. Fetch one: `gh api "repos/voltagent/awesome-design-md/contents/design-md/<name>/DESIGN.md" --jq '.content' \| base64 -d`. Pull 3-5 that match the target aesthetic before starting a redesign, don't invent a palette from scratch. See §4 for extracted tokens from the ones already pulled. |
| https://playwright.dev/agent-cli/introduction | **Playwright Agent CLI** — a browser-automation CLI purpose-built for coding agents: token-efficient commands, installable skill-based capabilities, daemon persistence (no per-command startup cost), ref-based accessibility snapshots for deterministic interaction, multiple isolated sessions. Differs from raw Chrome DevTools Protocol by being agent-optimised rather than built for interactive human debugging. | Consider for any project needing repeated browser-driven verification (visual QA, e2e checks) where the existing chrome-devtools MCP tooling feels heavy on context. Not yet installed/trialled on this account as of writing. |

---

## 2. Extracted rules from `leonxlnx/taste-skill` (the plugin, not the repo root)

### `minimalist-skill` — "Premium Utilitarian Minimalism & Editorial UI"
A concrete protocol for clean, editorial, warm-monochrome interfaces. Key rules:
- **Banned as generic defaults**: Inter/Roboto/Open Sans, Lucide/Feather/Heroicons icon sets, heavy Tailwind shadows (`shadow-lg`+), bright primary-colour hero sections, gradients/neon/glassmorphism-everywhere, `rounded-full` on large containers, emojis anywhere, "Elevate/Seamless/Unleash/Next-Gen/Game-changer/Delve" style AI copywriting.
- Editorial serif for hero headings only (sparingly), heavy sans for body/UI, mono for code/metadata.
- Warm off-white canvas (`#F7F6F3`/`#FBFBFA`), body text never pure black, muted washed-out pastels only for tags/badges.
- Illustration directive worth knowing: *"monochromatic, rough continuous-line ink sketches on a white background, featuring a single offset geometric shape filled with a muted pastel colour"* — i.e. hand-drawn/sketch-style SVG illustration is a **named, legitimate** premium-minimalist pattern, not automatically "childish". Context and execution quality determine which it reads as.

### `brutalist-skill` — "Industrial Brutalism & Tactical Telemetry Interface Engineering"
Two archetypes, pick one, never mix:
- **Swiss Industrial Print** (light): matte off-white background, monolithic heavy sans type, aggressive negative space, one red accent only.
- **Tactical Telemetry / CRT Terminal** (dark): dark-mode exclusive (background `#0A0A0A`/`#121212`, **never pure `#000000`**), monospace-dominant, phosphor-white text, ASCII framing devices (`[ SECTION ]`, `>>>`), crosshair `+` marks, CRT scanline overlays (`repeating-linear-gradient`), global low-opacity SVG grain.
- Structural rules for either: **zero `border-radius`** (every corner 90°), `display: grid; gap: 1px` with contrasting parent/child backgrounds for razor-thin dividers instead of border declarations, macro type at `clamp(4rem, 10vw, 15rem)` with tracking `-0.03em` to `-0.06em`.
- ⚠️ This protocol *recommends* fake telemetry strings ("REV 2.6", "UNIT/D-01") for atmosphere. The `taste-skill` anti-pattern list (below) explicitly bans exactly that as "fake operator/runtime jargon". **When the two conflict: only label real data. Never invent decorative technical-sounding filler.**

### `taste-skill` (1200+ lines) — the anti-pattern authority, most valuable single file
This is the one to consult first on any "does this look AI-generated" question. Concrete, quotable rules:
- **Explicit slop list**: "AI-purple gradients, centered hero over dark mesh, three equal feature cards, generic glassmorphism on everything, infinite-loop micro-animations everywhere, Inter + slate-900."
- **Serif-as-default is banned**: *"'creative brief = serif' is the single most-tested AI tell in production rounds."* `Fraunces` and `Instrument_Serif` specifically named as banned defaults.
- **THE LILA RULE**: no automatic purple button glows, no random neon gradients.
- **PREMIUM-CONSUMER PALETTE BAN**: beige/cream + brass/clay/oxblood/ochre + espresso-near-black as a default palette family is also a tell (it's the *other* common AI aesthetic, opposite the purple one).
- **SPLIT-HEADER BAN**: "left big headline + right small explainer paragraph" as a section header pattern is banned as default.
- **EYEBROW RESTRAINT**: max one eyebrow label per 3 sections.
- **SECTION-LAYOUT-REPETITION BAN**: a layout family (e.g. image+text split) can appear at most once per page; a 3rd consecutive repeat is a fail.
- **HERO STACK DISCIPLINE**: max 4 text elements (eyebrow OR nothing / headline max 2 lines / subtext max 20 words max 4 lines / 1 primary + max 1 secondary CTA). Banned in hero: trust micro-strips, feature bullet lists, taglines under CTAs, pricing teasers.
- **Motion must be motivated**: *"Before adding any animation, ask: what does this communicate? Valid: hierarchy, storytelling, feedback, state transition. Invalid: it looked cool."* Max one marquee per page.
- **Exact motion values given**: spring `stiffness 100, damping 20`; scroll-reveal stagger `i * 0.06`, easing `[0.16, 1, 0.3, 1]`, duration 0.6s; standard transitions 200-300ms; tactile press feedback `translateY(-1px)` or `scale(0.98)`.
- **Fake-precise numbers are flagged** as an AI tell (e.g. inventing "92%" or "4.1×" with no real source) — numbers must be real, labelled as mock, or omitted.
- **Layout discipline**: `min-height: 100dvh` not `100vh`; break symmetry (split-screen, left-content/right-asset, asymmetric whitespace) once `DESIGN_VARIANCE` complexity is above trivial; centered-hero override only for genuine editorial/manifesto content.
- **COPY SELF-AUDIT**: re-read every visible string for "sounds like AI hallucination" or "reads like LLM trying to sound thoughtful", rewrite flagged ones plainly.
- **LOGO-ONLY RULE**: a logo wall is logos and nothing else, no category/industry labels underneath.

### `redesign-skill` — priority order for improving an existing page
1. Font swap (biggest instant improvement, lowest risk) → 2. Colour palette cleanup → 3. Hover/active states → 4. Layout/spacing/grid → 5. Replace generic/cliché components → 6. Loading/empty/error states → 7. Final typography/spacing polish.
Also: replace Lucide/Feather icon defaults, avoid pure `#000000`, desaturate accents below 80%, pick exactly one accent colour, lock to one grey family, use CSS Grid over flexbox percentage math, vary border-radius rather than making everything uniform, add tabular-nums to any numeric column.

### `soft-skill` — the glass/glow/gradient counterpart
Section padding `py-24` to `py-40`; macro-whitespace = double your default padding; fade-up entrance `translateY(16px) blur(md) opacity:0` → resting state over 800ms+. Use when the brief explicitly wants a soft/premium/rounded aesthetic rather than brutalist/editorial.

---

## 3. Vercel Web Interface Guidelines (the real content behind the wrapper link)

Fetch fresh at `https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md` — concrete, engineering-level rules, grouped:

- **Accessibility**: icon-only buttons need `aria-label`; `<button>` for actions, `<a>` for navigation (never `<div onClick>`); decorative icons `aria-hidden="true"`; async updates need `aria-live="polite"`; heading hierarchy `<h1>`-`<h6>` plus a skip link.
- **Focus**: visible `:focus-visible` always; never `outline: none` without a replacement; prefer `:focus-visible` over `:focus` to avoid a ring on click.
- **Animation**: honour `prefers-reduced-motion`; animate `transform`/`opacity` only (compositor-friendly); **never `transition: all`**, list properties explicitly; autoplaying motion over 5s needs a pause/stop control.
- **Typography**: real ellipsis `…` not `...`; `font-variant-numeric: tabular-nums` on any numeric column/comparison; `text-wrap: balance` on headings.
- **Images**: explicit `width`/`height` always (prevents layout shift); `loading="lazy"` below the fold; `fetchpriority="high"` for the one above-fold critical image.
- **Forms**: correct `type`/`inputmode`; never block paste; labels must be clickable; disable spellcheck on emails/codes; errors inline next to the field, focus the first error on submit.
- **Touch**: `touch-action: manipulation` to kill the double-tap-zoom delay; `overscroll-behavior: contain` inside modals/drawers.
- **Dark mode**: `color-scheme: dark` on `<html>`; matching `<meta name="theme-color">`.
- **Navigation**: use real `<a>`/`<Link>` everywhere (preserves Cmd/Ctrl-click and middle-click); reflect real state (filters/tabs/pagination) in the URL.

---

## 4. Extracted design-system tokens (from `voltagent/awesome-design-md`)

Already pulled and worth reusing directly rather than re-fetching:

**Linear** — `bg #010102` → surface ladder `#0f1011` → `#141516` → `#18191a` → `#191a1b` (hierarchy via stepped lightness, **no drop shadows on dark**, subtle white edge-highlight on a lifted panel's top edge instead); accent `#5e6ad2` used **only** for brand mark / focus ring / primary CTA, never decoratively; type: Linear Display 80/56/40px at weight 600; spacing 4/8/12/16/24/32/48/96; radius 4/6/8/12/16/24/9999(pill); focus ring 2px at 50% opacity.

**Raycast** — `bg #07080a`, ink `#f4f4f6`, dark-mode only; primary CTA pure white; chromatic accents (blue/red/green/yellow) confined **only** to feature illustrations, never on chrome; one red diagonal-stripe gradient band in the hero, max once per page; `font-feature-settings: "ss03"` site-wide as a quiet brand signature.

**Cursor** — warm cream `#f7f7f4` / warm near-black `#26251e` (not pure white/black); accent `#f54e00` scarce, CTAs and wordmark only; display type weight **400, never bold**, negative tracking — proof that a light-weight face with tight tracking can read more confident than a heavy black one; zero drop shadows, hairline depth only.

**Warp** — warm dark `#2b2622` / warm off-white `#f7f5f0`; **no chromatic accent at all**, the off-white doubles as both button fill and text; radius capped 0-4px ("almost rectangular, never pills"); hero 64px/weight 400/-1.6px tracking described as "quietly confident".

**The one pattern that repeats across every system pulled so far, and it's the single most important cross-cutting rule**: *the accent colour is never decorative.* It is reserved for the brand mark, focus rings, primary CTAs, or — in data contexts — the data itself. Ambient glow, background washes, and page furniture in the accent colour are what make a page look AI-generated. Data/CTAs glow; the page around them does not.

---

## 5. General working notes for any agent using this file

- **Prefer bespoke CSS + Motion over adopting a component library** (Bklit/KokonutUI both hard-require Tailwind+shadcn) unless the target project is already on that stack. Steal the *visual idea*, reimplement natively.
- **Compute contrast ratios, never eyeball them.** WCAG AA = 4.5:1 body text, 3:1 large text/non-text UI. This applies doubly on any dark or glowing palette, since accent colours often fail contrast in one theme even when they look fine in the other — check both explicitly if the project is dual-theme.
- **`prefers-reduced-motion` and `(hover: hover) and (pointer: fine)` are hard gates**, not nice-to-haves, for any cursor-following, parallax, or WebGL effect. Disable the whole system on touch/coarse-pointer devices, don't just reduce it.
- **A hard-edged rectangular canvas/WebGL layer sitting over a differently-coloured background reads as a pasted image block.** If adding a canvas/3D layer over page content, mask its edges (radial gradient mask, `mix-blend-mode`) so it dissolves into the page rather than sitting in a visible box, and pick blend mode per theme (`screen` on dark to add light, `multiply`/lower opacity on light so it doesn't just look like a grey smear).
- **When forking parallel agents on a shared file tree**: give each agent exclusive ownership of specific files and tell them explicitly not to touch anything else, or work collides. A shared dev server / `.next` build cache being hit by two agents' `npm run build` at once will corrupt itself.
- **Verify accessibility trees, not just visuals**: `role="img"` on an `<svg>` silently swallows all focusable descendants from the a11y tree. If an SVG contains real interactive/focusable elements, put the descriptive label on a wrapping element with `role="group"`, not on the svg itself.
