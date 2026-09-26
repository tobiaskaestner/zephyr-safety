# Requirements — zdocs conf.py shim.
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])

from zdocs_conf import configure

# See the note in safety-committee/conf.py: downstream extensions are APPENDED.
sys.path.append(str(Path(__file__).resolve().parents[1] / "_extensions"))

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
        "strictdoc_runner",
    ],
)

# The StrictDoc requirements are a separate west project (reqmgmt), not part of
# this repository — hence the workspace-relative path rather than a repo-relative
# one. Phase 3 (S3) replaces this with a generator emitting `.. req::` needs.
strictdoc_source_dir = str(Path(os.environ["ZDOCS_WEST_TOPDIR"]) / "doc" / "reqmgmt" / "docs")
