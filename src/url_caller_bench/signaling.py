"""Python scheduling plus loopback event receipt, not navigation or reload."""

import json
import random
import subprocess
import sys
import time

from timed_url_caller import Schedule, TimedBrowserCaller

from .local import stop_process


def measure(args, rows, metadata):
    rng = random.Random(4941)
    for index in range(-2, args.samples):
        cases = ["indicators_on", "indicators_off"]
        rng.shuffle(cases)
        for case in cases:
            process = None
            row = {
                "case": case,
                "iteration": index,
                "error": "Incomplete",
                "detail": "Run stopped before completion.",
            }
            if index >= 0:
                rows.append(row)

            def opener(url, **_):
                nonlocal process
                process = subprocess.Popen(
                    [sys.executable, "-m", "url_caller_bench.probe", url],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                return True

            try:
                cpu = time.process_time_ns()
                result = TimedBrowserCaller(
                    "http://127.0.0.1:9/not-visited",
                    Schedule.after(args.lead_seconds),
                    opener=opener,
                    progress=case == "indicators_on",
                    force_terminal=True,
                ).run()
                row.update(result.as_dict())
                row["caller_cpu_ms"] = (time.process_time_ns() - cpu) / 1e6
                stdout, stderr = process.communicate(timeout=5)
                if process.returncode:
                    raise RuntimeError(stderr.strip() or "Receiver failed.")
                received = json.loads(stdout)["event_received_ns"]
                row.update(
                    event_received_ns=received,
                    event_receipt_ms=(received - result.deadline_monotonic_ns) / 1e6,
                )
                row.pop("error", None)
                row.pop("detail", None)
            except Exception as exc:
                row.update(error=type(exc).__name__, detail=str(exc))
            finally:
                if process is not None:
                    stop_process(process)
            if index < 0 and "error" in row:
                metadata["warmup_errors"].append(row)
