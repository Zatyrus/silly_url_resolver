# One concise notebook

Open `notebooks/quickstart.ipynb` for a local tour of the package.

```sh
uv sync --locked --group notebook-only
uv run --locked --group notebook-only playwright install chromium
uv run --locked --group notebook-only jupyter lab notebooks/quickstart.ipynb
```

Select the Python kernel from this environment. The first cell checks that it
can find the installed package and project root. Run cells from top to bottom.

It introduces a deadline, navigate versus refresh, the public API, the independent
local server, tests and the browser benchmark. Terms are explained where used.
Interactive browser opening is opt-in, so “Run All” does not unexpectedly visit a
site or start an operator session. All demonstrated destinations are local.
Connected actions use a subprocess to avoid Jupyter's active event-loop conflict.

The browser comparison attempts real Chromium and preserves any launch failure.
A separate, explicitly labeled Python signaling diagnostic also runs. The final
cell displays the browser plot when available, otherwise the signaling plot with
a clear statement that no browser timing was measured. Outputs go to a fresh
`.notebook-runs` directory; rerunning does not overwrite an earlier measurement.

Before committing notebook changes, clear all outputs and execution counts.
Keep generated measurements under the ignored `.notebook-runs/` directory.
Both graph variants label delay in milliseconds (ms).
