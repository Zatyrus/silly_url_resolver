"""Timing options. Use Schedule.after(seconds) or Schedule.at(ISO_timestamp).

Absolute times require a UTC offset. By default late dispatch is best-effort;
set max_late_ms to reject a stale action rather than execute it late.
"""

import math
import time
from dataclasses import dataclass

from .timing.clock import NS, parse_at, positive


@dataclass(frozen=True)
class Schedule:
    target_wall_ns: int
    spin_ms: float = 2.0
    max_late_ms: float | None = None
    primed_seconds: float = 10.0

    def __post_init__(self):
        if type(self.target_wall_ns) is not int:
            raise ValueError("target_wall_ns must be an integer timestamp.")
        for name in ("spin_ms", "max_late_ms", "primed_seconds"):
            value = getattr(self, name)
            if value is None and name == "max_late_ms":
                continue
            try:
                finite = math.isfinite(value)
            except (TypeError, OverflowError):
                finite = False
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not finite
                or value < 0
            ):
                raise ValueError(f"{name} must be finite and nonnegative.")
        if self.spin_ms > 50:
            raise ValueError("spin_ms must not exceed 50 milliseconds.")

    @classmethod
    def after(cls, seconds, **options):
        return cls(time.time_ns() + int(positive(str(seconds)) * NS), **options)

    @classmethod
    def at(cls, text: str, **options):
        return cls(parse_at(text), **options)
