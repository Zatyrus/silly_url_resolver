# Modes and scheduling

| Mode | Before the deadline | At the deadline | Browser setup |
|---|---|---|---|
| `navigate` | Open a ready tab; do not visit the destination | Request navigation once | Default browser, or connected Chromium |
| `refresh` | Visit the destination and wait for its document | Request a genuine reload once | Connected Chromium |

Refresh may reuse cookies, connections and cached assets. It also performs an
early request, which may change state on the destination. It is not universally
faster. Use the same connected browser for both modes when comparing them.

## Choose the time

```sh
uv run --locked scripts/call_url.py 'https://example.com/' --after 15
uv run --locked scripts/call_url.py 'https://example.com/' --at '2030-01-01T12:00:00+01:00'
```

`--after` counts seconds from configuration near command start, not from the end
of browser preparation. `--at` accepts an ISO date and time with an explicit UTC
offset, or `Z` for UTC. Choose a future time within 365 days, allowing enough
preparation time (15–30 seconds is a sensible interactive starting point).
Ambiguous local times, negative intervals and nonfinite numbers are rejected.

The clock follows system wall-clock adjustments until the final 50 ms, then
uses a monotonic clock (one that does not jump with clock corrections). The final
2 ms use a busy wait by default. `--spin-ms 0` avoids that brief CPU use but may
increase scheduling error. Keep the computer awake and its clock synchronized.

## Progress and primed state

The Rich progress bar shows the lead-up. Once preparation succeeds, the
PieSpinner appears during the final `--primed-seconds` (10 by default). Short
schedules may enter the spinner immediately. “Primed” means the dispatch path
is ready, not that the remote site is guaranteed to respond.

Rendering runs in a separate process, at most ten updates per second, and pauses
in the final 100 ms. This reduces interference but does not eliminate OS resource
contention. `--no-progress` disables it. Captured terminals may suppress animated
output; `--force-terminal` enables it explicitly.

## Late actions, cancellation and changing tabs

Best-effort is the default: send one prepared action as soon as possible at or
after the deadline, even if the process woke late. For a strict policy:

```sh
uv run --locked scripts/call_url.py 'https://example.com/' --after 15 --max-late-ms 20
```

That option cancels if Python or the browser observes excessive lateness. It is
not a promise that the network request or render finishes within 20 ms. With the
default-browser bridge, Python cannot observe the browser's final acceptance.

Do not navigate, reload, submit forms or change the prepared URL while armed.
Connected Chromium binds the action to that exact document and URL; replacing
it causes failure rather than acting on an unrelated tab. A single-page app can
change internal state without changing its document/URL, so keep it untouched.

Ctrl+C cancels waiting. The caller never automatically retries an uncertain send.
An early refresh-mode visit or an in-flight action cannot be undone. After a
failure, inspect the browser before scheduling again.

## What a target can be

HTTP and HTTPS targets are accepted without a hostname allowlist, including
query strings, fragments, internationalized hosts and explicit ports. Encode
spaces and quote shell-sensitive URLs. Embedded credentials, file URLs and
JavaScript URLs are rejected. Sign in through the browser instead.

A target must be a page the browser can load. Downloads, TLS failures, login
requirements, restrictive browser/site policy and network failures may prevent
preparation or loading. The caller does not bypass these restrictions.
Refresh accepts HTTP error documents, including 403 and 503, because such pages
may become available later. Following a redirect prepares its final document;
refresh reloads that final URL rather than replaying the original redirect URL.
