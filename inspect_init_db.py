from pathlib import Path

text = Path("app.py").read_text(encoding="utf-8")

start = text.find("def init_db(")
end = text.find("\ndef ", start + 5)

print("=== INIT_DB ===")
print(text[start:end])
