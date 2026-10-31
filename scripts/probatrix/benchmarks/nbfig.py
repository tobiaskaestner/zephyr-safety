# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Interactive figures for the study notebooks (needs pandas and plotly).

    from probatrix.benchmarks import data, nbfig
    inst = data.load_instance(INSTANCE)
    nbfig.intro(inst)                          the instance, the tools, the question
    nbfig.ccdf({label: hists}, "title")        CCDF, a menu selects the metric
    nbfig.hist({label: hists}, "title")        histogram (the line goes down at empty bins), a menu for the metric
    nbfig.hists_of(inst, "wake-isr-1m")        {label: hists} of the evidence points of an experiment
    nbfig.clocks_of(inst, "irq-checks-1m")     {label: core_hz} of the same points (the hz of ccdf and hist)
    nbfig.ladder(df, "title")                  the percentiles of each point, one line per series
    nbfig.sweep(df, "value.timers", "title")   a statistic over a numeric axis, one line per group
    nbfig.dots(df, "title")                    statistics per point: colour = tree, symbol = statistic
    nbfig.pivot(df, "p50")                     a table: points x metrics
    nbfig.limits(df, "title", "y")             measured values against the limit range of their checks
    nbfig.distinct(fig)                        a symbol and a size per series, so equal values stay visible
    nbfig.style(fig, "title", "x", "y")        the common look for a figure of your own
    nbfig.built(inst, "wake-kconfig-1m")       False (with the reason) if the results tree has no data of it

The differences to a reference point of the same run (kconfig-factors):

    d = nbfig.diffs(inst, "wake-kconfig-1m")   each point minus the point variant=baseline with the same load
    nbfig.check_limits(inst, exp, d)           the limits of the checks of hypotheses.yaml, as differences
    nbfig.diff_fig(d, "title", limits=lim)     diverging bars: one panel per statistic, a menu for the metric
    nbfig.diff_table(d)                        the same differences as a table

The modes of a histogram (check-forms.rst, studylib.stats.modes):

    nbfig.modes(hist)                          [(first value, last value, share)], fastest first
    nbfig.mode_table(inst, [exp], "t2t")       one row per point: the modes and their shares
    nbfig.mode_range(series, "t2t", pad)       an x range around the modes (for hist)

The witnesses of the tail samples (LATBENCH_TAIL, tails.py):

    w = inst.tails("irq-witness-check-1m")     one row per tail sample: counters, labels, cause
    nbfig.tails(w, "title")                    each tail sample at its tick phase, the colour is the cause

df is a table of inst.rows(experiment) (or several of them, concatenated).
Each figure has a hover text with the value in cycles and in microseconds,
a legend (click an entry to hide the series) and zoom (drag). The
microseconds use the clock of each point: the column core_hz of df (or the
hz argument of ccdf and hist), else CORE_HZ. The colours are a fixed order
of eight colours: a series keeps its colour when a menu changes the
metric. A figure with a metric menu gives each metric its own traces and
legend entries: a legend click never shows a trace of another metric. The
notebooks keep the data in tables beside the figures, so a value is never
in a colour only. The HTML of an executed notebook loads plotly.js from its
CDN (cdn.plot.ly) when it opens.
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from probatrix.benchmarks import data
from probatrix.benchmarks.studylib import stats as _stats

# Each figure gives the plotly data (Jupyter) and HTML that loads plotly.js
# from its CDN: nbconvert can only show the HTML.
pio.renderers.default = "plotly_mimetype+notebook_connected"

# The categorical colours, in a fixed order (light surface).
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
STATS = ["p50", "p90", "p99", "p99.9", "p99.99", "max"]
# The metrics in the order of the menus: the main metric of each app first.
METRIC_NAMES = {
    "t2t": "thread to thread (wake call to taker)",
    "isr2thr": "ISR to thread",
    "irq": "IRQ entry (edge to ISR)",
    "irq2thr": "edge to thread",
    "t2t_ret": "wake call to its return",
    "irq_sw": "IRQ entry, software trigger (STIR to ISR)",
    "isr2thr_sw": "ISR to thread, software trigger",
    "irq2thr_sw": "STIR to thread, software trigger",
    "irq_unlock": "irq_unlock() to ISR",
    "irq_nested": "IRQ entry in a lower-priority ISR",
    "irq_nested_sw": "IRQ entry in a lower-priority ISR, software trigger",
    "irq_exit": "end of the ISR to the interrupted thread",
    "irq_b2b": "ISR entry to the next ISR entry (back to back)",
}
CORE_HZ = 170_000_000
# The statistics of the difference figures, and the open end of a limit band.
DIFF_STATS = ("p50", "p99", "max")
INF = float("inf")


def color(i):
    return COLORS[i % len(COLORS)]


def metric_order(names):
    """The metrics of names in the order of the menus: the main metric of each app first."""
    names = set(names)
    return [m for m in METRIC_NAMES if m in names] + sorted(names - set(METRIC_NAMES))


def _hz(df):
    """The core clock of each row of df: its column core_hz, else CORE_HZ."""
    if "core_hz" not in df:
        return [CORE_HZ] * len(df)
    return [CORE_HZ if pd.isna(h) else h for h in df["core_hz"]]


def _us(cycles, hz):
    """Microseconds of cycle values (None is 0); hz: one clock for all, or one per value."""
    hz = hz if isinstance(hz, (list, tuple)) else [hz] * len(cycles)
    return [(0 if v is None or pd.isna(v) else v) * 1e6 / h for v, h in zip(cycles, hz)]


def _mhz_title(clocks):
    """The x axis title of a latency in cycles: with the clock if all series have one clock."""
    clocks = set(clocks)
    return f"latency (cycles, {int(clocks.pop()) // 1_000_000} MHz)" if len(clocks) == 1 else \
        "latency (cycles of the core clock of each series)"


def style(fig, title, xtitle, ytitle, **kw):
    """The common look: title, axis titles, white template, legend clicks; kw goes to update_layout."""
    fig.update_layout(title=title, xaxis_title=xtitle, yaxis_title=ytitle, template="plotly_white",
                      height=kw.pop("height", 480), hovermode=kw.pop("hovermode", "closest"),
                      legend={"itemclick": "toggle", "itemdoubleclick": "toggleothers"}, **kw)
    fig.update_xaxes(showline=True, linecolor="#c3c2b7", gridcolor="#ecebe7")
    fig.update_yaxes(showline=True, linecolor="#c3c2b7", gridcolor="#ecebe7")
    return fig


def _metric_menu(fig, metrics, per_metric):
    """A menu above the figure: one entry per metric; each metric has per_metric traces."""
    if len(metrics) < 2:
        return
    n = len(metrics) * per_metric
    fig.update_layout(updatemenus=[{
        "buttons": [{"label": METRIC_NAMES.get(m, m), "method": "update",
                     "args": [{"visible": [j // per_metric == i for j in range(n)]}]}
                    for i, m in enumerate(metrics)],
        "x": 1.0, "xanchor": "right", "y": 1.15, "yanchor": "top"}])


def _hover(label):
    return "%{x} cycles (%{customdata:.2f} µs): %{y:.3g}<extra>" + label + "</extra>"


def intro(inst):
    """Print the instance, the tool revision, the warnings and the question of the study."""
    import hashlib
    s = inst.study
    print(s["instance"], "| board", s["board"], "| tools", s["made_by"]["safety_rev"][:12])
    for name, digest in s["design"]["files"].items():
        if hashlib.sha256((inst.design_folder / name).read_bytes()).hexdigest() != digest:
            print(f"WARNING: {name} changed after the build of the instance")
    print()
    print(s["question"])


def metrics_of(series):
    """The metrics that all series have, in a fixed order."""
    return metric_order(set.intersection(*(set(h) for h in series.values())) if series else set())


def _clock_of(hz, label):
    """The core clock of a series: hz is None (CORE_HZ), one clock, or {label: clock} (CORE_HZ if absent)."""
    if hz is None:
        return CORE_HZ
    return hz.get(label, CORE_HZ) if isinstance(hz, dict) else hz


def ccdf(series, title, metrics=None, dashed=(), hz=None):
    """series: {label: {metric: hist}}. The share of the samples >= x, log scale. hz: the core clock of the
    series for the microseconds (one clock or {label: clock}, see clocks_of)."""
    metrics = metrics or metrics_of(series)
    fig = go.Figure()
    for i, m in enumerate(metrics):
        for k, (label, hists) in enumerate(series.items()):
            x, y = data.ccdf(hists[m])
            fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line_shape="hv", name=label,
                                     visible=(i == 0), customdata=_us(x, _clock_of(hz, label)),
                                     line={"color": color(k), "width": 2, "dash": "dash" if label in dashed else None},
                                     hovertemplate=_hover(label)))
    _metric_menu(fig, metrics, len(series))
    return style(fig, title, _mhz_title(_clock_of(hz, label) for label in series), "share of samples >= x",
                 yaxis_type="log")


def _edges(h):
    """[(lower edge, width, count per cycle)] of the non-empty bins of a histogram (fine bins are 1 cycle wide)."""
    return sorted([(v, 1, c) for v, c in h["bins"]] + [(v, w, c / max(w, 1)) for v, c, w in h["coarse"]])


def _steps(h, floor):
    """The outline of a histogram: a flat top over each bin, a vertical edge down to floor at the start and at
    the end of each run of touching bins, and a gap up to the next run, so an empty bin shows no count and a
    single bin of 1 cycle stays visible. The text of each point is its count ("empty" at the floor)."""
    edges = _edges(h)
    xs, ys, texts = [], [], []
    for j, (v, w, c) in enumerate(edges):
        if j == 0 or edges[j - 1][0] + edges[j - 1][1] != v:
            xs.append(v)
            ys.append(floor)
            texts.append("empty")
        xs += [v, v + w]
        ys += [c, c]
        texts += [f"{c:.3g}"] * 2
        if j + 1 == len(edges) or edges[j + 1][0] != v + w:
            xs += [v + w, None]
            ys += [floor, None]
            texts += ["empty", ""]
    return xs, ys, texts


def hist(series, title, metrics=None, xrange=None, hz=None):
    """series: {label: {metric: hist}}. The count per cycle of each bin (a coarse bin: its count / its width),
    log y; the outline goes down to a floor below the smallest count at each empty bin. hz: the core clock of
    the series, as for ccdf. With one metric, the x axis title names it."""
    metrics = metrics or metrics_of(series)
    fig = go.Figure()
    for i, m in enumerate(metrics):
        # one floor for all series of a metric: half the smallest count per cycle, at most 0.5
        floor = min([0.5] + [c / 2 for hists in series.values() for _, _, c in _edges(hists[m]) if c > 0])
        for k, (label, hists) in enumerate(series.items()):
            xs, ys, texts = _steps(hists[m], floor)
            fig.add_trace(go.Scatter(x=xs, y=ys, text=texts, mode="lines", name=label, connectgaps=False,
                                     visible=(i == 0), customdata=_us(xs, _clock_of(hz, label)),
                                     line={"color": color(k), "width": 2},
                                     hovertemplate="%{x} cycles (%{customdata:.2f} µs): %{text}<extra>" + label
                                                   + "</extra>"))
    _metric_menu(fig, metrics, len(series))
    fig = style(fig, title, f"{metrics[0]} latency (cycles)" if len(metrics) == 1 else "latency (cycles)",
                "samples per cycle", yaxis_type="log")
    if xrange:
        fig.update_xaxes(range=list(xrange))
    return fig


def _reps_of(inst, experiment, tree=None, label=None, points=None):
    """{label: rep 1} of the evidence points of an experiment (see hists_of)."""
    pts = inst.points(experiment)
    trees = {t for _, t, _, _ in pts}
    if points is not None:
        pts = sorted((x for x in pts if x[2] in points), key=lambda x: list(points).index(x[2]))
    out = {}
    for run, t, point, rep in pts:
        if tree is not None and t != tree:
            continue
        out[label(run, t, point) if label else (point if len(trees) == 1 else f"{t}/{point}")] = rep
    return out


def hists_of(inst, experiment, tree=None, label=None, points=None):
    """{label: hists} of the evidence points of an experiment. label(run, tree, point) names a series (default:
    the point, with its tree if the experiment has several trees). points: only these points, in this order."""
    return {k: rep["hists"] for k, rep in _reps_of(inst, experiment, tree, label, points).items()}


def clocks_of(inst, experiment, tree=None, label=None, points=None):
    """{label: core_hz} of the same points as hists_of (LAT META core_hz; CORE_HZ if a point has none)."""
    out = {}
    for k, rep in _reps_of(inst, experiment, tree, label, points).items():
        h = rep["meta"].get("core_hz")
        out[k] = h if isinstance(h, (int, float)) else CORE_HZ
    return out


def ladder(df, title, stats=STATS, series="point"):
    """The percentiles of each series (log y), one line per series; a menu selects the metric."""
    metrics = metric_order(df.metric)
    groups = list(dict.fromkeys(df[series]))
    fig = go.Figure()
    for i, m in enumerate(metrics):
        for k, g in enumerate(groups):
            row = df[(df.metric == m) & (df[series] == g)]
            ys = [row[s].iloc[0] if len(row) else None for s in stats]
            fig.add_trace(go.Scatter(x=list(stats), y=ys, mode="lines+markers", name=str(g),
                                     visible=(i == 0), marker={"size": 8},
                                     line={"color": color(k), "width": 2},
                                     customdata=_us(ys, _hz(row)[0] if len(row) else CORE_HZ),
                                     hovertemplate="%{x}: %{y} cycles (%{customdata:.2f} µs)<extra>" + str(g)
                                                   + "</extra>"))
    _metric_menu(fig, metrics, len(groups))
    return style(fig, title, "statistic", "latency (cycles)", yaxis_type="log")


def sweep(df, x, title, stats=("p50", "p99", "max"), group=None, log_y=False):
    """A statistic over a numeric column x, one line per group (and per statistic); a menu selects the metric."""
    metrics = metric_order(df.metric)
    groups = list(dict.fromkeys(df[group])) if group else [None]
    fig = go.Figure()
    per = len(groups) * len(stats)
    for i, m in enumerate(metrics):
        k = 0
        for g in groups:
            for j, st in enumerate(stats):
                sub = df[df.metric == m] if g is None else df[(df.metric == m) & (df[group] == g)]
                sub = sub.sort_values(x)
                name = st if g is None else f"{g} {st}"
                fig.add_trace(go.Scatter(x=sub[x], y=sub[st], mode="lines+markers", name=name,
                                         visible=(i == 0), marker={"size": 8},
                                         line={"color": color(k if g is None else groups.index(g)), "width": 2,
                                               "dash": [None, "dash", "dot", "dashdot"][j % 4]},
                                         customdata=sub["point"],
                                         hovertemplate=f"{x.split('.')[-1]} %{{x}}: %{{y}} cycles"
                                                       "<br>%{customdata}<extra>" + name + "</extra>"))
                k += 1
    _metric_menu(fig, metrics, per)
    return style(fig, title, x.split(".", 1)[-1], "latency (cycles)", yaxis_type="log" if log_y else "linear")


SYMBOLS = ["circle", "diamond", "triangle-up", "square", "x", "star"]


def dots(df, title, stats=("p50", "p99", "max"), x="point", group="tree", log_y=True):
    """The statistics of each point on a categorical x axis: the colour is the group (the tree), the symbol
    the statistic. A menu selects the metric. Equal values of two groups do not hide each other: each series has
    its own offset on the x axis (scattermode "group"), because the symbol already gives the statistic."""
    metrics = metric_order(df.metric)
    groups = list(dict.fromkeys(df[group]))
    fig = go.Figure()
    for i, m in enumerate(metrics):
        for k, g in enumerate(groups):
            sub = df[(df.metric == m) & (df[group] == g)]
            for j, st in enumerate(stats):
                name = st if len(groups) == 1 else f"{g} {st}"
                fig.add_trace(go.Scatter(x=sub[x], y=sub[st], mode="markers", name=name,
                                         visible=(i == 0), offsetgroup=name,
                                         marker={"color": color(k), "size": 10, "symbol": SYMBOLS[j % len(SYMBOLS)],
                                                 "line": {"color": "#fcfcfb", "width": 1}},
                                         customdata=_us(list(sub[st]), _hz(sub)),
                                         hovertemplate="%{x}: %{y} cycles (%{customdata:.2f} µs)<extra>" + name
                                                       + "</extra>"))
    _metric_menu(fig, metrics, len(groups) * len(stats))
    # scattermode "group": each statistic has its own offset, so equal values do not hide each other
    return style(fig, title, x, "latency (cycles)", yaxis_type="log" if log_y else "linear", scattermode="group")


def pivot(df, stat="p50", index="point", columns="metric"):
    """A table: one row per point, one column per metric (and tree, if there are several). stat can be a
    list: then one column per statistic and metric."""
    cols = [columns] if df["tree"].nunique() == 1 else ["tree", columns]
    return df.pivot_table(index=index, columns=cols, values=stat, aggfunc="first", sort=False)


def built(inst, experiment):
    """True if the results tree has the built experiment; else print why not (a section then shows nothing)."""
    try:
        inst.experiment_folder(experiment)
        return True
    except FileNotFoundError as e:
        print(f"{experiment}: not shown: {e}")
        return False


# ------------------------------------------------------------------ limits of checks, equal values
def limits(df, title, ytitle, label="check", series="series"):
    """Each row of df: a measured value (column value; a marker, the colour is the series) and the limit range of
    its check (columns lo, hi; a grey bar). label names the x category of a row."""
    lim = df.drop_duplicates(label)
    fig = go.Figure(go.Bar(x=lim[label], y=lim.hi - lim.lo, base=lim.lo, width=0.5, name="limit of the check",
                           marker={"color": "#c3c2b7", "opacity": 0.5}, customdata=lim[["lo", "hi"]],
                           hovertemplate="%{x}<br>limit %{customdata[0]} .. %{customdata[1]}<extra></extra>"))
    for k, s in enumerate(dict.fromkeys(df[series])):
        sub = df[df[series] == s]
        fig.add_trace(go.Scatter(x=sub[label], y=sub.value, mode="markers", name=str(s),
                                 marker={"color": color(k), "size": 12, "symbol": SYMBOLS[k % len(SYMBOLS)],
                                         "line": {"color": "#fcfcfb", "width": 1}},
                                 hovertemplate="%{x}: %{y}<extra>" + str(s) + "</extra>"))
    return style(fig, title, "", ytitle)


def distinct(fig):
    """A symbol and a size for each series with markers (its legend entry), so that equal values of two series
    stay visible: the later series is smaller, inside the earlier one. For a figure whose symbols give no
    other information; dots gives each series an x offset instead."""
    marked = [t for t in fig.data if t.type == "scatter" and "markers" in (t.mode or "")]
    groups = list(dict.fromkeys(t.legendgroup or t.name for t in marked))
    for t in marked:
        k = groups.index(t.legendgroup or t.name)
        t.marker.symbol = SYMBOLS[k % len(SYMBOLS)]
        t.marker.size = max(14 - 2 * k, 6)
    return fig


# ------------------------------------------------------------------ differences to a reference point
def diffs(inst, experiment, axis="variant", baseline="baseline", match=("load",), names=None, stats=DIFF_STATS,
          missing="none"):
    """The differences of each point to its reference point. The reference has the label baseline on the axis
    and the same labels on the axes of match, in the same run, tree and repetition. One row per run, point and
    metric of the evidence runs (without the runs that the acceptance excluded): v_<stat> the value of the
    point, b_<stat> the value of the reference, d_<stat> = v_<stat> - b_<stat>, reference (True for the
    reference points). The column <axis> has the label of the axis, a column <a> for each axis a of match its
    label with the text of names ({label: text}). An experiment without the axis a has the label missing. With
    two runs or more, the point names get the UTC of their run."""
    ej = inst.experiment_json(experiment)
    excluded = {r["id"] for r in ej["runs"] if r.get("excluded_by_acceptance")}
    df = inst.rows(experiment)
    df = df[(df.role == "evidence") & ~df.run.isin(excluded)].copy()
    for a in match:
        if f"axis.{a}" not in df:
            df[f"axis.{a}"] = missing
    if df.run.nunique() > 1:
        df["point"] = df.point + " " + df.run.str.split("/").str[1]
    key = ["run", "tree", "rep", *[f"axis.{a}" for a in match], "metric"]
    base = df[df[f"axis.{axis}"] == baseline].set_index(key)[list(stats)].add_prefix("b_")
    d = df.join(base, on=key)
    for s in stats:
        d["v_" + s] = d[s]
        d["d_" + s] = d[s] - d["b_" + s]
    d[axis] = d[f"axis.{axis}"]
    d["reference"] = d[axis] == baseline
    for a in match:
        d[a] = d[f"axis.{a}"].map(lambda v: (names or {}).get(v, v))
    return d


def check_limits(inst, experiment, d, axis="variant", baseline="baseline"):
    """The limits of the checks of hypotheses.yaml on the experiment, as a difference to the reference point (the
    unit of diff_fig). d: the table of diffs. One row per band: check, point, metric, stat, lo, hi (INF: an open
    end), expect. Forms: range, diff_to and ratio_to (with a point as reference) and order (a list of points).
    The manual checks and the other forms are in inst.checks() only."""
    v = d.groupby(["point", "metric"])[[c for c in d if c[:2] in ("v_", "b_")]].mean()
    label = d.drop_duplicates("point").set_index("point")[axis]

    def val(p, m, s, kind="v"):
        try:
            return float(v.loc[(p, m), f"{kind}_{s}"])
        except KeyError:
            return None

    def dif(p, q, m, s):
        """The value of p minus the reference value of q (q = p: the difference of p in diff_fig)."""
        a, b = val(p, m, s), val(q, m, s, "b")
        return None if a is None or b is None else a - b

    def band(lo, hi, f):
        """(lo, hi) through f, an open end (None) as -INF / INF."""
        return -INF if lo is None else f(lo), INF if hi is None else f(hi)

    out = []
    for h in inst.design_hypotheses.values():
        for c in h.get("checks", []):
            if c.get("experiment") != experiment or c.get("manual") or "metric" not in c:
                continue
            m, s, e = c["metric"], c["stat"], c["expect"]
            if f"v_{s}" not in v:
                continue
            sel = (c.get("select") or {}).get("point")
            bands = []
            if "diff_to" in e and "range" in e["diff_to"] and sel and "point" in e["diff_to"]:
                # value - the value of the reference point in lo..hi: the difference of sel in lo + off..hi + off
                off = dif(e["diff_to"]["point"], sel, m, s)
                if off is not None:
                    bands = [(sel, *band(*e["diff_to"]["range"], lambda x: x + off))]
            elif "ratio_to" in e and sel and "point" in e["ratio_to"]:
                r, b = val(e["ratio_to"]["point"], m, e["ratio_to"].get("stat", s)), val(sel, m, s, "b")
                if r is not None and b is not None:
                    bands = [(sel, *band(*e["range"], lambda x: x * r - b))]
            elif "range" in e and sel:
                b = val(sel, m, s, "b")
                if b is not None:
                    bands = [(sel, *band(*e["range"], lambda x: x - b))]
            elif isinstance(e.get("order"), list):
                # each pair: the later point is above the earlier one. The band is on the later point, or on the
                # earlier one if the later one is a reference point (diff_fig does not show it)
                for a, b in zip(e["order"], e["order"][1:]):
                    if label.get(b) == baseline and dif(b, a, m, s) is not None:
                        bands.append((a, -INF, dif(b, a, m, s)))
                    elif dif(a, b, m, s) is not None:
                        bands.append((b, dif(a, b, m, s), INF))
            for p, lo, hi in bands:
                out.append({"check": f"{h['id']} {c['id']}", "point": p, "metric": m, "stat": s, "lo": lo, "hi": hi,
                            "expect": str(e)})
    return pd.DataFrame(out, columns=["check", "point", "metric", "stat", "lo", "hi", "expect"])


def diff_fig(d, title, limits=None, y="point", color="load", menu="metric", stats=DIFF_STATS,
             what="variant - baseline"):
    """Diverging bars: one panel per statistic (its own x scale), one bar per category of y, the colour is the
    group (column color); a dot at the end of each bar keeps a difference of 0 visible. A menu selects the
    value of the column menu (the metric). The grey bands are limits (rows of check_limits, matched by y, menu and
    stat). d: a table with the columns d_/v_/b_<stat> (diffs); its reference points are left out. A legend
    entry is one group of one metric: a click hides its bars in all panels."""
    d = d[~d["reference"]] if "reference" in d else d
    menus = metric_order(d[menu])
    groups = list(dict.fromkeys(d[color]))
    cats = list(dict.fromkeys(d[y]))
    fig = make_subplots(rows=1, cols=len(stats), shared_yaxes=True, horizontal_spacing=0.03,
                        subplot_titles=[f"{s}: {what}" for s in stats])
    owner = []

    def add(trace, i, j):
        fig.add_trace(trace, row=1, col=j + 1)
        owner.append(i)

    for i, m in enumerate(menus):
        dm = d[d[menu] == m]
        for j, s in enumerate(stats):
            for k, g in enumerate(groups):
                sub = dm[dm[color] == g]
                if not len(sub):
                    continue
                # the legend group is the metric and the group: a click cannot show a trace of another metric
                lg = f"{m} / {g}"
                cd = list(zip(sub["v_" + s], sub["b_" + s], _us(list(sub["d_" + s]), _hz(sub))))
                add(go.Bar(y=sub[y], x=sub["d_" + s], orientation="h", name=str(g), legendgroup=lg,
                           showlegend=(j == 0), visible=(i == 0), marker_color=COLORS[k % len(COLORS)],
                           customdata=cd,
                           hovertemplate="%{y}: %{x:+.0f} cycles (%{customdata[2]:+.2f} µs)"
                                         "<br>value %{customdata[0]}, reference %{customdata[1]}"
                                         f"<extra>{g} {s}</extra>"), i, j)
                add(go.Scatter(y=sub[y], x=sub["d_" + s], mode="markers", name=str(g), legendgroup=lg,
                               showlegend=False, visible=(i == 0), hoverinfo="skip",
                               marker={"color": COLORS[k % len(COLORS)], "size": 7,
                                       "line": {"color": "#fcfcfb", "width": 1}}), i, j)
            # the x axis of a panel spans at least -5..5 cycles: a difference of 1 cycle stays small
            add(go.Scatter(x=[-5, 5], y=[cats[0]] * 2, mode="markers", marker={"opacity": 0}, showlegend=False,
                           visible=(i == 0), hoverinfo="skip"), i, j)
            if limits is None or not len(limits):
                continue
            lim = limits[(limits[menu] == m) & (limits.stat == s) & limits[y].isin(cats)]
            span = max([abs(x) for x in dm["d_" + s].dropna()] + [abs(x) for x in lim.lo.tolist() + lim.hi.tolist()
                                                                  if abs(x) != INF] + [1]) * 1.08
            for r in lim.itertuples():
                lo, hi = max(r.lo, -span), min(r.hi, span)
                add(go.Scatter(x=[lo, hi], y=[getattr(r, y)] * 2, mode="lines+markers",
                               line={"color": "rgba(80,80,80,0.30)", "width": 12},
                               marker={"symbol": "line-ns", "size": [16 if abs(r.lo) != INF else 0,
                                                                     16 if abs(r.hi) != INF else 0],
                                       "line": {"color": "#555", "width": 2}},
                               name="limit of a check", legendgroup=f"{m} / limit",
                               showlegend=not any(t.legendgroup == f"{m} / limit" for t in fig.data),
                               visible=(i == 0),
                               hovertemplate=f"{r.check}: {r.expect}<extra>limit of a check</extra>"), i, j)
    if len(menus) > 1:
        fig.update_layout(updatemenus=[{"buttons": [{"label": METRIC_NAMES.get(m, m), "method": "update",
                                                     "args": [{"visible": [o == i for o in owner]}]}
                                                    for i, m in enumerate(menus)],
                                        "x": 1.0, "xanchor": "right", "y": 1.0, "yanchor": "bottom",
                                        "pad": {"b": 34}}])
    style(fig, title, "", "", height=max(380, 230 + 34 * len(cats)), barmode="overlay", margin={"t": 130})
    fig.update_xaxes(zeroline=True, zerolinecolor="#6b6a64", zerolinewidth=1.5, title_text="cycles")
    fig.update_yaxes(categoryorder="array", categoryarray=cats, autorange="reversed")
    return fig


def diff_table(d, y="point", stats=DIFF_STATS):
    """The differences of diff_fig as a table: one row per category of y, one column per metric and statistic
    (cycles, rounded)."""
    d = d[~d["reference"]] if "reference" in d else d
    long = d.melt(id_vars=[y, "metric"], value_vars=[f"d_{s}" for s in stats], var_name="stat", value_name="diff")
    long["stat"] = long["stat"].str[2:]
    t = long.pivot_table(index=y, columns=["metric", "stat"], values="diff", aggfunc="first", sort=False)
    cols = [(m, s) for m in metric_order(long.metric) for s in stats if (m, s) in t.columns]
    return t[cols].round(0).astype("Int64")


# ------------------------------------------------------------------ modes
def modes(h, coarse=False):
    """[(first value, last value, share of the samples)] of the modes of a histogram, fastest first. The modes of
    the checks (studylib.stats.modes, check-forms.rst): groups of fine bins that each hold >= 0.1 % of the
    samples, at most 2 cycles apart. coarse=True: the same rule over the fine and the coarse bins (a coarse
    bin is one bin, its mode spans the whole bin); no check reads this view."""
    if not coarse:
        return [(a, b, c / h["n"]) for a, b, c in _stats.modes(h)]
    out = []
    for v, c, w in sorted([(v, c, 1) for v, c in h["bins"]] + [tuple(x) for x in h["coarse"]]):
        if c < _stats.MODE_MIN_SHARE * h["n"]:
            continue
        if out and v - out[-1][1] <= _stats.MODE_GAP:
            out[-1][1] = v + w - 1
            out[-1][2] += c
        else:
            out.append([v, v + w - 1, c])
    return [(a, b, c / h["n"]) for a, b, c in out]


def _span(a, b):
    return str(a) if a == b else f"{a}..{b}"


def mode_table(inst, experiments, metric, points=None, max_modes=3, coarse=False):
    """One row per evidence point (index experiment, point; only the points named in points, if given): the
    number of modes, the first to the last mode (cycles), the values and the share of the first max_modes modes,
    as the checks count them (modes). coarse=True adds the same columns for the view with the coarse bins, named
    "... with coarse bins"."""
    views = [("", False)] + ([(" with coarse bins", True)] if coarse else [])
    cols = ["experiment", "point"]
    for suffix, _ in views:
        cols += [f"modes{suffix}", f"first to last mode{suffix} (cycles)"]
        cols += [f"{c} {k}{suffix}" for k in range(1, max_modes + 1) for c in ("mode", "share")]
    rows = []
    for exp in experiments:
        for _, _, point, rep in inst.points(exp):
            if points is not None and point not in points:
                continue
            row = {"experiment": exp, "point": point}
            for suffix, view in views:
                ms = modes(rep["hists"][metric], coarse=view)
                row[f"modes{suffix}"] = len(ms)
                row[f"first to last mode{suffix} (cycles)"] = ms[-1][0] - ms[0][0] if ms else None
                for k, (a, b, s) in enumerate(ms[:max_modes], 1):
                    row[f"mode {k}{suffix}"] = _span(a, b)
                    row[f"share {k}{suffix}"] = round(s, 4)
            rows.append(row)
    t = pd.DataFrame(rows, columns=cols).set_index(["experiment", "point"])
    # a column that no point has (fewer modes than max_modes everywhere) is left out
    return t.dropna(axis=1, how="all")


def mode_range(series, metric, pad=20, coarse=False):
    """(lo, hi): an x range around the modes of all series ({label: hists}) for hist, pad cycles wider; None
    if no series has a mode."""
    ms = [m for hists in series.values() for m in modes(hists[metric], coarse=coarse)]
    return (min(a for a, _, _ in ms) - pad, max(b for _, b, _ in ms) + pad) if ms else None


def tails(df, title, x="phase"):
    """Each row of inst.tails() as a dot: x the tick phase of its stimulus (or another column), y its latency,
    the colour its cause (tails.CAUSES order), the symbol its point. The hover gives the labels, the function of
    the interrupted code and the sample number."""
    from probatrix.benchmarks import tails as tailmod
    fig = go.Figure()
    points = list(dict.fromkeys(df.point)) if len(df) else []
    for i, c in enumerate(tailmod.CAUSES):
        for k, p in enumerate(points):
            sub = df[(df.cause == c) & (df.point == p)]
            if sub.empty:
                continue
            name = c if len(points) == 1 else f"{p} {c}"
            text = [f"{m} #{s}: {lab or '-'}; {f or '-'}" for m, s, lab, f in
                    zip(sub.metric, sub.seq, sub.labels, sub.function)]
            fig.add_trace(go.Scatter(x=sub[x], y=sub.lat, mode="markers", name=name, text=text,
                                     marker={"color": color(i), "size": 9, "symbol": SYMBOLS[k % len(SYMBOLS)],
                                             "line": {"color": "#fcfcfb", "width": 1}},
                                     hovertemplate="%{text}<br>" + x + " %{x}, %{y} cycles<extra>" + name + "</extra>"))
    return style(fig, title, "tick phase of the stimulus (cycles)" if x == "phase" else x, "latency (cycles)")
