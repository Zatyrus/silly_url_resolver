"""Introduction
------------
Request one browser navigation or refresh at a scheduled time, then leave the
page open. Destinations may be any absolute HTTP(S) URL, not just a local server.
This script delegates to the Python module; it contains no separate timing logic.

Instructions
------------
From the project directory:
  uv run scripts/call_url.py https://example.com/ --after 15
  uv run --group browser scripts/call_url.py https://example.com/ --after 20 \
      --mode refresh --browser-url http://127.0.0.1:9222

For refresh, first run scripts/open_browser.py. Refresh visits the URL early;
navigate does not. Keep the tab visible. Use --at with an ISO timestamp and UTC
offset for an absolute time. Replace the URL with your real destination.

Help
----
  uv run scripts/call_url.py --help
Use --max-late-ms 20 only if a missed deadline should cancel the action.
Press Ctrl+C to cancel before dispatch; an early visit cannot be undone.
"""

from timed_url_caller.cli import main

if __name__ == "__main__":
    raise SystemExit(main(description=__doc__))
