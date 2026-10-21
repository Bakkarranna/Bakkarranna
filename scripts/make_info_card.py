"""Generate info-card.svg -- a neofetch-style panel that prints line by line.

Hand-authored so the content lives here, not in the contribution graph: the
graph covers GitHub stats, this card is for the story numbers can't tell.
Each line fades and slides in on a short stagger so the panel looks like it's
printing next to the portrait.

The card is transparent and light-theme-first: GitHub's default canvas is
white, and the previous palette was dark-theme text (#c9d1d9 on white) which
rendered the body nearly invisible. A prefers-color-scheme media query
re-inks everything for GitHub's dark theme (SVGs served as <img> inherit the
embedding page's color scheme in Chromium).

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

# Light-theme ink (GitHub light primitives), dark-theme overrides in DARK.
FG = "#1f2328"       # values / body
DIM = "#59636e"      # secondary text
ACCENT = "#1a7f37"   # green headline accent
SWATCHES = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39", "#1a7f37"]

DARK = {
    "fg": "#e6edf3", "dim": "#8b949e", "accent": "#3fb950",
    "rule": "#30363d",
    "swatches": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"],
    "rows": ["#3fb950", "#58a6ff", "#d29922", "#bc8cff", "#f778ba"],
}
LIGHT_ROWS = ["#1a7f37", "#0969da", "#9a6700", "#8250df", "#bf3989"]

# The story the numbers can't tell. (key, value, light color, dark color)
ROWS = [
    ("Now", "building agentic systems at Synaptix Studio", LIGHT_ROWS[0], DARK["rows"][0]),
    ("Prev", "F1 race-strategy analytics on OpenF1/FastF1", LIGHT_ROWS[1], DARK["rows"][1]),
    ("Stack", "Python / TypeScript / PHP / Kotlin", LIGHT_ROWS[2], DARK["rows"][2]),
    ("Focus", "shipping LLM agents that survive production", LIGHT_ROWS[3], DARK["rows"][3]),
    ("Also", "onboard vision for motorsport telemetry", LIGHT_ROWS[4], DARK["rows"][4]),
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


def theme_css(static: bool) -> str:
    css = [
        ".fg{fill:" + FG + "}",
        ".dim{fill:" + DIM + "}",
        ".accent{fill:" + ACCENT + "}",
        ".rule{stroke:#d0d7de}",
    ]
    for i, c in enumerate(SWATCHES):
        css.append(f".sw{i}{{fill:{c}}}")
    if not static:
        css.insert(0, ".line,.title,.swatches,.logo{opacity:0}")
        css += [
            "@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}",
            ".title{animation:rise .5s ease .15s forwards}",
            ".swatches{animation:rise .5s ease .5s forwards}",
            ".logo{animation:rise .6s ease .2s forwards}",
            ".line{animation:rise .5s ease forwards}",
        ]
    # Dark-theme re-ink.
    dark = [".fg{fill:" + DARK["fg"] + "}", ".dim{fill:" + DARK["dim"] + "}",
            ".accent{fill:" + DARK["accent"] + "}", ".rule{stroke:" + DARK["rule"] + "}"]
    for i, c in enumerate(DARK["swatches"]):
        dark.append(f".sw{i}{{fill:{c}}}")
    css.append("@media (prefers-color-scheme: dark){" + "".join(dark) + "}")
    css.append("@media (prefers-reduced-motion: reduce)"
               "{.line,.title,.swatches,.logo{animation:none;opacity:1}}")
    return "".join(css)


def build(static: bool) -> str:
    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="{FONT}">'
    )
    svg.append(f"<style>{theme_css(static)}</style>")
    if static:
        svg.append("<style>.line,.title,.swatches,.logo{opacity:1}</style>")

    # ---- left column: logo + swatches -------------------------------------
    svg.append(f'<g class="logo">{pixel_logo(30, 26, 13, ACCENT)}</g>')
    svg.append(f'<text x="30" y="158" font-size="13" class="dim">synaptix-studio</text>')
    sw = "".join(
        f'<rect x="{30 + i * 26}" y="176" width="22" height="10" rx="2" class="sw{i}"/>'
        for i in range(len(SWATCHES))
    )
    svg.append(f'<g class="swatches">{sw}</g>')

    # ---- right column: title + key/value rows ------------------------------
    tx, ty = 168, 44
    svg.append(
        f'<text class="title fg" x="{tx}" y="{ty}" font-size="19" font-weight="bold">'
        f"bakkarranna@github</text>"
    )
    svg.append(
        f'<line class="rule" x1="{tx}" y1="{ty + 12}" x2="{W - 16}" y2="{ty + 12}" stroke-width="1"/>'
    )

    for i, (key, value, light, dark) in enumerate(ROWS):
        y = ty + 46 + i * 42
        delay = 0.6 + i * 0.28
        style = "" if static else f' style="animation-delay:{delay:.2f}s"'
        svg.append(
            f'<g class="line"{style}>'
            f'<circle cx="{tx + 4}" cy="{y - 4}" r="4" fill="{light}"/>'
            f'<text x="{tx + 18}" y="{y}" font-size="13" fill="{light}">{escape(key)}</text>'
            f'<text x="{tx + 96}" y="{y}" font-size="13" class="fg">{escape(value)}</text>'
            f"</g>"
        )

    # contact line at the bottom
    contact_y = ty + 46 + len(ROWS) * 42
    cd = 0.6 + len(ROWS) * 0.28
    cstyle = "" if static else f' style="animation-delay:{cd:.2f}s"'
    svg.append(
        f'<g class="line"{cstyle}>'
        f'<text x="{tx}" y="{contact_y}" font-size="12" class="dim">'
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
