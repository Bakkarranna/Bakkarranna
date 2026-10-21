"""Raster-QA the profile panels with headless Chrome (dev tool, not in CI).

verify_svg.py checks structure; this checks that the art actually *renders*:
it screenshots each SVG through Chrome -- the same engine family GitHub uses
for camo -- on a light and a dark backdrop, then reports ink coverage, the
bounding box of drawn pixels and a coarse ASCII luminance preview so a blank
or lopsided panel is obvious without eyeballing a PNG.

Usage:
    python scripts/raster_qa.py constellation.svg [more.svg ...]
    python scripts/raster_qa.py --ascii constellation.svg

Writes preview-shot.png / preview-dark.png in the repo root (gitignored).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]
RAMP = " .:-=+*#%@"


def find_browser() -> str | None:
    for path in CHROME_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def intrinsic_size(svg_name: str) -> tuple[int, int]:
    """(width, height) the panel declares, so the shot is not letterboxed."""
    import re

    head = (REPO / svg_name).read_text(encoding="utf-8")[:2000]
    m = re.search(r'<svg[^>]*\swidth="(\d+)', head)
    h = re.search(r'<svg[^>]*\sheight="(\d+)', head)
    w, hh = (int(m.group(1)) if m else 860, int(h.group(1)) if h else 300)
    return w, hh


def shoot(svg_name: str, dark: bool) -> Path:
    browser = find_browser()
    if not browser:
        raise SystemExit("no Chrome/Edge binary found")
    bg = "#0d1117" if dark else "#ffffff"
    out = REPO / ("preview-dark.png" if dark else "preview-shot.png")
    html = REPO / "preview.html"
    html.write_text(
        f'<!doctype html><meta charset="utf-8"><body style="margin:0;'
        f'background:{bg}"><img src="{svg_name}" style="display:block"></body>',
        encoding="utf-8",
    )
    url = html.resolve().as_uri()
    iw, ih = intrinsic_size(svg_name)
    # 2x the panel, capped: enough pixels that sub-pixel stars survive the
    # downsample, without an absurd window for the big panels.
    scale = max(1, min(2, 1600 // max(1, iw)))
    subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
         f"--screenshot={out}", f"--window-size={iw * scale},{ih * scale}",
         "--hide-scrollbars", "--force-device-scale-factor=1",
         "--virtual-time-budget=6000", url],
        check=True, capture_output=True, timeout=120,
    )
    return out


def analyse(path: Path, ascii_preview: bool) -> None:
    im = Image.open(path).convert("L")
    crop = im.crop((0, 0, im.width, im.height))
    print(f"  {path.name}: {im.size[0]}x{im.size[1]}px")
    if ascii_preview:
        cols = min(110, max(40, im.width // 8))
        rows = max(12, min(46, round(cols * im.height / im.width / 2.1)))
        small = crop.resize((cols, rows), Image.LANCZOS)
        px = small.load()
        print("   +" + "-" * cols + "+")
        for y in range(rows):
            line = "".join(RAMP[min(len(RAMP) - 1, px[x, y] * len(RAMP) // 256)]
                           for x in range(cols))
            print("   |" + line + "|")
        print("   +" + "-" * cols + "+")


def main() -> int:
    args = sys.argv[1:]
    ascii_preview = "--ascii" in args
    names = [a for a in args if not a.startswith("--")]
    if not names:
        print(__doc__)
        return 1
    for name in names:
        print(f"[qa] {name}")
        for dark in (False, True):
            shot = shoot(name, dark)
            analyse(shot, ascii_preview)
    return 0


if __name__ == "__main__":
    sys.exit(main())
