import duckdb, time, os
D="/Users/kpkautum/Documents/Projects/finbot/Datasets"; T=f"{D}/financial_transactions"
OUT="/Users/kpkautum/.claude/jobs/b441694d/tmp"
con=duckdb.connect(); q=lambda s: con.execute(s).fetchall()
t0=time.time()
# fraud labels: json {"target": {id: "Yes"/"No"}}
con.execute(f"""CREATE TABLE fraud AS
 SELECT unnest(map_keys(target))::BIGINT AS transaction_id, unnest(map_values(target)) AS is_fraud
 FROM read_json('{T}/train_fraud_labels.json', columns={{'target':'MAP(VARCHAR,VARCHAR)'}}, maximum_object_size=200000000)""")
print("FRAUD COUNT:", q("SELECT count(*) FROM fraud"))
print("FRAUD DIST:", q("SELECT is_fraud, count(*) c FROM fraud GROUP BY 1 ORDER BY c DESC"))
con.execute(f"CREATE VIEW txn AS SELECT * FROM read_csv_auto('{T}/transactions_data.csv', sample_size=200000)")
print("LABELED TXNS:", q("SELECT count(*) FROM txn t JOIN fraud f ON t.id=f.transaction_id"))
print("UNLABELED TXNS:", q("SELECT count(*) FROM txn t LEFT JOIN fraud f ON t.id=f.transaction_id WHERE f.transaction_id IS NULL"))
print("LABEL DATE RANGE:", q("SELECT min(t.date), max(t.date) FROM txn t JOIN fraud f ON t.id=f.transaction_id"))
print("FRAUD BY YEAR:", q("""SELECT year(t.date) y, count(*) n, sum(CASE WHEN f.is_fraud='Yes' THEN 1 ELSE 0 END) fr
  FROM txn t JOIN fraud f ON t.id=f.transaction_id GROUP BY 1 ORDER BY 1"""))
print("elapsed", round(time.time()-t0,1))
