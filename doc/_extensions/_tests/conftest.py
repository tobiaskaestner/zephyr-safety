import sys
from pathlib import Path

import pytest

# Make _extensions/ importable without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIXTURES = Path(__file__).parent / "fixtures"

pytest_plugins = "sphinx.testing.fixtures"
# rootdir is intentionally left as the sphinx.testing default (None).
# Tests pass srcdir as an absolute path so Sphinx uses the source tree directly
# without copying, keeping __file__-relative paths in conf.py correct.
