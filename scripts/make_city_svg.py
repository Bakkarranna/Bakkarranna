"""Generate contribution-city.svg -- an isometric city built from a year of days.

Every day of the trailing year is one lot on a 53x7 isometric plot. What gets
built on it depends on that day: the busiest day becomes a landmark skyscraper
with a crane and a rotating beacon, a heavy day an office or a tower with a
lit window grid, a lazy day a cafe with a striped awning and a neon sign or a
house with a pitched roof and a smoking chimney, and a day with no activity a
park, plaza, parked car or planter instead of a bare block -- so the grid still
reads as a calendar without reading as 328 empty boxes.

Heights still scale with that day's contribution count and colour still comes
from the same green ramp the heatmap uses, so the panel can never disagree
with the heatmap beside it. The left column carries the headline numbers, all
straight out of data/contributions.json.

Isometric projection used throughout (2:1 dimetric, no perspective math):
    sx = (gx - gy) * TW / 2
    sy = (gx + gy) * TH / 2
with gx = week index and gy = day-of-week, so weeks march away to the right
and the week's seven days stack towards the viewer.

Conventions shared with the other panels -- each one exists because an earlier
attempt broke behind GitHub's camo <img> proxy:
  * No <script>, no foreignObject, no external font or image. Camo strips
    scripts, so the interaction has to be what survives an <img> proxy: a
    native <title> tooltip per day, and a pure-CSS :hover wash, nothing more.
    Everything else about the life is ambient.
  * Animation is opacity + transform only. Animating geometry (clip-path,
    rect width) froze mid-print behind camo; those two never do.
  * Every element inks from a class, and every painting class carries a full
    prefers-color-scheme re-ink, so a theme flip never punches a hole.
  * Every animated element carries its own animation-delay, and every
    animation ends at opacity 1 so prefers-reduced-motion shows the finished
    city rather than a half-blinking one.

Run: python scripts/make_city_svg.py          # animated
     STATIC=1 python scripts/make_city_svg.py # frozen frame for previews
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data" / "contributions.json"
FONT = "'JetBrains Mono','Fira Mono','SFMono-Regular',Menlo,Consolas,monospace"

W, H = 860, 470
TW, TH = 14.0, 7.0         # iso tile footprint in viewBox units
FLOOR_Y = 252               # screen y of the grid origin (back-left corner)
ORIGIN_X = 430              # screen x of the grid origin
TOWER_MIN, TOWER_MAX = 8.0, 84.0
MARGIN = 28

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# level -> (top, left, right) face fills. Light theme first, dark re-inked
# below in theme_css(); right stays darkest so every block reads 3D.
LIGHT_RAMP = [
    ("#9be9a8", "#6fd08b", "#57bb74"),
    ("#6fdd8d", "#4fc472", "#3fae60"),
    ("#40c463", "#2fa14e", "#279143"),
    ("#30a14e", "#22803d", "#1c6e35"),
    ("#216e39", "#17542b", "#134724"),
]
DARK_RAMP = [
    ("#0e4429", "#0b3a22", "#09301b"),
    ("#006d32", "#005c2a", "#004d23"),
    ("#26a641", "#1d8a35", "#17752c"),
    ("#39d353", "#2bb344", "#249a3a"),
    ("#69f0a0", "#4fd18a", "#42bd7b"),
]

# Everything that is not a contribution-level face. Light value first, dark
# value beside it; theme_css() turns this table into ink classes, so a class
# added here is re-inked for free and one that is not listed here simply
# cannot be painted -- which is the point: no hard-coded hex ever reaches an
# element.
INK = {
    # ground / chrome (existing semantics, kept for the other panels' parity)
    "gnd": ("#f6f8fa", "#0d1117"),
    "tile": ("#eaeef2", "#21262d"),
    "trk": ("#eaeef2", "#21262d"),
    "rule": ("#d0d7de", "#30363d"),
    "fg": ("#1f2328", "#e6edf3"),
    "dim": ("#59636e", "#8b949e"),
    "win": ("#e3b341", "#f2cc0d"),
    # building
    "gls": ("#cfe6f7", "#1b2733"),        # unlit glass
    "rf": ("#8c6d4f", "#3d3226"),          # roof, lit face
    "rf2": ("#6f5540", "#2b241b"),         # roof, shaded face
    "aw1": ("#e5534b", "#d1584f"),         # awning stripe A
    "aw2": ("#f6f8fa", "#1b2027"),         # awning stripe B
    "neon": ("#39d353", "#56d364"),        # neon sign
    # props
    "lea": ("#3fb950", "#238636"),         # canopy
    "lea2": ("#2c974a", "#1a7f37"),        # canopy, shaded
    "wod": ("#8a6d3b", "#6b5330"),         # trunk / timber
    "met": ("#aeb6c0", "#6e7681"),         # metal, posts, cars
    "lmp": ("#e3b341", "#d29922"),         # lamp light
    "wat": ("#79c0ff", "#388bfd"),         # water
    "smk": ("#c9d1d9", "#8b949e"),         # smoke
    "cld": ("#eef2f6", "#1b2027"),         # cloud
    "brd": ("#59636e", "#8b949e"),         # bird
    "bcn": ("#f85149", "#ff7b72"),         # beacon
    "glow": ("#ffffff", "#79c0ff"),         # the hover wash over a day plot
}


def load() -> tuple[list[dict], dict]:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    return payload.get("days", []), payload.get("stats", {})


def level_of(count: int, peak: int) -> int:
    if count <= 0:
        return -1
    ratio = count / peak if peak else 0.0
    return min(4, int(ratio * 5))


def iso(gx: float, gy: float) -> tuple[float, float]:
    """Grid coords -> screen coords of the tile's front (viewer) corner."""
    return ORIGIN_X + (gx - gy) * TW / 2.0, FLOOR_Y + (gx + gy) * TH / 2.0


def flat_tile(x: float, y: float, w: float = TW, d: float = TH) -> str:
    """Diamond footprint of one lot -- keeps the calendar grid."""
    return (
        f"{x:.1f},{y - d:.1f} {x + w / 2:.1f},{y - d / 2:.1f} "
        f"{x:.1f},{y:.1f} {x - w / 2:.1f},{y - d / 2:.1f}"
    )


def prism(x: float, y: float, w: float, d: float, h: float) -> tuple[str, str, str]:
    """Top, left and right faces of a box whose base front corner is (x, y)."""
    top = (
        f"{x - w / 2:.1f},{y - d / 2 - h:.1f} "
        f"{x:.1f},{y - d - h:.1f} "
        f"{x + w / 2:.1f},{y - d / 2 - h:.1f} "
        f"{x:.1f},{y - h:.1f}"
    )
    left = (
        f"{x - w / 2:.1f},{y - d / 2 - h:.1f} "
        f"{x:.1f},{y - h:.1f} "
        f"{x:.1f},{y:.1f} "
        f"{x - w / 2:.1f},{y - d / 2:.1f}"
    )
    right = (
        f"{x + w / 2:.1f},{y - d / 2 - h:.1f} "
        f"{x:.1f},{y - h:.1f} "
        f"{x:.1f},{y:.1f} "
        f"{x + w / 2:.1f},{y - d / 2:.1f}"
    )
    return top, left, right


def hip_roof(x: float, y: float, w: float, d: float, h: float,
             r: float) -> list[str]:
    """A four-faced roof of height r on top of walls of height h."""
    bl = f"{x - w / 2:.1f},{y - d / 2 - h:.1f}"
    br = f"{x + w / 2:.1f},{y - d / 2 - h:.1f}"
    bc = f"{x:.1f},{y - h:.1f}"
    bk = f"{x:.1f},{y - d - h:.1f}"
    tl = f"{x - w / 2:.1f},{y - d / 2 - h - r:.1f}"
    tr = f"{x + w / 2:.1f},{y - d / 2 - h - r:.1f}"
    tc = f"{x:.1f},{y - h - r:.1f}"
    tk = f"{x:.1f},{y - d - h - r:.1f}"
    return [
        f"M{tk} {tr} {tl}Z",                       # back slope (rarely seen)
        f"M{tl} {tc} {bc} {bl}Z",                   # left slope
        f"M{tr} {tc} {bc} {br}Z",                   # right slope
        f"M{tk} {tr} {tc} {tl}Z",                   # ridge
    ]


def height_of(count: int, peak: int) -> float:
    if count <= 0:
        return 0.0
    ratio = count / peak if peak else 0.0
    return TOWER_MIN + ratio * (TOWER_MAX - TOWER_MIN)


STROKE_CLASSES = {"rule"}

# One row per ambient loop: (class, animation, duration, delay, frozen opacity).
#
# The fifth field is what prefers-reduced-motion must land that class on, and
# it has to match the terminal stop of that animation's keyframes: an element
# caught mid-cycle has to be stopped on the frame its animation would have
# ended on. Getting it wrong shows a cigarette smoke frozen solid over a
# chimney, or a plane parked in mid-air, which is exactly the tell that motion
# was never thought through.
#
# Every element carrying one of these also carries its own animation-delay, so
# the loops drift out of step and the city never blinks in unison.
LOOPS = [
    ("win", "blink", "1.9s", ".35", "1"),
    ("neon", "flick", "2.6s", ".2", "1"),
    ("smk", "puff", "3.4s", "0", "0"),
    ("bcn", "spin", "1.7s", ".8", ".25"),
    ("cld", "drift", "26s", "0", "1"),
    ("brd", "bob", "1.4s", ".3", "1"),
    ("fly", "fly", "9s", "1.2", "0"),
]

# Animations that are not ambient loops: (class, animation, frozen opacity).
# The pulse on the NOW marker and the panel's own entrance. Both end at opacity
# 1, so both freeze at 1 -- the entrance is the one animation reduced motion
# keeps, because without it the panel would start invisible rather than still.
ENTRANCE = [
    ("now", "pulse", "1"),
    ("tw", "rise", "1"),
    ("tile", "rise", "1"),
]


def reduced_motion_css(static: bool) -> str:
    """Freeze every animated class on the frame its keyframes would end on.

    One flat rule per class, no comma lists and no nested blocks: a class that
    gets its own rule can never be wrongly caught by a selector that was
    written for a neighbour. `@keyframes rise` is defined at top level in
    theme_css(), so the entrance it refers to here is already in scope.
    """
    if static:
        return ""
    rules: list[str] = []
    for cls, _anim, frozen in ENTRANCE:
        if cls in ("tw", "tile"):
            # the entrance survives, it just has to reach its end frame
            rules.append(f".{cls}{{opacity:1;animation:rise .5s ease forwards}}")
        else:
            rules.append(f".{cls}{{animation:none;opacity:{frozen};transform:none}}")
    for cls, _anim, _dur, _delay, frozen in LOOPS:
        rules.append(f".{cls}{{animation:none;opacity:{frozen};transform:none}}")
    return (
        "@media (prefers-reduced-motion: reduce){" + "".join(rules) + "}"
        # smoke is invisible in the dark theme while frozen, as it is at rest
        + "@media (prefers-reduced-motion: reduce) and (prefers-color-scheme: dark)"
        + "{.smk{opacity:0}}"
    )


def language_stack() -> list[tuple[str, int]]:
    """Language mix as percentages, read from the single authored source."""
    sys.path.insert(0, str(HERE))
    import make_skills_svg as gen

    for name, skills in gen.GROUPS:
        if name == "languages":
            return [(s, level * 20) for s, level in skills]
    return []


def theme_css(static: bool) -> str:
    """Panel CSS: ink by class, dark re-ink, opacity+transform animation only.

    The light and dark halves are generated from one table, so a class can
    never be painted on one theme and forgotten on the other.
    """
    light: list[str] = []
    dark: list[str] = []
    for cls, (lo, dk) in INK.items():
        prop = "stroke" if cls in STROKE_CLASSES else "fill"
        light.append(f".{cls}{{{prop}:{lo}}}")
        dark.append(f".{cls}{{{prop}:{dk}}}")
    for i, (top, left, right) in enumerate(LIGHT_RAMP):
        light.append(f".t{i}{{fill:{top}}}.l{i}{{fill:{left}}}.r{i}{{fill:{right}}}")
    for i, (top, left, right) in enumerate(DARK_RAMP):
        dark.append(f".t{i}{{fill:{top}}}.l{i}{{fill:{left}}}.r{i}{{fill:{right}}}")

    body = "".join(light)
    if not static:
        body += (
            ".tw,.tile{opacity:0}"
            "@keyframes rise{from{opacity:0;transform:translateY(8px)}"
            "to{opacity:1;transform:translateY(0)}}"
            ".tw,.tile{animation:rise .5s ease forwards}"
            "@keyframes pulse{0%,100%{opacity:1}50%{opacity:.2}}"
            ".now{animation:pulse 1.6s ease-in-out infinite}"
            # windows breathe out of step, so a lit facade reads as a lived-in
            # one instead of a circuit board switching on and off
            "@keyframes blink{0%,100%{opacity:1}50%{opacity:.35}}"
            ".win{animation:blink 1.9s ease-in-out infinite}"
            # a cafe sign with a tired tube
            "@keyframes flick{0%,100%{opacity:1}44%{opacity:.35}"
            "46%{opacity:1}48%{opacity:.15}50%{opacity:1}}"
            ".neon{animation:flick 2.6s steps(1,end) infinite}"
            # chimney smoke: rises, thins out, comes back
            "@keyframes puff{0%{opacity:0;transform:translateY(2px)}"
            "25%{opacity:.5}100%{opacity:0;transform:translateY(-6px)}}"
            ".smk{animation:puff 3.4s linear infinite}"
            "@keyframes spin{0%,100%{opacity:.25}50%{opacity:1}}"
            ".bcn{animation:spin 1.7s ease-in-out infinite}"
            # the sky moves, the city does not
            "@keyframes drift{0%{transform:translateX(-9px)}"
            "100%{transform:translateX(9px)}}"
            ".cld{animation:drift 26s ease-in-out infinite alternate}"
            "@keyframes bob{0%,100%{opacity:1;transform:translateY(0)}"
            "50%{opacity:1;transform:translateY(-1.6px)}}"
            ".brd{animation:bob 1.4s ease-in-out infinite}"
            "@keyframes fly{0%{opacity:0;transform:translateX(26px)}"
            "12%{opacity:1}88%{opacity:1}"
            "100%{opacity:0;transform:translateX(-26px)}}"
            ".fly{animation:fly 9s linear infinite}"
        )
    body += (
        # the one interaction camo lets through: a hover wash over the day
        # plot. fill-opacity rides as an inline attribute, so the invisible
        # resting frame is written on the element itself and the wash can
        # never be caught mid-open by a theme rule; opacity alone is animated,
        # never geometry, so the freeze rules stay untouched by it.
        ".glow{pointer-events:none}"
        ".tw:hover .glow,.tile:hover .glow{fill-opacity:.34}"
    )
    body += "@media (prefers-color-scheme: dark){" + "".join(dark) + "}"
    # The freeze rule lives in reduced_motion_css(), one row per loop, so a new
    # animation added to LOOPS cannot be forgotten there.
    body += reduced_motion_css(static)
    return body



# ---------------------------------------------------------------------------
# PART 3 -- the drawing layer. Rewritten from the head generator, which drew
# one flat box per day: colours and heights carried every signal, so a slow
# Sunday and a quiet Tuesday were the same bare block. This builds something
# instead -- a skyscraper on the best day, glass offices for the busy days, a
# cafe or a house for the quiet ones -- so the skyline reads as a year of
# different days, and the empty lots become parks, ponds and parked cars so
# the 53x7 plot still reads as a calendar rather than 328 vacant lots.
#
# What is carried over from head, unchanged, so the panel can still never
# disagree with the heatmap beside it:
#   * heights scale with that day's contribution count (height_of / peak);
#   * colour comes from the same green ramp, by level_of(count, peak);
#   * only opacity + transform animate, and every class re-inks for dark.
# ---------------------------------------------------------------------------

# Three grade bands, split out of the contribution levels 0-4 so a level is a
# *kind* of building rather than a colour index. peak 27 gives, roughly:
#   quiet   : count <= peak / 5   -> cottages and houses
#   steady  : peak / 5 < count <= 3 * peak / 5 -> cafes and tall houses
#   big     : the rest            -> glass office towers
# The best day of the year is special-cased into a landmark.
QUIET_R, STEADY_R = 0.2, 0.6


def band_of(count: int, peak: int) -> str:
    r = count / peak if peak else 0.0
    if r <= QUIET_R:
        return "quiet"
    if r <= STEADY_R:
        return "steady"
    return "big"


def _delay(base: float, seed: int = 0, step: int = 7) -> float:
    """An animation-delay, jittered by a stable seed.

    The commit ramp below uses one row per element, so the sweep in
    verify_svg.py that catches undelayed animation stops finding bare spots.
    The jitter is what keeps the loops from blinking in unison -- it is
    rounded to two places so the printed value always matches the float the
    sweep reads back.
    """
    return round(base + (seed % step) * 0.035, 2)


def _stagger(days: list[dict]) -> dict[int, float]:
    """A delay per day, ordered back to front in the plot.

    Delays are folded out over the whole diagonal arete, grouped by depth so
    a tile emerging behind a tower emerges before it and the grid never pops
    in walls-first. Independent clamps on the delay and the sweep keep the
    last frame arriving in ~0.9s, comfortably inside the reader's patience.
    """
    depths = sorted({d.get("week", 0) + d.get("weekday", 0) for d in days})
    if not depths:
        return {}
    slowest = max(1, min(28, len(days) // 14))
    ramp: dict[int, float] = {}
    prev = 0.0
    for i, dep in enumerate(depths):
        ramp[dep] = round(0.04 + i * 0.024 if i < slowest else prev + 0.024, 2)
        prev = ramp[dep]
    return ramp


def _ambient() -> list[str]:
    """Clouds, birds and a plane: the sky layer, behind the city.

    Ambient life, per the docstring -- the panel never animates geometry, so
    this is the whole of the motion the camo proxy lets through.
    """
    out: list[str] = []
    clouds = [
        (128, 74, 1.0, 0), (292, 60, 0.78, 3), (556, 70, 0.9, 6),
        (742, 92, 0.7, 2), (452, 52, 0.82, 5),
    ]
    for cx, cy, k, seed in clouds:
        dl = _delay(0.0, seed)
        out.append(
            f'<g class="cld" style="animation-delay:{dl}s">'
            f'<path d="M{cx - 22 * k:.1f},{cy} a{9 * k:.1f},{9 * k:.1f} 0 0 1 '
            f'{2 * k:.1f},{-9 * k:.1f} a{11 * k:.1f},{11 * k:.1f} 0 0 1 '
            f'{21 * k:.1f},{-2 * k:.1f} h{20 * k:.1f} a{8 * k:.1f},'
            f'{8 * k:.1f} 0 0 1 {6 * k:.1f},{9 * k:.1f}Z"/></g>'
        )
    for bx, by, seed in ((200, 108, 1), (246, 96, 4), (614, 118, 7)):
        dl = _delay(0.3, seed)
        out.append(
            f'<g class="brd" style="animation-delay:{dl}s">'
            f'<path d="M{bx},{by} q3,-4 6,0 q3,-4 6,0"/></g>'
        )
    out.append(
        f'<g class="fly" style="animation-delay:{_delay(1.2, 2)}s">'
        '<path d="M796,66 l-9,3 9,3 1,-3Z"/></g>'
    )
    return out


def _dia(cx: float, cy: float, rx: float, ry: float,
         cls: str, delay: float = 0.0) -> str:
    dl = f' style="animation-delay:{delay}s"' if delay else ""
    return (
        f'<path class="{cls}"{dl} d="M{cx:.1f},{cy - ry:.1f} '
        f'{cx + rx:.1f},{cy:.1f} {cx:.1f},{cy + ry:.1f} '
        f'{cx - rx:.1f},{cy:.1f}Z"/>'
    )


def _lot_props(gx: int, gy: int, x: float, y: float, idx: int,
               out: list[str]) -> None:
    """Paint something on an empty lot instead of leaving a bare diamond.

    A deterministic third of the quiet lots get a park, a pond, planter,
    street lamp or parked car -- enough life that the calendar grid stays
    legible without turning into a field of props. None of this animates, so
    nothing here needs a delay of its own.
    """
    pick = idx % 5
    if pick == 4:
        return  # a genuinely empty lot; the diamond itself carries the day
    if pick == 0:                                   # a tree over a small lawn
        out.append(_dia(x, y - 2.4, 6.0, 3.0, "lea"))
        out.append(f'<path class="wod" d="M{x - 0.7:.1f},{y - 1:.1f} '
                   f'{x + 0.7:.1f},{y - 1:.1f} {x + 0.7:.1f},{y + 1.2:.1f} '
                   f'{x - 0.7:.1f},{y + 1.2:.1f}Z"/>')
    elif pick == 1:                                 # a park pond
        out.append(_dia(x, y - 1.2, 5.2, 2.6, "wat"))
    elif pick == 2:                                 # a planter box
        out.append(f'<path class="wod" d="M{x - 4:.1f},{y - 3:.1f} '
                   f'{x + 4:.1f},{y - 3:.1f} {x + 3.4:.1f},{y - 1.6:.1f} '
                   f'{x - 3.4:.1f},{y - 1.6:.1f}Z"/>')
        out.append(_dia(x, y - 4.4, 3.2, 1.6, "lea"))
    else:                                           # a parked car
        out.append(f'<path class="met" d="M{x - 4:.1f},{y - 2.2:.1f} '
                   f'{x + 4:.1f},{y - 2.2:.1f} {x + 4:.1f},{y + 0.4:.1f} '
                   f'{x - 4:.1f},{y + 0.4:.1f}Z"/>')
        out.append(f'<path class="gls" d="M{x - 2.4:.1f},{y - 3.4:.1f} '
                   f'{x + 1.6:.1f},{y - 3.4:.1f} {x + 2.2:.1f},{y - 2.2:.1f} '
                   f'{x - 2.4:.1f},{y - 2.2:.1f}Z"/>')
        out.append(_dia(x, y + 2.6, 1.6, 0.8, "lmp"))

def _win(x: float, y: float, r: float, c: float, rows: int,
         i: int, delay: float) -> str:
    """One lit window as two parallelograms on a tower face.

    Faces are drawn back to front (right then left) so a window on the near
    face always lands on top of the one behind it, exactly like the walls.
    """
    pts: list[str] = []
    for face in (1, -1):
        u = (c + 0.5) / 2.4
        v = (r + 0.6) / (rows + 0.4)
        span = TW * 0.30
        gap = TH * 0.22
        if face < 0:
            px = (x - TW / 2) + u * TW
        else:
            px = (x + TW / 2) - u * TW
        tilt = (0.5 - u) * TH
        cy = (y - TH / 2 - hh) + u * TH + v * hh + tilt
        pts.append(
            f"{px - 1.0:.1f},{cy - gap:.1f} {px + 1.0:.1f},{cy - gap:.1f} "
            f"{px + 1.0:.1f},{cy + gap:.1f} {px - 1.0:.1f},{cy + gap:.1f}"
        )
    return "".join(
        f'<path class="win" style="animation-delay:{delay}s" d="M{p}Z"/>'
        for p in pts
    )


def _facade_windows(x: float, y: float, h: float, gx: int,
                    gy: int) -> list[str]:
    """A lit window grid down the two visible faces of a tall tower."""
    if h < 26:
        return []
    rows = min(5, max(2, int(h // 16)))
    out: list[str] = []
    i = 0
    for r in range(rows):
        for c in (0, 1):
            i += 1
            dl = _delay(0.35, gx * 7 + gy + i)
            u = (c + 0.5) / 2.4
            v = (r + 0.6) / (rows + 0.4)
            gap = TH * 0.20
            for face in (1, -1):
                if face < 0:
                    px = (x - TW / 2) + u * TW
                else:
                    px = (x + TW / 2) - u * TW
                tilt = (0.5 - u) * TH
                top = (y - TH / 2 - h) + u * TH + v * h + tilt
                bot = (y - TH / 2 - h) + u * TH + ((r + 1.4) / (rows + 0.4)) * h + tilt
                out.append(
                    f'<path class="win" style="animation-delay:{dl}s" '
                    f'd="M{px - 1.1:.1f},{top:.1f} {px + 1.1:.1f},{top:.1f} '
                    f'{px + 1.1:.1f},{bot:.1f} {px - 1.1:.1f},{bot:.1f}Z"/>'
                )
    return out


def _office(x: float, y: float, h: float, lvl: int, gx: int,
            gy: int, out: list[str]) -> None:
    """A glass tower: unlit panes with a lit window grid over them."""
    top, left, right = prism(x, y, TW, TH, h)
    out.append(f'<path class="gls" d="M{right}Z"/>')
    out.append(f'<path class="gls" d="M{left}Z"/>')
    out.extend(_facade_windows(x, y, h, gx, gy))
    out.append(f'<path class="t{lvl}" d="M{top}Z"/>')
    out.append(
        f'<path class="l{lvl}" d="M{x - TW / 2:.1f},{y - TH / 2:.1f} '
        f'{x:.1f},{y:.1f} {x:.1f},{y - 0.6:.1f} {x - TW / 2:.1f},'
        f'{y - TH / 2 - 0.6:.1f}Z"/>'
    )


def _house(x: float, y: float, h: float, lvl: int, gx: int, gy: int,
           smoke: bool, out: list[str]) -> None:
    """A house with a pitched roof, and a chimney when someone is home."""
    top, left, right = prism(x, y, TW, TH, h)
    out.append(f'<path class="r{lvl}" d="M{right}Z"/>')
    out.append(f'<path class="l{lvl}" d="M{left}Z"/>')
    out.append(f'<path class="t{lvl}" d="M{top}Z"/>')
    # two lit windows and a door on the front (nearer) face
    wi = 0
    for u, cls in ((0.3, "win"), (0.7, "win")):
        wi += 1
        wd = _delay(0.35, gx * 7 + gy + wi)
        px = (x + TW / 2) - u * TW
        cy = (y - TH / 2 - h) + u * TH + h * 0.45
        out.append(
            f'<path class="{cls}" style="animation-delay:{wd}s" '
            f'd="M{px - 1.0:.1f},{cy - 1.0:.1f} '
            f'{px + 1.0:.1f},{cy - 1.0:.1f} {px + 1.0:.1f},{cy + 1.0:.1f} '
            f'{px - 1.0:.1f},{cy + 1.0:.1f}Z"/>'
        )
    out.append(
        f'<path class="rf2" d="M{x:.1f},{y - TH / 2 - h:.1f} '
        f'{x + 1.3:.1f},{y - h - 0.6:.1f} {x + 1.3:.1f},{y - 0.6:.1f} '
        f'{x:.1f},{y:.1f}Z"/>'
    )
    roof = hip_roof(x, y, TW, TH, h, 5.0)
    out.append(f'<path class="rf" d="{roof[2]}"/>')
    out.append(f'<path class="rf2" d="{roof[1]}"/>')
    out.append(f'<path class="rf" d="{roof[3]}"/>')
    if smoke:
        cx = x - TW * 0.22
        base = y - TH / 2 - h - 5.0
        dl = _delay(0.0, gx * 7 + gy, 6)
        out.append(
            f'<path class="wod" d="M{cx - 0.8:.1f},{base:.1f} '
            f'{cx + 0.8:.1f},{base:.1f} {cx + 0.8:.1f},{base - 3.2:.1f} '
            f'{cx - 0.8:.1f},{base - 3.2:.1f}Z"/>'
        )
        for k in range(3):
            up = base - 3.2 - k * 2.4
            out.append(
                f'<path class="smk" style="animation-delay:{_delay(0.0, gx * 7 + gy + k, 6)}s" '
                f'd="M{cx - 1.6 + k * 0.5:.1f},{up:.1f} '
                f'{cx + 1.6 - k * 0.5:.1f},{up:.1f} '
                f'{cx:.1f},{up - 2.6:.1f}Z"/>'
            )


def _cafe(x: float, y: float, h: float, lvl: int, gx: int, gy: int,
          out: list[str]) -> None:
    """A cafe: a block, a striped awning over the door, and a neon sign."""
    top, left, right = prism(x, y, TW, TH, h)
    out.append(f'<path class="r{lvl}" d="M{right}Z"/>')
    out.append(f'<path class="l{lvl}" d="M{left}Z"/>')
    out.append(f'<path class="t{lvl}" d="M{top}Z"/>')
    # a wide lit window band across the front face
    bwd = _delay(0.35, gx * 7 + gy + 9)
    out.append(
        f'<path class="win" style="animation-delay:{bwd}s" '
        f'd="M{x - 4.6:.1f},{y - TH / 2 - h + 3:.1f} '
        f'{x + 4.6:.1f},{y - TH / 2 - h + 3:.1f} {x + 4.6:.1f},'
        f'{y - TH / 2 - h + 8:.1f} {x - 4.6:.1f},{y - TH / 2 - h + 8:.1f}Z"/>'
    )
    awy = y - TH / 2 - h + 1.4
    for i in range(4):
        ax = x - 4.4 + i * 2.2
        cls = "aw1" if i % 2 == 0 else "aw2"
        out.append(
            f'<path class="{cls}" d="M{ax:.1f},{awy:.1f} '
            f'{ax + 2.2:.1f},{awy:.1f} {ax + 2.2 - 1.1:.1f},{awy + 2.4:.1f} '
            f'{ax - 1.1:.1f},{awy + 2.4:.1f}Z"/>'
        )
    dl = _delay(0.2, gx * 7 + gy, 6)
    out.append(
        f'<path class="neon" style="animation-delay:{dl}s" '
        f'd="M{x - 1.1:.1f},{y - TH - h - 1:.1f} {x + 1.1:.1f},'
        f'{y - TH - h - 1:.1f} {x + 1.1:.1f},{y - TH - h + 2.6:.1f} '
        f'{x - 1.1:.1f},{y - TH - h + 2.6:.1f}Z"/>'
    )


def _landmark(x: float, y: float, gx: int, gy: int,
              out: list[str]) -> None:
    """The best day of the year: the tallest tower, a crane and a beacon."""
    h = height_of(peak_count, peak_count)
    top, left, right = prism(x, y, TW * 0.82, TH, h)
    out.append(f'<path class="gls" d="M{right}Z"/>')
    out.append(f'<path class="gls" d="M{left}Z"/>')
    out.extend(_facade_windows(x, y, h, gx, gy))
    out.append(f'<path class="t4" d="M{top}Z"/>')
    # a mast with a rotating beacon
    mx = x + 0.6
    base = y - TH - h
    out.append(f'<path class="met" d="M{mx - 0.5:.1f},{base:.1f} '
               f'{mx + 0.5:.1f},{base:.1f} {mx + 0.5:.1f},{base - 16:.1f} '
               f'{mx - 0.5:.1f},{base - 16:.1f}Z"/>')
    out.append(
        f'<path class="bcn" style="animation-delay:{_delay(0.8, gx)}s" '
        f'd="M{mx:.1f},{base - 19:.1f} {mx + 2.4:.1f},{base - 17.4:.1f} '
        f'{mx:.1f},{base - 15.8:.1f} {mx - 2.4:.1f},{base - 17.4:.1f}Z"/>'
    )
    # a crane on the roof
    cx, cy = x - TW * 0.2, base
    out.append(f'<path class="met" d="M{cx:.1f},{cy:.1f} {cx:.1f},{cy - 20:.1f} '
               f'{cx + 13:.1f},{cy - 15:.1f} {cx + 13:.1f},{cy - 12.6:.1f} '
               f'{cx:.1f},{cy - 17:.1f}Z"/>')
    out.append(f'<path class="met" d="M{cx - 0.6:.1f},{cy:.1f} '
               f'{cx + 0.6:.1f},{cy:.1f} {cx + 0.6:.1f},{cy - 20:.1f} '
               f'{cx - 0.6:.1f},{cy - 20:.1f}Z"/>')
    out.append(f'<path class="met" d="M{cx + 8:.1f},{cy - 15:.1f} '
               f'{cx + 8:.1f},{cy - 9:.1f}" stroke-width="0.7"/>')

def _day_title(count: int, day: dict) -> str:
    """The tooltip a hovered day answers with, as its first child.

    A native <title> is the only text a reader gets from a hover inside an
    <img>-embedded SVG: scripts are stripped behind camo, CSS cannot move a
    label onto a hovered element, and a foreignObject tooltip is out too.
    The phrasing is the heatmap's, so the two panels answer identically.
    """
    date = escape(str(day.get("date", "-")))
    return f"<title>{count} contributions on {date}</title>"


def city(out: list[str], days: list[dict], stats: dict, static: bool) -> None:
    """Paint the isometric plot back to front (painter's algorithm on gx+gy)."""
    global peak_count
    peak_count = max((d.get("count", 0) for d in days), default=0)

    weeks = max((d.get("week", 0) for d in days), default=0) + 1
    corners = [iso(0, 0), iso(weeks - 1, 0), iso(weeks - 1, 6), iso(0, 6)]
    pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in corners)
    out.append(f'<path class="gnd" d="M{pts}Z"/>')

    ramp = _stagger(days)
    for i, d in enumerate(days):
        gx = d.get("week", 0)
        gy = d.get("weekday", 0)
        count = d.get("count", 0)
        delay = ramp.get(gx + gy, 0.04)
        x, y = iso(gx, gy)
        if count <= 0:
            body: list[str] = [f'<path d="M{flat_tile(x, y)}Z"/>']
            _lot_props(gx, gy, x, y, i, body)
            # the wash rides last, so it covers the whole day plot, and it
            # rests invisible: fill-opacity 0 is on the element, not in a
            # stylesheet, so reduced motion can never catch it mid-open.
            body.append(
                f'<path class="glow" fill-opacity="0" d="M{flat_tile(x, y)}Z"/>'
            )
            if static:
                style = ""
            else:
                style = f' style="animation-delay:{delay}s"'
            out.append(
                f'<g class="tile"{style}>' + _day_title(count, d) + "".join(body) + "</g>"
            )
            continue
        lvl = level_of(count, peak_count)
        h = height_of(count, peak_count)
        face: list[str] = []
        if count == peak_count:
            _landmark(x, y, gx, gy, face)
        elif band_of(count, peak_count) == "big":
            _office(x, y, h, lvl, gx, gy, face)
        elif band_of(count, peak_count) == "steady":
            _cafe(x, y, h, lvl, gx, gy, face)
        else:
            _house(x, y, h, lvl, gx, gy, (gx + gy) % 5 == 0, face)
        # same wash over the building, so hover answers on towers and lots alike
        face.append(
            f'<path class="glow" fill-opacity="0" d="M{flat_tile(x, y)}Z"/>'
        )
        if static:
            style = ""
        else:
            style = f' style="animation-delay:{delay}s"'
        out.append(
            f'<g class="tw"{style}>' + _day_title(count, d) + "".join(face) + "</g>"
        )

    out.extend(_ambient())

    # "today" pin over the newest day, sequenced one step past its own ramp
    last = days[-1] if days else None
    if last is not None:
        x, y = iso(last.get("week", 0), last.get("weekday", 0))
        h = height_of(last.get("count", 0), peak_count)
        cy = y - TH - h - 9
        base = 0.04 + (len({d.get("week", 0) + d.get("weekday", 0) for d in days})) * 0.024
        if static:
            style = f' class="now"'
        else:
            style = f' class="now" style="animation-delay:{round(base + 0.024, 2)}s"'
        out.append(
            f'<g{style}><path d="M{x:.1f},{cy - 4} {x + 2.6:.1f},{cy:.1f} '
            f"{x:.1f},{cy + 4} {x - 2.6:.1f},{cy:.1f}Z\"/></g>"
        )


def header(out: list[str], days: list[dict]) -> None:
    out.append(
        f'<text x="{MARGIN}" y="26" font-size="13" font-weight="bold" '
        'class="fg">the city i built this year</text>'
    )
    n = len(days)
    out.append(
        f'<text x="{MARGIN}" y="42" font-size="10" class="dim">'
        f"{n} days as buildings &#183; height = that day's contributions "
        "&#183; hover for the date and count</text>"
    )
    out.append(
        f'<line class="rule" x1="{MARGIN}" y1="52" x2="352" y2="52" '
        'stroke-width="1"/>'
    )


def left_column(out: list[str], days: list[dict], stats: dict) -> None:
    best = stats.get("best_day", {}) or {}
    blocks = [
        ("contributions", str(stats.get("total_last_year", 0)), "last 12 months"),
        ("active days", str(stats.get("active_days", 0)),
         f"of {len(days)} days"),
        ("busiest day", str(best.get("count", 0)), best.get("date", "-")),
        ("longest streak", str(stats.get("longest_streak", 0)), "days"),
    ]
    for i, (label, value, sub) in enumerate(blocks):
        yb = 72 + i * 44
        out.append(
            f'<text x="{MARGIN}" y="{yb}" font-size="10" class="dim">{label}</text>'
        )
        out.append(
            f'<text x="{MARGIN}" y="{yb + 20}" font-size="20" '
            f'font-weight="bold" class="fg">{value}</text>'
        )
        out.append(
            f'<text x="{MARGIN + 96}" y="{yb + 14}" font-size="10" '
            f'class="dim">{sub}</text>'
        )

    out.append(
        f'<text x="{MARGIN}" y="252" font-size="10" font-weight="bold" '
        'class="fg">language stack</text>'
    )
    out.append(
        f'<line class="rule" x1="{MARGIN}" y1="258" x2="352" y2="258" '
        'stroke-width="1"/>'
    )
    for i, (name, pct) in enumerate(language_stack()):
        ry = 278 + i * 21
        fill = level_of(pct, 100)
        out.append(
            f'<text x="{MARGIN}" y="{ry}" font-size="10" class="fg">'
            f"{escape(name)}</text>"
        )
        out.append(
            f'<rect class="trk" x="104" y="{ry - 6}" width="206" '
            'height="5" rx="2.5"/>'
        )
        out.append(
            f'<rect class="t{fill}" x="104" y="{ry - 6}" '
            f'width="{206 * pct / 100:.1f}" height="5" rx="2.5"/>'
        )
        out.append(
            f'<text x="352" y="{ry}" font-size="10" class="dim" text-anchor="end">{pct}%</text>'
        )

    out.append(
        f'<text x="{MARGIN}" y="410" font-size="10" class="dim">less</text>'
    )
    for i in range(5):
        cx, cy = 62 + i * 16, 413
        out.append(
            f'<path class="t{i}" d="M{cx},{cy - 2.5} {cx + 5},{cy} '
            f"{cx},{cy + 2.5} {cx - 5},{cy}Z\"/>"
        )
    out.append(
        f'<text x="{62 + 5 * 16 + 6}" y="410" font-size="10" class="dim">more</text>'
    )
    out.append(
        f'<text x="{MARGIN}" y="442" font-size="10" class="dim">'
        "one tower per day &#183; height = that day's contributions</text>"
    )


def statistic_chip(out: list[str]) -> None:
    out.append(
        '<rect x="676" y="16" width="164" height="24" rx="6" class="gnd"/>'
    )
    out.append('<path class="t4" d="M700,31 706,27 712,31 706,35Z"/>')
    out.append(
        f'<text x="722" y="32" font-size="10" class="dim">'
        "3D contribution viz</text>"
    )


def build(static: bool) -> str:
    days, stats = load()
    out: list[str] = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="{FONT}">'
    )
    out.append(f"<style>{theme_css(static)}</style>")
    if static:
        out.append("<style>.tw,.tile{opacity:1;transform:none}</style>")
    out.append(f"<title>bakkarranna's contribution city</title>")
    header(out, days)
    left_column(out, days, stats)
    statistic_chip(out)
    city(out, days, stats, static)
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    static = os.environ.get("STATIC") == "1"
    svg = build(static)
    dst = REPO / "contribution-city.svg"
    dst.write_text(svg, encoding="utf-8")
    towers = svg.count('class="tw"')
    tiles = svg.count('class="tile"')
    print(
        f"[city] wrote {dst} ({towers} towers, {tiles} floor tiles, "
        f"{'static' if static else 'animated'})"
    )


if __name__ == "__main__":
    main()
