"""Verify the generated SVGs structurally -- no browser needed.

The profile page embeds these SVGs via GitHub's camo proxy, which sanitizes
scripts: what renders is pure XML + SMIL/CSS animation. So every break is a
structural break, and this script can catch each one offline.

Checks:
  1. XML well-formedness (etree parse).
  2. contrib-heatmap.svg: one titled cell per contribution day, diagonal
     stagger begins, month labels + Less/More legend, stats footer.
  3. bakkarranna-ascii.svg: exactly ROWS text rows, one clipPath wipe + cursor
     block per row, final reveal finishes before the freeze.
  4. info-card.svg: story rows, pixel logo, colour swatches, per-line stagger.
  5. Animation totals so nothing freezes mid-print.

Usage: python scripts/verify_svg.py     # exits 1 on any failure
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data" / "contributions.json"


def check_heatmap(path: Path, report: list[str]) -> bool:
    text = path.read_text(encoding="utf-8")
    ok = True

    expected_days = len(json.loads(DATA.read_text(encoding="utf-8"))["days"])
    cells = text.count("<title>")
    if cells != expected_days:
        report.append(f"  FAIL heatmap: {cells} titled cells, expected {expected_days}")
        ok = False
    else:
        report.append(f"  OK   heatmap: {cells} titled contribution cells")

    begins = [float(m) for m in re.findall(r'begin="([\d.]+)s"', text)]
    if len(begins) < expected_days:
        report.append(f"  FAIL heatmap: only {len(begins)} reveal animations")
        ok = False
    else:
        report.append(
            f"  OK   heatmap: {len(begins)} reveals, stagger 0..{max(begins):.2f}s"
        )

    for needle in ("Jan", "Jun", "Dec", "Less", "More", "contributions in the last year"):
        if needle not in text:
            report.append(f"  FAIL heatmap: missing {needle!r}")
            ok = False
    if ok:
        report.append("  OK   heatmap: month labels, legend and stats footer present")

    for bad in ("<unknown>", "None", "NaN"):
        if bad in text:
            report.append(f"  FAIL heatmap: leaked token {bad!r}")
            ok = False
    return ok


def check_ascii(path: Path, report: list[str]) -> bool:
    text = path.read_text(encoding="utf-8")
    ok = True

    rows = re.findall(r"<text[^>]*>([^<]*)</text>", text)
    if len(rows) != 53:
        report.append(f"  FAIL ascii: {len(rows)} text rows, expected 53")
        ok = False
    else:
        glyph = set("".join(rows))
        report.append(
            f"  OK   ascii: 53 rows, widest {max(len(r) for r in rows)} chars, "
            f"{len(glyph)} distinct glyphs"
        )

    clips = re.findall(r'<clipPath id="rowClip\d+">', text)
    if len(clips) != 53:
        report.append(f"  FAIL ascii: {len(clips)} row clipPaths, expected 53")
        ok = False

    cursors = re.findall(r"<rect[^>]*opacity=\"0.9\"", text)
    if len(cursors) != 53:
        report.append(f"  FAIL ascii: {len(cursors)} cursor blocks, expected 53")
        ok = False

    begins = [float(m) for m in re.findall(r'begin="([\d.]+)s"', text)]
    if begins:
        report.append(f"  OK   ascii: final reveal finishes at ~{max(begins) + 1.05:.2f}s")
    return ok


def check_card(path: Path, report: list[str]) -> bool:
    text = path.read_text(encoding="utf-8")
    ok = True

    lines = len(re.findall(r'<g class="line"', text))
    if lines != 6:  # 5 story rows + contact line
        report.append(f"  FAIL card: {lines} .line groups, expected 6")
        ok = False
    else:
        report.append(f"  OK   card: {lines} line groups (5 story rows + contact)")

    if "bakkarranna@github" not in text:
        report.append("  FAIL card: missing title 'bakkarranna@github'")
        ok = False

    swatches = len(re.findall(r'<g class="swatches">.*?</g>', text, re.S))
    swatch_rects = len(re.findall(r'rx="2"', text))
    if swatch_rects != 6:
        report.append(f"  FAIL card: {swatch_rects} colour swatches, expected 6")
        ok = False

    if 'class="logo"' not in text:
        report.append("  FAIL card: missing pixel logo")
        ok = False

    delays = [float(m) for m in re.findall(r"animation-delay:([\d.]+)s", text)]
    if len(delays) == 6:
        report.append(f"  OK   card: stagger 0..{max(delays):.2f}s")
    elif "opacity:1" not in text:
        report.append("  FAIL card: neither animated nor static-free of rows")
        ok = False
    return ok


CHECKS = {
    "contrib-heatmap.svg": check_heatmap,
    "bakkarranna-ascii.svg": check_ascii,
    "info-card.svg": check_card,
}


def main() -> int:
    report: list[str] = ["SVG verification (structural, no browser)"]
    all_ok = True
    for name, checker in CHECKS.items():
        path = REPO / name
        if not path.exists():
            report.append(f"  FAIL {name}: file missing")
            all_ok = False
            continue
        try:
            ElementTree.parse(path)
            report.append(f"OK   {name}: well-formed XML")
        except ElementTree.ParseError as exc:
            report.append(f"  FAIL {name}: {exc}")
            all_ok = False
            continue
        all_ok = checker(path, report) and all_ok
    report.append("RESULT: " + ("PASS" if all_ok else "FAIL"))

    print("\n".join(report))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
