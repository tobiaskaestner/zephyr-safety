#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The pinned source trees of validation/trees/<tree>.yml (commands: study.py trees).

    study.py trees setup [TREE ...]   make the west workspace <trees root>/<tree>/ of each
                                      tree: the manifest copy, west init -l, west update
    study.py trees check [TREE ...]   the state of each tree: ok, not set up, or wrong
                                      (a repo not at its pin or dirty, another manifest copy)
    study.py trees show [TREE ...]    print the trees and their paths

Each tree is a west manifest in validation/trees/ (one file, one tree; the
pins of a tree never change). "setup" copies it to
<trees root>/<tree>/manifest/west.yml, runs "west init -l manifest" there and
"west update" with the cache <[trees] source of the lab>/<tree> (a plain
git clone of each project from the cache, else from its url). west runs
without the ZEPHYR_* variables of the caller and without the user and
system west configuration, and only after "west topdir" gives the tree
folder: a west command never acts on another workspace. The check before
a build is our own: each repo at its pinned revision and clean (no
untracked files), the pins of the manifest copy the same as those of the
repo file (the repo file may add a project, never change a pin).

The trees root and the SDK path come from the lab space (.lab/config), or
from --trees-root / LATBENCH_TREES_ROOT.
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
TREES_DIR = REPO_DIR / "validation" / "trees"
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


def manifest_file(tree):
    return TREES_DIR / f"{tree}.yml"


def read_manifest(path):
    """{description, zephyr_sdk, repos: {name: {path, url, rev, branch}}} of a tree manifest."""
    from west.manifest import MalformedManifest, validate
    data = yaml.safe_load(Path(path).read_text())
    try:
        validate(data)
    except MalformedManifest as e:
        raise TreeError(f"{path}: not a valid west manifest: {e}") from None
    m = data["manifest"]
    user = (m.get("self") or {}).get("userdata") or {}
    repos = {}
    for pr in m.get("projects", []):
        repos[pr["name"]] = {"path": pr.get("path", pr["name"]), "url": pr["url"], "rev": str(pr["revision"]),
                             **({"branch": pr["userdata"]["branch"]} if (pr.get("userdata") or {}).get("branch")
                                else {})}
    if not user.get("zephyr_sdk"):
        raise TreeError(f"{path}: no self.userdata.zephyr_sdk")
    return {"description": user.get("description", ""), "zephyr_sdk": str(user["zephyr_sdk"]),
            "manifest": str(Path(path).relative_to(REPO_DIR)) if Path(path).is_relative_to(REPO_DIR) else str(path),
            "repos": repos}


def load(trees_root=None, lab=None, find_lab=True):
    """The pins of validation/trees/*.yml with the paths of this host.

    root: --trees-root, LATBENCH_TREES_ROOT or the [trees] root of the lab
    space (None if there is none: then a tree path is an error). The SDK path:
    the [toolchain] of the lab space, else ~/zephyr-sdk-<version>. All trees
    must have the same SDK version (a lab space has one SDK).
    """
    trees_ = {f.stem: read_manifest(f) for f in sorted(TREES_DIR.glob("*.yml"), key=lambda f: f.stem)}
    versions = sorted({t["zephyr_sdk"] for t in trees_.values()})
    if len(versions) > 1:
        raise TreeError(f"the trees of {TREES_DIR} need the SDK versions {versions}; a lab space has one SDK")
    cfg = {"toolchain": {"zephyr_sdk": {"version": versions[0] if versions else None}}, "trees": trees_}
    if lab is None and find_lab:
        lab = labmod.find()
    root = trees_root or os.environ.get("LATBENCH_TREES_ROOT") or (lab.trees_root if lab else None)
    cfg["root"] = Path(root).expanduser() if root else None
    sdk = cfg["toolchain"]["zephyr_sdk"]
    if lab and lab.sdk:
        sdk["path"] = str(lab.sdk)
    else:
        sdk["path"] = f"~/zephyr-sdk-{sdk['version']}"
    cfg["source_root"] = lab.trees_source if lab else None
    cfg["lab"] = lab
    return cfg


def load_boards():
    from studylib import schema
    try:
        return schema.check("boards", yaml.safe_load(BOARDS_FILE.read_text()), BOARDS_FILE)
    except schema.SchemaError as e:
        raise TreeError(str(e)) from None


def board_repos(boards, board):
    """Return the repos of a tree that a build for board needs: zephyr and the board modules."""
    if board not in boards["boards"]:
        raise TreeError(f"unknown board '{board}', see {BOARDS_FILE}")
    return ["zephyr", *boards["boards"][board]["modules"]]


def check_tree_has(cfg, tree, repos):
    """Raise TreeError if the tree does not pin all of repos."""
    missing = [r for r in repos if r not in cfg["trees"][tree]["repos"]]
    if missing:
        raise TreeError(f"tree '{tree}' does not pin {missing}; pin them in a new tree in {TREES_DIR}")


def repo_dir(cfg, tree, repo):
    if cfg.get("root") is None:
        raise TreeError("no trees root: work in a lab space (study.py lab init) or give --trees-root")
    return cfg["root"] / tree / cfg["trees"][tree]["repos"][repo]["path"]


def repo_state(path):
    """Return (rev, dirty lines) of a git checkout."""
    rev = git("rev-parse", "HEAD", cwd=path)
    dirty = git("status", "--porcelain", "--untracked-files=all", cwd=path)
    return rev, dirty


def copy_differs(copy, repo_file):
    """Why the manifest copy of a workspace does not fit the repo file, or None.

    The repo file may add projects (a module for a new board); a pin of the copy must not
    change or go away.
    """
    if not copy.is_file() or not repo_file.is_file() or copy.read_bytes() == repo_file.read_bytes():
        return None
    try:
        old, new = read_manifest(copy)["repos"], read_manifest(repo_file)["repos"]
    except (TreeError, yaml.YAMLError, KeyError, TypeError) as e:
        return f"the manifest copy {copy} does not load: {e}"
    for name, r in old.items():
        if name not in new:
            return f"{repo_file} has no project {name} any more (the copy {copy} has it)"
        if (new[name]["rev"], new[name]["path"]) != (r["rev"], r["path"]):
            return (f"the pin of {name} in {repo_file} ({new[name]['rev'][:12]} at {new[name]['path']}) is not "
                    f"that of the copy {copy} ({r['rev'][:12]} at {r['path']}): pin a new tree instead")
    return None


class NotSetUp(TreeError):
    """A repo of the tree has no checkout yet (study.py trees setup makes it)."""


def check_tree(cfg, tree, repos=None):
    """Raise TreeError if a repo of the tree is missing (NotSetUp), not at its rev, or dirty, or if
    the manifest copy of the workspace differs from the repo file.

    repos: check only these repos (default: all repos of the tree).
    """
    if tree not in cfg["trees"]:
        raise TreeError(f"unknown tree '{tree}'")
    spec_t = cfg["trees"][tree]
    if spec_t.get("manifest") and cfg.get("root") is not None:
        why = copy_differs(cfg["root"] / tree / "manifest" / "west.yml", REPO_DIR / spec_t["manifest"])
        if why:
            raise TreeError(f"{tree}: {why}")
    for name, spec in spec_t["repos"].items():
        if repos is not None and name not in repos:
            continue
        path = repo_dir(cfg, tree, name)
        if not path.is_dir():
            raise NotSetUp(f"{tree}/{name}: {path} does not exist, run 'study.py trees setup {tree}'")
        rev, dirty = repo_state(path)
        if rev != spec["rev"]:
            raise TreeError(f"{tree}/{name}: {path} is at {rev}, pinned rev is {spec['rev']}")
        if dirty:
            raise TreeError(f"{tree}/{name}: {path} is dirty:\n{dirty}")


def tree_state(cfg, tree, repos=None):
    """("ok" | "not set up" | "wrong", text) of a tree."""
    try:
        check_tree(cfg, tree, repos)
        return "ok", ""
    except NotSetUp as e:
        return "not set up", str(e).splitlines()[0]
    except TreeError as e:
        return "wrong", str(e).splitlines()[0]


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


def west_env():
    """The environment of a west command: no ZEPHYR_* of the caller (ZEPHYR_BASE would lead west to
    another workspace), no user or system west configuration (it could add CMake arguments)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("ZEPHYR_") and k != "WEST_CONFIG_LOCAL"}
    env.update(WEST_CONFIG_GLOBAL=os.devnull, WEST_CONFIG_SYSTEM=os.devnull)
    return env


def west(args, cwd, check=True):
    r = subprocess.run([sys.executable, "-m", "west", *args], cwd=cwd, env=west_env(), capture_output=True,
                       text=True)
    if check and r.returncode != 0:
        raise TreeError(f"west {' '.join(args)} ({cwd}): {(r.stderr or r.stdout).strip()[-2000:]}")
    return r


def west_topdir(tdir):
    """The west workspace of the folder tdir; TreeError if it is not tdir itself."""
    r = west(["topdir"], tdir, check=False)
    top = r.stdout.strip()
    if r.returncode != 0 or Path(top).resolve() != Path(tdir).resolve():
        raise TreeError(f"west finds the workspace {top or '(none)'} from {tdir}, not {tdir}: "
                        f"{r.stderr.strip()[-300:]}")
    return Path(top)


def west_version():
    r = west(["--version"], REPO_DIR, check=False)
    return (r.stdout or r.stderr).strip().split()[-1] if r.returncode == 0 else None


def setup_tree(cfg, tree, log=print):
    """Make the west workspace of a tree (or complete it) and check it."""
    if cfg.get("root") is None:
        raise TreeError("no trees root: work in a lab space (study.py lab init) or give --trees-root")
    spec = cfg["trees"][tree]
    tdir = cfg["root"] / tree
    mdir = tdir / "manifest"
    mdir.mkdir(parents=True, exist_ok=True)
    src = REPO_DIR / spec["manifest"]
    copy = mdir / "west.yml"
    why = copy_differs(copy, src)
    if why:
        raise TreeError(f"{tree}: {why}")
    copy.write_bytes(src.read_bytes())       # the same pins (and maybe a new project)
    if not (tdir / ".west").is_dir():
        west(["init", "-l", "manifest"], tdir)
        log(f"{tree}: west workspace {tdir}")
    west_topdir(tdir)
    cache = Path(cfg["source_root"]) / tree if cfg.get("source_root") else None
    had = {name for name, r in spec["repos"].items() if (tdir / r["path"]).is_dir()}
    args = ["update"] + (["--path-cache", str(cache)] if cache and cache.is_dir() else [])
    west(args, tdir)
    for name, r in spec["repos"].items():
        src = ("there before" if name in had else f"from {cache}" if cache and (cache / r["path"]).is_dir()
               else f"from {r['url']}")
        log(f"{tree}/{name}: {r['rev'][:12]} ({src})")
    check_tree(cfg, tree)


def main(args, log=print):
    """study.py trees: setup, check or show (args: cmd, trees, trees_root); return the exit code."""
    cfg = load(args.trees_root)
    names = args.trees or list(cfg["trees"])
    for t in names:
        if t not in cfg["trees"]:
            raise TreeError(f"unknown tree '{t}' (the trees: {', '.join(cfg['trees'])})")
    if args.cmd == "setup":
        for t in names:
            setup_tree(cfg, t, log=log)
        return 0
    if args.cmd == "check":
        bad = 0
        try:
            log(f"zephyr sdk {cfg['toolchain']['zephyr_sdk']['version']}: {check_toolchain(cfg)}")
        except TreeError as e:
            log(f"error: {e}")
            bad += 1
        for t in names:
            state, text = tree_state(cfg, t)
            # a tree that this lab space never set up is information, unless it was asked for by name
            wrong = state == "wrong" or (state == "not set up" and bool(args.trees))
            log(f"{'error: ' if wrong else ''}{t}: {state}" + (f" ({text})" if text else ""))
            bad += wrong
        return 1 if bad else 0
    log(f"trees root: {cfg['root']}")
    for t in names:
        log(f"{t}: {cfg['trees'][t]['description']} ({cfg['trees'][t]['manifest']})")
        for name, spec in cfg["trees"][t]["repos"].items():
            log(f"  {name:10} {spec['rev'][:12]}  {repo_dir(cfg, t, name) if cfg['root'] else '-'}")
    return 0


if __name__ == "__main__":
    sys.exit("trees.py has no commands of its own: use scripts/benchmarks/study.py trees setup|check|show")
