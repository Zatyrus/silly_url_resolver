"""Quiet clock helpers; no terminal output or network work in the wait loop."""

import math
import time
from datetime import datetime, timezone

NS = 1_000_000_000


def positive(value):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Use a positive number of seconds, no more than 365 days.") from exc
    if not math.isfinite(number) or not 0 < number <= 31_536_000:
        raise ValueError("Use a positive number of seconds, no more than 365 days.")
    return number


def parse_at(text):
    if not isinstance(text, str):
        raise ValueError("Use an ISO timestamp string with a UTC offset.")
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ValueError("Use an ISO timestamp, for example 2030-01-01T12:00:00+01:00.") from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("The timestamp needs Z (UTC) or an offset such as +01:00.")
    try:
        delta = value.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
    except OverflowError as exc:
        raise ValueError("The timestamp falls outside the supported calendar range.") from exc
    return (delta.days * 86400 + delta.seconds) * NS + delta.microseconds * 1000


def map_deadline(wall_ns):
    brackets = []
    for _ in range(7):
        before = time.monotonic_ns()
        wall = time.time_ns()
        after = time.monotonic_ns()
        brackets.append((after - before, (before + after) // 2 + wall_ns - wall))
    return min(brackets)[1]


def final_deadline(wall_ns):
    # Follow wall-clock corrections until the final 50 ms; then use monotonic time.
    while True:
        deadline = map_deadline(wall_ns)
        left = deadline - time.monotonic_ns()
        if left <= 50_000_000:
            return deadline
        time.sleep(min(0.25, (left - 50_000_000) / NS))


def wait_until(deadline, spin_ns):
    clock = time.monotonic_ns
    while (left := deadline - clock()) > spin_ns:
        time.sleep((left - spin_ns) / NS)
    while clock() < deadline:
        pass
