# 15 — Statistical inference

**Status: built and verified, NOT yet wired into the agent.** `agent/statistics.py` passes
its full oracle suite. The remaining work is registering the tools in `agent/agent.py`,
documenting them in the system prompt, and rendering results in the UI — see §6.

This is the layer that makes Finbot an analyst rather than a chart generator. Power BI
shows you *that* online fraud is higher than in-person. It will not tell you whether that
gap is real, how precisely it is known, or whether it is large enough to act on.

---

## 1. The finding that shaped the whole design

**Cohen's h — the textbook effect size for comparing two proportions — is unusable on this
dataset, and using it would have produced a confidently wrong headline.**

Measured directly:

| Comparison | Risk ratio | Cohen's h | h verdict |
|---|---|---|---|
| Online vs in-person domestic fraud | **53.0×** | 0.158 | "negligible" |
| Trivial gap, 1.02% vs 1.00% | 1.02× | 0.0005 | "negligible" |
| Mid-range, 60% vs 30% | 2.0× | 0.613 | "medium" |

The arcsine transform behind h compresses hard as *p* approaches zero. Cohen's conventions
(0.2 / 0.5 / 0.8) were calibrated on mid-range proportions. On fraud data living at
0.0158%–0.8378%, h systematically understates the effect: **a 53× difference and a 1.02×
difference land in the same band.**

Had the verdict been gated on h, Finbot would have reported the single most important
finding in the dataset — the 353× channel spread — as "negligible".

**Resolution: practical significance is judged on the risk ratio.** Bands, deliberately
conservative: `<1.1× negligible · <1.5× small · <3× moderate · ≥3× large`. Cohen's h is
still reported, carrying an explicit caveat, because it is what a reviewer will look for.

This is recorded here because it is not in the textbooks — they discuss h without the
rare-event caveat — and because it is the kind of error that produces a plausible number
rather than a crash.

## 2. The other trap: N is too large for p-values to mean anything alone

With 8,914,963 labelled rows, almost any difference reaches p < 0.05. The online-vs-domestic
z-statistic is **235**, and the p-value underflows float64 entirely (reported as `< 1e-300`,
never as `0`, which would be a false precision claim).

A p-value at this scale is largely a measure of the sample size. So every comparison returns
four things, and the verdict answers two separate questions:

- **Is it real?** p-value, with the test named.
- **Is it big?** risk ratio with CI, absolute difference in percentage points with CI, and
  Cohen's h for reference.

When a result is significant but the ratio is under 1.1×, the tool says so in as many words:
*"With 20,000,000 transactions, differences this small reach significance without being
worth acting on — the p-value is detecting the sample size, not an important gap."*

## 3. Methods chosen, and why

| Need | Method | Why not the obvious alternative |
|---|---|---|
| CI for one rate | **Wilson score** | Wald has badly wrong coverage as p→0 and returns negative lower bounds. Wilson stays in [0,1] and holds near-nominal coverage. Clopper–Pearson is valid but needlessly conservative. |
| Two rates, test | **z-test, pooled SE** | The test assumes H₀ (rates equal), so pooling is correct *here*. |
| Two rates, interval | **Newcombe hybrid score, unpooled** | A CI makes no null assumption, so it must not pool. Using the pooled SE for both is a classic and silent error. |
| Small counts | **Fisher's exact** | Automatic fallback when any expected cell < 5. Capped at N ≤ 100,000, above which it is slow and unnecessary. |
| 3+ groups | **Chi-square + Benjamini–Hochberg** | Testing 108 categories at α=0.05 yields ~5 false positives by construction. Ranking on uncorrected p-values is how spurious findings get demoed. |

## 4. Refusals, not guesses

Every degenerate input either raises `StatsError` or returns an explicit refusal. Nothing
returns a plausible-looking number it cannot justify.

- events > trials, negative counts, fractional counts, NaN/inf, strings, booleans → raise
- zero trials → raise
- fewer than 3 groups to `compare_many_rates`, mismatched array lengths → raise
- confidence outside (0,1) → raise
- **no events in either group** → "nothing to test; the segments are probably too small"
- **expected cell < 5 and N too large for Fisher** → "cannot test reliably, compare coarser
  segments"
- **risk ratio with a zero-event group** → reported as undefined, not as infinity
- **fewer than 30 events** in a single-rate interval → "too imprecise to rank against other
  segments"
- **zero events observed** → "the rate could still be as high as X% — absence of events is
  not proof of a zero rate"

## 5. Verification

Oracle checks in `agent/statistics.py::_selftest`, all passing. Verified against sources
outside the module, not just self-consistency:

- **Wilson** against closed-form arithmetic worked by hand, and against the published 95% CI
  for 10/100 = (0.0552, 0.1744)
- **Two-proportion z** against a hand-rolled implementation using only `math.erfc`, agreeing
  to 1e-12 on the real online-vs-domestic counts
- **Fisher** against `scipy.stats.fisher_exact` called directly on the same table
- **Chi-square** against `scipy.stats.chi2_contingency` on the same table (χ², dof, p)
- **BH correction** — asserted that adjusted p ≥ raw p for every group
- **Boundary behaviour** — Wilson at 0 successes and at n successes

One real bug found by these checks: statsmodels returns `4.3e-19` for the Wilson lower bound
at zero successes, where the terms cancel to exactly zero analytically. Snapped, with the
derivation in a comment so it does not read as a fudge.

**Not tested:** behaviour under concurrent calls (the functions are pure, so this is low
risk), and performance on very large group counts in `compare_many_rates` (108 groups is the
realistic maximum here and is instant).

## 6. Remaining work to ship it

1. Register `compare_two_rates`, `rate_interval`, `compare_many_rates` as `@tool` in
   `agent/agent.py` and add to the `tools` list.
2. **Include them in the over-budget rebind at `agent.py:167`.** When the 4-query budget is
   exhausted the model is rebound to `[chart]` only; without adding the stats tools there,
   a test becomes unreachable at exactly the point the model has the counts it needs.
3. System-prompt guidance: call a test whenever the user asks whether a difference is real,
   significant, or meaningful — and never claim significance without having run one.
4. A `StatCard` React component + `useRenderTool` registration, keyed to the exact tool
   names. Should lead with the verdict sentence, then the rates with CI error bars, then
   p and effect size as secondary detail.
5. Update [02](02-data-dictionary.md) and [07](07-roadmap.md) — this closes Phase 7 ahead of
   its place in the sequence.

## 7. Claims this earns

Safe to say in a demo:
- "It reports confidence intervals, not just point estimates."
- "It corrects for multiple comparisons when ranking 108 categories."
- "It distinguishes statistically significant from actually meaningful — which matters,
  because at 8.9 million rows nearly everything is significant."
- "It refuses to test segments too small to support a conclusion."

Do **not** say: that it does causal inference, time-series forecasting, or anything
requiring raw-row access. It tests proportions from aggregate counts. That is the whole
scope, and it is enough.
