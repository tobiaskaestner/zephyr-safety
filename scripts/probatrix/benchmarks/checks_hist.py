# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The check forms that only the latency benchmarks have (the extra_forms of the latbench Kind).

within: {experiment: E, ...} + tolerance_bins: k    value in min..max of the points of E, +- k coarse bins
hist_identical_to: {run | experiment, point[, tree]}  the same histogram, bin for bin

The code of the two forms was in studylib/checks.py and is moved without a change of the rounding or of the
texts; only value() now takes the Kind (it rejects a boolean or a text), and hist_identical_to returns its
limit text instead of calling finish(). The general bin rule for range (the interval of a value with a width)
stays in core/checks.py: it is interval arithmetic and has no histogram in it.
"""

from probatrix.benchmarks.studylib import stats
from probatrix.core.checks import as_list, fmt, label, value  # noqa: F401
from probatrix.core.errors import NoValue


def within_check(res, lab, pts, m, st, expect, src, series):
    spec = expect["within"]
    ref = [r for r in src.observations(spec["experiment"]) if r.tree == series[1]]
    if not ref:
        raise NoValue(f"no points of {spec['experiment']} on tree {series[1]}")
    rv = [value(res.kind, r, m, st) for r in ref]
    # one coarse bin: the width of the coarse bins of this metric (in the point or in the reference)
    widths = [stats.coarse_width(x.rep["hists"][m]) for x in [*pts, *ref] if m in x.rep["hists"]]
    width = max(widths) if widths else 1
    for o in pts:
        v = value(res.kind, o, m, st)
        tol = expect.get("tolerance_bins", 0) * width
        ok = min(rv) - tol <= v <= max(rv) + tol
        res.add(ok, f"{lab} {o.point}: {fmt(v)} ({spec['experiment']} {fmt(min(rv))}..{fmt(max(rv))}, +-{tol})",
                {"series": lab, "point": o.point, "value": v, "range": [min(rv), max(rv)], "tolerance": tol})


def hist_identical_check(res, src, expect, series, metrics):
    """The form hist_identical_to; returns the limit text."""
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
    return "the same histogram, bin for bin as " + f"{name} {ref['point']}"


class Within:
    companions = ("tolerance_bins",)
    needs_stat = True

    @staticmethod
    def limit(e):
        return f"within {e['within']['experiment']} +- {e.get('tolerance_bins', 0)} coarse bins"

    @staticmethod
    def evaluate(res, src, expect, series, metrics, stat_list, with_run):
        for s, pts in series.items():
            for m in metrics:
                for st in stat_list:
                    lab = label(s, m, st, with_run)
                    within_check(res, lab, pts, m, st, expect, src, s)
        return Within.limit(expect)


class HistIdentical:
    companions = ()
    needs_stat = False

    @staticmethod
    def limit(e):
        return "the same histogram, bin for bin"

    @staticmethod
    def evaluate(res, src, expect, series, metrics, stat_list, with_run):
        return hist_identical_check(res, src, expect, series, metrics)


FORMS = {"within": Within, "hist_identical_to": HistIdentical}
