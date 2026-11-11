"""One dispatch's timestamps. Call as_dict() for JSON-friendly output.

Command return means local send/command completion, not target HTTP success,
render completion, or proof that a person has seen the page.
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CallResult:
    target_wall_ns: int
    deadline_monotonic_ns: int
    dispatch_ns: int
    command_return_ns: int
    mode: str = "navigate"
    transport: str = "sse"

    def as_dict(self):
        result = asdict(self)
        result["dispatch_lateness_ms"] = (self.dispatch_ns - self.deadline_monotonic_ns) / 1e6
        result["command_return_lateness_ms"] = (
            self.command_return_ns - self.deadline_monotonic_ns
        ) / 1e6
        return result
