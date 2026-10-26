import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

print("disk names containing 'ascii':")
for p in REPO.rglob("*.svg"):
    if "ascii" in p.name:
        print("   ", p.name.encode("utf-8"), p.stat().st_size)

print("\nREADME (HEAD) references:")
head = subprocess.run(
    ["git", "show", "HEAD:README.md"], cwd=REPO, capture_output=True, text=True
).stdout
for m in re.finditer(r'src="([^"]+)"', head):
    if "ascii" in m.group(1):
        print("   ", m.group(1).encode("utf-8"))

print("\nREADME (disk) references:")
disk = (REPO / "README.md").read_text(encoding="utf-8")
for m in re.finditer(r'src="([^"]+)"', disk):
    if "ascii" in m.group(1):
        print("   ", m.group(1).encode("utf-8"))

print("\ngit ls-files:")
out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout
for line in out.splitlines():
    if "ascii" in line:
        print("   ", line.encode("utf-8"))

print("\nusername in data:", __import__("json").load(
    open(REPO / "data/contributions.json", encoding="utf-8"))["username"].encode("utf-8"))
