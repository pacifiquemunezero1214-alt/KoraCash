import os
import psycopg
from dotenv import load_dotenv

load_dotenv(override=True)

database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise RuntimeError("DATABASE_URL ntibonetse")

conn = psycopg.connect(database_url)

cur = conn.cursor()

cur.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = %s
    ORDER BY ordinal_position
""", ("users",))

print("=== CURRENT NEON USERS COLUMNS ===")

for row in cur.fetchall():
    print(row[0])

cur.close()
conn.close()