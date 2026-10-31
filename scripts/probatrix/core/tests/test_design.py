# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests of the design loader: studies, experiments, renames, imports and errors.

The schema folder of the benchmarks is registered by its path (core does not import the kind).
"""

from pathlib import Path

import pytest
import yaml

from probatrix.core import config, schema
from probatrix.core.design import Design, DesignError, repo_rel

schema.register("latbench", Path(__file__).resolve().parents[2] / "benchmarks" / "schemas")


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data))


def experiment(name, **more):
    return {"name": name, "app": "wake_latency", "trees": ["ws-up"], **more}


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "design"
    write(r / "study.yaml", {"name": "top", "substudies": ["sub"], "experiments": ["e0"]})
    write(r / "ex-e0" / "experiment.yaml", experiment("e0"))
    write(r / "st-sub" / "study.yaml", {"name": "sub", "experiments": ["e1"]})
    write(r / "st-sub" / "ex-e1" / "experiment.yaml", experiment("e1", renamed_from="old-e1"))
    write(r / "st-sub" / "hypotheses.yaml", {"hypotheses": [{
        "id": "H1", "type": "model", "statement": "s", "basis": "b", "wrong_if": "w",
        "checks": [{"id": "a", "manual": True, "statement": "x"}]}]})
    return r


def test_the_tree_of_studies_and_experiments(root):
    d = Design(root)
    assert list(d.studies) == ["", "sub"]
    assert d.top.name == "top" and d.study("sub").name == "sub"
    assert sorted(d.experiments) == ["e0", "e1"]
    assert d.experiment("e1").study == "sub"
    assert [h["id"] for h in d.study("sub").hypotheses] == ["H1"]


def test_renamed_experiments_keep_their_runs(root):
    d = Design(root)
    assert d.canonical("old-e1") == "e1" and d.canonical("e0") == "e0"
    assert d.names("old-e1") == ["e1", "old-e1"]
    assert d.run_experiment("old-e1/20260101T000000Z") == "e1"
    assert d.experiment("old-e1").name == "e1"


def test_design_files_have_a_hash(root):
    files = Design(root).study("sub").files()
    assert sorted(files) == ["hypotheses.yaml", "study.yaml"]
    assert all(len(v) == 64 for v in files.values())
    assert sorted(Design(root).top.files()) == ["study.yaml"]


def test_the_root_comes_from_the_project(root):
    with config.use(config.Project.default().with_(design_root=root)):
        assert Design().root == root


def test_repo_rel(tmp_path):
    repo = config.project().repo
    assert repo_rel(repo / "a" / "b") == "a/b"
    assert repo_rel(tmp_path / "x") == str(tmp_path / "x")


def test_errors_of_the_design(root):
    d = Design(root)
    with pytest.raises(DesignError):
        d.study("nope")
    with pytest.raises(DesignError):
        d.experiment("nope")
    (root / "st-sub" / "study.yaml").unlink()
    with pytest.raises(DesignError, match="no study.yaml"):
        Design(root)


def test_a_missing_experiment_folder(root):
    write(root / "study.yaml", {"name": "top", "substudies": ["sub"], "experiments": ["e0", "ghost"]})
    with pytest.raises(DesignError, match="no experiment folder"):
        Design(root)


def test_an_experiment_with_two_owners(root):
    write(root / "st-sub" / "study.yaml", {"name": "sub", "experiments": ["e1", "e0"]})
    write(root / "st-sub" / "ex-e0" / "experiment.yaml", experiment("e0"))
    with pytest.raises(DesignError, match="owned by"):
        Design(root)


def test_an_import_of_an_experiment_that_the_study_does_not_own(root):
    write(root / "study.yaml", {"name": "top", "substudies": ["sub"], "experiments": ["e0"],
                                "imports": [{"study": "sub", "experiment": "e0"}]})
    with pytest.raises(DesignError, match="does not own"):
        Design(root)


def test_a_design_file_that_breaks_its_schema(root):
    write(root / "st-sub" / "study.yaml", {"name": "sub", "experiments": ["e1"], "typo": 1})
    with pytest.raises(DesignError, match="unknown key 'typo'"):
        Design(root)
