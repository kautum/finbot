"""Statistical inference over aggregate counts.

This is the layer that separates an analyst from a chart generator: not "online fraud is
higher", but "online fraud is 53x domestic, 95% CI [50x, 57x], and that is not chance".

## Design decisions, and why

**Only aggregate counts cross this boundary.** Every function takes successes/trials that
`run_sql` already returned. No raw rows, no dataframes, no sandboxed Python.

**Effect size is mandatory, not optional.** With 8.9M labelled transactions, almost any
difference reaches p < 0.05 -- a p-value alone is close to meaningless at this scale, and
reporting it alone is the single most common way a large dataset produces a confident,
useless finding. So every comparison returns the risk ratio, the absolute difference, and
Cohen's h alongside the p-value, and the verdict names both questions separately:
is it real, and is it big enough to care about.

**Practical significance is judged on relative risk, not Cohen's h.** Measured while
building this: h scores the 53x online-vs-in-person fraud gap as "negligible", because the
arcsine transform compresses hard as p approaches zero. h is still reported, labelled with
that caveat, but it does not drive the verdict.

**Wilson score intervals, not Wald.** Fraud is 0.1495% of rows. The Wald interval has badly
wrong coverage as p approaches 0 and will happily return a negative lower bound; Wilson
inverts the score test, stays inside [0, 1], and holds near-nominal coverage at the
boundaries. It is the modern default and the right one for rare events.

**Pooled SE for the test, unpooled for the interval.** The hypothesis test assumes H0: the
proportions are equal, so pooling is correct there. The confidence interval makes no such
assumption, so it must not pool. Conflating the two is a classic error; statsmodels'
Newcombe hybrid-score method is used for the difference interval.

**It refuses rather than guessing.** Normal approximation invalid, zero events, degenerate
input -- each returns an explicit refusal or falls back to Fisher's exact test, never a
plausible-looking number.

Sources: arxiv.org/pdf/2109.02516 (rare-event binomial CIs),
pmc.ncbi.nlm.nih.gov/articles/PMC3444174 (effect size vs p),
online.stat.psu.edu/stat200 (pooled vs unpooled).
"""
from __future__ import annotations

import math
from typing import Sequence

from scipy import stats as sps
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import (
    confint_proportions_2indep,
    proportion_confint,
)

# Below this expected cell count the normal approximation is not trustworthy and we
# switch to an exact test. 5 is the conventional floor; some texts say 10.
MIN_EXPECTED_CELL = 5

# Fisher's exact test is exact but combinatorially expensive; past this total it is both
# unnecessary (the normal approximation is excellent) and slow.
FISHER_MAX_N = 100_000

# Cohen's conventions for h. Reported, but NOT used to judge practical significance --
# see _effect_label. Rules of thumb, not laws of nature.
COHEN_H_BANDS = ((0.2, "negligible"), (0.5, "small"), (0.8, "medium"))

# Practical significance is judged on the RISK RATIO, not Cohen's h.
#
# Measured here: online fraud (0.8378%) vs domestic in-person (0.0158%) is a 53x
# difference -- the single most important finding in this dataset -- and Cohen's h scores
# it 0.158, which lands in the "negligible" band. A merely 2x difference between 60% and
# 30% scores 0.61, "medium". The arcsine transform compresses hard as p approaches 0, so
# h is calibrated for mid-range proportions and systematically understates rare-event
# effects. Gating the verdict on h would have reported the channel finding as negligible.
#
# Relative risk has no such distortion and is also the number a fraud team actually acts
# on. Bands are deliberately conservative: under 10% relative difference is noise.
RISK_RATIO_BANDS = ((1.1, "negligible"), (1.5, "small"), (3.0, "moderate"))

# scipy returns exactly 0.0 once |z| is large enough to underflow float64. Reporting
# "p = 0" would be a false precision claim, so it is displayed as a bound instead.
P_UNDERFLOW_FLOOR = 1e-300


class StatsError(ValueError):
    """Input that cannot yield a meaningful test. Raised rather than approximated."""


# --------------------------------------------------------------------------- validation


def _as_count(name: str, value) -> int:
    """Coerce a JSON number to a non-negative integer count, or raise.

    JSON has no integer type, so 8779.0 arrives as a float and must be accepted; 8779.5
    is a sign the caller computed something wrong and must not be silently rounded.
    """
    if isinstance(value, bool):  # bool is an int subclass; almost certainly a mistake
        raise StatsError(f"{name} must be a number, got a boolean")
    if not isinstance(value, (int, float)):
        raise StatsError(f"{name} must be a number, got {type(value).__name__}")
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise StatsError(f"{name} must be finite, got {value}")
        if not float(value).is_integer():
            raise StatsError(f"{name} must be a whole count, got {value}")
    value = int(value)
    if value < 0:
        raise StatsError(f"{name} cannot be negative, got {value}")
    return value


def _validate_group(label: str, successes, trials) -> tuple[int, int]:
    s = _as_count(f"successes for {label}", successes)
    n = _as_count(f"trials for {label}", trials)
    if n == 0:
        raise StatsError(f"{label} has zero transactions; there is nothing to test")
    if s > n:
        raise StatsError(
            f"{label} has more events ({s:,}) than transactions ({n:,}), "
            "which is impossible -- check the query"
        )
    return s, n


def _validate_confidence(confidence) -> float:
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise StatsError("confidence must be a number between 0 and 1")
    c = float(confidence)
    if math.isnan(c) or not (0.0 < c < 1.0):
        raise StatsError(f"confidence must be strictly between 0 and 1, got {confidence}")
    return c


# ------------------------------------------------------------------------------- pieces


def _wilson(successes: int, trials: int, confidence: float) -> tuple[float, float]:
    lo, hi = proportion_confint(successes, trials, alpha=1 - confidence, method="wilson")
    lo, hi = max(0.0, float(lo)), min(1.0, float(hi))
    # At the boundaries the Wilson terms cancel exactly -- with p=0 the numerator is
    # z^2/2n - z*sqrt(z^2/4n^2) = 0 -- but in floating point statsmodels returns ~4e-19.
    # Snapping is restoring the analytic value, not rounding away a real quantity.
    if successes == 0:
        lo = 0.0
    if successes == trials:
        hi = 1.0
    return lo, hi


def _cohens_h(p1: float, p2: float) -> float:
    """Arcsine-transformed difference between two proportions.

    Reported for reference only. h *does* collapse toward zero when both proportions are
    near 0 -- measured at 0.158 for a 53x fraud-rate difference -- so it must not be used
    to judge practical significance on rare-event data. See RISK_RATIO_BANDS.
    """
    return 2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2))


def _cohen_label(h: float) -> str:
    a = abs(h)
    for threshold, name in COHEN_H_BANDS:
        if a < threshold:
            return name
    return "large"


def _effect_label(risk_ratio: float | None, h: float) -> str:
    """How big is the difference, in terms a fraud team would act on.

    Driven by relative risk. Cohen's h is only the fallback for the case where one group
    has zero events and no ratio exists -- there, a significant result against a zero
    baseline is by definition a large relative effect.
    """
    if risk_ratio is None:
        return "large" if abs(h) >= 0.2 else "negligible"
    r = max(risk_ratio, 1 / risk_ratio) if risk_ratio > 0 else float("inf")
    for threshold, name in RISK_RATIO_BANDS:
        if r < threshold:
            return name
    return "large"


def _p_display(p: float) -> str:
    if p < P_UNDERFLOW_FLOOR:
        return f"< {P_UNDERFLOW_FLOOR:g}"
    if p < 0.0001:
        return f"{p:.2e}"
    return f"{p:.4f}"


def _risk_ratio(p1: float, s1: int, n1: int, p2: float, s2: int, n2: int,
                confidence: float) -> dict:
    """Ratio of the two rates, with a Katz log-method confidence interval.

    Undefined when either group has zero events -- reported as such rather than as inf.
    """
    if s1 == 0 or s2 == 0:
        return {
            "value": None,
            "ci": None,
            "note": "Undefined: one group has zero events, so a ratio cannot be formed.",
        }
    rr = p1 / p2
    # SE of log(RR); Katz et al.
    se = math.sqrt(1 / s1 - 1 / n1 + 1 / s2 - 1 / n2)
    z = sps.norm.ppf(1 - (1 - confidence) / 2)
    return {
        "value": round(rr, 4),
        "ci": [round(math.exp(math.log(rr) - z * se), 4),
               round(math.exp(math.log(rr) + z * se), 4)],
        "note": None,
    }


# -------------------------------------------------------------------------------- tests


def compare_two_rates(
    label_a: str,
    successes_a,
    trials_a,
    label_b: str,
    successes_b,
    trials_b,
    confidence: float = 0.95,
) -> dict:
    """Test whether two rates differ, and by how much.

    Returns both halves of the answer: whether the difference is distinguishable from
    chance, and whether it is large enough to matter.
    """
    confidence = _validate_confidence(confidence)
    alpha = 1 - confidence
    sa, na = _validate_group(label_a, successes_a, trials_a)
    sb, nb = _validate_group(label_b, successes_b, trials_b)

    pa, pb = sa / na, sb / nb
    ci_a, ci_b = _wilson(sa, na, confidence), _wilson(sb, nb, confidence)

    result = {
        "test": "two-proportion comparison",
        "confidence_level": confidence,
        "groups": [
            {"label": label_a, "events": sa, "total": na,
             "rate_pct": round(100 * pa, 4),
             "ci_pct": [round(100 * ci_a[0], 4), round(100 * ci_a[1], 4)]},
            {"label": label_b, "events": sb, "total": nb,
             "rate_pct": round(100 * pb, 4),
             "ci_pct": [round(100 * ci_b[0], 4), round(100 * ci_b[1], 4)]},
        ],
    }

    # Degenerate: no events anywhere, or every trial an event in both groups. The
    # proportions are identical by construction and no test is informative.
    if (sa == 0 and sb == 0) or (sa == na and sb == nb and pa == pb):
        result["conclusion"] = (
            f"Both groups have identical rates ({100 * pa:.4f}%), so there is nothing to "
            "test. This usually means the segments are too small or the filter is wrong."
        )
        result["significant"] = False
        result["p_value"] = 1.0
        result["p_value_display"] = "1.0000"
        return result

    # Choose the test. The normal approximation needs enough expected events AND
    # non-events in each cell under the pooled rate.
    p_pool = (sa + sb) / (na + nb)
    expected = [na * p_pool, na * (1 - p_pool), nb * p_pool, nb * (1 - p_pool)]
    approx_ok = min(expected) >= MIN_EXPECTED_CELL
    total_n = na + nb

    if approx_ok:
        se_pooled = math.sqrt(p_pool * (1 - p_pool) * (1 / na + 1 / nb))
        z = (pa - pb) / se_pooled if se_pooled > 0 else 0.0
        p_value = float(2 * sps.norm.sf(abs(z)))
        method = "two-proportion z-test (pooled standard error, two-sided)"
        result["z_statistic"] = round(z, 4)
    elif total_n <= FISHER_MAX_N:
        _, p_value = sps.fisher_exact([[sa, na - sa], [sb, nb - sb]])
        p_value = float(p_value)
        method = "Fisher's exact test (normal approximation not valid at these counts)"
    else:
        result["conclusion"] = (
            f"Cannot test reliably: the expected event count in the smallest cell is "
            f"{min(expected):.1f}, below the threshold of {MIN_EXPECTED_CELL}, and the "
            f"dataset is too large for an exact test. Compare coarser segments."
        )
        result["significant"] = None
        return result

    result["method"] = method
    result["p_value"] = p_value
    result["p_value_display"] = _p_display(p_value)
    result["significant"] = bool(p_value < alpha)

    # Absolute difference, unpooled -- a CI must not assume the null it is not testing.
    diff_lo, diff_hi = confint_proportions_2indep(
        sa, na, sb, nb, method="newcomb", compare="diff", alpha=alpha
    )
    result["difference_pct_points"] = {
        "value": round(100 * (pa - pb), 4),
        "ci": [round(100 * float(diff_lo), 4), round(100 * float(diff_hi), 4)],
    }
    result["risk_ratio"] = _risk_ratio(pa, sa, na, pb, sb, nb, confidence)

    h = _cohens_h(pa, pb)
    label = _effect_label(result["risk_ratio"]["value"], h)
    result["effect_size"] = {
        "magnitude": label,
        "judged_on": "risk ratio",
        "scale": "relative risk: <1.1x negligible, <1.5x small, <3x moderate, else large",
        "cohens_h": round(h, 4),
        "cohens_h_magnitude": _cohen_label(h),
        "cohens_h_caveat": (
            "Cohen's h compresses severely for rare events and is reported for reference "
            "only. It scores the 53x online-vs-in-person fraud gap as 'negligible'. The "
            "magnitude above is judged on relative risk instead."
        ),
    }

    result["conclusion"] = _verdict(
        label_a, label_b, pa, pb, result["significant"], label,
        result["risk_ratio"], total_n, alpha,
    )
    return result


def _verdict(label_a, label_b, pa, pb, significant, magnitude, rr, total_n, alpha) -> str:
    """Plain-language reading that keeps 'real' and 'big' as separate questions."""
    higher, lower = (label_a, label_b) if pa >= pb else (label_b, label_a)

    if not significant:
        return (
            f"No significant difference between {label_a} ({100 * pa:.4f}%) and "
            f"{label_b} ({100 * pb:.4f}%) at the {int((1 - alpha) * 100)}% level. The "
            "observed gap is within what chance alone would produce."
        )

    ratio = ""
    if rr["value"]:
        r = rr["value"] if pa >= pb else 1 / rr["value"]
        # .3g, not .2g: a ratio of 1.02 renders as "1x" at two significant figures,
        # which reads as "no difference" and hides the very case being explained.
        ratio = f" {higher} is {r:.3g}x the rate of {lower}."

    if magnitude == "negligible":
        return (
            f"Statistically significant, but the effect is negligible.{ratio} With "
            f"{total_n:,} transactions, differences this small reach significance without "
            "being worth acting on -- the p-value is detecting the sample size, not an "
            "important gap. Treat this as 'no practical difference'."
        )
    return (
        f"{higher} has a genuinely higher rate than {lower}, and the effect is "
        f"{magnitude}.{ratio} This is unlikely to be chance."
    )


def rate_interval(label: str, successes, trials, confidence: float = 0.95) -> dict:
    """Wilson score interval for a single rate -- how precisely it is known."""
    confidence = _validate_confidence(confidence)
    s, n = _validate_group(label, successes, trials)
    p = s / n
    lo, hi = _wilson(s, n, confidence)
    out = {
        "label": label,
        "events": s,
        "total": n,
        "rate_pct": round(100 * p, 4),
        "ci_pct": [round(100 * lo, 4), round(100 * hi, 4)],
        "confidence_level": confidence,
        "method": "Wilson score interval",
    }
    width = 100 * (hi - lo)
    if s == 0:
        out["conclusion"] = (
            f"{label} has no events in {n:,} transactions. The rate could still be as high "
            f"as {100 * hi:.4f}% -- absence of events is not proof of a zero rate."
        )
    elif s < 30:
        out["conclusion"] = (
            f"{label}: {100 * p:.4f}%, but with only {s} events the interval spans "
            f"{width:.4f} percentage points. Too imprecise to rank against other segments."
        )
    else:
        out["conclusion"] = (
            f"{label}: {100 * p:.4f}% ({int((1 - (1 - confidence)) * 100)}% CI "
            f"{100 * lo:.4f}% to {100 * hi:.4f}%), based on {s:,} events in {n:,}."
        )
    return out


def compare_many_rates(
    labels: Sequence[str],
    successes: Sequence,
    trials: Sequence,
    confidence: float = 0.95,
) -> dict:
    """Test whether rates differ across three or more groups.

    Runs an overall chi-square test of independence, then each group against the pooled
    remainder with Benjamini-Hochberg correction. The correction matters: testing 108
    merchant categories at alpha=0.05 yields about five false positives by construction,
    and ranking on uncorrected p-values is how spurious 'findings' get demoed.
    """
    confidence = _validate_confidence(confidence)
    alpha = 1 - confidence

    if not (len(labels) == len(successes) == len(trials)):
        raise StatsError(
            f"labels ({len(labels)}), successes ({len(successes)}) and trials "
            f"({len(trials)}) must be the same length"
        )
    if len(labels) < 3:
        raise StatsError(
            "compare_many_rates needs at least 3 groups; use compare_two_rates for 2"
        )

    groups = []
    for lab, s, n in zip(labels, successes, trials):
        si, ni = _validate_group(str(lab), s, n)
        groups.append((str(lab), si, ni))

    table = [[s, n - s] for _, s, n in groups]
    chi2, p_overall, dof, expected = sps.chi2_contingency(table)
    min_expected = float(min(min(row) for row in expected))

    out = {
        "test": "chi-square test of independence across groups",
        "groups_tested": len(groups),
        "chi2": round(float(chi2), 4),
        "degrees_of_freedom": int(dof),
        "p_value": float(p_overall),
        "p_value_display": _p_display(float(p_overall)),
        "significant": bool(p_overall < alpha),
        "min_expected_cell": round(min_expected, 2),
    }
    if min_expected < MIN_EXPECTED_CELL:
        out["warning"] = (
            f"The smallest expected cell is {min_expected:.2f}, below {MIN_EXPECTED_CELL}. "
            "The chi-square approximation is unreliable here; merge the smallest groups."
        )

    # Each group against everything else, BH-corrected.
    total_s = sum(s for _, s, _ in groups)
    total_n = sum(n for _, _, n in groups)
    raw_p, rows = [], []
    for lab, s, n in groups:
        os_, on = total_s - s, total_n - n
        p_in = s / n
        p_out = os_ / on if on else 0.0
        pooled = (s + os_) / (n + on)
        se = math.sqrt(pooled * (1 - pooled) * (1 / n + 1 / on)) if on else 0.0
        z = (p_in - p_out) / se if se > 0 else 0.0
        pv = float(2 * sps.norm.sf(abs(z)))
        raw_p.append(pv)
        lo, hi = _wilson(s, n, confidence)
        rows.append({
            "label": lab, "events": s, "total": n,
            "rate_pct": round(100 * p_in, 4),
            "ci_pct": [round(100 * lo, 4), round(100 * hi, 4)],
            "vs_rest_ratio": round(p_in / p_out, 3) if p_out > 0 else None,
            "p_raw": pv,
        })

    rejected, p_adj, _, _ = multipletests(raw_p, alpha=alpha, method="fdr_bh")
    for row, adj, rej in zip(rows, p_adj, rejected):
        row["p_adjusted"] = float(adj)
        row["p_adjusted_display"] = _p_display(float(adj))
        row["differs_from_rest"] = bool(rej)

    rows.sort(key=lambda r: r["rate_pct"], reverse=True)
    out["groups"] = rows
    n_sig = sum(1 for r in rows if r["differs_from_rest"])
    out["conclusion"] = (
        (f"Rates differ across these {len(groups)} groups (chi-square p "
         f"{out['p_value_display']}). After Benjamini-Hochberg correction for "
         f"{len(groups)} comparisons, {n_sig} group(s) differ from the rest.")
        if out["significant"] else
        (f"No detectable difference across these {len(groups)} groups "
         f"(chi-square p {out['p_value_display']}). The variation is consistent with chance.")
    )
    return out


# ------------------------------------------------------------------------------- oracle


def _selftest() -> None:
    """Verified against values computed independently of this module.

    Oracles used:
      * closed-form Wilson arithmetic worked by hand (see comment) and the published
        95% CI for 10/100
      * scipy.stats.chi2_contingency and fisher_exact, called directly
      * a hand-rolled z-test using only `math`, compared to the library path
      * statsmodels proportion_confint cross-checked against the hand formula
    """
    close = lambda a, b, tol=1e-9: abs(a - b) <= tol

    # -- Wilson against hand arithmetic and the published value for 10/100 -------------
    # centre = (p + z^2/2n)/(1 + z^2/n); half = z/(1+z^2/n) * sqrt(p(1-p)/n + z^2/4n^2)
    n, x, z = 100, 10, 1.959963984540054
    p = x / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = (z / (1 + z * z / n)) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    lo, hi = _wilson(x, n, 0.95)
    assert close(lo, centre - half, 1e-12) and close(hi, centre + half, 1e-12), (lo, hi)
    assert close(lo, 0.05522, 1e-4) and close(hi, 0.17436, 1e-4), (lo, hi)

    # -- Wilson stays inside [0,1] at the boundaries where Wald does not ---------------
    z_lo, z_hi = _wilson(0, 500, 0.95)
    assert z_lo == 0.0 and 0 < z_hi < 1, (z_lo, z_hi)
    o_lo, o_hi = _wilson(500, 500, 0.95)
    assert o_hi == 1.0 and 0 < o_lo < 1, (o_lo, o_hi)

    # -- two-proportion z against a hand-rolled implementation using only `math` -------
    sa, na, sb, nb = 8779, 1047865, 1234, 7807586      # real: online vs domestic fraud
    pa, pb = sa / na, sb / nb
    pool = (sa + sb) / (na + nb)
    se = math.sqrt(pool * (1 - pool) * (1 / na + 1 / nb))
    z_hand = (pa - pb) / se
    p_hand = math.erfc(abs(z_hand) / math.sqrt(2))      # 2*(1-Phi(|z|)) via erfc
    r = compare_two_rates("Online", sa, na, "In-person", sb, nb)
    assert close(r["z_statistic"], round(z_hand, 4), 1e-4), (r["z_statistic"], z_hand)
    assert close(r["p_value"], p_hand, 1e-12) or (r["p_value"] == 0.0 and p_hand < 1e-300)
    assert r["significant"] is True
    assert r["effect_size"]["magnitude"] == "large", r["effect_size"]
    # The regression this guards: Cohen's h scores this 53x gap as "negligible".
    assert r["effect_size"]["cohens_h_magnitude"] == "negligible", r["effect_size"]
    # Sanity: online fraud really is tens of times the domestic rate.
    assert 40 < r["risk_ratio"]["value"] < 70, r["risk_ratio"]

    # -- the large-N trap: a trivial gap must be flagged negligible, not "significant" --
    # 1.02% vs 1.00% across 20M rows: a 2% relative difference nobody would act on,
    # which the sample size alone drives to p < 1e-5.
    trap = compare_two_rates("A", 102_000, 10_000_000, "B", 100_000, 10_000_000)
    assert trap["significant"] is True, trap["p_value"]
    assert trap["effect_size"]["magnitude"] == "negligible", trap["effect_size"]
    assert "negligible" in trap["conclusion"]

    # -- identical rates -> not significant --------------------------------------------
    same = compare_two_rates("A", 50, 1000, "B", 100, 2000)
    assert same["significant"] is False and close(same["p_value"], 1.0), same["p_value"]

    # -- no events anywhere -> refuse to test ------------------------------------------
    zero = compare_two_rates("A", 0, 500, "B", 0, 900)
    assert zero["significant"] is False and "nothing to test" in zero["conclusion"]

    # -- small counts -> Fisher, cross-checked against scipy directly -------------------
    small = compare_two_rates("A", 1, 30, "B", 8, 30)
    assert "Fisher" in small["method"], small["method"]
    _, p_ref = sps.fisher_exact([[1, 29], [8, 22]])
    assert close(small["p_value"], float(p_ref), 1e-12)

    # -- risk ratio undefined when a group has zero events -----------------------------
    rr0 = compare_two_rates("A", 0, 20_000, "B", 300, 20_000)
    assert rr0["risk_ratio"]["value"] is None and rr0["risk_ratio"]["note"]

    # -- chi-square cross-checked against scipy on the same table ----------------------
    labels = ["Visa", "Mastercard", "Amex", "Discover"]
    succ, tot = [900, 850, 300, 120], [600_000, 580_000, 190_000, 90_000]
    many = compare_many_rates(labels, succ, tot)
    chi_ref, p_ref2, dof_ref, _ = sps.chi2_contingency(
        [[s, n - s] for s, n in zip(succ, tot)]
    )
    assert close(many["chi2"], round(float(chi_ref), 4), 1e-4)
    assert close(many["p_value"], float(p_ref2), 1e-12)
    assert many["degrees_of_freedom"] == int(dof_ref) == 3
    # BH-adjusted p must never be below the raw p.
    for row in many["groups"]:
        assert row["p_adjusted"] >= row["p_raw"] - 1e-12, row
    assert [r["rate_pct"] for r in many["groups"]] == sorted(
        (r["rate_pct"] for r in many["groups"]), reverse=True
    )

    # -- single-rate interval ----------------------------------------------------------
    ri = rate_interval("Cruise Lines", 165, 276)
    assert ri["ci_pct"][0] < ri["rate_pct"] < ri["ci_pct"][1]
    thin = rate_interval("Tiny", 3, 900)
    assert "Too imprecise" in thin["conclusion"]
    none_seen = rate_interval("Nothing", 0, 4000)
    assert "not proof of a zero rate" in none_seen["conclusion"]

    # -- malformed input raises rather than returning something plausible ---------------
    bad = [
        (("A", 10, 5, "B", 1, 10), "more events"),
        (("A", -1, 50, "B", 1, 10), "negative"),
        (("A", 1.5, 50, "B", 1, 10), "whole count"),
        (("A", float("nan"), 50, "B", 1, 10), "finite"),
        (("A", 1, 0, "B", 1, 10), "zero transactions"),
        (("A", "5", 50, "B", 1, 10), "must be a number"),
        (("A", True, 50, "B", 1, 10), "boolean"),
    ]
    for args, expect in bad:
        try:
            compare_two_rates(*args)
        except StatsError as e:
            assert expect in str(e), (args, str(e))
        else:
            raise AssertionError(f"should have raised for {args}")

    for c in (0, 1, -0.5, 1.5, float("nan"), "0.95"):
        try:
            compare_two_rates("A", 5, 50, "B", 6, 50, confidence=c)
        except StatsError:
            pass
        else:
            raise AssertionError(f"should have raised for confidence={c}")

    try:
        compare_many_rates(["a", "b"], [1, 2], [10, 20])
    except StatsError as e:
        assert "at least 3 groups" in str(e)
    else:
        raise AssertionError("should have raised for 2 groups")

    try:
        compare_many_rates(["a", "b", "c"], [1, 2], [10, 20, 30])
    except StatsError as e:
        assert "same length" in str(e)
    else:
        raise AssertionError("should have raised for mismatched lengths")

    print("statistics.py: all oracle checks passed")
    print(f"  online vs domestic  z={r['z_statistic']}  p={r['p_value_display']}  "
          f"RR={r['risk_ratio']['value']}x  h={r['effect_size']['cohens_h']} "
          f"({r['effect_size']['magnitude']})")
    print(f"  large-N trap        {trap['conclusion'][:96]}...")
    print(f"  4-way card brands   {many['conclusion']}")


if __name__ == "__main__":
    _selftest()
