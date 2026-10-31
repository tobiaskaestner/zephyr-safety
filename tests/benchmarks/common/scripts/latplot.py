# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The standard plots of an experiment: the common part of the plot scripts of the apps.

Each app has tests/benchmarks/<app>/scripts/plot.py. It calls main() of this
module with its name and its main metrics. The results build (study.py
analysis build) runs it once for each experiment of an instance:

    plot.py OUT_DIR RUN_ID=APP_JSON ...

APP_JSON is the app data of a run that is not excluded (<UTC>.<app>.json,
from the extractor); RUN_ID can have the role in parentheses, for example
"irq-smoke/20261028T001313Z (adjustment)". The plots go to OUT_DIR (ex-<experiment>/plots/ of the instance):

    overview-<metric>[-<k>].svg   the exceedance probability of each point (the
                                  newest run), at most 8 points in one chart
    ccdf-<metric>-<tree>-<point>.svg
                                  the exceedance probability of one point, one
                                  line for each run (the newest 8)
    hist-<metric>-<tree>-<point>.svg
                                  the histogram of one point (the newest run)
    plots.json                    the list of the plots and the digest of the inputs

If plots.json has the digest of the same inputs (the app data and the plot
scripts), nothing is drawn again. The SVG files have no date and a fixed
hash salt, so the same inputs and the same matplotlib give the same bytes.
"""

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from probatrix.benchmarks import plot as base  # noqa: E402  (the style and the colours of scripts/probatrix/benchmarks/plot.py)

FORMAT = "latbench-plots/1"
PER_CHART = len(base.SERIES)


def pairs(h):
    """(value, count) of a histogram of the app data: the fine bins, the coarse bins at their lower
    edge and the overflow bins at 2^e."""
    out = [(v, c) for v, c in h.get("bins", [])]
    out += [(v, c) for v, c, _ in h.get("coarse", [])]
    out += [(1 << e, c) for e, c in h.get("ovf_log2", []) if e < 31]
    return sorted(out)


def ccdf_xy(h):
    n = sum(c for _, c in pairs(h))
    xs, ys, above = [], [], n
    for v, c in pairs(h):
        xs.append(v)
        ys.append(above / n)
        above -= c
        xs.append(v)
        ys.append(max(above, 0.5) / n)
    return xs, ys, n


def figure():
    plt.rcParams["svg.hashsalt"] = "latbench"
    fig, ax = plt.subplots(figsize=(8, 4.6), facecolor=base.SURFACE)
    base.style(ax)
    return fig, ax


def save(fig, path):
    fig.savefig(path, format="svg", metadata={"Date": None, "Creator": None}, bbox_inches="tight")
    plt.close(fig)


def ccdf_chart(path, title, series):
    """series: [(label, hist)], at most PER_CHART."""
    fig, ax = figure()
    nmax = 1
    for i, (label, h) in enumerate(series):
        xs, ys, n = ccdf_xy(h)
        if not xs:
            continue
        nmax = max(nmax, n)
        ax.plot(xs, ys, color=base.SERIES[i], linewidth=2, label=f"{label}  (max {h.get('max')})")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_ylim(0.3 / nmax, 1.5)
    ax.set_xlabel("latency (core cycles)", color=base.TEXT2, fontsize=9)
    ax.set_ylabel("share of samples >= x", color=base.TEXT2, fontsize=9)
    ax.set_title(title, color=base.TEXT, fontsize=10, loc="left")
    ax.legend(fontsize=7, frameon=False, labelcolor=base.TEXT)
    save(fig, path)


def hist_chart(path, title, h):
    fig, ax = figure()
    ps = pairs(h)
    if ps:
        ax.bar([v for v, _ in ps], [c for _, c in ps], width=1.0, color=base.SERIES[0], linewidth=0)
    ax.set_yscale("log")
    ax.set_xlabel("latency (core cycles)", color=base.TEXT2, fontsize=9)
    ax.set_ylabel("samples per bin", color=base.TEXT2, fontsize=9)
    ax.set_title(title, color=base.TEXT, fontsize=10, loc="left")
    save(fig, path)


def safe(name):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


def digest(files):
    h = hashlib.sha256()
    for f in files:
        h.update(Path(f).name.encode())
        h.update(hashlib.sha256(Path(f).read_bytes()).digest())
    return h.hexdigest()


def plot_experiment(app, metrics, out, runs, scripts):
    """runs: [(run id, app data file)], oldest first; return the plots.json data."""
    out = Path(out)
    inputs = digest([f for _, f in runs] + list(scripts))
    index = out / "plots.json"
    if index.is_file():
        old = json.loads(index.read_text())
        if old.get("inputs") == inputs and all((out / p["file"]).is_file() for p in old.get("plots", [])):
            return old
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.svg"):
        f.unlink()
    data = [(rid, json.loads(Path(f).read_text())) for rid, f in runs]
    plots = []
    newest = data[-1][1] if data else None
    for metric in metrics:
        pts = [p for p in (newest or {}).get("points", []) if metric in p["reps"][0].get("hists", {})]
        for k in range(0, len(pts), PER_CHART):
            chunk = pts[k:k + PER_CHART]
            name = f"overview-{safe(metric)}" + (f"-{k // PER_CHART + 1}" if len(pts) > PER_CHART else "") + ".svg"
            ccdf_chart(out / name, f"{metric}: each point, run {data[-1][0]}",
                       [(f"{p['tree']}/{p['point']}", p["reps"][0]["hists"][metric]) for p in chunk])
            plots.append({"file": name, "kind": "overview", "metric": metric})
        for p in pts:
            tag = f"{safe(metric)}-{safe(p['tree'])}-{safe(p['point'])}"
            series = []
            for rid, d in data[-PER_CHART:]:
                q = next((x for x in d.get("points", []) if x["tree"] == p["tree"] and x["point"] == p["point"]), None)
                if q and metric in q["reps"][0].get("hists", {}):
                    series.append((rid.split("/", 1)[-1], q["reps"][0]["hists"][metric]))
            ccdf_chart(out / f"ccdf-{tag}.svg", f"{metric}: {p['tree']}/{p['point']}, each run", series)
            hist_chart(out / f"hist-{tag}.svg", f"{metric}: {p['tree']}/{p['point']}, run {data[-1][0]}",
                       p["reps"][0]["hists"][metric])
            plots += [{"file": f"ccdf-{tag}.svg", "kind": "ccdf", "metric": metric, "tree": p["tree"],
                       "point": p["point"]},
                      {"file": f"hist-{tag}.svg", "kind": "hist", "metric": metric, "tree": p["tree"],
                       "point": p["point"]}]
    res = {"format": FORMAT, "app": app, "inputs": inputs, "runs": [rid for rid, _ in runs], "plots": plots}
    index.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    return res


def main(app, metrics):
    """plot.py OUT_DIR RUN_ID=APP_JSON ... of an app."""
    if len(sys.argv) < 3:
        sys.exit(f"usage: plot.py OUT_DIR RUN_ID=APP_JSON ...  (the plots of an experiment of {app})")
    runs = [tuple(a.split("=", 1)) for a in sys.argv[2:]]
    scripts = [Path(sys.modules["__main__"].__file__), Path(__file__), REPO / "scripts" / "probatrix" / "benchmarks" / "plot.py"]
    res = plot_experiment(app, metrics, sys.argv[1], runs, scripts)
    print(f"{len(res['plots'])} plots in {sys.argv[1]}")
