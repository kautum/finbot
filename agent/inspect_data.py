import pandas as pd
from pathlib import Path

data_dir = Path("../Datasets")

xlsx_path = data_dir / "Databank-wide.xlsx"
findex_path = data_dir / "GlobalFindexDatabase2025.csv"
txn_path = data_dir / "financial_transactions"

print("=== Databank-wide.xlsx ===")
xl = pd.ExcelFile(xlsx_path)
print("Sheets:", xl.sheet_names)
df = xl.parse(xl.sheet_names[0], nrows=5)
print("Shape (first sheet, sample):", df.shape)
print("Columns:", list(df.columns))

print("\n=== GlobalFindexDatabase2025.csv ===")
df2 = pd.read_csv(findex_path, nrows=5)
print("Columns:", list(df2.columns))
row_count = sum(1 for _ in open(findex_path)) - 1
print("Approx rows:", row_count)

print("\n=== financial_transactions ===")
if txn_path.is_dir():
    for f in txn_path.iterdir():
        print(f.name, f.stat().st_size / 1e6, "MB")
else:
    df3 = pd.read_csv(txn_path, nrows=5)
    print("Columns:", list(df3.columns))