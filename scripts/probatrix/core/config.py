# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The Project: where the design and the tools of a safety repo are.

One Project holds the folders and the names that the engine needs: the repo,
the design root (the top study), the folder of the benchmark apps, the folder
of the tree manifests, the prefixes of the folders (ex-, st-), the prefix of
the file formats and of the git refs, and the paths whose changes make a
build "dirty".

The default Project is made from the place of this package: the repo is the
folder above scripts/. To use another one, call set_project(Project.at(repo))
or use(project) (a context manager, for tests). Code that needs a folder
asks project(); it does not keep a copy.
"""

import contextlib
from dataclasses import dataclass, field, replace
from pathlib import Path

# parents: core, probatrix, scripts, then the repo
_REPO = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Project:
    repo: Path
    design_root: Path
    bench_dir: Path
    trees_dir: Path
    boards_file: Path
    experiment_file: str = "experiment.yaml"
    experiment_prefix: str = "ex-"
    study_prefix: str = "st-"
    format_prefix: str = "latbench"        # latbench-study/2, latbench-run/2, ...
    ref_prefix: str = "refs/latbench"      # refs/latbench/run/..., refs/latbench/campaign/...
    dirt_paths: tuple = field(default=("validation", "scripts/probatrix", "tests/benchmarks"))

    @classmethod
    def at(cls, repo, **override):
        """The Project of a safety repo with the usual layout. Any field can be given instead."""
        repo = Path(repo)
        bench = repo / "tests" / "benchmarks"
        values = dict(repo=repo,
                      design_root=repo / "validation" / "empirical" / "latencies",
                      bench_dir=bench,
                      trees_dir=repo / "validation" / "trees",
                      boards_file=bench / "boards.yaml")
        values.update(override)
        return cls(**values)

    @classmethod
    def default(cls):
        """The Project of the repo that holds this package."""
        return cls.at(_REPO)

    def with_(self, **changes):
        """A copy with other values."""
        return replace(self, **changes)

    def format_id(self, name, version):
        """The id of a file format, e.g. "latbench-study/2"."""
        return f"{self.format_prefix}-{name}/{version}"

    def ref(self, *parts):
        """A git ref below the prefix, e.g. refs/latbench/run/<exp>/<id>."""
        return "/".join([self.ref_prefix, *map(str, parts)])


_current = None


def project():
    """The Project in use: the one of set_project()/use(), else the default one."""
    global _current
    if _current is None:
        _current = Project.default()
    return _current


def set_project(p):
    """Use p from now on (None: the default Project again)."""
    global _current
    _current = p


@contextlib.contextmanager
def use(p):
    """Use p inside a with block."""
    global _current
    old = _current
    _current = p
    try:
        yield p
    finally:
        _current = old
