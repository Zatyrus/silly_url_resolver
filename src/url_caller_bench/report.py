"""Fresh output directories, honest summaries and plots of measured samples."""

import csv
import json
import math
import random
from datetime import datetime, timezone

BROWSER_FIELDS = ("dispatch_lateness_ms", "arrival_ms", "interactive_receipt_ms")
SIGNAL_FIELDS = ("dispatch_lateness_ms", "event_receipt_ms")
LABELS = {
    "navigate_sse_ui": "Navigate SSE\nUI on",
    "navigate_sse_quiet": "Navigate SSE\nUI off",
    "navigate_cdp_ui": "Navigate CDP\nUI on",
    "navigate_cdp_quiet": "Navigate CDP\nUI off",
    "refresh_cdp_ui": "Refresh CDP\nUI on",
    "refresh_cdp_quiet": "Refresh CDP\nUI off",
    "indicators_on": "Signals only\nUI on",
    "indicators_off": "Signals only\nUI off",
}


def claim_output(path, signal):
    path.mkdir(parents=True, exist_ok=True)
    if any(path.iterdir()):
        raise ValueError(f"Choose a new or empty output directory: {path}")
    with (path / "run_status.json").open("x") as stream:
        json.dump(
            {
                "status": "running",
                "mode": "signal-only" if signal else "browser",
                "started_utc": datetime.now(timezone.utc).isoformat(),
            },
            stream,
            indent=2,
        )


def summarize(rows, fields):
    result = {}
    for case in dict.fromkeys(r["case"] for r in rows):
        selected = [r for r in rows if r["case"] == case]
        good = [r for r in selected if "error" not in r]
        item = {
            "attempts": len(selected),
            "successes": len(good),
            "errors": len(selected) - len(good),
        }
        for field in fields:
            values = sorted(r[field] for r in good)
            if values:
                item[field] = {
                    f"p{p}": values[math.ceil(p / 100 * len(values)) - 1] for p in (50, 95, 99)
                }
                item[field].update(
                    max=max(values),
                    ge_20ms=sum(v >= 20 for v in values),
                    early=sum(v < 0 for v in values),
                )
        result[case] = item
    return result


def plot(rows, path, metadata, status):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, SymmetricalLogLocator

    signal = metadata["signal_only"]
    fields = SIGNAL_FIELDS if signal else BROWSER_FIELDS
    titles = (
        ("Python dispatch", "Python event receipt")
        if signal
        else ("Python dispatch", "Document arrival", "Interactive receipt")
    )
    cases = list(dict.fromkeys(r["case"] for r in rows))
    fig, axes = plt.subplots(
        1, len(fields), figsize=(12 if signal else 16, 6), constrained_layout=True
    )
    randomizer = random.Random(84)
    colors = ["#087f77", "#5bb6a9", "#2158b1", "#6d97da", "#ae580d", "#ce9a67"]
    for ax, field, title in zip(axes, fields, titles):
        for index, case in enumerate(cases):
            values = sorted(r[field] for r in rows if r["case"] == case and "error" not in r)
            if not values:
                continue
            ax.scatter(
                [index + randomizer.uniform(-0.12, 0.12) for _ in values],
                values,
                s=17,
                alpha=0.65,
                color=colors[index % len(colors)],
            )
            median, p95 = (values[math.ceil(len(values) * q) - 1] for q in (0.5, 0.95))
            ax.plot([index - 0.2, index + 0.2], [median, median], color="#14202b", lw=2)
            ax.plot(index, p95, "D", color="#14202b", ms=5)
        ax.axhline(20, color="#b42318", ls="--", lw=1)
        ax.set_yscale("symlog", linthresh=1)
        # Include the deadline baseline and useful ticks even when all samples
        # fall between logarithmic powers (for example, between 10 and 100 ms).
        ax.set_ylim(bottom=min(0, ax.get_ylim()[0]))
        ax.yaxis.set_major_locator(SymmetricalLogLocator(base=10, linthresh=1, subs=(1, 2, 5)))
        ax.set_xticks(
            range(len(cases)),
            [LABELS.get(n, n) for n in cases],
            rotation=15,
            fontsize=8,
        )
        ax.set_ylabel("Delay relative to scheduled time (ms)")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g} ms"))
        ax.set_xlabel("Benchmark case")
        ax.set_title(f"{title} (ms)", weight="bold")
        ax.grid(axis="y", alpha=0.2)
        ax.spines[["top", "right"]].set_visible(False)
    title = (
        "Python signaling ONLY — no browser measured"
        if signal
        else "Navigate vs refresh — loopback Chromium"
    )
    fig.suptitle(title, fontsize=16, weight="bold")
    failures = sum("error" in r for r in rows)
    scope = (
        "No navigation, reload or rendering measured."
        if signal
        else "Interactive receipt includes two animation frames + beacon; not physical screen paint."
    )
    fig.supxlabel(
        f"Dots: successes | line: median | diamond: p95 | dashed: 20 ms | failures: {failures}/{len(rows)} | {status}\n"
        f"Scale: linear within ±1 ms, logarithmic beyond. {scope}",
        fontsize=9,
    )
    try:
        for extension in ("png", "svg"):
            fig.savefig(path / f"performance.{extension}", dpi=180)
    finally:
        plt.close(fig)


def save_run(path, rows, metadata, status, failure=None):
    if rows:
        with (path / "raw.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=sorted({k for r in rows for k in r}))
            writer.writeheader()
            writer.writerows(
                {k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in r.items()}
                for r in rows
            )
    successful = sum("error" not in r for r in rows)
    generated = False
    if successful:
        try:
            plot(rows, path, metadata, status)
            generated = True
        except Exception as exc:
            status = "failed"
            failure = {"stage": "plot", "type": type(exc).__name__, "message": str(exc)}
            for suffix in ("png", "svg"):
                (path / f"performance.{suffix}").unlink(missing_ok=True)
    fields = SIGNAL_FIELDS if metadata["signal_only"] else BROWSER_FIELDS
    report = {
        "status": status,
        "units": {
            "latency": "ms",
            "timestamps": "ns",
            "caller_cpu_time": "ms",
            "counts": "count",
        },
        "metadata": metadata,
        "results": summarize(rows, fields),
        "failure": failure,
    }
    (path / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    state = json.loads((path / "run_status.json").read_text())
    state.update(
        status=status,
        finished_utc=datetime.now(timezone.utc).isoformat(),
        measured_attempts=len(rows),
        successful_trials=successful,
        performance_plot_generated=generated,
        failure=failure,
    )
    temporary = path / "run_status.tmp"
    temporary.write_text(json.dumps(state, indent=2) + "\n")
    temporary.replace(path / "run_status.json")
    return status
