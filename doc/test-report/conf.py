# Test Report — zdocs conf.py shim.
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])

from zdocs_conf import configure

# skip_classes is a downstream extension (see _extensions/README.rst): appended
# after zdocs_conf, never before, so it cannot shadow an engine module.
sys.path.append(str(Path(os.environ["ZDOCS_REGISTRY"]).parent / "_extensions"))

configure(
    globals(),
    doc_dir=Path(__file__).resolve().parent,
    # This document's own custom.css / custom.js (loaded in setup() below).
    static_path=[Path(__file__).resolve().parent / "_static"],
    project="Zephyr Test Report",
    author="Zephyr Project Contributors",
    copyright_holder="Zephyr Project Contributors",
    extensions=[
        "sphinx_tabs.tabs",
        "zephyr.kconfig",
        "zephyr.application",
        "zephyr.link-roles",
        "skip_classes",
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

# The per-area and per-module pages are generated from doc/test-scope.yaml by
# the `testspec-gen` target (see doc/CMakeLists.txt) and copied in here.
external_content_contents.append(
    (Path(os.environ["SAFETY_TESTSPEC_GEN_DIR"]) / "report", "*")
)

# twister output: honour ZDOCS_TWISTER_OUT when the build sets it, else fall
# back to the workspace's own run. Absent input is a normal state — the
# directives soft-fail to a "not found" node.
if not twister_output_dir:
    twister_output_dir = str(Path(os.environ["ZDOCS_WEST_TOPDIR"]) / "twister-out")

needs_layouts = {
    "test_result": {
        "grid": "simple",
        "layout": {
            "head": [
                '<<meta("type_name")>> <<meta_id()>>: **<<meta("title")>>** '
                '<<collapse_button("meta", collapsed="icon:arrow-down-circle", '
                'visible="icon:arrow-right-circle", initial=False)>>'
            ],
            "meta": [
                '<<meta("test_module",    prefix="\\*\\*test module:\\*\\* ")>>',
                '<<meta("platform",       prefix="\\*\\*platform:\\*\\* ")>>',
                '<<meta("scenario",       prefix="\\*\\*scenario:\\*\\* ")>>',
                '<<meta("twister_id",     prefix="\\*\\*twister id:\\*\\* ")>>',
                '<<meta("execution_time", prefix="\\*\\*time:\\*\\* ", show_empty=True)>>',
                '<<meta("status",         prefix="\\*\\*status:\\*\\* ", show_empty=True)>>',
                '<<meta("reason",         prefix="\\*\\*reason:\\*\\* ")>>',
                '<<meta("depends_met",    prefix="\\*\\*depends met:\\*\\* ")>>',
                '<<meta("skip_class",     prefix="\\*\\*skip class:\\*\\* ")>>',
                "<<meta_links_all()>>",
            ],
        },
    }
}
needs_default_layout = "test_result"

# The adequacy needs of adequacy.rst (zdocs `testcoverage ... :layout:
# adequacy`) get their own layout: their fields are not the fields of a test
# result.
needs_layouts["adequacy"] = {
    "grid": "simple",
    "layout": {
        "head": [
            '<<meta("type_name")>> <<meta_id()>>: **<<meta("title")>>** '
            '<<collapse_button("meta", collapsed="icon:arrow-down-circle", '
            'visible="icon:arrow-right-circle", initial=False)>>'
        ],
        "meta": [
            '<<meta("verdict",        prefix="\\*\\*verdict:\\*\\* ", show_empty=True)>>',
            '<<meta("evidence",       prefix="\\*\\*evidence:\\*\\* ")>>',
            '<<meta("coverage_run",   prefix="\\*\\*coverage run:\\*\\* ")>>',
            '<<meta("judged_symbols", prefix="\\*\\*judged symbols:\\*\\* ")>>',
            '<<meta("symbol_hits",    prefix="\\*\\*symbol hits:\\*\\* ")>>',
            "<<meta_links_all()>>",
        ],
    },
}

# The per-test coverage run for adequacy.rst comes from ZDOCS_COVERAGE_OUT
# (zdocs sets coverage_output_dir). It has no fallback: without a run, the page
# says that no coverage run is configured.


def setup(app):
    app.add_css_file("css/custom.css")
    app.add_js_file("js/custom.js")
