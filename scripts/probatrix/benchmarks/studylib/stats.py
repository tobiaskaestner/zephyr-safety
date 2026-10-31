# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Values of one point (one repetition) of a run, from its app data.

A metric is one of:
    irq, isr2thr, irq2thr, t2t, ...      a latency histogram of the app
    meta.<key>                           a LAT META value; meta.m4_masked_share
                                         is m4_masked_cyc / m4_window_cyc,
                                         meta.used and meta.dropped come from
                                         the LAT M4 BEGIN line
    m4.<kind>[.<ctx>][<function>]        the M4 sites of a kind (mask, isr),
                                         of a context (t thread, e<n>
                                         exception n) and of a function
                                         (the start function or one of the
                                         inlined functions of the site)
    tail.<hist>                          the witness table of a histogram
                                         (LATBENCH_TAIL, scripts/probatrix/benchmarks/tails.py)
    None                                 the point itself (drift_per_wake,
                                         drift_ppm)

A stat of a histogram: n, min, max, mean, invalid, p<q> (p50, p99.99, ...),
count_ge(x), mode_share(k). A mode is a group of fine bins that each hold
at least 0.1 % of the samples, with at most 2 cycles between neighbours;
the modes are numbered by value (mode 1 is the fastest). mode_share(k) is
the share of the samples in mode k, 0 if the histogram has fewer modes. A stat of a set of M4 sites: n (sum of the sections), max,
max_net, min_net (net = value - the floor of the calibration), max(x),
top_place. A stat of a META metric: value. A stat of a witness table: n
(rows), seen, exc_min, rows_ge(x), explained_share(x) (the share of the
rows >= x cycles with a cause other than none), cause_share(c, x),
label_share(l, x).

value() returns a number or a text, or raises NoValue with the reason.
"""

import math
import re


class NoValue(Exception):
    """The data do not give the value (the metric is absent, a form has no tool)."""


class MissingRun(NoValue):
    """No evidence run of an experiment in an instance: the run is to be made (analysis missing)."""

    def __init__(self, experiment, where):
        super().__init__(f"no evidence run of {experiment} in {where}")
        self.experiment, self.where = experiment, where


HIST_STATS = {"n", "min", "max", "mean", "invalid"}
_Q = re.compile(r"^p(\d+(?:\.\d+)?)$")
_COUNT = re.compile(r"^count_ge\((\d+)\)$")
_MODE = re.compile(r"^mode_share\((\d+)\)$")
MODE_MIN_SHARE = 0.001
MODE_GAP = 2
_AGG = re.compile(r"^(max|min)\((.+)\)$")
_M4 = re.compile(r"^m4\.(mask|isr)(?:\.(t|e\d+))?(?:\[([\w.]+)\])?$")
_TAIL_X = re.compile(r"^(rows_ge|explained_share)\((\d+)\)$")
_TAIL_L = re.compile(r"^(cause_share|label_share)\(([a-z+-]+),\s*(\d+)\)$")
TAIL_STATS = {"n", "seen", "exc_min"}


def quantile_bin(h, q):
    """(lower edge, width) of the bin that holds the q quantile (the lower edge is latbench.quantile)."""
    if h["n"] == 0:
        raise NoValue("the histogram has no samples")
    target = math.ceil(q * h["n"])
    acc = 0
    edges = sorted([(v, c, 1) for v, c in h["bins"]] + [(v, c, w) for v, c, w in h["coarse"]])
    for v, c, w in edges:
        acc += c
        if acc >= target:
            return v, w
    for e, c in h["ovf_log2"]:
        acc += c
        if acc >= target:
            raise NoValue(f"the quantile {q} is in the overflow bin >= 2^{e}")
    return h["max"], 1


def quantile(h, q):
    """The q quantile: the lower edge of the bin that holds it. In a coarse bin of width w, the
    true value is up to w - 1 cycles higher."""
    return quantile_bin(h, q)[0]


def count_ge(h, x):
    """Samples >= x. x must be a bin edge, else the count is not exact."""
    total = 0
    for v, c in h["bins"]:
        if v >= x:
            total += c
    for v, c, w in h["coarse"]:
        if v >= x:
            total += c
        elif v + w > x:
            raise NoValue(f"count_ge({x}): {x} is inside the coarse bin {v}..{v + w - 1}")
    for e, c in h["ovf_log2"]:
        # overflow bin e holds samples of 2^e .. 2^(e+1) - 1 (from the end of the histogram on)
        if (1 << e) >= x:
            total += c
        elif c and (1 << (e + 1)) > x:
            raise NoValue(f"count_ge({x}): {x} is inside the overflow bin 2^{e}..2^{e + 1}-1")
    return total


def modes(h):
    """[(first value, last value, count)] of the modes of a histogram, fastest first."""
    limit = MODE_MIN_SHARE * h["n"]
    out = []
    for v, c in sorted(h["bins"]):
        if c < limit:
            continue
        if out and v - out[-1][1] <= MODE_GAP:
            first, _, total = out[-1]
            out[-1] = (first, v, total + c)
        else:
            out.append((v, v, c))
    return out


def hist_value(h, stat):
    if stat in ("n", "invalid"):
        return h[stat]
    if h["n"] == 0:
        raise NoValue("the histogram has no samples")
    if stat in HIST_STATS:
        return h[stat]
    m = _Q.match(stat)
    if m:
        return quantile(h, float(m.group(1)) / 100)
    m = _COUNT.match(stat)
    if m:
        return count_ge(h, int(m.group(1)))
    m = _MODE.match(stat)
    if m:
        k = int(m.group(1))
        found = modes(h)
        return found[k - 1][2] / h["n"] if len(found) >= k else 0
    raise NoValue(f"stat {stat!r} of a histogram has no tool")


def value_width(rep, metric, stat):
    """The width of the bin of a quantile value (1 for an exact value)."""
    if metric is None or metric.startswith(("meta.", "m4.", "tail.")) or not isinstance(stat, str):
        return 1
    m = _Q.match(stat)
    h = rep["hists"].get(metric)
    if not m or h is None:
        return 1
    return quantile_bin(h, float(m.group(1)) / 100)[1]


def function_seen(rep, metric):
    """For an M4 metric with [function]: whether a site of this kind has the function (any context)."""
    m = _M4.match(metric or "")
    if not m or not m.group(3) or not rep.get("m4"):
        return True
    kind, _, func = m.groups()
    return any(s["kind"] == kind and (func == s.get("function") or func in (s.get("via") or "").split("<"))
               for s in rep["m4"]["sites"])


def m4_sites(rep, metric):
    m = _M4.match(metric)
    if not m:
        raise NoValue(f"metric {metric!r} is not an M4 metric")
    kind, ctx, func = m.groups()
    data = rep.get("m4")
    if data is None:
        raise NoValue("the run has no M4 data")
    if func and not data.get("symbols"):
        raise NoValue("the M4 sites have no function names (no ELF or no binutils)")
    out = []
    for s in data["sites"]:
        if s["kind"] != kind:
            continue
        if ctx and s["name"].split(".")[2] != ctx:
            continue
        if func and func != s.get("function") and func not in (s.get("via") or "").split("<"):
            continue
        out.append(s)
    return out


def m4_value(rep, metric, stat):
    sites = m4_sites(rep, metric)
    meta = rep["meta"]
    kind = _M4.match(metric).group(1)
    floor = meta.get("m4_isr_floor_cyc" if kind == "isr" else "m4_floor_cyc", 0)
    if not isinstance(floor, int):
        floor = 0

    def site_value(s, x):
        if x in ("max", "min", "n", "sum"):
            return s[x]
        if x == "max_net":
            return max(s["max"] - floor, 0)
        if x == "min_net":
            return max(s["min"] - floor, 0)
        raise NoValue(f"stat {x!r} of an M4 site has no tool")

    m = _AGG.match(stat)
    if m:
        f, x = m.groups()
        vals = [site_value(s, x) for s in sites if s["n"]]
        if not vals:
            if f == "max":
                return 0  # no section: the longest section is 0
            raise NoValue(f"{metric}: no section, so no min({x})")
        return max(vals) if f == "max" else min(vals)
    if stat == "n":
        return sum(s["n"] for s in sites)
    if stat in ("max", "max_net"):
        vals = [site_value(s, stat) for s in sites if s["n"]]
        return max(vals) if vals else 0
    if stat == "min_net":
        vals = [site_value(s, stat) for s in sites if s["n"]]
        if not vals:
            raise NoValue(f"{metric}: no section")
        return min(vals)
    if stat == "top_place":
        live = [s for s in sites if s["n"]]
        if not live:
            raise NoValue(f"{metric}: no section")
        if not all("function" in s for s in live):
            raise NoValue("the M4 sites have no function names")
        top = max(live, key=lambda s: (site_value(s, "max_net"), s["name"]))
        return top["function"] + (f" (via {top['via']})" if top.get("via") else "")
    raise NoValue(f"stat {stat!r} of an M4 metric has no tool")


def meta_value(rep, key):
    meta = rep["meta"]
    if key == "m4_masked_share":
        try:
            return meta["m4_masked_cyc"] / meta["m4_window_cyc"]
        except (KeyError, TypeError, ZeroDivisionError):
            raise NoValue("no m4_masked_cyc / m4_window_cyc") from None
    if key in ("used", "dropped", "sites") and rep.get("m4"):
        return rep["m4"]["table"][key]
    if key not in meta:
        raise NoValue(f"no LAT META {key}")
    return meta[key]


def point_value(rep, stat):
    meta = rep["meta"]
    try:
        if stat == "drift_per_wake":
            return meta["clock_drift_cyc"] / meta["samples"]
        if stat == "drift_ppm":
            return meta["clock_drift_cyc"] / meta["clock_elapsed_cyc"] * 1e6
    except (KeyError, TypeError, ZeroDivisionError):
        raise NoValue(f"{stat}: no clock_drift_cyc, samples or clock_elapsed_cyc") from None
    raise NoValue(f"stat {stat!r} of a point has no tool")


def tail_value(rep, metric, stat):
    """A stat of the witness table of a histogram (metric tail.<hist>)."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # scripts/probatrix/benchmarks: tails.py
    import tails

    t = (rep.get("tails") or {}).get(metric[5:])
    if t is None:
        raise NoValue(f"the point has no witness table {metric[5:]!r} (LATBENCH_TAIL)")
    if stat in TAIL_STATS:
        return t[stat]
    meta = rep.get("meta", {})
    m = _TAIL_X.match(stat or "")
    if m:
        x = int(m.group(2))
        if m.group(1) == "rows_ge":
            return len(tails.rows(t, meta, x))
        v = tails.explained_share(t, meta, x)
    else:
        m = _TAIL_L.match(stat or "")
        if not m:
            raise NoValue(f"stat {stat!r} of a witness table has no tool")
        kind, name, x = m.group(1), m.group(2), int(m.group(3))
        sel = tails.rows(t, meta, x)
        v = None if not sel else sum((r["cause"] == name) if kind == "cause_share" else (name in r["labels"])
                                     for r in sel) / len(sel)
    if v is None:
        raise NoValue(f"{metric}: no row of {m.group(m.lastindex)} cycles or more")
    return v


def value(rep, metric, stat):
    """The value of a metric and a stat for one repetition of a point."""
    if metric is None:
        return point_value(rep, stat)
    if metric.startswith("meta."):
        if stat not in (None, "value"):
            raise NoValue(f"stat {stat!r} of a META metric has no tool")
        return meta_value(rep, metric[5:])
    if metric.startswith("m4."):
        return m4_value(rep, metric, stat)
    if metric.startswith("tail."):
        return tail_value(rep, metric, stat)
    h = rep["hists"].get(metric)
    if h is None:
        raise NoValue(f"the point has no histogram {metric!r}")
    return hist_value(h, stat)


def hist_identical(a, b):
    return a["bins"] == b["bins"] and a["coarse"] == b["coarse"] and a["ovf_log2"] == b["ovf_log2"]


def coarse_width(h):
    return h["coarse"][0][2] if h["coarse"] else 1


def known(metric, stat):
    """Whether the tools have a value for this metric and stat (the stat may be None or a list)."""
    stat_list = stat if isinstance(stat, list) else [stat]
    for st in stat_list:
        if metric is None:
            ok = st in ("drift_per_wake", "drift_ppm")
        elif metric.startswith("meta."):
            ok = st in (None, "value")
        elif metric.startswith("tail."):
            ok = st in TAIL_STATS or bool(_TAIL_X.match(st or "") or _TAIL_L.match(st or ""))
        elif metric.startswith("m4."):
            inner = _AGG.match(st).group(2) if st and _AGG.match(st) else st
            ok = bool(_M4.match(metric)) and (st == "top_place" or inner in ("n", "max", "min", "max_net", "min_net"))
        else:
            inner = _AGG.match(st).group(2) if st and _AGG.match(st) else st
            ok = st is None or inner in HIST_STATS or bool(_Q.match(inner) or _COUNT.match(inner) or _MODE.match(inner))
        if not ok:
            return False
    return True
