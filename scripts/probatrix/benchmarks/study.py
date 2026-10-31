#!/usr/bin/env python3
# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""Compatibility launcher: the same command line as scripts/probatrix/study.py.

Docs, lab spaces and old command lines start this file. The commands are in cli.py (the kind
latbench) and the dispatcher is probatrix.core.cli. In a lab space, the launcher of the design
repo of the lab space runs (see studylib/lab.py).
"""

import importlib.util
import sys
from pathlib import Path

# A launcher: the folder scripts/ holds the package probatrix.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# The lab space and the restart come first. The module lab.py needs only the standard library. It is
# loaded from its file, not through the package: the package imports PyYAML, and this launcher can
# be started by a Python that has not got it.
_spec = importlib.util.spec_from_file_location(
    "_probatrix_lab", Path(__file__).resolve().parent / "studylib" / "lab.py")
labmod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(labmod)

REEXEC_ENV = labmod.REEXEC_ENV


def reexec_in_lab_repo(argv):
    """Run the launcher of the design repo of the lab space (see studylib/lab.py)."""
    labmod.reexec_in_lab_repo(argv, Path(__file__).resolve())


def parser():
    from probatrix.core import cli
    return cli.parser()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    reexec_in_lab_repo(argv)
    from probatrix.core import cli
    cli.main(argv)


if __name__ == "__main__":
    main()
