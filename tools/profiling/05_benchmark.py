import duckdb, time, os
PQ="/Users/kpkautum/.claude/jobs/b441694d/tmp/pq"
DB="/Users/kpkautum/.claude/jobs/b441694d/tmp/finbot.duckdb"
if os.path.exists(DB): os.remove(DB)
con=duckdb.connect(DB)
for t in ["transactions","fraud_labels","users","cards","mcc_codes","findex","databank"]:
    con.execute(f"CREATE TABLE {t} AS SELECT * FROM read_parquet('{PQ}/{t}.parquet')")
con.close()
print("single .duckdb file MB:", round(os.path.getsize(DB)/1e6,1))

con=duckdb.connect(DB, read_only=True)
def bench(label, sql):
    t=time.time(); r=con.execute(sql).fetchall(); 
    print(f"{label}: {round((time.time()-t)*1000)} ms -> {r[:3]}")
bench("Q1 fraud rate overall", "SELECT count(*) n, sum(is_fraud::INT) f, round(100.0*sum(is_fraud::INT)/count(*),4) pct FROM fraud_labels")
bench("Q2 fraud rate by MCC (join 3 tables)", """SELECT m.description, count(*) n, sum(f.is_fraud::INT) fr,
 round(100.0*sum(f.is_fraud::INT)/count(*),3) pct
 FROM transactions t JOIN fraud_labels f ON t.id=f.transaction_id JOIN mcc_codes m ON t.mcc=m.mcc_code
 GROUP BY 1 HAVING count(*)>10000 ORDER BY pct DESC LIMIT 5""")
bench("Q3 fraud by credit-score band (4-table join)", """SELECT CASE WHEN u.credit_score<600 THEN 'poor' WHEN u.credit_score<700 THEN 'fair'
 WHEN u.credit_score<800 THEN 'good' ELSE 'excellent' END band, count(*) n,
 round(100.0*sum(f.is_fraud::INT)/count(*),3) fraud_pct, round(avg(t.amount),2) avg_amt
 FROM transactions t JOIN fraud_labels f ON t.id=f.transaction_id JOIN cards c ON t.card_id=c.id
 JOIN users u ON c.client_id=u.id GROUP BY 1 ORDER BY fraud_pct DESC""")
bench("Q4 monthly time series", """SELECT date_trunc('month',t.date) m, count(*) n, round(sum(t.amount),0) vol,
 sum(f.is_fraud::INT) fr FROM transactions t JOIN fraud_labels f ON t.id=f.transaction_id
 GROUP BY 1 ORDER BY 1 LIMIT 5""")
bench("Q5 window fn / user cohort", """SELECT client_id, count(*) n, sum(amount) tot,
 rank() OVER (ORDER BY sum(amount) DESC) rk FROM transactions GROUP BY 1 ORDER BY rk LIMIT 5""")
bench("Q6 online vs chip fraud (AB-test shape)", """SELECT t.use_chip, count(*) n, sum(f.is_fraud::INT) fr,
 round(100.0*sum(f.is_fraud::INT)/count(*),4) pct FROM transactions t JOIN fraud_labels f ON t.id=f.transaction_id
 GROUP BY 1 ORDER BY pct DESC""")
