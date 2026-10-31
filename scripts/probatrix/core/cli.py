# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The command line of probatrix: one parser, the commands come from the kinds.

The parser has one subcommand for each key that kind.commands() gives. The value is a function
that takes the subparsers object and adds the subparser of that command (with its own
subcommands and set_defaults(func=...)). Two kinds that give the same command name are an
error. This module does not import a kind: it gets the kinds from probatrix.core.kinds.

A kind can set two optional attributes: cli_doc (the text for --help; the texts of all kinds
are joined) and cli_errors (a tuple of exception classes that a command ends with
"error: <text>" and exit code 1; the core adds its own).
"""

import argparse
import sys

from probatrix.core import build, kinds
from probatrix.core.errors import CampaignError, DesignError, SealError

DESCRIPTION = "Studies of safety evidence: designs, runs, instances and verdicts."

# the errors of the core that end a command with "error: <text>"
ERRORS = (CampaignError, DesignError, SealError, build.BuildError, ValueError)


class CommandClash(Exception):
    """Two kinds give the same command name."""


def commands():
    """{command name: (kind, function)} of all kinds. A name that two kinds give is a CommandClash."""
    out = {}
    for name in kinds.names():
        kind = kinds.get(name)
        for cmd, func in kind.commands().items():
            if cmd in out:
                raise CommandClash(f"the command {cmd!r} comes from the kinds {out[cmd][0].name!r} and {kind.name!r}")
            out[cmd] = (kind, func)
    return out


def description():
    """The --help text: the cli_doc texts of the kinds, or a short default."""
    docs = [d for d in (getattr(kinds.get(n), "cli_doc", None) for n in kinds.names()) if d]
    return "\n".join(docs) if docs else DESCRIPTION


def parser(prog=None):
    p = argparse.ArgumentParser(prog=prog, description=description(), formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for _kind, func in commands().values():
        func(sub)
    return p


def errors():
    """The exception classes that end a command with "error: <text>": those of the core and of the kinds."""
    out = list(ERRORS)
    for name in kinds.names():
        out += getattr(kinds.get(name), "cli_errors", ())
    return tuple(out)


def main(argv=None, prog=None):
    argv = sys.argv[1:] if argv is None else argv
    args = parser(prog).parse_args(argv)
    try:
        sys.exit(args.func(args) or 0)
    except errors() as e:
        sys.exit(f"error: {e}")
