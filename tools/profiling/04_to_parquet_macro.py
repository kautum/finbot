import duckdb, time, os, json
D="/Users/kpkautum/Documents/Projects/finbot/Datasets"; T=f"{D}/financial_transactions"
OUT="/Users/kpkautum/.claude/jobs/b441694d/tmp/pq"
con=duckdb.connect()
# databank wide -> long
t0=time.time()
import pandas as pd
df = pd.read_excel(f"{D}/Databank-wide.xlsx", sheet_name="Data")
print("databank raw shape:", df.shape)
id_vars=[c for c in ["countrynewwb","codewb","year","regionwb21_hi","incomegroupwb21","pop_adult"] if c in df.columns]
print("id_vars found:", id_vars)
long_df = df.melt(id_vars=id_vars, var_name="indicator_code", value_name="value")
long_df = long_df.dropna(subset=["value"])
long_df["value"]=pd.to_numeric(long_df["value"], errors="coerce")
print("databank long shape (non-null):", long_df.shape)
con.register("db_long", long_df)
con.execute(f"COPY db_long TO '{OUT}/databank.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")
print("databank parquet MB:", round(os.path.getsize(f"{OUT}/databank.parquet")/1e6,2), round(time.time()-t0,1),"s")
mcc=json.load(open(f"{T}/mcc_codes.json"))
con.execute("CREATE TABLE mcc AS SELECT * FROM (VALUES " + ",".join(f"({k},'{v.replace(chr(39),chr(39)*2)}')" for k,v in mcc.items()) + ") t(mcc_code, description)")
con.execute(f"COPY mcc TO '{OUT}/mcc_codes.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")
print("TOTAL ALL PARQUET MB:", round(sum(os.path.getsize(f"{OUT}/{f}") for f in os.listdir(OUT))/1e6,1))
for f in sorted(os.listdir(OUT)): print(f"  {f}: {os.path.getsize(OUT+'/'+f)/1e6:.2f} MB")
