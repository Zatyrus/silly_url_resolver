"""Public local mock server: DemoServer(port=8765, cache_assets=False).

Use port=0 for an available loopback port. Call serve_forever() and shutdown()
like a standard Python HTTP server, or use scripts/mock_server.py.
"""

import socket
from http.server import ThreadingHTTPServer
from importlib.resources import files

from .http.handler import DemoHandler
from .http.recorder import Recorder


class DemoServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, port=8765, *, cache_assets=False, status_code=200):
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("Port must be an integer between 0 and 65535.")
        if type(status_code) is not int or status_code not in (200, 403, 404, 429, 500, 503):
            raise ValueError("Choose status 200, 403, 404, 429, 500 or 503.")
        self.assets = {
            name: files("url_caller_demo").joinpath("assets", name).read_bytes()
            for name in ("index.html", "demo.js", "demo.css")
        }
        self.recorder = Recorder()
        self.cache_assets = cache_assets
        self.status_code = status_code
        super().__init__(("127.0.0.1", port), DemoHandler)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_port}/"

    def get_request(self):
        connection, address = super().get_request()
        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        connection.settimeout(5)
        return connection, address
