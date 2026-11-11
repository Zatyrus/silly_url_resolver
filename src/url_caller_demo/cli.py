"""Run the independent loopback mock server for demos and measurements.

Use scripts/mock_server.py --help. This server is never required for a real URL.
"""

import argparse
import json
import sys

from .server import DemoServer


def main(argv=None, *, description=None):
    parser = argparse.ArgumentParser(
        description=description or __doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="loopback port; 0 chooses a free port (default: 8765)",
    )
    parser.add_argument(
        "--cache-assets",
        action="store_true",
        help="allow caching JS/CSS for local cache experiments",
    )
    parser.add_argument(
        "--status-code",
        type=int,
        choices=(200, 403, 404, 429, 500, 503),
        default=200,
        help="document HTTP status for local error-page tests",
    )
    parser.add_argument("--json", action="store_true", help="print the server address as JSON")
    args = parser.parse_args(argv)
    try:
        with DemoServer(
            args.port, cache_assets=args.cache_assets, status_code=args.status_code
        ) as server:
            print(
                json.dumps({"url": server.url})
                if args.json
                else f"Mock server ready: {server.url}\nPress Ctrl+C to stop.",
                flush=True,
            )
            server.serve_forever(poll_interval=0.05)
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError) as exc:
        print(
            f"Could not start the mock server: {exc}. Try --port 0 for an available port.",
            file=sys.stderr,
        )
        return 2
    return 0
