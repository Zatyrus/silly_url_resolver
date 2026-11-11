"""Main public workflow: prepare, wait, request one action, leave the browser open.

Example: TimedBrowserCaller(URL, Schedule.after(15)).run(). Refresh requires
browser_url. Use a guarded Python script or the supplied CLI for visible UI.
"""

import time
import webbrowser
from contextlib import nullcontext

from ._validation import validate_endpoint, validate_url
from .browser.bridge import BrowserBridge
from .browser.connection import BrowserConnection
from .schedule import Schedule
from .timing.scheduler import Scheduler
from .ui.progress import ProgressDisplay


class TimedBrowserCaller:
    def __init__(
        self,
        url,
        schedule,
        *,
        mode="navigate",
        browser_url=None,
        progress=True,
        force_terminal=False,
        opener=None,
        controlled_tab=None,
    ):
        self.url = validate_url(url)
        if not isinstance(schedule, Schedule):
            raise ValueError("Pass a Schedule.after(...) or Schedule.at(...) configuration.")
        if mode not in ("navigate", "refresh"):
            raise ValueError("Mode must be navigate or refresh.")
        if browser_url:
            validate_endpoint(browser_url)
        if mode == "refresh" and not (browser_url or controlled_tab):
            raise ValueError(
                "Refresh needs a connected browser. Run scripts/open_browser.py and add its --browser-url."
            )
        if opener and (browser_url or controlled_tab):
            raise ValueError("Choose either the default-browser opener or a controlled tab.")
        if browser_url and controlled_tab:
            raise ValueError("Choose either browser_url or controlled_tab, not both.")
        self.schedule, self.mode = schedule, mode
        self.browser_url, self.controlled_tab = browser_url, controlled_tab
        self.progress, self.force_terminal, self.opener = progress, force_terminal, opener
        self.used = False

    def run(self):
        if self.used:
            raise RuntimeError("This schedule was already used. Create a new caller.")
        self.used = True
        left = self.schedule.target_wall_ns - time.time_ns()
        if left <= 0:
            raise ValueError("The scheduled time has passed. Choose a future time.")
        if left > 31_536_000_000_000_000:
            raise ValueError("Choose a time within the next 365 days.")
        with ProgressDisplay(
            self.schedule, self.progress, self.force_terminal, self.mode
        ) as display:
            if self.browser_url or self.controlled_tab:
                connection = (
                    BrowserConnection(self.browser_url)
                    if self.browser_url
                    else nullcontext(self.controlled_tab)
                )
                with connection as tab:
                    try:
                        tab.prepare(
                            self.url,
                            self.mode,
                            self.schedule.target_wall_ns,
                            max_late_ms=self.schedule.max_late_ms,
                        )
                        display.mark_ready()
                        return Scheduler(self.schedule).run(
                            tab.dispatch, mode=self.mode, transport="cdp"
                        )
                    finally:
                        tab.close()
            opener = self.opener or webbrowser.get().open
            bridge = BrowserBridge(
                self.url, self.schedule.target_wall_ns, max_late_ms=self.schedule.max_late_ms
            )
            try:
                bridge.start()
                if not opener(bridge.landing_url, new=2, autoraise=True):
                    raise RuntimeError("Could not open your graphical default browser.")
                bridge.wait_ready()
                display.mark_ready()
                return Scheduler(self.schedule).run(
                    bridge.dispatch, mode="navigate", transport="sse"
                )
            finally:
                bridge.close()
