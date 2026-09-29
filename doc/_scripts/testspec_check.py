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


@dataclass
class Site:
    suite: str
    fn: str
    file: str
    line: int
    testid: object = None
    excluded_by: list = field(default_factory=list)  # conditions evaluated false

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
                            tid.group(1) if tid else None, hidden(line),
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
            ok.append(s)
        elif by_pair.get(s.pair) and per_pair[s.pair] > 1 and (s.testid or s.excluded_by):
            twins.append(s)
        elif s.testid or not by_pair.get(s.pair):
            missing.append(s)
        else:
            ok.append(s)  # undocumented, in the spec under its fallback id
    return ok, twins, missing, by_pair


def main(argv=None):
    ap = argparse.ArgumentParser(allow_abbrev=False, description=__doc__.split("\n")[0])
    ap.add_argument("--scope", required=True, type=Path)
    ap.add_argument("--zephyr-base", required=True, type=Path)
    ap.add_argument("--needs", required=True, type=Path, help="the test specification's needs.json")
    args = ap.parse_args(argv)

    all_sites = sites(args.scope, args.zephyr_base)
    ok, twins, missing, by_pair = classify(all_sites, spec_cases(args.needs))
    print(
        f"testspec-check: {len(all_sites)} ZTEST sites in scope: {len(ok)} in the spec, "
        f"{len(twins)} twin not chosen, {len(missing)} MISSING"
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
        cond = "; ".join(s.excluded_by) or "-"
        print(
            f"  error: MISSING  {s.where()}  {s.suite}.{s.fn}  id={s.testid or '-'}"
            f"  excluded by {cond}"
        )
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
