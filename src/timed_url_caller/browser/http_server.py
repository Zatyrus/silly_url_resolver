"""Private loopback HTTP server for the caller's ready page, not the demo."""

import socket
from http.server import ThreadingHTTPServer


class LoopbackServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def get_request(self):
        connection, address = super().get_request()
        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        connection.settimeout(5)
        return connection, address
