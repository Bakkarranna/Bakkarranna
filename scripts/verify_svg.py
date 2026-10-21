"""Verify the generated SVGs structurally -- no browser needed.

The profile page embeds these SVGs via GitHub's camo proxy, which sanitizes
scripts: what renders is pure XML + SMIL/CSS animation. So every break is a
structural break, and this script can catch each one offline.

Checks:
  1. XML well-formedness (etree parse).
  2. contrib-heatmap.svg: one titled cell per contribution day, diagonal
     stagger begins, month labels + Less/More legend, stats footer.
  3. bakkarranna-ascii.svg: exactly ROWS text rows, one clipPath wipe + cursor
     an opacity-only reveal, and no clipPath or cursor rect -- that wipe is
     the animation that froze behind camo.
  4. info-card.svg: story rows, pixel logo, colour swatches, per-line stagger.
  5. skills.svg: one group per skill family, five meter segments per chip, and
     exactly as many lit segments as the authored levels add up to.
  6. stats-strip.svg: six KPI tiles and one bar per month, with monthly totals
     cross-checked against data/contributions.json.
  7. contribution-city.svg: one tower per contribution day, diagonal stagger
     begins, month coverage and a language-stack block.
  8. projects.svg: one card per featured repo, wrapped blurbs within budget, and
     state badges matching data/projects.json.
  9. constellation.svg: bounded sprite count, sky-cell sampling and the keyframes
     that keep it alive.
 10. Every panel: no <script>, no foreignObject, no remote reference -- camo
     strips all three, so a panel depending on one is silently broken.
 11. Animation totals so nothing freezes mid-print.

Usage: python scripts/verify_svg.py     # exits 1 on any failure
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data" / "contributions.json"


def check_heatmap(path: Path, report: list[str]) -> bool:
    text = path.read_text(encoding="utf-8")
    ok = True

    expected_days = len(json.loads(DATA.read_text(encoding="utf-8"))["days"])
    cells = text.count("<title>")
    if cells != expected_days:
        report.append(f"  FAIL heatmap: {cells} titled cells, expected {expected_days}")
        ok = False
    else:
        report.append(f"  OK   heatmap: {cells} titled contribution cells")

    begins = [float(m) for m in re.findall(r'begin="([\d.]+)s"', text)]
    if len(begins) < expected_days:
        report.append(f"  FAIL heatmap: only {len(begins)} reveal animations")
        ok = False
    else:
        report.append(
            f"  OK   heatmap: {len(begins)} reveals, stagger 0..{max(begins):.2f}s"
        )

    for needle in ("Jan", "Jun", "Dec", "Less", "More", "contributions in the last year"):
        if needle not in text:
            report.append(f"  FAIL heatmap: missing {needle!r}")
            ok = False
    if ok:
        report.append("  OK   heatmap: month labels, legend and stats footer present")

    for bad in ("<unknown>", "None", "NaN"):
        if bad in text:
            report.append(f"  FAIL heatmap: leaked token {bad!r}")
            ok = False
    return ok


def check_ascii(path: Path, report: list[str]) -> bool:
    text = path.read_text(encoding="utf-8")
    ok = True

    rows = re.findall(r"<text[^>]*>([^<]*)</text>", text)
    if len(rows) != 53:
        report.append(f"  FAIL ascii: {len(rows)} text rows, expected 53")
        ok = False
    else:
        glyph = set("".join(rows))
        report.append(
            f"  OK   ascii: 53 rows, widest {max(len(r) for r in rows)} chars, "
            f"{len(glyph)} distinct glyphs"
        )

    clips = re.findall(r"clip-path|clipPath", text)
    if clips:
        report.append(f"  FAIL ascii: {len(clips)} clip-path uses -- that animation froze behind camo")
        ok = False

    cursors = len(re.findall(r"<rect", text))
    if cursors:
        report.append(f"  FAIL ascii: {cursors} <rect> cursor blocks left over from the wipe reveal")
        ok = False

    delays = sorted(float(m) for m in re.findall(r"animation-delay:([\d.]+)s", text))
    if len(delays) != 53:
        report.append(f"  FAIL ascii: {len(delays)} row delays, expected 53")
        ok = False
    elif delays != [round(i * 0.055, 2) for i in range(53)]:
        report.append(f"  FAIL ascii: row stagger is not a clean top-to-bottom ramp")
        ok = False
    else:
        report.append(
            f"  OK   ascii: 53 rows stagger 0..{delays[-1]:.2f}s, "
            f"reveal done ~{delays[-1] + 0.42:.2f}s, no clip-path"
        )

    for required in ("prefers-reduced-motion", "prefers-color-scheme", "@keyframes line"):
        if required not in text:
            report.append(f"  FAIL ascii: missing {required!r}")
            ok = False

    ends_with_theme = re.search(r'@keyframes line\{from\{opacity:0', text)
    if not ends_with_theme:
        report.append("  FAIL ascii: reveal must animate opacity, not geometry")
        ok = False
    return ok


def check_card(path: Path, report: list[str]) -> bool:
    text = path.read_text(encoding="utf-8")
    ok = True

    lines = len(re.findall(r'<g class="line"', text))
    if lines != 6:  # 5 story rows + contact line
        report.append(f"  FAIL card: {lines} .line groups, expected 6")
        ok = False
    else:
        report.append(f"  OK   card: {lines} line groups (5 story rows + contact)")

    if "bakkarranna@github" not in text:
        report.append("  FAIL card: missing title 'bakkarranna@github'")
        ok = False

    swatches = len(re.findall(r'<g class="swatches">.*?</g>', text, re.S))
    swatch_rects = len(re.findall(r'rx="2"', text))
    if swatch_rects != 6:
        report.append(f"  FAIL card: {swatch_rects} colour swatches, expected 6")
        ok = False

    if 'class="logo"' not in text:
        report.append("  FAIL card: missing pixel logo")
        ok = False

    delays = [float(m) for m in re.findall(r"animation-delay:([\d.]+)s", text)]
    if len(delays) == 6:
        report.append(f"  OK   card: stagger 0..{max(delays):.2f}s")
    elif "opacity:1" not in text:
        report.append("  FAIL card: neither animated nor static-free of rows")
        ok = False
    return ok


def check_no_scripts(path: Path, report: list[str]) -> bool:
    """Camo strips scripts, so a panel relying on one is silently broken."""
    text = path.read_text(encoding="utf-8")
    # xmlns is a namespace declaration, not a fetch: camo never strips it.
    text = re.sub(r'\sxmlns(:xlink)?="[^"]*"', "", text)
    ok = True
    for bad in ("<script", "<foreignObject", "http://", "https://"):
        if bad in text:
            report.append(f"  FAIL {path.name}: forbidden {bad!r} (camo strips it)")
            ok = False
    if ok:
        report.append(f"  OK   {path.name}: self-contained, no script/remote ref")
    return ok


def check_skills(path: Path, report: list[str]) -> bool:
    """skills.svg: groups, chips, meter segments, lit-segment arithmetic."""
    text = path.read_text(encoding="utf-8")
    ok = True
    # Read the authored levels from the generator instead of restating them
    # here -- duplicated expectations drift away from the art they check.
    sys.path.insert(0, str(REPO / "scripts"))
    import make_skills_svg as gen

    groups = re.findall(r'<g class="grp"', text)
    chips = re.findall(r'<g class="chip">', text)
    want_groups = len(gen.GROUPS)
    want_chips = sum(len(s) for _, s in gen.GROUPS)
    want_segments = want_chips * gen.METER_SEGMENTS
    want_lit = sum(level for _, skills in gen.GROUPS for _, level in skills)
    # STATIC=1 preview frames carry no delay/keyframes, only a frozen style.
    animated = "animation-delay:" in text

    checks = [
        ("groups", len(groups), want_groups),
        ("chips", len(chips), want_chips),
        ("meter segments", len(re.findall(r'class="m(?: on)? g\d+"', text)), want_segments),
        ("lit segments", len(re.findall(r'class="m on g\d+"', text)), want_lit),
        ("group delays", len(re.findall(r"animation-delay:([\d.]+)s", text)), want_groups if animated else 0),
    ]
    for label, got, want in checks:
        if got != want:
            report.append(f"  FAIL skills: {got} {label}, expected {want}")
            ok = False
        else:
            report.append(f"  OK   skills: {got} {label}")

    for needle in (("prefers-reduced-motion", "prefers-color-scheme", "@keyframes rise")
                   if animated else ("opacity:1",)):
        if needle not in text:
            report.append(f"  FAIL skills: missing {needle!r}")
            ok = False
    return ok


def check_stats(path: Path, report: list[str]) -> bool:
    """stats-strip.svg: KPI tiles, one bar per month, totals match the data."""
    text = path.read_text(encoding="utf-8")
    ok = True
    stats = json.loads(DATA.read_text(encoding="utf-8"))["stats"]
    monthly = stats.get("monthly", [])
    # STATIC=1 preview frames carry no delay/keyframes, only a frozen style.
    animated = "animation-delay:" in text

    kpis = re.findall(r'<g class="kpi"', text)
    bars = re.findall(r'<g class="bar"', text)
    # Bar value labels are the digit-only text-anchor=middle runs; month labels
    # are names, so isdigit separates them.
    labels = [
        t for t in re.findall(r'class="dim" text-anchor="middle">([^<]*)</text>', text)
        if t.isdigit()
    ]
    want_labels = sorted(str(m.get("total", 0)) for m in monthly if m.get("total", 0) > 0)
    painted = len(re.findall(r'class="b\d+"', text))
    total = stats.get("total_last_year")

    checks = [
        ("KPI tiles", len(kpis), 6),
        ("monthly bars", len(bars), len(monthly)),
        ("painted bars", painted, len(want_labels)),
    ]
    for label, got, want in checks:
        if got != want:
            report.append(f"  FAIL stats: {got} {label}, expected {want}")
            ok = False
        else:
            report.append(f"  OK   stats: {got} {label}")

    if sorted(labels) != want_labels:
        report.append(f"  FAIL stats: bar labels {sorted(labels)} != data {want_labels}")
        ok = False
    else:
        report.append(f"  OK   stats: bar labels match {len(want_labels)} active months")

    if total is not None:
        if str(total) not in text:
            report.append(f"  FAIL stats: headline total {total} missing")
            ok = False
        else:
            report.append(f"  OK   stats: headline total {total} present")

    for needle in (("prefers-reduced-motion", "prefers-color-scheme", "@keyframes rise")
                   if animated else ("opacity:1",)):
        if needle not in text:
            report.append(f"  FAIL stats: missing {needle!r}")
            ok = False
    return ok


def _load_generator(name: str):
    """Import a generator so a check reads its authored data, not a copy."""
    scripts = str(REPO / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    return __import__(name)


def check_city(path: Path, report: list[str]) -> bool:
    """contribution-city.svg: every day plotted, stagger, stats, language mix."""
    text = path.read_text(encoding="utf-8")
    ok = True
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    days = payload.get("days", [])
    stats = payload.get("stats", {})

    tiles = len(re.findall(r'<g class="tile"', text))
    towers = len(re.findall(r'<g class="tw"', text))
    want_tiles = sum(1 for d in days if d.get("count", 0) <= 0)
    want_towers = len(days) - want_tiles
    for label, got, want in (("floor tiles", tiles, want_tiles),
                             ("towers", towers, want_towers)):
        if got != want:
            report.append(f"  FAIL city: {got} {label}, expected {want}")
            ok = False
        else:
            report.append(f"  OK   city: {got} {label}")

    if tiles + towers == len(days):
        report.append(f"  OK   city: all {len(days)} days plotted")
    else:
        report.append(f"  FAIL city: {tiles + towers} plots for {len(days)} days")
        ok = False

    delays = [float(m) for m in re.findall(r'animation-delay:([\d.]+)s"', text)]
    if len(delays) != len(days):
        report.append(f"  FAIL city: {len(delays)} day animations, expected {len(days)}")
        ok = False
    elif delays != sorted(delays):
        report.append("  FAIL city: stagger is not a back-to-front ramp")
        ok = False
    else:
        report.append(f"  OK   city: painter's-order stagger 0..{max(delays):.2f}s")

    gen = _load_generator("make_city_svg")
    stack = gen.language_stack()
    tracks = len(re.findall(r'class="trk"', text))
    if tracks != len(stack):
        report.append(f"  FAIL city: {tracks} language bars, expected {len(stack)}")
        ok = False
    else:
        report.append(f"  OK   city: {tracks} language bars from the authored mix")

    best = stats.get("best_day", {}) or {}
    for label, value in (("total", stats.get("total_last_year")),
                         ("active days", stats.get("active_days")),
                         ("longest streak", stats.get("longest_streak")),
                         ("best day", best.get("count"))):
        if str(value) not in text:
            report.append(f"  FAIL city: headline {label} ({value}) missing")
            ok = False
    if ok:
        report.append("  OK   city: headline stats read from contributions.json")

    for needle in ("less", "more", "one tower per day", "language stack"):
        if needle not in text:
            report.append(f"  FAIL city: missing {needle!r}")
            ok = False

    if "clip-path" in text or "clipPath" in text:
        report.append("  FAIL city: clip-path animation froze behind camo")
        ok = False
    return ok


def check_projects(path: Path, report: list[str]) -> bool:
    """projects.svg: one card per authored repo, badges, wrapped blurbs."""
    text = path.read_text(encoding="utf-8")
    ok = True
    payload = json.loads((REPO / "data" / "projects.json").read_text(encoding="utf-8"))
    projects = payload.get("featured", [])
    gen = _load_generator("make_projects_svg")

    want_b = sum(min(3, len(gen.wrap(p["blurb"], 46))) for p in projects)
    want_s = sum(len(gen.chips(p.get("stack", []))) for p in projects)
    checks = [
        ("cards", len(re.findall(r'<rect class="card(?: alt)?"', text)), len(projects)),
        ("titles", len(re.findall(r'class="h"', text)), len(projects)),
        ("kickers", len(re.findall(r'class="k"', text)), len(projects)),
        ("state badges", len(re.findall(r'class="badge"', text)), len(projects)),
        ("blurb lines", len(re.findall(r'class="b"', text)), want_b),
        ("stack chips", len(re.findall(r'class="s"', text)), want_s),
        ("proof lines", len(re.findall(r'class="p"', text)),
         sum(1 for p in projects if p.get("proof"))),
    ]
    for label, got, want in checks:
        if got != want:
            report.append(f"  FAIL projects: {got} {label}, expected {want}")
            ok = False
        else:
            report.append(f"  OK   projects: {got} {label}")

    badges = re.findall(r'class="badge"[^>]*>([^<]*)</text>', text)
    want_badges = [gen.STATE_BADGE.get(p.get("state", "public"), "?").upper()
                   for p in projects]
    if badges != want_badges:
        report.append(f"  FAIL projects: badges {badges} != {want_badges}")
        ok = False
    else:
        report.append("  OK   projects: every badge matches its authored state")

    for p in projects:
        for key in ("name", "kicker"):
            value = gen.esc(str(p[key]))
            if key == "kicker":
                value = value.upper()
            if value not in text:
                report.append(f"  FAIL projects: {key} {p[key]!r} not printed")
                ok = False
        if gen.esc(gen.wrap(p["blurb"], 46)[0]) not in text:
            report.append(f"  FAIL projects: blurb for {p['name']!r} not printed")
            ok = False

    if text.count("<") > gen.NODE_BUDGET:
        report.append(f"  FAIL projects: {text.count('<')} nodes over budget")
        ok = False
    else:
        report.append(f"  OK   projects: {text.count('<')} nodes, budget "
                      f"{gen.NODE_BUDGET}")

    for needle in ("prefers-color-scheme", "<title>", 'aria-label="Featured projects:'):
        if needle not in text:
            report.append(f"  FAIL projects: missing {needle!r}")
            ok = False
    return ok


def check_constellation(path: Path, report: list[str]) -> bool:
    """constellation.svg: bounded star field, flared core, both themes."""
    text = path.read_text(encoding="utf-8")
    ok = True
    gen = _load_generator("make_constellation_svg")
    animated = "animation-delay:" in text

    stars = len(re.findall(r"<circle", text))
    flared = len(re.findall(r'<circle class="(?:tw )?s1"', text))
    twinkles = len(re.findall(r'<circle class="tw s[12]"', text))
    links = len(re.findall(r'class="ln"', text))
    arms = len(re.findall(r'<line class="s2"', text))

    checks = [
        ("stars", stars, 0, gen.MAX_STARS),
        ("flared stars", flared, 0, gen.FLARE_CELLS),
        ("twinkles", twinkles, 1 if animated else 0, gen.MAX_STARS),
        ("skeleton links", links, 1 if animated else 0, gen.SKELETON_LINKS),
        ("flare arms", arms, flared * 2, flared * 2),
    ]
    for label, got, low, high in checks:
        if not low <= got <= high:
            report.append(f"  FAIL constellation: {got} {label}, "
                          f"expected {low}..{high}")
            ok = False
        else:
            report.append(f"  OK   constellation: {got} {label}")

    needles = (gen.INK, gen.INK_SOFT, gen.INK_DARK, gen.INK_DARK_SOFT,
               "prefers-color-scheme", "prefers-reduced-motion", "stargaze")
    if animated:
        needles += ("@keyframes tw", "@keyframes ln")
    for needle in needles:
        if needle not in text:
            report.append(f"  FAIL constellation: missing {needle!r}")
            ok = False
    if ok:
        report.append("  OK   constellation: light/dark ink, reduced motion, keys")
    return ok


def check_sky(path: Path, report: list[str]) -> bool:
    """night-sky.svg: gradient defs, bounded stars, ridge, motion guard."""
    text = path.read_text(encoding="utf-8")
    ok = True
    stars = text.count("<circle")
    if not (200 <= stars <= 1600):
        report.append(f"  FAIL night-sky.svg: {stars} stars (expected bounded)")
        ok = False
    else:
        report.append(f"OK   night-sky.svg: {stars} stars, bounded")
    for need in ('id="sky"', 'id="nb"', 'id="gr"', 'prefers-reduced-motion'):
        if need not in text:
            report.append(f"  FAIL night-sky.svg: missing {need}")
            ok = False
    if text.count("<path") < 1:
        report.append("  FAIL night-sky.svg: no horizon ridge")
        ok = False
    return ok


CHECKS = {
    "contrib-heatmap.svg": check_heatmap,
    "bakkarranna-ascii.svg": check_ascii,
    "info-card.svg": check_card,
    "skills.svg": check_skills,
    "stats-strip.svg": check_stats,
    "contribution-city.svg": check_city,
    "projects.svg": check_projects,
    "constellation.svg": check_constellation,
    "night-sky.svg": check_sky,
}


def main() -> int:
    report: list[str] = ["SVG verification (structural, no browser)"]
    all_ok = True
    for name, checker in CHECKS.items():
        path = REPO / name
        if not path.exists():
            report.append(f"  FAIL {name}: file missing")
            all_ok = False
            continue
        try:
            ElementTree.parse(path)
            report.append(f"OK   {name}: well-formed XML")
        except ElementTree.ParseError as exc:
            report.append(f"  FAIL {name}: {exc}")
            all_ok = False
            continue
        all_ok = checker(path, report) and all_ok
        all_ok = check_no_scripts(path, report) and all_ok
    report.append("RESULT: " + ("PASS" if all_ok else "FAIL"))

    print("\n".join(report))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
