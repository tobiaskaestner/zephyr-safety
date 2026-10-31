# Copyright (c) 2026 inovex GmbH
# SPDX-License-Identifier: Apache-2.0

"""The design of the repo has no lint errors (study.py design lint), plus checks of single experiments.

Kconfig only warns about a value that it cannot apply, and run.py finds it
only after the build. The lint (studylib/lint.py) finds such errors in the
design files before a run.
"""

from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parent.parent

from probatrix.benchmarks import run  # noqa: E402
from probatrix.benchmarks import trees  # noqa: E402
from probatrix.benchmarks.studylib import lint  # noqa: E402


def test_repo_design_has_no_lint_errors():
    errors = [str(p) for p in lint.lint() if p.severity == lint.ERROR]
    assert not errors, "\n".join(errors)


def test_code_layout_selects_the_pad():
    """wake-code-layout measures the flash pad, as the run 20261025T060257Z."""
    for pt in run.expand_points(yaml.safe_load(trees.experiment_file("wake-code-layout").read_text())):
        assert lint.is_y(pt["kconfig"], "LATBENCH_CODE_FLASH_PAD"), pt["id"]
