"""Generate contribution-city.svg -- an isometric 3D city from a year of days.

Every day of the trailing year is one tower on a 53x7 isometric plot: height
scales with that day's contribution count, colour comes from the same green
ramp the heatmap uses, and days with no activity stay as flat floor tiles so
the grid still reads as a calendar. The left column carries the headline
numbers, all straight out of data/contributions.json -- the panel can never
disagree with the heatmap next to it.

Isometric projection used throughout (2:1 dimetric, no perspective math):
    sx = (gx - gy) * TW / 2
    sy = (gx + gy) * TH / 2
with gx = week index and gy = day-of-week, so weeks march away to the right
and the week's seven days stack towards the viewer.

Conventions shared with the other panels: transparent canvas, light theme with
a prefers-color-scheme re-ink, no script/foreignObject/external reference
(camo strips them), animation limited to opacity + transform (clip-path and
width animation froze behind camo in earlier panels), and prefers-reduced-motion
collapses to the finished city.

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
EMPTY_TILE, EMPTY_TILE_DARK = "#eaeef2", "#21262d"
GROUND, GROUND_DARK = "#f6f8fa", "#0d1117"
WIN, WIN_DARK = "#e3b341", "#f2cc0d"
GRID_LINE, GRID_LINE_DARK = "#d0d7de", "#30363d"
FG, FG_DARK = "#1f2328", "#e6edf3"
DIM, DIM_DARK = "#59636e", "#8b949e"


def load() -> tuple[list[dict], dict]:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    return payload.get("days", []), payload.get("stats", {})


def level_of(count: int, peak: int) -> int:
    if count <= 0:
        return -1
    ratio = count / peak if peak else 0.0
    return min(4, int(ratio * 5))


def iso(gx: float, gy: float) -> tuple[float, float]:
    """Grid coords -> screen coords of the tile's top corner."""
    return ORIGIN_X + (gx - gy) * TW / 2.0, FLOOR_Y + (gx + gy) * TH / 2.0


def tower_paths(x: float, y: float, h: float) -> tuple[str, str, str]:
    """Top, left and right faces of one box whose base sits at (x, y)."""
    top = (
        f"{x - TW / 2:.1f},{y - TH / 2 - h:.1f} "
        f"{x:.1f},{y - TH - h:.1f} "
        f"{x + TW / 2:.1f},{y - TH / 2 - h:.1f} "
        f"{x:.1f},{y - h:.1f}"
    )
    left = (
        f"{x - TW / 2:.1f},{y - TH / 2 - h:.1f} "
        f"{x:.1f},{y - h:.1f} "
        f"{x:.1f},{y:.1f} "
        f"{x - TW / 2:.1f},{y - TH / 2:.1f}"
    )
    right = (
        f"{x + TW / 2:.1f},{y - TH / 2 - h:.1f} "
        f"{x:.1f},{y - h:.1f} "
        f"{x:.1f},{y:.1f} "
        f"{x + TW / 2:.1f},{y - TH / 2:.1f}"
    )
    return top, left, right


def language_stack() -> list[tuple[str, int]]:
    """Language mix as percentages, read from the single authored source."""
    sys.path.insert(0, str(HERE))
    import make_skills_svg as gen

    for name, skills in gen.GROUPS:
        if name == "languages":
            return [(s, level * 20) for s, level in skills]
    return []


def flat_tile(x: float, y: float) -> str:
    """Diamond footprint of a zero-activity day -- keeps the calendar grid."""
    return (
        f"{x:.1f},{y - TH:.1f} {x + TW / 2:.1f},{y - TH / 2:.1f} "
        f"{x:.1f},{y:.1f} {x - TW / 2:.1f},{y - TH / 2:.1f}"
    )


def height_of(count: int, peak: int) -> float:
    if count <= 0:
        return 0.0
    ratio = count / peak if peak else 0.0
    return TOWER_MIN + ratio * (TOWER_MAX - TOWER_MIN)


def face_windows(x: float, y: float, h: float) -> list[str]:
    """Lit iso-diamond windows on the two visible faces of a tall tower."""
    if h < 26:
        return []
    rows = min(4, max(1, int(h // 15)))
    cols = 2
    w, v = 1.7, 1.0
    out: list[str] = []
    for face in (-1, 1):
        for r in range(rows):
            for c in range(cols):
                u = (c + 0.5) / cols
                vv = (r + 0.7) / (rows + 0.4)
                if face < 0:
                    px = (x - TW / 2) + u * (TW / 2)
                else:
                    px = (x + TW / 2) - u * (TW / 2)
                py = (y - TH / 2 - h) + u * (TH / 2) + vv * h
                out.append(
                    f"{px:.1f},{py - v:.1f} {px + w:.1f},{py:.1f} "
                    f"{px:.1f},{py + v:.1f} {px - w:.1f},{py:.1f}"
                )
    return out


def theme_css(static: bool) -> str:
    """Panel CSS: ink by class, dark re-ink, opacity+transform animation only."""
    css = [
        ".fg{fill:" + FG + "}",
        ".dim{fill:" + DIM + "}",
        ".rule{stroke:" + GRID_LINE + "}",
        ".gnd{fill:" + GROUND + ";stroke:" + GRID_LINE + "}",
        ".tile{fill:" + EMPTY_TILE + "}",
        ".trk{fill:" + EMPTY_TILE + "}",
        ".win{fill:" + WIN + ";opacity:.75}",
        ".now{fill:" + FG + "}",
    ]
    for i, (top, left, right) in enumerate(LIGHT_RAMP):
        css.append(f".t{i}{{fill:{top}}}")
        css.append(f".l{i}{{fill:{left}}}")
        css.append(f".r{i}{{fill:{right}}}")
    if not static:
        css += [
            ".tw,.tile{opacity:0}",
            "@keyframes rise{from{opacity:0;transform:translateY(8px)}"
            "to{opacity:1;transform:translateY(0)}}",
            ".tw,.tile{animation:rise .5s ease forwards}",
            "@keyframes pulse{0%,100%{opacity:1}50%{opacity:.2}}",
            ".now{animation:pulse 1.6s ease-in-out infinite}",
        ]
    dark = [
        ".fg{fill:" + FG_DARK + "}",
        ".dim{fill:" + DIM_DARK + "}",
        ".rule{stroke:" + GRID_LINE_DARK + "}",
        ".gnd{fill:" + GROUND_DARK + ";stroke:" + GRID_LINE_DARK + "}",
        ".tile{fill:" + EMPTY_TILE_DARK + "}",
        ".trk{fill:" + EMPTY_TILE_DARK + "}",
        ".win{fill:" + WIN_DARK + ";opacity:.85}",
        ".now{fill:" + FG_DARK + "}",
    ]
    for i, (top, left, right) in enumerate(DARK_RAMP):
        dark.append(f".t{i}{{fill:{top}}}")
        dark.append(f".l{i}{{fill:{left}}}")
        dark.append(f".r{i}{{fill:{right}}}")
    css.append("@media (prefers-color-scheme: dark){" + "".join(dark) + "}")
    css.append(
        "@media (prefers-reduced-motion: reduce)"
        "{.tw,.tile,.now{animation:none;opacity:1;transform:none}}"
    )
    return "".join(css)


def stat_blocks(stats: dict) -> list[tuple[str, str, str]]:
    best = stats.get("best_day", {}) or {}
    total = stats.get("total_last_year", 0)
    active = stats.get("active_days", 0)
    return [
        ("contributions", str(total), "last 12 months"),
        ("active days", str(active), f"{active / 365 * 100:.0f}% of the year"),
        ("busiest day", str(best.get("count", 0)), best.get("date", "-")),
        ("longest streak", str(stats.get("longest_streak", 0)), "days"),
    ]


def header(out: list[str]) -> None:
    out.append(
        f'<text x="{MARGIN}" y="26" font-size="13" font-weight="bold" '
        'class="fg">the city i built this year</text>'
    )
    out.append(
        f'<text x="{MARGIN}" y="42" font-size="9.5" class="dim">'
        "every day of the last 12 months, as a building</text>"
    )
    out.append(
        f'<line class="rule" x1="{MARGIN}" y1="52" x2="352" y2="52" '
        'stroke-width="1"/>'
    )


def left_column(out: list[str], stats: dict) -> None:
    for i, (label, value, sub) in enumerate(stat_blocks(stats)):
        yb = 72 + i * 44
        out.append(
            f'<text x="{MARGIN}" y="{yb}" font-size="9" class="dim">'
            f"{label}</text>"
        )
        out.append(
            f'<text x="{MARGIN}" y="{yb + 20}" font-size="20" '
            f'font-weight="bold" class="fg">{value}</text>'
        )
        out.append(
            f'<text x="{MARGIN + 92}" y="{yb + 14}" font-size="8.5" '
            f'class="dim">{sub}</text>'
        )

    out.append(
        f'<text x="{MARGIN}" y="250" font-size="10" font-weight="bold" '
        'class="fg">language stack</text>'
    )
    out.append(
        f'<line class="rule" x1="{MARGIN}" y1="256" x2="352" y2="256" '
        'stroke-width="1"/>'
    )
    for i, (name, pct) in enumerate(language_stack()):
        ry = 274 + i * 21
        fill = level_of(pct, 100)
        out.append(
            f'<text x="{MARGIN}" y="{ry}" font-size="9" class="fg">'
            f"{escape(name)}</text>"
        )
        out.append(
            f'<rect class="trk" x="104" y="{ry - 6}" width="222" '
            'height="5" rx="2.5"/>'
        )
        out.append(
            f'<rect class="t{fill}" x="104" y="{ry - 6}" '
            f'width="{222 * pct / 100:.1f}" height="5" rx="2.5"/>'
        )
        out.append(
            f'<text x="334" y="{ry}" font-size="8.5" class="dim">'
            f"{pct}%</text>"
        )

    # legend + footer
    out.append(
        f'<text x="{MARGIN}" y="414" font-size="9" class="dim">less</text>'
    )
    for i in range(5):
        cx, cy = 62 + i * 16, 417
        out.append(
            f'<path class="t{i}" d="M{cx},{cy - 2.5} {cx + 5},{cy} '
            f'{cx},{cy + 2.5} {cx - 5},{cy}Z"/>'
        )
    out.append(
        f'<text x="{62 + 5 * 16 + 6}" y="414" font-size="9" class="dim">'
        "more</text>"
    )
    out.append(
        f'<text x="{MARGIN}" y="446" font-size="8.5" class="dim">'
        "one tower per day &#183; height = that day's contributions</text>"
    )


def statistic_chip(out: list[str]) -> None:
    out.append(
        '<rect x="676" y="16" width="164" height="24" rx="6" '
        'class="gnd"/>'
    )
    out.append(
        '<path class="t4" d="M700,31 706,27 712,31 706,35Z"/>'
    )
    out.append(
        '<path class="l4" d="M700,31 712,31 712,38 700,38Z"/>'
    )
    out.append(
        f'<text x="722" y="32" font-size="9" class="dim">'
        "3D contribution viz</text>"
    )


def city(out: list[str], days: list[dict], static: bool) -> None:
    """Paint the isometric plot back-to-front (painter's algorithm on gx+gy)."""
    peak = max((d.get("count", 0) for d in days), default=0) or 1
    weeks = max((d.get("week", 0) for d in days), default=0) + 1
    corners = [iso(0, 0), iso(weeks - 1, 0), iso(weeks - 1, 6), iso(0, 6)]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in corners)
    out.append(f'<path class="gnd" d="M{pts}Z"/>')

    cells = [
        (d.get("week", 0) + d.get("weekday", 0), d.get("week", 0),
         d.get("weekday", 0), d)
        for d in days
    ]
    cells.sort(key=lambda c: (c[0], c[2]))
    for total_d, gx, gy, d in cells:
        x, y = iso(gx, gy)
        count = d.get("count", 0)
        delay = 0.05 + total_d * 0.012
        if count <= 0:
            out.append(
                f'<g class="tile" style="animation-delay:{delay:.3f}s">'
                f'<path d="M{flat_tile(x, y)}Z"/></g>'
            )
            continue
        h = height_of(count, peak)
        lvl = level_of(count, peak)
        top, left, right = tower_paths(x, y, h)
        out.append(
            f'<g class="tw" style="animation-delay:{delay:.3f}s">'
            f'<path class="r{lvl}" d="M{right}Z"/>'
            f'<path class="l{lvl}" d="M{left}Z"/>'
        )
        for w in face_windows(x, y, h):
            out.append(f'<path class="win" d="M{w}Z"/>')
        out.append(f'<path class="t{lvl}" d="M{top}Z"/></g>')

    # "today" pin over the newest day
    last = days[-1] if days else None
    if last is not None:
        x, y = iso(last.get("week", 0), last.get("weekday", 0))
        h = height_of(last.get("count", 0), peak)
        cy = y - TH - h - 9
        out.append(
            f'<g class="now"><path d="M{x},{cy - 4} {x + 2.6},{cy} '
            f'{x},{cy + 4} {x - 2.6},{cy}Z"/></g>'
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
        out.append("<style>.tw,.tile,.now{opacity:1;transform:none}</style>")
    header(out)
    left_column(out, stats)
    statistic_chip(out)
    city(out, days, static)
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


