# Test Specification — zdocs conf.py shim.
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])

from zdocs_conf import configure

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

# The engine's testmodule_* config values (XML dir, doxygen URLs, spec
# needs.json) all come from this document's `testmodule:` registry block — see
# documents.yaml. Two things the registry cannot supply:
#
# testmodule_root defaults to ZDOCS_PROJECT_BASE (this repo), but the documented
# ztest sources live in the *zephyr* west project, so the scenario-table lookup
# would resolve against the wrong tree.
testmodule_root = os.environ["ZEPHYR_BASE"]

# A suite name that more than one module in scope has tests of (workqueue_api)
# gets one Doxygen group per module, `<module group>__<suite>`
# (_scripts/testspec_scope.py); the test cases' suite is the part after "__".
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
needs_layouts = {
    "safety": {
        "grid": "simple",
        "layout": {
            "head": [
                '<<meta("type_name")>> <<meta_id()>>: **<<meta("title")>>** '
                '<<collapse_button("meta", collapsed="icon:arrow-down-circle", '
                'visible="icon:arrow-right-circle", initial=False)>>'
            ],
            "meta": [
                '<<meta("test_function", prefix="\\*\\*test function:\\*\\* ")>>',
                '<<meta("test_module",   prefix="\\*\\*test module:\\*\\* ")>>',
                '<<meta("suite",         prefix="\\*\\*suite:\\*\\* ")>>',
                '<<meta("depends_on",    prefix="\\*\\*depends on:\\*\\* ")>>',
                '<<meta("status",        prefix="\\*\\*status:\\*\\* ", show_empty=True)>>',
                "<<meta_links_all()>>",
            ],
        },
    }
}
needs_default_layout = "safety"


def setup(app):
    app.add_css_file("css/custom.css")
    app.add_js_file("js/custom.js")
