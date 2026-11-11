# Troubleshooting

| Symptom | What to do |
|---|---|
| `uv` is not found | Install uv, reopen the terminal, and confirm `uv --version` |
| Module cannot be imported | Run from the extracted project root using `uv run`; select the same environment in Jupyter |
| Playwright import is missing | Include `--group browser`, `benchmark`, `notebook-only` or `full` on `uv run` |
| Chromium executable is missing | Run `uv run --group browser playwright install chromium`, or supply `--executable` |
| Browser does not become ready | Inspect the printed launcher log; check graphical desktop, platform libraries, port and browser executable |
| Port already in use | Reuse the existing dedicated browser address, or choose a different `--port`; for the demo use `--port 0` |
| Ready tab did not connect | Use a graphical browser, allow the local ready page's scripts, and choose a later deadline |
| Preparation finished too late | Increase `--after`; the caller does not dispatch an unprepared action |
| Timestamp lacks an offset | Add `Z` or a numeric offset such as `+01:00` |
| Strict maximum lateness exceeded | Inspect the tab; omit `--max-late-ms` if best-effort behavior is appropriate |
| Prepared document changed | Keep the armed tab unchanged; inspect it before creating a fresh schedule |
| Delivery is uncertain | Do not assume success or retry blindly; check the browser first |
| Notebook complains about a running asyncio loop | Use the notebook's subprocess CLI pattern for connected browser work |
| Benchmark is blocked or has no plot | Read `run_status.json` and `summary.json`; a browser launch failure is not timing data |
| Existing output directory is rejected | Choose a new directory to preserve earlier results |

The mock server accepts `127.0.0.1` with its printed port; use that numeric address
rather than replacing it with `localhost`. Its host checks are intentional.

## Browser restrictions and authentication

The destination may require login, allow only some browser behavior, redirect,
download a file, reject TLS, or respond with an HTTP error. Sign in through the
dedicated browser before scheduling. HTTP error documents can be refreshed;
network failures and downloads do not provide a usable document to arm. Browser
or site restrictions are reported rather than bypassed.

For refresh, a redirect means the final document is the one reloaded. A
single-page app may update without a full document navigation; the caller does
not interpret the application's internal state.

## Documentation preview

Run `uv run --locked --group docs mkdocs serve --dev-addr 127.0.0.1:8000`
and open `http://127.0.0.1:8000/`. This serves documentation only. A static build
uses `uv run --locked --group docs mkdocs build --strict` and writes to `site/`.
Serve that directory over HTTP for search to work; do not open its HTML files
directly with a `file://` URL.
