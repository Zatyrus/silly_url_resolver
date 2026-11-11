# URL Caller

Schedule a browser page, then continue working in it by hand. Choose between
**navigate** (first destination visit at the deadline) and **refresh** (visit
in advance, then reload the prepared document at the deadline).

Targets can be public sites, intranet pages or local servers, provided they are
absolute HTTP(S) URLs supported by the browser. The mock server is optional and
exists only for demos, tests and benchmarks. Start with `README.md` in the
project root for installation, script examples and the full quick start.

## Get started in five minutes

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), clone or extract the
project and open a terminal in its root directory:

```sh
uv sync --locked
uv run --locked scripts/mock_server.py
```

Leave that server running. In a second terminal in the same directory:

```sh
uv run --locked scripts/call_url.py http://127.0.0.1:8765/ --after 15
```

A ready tab opens now; the destination opens after 15 seconds. Click the wisdom
button to confirm the page is usable. Stop the server with Ctrl+C.
A graphical default browser is required for this interactive demo. The page
clock is seeded from the server response and is for display only; it does not
control scheduling.

Replace the URL with your own HTTP(S) destination for real use. No mock server
is required. See [Chromium setup](browser-setup.md) to enable refresh.

## Find your next step

- [Select a mode and deadline](usage.md).
- [Run the scripts](cli.md) or [call the Python API](api.md).
- [Measure local timing](testing.md) or [open the notebook](notebook.md).
- [Resolve common errors](troubleshooting.md).

Read these Markdown pages on GitHub, or run the searchable documentation site:

```sh
uv run --locked --group docs mkdocs serve --dev-addr 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/` and use the search box. Build static HTML with
`uv run --locked --group docs mkdocs build --strict`; the generated `site/`
directory is ignored by Git.

## Read timings correctly

The caller reports **dispatch lateness**: when Python starts sending the prepared
action relative to its deadline. A usable page comes later. Network and browser
work mean that a universal “page usable within 20 ms” guarantee is not possible.
The benchmarks separate dispatch, document arrival and an interactive receipt.
