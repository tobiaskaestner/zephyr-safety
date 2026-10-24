#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Create and check the pinned source trees of trees.yaml.

    trees.py setup [TREE ...]   create the missing worktrees at their pinned rev
    trees.py check [TREE ...]   check that each worktree is at its rev and clean
    trees.py show               print the trees and their worktree paths
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml

BENCH_DIR = Path(__file__).resolve().parent.parent
TREES_FILE = BENCH_DIR / "trees.yaml"


class TreeError(Exception):
    pass


def git(*args, cwd=None, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise TreeError(f"git {' '.join(args)} ({cwd}): {r.stderr.strip()}")
    return r.stdout.strip()


def load(trees_root=None):
    cfg = yaml.safe_load(TREES_FILE.read_text())
    root = trees_root or os.environ.get("LATBENCH_TREES_ROOT") or cfg["root"]
    cfg["root"] = Path(root).expanduser()
    return cfg


def repo_dir(cfg, tree, repo):
    return cfg["root"] / tree / cfg["trees"][tree]["repos"][repo]["path"]


def repo_state(path):
    """Return (rev, dirty lines) of a git checkout."""
    rev = git("rev-parse", "HEAD", cwd=path)
    dirty = git("status", "--porcelain", "--untracked-files=all", cwd=path)
    return rev, dirty


def check_tree(cfg, tree):
    """Raise TreeError if a repo of the tree is missing, not at its rev, or dirty."""
    if tree not in cfg["trees"]:
        raise TreeError(f"unknown tree '{tree}'")
    for name, spec in cfg["trees"][tree]["repos"].items():
        path = repo_dir(cfg, tree, name)
        if not path.is_dir():
            raise TreeError(f"{tree}/{name}: {path} does not exist, run 'trees.py setup {tree}'")
        rev, dirty = repo_state(path)
        if rev != spec["rev"]:
            raise TreeError(f"{tree}/{name}: {path} is at {rev}, pinned rev is {spec['rev']}")
        if dirty:
            raise TreeError(f"{tree}/{name}: {path} is dirty:\n{dirty}")


def check_toolchain(cfg):
    sdk = cfg["toolchain"]["zephyr_sdk"]
    path = Path(sdk["path"]).expanduser()
    version_file = path / "sdk_version"
    if not version_file.is_file():
        raise TreeError(f"Zephyr SDK not found at {path}")
    version = version_file.read_text().strip()
    if version != str(sdk["version"]):
        raise TreeError(f"Zephyr SDK at {path} is {version}, pinned version is {sdk['version']}")
    return path


def setup_tree(cfg, tree):
    for name, spec in cfg["trees"][tree]["repos"].items():
        path = repo_dir(cfg, tree, name)
        if path.exists():
            print(f"{tree}/{name}: exists ({path})")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        source = Path(spec.get("source", "")).expanduser()
        if spec.get("source") and source.is_dir():
            if git("cat-file", "-t", spec["rev"], cwd=source, check=False) != "commit":
                git("fetch", spec["url"], spec.get("branch", spec["rev"]), cwd=source)
            git("worktree", "add", "--detach", str(path), spec["rev"], cwd=source)
            print(f"{tree}/{name}: worktree of {source} at {spec['rev'][:12]}")
        else:
            git("clone", "--no-checkout", spec["url"], str(path))
            git("checkout", "--detach", spec["rev"], cwd=path)
            print(f"{tree}/{name}: clone of {spec['url']} at {spec['rev'][:12]}")
    check_tree(cfg, tree)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--trees-root")
    p.add_argument("cmd", choices=["setup", "check", "show"])
    p.add_argument("trees", nargs="*")
    args = p.parse_args()

    cfg = load(args.trees_root)
    trees = args.trees or list(cfg["trees"])
    try:
        if args.cmd == "setup":
            for t in trees:
                setup_tree(cfg, t)
        elif args.cmd == "check":
            check_toolchain(cfg)
            for t in trees:
                check_tree(cfg, t)
                print(f"{t}: ok")
        else:
            for t in trees:
                print(f"{t}: {cfg['trees'][t]['description']}")
                for name, spec in cfg["trees"][t]["repos"].items():
                    print(f"  {name:10} {spec['rev'][:12]}  {repo_dir(cfg, t, name)}")
    except TreeError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
