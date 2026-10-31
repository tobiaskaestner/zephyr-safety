# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The kind "latbench": the latency benchmarks of the kernel (see study.py and run.py).

This object holds what only the benchmarks need: the folder of the benchmark apps, the tree
manifests, the boards file, the prefixes of file formats and git refs, the tests/benchmarks
dirt path, the board axis of an instance and the metric provider (histograms, M4, META,
witness tables, clock drift). The provider code is still in studylib/stats.py and the check
forms in studylib/checks.py; R5b moves them. Importing this module registers the kind with
probatrix.core.kinds and its schema folder with probatrix.core.schema.
"""

from pathlib import Path

from probatrix.core import config, kinds, schema

HERE = Path(__file__).resolve().parent


class BoardAxis:
    """The instance axis of the benchmarks: the board. The rules are in studylib/boardaxis.py."""

    @staticmethod
    def strip(instance_path):
        from probatrix.benchmarks.studylib import boardaxis
        return boardaxis.strip_board(instance_path)

    @staticmethod
    def suffix(instance_path):
        from probatrix.benchmarks.studylib import boardaxis
        return boardaxis.board_suffix(instance_path)

    @staticmethod
    def folder_name(study_name, value, prefix=""):
        from probatrix.benchmarks.studylib import boardaxis
        return boardaxis.folder_name(study_name, value, prefix)

    @staticmethod
    def of(folder):
        from probatrix.benchmarks.studylib import boardaxis
        return boardaxis.board_of(folder)

    @staticmethod
    def lock_key(value):
        from probatrix.benchmarks.studylib import boardaxis
        return boardaxis.lock_key(value)


class LatbenchKind:
    name = "latbench"
    schema_prefix = "latbench"
    schema_folder = HERE / "schemas"
    format_prefix = "latbench"             # latbench-study/2, latbench-run/2, ...
    ref_prefix = "refs/latbench"           # refs/latbench/run/..., refs/latbench/campaign/...
    dirt_paths = ("tests/benchmarks",)
    tool = "scripts/probatrix/benchmarks/study.py"
    instance_axis = BoardAxis()

    def __init__(self, repo=None):
        # folders of the benchmark side of the repo. They are fixed when the Kind is made (the repo that
        # holds this package, as before the split); a test that needs others makes its own LatbenchKind.
        repo = config.Project.default().repo if repo is None else repo
        self.bench_dir = repo / "tests" / "benchmarks"
        self.trees_dir = repo / "validation" / "trees"
        self.boards_file = self.bench_dir / "boards.yaml"

    def format_id(self, name, version):
        """The id of a file format, e.g. "latbench-study/2"."""
        return f"{self.format_prefix}-{name}/{version}"

    def ref(self, *parts):
        """A git ref below the prefix, e.g. refs/latbench/run/<exp>/<id>."""
        return "/".join([self.ref_prefix, *map(str, parts)])

    def points(self, experiment):
        from probatrix.benchmarks.studylib import kindhooks
        return kindhooks.expand_points(experiment)

    def run_json(self, run_dir, run_id, digest, made_by, experiment_file):
        from probatrix.benchmarks.studylib import runfiles
        return runfiles.run_json(run_dir, run_id, digest, made_by, experiment_file)

    def app_json(self, run_dir, app, run_id, digest, made_by):
        from probatrix.benchmarks.studylib import runfiles
        return runfiles.app_json(run_dir, app, run_id, digest, made_by)

    def value(self, rep, metric, stat):
        from probatrix.benchmarks.studylib import stats
        return stats.value(rep, metric, stat)

    def known(self, metric, stat):
        from probatrix.benchmarks.studylib import stats
        return stats.known(metric, stat)

    def width(self, rep, metric, stat):
        from probatrix.benchmarks.studylib import stats
        return stats.value_width(rep, metric, stat)

    def seen(self, rep, metric):
        from probatrix.benchmarks.studylib import stats
        return stats.function_seen(rep, metric)

    def experiment_json(self, tree, folder, experiment, runs):
        from probatrix.benchmarks.studylib import experimentjson
        return experimentjson.experiment_json(tree, folder, experiment, runs)

    def plot(self, tree, folder, experiment, runs):
        from probatrix.benchmarks.studylib import experimentjson
        return experimentjson.plot(tree, folder, experiment, runs)

    def central_result(self, central_result, source, context):
        from probatrix.benchmarks.studylib import central
        return central.evaluate(central_result, source, context)

    def pending(self, root, design):
        from probatrix.benchmarks.studylib import experimentjson
        return experimentjson.pending(root, design)

    def extra_forms(self):
        from probatrix.benchmarks import checks_hist
        return checks_hist.FORMS

    @staticmethod
    def is_point_agg(metric, stat):
        """max(x) / min(x) of a metric is an aggregate over the selected points, but not for an M4 metric
        (there it is inside the value)."""
        import re
        return isinstance(stat, str) and bool(re.match(r"^(max|min)\((.+)\)$", stat)) \
            and not (metric or "").startswith("m4.")

    def generated_checks(self, experiment):
        return []

    def commands(self):
        return {}


KIND = LatbenchKind()
kinds.register(KIND)
schema.register(KIND.schema_prefix, KIND.schema_folder)
