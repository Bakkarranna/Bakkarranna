"""Generate info-card.svg -- a neofetch-style panel that prints line by line.

Hand-authored so the content lives here, not in the contribution graph: the
graph covers GitHub stats, this card is for the story numbers can't tell.
Each line fades and slides in on a short stagger so the panel looks like it's
printing next to the portrait.

Layout, and why it is the way it is:
    Left column (x 30..150)  rounded logo tile + <title> wordmark + swatches.
    Right column (x 176..)   title, rule, then five key/value rows.
Every row is *measured*, not guessed: the value column has a hard budget of
VALUE_BUDGET characters at the monospace advance width, so a value can never
run off the 520px canvas. An earlier version drew values at a fixed x with a
13px monospace font and they silently spilled past the viewBox edge, which is
what made the card look like it was overlapping its neighbours.

The card is transparent and light-theme-first: GitHub's default canvas is
white, and the previous palette was dark-theme text (#c9d1d9 on white) which
rendered the body nearly invisible. A prefers-color-scheme media query
re-inks everything for GitHub's dark theme (SVGs served as <img> inherit the
embedding page's color scheme in Chromium).

Run:  python scripts/make_info_card.py           # animated
      STATIC=1 python scripts/make_info_card.py  # frozen frame for local preview
"""
import json
import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import tile_mark  # noqa: E402  (paths in, so it needs the scripts dir on sys.path)
W, H = 560, 340
FONT = "'JetBrains Mono','Fira Mono','SFMono-Regular',Menlo,Consolas,monospace"

FS_VALUE = 13.0
ADV = 0.60 * FS_VALUE          # monospace advance, ~7.8px per char
VALUE_X = 176                  # left edge of the value column
VALUE_END = W - 18             # right edge values may occupy
VALUE_BUDGET = int((VALUE_END - 246) / ADV)   # 246 = VALUE_X + key width

# Light-theme ink (GitHub light primitives), dark-theme overrides in DARK.
FG = "#1f2328"       # values / body
DIM = "#59636e"      # secondary text
ACCENT = "#1a7f37"   # green headline accent (logo pixels, .px)
SWATCHES = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39", "#1a7f37"]

DARK = {
    "fg": "#e6edf3", "dim": "#8b949e", "px": "#3fb950",
    "rule": "#30363d",
    "swatches": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"],
    "rows": ["#3fb950", "#58a6ff", "#d29922", "#bc8cff", "#f778ba"],
}
LIGHT_ROWS = ["#1a7f37", "#0969da", "#9a6700", "#8250df", "#bf3989"]

# The story the numbers can't tell. (key, value, light color, dark color)
ROWS = [
    ("Now", "agentic systems @ Synaptix Studio", LIGHT_ROWS[0], DARK["rows"][0]),
    ("Prev", "F1 race-strategy analytics (OpenF1)", LIGHT_ROWS[1], DARK["rows"][1]),
    ("Stack", "Python / TypeScript / PHP / Kotlin", LIGHT_ROWS[2], DARK["rows"][2]),
    ("Focus", "shipping LLM agents that survive prod", LIGHT_ROWS[3], DARK["rows"][3]),
    ("Also", "onboard vision for motorsport", LIGHT_ROWS[4], DARK["rows"][4]),
]

# Synaptix mark: a rounded tile holding the traced neural "S" -- two
# interlocking arms with their gaps cut out, so it re-inks in dark.
LOGO_TILE = 116
LOGO_X, LOGO_Y = 30, 30
# The mark's silhouette, traced off the source render by trace_mark.py.
MARK = REPO / "data" / "synaptix-mark.json"


def logo_tile() -> str:
    """Soft rounded tile with a corner highlight, so the mark sits on a plate."""
    return (
        f'<rect x="{LOGO_X}" y="{LOGO_Y}" width="{LOGO_TILE}" '
        f'height="{LOGO_TILE}" rx="26" ry="26" class="tile"/>'
        f'<rect x="{LOGO_X + 8}" y="{LOGO_Y + 8}" width="{LOGO_TILE - 16}" '
        f'height="{LOGO_TILE - 16}" rx="20" ry="20" class="tile-in"/>'
    )


# Hard bound on the glyph: the mark is clipped to the inner plate, so the logo
# can never be wider than the box the card puts it in.
CLIP_ID = "logo-plate"


def logo_clip() -> str:
    return (
        f'<clipPath id="{CLIP_ID}">'
        f'<rect x="{LOGO_X + 8}" y="{LOGO_Y + 8}" width="{LOGO_TILE - 16}" '
        f'height="{LOGO_TILE - 16}" rx="20" ry="20"/>'
        "</clipPath>"
    )


def logo_glyph() -> str:
    """The traced Synaptix mark: two <path> arms, gaps included.

    The silhouette is authored data (data/synaptix-mark.json), not a hand-drawn
    approximation: tile_mark.glyph scales and centres it into the tile, so the
    card's logo is the same mark the favicon and the README badge carry.
    """
    try:
        mark = json.loads(MARK.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"[card] cannot read mark {MARK}: {exc}") from exc
    return tile_mark.glyph(mark)



def theme_css(static: bool) -> str:
    css = [
        ".fg{fill:" + FG + "}",
        ".dim{fill:" + DIM + "}",
        ".rule{stroke:#d0d7de}",
        ".tile{fill:#eef3ee}",
        ".tile-in{fill:#ffffff}",
        ".mk0,.mk1{fill:" + ACCENT + "}",
    ]
    for i, c in enumerate(SWATCHES):
        css.append(f".sw{i}{{fill:{c}}}")
    for i, c in enumerate(LIGHT_ROWS):
        css.append(f".row{i}{{fill:{c}}}")
    if not static:
        css.insert(0, ".line,.title,.swatches,.logo{opacity:0}")
        css += [
            "@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}",
            # No delay baked into the shorthand: every reveal position lives on the
            # element as animation-delay, the way the heatmap ramps its cells, so
            # the whole card's timing reads off one list in build().
            ".title{animation:rise .5s ease forwards}",
            ".swatches{animation:rise .5s ease forwards}",
            ".logo{animation:rise .6s ease forwards}",
            ".line{animation:rise .5s ease forwards}",
        ]
    dark = [".fg{fill:" + DARK["fg"] + "}", ".dim{fill:" + DARK["dim"] + "}",
            ".rule{stroke:" + DARK["rule"] + "}",
            ".tile{fill:#12181f}", ".tile-in{fill:#0d1117}",
            ".mk0,.mk1{fill:" + DARK["px"] + "}"]
    for i, c in enumerate(DARK["swatches"]):
        dark.append(f".sw{i}{{fill:{c}}}")
    for i, c in enumerate(DARK["rows"]):
        dark.append(f".row{i}{{fill:{c}}}")
    css.append("@media (prefers-color-scheme: dark){" + "".join(dark) + "}")
    css.append("@media (prefers-reduced-motion: reduce)"
               "{.line,.title,.swatches,.logo{animation:none;opacity:1;transform:none}}")
    return "".join(css)


def build(static: bool) -> str:
    def delay(seconds: float) -> str:
        """Inline reveal position, or nothing for the frozen static frame."""
        return "" if static else f' style="animation-delay:{seconds:.2f}s"'

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="{FONT}">'
    )
    svg.append(f"<style>{theme_css(static)}</style>")
    if static:
        svg.append("<style>.line,.title,.swatches,.logo{opacity:1}</style>")

    # ---- left column: logo + wordmark + swatches ---------------------------
    svg.append(
        f"<defs>{logo_clip()}</defs>"
        f'<g class="logo"{delay(0.20)}>{logo_tile()}'
        f'<g clip-path="url(#{CLIP_ID})">{logo_glyph()}</g></g>'
    )
    svg.append(
        f'<text class="title dim"{delay(0.15)} x="{LOGO_X + LOGO_TILE / 2}" '
        f'y="{LOGO_Y + LOGO_TILE + 26}" font-size="13" text-anchor="middle">'
        f"synaptix-studio</text>"
    )
    sw = "".join(
        f'<rect x="{LOGO_X + (i % 3) * 40}" y="{LOGO_Y + LOGO_TILE + 40 + (i // 3) * 20}" '
        f'width="34" height="15" rx="2" class="sw{i}"/>'
        for i in range(len(SWATCHES))
    )
    svg.append(f'<g class="swatches"{delay(0.50)}>{sw}</g>')

    # ---- right column: title + key/value rows ------------------------------
    svg.append(
        f'<text class="title fg"{delay(0.15)} x="{VALUE_X}" y="46" '
        f'font-size="19" font-weight="bold">bakkarranna@github</text>'
    )
    svg.append(
        f'<line class="rule" x1="{VALUE_X}" y1="58" x2="{W - 18}" '
        f'y2="58" stroke-width="1"/>'
    )

    for i, (key, value, _light, _dark) in enumerate(ROWS):
        y = 90 + i * 40
        style = delay(0.60 + i * 0.28)
        assert len(value) <= VALUE_BUDGET, (value, len(value), VALUE_BUDGET)
        svg.append(
            f'<g class="line"{style}>'
            f'<circle cx="{VALUE_X + 4}" cy="{y - 4}" r="4" class="row{i}"/>'
            f'<text x="{VALUE_X + 18}" y="{y}" font-size="13" class="row{i}">'
            f"{escape(key)}</text>"
            f'<text x="246" y="{y}" font-size="13" class="fg">{escape(value)}</text>'
            f"</g>"
        )

    # contact line, full width underneath so it cannot collide with a value
    contact_y = 90 + len(ROWS) * 40 - 6
    style = delay(0.60 + len(ROWS) * 0.28)
    svg.append(
        f'<g class="line"{style}>'
        f'<line class="rule" x1="{VALUE_X}" y1="{contact_y - 20}" '
        f'x2="{W - 18}" y2="{contact_y - 20}" stroke-width="1"/>'
        f'<text x="{VALUE_X}" y="{contact_y}" font-size="12" class="dim">'
        f"synaptixstudio.com &#183; linkedin.com/in/muhammadabubakar-siddique</text>"
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
