"""Лучшие окна для итогового времени — та же логика, что на сайте."""

from datetime import datetime, timedelta, timezone
from typing import Any

from backend.src.meetings.infrastructure import CELL_MINUTES, duration_to_minutes
from backend.src.notifications.meet_emails import format_range


def parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_z(value: datetime) -> str:
    utc = value
    if utc.tzinfo is None:
        utc = utc.replace(tzinfo=timezone.utc)
    else:
        utc = utc.astimezone(timezone.utc)
    return utc.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def expand_cells(ranges: list | None) -> set[datetime]:
    cells: set[datetime] = set()
    for item in ranges or []:
        if not item or len(item) < 2:
            continue
        start = parse_iso(str(item[0])).replace(second=0, microsecond=0)
        end = parse_iso(str(item[1])).replace(second=0, microsecond=0)
        current = start
        while current <= end:
            cells.add(current)
            current += timedelta(minutes=CELL_MINUTES)
    return cells


def heatmap(slots: list | None) -> dict[datetime, int]:
    counts: dict[datetime, int] = {}
    for slot in slots or []:
        if not isinstance(slot, dict):
            continue
        for cell in expand_cells(slot.get("slots") or []):
            counts[cell] = counts.get(cell, 0) + 1
    return counts


def _is_better(
    best: dict[str, Any] | None,
    candidate: dict[str, Any],
    target_cells: int | None,
) -> bool:
    if best is None:
        return True
    if target_cells:
        best_full = best["len"] == target_cells
        cand_full = candidate["len"] == target_cells
        if cand_full != best_full:
            return cand_full
    if candidate["min"] != best["min"]:
        return candidate["min"] > best["min"]
    if candidate["len"] != best["len"]:
        return candidate["len"] > best["len"]
    if candidate["sum"] != best["sum"]:
        return candidate["sum"] > best["sum"]
    return candidate["start"] < best["start"]


def suggest_windows(
    slots: list | None,
    duration: str | None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    counts = heatmap(slots)
    if not counts:
        return []
    minutes = duration_to_minutes(duration)
    target = max(1, minutes // CELL_MINUTES) if minutes else None
    cells = sorted(counts)
    ranked: list[dict[str, Any]] = []

    by_day: dict[str, list[datetime]] = {}
    for cell in cells:
        by_day.setdefault(cell.date().isoformat(), []).append(cell)

    for day_cells in by_day.values():
        day_cells.sort()
        for start in day_cells:
            window = [start]
            current = start
            max_len = target or 48
            while len(window) < max_len:
                nxt = current + timedelta(minutes=CELL_MINUTES)
                if nxt not in counts or nxt.date() != start.date():
                    break
                window.append(nxt)
                current = nxt
            people = [counts[item] for item in window]
            ranked.append(
                {
                    "start": window[0],
                    "end": window[-1],
                    "len": len(window),
                    "min": min(people),
                    "sum": sum(people),
                }
            )

    picked: list[dict[str, Any]] = []
    used: set[datetime] = set()
    while len(picked) < limit:
        best: dict[str, Any] | None = None
        for item in ranked:
            if item["start"] in used:
                continue
            if _is_better(best, item, target):
                best = item
        if best is None:
            break
        used.add(best["start"])
        display_end = best["end"] + timedelta(minutes=CELL_MINUTES)
        picked.append(
            {
                "label": format_range(best["start"], display_end),
                "people": int(best["min"]),
                "slots": [[iso_z(best["start"]), iso_z(best["end"])]],
            }
        )
    return picked
