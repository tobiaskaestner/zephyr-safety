# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The list parser (lists.py) and its comparison with the bash parser in spec/tla/tools/run_tlc.sh.

The comparison is not a copy of the rules: the test cuts the real lines out of run_tlc.sh (the function mb, the
variables SELECT and the loop `while read -r module config expected rest ... done < "$listfile"`), runs them in
bash on each real list file and compares the fields. If run_tlc.sh changes its layout so that the cut fails,
the test fails (it does not skip).
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from probatrix.core import config
from probatrix.tlaplus import lists

REPO = config.project().repo
TLA = REPO / "spec" / "tla"
RUN_TLC = TLA / "tools" / "run_tlc.sh"
# Every list file of spec/tla. run_tlc.sh reads only the first three (suites mc and selftest).
LISTS = ["mc/expected.txt", "mc/sensitivity.txt", "selftest/expected.txt", "apalache/expected.txt",
         "trace/expected.txt"]
READ_BY_RUN_TLC = LISTS[:3]

needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="no bash")


def bash_parser(drop_key_check=False):
    """The text of a bash script that parses $1 with the loop of run_tlc.sh and prints one line for each
    selected line: module, config, expected, rest (separated by tabs)."""
    src = RUN_TLC.read_text()
    mb = re.search(r"^mb\(\) \{.*?^\}\n", src, re.S | re.M)
    loop = re.search(r'^SELECT=\("\$@"\).*?^done < "\$listfile"\n', src, re.S | re.M)
    assert mb and loop, "run_tlc.sh has another layout: update the cut of the parser"
    text = loop.group(0)
    if drop_key_check:
        text, n = re.subn(r"^\tfor kv in \$rest; do\n.*?^\tdone\n", "", text, flags=re.S | re.M)
        assert n == 1, "run_tlc.sh has another key check: update the cut"
    return ("set -u\nlistfile=$1\nshift\n" + mb.group(0) + text +
            'for i in "${!L_MOD[@]}"; do\n'
            "\tprintf '%s\\t%s\\t%s\\t%s\\n' \"${L_MOD[$i]}\" \"${L_CFG[$i]}\" \"${L_EXP[$i]}\" \"${L_REST[$i]}\"\n"
            "done\n")


def run_bash(path, drop_key_check=False):
    r = subprocess.run(["bash", "-c", bash_parser(drop_key_check), "bash", str(path)],
                       capture_output=True, text=True)
    rows = [ln.split("\t", 3) for ln in r.stdout.splitlines()]
    return r.returncode, [(m, c, e, rest.split()) for m, c, e, rest in rows], r.stderr


def as_tuples(lines):
    return [(ln.module, ln.name, ln.expected, [f"{k}={v}" for k, v in ln.fields.items()]) for ln in lines]


def test_every_list_file_of_the_repo_is_in_the_comparison():
    found = {p.relative_to(TLA).as_posix() for p in TLA.glob("*/expected.txt")} | {"mc/sensitivity.txt"}
    assert found == set(LISTS)


@needs_bash
@pytest.mark.parametrize("name", READ_BY_RUN_TLC)
def test_the_parser_gives_the_fields_of_the_bash_parser(name):
    """The three lists that run_tlc.sh reads: same lines, same fields, and both accept the keys."""
    status, bash, err = run_bash(TLA / name)
    assert status == 0, err
    got = as_tuples(lists.read(TLA / name, lists.TLC_KEYS))
    assert got == bash and len(got) > 10


@needs_bash
@pytest.mark.parametrize("name", LISTS[3:])
def test_the_parser_gives_the_fields_of_the_bash_parser_without_the_key_check(name):
    """The lists of the other tools: the loop of the script without its check of the keys (each tool has its keys)."""
    status, bash, err = run_bash(TLA / name, drop_key_check=True)
    assert status == 0, err
    keys = lists.APALACHE_KEYS if name.startswith("apalache") else {}
    got = as_tuples(lists.read(TLA / name, keys))
    assert got == bash and len(got) > 10


@needs_bash
def test_run_tlc_rejects_the_keys_of_apalache_and_so_does_the_tlc_parser():
    path = TLA / "apalache" / "expected.txt"
    status, _, err = run_bash(path)
    assert status == 2 and "unknown field" in err
    with pytest.raises(lists.ListError, match="unknown field"):
        lists.read(path, lists.TLC_KEYS)


def test_the_real_counts():
    """The counts that the notes name: 72 lines in mc/expected.txt."""
    assert len(lists.read(TLA / "mc" / "expected.txt", lists.TLC_KEYS)) == 72
    assert len(lists.read(TLA / "trace" / "expected.txt", {})) == 152


def test_comments_blank_lines_and_fields():
    got = lists.parse("# comment\n\n   # indented comment\nMod cfg pass\n  Mod2   c2  fail:Inv  states=12\tdepth=3  \n",
                      lists.TLC_KEYS)
    assert [(g.id, g.expected, g.fields, g.lineno) for g in got] == [
        ("Mod:cfg", "pass", {}, 4), ("Mod2:c2", "fail:Inv", {"states": "12", "depth": "3"}, 5)]
    assert lists.parse("") == []


@pytest.mark.parametrize("text, message", [
    ("Mod cfg\n", "2 fields"),
    ("Mod cfg pass extra\n", "not <key>=<value>"),
    ("Mod cfg pass nokey=1\n", "unknown field nokey=1"),
    ("Mod cfg pass states=x\n", "bad value in states=x"),
    ("Mod cfg pass states=1 states=2\n", "given twice"),
    ("Mod cfg pass heap=2\n", "bad value in heap=2"),
    ("Mod cfg pass # comment\n", "not <key>=<value>"),
    ("Mod cfg pass\nMod cfg fail:X\n", "also on line 1"),
    ("Mod cfg pass", "no newline"),
])
def test_errors(text, message):
    with pytest.raises(lists.ListError, match=message):
        lists.parse(text, lists.TLC_KEYS)


def test_the_keys_of_the_tools():
    assert lists.parse("M c pass depth=10 traces=5 seed=-3 heap=1g\n", lists.SIMULATE_KEYS)[0].fields == {
        "depth": "10", "traces": "5", "seed": "-3", "heap": "1g"}
    with pytest.raises(lists.ListError, match="unknown field states=1"):
        lists.parse("M c pass states=1\n", lists.SIMULATE_KEYS)       # a simulation has no counts to check
    assert lists.parse("M c pass lasso=stutter trace=4\n", lists.TLC_KEYS)[0].fields["lasso"] == "stutter"
    assert lists.parse("M c pass anything=goes\n", None)[0].fields == {"anything": "goes"}


@needs_bash
def test_where_the_parsers_differ(tmp_path):
    """The three places where this parser is stricter than the script (see the module text of lists.py)."""
    def both(text, keys=lists.TLC_KEYS):
        p = tmp_path / "l.txt"
        p.write_text(text)
        status, bash, _ = run_bash(p)
        try:
            return status, bash, as_tuples(lists.read(p, keys))
        except lists.ListError as e:
            return status, bash, str(e)
    # 1. fewer than three fields: the script lets the line through with empty fields
    status, bash, py = both("Mod cfg\n")
    assert status == 0 and bash == [("Mod", "cfg", "", [])] and "2 fields" in py
    # 2. a number that only starts with a digit
    status, bash, py = both("Mod cfg pass states=12x\n")
    assert status == 0 and bash[0][3] == ["states=12x"] and "bad value" in py
    # 3. a last line without a newline: the script skips it, without a message
    status, bash, py = both("Mod cfg pass\nMod2 cfg pass")
    assert status == 0 and [b[0] for b in bash] == ["Mod"] and "no newline" in py
