# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests of the Project (probatrix.core.config)."""

from pathlib import Path

import pytest

from probatrix.benchmarks import kind as benchkind
from probatrix.benchmarks import trees
from probatrix.core import design as designmod
from probatrix.core import layout
from probatrix.core import config

HERE = Path(__file__).resolve()


def test_default_project_is_the_repo_of_the_package():
    p = config.Project.default()
    assert p.repo == HERE.parents[4]                      # the folder above scripts/
    assert (p.repo / "scripts" / "probatrix" / "core" / "config.py").is_file()
    assert p.design_root == p.repo / "validation" / "empirical" / "latencies"
    k = benchkind.KIND
    assert k.bench_dir == p.repo / "tests" / "benchmarks"
    assert k.trees_dir == p.repo / "validation" / "trees"
    assert k.boards_file == k.bench_dir / "boards.yaml"
    assert (p.design_root / "study.yaml").is_file()
    assert k.boards_file.is_file()


def test_at_and_override(tmp_path):
    p = config.Project.at(tmp_path, design_root=tmp_path / "d", study_prefix="s-")
    assert p.repo == tmp_path
    assert p.design_root == tmp_path / "d"
    assert p.study_prefix == "s-" and p.experiment_prefix == "ex-"
    with pytest.raises(Exception):
        p.repo = Path("/")                                # frozen


def test_use_and_set_project(tmp_path):
    before = config.project()
    other = config.Project.at(tmp_path)
    with config.use(other):
        assert config.project() is other
        assert trees.study_dir("a/b") == tmp_path / "validation" / "empirical" / "latencies" / "st-a" / "st-b"
    assert config.project() is before
    config.set_project(other)
    try:
        assert config.project() is other
    finally:
        config.set_project(before)


def test_names_of_formats_and_refs():
    k = benchkind.KIND
    assert k.format_id("study", 2) == "latbench-study/2"
    assert k.ref("run", "exp", "20260101T000000Z") == "refs/latbench/run/exp/20260101T000000Z"
    assert k.ref("campaign", "c1") == "refs/latbench/campaign/c1"


def test_design_takes_its_root_from_the_project(tmp_path):
    (tmp_path / "study.yaml").write_text("name: top\n")
    with config.use(config.Project.default().with_(design_root=tmp_path)):
        d = designmod.Design()
    assert d.root == tmp_path and list(d.studies) == [""]
    assert designmod.Design(tmp_path / ".").root == tmp_path / "."      # an explicit root wins


def test_repo_rev_uses_the_dirt_paths_of_the_project(tmp_path):
    import subprocess
    def git(*a):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=tmp_path, check=True,
                       capture_output=True)
    git("init", "-q")
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "f").write_text("1")
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "g").write_text("1")
    git("add", "-A")
    git("commit", "-qm", "x")
    (tmp_path / "b" / "g").write_text("2")
    watching_a = config.Project.at(tmp_path, dirt_paths=("a",))
    watching_b = config.Project.at(tmp_path, dirt_paths=("b",))
    with config.use(watching_a):
        assert designmod.repo_rev()[1] is False
    with config.use(watching_b):
        assert designmod.repo_rev()[1] is True
        assert designmod.repo_rel(tmp_path / "b" / "g") == "b/g"


def test_the_old_constants_are_aliases_of_the_default_project():
    p = config.Project.default()
    assert (trees.REPO_DIR, trees.STUDIES_DIR, trees.BENCH_DIR) == (p.repo, p.design_root, benchkind.KIND.bench_dir)
    assert (trees.TREES_DIR, trees.BOARDS_FILE) == (benchkind.KIND.trees_dir, benchkind.KIND.boards_file)
    assert (trees.EXPERIMENT_PREFIX, trees.STUDY_PREFIX) == (p.experiment_prefix, p.study_prefix)
    assert (layout.EXPERIMENT_PREFIX, layout.STUDY_PREFIX) == (p.experiment_prefix, p.study_prefix)


def _repo_in_process(package_root, var=None):
    """(stdout, stderr) of a process that prints the repo of the default Project of the package at package_root."""
    import os
    import subprocess
    import sys
    env = {k: v for k, v in os.environ.items() if k not in ("ZEPHYR_BASE", "PROBATRIX_REPO")}
    env["PYTHONPATH"] = str(package_root)
    if var is not None:
        env["PROBATRIX_REPO"] = str(var)
    r = subprocess.run([sys.executable, "-c", "from probatrix.core import config; print(config.project().repo)"],
                       env=env, capture_output=True, text=True)
    return r.stdout.strip(), r.stderr


def test_a_clone_is_its_own_repo_without_the_variable():
    out, err = _repo_in_process(HERE.parents[3])
    assert out == str(HERE.parents[4]) and err == ""


def test_a_clone_ignores_a_different_variable_with_one_warning(tmp_path):
    out, err = _repo_in_process(HERE.parents[3], tmp_path)
    assert out == str(HERE.parents[4])
    assert err.count("warning: PROBATRIX_REPO") == 1 and str(tmp_path) in err


def test_a_clone_takes_the_same_variable_without_a_warning():
    out, err = _repo_in_process(HERE.parents[3], HERE.parents[4])
    assert out == str(HERE.parents[4]) and err == ""


def test_an_installed_copy_takes_the_variable(tmp_path):
    """A wheel-like layout: the package in site/, no scripts/probatrix/study.py above it."""
    import shutil
    site = tmp_path / "site"
    shutil.copytree(HERE.parents[2], site / "probatrix", ignore=shutil.ignore_patterns("__pycache__", "benchmarks"))
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _repo_in_process(site, repo) == (str(repo), "")
    assert _repo_in_process(site)[0] == str(tmp_path)  # no variable: the folder above, as before
