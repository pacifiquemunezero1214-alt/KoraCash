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

    print("=== TASK REWARDS ===")

    cur.execute("""
        SELECT id, title, reward, is_active
        FROM tasks
        ORDER BY id
    """)

    for row in cur.fetchall():
        print(row)

    print()
    print("=== VIDEO REWARDS ===")

    cur.execute("""
        SELECT id, title, reward, is_active
        FROM videos
        ORDER BY id
    """)

    for row in cur.fetchall():
        print(row)

finally:
    conn.close()