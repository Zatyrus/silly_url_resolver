"""Serve the demo page and visit-specific benchmark metrics on loopback only."""

import html
import json
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit


class DemoHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def reply(self, status, data=b"", kind="text/plain; charset=utf-8", cache=False):
        self.close_connection = True
        try:
            self.send_response(status)
            for name, value in [
                ("Content-Type", kind),
                ("Content-Length", str(len(data))),
                ("Cache-Control", "public, max-age=3600" if cache else "no-store"),
                ("X-Content-Type-Options", "nosniff"),
                ("Connection", "close"),
            ]:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def valid_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def do_GET(self):
        if not self.valid_host():
            return self.reply(403)
        try:
            parts = urlsplit(self.path)
            trial = parse_qs(parts.query, max_num_fields=10).get("trial", [""])[0]
        except ValueError:
            return self.reply(400)
        if len(trial) > 80:
            return self.reply(400)
        if parts.path == "/":
            visit = self.server.recorder.arrival(trial)
            page = (
                self.server.assets["index.html"]
                .decode()
                .replace("__TIME__", str(time.time_ns() // 1_000_000))
            )
            page = page.replace("__VISIT__", visit).replace(
                "__TRIAL__", html.escape(trial, quote=True)
            )
            return self.reply(self.server.status_code, page.encode(), "text/html; charset=utf-8")
        if parts.path == "/metrics":
            return self.reply(
                200, json.dumps(self.server.recorder.get(trial)).encode(), "application/json"
            )
        for name, kind in [("demo.js", "text/javascript"), ("demo.css", "text/css")]:
            if parts.path == "/" + name:
                return self.reply(200, self.server.assets[name], kind, self.server.cache_assets)
        self.reply(404)

    def do_POST(self):
        if (
            not self.valid_host()
            or self.headers.get("Origin", self.server.url[:-1]) != self.server.url[:-1]
        ):
            return self.reply(403)
        if self.path != "/metrics":
            return self.reply(404)
        if self.headers.get("Transfer-Encoding"):
            return self.reply(400)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                return self.reply(413)
            data = json.loads(self.rfile.read(length))
            trial, visit = data["trial"], data["visit"]
            if (
                not isinstance(trial, str)
                or not 0 < len(trial) <= 80
                or not isinstance(visit, str)
                or len(visit) != 32
                or data.get("event") != "interactive"
            ):
                return self.reply(400)
        except (ValueError, KeyError, TypeError):
            return self.reply(400)
        except TimeoutError:
            return self.reply(408)
        accepted = self.server.recorder.interactive(trial, visit, data)
        self.reply(204 if accepted else 404)

    def log_message(self, *_):
        pass
