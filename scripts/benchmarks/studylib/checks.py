# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Evaluation of a check of a hypothesis or of an acceptance check.

A check reads the points of an experiment (`experiment`, `select`), one or
more metrics and stats, and compares them (`expect`). The points of each
run and tree form a series; a check is confirmed only if it holds in each
series, for each metric and each stat.

select:
    {point: id | [ids]}, {axes: {axis: value | [values]}}, {axis: value | [values]}
stat:
    a stat of stats.py; for a histogram metric, max(<stat>) / min(<stat>) is
    the largest / smallest value over the selected points.
expect:
    range: [lo, hi]                each value in lo..hi (null: no limit)
    equals: x                      each value is x (for top_place: x is the
                                   start function or one of its inlined functions)
    spread_le: x                   (max - min) / min over the points <= x
    spread_abs_le: x               max - min over the points <= x
    order: [p1, p2, ...]           the values increase in this point order
    order: {axis: [v1, v2, ...]}   the values increase along these axis values,
                                   for each value of the other axes
    diff_to: {REF, range | spread_abs_le}
                                   value - the value of the reference
    ratio_to: {REF, stat} + range  value / the value of the reference
    diff_change: {point: P, of: [Q, R], range}
                                   (value - P) - (Q - R), in the same series
    within: {experiment: E, stat: range} + tolerance_bins: k
                                   value in min..max of all points of E,
                                   +- k coarse bins
    hist_identical_to: {run, point}
                                   the same histogram, bin for bin
REF: point: P | axes: {axis: v} (the point with this axis value and the
same other axes) | run: <study path>/<experiment>/<UTC> with point: P,
points: {selected: reference} or the same point id, and tree: T |
experiment: E, point: same | metric: M, stat: S (the same point).
"""

import re

from . import stats
from .stats import NoValue

AGG = re.compile(r"^(max|min)\((.+)\)$")
EXPECT = {"range", "equals", "spread_le", "spread_abs_le", "order", "diff_to", "ratio_to", "diff_change",
          "within", "tolerance_bins", "hist_identical_to"}
SELECT_KEYS = {"point", "axes"}


def problems(check):
    """Forms of a check that the tools do not know (an empty list if all are known)."""
    if check.get("manual"):
        return [] if check.get("statement") else ["a manual check needs a statement"]
    out = []
    for k in check.get("expect") or {}:
        if k not in EXPECT:
            out.append(f"expect {k!r}")
    if not check.get("expect"):
        out.append("no expect")
    for m in as_list(check.get("metric")):
        if not stats.known(m, check.get("stat")):
            out.append(f"metric {m!r} with stat {check.get('stat')!r}")
    return out


class Obs:
    """One point of a run: rep 1 of its app data."""

    def __init__(self, run, tree, point, axes, rep, reps=1):
        self.run, self.tree, self.point, self.axes, self.rep, self.reps = run, tree, point, axes, rep, reps

    @property
    def series(self):
        return (self.run, self.tree)

    def __repr__(self):
        return f"{self.run}:{self.tree}/{self.point}"


def as_list(x):
    if x is None:
        return [None]
    return list(x) if isinstance(x, list) else [x]


def select(obs, sel):
    """The points of obs that the select of a check names."""
    if not sel:
        return list(obs)
    out = []
    for o in obs:
        ok = True
        for k, v in sel.items():
            if k == "point":
                ok &= o.point in as_list(v)
            elif k == "axes":
                ok &= all(o.axes.get(a) in as_list(x) for a, x in v.items())
            else:
                ok &= o.axes.get(k) in as_list(v)
        if ok:
            out.append(o)
    return out


def by_series(obs):
    groups = {}
    for o in obs:
        groups.setdefault(o.series, []).append(o)
    return groups


def is_point_agg(metric, stat):
    """max(x) / min(x) of a histogram metric: over the selected points."""
    return stat is not None and AGG.match(stat) and not (metric or "").startswith("m4.")


def value(o, metric, stat):
    return stats.value(o.rep, metric, stat)


def series_values(points, metric, stat):
    """[(label, value)] for the points of one series; one value for a point aggregate."""
    m = AGG.match(stat) if is_point_agg(metric, stat) else None
    if m:
        f, inner = m.groups()
        vals = [(o.point, value(o, metric, inner)) for o in points]
        best = (max if f == "max" else min)(vals, key=lambda x: x[1])
        return [(f"{f} over {len(vals)} points ({best[0]})", best[1])]
    return [(o.point, value(o, metric, stat)) for o in points]


def in_range(v, rng):
    lo, hi = rng
    return (lo is None or v >= lo) and (hi is None or v <= hi)


def fmt(v):
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def rng_text(rng):
    lo, hi = rng
    if lo is None:
        return f"<= {fmt(hi)}"
    if hi is None:
        return f">= {fmt(lo)}"
    return f"{fmt(lo)}..{fmt(hi)}"


class Result:
    def __init__(self):
        self.ok = True
        self.lines = []
        self.values = []

    def add(self, ok, text, value=None):
        self.ok &= bool(ok)
        self.lines.append(("" if ok else "FAIL ") + text)
        if value is not None:
            self.values.append(value)


def label(series, metric, stat):
    run, tree = series
    parts = [tree]
    if metric:
        parts.append(metric)
    if stat:
        parts.append(stat)
    return " ".join(parts)


def evaluate(check, src):
    """Return {verdict, measured, limit, values} for a check that is not manual."""
    exp = check.get("experiment")
    obs = select(src.observations(exp), check.get("select"))
    if not obs:
        raise NoValue(f"no points of {exp} for select {check.get('select')}")
    expect = dict(check.get("expect") or {})
    metrics = as_list(check.get("metric"))
    stat_list = as_list(check.get("stat"))
    res = Result()
    series = by_series(obs)

    if "hist_identical_to" in expect:
        ref = expect["hist_identical_to"]
        for s, pts in series.items():
            ref_obs = [r for r in src.run_obs(ref["run"]) if r.point == ref["point"] and r.tree == s[1]]
            if not ref_obs:
                ref_obs = [r for r in src.run_obs(ref["run"]) if r.point == ref["point"]]
            if not ref_obs:
                raise NoValue(f"reference {ref['run']} has no point {ref['point']}")
            for o in pts:
                for m in metrics:
                    same = stats.hist_identical(o.rep["hists"][m], ref_obs[0].rep["hists"][m])
                    res.add(same, f"{o.tree}/{o.point} {m}: {'same' if same else 'differs'}",
                            {"point": o.point, "metric": m, "identical": same})
        return finish(res, "the same histogram, bin for bin as " + f"{ref['run']} {ref['point']}")

    for s, pts in series.items():
        for m in metrics:
            for st in stat_list:
                lab = label(s, m, st)
                if "range" in expect and not ({"ratio_to"} & set(expect)):
                    for name, v in series_values(pts, m, st):
                        res.add(in_range(v, expect["range"]), f"{lab} {name}: {fmt(v)}",
                                {"series": lab, "point": name, "value": v})
                elif "equals" in expect:
                    want = expect["equals"]
                    for name, v in series_values(pts, m, st):
                        ok = v == want or (isinstance(v, str) and st == "top_place"
                                           and want in re.split(r"[ ()<]+|via ", v))
                        res.add(ok, f"{lab} {name}: {fmt(v)}", {"series": lab, "point": name, "value": v})
                elif "spread_le" in expect or "spread_abs_le" in expect:
                    vals = series_values(pts, m, st)
                    nums = [v for _, v in vals]
                    if "spread_le" in expect:
                        sp = (max(nums) - min(nums)) / min(nums) if min(nums) else float("inf")
                        res.add(sp <= expect["spread_le"], f"{lab}: spread {sp:.2%} ({fmt(min(nums))}..{fmt(max(nums))})",
                                {"series": lab, "spread": sp, "min": min(nums), "max": max(nums)})
                    else:
                        sp = max(nums) - min(nums)
                        res.add(sp <= expect["spread_abs_le"], f"{lab}: {fmt(min(nums))}..{fmt(max(nums))}",
                                {"series": lab, "spread": sp, "min": min(nums), "max": max(nums)})
                elif "order" in expect:
                    order_check(res, lab, pts, m, st, expect["order"])
                elif "diff_to" in expect or "ratio_to" in expect or "diff_change" in expect:
                    ref_check(res, lab, pts, m, st, expect, src)
                elif "within" in expect:
                    within_check(res, lab, pts, m, st, expect, src, s)
                else:
                    raise NoValue(f"expect {sorted(expect)} has no tool")
    return finish(res, limit_text(expect))


def order_check(res, lab, pts, m, st, order):
    if isinstance(order, list):
        groups = {(): [o for o in pts if o.point in order]}
        key = {p: i for i, p in enumerate(order)}
        rank = lambda o: key[o.point]  # noqa: E731
    else:
        (axis, seq), = order.items()
        key = {v: i for i, v in enumerate(seq)}
        groups = {}
        for o in pts:
            if o.axes.get(axis) in key:
                other = tuple(sorted((a, v) for a, v in o.axes.items() if a != axis))
                groups.setdefault(other, []).append(o)
        rank = lambda o: key[o.axes[axis]]  # noqa: E731
    if not groups or not any(len(g) > 1 for g in groups.values()):
        raise NoValue(f"order {order}: fewer than two points")
    for other, g in sorted(groups.items()):
        g = sorted(g, key=rank)
        vals = [(o.point, value(o, m, st)) for o in g]
        ok = all(a[1] < b[1] for a, b in zip(vals, vals[1:]))
        where = (" " + ",".join(f"{a}={v}" for a, v in other)) if other else ""
        res.add(ok, f"{lab}{where}: " + " < ".join(f"{p} {fmt(v)}" for p, v in vals),
                {"series": lab, "group": dict(other), "values": vals})


def ref_obs_for(o, spec, src):
    """The reference point of o for a diff_to / ratio_to spec."""
    if "run" in spec:
        cands = src.run_obs(spec["run"])
        want = spec.get("points", {}).get(o.point) if "points" in spec else spec.get("point", o.point)
        tree = spec.get("tree", o.tree)
        found = [r for r in cands if r.point == want and r.tree == tree]
        if not found:
            raise NoValue(f"reference {spec['run']} has no point {tree}/{want}")
        return found[0]
    if "experiment" in spec:
        want = o.point if spec.get("point", "same") == "same" else spec["point"]
        cands = [r for r in src.observations(spec["experiment"]) if r.point == want]
        found = [r for r in cands if r.tree == spec.get("tree", o.tree)]
        if not found and "tree" not in spec and len({r.tree for r in cands}) == 1:
            found = cands  # the reference experiment has the point on one other tree only
        if not found:
            raise NoValue(f"reference {spec['experiment']} has no point {o.tree}/{want}")
        return found[0]
    if "axes" in spec:
        want = {**o.axes, **spec["axes"]}
        found = [r for r in src.observations(None, series=o.series) if r.axes == want]
        if not found:
            raise NoValue(f"no point with axes {want} for {o.point}")
        return found[0]
    if "point" in spec:
        found = [r for r in src.observations(None, series=o.series) if r.point == spec["point"]]
        if not found:
            raise NoValue(f"no reference point {spec['point']} in {o.series}")
        return found[0]
    return o  # metric / stat of the same point


def ref_check(res, lab, pts, m, st, expect, src):
    if "diff_change" in expect:
        spec = expect["diff_change"]
        q, r = spec["of"]
        for o in pts:
            same = src.observations(None, series=o.series)
            get = lambda p: next(x for x in same if x.point == p)  # noqa: E731
            v = (value(o, m, st) - value(get(spec["point"]), m, st)) - (value(get(q), m, st) - value(get(r), m, st))
            res.add(in_range(v, spec["range"]), f"{lab} {o.point}: ({o.point} - {spec['point']}) - ({q} - {r}) = {fmt(v)}",
                    {"series": lab, "point": o.point, "value": v})
        return
    ratio = "ratio_to" in expect
    spec = expect["ratio_to" if ratio else "diff_to"]
    ref_metric = spec.get("metric", m)
    ref_stat = spec.get("stat", st)
    if is_point_agg(m, st):
        # max(x) over the points against one reference point
        (name, v), = series_values(pts, m, st)
        r = ref_obs_for(pts[0], spec, src)
        rv = value(r, ref_metric, ref_stat)
        pairs = [(name, v, r, rv)]
    else:
        pairs = []
        for o in pts:
            r = ref_obs_for(o, spec, src)
            pairs.append((o.point, value(o, m, st), r, value(r, ref_metric, ref_stat)))
    for name, v, r, rv in pairs:
        what = f"{r.point}" if r.run == pts[0].run else f"{r.run} {r.tree}/{r.point}"
        if ref_metric != m or ref_stat != st:
            what += f" {ref_metric or ''} {ref_stat or ''}".rstrip()
        if ratio:
            q = v / rv if rv else float("inf")
            res.add(in_range(q, expect["range"]), f"{lab} {name}: {fmt(v)} / {fmt(rv)} ({what}) = {q:.3f}",
                    {"series": lab, "point": name, "value": v, "reference": rv, "ratio": q})
        else:
            d = v - rv
            if "spread_abs_le" in spec:
                ok = abs(d) <= spec["spread_abs_le"]
            else:
                ok = in_range(d, spec["range"])
            res.add(ok, f"{lab} {name}: {fmt(v)} - {fmt(rv)} ({what}) = {fmt(d)}",
                    {"series": lab, "point": name, "value": v, "reference": rv, "diff": d})


def within_check(res, lab, pts, m, st, expect, src, series):
    spec = expect["within"]
    ref = [r for r in src.observations(spec["experiment"]) if r.tree == series[1]]
    if not ref:
        raise NoValue(f"no points of {spec['experiment']} on tree {series[1]}")
    rv = [value(r, m, st) for r in ref]
    for o in pts:
        v = value(o, m, st)
        tol = expect.get("tolerance_bins", 0) * stats.coarse_width(o.rep["hists"][m])
        ok = min(rv) - tol <= v <= max(rv) + tol
        res.add(ok, f"{lab} {o.point}: {fmt(v)} ({spec['experiment']} {fmt(min(rv))}..{fmt(max(rv))}, +-{tol})",
                {"series": lab, "point": o.point, "value": v, "range": [min(rv), max(rv)], "tolerance": tol})


def limit_text(expect):
    e = dict(expect)
    if "range" in e and not ({"ratio_to"} & set(e)):
        return rng_text(e["range"])
    if "equals" in e:
        return f"= {e['equals']}"
    if "spread_le" in e:
        return f"spread <= {e['spread_le']:.0%}"
    if "spread_abs_le" in e:
        return f"max - min <= {fmt(e['spread_abs_le'])}"
    if "order" in e:
        o = e["order"]
        return ("increasing: " + " < ".join(o)) if isinstance(o, list) else \
            "increasing along " + ", ".join(f"{a}: {' < '.join(v)}" for a, v in o.items())
    if "ratio_to" in e:
        return f"ratio {rng_text(e['range'])}"
    if "diff_to" in e:
        d = e["diff_to"]
        return f"diff {rng_text(d['range'])}" if "range" in d else f"|diff| <= {fmt(d['spread_abs_le'])}"
    if "diff_change" in e:
        return f"change {rng_text(e['diff_change']['range'])}"
    if "within" in e:
        return f"within {e['within']['experiment']} +- {e.get('tolerance_bins', 0)} coarse bins"
    return str(e)


def finish(res, limit):
    return {"verdict": "confirmed" if res.ok else "wrong", "measured": "; ".join(res.lines),
            "limit": limit, "values": res.values}
