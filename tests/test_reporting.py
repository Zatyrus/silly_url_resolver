"""Benchmark integrity and launcher help, without requiring Chromium."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from url_caller_bench.report import SIGNAL_FIELDS, claim_output, plot, save_run, summarize

ROOT = Path(__file__).resolve().parents[1]


class ReportingTests(unittest.TestCase):
    def test_nonempty_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            claim_output(path, True)
            with self.assertRaisesRegex(ValueError, "empty"):
                claim_output(path, True)

    def test_failed_and_slow_trials_remain_visible(self):
        rows = [{"case": "a", "dispatch_lateness_ms": v, "event_receipt_ms": v} for v in (1, 2, 30)]
        rows.append({"case": "a", "error": "TimeoutError"})
        result = summarize(rows, SIGNAL_FIELDS)["a"]
        self.assertEqual((result["attempts"], result["successes"], result["errors"]), (4, 3, 1))
        self.assertEqual(result["event_receipt_ms"]["ge_20ms"], 1)
        self.assertEqual(result["event_receipt_ms"]["p95"], 30)

    def test_blocked_run_has_no_plot(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            claim_output(path, False)
            save_run(path, [], {"signal_only": False}, "blocked", {"stage": "browser_launch"})
            self.assertFalse((path / "performance.png").exists())
            state = json.loads((path / "run_status.json").read_text())
            self.assertEqual(state["measured_attempts"], 0)
            self.assertFalse(state["performance_plot_generated"])
            summary = json.loads((path / "summary.json").read_text())
            self.assertEqual(summary["units"]["latency"], "ms")
            self.assertEqual(summary["units"]["timestamps"], "ns")

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "Requires the benchmark group")
    def test_both_plot_types_label_axes_and_ticks_with_units(self):
        for signal in (True, False):
            with self.subTest(signal_only=signal), tempfile.TemporaryDirectory() as folder:
                rows = [
                    {
                        "case": "indicators_on" if signal else "refresh_cdp_ui",
                        "dispatch_lateness_ms": 0.5,
                        "event_receipt_ms": 1.5,
                        "arrival_ms": 2.5,
                        "interactive_receipt_ms": 32.5,
                    }
                ]
                with patch("matplotlib.figure.Figure.savefig", autospec=True) as save:
                    plot(rows, Path(folder), {"signal_only": signal}, "completed")
                self.assertEqual(save.call_count, 2)  # PNG and SVG share the labeled figure.
                figure = save.call_args.args[0]
                self.assertEqual(len(figure.axes), 2 if signal else 3)
                for axis in figure.axes:
                    self.assertIn("(ms)", axis.get_ylabel())
                    self.assertIn("(ms)", axis.get_title())
                    self.assertEqual(axis.get_xlabel(), "Benchmark case")
                    lower, upper = axis.get_ylim()
                    visible_ticks = [t for t in axis.get_yticks() if lower <= t <= upper]
                    self.assertGreaterEqual(len(visible_ticks), 3)
                    self.assertIn(0, visible_ticks)
                    self.assertIn(20, visible_ticks)
                    self.assertTrue(
                        all(t.get_text().endswith(" ms") for t in axis.get_yticklabels())
                    )

    def test_plot_failure_removes_partial_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            claim_output(path, True)
            (path / "performance.png").write_bytes(b"partial")
            rows = [{"case": "a", "dispatch_lateness_ms": 1, "event_receipt_ms": 2}]
            with patch("url_caller_bench.report.plot", side_effect=RuntimeError("plot failed")):
                self.assertEqual(save_run(path, rows, {"signal_only": True}, "completed"), "failed")
            self.assertFalse((path / "performance.png").exists())
            self.assertTrue((path / "raw.csv").exists())

    def test_scripts_describe_introduction_instructions_help(self):
        for script in ("call_url.py", "mock_server.py", "open_browser.py", "benchmark.py"):
            with self.subTest(script=script):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / script), "--help"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                for heading in ("Introduction", "Instructions", "Help"):
                    self.assertIn(heading, result.stdout)

    def test_benchmark_has_no_public_target_option(self):
        result = subprocess.run(
            [sys.executable, "-m", "url_caller_bench", "--url", "https://example.test"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized arguments", result.stderr)


if __name__ == "__main__":
    unittest.main()
