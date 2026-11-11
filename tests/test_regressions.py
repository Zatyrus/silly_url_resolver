"""Public API, browser lifecycle and error-handling regression tests."""

import http.client
import importlib
import io
import os
import pkgutil
import select
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

from timed_url_caller import CallResult, Schedule
from timed_url_caller.browser.bridge import BrowserBridge
from timed_url_caller.browser.bridge_handler import BridgeHandler
from timed_url_caller.browser.connection import BrowserConnection
from timed_url_caller.ui.progress import ProgressDisplay, _render
from url_caller_bench.cli import main as benchmark_main
from url_caller_demo.http.handler import DemoHandler


class CompatibilityTests(unittest.TestCase):
    def test_call_result_four_argument_constructor_still_works(self):
        result = CallResult(100, 200, 300, 400)
        self.assertEqual((result.mode, result.transport), ("navigate", "sse"))

    def test_schedule_at_text_keyword_still_works(self):
        self.assertEqual(
            Schedule.at(text="2030-01-01T12:00:00Z"), Schedule.at("2030-01-01T12:00:00Z")
        )

    def test_all_modules_import_without_optional_browser_startup(self):
        for name in ("timed_url_caller", "url_caller_demo", "url_caller_bench"):
            package = importlib.import_module(name)
            for module in pkgutil.walk_packages(package.__path__, name + "."):
                importlib.import_module(module.name)

    def test_runtime_packages_are_independent_and_start_no_threads(self):
        for name, other in [
            ("timed_url_caller", "url_caller_demo"),
            ("url_caller_demo", "timed_url_caller"),
        ]:
            code = f"import sys, threading; before=threading.active_count(); import {name}; assert threading.active_count()==before; assert not any(n.startswith({other!r}) for n in sys.modules)"
            subprocess.run([sys.executable, "-c", code], check=True, timeout=5)

    def test_time_fraction_precision_is_preserved(self):
        self.assertEqual(Schedule.at("1970-01-01T00:00:00.000001Z").target_wall_ns, 1000)

    def test_js_assets_when_node_is_available(self):
        import shutil

        if not shutil.which("node"):
            self.skipTest("Node is optional for JavaScript asset tests")
        root = Path(__file__).resolve().parents[1]
        subprocess.run(
            ["node", "--test", str(root / "tests/test_assets.cjs")],
            check=True,
            capture_output=True,
            timeout=10,
        )


class BridgeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.bridge = BrowserBridge(
            "https://example.test/__TIME__", time.time_ns() + 5_000_000_000
        ).start()
        self.addCleanup(self.bridge.close)

    def connection(self):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.bridge.server.server_port, timeout=2
        )
        self.addCleanup(connection.close)
        return connection

    def arm(self):
        stream = self.connection()
        stream.request("GET", "/events/" + self.bridge.token)
        response = stream.getresponse()
        self.addCleanup(response.close)
        response.fp.readline()
        response.fp.readline()
        ack = self.connection()
        ack.request("POST", "/armed/" + self.bridge.token, headers={"Origin": self.bridge.origin})
        receipt = ack.getresponse()
        self.assertEqual(receipt.status, 204)
        receipt.read()
        return stream, response

    def test_preparation_never_sends_a_navigation(self):
        _, response = self.arm()
        self.bridge.wait_ready()
        self.assertFalse(select.select([response.fp], [], [], 0.02)[0])

    def test_closed_tab_rejects_dispatch(self):
        connection, response = self.arm()
        response.close()
        connection.close()
        self.assertTrue(self.bridge.disconnected.wait(1))
        with self.assertRaisesRegex(RuntimeError, "disconnected"):
            self.bridge.dispatch()

    def test_cancellation_closes_without_sending(self):
        _, response = self.arm()
        self.bridge.close()
        self.assertEqual(response.read(), b"")
        self.assertFalse(self.bridge.fired)

    def test_wrong_token_and_host_rejected(self):
        connection = self.connection()
        connection.request("GET", "/events/wrong")
        self.assertEqual(connection.getresponse().status, 404)
        connection.close()
        connection.request("GET", "/ready/" + self.bridge.token, headers={"Host": "wrong.test"})
        self.assertEqual(connection.getresponse().status, 403)

    def test_user_url_is_not_reinterpreted_as_template_markup(self):
        connection = self.connection()
        connection.request("GET", "/ready/" + self.bridge.token)
        self.assertIn(b"https://example.test/__TIME__", connection.getresponse().read())


class FailureTests(unittest.TestCase):
    def test_clients_closing_during_headers_are_normal_disconnects(self):
        for cls in (BridgeHandler, DemoHandler):
            handler = object.__new__(cls)
            handler.send_response = Mock(side_effect=ConnectionResetError)
            handler.reply(200)
            self.assertTrue(handler.close_connection)

    def test_event_stream_disconnect_during_headers_is_reported(self):
        handler = object.__new__(BridgeHandler)
        owner = Mock(claimed=False, lock=threading.Lock(), token="synthetic")
        owner.disconnected = threading.Event()
        handler.server = Mock(owner=owner)
        handler.connection = Mock()
        handler.path = "/events/synthetic"
        handler.valid_host = lambda: True
        handler.send_response = Mock(side_effect=BrokenPipeError)
        handler.do_GET()
        self.assertTrue(owner.disconnected.is_set())
        self.assertTrue(handler.close_connection)

    def test_invalid_timestamp_types_and_extreme_options_have_clear_errors(self):
        for text in (None, 123, b"2030-01-01T00:00:00Z"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "timestamp string"):
                Schedule.at(text)
        with self.assertRaisesRegex(ValueError, "finite"):
            Schedule.after(1, primed_seconds=10**1000)

    def test_invalid_unicode_url_is_rejected_before_opening(self):
        from timed_url_caller import TimedBrowserCaller

        with self.assertRaisesRegex(ValueError, "Unicode"):
            TimedBrowserCaller("https://example.test/\ud800", Schedule.after(1))

    def test_connection_cancellation_disconnects_client(self):
        controller = Mock()
        controller.chromium.connect_over_cdp.side_effect = KeyboardInterrupt
        adapter = Mock()
        adapter.start.return_value = controller
        module = ModuleType("playwright.sync_api")
        module.sync_playwright = lambda: adapter
        with patch.dict(sys.modules, {"playwright.sync_api": module}):
            with self.assertRaises(KeyboardInterrupt):
                BrowserConnection("http://127.0.0.1:9222").__enter__()
        controller.stop.assert_called_once()

    def test_quiet_display_needs_no_process_resources(self):
        with patch("multiprocessing.get_context", side_effect=AssertionError("unexpected IPC")):
            with ProgressDisplay(Schedule.after(1), enabled=False) as display:
                display.mark_ready()

    def test_unprepared_tab_never_shows_primed_spinner(self):
        stop = Mock()
        stop.is_set.side_effect = [False, False, True]
        with patch("progress.spinner.PieSpinner") as spinner, redirect_stderr(io.StringIO()):
            _render(time.time_ns() - 1_000_000, 10, threading.Event(), stop, False, "navigate")
        spinner.assert_not_called()

    def test_progress_runs_in_another_process(self):
        display = ProgressDisplay(Schedule.after(0.7, primed_seconds=0.3))
        with display:
            display.mark_ready()
            self.assertNotEqual(display.process.pid, os.getpid())
            time.sleep(0.6)
        self.assertEqual(display.process.exitcode, 0)

    def test_output_io_failure_is_a_friendly_cli_error(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("url_caller_bench.signaling.measure"),
            patch("url_caller_bench.cli.save_run", side_effect=OSError("disk full")),
            redirect_stderr(io.StringIO()) as errors,
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(
                benchmark_main(["--signal-only", "--samples", "1", "--output", folder]), 2
            )
        self.assertIn("Could not save", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
