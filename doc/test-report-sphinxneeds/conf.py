# Configuration file for the Sphinx documentation builder.
# Test Report — sphinx-needs experiment (Route B).
# Build AFTER test-specification-sphinxneeds-html (needs needs.json from that output).
# Do NOT modify safety/doc/test-report/ — this is a parallel experiment.

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ZEPHYR_BASE = Path(os.getenv("ZEPHYR_BASE"))
DOC_BASE = Path(__file__).resolve().parents[2]
# OUTPUT_DIR is the HTML output dir (bdoc/deploy/<name>/html).
# Go 3 levels up to reach the bdoc root.
ZEPHYR_BUILD = Path(os.environ.get("OUTPUT_DIR")).resolve().parents[2]
BASE_URL = "http://localhost:8000/"

_REQ_HTML = ZEPHYR_BUILD / "deploy" / "requirements" / "html"


def _build_req_needs_stub() -> Path:
    """Convert requirements objects.inv → sphinx-needs external needs JSON.

    Identical to the function in test-specification-sphinxneeds/conf.py.
    Filters zep-srs-* labels from the intersphinx inventory and writes a
    minimal needs.json stub so that needs_external_needs can resolve
    outgoing verifies links from imported spec test_case needs.
    The stub is reused across incremental builds (regenerated only when
    the inventory is newer).
    """
    inv_path = _REQ_HTML / "objects.inv"
    json_path = _REQ_HTML / "objects.json"
    out_path = _REQ_HTML / "req-needs.json"

    if not inv_path.exists():
        sys.stderr.write(f"warning: requirements inventory not found: {inv_path}\n")
        return out_path

    if not json_path.exists() or json_path.stat().st_mtime < inv_path.stat().st_mtime:
        subprocess.run(
            ["sphobjinv", "co", "json", str(inv_path), "--overwrite"],
            check=True, capture_output=True,
        )

    with open(json_path) as f:
        inv_data = json.load(f)

    needs = {}
    for k, v in inv_data.items():
        if k in ("project", "version", "count"):
            continue
        if v["role"] != "label" or not re.match(r"^zep-srs-\d+-\d+$", v["name"]):
            continue
        name = v["name"]
        title = v["dispname"] if v["dispname"] not in ("-", name) else name
        uri = v["uri"].replace("$", name)
        docname = uri.split(".html")[0]
        needs[name] = {
            "id": name,
            "type": "requirement",
            "title": title,
            "content": "",
            "status": "approved",
            "docname": docname,
        }

    stub = {
        "current_version": "1.0",
        "versions": {"1.0": {"needs": needs, "needs_amount": len(needs)}},
    }
    with open(out_path, "w") as f:
        json.dump(stub, f, indent=2)

    return out_path


_req_needs_path = _build_req_needs_stub()

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
    "suite_title":    {**_str_field, "description": "Human-readable Doxygen group title for the suite"},
}

needs_id_regex = r"^[A-Za-z][A-Za-z0-9_-]+"

needs_types = [
    dict(directive="test_result",   title="Test Result",     prefix="TRESULT_", color="#FCE4D6", style="node"),
    dict(directive="test_case",     title="Test Case",       prefix="TCASE_",   color="#E2EFDA", style="node"),
    dict(directive="test_procedure", title="Test Procedure", prefix="TPROC_",   color="#D6E4F7", style="node"),
    dict(directive="requirement",   title="Requirement",     prefix="REQ_",     color="#FDEBD0", style="node"),
]

needs_links = {
    "verifies": {
        "description": "Test case verifies a requirement",
        "incoming": "verified by",
        "outgoing": "verifies",
    },
    "result_of": {
        "description": "Test result is an outcome of a test case",
        "incoming": "has results",
        "outgoing": "result of",
    },
    "covers": {
        "description": "Test result covers a requirement (derived from verifying test case)",
        "incoming": "covered by",
        "outgoing": "covers",
    },
}

needs_external_needs = [
    {
        "json_path": _testspec_needs_json,
        "base_url": BASE_URL + "test-specification-sphinxneeds/html",
        "version": "4.4.99",
    },
    {
        "json_path": str(_req_needs_path),
        "base_url": BASE_URL + "requirements/html",
        "version": "1.0",
    },
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

html_context = {
    "reference_links": {
        "Test Specification": BASE_URL + "test-specification-sphinxneeds/html",
        "Requirements": BASE_URL + "requirements/html",
    }
}

LATEX_DOC = os.getenv("LATEX_DOC", "test-report-sphinxneeds.tex")
latex_documents = [("index", LATEX_DOC, "", "", "manual")]

suppress_warnings = ["config.cache"]

# twister-out lives one level above the bdoc build root
twister_output_dir = str(ZEPHYR_BUILD.parent / "twister-out")

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
