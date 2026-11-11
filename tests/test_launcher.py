"""Profile ownership and connection cleanup; no browser process is launched."""

import socket
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from timed_url_caller.browser.connection import BrowserConnection
from timed_url_caller.browser.launcher import launch_browser


class LauncherTests(unittest.TestCase):
    def test_unrelated_profile_is_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as folder, patch("subprocess.Popen") as launch:
            profile = Path(folder)
            (profile / "unrelated-data").write_text("keep")
            with self.assertRaisesRegex(ValueError, "empty profile"):
                launch_browser(profile)
            launch.assert_not_called()
            self.assertEqual((profile / "unrelated-data").read_text(), "keep")

    def test_busy_port_is_not_reused(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            socket.socket() as listener,
            patch("subprocess.Popen") as launch,
        ):
            listener.bind(("127.0.0.1", 0))
            with self.assertRaisesRegex(ValueError, "already in use"):
                launch_browser(folder, port=listener.getsockname()[1])
            launch.assert_not_called()

    def test_invalid_port_is_clear(self):
        for port in (0, 65536, True, "9222"):
            with self.subTest(port=port), self.assertRaises(ValueError):
                launch_browser("unused", port=port)

    def test_missing_executable_does_not_create_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            profile = Path(folder) / "new"
            with self.assertRaisesRegex(ValueError, "Chromium is missing"):
                launch_browser(profile, executable=Path(folder) / "absent-browser")
            self.assertFalse(profile.exists())

    def test_connected_client_disconnects_without_closing_browser(self):
        controller = Mock()
        page = Mock()
        browser = Mock(contexts=[Mock()])
        browser.contexts[0].new_page.return_value = page
        controller.chromium.connect_over_cdp.return_value = browser
        adapter = Mock()
        adapter.start.return_value = controller
        module = types.ModuleType("playwright.sync_api")
        module.sync_playwright = lambda: adapter
        with patch.dict(sys.modules, {"playwright.sync_api": module}):
            with BrowserConnection("http://127.0.0.1:9222") as tab:
                self.assertIs(tab.page, page)
        controller.stop.assert_called_once()
        browser.close.assert_not_called()
        page.close.assert_not_called()
        browser.contexts[0].new_page.assert_called_once()


if __name__ == "__main__":
    unittest.main()
