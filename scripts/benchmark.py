"""Introduction
------------
Compare scheduled navigation and refresh against the bundled local mock server,
with progress on/off. This script uses the module's benchmark implementation.
No public destination can be supplied. Results include CSV, JSON, PNG and SVG.

Instructions
------------
From the project directory:
  uv sync --locked --group benchmark
  uv run --locked --group benchmark playwright install chromium
  uv run --locked --group benchmark scripts/benchmark.py --samples 30 --output benchmark-results
The harness starts and stops its own server and private browser. Choose a fresh
output directory for each run. Use --headed to show the benchmark browser.

Help
----
  uv run --locked --group benchmark scripts/benchmark.py --help
--signal-only measures Python scheduling and local event receipt only: it does
not measure navigation, reload or rendering. A blocked browser run is reported
as blocked and never silently replaced with this diagnostic.
"""

from url_caller_bench.cli import main

if __name__ == "__main__":
    raise SystemExit(main(description=__doc__))
