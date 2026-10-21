"""Convert source-prepped.png into a self-typing monochrome ASCII SVG.

The prepped image is downsampled to a character grid (100x53) and each pixel's
brightness picks a glyph from a density ramp -- sparse characters for bright
areas, dense ones for dark:

    RAMP = " .`:-=+*cs#%@"   # bright (sparse) -> dark (dense)
    # ^ leading space clears the background to nothing

Two design choices keep it clean instead of noisy:
  * Monochrome -- one light-gray fill. Per-character rainbow coloring is what
    makes most ASCII portraits look like static.
  * High contrast -- a busy background washes out to the space glyph, so only
    the subject prints.

Animation: each row is wrapped in a horizontal clip that wipes left-to-right
(a small block "cursor" rides the wipe edge), staggered top to bottom. The
portrait prints once and freezes -- SMIL, so GitHub plays it.

Run: python scripts/make_ascii_svg.py      # writes bakkarranna-ascii.svg
"""
from pathlib import Path
from xml.sax.saxutils import escape

import cv2

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

COLS, ROWS = 100, 53
RAMP = " .`:-=+*cs#%@"  # bright (sparse) -> dark (dense)
FILL = "#9ba3af"  # single light-gray monochrome fill
FONT_STACK = "'JetBrains Mono','Fira Mono','SFMono-Regular',Menlo,Consolas,monospace"

# Character cell metrics for the monospace grid (viewBox units).
CELL_W, CELL_H = 7.2, 13.6

# Print timing.
ROW_DURATION = 1.05   # seconds for one row to wipe across
ROW_STAGGER = 0.34    # delay between rows
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
        f'viewBox="0 0 {WIDTH:.0f} {HEIGHT:.0f}" font-family="{FONT_STACK}" '
        f'font-size="12" fill="{FILL}">'
    )
    out.append(
        "<style>text{white-space:pre;letter-spacing:0}</style>"
    )
    # One clip per row, each animating its reveal width; a cursor block rides the edge.
    out.append("<defs>")
    for r in range(ROWS):
        out.append(
            f'<clipPath id="rowClip{r}"><rect id="clipRect{r}" x="0" y="0" width="0" '
            f'height="{CELL_H:.1f}"><animate attributeName="width" from="0" to="{WIDTH:.0f}" '
            f'dur="{ROW_DURATION}s" begin="{r * ROW_STAGGER:.2f}s" fill="freeze" '
            f'calcMode="spline" keySplines="0.4 0 0.2 1" keyTimes="0;1" '
            f'values="0;{WIDTH:.0f}"/></rect></clipPath>'
        )
    out.append("</defs>")

    for r, text in enumerate(rows):
        delay = r * ROW_STAGGER
        baseline = r * CELL_H + CELL_H * 0.72  # text baseline inside the cell
        out.append(
            f'<g clip-path="url(#rowClip{r})">'
            f'<text x="0" y="{baseline:.1f}">{escape(text)}</text>'
            f"</g>"
        )
        # Cursor block that rides the wipe edge, frozen at the end of the row.
        out.append(
            f'<rect x="0" y="{baseline - CELL_H * 0.82:.1f}" width="{CELL_W * 1.2:.1f}" '
            f'height="{CELL_H * 0.85:.1f}" fill="{FILL}" opacity="0.9">'
            f'<animate attributeName="x" from="0" to="{WIDTH - CELL_W * 1.2:.1f}" '
            f'dur="{ROW_DURATION}s" begin="{delay:.2f}s" fill="freeze" '
            f'calcMode="spline" keySplines="0.4 0 0.2 1" keyTimes="0;1" values="0;{WIDTH - CELL_W * 1.2:.1f}"/>'
            f'<animate attributeName="opacity" values="0.9;0.9" dur="{ROW_DURATION}s" '
            f'begin="{delay:.2f}s" fill="freeze"/>'
            f"</rect>"
        )
    # Hide the last cursor once its row finishes so the portrait freezes clean.
    last = (ROWS - 1) * ROW_STAGGER + ROW_DURATION
    out.append(
        f'<rect x="0" y="0" width="0" height="0" fill="none">'
        f'<animate attributeName="width" from="0" to="{WIDTH:.0f}" begin="{last:.2f}s" '
        f'dur="0.001s" fill="freeze"/></rect>'
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
    print(f"[ascii] wrote {dst} ({COLS}x{ROWS} grid, {ROWS * ROW_STAGGER + ROW_DURATION:.1f}s print)")


if __name__ == "__main__":
    main()
