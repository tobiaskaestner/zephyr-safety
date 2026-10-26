# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The central results of a study: characterisation with measured values.

A central result has a statement with {placeholders}, the data (from) and
a stat. The build fills the statement once for each row of values: for
each point, or for each group of points of an aggregate stat. A
placeholder is a value of the row: a stat name, an axis name, tree, point,
metric, run, or a name that the stat gives (slope, bound, ...).

from:  experiment (or a list), point (or a list), axes, exclude, metric
       (or a list); hypotheses: [ids] (stat conclusion); substudy: name
stat:  a stat or a list of stats of stats.py, value (META metrics),
       top_site, conclusion, phase_share_range, hist_identical_count, or
       {spread: [stats]}, {spread_abs: [stats]}, {slope: {stat, axis}},
       {fit_linear: {stat, x: [axes]}}, {diff_rank: [stats]},
       {tree_diff: stat}, {ram_cost: [stats]},
       {exceedance_bound: {thresholds: [..], confidence: c}}
For an aggregate stat, the points form groups: one group for each series
(run, tree) and each value of the axes that the statement names.
"""

import math
import re
import statistics

from . import checks, stats
from .stats import NoValue

PLACEHOLDER = re.compile(r"\{([\w.\-]+)(?::([^}]*))?\}")


def fill(template, row):
    """Fill {name[:spec]}; a missing name stays as it is. Return (text, missing names)."""
    missing = []

    def sub(m):
        key, spec = m.group(1), m.group(2) or ""
        if key not in row or row[key] is None:
            missing.append(key)
            return m.group(0)
        v = row[key]
        try:
            return format(v, spec)
        except (ValueError, TypeError):
            return str(v)
    text = PLACEHOLDER.sub(sub, " ".join(template.split()))
    return text, missing


def placeholders(template):
    return [m.group(1) for m in PLACEHOLDER.finditer(template or "")]


def poisson_upper(k, n, conf):
    """One-sided upper bound of the probability per sample for k events in n samples (exact Poisson)."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        p = (lo + hi) / 2
        lam = n * p
        cdf = sum(math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1)) for i in range(k + 1))
        lo, hi = (p, hi) if cdf > 1 - conf else (lo, p)
    return hi


def lstsq(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        raise NoValue("all x values are the same")
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return slope, my - slope * mx


def base_row(o, metric=None):
    row = {"run": o.run, "tree": o.tree, "point": o.point, **o.axes}
    if metric:
        row["metric"] = metric
    return row


def groups(obs, template, extra_keys=()):
    """Group points by series and by the axes that the statement names."""
    names = set(placeholders(template)) | set(extra_keys)
    out = {}
    for o in obs:
        key = (o.run, o.tree) + tuple(sorted((a, v) for a, v in o.axes.items() if a in names))
        out.setdefault(key, []).append(o)
    return out


def from_obs(cr, src):
    f = cr.get("from") or {}
    obs, missing = [], []
    for e in checks.as_list(f.get("experiment")):
        try:
            obs += src.observations(e)
        except NoValue as err:
            missing.append(str(err))
    if not obs and missing:
        raise NoValue("; ".join(missing))
    sel = {}
    if "point" in f:
        sel["point"] = f["point"]
    if "axes" in f:
        sel["axes"] = f["axes"]
    obs = checks.select(obs, sel)
    excl = set(checks.as_list(f.get("exclude"))) - {None}
    return [o for o in obs if o.point not in excl]


def evaluate(cr, src, ctx):
    """Return the central result: {id, stat, texts, rows, by[, verdict]} (or raises NoValue)."""
    st = cr.get("stat")
    f = cr.get("from") or {}
    template = cr.get("statement", "")
    metrics = checks.as_list(f.get("metric"))
    rows = []

    if "substudy" in f:
        sub = ctx.substudy_result(f["substudy"], cr["id"])
        if sub is None:
            raise NoValue(f"sub-study {f['substudy']} has no central result {cr['id']}")
        return {**sub, "from": {"substudy": f["substudy"]}}

    if st == "conclusion" or (st is None and "hypotheses" in f):
        hyps = f.get("hypotheses", [])
        verdicts = {h: ctx.hypothesis_verdict(h) for h in hyps}
        manual = ctx.manual_verdict(cr["id"])
        text, _ = fill(template, {})
        out = {"id": cr["id"], "stat": "conclusion", "texts": [text], "rows": [],
               "verdicts_of_hypotheses": verdicts}
        if manual:
            out["verdict"] = manual["verdict"]
            out["by"] = manual.get("by")
        else:
            out["verdict"] = "open (a person confirms the sentence)"
            out["by"] = None
        return out

    obs = from_obs(cr, src)
    if not obs:
        raise NoValue(f"no points for {f}")

    if isinstance(st, dict):
        (kind, arg), = st.items()
        if kind in ("spread", "spread_abs"):
            for m in metrics:
                for key, g in sorted(groups(obs, template).items()):
                    row = {**base_row(g[0], m), "points": len(g)}
                    for s in arg:
                        vals = [stats.value(o.rep, None if s.startswith("drift") else m, s) for o in g]
                        row[s] = ((max(vals) - min(vals)) / min(vals)) if kind == "spread" else max(vals) - min(vals)
                    del row["point"]
                    rows.append(row)
        elif kind == "exceedance_bound":
            for m in metrics:
                for o in obs:
                    h = o.rep["hists"][m]
                    if h.get("overflow"):
                        raise NoValue("the histogram has overflow samples")
                    for x in arg["thresholds"]:
                        k = stats.count_ge(h, x)
                        b = poisson_upper(k, h["n"], arg["confidence"])
                        rows.append({**base_row(o, m), "load_seed": o.rep["meta"].get("load_timer_seed"),
                                     "threshold": x, "count": k, "n": h["n"], "bound": float(f"{b:.3g}"),
                                     "confidence": arg["confidence"]})
        elif kind in ("slope", "fit_linear"):
            stat = arg["stat"]
            axes = [arg["axis"]] if kind == "slope" else arg["x"]
            for m in metrics:
                for key, g in sorted(groups(obs, template).items()):
                    pts = []
                    for o in g:
                        nums = [ctx.axis_number(o, a) for a in axes]
                        if None in nums:
                            continue
                        pts.append((sum(nums), stats.value(o.rep, m, stat)))
                    if len(pts) < 2:
                        continue
                    slope, icept = lstsq(*zip(*pts))
                    row = {**base_row(g[0], m), "slope": slope, "intercept": icept, "points": len(pts)}
                    del row["point"]
                    rows.append(row)
        elif kind == "diff_rank":
            for m in metrics:
                for s in arg:
                    by_series = checks.by_series(obs)
                    for series, g in sorted(by_series.items()):
                        diffs, skipped = [], []
                        for o in g:
                            if o.axes.get("variant") == "baseline":
                                continue
                            ref = [r for r in g if r.axes.get("variant") == "baseline"
                                   and {a: v for a, v in r.axes.items() if a != "variant"}
                                   == {a: v for a, v in o.axes.items() if a != "variant"}]
                            if not ref:
                                continue
                            try:
                                diffs.append((o.point, stats.value(o.rep, m, s) - stats.value(ref[0].rep, m, s)))
                            except NoValue as e:
                                skipped.append(f"{o.point}: {e}")
                        if not diffs:
                            continue
                        diffs.sort(key=lambda x: (-abs(x[1]), x[0]))
                        row = {"run": series[0], "tree": series[1], "metric": m, "stat": s,
                               "first": diffs[0][0], "first_diff": int(diffs[0][1]),
                               "ranking": ", ".join(f"{p} ({d:+.0f})" for p, d in diffs)}
                        if skipped:
                            row["skipped"] = skipped
                        rows.append(row)
        elif kind == "tree_diff":
            for m in metrics:
                ids = sorted({o.point for o in obs})
                for p in ids:
                    up = [o for o in obs if o.point == p and o.tree == "ws-up"]
                    sf = [o for o in obs if o.point == p and o.tree == "ws-safety"]
                    if up and sf:
                        rows.append({"point": p, "metric": m, **up[0].axes,
                                     "tree_diff": stats.value(up[0].rep, m, arg) - stats.value(sf[0].rep, m, arg)})
        elif kind == "ram_cost":
            for m in metrics:
                for key, g in sorted(groups(obs, template).items()):
                    ram = [o for o in g if str(o.axes.get("place", "")).startswith("r")]
                    flash = [o for o in g if str(o.axes.get("place", "")).startswith("f")]
                    if not ram or not flash:
                        continue
                    row = {**base_row(g[0], m)}
                    del row["point"]
                    for s in arg:
                        mm = None if s.startswith("drift") else m
                        row[s] = statistics.median(stats.value(o.rep, mm, s) for o in ram) - \
                            statistics.median(stats.value(o.rep, mm, s) for o in flash)
                    rows.append(row)
        else:
            raise NoValue(f"stat {kind} has no tool")
    elif st == "phase_share_range":
        for m in metrics:
            for o in obs:
                ph = o.rep["phases"].get(m)
                if not ph:
                    raise NoValue(f"{o.point} has no phase table {m}")
                tot = sum(b[1] for b in ph["bins"])
                shares = [b[1] * len(ph["bins"]) / tot for b in ph["bins"]]
                rows.append({**base_row(o, m), "min": min(shares), "max": max(shares)})
    elif st == "hist_identical_count":
        n = same = 0
        for o in obs:
            ref = ctx.owner_point(o)
            if ref is None:
                continue
            n += 1
            same += all(stats.hist_identical(o.rep["hists"][k], ref.rep["hists"][k]) for k in o.rep["hists"])
        rows.append({"hist_identical_count": same, "n": n})
    elif st == "top_site":
        for m in metrics:
            for o in obs:
                sites = [s for s in stats.m4_sites(o.rep, m) if s["n"]]
                if not sites:
                    continue
                floor = o.rep["meta"].get("m4_floor_cyc", 0)
                top = max(sites, key=lambda s: (s["max"] - floor, s["name"]))
                rows.append({**base_row(o, m), "max_net": max(top["max"] - floor, 0),
                             "place": top.get("function", top["name"]) + (f" (via {top['via']})" if top.get("via") else ""),
                             "ctx": top["ctx"]})
    else:
        stat_list = checks.as_list(st)
        for o in obs:
            if all(m is not None and m.startswith("meta.") for m in metrics) and metrics != [None]:
                row = base_row(o)
                for m in metrics:
                    v = stats.value(o.rep, m, "value")
                    row[m[5:]] = v
                    row["value"] = v
                rows.append(row)
                continue
            for m in metrics:
                row = base_row(o, m)
                for s in stat_list:
                    row[s] = stats.value(o.rep, m, s)
                rows.append(row)

    texts, missing = [], set()
    for row in rows:
        t, miss = fill(template, {**ctx.defaults(), **row})
        texts.append(t)
        missing |= set(miss)
    out = {"id": cr["id"], "stat": st, "texts": texts, "rows": rows, "by": "auto"}
    if cr.get("unit"):
        out["unit"] = cr["unit"]
    if missing:
        out["unfilled"] = sorted(missing)
    return out
