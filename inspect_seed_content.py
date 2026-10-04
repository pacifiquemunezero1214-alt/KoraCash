from pathlib import Path

text = Path("app.py").read_text(encoding="utf-8")

start = text.find("def seed_content(")
if start == -1:
    raise RuntimeError("seed_content ntibonetse")

end = text.find("\ndef ", start + 5)
if end == -1:
    end = text.find("\n# ============================================================", start + 5)

print("=== SEED_CONTENT ===")
print(text[start:end])
