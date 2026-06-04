# Configuration file for the Sphinx documentation builder.
# Test Report — sphinx-needs experiment (Route B).
# Build AFTER test-specification-sphinxneeds-html (needs needs.json from that output).
# Do NOT modify safety/doc/test-report/ — this is a parallel experiment.

import os
import re
import sys
from pathlib import Path

ZEPHYR_BASE = Path(os.getenv("ZEPHYR_BASE"))
DOC_BASE = Path(__file__).resolve().parents[2]
# OUTPUT_DIR is the HTML output dir (bdoc/deploy/<name>/html).
# Go 3 levels up to reach the bdoc root.
ZEPHYR_BUILD = Path(os.environ.get("OUTPUT_DIR")).resolve().parents[2]
BASE_URL = "http://localhost:8000/"

sys.path.insert(0, str(ZEPHYR_BASE / "doc" / "_extensions"))
sys.path.insert(0, str(DOC_BASE / "doc" / "_extensions"))

project = "Zephyr Test Report (sphinx-needs)"
copyright = "2025, Zephyr Project Contributors"
author = "Zephyr Project Contributors"

with open(ZEPHYR_BASE / "VERSION") as f:
    m = re.match(
        (
            r"^VERSION_MAJOR\s*=\s*(\d+)$\n"
            + r"^VERSION_MINOR\s*=\s*(\d+)$\n"
            + r"^PATCHLEVEL\s*=\s*(\d+)$\n"
            + r"^VERSION_TWEAK\s*=\s*\d+$\n"
            + r"^EXTRAVERSION\s*=\s*(.*)$"
        ),
        f.read(),
        re.MULTILINE,
    )
    if not m:
        version = "Unknown"
    else:
        major, minor, patch, extra = m.groups(1)
        version = ".".join((major, minor, patch))
        if extra:
            version += "-" + extra

release = version

extensions = [
    "sphinx_needs",
    "test_module",
    "sphinx_rtd_theme",
    "sphinx.ext.intersphinx",
    "sphinx_tabs.tabs",
    "zephyr.kconfig",
    "zephyr.application",
    "zephyr.link-roles",
    "zephyr.external_content",
]

templates_path = ["_templates"]
html_static_path = ["_static"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

external_content_contents = [
    (DOC_BASE / "doc" / "test-report-sphinxneeds", "[!_]*"),
]

# -- sphinx-needs -------------------------------------------------------------

_testspec_needs_json = str(
    ZEPHYR_BUILD / "deploy" / "test-specification-sphinxneeds" / "html" / "needs.json"
)

_str_field = {"schema": {"type": "string"}, "nullable": True}
needs_fields = {
    # test_result fields
    "platform":       {**_str_field, "description": "Target board (e.g. qemu_cortex_m3/ti_lm3s6965)"},
    "scenario":       {**_str_field, "description": "Twister scenario name (e.g. kernel.queue)"},
    "twister_id":     {**_str_field, "description": "Full test identifier from JUnit XML @name"},
    "execution_time": {**_str_field, "description": "Test execution time in seconds"},
    "reason":         {**_str_field, "description": "Failure or skip reason"},
    # spec test_case fields — declared so external needs from needs_external_needs load cleanly
    "test_function":  {**_str_field, "description": "C function name of the test case"},
    "test_module":    {**_str_field, "description": "Path to the test module (e.g. tests/kernel/queue)"},
    "suite":          {**_str_field, "description": "Doxygen test suite group name"},
}

needs_id_regex = r"^[A-Za-z][A-Za-z0-9_-]+"

needs_types = [
    dict(directive="test_result",   title="Test Result",     prefix="TRESULT_", color="#FCE4D6", style="node"),
    dict(directive="test_case",     title="Test Case",       prefix="TCASE_",   color="#E2EFDA", style="node"),
    dict(directive="test_procedure", title="Test Procedure", prefix="TPROC_",   color="#D6E4F7", style="node"),
    dict(directive="requirement",   title="Requirement",     prefix="REQ_",     color="#FDEBD0", style="node"),
]

needs_external_needs = [
    {
        "json_path": _testspec_needs_json,
        "base_url": BASE_URL + "test-specification-sphinxneeds/html",
        "version": "4.4.99",
    }
]

needs_layouts = {
    "test_result": {
        "grid": "simple",
        "layout": {
            "head": [
                '<<meta("type_name")>>: **<<meta("title")>>** '
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
                "<<meta_links_all()>>",
            ],
        },
    }
}
needs_default_layout = "test_result"

# -- HTML output --------------------------------------------------------------

html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "logo_only": True,
    "prev_next_buttons_location": None,
    "navigation_depth": 5,
}

html_baseurl = "https://docs.zephyrproject.org/latest/"
html_title = "Zephyr Project Documentation"
html_logo = str(ZEPHYR_BASE / "doc" / "_static" / "images" / "logo.svg")
html_favicon = str(ZEPHYR_BASE / "doc" / "_static" / "images" / "favicon.png")
html_last_updated_fmt = "%b %d, %Y"
html_domain_indices = False
html_split_index = True
html_show_sourcelink = False
html_show_sphinx = False

LATEX_DOC = os.getenv("LATEX_DOC", "test-report-sphinxneeds.tex")
latex_documents = [("index", LATEX_DOC, "", "", "manual")]

suppress_warnings = ["config.cache"]

# -- Intersphinx --------------------------------------------------------------

intersphinx_mapping = {
    "testspec": (
        BASE_URL + "test-specification-sphinxneeds/html",
        ("../../deploy/test-specification-sphinxneeds/html/objects.inv", None),
    ),
    "req": (
        BASE_URL + "requirements/html",
        ("../../deploy/requirements/html/objects.inv", None),
    ),
}


def setup(app):
    app.add_css_file("css/custom.css")
    app.add_js_file("js/custom.js")
