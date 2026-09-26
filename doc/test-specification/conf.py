# Test Specification (hand-crafted) — zdocs conf.py shim (sandbox).
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])

from zdocs_conf import configure

configure(
    globals(),
    doc_dir=Path(__file__).resolve().parent,
    project="Zephyr Test Specification (hand-crafted)",
    author="Zephyr Project Contributors",
    copyright_holder="Zephyr Project Contributors",
    extensions=[
        "sphinx_tabs.tabs",
        "zephyr.kconfig",
        "zephyr.application",
        "zephyr.link-roles",
    ],
)

# This document's pages are hand-written RST that lives beside the tests.
external_content_contents += [
    (Path(os.environ["ZEPHYR_BASE"]) / "tests", "kernel/**/test-spec.rst"),
]
