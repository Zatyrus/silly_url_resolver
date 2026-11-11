"""Prepare a default-browser tab and send one local event at T.

The destination can be any validated HTTP(S) URL. No destination request is
made by Python. The event payload is encoded before the timing-critical send.
"""

import json
import secrets
import socket
import threading
import time
from importlib.resources import files

from .bridge_handler import BridgeHandler
from .http_server import LoopbackServer


class BrowserBridge:
    def __init__(self, url, target_wall_ns, *, max_late_ms=None):
        self.url, self.target_wall_ns = url, target_wall_ns
        self.token = secrets.token_urlsafe(32)
        self.ready = threading.Event()
        self.closed = threading.Event()
        self.disconnected = threading.Event()
        self.connection = None
        self.claimed = False
        self.fired = False
        self.lock = threading.Lock()
        expiry = None if max_late_ms is None else target_wall_ns / 1e6 + max_late_ms
        self.payload = (
            "event: navigate\ndata: " + json.dumps({"url": url, "expires_ms": expiry}) + "\n\n"
        ).encode()
        self.assets = {
            name: files("timed_url_caller").joinpath("browser", "assets", name).read_bytes()
            for name in ("ready.html", "ready.js", "ready.css")
        }
        self.server = LoopbackServer(("127.0.0.1", 0), BridgeHandler)
        self.server.owner = self
        self.origin = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        self.started = False

    @property
    def landing_url(self):
        return f"{self.origin}/ready/{self.token}"

    def start(self):
        self.thread.start()
        self.started = True
        return self

    def wait_ready(self, timeout=30):
        limit = time.monotonic() + timeout
        while not self.ready.wait(0.02):
            if self.disconnected.is_set() or time.monotonic() >= limit:
                raise TimeoutError(
                    "The ready tab did not connect. Check your browser and choose a later time."
                )
            if time.time_ns() >= self.target_wall_ns - 100_000_000:
                raise TimeoutError(
                    "Browser setup missed the preparation deadline. Choose a later time."
                )
        if time.time_ns() >= self.target_wall_ns:
            raise TimeoutError("The browser became ready after the scheduled time.")

    def dispatch(self):
        if self.fired:
            raise RuntimeError("This navigation was already attempted; it will not be retried.")
        if not self.ready.is_set() or self.disconnected.is_set() or self.connection is None:
            raise RuntimeError("The ready tab disconnected. No navigation was sent.")
        self.fired = True
        try:
            self.connection.sendall(self.payload)
        except OSError as exc:
            raise RuntimeError(
                "Signal delivery is uncertain. No retry was made; check the browser."
            ) from exc

    def close(self):
        if self.closed.is_set():
            return
        self.closed.set()
        if self.connection is not None:
            try:
                self.connection.shutdown(socket.SHUT_WR)
            except OSError:
                pass
        if self.started:
            self.server.shutdown()
            self.thread.join(timeout=1)
        self.server.server_close()
