# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The kind "tlaplus": TLA+ model checks of the kernel spec (spec/tla).

One experiment is one list file (lists.py): each line is a point, a model run with an expected result.
A run is a raw TLC run folder (tlc.py reads it). The subject of an experiment (subject.py) is the set of
repo paths that its result depends on. The kind has no instance axis (an instance is a study). Importing this
module registers the kind with probatrix.core.kinds and its schema folder with probatrix.core.schema.

The metric provider: a check reads one value of a repetition by name (metric: verdict, expected, states,
depth, seconds, evidence, ...), without a stat. The values are in VALUES. A value can be a number, a text
or a boolean (core/checks.py: equals takes all three, the numeric forms reject a text and a boolean).

The tools of the experiments (the key `tool`): tlc and tlc-simulate have an adapter (tlc.py). apalache and
traces are in the schema, but they have none yet: the design lint reports them.
"""

from pathlib import Path

from probatrix.core import config, kinds, schema
from probatrix.core.errors import NoValue

HERE = Path(__file__).resolve().parent
# The values that a check can read (metric names) and their types. tlc.py makes them from a TLC run.
VALUES = {"verdict": str, "expected": str, "states": int, "depth": int, "seconds": float, "evidence": bool,
          "violated": str, "trace_len": int, "lasso": str, "collision_calculated": float,
          "collision_actual": float, "workers": int, "heap": str, "runner_verdict": str}
EXPECTED = r"^(pass|probes|no-states|fail:\S+)$"      # the expected results of a TLC line (run_tlc.sh)


class TlaplusKind(kinds.BaseKind):
    name = "tlaplus"
    schema_prefix = "tlaplus"
    schema_folder = HERE / "schemas"
    format_prefix = "tlaplus"              # tlaplus-run/1, tlaplus-app-tlc/1, tlaplus-study/2, ...
    ref_prefix = "refs/tlaplus"            # refs/tlaplus/run/<experiment>/<UTC>
    dirt_paths = ("spec/tla",)             # the models, the lists and the runners (tools/)
    tool = "scripts/probatrix/study.py"

    # ---------------------------------------------------------------- points
    def keys(self, experiment):
        from probatrix.tlaplus import lists
        return lists.KEYS_OF_TOOL[experiment["tool"]]

    def lines(self, experiment):
        """The lines of the list file of an experiment (SystemExit with the error text, as points() must)."""
        from probatrix.tlaplus import lists
        path = config.project().repo / experiment["list"]
        try:
            lines = lists.read(path, self.keys(experiment))
        except (OSError, lists.ListError) as e:
            raise SystemExit(f"error: {e}") from None
        if experiment["tool"] in ("tlc", "tlc-simulate"):
            import re
            for ln in lines:
                if not re.match(EXPECTED, ln.expected):
                    raise SystemExit(f"error: {path}:{ln.lineno}: {ln.id}: the expected result {ln.expected!r} "
                                     "is not pass, probes, no-states or fail:<Name>")
        return lines

    def point_params(self, experiment, line):
        """The parameters of a point: for tlc-simulate depth, traces and seed (the line over the defaults of
        the experiment), else {}."""
        if experiment["tool"] != "tlc-simulate":
            return {}
        merged = {**(experiment.get("simulate") or {}), **{k: int(v) for k, v in line.fields.items()
                                                           if k in ("depth", "traces", "seed")}}
        return {k: merged[k] for k in ("depth", "traces", "seed") if k in merged}

    def points(self, experiment):
        return [{"id": ln.id, "axes": {}, "module": ln.module, "config": ln.name, "expected": ln.expected,
                 "fields": dict(ln.fields), "params": self.point_params(experiment, ln)}
                for ln in self.lines(experiment)]

    def generated_checks(self, experiment):
        """One check for each line: the verdict equals the expected result. Where the line gives states= and depth=
        (a model check), one more check for each: the count equals it. A line of a simulation has no counts to
        check (its depth= is a parameter)."""
        try:
            lines = self.lines(experiment)
        except SystemExit:
            return []
        out = []
        for ln in lines:
            sel = {"point": ln.id}
            out.append({"id": f"{ln.id}-verdict", "metric": "verdict", "select": sel,
                        "expect": {"equals": ln.expected}})
            if experiment["tool"] == "tlc":
                for key in ("states", "depth"):
                    if key in ln.fields:
                        out.append({"id": f"{ln.id}-{key}", "metric": key, "select": sel,
                                    "expect": {"equals": int(ln.fields[key])}})
        return out

    # ---------------------------------------------------------------- adapters
    def run_json(self, run_dir, run_id, digest, made_by, experiment_file):
        from probatrix.tlaplus import tlc
        return tlc.run_json(run_dir, run_id, digest, made_by, experiment_file)

    def app_json(self, run_dir, app, run_id, digest, made_by):
        from probatrix.tlaplus import tlc
        return tlc.app_json(run_dir, app, run_id, digest, made_by)

    # ---------------------------------------------------------------- the provider
    def value(self, rep, metric, stat):
        if stat is not None:
            raise NoValue(f"{metric}: the kind tlaplus has no stats (got {stat!r})")
        try:
            return rep["values"][metric]
        except KeyError:
            raise NoValue(f"the point has no value {metric!r}") from None

    def known(self, metric, stat):
        return stat is None and metric in VALUES

    def stat_needed(self, metric):
        return False

    # ---------------------------------------------------------------- commands
    def commands(self):
        """The CLI commands of the kind (importer.py): import-lab."""
        from probatrix.tlaplus import importer
        return dict(importer.COMMANDS)

    @property
    def cli_errors(self):
        from probatrix.tlaplus import importer
        return importer.ERRORS

    # ---------------------------------------------------------------- lint
    def lint_experiment(self, e):
        """The generic lint (folder, experiment.md, points) and the rules between the keys: the tool has an
        adapter, simulate goes with tlc-simulate, the list is inside a subject path, the paths exist."""
        pts, out = super().lint_experiment(e)
        f, exp, repo = e.folder / "experiment.yaml", e.data, config.project().repo
        tool = exp["tool"]
        if tool not in ("tlc", "tlc-simulate"):
            out.append(("error", f, f"the tool {tool!r} has no adapter yet (tlc and tlc-simulate have)"))
        if tool == "tlc-simulate" and "simulate" not in exp:
            out.append(("error", f, "the tool tlc-simulate needs the defaults simulate: {depth, traces, seed}"))
        if tool != "tlc-simulate" and "simulate" in exp:
            out.append(("error", f, "simulate is for the tool tlc-simulate only"))
        if not any(exp["list"] == p or exp["list"].startswith(p.rstrip("/") + "/") for p in exp["subject"]):
            out.append(("error", f, f"the list {exp['list']} is not inside a path of subject (a change of the list "
                                    "must change the subject tree)"))
        for key in ("subject", "tools"):
            for p in exp[key]:
                if not (repo / p).exists():
                    out.append(("error", f, f"{key}: {p} does not exist"))
        from probatrix.core import checks
        for a in e.acceptance:
            for p in checks.problems(a, self):
                out.append(("error", f, f"acceptance {a.get('id')}: {p}"))
        return pts, out


KIND = TlaplusKind()
kinds.register(KIND)
schema.register(KIND.schema_prefix, KIND.schema_folder, default=False)   # latbench stays the default prefix
