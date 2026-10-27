# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for trees.py setup with local git repos (no network)."""

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import trees  # noqa: E402


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def make_source(tmp_path):
    src = tmp_path / "ws-up" / "zephyr"
    src.mkdir(parents=True)
    git("init", "-q", "-b", "main", cwd=src)
    (src / "a.txt").write_text("1\n")
    git("add", "a.txt", cwd=src)
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "one", cwd=src)
    rev = git("rev-parse", "HEAD", cwd=src)
    (src / "a.txt").write_text("2\n")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-am", "two", cwd=src)
    return src, rev


def files(path):
    return sorted(str(p.relative_to(path)) for p in path.rglob("*"))


def config(tmp_path, url, rev, source_root=None):
    """A trees config with one tree "t" (zephyr only) and its manifest file."""
    m = tmp_path / "pins" / "t.yml"
    m.parent.mkdir(exist_ok=True)
    m.write_text(f"""manifest:
  version: "1.0"
  self:
    userdata: {{description: test, zephyr_sdk: "1.0.1"}}
  projects:
    - name: zephyr
      url: {url}
      revision: {rev}
      path: zephyr
""")
    t = trees.read_manifest(m)
    return {"root": tmp_path / "lab-trees", "trees": {"t": t}, "source_root": source_root,
            "toolchain": {"zephyr_sdk": {"version": "1.0.1"}}}


def test_setup_makes_a_west_workspace_at_the_pin(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEPHYR_BASE", str(tmp_path / "elsewhere"))      # must not lead west away
    src, rev = make_source(tmp_path)
    cfg = config(tmp_path, src, rev)
    trees.setup_tree(cfg, "t", log=lambda *a: None)
    path = trees.repo_dir(cfg, "t", "zephyr")
    assert git("rev-parse", "HEAD", cwd=path) == rev and (path / "a.txt").read_text() == "1\n"
    assert (cfg["root"] / "t" / ".west").is_dir()
    assert trees.west_topdir(cfg["root"] / "t") == (cfg["root"] / "t").resolve()
    assert trees.tree_state(cfg, "t") == ("ok", "")
    trees.setup_tree(cfg, "t", log=lambda *a: None)                    # again: nothing changes
    m = tmp_path / "pins" / "t.yml"
    copy = cfg["root"] / "t" / "manifest" / "west.yml"
    m.write_text(m.read_text() + "    - name: extra\n      url: x\n      revision: " + rev + "\n")
    assert trees.copy_differs(copy, m) is None                         # a new project is good
    m.write_text(m.read_text().replace(f"revision: {rev}\n      path: zephyr", f"revision: {'0' * 40}\n      path: zephyr"))
    why = trees.copy_differs(copy, m)
    assert why and "pin a new tree" in why


def test_setup_from_the_cache_writes_nothing_into_it(tmp_path):
    src, rev = make_source(tmp_path)
    cache = tmp_path / "cache"
    git("clone", "-q", str(src), str(cache / "t" / "zephyr"), cwd=tmp_path)
    before = files(cache)
    cfg = config(tmp_path, "https://example.invalid/zephyr", rev, source_root=cache)
    trees.setup_tree(cfg, "t", log=lambda *a: None)                    # no network: the url is invalid
    path = trees.repo_dir(cfg, "t", "zephyr")
    assert files(cache) == before
    assert git("rev-parse", "HEAD", cwd=path) == rev
    assert git("remote", "get-url", "origin", cwd=path) == "https://example.invalid/zephyr"
    assert not (path / ".git" / "objects" / "info" / "alternates").exists()


def test_tree_states(tmp_path):
    src, rev = make_source(tmp_path)
    cfg = config(tmp_path, src, rev)
    assert trees.tree_state(cfg, "t")[0] == "not set up"
    trees.setup_tree(cfg, "t", log=lambda *a: None)
    (trees.repo_dir(cfg, "t", "zephyr") / "new.txt").write_text("x\n")
    state, text = trees.tree_state(cfg, "t")
    assert state == "wrong" and "dirty" in text


def test_west_env_has_no_zephyr_variables(monkeypatch):
    monkeypatch.setenv("ZEPHYR_BASE", "/x")
    env = trees.west_env()
    assert "ZEPHYR_BASE" not in env and env["WEST_CONFIG_GLOBAL"] == __import__("os").devnull


def test_the_pins_of_the_repo_load():
    cfg = trees.load(find_lab=False)
    assert next(iter(cfg["trees"])) == "ws-safety"
    assert cfg["toolchain"]["zephyr_sdk"]["version"] == "1.0.1"
    assert all("zephyr" in t["repos"] for t in cfg["trees"].values())


def test_lab_space_gives_the_paths(tmp_path, monkeypatch):
    from studylib import lab as labmod
    repo = tmp_path / "safety"
    (repo / "scripts" / "benchmarks").mkdir(parents=True)
    (repo / "scripts" / "benchmarks" / "study.py").write_text("")
    lab = labmod.init(tmp_path / "lab", repo, trees_source=tmp_path / "other", sdk="~/sdk-x")
    assert lab.id.startswith("lab-") and len(lab.id) == len("lab-") + 8
    assert lab.repo == repo.resolve() and lab.trees_root == tmp_path / "lab" / "trees"
    assert (tmp_path / "lab" / "results").is_dir()
    monkeypatch.chdir(tmp_path / "lab" / "results")
    monkeypatch.delenv("LATBENCH_TREES_ROOT", raising=False)
    found = labmod.find()
    assert found.folder == lab.folder
    cfg = trees.load()
    assert cfg["root"] == lab.trees_root and cfg["source_root"] == tmp_path / "other"
    assert cfg["toolchain"]["zephyr_sdk"]["path"] == str(Path("~/sdk-x").expanduser())
    monkeypatch.chdir(tmp_path)
    assert trees.load()["root"] is None


def test_owner_of_a_results_root_outside_the_lab(tmp_path, monkeypatch):
    from studylib import lab as labmod
    repo = tmp_path / "safety"
    (repo / "scripts" / "benchmarks").mkdir(parents=True)
    (repo / "scripts" / "benchmarks" / "study.py").write_text("")
    lab = labmod.init(tmp_path / "lab", repo, results=tmp_path / "data" / "results")
    deep = tmp_path / "data" / "results" / "top" / "st-a"
    deep.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    assert labmod.find(deep) is None and labmod.owner(deep).folder == lab.folder
    assert labmod.owner(tmp_path / "lab" / "trees").folder == lab.folder
    assert labmod.owner(tmp_path) is None
