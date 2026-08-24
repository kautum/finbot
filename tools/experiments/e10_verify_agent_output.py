"""E10: Independently verify what the agent claimed in E9.

The agent reported MCC 4112 'Passenger Railways' at 1,463 txns / 5.9% fraud, but an
earlier benchmark reported 'Passenger Railways' at 11,877 txns / 2.004%. One of them
is wrong, or the grouping key differs. Never trust an LLM's numbers without checking.
"""
import duckdb, os

FACT = os.environ.get("FINBOT_FACT", "/Users/kpkautum/.claude/jobs/b441694d/tmp/fact.duckdb")
con = duckdb.connect(":memory:")
con.execute(f"ATTACH '{FACT}' AS fact (READ_ONLY)")
con.execute("CREATE VIEW f AS SELECT * FROM fact.fact_transactions")

print("=" * 70)
print("1. DOES ONE DESCRIPTION MAP TO MULTIPLE MCC CODES?")
print("=" * 70)
for r in con.execute("""
 SELECT mcc_description, count(DISTINCT mcc) codes, list(DISTINCT mcc) which, count(*) n
 FROM f GROUP BY 1 HAVING count(DISTINCT mcc) > 1 ORDER BY n DESC LIMIT 10""").fetchall():
    print(f"  {str(r[0])[:38]:40s} {r[1]} codes {str(r[2]):18s} {r[3]:>9,} txns")

print("\n=" * 1 + "=" * 69)
print("2. PASSENGER RAILWAYS, BROKEN OUT BY MCC")
print("=" * 70)
for r in con.execute("""
 SELECT mcc, mcc_description, count(*) n, sum(is_fraud::INT) fr,
        round(100.0*sum(is_fraud::INT)/count(*),3) pct
 FROM f WHERE mcc_description ILIKE '%Passenger Railway%' GROUP BY 1,2 ORDER BY n DESC""").fetchall():
    print(f"  mcc={r[0]:<6} {str(r[1])[:28]:30s} {r[2]:>8,} txns {r[3]:>5,} fraud {r[4]:>7}%")
print("  grouped by DESCRIPTION instead:", con.execute("""
 SELECT count(*), sum(is_fraud::INT), round(100.0*sum(is_fraud::INT)/count(*),3)
 FROM f WHERE mcc_description ILIKE '%Passenger Railway%'""").fetchone())

print("\n" + "=" * 70)
print("3. VERIFY THE AGENT'S TOP-RISK CLAIMS (>=30 fraud cases)")
print("=" * 70)
for r in con.execute("""
 SELECT mcc, mcc_description, count(*) n, sum(is_fraud::INT) fr,
        round(100.0*sum(is_fraud::INT)/count(*),2) pct
 FROM f GROUP BY 1,2 HAVING sum(is_fraud::INT) >= 30
 ORDER BY sum(is_fraud::INT)*1.0/count(*) DESC LIMIT 8""").fetchall():
    print(f"  mcc={r[0]:<6} {str(r[1])[:34]:36s} {r[2]:>7,} n {r[3]:>5,} fraud {r[4]:>7}%")

print("\n" + "=" * 70)
print("4. AGENT'S OVERALL FRAUD RATE CLAIM")
print("=" * 70)
print("  ", con.execute(
    "SELECT count(*), sum(is_fraud::INT), round(100.0*sum(is_fraud::INT)/count(*),4) FROM f"
).fetchone(), " (agent said 8,914,963 / 13,332 / 0.1495%)")
