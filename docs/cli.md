# Scripts and CLI

Run these commands from the project root. Each script begins with
**Introduction**, **Instructions** and **Help** sections in its source. The same
text appears in `--help`; the wrappers delegate to the installed Python module.
Installed commands and source scripts run the same implementation. On Windows,
the installed commands use `.exe` launchers in `.venv\Scripts`; the application
still runs as Python and depends on that environment.

| Source script | Equivalent command | Purpose |
|---|---|---|
| `scripts/call_url.py` | `timed-url-caller` | Schedule one browser action |
| `scripts/mock_server.py` | `timed-url-demo` | Run the independent local mock server |
| `scripts/open_browser.py` | `timed-url-browser` | Start dedicated Chromium with debugging |
| `scripts/benchmark.py` | `timed-url-benchmark` | Run local measurements and generate plots |

## Caller examples

```sh
uv run --locked scripts/call_url.py 'https://example.com/' --after 15
uv run --locked --group browser scripts/call_url.py 'https://example.com/' --after 20 --mode refresh --browser-url http://127.0.0.1:9222
uv run --locked scripts/call_url.py 'https://example.com/' --at '2030-01-01T12:00:00+01:00'
```

Replace the example URL and timestamp. Refresh requires the browser launcher to
have run first. A public destination does not require the mock server.

| Option | Meaning |
|---|---|
| positional `url` | Absolute HTTP(S) destination |
| `--after SECONDS` / `--at TIMESTAMP` | Choose exactly one time format |
| `--mode navigate\|refresh` | First visit at T, or early visit and reload at T |
| `--browser-url ADDRESS` | Loopback CDP address; required for refresh |
| `--max-late-ms MS` | Optional cancellation cutoff; default is best-effort |
| `--spin-ms MS` | Final busy wait, default 2 ms; use 0 for sleep only |
| `--primed-seconds SECONDS` | Spinner period once ready, default 10 seconds |
| `--no-progress` | Disable progress rendering |
| `--force-terminal` | Render animated indicators in captured output |

Results are JSON on stdout; human status and errors go to stderr. Exit codes are
0 for requested action, 2 for invalid setup/failure, and 130 for cancellation.
Success does not confirm target HTTP success or page-load completion.

## Mock server

```sh
uv run --locked scripts/mock_server.py --port 8765
uv run --locked scripts/mock_server.py --port 0 --json
uv run --locked scripts/mock_server.py --status-code 503
```

`--port 0` chooses a free port. `--json` prints the chosen URL for tooling.
`--cache-assets` allows JS/CSS caching; the page itself remains uncached.
`--status-code` simulates HTTP error documents for refresh checks. Ctrl+C stops
the server. Use its printed numeric `127.0.0.1` address.

## Browser launcher

```sh
uv run --locked --group browser scripts/open_browser.py
uv run --locked --group browser scripts/open_browser.py --port 9333 --profile .url-caller-profile-2
```

`--executable` accepts an installed Chromium executable; `--json` prints the
endpoint, profile path and process ID. The launcher uses a dedicated profile,
waits for debugging readiness and exits while leaving the browser open. See
[Chromium setup](browser-setup.md) for installation and platform details.

## Full help

```sh
uv run --locked scripts/call_url.py --help
uv run --locked scripts/mock_server.py --help
uv run --locked --group browser scripts/open_browser.py --help
uv run --locked --group benchmark scripts/benchmark.py --help
```

Benchmark output directories must be new or empty. Exit code 1 means measured
trial errors, 2 means blocked/failed setup or export, and 130 means interruption.
See [tests and benchmarks](testing.md) before interpreting timing numbers.
