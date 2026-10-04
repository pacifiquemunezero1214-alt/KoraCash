import os
import sqlite3
import psycopg
from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing")

SQLITE_DB = "koracash.db"

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

sqlite_conn = sqlite3.connect(SQLITE_DB)
sqlite_conn.row_factory = sqlite3.Row

try:
    with psycopg.connect(DATABASE_URL) as pg_conn:
        with pg_conn.cursor() as pg_cur:

            for table in tables:
                print(f"Migrating {table}...")

                sqlite_cur = sqlite_conn.execute(
                    f"SELECT * FROM {table}"
                )

                rows = sqlite_cur.fetchall()

                if not rows:
                    print(f"  {table}: 0 records")
                    continue

                columns = [description[0] for description in sqlite_cur.description]

                column_sql = ", ".join(f'"{c}"' for c in columns)
                placeholders = ", ".join(["%s"] * len(columns))

                insert_sql = f"""
                    INSERT INTO "{table}" ({column_sql})
                    VALUES ({placeholders})
                    ON CONFLICT DO NOTHING
                """

                for row in rows:
                    pg_cur.execute(
                        insert_sql,
                        tuple(row[c] for c in columns)
                    )

                print(f"  {table}: {len(rows)} records")

        pg_conn.commit()

finally:
    sqlite_conn.close()

print("")
print("MIGRATION: OK")
