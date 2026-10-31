# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Load a built study instance for a notebook (needs pandas): the latency tables.

Instance adds to probatrix.core.data.Instance (hypotheses, checks, central, experiment_json).

    from probatrix.benchmarks import data
    inst = data.load_instance("/wrk/z/lab-benchmarks/results/kernel-latency/st-.../st-...@nucleo_g474re")
    inst.hypotheses()            one row per hypothesis
    inst.checks()                one row per check, with the basis from the design
    inst.central()               one row per sentence of a central result
    inst.rows("wake-stim-seed-1m")    the rows of experiment.json (percentiles per run, tree, point, metric),
                                      with a column value.<axis> for each axis that has numbers and
                                      the core clock core_hz of each point
    inst.axis_values("wake-timers-1m")   {axis: {label: value}} from the design of the experiment
    inst.points("wake-stim-seed-1m")  the points of the evidence runs: app data of rep 1
    inst.meta("wake-clock-drift")     one row per point with its LAT META values
    inst.drift(["wake-clock-drift"])  one row per point: the clock drift in ppm and in cycles per sample
    inst.sites("wake-m4-validate")    one row per M4 site of each point, with max_net
    inst.hist(point, "irq", "wake-stim-seed-1m")
    inst.tails("irq-witness-check-1m")  one row per witness row (LATBENCH_TAIL) with its labels and cause
    inst.tail_causes("irq-witness-check-1m")   the count of each cause per point and table
    data.ccdf(hist)              (x, share of samples >= x)

An experiment of another instance (an import) or a reference run is found
in the results tree by its name and run id.
"""

import yaml

from probatrix.benchmarks import tails as tailmod  # noqa: E402
from probatrix.benchmarks.studylib import stats  # noqa: E402
from probatrix.core import config  # noqa: E402
from probatrix.core import data as coredata
from probatrix.core import layout
from probatrix.core.data import load_json as _load


# The columns of Instance.tails.
TAIL_COLUMNS = ["run", "tree", "point", "metric", "seq", "lat", "aux", "phase", "win", "exc", "extra_exc",
                "systick_age", "tmr", "wake", "pc", "function", "labels", "cause"]

# The columns of Instance.sites.
SITE_COLUMNS = ["tree", "point", "kind", "exc", "ctx", "function", "place", "via", "n", "min", "max", "max_net"]


def ccdf(h):
    """(x, share of the samples >= x) at the lower edge of each non-empty bin of a histogram."""
    edges = sorted([(v, c) for v, c in h["bins"]] + [(v, c) for v, c, _ in h["coarse"]]
                   + [(1 << e, c) for e, c in h["ovf_log2"]])
    n = h["n"]
    xs, ys, above = [], [], n
    for v, c in edges:
        xs.append(v)
        ys.append(above / n)
        above -= c
    return xs, ys


class Instance(coredata.Instance):
    def __init__(self, folder):
        super().__init__(folder)
        self._app_data = {}

    def rows(self, experiment):
        import pandas as pd
        ej = self.experiment_json(experiment)
        df = pd.DataFrame(ej["rows"], columns=ej["columns"])
        for axis, values in self.axis_values(experiment).items():
            if f"axis.{axis}" in df and values:
                df[f"value.{axis}"] = df[f"axis.{axis}"].map(values)
        clock = self._core_hz(df.run.unique() if "run" in df else [])
        default = ej.get("core_hz")
        df["core_hz"] = [clock.get(k, default) for k in zip(df.get("run", []), df.get("tree", []), df.get("point", []),
                                                           df.get("rep", []))]
        return df

    def _core_hz(self, run_ids):
        """{(run, tree, point, rep): LAT META core_hz} of the runs (a run without app data gives nothing)."""
        out = {}
        for rid in run_ids:
            try:
                app = self.app_data(rid)
            except FileNotFoundError:
                continue
            for p in app["points"]:
                for i, rep in enumerate(p["reps"], 1):
                    if isinstance(rep["meta"].get("core_hz"), (int, float)):
                        out[(rid, p["tree"], p["point"], i)] = rep["meta"]["core_hz"]
        return out

    def axis_values(self, experiment):
        """{axis: {label: value}}: the "value:" of each axis label in the design of the experiment."""
        f = config.project().repo / self.experiment_json(experiment)["design"]["file"]
        if not f.is_file():
            return {}
        axes = (yaml.safe_load(f.read_text()) or {}).get("axes") or {}
        return {a: {k: v["value"] for k, v in (labels or {}).items() if isinstance(v, dict) and "value" in v}
                for a, labels in axes.items()}

    def app_data(self, run_id):
        """The app data of a run of the results tree, by run id <experiment>/<UTC> (read once, then kept)."""
        if run_id in self._app_data:
            return self._app_data[run_id]
        exp, utc = run_id.split("/")
        for f in layout.instance_folders(self.root):
            folder = f / f"{layout.EXPERIMENT_PREFIX}{exp}"
            if (folder / utc).is_dir():
                app = [p for p in folder.glob(f"{utc}.*.json") if not p.name.endswith(".run.json")]
                if app:
                    self._app_data[run_id] = _load(app[0])
                    return self._app_data[run_id]
        raise FileNotFoundError(f"no app data of {run_id} (build the instance of the run)")

    def points(self, experiment, roles=("evidence",)):
        """[(run id, tree, point, rep 1 of the app data)] of the runs of an experiment."""
        ej = self.experiment_json(experiment)
        out = []
        for r in ej["runs"]:
            if r["role"] not in roles or r.get("excluded_by_acceptance"):
                continue
            for p in self.app_data(r["id"])["points"]:
                if p["reps"]:
                    out.append((r["id"], p["tree"], p["point"], p["reps"][0]))
        return out

    def meta(self, experiment):
        """One row per evidence point: run, tree, point and the LAT META values of rep 1."""
        import pandas as pd
        return pd.DataFrame([{"run": r, "tree": t, "point": p, **rep["meta"]} for r, t, p, rep in self.points(experiment)])

    def drift(self, experiments):
        """One row per evidence point of the experiments: experiment, the LAT META values, drift_ppm and
        drift_per_sample (stats.value: clock_drift_cyc / clock_elapsed_cyc x 1e6 and clock_drift_cyc / samples,
        the values that the checks read). A value that the data do not give is NaN."""
        import pandas as pd

        def value(rep, stat):
            try:
                return stats.value(rep, None, stat)
            except stats.NoValue:
                return float("nan")

        rows = [{"experiment": e, "run": r, "tree": t, "point": p, **rep["meta"],
                 "drift_ppm": value(rep, "drift_ppm"), "drift_per_sample": value(rep, "drift_per_wake")}
                for e in experiments for r, t, p, rep in self.points(e)]
        return pd.DataFrame(rows, columns=None if rows else ["experiment", "run", "tree", "point", "samples",
                                                             "clock_drift_cyc", "clock_elapsed_cyc", "drift_ppm",
                                                             "drift_per_sample"])

    def sites(self, experiment):
        """One row per M4 site of each evidence point. exc: the exception number at the start (t: a thread).
        max_net: the max minus the floor of the calibration of the same log, read with stats.value as the checks
        read it (None for a site without a section)."""
        import pandas as pd
        out = []
        for _, tree, point, rep in self.points(experiment):
            m4 = rep.get("m4") or {}
            for s in m4.get("sites", []):
                # stats.value of a set with this one site gives the value of the site
                one = {**rep, "m4": {**m4, "sites": [s]}}
                out.append({"tree": tree, "point": point, "kind": s["kind"], "exc": s["name"].split(".")[2],
                            "ctx": s["ctx"], "function": s.get("function"), "place": s.get("place"),
                            "via": s.get("via"), "n": s["n"], "min": s["min"], "max": s["max"],
                            "max_net": stats.value(one, f"m4.{s['kind']}", "max_net") if s["n"] else None})
        return pd.DataFrame(out, columns=SITE_COLUMNS)

    def tails(self, experiment, metric=None, at_least=0):
        """One row per witness row of the evidence points (LATBENCH_TAIL), largest first in each table:
        the fields of the row, extra_exc (exc - exc_min of the table), systick_age (counts from the last
        SysTick reload to the end, None without a jump), the function of pc, the labels and the cause
        (tails.py). metric: only this table. at_least: only rows with lat >= at_least."""
        import pandas as pd
        out = []
        for rid, tree, point, rep in self.points(experiment):
            for name, t in (rep.get("tails") or {}).items():
                if metric is not None and name != metric:
                    continue
                for r in tailmod.rows(t, rep["meta"], at_least):
                    n = tailmod.norm(r)
                    out.append({"run": rid, "tree": tree, "point": point, "metric": name,
                                **{k: n.get(k) for k in ("seq", "lat", "aux", "phase", "win", "exc", "tmr", "wake")},
                                "extra_exc": r["extra_exc"], "systick_age": tailmod.systick_age(n, rep["meta"]),
                                "pc": r.get("pc"), "function": r.get("function"),
                                "labels": " ".join(r["labels"]), "cause": r["cause"]})
        return pd.DataFrame(out, columns=TAIL_COLUMNS)

    def tail_causes(self, experiment, metric=None, at_least=0):
        """The count of each cause per point and table (columns: the causes of tails.CAUSES)."""
        df = self.tails(experiment, metric, at_least)
        if df.empty:
            return df
        out = df.groupby(["tree", "point", "metric", "cause"]).size().unstack("cause", fill_value=0)
        return out.reindex(columns=[c for c in tailmod.CAUSES if c in out.columns]).reset_index()

    def hist(self, point, metric, experiment, tree=None, run_id=None):
        for rid, t, p, rep in (self.points(experiment) if run_id is None else
                               [(run_id, x["tree"], x["point"], x["reps"][0]) for x in self.app_data(run_id)["points"]]):
            if p == point and (tree is None or t == tree):
                return rep["hists"][metric]
        raise KeyError(f"no point {point} of {experiment or run_id}")


def load_instance(folder):
    return Instance(folder)
