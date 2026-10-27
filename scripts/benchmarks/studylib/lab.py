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
"""

import configparser
import os
import secrets
from pathlib import Path

CONFIG = Path(".lab") / "config"


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
    def hw_map(self):
        return self._path("hardware", "map", "hw-map.yml")

    @property
    def build_cache(self):
        return self.folder / ".lab" / "build-cache"

    @property
    def campaigns(self):
        return self.folder / ".lab" / "campaigns"

    @property
    def lock(self):
        return self.folder / ".lab" / "campaign.lock"

    def describe(self):
        return {"id": self.id, "name": self.name, "folder": str(self.folder)}


def find(start=None):
    """The lab space that holds start (default: the current folder), or None."""
    start = Path(start or os.getcwd()).resolve()
    for p in [start, *start.parents]:
        if (p / CONFIG).is_file():
            return Lab(p)
    return None


def require(start=None):
    lab = find(start)
    if lab is None:
        raise LabError(f"{Path(start or os.getcwd()).resolve()} is not in a lab space (make one with "
                       f"'study.py lab init <folder> --repo <safety repo>')")
    return lab


def init(folder, repo, name=None, trees_root=None, trees_source=None, sdk=None, results=None, hw_map=None):
    """Make the lab space folder (with .lab/config, results/ and trees/); return the Lab."""
    folder = Path(folder).resolve()
    if (folder / CONFIG).exists():
        raise LabError(f"{folder} is a lab space already ({folder / CONFIG})")
    repo = Path(repo).expanduser().resolve()
    if not (repo / "scripts" / "benchmarks" / "study.py").is_file():
        raise LabError(f"{repo} is not a safety repo (no scripts/benchmarks/study.py)")
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
    (folder / ".lab").mkdir(parents=True)
    with open(folder / CONFIG, "w") as f:
        f.write("# The lab space (scripts/benchmarks/studylib/lab.py). Made by study.py lab init.\n")
        cfg.write(f)
    lab = Lab(folder)
    lab.results.mkdir(parents=True, exist_ok=True)
    lab.trees_root.mkdir(parents=True, exist_ok=True)
    return lab
