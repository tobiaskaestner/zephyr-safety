# Safety Committee — zdocs conf.py shim.
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])

from zdocs_conf import configure

# strictdoc_runner is a downstream (project-specific) extension; the engine does
# not ship it, so its directory has to be added AFTER zdocs_conf has put its own
# _extensions first — never before, or a stale local copy of an engine module
# would shadow the engine's.
sys.path.append(str(Path(__file__).resolve().parents[1] / "_extensions"))

configure(
    globals(),
    doc_dir=Path(__file__).resolve().parent,
    project="Zephyr Safety Committee Documentation",
    author="Zephyr Project Contributors",
    copyright_holder="Zephyr Project Contributors",
    extensions=[
        "sphinx_tabs.tabs",
        "zephyr.kconfig",
        "zephyr.application",
        "zephyr.link-roles",
        "strictdoc_runner",
    ],
)

# The committee's StrictDoc sources live in their own west project. Their
# project config declares the @plan_grammar alias every document imports.
strictdoc_source_dir = str(
    Path(os.environ["ZDOCS_WEST_TOPDIR"]) / "doc" / "safety-committee" / "FSM_and_Concept"
)
strictdoc_config = str(Path(strictdoc_source_dir) / "strictdoc_config.py")
