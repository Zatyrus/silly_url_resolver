"""Actual browser comparison: navigate/refresh, same controller, UI on/off.

Only the harness-created loopback URL is accepted by this internal measurement.
Refresh's early visit and timed visit have independent document IDs.
"""

import random
import uuid
from urllib.parse import urlsplit

from timed_url_caller import Schedule, TimedBrowserCaller
from timed_url_caller.browser.controlled_tab import ControlledTab

from .local import metrics

CASES = (
    "navigate_sse_ui",
    "navigate_sse_quiet",
    "navigate_cdp_ui",
    "navigate_cdp_quiet",
    "refresh_cdp_ui",
    "refresh_cdp_quiet",
)


def trial(page, base, case, lead, row=None):
    parts = urlsplit(base)
    if parts.scheme != "http" or parts.hostname != "127.0.0.1":
        raise ValueError("Benchmarks use only the local mock server.")
    mode, transport, ui = case.split("_")
    trial_id = uuid.uuid4().hex
    url = base + "?trial=" + trial_id
    expected = 2 if mode == "refresh" else 1
    row = {} if row is None else row
    row.update(trial=trial_id, expected_document_count=expected)
    options = (
        {"controlled_tab": ControlledTab(page)}
        if transport == "cdp"
        else {
            "opener": lambda url, **_: (
                page.goto(url, wait_until="domcontentloaded", timeout=10000) is not None
            )
        }
    )
    result = TimedBrowserCaller(
        url, Schedule.after(lead), mode=mode, progress=ui == "ui", force_terminal=True, **options
    ).run()
    row.update(result.as_dict())
    observed = metrics(base, trial_id, count=expected)
    visit = observed["visits"][-1]
    kind = visit["interactive_data"].get("navigation_type")
    if kind != ("reload" if mode == "refresh" else "navigate"):
        raise RuntimeError(f"Unexpected browser navigation type: {kind!r}.")
    deadline = result.deadline_monotonic_ns
    if visit["arrival_ns"] < deadline:
        raise RuntimeError("The timed request arrived before the deadline.")
    if mode == "refresh" and observed["visits"][0]["arrival_ns"] >= deadline:
        raise RuntimeError("The preload was not before the deadline.")
    row.update(
        arrival_count=observed["arrival_count"],
        navigation_type=kind,
        arrival_ms=(visit["arrival_ns"] - deadline) / 1e6,
        interactive_receipt_ms=(visit["interactive_ns"] - deadline) / 1e6,
        visits=observed["visits"],
    )
    return row


def preflight(browser, base):
    for case in ("navigate_sse_quiet", "navigate_cdp_quiet", "refresh_cdp_quiet"):
        with browser.new_context() as context:
            page = context.new_page()
            trial(page, base, case, 2)
            page.get_by_role("button", name="Click me for some wisdom.", exact=True).click()
            wisdom = page.locator("#wisdom")
            if (
                not wisdom.is_visible()
                or wisdom.inner_text()
                != "Two plus two is four, minus one that's three; quick math."
            ):
                raise RuntimeError("The wisdom button failed preflight.")
            before = page.locator("#clock").inner_text()
            page.wait_for_timeout(200)
            if before == page.locator("#clock").inner_text() or before == "—":
                raise RuntimeError("The clock is not ticking.")
    return {
        "status": "passed",
        "checks": [
            "SSE navigate",
            "CDP navigate",
            "CDP reload",
            "request counts",
            "button",
            "clock",
        ],
    }


def measure(browser, base, args, rows, metadata):
    rng = random.Random(7781)
    for index in range(-2, args.samples):
        cases = list(CASES)
        rng.shuffle(cases)
        for case in cases:
            row = {
                "case": case,
                "iteration": index,
                "error": "Incomplete",
                "detail": "Run stopped before completion.",
            }
            if index >= 0:
                rows.append(row)
            try:
                with browser.new_context() as context:
                    trial(context.new_page(), base, case, args.lead_seconds, row)
                row.pop("error", None)
                row.pop("detail", None)
            except Exception as exc:
                row.update(error=type(exc).__name__, detail=str(exc))
            if index < 0 and "error" in row:
                metadata["warmup_errors"].append(row)
