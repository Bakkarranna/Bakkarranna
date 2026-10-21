"""Fetch real contribution data -- no token, no GraphQL.

GitHub serves your contribution calendar as public HTML at
https://github.com/users/<username>/contributions -- the same fragment the
profile page itself uses. The day cells are laid out column-major (one column
per week) and carry data-date + data-level; the exact per-day counts live in
<tool-tip for="contribution-day-component-..."> elements ("3 contributions on
..."), linked back to their cell. We also take the official headline total
from the fragment header.

Writes data/contributions.json with raw days plus derived stats (total,
current streak, longest streak, best day, monthly totals).

Run: python scripts/fetch_contributions.py
"""
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

USERNAME = "Bakkarranna"
HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = REPO / "data" / "contributions.json"
URL = f"https://github.com/users/{USERNAME}/contributions"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; profile-art/1.0)"}


def days_from_cells(soup):
    """id -> {date, level}; the fragment is column-major, so we key by cell id
    and later recover (week, weekday) from the date itself."""
    cells = {}
    for td in soup.select("td.ContributionCalendar-day"):
        data_date = td.get("data-date")
        if not data_date:
            continue
        cells[td.get("id")] = {
            "date": data_date,
            "level": int(td.get("data-level") or 0),
        }
    return cells


def counts_from_tooltips(soup) -> dict:
    """tool-tip element id -> contribution count."""
    counts = {}
    for tip in soup.select("tool-tip"):
        target = tip.get("for")
        text = tip.get_text(" ", strip=True)
        m = re.search(r"(\d+)\s+contributions?\s+on", text)
        counts[target] = int(m.group(1)) if m else 0  # "No contributions on ..."
    return counts


def official_total(soup) -> int | None:
    head = " ".join(soup.get_text(" ", strip=True).split()[:12])
    m = re.search(r"([\d,]+)\s+contributions\s+in\s+the\s+last\s+year", head)
    return int(m.group(1).replace(",", "")) if m else None


def with_grid_positions(days: list[dict]) -> None:
    """Recover week/weekday (Sunday-first) from each date."""
    start = min(date.fromisoformat(d["date"]) for d in days)
    start -= __import__("datetime").timedelta(days=(start.weekday() + 1) % 7)
    for d in days:
        dt = date.fromisoformat(d["date"])
        d["weekday"] = (dt.weekday() + 1) % 7  # Sunday = 0
        d["week"] = (dt - start).days // 7


def derive_stats(days: list[dict], total: int | None) -> dict:
    counted = sum(d["count"] for d in days)
    best = max(days, key=lambda d: d["count"]) if days else None

    current = longest = 0
    for d in days:
        current = current + 1 if d["count"] > 0 else 0
        longest = max(longest, current)

    monthly: dict[str, int] = {}
    for d in days:
        monthly[d["date"][:7]] = monthly.get(d["date"][:7], 0) + d["count"]

    return {
        "total_last_year": total if total is not None else counted,
        "counted_total": counted,
        "active_days": sum(1 for d in days if d["count"] > 0),
        "current_streak": current,
        "longest_streak": longest,
        "best_day": {"date": best["date"], "count": best["count"]} if best else None,
        "monthly": [{"month": k, "total": v} for k, v in sorted(monthly.items())],
    }


def main() -> None:
    print(f"[fetch] GET {URL}")
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cells = days_from_cells(soup)
    tips = counts_from_tooltips(soup)
    if not cells or not tips:
        raise SystemExit("no day cells parsed -- GitHub markup changed?")

    days = []
    for cell_id, info in cells.items():
        if cell_id not in tips:
            continue
        days.append({**info, "count": tips[cell_id]})
    days.sort(key=lambda d: d["date"])
    if not days:
        raise SystemExit("no days matched to tooltips -- markup changed?")

    with_grid_positions(days)
    total = official_total(soup)
    payload = {
        "username": USERNAME,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "first_day": days[0]["date"],
        "last_day": days[-1]["date"],
        "days": days,
        "stats": derive_stats(days, total),
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    s = payload["stats"]
    print(f"[fetch] {len(days)} days ({days[0]['date']} -> {days[-1]['date']}) -> {OUT}")
    print(f"[fetch] official_total={s['total_last_year']} counted={s['counted_total']} "
          f"active={s['active_days']} streak={s['current_streak']} "
          f"longest={s['longest_streak']} best={s['best_day']}")


if __name__ == "__main__":
    main()
