import app

conn = app.get_db()

rows = conn.execute("""
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'cash_ins'
ORDER BY ordinal_position
""").fetchall()

for row in rows:
    print(dict(row))

conn.close()
