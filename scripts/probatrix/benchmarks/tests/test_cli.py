# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The command line of study.py: each command is in a namespace."""

from pathlib import Path

import pytest


from probatrix.benchmarks import study  # noqa: E402

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
    ["analysis", "notebooks", "r", "--force"],
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


def subcommands(parser, prefix=()):
    """The full command paths of a parser, for example ("design", "scaffold", "study")."""
    import argparse
    out = []
    for a in parser._actions:
        if isinstance(a, argparse._SubParsersAction):
            for name, sub in a.choices.items():
                deeper = subcommands(sub, prefix + (name,))
                out += deeper or [prefix + (name,)]
    return out


def test_the_reference_names_each_command():
    """doc/benchmark-guide/reference/cli/study-py.rst has a synopsis line for each command of study.py."""
    page = (Path(study.__file__).resolve().parents[3] / "doc" / "benchmark-guide" / "reference" / "cli"
            / "study-py.rst").read_text()
    cmds = subcommands(study.parser())
    assert len(cmds) > 25
    missing = [" ".join(c) for c in cmds
               if f"study.py {' '.join(c)}" not in page and not (c[0] == "trees" and "study.py trees setup" in page)]
    assert missing == [], f"not in the reference: {missing}"


# ------------------------------------------------------------------ R7: the dispatcher and the launchers
def test_the_kind_gives_its_commands_in_the_old_order():
    from probatrix.benchmarks import kind as benchkind
    assert list(benchkind.KIND.commands()) == ["design", "lab", "campaign", "trees", "instance", "analysis"]


def test_the_parser_of_the_dispatcher_is_the_parser_of_study_py():
    from probatrix.core import cli
    assert subcommands(cli.parser()) == subcommands(study.parser())


def test_made_by_tool():
    from probatrix.benchmarks import kind as benchkind
    assert benchkind.KIND.tool == "scripts/probatrix/study.py"


@pytest.mark.parametrize("launcher", ["study.py", "benchmarks/study.py"])
def test_the_launchers_and_python_m_give_the_same_help(launcher):
    import subprocess
    import sys
    scripts = Path(study.__file__).resolve().parents[2]
    run = [sys.executable, str(scripts / "probatrix" / launcher), "design", "--help"]
    a = subprocess.run(run, capture_output=True, text=True, cwd="/")
    assert a.returncode == 0 and "usage: study.py design" in a.stdout
    b = subprocess.run([sys.executable, "-m", "probatrix", "design", "--help"], capture_output=True, text=True,
                       cwd=str(scripts))
    assert b.returncode == 0 and b.stdout.replace("probatrix design", "study.py design") == a.stdout
