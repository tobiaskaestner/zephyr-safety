# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""python -m probatrix: the same command line as study.py (the lab re-exec is the same)."""

import sys
from pathlib import Path

from probatrix.benchmarks.studylib import lab as labmod
from probatrix.core import cli

if __name__ == "__main__":
    labmod.reexec_in_lab_repo(sys.argv[1:], Path(__file__).resolve().parent / "study.py")
    cli.main(prog="probatrix")
