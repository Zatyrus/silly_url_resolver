"""Opt-in real Chromium tests. Set RUN_BROWSER_TESTS=1; all traffic is local.

Optionally set BROWSER_EXECUTABLE to an installed Chromium executable. A launch
failure is a test error, never a pass or a substitution with a simulated browser.
"""

import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from timed_url_caller import Schedule, TimedBrowserCaller
from timed_url_caller.browser.bridge import BrowserBridge
from timed_url_caller.browser.controlled_tab import ControlledTab
from url_caller_demo import DemoServer


@unittest.skipUnless(os.environ.get("RUN_BROWSER_TESTS") == "1", "opt-in real Chromium tests")
class BrowserIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright

        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(
                executable_path=os.environ.get("BROWSER_EXECUTABLE"),
                args=["--disable-background-networking"],
            )
        except Exception:
            cls.playwright.stop()
            raise
        cls.server = DemoServer(0)
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(1)

    def setUp(self):
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.server.status_code = 200

    def tearDown(self):
        self.context.close()

    def test_modes_and_transports_leave_clickable_tab(self):
        from url_caller_bench.browser import preflight

        self.assertEqual(preflight(self.browser, self.server.url)["status"], "passed")

    def test_error_page_can_be_refreshed(self):
        self.server.status_code = 503
        url = self.server.url + "?trial=error-page"
        tab = ControlledTab(self.page)
        TimedBrowserCaller(
            url, Schedule.after(2), mode="refresh", controlled_tab=tab, progress=False
        ).run()
        self.page.wait_for_function(
            "performance.getEntriesByType('navigation')[0]?.type === 'reload'"
        )
        self.assertEqual(tab.preload_status, 503)
        self.assertEqual(
            self.page.evaluate("performance.getEntriesByType('navigation')[0].type"), "reload"
        )

    def test_replacement_document_at_same_url_is_not_acted_on(self):
        tab = ControlledTab(self.page)
        tab.prepare(self.server.url, "refresh", time.time_ns() + 5_000_000_000)
        self.page.reload(wait_until="domcontentloaded")
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            tab.dispatch()
        tab.close()

    def test_hash_change_prevents_action(self):
        tab = ControlledTab(self.page)
        tab.prepare(self.server.url, "refresh", time.time_ns() + 5_000_000_000)
        self.page.evaluate("location.hash = 'changed'")
        with self.assertRaisesRegex(RuntimeError, "document changed"):
            tab.dispatch()
        tab.close()

    def test_closed_tab_is_not_retried(self):
        tab = ControlledTab(self.page)
        tab.prepare(self.server.url, "refresh", time.time_ns() + 5_000_000_000)
        self.page.close()
        with self.assertRaises(RuntimeError):
            tab.dispatch()
        with self.assertRaisesRegex(RuntimeError, "already attempted"):
            tab.dispatch()
        tab.close()

    def test_cookie_survives_refresh(self):
        self.context.add_cookies([{"name": "operator", "value": "yes", "url": self.server.url}])
        tab = ControlledTab(self.page)
        TimedBrowserCaller(
            self.server.url, Schedule.after(2), mode="refresh", controlled_tab=tab, progress=False
        ).run()
        self.page.wait_for_function(
            "performance.getEntriesByType('navigation')[0]?.type === 'reload'"
        )
        self.assertIn("operator=yes", self.page.evaluate("document.cookie"))

    def test_strict_browser_expiry_prevents_reload(self):
        trial = "strict-expiry"
        tab = ControlledTab(self.page)
        self.addCleanup(tab.close)
        tab.prepare(
            self.server.url + "?trial=" + trial,
            "refresh",
            time.time_ns() + 600_000_000,
            max_late_ms=20,
        )
        self.page.wait_for_timeout(750)
        with self.assertRaises(TimeoutError):
            tab.dispatch()
        self.assertEqual(self.server.recorder.get(trial)["arrival_count"], 1)

    def test_bridge_cancellation_never_visits_destination(self):
        bridge = BrowserBridge(
            self.server.url + "?trial=cancelled", time.time_ns() + 5_000_000_000
        ).start()
        self.addCleanup(bridge.close)
        self.page.goto(bridge.landing_url, wait_until="domcontentloaded")
        # Pump the Playwright event loop while the page acknowledges readiness.
        self.page.wait_for_function("document.body.dataset.ready === 'true'")
        bridge.wait_ready()
        bridge.close()
        self.page.wait_for_timeout(100)
        self.assertEqual(self.server.recorder.get("cancelled"), {})

    def test_cli_disconnect_leaves_operator_tab_clickable(self):
        with tempfile.TemporaryDirectory() as profile:
            context = self.playwright.chromium.launch_persistent_context(
                profile,
                headless=True,
                executable_path=os.environ.get("BROWSER_EXECUTABLE"),
                args=[
                    "--remote-debugging-port=0",
                    "--remote-debugging-address=127.0.0.1",
                    "--disable-background-networking",
                ],
            )
            try:
                port = int((Path(profile) / "DevToolsActivePort").read_text().splitlines()[0])
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "timed_url_caller",
                        self.server.url,
                        "--after",
                        "3",
                        "--mode",
                        "refresh",
                        "--browser-url",
                        f"http://127.0.0.1:{port}",
                        "--no-progress",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                context.pages[0].wait_for_timeout(100)  # Drain new-tab events.
                matching = [page for page in context.pages if page.url == self.server.url]
                self.assertEqual(len(matching), 1)
                page = matching[0]
                self.assertFalse(page.is_closed())
                page.get_by_role("button", name="Click me for some wisdom.", exact=True).click()
                self.assertTrue(page.locator("#wisdom").is_visible())
            finally:
                context.close()


if __name__ == "__main__":
    unittest.main()
