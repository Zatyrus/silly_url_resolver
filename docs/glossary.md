# Terms and timing limits

| Term | Meaning here |
|---|---|
| Deadline / T | The requested time for the browser action |
| Navigate | First visit to the destination at T |
| Preload | Refresh mode's early destination visit, including its normal effects |
| Refresh / reload | Browser reload of the prepared document at T |
| Dispatch | Python starts sending the prepared command/event |
| Lateness | Measured time minus deadline; positive means late |
| Wall clock | Calendar time, which can change when synchronized or adjusted |
| Monotonic clock | Elapsed-time clock used for the final wait; does not jump with calendar corrections |
| Loopback | `127.0.0.1`, the same computer, not the public network |
| CDP | Chrome DevTools Protocol, used to control the chosen Chromium tab |
| SSE | Server-sent events, a persistent connection from the local bridge to the ready page |
| Browser context | A browser session container for cookies and related state |
| Profile | Browser data kept on disk, including sign-in state |
| Primed | Preparation succeeded; waiting for the scheduled dispatch |
| p95 | At least 95% of successful measured values are at or below this value |
| CET | Fixed UTC+1 in this demo; not the summer-time-aware Europe/Berlin zone |

## What under 20 ms can mean

Dispatch within 20 ms, request arrival within 20 ms, and visible interactive page
within 20 ms are different requirements. DNS resolution, TLS negotiation, network
travel, server processing, browser queues and rendering all happen outside the
Python scheduler. Even loopback browser timings vary with machine load and tab
visibility. No result from a Python-only receiver proves browser performance.

Keep the browser warm, the tab visible and the computer awake. Use synchronized
system time for absolute deadlines. Measure both modes on the intended machine
against a controlled local server first; never assume that a faster local reload
will improve a different production site's behavior.
