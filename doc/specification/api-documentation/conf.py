# API Documentation — zdocs conf.py shim.
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])

from zdocs_conf import configure

configure(
    globals(),
    doc_dir=Path(__file__).resolve().parent,
    project="Zephyr API Documentation (Safety Scope)",
    author="Zephyr Project Contributors",
    copyright_holder="Zephyr Project Contributors",
    extensions=[
        "sphinx_tabs.tabs",
        "sphinx.ext.todo",
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

# doxylink is supplied by the engine and its mapping comes from the registry —
# one role per `kind: doxygen` document, e.g. :dox_api:`k_queue_append`.
todo_include_todos = True
