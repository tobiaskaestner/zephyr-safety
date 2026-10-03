# Requirements — zdocs conf.py shim.
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])

from zdocs_conf import configure

configure(
    globals(),
    doc_dir=Path(__file__).resolve().parent,
    project="Zephyr Requirements Documentation",
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

# The requirement pages are generated from the StrictDoc sources (doc/reqmgmt)
# by the `requirements-gen` target — see doc/CMakeLists.txt — and copied in here
# as generated/*.rst. Only the per-component pages: the generator's own
# index.rst links to traceability views that belong to Zephyr's doc build, not
# to this one; this document's index.rst takes its place.
external_content_contents.append(
    (Path(os.environ["SAFETY_REQ_GEN_RST_DIR"]), "generated/zephyr_*.rst")
)

# The coverage table per component (traceability/components.rst) is generated
# by the `component-gen` target from the component names of those pages.
external_content_contents.append(
    (Path(os.environ["SAFETY_COMPONENT_GEN_RST_DIR"]), "traceability/*.rst")
)
