"""E7: Chase the anomaly E6 surfaced - Italy showed a 65% fraud rate.

Either a bug, or the strongest finding in the dataset. Determine which, and
characterise foreign vs domestic fraud properly.
"""
import duckdb, os

FACT = os.environ.get("FINBOT_FACT", "/Users/kpkautum/.claude/jobs/b441694d/tmp/fact.duckdb")
con = duckdb.connect(":memory:")
con.execute(f"ATTACH '{FACT}' AS fact (READ_ONLY)")
con.execute("CREATE VIEW f AS SELECT * FROM fact.fact_transactions")

print("=" * 66)
print("1. IS merchant_state A US STATE OR A COUNTRY?")
print("=" * 66)
for r in con.execute("""
 SELECT CASE WHEN merchant_state IS NULL THEN 'NULL (online?)'
             WHEN length(merchant_state)=2 THEN 'US state code'
             ELSE 'foreign country' END kind,
        count(*) n, sum(is_fraud::INT) fraud,
        round(100.0*sum(is_fraud::INT)/count(*),4) pct
 FROM f GROUP BY 1 ORDER BY n DESC""").fetchall():
    print(f"  {r[0]:18s} {r[1]:>10,} txns  {r[2]:>6,} fraud  {r[3]:>8}%")

print("\n" + "=" * 66)
print("2. WHAT IS merchant_state WHEN use_chip = 'Online Transaction'?")
print("=" * 66)
for r in con.execute("""
 SELECT use_chip, CASE WHEN merchant_state IS NULL THEN 'NULL' ELSE 'has value' END s,
        count(*) n, sum(is_fraud::INT) fraud, round(100.0*sum(is_fraud::INT)/count(*),4) pct
 FROM f GROUP BY 1,2 ORDER BY 1,2""").fetchall():
    print(f"  {r[0]:20s} state={r[1]:10s} {r[2]:>10,}  {r[3]:>6,} fraud  {r[4]:>8}%")

print("\n" + "=" * 66)
print("3. TOP FOREIGN COUNTRIES BY FRAUD RATE (min 500 txns)")
print("=" * 66)
for r in con.execute("""
 SELECT merchant_state, count(*) n, sum(is_fraud::INT) fraud,
        round(100.0*sum(is_fraud::INT)/count(*),3) pct
 FROM f WHERE length(merchant_state)>2 GROUP BY 1 HAVING count(*)>=500
 ORDER BY pct DESC LIMIT 10""").fetchall():
    print(f"  {r[0]:22s} {r[1]:>8,} txns  {r[2]:>6,} fraud  {r[3]:>8}%")

print("\n" + "=" * 66)
print("4. IS THE ITALY SPIKE TIME-CONCENTRATED? (a breach signature)")
print("=" * 66)
for r in con.execute("""
 SELECT year(date) y, count(*) n, sum(is_fraud::INT) fraud,
        round(100.0*sum(is_fraud::INT)/count(*),2) pct
 FROM f WHERE merchant_state='Italy' GROUP BY 1 ORDER BY 1""").fetchall():
    print(f"  {r[0]}  {r[1]:>7,} txns  {r[2]:>6,} fraud  {r[3]:>7}%")

print("\n  same for a control country (Canada):")
for r in con.execute("""
 SELECT year(date) y, count(*) n, sum(is_fraud::INT) fraud
 FROM f WHERE merchant_state='Canada' GROUP BY 1 ORDER BY 1 LIMIT 4""").fetchall():
    print(f"  {r[0]}  {r[1]:>7,} txns  {r[2]:>6,} fraud")

print("\n" + "=" * 66)
print("5. HOW MANY DISTINCT MERCHANTS / CLIENTS DRIVE THE ITALY FRAUD?")
print("=" * 66)
print(" ", con.execute("""
 SELECT count(DISTINCT merchant_id) merchants, count(DISTINCT client_id) clients,
        count(*) fraud_txns
 FROM f WHERE merchant_state='Italy' AND is_fraud""").fetchone())
