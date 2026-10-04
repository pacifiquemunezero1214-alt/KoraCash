from pathlib import Path

p = Path("app.py")
text = p.read_text(encoding="utf-8")

text = text.replace(
    "import sqlite3\n",
    "import sqlite3\nimport psycopg\nfrom psycopg.rows import dict_row\n"
)

old = '''DATABASE = os.path.join(BASE_DIR, "koracash.db")

app = Flask(__name__)
'''

new = '''DATABASE = os.path.join(BASE_DIR, "koracash.db")
DATABASE_URL = os.getenv("DATABASE_URL")

app = Flask(__name__)
'''

if old not in text:
    raise RuntimeError("DATABASE block ntibonetse")

text = text.replace(old, new, 1)

start = text.find("def get_db():")
end = text.find("\\n\\n", start)

if start == -1:
    raise RuntimeError("get_db() ntibonetse")

old_get_db = text[start:end]

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

    return conn'''

text = text[:start] + new_get_db + text[end:]

p.write_text(text, encoding="utf-8")

print("APP DATABASE LAYER: UPDATED")
