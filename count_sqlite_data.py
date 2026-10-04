import sqlite3

conn = sqlite3.connect("koracash.db")
cur = conn.cursor()

tables = [
    "users",
    "tasks",
    "videos",
    "transactions",
    "withdrawals",
    "cash_ins",
    "referrals",
    "notifications",
    "daily_activities",
    "task_submissions"
]

print("=== SQLITE RECORD COUNTS ===")

for table in tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"{table}: {count}")

conn.close()
