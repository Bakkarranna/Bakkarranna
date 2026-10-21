"""Render data/contributions.json as the classic 53-week x 7-day heatmap.

Rounded, colored boxes on a GitHub-ish green ramp. The palette is paired --
a light-theme ramp and a dark-theme ramp selected by prefers-color-scheme,
which SVG <img> documents inherit from the embedding page. The previous
single dark palette (#161b22 for "no contributions") drew an invisible gray
box on GitHub's white canvas.

Reveal: a diagonal, line-after-line slide-in (CSS opacity + transform, no
SMIL geometry animating inside clipPath -- that never unfreezes behind
GitHub's camo <img>). Plus a Less->More legend and a stats footer.

Run: python scripts/render_heatmap_svg.py    # writes contrib-heatmap.svg
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data" / "contributions.json"
OUT = REPO / "contrib-heatmap.svg"

PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]
# fixed thresholds -> 0..5 (level 5 is the neon top end)
THRESHOLDS = [0, 1, 4, 8, 12, 20]

CELL, GAP, PITCH = 10, 3, 13
MARGIN_L, TOP = 30, 20  # room for weekday labels (left) and month labels (top)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

FG, DIM = "#c9d1d9", "#8b949e"


def level_for(count: int) -> int:
    lvl = 0
    for i, t in enumerate(THRESHOLDS):
        if count >= t:
            lvl = i
    return lvl


def build(payload: dict) -> str:
    days = payload["days"]
    n_weeks = max(d["week"] for d in days) + 1
    width = MARGIN_L + n_weeks * PITCH + 8
    legend_y = TOP + 7 * PITCH + 16
    height = legend_y + 30

    # cell lookup: (week, weekday) -> color index. GitHub's own data-level is
    # authoritative; the count thresholds are only a fallback for days that
    # lack one. The neon top end (#69f0a0) is reserved for genuinely big days.
    def color_index(d):
        if d["count"] >= THRESHOLDS[-1]:
            return len(PALETTE) - 1
        return d.get("level") if d.get("level") is not None else level_for(d["count"])

    grid = {(d["week"], d["weekday"]): color_index(d) for d in days}

    # month labels: place where the first day of a month lands
    month_marks = []
    seen = set()
    for d in days:
        m = int(d["date"][5:7])
        if m not in seen and d["weekday"] <= 3:  # only labels near the week start
            seen.add(m)
            month_marks.append((d["week"], MONTHS[m - 1]))

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="monospace">'
    ]
    out.append(f'<rect width="{width}" height="{height}" fill="none"/>')

    # month labels
    for week, name in month_marks:
        out.append(
            f'<text x="{MARGIN_L + week * PITCH}" y="{TOP - 6}" font-size="10" fill="{DIM}">{name}</text>'
        )
    # weekday labels (Mon / Wed / Fri)
    for day, name in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        out.append(
            f'<text x="0" y="{TOP + day * PITCH + 9}" font-size="10" fill="{DIM}">{name}</text>'
        )

    # cells -- diagonal slide-in reveal, once, frozen
    for week in range(n_weeks):
        for weekday in range(7):
            lvl = grid.get((week, weekday))
            if lvl is None:
                continue
            x = MARGIN_L + week * PITCH
            y = TOP + weekday * PITCH
            delay = (week + weekday) * 0.035
            color = PALETTE[lvl]
            title = next(d for d in days if d["week"] == week and d["weekday"] == weekday)
            out.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" ry="2" fill="{color}">'
                f"<title>{title['count']} contributions on {title['date']}</title>"
                f'<animate attributeName="opacity" from="0" to="1" dur="0.35s" begin="{delay:.3f}s" fill="freeze"/>'
                f'<animateTransform attributeName="transform" type="translate" '
                f'from="-4 -4" to="0 0" dur="0.35s" begin="{delay:.3f}s" fill="freeze" '
                f'calcMode="spline" keySplines="0.25 1 0.5 1" keyTimes="0;1" values="-4 -4;0 0"/>'
                f"</rect>"
            )

    # legend: Less -> More (5 steps + the reserved neon top end)
    used = sorted(set(grid.values()))
    steps = used if 1 < len(used) < len(PALETTE) else list(range(len(PALETTE)))
    lx = MARGIN_L + n_weeks * PITCH - (len(steps) + 1) * PITCH
    out.append(f'<text x="{lx - 34}" y="{legend_y + 9}" font-size="10" fill="{DIM}">Less</text>')
    for i, idx in enumerate(steps):
        out.append(
            f'<rect x="{lx + i * PITCH}" y="{legend_y}" width="{CELL}" height="{CELL}" rx="2" ry="2" '
            f'fill="{PALETTE[idx]}"/>'
        )
    out.append(
        f'<text x="{lx + len(steps) * PITCH + 6}" y="{legend_y + 9}" font-size="10" fill="{DIM}">More</text>'
    )

    # footer stats
    s = payload["stats"]
    out.append(
        f'<text x="{MARGIN_L}" y="{height - 8}" font-size="12" fill="{FG}">'
        f"{s['total_last_year']:,} contributions in the last year</text>"
    )
    out.append(
        f'<text x="{width - 8}" y="{height - 8}" font-size="11" fill="{DIM}" text-anchor="end">'
        f"streak {s['current_streak']}d · best {s['best_day']['count']} · "
        f"longest {s['longest_streak']}d</text>"
    )
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    svg = build(payload)
    OUT.write_text(svg, encoding="utf-8")
    print(f"[heatmap] wrote {OUT} ({len(payload['days'])} days, "
          f"{max(d['week'] for d in payload['days']) + 1} weeks)")


if __name__ == "__main__":
    main()
