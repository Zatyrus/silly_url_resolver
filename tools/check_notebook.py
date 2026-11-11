"""Execute notebook code cells as ordinary Python, without starting a kernel.

Instructions: uv run --group notebook-only python tools/check_notebook.py
This is a cell-level smoke check, not a Jupyter UI/kernel test. It runs only the
notebook's local tests and benchmarks; interactive browser opening stays off.
"""

import json
import os
import time
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    notebook = json.loads((root / "notebooks" / "quickstart.ipynb").read_text())
    namespace = {"__name__": "notebook_cell_check"}
    started = time.monotonic()
    executed = 0
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        print(f"Executing code cell {index}", flush=True)
        exec(compile("".join(cell["source"]), f"notebook-cell-{index}", "exec"), namespace)
        executed += 1
    state = {
        "validation": "ordinary Python cell execution; not a Jupyter kernel",
        "status": "passed",
        "code_cells": executed,
        "seconds": round(time.monotonic() - started, 2),
        "browser_status": namespace["browser_state"]["status"],
        "signal_status": namespace["signal_state"]["status"],
        "selected_plot_kind": (
            "browser"
            if namespace["browser_state"]["performance_plot_generated"]
            else "signal-only"
            if namespace["chosen"]
            else None
        ),
        "note": "Smoke-run outputs belong in ignored local directories.",
    }
    destination = root / ".validation"
    destination.mkdir(exist_ok=True)
    (destination / "notebook-cells.json").write_text(json.dumps(state, indent=2) + "\n")
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
