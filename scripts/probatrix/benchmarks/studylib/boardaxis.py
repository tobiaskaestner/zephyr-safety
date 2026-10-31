# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The board axis of an instance path: "<study>@<board>/<sub-study>".

A benchmark instance has the board in its folder name (st-x@nucleo_g474re). Other kinds
have no such axis, so the rule is here and not in core/layout.py.
"""


def strip_board(instance_path):
    """The study path of an instance path."""
    return "/".join(n.split("@")[0] for n in instance_path.split("/") if n)


def board_suffix(instance_path):
    """The board name in the path ('' if no level of the path fixes a board)."""
    for n in instance_path.split("/"):
        if "@" in n:
            return n.split("@", 1)[1]
    return ""
