"""Prepare one connected Chromium document for navigation or true reload.

All setup runs before T. The deadline command uses one isolated, globally unique
execution context so it cannot accidentally act on a replacement document.
"""

import html
import json
import secrets
import time

from .._validation import validate_url


def action_expression(url, expected, mode, expires_ms):
    expiry = "" if expires_ms is None else f'if (Date.now() > {expires_ms}) return "expired";'
    action = "location.reload()" if mode == "refresh" else f"location.replace({json.dumps(url)})"
    return (
        "(() => {" + expiry + f'if (location.href !== {json.dumps(expected)}) return "changed";'
        'if (globalThis.__urlCallerFired) return "already-fired";'
        "globalThis.__urlCallerFired=true;" + action + '; return "requested";})()'
    )


class ControlledTab:
    def __init__(self, page):
        self.page = page
        self.session = None
        self.parameters = None
        self.attempted = False
        self.preload_status = None

    def prepare(self, url, mode, target_wall_ns, *, max_late_ms=None):
        validate_url(url)
        if mode not in ("navigate", "refresh"):
            raise ValueError("Choose navigate or refresh.")
        if self.parameters is not None or self.attempted:
            raise RuntimeError("This tab has already been prepared. Create a new schedule.")
        remaining = (target_wall_ns - time.time_ns()) / 1e6 - 100
        if remaining <= 0:
            raise TimeoutError("Not enough preparation time. Choose a later time.")
        timeout = min(30_000, remaining)
        self.page.set_default_timeout(timeout)
        self.page.bring_to_front()
        if mode == "refresh":
            # HTTP 4xx/5xx responses are still documents that can be refreshed.
            # Network failures, downloads and unsupported navigation still raise.
            response = self.page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            if response is None:
                raise RuntimeError("The early visit did not produce a document to refresh.")
            self.preload_status = response.status
            validate_url(self.page.url)
        else:
            self.page.set_content(
                '<!doctype html><meta charset="utf-8"><title>Ready to navigate</title>'
                "<h1>Waiting to open your page</h1><p>The destination has not been visited.</p>"
                f"<p>{html.escape(url)}</p><p>Keep this tab visible; watch the terminal countdown.</p>",
                timeout=timeout,
            )
        self.session = self.page.context.new_cdp_session(self.page)
        name = "url-caller-" + secrets.token_hex(12)
        description = {}

        def capture(event):
            context = event.get("context", {})
            if context.get("name") == name:
                description.update(context)

        self.session.on("Runtime.executionContextCreated", capture)
        self.session.send("Runtime.enable")
        tree = self.session.send("Page.getFrameTree")
        world = self.session.send(
            "Page.createIsolatedWorld",
            {"frameId": tree["frameTree"]["frame"]["id"], "worldName": name},
        )
        if not description:
            self.page.wait_for_timeout(10)  # Preparation-only event drain.
        if description.get("id") != world["executionContextId"] or not description.get("uniqueId"):
            raise RuntimeError(
                "Could not bind the prepared document safely. Update Chromium and try again."
            )
        self.session.remove_listener("Runtime.executionContextCreated", capture)
        expiry = None if max_late_ms is None else target_wall_ns / 1e6 + max_late_ms
        self.parameters = {
            "expression": action_expression(url, self.page.url, mode, expiry),
            "uniqueContextId": description["uniqueId"],
            "returnByValue": True,
            "timeout": 1000,
            "allowUnsafeEvalBlockedByCSP": False,
        }
        if time.time_ns() >= target_wall_ns - 100_000_000:
            raise TimeoutError("Preparation finished too late. No timed action was sent.")

    def dispatch(self):
        if self.attempted:
            raise RuntimeError("This action was already attempted; it will not be repeated.")
        if self.parameters is None or self.session is None:
            raise RuntimeError("The tab has not been prepared.")
        self.attempted = True
        try:
            response = self.session.send("Runtime.evaluate", self.parameters)
        except Exception as exc:
            raise RuntimeError(
                "The tab changed, closed or stopped responding. Delivery is uncertain; no retry was made."
            ) from exc
        if response.get("exceptionDetails"):
            raise RuntimeError("The browser could not perform the action. No retry was made.")
        outcome = response.get("result", {}).get("value")
        if outcome == "expired":
            raise TimeoutError(
                "The browser exceeded the maximum lateness. No new action was requested."
            )
        if outcome != "requested":
            raise RuntimeError(
                "The prepared document changed or was already used. No new action was requested."
            )

    def close(self):
        if self.session is not None:
            try:
                self.session.detach()
            except Exception:
                pass
            self.session = None
