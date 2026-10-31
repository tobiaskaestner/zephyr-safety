# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The Project: where the design and the tools of a safety repo are.

One Project holds the generic folders and names that the engine needs: the repo, the
design roots, the prefixes of the folders (ex-, st-), the name of the kind that a design
without a "kind:" key has, and the paths whose changes make a build "dirty". Whatever
belongs to one kind of study (the folder of the benchmark apps, the tree manifests, the
prefixes of file formats and git refs, its own dirt paths) is in the Kind object of that
kind (kinds.py; benchmarks/kind.py), not here.

Design roots: a repo can have more than one (validation/empirical/latencies,
validation/formal/...). The Project holds a tuple of Root(path, kind). A root is the folder
of one top study; its kind (a name, or None for the default kind of the Project) is what a
design below it has when no design file names a kind. So the kind is found from the design
file first, then its parents, then the root, then Project.default_kind (kinds.kind_of).
design_root is the first root: the one that the tools use when the user gives no other.

The default Project is made from the place of this package: the repo is the folder above
scripts/. To use another one, call set_project(Project.at(repo)) or use(project) (a context
manager, for tests). Code that needs a folder asks project(); it does not keep a copy.
"""

import contextlib
from dataclasses import dataclass, field, replace
from pathlib import Path

# parents: core, probatrix, scripts, then the repo
_REPO = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Root:
    """The folder of a top study and the name of its kind (None: Project.default_kind)."""
    path: Path
    kind: str = None


@dataclass(frozen=True)
class Project:
    repo: Path
    roots: tuple
    default_kind: str = "latbench"         # the kind of a design that names none (the only place)
    experiment_file: str = "experiment.yaml"
    experiment_prefix: str = "ex-"
    study_prefix: str = "st-"
    dirt_paths: tuple = field(default=("validation", "scripts/probatrix"))

    @property
    def design_root(self):
        """The first design root (the one the tools use by default)."""
        return self.roots[0].path

    @classmethod
    def at(cls, repo, design_root=None, **override):
        """The Project of a safety repo with the usual layout. Any field can be given instead
        (design_root: the path of the one root)."""
        repo = Path(repo)
        values = dict(repo=repo, roots=(Root(design_root or repo / "validation" / "empirical" / "latencies"),))
        values.update(override)
        return cls(**values)

    @classmethod
    def default(cls):
        """The Project of the repo that holds this package."""
        return cls.at(_REPO)

    def with_(self, design_root=None, **changes):
        """A copy with other values (design_root: a new path for the first root)."""
        if design_root is not None:
            changes["roots"] = (replace(self.roots[0], path=Path(design_root)), *self.roots[1:])
        return replace(self, **changes)

    def root_of(self, path):
        """The Root that holds path (the longest match), or None."""
        path = Path(path).resolve()
        hits = [r for r in self.roots if path == r.path.resolve() or r.path.resolve() in path.parents]
        return max(hits, key=lambda r: len(r.path.parts), default=None)


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
