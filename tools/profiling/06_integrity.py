import duckdb
con=duckdb.connect("/Users/kpkautum/.claude/jobs/b441694d/tmp/finbot.duckdb", read_only=True)
q=lambda s: con.execute(s).fetchall()
print("users:", q("SELECT count(*) FROM users"), "cards:", q("SELECT count(*) FROM cards"))
print("users with txns:", q("SELECT count(DISTINCT c.client_id) FROM cards c JOIN transactions t ON t.card_id=c.id"))
print("orphan card_ids in txn:", q("SELECT count(*) FROM transactions t LEFT JOIN cards c ON t.card_id=c.id WHERE c.id IS NULL"))
print("orphan client_ids:", q("SELECT count(*) FROM transactions t LEFT JOIN users u ON t.client_id=u.id WHERE u.id IS NULL"))
print("cards cols:", [r[0] for r in q("DESCRIBE cards")])
print("users cols:", [r[0] for r in q("DESCRIBE users")])
print("findex cols n:", q("SELECT count(*) FROM (DESCRIBE findex)"), "rows:", q("SELECT count(*) FROM findex"))
print("findex countries/years:", q("SELECT count(DISTINCT countrynewwb), min(year), max(year) FROM findex"))
print("databank years:", q("SELECT min(year), max(year), count(DISTINCT indicator_code), count(DISTINCT countrynewwb) FROM databank"))
# fraud counts per segment -> statistical power check
print("min fraud per MCC segment:", q("""SELECT count(*) segs, sum(CASE WHEN fr<10 THEN 1 ELSE 0 END) segs_under_10_fraud FROM
 (SELECT t.mcc, sum(f.is_fraud::INT) fr FROM transactions t JOIN fraud_labels f ON t.id=f.transaction_id GROUP BY 1)"""))
