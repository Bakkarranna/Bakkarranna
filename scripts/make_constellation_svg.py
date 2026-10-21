"""Turn the prepped portrait into a star field -- constellation.svg.

The same luminance grid that drives bakkarrarna-ascii.svg is reused, but
instead of picking a glyph per cell it places a star: dark subject detail
becomes dense bright stars, the white background becomes empty sky, so the
portrait reads as a night sky instead of ASCII art. The brightest dark cells
are promoted to flared "named" stars and wired into a constellation skeleton,
which is what keeps it from looking like TV static.

Conventions shared with the other panels: transparent canvas, ink swapped by
a prefers-color-scheme media query (GitHub renders both themes), animation
limited to opacity (camo strips scripts and freezes clip-path), and
prefers-reduced-motion shows the finished sky immediately.

The daily workflow runs this too: with no source-prepped.png in CI it exits
without touching the committed art (the panel only changes when the portrait
is regenerated locally).

Run: python scripts/make_constellation_svg.py          # animated
     STATIC=1 python scripts/make_constellation_svg.py # frozen frame
"""
from __future__ import annotations

import os
from pathlib import Path
from xml.sax.saxutils import escape

import cv2

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SRC = HERE / "source-prepped.png"
FONT = "'JetBrains Mono','Fira Mono','SFMono-Regular',Menlo,Consolas,monospace"

W, H = 860, 300
GRID_W, GRID_H = 150, 52
CELL_W, CELL_H = W / GRID_W, H / GRID_H

INK = "#1f2328"        # light-theme star ink
INK_SOFT = "#57606a"   # faint stars / caption
INK_DARK = "#e6edf3"   # dark-theme star ink
INK_DARK_SOFT = "#8b949e"

SEED = 20261021
MAX_STARS = 1700       # keep the panel light enough for a README <img>
MIN_DARKNESS = 70      # below this the cell is sky, not subject
FLARE_CELLS = 150       # brightest cells become named-star points with flares
SKELETON_LINKS = 260    # cap on constellation lines (each flares once)


def _lcg(seed: int):
    """Deterministic jitter source -- the art must be byte-stable."""
    state = seed & 0xFFFFFFFF

    def nxt() -> float:
        nonlocal state
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        return state / 0x7FFFFFFF

    return nxt


def star_cells() -> tuple[list[tuple[float, float, float, int]], list[tuple[float, float]]]:
    """Return (stars, skeleton_pairs).

    stars: (x, y, radius, flare_flag) -- radius grows with darkness, so the
    subject's core prints as the densest part of the sky.
    skeleton_pairs: (x1, y1, x2, y2) lines linking the flared stars.
    """
    gray = cv2.imread(str(SRC), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise SystemExit(f"missing {SRC} -- run prep_photo.py first")
    grid = cv2.resize(gray, (GRID_W, GRID_H), interpolation=cv2.INTER_AREA)

    qualifying = [
        (gx, gy, 255 - int(grid[gy, gx]))
        for gy in range(GRID_H)
        for gx in range(GRID_W)
        if 255 - int(grid[gy, gx]) >= MIN_DARKNESS
    ]
    # Darkest first, then capped: the portrait's core prints as the densest
    # part of the sky and the paper-white backdrop stays empty.
    qualifying.sort(key=lambda c: -c[2])
    qualifying = qualifying[:MAX_STARS]
    flares = {(c[0], c[1]) for c in qualifying[:FLARE_CELLS]}

    rnd = _lcg(SEED)
    stars: list[tuple[float, float, float, int]] = []
    for gx, gy, darkness in qualifying:
        x = (gx + 0.5) * CELL_W + (rnd() - 0.5) * CELL_W * 0.5
        y = (gy + 0.5) * CELL_H + (rnd() - 0.5) * CELL_H * 0.5
        r = 0.45 + (darkness / 255.0) ** 2.0 * 1.6
        stars.append((x, y, r, 1 if (gx, gy) in flares else 0))

    # Link each flared star to the nearest other one within reach -- a sparse
    # skeleton over the core is what separates a sky from TV static.
    fl = sorted(
        flares,
        key=lambda c: -next(d for gx, gy, d in qualifying if (gx, gy) == c),
    )
    pairs: list[tuple[float, float, float, float]] = []
    for i, (gx1, gy1) in enumerate(fl):
        x1 = (gx1 + 0.5) * CELL_W
        y1 = (gy1 + 0.5) * CELL_H
        best, best_d = None, 1e9
        for j, (gx2, gy2) in enumerate(fl):
            if i == j:
                continue
            d = (gx1 - gx2) ** 2 + (gy1 - gy2) ** 2
            if d < best_d:
                best, best_d = (gx2, gy2), d
        if best and best_d < (CELL_W * 9) ** 2:
            x2 = (best[0] + 0.5) * CELL_W
            y2 = (best[1] + 0.5) * CELL_H
            pairs.append((x1, y1, x2, y2))
    return stars, pairs[:SKELETON_LINKS]


def build(static: bool) -> str:
    stars, pairs = star_cells()
    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="{FONT}">'
    )
    css = [
        ".s1{fill:" + INK + "}",
        ".s2{fill:" + INK_SOFT + "}",
        ".ln{stroke:" + INK_SOFT + ";stroke-width:.6;opacity:.5}",
        ".cap{fill:" + INK_SOFT + ";font-size:11}",
        ".hd{fill:" + INK + ";font-size:13;font-weight:bold}",
    ]
    if not static:
        css += [
            ".tw{opacity:0}",
            "@keyframes tw{to{opacity:1}}",
            ".tw{animation:tw 2.4s ease-in-out infinite alternate}",
            ".ln{animation:ln 1s ease .3s forwards}",
            "@keyframes ln{from{opacity:0}to{opacity:.5}}",
        ]
    css.append(
        "@media (prefers-color-scheme: dark){"
        + ".s1{fill:" + INK_DARK + "}.s2{fill:" + INK_DARK_SOFT + "}"
        + ".ln{stroke:" + INK_DARK_SOFT + "}"
        + ".cap{fill:" + INK_DARK_SOFT + "}.hd{fill:" + INK_DARK + "}}"
    )
    css.append(
        "@media (prefers-reduced-motion: reduce)"
        "{.tw{animation:none;opacity:1}.ln{animation:none;opacity:.5}}"
    )
    out.append("<style>" + "".join(css) + "</style>")

    out.append(
        f'<text class="hd" x="14" y="24">bakkarranna@github ~ $ stargaze</text>'
    )
    out.append(
        '<text class="cap" x="14" y="42">the same luminance grid as the ASCII '
        'portrait -- dark detail becomes stars, paper-white becomes empty sky</text>'
    )

    rnd = _lcg(SEED + 7)
    for i, (x1, y1, x2, y2) in enumerate(pairs):
        delay = "" if static else f' style="animation-delay:{0.3 + i * 0.02:.2f}s"'
        out.append(
            f'<line class="ln"{delay} x1="{x1:.1f}" y1="{y1:.1f}" '
            f'x2="{x2:.1f}" y2="{y2:.1f}"/>'
        )
    for i, (x, y, r, flare) in enumerate(stars):
        twinkle = (not static) and (i % 9 == 0)
        style = f' style="animation-delay:{rnd() * 2.4:.2f}s"' if twinkle else ""
        cls = "tw s1" if twinkle else ("s1" if flare else "s2")
        if twinkle and not flare:
            cls = "tw s2"
        out.append(
            f'<circle class="{cls}"{style} cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}"/>'
        )
        if flare:
            arm = r + 2.6
            out.append(
                f'<line class="s2" x1="{x - arm:.1f}" y1="{y:.1f}" '
                f'x2="{x + arm:.1f}" y2="{y:.1f}" stroke-width=".7"/>'
            )
            out.append(
                f'<line class="s2" x1="{x:.1f}" y1="{y - arm:.1f}" '
                f'x2="{x:.1f}" y2="{y + arm:.1f}" stroke-width=".7"/>'
            )
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    static = os.environ.get("STATIC") == "1"
    if not SRC.exists():
        # CI has no portrait: keep the committed sky untouched and succeed.
        print(f"[constellation] no {SRC.name} -- keeping existing art")
        return
    svg = build(static)
    dst = REPO / "constellation.svg"
    dst.write_text(svg, encoding="utf-8")
    n = svg.count("<circle")
    print(f"[constellation] wrote {dst} ({n} stars, {'static' if static else 'animated'})")


if __name__ == "__main__":
    main()
