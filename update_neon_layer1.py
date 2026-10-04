from pathlib import Path

p = Path("app.py")
text = p.read_text(encoding="utf-8")

# Add PostgreSQL imports
if "import psycopg" not in text:
    text = text.replace(
        "import sqlite3\n",
        "import sqlite3\nimport psycopg\nfrom psycopg.rows import dict_row\n",
        1
    )

# Add DATABASE_URL
if 'DATABASE_URL = os.getenv("DATABASE_URL")' not in text:
    text = text.replace(
        'DATABASE = os.path.join(BASE_DIR, "koracash.db")',
        'DATABASE = os.path.join(BASE_DIR, "koracash.db")\nDATABASE_URL = os.getenv("DATABASE_URL")',
        1
    )

# Replace the complete get_db() function safely
start = text.find("def get_db():")
if start == -1:
    raise RuntimeError("get_db() ntibonetse")

end = text.find("\ndef ensure_column", start)
if end == -1:
    raise RuntimeError("ensure_column ntibonetse")

new_get_db = '''def get_db():
    if DATABASE_URL:
        return psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row,
        )

    conn = sqlite3.connect(
        DATABASE,
        timeout=30,
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    return conn


'''

text = text[:start] + new_get_db + text[end + 1:]

p.write_text(text, encoding="utf-8")

print("NEON DB LAYER 1: UPDATED")
