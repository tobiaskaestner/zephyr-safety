#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The pinned source trees of validation/trees.yaml (commands: study.py trees).

    study.py trees setup [TREE ...]   create the missing checkouts at their pinned rev
    study.py trees setup --clone-source [TREE ...]
                                      clone each source repo instead of adding a
                                      worktree to it: nothing is written into the
                                      source (on a host where the source is a repo
                                      of another workspace that must stay as it is)
    study.py trees check [TREE ...]   check that each checkout is at its rev and clean
    study.py trees show               print the trees and their paths

The trees root and the SDK path come from the lab space (.lab/config), or
from --trees-root / LATBENCH_TREES_ROOT. A clone source is, in this order:
<[trees] source of the lab>/<tree>/<path>, the "source" of the repo in
trees.yaml, its "url".
"""

import os
import subprocess
import sys
from pathlib import Path

import yaml

from studylib import lab as labmod

# The safety repo, the folder of the benchmark apps and the folder of the
# latency studies. Each experiment is a folder ex-<name>/ with
# experiment.yaml and experiment.md, in the folder of the study that owns
# it. Each sub-study is a folder st-<name>/ with study.yaml. The prefixes
# are only in the folder names: names and references have none.
REPO_DIR = Path(__file__).resolve().parents[2]
BENCH_DIR = REPO_DIR / "tests" / "benchmarks"
STUDIES_DIR = REPO_DIR / "validation" / "empirical" / "latencies"
EXPERIMENT_FILE = "experiment.yaml"
EXPERIMENT_PREFIX = "ex-"
STUDY_PREFIX = "st-"
TREES_FILE = REPO_DIR / "validation" / "trees.yaml"
BOARDS_FILE = BENCH_DIR / "boards.yaml"


class TreeError(Exception):
    pass


def experiment_files():
    """All experiment files of the studies, sorted by path."""
    return sorted(STUDIES_DIR.rglob(EXPERIMENT_FILE))


def study_dir(path):
    """The folder of a study from its path of names, e.g. "load-scaling/t2t-under-load"."""
    return STUDIES_DIR.joinpath(*(STUDY_PREFIX + n for n in path.split("/") if n))


def experiment_file(name):
    """The experiment file of the experiment name. The names are unique over all studies."""
    found = [p for p in experiment_files() if p.parent.name == EXPERIMENT_PREFIX + name]
    if len(found) != 1:
        raise TreeError(f"experiment '{name}': {len(found)} files {[str(p) for p in found]}")
    return found[0]


def git(*args, cwd=None, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise TreeError(f"git {' '.join(args)} ({cwd}): {r.stderr.strip()}")
    return r.stdout.strip()


def load(trees_root=None, lab=None, find_lab=True):
    """The pins of trees.yaml with the paths of this host.

    root: --trees-root, LATBENCH_TREES_ROOT or the [trees] root of the lab
    space (None if there is none: then a tree path is an error). The SDK path:
    the [toolchain] of the lab space, else ~/zephyr-sdk-<version>.
    """
    cfg = yaml.safe_load(TREES_FILE.read_text())
    if lab is None and find_lab:
        lab = labmod.find()
    root = trees_root or os.environ.get("LATBENCH_TREES_ROOT") or (lab.trees_root if lab else None)
    cfg["root"] = Path(root).expanduser() if root else None
    sdk = cfg["toolchain"]["zephyr_sdk"]
    if lab and lab.sdk:
        sdk["path"] = str(lab.sdk)
    elif not sdk.get("path"):
        sdk["path"] = f"~/zephyr-sdk-{sdk['version']}"
    cfg["source_root"] = lab.trees_source if lab else None
    cfg["lab"] = lab
    return cfg


def load_boards():
    return yaml.safe_load(BOARDS_FILE.read_text())


def board_repos(boards, board):
    """Return the repos of a tree that a build for board needs: zephyr and the board modules."""
    if board not in boards["boards"]:
        raise TreeError(f"unknown board '{board}', see {BOARDS_FILE}")
    return ["zephyr", *boards["boards"][board]["modules"]]


def check_tree_has(cfg, tree, repos):
    """Raise TreeError if the tree does not pin all of repos."""
    missing = [r for r in repos if r not in cfg["trees"][tree]["repos"]]
    if missing:
        raise TreeError(f"tree '{tree}' does not pin {missing}; add them to {TREES_FILE}")


def repo_dir(cfg, tree, repo):
    if cfg.get("root") is None:
        raise TreeError("no trees root: work in a lab space (study.py lab init) or give --trees-root")
    return cfg["root"] / tree / cfg["trees"][tree]["repos"][repo]["path"]


def repo_state(path):
    """Return (rev, dirty lines) of a git checkout."""
    rev = git("rev-parse", "HEAD", cwd=path)
    dirty = git("status", "--porcelain", "--untracked-files=all", cwd=path)
    return rev, dirty


def check_tree(cfg, tree, repos=None):
    """Raise TreeError if a repo of the tree is missing, not at its rev, or dirty.

    repos: check only these repos (default: all repos of the tree).
    """
    if tree not in cfg["trees"]:
        raise TreeError(f"unknown tree '{tree}'")
    for name, spec in cfg["trees"][tree]["repos"].items():
        if repos is not None and name not in repos:
            continue
        path = repo_dir(cfg, tree, name)
        if not path.is_dir():
            raise TreeError(f"{tree}/{name}: {path} does not exist, run 'study.py trees setup {tree}'")
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


def setup_tree(cfg, tree, clone_source=False):
    for name, spec in cfg["trees"][tree]["repos"].items():
        path = repo_dir(cfg, tree, name)
        if path.exists():
            print(f"{tree}/{name}: exists ({path})")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        source = Path(spec.get("source", "")).expanduser() if spec.get("source") else None
        lab_source = cfg.get("source_root") and Path(cfg["source_root"]) / tree / spec["path"]
        if lab_source and (lab_source / ".git").exists():
            source = lab_source
        has_source = source is not None and source.is_dir()
        if clone_source and has_source:
            # A local clone hardlinks the objects and writes nothing into the source.
            git("clone", "--no-checkout", str(source), str(path))
            git("remote", "set-url", "origin", spec["url"], cwd=path)
            if git("cat-file", "-t", spec["rev"], cwd=path, check=False) != "commit":
                git("fetch", spec["url"], spec.get("branch", spec["rev"]), cwd=path)
            git("checkout", "--detach", spec["rev"], cwd=path)
            print(f"{tree}/{name}: clone of {source} at {spec['rev'][:12]}")
        elif has_source:
            if git("cat-file", "-t", spec["rev"], cwd=source, check=False) != "commit":
                git("fetch", spec["url"], spec.get("branch", spec["rev"]), cwd=source)
            git("worktree", "add", "--detach", str(path), spec["rev"], cwd=source)
            print(f"{tree}/{name}: worktree of {source} at {spec['rev'][:12]}")
        else:
            git("clone", "--no-checkout", spec["url"], str(path))
            git("checkout", "--detach", spec["rev"], cwd=path)
            print(f"{tree}/{name}: clone of {spec['url']} at {spec['rev'][:12]}")
    check_tree(cfg, tree)


def main(args, log=print):
    """study.py trees: setup, check or show (args: cmd, trees, trees_root, clone_source)."""
    cfg = load(args.trees_root)
    names = args.trees or list(cfg["trees"])
    if args.cmd == "setup":
        for t in names:
            setup_tree(cfg, t, clone_source=args.clone_source)
    elif args.cmd == "check":
        log(f"zephyr sdk {cfg['toolchain']['zephyr_sdk']['version']}: {check_toolchain(cfg)}")
        for t in names:
            check_tree(cfg, t)
            log(f"{t}: ok")
    else:
        log(f"trees root: {cfg['root']}")
        for t in names:
            log(f"{t}: {cfg['trees'][t]['description']}")
            for name, spec in cfg["trees"][t]["repos"].items():
                log(f"  {name:10} {spec['rev'][:12]}  {repo_dir(cfg, t, name) if cfg['root'] else '-'}")


if __name__ == "__main__":
    sys.exit("trees.py has no commands of its own: use scripts/benchmarks/study.py trees setup|check|show")
