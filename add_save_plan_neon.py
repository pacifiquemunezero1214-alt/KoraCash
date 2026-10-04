import os
import psycopg
from dotenv import load_dotenv

load_dotenv(override=True)

database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise RuntimeError("DATABASE_URL ntibonetse")

conn = psycopg.connect(database_url)

try:
    cur = conn.cursor()

    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
    """, ("users",))

    columns = {row[0] for row in cur.fetchall()}

    print("=== BEFORE MIGRATION ===")
    print("save_plan exists:", "save_plan" in columns)

    if "save_plan" not in columns:
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN save_plan INTEGER
        """)
        print("save_plan yongewemo neza.")
    else:
        print("save_plan yari isanzwe ihari. Nta cyahinduwe.")

    conn.commit()

    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, ("users",))

    print()
    print("=== USERS COLUMNS AFTER MIGRATION ===")

    for row in cur.fetchall():
        print(row[0], "-", row[1])

finally:
    conn.close()

print()
print("MIGRATION: OK")