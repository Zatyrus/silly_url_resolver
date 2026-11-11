"""Public API, input validation and deadline policy; no destination requests."""

import subprocess
import sys
import time
import unittest
from unittest.mock import Mock, patch

from timed_url_caller import CallResult, Schedule, TimedBrowserCaller
from timed_url_caller._validation import validate_endpoint, validate_url
from timed_url_caller.timing.clock import parse_at
from timed_url_caller.timing.scheduler import Scheduler


class ValidationTests(unittest.TestCase):
    def test_arbitrary_http_targets_are_not_local_only(self):
        for url in (
            "https://example.test/a?q=yes#part",
            "http://intranet:8080/",
            "https://[::1]/",
            "https://münchen.test/",
        ):
            with self.subTest(url=url):
                self.assertEqual(validate_url(url), url)
                TimedBrowserCaller(url, Schedule.after(10), progress=False)

    def test_bad_urls(self):
        for value in (
            None,
            "",
            "/relative",
            "javascript:alert(1)",
            "file:///tmp/a",
            "https://",
            "https://user:pass@host/",
            "http://a:0",
            "http://a:65536",
            "http://a:bad",
            "http://a/\n",
            "http://a\\b",
            "http://[bad]/",
            "http://a/" + "x" * 8192,
        ):
            with self.subTest(value=str(value)[:40]), self.assertRaises(ValueError):
                validate_url(value)

    def test_control_endpoint_is_separate(self):
        self.assertEqual(validate_endpoint("http://127.0.0.1:9222/"), "http://127.0.0.1:9222")
        for value in (
            "https://example.test/",
            "http://localhost:9222",
            "http://127.0.0.1",
            "http://127.0.0.1:9222/path",
            "http://127.0.0.1:9222/?x=1",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_endpoint(value)

    def test_absolute_time_requires_offset(self):
        self.assertEqual(parse_at("2030-01-01T12:00:00+01:00"), parse_at("2030-01-01T11:00:00Z"))
        for value in ("2030-01-01T12:00:00", "tomorrow", "0001-01-01T00:00:00+01:00", None):
            with self.assertRaises(ValueError):
                parse_at(value)

    def test_schedule_rejects_nonfinite_and_invalid_options(self):
        for seconds in (0, -1, float("nan"), float("inf"), True, 31_536_001):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                Schedule.after(seconds)
        for options in (
            {"spin_ms": 51},
            {"spin_ms": -1},
            {"max_late_ms": float("nan")},
            {"primed_seconds": -1},
            {"spin_ms": True},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                Schedule.after(1, **options)
        with self.assertRaises(ValueError):
            Schedule(True)

    def test_mode_and_backend_errors(self):
        for options in (
            {"mode": "post"},
            {"mode": "refresh"},
            {"browser_url": "https://remote.test"},
            {"opener": Mock(), "controlled_tab": Mock()},
            {"browser_url": "http://127.0.0.1:9222", "controlled_tab": Mock()},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                TimedBrowserCaller("https://example.test", Schedule.after(5), **options)

    def test_public_imports_have_no_server_or_browser_side_effect(self):
        code = "import sys; import timed_url_caller, url_caller_demo; assert 'playwright.sync_api' not in sys.modules; assert 'url_caller_bench' not in sys.modules; from timed_url_caller import Schedule, TimedBrowserCaller, CallResult; from url_caller_demo import DemoServer"
        subprocess.run([sys.executable, "-c", code], check=True, capture_output=True)


class TimingTests(unittest.TestCase):
    def test_best_effort_dispatches_even_when_late(self):
        action = Mock()
        with (
            patch("timed_url_caller.timing.scheduler.final_deadline", return_value=100),
            patch("timed_url_caller.timing.scheduler.wait_until"),
            patch("timed_url_caller.timing.scheduler.time.monotonic_ns", return_value=50_000_100),
        ):
            result = Scheduler(Schedule.after(1)).run(action)
        action.assert_called_once_with()
        self.assertEqual(result.as_dict()["dispatch_lateness_ms"], 50)

    def test_strict_cutoff_does_not_dispatch(self):
        action = Mock()
        with (
            patch("timed_url_caller.timing.scheduler.final_deadline", return_value=100),
            patch("timed_url_caller.timing.scheduler.wait_until"),
            patch("timed_url_caller.timing.scheduler.time.monotonic_ns", return_value=50_000_100),
        ):
            with self.assertRaisesRegex(TimeoutError, "no action"):
                Scheduler(Schedule.after(1, max_late_ms=20)).run(action)
        action.assert_not_called()

    def test_real_wait_is_not_early(self):
        result = Scheduler(Schedule.after(0.04)).run(lambda: None)
        self.assertGreaterEqual(result.dispatch_ns, result.deadline_monotonic_ns)

    def test_failed_callback_is_not_retried(self):
        action = Mock(side_effect=RuntimeError("uncertain"))
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            Scheduler(Schedule.after(0.02)).run(action)
        action.assert_called_once()

    def test_caller_prepares_then_dispatches_once_and_closes_controller(self):
        tab = Mock()
        caller = TimedBrowserCaller(
            "https://example.test/sale",
            Schedule.after(0.04),
            mode="refresh",
            controlled_tab=tab,
            progress=False,
        )
        result = caller.run()
        self.assertIsInstance(result, CallResult)
        self.assertEqual([c[0] for c in tab.mock_calls], ["prepare", "dispatch", "close"])
        self.assertEqual(tab.prepare.call_args.args[:2], ("https://example.test/sale", "refresh"))
        with self.assertRaisesRegex(RuntimeError, "already used"):
            caller.run()

    def test_setup_failure_never_dispatches(self):
        tab = Mock()
        tab.prepare.side_effect = RuntimeError("setup failed")
        with self.assertRaisesRegex(RuntimeError, "setup failed"):
            TimedBrowserCaller(
                "http://example.test", Schedule.after(5), controlled_tab=tab, progress=False
            ).run()
        tab.dispatch.assert_not_called()
        tab.close.assert_called_once()

    def test_past_and_too_far_future_fail_before_browser(self):
        for target in (time.time_ns() - 1, time.time_ns() + 32_000_000_000_000_000):
            opener = Mock()
            with self.assertRaises(ValueError):
                TimedBrowserCaller(
                    "https://example.test", Schedule(target), opener=opener, progress=False
                ).run()
            opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
