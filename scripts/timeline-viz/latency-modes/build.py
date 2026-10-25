#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Build the latency-modes page from template.html, cards/ and the run logs.

Usage: build.py --results <dir> -o <page.html>

<dir> is the folder that holds the result folders of run.py
(<experiment>/<stamp>/<tree>/<point>/rep1.log). The page data comes only
from result folders of pinned runs.
"""
import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tests" / "benchmarks" / "scripts"))
from latbench import parse_log, quantile  # noqa: E402

sys.path.insert(0, str(HERE.parent))
import tdl  # noqa: E402

RESULTS = None  # set by main()

# Histograms: all bins as [value, count] (1-cycle bins only).
HISTS = {
    "irq_direct": ("irq-baseline-1m/20261024T155016Z/ws-safety/direct-idle/rep1.log", "irq"),
    "irq_zli": ("irq-baseline-1m/20261024T155016Z/ws-safety/zli-idle/rep1.log", "irq"),
    "isr2thr_sem": ("wake-isr-1m/20261024T170705Z/ws-safety/wrapped-sem/rep1.log", "isr2thr"),
}

# CCDF curves: [value, P(latency >= value)], reduced.
CCDFS = {
    "irq_t0": ("wake-timers-1m/20261024T225125Z/ws-safety/t0-default/rep1.log", "irq"),
    "irq_t256_same": ("systick-prio-1m/20261025T051643Z/ws-safety/t256-same/rep1.log", "irq"),
    "irq_t256_lower": ("systick-prio-1m/20261025T051643Z/ws-safety/t256-lower/rep1.log", "irq"),
    "thr_t0_noslice": ("wake-timers-1m/20261024T225125Z/ws-safety/t0-noslice/rep1.log", "isr2thr"),
    "thr_t0": ("wake-timers-1m/20261024T225125Z/ws-safety/t0-default/rep1.log", "isr2thr"),
    "thr_t256_wheel": ("timeout-backends-1m/20261025T040826Z/ws-safety/wheel/rep1.log", "isr2thr"),
    "thr_t256_dlist": ("timeout-backends-1m/20261025T040826Z/ws-safety/dlist/rep1.log", "isr2thr"),
    "anc_legacy": ("wake-anchors-1m/20261024T174308Z/ws-safety/default-legacy/rep1.log", "isr2thr"),
    "anc_switch": ("wake-anchors-1m/20261024T174308Z/ws-safety/default-switch/rep1.log", "isr2thr"),
    "anc_noslice_legacy": ("wake-anchors-1m/20261024T174308Z/ws-safety/noslice-legacy/rep1.log", "isr2thr"),
    "anc_noslice_switch": ("wake-anchors-1m/20261024T174308Z/ws-safety/noslice-switch/rep1.log", "isr2thr"),
    "t2t_sem": ("thread2thread-switch/20261025T100427Z/ws-safety/sem-legacy/rep1.log", "t2t"),
    "t2t_sem_up": ("thread2thread-switch/20261025T100427Z/ws-up/sem-legacy/rep1.log", "t2t"),
    "t2t_sem_sw": ("thread2thread-switch/20261025T100427Z/ws-safety/sem-switch/rep1.log", "t2t"),
    "t2t_sem_sw_up": ("thread2thread-switch/20261025T100427Z/ws-up/sem-switch/rep1.log", "t2t"),
}


def load(rel, name):
    run = parse_log(RESULTS / rel)
    h = run["hists"][name]
    if h.get("invalid", 0) or h.get("overflow", 0):
        raise SystemExit(f"{rel}: {name} has invalid or overflow samples")
    return run, h


def hist_entry(rel, name):
    _, h = load(rel, name)
    if h["width"]:
        raise SystemExit(f"{rel}: coarse bins are not supported for a histogram")
    return {"n": h["n"], "source": rel, "bins": sorted([v, c] for v, c in h["bins"].items())}


def ccdf_entry(rel, name):
    run, h = load(rel, name)
    n = h["n"]
    pts = []
    rest = n
    for v in sorted(h["bins"]):
        pts.append((v, rest / n))
        rest -= h["bins"][v]
    # Keep a point if the curve moved by 0.4 % in log x or 0.02 in log y.
    out = [pts[0]]
    for i, (v, s) in enumerate(pts[1:], 1):
        lv, ls = out[-1]
        last = i == len(pts) - 1
        if last or abs(math.log10(s) - math.log10(ls)) > 0.02 or math.log10(v / lv) > 0.004:
            out.append((v, s))
    if out[-1][0] != h["max"]:
        out.append((h["max"], 1 / n))
    return {
        "n": n, "source": rel, "max": h["max"], "mean": h["mean"],
        "q": {k: quantile(h, q) for k, q in (("p50", 0.5), ("p99", 0.99), ("p99.99", 0.9999))},
        # older logs (before the drift check) have no drift
        "drift_ppm": (round(1e6 * int(run["meta"]["clock_drift_cyc"]) / int(run["meta"]["clock_elapsed_cyc"]), 1)
                      if "clock_drift_cyc" in run["meta"] else None),
        "pts": [[v, float(f"{s:.4g}")] for v, s in out],
    }


def tdl_cards():
    """Compile the timing diagram cards (cards/*.tdl)."""
    lanes = {}
    try:
        cards = [tdl.compile_file(f, lanes) for f in sorted((HERE / "cards").glob("*.tdl"))]
    except tdl.TdlError as e:
        raise SystemExit(f"error: {e}")
    return {"lanes": lanes, "laneKeys": list(lanes), "cards": cards}


def fill(tpl, marker, text):
    if tpl.count(marker) != 1:
        raise SystemExit(f"template: the marker {marker} must occur once")
    return tpl.replace(marker, text)


def main():
    global RESULTS
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", required=True, type=Path)
    ap.add_argument("-o", "--out", required=True, type=Path)
    args = ap.parse_args()
    RESULTS = args.results
    data = {k: hist_entry(*v) for k, v in HISTS.items()}
    data.update({k: ccdf_entry(*v) for k, v in CCDFS.items()})
    cards = tdl_cards()
    tpl = (HERE / "template.html").read_text()
    out = fill(tpl, "/*DATA*/null", json.dumps(data, separators=(",", ":")))
    out = fill(out, "/*TDL*/null", json.dumps(cards, ensure_ascii=False, separators=(",", ":")))
    out = fill(out, "/*RENDER*/", (HERE.parent / "render.js").read_text())
    args.out.write_text(out)
    print(f"{args.out}: {len(out)} bytes, {len(data)} data sets, {len(cards['cards'])} cards")


if __name__ == "__main__":
    main()
