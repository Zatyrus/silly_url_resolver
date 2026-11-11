"""Measure local browser navigation/refresh and export PNG/SVG plots.

No public target can be supplied. Use --signal-only for a clearly labelled
Python event diagnostic; it does not measure browser navigation or refresh.
"""

import argparse
import json
import math
import platform
import sys
from pathlib import Path

from timed_url_caller import __version__

from .local import demo_process
from .report import claim_output, save_run


def main(argv=None, *, description=None):
    parser = argparse.ArgumentParser(
        description=description or __doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--samples", type=int, default=30, help="measured trials per case (default: 30)"
    )
    parser.add_argument(
        "--lead-seconds", type=float, default=1, help="preparation lead per trial (default: 1)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-results"),
        help="new or empty output directory",
    )
    parser.add_argument("--headed", action="store_true", help="show the private benchmark browser")
    parser.add_argument(
        "--cache-assets", action="store_true", help="allow mock-server JS/CSS caching"
    )
    parser.add_argument("--executable", type=Path, help="optional installed Chromium executable")
    parser.add_argument(
        "--signal-only", action="store_true", help="Python + loopback SSE only; no browser"
    )
    args = parser.parse_args(argv)
    if (
        not 1 <= args.samples <= 10000
        or not math.isfinite(args.lead_seconds)
        or not 0.3 <= args.lead_seconds <= 60
    ):
        parser.error("Use 1..10000 samples and a lead between 0.3 and 60 seconds.")
    if args.signal_only and (args.headed or args.cache_assets or args.executable):
        parser.error("--signal-only cannot use browser options.")
    try:
        claim_output(args.output, args.signal_only)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    rows = []
    metadata = {
        "package_version": __version__,
        "python": sys.version,
        "platform": platform.platform(),
        "signal_only": args.signal_only,
        "samples_per_case": args.samples,
        "lead_seconds": args.lead_seconds,
        "headed": args.headed,
        "cache_assets": args.cache_assets,
        "late_policy": "best-effort; no 20 ms sample censoring",
        "warmup_errors": [],
        "scope": "Python receiver only; no browser."
        if args.signal_only
        else "Warm private browser; fresh context per trial; loopback only. Automation flags differ from an ordinary profile.",
    }
    stage = "dependencies"
    failure = None
    try:
        if args.signal_only:
            from .signaling import measure

            stage = "signal_measurement"
            measure(args, rows, metadata)
        else:
            from playwright.sync_api import sync_playwright

            from .browser import measure, preflight

            stage = "mock_server_start"
            with demo_process(args.cache_assets) as base:
                stage = "browser_launch"
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=not args.headed,
                        executable_path=str(args.executable) if args.executable else None,
                        args=["--disable-background-networking"],
                    )
                    try:
                        metadata["browser_version"] = browser.version
                        stage = "preflight"
                        metadata["preflight"] = preflight(browser, base)
                        stage = "browser_measurement"
                        measure(browser, base, args, rows, metadata)
                    finally:
                        browser.close()  # This benchmark owns it; production callers never do this.
        status = "completed_with_errors" if any("error" in r for r in rows) else "completed"
    except KeyboardInterrupt:
        status = "interrupted"
        failure = {"stage": stage, "type": "KeyboardInterrupt", "message": "Cancelled by operator."}
    except Exception as exc:
        status = "failed" if rows else "blocked"
        failure = {"stage": stage, "type": type(exc).__name__, "message": str(exc)[:6000]}
    try:
        status = save_run(args.output, rows, metadata, status, failure)
    except OSError as exc:
        print(
            f"Could not save the benchmark results: {exc}. Check free space and output-directory permissions. Any files already written were retained.",
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {"status": status, "measured_attempts": len(rows), "output": str(args.output)}, indent=2
        )
    )
    return {"completed": 0, "completed_with_errors": 1, "interrupted": 130}.get(status, 2)
