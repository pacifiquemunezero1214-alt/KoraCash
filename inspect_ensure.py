from pathlib import Path

text = Path("app.py").read_text(encoding="utf-8")

start = text.find("def ensure_column")
end = text.find("\ndef ", start + 5)

print("=== ensure_column ===")
print(text[start:end])
