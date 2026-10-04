from app import get_db

conn = get_db()

try:
    row = conn.execute(
        "SELECT id, phone FROM users ORDER BY id LIMIT 1"
    ).fetchone()

    print("NEON APP CONNECTION: OK")
    print("FIRST USER:", dict(row) if row else None)

finally:
    conn.close()
