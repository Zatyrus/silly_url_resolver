"""Internal ready-page and event-stream routes; one token, one tab, one signal."""

import html
import select
import socket
from http.server import BaseHTTPRequestHandler


class BridgeHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def reply(self, status, data=b"", kind="text/plain; charset=utf-8"):
        self.close_connection = True
        try:
            self.send_response(status)
            for name, value in [
                ("Content-Type", kind),
                ("Content-Length", str(len(data))),
                ("Cache-Control", "no-store"),
                ("Referrer-Policy", "no-referrer"),
                ("X-Content-Type-Options", "nosniff"),
                ("Connection", "close"),
            ]:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def valid_host(self):
        return self.headers.get("Host") == self.server.owner.origin.removeprefix("http://")

    def do_GET(self):
        owner = self.server.owner
        if not self.valid_host():
            return self.reply(403)
        if self.path == f"/ready/{owner.token}":
            page = owner.assets["ready.html"].decode().replace("__TOKEN__", owner.token)
            page = page.replace("__TIME__", str(owner.target_wall_ns // 1_000_000)).replace(
                "__URL__", html.escape(owner.url, quote=True)
            )
            return self.reply(200, page.encode(), "text/html; charset=utf-8")
        for name, kind in [("ready.js", "text/javascript"), ("ready.css", "text/css")]:
            if self.path == "/" + name:
                return self.reply(200, owner.assets[name], kind)
        if self.path != f"/events/{owner.token}":
            return self.reply(404)
        with owner.lock:
            if owner.claimed:
                return self.reply(409)
            owner.claimed = True
            owner.connection = self.connection
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while not owner.closed.is_set():
                if select.select([self.connection], [], [], 0.1)[0]:
                    if not self.connection.recv(1, socket.MSG_PEEK):
                        owner.disconnected.set()
                    break
        except OSError:
            owner.disconnected.set()
        self.close_connection = True

    def do_POST(self):
        owner = self.server.owner
        if (
            not self.valid_host()
            or self.headers.get("Origin") != owner.origin
            or self.path != f"/armed/{owner.token}"
            or owner.connection is None
        ):
            return self.reply(403)
        owner.ready.set()
        self.reply(204)

    def log_message(self, *_):
        pass
