#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Capture, parse and summarise the output of the latency benchmarks.

The apps print "LAT" lines (see common/src/hist.c and common/src/meta.c):

    LAT BEGIN
    LAT META <key>=<value>
    LAT CFG <SYM>=<0|1> ...
    LAT HIST <name> n=.. min=.. max=.. mean=.. overflow=.. invalid=..
    LAT BIN <cycles> <count>
    LAT CBIN <lower edge> <count> <width>
    LAT OVF <log2> <count>
    LAT END <name>
    LAT PHASE <name> bins=.. period=..
    LAT PB <bin> <count> <min> <max> <sum>
    LAT END <name>
    LAT ERROR <text>
    LAT DONE

Subcommands:

    capture  flash a build (optional) and save the serial output until
             "LAT DONE". The script reads the port all the time, so the
             host buffer does not overflow while the app prints.
             For development only: a data point comes from run.py.
    parse    convert a raw log to JSON.
    summary  print percentiles for each histogram of one or more logs.

A sample of 2^31 cycles or more is a negative difference (the event came
before its reference time). It is not a latency. The apps count it only in
"invalid=", so n, min, max, mean and the bins do not include it. An old log
has no "invalid=" field: there these samples are in n, max, mean and in the
overflow bin 31 (see invalid() and mean()).
"""

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path


class CaptureError(Exception):
    pass


def run_capture(out, flash_cmd=None, port="/dev/ttyACM0", baud=115200, timeout=600, echo=False):
    """Run flash_cmd (if any) and save the serial output to out until 'LAT DONE'.

    The port is open before the flash starts, so the boot output is not lost.
    Raise CaptureError if the flash fails or no 'LAT DONE' comes in time.
    """
    import serial

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    ser = serial.Serial(port, baud, timeout=0.2)
    ser.reset_input_buffer()

    flash = None
    flash_log = b""
    if flash_cmd:
        flash = subprocess.Popen(flash_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    deadline = time.monotonic() + timeout
    seen_begin = False
    done = False
    buf = b""
    try:
        with out.open("w") as f:
            while time.monotonic() < deadline:
                buf += ser.read(4096)
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    line = raw.decode(errors="replace").rstrip("\r")
                    f.write(line + "\n")
                    if line.startswith("LAT BEGIN"):
                        seen_begin = True
                    elif seen_begin and line.startswith("LAT DONE"):
                        done = True
                    if echo and not line.startswith(("LAT BIN", "LAT OVF")):
                        print(line, flush=True)
                if done:
                    break
                if flash is not None and flash.poll() is not None:
                    flash_log += flash.stdout.read()
                    if flash.returncode != 0:
                        raise CaptureError(
                            f"flash failed ({flash.returncode}):\n{flash_log.decode(errors='replace')}"
                        )
                    flash = None
    finally:
        ser.close()
        if flash is not None:
            flash.wait()
    if not done:
        raise CaptureError(f"timeout: no 'LAT DONE' after {timeout} s, see {out}")


def capture(args):
    flash_cmd = None
    if args.flash:
        flash_cmd = ["west", "flash", "-d", args.flash, "-r", args.runner]
    try:
        run_capture(args.out, flash_cmd, args.port, args.baud, args.timeout, args.echo)
    except CaptureError as e:
        sys.exit(str(e))
    print(f"saved {args.out}")


def parse_log(path):
    """Return the last run in the log as a dict."""
    run = None
    hist = None
    phase = None
    for line in Path(path).read_text().splitlines():
        if not line.startswith("LAT "):
            continue
        tag, _, rest = line[4:].partition(" ")
        if tag == "BEGIN":
            run = {"source": str(path), "meta": {}, "cfg": {}, "hists": {}, "phases": {}, "errors": []}
        elif run is None:
            continue
        elif tag == "META":
            key, _, value = rest.partition("=")
            run["meta"][key] = value
        elif tag == "CFG":
            for item in rest.split():
                key, _, value = item.partition("=")
                run["cfg"][key] = int(value)
        elif tag == "ERROR":
            run["errors"].append(rest)
        elif tag == "HIST":
            name, *fields = rest.split()
            # "bins" maps the lower edge of a bin to its count, "width" its
            # width (only coarse bins have an entry, all others are 1 cycle).
            hist = {"name": name, "bins": {}, "width": {}, "ovf_log2": {}}
            for item in fields:
                key, _, value = item.partition("=")
                hist[key] = float(value) if key == "mean" else int(value)
            run["hists"][name] = hist
        elif tag == "BIN" and hist is not None:
            v, c = rest.split()
            hist["bins"][int(v)] = int(c)
        elif tag == "CBIN" and hist is not None:
            v, c, w = (int(x) for x in rest.split())
            hist["bins"][v] = c
            hist["width"][v] = w
        elif tag == "OVF" and hist is not None:
            e, c = rest.split()
            hist["ovf_log2"][int(e)] = int(c)
        elif tag == "PHASE":
            name, *fields = rest.split()
            phase = {"name": name, "bins": {}}
            for item in fields:
                key, _, value = item.partition("=")
                # "bins=" is the bin count; "bins" holds the table.
                phase["nbins" if key == "bins" else key] = int(value)
            run["phases"][name] = phase
        elif tag == "PB" and phase is not None:
            b, count, vmin, vmax, vsum = (int(x) for x in rest.split())
            phase["bins"][b] = {"count": count, "min": vmin, "max": vmax, "sum": vsum}
        elif tag == "END":
            hist = None
            phase = None
    if run is None:
        raise ValueError(f"{path}: no 'LAT BEGIN'")
    return run


def quantile(hist, q):
    """Return the q quantile in cycles, or a '>=2^e' string if it is in an overflow bin."""
    target = math.ceil(q * hist["n"])
    acc = 0
    for v in sorted(hist["bins"]):
        acc += hist["bins"][v]
        if acc >= target:
            return v
    for e in sorted(hist["ovf_log2"]):
        acc += hist["ovf_log2"][e]
        if acc >= target:
            return f">={1 << e}"
    return hist["max"]


def invalid(hist):
    """Number of negative differences: the "invalid=" field, or overflow bin 31 of an old log."""
    return hist.get("invalid", 0) + sum(c for e, c in hist["ovf_log2"].items() if e >= 31)


def mean(hist):
    """Mean without the negative differences.

    A new log prints this mean. In an old log, the printed mean includes the
    negative differences. Then the mean comes from the bins (a coarse bin
    counts at its centre), if all other samples are in bins. Otherwise the
    printed mean stays.
    """
    bad = sum(c for e, c in hist["ovf_log2"].items() if e >= 31)
    if "invalid" in hist or bad == 0:
        return hist["mean"]
    valid = hist["n"] - bad
    if valid <= 0 or sum(hist["bins"].values()) != valid:
        return hist["mean"]
    w = hist.get("width", {})
    return round(sum(c * (v + (w.get(v, 1) - 1) / 2) for v, c in hist["bins"].items()) / valid, 2)


def stddev(hist):
    """Standard deviation; a coarse bin counts at its centre."""
    in_bins = sum(hist["bins"].values())
    if in_bins != hist["n"] or hist["n"] == 0:
        return float("nan")
    m = hist["mean"]
    w = hist.get("width", {})
    return math.sqrt(
        sum(c * (v + (w.get(v, 1) - 1) / 2 - m) ** 2 for v, c in hist["bins"].items()) / hist["n"])


QUANTILES = [("p50", 0.5), ("p90", 0.9), ("p99", 0.99), ("p99.9", 0.999), ("p99.99", 0.9999)]


def drift_ppm(meta):
    """Drift of the kernel cycle counter against the stimulus timer in ppm, or None."""
    try:
        return round(int(meta["clock_drift_cyc"]) / int(meta["clock_elapsed_cyc"]) * 1e6, 1)
    except (KeyError, ValueError, ZeroDivisionError):
        return None


def summary(args):
    """Print one row per log and histogram.

    args.hist: only these histograms (default: all). args.meta: META keys
    to add as columns ("drift_ppm" is computed from the clock keys).
    args.md: a Markdown table.
    """
    only = getattr(args, "hist", None)
    meta_keys = getattr(args, "meta", None) or []
    rows = []
    for path in args.logs:
        run = parse_log(path)
        label = run["meta"].get("variant", "?")
        for name, h in run["hists"].items():
            if only and name not in only:
                continue
            row = {
                "log": "/".join(Path(path).parts[-3:]),
                "variant": label,
                "hist": name,
                "n": h["n"],
                "min": h["min"],
                **{k: quantile(h, q) for k, q in QUANTILES},
                "max": h["max"],
                "mean": mean(h),
                "sd": round(stddev(h), 2),
                "ovf": h["overflow"],
                "inv": invalid(h),
            }
            for key in meta_keys:
                row[key] = drift_ppm(run["meta"]) if key == "drift_ppm" else run["meta"].get(key)
            rows.append(row)
        for err in run["errors"]:
            print(f"{path}: ERROR {err}", file=sys.stderr)
    if not rows:
        return
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    cols = list(rows[0].keys())
    if getattr(args, "md", False):
        print("| " + " | ".join(cols) + " |")
        print("|" + "|".join("---" for _ in cols) + "|")
        for r in rows:
            print("| " + " | ".join(str(r[c]) for c in cols) + " |")
        return
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
    print("  ".join(c.rjust(widths[c]) for c in cols))
    for r in rows:
        print("  ".join(str(r[c]).rjust(widths[c]) for c in cols))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("capture")
    c.add_argument("--port", default="/dev/ttyACM0")
    c.add_argument("--baud", type=int, default=115200)
    c.add_argument("--timeout", type=float, default=600)
    c.add_argument("--flash", metavar="BUILD_DIR", help="run 'west flash' for this build first")
    c.add_argument("--runner", default="openocd")
    c.add_argument("--echo", action="store_true", help="print the lines, without BIN/OVF")
    c.add_argument("out")
    c.set_defaults(fn=capture)

    s = sub.add_parser("parse")
    s.add_argument("log")
    s.set_defaults(fn=lambda a: print(json.dumps(parse_log(a.log), indent=1)))

    s = sub.add_parser("summary")
    s.add_argument("--json", action="store_true")
    s.add_argument("--md", action="store_true", help="print a Markdown table")
    s.add_argument("--hist", action="append", help="only this histogram (repeat for more)")
    s.add_argument("--meta", action="append", help="add this META key as a column (drift_ppm: computed)")
    s.add_argument("logs", nargs="+")
    s.set_defaults(fn=summary)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
