import os
from dotenv import load_dotenv
import psycopg

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing")

TABLES = [
    "cash_ins",
    "daily_activities",
    "notifications",
    "referrals",
    "task_submissions",
    "tasks",
    "transactions",
    "users",
    "videos",
    "withdrawals",
]

conn = psycopg.connect(DATABASE_URL)

try:
    for table in TABLES:
        sequence = f"{table}_id_seq"

        conn.execute(
            f'CREATE SEQUENCE IF NOT EXISTS "{sequence}"'
        )

        row = conn.execute(
            f'SELECT COALESCE(MAX(id), 0) FROM "{table}"'
        ).fetchone()

        max_id = int(row[0])

        if max_id > 0:
            conn.execute(
                f"SELECT setval('{sequence}', {max_id}, true)"
            )
        else:
            conn.execute(
                f"SELECT setval('{sequence}', 1, false)"
            )

        conn.execute(
            f"""
            ALTER TABLE "{table}"
            ALTER COLUMN id
            SET DEFAULT nextval('{sequence}'::regclass)
            """
        )

        conn.execute(
            f"""
            ALTER SEQUENCE "{sequence}"
            OWNED BY "{table}".id
            """
        )

        print(f"OK: {table} -> {sequence}")

    conn.commit()
    print("")
    print("NEON ID SEQUENCES: OK")

finally:
    conn.close()