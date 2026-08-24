"""What is in the dataset, in plain English, for the UI's discovery panel.

Every number here is measured at startup rather than written down, so the panel cannot
drift away from the data the way a hand-maintained data dictionary does.
"""
import db

# Grouped so the panel reads as "here is what you can slice by", not as a schema dump.
FIELD_GROUPS = [
    {
        "group": "Transaction",
        "fields": [
            ("date", "When it happened, to the minute"),
            ("amount", "Value in USD. Negative means a refund"),
            ("channel", "Online, in-person domestic, or in-person foreign"),
            ("use_chip", "Chip, swipe, or online"),
            ("is_fraud", "Whether it was confirmed fraudulent"),
            ("errors", "What went wrong, if anything, at the terminal"),
        ],
    },
    {
        "group": "Merchant",
        "fields": [
            ("mcc_description", "Category, e.g. Grocery Stores"),
            ("merchant_city", "City the merchant is in"),
            ("merchant_country", "Country, or blank for online"),
            ("merchant_id", "Anonymous merchant identifier"),
        ],
    },
    {
        "group": "Card",
        "fields": [
            ("card_brand", "Visa, Mastercard, Amex, Discover"),
            ("card_type", "Credit, debit, or prepaid"),
            ("credit_limit", "The card's limit in USD"),
        ],
    },
    {
        "group": "Cardholder",
        "fields": [
            ("current_age", "Age in years"),
            ("gender", "Reported gender"),
            ("credit_score", "Credit score, roughly 480-850"),
            ("yearly_income", "Annual income in USD"),
        ],
    },
]

# Sample questions, the pattern every product in this space converges on (Databricks Genie
# calls them "sample questions", ThoughtSpot "quickstart suggestions"). Grouped by the kind
# of analysis rather than by table, because the user is picking a question, not a join.
QUESTION_GROUPS = [
    {
        "group": "Fraud",
        "blurb": "Where losses concentrate, and whether the pattern is real",
        "questions": [
            "Which merchant categories have the worst fraud rates?",
            "Is online fraud significantly higher than in-person?",
            "How did fraud change year over year?",
        ],
    },
    {
        "group": "Spending",
        "blurb": "Volume, value, and how they move over time",
        "questions": [
            "How has total spending changed year over year?",
            "What are the biggest merchant categories by spend?",
            "What does an average transaction look like by card brand?",
        ],
    },
    {
        "group": "Customers",
        "blurb": "Who spends, who gets targeted, and how they differ",
        "questions": [
            "Does credit score predict being defrauded?",
            "How does spending vary by age group?",
            "Do higher-income cardholders use different card types?",
        ],
    },
    {
        "group": "Deep dives",
        "blurb": "The questions a dashboard cannot answer",
        "questions": [
            "Which country has the strangest fraud pattern, and when did it start?",
            "Are chip transactions actually safer than swipe?",
            "Which merchant categories are too small to draw conclusions from?",
        ],
    },
]

_STATS_SQL = """
SELECT count(*)                                   AS labeled_transactions,
       sum(is_fraud::INT)                         AS fraud_cases,
       round(100.0*sum(is_fraud::INT)/count(*),4) AS fraud_rate_pct,
       count(DISTINCT client_id)                  AS cardholders,
       count(DISTINCT card_id)                    AS cards,
       count(DISTINCT merchant_id)                AS merchants,
       count(DISTINCT mcc_description)            AS categories,
       count(DISTINCT merchant_country)           AS countries,
       min(date)::VARCHAR                         AS first_date,
       max(date)::VARCHAR                         AS last_date
FROM v_transactions
"""


def build(con) -> dict:
    cols, rows, err = db.run(con, _STATS_SQL)
    if err:
        raise RuntimeError(f"catalog stats failed: {err}")
    stats = dict(zip(cols, rows[0]))

    _, cov, _ = db.run(con, "SELECT total_transactions, unlabeled_transactions FROM v_coverage")
    stats["total_transactions"], stats["unlabeled_transactions"] = cov[0]

    _, chan, _ = db.run(con, """
        SELECT channel, count(*), round(100.0*sum(is_fraud::INT)/count(*), 4)
        FROM v_transactions GROUP BY 1 ORDER BY 3 DESC""")
    stats["channels"] = [{"name": c, "transactions": n, "fraud_rate_pct": r} for c, n, r in chan]

    return {
        "stats": {k: (float(v) if isinstance(v, float) else v) for k, v in stats.items()},
        "field_groups": [
            {"group": g["group"], "fields": [{"name": n, "description": d} for n, d in g["fields"]]}
            for g in FIELD_GROUPS
        ],
        "question_groups": QUESTION_GROUPS,
        # Stated plainly because it is the caveat that makes every fraud number here honest.
        "caveat": (
            f"Fraud figures cover the {stats['labeled_transactions']:,} transactions that carry "
            f"a fraud label. A further {stats['unlabeled_transactions']:,} have no label and are "
            "excluded, because counting them would understate every fraud rate by about a third."
        ),
    }


if __name__ == "__main__":
    import json

    out = build(db.connect())
    assert out["stats"]["labeled_transactions"] == 8_914_963, out["stats"]
    assert len(out["stats"]["channels"]) == 3
    print(json.dumps(out["stats"], indent=2, default=str))
