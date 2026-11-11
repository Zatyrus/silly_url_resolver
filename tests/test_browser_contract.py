"""Controller contracts using fakes; these are NOT real-browser validation."""

import json
import shutil
import subprocess
import time
import unittest
from unittest.mock import Mock

from timed_url_caller.browser.controlled_tab import ControlledTab, action_expression


class FakeSession:
    def __init__(self):
        self.calls = []
        self.callback = None
        self.detached = False
        self.result = {"result": {"value": "requested"}}

    def on(self, _, callback):
        self.callback = callback

    def remove_listener(self, *_):
        self.callback = None

    def send(self, method, parameters=None):
        self.calls.append((method, parameters))
        if method == "Page.getFrameTree":
            return {"frameTree": {"frame": {"id": "frame"}}}
        if method == "Page.createIsolatedWorld":
            self.callback(
                {
                    "context": {
                        "name": parameters["worldName"],
                        "id": 7,
                        "uniqueId": "globally-unique",
                    }
                }
            )
            return {"executionContextId": 7}
        return self.result

    def detach(self):
        self.detached = True


def fake_page(status=200):
    page = Mock(url="https://example.test/final")
    session = FakeSession()
    page.context.new_cdp_session.return_value = session
    page.goto.return_value.status = status
    return page, session


class ControllerTests(unittest.TestCase):
    def test_navigate_does_not_preload_destination(self):
        page, session = fake_page()
        tab = ControlledTab(page)
        tab.prepare("https://example.test/new", "navigate", time.time_ns() + 5_000_000_000)
        page.goto.assert_not_called()
        self.assertEqual(tab.parameters["uniqueContextId"], "globally-unique")
        self.assertNotIn("contextId", tab.parameters)
        tab.dispatch()
        self.assertEqual(session.calls[-1][0], "Runtime.evaluate")
        with self.assertRaisesRegex(RuntimeError, "already attempted"):
            tab.dispatch()

    def test_refresh_accepts_http_error_documents_and_keeps_final_url(self):
        for status in (200, 403, 404, 429, 500, 503):
            with self.subTest(status=status):
                page, _ = fake_page(status)
                tab = ControlledTab(page)
                tab.prepare(
                    "https://example.test/redirect", "refresh", time.time_ns() + 5_000_000_000
                )
                self.assertEqual(tab.preload_status, status)
                self.assertEqual(page.goto.call_args.kwargs["wait_until"], "domcontentloaded")
                self.assertIn("location.reload()", tab.parameters["expression"])
                self.assertIn("https://example.test/final", tab.parameters["expression"])

    def test_missing_document_rejected(self):
        page, _ = fake_page()
        page.goto.return_value = None
        with self.assertRaisesRegex(RuntimeError, "document"):
            ControlledTab(page).prepare(
                "https://example.test", "refresh", time.time_ns() + 5_000_000_000
            )

    def test_too_little_preparation_time(self):
        page, _ = fake_page()
        with self.assertRaises(TimeoutError):
            ControlledTab(page).prepare("https://example.test", "refresh", time.time_ns())
        page.goto.assert_not_called()

    def test_changed_expired_and_browser_exception_fail_without_retry(self):
        for outcome in ("changed", "expired", "already-fired", "exception"):
            with self.subTest(outcome=outcome):
                page, session = fake_page()
                tab = ControlledTab(page)
                tab.prepare("https://example.test", "navigate", time.time_ns() + 5_000_000_000)
                session.result = (
                    {"exceptionDetails": {}}
                    if outcome == "exception"
                    else {"result": {"value": outcome}}
                )
                with self.assertRaises((RuntimeError, TimeoutError)):
                    tab.dispatch()
                self.assertEqual(sum(m == "Runtime.evaluate" for m, _ in session.calls), 1)

    def test_close_detaches_only(self):
        page, session = fake_page()
        tab = ControlledTab(page)
        tab.prepare("https://example.test", "navigate", time.time_ns() + 5_000_000_000)
        tab.close()
        tab.close()
        self.assertTrue(session.detached)
        page.close.assert_not_called()

    def test_connection_failure_never_retries_an_uncertain_action(self):
        page, session = fake_page()
        tab = ControlledTab(page)
        tab.prepare("https://example.test", "navigate", time.time_ns() + 5_000_000_000)
        session.send = Mock(side_effect=OSError("connection lost"))
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            tab.dispatch()
        with self.assertRaisesRegex(RuntimeError, "already attempted"):
            tab.dispatch()
        session.send.assert_called_once()

    @unittest.skipUnless(
        shutil.which("node"), "Node is optional; needed for JavaScript contract test"
    )
    def test_actual_action_javascript_guards_and_modes(self):
        expressions = [
            action_expression("https://example.test/new", "https://example.test/old", mode, expiry)
            for mode, expiry in (("navigate", None), ("refresh", None), ("refresh", 100))
        ]
        code = r"""
const vm = require('node:vm');
const assert = require('node:assert/strict');
const expressions = JSON.parse(process.argv[1]);
for (let i = 0; i < expressions.length; i++) {
  let calls = [];
  const context = vm.createContext({Date: {now: () => 101}, location: {
    href: 'https://example.test/old', replace: u => calls.push(u), reload: () => calls.push('reload')
  }});
  assert.equal(vm.runInContext(expressions[i], context), i === 2 ? 'expired' : 'requested');
  assert.deepEqual(calls, i === 2 ? [] : [i === 0 ? 'https://example.test/new' : 'reload']);
  if (i < 2) assert.equal(vm.runInContext(expressions[i], context), 'already-fired');
  context.location.href = 'https://example.test/changed';
  assert.equal(vm.runInContext(expressions[0], context), 'changed');
}
"""
        subprocess.run(
            ["node", "-e", code, json.dumps(expressions)], check=True, capture_output=True
        )


if __name__ == "__main__":
    unittest.main()
