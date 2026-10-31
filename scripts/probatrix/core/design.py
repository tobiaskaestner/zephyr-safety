# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The design tree below validation/empirical/latencies.

A folder with study.yaml is a study (st-<name>, the top study is the
root), a folder with experiment.yaml is an experiment (ex-<name>). A study
can have hypotheses.yaml and report.ipynb. Studies refer to each other by
study path and to experiments by name.
"""

import subprocess
from pathlib import Path

import yaml

from probatrix.core import config, kinds, layout, schema
from probatrix.core.seal import file_sha256


from probatrix.core.errors import DesignError  # noqa: F401  (design.DesignError)


def load(kind, path):
    """A design file, checked against its schema; DesignError at the first violation."""
    data = yaml.safe_load(path.read_text())
    try:
        return schema.check(kind, data, path)
    except schema.SchemaError as e:
        raise DesignError(str(e)) from None


def repo_rel(path):
    """A path relative to the safety repo, if it is in the repo."""
    path = Path(path)
    repo = config.project().repo
    return str(path.relative_to(repo)) if path.is_relative_to(repo) else str(path)


def repo_rev(repo=None, kind=None):
    """(rev, dirty) of the safety repo that holds the design and the tools. A change below the dirt paths
    of the Project or of the kind of the design (default: the Project's default kind) makes it dirty;
    a change below the paths of another kind does not."""
    project = config.project()
    repo = project.repo if repo is None else repo
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", *kinds.dirt_paths(kind)],
                                cwd=repo, capture_output=True, text=True).stdout.strip())
    return rev, dirty


class Study:
    def __init__(self, path, folder):
        self.path = path
        self.folder = folder
        self.data = load("study", folder / "study.yaml")
        h = folder / "hypotheses.yaml"
        self.hypotheses = load("hypotheses", h)["hypotheses"] if h.is_file() else []
        self.experiments = list(self.data.get("experiments") or [])
        self.imports = list(self.data.get("imports") or [])
        self.central_results = list(self.data.get("central_results") or [])
        self.substudies = []
        for s in self.data.get("substudies") or []:
            name = s["use"] if isinstance(s, dict) else s
            self.substudies.append(f"{path}/{name}" if path else name)

    @property
    def name(self):
        return self.data["name"]

    def files(self):
        """The design files of the study with their sha256 (study.yaml, hypotheses.yaml)."""
        return {f.name: file_sha256(f) for f in (self.folder / "study.yaml", self.folder / "hypotheses.yaml")
                if f.is_file()}

    def readable(self):
        """Experiments whose data the study reads: its own and the imported ones."""
        return set(self.experiments) | {i["experiment"] for i in self.imports}


class Experiment:
    def __init__(self, folder, study):
        self.folder = folder
        self.study = study
        self.data = load("experiment", folder / "experiment.yaml")
        self.name = self.data["name"]
        self.acceptance = list(self.data.get("acceptance") or [])
        rf = self.data.get("renamed_from") or []
        self.renamed_from = [rf] if isinstance(rf, str) else list(rf)

    def file_ref(self):
        f = self.folder / "experiment.yaml"
        return {"file": repo_rel(f), "sha256": file_sha256(f)}


class Design:
    """All studies and experiments of the design tree."""

    def __init__(self, root=None):
        self.root = Path(config.project().design_root if root is None else root)
        self.studies = {}
        self.experiments = {}
        self._load("", self.root)
        for path, st in self.studies.items():
            for e in st.experiments:
                folder = st.folder / (layout.EXPERIMENT_PREFIX + e)
                if not (folder / "experiment.yaml").is_file():
                    raise DesignError(f"study {path or '(top)'}: no experiment folder {folder}")
                if e in self.experiments:
                    raise DesignError(f"experiment {e}: owned by {self.experiments[e].study} and {path}")
                self.experiments[e] = Experiment(folder, path)
        # the earlier names of renamed experiments: runs, refs and imports with these names stay valid
        self.aliases = {}
        for name, e in self.experiments.items():
            for old in e.renamed_from:
                if old in self.experiments or old in self.aliases:
                    raise DesignError(f"experiment {name}: renamed_from {old!r} is the name of another "
                                      "experiment or an earlier name of one")
                self.aliases[old] = name
        for path, st in self.studies.items():
            for i in st.imports:
                owner = self.experiments.get(i["experiment"])
                if owner is None or owner.study != i["study"]:
                    raise DesignError(f"study {path}: import {i}: the study {i['study']} does not own "
                                      f"{i['experiment']}")

    def _load(self, path, folder):
        if not (folder / "study.yaml").is_file():
            raise DesignError(f"{folder}: no study.yaml")
        st = Study(path, folder)
        self.studies[path] = st
        for sub in st.substudies:
            name = sub.rsplit("/", 1)[-1]
            self._load(sub, folder / (layout.STUDY_PREFIX + name))

    def study(self, path):
        try:
            return self.studies[path]
        except KeyError:
            raise DesignError(f"no study {path!r}") from None

    def canonical(self, name):
        """The current name of an experiment (an earlier name of a renamed experiment maps to it)."""
        return self.aliases.get(name, name)

    def names(self, name):
        """The current name and the earlier names of an experiment."""
        name = self.canonical(name)
        e = self.experiments.get(name)
        return [name, *(e.renamed_from if e else [])]

    def run_experiment(self, run_id):
        """The current experiment name of a run id <experiment>/<UTC>."""
        return self.canonical(run_id.split("/")[0])

    def experiment(self, name):
        try:
            return self.experiments[self.canonical(name)]
        except KeyError:
            raise DesignError(f"no experiment {name!r}") from None

    @property
    def top(self):
        return self.studies[""]
