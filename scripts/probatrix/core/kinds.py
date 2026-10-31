# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The kinds of study: the Kind interface, the registry and kind_of().

A kind is the part of probatrix that knows one sort of evidence (latency benchmarks, a TLA+
model check, ...). The engine in core/ calls only the hooks below. A kind is a Python object
with these attributes and methods. Kind is the Protocol (the contract, for the type checker and the
docstrings). BaseKind is the class to inherit from: it has a safe default for each optional hook, so a
new kind writes only the required ones. The core calls every hook directly (no `getattr` fallback):
a kind that does not inherit BaseKind must have all hooks.

Required (BaseKind has no default): name, schema_prefix, schema_folder, format_prefix, ref_prefix,
tool, points, run_json, app_json, value, known.
Optional (BaseKind default): dirt_paths (()), format_id, ref (from the prefixes), width (1), seen (True),
extra_forms ({}), is_point_agg (False), generated_checks ([]), instance_axis (None), experiment_json (a
generic file without data rows), plot (None), central_result (NoValue), pending ({}), commands ({}).

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
from probatrix.core.errors import NoValue

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
    """Optional (()). Paths below the repo (besides Project.dirt_paths) whose changes make made_by.dirty true."""

    def format_id(self, name: str, version: int) -> str:
        """Optional (from format_prefix). The id of a file format of this kind, e.g. "latbench-study/2"."""

    def ref(self, *parts) -> str:
        """Optional (from ref_prefix). A git ref below ref_prefix, e.g. "refs/latbench/run/<exp>/<id>"."""

    # 2. points ---------------------------------------------------------------------
    def points(self, experiment: dict) -> list:
        """Required. The points of an experiment: a list of dicts, each with the key "id" and the values of
        its axes. The order is the order of the design. It raises SystemExit("error: ...") if
        the experiment file has an error (the contract of today's run.expand_points). Benchmarks:
        the Kconfig expansion of the experiment. A kind with a list file reads the lines of the file.
        The experiment is the parsed experiment.yaml (the dict that design.Experiment holds)."""

    # 3. adapters: derived files of a raw run ---------------------------------------
    def run_json(self, run_dir, run_id, digest, made_by, experiment_file) -> dict:
        """Required. The run.json data (format, run, points, ...) that is made from a raw run folder, as a dict
        that jsonout can write. Same arguments as runfiles.run_json."""

    def app_json(self, run_dir, app, run_id, digest, made_by) -> dict:
        """Required. The data of the extractor of the app of a run, as a dict (format "<prefix>-app-<app>/1").
        Same arguments as runfiles.app_json."""

    # 4. the metric provider --------------------------------------------------------
    # rep is one repetition of a point as build.py reads it: a dict with the keys hists, meta, m4,
    # tails (as the run data has them). metric is a name ("<hist>", "meta.<key>", "m4.mask...",
    # "tail.<hist>") or None (a value of the whole point, e.g. the clock drift). stat is the
    # name of the statistic ("p99", "max", "n", "count_ge(100)", "drift_ppm", ...) or None.
    def value(self, rep: dict, metric: str | None, stat: str | None) -> float | str | bool:
        """Required. The value of metric and stat for one repetition: a number, a text or a boolean (a formal
        kind has verdict "pass" and evidence true). The forms equals and in take any of them; all
        numeric forms reject a boolean and a text with a NoValue (checks.number). It raises core.errors.NoValue (with the
        reason) if the point has no such value or the tools have none."""

    def known(self, metric: str | None, stat: str | list | None) -> bool:
        """Required. Whether the tools have a value for metric and stat (stat can be a list: all must be known).
        It never raises; lint uses it to find checks that no tool can evaluate."""

    def width(self, rep: dict, metric: str | None, stat: str | None) -> int:
        """Optional (1). The width of the interval that holds the exact value, in the unit of the value (a
        histogram quantile is only known to its bin: width of the bin; an exact value: 1)."""

    def seen(self, rep: dict, metric: str | None) -> bool:
        """Optional (True). Whether the repetition can have a value for metric at all (benchmarks: an M4 metric
        with [function] needs a site with that function). True if the kind has no such rule."""

    # 5. extra check forms ----------------------------------------------------------
    def extra_forms(self) -> dict:
        """Optional ({}). {form name: form} of the check forms that only this kind has (benchmarks: within with
        tolerance_bins, hist_identical_to; see benchmarks/checks_hist.py). {} if there are none.
        A form object has:
          companions: tuple of the keys of expect that go with it (within: ("tolerance_bins",))
          needs_stat: whether the check needs a stat
          limit(expect) -> str: the text of the limit
          evaluate(res, src, expect, series, metrics, stat_list, with_run) -> str: adds its lines to the
            checks.Result res (values only through res.kind and checks.value, which reject a boolean
            or a text) and returns the limit text. It raises NoValue if the data cannot give a verdict."""

    def is_point_agg(self, metric: str | None, stat: str | None) -> bool:
        """Optional (False). Whether max(x) / min(x) as stat means the largest / smallest value over the
        selected points (benchmarks: yes, except for M4 metrics). A kind that has the aggregate form max(x) / min(x) returns checks.AGG.match(stat) here."""

    # 6. generated checks -----------------------------------------------------------
    def generated_checks(self, experiment: dict) -> list:
        """Optional ([]). Checks that come from a file, as a list of check dicts (same keys as a check in
        hypotheses.yaml). [] for the benchmarks."""

    # 7. instance axis --------------------------------------------------------------
    instance_axis: Any
    """Optional (None). None if the instances of this kind have no axis. Otherwise an object with:
         strip(instance_path) -> study path       "st-a@board/st-b" -> "a/b" (names without the axis)
         suffix(instance_path) -> str             the axis value in the path ('' if none)
         folder_name(study_name, value, prefix="") -> str    the folder name of a study that fixes the axis
         base_name(name) -> str                   one name of a path or folder without the axis value ("a@b" -> "a")
         fixes(name) -> bool                      whether this name fixes the axis value
         of(folder) -> value or None              the axis value an instance folder (or a parent) fixes
         lock_key(value) -> str                   the file-name part of the lock of this value"""

    # 9. build (core/build.py calls these; the kind owns the files of its format) ----------
    tool: str
    """Required. The text of made_by.tool in the aggregates ("scripts/probatrix/benchmarks/study.py")."""

    def experiment_json(self, tree, folder: Any, experiment: str, runs: list) -> dict:
        """Optional (a generic file: format, runs with digests and file hashes, no rows). The data of ex-<experiment>/experiment.json of an instance folder. tree is the core Tree
        (tree.loaded, tree.design, tree.made_by, tree.failed_acceptance); runs are the run-list entries."""

    def plot(self, tree, folder: Any, experiment: str, runs: list) -> str | None:
        """Optional (None: no plots). Make the standard plots of an experiment. None, or the reason why they failed."""

    def central_result(self, central_result: dict, source, context) -> dict:
        """Optional (raises NoValue: the kind has no central results). The central result of a study
        (core.build.Source, core.build.Context); NoValue if the data cannot give it."""

    def pending(self, root, design) -> dict:
        """Optional ({}). {(instance folder, experiment): campaign id} of the runs that a campaign has still to do for the
        results tree root (provisional results). {} if the kind has no campaigns."""

    # 8. commands -------------------------------------------------------------------
    def commands(self) -> dict:
        """Optional ({}). {command name: function} of CLI subcommands that only this kind has.
        R5a: still {}; study.py keeps its own for now."""


class BaseKind:
    """The class to inherit from. It gives each optional hook of Kind its default (see Kind). A kind sets
    the attributes name, schema_prefix, schema_folder, format_prefix, ref_prefix, tool and writes points,
    run_json, app_json, value and known."""

    dirt_paths = ()
    instance_axis = None

    def format_id(self, name, version):
        return f"{self.format_prefix}-{name}/{version}"

    def ref(self, *parts):
        return "/".join([self.ref_prefix, *map(str, parts)])

    def width(self, rep, metric, stat):
        return 1

    def seen(self, rep, metric):
        return True

    def extra_forms(self):
        return {}

    def is_point_agg(self, metric, stat):
        return False

    def generated_checks(self, experiment):
        return []

    def experiment_json(self, tree, folder, experiment, runs):
        """The generic experiment.json: the runs with the digests and the hashes of their derived files."""
        out_runs = []
        for r in runs:
            rj, aj, rsha, asha = tree.loaded[(folder, r["id"])]
            utc = r["id"].split("/")[1]
            out_runs.append({"id": r["id"], "digest": r["digest"], "role": r["role"],
                             "excluded_by_acceptance": tree.failed_acceptance(folder, r["id"]),
                             "run_json": f"{utc}.run.json", "run_json_sha256": rsha,
                             "app_json": f"{utc}.{aj['app']}.json", "app_json_sha256": asha})
        efile = tree.design.experiments.get(experiment)
        return {"format": self.format_id("experiment", 2), "made_by": tree.made_by, "experiment": experiment,
                "design": efile.file_ref() if efile else None, "runs": out_runs}

    def plot(self, tree, folder, experiment, runs):
        return None

    def central_result(self, central_result, source, context):
        raise NoValue(f"the kind {self.name!r} has no central results")

    def pending(self, root, design):
        return {}

    def commands(self):
        return {}


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


def dirt_paths(kind=None):
    """The paths whose changes make a build dirty: the Project's and those of one kind (the given one,
    else the default kind of the Project). Not those of the other kinds: an uncommitted edit of the
    spec of one kind must not make a build of another kind dirty."""
    out = list(config.project().dirt_paths)
    kind = kind if kind is not None else get(config.project().default_kind)
    return tuple(out + [p for p in kind.dirt_paths if p not in out])
