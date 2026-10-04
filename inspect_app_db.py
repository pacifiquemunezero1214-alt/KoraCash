from pathlib import Path

p = Path("app.py")
text = p.read_text(encoding="utf-8")

print("=== APP DATABASE SECTION ===")
start = text.find("DATABASE =")
end = text.find("def ensure_column")
print(text[start:end])

print("=== APP IMPORTS ===")
print("\n".join(text.splitlines()[:45]))
