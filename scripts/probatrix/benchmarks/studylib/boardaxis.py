# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The board axis of an instance: "<study>@<board>/<sub-study>".

A benchmark instance has the board in its folder name (st-x@nucleo_g474re). Other kinds
have no such axis, so the rules are here and not in core. This module owns all three:
the folder name (folder_name, strip_board, board_suffix), the board of an instance
folder (board_of: instance.json "board", looked up in the folder and its parents) and the
key of the board lock (lock_key). The latbench Kind gives them out as its instance_axis.
"""

import json
from pathlib import Path


def base_name(name):
    """One folder or path name without the board: "x@board" gives "x" (a "st-" prefix stays)."""
    return name.split("@")[0]


def fixes_board(name):
    """Whether this name of an instance path (or folder) fixes a board."""
    return "@" in name


def strip_board(instance_path):
    """The study path of an instance path."""
    return "/".join(base_name(n) for n in instance_path.split("/") if n)


def board_suffix(instance_path):
    """The board name in the path ('' if no level of the path fixes a board)."""
    for n in instance_path.split("/"):
        if fixes_board(n):
            return n.split("@", 1)[1]
    return ""


def folder_name(study_name, port, prefix=""):
    """The folder name of a study that fixes a board: <prefix><study>@<port>."""
    return f"{prefix}{study_name}@{port}"


def board_of(folder):
    """The board that this instance or a parent instance fixes, or None."""
    folder = Path(folder).resolve()
    for p in [folder, *folder.parents]:
        f = p / "instance.json"
        if not f.is_file():
            break
        b = json.loads(f.read_text()).get("board")
        if b:
            return b
    return None


def lock_key(board):
    """The part of a board name that goes into a file name (the lock board-<key>.lock, the hwcheck tag)."""
    return board.replace("/", "_").replace("@", "_")
