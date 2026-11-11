"""Navigate to any HTTP(S) URL at T, or visit early and refresh at T.

Run timed-url-caller --help or scripts/call_url.py --help. Times need an offset
when absolute. Requests are best-effort by default, with no automatic retries.
"""

import argparse
import json
import multiprocessing
import sys

from .caller import TimedBrowserCaller
from .schedule import Schedule
from .timing.clock import positive


def main(argv=None, *, description=None):
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(
        description=description or __doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  uv run scripts/call_url.py https://example.com/ --after 15\n  uv run --group browser scripts/call_url.py https://example.com/ --after 20 --mode refresh --browser-url http://127.0.0.1:9222",
    )
    parser.add_argument("url", help="destination: any absolute http:// or https:// URL")
    when = parser.add_mutually_exclusive_group(required=True)
    when.add_argument("--after", type=positive, help="seconds from command start (for example 15)")
    when.add_argument("--at", help="ISO timestamp with Z or offset, e.g. 2030-01-01T12:00:00+01:00")
    parser.add_argument(
        "--mode",
        choices=("navigate", "refresh"),
        default="navigate",
        help="navigate at T (default), or visit early and reload at T",
    )
    parser.add_argument(
        "--browser-url",
        help="local browser control address, required for refresh; destination URLs are not restricted to local hosts",
    )
    parser.add_argument(
        "--max-late-ms",
        type=float,
        default=None,
        help="optional strict cutoff; otherwise dispatch once as soon as possible after T",
    )
    parser.add_argument(
        "--spin-ms",
        type=float,
        default=2,
        help="final busy-wait duration; 0 uses sleep only (default: 2)",
    )
    parser.add_argument(
        "--primed-seconds",
        type=float,
        default=10,
        help="switch ready progress to spinner this many seconds before T",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="disable indicators for embedded use or measurement",
    )
    parser.add_argument(
        "--force-terminal", action="store_true", help="render indicators in captured output"
    )
    args = parser.parse_args(argv)
    try:
        options = {
            "spin_ms": args.spin_ms,
            "max_late_ms": args.max_late_ms,
            "primed_seconds": args.primed_seconds,
        }
        schedule = (
            Schedule.at(args.at, **options) if args.at else Schedule.after(args.after, **options)
        )
        caller = TimedBrowserCaller(
            args.url,
            schedule,
            mode=args.mode,
            browser_url=args.browser_url,
            progress=not args.no_progress,
            force_terminal=args.force_terminal,
        )
        if args.mode == "refresh":
            print(
                "REFRESH: visiting the destination now, then reloading the prepared document once at T.\nKeep it visible; do not navigate or submit forms while armed. HTTP error pages may also be refreshed.",
                file=sys.stderr,
            )
        else:
            print(
                "NAVIGATE: opening a ready tab. The destination will be visited at T. Keep the tab visible and the computer awake.",
                file=sys.stderr,
            )
        print(
            "Timing: best-effort."
            if args.max_late_ms is None
            else f"Timing: reject actions more than {args.max_late_ms:g} ms late.",
            file=sys.stderr,
        )
        result = caller.run()
        print(
            "Action requested once. Your browser remains open. Dispatch does not confirm page load or HTTP success.",
            file=sys.stderr,
        )
        print(json.dumps(result.as_dict(), indent=2))
        return 0
    except KeyboardInterrupt:
        print(
            "Cancelled. No retry will be made. An early visit or an in-flight action cannot be undone.",
            file=sys.stderr,
        )
        return 130
    except Exception as exc:
        print(
            f"Could not complete the schedule: {(str(exc).splitlines() or [type(exc).__name__])[0]}\nNo automatic retry was made. Check the browser before scheduling again.",
            file=sys.stderr,
        )
        return 2
