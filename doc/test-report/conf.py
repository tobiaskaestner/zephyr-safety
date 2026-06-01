# Configuration file for the Sphinx documentation builder.
# Test Report document — separate from Test Specification.
# Build AFTER test-specification-html so intersphinx can resolve labels.

import os
import re
import sys
from pathlib import Path

ZEPHYR_BASE = Path(os.getenv("ZEPHYR_BASE"))
DOC_BASE = Path(__file__).resolve().parents[2]
ZEPHYR_BUILD = Path(os.environ.get("OUTPUT_DIR")).resolve()
BASE_URL = "http://localhost:8000/"

sys.path.insert(0, str(ZEPHYR_BASE / "doc" / "_extensions"))
sys.path.insert(0, str(DOC_BASE / "doc" / "_extensions"))

project = "Zephyr Test Report"
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
    (DOC_BASE / "doc" / "test-report", "[!_]*"),
]

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

LATEX_DOC = os.getenv("LATEX_DOC", "test-report.tex")
latex_documents = [("index", LATEX_DOC, "", "", "manual")]

suppress_warnings = ["config.cache"]

# test-specification must be built first to produce objects.inv
intersphinx_mapping = {
    "testspec": (
        BASE_URL + "test-specification/html",
        ("../../deploy/test-specification/html/objects.inv", None),
    ),
    "req": (
        BASE_URL + "requirements/html",
        ("../../deploy/requirements/html/objects.inv", None),
    ),
}


def setup(app):
    app.add_css_file("css/custom.css")
    app.add_js_file("js/custom.js")
