import os
import psycopg
from dotenv import load_dotenv

load_dotenv(override=True)

conn = psycopg.connect(os.getenv("DATABASE_URL"))

with conn.cursor() as cur:
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'users'
        ORDER BY ordinal_position
    """)

    print("=== USERS COLUMNS ===")

    for row in cur.fetchall():
        print(row)

conn.close()
