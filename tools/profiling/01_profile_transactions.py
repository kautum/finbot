import duckdb, time
D = "/Users/kpkautum/Documents/Projects/finbot/Datasets"
T = f"{D}/financial_transactions"
con = duckdb.connect()
q = lambda s: con.execute(s).fetchall()

t0=time.time()
con.execute(f"""CREATE VIEW txn AS SELECT * FROM read_csv_auto('{T}/transactions_data.csv', sample_size=200000)""")
print("SCHEMA txn:", q("DESCRIBE txn"))
print("COUNT:", q("SELECT count(*) FROM txn"))
print("DATE RANGE:", q("SELECT min(date), max(date) FROM txn"))
print("DISTINCT:", q("""SELECT count(DISTINCT client_id) clients, count(DISTINCT card_id) cards,
   count(DISTINCT merchant_id) merchants, count(DISTINCT mcc) mccs,
   count(DISTINCT merchant_state) states FROM txn"""))
print("AMOUNT (parsed):", q("""SELECT round(min(a),2), round(max(a),2), round(avg(a),2), round(median(a),2)
  FROM (SELECT TRY_CAST(replace(replace(amount,'$',''),',','') AS DOUBLE) a FROM txn)"""))
print("NEG AMOUNTS:", q("SELECT count(*) FROM txn WHERE amount LIKE '$-%'"))
print("ERRORS TOP:", q("SELECT errors, count(*) c FROM txn GROUP BY 1 ORDER BY c DESC LIMIT 6"))
print("USE_CHIP:", q("SELECT use_chip, count(*) c FROM txn GROUP BY 1 ORDER BY c DESC"))
print("ROWS PER YEAR:", q("SELECT year(CAST(date AS TIMESTAMP)) y, count(*) c FROM txn GROUP BY 1 ORDER BY 1"))
print("elapsed", round(time.time()-t0,1))
