"""Execute one already-prepared callback at the deadline, without retries.

Usually used through TimedBrowserCaller. max_late_ms=None means best-effort.
"""

import time

from ..result import CallResult
from .clock import final_deadline, wait_until


class Scheduler:
    def __init__(self, schedule):
        self.schedule = schedule

    def run(self, callback, *, mode="navigate", transport="sse"):
        deadline = final_deadline(self.schedule.target_wall_ns)
        wait_until(deadline, int(self.schedule.spin_ms * 1e6))
        started = time.monotonic_ns()
        limit = self.schedule.max_late_ms
        if limit is not None and started - deadline > limit * 1e6:
            raise TimeoutError("The maximum lateness was exceeded; no action was sent.")
        callback()  # Prepared before T. No validation, UI refresh or browser startup here.
        return CallResult(
            self.schedule.target_wall_ns, deadline, started, time.monotonic_ns(), mode, transport
        )
