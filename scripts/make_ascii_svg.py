"""Convert source-prepped.png into a self-typing monochrome ASCII SVG.

The prepped image is downsampled to a character grid (100x53) and each pixel's
brightness picks a glyph from a density ramp -- sparse characters for bright
areas, dense ones for dark:

    RAMP = " .`:-=+*cs#%@"   # bright (sparse) -> dark (dense)
    # ^ leading space clears the background to nothing

Two design choices keep it clean instead of noisy:
  * Monochrome -- one ink fill. Per-character rainbow coloring is what
    makes most ASCII portraits look like static.
  * High contrast -- a busy background washes out to the space glyph, so only
    the subject prints.

Animation: rows fade and rise in on a stagger top-to-bottom, so the portrait
types itself into existence. The reveal is CSS keyframes animating only opacity
and transform on each row group.

Why opacity/transform and not the two clip approaches tried before it:
  1. SMIL <animate> on the width of a <rect> inside a <clipPath> (the heatmap
     technique) froze in the start state -- every row stayed clipped to
     width 0 and the portrait rendered as a blank box with only the cursor
     blocks visible. Verified on the live profile: 1.22% ink, cursors present,
     glyph text absent.
  2. CSS keyframes animating clip-path:inset() on the group was also honoured
     only partially -- it froze mid-clip and left a faint partial trace.
     clip-path is not a compositor property in this context, so it is the one
     animatable property that does not unpause.

opacity + transform are the properties the info card and heatmap already
animate successfully in the same camo <img> context, and they degrade safely:
if a renderer drops the animation entirely, the end state is opacity 1 and
translateY(0), so the art can only ever render complete -- never blank.

The fill is set per <text> element, not only on the root: a root-level fill
attribute is ignored for text when the SVG renders as a standalone image
(glyphs came out black). A prefers-color-scheme media query re-inks the
portrait for GitHub's dark theme, and prefers-reduced-motion skips the print.

The fill is set per <text> element, not only on the root: a root-level fill
attribute is ignored for text when the SVG renders as a standalone image
(glyphs came out black). A prefers-color-scheme media query re-inks the
portrait for GitHub's dark theme, and prefers-reduced-motion skips the print.

Run: python scripts/make_ascii_svg.py      # writes bakkarranna-ascii.svg
"""
from pathlib import Path
from xml.sax.saxutils import escape

import cv2

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

COLS, ROWS = 100, 53
RAMP = " .`:-=+*cs#%" + "@"  # bright (sparse) -> dark (dense)
INK = "#57606a"   # light-theme glyph ink (readable on white canvas)
INK_DARK = "#c6cdd5"  # dark-theme glyph ink
FONT_STACK = "'JetBrains Mono','Fira Mono','SFMono-Regular',Menlo,Consolas,monospace"

# Character cell metrics for the monospace grid (viewBox units).
CELL_W, CELL_H = 7.2, 13.6

# Print timing. Rows fade+rise rather than wipe: a left-to-right wipe needs
# clip-path, and animating clip-path on an SVG group is the one thing that
# never unfreezes behind GitHub's camo <img> (it froze mid-clip on the live
# profile, leaving a faint partial trace -- measured at 1.22% ink). opacity +
# transform are the properties the info card and heatmap already animate
# successfully in that same context, so the reveal uses only those.
ROW_DURATION = 0.42   # seconds for one row to fade/rise in
ROW_STAGGER = 0.055   # delay between rows -> ~3.2s for the whole portrait
WIDTH = COLS * CELL_W
HEIGHT = ROWS * CELL_H


def to_ascii_rows(gray) -> list[str]:
    grid = cv2.resize(gray, (COLS, ROWS), interpolation=cv2.INTER_AREA)
    rows = []
    for y in range(ROWS):
        chars = []
        for x in range(COLS):
            v = int(grid[y, x])  # 0 (black) .. 255 (white)
            # Invert: the prepped photo's background is pure white and must land
            # on the blank end of the ramp (a space), while dark subject detail
            # gets the dense glyphs. Mapping brightness forward (white -> '@')
            # renders the portrait as a negative.
            idx = len(RAMP) - 1 - int(round((v / 255.0) * (len(RAMP) - 1)))
            chars.append(RAMP[idx])
        rows.append("".join(chars))
    return rows


def build_svg(rows: list[str]) -> str:
    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH:.0f}" height="{HEIGHT:.0f}" '
        f'viewBox="0 0 {WIDTH:.0f} {HEIGHT:.0f}" font-family="{FONT_STACK}" fill="{INK}">'
    )
    out.append(
        "<style>"
        "text{fill:" + INK + ";white-space:pre;letter-spacing:0}"
        ".row{animation:line " + f"{ROW_DURATION}s" + " ease both}"
        "@keyframes line{from{opacity:0;transform:translateY(3px)}"
        "to{opacity:1;transform:translateY(0)}}"
        f"@media (prefers-color-scheme: dark){{text{{fill:{INK_DARK}}}}}"
        "@media (prefers-reduced-motion: reduce)"
        "{.row{animation:none;opacity:1;transform:none}}"
        "</style>"
    )

    for r, text in enumerate(rows):
        delay = r * ROW_STAGGER
        baseline = r * CELL_H + CELL_H * 0.72  # text baseline inside the cell
        out.append(
            f'<g class="row" style="animation-delay:{delay:.2f}s">'
            f'<text x="0" y="{baseline:.1f}" fill="{INK}">{escape(text)}</text>'
            f"</g>"
        )
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    src = HERE / "source-prepped.png"
    gray = cv2.imread(str(src), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise SystemExit(f"missing {src} -- run prep_photo.py first")
    rows = to_ascii_rows(gray)
    svg = build_svg(rows)
    dst = REPO / "bakkarranna-ascii.svg"
    dst.write_text(svg, encoding="utf-8")
    print(
        f"[ascii] wrote {dst} ({COLS}x{ROWS} grid, "
        f"{ROWS * ROW_STAGGER + ROW_DURATION:.1f}s reveal)"
    )


if __name__ == "__main__":
    main()
