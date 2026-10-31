# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The kinds of study: the Kind interface, the registry and kind_of().

A kind is the part of probatrix that knows one sort of evidence (latency benchmarks, a TLA+
model check, ...). The engine in core/ calls only the hooks below. A kind is a Python object
with these attributes and methods; it need not inherit from Kind (Kind is a Protocol, for the
type checker and for the docstrings). A hook that a kind does not need can be left out
(`hasattr`) or return the empty value that the docstring names.

    register(kind)            make a kind known (by kind.name)
    get(name)                 the kind with this name (KindError if there is none)
    names()                   the names of all kinds
    kind_of(design, *parents) the kind of a study or an experiment

How the registry is filled: a kind module calls register() when it is imported
(probatrix/benchmarks/kind.py does, and probatrix.benchmarks imports it). core/ must not
import a kind. So get() and names() load the modules that PLUGINS lists, by name, with
importlib, when they need a kind that is not registered yet. PLUGINS is the one place that
names kind modules. Later (PyPI) the same list comes from the entry-point group
"probatrix.kinds"; get() does not change.
"""

import importlib
from typing import Any, Protocol

from probatrix.core import config

# name of a kind -> the module that registers it (loaded on the first get() of an unknown name)
PLUGINS = {"latbench": "probatrix.benchmarks.kind"}


class KindError(Exception):
    """An unknown kind."""


class Kind(Protocol):
    """What the engine needs from a kind. The hooks are listed in the order of the plan
    (claude/kernel-unit/studies/study-framework-design.md, 2.1)."""

    name: str
    """The name that a design file gives with `kind:` ("latbench")."""

    # 1. schemas, names -------------------------------------------------------------
    schema_prefix: str
    """The $id prefix of the schema files of this kind ("latbench": ids latbench/<name>.schema.yaml)."""
    schema_folder: Any
    """The folder (a Path) with the <name>.schema.yaml files. Registered with core.schema."""
    format_prefix: str
    """The prefix of the file format ids: format_id("run", 2) -> "<prefix>-run/2"."""
    ref_prefix: str
    """The prefix of the git refs: ref("run", a, b) -> "<prefix>/run/a/b"."""
    dirt_paths: tuple
    """Paths below the repo (besides Project.dirt_paths) whose changes make made_by.dirty true."""

    def format_id(self, name: str, version: int) -> str:
        """The id of a file format of this kind, e.g. "latbench-study/2"."""

    def ref(self, *parts) -> str:
        """A git ref below ref_prefix, e.g. "refs/latbench/run/<exp>/<id>"."""

    # 2. points ---------------------------------------------------------------------
    def points(self, experiment: dict) -> list:
        """The points of an experiment: a list of dicts, each with the key "id" and the values of
        its axes. The order is the order of the design. It raises SystemExit("error: ...") if
        the experiment file has an error (the contract of today's run.expand_points). Benchmarks:
        the Kconfig expansion of the experiment. A kind with a list file reads the lines of the file.
        The experiment is the parsed experiment.yaml (the dict that design.Experiment holds)."""

    # 3. adapters: derived files of a raw run ---------------------------------------
    def run_json(self, run_dir, run_id, digest, made_by, experiment_file) -> dict:
        """The run.json data (format, run, points, ...) that is made from a raw run folder, as a dict
        that jsonout can write. Same arguments as runfiles.run_json."""

    def app_json(self, run_dir, app, run_id, digest, made_by) -> dict:
        """The data of the extractor of the app of a run, as a dict (format "<prefix>-app-<app>/1").
        Same arguments as runfiles.app_json."""

    # 4. the metric provider --------------------------------------------------------
    # rep is one repetition of a point as build.py reads it: a dict with the keys hists, meta, m4,
    # tails (as the run data has them). metric is a name ("<hist>", "meta.<key>", "m4.mask...",
    # "tail.<hist>") or None (a value of the whole point, e.g. the clock drift). stat is the
    # name of the statistic ("p99", "max", "n", "count_ge(100)", "drift_ppm", ...) or None.
    def value(self, rep: dict, metric: str | None, stat: str | None) -> float:
        """The value of metric and stat for one repetition. It raises core.errors.NoValue (with the
        reason) if the point has no such value or the tools have none."""

    def known(self, metric: str | None, stat: str | list | None) -> bool:
        """Whether the tools have a value for metric and stat (stat can be a list: all must be known).
        It never raises; lint uses it to find checks that no tool can evaluate."""

    def width(self, rep: dict, metric: str | None, stat: str | None) -> int:
        """The width of the interval that holds the exact value, in the unit of the value (a
        histogram quantile is only known to its bin: width of the bin; an exact value: 1)."""

    def seen(self, rep: dict, metric: str | None) -> bool:
        """Whether the repetition can have a value for metric at all (benchmarks: an M4 metric
        with [function] needs a site with that function). True if the kind has no such rule."""

    # 5. extra check forms ----------------------------------------------------------
    def extra_forms(self) -> dict:
        """{form name: function} of the check forms that only this kind has (benchmarks: the
        bin-aware range, within and tolerance_bins, hist_identical_to). The function takes
        (result, label, points, metric, stat, expect, source, series) like today's
        checks.within_check and adds to the result. {} if there are none. R5a: still {}; the code
        moves with checks.py in R5b."""

    # 6. generated checks -----------------------------------------------------------
    def generated_checks(self, experiment: dict) -> list:
        """Checks that come from a file, as a list of check dicts (same keys as a check in
        hypotheses.yaml). [] for the benchmarks."""

    # 7. instance axis --------------------------------------------------------------
    instance_axis: Any
    """None if the instances of this kind have no axis. Otherwise an object with:
         strip(instance_path) -> study path       "st-a@board/st-b" -> "a/b" (names without the axis)
         suffix(instance_path) -> str             the axis value in the path ('' if none)
         folder_name(study_name, value, prefix="") -> str    the folder name of a study that fixes the axis
         of(folder) -> value or None              the axis value an instance folder (or a parent) fixes
         lock_key(value) -> str                   the file-name part of the lock of this value"""

    # 8. commands -------------------------------------------------------------------
    def commands(self) -> dict:
        """{command name: function} of CLI subcommands that only this kind has. {} if none.
        R5a: still {}; study.py keeps its own for now."""


_KINDS = {}


def register(kind):
    """Make a kind known by kind.name (the same object twice is fine; another object is an error)."""
    old = _KINDS.get(kind.name)
    if old is not None and old is not kind:
        raise KindError(f"kind {kind.name!r} is already registered")
    _KINDS[kind.name] = kind
    return kind


def get(name):
    """The kind with this name. A kind that PLUGINS lists is imported on the first call."""
    if name not in _KINDS and name in PLUGINS:
        importlib.import_module(PLUGINS[name])
    if name not in _KINDS:
        raise KindError(f"unknown kind {name!r} (known: {', '.join(names()) or 'none'})")
    return _KINDS[name]


def names():
    """The names of all kinds (the kinds of PLUGINS are loaded first)."""
    for name in PLUGINS:
        get(name)
    return list(_KINDS)


def kind_of(design, *parents):
    """The kind of a study or an experiment.

    design is the parsed design file (a dict) or an object with that dict as .data. Order of
    the answer: the "kind" key of design, then of each of parents (nearest first: the parent
    study, its parent, ...), then the kind of the design root (pass the Root as the last
    parent, or None), then Project.default_kind. A name that no kind has is a KindError."""
    chain = [*parents]
    for item in [design, *chain]:
        if isinstance(item, config.Root):
            name = item.kind
        else:
            data = getattr(item, "data", item)
            name = data.get("kind") if isinstance(data, dict) else None
        if name:
            return get(name)
    return get(config.project().default_kind)


def dirt_paths():
    """The paths whose changes make a build dirty: the Project's and those of all kinds."""
    out = list(config.project().dirt_paths)
    for name in names():
        out += [p for p in get(name).dirt_paths if p not in out]
    return tuple(out)
