import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # _extensions/

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

extensions = ["sphinx_needs", "test_module"]
master_doc = "index"
exclude_patterns = ["_build"]

needs_types = [
    dict(directive="test_result", title="Test Result", prefix="TRESULT_", color="#FCE4D6", style="node"),
    dict(directive="test_case",   title="Test Case",   prefix="TCASE_",   color="#E2EFDA", style="node"),
]
_str_field = {"schema": {"type": "string"}, "nullable": True}
needs_fields = {
    "platform":       {**_str_field},
    "scenario":       {**_str_field},
    "twister_id":     {**_str_field},
    "execution_time": {**_str_field},
    "reason":         {**_str_field},
    "test_function":  {**_str_field},
    "test_module":    {**_str_field},
    "suite":          {**_str_field},
    "suite_title":    {**_str_field},
}
needs_id_regex = r"^[A-Za-z][A-Za-z0-9_-]+"
needs_links = {
    "result_of": {"description": "result of",  "incoming": "has results",  "outgoing": "result of"},
    "covers":    {"description": "covers",      "incoming": "covered by",   "outgoing": "covers"},
    "verifies":  {"description": "verifies",    "incoming": "verified by",  "outgoing": "verifies"},
}
needs_external_needs = [{
    "json_path": str(_FIXTURES / "needs" / "needs.json"),
    "base_url": "http://localhost/",
    "version": "1.0",
}]
twister_output_dir = str(_FIXTURES / "twister")
testspec_doxygen_url = "testspec"
api_doxygen_url = "api"
needs_build_json = True
suppress_warnings = ["needs.link_outgoing", "needs.external_link_outgoing", "config.cache"]
