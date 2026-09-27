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

The id goes into the test's own doc comment, with ``@draft`` unless the comment
already carries a status, just before its first ``@see`` / ``@verifies`` /
``@satisfies`` / status line, or at its end. A ZTEST with no doc comment gets no
id; it is listed, because the test specification can only give it the
generated fallback id.

Without ``--write`` nothing is changed and the assignments are printed.
"""

import argparse
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from testspec_scope import _sources, load_scope  # noqa: E402

ZTEST = re.compile(r"^[ \t]*ZTEST(?:_USER|_F|_USER_F|_EXPECT_FAIL)?\s*\(\s*(\w+)\s*,\s*(\w+)", re.M)
TAIL = re.compile(r"^\s*\*\s*[@\\](see|verifies|satisfies|draft|active|obsolete)\b")
STATUS = re.compile(r"[@\\](draft|active|obsolete)\b")


def doc_block(text, pos):
    """(start, end) of the /** ... */ comment ending right before pos, or None."""
    head = text[:pos].rstrip()
    if not head.endswith("*/"):
        return None
    start = head.rfind("/**")
    if start < 0 or "*/" in head[start:-2]:
        return None
    return start, len(head)


def plan(areas, ledger, zephyr_base):
    """Yield (file, suite, fn, id_or_None) in file order; ids not yet assigned."""
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
                if block is None:
                    yield f, m.group(1), m.group(2), None
                    continue
                if "@testid" in text[block[0]:block[1]]:
                    continue
                last += 1
                yield f, m.group(1), m.group(2), f"TSPEC-{area.code}-{last:03d}"
        ledger[area.code] = last


def insert_id(text, pos, test_id):
    start, end = doc_block(text, pos)
    lines = text[start:end].split("\n")
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
    todo = [(f, s, fn, tid) for f, s, fn, tid in assignments if tid]
    for f, s, fn, tid in todo:
        print(f"{tid}  {s}.{fn}  ({f.relative_to(args.zephyr_base)})")
    for f, s, fn in undocumented:
        print(f"no doc comment, no id: {s}.{fn}  ({f.relative_to(args.zephyr_base)})", file=sys.stderr)
    print(f"{len(todo)} to assign, {len(undocumented)} undocumented", file=sys.stderr)

    if args.write and todo:
        # Last first, so earlier offsets in the same file stay valid.
        for f, s, fn, tid in reversed(todo):
            text = f.read_text()
            pos = next(m.start() for m in ZTEST.finditer(text) if (m.group(1), m.group(2)) == (s, fn))
            f.write_text(insert_id(text, pos, tid))
        header = (
            "# Last test-id number issued per area code (assign_testids.py).\n"
            "# Append-only: a number here is never issued again, even if its test is gone.\n"
        )
        args.ledger.write_text(header + yaml.safe_dump(dict(sorted(ledger.items()))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
