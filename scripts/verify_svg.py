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

    begins = [float(m) for m in re.findall(r"animation-delay:([\d.]+)s", text)]
    if len(begins) < expected_days:
        report.append(f"  FAIL heatmap: only {len(begins)} reveal animations")
        ok = False
    else:
        report.append(
            f"  OK   heatmap: {len(begins)} CSS reveals, stagger 0..{max(begins):.2f}s"
        )

    if re.findall(r"<animate|<set\b|begin=", text):
        report.append(
            "  FAIL heatmap: SMIL reveal left behind -- camo freezes it, use "
            "animation-delay so prefers-reduced-motion still applies"
        )
        ok = False

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

    delays = re.findall(r"animation-delay:([\d.]+)s", text)
    if delays:
        values = [float(d) for d in delays]
        report.append(f"  OK   card: {len(values)} reveals, 0..{max(values):.2f}s")
    elif "opacity:1" not in text:
        report.append("  FAIL card: neither animated nor a frozen finished frame")
        ok = False
    else:
        report.append("  OK   card: static finished frame")
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

    # Only the day plots ramp, and the "now" marker runs its own class, so
    # the ramp is exactly one delayed element per plotted day. Both the tile
    # (zero-activity day) and tower (active day) classes are counted: a panel
    # that gave only its buildings a delay snaps a third of the calendar in on
    # frame one while its neighbours ramp, which is exactly the bug this
    # catches. Order is the generator's painter order (back to front), not a
    # sort, so the check asserts coverage and span, never sortedness.
    undelayed = [
        cls
        for cls in ("tile", "tw")
        if sum(1 for d in _element_delays(text).get(cls, []) if d is None)
    ]
    delays = sorted(
        d
        for cls in ("tile", "tw")
        for d in _element_delays(text).get(cls, [])
        if d is not None
    )
    if undelayed:
        report.append(f"  FAIL city: day plots with no delay: {', '.join(undelayed)}")
        ok = False
    elif len(delays) != len(days):
        report.append(
            f"  FAIL city: {len(delays)} ramped day plots, expected {len(days)}"
        )
        ok = False
    else:
        span = max(delays) - min(delays)
        if span > MAX_REVEAL_SPAN:
            report.append(
                f"  FAIL city: stagger spans {span:.2f}s, past the "
                f"{MAX_REVEAL_SPAN:.2f}s a reader waits"
            )
            ok = False
        else:
            report.append(
                f"  OK   city: painter's-order stagger {min(delays):.2f}"
                f"..{max(delays):.2f}s over {len(delays)} day plots"
            )

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


def _ink_rules(section: str) -> dict[str, str]:
    """`.class{prop:value}` rules in one CSS section, selectors split on ','.

    Only rules that paint (fill/stroke/stop-color) count, so animation and
    grouping rules (.kpi{animation:...}, .line{opacity:0}) are not mistaken
    for missing dark ink. Grouped selectors expand, so a class dropped from a
    group on one side still shows up as missing on the other.
    """
    rules: dict[str, str] = {}
    for selectors, decl in re.findall(r"([^{}@\n][^{}]*)\{([^{}]*)\}", section):
        if "@" in selectors or not re.search(r"\b(?:fill|stroke|stop-color):", decl):
            continue
        for sel in selectors.split(","):
            sel = sel.strip()
            if sel.startswith("."):
                rules[sel[1:]] = decl.strip()
    return rules


def _dark_block(body: str) -> str:
    """The rules inside @media (prefers-color-scheme: dark){...}."""
    m = re.search(
        r"@media \(prefers-color-scheme: dark\)\{(.*?)\}\s*(?=@media|$)", body, re.S
    )
    return m.group(1) if m else ""


# A reveal that takes longer than this reads as art stuck mid-arrival. Both
# long ramps in the repo stay under 3.3s, so this leaves headroom without
# letting a panel creep into "wait, is it frozen?" territory.
MAX_REVEAL_SPAN = 4.0


def _animation_rules(body: str) -> list[tuple[str, str]]:
    """(class, decl) for every CSS rule that runs a named animation.

    Splits grouped selectors the way _ink_rules does, so a class dropped from
    a group on one side still shows up. `animation:none` is skipped, so the
    prefers-reduced-motion override does not make a static class look alive.
    Grouped selectors repeat the decl per class, which keeps a grouped reveal
    (`.kpi,.bar,.chart-label{animation:...}`) honest when it is read back.
    """
    rules: list[tuple[str, str]] = []
    for selectors, decl in re.findall(r"([^{}@\n][^{}]*)\{([^{}]*)\}", body):
        if "@" in selectors:
            continue
        if not re.search(r"\banimation:\s*(?!none\b)\w+", decl):
            continue
        for sel in selectors.split(","):
            sel = sel.strip()
            if sel.startswith("."):
                rules.append((sel[1:], decl))
    return rules


def _animated_classes(body: str) -> set[str]:
    """Classes that actually run an animation, read off the CSS rules."""
    return {cls for cls, _ in _animation_rules(body)}


def _balanced_block(css: str, open_at: int) -> str:
    """Body of the rule whose '{' sits at open_at, brace-matched.

    Stopping at the first '}' truncates an at-rule holding more than one
    rule -- constellation's two-class collapse -- which drops classes out of
    the check and lets them stay hidden. Braces inside @keyframes stop rules
    are counted the same way, so the walk stays correct in there too.
    """
    depth = 0
    for i in range(open_at, len(css)):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return css[open_at + 1 : i]
    return ""


def _keyframe_end_opacity(body: str) -> dict[str, float]:
    """Keyframes name -> the opacity its terminal stop lands on.

    A reveal (`from{opacity:0}to{opacity:1}`) ends at its `to` stop; a
    ping-pong twinkle (`0%,100%{opacity:.25}50%{opacity:1}`) ends on its
    `100%` stop. Those are the two shapes in this repo, and they are exactly
    the frame prefers-reduced-motion must freeze on: the one the animation
    would have finished on.
    """
    ends: dict[str, float] = {}
    for m in re.finditer(r"@keyframes\s+([\w-]+)\s*\{", body):
        inner = _balanced_block(body, m.end() - 1)
        for pattern in (
            r"\bto\s*\{([^}]*)\}",
            r"\b100%\s*\{([^}]*)\}",
            r"\bfrom\s*\{([^}]*)\}",
        ):
            stop = re.search(pattern, inner)
            if stop:
                op = re.search(r"\bopacity:\s*([\d.]+)", stop.group(1))
                if op:
                    ends[m.group(1)] = float(op.group(1))
                break
    return ends


def _ink_selectors(section: str) -> set[str]:
    """Selectors in one CSS section that paint: .class rules and bare tags.

    Built the way _ink_rules splits them, so a class dropped from a grouped
    selector on one side counts as unpainted there. Bare tags count as well:
    bakkarrarna-ascii.svg inks every glyph through `text{fill:...}`, so the
    per-text fill attributes it also carries are dead weight rather than live
    fixed ink, and only a tag rule can say so.
    """
    out: set[str] = set()
    for selectors, decl in re.findall(r"([^{}@\n][^{}]*)\{([^{}]*)\}", section):
        if "@" in selectors or not re.search(r"\b(?:fill|stroke|stop-color):", decl):
            continue
        for sel in selectors.split(","):
            sel = sel.strip()
            if sel.startswith("."):
                out.add(sel)
            elif sel and sel[0].isalpha():
                out.add(sel)
    return out


def _hard_ink_elements(markup: str) -> list[tuple[str, str]]:
    """(tag, attrs) for every element carrying a hard-coded fill/stroke.

    Presentation attributes and inline style hexes both count: ink living on
    the element instead of a class is the fixed-ink bug waiting to happen.
    The caller decides whether that ink is live or already overridden.
    """
    out: list[tuple[str, str]] = []
    for m in re.finditer(r'<([a-z][\w:-]*)((?:\s+[\w:-]+="[^"]*")*)\s*/?>', markup):
        attrs = m.group(2)
        if re.search(r'(?:fill|stroke)="#[0-9a-fA-F]{3,8}"', attrs) or re.search(
            r'style="[^"]*(?:fill|stroke):#', attrs
        ):
            out.append((m.group(1), attrs))
    return out


# A start tag with only simple quoted attributes; enough to read class/style.
_TAG_ATTRS = r"<[a-z]+((?:\s+[\w:-]+=\"[^\"]*\")*)\s*/?>"


def _element_delays(text: str) -> dict[str, list[float | None]]:
    """Per class, the inline animation-delay of every element carrying it.

    Walks the markup tag by tag instead of matching one fixed attribute order,
    so `style` before `class` (or attributes in between) still counts. A None
    entry means "this element runs the class but got no delay of its own" --
    exactly the gap that makes a third of a panel snap in on the first frame.
    """
    markup = re.sub(r"<style>.*?</style>", "", text, flags=re.S)
    ramp: dict[str, list[float | None]] = {}
    for attrs in re.findall(_TAG_ATTRS, markup):
        classes = re.search(r'class="([\w -]+)"', attrs)
        if not classes:
            continue
        delay = re.search(r"animation-delay:([\d.]+)s", attrs)
        for cls in classes.group(1).split():
            ramp.setdefault(cls, []).append(float(delay.group(1)) if delay else None)
    return ramp


def check_theme_contract(path: Path, report: list[str]) -> bool:
    """The animated-theming contract contrib-heatmap.svg sets for every panel.

    Four things, all of which had to hold in contrib-heatmap.svg before it read
    as one piece of art on both themes:

      1. every element inks from a class, never a hard-coded fill/stroke --
         the bug this sweep exists to catch, since one element keeping its
         light hex reads as a hole punched in the art on dark;
      2. every painting class has a full prefers-color-scheme re-ink;
      3. the reveal is CSS @keyframes on a per-element animation-delay ramp,
         never SMIL, because camo strips scripts and reduced-motion only
         reaches CSS;
      4. every animated element carries a delay of its own. The count is
         derived from the markup, never restated here, so a panel that grows
         elements cannot quietly fall out of contract: info-card.svg and
         stats-strip.svg each ramped only some of their art and landed the
         rest on frame one.
      5. prefers-reduced-motion collapses to the finished frame for every
         animated class, so the panel never stays hidden for someone who
         asked for less motion.
    """
    name = path.name
    text = path.read_text(encoding="utf-8")
    ok = True

    def fail(msg: str) -> None:
        nonlocal ok
        report.append(f"  FAIL {name}: {msg}")
        ok = False

    style = re.search(r"<style>(.*?)</style>", text, re.S)
    if not style:
        fail("no <style> block to ink from")
        return ok
    body = style.group(1)

    if body.count("{") != body.count("}"):
        fail("unbalanced braces in <style>")

    # 1. no hard-coded ink left on an element the renderer will actually paint.
    #    A presentation attribute that no CSS rule touches is dead weight: it
    #    renders the light value under both themes, so it counts as fixed ink.
    #    An attribute a class or tag rule already re-inks for both themes is
    #    harmless -- CSS beats presentation attributes, so the rule wins and
    #    the paint follows the theme. Judging the ink the element renders is
    #    what keeps bakkarrarna-ascii.svg's per-text fill attributes (its ink
    #    really comes from `text{fill:...}` on both sides) from failing a
    #    panel that is in fact fully themed.
    markup = re.sub(r"<style>.*?</style>", "", text, flags=re.S)
    cut = body.find("@media (prefers-color-scheme: dark)")
    light_paints = _ink_selectors(body[:cut] if cut >= 0 else body)
    dark_paints = _ink_selectors(_dark_block(body))
    fixed = []
    for tag, attrs in _hard_ink_elements(markup):
        classes = re.search(r'class="([\w -]+)"', attrs)
        keys = {tag}
        keys.update(f".{c}" for c in (classes.group(1).split() if classes else []))
        if not (keys & light_paints) or not (keys & dark_paints):
            fixed.append(f"<{tag}")
    if fixed:
        fail(
            f"{len(fixed)} element(s) carry fixed ink that cannot re-ink: "
            f"{fixed[0]} -- no CSS rule paints them for both themes"
        )

    # 2. light/dark ink pair
    if cut < 0:
        fail("no prefers-color-scheme re-ink block")
    else:
        light = _ink_rules(body[:cut])
        dark = _ink_rules(_dark_block(body))
        missing = sorted(c for c in light if c not in dark)
        if missing:
            fail(f"ink classes with no dark override: {', '.join(missing)}")
        elif light:
            report.append(
                f"  OK   {name}: {len(light)} ink classes, all re-inked for dark"
            )

    # 3. CSS-only keyframes reveal, and a real delay ramp
    if re.search(r"<animate|<animateTransform|<set\b|begin=", markup):
        fail("SMIL reveal left behind -- CSS only, SMIL ignores prefers-reduced-motion")
    animated = _animated_classes(body)
    if animated:
        if "@keyframes" not in body:
            fail("animation: rules with no @keyframes to run")

        ramp = _element_delays(text)
        landed = [
            d for cls, ds in ramp.items() if cls in animated for d in ds if d is not None
        ]
        # Any element running an animated class without a delay of its own.
        gaps = sorted(
            cls
            for cls in animated
            if any(d is None for d in ramp.get(cls, []))
        )
        if not landed:
            fail("no element carries an animation-delay -- the reveal never runs")
        elif gaps:
            counts = ", ".join(
                f".{cls} ({sum(d is None for d in ramp[cls])} of {len(ramp[cls])})"
                for cls in gaps
            )
            fail(
                f"animated elements with no delay of their own: {counts} -- "
                "they land on the first frame instead of ramping"
            )
        else:
            span = max(landed)
            report.append(
                f"  OK   {name}: {len(landed)} reveals across "
                f"{len(animated)} animated classes, 0..{span:.2f}s, "
                "every animated element carries its own delay"
            )
            if span > MAX_REVEAL_SPAN:
                fail(
                    f"reveal spans {span:.2f}s, past the {MAX_REVEAL_SPAN:.2f}s "
                    "a reader waits for art to arrive"
                )

        # 4. reduced motion shows the finished frame
        m = re.search(r"@media \(prefers-reduced-motion: reduce\)\{", body)
        if not m:
            fail("no prefers-reduced-motion collapse -- the panel stays hidden")
        else:
            rules: dict[str, str] = {}
            for selectors, decl in re.findall(
                r"([^\{\}@\n][^\{\}]*)\{([^\{\}]*)\}", _balanced_block(body, m.end() - 1)
            ):
                for sel in selectors.split(","):
                    sel = sel.strip()
                    if sel.startswith(".") and "animation" in decl:
                        rules[sel[1:]] = decl
            hidden = sorted(animated - set(rules))
            if hidden:
                fail(f"reduced motion leaves animated classes hidden: {', '.join(hidden)}")
            else:
                # The collapse has to land each class on the frame its own
                # keyframes end at: a reveal freezes at opacity 1, a twinkle
                # at its dim stop. Freezing a twinkle bright reads as art
                # stuck mid-blink, so the frozen value must match the
                # terminal stop, not just be a visible number.
                terminal = _keyframe_end_opacity(body)
                names = {
                    cls: re.search(r"\banimation:\s*(\w+)", decl).group(1)
                    for cls, decl in _animation_rules(body)
                }
                wrong = []
                for cls in sorted(animated):
                    need = terminal.get(names.get(cls, ""), 1.0)
                    got = re.search(r"\bopacity:\s*([\d.]+)", rules.get(cls, ""))
                    if not got or float(got.group(1)) != round(need, 6):
                        frozen = f"opacity {got.group(1)}" if got else "no opacity"
                        wrong.append(
                            f".{cls} freezes at {frozen}, its "
                            f"{names.get(cls, '?')} keyframes end at {need:g}"
                        )
                if wrong:
                    fail(
                        "reduced motion does not show the finished frame: "
                        + "; ".join(wrong)
                    )
                else:
                    report.append(
                        f"  OK   {name}: reduced motion shows the finished frame "
                        f"for {len(animated)} animated classes"
                    )
    return ok


CHECKS = {
    "contrib-heatmap.svg": check_heatmap,
    "bakkarranna-ascii.svg": check_ascii,
    "info-card.svg": check_card,
    "skills.svg": check_skills,
    "stats-strip.svg": check_stats,
    "contribution-city.svg": check_city,
    "projects.svg": check_projects,
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
        all_ok = check_theme_contract(path, report) and all_ok
    report.append("RESULT: " + ("PASS" if all_ok else "FAIL"))

    print("\n".join(report))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
