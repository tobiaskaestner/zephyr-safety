#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""probatrix: the command line of the studies (design, lab, campaign, instance, analysis ...).

This is the launcher. It puts the folder scripts/ on sys.path, runs the launcher of the design
repo of the lab space (if the current folder is in one), and then starts probatrix.core.cli.
"python -m probatrix" gives the same command line. See benchmarks/cli.py for the commands.
"""

import importlib.util
import sys
from pathlib import Path

# A launcher: the folder scripts/ holds the package probatrix.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The lab space and the restart come first. The module lab.py needs only the standard library. It is
# loaded from its file, not through the package: the package imports PyYAML, and this launcher can
# be started by a Python that has not got it.
_spec = importlib.util.spec_from_file_location(
    "_probatrix_lab", Path(__file__).resolve().parent / "benchmarks" / "studylib" / "lab.py")
labmod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(labmod)

if __name__ == "__main__":
    labmod.reexec_in_lab_repo(sys.argv[1:], Path(__file__).resolve())
    from probatrix.core import cli
    cli.main()
