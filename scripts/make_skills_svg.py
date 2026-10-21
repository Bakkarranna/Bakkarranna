"""Generate skills.svg -- grouped skill chips with five-segment level meters.

Content is hand-authored here (same as info-card.svg): the contributions graph
covers GitHub activity, the info card covers the story, and this one covers the
toolbox. Levels are 1..5 and are drawn as meter segments rather than a numeric
score, so the panel reads at a glance instead of looking like a spreadsheet.

Design constraints inherited from the other three SVGs -- each one exists
because an earlier attempt broke behind GitHub's camo <img> proxy:
  * No <script>, no <foreignObject>, no external fonts or images. Camo strips
    scripts, so anything interactive is dead weight.
  * Animation is opacity + transform only. Animating geometry (clip-path,
    rect width) froze mid-print behind camo; those two properties never do.
  * Light theme first, re-inked by a prefers-color-scheme media query, because
    GitHub's default canvas is white and a dark-theme-first SVG renders its own
    text invisible there.
  * prefers-reduced-motion collapses every group to its end state, and the end
    state of every animation here is fully visible, so a renderer that drops
    animation can only ever show a complete panel.

Run: python scripts/make_skills_svg.py            # animated
     STATIC=1 python scripts/make_skills_svg.py   # frozen frame for screenshots
"""
import os
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
FONT = "'JetBrains Mono','Fira Mono','SFMono-Regular',Menlo,Consolas,monospace"

# Light theme first (GitHub light primitives); DARK re-inks everything below.
FG = "#1f2328"
DIM = "#59636e"
CHIP_BG = "#f6f8fa"
CHIP_RULE = "#d0d7de"
METER_EMPTY = "#d8dee4"
INK = "#1f2328"

GROUP_INK = ["#1a7f37", "#0969da", "#9a6700", "#8250df"]        # light
DARK_GROUP_INK = ["#3fb950", "#58a6ff", "#d29922", "#bc8cff"]   # dark
DARK = {
    "fg": "#e6edf3",
    "dim": "#8b949e",
    "chip_bg": "#161b22",
    "chip_rule": "#30363d",
    "meter_empty": "#30363d",
}

# Groups of skills with a 1..5 level. Kept to six per row so the panel stays
# one row per group instead of wrapping into a ragged block.
GROUPS = [
    ("languages", [("Python", 5), ("TypeScript", 4), ("PHP", 3), ("Kotlin", 3), ("SQL", 3), ("Rust", 2)]),
    ("agentic", [("LLM agents", 5), ("Tool use", 4), ("MCP servers", 4), ("RAG", 4), ("Evals", 3)]),
    ("backend", [("FastAPI", 5), ("Node", 4), ("Laravel", 3), ("Postgres", 4), ("Docker", 4)]),
    ("data", [("pandas", 5), ("NumPy", 5), ("OpenCV", 4), ("FastF1", 4), ("OpenF1", 4)]),
]

CHIP_W, CHIP_H = 124, 44
CHIP_GAP = 12
MARGIN = 16
HEADER_H = 20        # group label + breathing room above its chip row
GROUP_GAP = 18       # gap between group blocks
TITLE_BLOCK = 54     # title + rule
METER_SEGMENTS = 5
METER_W, METER_H, METER_GAP = 13, 4, 3

W = MARGIN * 2 + CHIP_W * 6 + CHIP_GAP * 5   # 836 -> 868
H = TITLE_BLOCK + len(GROUPS) * (HEADER_H + CHIP_H + GROUP_GAP) + CHIP_H


def chip(x: int, y: int, name: str, level: int, idx: int) -> str:
    """One chip: rounded plate, skill name, five-segment meter underneath."""
    mx = x + 10
    my = y + CHIP_H - 14
    segs = []
    for i in range(METER_SEGMENTS):
        on = i < level
        segs.append(
            f'<rect x="{mx + i * (METER_W + METER_GAP)}" y="{my}" '
            f'width="{METER_W}" height="{METER_H}" rx="2" '
            f'class="m{" on" if on else ""} g{idx}"/>'
        )
    return (
        f'<g class="chip">'
        f'<rect x="{x}" y="{y}" width="{CHIP_W}" height="{CHIP_H}" rx="6" class="plate"/>'
        f'<text x="{x + 10}" y="{y + 20}" font-size="13" class="fg">{escape(name)}</text>'
        + "".join(segs)
        + "</g>"
    )


def theme_css(static: bool) -> str:
    css = [
        ".fg{fill:" + FG + "}",
        ".dim{fill:" + DIM + "}",
        ".plate{fill:" + CHIP_BG + ";stroke:" + CHIP_RULE + "}",
        ".m{fill:" + METER_EMPTY + "}",
    ]
    for i, c in enumerate(GROUP_INK):
        css.append(f".g{i}{{fill:{c}}}")
    if not static:
        css += [
            ".grp{opacity:0}",
            "@keyframes rise{from{opacity:0;transform:translateY(8px)}"
            "to{opacity:1;transform:translateY(0)}}",
            ".grp{animation:rise .45s ease forwards}",
        ]
    dark = [
        ".fg{fill:" + DARK["fg"] + "}",
        ".dim{fill:" + DARK["dim"] + "}",
        ".plate{fill:" + DARK["chip_bg"] + ";stroke:" + DARK["chip_rule"] + "}",
        ".m{fill:" + DARK["meter_empty"] + "}",
    ]
    for i, c in enumerate(DARK_GROUP_INK):
        dark.append(f".g{i}{{fill:{c}}}")
    css.append("@media (prefers-color-scheme: dark){" + "".join(dark) + "}")
    css.append(
        "@media (prefers-reduced-motion: reduce){.grp{animation:none;opacity:1;transform:none}}"
    )
    return "".join(css)


def build(static: bool) -> str:
    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="{FONT}">'
    )
    out.append(f"<style>{theme_css(static)}</style>")
    if static:
        out.append("<style>.grp{opacity:1;transform:none}</style>")

    out.append(
        f'<text x="{MARGIN}" y="26" font-size="15" class="fg" '
        f'font-weight="bold">skills</text>'
    )
    out.append(
        f'<text x="{MARGIN + 52}" y="26" font-size="12" class="dim">'
        f"--format=meters  (5 = daily driver, 1 = dabbling)</text>"
    )
    out.append(
        f'<line x1="{MARGIN}" y1="36" x2="{W - MARGIN}" y2="36" '
        f'stroke="{CHIP_RULE}" stroke-width="1"/>'
    )

    y = TITLE_BLOCK
    for gi, (label, skills) in enumerate(GROUPS):
        ink = GROUP_INK[gi]
        delay = 0.15 + gi * 0.22
        style = "" if static else f' style="animation-delay:{delay:.2f}s"'
        out.append(f'<g class="grp"{style}>')
        out.append(
            f'<text x="{MARGIN}" y="{y}" font-size="11" class="g{gi}" '
            f'letter-spacing="1.5">{escape(label)}</text>'
        )
        for ci, (name, level) in enumerate(skills):
            out.append(chip(MARGIN + ci * (CHIP_W + CHIP_GAP), y + 8, name, level, gi))
        out.append("</g>")
        y += HEADER_H + CHIP_H + GROUP_GAP

    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    static = os.environ.get("STATIC") == "1"
    svg = build(static)
    dst = REPO / "skills.svg"
    dst.write_text(svg, encoding="utf-8")
    print(f"[skills] wrote {dst} ({len(GROUPS)} groups, {'static' if static else 'animated'})")


if __name__ == "__main__":
    main()
