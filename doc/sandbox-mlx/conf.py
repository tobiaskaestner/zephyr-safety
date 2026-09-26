# Sandbox: mlx.traceability — zdocs conf.py shim (sandbox: tooling experiment).
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])

from zdocs_conf import configure

configure(
    globals(),
    doc_dir=Path(__file__).resolve().parent,
    project="Sandbox: mlx.traceability",
    author="Zephyr Project Contributors",
    copyright_holder="Zephyr Project Contributors",
    extensions=[
        "sphinx_tabs.tabs",
        "zephyr.kconfig",
        "zephyr.application",
        "zephyr.link-roles",
    ],
)
