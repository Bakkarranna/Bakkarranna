"""Generate stats-strip.svg -- KPI row plus a monthly bar chart from real data.

This is the only art that is genuinely data-driven: skills.svg and info-card.svg
are hand-authored, but every number here comes from data/contributions.json that
fetch_contributions.py scrapes, so the panel can never disagree with the
heatmap next to it. If a key is missing the generator fills a placeholder rather
than raising -- the daily workflow must still be able to commit the other art.

Reads (from data/contributions.json):
  stats.total_last_year   lifetime-ish total for the trailing year
  stats.active_days       days with >= 1 contribution
  stats.current_streak    consecutive days ending today
  stats.longest_streak    best run in the window
  stats.best_day          {date, count} -- busiest single day
  stats.monthly           [{month: "YYYY-MM", total: n}, ...] -- 12 entries

Conventions shared with the other SVGs: transparent canvas, light theme first
with a prefers-color-scheme re-ink, no script/foreignObject/external asset
(camo strips scripts), animation limited to opacity and transform (clip-path and
width animation froze behind camo before), and prefers-reduced-motion collapses
to the fully visible end state.

Run: python scripts/make_stats_strip_svg.py          # animated
     STATIC=1 python scripts/make_stats_strip_svg.py # frozen frame for previews
"""
import json
import os
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data" / "contributions.json"
FONT = "'JetBrains Mono','Fira Mono','SFMono-Regular',Menlo,Consolas,monospace"

W, H = 860, 236
MARGIN = 16
FG = "#1f2328"
DIM = "#59636e"
RULE = "#d0d7de"
TRACK = "#eaeef2"
BAR_SCALE = ["#9be9a8", "#40c463", "#30a14e", "#216e39", "#1a7f37"]      # light
DARK_BAR_SCALE = ["#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]  # dark
DARK = {"fg": "#e6edf3", "dim": "#8b949e", "rule": "#30363d", "track": "#21262d"}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# KPI tiles: (label, value, sub). Filled from the data below.
BAR_H_MAX = 86
BAR_W = 40


def load() -> dict:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    return payload.get("stats", {})


def kpis(stats: dict) -> list[tuple[str, str, str]]:
    total = stats.get("total_last_year", 0)
    days = stats.get("active_days", 0)
    cur = stats.get("current_streak", 0)
    longest = stats.get("longest_streak", 0)
    best = stats.get("best_day", {}) or {}
    avg = total / 365.0 if total else 0.0
    return [
        ("contributions", str(total), "last 12 months"),
        ("active days", str(days), f"{days / 365 * 100:.0f}% of the year"),
        ("current streak", str(cur), "days"),
        ("longest streak", str(longest), "days"),
        ("best day", str(best.get("count", 0)), best.get("date", "-")),
        ("daily average", f"{avg:.1f}", "per calendar day"),
    ]


def bar_level(total: int, peak: int) -> int:
    """Map a monthly total onto the green ramp (0 = empty month)."""
    if total <= 0:
        return -1
    ratio = total / peak if peak else 0
    return min(len(BAR_SCALE) - 1, int(ratio * len(BAR_SCALE)))


def theme_css(static: bool) -> str:
    css = [
        ".fg{fill:" + FG + "}",
        ".dim{fill:" + DIM + "}",
        ".rule{stroke:" + RULE + "}",
        ".track{fill:" + TRACK + "}",
    ]
    for i, c in enumerate(BAR_SCALE):
        css.append(f".b{i}{{fill:{c}}}")
    if not static:
        css += [
            ".kpi,.bar,.chart-label{opacity:0}",
            "@keyframes rise{from{opacity:0;transform:translateY(10px)}"
            "to{opacity:1;transform:translateY(0)}}",
            ".chart-label{animation:rise .4s ease forwards}",
            ".kpi{animation:rise .45s ease forwards}",
            ".bar{animation:rise .5s ease forwards}",
        ]
    dark = [
        ".fg{fill:" + DARK["fg"] + "}",
        ".dim{fill:" + DARK["dim"] + "}",
        ".rule{stroke:" + DARK["rule"] + "}",
        ".track{fill:" + DARK["track"] + "}",
    ]
    for i, c in enumerate(DARK_BAR_SCALE):
        dark.append(f".b{i}{{fill:{c}}}")
    css.append("@media (prefers-color-scheme: dark){" + "".join(dark) + "}")
    css.append(
        "@media (prefers-reduced-motion: reduce)"
        "{.kpi,.bar,.chart-label{animation:none;opacity:1;transform:none}}"
    )
    return "".join(css)


def build(static: bool) -> str:
    def _delay(seconds: float) -> str:
        """Inline reveal position, or nothing for the frozen static frame.

        Same convention as the heatmap and the info card: the timing lives on
        the element, never baked into the animation shorthand, so one place in
        this generator reads the panel's whole reveal order.
        """
        return "" if static else f' style="animation-delay:{seconds:.2f}s"'

    stats = load()
    monthly = stats.get("monthly", [])
    peak = max((m.get("total", 0) for m in monthly), default=0) or 1

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="{FONT}">'
    )
    out.append(f"<style>{theme_css(static)}</style>")
    if static:
        out.append("<style>.kpi,.bar,.chart-label{opacity:1;transform:none}</style>")

    out.append(
        f'<text x="{MARGIN}" y="22" font-size="13" class="fg" font-weight="bold">'
        f"activity</text>"
    )
    out.append(
        f'<text x="{MARGIN + 58}" y="22" font-size="11" class="dim">'
        f"scraped from github.com/users/Bakkarranna/contributions</text>"
    )
    out.append(
        f'<line class="rule" x1="{MARGIN}" y1="30" x2="{W - MARGIN}" y2="30" '
        f'stroke-width="1"/>'
    )

    # ---- KPI row ----------------------------------------------------------
    cell_w = (W - MARGIN * 2) / len(kpis(stats))
    for i, (label, value, sub) in enumerate(kpis(stats)):
        x = MARGIN + i * cell_w
        style = _delay(0.10 + i * 0.07)
        out.append(f'<g class="kpi"{style}>')
        out.append(f'<text x="{x}" y="52" font-size="10" class="dim">{escape(label)}</text>')
        out.append(
            f'<text x="{x}" y="74" font-size="21" class="fg" font-weight="bold">'
            f"{escape(value)}</text>"
        )
        out.append(f'<text x="{x}" y="90" font-size="10" class="dim">{escape(sub)}</text>')
        out.append("</g>")
        if i:
            out.append(
                f'<line class="rule" x1="{x - 8}" y1="44" x2="{x - 8}" y2="92" '
                f'stroke-width="1"/>'
            )

    # ---- monthly bars -----------------------------------------------------
    top = 116
    baseline = H - 22
    out.append(
        f'<g class="chart-label"{_delay(0.10)}>'
        f'<text x="{MARGIN}" y="{top}" font-size="11" class="dim">'
        f"contributions per month</text></g>"
    )
    chart_w = W - MARGIN * 2
    cell = chart_w / max(len(monthly), 1)
    for i, entry in enumerate(monthly):
        total = entry.get("total", 0)
        cx = MARGIN + i * cell
        x = cx + (cell - BAR_W) / 2
        h = max(2, round(total / peak * BAR_H_MAX)) if total else 3
        y = baseline - h
        style = _delay(0.25 + i * 0.04)
        out.append(f'<g class="bar"{style}>')
        out.append(
            f'<rect x="{x:.1f}" y="{baseline - 3:.1f}" width="{BAR_W}" height="3" rx="1" '
            f'class="track"/>'
        )
        if total:
            level = bar_level(total, peak)
            out.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{BAR_W}" height="{h}" rx="2" '
                f'class="b{level}"/>'
            )
            out.append(
                f'<text x="{x + BAR_W / 2:.1f}" y="{y - 5:.1f}" font-size="10" '
                f'class="dim" text-anchor="middle">{total}</text>'
            )
        month = entry.get("month", "")
        label = month
        if "-" in month:
            year_s, mon_s = month.split("-")
            mon = int(mon_s) if mon_s.isdigit() else 1
            label = MONTHS[mon - 1] if mon_s.isdigit() and 1 <= mon <= 12 else mon_s
            if mon == 1:
                label += " '" + year_s[2:]
        out.append(
            f'<text x="{x + BAR_W / 2:.1f}" y="{baseline + 14:.1f}" font-size="10" '
            f'class="dim" text-anchor="middle">{escape(label)}</text>'
        )
        out.append("</g>")

    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    static = os.environ.get("STATIC") == "1"
    svg = build(static)
    dst = REPO / "stats-strip.svg"
    dst.write_text(svg, encoding="utf-8")
    print(f"[stats] wrote {dst} ({'static' if static else 'animated'})")


if __name__ == "__main__":
    main()
