# Architecture — zdocs conf.py shim.
#
# ZDOCS_CONF_DIR is exported into every sphinx-build by zdocs' sphinx.cmake and
# equals <engine>/sphinx. Deriving the engine root from it rather than from
# __file__ arithmetic is deliberate: external_content builds from a COPY of this
# directory, so relative paths out of the source tree do not survive.
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])

from zdocs_conf import configure

configure(
    globals(),
    doc_dir=Path(__file__).resolve().parent,
    project="Zephyr Software Architecture Documentation (Safety Scope)",
    author="Zephyr Project Contributors",
    copyright_holder="Zephyr Project Contributors",
    extensions=[
        "sphinx_tabs.tabs",
        "sphinx.ext.todo",
    ],
)

# The Safety Committee document is left out of a build without its sources
# (SAFETY_DOC_COMMITTEE in doc/CMakeLists.txt). The tag lets xref-test.rst
# link to it only when the registry has it.
if "committee" in intersphinx_mapping:
    tags.add("committee")

todo_include_todos = True

# The design elements are generated from the `.. design::` blocks in Zephyr's
# doc/kernel by the `design-gen` target — see doc/CMakeLists.txt — and copied
# in here as generated/design_elements.rst.
external_content_contents.append(
    (Path(os.environ["SAFETY_DESIGN_GEN_RST_DIR"]), "generated/*.rst")
)
