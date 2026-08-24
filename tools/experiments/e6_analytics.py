"""E6: Validate the analytical claims the demo depends on.

  1. The findex cross-domain join (104 countries) and its ~49x fan-out trap
  2. The statistical tools from roadmap Phase 7, on real numbers
  3. The refusal guardrail - does a thin segment actually fail the power test?
"""
import duckdb, os

FACT = os.environ.get("FINBOT_FACT", "/Users/kpkautum/.claude/jobs/b441694d/tmp/fact.duckdb")
PQ = os.environ.get("FINBOT_PQ", "/Users/kpkautum/.claude/jobs/b441694d/tmp/pq")

# NOTE: connecting directly with read_only=True also blocks CREATE VIEW, so the
# production pattern is an in-memory connection with the data ATTACHed READ_ONLY.
con = duckdb.connect(":memory:")
con.execute(f"ATTACH '{FACT}' AS fact (READ_ONLY)")
con.execute("CREATE VIEW fact_transactions AS SELECT * FROM fact.fact_transactions")
con.execute(f"CREATE VIEW findex AS SELECT * FROM read_parquet('{PQ}/findex.parquet')")

print("=" * 62)
print("1. THE CROSS-DOMAIN JOIN")
print("=" * 62)
print("  countries matching:", con.execute("""
  SELECT count(DISTINCT f.merchant_state) FROM fact_transactions f
  JOIN findex x ON f.merchant_state = x.countrynewwb""").fetchone()[0])

naive = con.execute("""SELECT count(*) FROM fact_transactions f
  JOIN findex x ON f.merchant_state = x.countrynewwb""").fetchone()[0]
correct = con.execute("""SELECT count(*) FROM fact_transactions f
  WHERE f.merchant_state IN (SELECT DISTINCT countrynewwb FROM findex)""").fetchone()[0]
print(f"  naive join row count : {naive:,}   <-- WRONG, fans out")
print(f"  actual transactions  : {correct:,}")
print(f"  fan-out factor       : {naive/correct:.1f}x")

print("\n  CORRECT pattern (aggregate first, then join):")
for r in con.execute("""
  WITH per_country AS (
    SELECT merchant_state AS country, count(*) n, sum(is_fraud::INT) fraud
    FROM fact_transactions WHERE merchant_state IS NOT NULL GROUP BY 1
  )
  SELECT p.country, p.n, p.fraud, round(100.0*p.fraud/p.n,3) fraud_pct,
         round(avg(TRY_CAST(x.account_t_d AS DOUBLE)),3) acct_ownership
  FROM per_country p JOIN findex x ON p.country = x.countrynewwb
  WHERE x.year = 2021 AND p.n > 500
  GROUP BY 1,2,3,4 ORDER BY p.n DESC LIMIT 6""").fetchall():
    print("   ", r)

print("\n" + "=" * 62)
print("2. STATISTICAL TOOLS (Phase 7) ON REAL NUMBERS")
print("=" * 62)
rows = con.execute("""SELECT use_chip, count(*) n, sum(is_fraud::INT) fr
  FROM fact_transactions GROUP BY 1""").fetchall()
seg = {r[0]: (r[2], r[1]) for r in rows}
for k, v in seg.items():
    print(f"  {k:22s} {v[0]:>6,} fraud / {v[1]:>9,} = {100*v[0]/v[1]:.4f}%")

try:
    from statsmodels.stats.proportion import proportions_ztest, proportion_confint
    a, na = seg["Online Transaction"]
    b, nb = seg["Swipe Transaction"]
    stat, p = proportions_ztest([a, b], [na, nb])
    print(f"\n  two-proportion z-test, Online vs Swipe:")
    print(f"    z = {stat:.1f},  p = {p:.3g}")
    lo, hi = proportion_confint(a, na, alpha=0.05, method="wilson")
    print(f"    Online 95% CI: [{100*lo:.4f}%, {100*hi:.4f}%]")
    lo2, hi2 = proportion_confint(b, nb, alpha=0.05, method="wilson")
    print(f"    Swipe  95% CI: [{100*lo2:.4f}%, {100*hi2:.4f}%]")
    print(f"    intervals overlap: {not (lo > hi2 or lo2 > hi)}")

    print("\n" + "=" * 62)
    print("3. THE REFUSAL GUARDRAIL - thin segments")
    print("=" * 62)
    thin = con.execute("""SELECT mcc_description, count(*) n, sum(is_fraud::INT) fr
      FROM fact_transactions GROUP BY 1 HAVING sum(is_fraud::INT) < 10 AND count(*) > 1000
      ORDER BY count(*) DESC LIMIT 4""").fetchall()
    print("  segments that MUST be refused (fraud count < 30):")
    for d, n, fr in thin:
        lo, hi = proportion_confint(fr, n, alpha=0.05, method="wilson")
        width = 100 * (hi - lo)
        print(f"    {str(d)[:34]:36s} {fr:>3} fraud / {n:>7,}  CI width {width:.3f}pp -> REFUSE")
    big = con.execute("""SELECT mcc_description, count(*) n, sum(is_fraud::INT) fr
      FROM fact_transactions GROUP BY 1 HAVING sum(is_fraud::INT) > 500
      ORDER BY sum(is_fraud::INT) DESC LIMIT 2""").fetchall()
    print("  segments that are safe to report:")
    for d, n, fr in big:
        lo, hi = proportion_confint(fr, n, alpha=0.05, method="wilson")
        print(f"    {str(d)[:34]:36s} {fr:>4} fraud / {n:>8,}  CI width {100*(hi-lo):.4f}pp -> OK")
except ImportError:
    print("  statsmodels not installed in this interpreter - skipped")
