# URL Caller

**Schedule a browser navigation or refresh, then continue working in the page.**

URL Caller prepares the browser before the deadline and requests one action at
the chosen time. A progress bar and primed spinner show its state, and the
browser stays open afterward. Destinations can be public sites, intranet pages
or local servers: any absolute HTTP(S) URL the browser can load.

[Quick start](#quick-start) · [Refresh mode](#visit-early-then-refresh) ·
[Python API](#use-from-python) · [Tests and benchmarks](#tests-and-benchmarks) ·
[Documentation](docs/index.md) · [Notebook](notebooks/quickstart.ipynb)

| Mode | Before the deadline | At the deadline |
|---|---|---|
| **Navigate** (default) | Open a ready tab; leave the destination unvisited | Navigate to the destination once |
| **Refresh** | Visit the destination and prepare its document | Reload that document once |

The mock server is for demos and measurements. **Real destinations do not require
it.** Refresh may benefit from existing browser state, but is not necessarily
faster; an early visit can itself have effects on a real site.

## Install with uv

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use a
graphical browser for interactive calls. Python 3.11+ is supported; development
uses Python 3.12, which uv can obtain if needed.

Clone this repository or download and extract its source ZIP. Open a terminal
in the project root, the directory containing `pyproject.toml`, then run:

```sh
uv sync --locked
```

This installs the package in `.venv` using the versions in `uv.lock`. No manual
environment activation is needed. If uv is missing, follow its platform
installation guide above; `python -m pip install uv` is another installation
option. The examples work in Bash and PowerShell unless marked otherwise.

## Quick start

Once uv is installed, this local demo takes only a few minutes and uses your
normal graphical browser.

**Terminal 1 — start the mock server:**

```sh
uv run --locked timed-url-demo
```

**Terminal 2 — schedule navigation from the same project directory:**

```sh
uv run --locked timed-url-caller http://127.0.0.1:8765/ --after 15
```

1. A ready tab opens immediately. Keep it visible and the computer awake.
2. After 15 seconds, it navigates to the demo page.
3. Click **“Click me for some wisdom.”** to confirm that the page is usable.

The page also shows a live **CET** clock: fixed UTC+1, without summer-time
adjustment. It is a display clock, not the scheduling reference. The browser
stays open; stop the server with Ctrl+C when finished.

For real use, replace the URL and omit the mock-server step. Quote URLs that
contain shell characters such as `&`:

```sh
uv run --locked timed-url-caller "https://example.com/" --after 15
```

## Visit early, then refresh

Refresh requires a connected Chromium browser. **Remote debugging** is the local
control connection used by the caller, separate from the destination URL.
Install the adapter and browser, then start the dedicated browser:

```sh
uv sync --locked --group browser
uv run --locked --group browser playwright install chromium
uv run --locked --group browser timed-url-browser
```

The launcher creates a separate persistent profile and enables debugging at
`http://127.0.0.1:9222`. It prints that address and exits while Chromium stays
open. Sign in there if the destination requires it, then run:

```sh
uv run --locked --group browser timed-url-caller "https://example.com/" --after 20 --mode refresh --browser-url http://127.0.0.1:9222
```

Use `--mode navigate` to use the same connected browser without visiting the
destination early. Keep the prepared tab unchanged while armed: navigating,
reloading or changing its URL invalidates the prepared action.

Already have Chrome/Chromium? Use `timed-url-browser --executable ...` with its
full executable path. The [browser setup guide](docs/browser-setup.md) covers
Windows and macOS paths, Linux libraries, profiles and manual debugging setup.
Close the browser window when finished. Keep its profile local: it can contain
cookies and sign-in state.

## Choose a time and lateness policy

`--after 15` means 15 seconds from configuration near command start, including
preparation. To choose a particular date and time, use `--at` instead:

```sh
uv run --locked timed-url-caller "https://example.com/" --at "2030-01-01T12:00:00+01:00"
```

Replace the example timestamp with a future time within 365 days. Include a UTC
offset such as `+01:00`, or `Z` for UTC, to avoid ambiguous local times. Allow
enough time for browser preparation.

**Best-effort is the default:** request the action once as soon as possible at
or after the deadline. Add `--max-late-ms 20` to cancel an action observed more
than 20 milliseconds late. This is not a page-load guarantee. Ctrl+C cancels
waiting; an early visit or an action already sent cannot be undone. There are
no automatic retries.

## Scripts and command-line help

The scripts and installed commands call the same modules. Choose either form;
they are equivalent, not separate modes. Each script starts with Introduction,
Instructions and Help sections, also available through `--help`.

| Source script | Installed command | Purpose |
|---|---|---|
| `scripts/call_url.py` | `timed-url-caller` | Schedule navigation or refresh |
| `scripts/mock_server.py` | `timed-url-demo` | Run the local mock server |
| `scripts/open_browser.py` | `timed-url-browser` | Start Chromium with debugging |
| `scripts/benchmark.py` | `timed-url-benchmark` | Measure local timing and generate plots |

```sh
uv run --locked timed-url-caller --help
uv run --locked scripts/call_url.py --help
uv run --locked timed-url-demo --help
uv run --locked --group browser timed-url-browser --help
uv run --locked --group benchmark timed-url-benchmark --help
```

Caller results are JSON on stdout; status, progress and errors go to stderr.
Success means the action was requested, not that the destination loaded
successfully. See the [CLI reference](docs/cli.md) for options and exit codes.

## Use from Python

```python
from timed_url_caller import Schedule, TimedBrowserCaller


def main():
    result = TimedBrowserCaller(
        "https://example.com/",
        Schedule.after(15),
        mode="navigate",
    ).run()
    print(result.as_dict())


if __name__ == "__main__":
    main()
```

The `if __name__ == "__main__":` guard prevents the scheduling code from running
again when Python starts the separate progress process. Use it in your scripts;
the supplied CLI already handles it. Embedded code can use `progress=False`.

For refresh, set `mode="refresh"` and
`browser_url="http://127.0.0.1:9222"` after starting the dedicated browser.
Use `Schedule.at(text="2030-01-01T12:00:00+01:00")` for an absolute time.
A caller instance is single-use. The independent demo API is
`from url_caller_demo import DemoServer`; `DemoServer(port=0)` selects an
available loopback port. See the [API reference](docs/api.md) for its lifecycle
and result fields. The notebook uses subprocesses for connected browser work.

## Tests and benchmarks

**Tests check correctness; benchmarks measure timing.** All supplied tests and
benchmarks use local loopback traffic or fakes, without requesting public sites.

```sh
uv run --locked python -m unittest discover -s tests -v
uv run --locked --group dev ruff check src scripts tests tools
```

Real Chromium tests require installation of the browser and the explicit
`RUN_BROWSER_TESTS=1` environment variable. Selecting `--group browser` installs
the adapter but does not enable these tests. See the [testing guide](docs/testing.md)
for Bash and PowerShell commands.

To compare navigate/refresh and progress on/off:

```sh
uv run --locked --group benchmark playwright install chromium
uv run --locked --group benchmark timed-url-benchmark --samples 30 --lead-seconds 1 --output benchmark-results
```

This runs **30 measured trials per case: 180 total**, plus warm-ups and functional
preflight checks. The one-second lead is preparation time, not measured latency.
The benchmark owns its local server and private browser. It exports CSV, JSON,
PNG and SVG with explicit units: plotted delays are in **milliseconds (ms)**;
raw fields ending in `_ns` use **nanoseconds (ns)**. Read failures alongside
percentiles. A blocked browser run records its failure and produces no browser
plot. Use a new output directory for every run.

A separate Python-only signaling diagnostic is available:

```sh
uv run --locked --group benchmark timed-url-benchmark --signal-only --samples 30 --output signal-results
```

This measures scheduling and local event delivery, without browser navigation,
reload or rendering. [Measurement definitions](docs/testing.md#what-the-plot-measures)
explain the distinction.

## Notebook and documentation

Open the [quickstart notebook](notebooks/quickstart.ipynb):

```sh
uv run --locked --group notebook-only jupyter lab notebooks/quickstart.ipynb
```

Install Chromium first for its browser measurements. The notebook introduces the
API, local server, modes, tests and benchmarks, and ends with a clearly labeled
performance graph. Interactive desktop opening is opt-in.

Read the [documentation](docs/index.md) directly on GitHub, or serve its
searchable HTML version locally:

```sh
uv run --locked --group docs mkdocs serve --dev-addr 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/`. For a static website build, run
`uv run --locked --group docs mkdocs build --strict`; output goes to the ignored
`site/` directory. Documentation sources, rather than generated pages, belong
in the repository.

## Dependency groups and layout

Base runtime dependencies are Rich and progress (PieSpinner). Choose groups on
both `uv sync` and `uv run`:

| Group | Additional dependencies |
|---|---|
| `demo-only` | None; the mock server uses the standard library |
| `browser` | Playwright adapter; Chromium is a separate download |
| `benchmark` | Browser group and Matplotlib |
| `notebook-only` | Benchmark group, JupyterLab and notebook execution |
| `docs` | MkDocs Material with search |
| `dev` | Ruff and notebook-format validation |
| `full` | All groups above |

`uv sync --locked --group full` prepares the complete development environment.
A later sync can remove unrequested groups. Use `uv run --no-sync ...` to retain
an already prepared environment when running project commands concurrently.
Wheel installs also provide `browser`, `benchmark`, `notebook` and `dev` extras.

| Location | Contents |
|---|---|
| `src/timed_url_caller/` | Public API, browser control, timing and progress |
| `src/url_caller_demo/` | Independent mock server and page assets |
| `src/url_caller_bench/` | Local measurement harness and plotting |
| `scripts/`, `tests/`, `tools/` | Entry points, regression tests and development checks |
| `docs/`, `notebooks/` | Reference documentation and runnable tutorial |

## Timing limits and license

Dispatch, request arrival and page usability are different measurements. DNS,
TLS, network travel, destination processing and browser rendering add latency
outside the scheduler. This is best-effort software; it cannot guarantee that
an arbitrary website becomes usable within 20 ms. See the [timing glossary](docs/glossary.md).

Version **0.5.0**. Licensed under [Apache License 2.0](LICENSE).

## AI assistance

AI tools assisted with the code, documentation and review. Their output can
contain mistakes. Review changes and run the supplied tests in your environment
before relying on timing-sensitive behavior; AI assistance is not a guarantee
of correctness or performance.
