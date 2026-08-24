import duckdb, time, os
D="/Users/kpkautum/Documents/Projects/finbot/Datasets"; T=f"{D}/financial_transactions"
OUT="/Users/kpkautum/.claude/jobs/b441694d/tmp/pq"
os.makedirs(OUT, exist_ok=True)
con=duckdb.connect()
t0=time.time()
# typed + cleaned transactions -> parquet zstd
con.execute(f"""COPY (
 SELECT id, date, client_id, card_id,
        TRY_CAST(replace(replace(amount,'$',''),',','') AS DECIMAL(10,2)) AS amount,
        use_chip, merchant_id, merchant_city, merchant_state,
        TRY_CAST(zip AS INTEGER) AS zip, mcc, errors
 FROM read_csv_auto('{T}/transactions_data.csv', sample_size=200000)
) TO '{OUT}/transactions.parquet' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 1000000)""")
print("txn parquet MB:", round(os.path.getsize(f"{OUT}/transactions.parquet")/1e6,1), "in", round(time.time()-t0,1),"s")

t1=time.time()
con.execute(f"""COPY (
 SELECT unnest(map_keys(target))::BIGINT AS transaction_id,
        unnest(map_values(target))='Yes' AS is_fraud
 FROM read_json('{T}/train_fraud_labels.json', columns={{'target':'MAP(VARCHAR,VARCHAR)'}}, maximum_object_size=200000000)
) TO '{OUT}/fraud_labels.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)""")
print("fraud parquet MB:", round(os.path.getsize(f"{OUT}/fraud_labels.parquet")/1e6,1), "in", round(time.time()-t1,1),"s")

for name, src in [("users",f"{T}/users_data.csv"),("cards",f"{T}/cards_data.csv"),("findex",f"{D}/GlobalFindexDatabase2025.csv")]:
    con.execute(f"COPY (SELECT * FROM read_csv_auto('{src}', sample_size=-1)) TO '{OUT}/{name}.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")
    print(f"{name} parquet MB:", round(os.path.getsize(f"{OUT}/{name}.parquet")/1e6,2))
print("TOTAL MB:", round(sum(os.path.getsize(f"{OUT}/{f}") for f in os.listdir(OUT))/1e6,1))
