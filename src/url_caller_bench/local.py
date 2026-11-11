"""A separate local server process and visit-specific metric collection."""

import json
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from queue import Empty, Queue
from urllib.request import ProxyHandler, build_opener

HTTP = build_opener(ProxyHandler({}))


def stop_process(process):
    if process.poll() is None:
        process.terminate()
    try:
        process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=5)


@contextmanager
def demo_process(cache=False):
    command = [sys.executable, "-m", "url_caller_demo", "--port", "0", "--json"]
    if cache:
        command.append("--cache-assets")
    with tempfile.TemporaryFile(mode="w+t") as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors, text=True)
        queue = Queue()
        reader = threading.Thread(target=lambda: queue.put(process.stdout.readline()), daemon=True)
        reader.start()
        try:
            try:
                line = queue.get(timeout=8)
            except Empty as exc:
                raise RuntimeError("The mock server did not start within 8 seconds.") from exc
            if not line:
                errors.seek(0)
                raise RuntimeError("Mock server startup failed: " + errors.read(1000))
            yield json.loads(line)["url"]
        finally:
            stop_process(process)
            reader.join(timeout=1)


def metrics(base, trial, count=1, timeout=5):
    until = time.monotonic() + timeout
    row = {}
    while time.monotonic() < until:
        with HTTP.open(f"{base}metrics?trial={trial}", timeout=2) as response:
            row = json.load(response)
        if row.get("arrival_count", 0) > count:
            raise RuntimeError("Unexpected duplicate document request.")
        if row.get("arrival_count") == count and "interactive_ns" in row["visits"][-1]:
            return row
        time.sleep(0.01)
    raise TimeoutError(f"No interactive receipt for document {count}; observations={row}")
