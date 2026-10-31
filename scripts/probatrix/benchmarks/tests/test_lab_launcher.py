# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The launcher lookup of a lab space: a lab repo can have any of the three layouts (no lab host)."""

import os
import sys
from pathlib import Path

import pytest

from probatrix.benchmarks.studylib import lab


def make_repo(root, layout):
    """A fake design repo with the launcher of one layout (0 new, 1 middle, 2 old) and no others."""
    repo = root / "repo"
    f = repo / lab.LAUNCHERS[layout]
    f.parent.mkdir(parents=True)
    f.write_text("# fake launcher\n")
    return repo


def make_lab(root, repo, venv=None):
    folder = root / "labspace"
    (folder / ".lab").mkdir(parents=True)
    text = f"[lab]\nid = l-1\nname = l\n[design]\nrepo = {repo}\n"
    if venv:
        text += f"[python]\nvenv = {venv}\n"
    (folder / ".lab" / "config").write_text(text)
    return folder


@pytest.fixture
def execs(monkeypatch):
    """os.execv is a recorder. The re-exec variable is not set."""
    calls = []
    monkeypatch.setenv(lab.REEXEC_ENV, "x")
    monkeypatch.delenv(lab.REEXEC_ENV)
    monkeypatch.setattr(os, "execv", lambda exe, args: calls.append((exe, args)))
    return calls


def test_the_three_launchers_in_order():
    assert lab.LAUNCHERS == ("scripts/probatrix/study.py", "scripts/probatrix/benchmarks/study.py",
                             "scripts/benchmarks/study.py")


@pytest.mark.parametrize("layout", [0, 1, 2])
def test_reexec_runs_the_launcher_of_the_layout(tmp_path, monkeypatch, execs, layout):
    folder = make_lab(tmp_path, make_repo(tmp_path, layout))
    monkeypatch.chdir(folder)
    other = tmp_path / "other" / "study.py"
    lab.reexec_in_lab_repo(["lab", "status"], other)
    target = tmp_path / "repo" / lab.LAUNCHERS[layout]
    assert execs == [(sys.executable, [sys.executable, str(target), "lab", "status"])]
    assert os.environ[lab.REEXEC_ENV] == str(other.resolve())


def test_reexec_takes_the_first_launcher_that_exists(tmp_path, monkeypatch, execs):
    repo = make_repo(tmp_path, 2)
    monkeypatch.chdir(make_lab(tmp_path, repo))
    for layout in (1, 0):
        f = repo / lab.LAUNCHERS[layout]
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("")
        monkeypatch.delenv(lab.REEXEC_ENV, raising=False)
        lab.reexec_in_lab_repo([], tmp_path / "other.py")
        assert execs[-1][1][1] == str(f)


def test_reexec_not_for_the_same_script_and_python(tmp_path, monkeypatch, execs):
    repo = make_repo(tmp_path, 1)
    monkeypatch.chdir(make_lab(tmp_path, repo))
    lab.reexec_in_lab_repo(["lab", "status"], repo / lab.LAUNCHERS[1])
    assert execs == []


def test_reexec_for_the_same_script_and_another_python(tmp_path, monkeypatch, execs):
    repo = make_repo(tmp_path, 0)
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "python").write_text("")
    monkeypatch.chdir(make_lab(tmp_path, repo, venv=venv))
    lab.reexec_in_lab_repo([], repo / lab.LAUNCHERS[0])
    assert execs and execs[0][0] == str(venv / "bin" / "python")


def test_reexec_not_when_the_variable_is_set(tmp_path, monkeypatch, execs):
    monkeypatch.chdir(make_lab(tmp_path, make_repo(tmp_path, 2)))
    monkeypatch.setenv(lab.REEXEC_ENV, "1")
    lab.reexec_in_lab_repo([], tmp_path / "other.py")
    assert execs == []


def test_reexec_not_for_lab_init_or_outside_a_lab_space(tmp_path, monkeypatch, execs):
    monkeypatch.chdir(make_lab(tmp_path, make_repo(tmp_path, 2)))
    lab.reexec_in_lab_repo(["lab", "init", "x"], tmp_path / "other.py")
    monkeypatch.chdir(tmp_path)
    lab.reexec_in_lab_repo(["lab", "status"], tmp_path / "other.py")
    assert execs == []


def test_reexec_error_names_the_three_paths(tmp_path, monkeypatch, execs):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(make_lab(tmp_path, repo))
    with pytest.raises(SystemExit) as e:
        lab.reexec_in_lab_repo([], tmp_path / "other.py")
    text = str(e.value)
    assert text.startswith("error: the lab space ") and "which has none of" in text
    for rel in lab.LAUNCHERS:
        assert str(repo / rel) in text
    assert execs == []


def test_reexec_error_when_the_python_is_missing(tmp_path, monkeypatch, execs):
    monkeypatch.chdir(make_lab(tmp_path, make_repo(tmp_path, 0), venv="novenv"))
    with pytest.raises(SystemExit) as e:
        lab.reexec_in_lab_repo([], tmp_path / "other.py")
    assert "has the Python environment" in str(e.value)


@pytest.mark.parametrize("layout", [0, 1, 2])
def test_init_accepts_each_layout(tmp_path, layout):
    repo = make_repo(tmp_path, layout)
    folder = tmp_path / "newlab"
    folder.mkdir()
    made = lab.init(folder, repo)
    assert made.repo == repo.resolve()


def test_init_error_names_the_launchers(tmp_path):
    (tmp_path / "repo").mkdir()
    with pytest.raises(lab.LabError) as e:
        lab.init(tmp_path / "newlab", tmp_path / "repo")
    for rel in lab.LAUNCHERS:
        assert rel in str(e.value)


@pytest.mark.parametrize("layout, folder", [(0, "scripts/probatrix/benchmarks"), (1, "scripts/benchmarks")])
def test_requirements_from_the_new_folder_or_the_old_one(tmp_path, layout, folder):
    d = tmp_path / folder
    d.mkdir(parents=True)
    (d / "requirements.txt").write_text("PyYAML>=6  # why\n# only a comment\nnumpy\n")
    assert lab.requirements(tmp_path) == [("PyYAML", ">=6"), ("numpy", "")]
    assert lab.requirements(tmp_path, "requirements.lock") == []


def test_requirements_prefer_the_new_folder(tmp_path):
    for folder, text in (("scripts/probatrix/benchmarks", "new==1\n"), ("scripts/benchmarks", "old==1\n")):
        (tmp_path / folder).mkdir(parents=True)
        (tmp_path / folder / "requirements.txt").write_text(text)
    assert lab.requirements(tmp_path) == [("new", "==1")]


def test_requirements_fall_back_per_file(tmp_path):
    new = tmp_path / "scripts/probatrix/benchmarks"
    old = tmp_path / "scripts/benchmarks"
    new.mkdir(parents=True)
    old.mkdir(parents=True)
    (new / "requirements.txt").write_text("a>=1\n")
    (old / "requirements.lock").write_text("a==1.2\n")
    assert lab.requirements(tmp_path, "requirements.lock") == [("a", "==1.2")]


@pytest.mark.parametrize("launcher", ["study.py", "benchmarks/study.py"])
@pytest.mark.parametrize("layout", [0, 2])
def test_the_launchers_re_exec_before_they_need_pyyaml(tmp_path, launcher, layout):
    """The Python that starts a launcher in a lab space can lack PyYAML: the re-exec comes first."""
    import subprocess
    (tmp_path / "noyaml").mkdir()
    (tmp_path / "noyaml" / "yaml.py").write_text("raise ImportError('no yaml')\n")
    repo = make_repo(tmp_path, layout)
    (repo / lab.LAUNCHERS[layout]).write_text("import sys\nprint('ran', sys.argv[1:])\n")
    folder = make_lab(tmp_path, repo)
    scripts = Path(lab.__file__).resolve().parents[3]
    env = {k: v for k, v in os.environ.items() if k not in ("ZEPHYR_BASE", lab.REEXEC_ENV)}
    env["PYTHONPATH"] = str(tmp_path / "noyaml")
    r = subprocess.run([sys.executable, str(scripts / "probatrix" / launcher), "lab", "status"], cwd=folder,
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "ran ['lab', 'status']", r.stderr
