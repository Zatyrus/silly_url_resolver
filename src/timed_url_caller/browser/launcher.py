"""Start a dedicated Chromium profile with debugging restricted to loopback.

Run scripts/open_browser.py --help. This starts an independent browser process,
prints the connection address, then exits without closing the browser.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import ProxyHandler, build_opener


def launch_browser(profile, port=9222, executable=None):
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Choose a browser port between 1 and 65535.")
    profile = Path(profile).resolve()
    marker = profile / ".url-caller-owned"
    if profile.exists() and any(profile.iterdir()) and not marker.is_file():
        raise ValueError(
            "Choose an empty profile directory. Existing browser profiles are not used."
        )
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise ValueError(
                f"Port {port} is already in use. Use the existing browser address or choose --port with a free port."
            ) from exc
    if executable is None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Run: uv sync --locked --group browser") from exc
        with sync_playwright() as p:
            executable = p.chromium.executable_path
    executable = Path(executable).expanduser().resolve()
    if not executable.is_file():
        raise ValueError(
            "Chromium is missing. Run: uv run --group browser playwright install chromium"
        )
    profile.mkdir(parents=True, exist_ok=True)
    marker.touch(exist_ok=True)
    log_path = profile / "launcher.log"
    arguments = [
        str(executable),
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "about:blank",
    ]
    detach = (
        {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    with log_path.open("a") as log:
        process = subprocess.Popen(
            arguments, stdin=subprocess.DEVNULL, stdout=log, stderr=log, **detach
        )
    endpoint = f"http://127.0.0.1:{port}"
    local_http = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and process.poll() is None:
        try:
            with local_http.open(endpoint + "/json/version", timeout=0.3) as response:
                data = json.load(response)
            if data.get("webSocketDebuggerUrl"):
                return {"browser_url": endpoint, "profile": str(profile), "pid": process.pid}
        except (OSError, ValueError):
            time.sleep(0.1)
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
    raise RuntimeError(
        f"Chromium did not become ready. Check {log_path}. A graphical desktop is required."
    )


def main(argv=None, *, description=None):
    parser = argparse.ArgumentParser(
        description=description or __doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path(".url-caller-profile"),
        help="dedicated profile directory (default: .url-caller-profile)",
    )
    parser.add_argument(
        "--port", type=int, default=9222, help="loopback debugging port (default: 9222)"
    )
    parser.add_argument(
        "--executable",
        type=Path,
        help="optional full path to an existing Chrome/Chromium executable",
    )
    parser.add_argument("--json", action="store_true", help="print connection information as JSON")
    args = parser.parse_args(argv)
    try:
        result = launch_browser(args.profile, args.port, args.executable)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Could not start the browser: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(result)
        if args.json
        else f"Browser ready. Add --browser-url {result['browser_url']} to your caller command.\nSign in using this dedicated profile if needed. Close the browser window when finished."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
