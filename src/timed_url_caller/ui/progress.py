"""Rich progress bar and PieSpinner in a separate spawned process.

Rendering is limited to 10 Hz and pauses in the final 100 ms. Use a guarded
Python entry point or the supplied CLI/scripts when enabling the process.
"""

import multiprocessing
import sys
import time


def _render(target, primed_seconds, ready, stop, force_terminal, mode):
    from progress.spinner import PieSpinner
    from rich.console import Console
    from rich.progress import Progress

    total = max(0.001, (target - time.time_ns()) / 1e9 - primed_seconds)
    console = Console(file=sys.stderr, force_terminal=force_terminal or None)
    label = (
        "Visiting early; waiting to refresh"
        if mode == "refresh"
        else "Preparing; waiting to navigate"
    )
    with Progress(console=console, auto_refresh=False) as bar:
        task = bar.add_task(label, total=total)
        while not stop.is_set():
            left = (target - time.time_ns()) / 1e9
            if ready.is_set() and left <= primed_seconds:
                bar.update(task, completed=total)
                bar.refresh()
                break
            if left <= 0.1:
                break
            bar.update(task, completed=min(total, max(0, total - max(0, left - primed_seconds))))
            bar.refresh()
            stop.wait(0.1)
    if stop.is_set() or not ready.is_set():
        return  # A deadline approaching does not mean browser setup succeeded.
    with PieSpinner(
        message=f"Primed... {mode} at the scheduled time ",
        fill="█",
        empty_fill="░",
        file=sys.stderr,
        check_tty=not force_terminal,
    ) as spinner:
        while not stop.is_set():
            if (target - time.time_ns()) / 1e9 > 0.1:
                spinner.next()
            stop.wait(0.1)


class ProgressDisplay:
    def __init__(self, schedule, enabled=True, force_terminal=False, mode="navigate"):
        self.enabled = enabled
        if not enabled:
            return  # Quiet embedded use needs no multiprocessing resources.
        context = multiprocessing.get_context("spawn")
        self.ready = context.Event()
        self.stop = context.Event()
        self.process = context.Process(
            target=_render,
            args=(
                schedule.target_wall_ns,
                schedule.primed_seconds,
                self.ready,
                self.stop,
                force_terminal,
                mode,
            ),
            daemon=True,
        )

    def __enter__(self):
        if self.enabled:
            self.process.start()
        return self

    def mark_ready(self):
        if self.enabled:
            self.ready.set()

    def __exit__(self, *_):
        if self.enabled:
            self.stop.set()
            self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=1)
