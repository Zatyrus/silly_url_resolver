"""Attach to an explicitly selected local Chromium, creating a new operator tab.

No existing tab is inspected. Disconnecting this client leaves the separately
started browser and its default-profile tab open for the operator.
"""

from .._validation import validate_endpoint
from .controlled_tab import ControlledTab


class BrowserConnection:
    def __init__(self, endpoint):
        self.endpoint = validate_endpoint(endpoint)
        self.playwright = None
        self.tab = None

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Browser control is missing. Run: uv sync --locked --group browser"
            ) from exc
        try:
            self.playwright = sync_playwright().start()
            browser = self.playwright.chromium.connect_over_cdp(self.endpoint, timeout=5000)
            if not browser.contexts:
                raise RuntimeError("The browser has no default profile window.")
            self.tab = ControlledTab(browser.contexts[0].new_page())
            return self.tab
        except BaseException as exc:
            self.__exit__(None, None, None)
            if not isinstance(exc, Exception):
                raise  # Cancellation still disconnects this client.
            raise RuntimeError(
                "Could not connect to Chromium. Run scripts/open_browser.py first, then use its printed --browser-url."
            ) from exc

    def __exit__(self, *_):
        if self.tab:
            self.tab.close()
        if self.playwright:
            try:
                self.playwright.stop()  # Disconnect only; never close the operator's browser.
            except Exception:
                pass
            self.playwright = None
