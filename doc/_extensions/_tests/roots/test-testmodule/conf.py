import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # _extensions/

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

# Point ZEPHYR_BASE at an empty dir so testcase.yaml lookup silently returns [].
os.environ.setdefault("ZEPHYR_BASE", str(_FIXTURES))

extensions = ["sphinx_needs", "test_module", "breathe"]
master_doc = "index"
exclude_patterns = ["_build"]

needs_types = [
    dict(directive="test_case",      title="Test Case",      prefix="TCASE_", color="#E2EFDA", style="node"),
    dict(directive="test_procedure", title="Test Procedure", prefix="TPROC_", color="#D6E4F7", style="node"),
]
_str_field = {"schema": {"type": "string"}, "nullable": True}
needs_fields = {
    "test_function": {**_str_field},
    "test_module":   {**_str_field},
    "suite":         {**_str_field},
    "suite_title":   {**_str_field},
}
needs_id_regex = r"^[A-Za-z][A-Za-z0-9_-]+"
needs_links = {
    "verifies": {"description": "verifies", "incoming": "verified by", "outgoing": "verifies"},
}
needs_build_json = True
suppress_warnings = ["needs.link_outgoing", "config.cache"]

breathe_projects = {"testspec": str(_FIXTURES / "doxygen")}
breathe_default_project = "testspec"
breathe_implementation_filename_extensions = []

testspec_doxygen_url = "testspec"
api_doxygen_url = "api"
