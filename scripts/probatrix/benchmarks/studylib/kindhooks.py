# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The functions that the engine takes from the kind of a study.

The engine (design lint, run.json) needs the points of an experiment and the
meaning of a Kconfig value. They come from run.py of the kind. run.py imports
studylib, so studylib must not import run.py at load time: this module imports
it when a function is called. Stub: the one kind is "latbench", and its run.py is
the provider. A later step lets the kind of a design choose the provider.
"""


def run_module():
    """The run.py module of the kind (imported on the first call)."""
    from probatrix.benchmarks import run
    return run


def expand_points(exp):
    """The points of an experiment (a SystemExit with "error: ..." if the file has an error)."""
    return run_module().expand_points(exp)


def kconfig_value(value):
    """The Kconfig text ("y", "n" or the value) of a design value."""
    return run_module().kconfig_value(value)
