# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Interactive figures for the study notebooks (needs pandas and plotly).

    import data, nbfig
    inst = data.load_instance(INSTANCE)
    nbfig.intro(inst)                          the instance, the tools, the question
    nbfig.ccdf({label: hists}, "title")        CCDF, a menu selects the metric
    nbfig.hist({label: hists}, "title")        histogram (fine bins), a menu selects the metric
    nbfig.ladder(df, "title")                  the percentiles of each point, one line per series
    nbfig.sweep(df, "value.timers", "title")   a statistic over a numeric axis, one line per group
    nbfig.dots(df, "title")                    statistics per point: colour = tree, symbol = statistic
    nbfig.pivot(df, "p50")                     a table: points x metrics
    nbfig.style(fig, "title", "x", "y")        the common look for a figure of your own
    nbfig.built(inst, "wake-kconfig-1m")       False (with the reason) if the results tree has no data of it

df is a table of inst.rows(experiment) (or several of them, concatenated).
Each figure has a hover text with the value in cycles and in microseconds,
a legend (click an entry to hide the series) and zoom (drag). The colours
are a fixed order of eight colours: a series keeps its colour when a
menu changes the metric. The notebooks keep the data in tables beside the
figures, so a value is never in a colour only. The HTML of an executed
notebook loads plotly.js from its CDN (cdn.plot.ly) when it opens.
"""

import plotly.graph_objects as go
import plotly.io as pio

import data

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
}
CORE_HZ = 170_000_000


def color(i):
    return COLORS[i % len(COLORS)]


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
    common = set.intersection(*(set(h) for h in series.values())) if series else set()
    return [m for m in METRIC_NAMES if m in common] + sorted(common - set(METRIC_NAMES))


def ccdf(series, title, metrics=None, dashed=()):
    """series: {label: {metric: hist}}. The share of the samples >= x, log scale."""
    metrics = metrics or metrics_of(series)
    fig = go.Figure()
    for i, m in enumerate(metrics):
        for k, (label, hists) in enumerate(series.items()):
            x, y = data.ccdf(hists[m])
            fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line_shape="hv", name=label, legendgroup=label,
                                     showlegend=(i == 0), visible=(i == 0), customdata=[v * 1e6 / CORE_HZ for v in x],
                                     line={"color": color(k), "width": 2, "dash": "dash" if label in dashed else None},
                                     hovertemplate=_hover(label)))
    _metric_menu(fig, metrics, len(series))
    return style(fig, title, f"latency (cycles, {CORE_HZ // 1_000_000} MHz)", "share of samples >= x",
                   yaxis_type="log")


def hist(series, title, metrics=None, xrange=None):
    """series: {label: {metric: hist}}. The count of each fine bin (the coarse bins as wide bars), log y."""
    metrics = metrics or metrics_of(series)
    fig = go.Figure()
    for i, m in enumerate(metrics):
        for k, (label, hists) in enumerate(series.items()):
            h = hists[m]
            xs = [v for v, _ in h["bins"]] + [v for v, _, _ in h["coarse"]]
            ys = [c for _, c in h["bins"]] + [c / max(w, 1) for _, c, w in h["coarse"]]
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line_shape="hv", name=label, legendgroup=label,
                                     showlegend=(i == 0), visible=(i == 0), customdata=[v * 1e6 / CORE_HZ for v in xs],
                                     line={"color": color(k), "width": 2}, hovertemplate=_hover(label)))
    _metric_menu(fig, metrics, len(series))
    fig = style(fig, title, "latency (cycles)", "samples per cycle", yaxis_type="log")
    if xrange:
        fig.update_xaxes(range=list(xrange))
    return fig


def hists_of(inst, experiment, tree=None, label=None):
    """{label: hists} of the evidence points of an experiment. label(run, tree, point) names a series."""
    out = {}
    pts = inst.points(experiment)
    trees = {t for _, t, _, _ in pts}
    for run, t, point, rep in pts:
        if tree is not None and t != tree:
            continue
        name = label(run, t, point) if label else (point if len(trees) == 1 else f"{t}/{point}")
        out[name] = rep["hists"]
    return out


def ladder(df, title, stats=STATS, series="point"):
    """The percentiles of each series (log y), one line per series; a menu selects the metric."""
    metrics = [m for m in METRIC_NAMES if m in set(df.metric)] + sorted(set(df.metric) - set(METRIC_NAMES))
    groups = list(dict.fromkeys(df[series]))
    fig = go.Figure()
    for i, m in enumerate(metrics):
        for k, g in enumerate(groups):
            row = df[(df.metric == m) & (df[series] == g)]
            ys = [row[s].iloc[0] if len(row) else None for s in stats]
            fig.add_trace(go.Scatter(x=list(stats), y=ys, mode="lines+markers", name=str(g), legendgroup=str(g),
                                     showlegend=(i == 0), visible=(i == 0), marker={"size": 8},
                                     line={"color": color(k), "width": 2},
                                     customdata=[(y or 0) * 1e6 / CORE_HZ for y in ys],
                                     hovertemplate="%{x}: %{y} cycles (%{customdata:.2f} µs)<extra>" + str(g)
                                                   + "</extra>"))
    _metric_menu(fig, metrics, len(groups))
    return style(fig, title, "statistic", "latency (cycles)", yaxis_type="log")


def sweep(df, x, title, stats=("p50", "p99", "max"), group=None, log_y=False):
    """A statistic over a numeric column x, one line per group (and per statistic); a menu selects the metric."""
    metrics = [m for m in METRIC_NAMES if m in set(df.metric)] + sorted(set(df.metric) - set(METRIC_NAMES))
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
                fig.add_trace(go.Scatter(x=sub[x], y=sub[st], mode="lines+markers", name=name, legendgroup=name,
                                         showlegend=(i == 0), visible=(i == 0), marker={"size": 8},
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
    the statistic. A menu selects the metric."""
    metrics = [m for m in METRIC_NAMES if m in set(df.metric)] + sorted(set(df.metric) - set(METRIC_NAMES))
    groups = list(dict.fromkeys(df[group]))
    fig = go.Figure()
    for i, m in enumerate(metrics):
        for k, g in enumerate(groups):
            sub = df[(df.metric == m) & (df[group] == g)]
            for j, st in enumerate(stats):
                name = st if len(groups) == 1 else f"{g} {st}"
                fig.add_trace(go.Scatter(x=sub[x], y=sub[st], mode="markers", name=name, legendgroup=name,
                                         showlegend=(i == 0), visible=(i == 0), offsetgroup=name,
                                         marker={"color": color(k), "size": 10, "symbol": SYMBOLS[j % len(SYMBOLS)],
                                                 "line": {"color": "#fcfcfb", "width": 1}},
                                         customdata=[v * 1e6 / CORE_HZ for v in sub[st]],
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
