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


def config(tmp_path, src, rev):
    return {
        "root": tmp_path / "latency-trees",
        "trees": {"t": {"repos": {"zephyr": {
            "path": "zephyr", "url": "https://example.invalid/zephyr", "branch": "main",
            "rev": rev, "source": str(src)}}}},
    }


def test_setup_clone_source_writes_nothing_into_the_source(tmp_path):
    src, rev = make_source(tmp_path)
    before = files(src)
    cfg = config(tmp_path, src, rev)
    trees.setup_tree(cfg, "t", clone_source=True)
    path = trees.repo_dir(cfg, "t", "zephyr")
    assert files(src) == before
    assert git("rev-parse", "HEAD", cwd=path) == rev
    assert git("remote", "get-url", "origin", cwd=path) == "https://example.invalid/zephyr"
    assert not (path / ".git" / "objects" / "info" / "alternates").exists()
    assert (path / "a.txt").read_text() == "1\n"


def test_setup_worktree_writes_into_the_source(tmp_path):
    """The default: a worktree of the source (it adds .git/worktrees there)."""
    src, rev = make_source(tmp_path)
    cfg = config(tmp_path, src, rev)
    trees.setup_tree(cfg, "t")
    assert (src / ".git" / "worktrees").is_dir()
    assert git("rev-parse", "HEAD", cwd=trees.repo_dir(cfg, "t", "zephyr")) == rev
