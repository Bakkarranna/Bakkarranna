import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAR = ROOT / "docs" / "variants"

NAME = {
    "static": "A static (control)",
    "clipcss": "B clipcss (current, suspect)",
    "clipsmil": "C clipsmil (SMIL)",
    "wipecss": "D wipecss (transform+opacity)",
    "fuse": "E fuse (per-glyph opacity)",
}

parts = ["<!DOCTYPE html><meta charset=utf-8><title>variants</title>",
         "<style>body{margin:0;background:#fff;font:12px monospace}"
         "img{display:block;image-rendering:pixelated}</style>"]
for k, label in NAME.items():
    p = VAR / f"{k}.svg"
    if not p.exists():
        continue
    b64 = base64.b64encode(p.read_bytes()).decode()
    parts.append(f"<div>{label}</div>")
    parts.append(f'<img src="data:image/svg+xml;base64,{b64}" width="480">')
(VAR / "compare.html").write_text("".join(parts), encoding="utf-8")
print("wrote docs/variants/compare.html")
