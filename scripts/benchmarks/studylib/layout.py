# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Names and folders of the design tree and of the results tree.

A study path is a path of names, for example "load-scaling/t2t-under-load".
An instance path is a study path with "@<board>" on the name where the
board is fixed, for example "load-scaling@nucleo_g474re/t2t-under-load".
A run id is "<experiment>/<UTC>". Names and ids have no prefix; only the
folders have one: st-<name> for a study or an instance, ex-<name> for an
experiment. The top study has no folder of its own: it is the root of the
tree (validation/empirical/latencies, results/<top>).
"""

import re
from pathlib import Path

from trees import EXPERIMENT_PREFIX, STUDY_PREFIX  # noqa: F401

UTC_RE = re.compile(r"^\d{8}T\d{6}Z$")


def study_folder(path):
    """Folder of a study or instance path, relative to the root of its tree."""
    return Path(*(STUDY_PREFIX + n for n in path.split("/") if n)) if path else Path()


def run_folder(run_id):
    """Folder of a run id, relative to the folder of its instance."""
    exp, utc = run_id.split("/")
    return Path(EXPERIMENT_PREFIX + exp) / utc


def strip_board(instance_path):
    """The study path of an instance path."""
    return "/".join(n.split("@")[0] for n in instance_path.split("/") if n)


def board_suffix(instance_path):
    """The board name in the path ('' if no level of the path fixes a board)."""
    for n in instance_path.split("/"):
        if "@" in n:
            return n.split("@", 1)[1]
    return ""


def instance_path_of(folder, root):
    """The instance path of an instance folder below the results root."""
    rel = Path(folder).relative_to(root)
    names = []
    for part in rel.parts:
        if not part.startswith(STUDY_PREFIX):
            raise ValueError(f"{folder}: {part} is not a study folder (st-<name>)")
        names.append(part[len(STUDY_PREFIX):])
    return "/".join(names)


def run_id_of(run_dir):
    """The run id of a raw run folder <...>/ex-<experiment>/<UTC>."""
    run_dir = Path(run_dir)
    exp = run_dir.parent.name
    if not exp.startswith(EXPERIMENT_PREFIX) or not UTC_RE.match(run_dir.name):
        raise ValueError(f"{run_dir}: not a run folder ex-<experiment>/<UTC>")
    return f"{exp[len(EXPERIMENT_PREFIX):]}/{run_dir.name}"


def find_root(path):
    """The results root (the folder of the top instance) of a folder in a results tree."""
    path = Path(path).resolve()
    for p in [path, *path.parents]:
        if (p / "instance.json").is_file() and not p.name.startswith(STUDY_PREFIX):
            return p
    raise ValueError(f"{path} is not in a results tree (no top instance.json above it)")


def instance_folders(root):
    """All instance folders of a results tree, the root first, then sorted by path."""
    root = Path(root)
    found = [p.parent for p in root.rglob("instance.json")]
    return sorted(found, key=lambda p: (p != root, str(p.relative_to(root))))
