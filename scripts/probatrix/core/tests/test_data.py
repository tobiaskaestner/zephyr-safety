# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The generic Instance of core/data.py over hand-made files (no kind, no build, no benchmarks)."""

import json

import pytest

from probatrix.core import config, data, layout


@pytest.fixture
def instance(tmp_path, monkeypatch):
    pytest.importorskip("pandas")
    design = tmp_path / "design" / "s1"
    design.mkdir(parents=True)
    (design / "hypotheses.yaml").write_text(
        "hypotheses:\n- id: H1\n  checks:\n  - id: c1\n    basis: |\n      because\n      of this\n")
    monkeypatch.setattr(config, "_current", config.project().with_(repo=tmp_path / "design"))
    folder = tmp_path / "res" / "top"
    exp = folder / f"{layout.EXPERIMENT_PREFIX}e1"
    exp.mkdir(parents=True)
    study = {"design": {"folder": "s1"},
             "hypotheses": [{"id": "H1", "type": "t", "statement": "s", "verdict": "confirmed", "checks_confirmed": 1,
                             "checks": [{"id": "c1", "verdict": "confirmed", "by": "x", "measured": 1, "limit": 2}]}],
             "central_results": [{"id": "R1", "texts": ["one", "two"]}, {"id": "R2", "not_evaluated": "why"}]}
    (folder / "study.json").write_text(json.dumps(study))
    (folder / "instance.json").write_text("{}")
    (exp / "experiment.json").write_text(json.dumps({"rows": [], "columns": []}))
    return data.load_instance(folder)


def test_tables(instance):
    assert list(instance.hypotheses()["id"]) == ["H1"]
    checks = instance.checks()
    assert list(checks["check"]) == ["H1 c1"] and list(checks["basis"]) == ["because of this"]
    assert list(instance.central()["result"]) == ["one", "two", "(not evaluated: why)"]


def test_experiment_json_and_missing_experiment(instance):
    assert instance.experiment_json("e1") == {"rows": [], "columns": []}
    assert instance.board is None
    with pytest.raises(FileNotFoundError):
        instance.experiment_json("nope")
