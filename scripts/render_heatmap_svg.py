"""Render data/contributions.json as the classic 53-week x 7-day heatmap.

Rounded, colored boxes on a GitHub-ish green ramp. The palette is paired --
a light-theme ramp and a dark-theme ramp selected by prefers-color-scheme,
which SVG <img> documents inherit from the embedding page. The previous
single dark palette (#161b22 for "no contributions") drew an invisible gray
box on GitHub's white canvas.

Reveal: a diagonal, cell-after-cell slide-in. Animation is opacity +
transform only and is driven by CSS animation-delay rather than SMIL
<animate> -- every other panel moved to that form after SMIL begin offsets
proved unreliable behind GitHub's camo <img>, and a frozen panel still shows
the full grid because every animation ends fully visible. Plus a Less->More
legend and a stats footer.

Run: python scripts/render_heatmap_svg.py     # animated
     STATIC=1 python scripts/render_heatmap_svg.py  # frozen frame
"""
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data" / "contributions.json"
OUT = REPO / "contrib-heatmap.svg"

# Light theme first (GitHub light primitives); the dark re-ink keeps the
# "no contributions" cell a gray that still reads on GitHub's dark canvas.
PALETTE = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39", "#1a7f37"]
DARK_PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]
FG, DIM = "#1f2328", "#57606e"
DARK_FG, DARK_DIM = "#e6edf3", "#8b949e"
# fixed thresholds -> 0..5 (level 5 is the neon top end)
THRESHOLDS = [0, 1, 4, 8, 12, 20]

CELL, GAP, PITCH = 10, 3, 13
MARGIN_L, TOP = 30, 20  # room for weekday labels (left) and month labels (top)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]



def level_for(count: int) -> int:
    lvl = 0
    for i, t in enumerate(THRESHOLDS):
        if count >= t:
            lvl = i
    return lvl


def theme_css(static: bool) -> str:
    """Light theme first; prefers-color-scheme re-inks cells and text.

    SVG <img> documents inherit the embedding page's color scheme, so GitHub's
    dark theme swaps the palette without a second markup variant. Cells are
    hidden only while the reveal runs, and prefers-reduced-motion collapses
    straight to the finished grid -- a frozen panel still shows every day.
    """
    css = [f".c{i}{{fill:{c}}}" for i, c in enumerate(PALETTE)]
    css.append(f".fg{{fill:{FG}}}")
    css.append(f".dim{{fill:{DIM}}}")
    if not static:
        css += [
            ".cell{opacity:0}",
            "@keyframes cell{from{opacity:0;transform:translate(-4px,-4px)}"
            "to{opacity:1;transform:none}}",
            ".cell{animation:cell .35s ease-out forwards}",
        ]
    dark = [f".c{i}{{fill:{c}}}" for i, c in enumerate(DARK_PALETTE)]
    dark.append(f".fg{{fill:{DARK_FG}}}")
    dark.append(f".dim{{fill:{DARK_DIM}}}")
    css.append("@media (prefers-color-scheme: dark){" + "".join(dark) + "}")
    css.append(
        "@media (prefers-reduced-motion: reduce)"
        "{.cell{animation:none;opacity:1;transform:none}}"
    )
    return "".join(css)


def build(payload: dict, static: bool = False) -> str:
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
    out.append(f'<style>{theme_css(static)}</style>')

    # month labels
    for week, name in month_marks:
        out.append(
            f'<text class="dim" font-size="10" x="{MARGIN_L + week * PITCH}" y="{TOP - 6}">{name}</text>'
        )
    # weekday labels (Mon / Wed / Fri)
    for day, name in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        out.append(
            f'<text class="dim" font-size="10" x="0" y="{TOP + day * PITCH + 9}">{name}</text>'
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
            style = "" if static else f' style="animation-delay:{delay:.2f}s"'
            title = next(d for d in days if d["week"] == week and d["weekday"] == weekday)
            out.append(
                f'<rect class="cell c{lvl}"{style} x="{x}" y="{y}" width="{CELL}"'
                f' height="{CELL}" rx="2" ry="2">'
                f"<title>{title['count']} contributions on {title['date']}</title>"
                f"</rect>"
            )

    # legend: Less -> More (5 steps + the reserved neon top end)
    used = sorted(set(grid.values()))
    steps = used if 1 < len(used) < len(PALETTE) else list(range(len(PALETTE)))
    lx = MARGIN_L + n_weeks * PITCH - (len(steps) + 1) * PITCH
    out.append('<text class="dim" font-size="10" x="620" y="136">Less</text>')
    for i, idx in enumerate(steps):
        out.append(
            f'<rect class="c{idx}" x="{lx + i * PITCH}" y="{legend_y}" width="{CELL}"'
            f' height="{CELL}" rx="2" ry="2"/>'
        )
    out.append(
        f'<text class="dim" font-size="10" x="{lx + len(steps) * PITCH + 6}" y="{legend_y + 9}">More</text>'
    )

    # footer stats
    s = payload["stats"]
    out.append(
        f'<text class="fg" font-size="12" x="{MARGIN_L}" y="{height - 8}">'
        f"{s['total_last_year']:,} contributions in the last year</text>"
    )
    out.append(
        f'<text class="dim" font-size="11" x="{width - 8}" y="{height - 8}" text-anchor="end">'
        f"streak {s['current_streak']}d · best {s['best_day']['count']} · "
        f"longest {s['longest_streak']}d</text>"
    )
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    static = os.environ.get("STATIC") == "1"
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    svg = build(payload, static)
    OUT.write_text(svg, encoding="utf-8")
    print(f"[heatmap] wrote {OUT} ({len(payload['days'])} days, "
          f"{max(d['week'] for d in payload['days']) + 1} weeks, "
          f"{'static' if static else 'animated'})")


if __name__ == "__main__":
    main()
