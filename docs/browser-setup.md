# Chromium setup

The default `navigate` mode uses your normal graphical browser. Connected
navigation and refresh use Chromium's **Chrome DevTools Protocol (CDP)**: a local
control connection. Install the Python adapter and Chromium separately:

```sh
uv sync --locked --group browser
uv run --locked --group browser playwright install chromium
uv run --locked --group browser scripts/open_browser.py
```

The launcher enables remote debugging on `http://127.0.0.1:9222` and creates a
persistent profile in `.url-caller-profile`. It prints the address to pass to the
caller, then exits without closing Chromium:

```sh
uv run --locked --group browser scripts/call_url.py 'https://example.com/' --after 20 --mode refresh --browser-url http://127.0.0.1:9222
```

For connected navigation, change `--mode refresh` to `--mode navigate`.
The caller creates a new tab, leaves it open, and disconnects after dispatch.
It does not inspect, close or reuse your other tabs.

## Profiles and sign-in

A profile stores cookies, sign-in state and browser preferences. The dedicated
profile is separate from your everyday Chrome profile; sign in in this window
before scheduling if necessary. Only use an empty directory or one previously
created by this launcher. Recent Chrome versions require a nondefault profile
for remote debugging, and keeping one dedicated profile avoids interference.

The default profile is ignored by Git. For a custom `--profile`, choose a path
under `.local/` (for example, `.local/operator-browser`) or outside the repository
so the entire profile stays private. An arbitrary directory name is not
automatically covered by the repository's ignore rules.

The browser-control address must be `http://127.0.0.1:PORT`. The **destination**
URL has no such restriction. Keep the debugging service on loopback: software
that can reach it can control that browser. Close its window when finished.

## Existing browser executable

If Chromium is already installed, skip its download and pass an executable path:

```sh
uv run --locked --group browser scripts/open_browser.py --executable /usr/bin/chromium
```

On Windows, use a quoted full path to `chrome.exe`; on macOS, use the executable
inside the application bundle, such as
`"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"`.
Paths depend on your installation. The launcher accepts `--profile` and `--port`
if the defaults are unsuitable. Do not launch a second process on an occupied
control port; reuse the printed address or choose another port.

For manual setup, these are the essential arguments (substitute your executable
and a dedicated profile path):

```sh
chromium --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 --user-data-dir=/absolute/path/to/dedicated-profile
```

## Linux and restricted environments

A desktop/display session is needed for operator use. Some Linux installations
also need browser system libraries; Playwright documents the supported packages
and provides `uv run --group browser playwright install-deps chromium`. This may
need administrator privileges. Install it on your own machine as appropriate;
do not disable the browser sandbox to work around a managed host's restrictions.

The benchmark can run headlessly, but still needs a working Chromium executable
and permission to launch it. An environment that forbids browser subprocess
sockets cannot validate browser timing. The diagnostic `--signal-only` is a
separate measurement, not a replacement for real browser validation.

## Primary references

- [Playwright browser installation](https://playwright.dev/python/docs/browsers)
- [Playwright CDP connection](https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp)
- [Chrome remote debugging and profiles](https://developer.chrome.com/blog/remote-debugging-port)
