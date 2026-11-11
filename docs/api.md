# Python API

Use the top-level imports; browser, timing and UI subpackages are implementation
details. The distribution is named `timed-url-caller`, while the Python import
uses underscores: `timed_url_caller`.

## Schedule and run

```python
from timed_url_caller import Schedule, TimedBrowserCaller

if __name__ == "__main__":
    caller = TimedBrowserCaller(
        "https://example.com/",
        Schedule.after(20, spin_ms=2, max_late_ms=None, primed_seconds=10),
        mode="refresh",
        browser_url="http://127.0.0.1:9222",
    )
    result = caller.run()
    print(result.as_dict())
```

Start the dedicated browser first for this refresh example. For ordinary
navigation, use `mode="navigate"` and omit `browser_url`.

| Object or argument | Meaning |
|---|---|
| `Schedule.after(seconds, **options)` | Future time relative to configuration |
| `Schedule.at(text, **options)` | ISO timestamp with `Z` or UTC offset |
| `spin_ms=2` | Final busy wait; accepted range 0–50 ms |
| `max_late_ms=None` | Best-effort; a nonnegative number enables a cutoff |
| `primed_seconds=10` | Spinner interval, once preparation is complete |
| `TimedBrowserCaller(url, schedule, ...)` | One-use workflow configuration |
| `mode="navigate"` | Choose `navigate` or `refresh` |
| `browser_url=None` | Optional local CDP endpoint; required for refresh |
| `progress=True` | Separate progress process; use a main guard |
| `force_terminal=False` | Force animated terminal output if captured |
| `run()` | Prepare, wait, request once, disconnect; returns `CallResult` |

Use each caller instance from a single thread. A caller instance can only run
once, including after a failed attempt. Create a
new instance and future schedule to try again. There are no automatic retries.
Validation and preparation happen before the timing-critical callback. The
`opener` and `controlled_tab` parameters support internal harness injection;
ordinary applications should use the documented browser selection above.

## Result and errors

`CallResult(target_wall_ns, deadline_monotonic_ns, dispatch_ns, command_return_ns,
mode="navigate", transport="sse")` retains its four-argument constructor.
`CallResult.as_dict()` returns JSON-friendly values:

| Field | Meaning |
|---|---|
| `target_wall_ns` | Requested UTC epoch time in nanoseconds |
| `deadline_monotonic_ns` | Deadline mapped to the local monotonic clock |
| `dispatch_ns` | Start of the prepared dispatch callback |
| `command_return_ns` | Callback return, not page-load completion |
| `dispatch_lateness_ms` | Dispatch start minus deadline, in ms |
| `command_return_lateness_ms` | Callback return minus deadline, in ms |
| `mode`, `transport` | Navigate/refresh and SSE/CDP |

Do not compare monotonic timestamps between different computers. Handle
`ValueError` for invalid configuration, `TimeoutError` for missed preparation or
strict lateness, and `RuntimeError` for browser or delivery failures. Catch
`KeyboardInterrupt` if your application handles cancellation. Never treat a
successful result as proof of HTTP success or visual readiness.

## Independent mock server

```python
import threading
from url_caller_demo import DemoServer

with DemoServer(port=0) as server:
    worker = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    worker.start()
    try:
        print(server.url)  # http://127.0.0.1:<available-port>/
        # Run local checks here while the server is alive.
    finally:
        server.shutdown()
        worker.join()
```

`port=8765` is the default. `cache_assets=True` permits JS/CSS caching;
`status_code=503` serves an error-status document for refresh tests. Supported
statuses are 200, 403, 404, 429, 500 and 503. The server binds only to loopback and
accepts its exact numeric host address. It imports no caller code.

## Notebooks and asynchronous applications

Use the notebook's subprocess pattern for connected browser work: Playwright's
synchronous API cannot run inside Jupyter's active event loop. The progress
process also needs an importable entry point. Simple default-browser embedded
use can disable progress. There is no asynchronous caller API in this release.
