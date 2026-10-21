"""Generate projects.svg — the featured-projects card row.

Six hand-curated cards (data/projects.json) rather than a live repo query: the
daily workflow runs with no token, so anything that needs the GitHub API would
either fail or go stale. The feed is authored once and refreshed by hand, but
the layout, colour ramp and text wrapping are all computed here so a longer
blurb reflows instead of overflowing.
"""

from __future__ import annotations

import html
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "projects.json"
OUT = ROOT / "projects.svg"

W = 900
PAD = 22
COLS = 3
GAP = 14
CARD_H = 176

INK = "#0d1117"
SUB = "#57606a"
RULE = "#d8dee4"
FACE = "#ffffff"
FACE_ALT = "#f6f8fa"

# Colour identity per card, reused in both themes so the row reads as a set.
ACCENTS = ["#8250df", "#0969da", "#1a7f37", "#bf3989", "#9a6700", "#cf222e"]

STATE_BADGE = {
    "public": "open source",
    "live": "live",
    "local": "private",
}

# Every label is written twice — once inside the <svg> and once inside the
# animated <defs> blocks — so the node counting below has no ordering tricks.
NODE_BUDGET = 1400


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def chips(items: list[str], limit: int = 3) -> list[str]:
    return items[:limit]


def wrap(blurb: str, width: int) -> list[str]:
    """Split a blurb into lines of at most `width` characters."""
    words = blurb.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if len(trial) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def card_w() -> float:
    return (W - 2 * PAD - (COLS - 1) * GAP) / COLS


def theme_css() -> str:
    return """<style>
    .card{fill:%(FACE)s;stroke:%(RULE)s}
    .card.alt{fill:%(FACE_ALT)s}
    .h{fill:%(INK)s;font:600 15px ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif}
    .k{fill:%(SUB)s;font:600 8.5px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;letter-spacing:1.1px}
    .b{fill:%(INK)s;font:12px ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif}
    .s{fill:%(SUB)s;font:10.5px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
    .p{fill:%(SUB)s;font:9px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;letter-spacing:.4px}
    .st{fill:%(SUB)s;font:600 8px ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif;letter-spacing:.7px}
    .badge{fill:%(FACE)s;font:700 7.5px ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif;letter-spacing:.6px}
    .ln{stroke:%(RULE)s;stroke-width:1;fill:none}
    @media (prefers-color-scheme: dark){
      .card{fill:#0d1117;stroke:#30363d}
      .card.alt{fill:#161b22}
      .h,.b{fill:#e6edf3}
      .k,.s,.p,.st{fill:#8b949e}
      .badge{fill:#0d1117}
      .ln{stroke:#30363d}
    }
    </style>""" % {"FACE": FACE, "FACE_ALT": FACE_ALT, "RULE": RULE, "INK": INK, "SUB": SUB}


def bar(total: int, peak: int, width: int) -> list[tuple[float, float]]:
    """Evenly spaced, peak-normalised column positions for a mini bar row."""
    if peak <= 0 or total <= 0:
        return []
    n = 24
    step = width / n
    pts = []
    for i in range(n):
        # Deterministic pseudo-random height, peak-normalised — a static feeder
        # row keeps the card visually alive without another data dependency.
        v = (0.35 + 0.65 * abs(math.sin(i * 12.9898) % 1.0)) * peak
        x = i * step
        y = v
        pts.append((x, y))
    return pts


def card_x(i: int) -> float:
    return PAD + i * (card_w() + GAP)


def build() -> str:
    projects = json.loads(DATA.read_text(encoding="utf-8"))["featured"]
    rows = []
    cols_rows = math.ceil(len(projects) / COLS)

    for idx, p in enumerate(projects):
        col, row = idx % COLS, idx // COLS
        x = card_x(col)
        y = PAD + row * (CARD_H + GAP)
        cw = card_w()
        accent = ACCENTS[idx % len(ACCENTS)]
        badge = STATE_BADGE.get(p.get("state", "public"), p.get("state", ""))

        parts = [f'<g transform="translate({x:.2f},{y:.2f})">']
        parts.append(
            f'<rect class="card{" alt" if idx % 2 else ""}" x="0" y="0" '
            f'width="{cw:.2f}" height="{CARD_H}" rx="12" ry="12"/>'
        )
        # accent hairline
        parts.append(
            f'<rect x="0" y="0" width="{cw:.2f}" height="3" rx="1.5" fill="{accent}"/>'
        )
        pad = 15
        iw = cw - 2 * pad

        # kicker + badge on one line
        parts.append(
            f'<text class="k" x="{pad}" y="{pad + 14}">{esc(p["kicker"]).upper()}</text>'
        )
        bw = 7.2 * len(badge) + 14
        parts.append(
            f'<rect x="{cw - pad - bw:.2f}" y="{pad + 4}" width="{bw:.2f}" height="15" '
            f'rx="7.5" fill="{accent}"/>'
        )
        parts.append(
            f'<text class="badge" x="{cw - pad - bw / 2:.2f}" y="{pad + 14.5}" '
            f'text-anchor="middle">{esc(badge).upper()}</text>'
        )

        # title
        parts.append(
            f'<text class="h" x="{pad}" y="{pad + 40}">{esc(p["name"])}</text>'
        )

        # blurb, wrapped
        lines = wrap(p["blurb"], 46)[:3]
        ty = pad + 58
        for line in lines:
            parts.append(f'<text class="b" x="{pad}" y="{ty}">{esc(line)}</text>')
            ty += 16

        # divider
        dy = CARD_H - 46
        parts.append(f'<line class="ln" x1="{pad}" y1="{dy}" x2="{cw - pad}" y2="{dy}"/>')

        # stack chips
        cx = pad
        cy = CARD_H - 24
        for chip in chips(p.get("stack", [])):
            label = esc(chip)
            cwid = 6.2 * len(label) + 12
            parts.append(
                f'<rect x="{cx:.2f}" y="{cy - 9}" width="{cwid:.2f}" height="16" rx="8" '
                f'fill="none" stroke="{RULE}"/>'
            )
            parts.append(
                f'<text class="s" x="{cx + cwid / 2:.2f}" y="{cy + 2}" '
                f'text-anchor="middle">{label}</text>'
            )
            cx += cwid + 6

        # proof line, right-aligned
        if p.get("proof"):
            parts.append(
                f'<text class="p" x="{cw - pad}" y="{cy + 2}" text-anchor="end">'
                f'{esc(p["proof"])}</text>'
            )

        parts.append("</g>")
        rows.append("".join(parts))

    height = PAD + cols_rows * CARD_H + (cols_rows - 1) * GAP + PAD
    doc = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" '
        f'viewBox="0 0 {W} {height}" role="img" '
        f'aria-label="Featured projects: {esc(", ".join(p["name"] for p in projects))}">',
        "<title>Featured projects</title>",
        theme_css(),
        *rows,
        "</svg>",
    ]
    OUT.write_text("\n".join(doc), encoding="utf-8")
    nodes = "\n".join(doc).count("<")
    print(f"wrote {OUT.relative_to(ROOT)} ({W}x{height}, ~{nodes} nodes)")
    if nodes > NODE_BUDGET:
        raise SystemExit(f"node budget exceeded: {nodes} > {NODE_BUDGET}")


if __name__ == "__main__":
    build()
