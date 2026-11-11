"""Introduction
------------
Start a dedicated Chromium browser for connected navigation and refresh. Remote
debugging lets the caller control its new tab; it is limited to 127.0.0.1.

Instructions
------------
From the project directory:
  uv sync --locked --group browser
  uv run --group browser playwright install chromium
  uv run --group browser scripts/open_browser.py
Use the printed --browser-url with call_url.py. Sign in using this browser if
needed: its dedicated profile is separate from your usual browser profile.
The script exits while leaving the browser open. Close its window when finished.

Help
----
  uv run --group browser scripts/open_browser.py --help
Use --port for a different control port, --profile for an empty/dedicated profile
directory, or --executable for an existing Chromium executable. Do not expose
the debugging port to a network or use your normal browser's profile directory.
"""

from timed_url_caller.browser.launcher import main

if __name__ == "__main__":
    raise SystemExit(main(description=__doc__))
