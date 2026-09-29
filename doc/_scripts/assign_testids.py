#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Give every documented ZTEST in test-scope.yaml a test id.

An id is ``TSPEC-<code>-<NNN>``, ``<code>`` being the area's code from the
scope file. Ids are append-only: an existing ``@testid`` is never touched, and a
number, once issued, is never issued again — the ledger (``testids.yaml``)
records the last number per area, so deleting the test that held the highest
number does not free it.

A ZTEST whose body is only ``ztest_test_skip();`` — the feature-off stub of a
test that lives elsewhere — gets no id either, even with a doc comment: the
test specification leaves stubs out (doxygen_filter_kconfig.py), so an id on
one would name nothing.

The id goes into the test's own doc comment, with ``@draft`` unless the comment
already carries a status, just before its first ``@see`` / ``@verifies`` /
``@satisfies`` / status line, or at its end. A ZTEST with no doc comment gets no
id; it is listed, because the test specification can only give it the
generated fallback id.

Without ``--write`` nothing is changed and the assignments are printed.
"""

import argparse
import bisect
import functools
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import doxygen_filter_kconfig as kconfig  # noqa: E402
from doxygen_filter_kconfig import ZTEST_MACRO, is_skip_stub  # noqa: E402
from testspec_scope import _sources, load_scope  # noqa: E402

# The macros that define a test (see doxygen_filter_kconfig.ZTEST_MACRO).
ZTEST = re.compile(rf"^[ \t]*{ZTEST_MACRO}\s*\(\s*(\w+)\s*,\s*(\w+)", re.M)
TAIL = re.compile(r"^\s*\*\s*[@\\](see|verifies|satisfies|draft|active|obsolete)\b")
STATUS = re.compile(r"[@\\](draft|active|obsolete)\b")
STUB = "stub"


@functools.lru_cache(maxsize=4)
def _lexed(text):
    lines = re.findall(r"[^\n]*\n|[^\n]+$", text)
    comments, in_comment = kconfig.lex(lines)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))
    return lines, comments, in_comment, starts


def doc_block(text, pos):
    """(start, end) of the doc comment Doxygen attaches to the declaration on
    the line at pos, or None.

    The comment Doxygen attaches, as the documentation build sees it
    (doxygen_filter_kconfig.attached_doc()): a conditional directive or a
    plain comment may stand between the doc comment and the ZTEST."""
    lines, comments, in_comment, starts = _lexed(text)
    n = bisect.bisect_right(starts, pos) - 1
    c = kconfig.attached_doc(lines, comments, in_comment, n)
    if c is None:
        return None
    return starts[c.start[0]] + c.start[1], starts[c.end[0]] + c.end[1] + 2


def plan(areas, ledger, zephyr_base):
    """Yield (file, suite, fn, id) in file order for the ids not yet assigned;
    id is None for an undocumented ZTEST, STUB for a stub."""
    for area in areas:
        issued = re.compile(rf"TSPEC-{re.escape(area.code)}-(\d+)\b")
        files = [f for m in area.modules for f in _sources(zephyr_base / m.path) if f.suffix == ".c"]
        texts = {f: f.read_text() for f in files}
        last = max(
            [ledger.get(area.code, 0)] + [int(n) for t in texts.values() for n in issued.findall(t)]
        )
        for f in files:
            text = texts[f]
            for m in ZTEST.finditer(text):
                block = doc_block(text, m.start())
                if block is not None and "@testid" in text[block[0]:block[1]]:
                    continue
                if is_skip_stub(text[m.start():]):
                    yield f, m.group(1), m.group(2), STUB
                    continue
                if block is None:
                    yield f, m.group(1), m.group(2), None
                    continue
                last += 1
                yield f, m.group(1), m.group(2), f"TSPEC-{area.code}-{last:03d}"
        ledger[area.code] = last


def _unassigned(text, m, suite, fn):
    """Whether ZTEST match m is (suite, fn) and a documented site with no id."""
    if (m.group(1), m.group(2)) != (suite, fn) or is_skip_stub(text[m.start():]):
        return False
    block = doc_block(text, m.start())
    return block is not None and "@testid" not in text[block[0]:block[1]]


def insert_id(text, pos, test_id):
    start, end = doc_block(text, pos)
    block = text[start:end]
    if "\n" not in block:
        # A one-line `/** @brief ... */` has no line to insert before: open it up.
        block = "/**\n * " + block[3:-2].strip() + "\n */"
    lines = block.split("\n")
    at = next((i for i, line in enumerate(lines) if TAIL.match(line)), len(lines) - 1)
    new = [" * @testid{" + test_id + "}"]
    if not STATUS.search(text[start:end]):
        new.append(" * @draft")
    if lines[at - 1].strip() not in ("*", "/**"):
        new.insert(0, " *")
    lines[at:at] = new
    return text[:start] + "\n".join(lines) + text[end:]


def main():
    ap = argparse.ArgumentParser(allow_abbrev=False)
    ap.add_argument("--scope", required=True, type=Path)
    ap.add_argument("--ledger", required=True, type=Path)
    ap.add_argument("--zephyr-base", required=True, type=Path)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    areas = load_scope(args.scope, args.zephyr_base)
    ledger = (yaml.safe_load(args.ledger.read_text()) if args.ledger.exists() else None) or {}
    assignments = list(plan(areas, ledger, args.zephyr_base))

    undocumented = [(f, s, fn) for f, s, fn, tid in assignments if tid is None]
    stubs = [(f, s, fn) for f, s, fn, tid in assignments if tid == STUB]
    todo = [(f, s, fn, tid) for f, s, fn, tid in assignments if tid and tid != STUB]
    for f, s, fn, tid in todo:
        print(f"{tid}  {s}.{fn}  ({f.relative_to(args.zephyr_base)})")
    for f, s, fn in undocumented:
        print(f"no doc comment, no id: {s}.{fn}  ({f.relative_to(args.zephyr_base)})", file=sys.stderr)
    for f, s, fn in stubs:
        print(f"skip stub, no id: {s}.{fn}  ({f.relative_to(args.zephyr_base)})", file=sys.stderr)
    print(
        f"{len(todo)} to assign, {len(undocumented)} undocumented, {len(stubs)} skip stubs",
        file=sys.stderr,
    )

    if args.write and todo:
        # In file order, each into the first site of its (suite, function)
        # still without an id: the feature-on and feature-off twins of a
        # test can share one file, and each gets its own id.
        for f, s, fn, tid in todo:
            text = f.read_text()
            pos = next(m.start() for m in ZTEST.finditer(text) if _unassigned(text, m, s, fn))
            f.write_text(insert_id(text, pos, tid))
        header = (
            "# Last test-id number issued per area code (assign_testids.py).\n"
            "# Append-only: a number here is never issued again, even if its test is gone.\n"
        )
        args.ledger.write_text(header + yaml.safe_dump(dict(sorted(ledger.items()))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
