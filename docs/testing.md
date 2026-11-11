# Tests and benchmarks

No supplied benchmark accepts a public destination. The harness starts its own
loopback server. Tests that use external-looking `.test` URLs validate strings
or fake controller calls only; they do not request those destinations.

## Fast tests and code checks

```sh
uv run --locked python -m unittest discover -s tests -v
uv run --locked --group dev ruff check src scripts tests tools
uv run --locked --group dev ruff format --check src scripts tests tools
node --test tests/test_assets.cjs
```

These tests cover input errors, time offsets, best-effort versus strict dispatch,
one-use semantics, actual local HTTP/SSE, independent visit metrics, controller
contracts, and benchmark output integrity. The Node command is optional; it runs page-asset regressions, readiness-race and best-effort checks. Python test discovery also runs
these JavaScript checks when Node.js is installed. Fake-controller tests are not browser validation.

## Real Chromium integration tests

Install Chromium first. On Linux/macOS:

```sh
uv run --locked --group browser playwright install chromium
RUN_BROWSER_TESTS=1 uv run --locked --group browser python -m unittest discover -s tests -v
```

On PowerShell:

```powershell
$env:RUN_BROWSER_TESTS = "1"
uv run --locked --group browser python -m unittest discover -s tests -v
Remove-Item Env:RUN_BROWSER_TESTS
```

Optionally set `BROWSER_EXECUTABLE` to an installed Chromium binary. Real tests
check both modes/transports, request counts, true reload, button/clock behavior,
HTTP-error refresh, replacement documents, changed URLs, closed tabs, cookies, strict browser expiry, cancellation and
CLI disconnect with an operator tab left clickable.
They are skipped unless explicitly enabled. A browser launch failure is an error,
not a successful test.

## Browser comparison

The test suite checks correctness. This benchmark measures timing distributions;
a completed run does not itself certify a latency target.

```sh
uv run --locked --group benchmark timed-url-benchmark --samples 30 --lead-seconds 1 --output benchmark-results
```

The benchmark owns and closes its private browser. It measures six cases:
navigate via SSE, navigate via CDP, and refresh via CDP, each with progress on/off.
A functional preflight checks both modes, followed by two warm-up trials per case.
`--samples 30` means 180 measured trials in total, not 30 across all cases.
`--lead-seconds 1` explicitly selects the default one-second preparation lead.
`scripts/benchmark.py` is an equivalent entry point to `timed-url-benchmark`.
Measured cases are interleaved in a reproducible shuffled order. Each trial uses
a fresh context in a warmed browser; this differs from an operator's persistent
profile and does not model cold startup or a production network.

Use `--headed` for a visible benchmark window and `--cache-assets` for a separate
cache experiment. Asset cache reuse is possible between preload and reload
within a refresh trial; fresh contexts prevent reuse between trials. Use the
same settings when comparing modes. `--executable` selects an installed browser.
A new or empty output directory is required; existing results are never replaced.

## What the plot measures

| Measurement | Unit | Endpoint |
|---|---|---|
| Python dispatch | ms | Start of the already-prepared callback |
| Document arrival | ms | Mock HTTP handler records the document request after header parsing |
| Interactive receipt | ms | Mock server receives a per-document beacon sent after two animation frames |

All differences use the same host's monotonic clock. The interactive receipt
includes beacon transit and scheduling; it is a readiness proxy, not physical
screen paint. Preload and reload have separate document identifiers, so a late
preload beacon cannot masquerade as the reload. The browser Navigation Timing
type must be `reload` for refresh and `navigate` for navigation.

Every delay axis and tick label uses milliseconds (ms); the horizontal axis
identifies benchmark cases and has no physical unit. Negative values mean early,
positive values mean late, and zero is the scheduled time.

Plots include individual successes, median, nearest-rank p95 and a 20 ms line.
The scale is symmetric logarithmic, linear near zero, so large outliers remain
visible. JSON additionally includes p99, maximum, early results, failures and
counts at or above 20 ms. Percentiles describe successful trials only; inspect
failure counts too. Small samples do not establish tail-latency guarantees.

The raw browser rows retain `navigation_type`; signal rows retain
`caller_cpu_ms` (CPU time of the caller process, excluding its display/receiver
children). Fields ending in `_ms` are milliseconds; timestamps ending in `_ns`
are nanoseconds. Counts such as `arrival_count` are unitless integers.

The default lateness policy remains best-effort during benchmarking, so slow
trials are not cancelled at 20 ms and silently excluded. Raw CSV keeps failed
trials and any timestamps collected before failure. Warm-up failures are
reported separately. `run_status.json` records completion, interruption or
failure. Zero successful trials produce no performance plot.

## Python signaling diagnostic

```sh
uv run --locked --group benchmark timed-url-benchmark --signal-only --samples 30 --output signal-results
```

This sends the real local SSE event to a **Python receiver**, with progress on
and off. The receiver never visits the target. It helps isolate scheduler and
local delivery overhead, but measures no browser navigation, refresh or render.
Its plot is explicitly labeled. A blocked browser benchmark never automatically
turns into this diagnostic.

To profile the Python wait loop in isolation, run:

```sh
uv run --locked python tools/profile_scheduler.py
```

This uses a no-op callback in one thread. It makes no requests and excludes
browser work, progress and transport. Profiling changes timing; its output is
for locating Python work, not proving a latency target.

## Reproduce the documentation and package

```sh
uv lock --check
uv build
uv run --locked --group docs mkdocs build --strict
uv run --locked --group docs python tools/check_docs.py
node tools/check_search.cjs
```

`uv sync --locked --group full` installs every dependency group, but still does
not download Chromium. Platform libraries and the browser binary are separate
from Python package resolution. Keep build products, browser profiles and
measurement output out of Git. The repository ignore rules cover the default
output locations and the benchmark's fixed filenames, even under a custom
`--output` directory. They also cover `scheduler-profile.txt`, common temporary
files, environments, caches, build products and known credential/key filenames.

Put custom logs, renamed results and browser profiles under `.local/` (ignored
in full), or outside the repository. Avoid using reserved output filenames such
as `summary.json` for source assets. The rules intentionally keep ordinary JSON,
CSV and image source files visible. Clear notebook outputs before committing;
Git cannot ignore outputs embedded inside a tracked notebook.

Before committing, inspect the files Git will include:

```sh
git status --short
git diff --cached --name-only
git ls-files -ci --exclude-standard
git check-ignore -v --no-index -- benchmark-results/performance.png
```

The third command lists already-tracked files that now match ignore rules; no
output is expected for a clean source tree. If it identifies a generated or
private file, remove that specific path from the index with
`git rm --cached -- path/to/file` (add `-r` for a directory), then commit the
removal. This preserves the local file but does not erase earlier commits.
Never rely on ignore rules to identify secrets by their contents or to prevent
`git add -f`. A secret already committed requires separate history/credential
remediation. See [Git's ignore documentation](https://git-scm.com/docs/gitignore).

The documentation checks validate local links, anchors, bundled runtime assets
and the generated search index. The optional Node.js command exercises the
actual search worker. Neither command requests public pages.
