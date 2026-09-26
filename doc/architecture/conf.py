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

todo_include_todos = True
