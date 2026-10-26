# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The data of a run of a latbench app: the common part of the app extractors.

Each app has tests/benchmarks/<app>/scripts/extract.py. It calls main()
of this module with its name. The output is one JSON object on stdout
(format latbench-app-<app>/1):

    app, unit ("cycles"), core_hz,
    points: [{tree, point, reps: [{rep, log, meta, cfg, cfg_check, errors,
                                   hists, phases, m4}]}]

- meta: the LAT META values (an integer where the value is an integer).
- cfg_check: the LAT CFG values of the app against the .config of the point.
- hists: the latency histograms: n, min, max, mean, overflow, invalid,
  bins [[value, count]], coarse [[value, count, width]], ovf_log2 [[e, count]].
- phases: the tick phase tables: period, nbins, bins [[bin, count, min, max, sum]].
- m4: null, or the M4 table and its sites (kind, ctx, pc, n, sum, min,
  max, hist, and function/place if the ELF and the binutils are there).

The extractor reads only the run folder; the run folder does not change.
"""

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts" / "benchmarks"))

import latbench  # noqa: E402
import m4  # noqa: E402
import trees  # noqa: E402


def hist_out(h):
    w = h.get("width", {})
    return {
        "n": h["n"], "min": h["min"], "max": h["max"], "mean": latbench.mean(h),
        "overflow": h.get("overflow", 0), "invalid": latbench.invalid(h),
        "bins": [[v, c] for v, c in sorted(h["bins"].items()) if v not in w],
        "coarse": [[v, c, w[v]] for v, c in sorted(h["bins"].items()) if v in w],
        "ovf_log2": [[e, c] for e, c in sorted(h["ovf_log2"].items())],
    }


def phase_out(p):
    return {"period": p.get("period"), "nbins": p.get("nbins"),
            "bins": [[b, x["count"], x["min"], x["max"], x["sum"]] for b, x in sorted(p["bins"].items())]}


def meta_value(v):
    return int(v) if v.lstrip("-").isdigit() else v


def config_values(path):
    vals = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            if line.startswith("CONFIG_") and "=" in line:
                k, v = line[7:].split("=", 1)
                vals[k] = v
    return vals


def cfg_check(cfg, config):
    """Compare the LAT CFG values of the app (0/1) with the .config of the build."""
    if not config:
        return {"status": "no .config", "keys": len(cfg)}
    differ = {}
    for k, v in sorted(cfg.items()):
        want = 1 if config.get(k) == "y" else 0
        if int(v) != want:
            differ[k] = {"log": int(v), "config": config.get(k, "not set")}
    out = {"status": "ok" if not differ else "differs", "keys": len(cfg)}
    if differ:
        out["differ"] = differ
    return out


def binutils_prefix():
    """The binutils of the Zephyr SDK of this host (trees.yaml), or None."""
    try:
        sdk = Path(os.path.expanduser(str(trees.load()["toolchain"]["zephyr_sdk"]["path"])))
    except Exception:
        return None
    p = sdk / "gnu" / "arm-zephyr-eabi" / "bin" / "arm-zephyr-eabi-"
    return str(p) if Path(str(p) + "nm").exists() else None


def m4_out(run, log, prefix):
    if run.get("m4") is None:
        return None
    sites = run["m4"]["sites"]
    names = {}
    sym = m4.symbolizer_for(log, prefix=prefix) if prefix else None
    if sym is not None:
        addrs = sorted({m4.site_addr(s) for s in sites})
        names = sym.lookup(addrs)
    out = []
    for s in sites:
        row = {k: s[k] for k in ("name", "kind", "ctx", "ipsr", "n", "sum", "min", "max")}
        row["pc"] = f"0x{s['pc']:08x}"
        row["end_pc"] = f"0x{s['end_pc']:08x}"
        if sym is not None:
            a = m4.site_addr(s)
            row["function"], row["place"], row["via"] = m4.describe(names.get(a, []), sym.nm_name(a))
        row["hist"] = hist_out(s["hist"]) if s["hist"] else None
        out.append(row)
    return {"table": run["m4"]["table"], "symbols": sym is not None, "sites": out}


def extract(run_dir, app, prefix=None):
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text())
    core_hz = None
    points = []
    for e in manifest["points"]:
        pdir = run_dir / e["tree"] / e["id"]
        config = config_values(pdir / ".config")
        reps = []
        for i, rel in enumerate(e["logs"], 1):
            log = run_dir / rel
            run = m4.parse_m4(log)
            site_names = {s["name"] for s in run["m4"]["sites"]} if run.get("m4") else set()
            meta = {k: meta_value(v) for k, v in run["meta"].items()}
            core_hz = core_hz or meta.get("core_hz")
            reps.append({
                "rep": i, "log": rel, "meta": meta, "cfg": run["cfg"],
                "cfg_check": cfg_check(run["cfg"], config), "errors": run["errors"],
                "hists": {k: hist_out(h) for k, h in sorted(run["hists"].items()) if k not in site_names},
                "phases": {k: phase_out(p) for k, p in sorted(run["phases"].items())},
                "m4": m4_out(run, log, prefix),
            })
        points.append({"tree": e["tree"], "point": e["id"], "reps": reps})
    return {"app": app, "unit": "cycles", "core_hz": core_hz, "points": points}


def main(app):
    p = argparse.ArgumentParser(description=f"Data of a run of {app} as JSON (stdout).")
    p.add_argument("run", help="raw run folder (with manifest.json)")
    p.add_argument("--binutils", help="binutils prefix for the M4 function names (default: SDK of trees.yaml)")
    args = p.parse_args()
    data = extract(args.run, app, args.binutils or binutils_prefix())
    json.dump(data, sys.stdout)
    sys.stdout.write("\n")
