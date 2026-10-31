# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The list files of the kind tlaplus: one line is one point (one model run).

The format is the format of spec/tla/mc/expected.txt, mc/sensitivity.txt, selftest/expected.txt,
apalache/expected.txt and trace/expected.txt:

    <module> <name> <expected> [<key>=<value> ...]

Blank lines and lines whose first word starts with "#" are comments. The fields are separated by
white space. spec/tla/tools/run_tlc.sh reads the same format in bash (the loop `while read -r module config
expected rest`); tests/test_lists.py runs that loop of the script on each real list file and compares.

The rules of this parser, and where it is stricter than the script:

- A line has three fields or more (the script lets a line with fewer fields through, with empty fields).
- A key must be in the set of the tool (TLC_KEYS, SIMULATE_KEYS, APALACHE_KEYS or None for any key) and must appear
  once. The values have a type (the script only checks that a number starts with a digit).
- The text must end with a newline. The script silently skips a last line without one (the bash `read`
  fails on it). This parser reports it.
- The pair (module, name) must be unique: it is the id of the point.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


class ListError(ValueError):
    """A list file with an error. The text starts with the line number."""


def _int(v):
    return re.fullmatch(r"[0-9]+", v) is not None


def _seed(v):
    return re.fullmatch(r"-?[0-9]+", v) is not None


def _size(v):
    return re.fullmatch(r"[0-9]+[gGmM]", v) is not None


def _lasso(v):
    return _int(v) or v == "stutter"


def _any(v):
    return v != ""


# The keys of the lines of run_tlc.sh (its header comment has the meaning of each key).
TLC_KEYS = {"states": _int, "depth": _int, "trace": _int, "lasso": _lasso, "heap": _size, "repeat": _int}
# The keys of a line of an experiment with the tool tlc-simulate: the point parameters and the heap.
SIMULATE_KEYS = {"depth": _int, "traces": _int, "seed": _seed, "heap": _size}
# The keys of apalache/expected.txt (tools/run_apalache.sh).
APALACHE_KEYS = {"init": _any, "next": _any, "inv": _any, "length": _int, "cinit": _any, "timeout": _any,
                 "omit": _any}
KEYS_OF_TOOL = {"tlc": TLC_KEYS, "tlc-simulate": SIMULATE_KEYS, "apalache": APALACHE_KEYS, "traces": {}}


@dataclass(frozen=True)
class Line:
    module: str
    name: str
    expected: str
    fields: dict = field(default_factory=dict)      # key -> text, in the order of the line
    lineno: int = 0

    @property
    def id(self):
        """The id of the point: <module>:<name> (the selection syntax of run_tlc_remote.py)."""
        return f"{self.module}:{self.name}"


def parse(text, keys=None, where="list"):
    """The lines of a list text. keys: {key: check function} of the tool, or None (any key, any value).
    Raises ListError with "<where>:<line number>: <text>"."""
    if text and not text.endswith("\n"):
        raise ListError(f"{where}: the last line has no newline (run_tlc.sh would skip it)")
    out, seen = [], {}
    for n, raw in enumerate(text.split("\n")[:-1] if text else [], 1):
        words = raw.split()
        if not words or words[0].startswith("#"):
            continue
        if len(words) < 3:
            raise ListError(f"{where}:{n}: {len(words)} fields, a line has <module> <name> <expected>")
        fields = {}
        for kv in words[3:]:
            key, eq, value = kv.partition("=")
            if not eq:
                raise ListError(f"{where}:{n}: {words[0]} {words[1]}: the field {kv!r} is not <key>=<value>")
            if keys is not None and key not in keys:
                raise ListError(f"{where}:{n}: {words[0]} {words[1]}: unknown field {kv}")
            if key in fields:
                raise ListError(f"{where}:{n}: {words[0]} {words[1]}: the key {key} is given twice")
            if keys is not None and not keys[key](value):
                raise ListError(f"{where}:{n}: {words[0]} {words[1]}: bad value in {kv}")
            fields[key] = value
        line = Line(words[0], words[1], words[2], fields, n)
        if line.id in seen:
            raise ListError(f"{where}:{n}: {line.id} is also on line {seen[line.id]}")
        seen[line.id] = n
        out.append(line)
    return out


def read(path, keys=None):
    """The lines of a list file (see parse)."""
    path = Path(path)
    return parse(path.read_text(), keys, str(path))
