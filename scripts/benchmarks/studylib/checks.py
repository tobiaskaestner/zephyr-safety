# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Evaluation of a check of a hypothesis or of an acceptance check.

A check reads the points of an experiment (`experiment`, `select`), one or
more metrics and stats, and compares them (`expect`). The points of each
run and tree form a series; a check is confirmed only if it holds in each
series, for each metric and each stat.

select:
    {point: id | [ids]}, {axes: {axis: value | [values]}}, {axis: value | [values]}
    A point that a select names must be in the data.
stat:
    a stat of stats.py; for a histogram metric, max(<stat>) / min(<stat>) is
    the largest / smallest value over the selected points.
expect (exactly one form):
    range: [lo, hi]                each value in lo..hi (null: no limit); a
                                   quantile in a coarse bin is in the range
                                   only if the whole bin is
    equals: x                      each value is x (for top_place: x is the
                                   start function or one of its inlined functions)
    spread_le: x                   (max - min) / min over the points <= x (2 points or more, min > 0)
    spread_abs_le: x               max - min over the points <= x (2 points or more)
    order: [p1, p2, ...]           the values increase in this point order (all points in each series)
    order: {axis: [v1, v2, ...]}   the values increase along these axis values,
                                   for each value of the other axes
    diff_to: {REF, range}          value - the value of the reference is in the range
    diff_to: {REF, spread_abs_le: x}
                                   the differences over the selected points
                                   differ by x or less (max - min of the differences)
    ratio_to: {REF, stat} + range  value / the value of the reference
    diff_change: {point: P, of: [Q, R], range}
                                   (value - P) - (Q - R), in the same series
    within: {experiment: E, stat: range} + tolerance_bins: k
                                   value in min..max of all points of E,
                                   +- k coarse bins
    hist_identical_to: {run | experiment, point[, tree]}
                                   the same histogram, bin for bin, on the same tree
                                   (experiment: its one evidence run)
REF: point: P | axes: {axis: v} (the point with this axis value and the
same other axes) | run: <study path>/<experiment>/<UTC> with point: P,
points: {selected: reference} or the same point id, and tree: T |
experiment: E, point: same (one run of E) | metric: M, stat: S (the same point).

A check that the data cannot give raises NoValue: it is "not evaluated",
never confirmed or wrong.
"""

import re

from . import stats
from .stats import NoValue

AGG = re.compile(r"^(max|min)\((.+)\)$")
FORMS = ("range", "equals", "spread_le", "spread_abs_le", "order", "diff_to", "ratio_to", "diff_change",
         "within", "hist_identical_to")
EXPECT = set(FORMS) | {"tolerance_bins"}


def form_of(expect):
    """The one comparison form of an expect (ratio_to takes range, within takes tolerance_bins)."""
    keys = set(expect)
    if "ratio_to" in keys:
        keys -= {"range"}
    if "within" in keys:
        keys -= {"tolerance_bins"}
    forms = [k for k in FORMS if k in keys]
    if len(forms) != 1 or keys - set(FORMS):
        raise NoValue(f"expect {sorted(expect)}: give exactly one form of {', '.join(FORMS)}")
    return forms[0]


def problems(check):
    """Forms of a check that the tools do not know (an empty list if all are known)."""
    if check.get("manual"):
        return [] if check.get("statement") else ["a manual check needs a statement"]
    out = []
    expect = check.get("expect") or {}
    if not expect:
        out.append("no expect")
    else:
        try:
            form = form_of(expect)
        except NoValue as e:
            out.append(str(e))
            form = None
        if check.get("stat") is None and form not in ("hist_identical_to", None) \
                and not all((m or "").startswith("meta.") for m in as_list(check.get("metric"))):
            out.append("no stat")
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
    """The points of obs that the select of a check names. A named point that is not there raises NoValue."""
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
    if "point" in sel:
        missing = sorted(set(as_list(sel["point"])) - {o.point for o in out})
        if missing:
            raise NoValue(f"select: the points {missing} are not in the data")
    return out


def by_series(obs):
    groups = {}
    for o in obs:
        groups.setdefault(o.series, []).append(o)
    return groups


def is_point_agg(metric, stat):
    """max(x) / min(x) of a histogram metric: over the selected points."""
    return isinstance(stat, str) and bool(AGG.match(stat)) and not (metric or "").startswith("m4.")


def value(o, metric, stat):
    return stats.value(o.rep, metric, stat)


def series_values(points, metric, stat):
    """[(name, value, obs, width)] for the points of one series; one entry for a point aggregate.

    width is the bin width of a quantile value (1 for an exact value).
    """
    m = AGG.match(stat) if is_point_agg(metric, stat) else None
    if m:
        f, inner = m.groups()
        vals = [(o, value(o, metric, inner)) for o in points]
        o, v = (max if f == "max" else min)(vals, key=lambda x: x[1])
        return [(f"{f} over {len(vals)} points ({o.point})", v, o, stats.value_width(o.rep, metric, inner))]
    return [(o.point, value(o, metric, stat), o, stats.value_width(o.rep, metric, stat)) for o in points]


def in_range(v, rng):
    lo, hi = rng
    return (lo is None or v >= lo) and (hi is None or v <= hi)


def range_verdict(v, width, rng):
    """True / False, or None if the limit is inside the bin of the value (lower edge v, width)."""
    if width <= 1:
        return in_range(v, rng)
    top = v + width - 1
    if in_range(v, rng) and in_range(top, rng):
        return True
    lo, hi = rng
    if (hi is not None and v > hi) or (lo is not None and top < lo):
        return False
    return None


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


def label(series, metric, stat, with_run=False):
    run, tree = series
    parts = [f"{run.split('/')[-1]} {tree}" if with_run else tree]
    if metric:
        parts.append(metric)
    if stat:
        parts.append(stat)
    return " ".join(parts)


def check_functions(src, exp, metrics):
    """An M4 metric with [function]: the function must be in the data (else it is a typo or another build)."""
    for m in metrics:
        if m and m.startswith("m4.") and "[" in m:
            if not any(stats.function_seen(o.rep, m) for o in src.observations(exp)):
                raise NoValue(f"{m}: no M4 site of this function in any point of {exp}")


def evaluate(check, src):
    """Return {verdict, measured, limit, values} for a check that is not manual."""
    exp = check.get("experiment")
    expect = dict(check.get("expect") or {})
    form = form_of(expect)
    obs = select(src.observations(exp), check.get("select"))
    if not obs:
        raise NoValue(f"no points of {exp} for select {check.get('select')}")
    metrics = as_list(check.get("metric"))
    stat_list = as_list(check.get("stat"))
    check_functions(src, exp, metrics)
    res = Result()
    series = by_series(obs)

    if form == "hist_identical_to":
        ref = expect["hist_identical_to"]
        name = ref.get("run") or ref.get("experiment")
        for s, pts in series.items():
            tree = ref.get("tree", s[1])
            cands = src.run_obs(ref["run"]) if "run" in ref else src.observations(ref["experiment"])
            ref_obs = [r for r in cands if r.point == ref["point"] and r.tree == tree]
            if not ref_obs:
                raise NoValue(f"reference {name} has no point {tree}/{ref['point']}")
            if len(ref_obs) > 1:
                raise NoValue(f"reference {name} {ref['point']}: {len(ref_obs)} runs, the reference is not clear")
            for o in pts:
                for m in metrics:
                    same = stats.hist_identical(o.rep["hists"][m], ref_obs[0].rep["hists"][m])
                    res.add(same, f"{label(o.series, None, None, len(series) > 1)}/{o.point} {m}: "
                                  f"{'same' if same else 'differs'}",
                            {"point": o.point, "metric": m, "identical": same})
        return finish(res, "the same histogram, bin for bin as " + f"{name} {ref['point']}")

    with_run = len({o.run for o in obs}) > 1
    undecided = []
    for s, pts in series.items():
        for m in metrics:
            for st in stat_list:
                lab = label(s, m, st, with_run)
                if form == "range":
                    for name, v, _, w in series_values(pts, m, st):
                        ok = range_verdict(v, w, expect["range"])
                        if ok is None:
                            undecided.append(f"{lab} {name}: {fmt(v)}..{fmt(v + w - 1)} (coarse bin)")
                            continue
                        bin_text = f" (bin {fmt(v)}..{fmt(v + w - 1)})" if w > 1 else ""
                        res.add(ok, f"{lab} {name}: {fmt(v)}{bin_text}", {"series": lab, "point": name, "value": v})
                elif form == "equals":
                    want = expect["equals"]
                    for name, v, _, _ in series_values(pts, m, st):
                        ok = v == want or (isinstance(v, str) and st == "top_place"
                                           and want in re.split(r"[ ()<]+|via ", v))
                        res.add(ok, f"{lab} {name}: {fmt(v)}", {"series": lab, "point": name, "value": v})
                elif form in ("spread_le", "spread_abs_le"):
                    nums = [v for _, v, _, _ in series_values(pts, m, st)]
                    if len(nums) < 2:
                        raise NoValue(f"{lab}: a spread needs two points or more, the series has {len(nums)}")
                    if form == "spread_le":
                        if min(nums) <= 0:
                            raise NoValue(f"{lab}: a relative spread needs values above 0 ({fmt(min(nums))})")
                        sp = (max(nums) - min(nums)) / min(nums)
                        res.add(sp <= expect["spread_le"], f"{lab}: spread {sp:.2%} ({fmt(min(nums))}..{fmt(max(nums))})",
                                {"series": lab, "spread": sp, "min": min(nums), "max": max(nums)})
                    else:
                        sp = max(nums) - min(nums)
                        res.add(sp <= expect["spread_abs_le"], f"{lab}: {fmt(min(nums))}..{fmt(max(nums))}",
                                {"series": lab, "spread": sp, "min": min(nums), "max": max(nums)})
                elif form == "order":
                    order_check(res, lab, pts, m, st, expect["order"])
                elif form in ("diff_to", "ratio_to", "diff_change"):
                    ref_check(res, lab, pts, m, st, expect, src)
                elif form == "within":
                    within_check(res, lab, pts, m, st, expect, src, s)
    if undecided and res.ok:
        raise NoValue("the limit is inside the coarse bin of the value: " + "; ".join(undecided))
    out = finish(res, limit_text(expect))
    if undecided:
        out["measured"] += "; undecided (coarse bin): " + "; ".join(undecided)
    return out


def order_check(res, lab, pts, m, st, order):
    if isinstance(order, list):
        present = {o.point for o in pts}
        missing = [p for p in order if p not in present]
        if missing:
            raise NoValue(f"{lab}: order {order}: the points {missing} are not in the series")
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
        groups = {k: g for k, g in groups.items() if len(g) > 1}
    if not groups:
        raise NoValue(f"{lab}: order {order}: no group of two points or more")
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
        if len(found) > 1:
            raise NoValue(f"reference {spec['experiment']} {want}: {len(found)} runs, the reference is not clear")
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
            same = {x.point: x for x in src.observations(None, series=o.series)}
            for p in (spec["point"], q, r):
                if p not in same:
                    raise NoValue(f"diff_change: no point {p} in {o.series}")
            v = (value(o, m, st) - value(same[spec["point"]], m, st)) - (value(same[q], m, st) - value(same[r], m, st))
            res.add(in_range(v, spec["range"]), f"{lab} {o.point}: ({o.point} - {spec['point']}) - ({q} - {r}) = {fmt(v)}",
                    {"series": lab, "point": o.point, "value": v})
        return
    ratio = "ratio_to" in expect
    spec = expect["ratio_to" if ratio else "diff_to"]
    ref_metric = spec.get("metric", m)
    ref_stat = spec.get("stat", st)
    pairs = []
    for name, v, o, _ in series_values(pts, m, st):
        r = ref_obs_for(o, spec, src)  # for a point aggregate: the reference of the point that gave it
        pairs.append((name, v, r, value(r, ref_metric, ref_stat)))
    diffs = []
    for name, v, r, rv in pairs:
        what = f"{r.point}" if r.run == pts[0].run else f"{r.run} {r.tree}/{r.point}"
        if ref_metric != m or ref_stat != st:
            what += f" {ref_metric or ''} {ref_stat or ''}".rstrip()
        if ratio:
            if not rv:
                raise NoValue(f"{lab} {name}: the reference value is 0")
            q = v / rv
            res.add(in_range(q, expect["range"]), f"{lab} {name}: {fmt(v)} / {fmt(rv)} ({what}) = {q:.3f}",
                    {"series": lab, "point": name, "value": v, "reference": rv, "ratio": q})
        else:
            d = v - rv
            diffs.append(d)
            if "spread_abs_le" in spec:
                res.lines.append(f"{lab} {name}: {fmt(v)} - {fmt(rv)} ({what}) = {fmt(d)}")
                res.values.append({"series": lab, "point": name, "value": v, "reference": rv, "diff": d})
            else:
                res.add(in_range(d, spec["range"]), f"{lab} {name}: {fmt(v)} - {fmt(rv)} ({what}) = {fmt(d)}",
                        {"series": lab, "point": name, "value": v, "reference": rv, "diff": d})
    if not ratio and "spread_abs_le" in spec:
        if len(diffs) < 2:
            raise NoValue(f"{lab}: diff_to spread_abs_le needs two points or more")
        sp = max(diffs) - min(diffs)
        res.add(sp <= spec["spread_abs_le"], f"{lab}: the differences {fmt(min(diffs))}..{fmt(max(diffs))} "
                                             f"differ by {fmt(sp)}", {"series": lab, "diff_spread": sp})


def within_check(res, lab, pts, m, st, expect, src, series):
    spec = expect["within"]
    ref = [r for r in src.observations(spec["experiment"]) if r.tree == series[1]]
    if not ref:
        raise NoValue(f"no points of {spec['experiment']} on tree {series[1]}")
    rv = [value(r, m, st) for r in ref]
    # one coarse bin: the width of the coarse bins of this metric (in the point or in the reference)
    widths = [stats.coarse_width(x.rep["hists"][m]) for x in [*pts, *ref] if m in x.rep["hists"]]
    width = max(widths) if widths else 1
    for o in pts:
        v = value(o, m, st)
        tol = expect.get("tolerance_bins", 0) * width
        ok = min(rv) - tol <= v <= max(rv) + tol
        res.add(ok, f"{lab} {o.point}: {fmt(v)} ({spec['experiment']} {fmt(min(rv))}..{fmt(max(rv))}, +-{tol})",
                {"series": lab, "point": o.point, "value": v, "range": [min(rv), max(rv)], "tolerance": tol})


def limit_text(expect):
    e = dict(expect)
    form = form_of(e)
    if form == "range":
        return rng_text(e["range"])
    if form == "equals":
        return f"= {e['equals']}"
    if form == "spread_le":
        return f"spread <= {e['spread_le']:.0%}"
    if form == "spread_abs_le":
        return f"max - min <= {fmt(e['spread_abs_le'])}"
    if form == "order":
        o = e["order"]
        return ("increasing: " + " < ".join(o)) if isinstance(o, list) else \
            "increasing along " + ", ".join(f"{a}: {' < '.join(v)}" for a, v in o.items())
    if form == "ratio_to":
        return f"ratio {rng_text(e['range'])}"
    if form == "diff_to":
        d = e["diff_to"]
        return f"diff {rng_text(d['range'])}" if "range" in d else \
            f"the differences differ by <= {fmt(d['spread_abs_le'])}"
    if form == "diff_change":
        return f"change {rng_text(e['diff_change']['range'])}"
    if form == "within":
        return f"within {e['within']['experiment']} +- {e.get('tolerance_bins', 0)} coarse bins"
    return "the same histogram, bin for bin"


# Up to this number of lines, "measured" has them all; with more, it has a short form (the
# number of values, min and max, the lines outside the limit) and "measured_lines" has them all.
MEASURED_LINES = 4


def short_measured(res):
    if len(res.lines) <= MEASURED_LINES:
        return "; ".join(res.lines)
    fails = [ln for ln in res.lines if ln.startswith("FAIL ")]
    # the value that the check compares with its limit: a ratio, a difference, else the value
    key = next((k for k in ("ratio", "diff") if any(k in v for v in res.values)), "value")
    nums = [v[key] for v in res.values if isinstance(v.get(key), (int, float)) and not isinstance(v.get(key), bool)]
    text = f"{len(res.lines)} values"
    if nums:
        text += f", {'' if key == 'value' else key + ' '}min {fmt(min(nums))}, max {fmt(max(nums))}"
    if fails:
        text += f"; {len(fails)} outside the limit: " + "; ".join(fails[:3]) + ("; ..." if len(fails) > 3 else "")
    else:
        text += "; all in the limit"
    return text


def finish(res, limit):
    out = {"verdict": "confirmed" if res.ok else "wrong", "measured": short_measured(res),
           "limit": limit, "values": res.values}
    if len(res.lines) > MEASURED_LINES:
        out["measured_lines"] = list(res.lines)
    return out
