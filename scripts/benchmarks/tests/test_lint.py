# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests of the design lint (studylib/lint.py) on small designs."""

import sys
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from studylib import lint  # noqa: E402
from test_studylib import make_design  # noqa: E402


def texts(root, severity=None):
    return [p.text for p in lint.lint(root) if severity is None or p.severity == severity]


def edit(path, change):
    data = yaml.safe_load(path.read_text())
    change(data)
    path.write_text(yaml.safe_dump(data))


def test_small_design_has_only_warnings(tmp_path):
    make_design(tmp_path)
    root = tmp_path / "design"
    assert texts(root, lint.ERROR) == []
    warn = texts(root, lint.WARNING)
    assert "a study has a description study.md" in warn
    assert any("['variant'] are not named in experiment.md" in w for w in warn)


def test_errors_of_checks(tmp_path):
    make_design(tmp_path)
    root = tmp_path / "design"
    h = root / "st-sub" / "hypotheses.yaml"

    def bad(d):
        c = d["hypotheses"][0]["checks"]
        c.append({"id": "c", "experiment": "nope", "metric": "isr2thr", "stat": "p50", "expect": {"range": [0, 1]}})
        c.append({"id": "d", "experiment": "exp1", "select": {"point": "zz"}, "metric": "isr2thr", "stat": "p50",
                  "expect": {"range": [0, 1]}})
        c.append({"id": "e", "experiment": "exp1", "select": {"variant": "q"}, "metric": "isr2thr", "stat": "p50",
                  "expect": {"range": [0, 1]}})
        c.append({"id": "f", "experiment": "exp1", "select": {"colour": "a"}, "metric": "isr2thr", "stat": "p5x",
                  "expect": {"rangee": [0, 1]}})
    edit(h, bad)
    err = texts(root, lint.ERROR)
    assert any("H1 c: experiment 'nope' is not an experiment of the study" in e for e in err)
    assert any("H1 d: select of the points ['zz']" in e for e in err)
    assert any("H1 e: select of variant = ['q']" in e for e in err)
    assert any("H1 f: select on the axis 'colour'" in e for e in err)
    assert any(e.startswith("H1 f: metric 'isr2thr' with stat 'p5x'") for e in err)


def test_errors_of_folders_and_points(tmp_path):
    make_design(tmp_path)
    root = tmp_path / "design"
    (root / "st-sub" / "stray").mkdir()
    edit(root / "st-sub" / "ex-exp1" / "experiment.yaml",
         lambda d: d.update(points=[{"id": "p1", "axes": {}}], app="no_such_app"))
    err = texts(root, lint.ERROR)
    assert "neither experiment.yaml nor study.yaml" in err
    assert "point 'p1': no value on the axes ['variant']" in err
    assert "app 'no_such_app' is not a folder of tests/benchmarks" in err


def test_only_filters_by_folder(tmp_path):
    make_design(tmp_path)
    root = tmp_path / "design"
    exp = root / "st-sub" / "ex-exp1"
    assert all(p.path.resolve().is_relative_to(exp) for p in lint.lint(root, only=exp))


def test_scaffold_study_and_experiment_pass_the_lint(tmp_path):
    from studylib import scaffold
    from studylib.design import Design
    make_design(tmp_path)
    root = tmp_path / "design"
    top_before = (root / "study.yaml").read_text()
    scaffold.scaffold(root / "st-new", "irq_latency", experiment="new-first")
    scaffold.scaffold(root / "st-new" / "ex-new-second", "wake_latency")
    d = Design(root)
    assert "new" in d.studies and d.study("new").experiments == ["new-first", "new-second"]
    assert d.experiment("new-first").data["app"] == "irq_latency"
    assert (root / "study.yaml").read_text().startswith(top_before.rstrip("\n"))
    assert texts(root, lint.ERROR) == []
    assert any("TODO texts of a template" in w for w in texts(root, lint.WARNING))
    import pytest
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.scaffold(root / "st-sub" / "ex-new-first", "irq_latency")    # names are unique
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.scaffold(root / "new-thing", "irq_latency")
