# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Load a built study instance for a notebook (needs pandas).

    import data
    inst = data.load_instance("/wrk/z/lab-benchmarks/results/kernel-latency/st-.../st-...@nucleo_g474re")
    inst.hypotheses()            one row per hypothesis
    inst.checks()                one row per check, with the basis from the design
    inst.central()               one row per sentence of a central result
    inst.rows("wake-stim-seed-1m")    the rows of experiment.json (percentiles per run, tree, point, metric),
                                      with a column value.<axis> for each axis that has numbers
    inst.axis_values("wake-timers-1m")   {axis: {label: value}} from the design of the experiment
    inst.points("wake-stim-seed-1m")  the points of the evidence runs: app data of rep 1
    inst.meta("wake-clock-drift")     one row per point with its LAT META values
    inst.hist(point, "irq", "wake-stim-seed-1m")
    data.ccdf(hist)              (x, share of samples >= x)

An experiment of another instance (an import) or a reference run is found
in the results tree by its name and run id.
"""

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import trees  # noqa: E402
from studylib import layout  # noqa: E402


def _load(path):
    return json.loads(Path(path).read_text())


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


class Instance:
    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        self.root = layout.find_root(self.folder)
        self.study = _load(self.folder / "study.json")
        self.instance = _load(self.folder / "instance.json")
        self.design_folder = trees.REPO_DIR / self.study["design"]["folder"]
        h = self.design_folder / "hypotheses.yaml"
        self.design_hypotheses = {x["id"]: x for x in yaml.safe_load(h.read_text())["hypotheses"]} if h.is_file() else {}

    # ------------------------------------------------------------ tables
    def hypotheses(self):
        import pandas as pd
        return pd.DataFrame([{"id": h["id"], "type": h["type"], "claim": h["statement"], "verdict": h["verdict"],
                              "provisional": bool(h.get("provisional")),
                              "checks confirmed": h["checks_confirmed"]} for h in self.study["hypotheses"]])

    def checks(self):
        import pandas as pd
        rows = []
        for h in self.study["hypotheses"]:
            design = {c["id"]: c for c in self.design_hypotheses.get(h["id"], {}).get("checks", [])}
            for c in h["checks"]:
                rows.append({"check": f"{h['id']} {c['id']}", "verdict": c["verdict"], "by": c.get("by"),
                             "measured": c.get("measured"), "limit": c.get("limit"),
                             "provisional": c.get("provisional"),
                             "basis": " ".join(design.get(c["id"], {}).get("basis", "").split())})
        return pd.DataFrame(rows)

    def central(self):
        import pandas as pd
        rows = []
        for c in self.study["central_results"]:
            if c.get("not_evaluated"):
                rows.append({"id": c["id"], "result": f"(not evaluated: {c['not_evaluated']})", "by": c.get("by")})
            for t in c.get("texts", []):
                rows.append({"id": c["id"], "result": t, "by": c.get("by")})
        return pd.DataFrame(rows)

    def rows(self, experiment):
        import pandas as pd
        ej = self.experiment_json(experiment)
        df = pd.DataFrame(ej["rows"], columns=ej["columns"])
        for axis, values in self.axis_values(experiment).items():
            if f"axis.{axis}" in df and values:
                df[f"value.{axis}"] = df[f"axis.{axis}"].map(values)
        return df

    def axis_values(self, experiment):
        """{axis: {label: value}}: the "value:" of each axis label in the design of the experiment."""
        f = trees.REPO_DIR / self.experiment_json(experiment)["design"]["file"]
        if not f.is_file():
            return {}
        axes = (yaml.safe_load(f.read_text()) or {}).get("axes") or {}
        return {a: {k: v["value"] for k, v in (labels or {}).items() if isinstance(v, dict) and "value" in v}
                for a, labels in axes.items()}

    # ------------------------------------------------------------ data
    def experiment_json(self, experiment):
        return _load(self.experiment_folder(experiment) / "experiment.json")

    def experiment_folder(self, experiment):
        """The folder of an experiment of this instance, or of the instance that owns it."""
        own = self.folder / f"{layout.EXPERIMENT_PREFIX}{experiment}"
        if (own / "experiment.json").is_file():
            return own
        for f in layout.instance_folders(self.root):
            p = f / f"{layout.EXPERIMENT_PREFIX}{experiment}" / "experiment.json"
            if p.is_file() and _load(f / "instance.json").get("board", None) in (None, self.board):
                return p.parent
        raise FileNotFoundError(f"no built experiment {experiment} in {self.root}")

    @property
    def board(self):
        return self.study.get("board")

    def app_data(self, run_id):
        """The app data of a run of the results tree, by run id <experiment>/<UTC>."""
        exp, utc = run_id.split("/")
        for f in layout.instance_folders(self.root):
            folder = f / f"{layout.EXPERIMENT_PREFIX}{exp}"
            if (folder / utc).is_dir():
                app = [p for p in folder.glob(f"{utc}.*.json") if not p.name.endswith(".run.json")]
                if app:
                    return _load(app[0])
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

    def hist(self, point, metric, experiment, tree=None, run_id=None):
        for rid, t, p, rep in (self.points(experiment) if run_id is None else
                               [(run_id, x["tree"], x["point"], x["reps"][0]) for x in self.app_data(run_id)["points"]]):
            if p == point and (tree is None or t == tree):
                return rep["hists"][metric]
        raise KeyError(f"no point {point} of {experiment or run_id}")


def load_instance(folder):
    return Instance(folder)
