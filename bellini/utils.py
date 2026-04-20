from __future__ import annotations

from datetime import datetime
from typing import Iterable

DAY_ORDER = ["M", "T", "W", "R", "F", "S", "U"]
DAY_MAP = {
    "M": "Monday",
    "T": "Tuesday",
    "W": "Wednesday",
    "R": "Thursday",
    "F": "Friday",
    "S": "Saturday",
    "U": "Sunday",
}


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and str(value) == "nan":
        return ""
    return str(value).strip()


def normalize_numeric_string(value: object) -> str:
    text = normalize_text(value)
    if text.endswith(".0"):
        text = text[:-2]
    return text


def parse_enrollment(value: object) -> int:
    text = normalize_numeric_string(value)
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def parse_time_range(time_range: str):
    text = normalize_text(time_range)
    if not text or text.upper() == "TBA":
        return None, None
    if "-" not in text:
        return None, None
    left, right = [part.strip() for part in text.split("-", 1)]
    formats = ["%I:%M %p", "%I %p"]
    for fmt in formats:
        try:
            start = datetime.strptime(left, fmt).time()
            end = datetime.strptime(right, fmt).time()
            return start, end
        except ValueError:
            continue
    return None, None


def meeting_day_letters(days: str) -> list[str]:
    text = normalize_text(days).upper()
    return [letter for letter in DAY_ORDER if letter in text]


def overlap(start1, end1, start2, end2) -> bool:
    if not all([start1, end1, start2, end2]):
        return False
    return start1 < end2 and start2 < end1


def shared_days(days1: str, days2: str) -> set[str]:
    return set(meeting_day_letters(days1)).intersection(meeting_day_letters(days2))


def safe_contains_any(text: str, keywords: Iterable[str]) -> bool:
    source = normalize_text(text).lower()
    return any(keyword.lower() in source for keyword in keywords if keyword.strip())
