"""Internal Python SSE receiver for signaling-only diagnostics; not a browser.

It timestamps one loopback event and NEVER visits the event's destination URL.
"""

import http.client
import json
import sys
import time
from urllib.parse import urlsplit


def main():
    parts = urlsplit(sys.argv[1])
    if (
        parts.scheme != "http"
        or parts.hostname != "127.0.0.1"
        or not parts.path.startswith("/ready/")
    ):
        raise ValueError("The probe accepts only a local ready-page URL.")
    token = parts.path.removeprefix("/ready/")
    origin = f"http://127.0.0.1:{parts.port}"
    connection = http.client.HTTPConnection("127.0.0.1", parts.port, timeout=5)
    try:
        connection.request("GET", "/events/" + token)
        stream = connection.getresponse()
        if stream.status != 200:
            raise RuntimeError("Could not open the local event stream.")
        stream.fp.readline()
        stream.fp.readline()
        ack = http.client.HTTPConnection("127.0.0.1", parts.port, timeout=5)
        try:
            ack.request("POST", "/armed/" + token, headers={"Origin": origin})
            response = ack.getresponse()
            if response.status != 204:
                raise RuntimeError("Readiness was rejected.")
            response.read()
        finally:
            ack.close()
        if stream.fp.readline() != b"event: navigate\n":
            raise RuntimeError("Stream ended without an action.")
        data = stream.fp.readline()
        received = time.monotonic_ns()
        json.loads(data.removeprefix(b"data: "))
        print(json.dumps({"event_received_ns": received}), flush=True)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
