# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The latbench Kind: registration, hooks, the instance axis."""

import json

from probatrix.benchmarks import kind as benchkind
from probatrix.benchmarks import run
from probatrix.benchmarks.studylib import boardaxis, campaign, hwcheck, instance, stats
from probatrix.core import config, kinds, schema


def test_registered_and_default():
    assert kinds.get("latbench") is benchkind.KIND
    assert kinds.kind_of({}) is benchkind.KIND                 # the default kind of the Project
    assert kinds.kind_of({"kind": "latbench"}, {}) is benchkind.KIND
    assert "latbench" in schema.prefixes()
    assert (benchkind.KIND.schema_folder / "study.schema.yaml").is_file()


def test_dirt_paths_are_project_and_kind():
    assert kinds.dirt_paths() == ("validation", "scripts/probatrix", "tests/benchmarks")


def test_expand_points_stays_in_run():
    exp = {"name": "x"}
    assert run.expand_points.__module__.endswith("run")
    import inspect
    assert list(inspect.signature(run.expand_points).parameters) == ["exp"]
    assert benchkind.KIND.points.__name__ == "points"


def test_metric_provider_delegates():
    rep = {"hists": {}, "meta": {"clock_drift_cyc": 5, "samples": 10, "clock_elapsed_cyc": 1000}}
    assert benchkind.KIND.value(rep, None, "drift_per_wake") == 0.5
    assert benchkind.KIND.value(rep, None, "drift_ppm") == 5000
    assert benchkind.KIND.known("meta.x", None) and not benchkind.KIND.known("meta.x", "p99")
    assert benchkind.KIND.width(rep, "meta.x", "p99") == 1
    assert benchkind.KIND.seen(rep, "meta.x") is True
    assert benchkind.KIND.value is not stats.value        # a method, same behaviour


def test_instance_axis_owns_the_three_rules(tmp_path):
    ax = benchkind.KIND.instance_axis
    assert ax.strip("a@b/c") == "a/c" and ax.suffix("a@b/c") == "b"
    assert ax.folder_name("a", "p", "st-") == "st-a@p"
    assert ax.lock_key("x/y@z") == "x_y_z"
    assert campaign.lock_file(type("L", (), {"locks": tmp_path})(), "x/y@z").name == "board-x_y_z.lock"
    assert hwcheck.board_tag("x/y@z") == "x_y_z"
    d = tmp_path / "i" / "j"
    d.mkdir(parents=True)
    (tmp_path / "i" / "instance.json").write_text(json.dumps({"board": "bb"}))
    (d / "instance.json").write_text("{}")
    assert ax.of(d) == "bb" and instance.board_of(d) == "bb" and boardaxis.board_of(tmp_path) is None


def test_format_and_ref_names():
    assert benchkind.KIND.format_id("run", 2) == "latbench-run/2"
    assert config.project().default_kind == "latbench"


def test_lock_key_is_the_old_file_name_rule():
    # old and new clones share the lab lock files: the key must not change
    assert boardaxis.lock_key("nucleo_g474re") == "nucleo_g474re"
    assert boardaxis.lock_key("a/b@c") == "a_b_c"
    old = lambda board: board.replace("/", "_").replace("@", "_")      # noqa: E731  (campaign.lock_file, hwcheck.board_tag of 54c0180)
    for b in ("nucleo_g474re", "nrf54l15dk", "a/b@c", "x@y/z@w", ""):
        assert boardaxis.lock_key(b) == old(b) == hwcheck.board_tag(b)


def test_bin_forms_reject_a_bool_and_a_text():
    import pytest
    from probatrix.core import checks
    from probatrix.core.errors import NoValue

    class Src:
        kind = benchkind.KIND

        def __init__(self, rep):
            self.rep = rep

        def observations(self, exp, series=None):
            return [checks.Obs("e/1", "t", "p", {}, self.rep)]

    for v in (True, "x"):
        c = {"experiment": "e", "metric": None, "stat": "drift_per_wake",
             "expect": {"within": {"experiment": "e"}, "tolerance_bins": 1}}
        s = Src({"hists": {}, "meta": {}})
        s.rep["meta"].update(clock_drift_cyc=1, samples=1)
        # the reference value is read like the point value: both go through checks.value
        k = benchkind.KIND
        k.value = lambda rep, m, st, v=v: v
        try:
            with pytest.raises(NoValue, match="boolean|text"):
                checks.evaluate(c, s)
        finally:
            del k.value                                     # back to the class method


def test_every_study_of_the_repo_names_its_kind():
    """The 25 study.yaml of the latency designs have kind: latbench (kind_of reads it)."""
    import yaml
    files = sorted(config.project().design_root.rglob("study.yaml"))
    assert len(files) == 25
    for f in files:
        data = yaml.safe_load(f.read_text())
        assert data.get("kind") == "latbench", f
        assert kinds.kind_of(data) is benchkind.KIND
