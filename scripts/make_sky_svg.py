"""Turn the prepped portrait into a night sky -- night-sky.svg.

Three readings of one luminance grid, one panel:
  * dark subject detail  -> a bounded star field (darker cells, bigger stars)
  * bright paper regions -> soft nebula clouds, so the sky has weather
  * the subject's lowest dark contour -> the horizon silhouette, so the
    portrait is literally the ground the sky sits on

Unlike the other panels this one is a night scene, so it stays dark in both
GitHub themes; animation is opacity-only (scripts are stripped) and
prefers-reduced-motion shows the finished sky immediately.

The daily workflow runs this too: with no source-prepped.png in CI it exits
without touching the committed art.

Run: python scripts/make_sky_svg.py          # animated
     STATIC=1 python scripts/make_sky_svg.py # frozen frame
"""
from __future__ import annotations

import os
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SRC = HERE / "source-prepped.png"

W, H = 860, 300
TOP = 58                      # caption strip, shared with the other panels
GRID_W, GRID_H = 150, 52
CELL_W, CELL_H = W / GRID_W, H / GRID_H

STAR = "#e6edf3"
STAR_SOFT = "#8b949e"
CAP = "#8b949e"
HEAD = "#e6edf3"

SEED = 20261022
MAX_STARS = 1200
MIN_DARKNESS = 60
NEBULA_CELLS = 34             # in-subject highlights become cloud centres
BRIGHT = 215                 # a "highlight" cell: lit, but not paper
DARK_NEIGHBOURS = 3           # highlights ringed by subject, not background


def _lcg(seed: int):
    """Deterministic jitter source -- the art must be byte-stable."""
    state = seed & 0xFFFFFFFF

    def nxt() -> float:
        nonlocal state
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        return state / 0x7FFFFFFF

    return nxt


def read_grid():
    gray = cv2.imread(str(SRC), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise SystemExit(f"missing {SRC} -- run prep_photo.py first")
    return cv2.resize(gray, (GRID_W, GRID_H), interpolation=cv2.INTER_AREA)


def stars(grid) -> list[tuple[float, float, float]]:
    """(x, y, r) -- dark cells, darkest first, capped; r grows with darkness."""
    cells = [
        (gx, gy, 255 - int(grid[gy, gx]))
        for gy in range(GRID_H)
        for gx in range(GRID_W)
        if 255 - int(grid[gy, gx]) >= MIN_DARKNESS
    ]
    cells.sort(key=lambda c: -c[2])
    cells = cells[:MAX_STARS]
    rnd = _lcg(SEED)
    out = []
    for gx, gy, darkness in cells:
        x = (gx + 0.5) * CELL_W + (rnd() - 0.5) * CELL_W * 0.6
        y = TOP + (gy + 0.5) * CELL_H * (H - TOP) / H + (rnd() - 0.5) * 1.2
        out.append((x, y, 0.5 + (darkness / 255.0) ** 2.0 * 1.5))
    return out


def clouds(grid) -> list[tuple[float, float, float]]:
    """(x, y, r) highlights inside the subject -- weather over the face."""
    dark = [
        [255 - int(grid[gy, gx]) >= MIN_DARKNESS for gx in range(GRID_W)]
        for gy in range(GRID_H)
    ]
    picks = []
    for gy in range(1, GRID_H - 1):
        for gx in range(1, GRID_W - 1):
            if int(grid[gy, gx]) < BRIGHT:
                continue
            ring = sum(
                dark[gy + dy][gx + dx]
                for dy in (-1, 0, 1)
                for dx in (-1, 0, 1)
                if (dx or dy)
            )
            if ring >= DARK_NEIGHBOURS:
                picks.append((gx, gy, ring))
    picks.sort(key=lambda c: -c[2])
    picks = picks[:NEBULA_CELLS]
    rnd = _lcg(SEED + 3)
    out = []
    for gx, gy, ring in picks:
        x = (gx + 0.5) * CELL_W + (rnd() - 0.5) * 10
        y = TOP + (gy + 0.5) * CELL_H * (H - TOP) / H + (rnd() - 0.5) * 6
        out.append((x, y, 26 + ring * 7 + rnd() * 18))
    return out


def horizon(grid) -> str:
    """Silhouette path: per column, the lowest dark cell, then smoothed.

    The subject's bottom contour becomes the ridge the sky sits on.
    """
    lows = []
    for gx in range(GRID_W):
        rows = [
            gy for gy in range(GRID_H) if 255 - int(grid[gy, gx]) >= MIN_DARKNESS
        ]
        lows.append(max(rows) if rows else GRID_H)
    win = 7
    sm = []
    for i in range(GRID_W):
        seg = lows[max(0, i - win) : i + win + 1]
        sm.append(sum(seg) / len(seg))
    pts = []
    for gx, gy in enumerate(sm):
        y = TOP + (gy + 1.0) * CELL_H * (H - TOP) / H
        pts.append((gx * CELL_W, min(y, H - 2)))
    d = [f"M0 {H:.1f}", f"L0 {pts[0][1]:.1f}"]
    d += [f"L{x:.1f} {y:.1f}" for x, y in pts[1:]]
    d += [f"L{W} {H:.1f}", "Z"]
    return " ".join(d)


def build(static: bool) -> str:
    grid = read_grid()
    pts = stars(grid)
    nebs = clouds(grid)
    ridge = horizon(grid)
    rnd = _lcg(SEED + 11)
    css = [
        ".st{fill:" + STAR + "}.sf{fill:" + STAR_SOFT + "}",
        ".cap{fill:" + CAP + ";font:11px 'JetBrains Mono','Fira Mono',"
        "'SFMono-Regular',Menlo,Consolas,monospace}",
        ".hd{fill:" + HEAD + ";font:600 13px 'JetBrains Mono','Fira Mono',"
        "'SFMono-Regular',Menlo,Consolas,monospace}",
        "@keyframes tw{0%,100%{opacity:.25}50%{opacity:1}}",
        ".tw{animation:tw 3.2s ease-in-out infinite}",
        "@media (prefers-reduced-motion: reduce){.tw{animation:none;opacity:.9}}",
    ]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"'
        ' viewBox="0 0 %d %d" role="img"' % (W, H),
        ' aria-label="The same portrait rendered as a night sky: stars where the'
        ' subject is dark, nebulae where it is lit, and the silhouette as the'
        ' horizon">',
        '<defs>',
        '<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">',
        '<stop offset="0" stop-color="#05070f"/>',
        '<stop offset=".55" stop-color="#0b1226"/>',
        '<stop offset="1" stop-color="#1a2547"/>',
        '</linearGradient>',
        '<radialGradient id="nb" cx=".5" cy=".5" r=".5">',
        '<stop offset="0" stop-color="#8fb6ff" stop-opacity=".34"/>',
        '<stop offset=".55" stop-color="#6d8fd6" stop-opacity=".12"/>',
        '<stop offset="1" stop-color="#6d8fd6" stop-opacity="0"/>',
        '</radialGradient>',
        '<linearGradient id="gr" x1="0" y1="0" x2="0" y2="1">',
        '<stop offset="0" stop-color="#04060c"/>',
        '<stop offset="1" stop-color="#01020a"/>',
        '</linearGradient>',
        '</defs>',
        f'<rect width="{W}" height="{H}" fill="url(#sky)"/>',
        '<style>' + "".join(css) + '</style>',
        '<text class="hd" x="14" y="24">bakkarranna@github ~ $ nightfall</text>',
        '<text class="cap" x="14" y="42">the same portrait after dark --'
        ' dark detail becomes stars, lit detail becomes cloud, the shoulders'
        ' become the horizon</text>',
    ]
    for x, y, r in nebs:
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="url(#nb)"/>')
    out.append(f'<path d="{ridge}" fill="url(#gr)"/>')
    for i, (x, y, r) in enumerate(pts):
        tw = (not static) and (i % 11 == 0)
        style = f' style="animation-delay:{rnd() * 3.2:.2f}s"' if tw else ""
        out.append(
            f'<circle class="{"tw " if tw else ""}s{'f' if r > 1.5 else 't'}"'
            f'{style} cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}"/>'
        )
    out.append('</svg>')
    return "\n".join(out)


def main() -> None:
    static = os.environ.get("STATIC") == "1"
    if not SRC.exists():
        # CI has no portrait: keep the committed sky untouched and succeed.
        print(f"[sky] no {SRC.name} -- keeping existing art")
        return
    svg = build(static)
    dst = REPO / "night-sky.svg"
    dst.write_text(svg, encoding="utf-8")
    n = svg.count("<circle")
    print(f"[sky] wrote {dst} ({n} marks, {'static' if static else 'animated'})")


if __name__ == "__main__":
    main()
