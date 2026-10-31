# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The lab space: a folder with .lab/config, like a west workspace with .west/config.

A lab space joins the things of one host that a study needs and that the
repo must not hold: the design repo (study designs and tools), the pinned
trees, the Zephyr SDK, the results tree, the hardware map, the build cache
and the campaign records. The tools find it from the current folder
upwards. .lab/config is an INI file; a relative path is relative to the
lab folder:

    [lab]
    id = lab-smoke-3f9a1c2e         name + random part, set once by "lab init"
    name = lab-smoke
    [design]
    repo = safety                   the safety repo (designs and tools)
    [trees]
    root = trees                    the pinned trees (study.py trees setup)
    source = /path/of/other/trees   optional: <tree>/<path> clones to clone from
    [toolchain]
    zephyr_sdk = ~/zephyr-sdk-1.0.1
    [results]
    root = results
    [hardware]
    map = hw-map.yml                the hardware map of the host (twister format)
    [python]
    venv = .venv                    the virtual environment that study.py runs in

The setup order: make the lab folder, clone the safety repo into it, make
a virtual environment with scripts/probatrix/benchmarks/requirements.lock of that
repo (the exact versions; requirements.txt has the ranges), then run "study.py lab init --repo <clone>" with the Python of that
environment, in the lab folder. lab init records the environment; every
study.py of the lab space then runs with its Python (see study.py).
"""

import configparser
import os
import secrets
import sys
from pathlib import Path

CONFIG = Path(".lab") / "config"
# In a results root outside the lab folder: a file with the path of the lab folder.
RESULTS_MARK = ".lab-space"
# The launcher of a design repo, newest layout first. A lab space can hold an old clone, so the
# tools look for each of them in this order: the layout of the package probatrix, the layout
# before the top launcher, the layout of 98b1afe and before. This is the one place of the list.
LAUNCHERS = ("scripts/probatrix/study.py", "scripts/probatrix/benchmarks/study.py", "scripts/benchmarks/study.py")
# The folders of requirements*.txt and requirements.lock in a design repo, newest layout first.
REQUIREMENTS_DIRS = ("scripts/probatrix/benchmarks", "scripts/benchmarks")
# The variable that stops a second re-exec (the study.py of 98b1afe uses the same name).
REEXEC_ENV = "LATBENCH_STUDY_REEXEC"


class LabError(Exception):
    pass


class Lab:
    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        self.config_file = self.folder / CONFIG
        self.cfg = configparser.ConfigParser()
        self.cfg.read(self.config_file)

    def _path(self, section, key, default=None):
        v = self.cfg.get(section, key, fallback=None)
        if v is None:
            return None if default is None else self.folder / default
        p = Path(v).expanduser()
        return p if p.is_absolute() else self.folder / p

    @property
    def id(self):
        return self.cfg.get("lab", "id")

    @property
    def name(self):
        return self.cfg.get("lab", "name", fallback=self.folder.name)

    @property
    def repo(self):
        p = self._path("design", "repo")
        if p is None:
            raise LabError(f"{self.config_file}: no [design] repo")
        return p

    @property
    def trees_root(self):
        return self._path("trees", "root", "trees")

    @property
    def trees_source(self):
        return self._path("trees", "source")

    @property
    def sdk(self):
        return self._path("toolchain", "zephyr_sdk")

    @property
    def results(self):
        return self._path("results", "root", "results")

    @property
    def venv(self):
        return self._path("python", "venv")

    @property
    def python(self):
        """The Python of the lab space (of its venv), or None."""
        v = self.venv
        if v is None:
            return None
        return v / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    @property
    def hw_map(self):
        return self._path("hardware", "map", "hw-map.yml")

    @property
    def build_cache(self):
        return self.folder / ".lab" / "build-cache"

    @property
    def campaigns(self):
        return self.folder / ".lab" / "campaigns"

    @property
    def locks(self):
        return self.folder / ".lab" / "locks"

    def describe(self):
        return {"id": self.id, "name": self.name, "folder": str(self.folder)}


def find(start=None):
    """The lab space that holds start (default: the current folder), or None."""
    start = Path(start or os.getcwd()).resolve()
    for p in [start, *start.parents]:
        if (p / CONFIG).is_file():
            return Lab(p)
    return None


def owner(path):
    """The lab space that owns path: the lab folder above it, or the lab space whose results root
    holds it (the mark file RESULTS_MARK in that root). Not the current folder: the answer must not
    depend on where a tool starts."""
    path = Path(path).resolve()
    for p in [path, *path.parents]:
        if (p / CONFIG).is_file():
            return Lab(p)
        mark = p / RESULTS_MARK
        if mark.is_file():
            folder = Path(mark.read_text().strip())
            if (folder / CONFIG).is_file():
                return Lab(folder)
    return None


def require(start=None):
    lab = find(start)
    if lab is None:
        raise LabError(f"{Path(start or os.getcwd()).resolve()} is not in a lab space (make one with "
                       f"'study.py lab init <folder> --repo <safety repo>')")
    return lab


def restart_with_lab_python(script, argv, env_var="LATBENCH_PYTHON_RESTART"):
    """Start script again with the Python of the lab space of the current folder (its venv), if this
    Python is another one. Only the standard library is needed here: the caller has not imported
    PyYAML yet."""
    if os.environ.get(env_var):
        return
    lab = find()
    if lab is None or lab.venv is None:
        return
    if Path(sys.prefix).resolve() == lab.venv.resolve():
        return
    if not lab.python.exists():
        sys.exit(f"error: the lab space {lab.folder} has the Python environment {lab.venv}, which has no {lab.python}")
    os.environ[env_var] = "1"
    os.execv(str(lab.python), [str(lab.python), str(script), *argv])


def launcher_of(repo):
    """The first launcher of LAUNCHERS that the design repo has (a Path), or None."""
    for rel in LAUNCHERS:
        f = Path(repo) / rel
        if f.is_file():
            return f
    return None


def launchers_text(repo):
    """The three launcher paths of repo, for an error text."""
    a, b, c = (Path(repo) / rel for rel in LAUNCHERS)
    return f"{a}, {b} or {c}"


def reexec_in_lab_repo(argv, script):
    """Run the launcher of the design repo of the lab space with the Python of the lab space (its
    venv, [python] of .lab/config), if this is another launcher or another Python. script is the
    launcher that calls this function. Only the standard library is needed here."""
    if os.environ.get(REEXEC_ENV) or (argv[:2] == ["lab", "init"]):
        return
    lab = find()
    if lab is None:
        return
    target = launcher_of(lab.repo)
    python = lab.python
    # a venv Python is a link to the base Python: compare the environments, not the files
    same_python = python is None or (lab.venv is not None and Path(sys.prefix).resolve() == lab.venv.resolve())
    if target is not None and target.resolve() == Path(script).resolve() and same_python:
        return
    if target is None:
        sys.exit(f"error: the lab space {lab.folder} has the design repo {lab.repo}, which has none of "
                 f"{launchers_text(lab.repo)}")
    if python is not None and not python.exists():
        sys.exit(f"error: the lab space {lab.folder} has the Python environment {lab.venv}, which has no {python}")
    exe = str(python) if python is not None else sys.executable
    os.environ[REEXEC_ENV] = str(Path(script).resolve())
    os.execv(exe, [exe, str(target), *argv])


def in_venv():
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def requirements(repo, name="requirements.txt"):
    """[(name, specifier text)] of <name> in the first folder of REQUIREMENTS_DIRS of a repo that has it
    (no comments)."""
    import re
    f = Path(repo) / REQUIREMENTS_DIRS[0] / name
    for d in REQUIREMENTS_DIRS:
        if (Path(repo) / d / name).is_file():
            f = Path(repo) / d / name
            break
    out = []
    for ln in f.read_text().splitlines() if f.is_file() else []:
        ln = ln.split("#", 1)[0].strip()
        m = re.match(r"^([A-Za-z0-9_.-]+)\s*(.*)$", ln)
        if m:
            out.append((m.group(1), m.group(2).strip()))
    return out


def packages(repo):
    """{name: installed version or None} of the packages of requirements.txt and requirements.lock
    (also the build packages of Zephyr), in this Python."""
    from importlib import metadata
    out = {}
    for name, _ in requirements(repo) + requirements(repo, "requirements.lock"):
        if name in out:
            continue
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = None
    return dict(sorted(out.items()))


def package_problems(repo):
    """The packages of this Python that are missing, out of the range of requirements.txt, or not
    at the version of requirements.lock, as text."""
    have = packages(repo)
    out = []
    try:
        from packaging.specifiers import SpecifierSet
    except ImportError:
        SpecifierSet = None
    for fname in ("requirements.txt", "requirements.lock"):
        for name, spec in requirements(repo, fname):
            v = have.get(name)
            if v is None:
                out.append(f"{name}: not installed ({fname}: {name}{spec})")
            elif spec and SpecifierSet is not None and v not in SpecifierSet(spec):
                out.append(f"{name}: {v} does not meet {spec} ({fname})")
    return list(dict.fromkeys(out))


def init(folder, repo, name=None, trees_root=None, trees_source=None, sdk=None, results=None, hw_map=None):
    """Make the lab space folder (with .lab/config, results/ and trees/); return the Lab.

    The Python that runs lab init is the Python of the lab space: its venv goes into [python].
    """
    folder = Path(folder).resolve()
    if (folder / CONFIG).exists():
        raise LabError(f"{folder} is a lab space already ({folder / CONFIG})")
    repo = Path(repo).expanduser().resolve()
    if launcher_of(repo) is None:
        raise LabError(f"{repo} is not a safety repo (no {', '.join(LAUNCHERS[:-1])} or {LAUNCHERS[-1]})")
    name = name or folder.name
    cfg = configparser.ConfigParser()

    def rel(p):
        p = Path(p).expanduser().resolve()
        return str(p.relative_to(folder)) if p.is_relative_to(folder) else str(p)

    cfg["lab"] = {"id": f"{name}-{secrets.token_hex(4)}", "name": name}
    cfg["design"] = {"repo": rel(repo)}
    cfg["trees"] = {"root": rel(trees_root) if trees_root else "trees"}
    if trees_source:
        cfg["trees"]["source"] = rel(trees_source)
    if sdk:
        cfg["toolchain"] = {"zephyr_sdk": str(sdk)}
    cfg["results"] = {"root": rel(results) if results else "results"}
    cfg["hardware"] = {"map": rel(hw_map) if hw_map else "hw-map.yml"}
    if in_venv():
        cfg["python"] = {"venv": rel(sys.prefix)}
    (folder / ".lab").mkdir(parents=True)
    with open(folder / CONFIG, "w") as f:
        f.write("# The lab space (scripts/probatrix/benchmarks/studylib/lab.py). Made by study.py lab init.\n")
        cfg.write(f)
    lab = Lab(folder)
    lab.results.mkdir(parents=True, exist_ok=True)
    if not lab.results.resolve().is_relative_to(folder):
        (lab.results / RESULTS_MARK).write_text(f"{folder}\n")
    lab.trees_root.mkdir(parents=True, exist_ok=True)
    return lab
