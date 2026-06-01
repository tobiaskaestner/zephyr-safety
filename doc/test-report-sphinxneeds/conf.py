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
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

external_content_contents = [
    (DOC_BASE / "doc" / "test-report-sphinxneeds", "[!_]*"),
]

# -- sphinx-needs -------------------------------------------------------------

# Path to needs.json produced by the spec build — used by the testreport directive.
testspec_needs_json = str(
    ZEPHYR_BUILD / "deploy" / "test-specification-sphinxneeds" / "html" / "needs.json"
)

# Must mirror the spec's needs_fields so imported needs are extendable.
_str_field = {"schema": {"type": "string"}, "nullable": True}
needs_fields = {
    "test_id":                         {**_str_field, "description": "Stable test identifier (e.g. TSPEC-QUEUE-API-001)"},
    "suite":                           {**_str_field, "description": "Doxygen test suite group name"},
    "source_file":                     {**_str_field, "description": "Source file and line number"},
    "doxygen_url":                     {**_str_field, "description": "URL to Doxygen HTML member page"},
    "kernel_queue_status":             {**_str_field, "description": "Test result for kernel.queue scenario"},
    "kernel_queue_minimallibc_status": {**_str_field, "description": "Test result for kernel.queue.minimallibc scenario"},
}

needs_id_regex = r"^[A-Za-z][A-Za-z0-9_-]+"

# No needs_types — the report defines no needs of its own.

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
