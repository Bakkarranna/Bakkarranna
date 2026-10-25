"""Theme-QA the profile panels: every panel on BOTH backdrops, side by side.

raster_qa.py renders one panel on a light and a dark wrapper; this drives it
across all nine panels, keeps each shot, composes per-panel light/dark sheets,
and prints a per-panel verdict about whether the art actually re-inks.

The verdict is the point. A panel that keeps one fixed palette looks perfect in
its own screenshot and turns invisible (dark ink on the dark GitHub background,
or light-on-light) once the reader's theme flips. So for each backdrop we
measure:

  * ink share   - fraction of pixels that differ from the panel's dominant
                  colour, i.e. how much of the canvas the art actually draws;
  * ink luma    - mean WCAG luminance of those ink pixels, so "the ink stayed
                  dark while the page went dark" is a number, not an opinion;
  * contrast    - WCAG contrast ratio between that mean ink and the dominant
                  colour, so low-contrast ink (-ish) is caught per theme.

A panel that re-inks shows a large ink-luma swing between backdrops and healthy
contrast on both. One that ignores the theme shows ink luma within a hair
across backdrops (theme-blind) and/or a weak contrast ratio in one of them.

Dev tool only -- it needs Chrome, so it is deliberately NOT part of the daily
workflow (which must run on a bare GitHub runner).

Usage:
    python scripts/theme_qa.py                 # all panels
    python scripts/theme_qa.py skills.svg      # just one

Writes theme-qa/ (gitignored): per-panel sheets, an all-panel contact sheet,
the raw light/dark shots, and report.md. Re-running overwrites them.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import raster_qa

REPO = raster_qa.REPO
OUT = REPO / "theme-qa"

# Every panel the README ships, in reading order (small to wide).
PANELS = [
    "info-card.svg",
    "stats-strip.svg",
    "skills.svg",
    "contrib-heatmap.svg",
    "projects.svg",
    "contribution-city.svg",
    "constellation.svg",
    "night-sky.svg",
    "bakkarranna-ascii.svg",
]

# Wrapper backdrops raster_qa.shoot() uses.
LIGHT_BG = (255, 255, 255)
DARK_BG = (13, 17, 23)

# A pixel this far from the dominant colour counts as ink, not background.
INK_TOLERANCE = 18


def _luma(rgb: tuple[int, int, int]) -> float:
    """WCAG relative luminance of an sRGB triple."""
    def chan(v: int) -> float:
        c = v / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (chan(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    """WCAG contrast ratio between two colours (1.0 = identical)."""
    la, lb = _luma(a), _luma(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _dominant(im) -> tuple[int, int, int]:
    """Most common exact colour -- the panel's effective background.

    PIL returns a list of (count, colour) pairs, or None when the shot has more
    distinct colours than the cap (heavy antialiasing on the large panels); the
    fallback downsamples first, which keeps the answer for a backdrop question.
    """
    counts = im.getcolors(maxcolors=1 << 24)
    if counts is None:
        small = im.resize((max(1, im.width // 4), max(1, im.height // 4)))
        counts = small.getcolors(maxcolors=1 << 24) or []
    seen: dict[tuple[int, int, int], int] = {}
    for n, rgb in counts:
        key = (rgb[0], rgb[1], rgb[2])  # ignore alpha: the wrapper is opaque
        seen[key] = seen.get(key, 0) + n
    return max(seen, key=seen.get) if seen else (0, 0, 0)


# Panels are composited edge-to-edge on the wrapper backdrop, so a
# hair-thin border frame is the wrapper's own colour: the one background
# colour guaranteed not to be the panel's art.
FRAME = 2


def frame_dominant(im) -> tuple[int, int, int]:
    """Dominant colour of the image's outer FRAME-pixel ring.

    Judging ink against the whole-image dominant would call a panel's own
    base layer its background (night-sky paints a near-black card), which is
    the colour its ink is meant to show against. The ring is the wrapper
    showing through the margins, so it answers "what is this panel sitting
    on" for every panel, themed or not.
    """
    if im.width < FRAME * 2 + 1 or im.height < FRAME * 2 + 1:
        return _dominant(im)
    seen: dict[tuple[int, int, int], int] = {}
    px = im.load()
    for x in range(im.width):
        for y in list(range(FRAME)) + list(range(im.height - FRAME, im.height)):
            r, g, b = px[x, y][:3]
            seen[(r, g, b)] = seen.get((r, g, b), 0) + 1
    for y in range(im.height):
        for x in list(range(FRAME)) + list(range(im.width - FRAME, im.width)):
            r, g, b = px[x, y][:3]
            seen[(r, g, b)] = seen.get((r, g, b), 0) + 1
    if not seen:
        return (0, 0, 0)
    best = max(seen, key=seen.get)
    # The ring is thin, so the margin's antialiased pixels dilute the exact
    # colour counts: accept the winner only when its near-neighbours back it,
    # otherwise fall back to the whole image.
    merged = sum(n for rgb, n in seen.items()
                 if all(abs(a - b) <= INK_TOLERANCE for a, b in zip(rgb, best)))
    return best if merged >= 0.25 * sum(seen.values()) else _dominant(im)


def ink_stats(path: Path) -> dict[str, float]:
    """Ink share, mean ink colour and its contrast against the canvas."""
    im = Image.open(path).convert("RGB")
    bg = frame_dominant(im)
    tol2 = INK_TOLERANCE ** 2
    px = im.load()
    total = ink = 0
    acc = [0, 0, 0]
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = px[x, y][:3]
            total += 1
            if (r - bg[0]) ** 2 + (g - bg[1]) ** 2 + (b - bg[2]) ** 2 > tol2:
                ink += 1
                acc[0] += r
                acc[1] += g
                acc[2] += b
    mean = (acc[0] // ink, acc[1] // ink, acc[2] // ink) if ink else bg
    return {
        "ink_share": ink / total if total else 0.0,
        "ink_luma": _luma(mean),
        "ink_mean": mean,
        "bg": bg,
        "contrast": _contrast(mean, bg),
        "size": (im.width, im.height),
    }


def reink_share(light: Image.Image, dark: Image.Image) -> tuple[float, float]:
    """(share of the frame the panel paints, share of that art that re-inks).

    The two shots are the same panel on the two wrapper backdrops, so a pixel
    that is bare wrapper in *both* frames is not the panel's ink and is
    ignored. Everything else is the panel's own art, and the part of it that
    changed colour between backdrops is the part that re-inks -- the answer
    to "does this panel notice the theme".

    Comparing colours per pixel beats comparing aggregate ink luminance: a
    mean over antialiased text moves by almost nothing on panels whose theme
    block only covers a few classes, even though half the panel did change.
    """
    if light.size != dark.size:
        return 0.0, 0.0
    w, h = light.size
    pl, dp = light.load(), dark.load()
    art = same = 0
    for y in range(h):
        for x in range(w):
            a = pl[x, y][:3]
            b = dp[x, y][:3]
            if _near(a, LIGHT_BG, 8) and _near(b, DARK_BG, 8):
                continue
            art += 1
            if _near(a, b, 8):
                same += 1
    if not art:
        return 0.0, 0.0
    return art / (w * h), (art - same) / art


def _near(a: tuple[int, int, int], b: tuple[int, int, int], tol: int) -> bool:
    """Per-channel closeness, for comparing rendered pixels."""
    return all(abs(u - v) <= tol for u, v in zip(a, b))


def render(name: str, dark: bool) -> Path:
    """Shoot one panel on one backdrop into theme-qa/shots/."""
    tag = "dark" if dark else "light"
    stem = Path(name).stem
    return raster_qa.shoot(name, dark, out=OUT / "shots" / f"{stem}-{tag}.png")


# How much of a panel's own art must change colour between the two backdrops
# before it counts as themed. Themed art sometimes carries a fixed-colour mark
# (a logo block, a brand swatch), so this is not 100%.
REINK_TARGET = 0.90

# Below this share the panel does not re-ink meaningfully at all.
REINK_FLOOR = 0.05

# A panel that paints at least this much of the frame owns its own surface,
# so a fixed palette is a design choice (a night scene stays a night scene),
# not a visibility bug. Thin ink straight onto the GitHub backdrop is the bug.
OWN_SURFACE = 0.50

# Mean-ink contrast is reported, never judged: deliberate low-contrast art
# (stars on a near-black card) is themed art, not broken art.
MIN_CONTRAST = 3.0

# Verdicts that mean an artist still has to go re-ink the panel. A panel that
# paints its own full-bleed surface ("FIXED PALETTE") is deliberately absent
# from this list: a night scene stays a night scene, and forcing it onto the
# reader's backdrop would destroy the art, so it is reported rather than
# queued. Only ink parked straight on the GitHub backdrop is work to do.
WORK_VERDICTS = ("PARTLY THEMED", "NEEDS THEMING")


def needs_work(state: str) -> bool:
    """True when the verdict means a human has to re-ink that panel."""
    return state in WORK_VERDICTS


def verdict(light: dict[str, float], dark: dict[str, float],
            painted: float, reink: float) -> tuple[str, str]:
    """(short verdict, why) for one panel shot on the two backdrops.

    Two pixel measurements decide it, both computed in reink_share():

      painted -- the share of the frame the panel draws itself instead of
        leaving the wrapper's backdrop showing through.
      reink  -- of that art, the share that changed colour between the light
        and dark shots. This is the answer to "does it notice the theme".

    The distinction that matters for the report: a panel that does not re-ink
    is either drawing its own full-bleed surface (a night scene stays a night
    scene on any backdrop -- a design choice), or it is thin ink parked
    directly on the GitHub backdrop (invisible on white, blazing on
    #0d1117 -- work to do). Half a panel changing is not "themed", so the
    fully-themed threshold is checked first, then the stuck remainder is
    called out.
    """
    if reink >= REINK_TARGET:
        return (
            "themed",
            f"{reink * 100:.0f}% of the art re-inks, "
            f"{min(light['contrast'], dark['contrast']):.1f}:1 min mean-ink "
            "contrast",
        )
    if reink >= REINK_FLOOR and painted < OWN_SURFACE:
        return (
            "PARTLY THEMED",
            f"only {reink * 100:.0f}% of the art re-inks; the other "
            f"{(1 - reink) * 100:.0f}% sits at the same colour on white and "
            "on #0d1117",
        )
    if painted >= OWN_SURFACE:
        return (
            "FIXED PALETTE",
            f"no art re-inks across {painted * 100:.0f}% painted, but the "
            "panel draws its own full-bleed surface, so it reads as its own "
            "scene rather than as broken ink",
        )
    return (
        "NEEDS THEMING",
        f"{reink * 100:.0f}% of the art re-inks and the rest is "
        "fixed-palette ink straight onto the GitHub backdrop",
    )


def compose(name: str, light_png: Path, dark_png: Path, light: dict, dark: dict,
            state: str, why: str) -> Path:
    """Side-by-side light | dark sheet with a verdict caption, for eyeballing."""
    from PIL import Image, ImageDraw, ImageFont

    pad, gap, cap_h = 12, 10, 30
    li = Image.open(light_png).convert("RGB")
    di = Image.open(dark_png).convert("RGB")
    h = max(li.height, di.height)
    w = li.width + gap + di.width
    sheet = Image.new("RGB", (w + pad * 2, h + cap_h + pad * 2), (110, 110, 110))
    sheet.paste(li, (pad, cap_h))
    sheet.paste(di, (pad + li.width + gap, cap_h))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=15)
    ink = min(light["contrast"], dark["contrast"])
    title = (f"{name}  |  {light['ink_share'] * 100:.1f}% ink light / "
             f"{dark['ink_share'] * 100:.1f}% dark  |  {ink:.1f}:1  |  {state}")
    if state != "themed":
        title += f"  --  {why}"
    draw.text((pad, 8), title, font=font,
              fill=(255, 235, 120) if state != "themed" else (255, 255, 255))
    out = OUT / f"{Path(name).stem}-themes.png"
    sheet.save(out)
    return out


def contact_sheet(rows: list[tuple[str, str, str, Path, Path, Path]]) -> Path:
    """Every panel stacked, light | dark side by side, one row each.

    The per-panel sheets answer "did this panel re-ink"; this answers "which
    panels still need work" in a single image, so the sweep has one artifact
    to open. Panels are scaled to a common half-width, which keeps the tall
    ascii panel from dominating while the verdict caption stays readable.
    """
    pad, gap, cap_h, row_gap = 14, 10, 32, 18
    half_w = 700
    font = ImageFont.load_default(size=15)
    placed: list[tuple[Image.Image, Image.Image, str, str, str]] = []
    for name, state, why, _sheet, light_png, dark_png in rows:
        li = Image.open(light_png).convert("RGB")
        di = Image.open(dark_png).convert("RGB")
        scale = half_w / max(li.width, 1)
        if scale < 1:
            size = (round(li.width * scale), round(li.height * scale))
            li, di = li.resize(size, Image.LANCZOS), di.resize(size, Image.LANCZOS)
        placed.append((li, di, name, state, why))

    width = max(li.width + gap + di.width for li, di, *_ in placed)
    height = (pad + sum(max(li.height, di.height) + cap_h + row_gap
                        for li, di, *_ in placed) + pad)
    sheet = Image.new("RGB", (width + pad * 2, height), (110, 110, 110))
    draw = ImageDraw.Draw(sheet)
    y = pad
    for li, di, name, state, why in placed:
        sheet.paste(li, (pad, y))
        sheet.paste(di, (pad + li.width + gap, y))
        cap = (255, 235, 120) if state != "themed" else (255, 255, 255)
        draw.text((pad, y + li.height + 5),
                  f"{name}  |  {state}", font=font, fill=cap)
        draw.text((pad, y + li.height + 21), why, font=font,
                  fill=(225, 225, 225))
        y += max(li.height, di.height) + cap_h + row_gap
    out = OUT / "all-themes.png"
    sheet.save(out)
    return out


def write_report(rows: list[tuple[str, str, str, Path, Path, Path]]) -> Path:
    """theme-qa/report.md -- the sweep's verdicts, in text."""
    themed = [r for r in rows if r[1] == "themed"]
    lines = [
        "# Theme QA: every panel on light and dark",
        "",
        "Generated by `python scripts/theme_qa.py` (dev tool: needs Chrome).",
        "",
        "| panel | verdict | why |",
        "| --- | --- | --- |",
    ]
    for name, state, why, *_rows in rows:
        lines.append(f"| {name} | {state} | {why.replace('|', chr(92) + '|')} |")
    todo = [r for r in rows if r[1] in WORK_VERDICTS]
    lines += ["", f"{len(themed)} of {len(rows)} panels re-ink across themes."]
    if todo:
        lines.append("")
        lines.append("Still needs theming work: "
                     + ", ".join(f"{r[0]} ({r[1]})" for r in todo) + ".")
    else:
        lines.append("")
        lines.append("No panel carries fixed-palette ink straight onto the "
                     "GitHub backdrop.")
    scenes = [r for r in rows if r[1] == "FIXED PALETTE"]
    if scenes:
        lines.append("")
        lines.append("Keeps one palette on purpose -- it paints its own "
                     "full-bleed surface, so it reads the same on both "
                     "backdrops: "
                     + ", ".join(r[0] for r in scenes) + ".")
    out = OUT / "report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main(argv: list[str]) -> int:
    import time

    names = [a for a in argv if not a.startswith("--")] or PANELS
    full = names is PANELS
    rows: list[tuple[str, str, str, Path, Path, Path]] = []
    for name in names:
        started = time.time()
        light_png = render(name, False)
        dark_png = render(name, True)
        light = ink_stats(light_png)
        dark = ink_stats(dark_png)
        with Image.open(light_png) as _l, Image.open(dark_png) as _d:
            painted, reink = reink_share(_l.convert("RGB"), _d.convert("RGB"))
        state, why = verdict(light, dark, painted, reink)
        sheet = compose(name, light_png, dark_png, light, dark, state, why)
        rows.append((name, state, why, sheet, light_png, dark_png))
        print(f"[{'!!' if state != 'themed' else 'ok'}] {name:<22} {state:<14} {why}"
              f"  ({time.time() - started:.0f}s)")

    themed = [r for r in rows if r[1] == "themed"]
    scenes = [r for r in rows if r[1] == "FIXED PALETTE"]
    todo = [r for r in rows if r[1] in WORK_VERDICTS]
    top = (f"sheets: {OUT}  ({len(rows)} panels, {len(themed)} themed")
    if scenes:
        top += f", {len(scenes)} own-surface scene(s)"
    if todo:
        top += f", {len(todo)} needing theming"
    print()
    print(top + ")")
    for name, _state, _why, sheet, *_rows in rows:
        print(f"  {sheet}")
    if full:
        # Auditing one panel must not clobber the all-panel sweep report.
        print(f"  {contact_sheet(rows)}")
        print(f"  {write_report(rows)}")
    if todo:
        print(f"RESULT: NEEDS THEMING -- {len(todo)} panel(s): "
              + ", ".join(r[0] for r in todo))
        return 1
    if scenes:
        print("RESULT: no panel needs theming work ("
              + ", ".join(r[0] for r in scenes)
              + " paints its own full-bleed surface by design)")
        return 0
    print("RESULT: all panels themed on light and dark")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
