# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Load a built study instance for a notebook (needs pandas): the generic part.

An Instance reads the files that every kind writes: study.json, instance.json and the
experiment.json of each experiment. A kind adds its own tables in a subclass (see
probatrix.benchmarks.data for the latency tables).

    inst = data.load_instance(folder)
    inst.hypotheses()            one row per hypothesis
    inst.checks()                one row per check, with the basis from the design
    inst.central()               one row per sentence of a central result
    inst.experiment_json(name)   the experiment.json of an experiment of this instance or of the instance that owns it

pandas is imported in the table methods only. The module needs no pandas to import.
"""

import json
from pathlib import Path

import yaml

from probatrix.core import config, layout


def load_json(path):
    return json.loads(Path(path).read_text())


class Instance:
    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        self.root = layout.find_root(self.folder)
        self.study = load_json(self.folder / "study.json")
        self.instance = load_json(self.folder / "instance.json")
        self.design_folder = config.project().repo / self.study["design"]["folder"]
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

    def experiment_json(self, experiment):
        return load_json(self.experiment_folder(experiment) / "experiment.json")

    def experiment_folder(self, experiment):
        """The folder of an experiment of this instance, or of the instance that owns it."""
        own = self.folder / f"{layout.EXPERIMENT_PREFIX}{experiment}"
        if (own / "experiment.json").is_file():
            return own
        for f in layout.instance_folders(self.root):
            p = f / f"{layout.EXPERIMENT_PREFIX}{experiment}" / "experiment.json"
            if p.is_file() and load_json(f / "instance.json").get("board", None) in (None, self.board):
                return p.parent
        raise FileNotFoundError(f"no built experiment {experiment} in {self.root}")

    @property
    def board(self):
        """The value of the instance axis ("board" in study.json), or None for a kind without an axis."""
        return self.study.get("board")


def load_instance(folder):
    return Instance(folder)
