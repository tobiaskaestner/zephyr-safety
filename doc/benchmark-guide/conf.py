# Benchmark Guide — zdocs conf.py shim.
#
# A plain Sphinx document: no sphinx-needs content of its own, no Doxygen
# input. The engine still loads its standard extensions (see zdocs_conf).
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["ZDOCS_CONF_DIR"])

from zdocs_conf import configure

configure(
    globals(),
    doc_dir=Path(__file__).resolve().parent,
    project="Zephyr Latency Benchmark Guide",
    author="Zephyr Project Contributors",
    copyright_holder="Zephyr Project Contributors",
)
