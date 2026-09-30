#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Check that every ZTEST in test-scope.yaml made it into the test specification.

A ZTEST can drop out of the specification without a warning: behind a
conditional Doxygen evaluates false, in a group nothing walks, under a doc
comment the macro expansion loses. This reads every ZTEST site in scope from
the sources and the test cases from the built specification's needs.json, and
classifies each site:

in spec
    its ``@testid`` is a test case; or it has none and its (suite, function) is
    one, under the fallback id.
TWIN not chosen
    another site with the same (suite, function) is the one in the spec — the
    feature-on and feature-off variants of a test. The condition that
    excluded it is printed. A warning when the unchosen twin carries a
    ``@testid`` (an id that names nothing), an info line otherwise.
MISSING
    its ``@testid`` is not in the spec, or its (suite, function) is nowhere in
    it. An error: the exit status is 1.
MISATTACHED
    its ``@testid`` is a test case, but of another function: Doxygen attached
    the doc comment to something else, typically a file-scope macro call it
    cannot expand (``K_APP_DMEM(part) int x;``) right before the ZTEST, and the
    test itself dropped out. An error too.

The other direction is checked as well, as warnings: a test case that is no
ZTEST in scope (NOT A TEST: Doxygen put some other function into a suite
group, e.g. a helper inside an upstream ``@{ ... @}`` span), or whose ZTEST
lives in another module than its ``test_module`` (WRONG MODULE: one suite group
shared by two modules).

CROSS-MODULE, an error: a (suite, function) pair that ZTESTs of two modules
in scope have, or test cases on the pages of two modules. A test report correlates a result
with its test case by that pair, so a result of either is ambiguous.
testspec_scope.py gives each module its own suite groups, which keeps the
test cases of a suite that two modules use apart, but not two tests of the
same name in it.

Which twin the documentation build sees is decided by
doxygen_filter_kconfig.py, whose evaluation this script reuses.
"""

import argparse
import collections
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import doxygen_filter_kconfig as kconfig  # noqa: E402
from assign_testids import ZTEST, doc_block  # noqa: E402
from testspec_scope import _sources, load_scope  # noqa: E402

TESTID = re.compile(r"[@\\]testid\{([\w-]+)\}")
# Any ZTEST-like macro, local aliases included (sys_mutex's ZTEST_USER_OR_NOT):
# a spec case that is one of these is a test, if not one the id tooling sees.
ANY_ZTEST = re.compile(r"^[ \t]*ZTEST\w*\s*\(\s*(\w+)\s*,\s*(\w+)", re.M)


@dataclass
class Site:
    suite: str
    fn: str
    file: str
    line: int
    module: str = ""
    testid: object = None
    excluded_by: list = field(default_factory=list)  # conditions evaluated false
    misattached_to: object = None  # the function its @testid's case names instead

    @property
    def pair(self):
        return self.suite, self.fn

    def where(self):
        return f"{self.file}:{self.line}"


def _excluded_by(text):
    """{line: [directive text, ...]} of the conditions hiding each line."""
    lines = re.findall(r"[^\n]*\n|[^\n]+$", text)
    comments, in_comment = kconfig.lex(lines)
    conds = kconfig.parse(lines, in_comment)
    ztests, stubs = kconfig.documented_ztests(lines, comments)
    for n in ztests:  # the twin rule, as the filter applies it
        if n not in stubs:
            for c, b in kconfig._enclosing(conds, n):
                if b.taken is False:
                    c.open_up = True

    def directive(b):
        return f"{' '.join(lines[b.line].split())} (line {b.line + 1})"

    def hidden(n):
        return [
            directive(b) + ("" if b is c.branches[0] else f" of {directive(c.branches[0])}")
            for c, b in kconfig._enclosing(conds, n)
            if b.taken is False and not c.open_up
        ]

    return hidden


def sites(scope, zephyr_base):
    out = []
    for area in load_scope(scope, zephyr_base):
        for m in area.modules:
            for f in _sources(zephyr_base / m.path):
                if f.suffix != ".c":
                    continue
                text = f.read_text(errors="replace")
                hidden = _excluded_by(text)
                for z in ZTEST.finditer(text):
                    block = doc_block(text, z.start())
                    tid = TESTID.search(text[block[0]:block[1]]) if block else None
                    line = text.count("\n", 0, z.start())
                    out.append(
                        Site(
                            z.group(1), z.group(2), str(f.relative_to(zephyr_base)), line + 1,
                            m.path, tid.group(1) if tid else None, hidden(line),
                        )
                    )
    return out


def spec_cases(needs_file):
    data = json.loads(Path(needs_file).read_text())
    versions = data["versions"]
    version = versions.get(data.get("current_version")) or next(iter(versions.values()))
    return {n["id"]: n for n in version["needs"].values() if n["type"] == "test_case"}


def classify(all_sites, cases):
    by_pair = collections.defaultdict(list)
    for n in cases.values():
        by_pair[(n.get("suite"), n.get("test_function"))].append(n["id"])
    per_pair = collections.Counter(s.pair for s in all_sites)
    ok, twins, missing = [], [], []
    for s in all_sites:
        if s.testid and s.testid in cases:
            fn = cases[s.testid].get("test_function")
            if fn == s.fn:
                ok.append(s)
            else:
                s.misattached_to = fn
                missing.append(s)
        elif by_pair.get(s.pair) and per_pair[s.pair] > 1 and (s.testid or s.excluded_by):
            twins.append(s)
        elif s.testid or not by_pair.get(s.pair):
            missing.append(s)
        else:
            ok.append(s)  # undocumented, in the spec under its fallback id
    return ok, twins, missing, by_pair


def alias_pairs(scope, zephyr_base):
    """(suite, fn) of every ZTEST-like macro call in scope."""
    return {
        pair
        for area in load_scope(scope, zephyr_base)
        for m in area.modules
        for f in _sources(zephyr_base / m.path)
        if f.suffix == ".c"
        for pair in ANY_ZTEST.findall(f.read_text(errors="replace"))
    }


def strays(all_sites, cases, aliases=frozenset()):
    """[(case, reason)] for the test cases no ZTEST site in scope accounts for;
    `aliases`, (suite, fn) pairs defined through a local ZTEST alias, are tests."""
    by_pair = collections.defaultdict(list)
    for s in all_sites:
        by_pair[s.pair].append(s)
    out = []
    for n in cases.values():
        if n.get("is_external"):
            continue
        here = by_pair.get((n.get("suite"), n.get("test_function")))
        if not here:
            if (n.get("suite"), n.get("test_function")) not in aliases:
                out.append((n, "NOT A TEST"))
        elif n.get("test_module") and not any(
            s.file.startswith(n["test_module"].rstrip("/") + "/") for s in here
        ):
            out.append((n, f"WRONG MODULE (the ZTEST is in {here[0].file})"))
    return out


def cross_module(all_sites, cases):
    """{(suite, fn): [module, ...]} of the pairs that ZTEST sites of more than
    one module have, or test cases of more than one module. (A single case
    on the page of another module than its ZTEST's is WRONG MODULE.)"""
    in_sources = collections.defaultdict(set)
    in_spec = collections.defaultdict(set)
    for s in all_sites:
        in_sources[s.pair].add(s.module)
    for n in cases.values():
        if not n.get("is_external") and n.get("test_module"):
            in_spec[(n.get("suite"), n.get("test_function"))].add(n["test_module"].rstrip("/"))
    return {
        pair: sorted(in_sources[pair] | in_spec[pair])
        for pair in sorted(set(in_sources) | set(in_spec))
        if len(in_sources[pair]) > 1 or len(in_spec[pair]) > 1
    }


def main(argv=None):
    ap = argparse.ArgumentParser(allow_abbrev=False, description=__doc__.split("\n")[0])
    ap.add_argument("--scope", required=True, type=Path)
    ap.add_argument("--zephyr-base", required=True, type=Path)
    ap.add_argument("--needs", required=True, type=Path, help="the test specification's needs.json")
    args = ap.parse_args(argv)

    all_sites = sites(args.scope, args.zephyr_base)
    cases = spec_cases(args.needs)
    ok, twins, missing, by_pair = classify(all_sites, cases)
    stray = strays(all_sites, cases, alias_pairs(args.scope, args.zephyr_base))
    shared = cross_module(all_sites, cases)
    print(
        f"testspec-check: {len(all_sites)} ZTEST sites in scope: {len(ok)} in the spec, "
        f"{len(twins)} twin not chosen, {len(missing)} MISSING or MISATTACHED; "
        f"{len(stray)} spec cases not a ZTEST of their module; "
        f"{len(shared)} CROSS-MODULE (suite, function) pairs"
    )
    for (suite, fn), mods in shared.items():
        print(f"  error: CROSS-MODULE  {suite}.{fn}  in {', '.join(mods)}")
    for n, reason in stray:
        print(
            f"  warning: {reason}  {n['id']}  {n.get('suite')}.{n.get('test_function')}"
            f"  test_module={n.get('test_module') or '-'}"
        )
    for s in twins:
        level = "warning" if s.testid else "info"
        cond = "; ".join(s.excluded_by) or "-"
        print(
            f"  {level}: TWIN not chosen  {s.where()}  {s.suite}.{s.fn}"
            f"{'  id=' + s.testid if s.testid else ''}  excluded by {cond}"
            f"  (spec has {', '.join(by_pair[s.pair])})"
        )
    for s in missing:
        if s.misattached_to:
            print(
                f"  error: MISATTACHED  {s.where()}  {s.suite}.{s.fn}  id={s.testid}"
                f"  (the spec's case is named {s.misattached_to!r})"
            )
            continue
        cond = "; ".join(s.excluded_by) or "-"
        print(
            f"  error: MISSING  {s.where()}  {s.suite}.{s.fn}  id={s.testid or '-'}"
            f"  excluded by {cond}"
        )
    return 1 if missing or shared else 0


if __name__ == "__main__":
    sys.exit(main())
