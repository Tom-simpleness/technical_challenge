"""
generate_csv.py — run this to produce sample_transactions.csv for testing.
Usage: python generate_csv.py
"""

import csv
import random
import uuid
from datetime import datetime, timedelta

CATEGORIES = ["food", "transport", "utilities", "entertainment", "health", "travel"]
MERCHANTS = [
    "Carrefour", "SNCF", "EDF", "Netflix", "Doctolib",
    "Air France", "Fnac", "Decathlon", "Uber", "Leclerc",
]
CURRENCIES = ["EUR", "USD", "GBP"]
STATUSES = ["completed", "completed", "completed", "pending", "failed"]

TOTAL_ROWS = 5000
DUPLICATE_REFS = 40   # rows that share a reference with an earlier row
BAD_ROWS = 30         # rows with missing or malformed fields

base_date = datetime(2024, 1, 1)
references = []

rows = []
for i in range(TOTAL_ROWS - DUPLICATE_REFS - BAD_ROWS):
    ref = str(uuid.uuid4())
    references.append(ref)
    rows.append(
        {
            "reference": ref,
            "amount": round(random.uniform(1.0, 2000.0), 2),
            "currency": random.choice(CURRENCIES),
            "category": random.choice(CATEGORIES),
            "merchant": random.choice(MERCHANTS),
            "status": random.choice(STATUSES),
            "transacted_at": (
                base_date + timedelta(days=random.randint(0, 364),
                                      hours=random.randint(0, 23))
            ).isoformat(),
        }
    )

for _ in range(DUPLICATE_REFS):
    ref = random.choice(references)
    rows.append(
        {
            "reference": ref,
            "amount": round(random.uniform(1.0, 500.0), 2),
            "currency": "EUR",
            "category": random.choice(CATEGORIES),
            "merchant": random.choice(MERCHANTS),
            "status": "completed",
            "transacted_at": (
                base_date + timedelta(days=random.randint(0, 364))
            ).isoformat(),
        }
    )

for _ in range(BAD_ROWS):
    rows.append(
        {
            "reference": str(uuid.uuid4()),
            "amount": random.choice(["", "not-a-number", None]),
            "currency": random.choice(CURRENCIES),
            "category": "",
            "merchant": random.choice(MERCHANTS),
            "status": "completed",
            "transacted_at": random.choice(["", "31/02/2024", "not-a-date"]),
        }
    )

random.shuffle(rows)

with open("sample_transactions.csv", "w", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["reference", "amount", "currency", "category",
                    "merchant", "status", "transacted_at"],
    )
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated sample_transactions.csv ({TOTAL_ROWS} rows)")
print(f"  {DUPLICATE_REFS} duplicate references")
print(f"  {BAD_ROWS} malformed rows")
