"""Tile the traced Synaptix mark into the info card's logo tile.

data/synaptix-mark.json is the mark's silhouette in source pixels -- two
interlocking rings, each carrying the enclosed gaps it has to stay transparent
in. This module turns that asset into card-relative SVG paths without
re-deciding the mark: it scales and centres the rings inside
LOGO_TILE/LOGO_X/LOGO_Y, and nothing else. The synapse node negatives are
already part of the rings' gap set, so the glyph needs no extra dots.

Run standalone to eyeball the transform:
    python scripts/tile_mark.py        # prints the tiled path data + bbox
"""

from __future__ import annotations

import json

LOGO_TILE = 116.0
LOGO_X = 30.0
LOGO_Y = 30.0

MARK = "data/synaptix-mark.json"

# The mark's silhouette spans y 55.1..121.5 in the source render, i.e. it sits
# off-centre; fit() below centres it inside the square tile on the long axis.
GAP = 0.012          # ring stroke pad, as a fraction of tile width


def _rings(mark: dict) -> list[list[tuple[float, float]]]:
    return [list(ring["points"]) for ring in mark["rings"]]


def _bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def fit(mark: dict, pad: float = GAP) -> tuple[float, float, float, float]:
    """Uniform scale + translation mapping the mark into the tile."""
    pts = [p for ring in _rings(mark) for p in ring]
    min_x, min_y, max_x, max_y = _bbox(pts)
    span_x = max_x - min_x
    span_y = max_y - min_y
    avail = LOGO_TILE * (1 - 2 * pad)
    scale = avail / max(span_x, span_y)
    # Centre the *source* bbox in the tile (not just the span), so the mark's
    # own off-centre composition survives the move.
    off_x = LOGO_X + (LOGO_TILE - span_x * scale) / 2 - min_x * scale
    off_y = LOGO_Y + (LOGO_TILE - span_y * scale) / 2 - min_y * scale
    return scale, off_x, off_y, avail


def ring_path(scale: float, off_x: float, off_y: float,
              points: list[tuple[float, float]]) -> str:
    """Polyline path data for one ring, sampled at its own vertices."""
    d = []
    for i, (x, y) in enumerate(points):
        d.append(f"{'M' if i == 0 else 'L'}{x * scale + off_x:.1f},"
                 f"{y * scale + off_y:.1f}")
    d.append("Z")
    return "".join(d)


def arm_path(scale: float, off_x: float, off_y: float, ring: dict) -> str:
    """One arm as a single even-odd path: outer boundary followed by its holes.

    A fill-rule of even-odd makes every subpath after the first subtract from
    it, so the enclosed gaps stay transparent and the mark re-inks on whatever
    backdrop the card puts behind it. The alternative -- one path per subpath
    with opposite fills -- needs the backdrop colour to be known in advance,
    which defeats the point of tracing the mark in the first place.
    """
    parts = [ring_path(scale, off_x, off_y, ring["points"])]
    parts += [ring_path(scale, off_x, off_y, hole)
              for hole in ring.get("holes", []) if len(hole) >= 3]
    return "".join(parts)


def glyph(mark: dict) -> str:
    """The whole mark: two <path> arms, classes .mk0 and .mk1.

    Each arm is ONE path carrying its own holes as extra subpaths, filled
    even-odd, so the interlocking gaps are cut out of the arm rather than
    painted over it -- that is what keeps the two arms reading as two arms and
    leaves the synapse node transparent. The mark's own negatives are already
    in the ring gap set, so no extra dots are drawn on top.
    """
    scale, off_x, off_y, _ = fit(mark)
    return "".join(
        f'<path class="mk{i}" fill-rule="evenodd" '
        f'd="{arm_path(scale, off_x, off_y, ring)}"/>'
        for i, ring in enumerate(mark["rings"])
    )


def main() -> None:
    mark = json.loads(open(MARK, encoding="utf-8").read())
    scale, off_x, off_y, avail = fit(mark)
    pts = [p for ring in _rings(mark) for p in ring]
    min_x, min_y, max_x, max_y = _bbox(pts)
    t_min_x = min_x * scale + off_x
    t_min_y = min_y * scale + off_y
    t_max_x = max_x * scale + off_x
    t_max_y = max_y * scale + off_y
    print(f"scale={scale:.4f} off=({off_x:.1f},{off_y:.1f}) avail={avail:.1f}")
    print(f"tiled bbox x {t_min_x:.1f}..{t_max_x:.1f} y {t_min_y:.1f}..{t_max_y:.1f}")
    print(f"inset into tile: {t_min_x - LOGO_X:.1f}/{LOGO_X + LOGO_TILE - t_max_x:.1f}"
          f" and {t_min_y - LOGO_Y:.1f}/{LOGO_Y + LOGO_TILE - t_max_y:.1f}")
    rings = mark["rings"]
    print(f"path bytes: {len(arm_path(scale, off_x, off_y, rings[0]))} "
          f"(holes kept: {[len(r.get('holes', ())) for r in rings]})")


if __name__ == "__main__":
    main()
