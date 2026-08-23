import os
import json
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DATA_DIR = Path("../Datasets")
TXN_DIR = DATA_DIR / "financial_transactions"

engine = create_engine(os.getenv("DATABASE_URL"))


def load_small_csv(path, table_name):
    print(f"Loading {table_name} from {path.name} ...")
    df = pd.read_csv(path)
    df.to_sql(table_name, engine, if_exists="replace", index=False)
    print(f"  -> {len(df):,} rows loaded into '{table_name}'")


def load_large_csv_chunked(path, table_name, chunksize=50_000):
    print(f"Loading {table_name} from {path.name} in chunks of {chunksize:,} ...")
    total = 0
    for i, chunk in enumerate(pd.read_csv(path, chunksize=chunksize)):
        chunk.to_sql(
            table_name,
            engine,
            if_exists="replace" if i == 0 else "append",
            index=False,
        )
        total += len(chunk)
        print(f"  chunk {i+1}: {total:,} rows loaded so far", end="\r")
    print(f"\n  -> {total:,} total rows loaded into '{table_name}'")


def load_mcc_codes(path, table_name):
    print(f"Loading {table_name} from {path.name} ...")
    with open(path) as f:
        data = json.load(f)
    df = pd.DataFrame(list(data.items()), columns=["mcc_code", "description"])
    df.to_sql(table_name, engine, if_exists="replace", index=False)
    print(f"  -> {len(df):,} rows loaded into '{table_name}'")


def load_fraud_labels(path, table_name):
    print(f"Loading {table_name} from {path.name} ...")
    with open(path) as f:
        data = json.load(f)

    # train_fraud_labels.json is typically {"target": {txn_id: "Yes"/"No", ...}}
    records = data.get("target", data)
    df = pd.DataFrame(list(records.items()), columns=["transaction_id", "is_fraud"])
    df.to_sql(table_name, engine, if_exists="replace", index=False, chunksize=50_000)
    print(f"  -> {len(df):,} rows loaded into '{table_name}'")


def load_findex(path, table_name):
    print(f"Loading {table_name} from {path.name} ...")
    df = pd.read_csv(path)
    df.to_sql(table_name, engine, if_exists="replace", index=False)
    print(f"  -> {len(df):,} rows loaded into '{table_name}'")


def load_databank_wide(path, table_name):
    print(f"Loading {table_name} from {path.name} (Data sheet, reshaped to long format) ...")
    df = pd.read_excel(path, sheet_name="Data")

    id_vars = [c for c in ["countrynewwb", "codewb", "year", "regionwb21_hi", "incomegroupwb21", "pop_adult"] if c in df.columns]
    value_vars = [c for c in df.columns if c not in id_vars]

    long_df = df.melt(id_vars=id_vars, value_vars=value_vars, var_name="indicator_code", value_name="value")
    long_df["value"] = long_df["value"].astype(str)

    long_df.to_sql(table_name, engine, if_exists="replace", index=False, chunksize=20_000)
    print(f"  -> {len(long_df):,} rows loaded into '{table_name}' (long format)")

if __name__ == "__main__":
    load_small_csv(TXN_DIR / "users_data.csv", "users")
    load_small_csv(TXN_DIR / "cards_data.csv", "cards")
    load_mcc_codes(TXN_DIR / "mcc_codes.json", "mcc_codes")
    load_fraud_labels(TXN_DIR / "train_fraud_labels.json", "fraud_labels")
    load_findex(DATA_DIR / "GlobalFindexDatabase2025.csv", "findex_2025")
    load_databank_wide(DATA_DIR / "Databank-wide.xlsx", "databank_wide")
    load_large_csv_chunked(TXN_DIR / "transactions_data.csv", "transactions")

    print("\nAll tables loaded successfully.")