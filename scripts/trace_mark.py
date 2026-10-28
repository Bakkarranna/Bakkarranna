"""Trace the Synaptix mark silhouette into data/synaptix-mark.json.

The source is a chrome 3D render, so the silhouette has to be recovered rather
than traced: the canvas is a flat light grey, the mark is two interlocking arms,
the renderer leaves white gloss inside the chrome, and a soft shadow hangs
below the mark. The trace:

  1. finds the two arm components (area and top-edge filters drop the shadow),
  2. keeps their OUTER contours as the asset's rings -- enclosed regions the
     renderer left backdrop-hued are not painted, so the artwork re-inks on
     whatever backdrop GitHub puts behind it,
  3. keeps each ring's INNER contours as its holes, so the arms stay two arms
     instead of collapsing into one solid blob.

Step 3 is what makes the mark read as interlocking rather than as a lump: the
silhouette alone fills every enclosed gap and the artwork loses the weave.
Both the holes and the gaps are part of the asset, so the fidelity reference is
the arm mask itself -- simplification is scored against what will actually be
drawn, not against a hole-free ideal.

Every enclosed non-ink region is kept, however small. The gaps *are* the
interlock: the four channels that make the two arms weave are 6-12px, and an
area floor that keeps only the 8 largest gaps throws the weave away and costs
1.6% of the ink. Only contours that cannot be a polygon at all (1- and 2-point
specks left by the renderer's antialiasing) are dropped, because filling them
would emit invalid path data -- and they enclose no ink, so dropping them
changes nothing.

Fidelity is scored with a 1px tolerance. The reference is a thresholded render
of thin chrome strokes, so every stroke edge carries an antialiased halo that
is ink by threshold and un-reachable by any polygon; an untoleranced IoU fails
on ~70 halo pixels instead of on simplification. A whole dropped gap, or a
collapsed corner, is tens of pixels wide and still fails the gate.

Usage:
    python scripts/trace_mark.py        # writes data/synaptix-mark.json
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SRC = REPO / "inspiration" / "rebranding-synaptix-studio.png"
OUT = REPO / "data" / "synaptix-mark.json"

CANVAS_LUM = 239.0     # measured grey of the render's backdrop
CANVAS_TOL = 25        # |lum - CANVAS_LUM| within this is backdrop
MIN_ARM_AREA = 1000    # specks below this are antialiasing, not design
MIN_ARM_TOP = 210      # the mark's arms sit above this; the shadow does not
MAX_POINTS = 260       # polygon budget per ring, so the asset stays small
MAX_HOLE_POINTS = 140  # coarser budget: holes are interior detail, not edges
TOL_PX = 1            # antialiasing halo at stroke edges, in px
MIN_FIDELITY = 0.999   # raster-vs-polygon agreement floor
MIN_HOLE_POINTS = 3    # a 1- or 2-point "gap" cannot be a polygon at all


def load_gray() -> np.ndarray:
    rgb = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float32)
    return rgb @ [0.299, 0.587, 0.114]


def arm_mask(gray: np.ndarray) -> np.ndarray:
    """Boolean raster of the mark: both arms, shadow band excluded."""
    canvas = (np.abs(gray - CANVAS_LUM) <= CANVAS_TOL).astype(np.uint8)
    ink = (1 - canvas).astype(np.uint8)
    count, labels, boxes, _ = cv2.connectedComponentsWithStats(ink, 8)
    arms = [i for i in range(1, count)
            if boxes[i][4] >= MIN_ARM_AREA and boxes[i][1] < MIN_ARM_TOP]
    if len(arms) != 2:
        raise SystemExit(f'expected 2 arms, found {arms}')
    return np.isin(labels, arms)


def _dist_to_ink(mask: np.ndarray) -> np.ndarray:
    """Distance in px from every pixel to the nearest ink pixel of `mask`."""
    return cv2.distanceTransform((~mask).astype(np.uint8), cv2.DIST_L2, 3)


def verify(reference: np.ndarray, raster: np.ndarray,
           tol: int = TOL_PX) -> float:
    """Agreement between the traced ink and the simplified polygons.

    With `tol` px of slack a pixel only counts as wrong when it is further
    than `tol` from the other mask's ink, so the antialiased halo around the
    reference's thin strokes is not scored against the asset. The result is
    an IoU-shaped number in [0, 1]: 1 means every pixel of the union is ink
    in both (or within `tol` of ink in both). `tol=0` is the plain strict
    IoU, kept so tests can prove the tolerance is not hiding a real miss.
    """
    union = int((reference | raster).sum())
    if not union:
        return 0.0
    if tol <= 0:
        return float((reference & raster).sum() / union)
    ref_d, got_d = _dist_to_ink(reference), _dist_to_ink(raster)
    # Ink the polygon has that the mark does not, and vice versa -- in both
    # cases only pixels further than `tol` px from the other side's ink.
    wrong = int((raster & (ref_d > tol)).sum())
    wrong += int((reference & (got_d > tol)).sum())
    return 1.0 - wrong / union


def _fill(poly: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """One polygon rasterised against the canvas, as uint8 0/1."""
    raster = np.zeros(shape, np.uint8)
    cv2.fillPoly(raster, [np.asarray(poly, np.int32)], 1)
    return raster


def ring_points(contour: np.ndarray,
                shape: tuple[int, int],
                budget: int = MAX_POINTS) -> tuple[list[tuple[int, int]], float]:
    """Simplified polygon for one contour plus the fidelity it kept.

    Bisects eps down to the smallest value whose candidate still fits the point
    budget -- i.e. the *finest* ring the budget allows, because fidelity falls
    monotonically as eps grows. Earlier versions walked a coarse eps grid (0..
    0.02 in 41 steps) and stopped at the first candidate under budget: the grid
    jumped straight past ~240 points to ~110, which is what capped fidelity at
    0.993. The bisection also documents the trade: at this perimeter, 0.999
    costs ~230 points per ring and 130 points costs ~0.994, so the budget is
    what decides the gate, not the sweep.
    """
    contour = np.asarray(contour, np.float32)
    peri = cv2.arcLength(contour, True)
    reference = _fill(contour, shape).astype(bool)
    lo, hi = 0.0, 0.05          # lo always over budget, hi always fits
    assert len(cv2.approxPolyDP(contour, hi * peri, True)) <= budget
    for _ in range(40):
        mid = (lo + hi) / 2
        if len(cv2.approxPolyDP(contour, mid * peri, True)) > budget:
            lo = mid
        else:
            hi = mid
    candidate = cv2.approxPolyDP(contour, hi * peri, True)
    fidelity = verify(reference, _fill(candidate, shape).astype(bool))
    pts = [(int(round(float(p[0][0]))), int(round(float(p[0][1]))))
           for p in candidate]
    return pts, fidelity


def trace() -> dict:
    """Rings of the mark: one outer contour per arm, plus each arm's holes.

    The arms are the ink, and every enclosed backdrop-hued region belongs to
    the design rather than to the backdrop. RETR_CCOMP hands that structure
    straight back: a contour with a negative parent is a ring's outer
    boundary, and a contour whose parent is that ring is a hole inside it.
    Filling only the outer boundaries paints the interlocking gaps solid,
    which is the exact bug this asset exists to remove -- the gaps are what
    make two arms read as two arms, and what leaves the synapse node
    negatives unpainted. So each ring keeps its own holes, and the fidelity
    reference becomes the traced ink mask itself: the simplified polygons,
    rendered with the holes cut out, have to reproduce that mask.
    """
    gray = load_gray()
    mask = arm_mask(gray)
    contours, hierarchy = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    parents = [int(h[3]) for h in hierarchy[0]]
    outer: list[tuple[int, np.ndarray]] = []
    for i, contour in enumerate(contours):
        if parents[i] < 0:
            outer.append((i, contour))
    if len(outer) != 2:
        raise SystemExit(f'expected 2 arm rings, found {len(outer)}')
    # CCOMP's own hole list is not enough: 965 of the 2351px it reports as holes
    # lie on ink, because several contours it calls holes straddle the arm
    # boundary -- cutting them out would remove real design ink. So define the
    # holes from the raster instead: enclosed non-ink inside the silhouette.
    # That is exactly what the SVG has to re-create, so it cannot disagree with
    # the reference the way a hierarchy walk can.
    solid = np.zeros(mask.shape, np.uint8)
    for _, contour in outer:
        solid |= _fill(contour, mask.shape)
    gaps = (solid.astype(bool) & ~mask).astype(np.uint8)
    gap_contours, _ = cv2.findContours(gaps, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_NONE)
    if not gap_contours:
        raise SystemExit('no enclosed gaps: the mark would render as a solid blob')
    # Every arm subtracts the same gap set. The gaps sit in the interlock
    # between the two arms, so a gap's centroid often falls in neither arm's
    # silhouette -- per-arm ownership silently eats real gaps and costs ~6%
    # fidelity. 1-point "gaps" are antialiasing specks: they cannot be a
    # polygon and the emitted SVG path data would be invalid.
    gaps = [g for g in gap_contours if len(g) >= MIN_HOLE_POINTS]
    if not gaps:
        raise SystemExit('every enclosed gap was a speck: the mark would '\
                         'render as a solid blob')
    print(f"gaps kept: {len(gaps)} of {len(gap_contours)} "
          f"(area {sum(cv2.contourArea(g) for g in gaps):.0f}px)")
    holes_by_parent = {i: gaps for i, _ in outer}

    rings = []
    fidelities = []
    for index, contour in outer:
        points, ring_fidelity = ring_points(contour, mask.shape)
        ring: dict = {"points": points, "holes": []}
        for hole in holes_by_parent.get(index, []):
            hole_points, _ = ring_points(hole, mask.shape, MAX_HOLE_POINTS)
            # Simplification can collapse a legal 3-point gap to a sliver that
            # is no polygon at all. Keeping it would emit "M x,y L x,y Z" --
            # path data no renderer accepts, and it encloses no ink anyway.
            if len(hole_points) >= MIN_HOLE_POINTS:
                ring["holes"].append(hole_points)
        rings.append(ring)
        fidelities.append(ring_fidelity)
    rings.sort(key=lambda r: -cv2.contourArea(np.array(r["points"])))

    # Render the asset the way the SVG will (outer minus holes, per ring) and
    # score it against the traced ink, so simplification is the only variable
    # the gate can fail on.
    raster = np.zeros(mask.shape, np.uint8)
    for ring in rings:
        ring_raster = _fill(np.array(ring["points"], np.int32), mask.shape)
        for hole in ring["holes"]:
            ring_raster &= ~_fill(np.array(hole, np.int32), mask.shape)
        raster |= ring_raster
    fidelity = verify(mask, raster.astype(bool))
    strict = verify(mask, raster.astype(bool), tol=0)
    print(f"rings={len(rings)} "
          f"points={[len(r['points']) for r in rings]} "
          f"holes={[len(r['holes']) for r in rings]} "
          f"hole points={[len(h) for r in rings for h in r['holes']]} "
          f"per-ring fidelity={[round(f, 4) for f in fidelities]} "
          f"fidelity={fidelity:.4f} (strict IoU {strict:.4f})")
    if fidelity < MIN_FIDELITY:
        raise SystemExit(f"mark simplified away too much ({fidelity:.4f})")
    xs = np.where(mask.any(axis=0))[0]
    ys = np.where(mask.any(axis=1))[0]
    return {
        "source": SRC.name,
        "viewBox": [int(xs.min()), int(ys.min()),
                    int(xs.max()) + 1, int(ys.max()) + 1],
        "rings": rings,
        "fidelity": round(fidelity, 4),
    }


def main() -> None:
    asset = trace()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(asset, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
