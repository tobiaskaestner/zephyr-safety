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

import trees

from . import layout
from .seal import file_sha256


class DesignError(Exception):
    pass


def repo_rel(path):
    """A path relative to the safety repo, if it is in the repo."""
    path = Path(path)
    return str(path.relative_to(trees.REPO_DIR)) if path.is_relative_to(trees.REPO_DIR) else str(path)


def repo_rev(repo=trees.REPO_DIR):
    """(rev, dirty) of the safety repo that holds the design and the tools."""
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "validation", "scripts/benchmarks",
                                 "tests/benchmarks"], cwd=repo, capture_output=True, text=True).stdout.strip())
    return rev, dirty


class Study:
    def __init__(self, path, folder):
        self.path = path
        self.folder = folder
        self.data = yaml.safe_load((folder / "study.yaml").read_text())
        h = folder / "hypotheses.yaml"
        self.hypotheses = yaml.safe_load(h.read_text())["hypotheses"] if h.is_file() else []
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
        self.data = yaml.safe_load((folder / "experiment.yaml").read_text())
        self.name = self.data["name"]
        self.acceptance = list(self.data.get("acceptance") or [])

    def file_ref(self):
        f = self.folder / "experiment.yaml"
        return {"file": repo_rel(f), "sha256": file_sha256(f)}


class Design:
    """All studies and experiments of the design tree."""

    def __init__(self, root=trees.STUDIES_DIR):
        self.root = Path(root)
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

    def experiment(self, name):
        try:
            return self.experiments[name]
        except KeyError:
            raise DesignError(f"no experiment {name!r}") from None

    @property
    def top(self):
        return self.studies[""]
