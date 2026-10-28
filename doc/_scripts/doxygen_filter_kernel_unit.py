#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""Doxygen input filter of the Kernel Unit Test Specification.

Usage: doxygen_filter_kernel_unit.py <file>

The filter runs doxygen_filter_kconfig.py on the file. Then it opens the
conditionals on ``Z_MUTEX_PI_ENABLED`` that have a ZTEST in their ``#else``
branch: it blanks their ``#if``, ``#else`` and ``#endif`` lines. Thus Doxygen
reads the tests of both branches.

``Z_MUTEX_PI_ENABLED`` (``zephyr/kernel/thread.h``) is not a Kconfig symbol,
so doxygen_filter_kconfig.py leaves it to Doxygen. The Doxyfile defines it as
1, so the tests without priority inheritance (the ``#else`` branch) are not
in the document without this filter. The doc comments of these tests say
"Without priority inheritance".

The output has as many lines as the input, so the line numbers of Doxygen
still point into the real file.
"""

import re
import subprocess
import sys
from pathlib import Path

KCONFIG_FILTER = Path(__file__).with_name("doxygen_filter_kconfig.py")
DIRECTIVE = re.compile(r"^[ \t]*#[ \t]*(ifdef|ifndef|if|elif|else|endif)\b(.*)$")
OPEN_CONDITION = re.compile(r"^\s*Z_MUTEX_PI_ENABLED\s*(/\*.*\*/)?\s*$")
ZTEST = re.compile(r"^[ \t]*ZTEST\s*\(")


def open_twins(lines):
    """Blank the directives of each Z_MUTEX_PI_ENABLED conditional with a ZTEST in #else."""
    stack = []  # [if line, condition, else line or None]
    to_blank = []
    for n, line in enumerate(lines):
        m = DIRECTIVE.match(line)
        if not m:
            continue
        kind, rest = m.group(1), m.group(2)
        if kind in ("if", "ifdef", "ifndef"):
            stack.append([n, kind == "if" and bool(OPEN_CONDITION.match(rest)), None])
        elif kind == "else" and stack:
            stack[-1][2] = n
        elif kind == "endif" and stack:
            start, ours, els = stack.pop()
            if ours and els is not None and any(ZTEST.match(x) for x in lines[els:n]):
                to_blank += [start, els, n]
    for n in to_blank:
        lines[n] = "\n" if lines[n].endswith("\n") else ""
    return lines


def main():
    out = subprocess.run([sys.executable, str(KCONFIG_FILTER), sys.argv[1]],
                         capture_output=True, text=True, check=True).stdout
    sys.stdout.write("".join(open_twins(out.splitlines(keepends=True))))


if __name__ == "__main__":
    main()
