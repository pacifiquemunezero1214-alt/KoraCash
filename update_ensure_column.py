from pathlib import Path

p = Path("app.py")
text = p.read_text(encoding="utf-8")

start = text.find("def ensure_column(")
if start == -1:
    raise RuntimeError("ensure_column ntibonetse")

end = text.find("\ndef ", start + 5)
if end == -1:
    raise RuntimeError("End ya ensure_column ntibonetse")

new_block = '''def ensure_column(
    conn,
    table_name,
    column_name,
    definition,
):
    if DATABASE_URL:
        columns = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
            """,
            (table_name,),
        ).fetchall()
    else:
        columns = conn.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()

    existing_columns = {
        column["column_name"] if DATABASE_URL else column["name"]
        for column in columns
    }

    if column_name not in existing_columns:
        conn.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {definition}
            """
        )
'''

text = text[:start] + new_block + text[end:]

p.write_text(text, encoding="utf-8")

print("ENSURE COLUMN: UPDATED")
