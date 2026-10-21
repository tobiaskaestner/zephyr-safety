#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Drift guard of the real copies in the shadow headers.

A shadow header can keep a pure function of a kernel-internal header real:
it has a copy of the function, without a change. The copy is between two
marker lines:

    /* KERNEL_UNIT_REAL_COPY_BEGIN kernel/include/ksched.h */
    static inline bool z_is_prio_higher(int prio, int test_prio)
    {
            ...
    }
    /* KERNEL_UNIT_REAL_COPY_END */

The path after BEGIN is relative to ZEPHYR_BASE. This script examines that
the text between the markers occurs in this file, character for character.
If a copy is not found, the script prints the copy and its file, and exits
with status 1. cmake/kernel_unit.cmake runs it when a test application is
configured. Thus a change of the real header stops the build until the copy
is updated.

Usage: check_real_copies.py <zephyr base> <shadow header>...
"""

import re
import sys
from pathlib import Path

BEGIN = re.compile(r"^/\* KERNEL_UNIT_REAL_COPY_BEGIN (\S+) \*/$")
END = "/* KERNEL_UNIT_REAL_COPY_END */"


def copies(path):
    """Yield (line number, real header, text) for each copy in a shadow header."""
    lines = path.read_text().split("\n")
    i = 0
    while i < len(lines):
        m = BEGIN.match(lines[i])
        if m:
            start = i + 1
            j = start
            while j < len(lines) and lines[j] != END:
                j += 1
            if j == len(lines):
                raise SystemExit(f"{path}:{i + 1}: KERNEL_UNIT_REAL_COPY_BEGIN without END")
            yield start, m.group(1), "\n".join(lines[start:j]) + "\n"
            i = j
        i += 1


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    zephyr_base = Path(sys.argv[1])
    failed = 0
    checked = 0
    for name in sys.argv[2:]:
        shadow = Path(name)
        for line, real, text in copies(shadow):
            checked += 1
            real_path = zephyr_base / real
            if not real_path.is_file():
                print(f"{shadow}:{line}: the real header {real_path} does not exist")
                failed += 1
            elif text not in real_path.read_text():
                print(f"{shadow}:{line}: the copy is not the same as the text of {real_path}:")
                print(text)
                failed += 1
    if failed:
        print(f"check_real_copies: {failed} of {checked} real copies are not up to date")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
