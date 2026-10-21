# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

import pytest

# doc/_extensions, appended (never prepended), as the conf.py shims do.
EXTENSIONS = Path(__file__).resolve().parents[1]
if str(EXTENSIONS) not in sys.path:
    sys.path.append(str(EXTENSIONS))

ROOTS = Path(__file__).parent / "roots"


@pytest.fixture(scope="session")
def rootdir():
    """The test roots. sphinx.testing copies roots/test-<name> to a temp dir."""
    return ROOTS


@pytest.fixture
def ksem_copy():
    """The test copy of KSem.tla (with tags), as a path."""
    return ROOTS / "test-tla" / "spec" / "KSem.tla"


@pytest.fixture
def extra_tla():
    return ROOTS / "test-tla" / "spec" / "Extra.tla"
