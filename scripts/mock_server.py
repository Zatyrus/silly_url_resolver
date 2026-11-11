"""Introduction
------------
Start the independent local mock server for demos, tests and benchmarks. It has
a wisdom button and a fixed CET (UTC+1) clock. Real destination URLs do not need it.

Instructions
------------
From the project directory:
  uv run scripts/mock_server.py --port 8765
Keep this terminal open, then use http://127.0.0.1:8765/ as a caller destination.
Use --port 0 to choose an available port. Press Ctrl+C to stop the server.

Help
----
  uv run scripts/mock_server.py --help
--cache-assets enables a local cache experiment; --status-code 503 simulates an
error document that can still be refreshed. The service binds only to loopback.
"""

from url_caller_demo.cli import main

if __name__ == "__main__":
    raise SystemExit(main(description=__doc__))
