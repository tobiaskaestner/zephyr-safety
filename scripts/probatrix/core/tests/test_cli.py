# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The dispatcher of core/cli.py with fake kinds (no benchmarks import)."""

from types import SimpleNamespace

import pytest

from probatrix.core import cli, kinds
from probatrix.core.errors import SealError


@pytest.fixture
def empty(monkeypatch):
    monkeypatch.setattr(kinds, "_KINDS", {})
    monkeypatch.setattr(kinds, "PLUGINS", {})


def kind(name, cmds, **extra):
    return kinds.register(SimpleNamespace(name=name, dirt_paths=(), commands=lambda: cmds, **extra))


def adder(command, func):
    def add(sub):
        s = sub.add_parser(command, help=f"the command {command}")
        s.add_argument("x", nargs="?")
        s.set_defaults(func=func)
    return add


def test_commands_of_all_kinds_are_in_the_parser(empty):
    kind("a", {"one": adder("one", lambda args: 0)})
    kind("b", {"two": adder("two", lambda args: 0)})
    p = cli.parser()
    assert callable(p.parse_args(["one"]).func) and callable(p.parse_args(["two", "v"]).func)
    with pytest.raises(SystemExit):
        p.parse_args(["three"])


def test_a_name_clash_between_two_kinds_is_an_error(empty):
    kind("a", {"one": adder("one", lambda args: 0)})
    kind("b", {"one": adder("one", lambda args: 0)})
    with pytest.raises(cli.CommandClash, match="'one'.*'a'.*'b'"):
        cli.parser()


def test_exit_code_and_error_text(empty, capsys):
    kind("a", {"ok": adder("ok", lambda args: 3), "seal": adder("seal", lambda args: (_ for _ in ()).throw(SealError("bad")))})
    with pytest.raises(SystemExit) as e:
        cli.main(["ok"])
    assert e.value.code == 3
    with pytest.raises(SystemExit) as e:
        cli.main(["seal"])
    assert e.value.code == "error: bad"


def test_errors_of_a_kind(empty):
    class Mine(Exception):
        pass

    def boom(args):
        raise Mine("mine")
    kind("a", {"boom": adder("boom", boom)}, cli_errors=(Mine,))
    with pytest.raises(SystemExit) as e:
        cli.main(["boom"])
    assert e.value.code == "error: mine"
    with pytest.raises(Mine):                      # no cli_errors: not caught
        kinds._KINDS["a"].cli_errors = ()
        cli.main(["boom"])


def test_description_from_the_kinds(empty):
    kind("a", {})
    assert cli.parser().description == cli.DESCRIPTION
    kind("b", {}, cli_doc="Text of b.")
    assert cli.parser().description == "Text of b."


def test_prog(empty):
    kind("a", {})
    assert cli.parser("probatrix").prog == "probatrix"
