#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Build the latency-modes page from template.html, cards/ and the run logs.

Usage: build.py --results <results tree> -o <page.html>

<results tree> is the root of a results tree of the latency study. A run
id is <experiment>/<stamp>. The folder of the run is ex-<experiment>/<stamp>
in one of the instance folders (at any depth). Its logs are
<tree>/<point>/rep1.log. The page data comes only from pinned runs: the
run ids in HISTS and CCDFS below. Each run id in the src line of a card
must also have a run folder.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from probatrix.benchmarks.latbench import parse_log, quantile  # noqa: E402

sys.path.insert(0, str(HERE.parent))
import tdl  # noqa: E402

RESULTS = None  # set by main()

# The pinned runs: Zephyr v4.5.0-rc3-40 (ec98918869c), tree ws-up.
IRQ_BASELINE = "irq-baseline-1m/20261029T012553Z"
WAKE_ISR = "wake-isr-1m/20261029T064014Z"
WAKE_TIMERS = "wake-timers-1m/20261029T045125Z"
SYSTICK_PRIO = "wake-systick-prio-1m/20261029T025755Z"
BACKENDS = "wake-timeout-backends-1m/20261029T032020Z"
ANCHORS = "wake-anchors-1m/20261029T014607Z"
THREAD_SWITCH = "thread-switch/20261029T024719Z"

# Histograms: all bins as [value, count] (1-cycle bins only).
# Each entry: (run id, tree, point, histogram).
HISTS = {
    "irq_direct": (IRQ_BASELINE, "ws-up", "direct-idle", "irq"),
    "irq_zli": (IRQ_BASELINE, "ws-up", "zli-idle", "irq"),
    "isr2thr_sem": (WAKE_ISR, "ws-up", "wrapped-sem", "isr2thr"),
}

# CCDF curves: [value, P(latency >= value)], reduced.
CCDFS = {
    "irq_t0": (WAKE_TIMERS, "ws-up", "t0-default", "irq"),
    "irq_t256_same": (SYSTICK_PRIO, "ws-up", "t256-same", "irq"),
    "irq_t256_lower": (SYSTICK_PRIO, "ws-up", "t256-lower", "irq"),
    "thr_t0_noslice": (WAKE_TIMERS, "ws-up", "t0-noslice", "isr2thr"),
    "thr_t0": (WAKE_TIMERS, "ws-up", "t0-default", "isr2thr"),
    "thr_t256_wheel": (BACKENDS, "ws-up", "wheel", "isr2thr"),
    "thr_t256_dlist": (BACKENDS, "ws-up", "dlist", "isr2thr"),
    "anc_legacy": (ANCHORS, "ws-up", "default-legacy", "isr2thr"),
    "anc_switch": (ANCHORS, "ws-up", "default-switch", "isr2thr"),
    "anc_noslice_legacy": (ANCHORS, "ws-up", "noslice-legacy", "isr2thr"),
    "anc_noslice_switch": (ANCHORS, "ws-up", "noslice-switch", "isr2thr"),
    "t2t_sem": (THREAD_SWITCH, "ws-up", "sem-legacy", "t2t"),
    "t2t_sem_sw": (THREAD_SWITCH, "ws-up", "sem-switch", "t2t"),
}

RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*/\d{8}T\d{6}Z")


def run_dir(run_id):
    """Return the folder of a run id (<experiment>/<stamp>) in the results tree."""
    experiment, stamp = run_id.split("/")
    found = sorted(RESULTS.glob(f"**/ex-{experiment}/{stamp}"))
    if len(found) != 1:
        what = "no run folder" if not found else f"{len(found)} run folders"
        raise SystemExit(f"{RESULTS}: {what} for the run {run_id}")
    return found[0]


def load(run_id, tree, point, name):
    rel = f"{run_id}/{tree}/{point}"
    run = parse_log(run_dir(run_id) / tree / point / "rep1.log")
    h = run["hists"][name]
    if h.get("invalid", 0) or h.get("overflow", 0):
        raise SystemExit(f"{rel}: {name} has invalid or overflow samples")
    return rel, run, h


def hist_entry(run_id, tree, point, name):
    rel, _, h = load(run_id, tree, point, name)
    if h["width"]:
        raise SystemExit(f"{rel}: coarse bins are not supported for a histogram")
    return {"n": h["n"], "source": rel, "bins": sorted([v, c] for v, c in h["bins"].items())}


def ccdf_entry(run_id, tree, point, name):
    rel, run, h = load(run_id, tree, point, name)
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


def check_card_sources(cards):
    """Each run id in the src line of a card must have a run folder."""
    for card in cards["cards"]:
        ids = RUN_ID.findall(card.get("src", ""))
        if not ids:
            raise SystemExit(f"card {card['id']}: the src line has no run id")
        for run_id in ids:
            run_dir(run_id)


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
    check_card_sources(cards)
    tpl = (HERE / "template.html").read_text()
    out = fill(tpl, "/*DATA*/null", json.dumps(data, separators=(",", ":")))
    out = fill(out, "/*TDL*/null", json.dumps(cards, ensure_ascii=False, separators=(",", ":")))
    out = fill(out, "/*RENDER*/", (HERE.parent / "render.js").read_text())
    args.out.write_text(out)
    print(f"{args.out}: {len(out)} bytes, {len(data)} data sets, {len(cards['cards'])} cards")


if __name__ == "__main__":
    main()
