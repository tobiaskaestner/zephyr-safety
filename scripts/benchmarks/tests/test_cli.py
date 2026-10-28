# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The command line of study.py: each command is in a namespace."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import study  # noqa: E402

COMMANDS = [
    ["design", "lint"],
    ["design", "scaffold", "study", "x/st-a"],
    ["design", "scaffold", "experiment", "x/ex-a", "--app", "irq_latency"],
    ["lab", "status"],
    ["campaign", "check", "x"],
    ["trees", "check"],
    ["instance", "seal", "r"],
    ["instance", "verify", "r"],
    ["analysis", "build", "r"],
    ["analysis", "check", "r"],
    ["analysis", "show", "r", "--details"],
    ["analysis", "missing"],
    ["instance", "exclude", "r", "--campaign", "c", "--reason", "x"],
    ["analysis", "html", "r"],
]


@pytest.mark.parametrize("argv", COMMANDS, ids=" ".join)
def test_commands_parse(argv):
    assert callable(study.parser().parse_args(argv).func)


@pytest.mark.parametrize("old", ["lint", "scaffold", "seal", "verify", "build", "check", "show", "html"])
def test_no_top_level_command_outside_a_namespace(old):
    with pytest.raises(SystemExit):
        study.parser().parse_args([old, "x"])
