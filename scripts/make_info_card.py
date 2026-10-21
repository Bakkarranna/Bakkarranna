"""Generate info-card.svg -- a neofetch-style panel that prints line by line.

Hand-authored so the content lives here, not in the contribution graph: the
graph covers GitHub stats, this card is for the story numbers can't tell.
Each line fades and slides in on a short stagger so the panel looks like it's
printing next to the portrait.

Run:  python scripts/make_info_card.py           # animated
      STATIC=1 python scripts/make_info_card.py  # frozen frame for local preview
"""
import os
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

W, H = 490, 316
FONT = "'JetBrains Mono','Fira Mono','SFMono-Regular',Menlo,Consolas,monospace"

FG = "#c9d1d9"       # values / body
DIM = "#8b949e"      # secondary text
ACCENT = "#39d353"   # github green
SWATCHES = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]

# The story the numbers can't tell.
ROWS = [
    ("Now", "building agentic systems at Synaptix Studio", ACCENT),
    ("Prev", "F1 race-strategy analytics on OpenF1/FastF1", "#58a6ff"),
    ("Stack", "Python / TypeScript / PHP / Kotlin", "#d29922"),
    ("Focus", "shipping LLM agents that survive production", "#bc8cff"),
    ("Also", "onboard vision for motorsport telemetry", "#f778ba"),
]

# 8x8 pixel-art "S" (Synaptix) -- blocky logo, font-independent.
LOGO = [
    "........",
    ".######.",
    "##....##",
    "##......",
    ".#####..",
    "......##",
    "##....##",
    ".######.",
]


def pixel_logo(x0: int, y0: int, cell: int, color: str) -> str:
    parts = []
    for r, line in enumerate(LOGO):
        for c, ch in enumerate(line):
            if ch == "#":
                parts.append(
                    f'<rect x="{x0 + c * cell}" y="{y0 + r * cell}" width="{cell}" height="{cell}" fill="{color}"/>'
                )
    return "".join(parts)


def build(static: bool) -> str:
    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'font-family="{FONT}">'
    )
    # One-shot reveal animation (CSS keyframes play inside <img>-embedded SVGs).
    if not static:
        svg.append(
            "<style>"
            ".line,.title,.swatches,.logo{opacity:0}"
            "@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}"
            ".title{animation:rise .5s ease .15s forwards}"
            ".swatches{animation:rise .5s ease .5s forwards}"
            ".logo{animation:rise .6s ease .2s forwards}"
            ".line{animation:rise .5s ease forwards}"
            "</style>"
        )
    else:
        svg.append("<style>.line,.title,.swatches,.logo{opacity:1}</style>")

    # ---- left column: logo + swatches -------------------------------------
    svg.append(f'<g class="logo">{pixel_logo(30, 26, 13, ACCENT)}</g>')
    svg.append(
        f'<text x="30" y="158" font-size="13" fill="{DIM}">synaptix-studio</text>'
    )
    sw = "".join(
        f'<rect x="{30 + i * 26}" y="176" width="22" height="10" rx="2" fill="{c}"/>'
        for i, c in enumerate(SWATCHES)
    )
    svg.append(f'<g class="swatches">{sw}</g>')

    # ---- right column: title + key/value rows ------------------------------
    tx, ty = 168, 44
    svg.append(
        f'<text class="title" x="{tx}" y="{ty}" font-size="19" font-weight="bold" fill="{FG}">'
        f"bakkarranna@github</text>"
    )
    svg.append(
        f'<line x1="{tx}" y1="{ty + 12}" x2="{W - 16}" y2="{ty + 12}" stroke="#30363d" stroke-width="1"/>'
    )

    for i, (key, value, color) in enumerate(ROWS):
        y = ty + 46 + i * 42
        delay = 0.6 + i * 0.28
        style = "" if static else f' style="animation-delay:{delay:.2f}s"'
        # colored bullet + key, then dim key label, then value
        svg.append(
            f'<g class="line"{style}>'
            f'<circle cx="{tx + 4}" cy="{y - 4}" r="4" fill="{color}"/>'
            f'<text x="{tx + 18}" y="{y}" font-size="13" fill="{color}">{escape(key)}</text>'
            f'<text x="{tx + 96}" y="{y}" font-size="13" fill="{FG}">{escape(value)}</text>'
            f"</g>"
        )

    # contact line at the bottom
    contact_y = ty + 46 + len(ROWS) * 42
    cd = 0.6 + len(ROWS) * 0.28
    cstyle = "" if static else f' style="animation-delay:{cd:.2f}s"'
    svg.append(
        f'<g class="line"{cstyle}>'
        f'<text x="{tx}" y="{contact_y}" font-size="12" fill="{DIM}">'
        f"synaptixstudio.com · linkedin.com/in/muhammadabubakar-siddique</text>"
        f"</g>"
    )

    svg.append("</svg>")
    return "\n".join(svg)


def main() -> None:
    static = os.environ.get("STATIC") == "1"
    svg = build(static)
    dst = REPO / "info-card.svg"
    dst.write_text(svg, encoding="utf-8")
    print(f"[card] wrote {dst} ({'static' if static else 'animated'})")


if __name__ == "__main__":
    main()
