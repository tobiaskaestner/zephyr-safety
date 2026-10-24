#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Plot latency distributions from run logs.

    plot.py ccdf  --out f.svg [--title T] [--label L]... LOG ...
    plot.py hist  --out f.svg [--title T] [--label L]... LOG ...
    plot.py phase --out f.svg [--title T] [--label L]... [--hist H] LOG ...

ccdf: exceedance probability P(latency > x) on a log scale, one line per
      log. It shows the floor, the modes and the tail in one chart.
hist: one panel per log, sample count per 1-cycle bin on a log scale.
phase: two panels per log, by the tick phase of the stimulus edge: the
      share of the samples (1 = uniform), and min, mean and max latency.
      --hist selects the phase histogram.

The default label of a log is "<tree>/<point>" from its run folder path.
"""

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import latbench  # noqa: E402

# Categorical slots in fixed order (validated: dataviz reference palette,
# light mode). Slots 3 and 4 are below 3:1 contrast, so every chart has a
# legend and the report has a table.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT2 = "#52514e"
GRID = "#e4e3df"


def style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(TEXT2)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=TEXT2, labelsize=8)
    ax.grid(True, which="major", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def values(hist):
    """Return (value, count) pairs, sorted by value. An overflow bin counts at 2^e.

    With coarse bins, 2^e of the first overflow bin can be less than the
    last coarse edges, so the list is sorted after the overflow bins are in.

    A value of 2^31 or more is a negative difference (the ISR ran before
    the edge time), so it is not a latency. An old log has these samples in
    overflow bin 31. They are left out here and named in the label (see
    invalid()).
    """
    pairs = list(hist["bins"].items())
    pairs += [((1 << e), c) for e, c in hist["ovf_log2"].items() if e < 31]
    return sorted(pairs)


def invalid(hist):
    return latbench.invalid(hist)


def max_text(hist):
    bad = invalid(hist)
    if not bad:
        return f"max {hist['max']}"
    if "invalid" in hist:
        # A new log: max is the largest valid sample.
        valid = hist["max"] if hist["n"] else None
    else:
        # An old log: max is a negative difference. Use the largest bin.
        pairs = values(hist)
        valid = max(v for v, _ in pairs) if pairs else None
    return f"max {'-' if valid is None else valid}, {bad} negative"


def pick(run, name):
    return run["hists"][name] if name else next(iter(run["hists"].values()))


def load(args):
    runs = []
    for i, path in enumerate(args.logs):
        run = latbench.parse_log(path)
        label = args.label[i] if args.label and i < len(args.label) else "/".join(Path(path).parts[-3:-1])
        hz = int(run["meta"].get("core_hz", 0))
        runs.append((label, run, hz))
    if len(runs) > len(SERIES):
        sys.exit(f"at most {len(SERIES)} logs per chart")
    return runs


def subtitle(runs):
    first = runs[0][1]["meta"]
    hz = {r[2] for r in runs}
    clock = f"{runs[0][2] / 1e6:g} MHz" if len(hz) == 1 else "mixed clocks"
    n = next(iter(runs[0][1]["hists"].values()))["n"]
    return f"{first.get('board', '')}, {clock}, n = {n:,} per series"


def ccdf(args):
    runs = load(args)
    fig, ax = plt.subplots(figsize=(8, 4.6), facecolor=SURFACE)
    style(ax)
    for i, (label, run, _) in enumerate(runs):
        h = pick(run, args.hist)
        n = h["n"]
        xs, ys = [], []
        above = n
        for v, c in values(h):
            xs.append(v)
            ys.append(above / n)
            above -= c
            xs.append(v)
            ys.append(max(above, 0.5) / n)
        ax.plot(xs, ys, color=SERIES[i], linewidth=2, label=f"{label}  ({max_text(h)})", drawstyle="default")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_ylim(0.3 / max(pick(r[1], args.hist)["n"] for r in runs), 1.5)
    ax.set_xlabel("latency (core cycles)", color=TEXT2, fontsize=9)
    ax.set_ylabel("P(latency > x)", color=TEXT2, fontsize=9)
    fig.suptitle(args.title or "IRQ latency: exceedance probability", color=TEXT, fontsize=11, x=0.01, ha="left")
    fig.text(0.01, 0.905, subtitle(runs), color=TEXT2, fontsize=8, ha="left")
    leg = ax.legend(frameon=False, fontsize=8, loc="upper right", labelcolor=TEXT)
    for line in leg.get_lines():
        line.set_linewidth(2)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(args.out, facecolor=SURFACE)
    print(f"saved {args.out}")


def hist(args):
    runs = load(args)
    fig, axes = plt.subplots(len(runs), 1, figsize=(8, 1.7 * len(runs) + 0.8), sharex=True, facecolor=SURFACE)
    if len(runs) == 1:
        axes = [axes]
    for i, (ax, (label, run, _)) in enumerate(zip(axes, runs)):
        style(ax)
        h = pick(run, args.hist)
        # A coarse bin shows its count per cycle, so that the scale stays the same.
        width = h.get("width", {})
        pairs = [(v, c / width.get(v, 1)) for v, c in values(h)]
        ax.vlines([v for v, _ in pairs], 0.7, [c for _, c in pairs], color=SERIES[i], linewidth=1.5)
        ax.plot([v for v, c in pairs if c <= 3], [c for _, c in pairs if c <= 3], "o", color=SERIES[i],
                markersize=3, markeredgewidth=0)
        ax.set_yscale("log")
        ax.set_ylim(0.7, h["n"] * 2)
        p9999 = latbench.quantile(h, 0.9999)
        ax.set_title(
            f"{label}   min {h['min']}   p50 {latbench.quantile(h, 0.5)}   p99.99 {p9999}   {max_text(h)}",
            color=TEXT, fontsize=9, loc="left",
        )
        ax.set_ylabel("samples / cycle" if width else "samples", color=TEXT2, fontsize=8)
    axes[-1].set_xscale("log")
    axes[-1].set_xlabel("latency (core cycles)", color=TEXT2, fontsize=9)
    fig.suptitle(args.title or "IRQ latency: samples per 1-cycle bin", color=TEXT, fontsize=11, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(args.out, facecolor=SURFACE)
    print(f"saved {args.out}")


def phase(args):
    runs = load(args)
    fig, axes = plt.subplots(2 * len(runs), 1, figsize=(8, 2.6 * len(runs) + 0.8), sharex=True, facecolor=SURFACE,
                             gridspec_kw={"height_ratios": [1, 2] * len(runs)})
    for i, (label, run, _) in enumerate(runs):
        ph = run["phases"][args.hist] if args.hist else next(iter(run["phases"].values()))
        nbins, period = ph["nbins"], ph["period"]
        width = period / nbins
        rows = sorted(ph["bins"].items())
        n = sum(r["count"] for _, r in rows)
        xs = [(b + 0.5) * width for b, _ in rows]
        ax_n, ax_v = axes[2 * i], axes[2 * i + 1]
        style(ax_n)
        style(ax_v)
        ax_n.bar(xs, [r["count"] * nbins / n for _, r in rows], width=width - 2 * width / 8, color=SERIES[i])
        ax_n.axhline(1.0, color=TEXT2, linewidth=0.8)
        ax_n.set_ylabel("share\n(1 = uniform)", color=TEXT2, fontsize=8)
        ax_n.set_title(f"{label}   {ph['name']}   n {n:,}   {nbins} bins of {width:.0f} cycles",
                       color=TEXT, fontsize=9, loc="left")
        ax_v.plot(xs, [r["sum"] / r["count"] for _, r in rows], color=SERIES[i], linewidth=2, label="mean")
        ax_v.plot(xs, [r["min"] for _, r in rows], color=SERIES[i], linewidth=1, linestyle="--", label="min")
        ax_v.plot(xs, [r["max"] for _, r in rows], "o", color=SERIES[i], markersize=3, markeredgewidth=0,
                  label="max")
        ax_v.set_yscale("log")
        ax_v.set_ylabel("latency (cycles)", color=TEXT2, fontsize=8)
        ax_v.legend(frameon=False, fontsize=8, loc="upper right", labelcolor=TEXT, ncol=3)
    axes[-1].set_xlim(0, period)
    axes[-1].set_xlabel("tick phase of the stimulus edge (cycles after the tick boundary)", color=TEXT2, fontsize=9)
    fig.suptitle(args.title or "Latency by tick phase", color=TEXT, fontsize=11, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(args.out, facecolor=SURFACE)
    print(f"saved {args.out}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kind", choices=["ccdf", "hist", "phase"])
    p.add_argument("--out", required=True)
    p.add_argument("--title")
    p.add_argument("--label", action="append", help="label of the next log, once per log")
    p.add_argument("--hist", default=None, help="histogram name (default: the first in each log)")
    p.add_argument("logs", nargs="+")
    args = p.parse_args()
    {"ccdf": ccdf, "hist": hist, "phase": phase}[args.kind](args)


if __name__ == "__main__":
    main()
