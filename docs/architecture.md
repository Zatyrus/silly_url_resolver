# Architecture and source layout

| Location | Responsibility |
|---|---|
| `src/timed_url_caller/caller.py` | Public workflow: prepare, wait, dispatch, disconnect |
| `src/timed_url_caller/schedule.py` | Validated time/options configuration |
| `src/timed_url_caller/result.py` | Public dispatch result |
| `src/timed_url_caller/browser/` | Default-browser bridge, connected tab and launcher |
| `src/timed_url_caller/timing/` | Clock mapping and one-shot scheduler |
| `src/timed_url_caller/ui/` | Separate progress-rendering process |
| `src/url_caller_demo/` | Independent mock server and page assets |
| `src/url_caller_demo/http/` | Routes and bounded per-visit records |
| `src/url_caller_bench/` | Local browser comparison, signaling diagnostic, exports |
| `scripts/` | Documented entry points using the modules |
| `tests/` | Fast contracts and opt-in real-browser checks |
| `notebooks/quickstart.ipynb` | Single runnable tutorial |
| `docs/` | Markdown sources for the searchable documentation website |

The mock server does not import the caller. The caller does not import the mock
server or benchmark. Only the benchmark coordinates both. The source layout is
installed normally by uv, avoiding `sys.path` hacks in launchers and application
code. Public imports remain at package top level; internals are grouped by task.

## Default-browser navigation

Python starts a short-lived loopback bridge and opens a ready page. The page
connects to a token-protected **server-sent event (SSE)** stream and acknowledges
readiness. Python prepares the destination payload before the deadline. At the
deadline it sends one event; page JavaScript requests navigation. The bridge then
shuts down, while the destination tab remains open. There is no Python GET to the
destination, browser startup at the deadline, or automatic reconnection/retry.

This path does not provide browser-side completion acknowledgement. Successful
local sending is not proof that a busy, suspended or closed tab acted on it.
Use connected Chromium for stronger command feedback and for refresh.

## Connected Chromium

The caller attaches to an explicitly selected local browser and creates a new
tab in its persistent default context. Refresh loads the destination during
preparation; navigation keeps a ready document. A unique isolated JavaScript
execution context binds the later action to that specific document. One prepared
CDP command requests `location.replace(url)` or `location.reload()` at the
deadline, with a URL guard, one-shot guard and optional expiry guard.

A replaced document cannot accidentally reuse a numeric context identifier.
Connection loss leaves delivery uncertain, so it is never retried. Disconnecting
the client leaves the operator's browser open. The benchmark, by contrast, owns
its private browser and closes it after measurement.

## Critical path and responsibilities

Validation, URL encoding, browser connection and preparation occur beforehand.
The final timing path waits using a monotonic clock and sends the prepared action.
Progress runs separately and pauses near the deadline. These choices reduce
avoidable Python overhead but do not control the OS, browser or destination.

This project does not run recurring schedules, submit forms, click destination
buttons, bypass browser protections, guarantee delivery, or validate a remote
transaction's outcome. One schedule requests at most one timed browser action.
