import duckdb
con = duckdb.connect("/Users/kpkautum/.claude/jobs/b441694d/tmp/finbot.duckdb", read_only=True)
q = lambda s: con.execute(s).fetchall()

print("=== 1. CREDIT BANDS (all, not top 3) ===")
for r in q("""SELECT CASE WHEN u.credit_score<600 THEN 'poor' WHEN u.credit_score<700 THEN 'fair'
 WHEN u.credit_score<800 THEN 'good' ELSE 'excellent' END band, count(*) n,
 round(100.0*sum(f.is_fraud::INT)/count(*),3) fraud_pct
 FROM transactions t JOIN fraud_labels f ON t.id=f.transaction_id JOIN cards c ON t.card_id=c.id
 JOIN users u ON c.client_id=u.id GROUP BY 1 ORDER BY fraud_pct DESC"""): print("  ", r)

print("=== 2. merchant_state: NULLs and non-US values ===")
print("  NULL count:", q("SELECT count(*) FROM transactions WHERE merchant_state IS NULL"))
print("  pct null:", q("SELECT round(100.0*count(*) FILTER (WHERE merchant_state IS NULL)/count(*),2) FROM transactions"))
print("  long (non-2-char) values:", q("SELECT merchant_state, count(*) c FROM transactions WHERE length(merchant_state)>2 GROUP BY 1 ORDER BY c DESC LIMIT 8"))

print("=== 3. JOIN KEY: merchant_state <-> findex.countrynewwb ===")
print("  matching countries:", q("""SELECT count(DISTINCT t.merchant_state) FROM transactions t
 JOIN findex fx ON t.merchant_state = fx.countrynewwb"""))
print("  sample:", q("""SELECT DISTINCT t.merchant_state FROM transactions t
 JOIN findex fx ON t.merchant_state=fx.countrynewwb LIMIT 8"""))
print("  findex rows per country:", q("SELECT round(avg(c),1) FROM (SELECT count(*) c FROM findex GROUP BY countrynewwb)"))

print("=== 4. labeled fraction per year ===")
for r in q("""SELECT year(t.date) y, count(*) tot, count(f.transaction_id) lab,
 round(100.0*count(f.transaction_id)/count(*),1) pct
 FROM transactions t LEFT JOIN fraud_labels f ON t.id=f.transaction_id GROUP BY 1 ORDER BY 1"""): print("  ", r)

print("=== 5. amount parse failures ===")
print("  unparseable:", q("SELECT count(*) FROM transactions WHERE amount IS NULL"))
print("=== 6. MCC fraud multiple vs baseline ===")
print("  baseline:", q("SELECT round(100.0*sum(is_fraud::INT)/count(*),4) FROM fraud_labels"))
