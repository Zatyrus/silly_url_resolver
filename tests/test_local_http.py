"""Actual loopback HTTP/SSE, malformed input and independent visit records."""

import http.client
import json
import threading
import time
import unittest

from timed_url_caller.browser.bridge import BrowserBridge
from url_caller_demo import DemoServer
from url_caller_demo.http.recorder import Recorder


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.server = DemoServer(0)
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(1)

    def request(self, path="/", method="GET", body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_page_button_and_clock_assets(self):
        status, headers, body = self.request()
        self.assertEqual(status, 200)
        self.assertIn(b"Click me for some wisdom.", body)
        self.assertIn(b"CET", body)
        self.assertEqual(headers["Cache-Control"], "no-store")
        status, _, js = self.request("/demo.js")
        self.assertIn(b"Two plus two is four, minus one that's three; quick math.", js)
        self.assertIn(b"3600000", js)
        self.assertEqual(status, 200)

    def test_http_error_document_is_delivered(self):
        self.server.status_code = 503
        status, _, body = self.request()
        self.assertEqual(status, 503)
        self.assertIn(b"wisdom", body)

    def test_host_origin_and_malformed_json_rejected(self):
        self.assertEqual(self.request(headers={"Host": "evil.test"})[0], 403)
        self.assertEqual(
            self.request("/metrics", "POST", "{}", {"Origin": "https://evil.test"})[0], 403
        )
        for body in ("bad", "{}", "[]", '{"trial": 1}'):
            with self.subTest(body=body):
                self.assertEqual(self.request("/metrics", "POST", body)[0], 400)
        self.assertEqual(self.request("/metrics", "POST", "x" * 4097)[0], 413)
        self.assertEqual(
            self.request("/metrics", "POST", "", {"Transfer-Encoding": "chunked"})[0], 400
        )
        self.assertEqual(self.request("/missing")[0], 404)

    def test_each_document_gets_its_own_receipt(self):
        self.request("/?trial=abc")
        self.request("/?trial=abc")
        before = self.server.recorder.get("abc")
        first, second = [v["visit"] for v in before["visits"]]
        payload = {
            "trial": "abc",
            "visit": second,
            "event": "interactive",
            "navigation_type": "reload",
        }
        self.assertEqual(self.request("/metrics", "POST", json.dumps(payload))[0], 204)
        payload.update(visit=first, navigation_type="navigate")
        self.assertEqual(self.request("/metrics", "POST", json.dumps(payload))[0], 204)
        _, _, content = self.request("/metrics?trial=abc")
        row = json.loads(content)
        self.assertEqual(row["arrival_count"], 2)
        self.assertEqual(row["visits"][-1]["interactive_data"]["navigation_type"], "reload")
        payload["visit"] = "0" * 32
        self.assertEqual(self.request("/metrics", "POST", json.dumps(payload))[0], 404)

    def test_cache_option_affects_assets_only(self):
        self.server.cache_assets = True
        self.assertIn("max-age", self.request("/demo.css")[1]["Cache-Control"])
        self.assertEqual(self.request()[1]["Cache-Control"], "no-store")

    def test_trial_placeholder_text_stays_literal(self):
        _, _, body = self.request("/?trial=__VISIT__")
        self.assertIn(b'data-trial="__VISIT__"', body)
        self.assertEqual(self.server.recorder.get("__VISIT__")["arrival_count"], 1)

    def test_trial_is_escaped_and_bounded(self):
        self.assertIn(b"&quot;&gt;&lt;script&gt;", self.request("/?trial=%22%3E%3Cscript%3E")[2])
        self.assertEqual(self.request("/?trial=" + "x" * 81)[0], 400)


class RecorderTests(unittest.TestCase):
    def test_bounds_and_copy_isolation(self):
        recorder = Recorder(2)
        recorder.arrival("old")
        for _ in range(6):
            recorder.arrival("many")
        recorder.arrival("new")
        self.assertEqual(recorder.get("old"), {})
        row = recorder.get("many")
        self.assertEqual(row["arrival_count"], 6)
        self.assertEqual(len(row["visits"]), 4)
        row["visits"].clear()
        self.assertEqual(len(recorder.get("many")["visits"]), 4)

    def test_first_beacon_wins(self):
        recorder = Recorder()
        visit = recorder.arrival("a")
        recorder.interactive("a", visit, {"value": 1})
        first = recorder.get("a")
        recorder.interactive("a", visit, {"value": 2})
        self.assertEqual(recorder.get("a"), first)


class BridgeTests(unittest.TestCase):
    def test_real_sse_sends_any_url_once_after_readiness(self):
        target = "https://public-target.test/event?q=1#part"
        bridge = BrowserBridge(target, time.time_ns() + 5_000_000_000).start()
        event = http.client.HTTPConnection("127.0.0.1", bridge.server.server_port, timeout=2)
        ack = http.client.HTTPConnection("127.0.0.1", bridge.server.server_port, timeout=2)
        try:
            with self.assertRaisesRegex(RuntimeError, "No navigation"):
                bridge.dispatch()
            event.request("GET", "/events/" + bridge.token)
            stream = event.getresponse()
            self.assertEqual(stream.status, 200)
            self.assertEqual(stream.fp.readline(), b": connected\n")
            stream.fp.readline()
            ack.request("POST", "/armed/" + bridge.token, headers={"Origin": "https://evil.test"})
            self.assertEqual(ack.getresponse().status, 403)
            self.assertFalse(bridge.ready.is_set())
            ack.close()
            ack.request("POST", "/armed/" + bridge.token, headers={"Origin": bridge.origin})
            response = ack.getresponse()
            self.assertEqual(response.status, 204)
            response.read()
            bridge.wait_ready()
            bridge.dispatch()
            self.assertEqual(stream.fp.readline(), b"event: navigate\n")
            payload = json.loads(stream.fp.readline().removeprefix(b"data: "))
            self.assertEqual(payload, {"url": target, "expires_ms": None})
            with self.assertRaisesRegex(RuntimeError, "already attempted"):
                bridge.dispatch()
            ack.close()
            ack.request("GET", "/events/" + bridge.token)
            self.assertEqual(ack.getresponse().status, 409)
        finally:
            bridge.close()
            event.close()
            ack.close()

    def test_strict_expiry_is_preencoded(self):
        bridge = BrowserBridge("http://example.test", 1_000_000_000, max_late_ms=20)
        try:
            self.assertIn(b'"expires_ms": 1020.0', bridge.payload)
        finally:
            bridge.close()
            bridge.close()

    def test_readiness_timeout_is_clear(self):
        bridge = BrowserBridge("http://example.test", time.time_ns() + 5_000_000_000).start()
        try:
            with self.assertRaisesRegex(TimeoutError, "ready tab"):
                bridge.wait_ready(timeout=0.03)
        finally:
            bridge.close()


if __name__ == "__main__":
    unittest.main()
