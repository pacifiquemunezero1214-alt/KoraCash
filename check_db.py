import sqlite3

conn = sqlite3.connect("koracash.db")

print("\n=== TABLES AND SCHEMAS ===")

tables = conn.execute("""
SELECT name
FROM sqlite_master
WHERE type='table'
ORDER BY name
""").fetchall()

for (table_name,) in tables:
    print(f"\n=== {table_name.upper()} ===")

    columns = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    for column in columns:
        print(column)

conn.close()