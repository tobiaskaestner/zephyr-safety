# Test Specification — zdocs conf.py shim.
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])

from zdocs_conf import configure, need_layout

configure(
    globals(),
    doc_dir=Path(__file__).resolve().parent,
    # This document's own custom.css / custom.js (loaded in setup() below).
    static_path=[Path(__file__).resolve().parent / "_static"],
    project="Zephyr Test Specification",
    author="Zephyr Project Contributors",
    copyright_holder="Zephyr Project Contributors",
    extensions=[
        "sphinx_tabs.tabs",
        "zephyr.kconfig",
        "zephyr.application",
        "zephyr.link-roles",
    ],
)

# The Safety Committee document is left out of a build without its sources
# (SAFETY_DOC_COMMITTEE in doc/CMakeLists.txt). The tag lets xref-test.rst
# link to it only when the registry has it.
if "committee" in intersphinx_mapping:
    tags.add("committee")

# The engine's testmodule_* config values (XML dir, doxygen URLs, spec
# needs.json) all come from this document's `testmodule:` registry block — see
# documents.yaml. Two things the registry cannot supply:
#
# testmodule_root defaults to ZDOCS_PROJECT_BASE (this repo), but the documented
# ztest sources live in the *zephyr* west project, so the scenario-table lookup
# would resolve against the wrong tree.
testmodule_root = os.environ["ZEPHYR_BASE"]

# A generated suite group has the Doxygen id `<module group>__<suite>`
# (_scripts/testspec_scope.py). Thus it cannot have the name of a C function,
# and a suite that two modules have tests of (workqueue_api) gets one group in
# each module. The suite of a test case is the part after the last "__".
testmodule_suite_qualifier = "__"

# The per-area and per-module pages are generated from doc/test-scope.yaml by
# the `testspec-gen` target (see doc/CMakeLists.txt) and copied in here.
external_content_contents.append(
    (Path(os.environ["SAFETY_TESTSPEC_GEN_DIR"]) / "spec", "*")
)

# twister output: honour ZDOCS_TWISTER_OUT when the build sets it, else fall
# back to the workspace's own run. Absent input is a normal state — the
# directives soft-fail to a "not found" node.
if not twister_output_dir:
    twister_output_dir = str(Path(os.environ["ZDOCS_WEST_TOPDIR"]) / "twister-out")

# Presentation stays per-document; the shared vocabulary is in needs_config.toml.
# "Depends on" is not a field here: the test case text says it, with Source and
# See also. Not the incoming "has results" links: a test case can have dozens of
# test results (TR-*), one per platform and run. The links stay in needs.json;
# the test report shows them.
needs_layouts = {
    "zdocs_test_case": need_layout(
        fields=[("test_function", "Function"), ("test_module", "Module"), ("suite", "Suite")],
        hide_backlinks=["result_of"],
    )
}
needs_default_layout = "zdocs_test_case"


def setup(app):
    app.add_css_file("css/custom.css")
    app.add_js_file("js/custom.js")
