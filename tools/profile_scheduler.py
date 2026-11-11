"""Profile the Python wait loop without a browser, server or progress process.

Introduction: isolate scheduler work in one thread with a no-op callback.
Instrumentation changes timing; this is not a navigation performance benchmark.
Instructions: uv run python tools/profile_scheduler.py > scheduler-profile.txt
Help: --help shows the optional sample count. No URL is opened or requested.
"""

import argparse
import cProfile
import pstats

from timed_url_caller import Schedule
from timed_url_caller.timing.scheduler import Scheduler


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--samples", type=int, default=20, help="1..1000 waits of 100 ms each")
    args = parser.parse_args(argv)
    if not 1 <= args.samples <= 1000:
        parser.error("Use a sample count between 1 and 1000.")
    print("Single-thread scheduler profile; no-op dispatch; no browser or network.")
    print("Instrumentation changes timing. Use the separate benchmark for latency.\n")
    profile = cProfile.Profile()
    with profile:
        for _ in range(args.samples):
            Scheduler(Schedule.after(0.1)).run(lambda: None)
    pstats.Stats(profile).strip_dirs().sort_stats("cumulative").print_stats(30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
